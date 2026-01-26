import requests
import os
from django.conf import settings
from django.core.cache import cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class TMDBService:
    def __init__(self):
        self.api_key = os.environ.get('TMDB_API_KEY')
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p/w500"
        self.backdrop_base_url = "https://image.tmdb.org/t/p/original"
        
        # Configure Retries
        self.session = requests.Session()
        # Increased retries and backoff for better reliability
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def fetch_parallel(self, tasks):
        # Helper for parallel execution
        # tasks: list of (method, args)
        from concurrent.futures import ThreadPoolExecutor
        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_key = {executor.submit(func, *args): key for key, func, args in tasks}
            for future in future_to_key:
                key = future_to_key[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    print(f"Error in parallel fetch for {key}: {e}")
                    results[key] = []
        return results

    def _fetch_movies(self, url, params, cache_key):
        # Helper to avoid repetition
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            movies = []
            for item in data.get('results', []):
                # Ensure strictly Telugu where applicable/possible
                if params.get('with_original_language') == 'te' and item.get('original_language') != 'te':
                    continue

                movies.append({
                    'id': item['id'],
                    'title': item['title'],
                    'poster_url': f"{self.image_base_url}{item['poster_path']}" if item.get('poster_path') else None,
                    'release_date': item.get('release_date', 'N/A'),
                    'overview': item.get('overview', ''),
                    'rating': item.get('vote_average', 0)
                })
            
            cache.set(cache_key, movies, 3600) # 1 hour
            return movies
        except requests.exceptions.RequestException as e:
            print(f"Error fetching movies for {cache_key}: {e}")
            return []

    def get_popular_telugu_movies(self):
        if not self.api_key: return []
        return self._fetch_movies(
            f"{self.base_url}/discover/movie",
            {'api_key': self.api_key, 'with_original_language': 'te', 'sort_by': 'popularity.desc', 'page': 1},
            'popular_telugu_movies'
        )

    def get_recent_releases(self):
        if not self.api_key: return []
        # 'now_playing' or sort by release_date.desc
        # TMDB discover is good for strict language filtering
        return self._fetch_movies(
            f"{self.base_url}/discover/movie",
            {
                'api_key': self.api_key, 
                'with_original_language': 'te', 
                'sort_by': 'primary_release_date.desc', 
                'primary_release_date.lte': '2026-01-11', # Ideally dynamic today's date
                'vote_count.gte': 0, # get everything
                'page': 1
            },
            'recent_telugu_movies'
        )

    def get_top_rated_telugu_movies(self):
        if not self.api_key: return []
        return self._fetch_movies(
            f"{self.base_url}/discover/movie",
            {
                'api_key': self.api_key, 
                'with_original_language': 'te', 
                'sort_by': 'vote_average.desc', 
                'vote_count.gte': 10, # Filter out noise
                'page': 1
            },
            'top_rated_telugu_movies'
        )

    def get_movie_details(self, movie_id):
        if not self.api_key:
            return None

        # Check Cache
        cache_key = f'movie_details_v2_{movie_id}' # v2 to invalidate old structure
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
            
        url = f"{self.base_url}/movie/{movie_id}"
        params = {
            'api_key': self.api_key,
            'append_to_response': 'credits,videos,external_ids,watch/providers'
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Process Cast
            cast = []
            for member in data.get('credits', {}).get('cast', [])[:15]: # Top 15
                cast.append({
                    'id': member['id'],
                    'name': member['name'],
                    'character': member['character'],
                    'profile_url': f"{self.image_base_url}{member['profile_path']}" if member.get('profile_path') else None
                })

            # Process Directors
            directors = []
            director_ids = []
            for crew in data.get('credits', {}).get('crew', []):
                 if crew['job'] == 'Director':
                     directors.append({'id': crew['id'], 'name': crew['name']})
                     director_ids.append(str(crew['id']))

            # Process Genres
            genres = []
            for g in data.get('genres', []):
                genres.append(g['name'])

            # Process Watch Providers (India - IN)
            providers = {}
            wp = data.get('watch/providers', {}).get('results', {}).get('IN', {})
            if wp:
                # Prioritize Flatrate (Streaming) -> Rent -> Buy
                if 'flatrate' in wp:
                    providers['stream'] = [{'name': p['provider_name'], 'logo': f"{self.image_base_url}{p['logo_path']}"} for p in wp['flatrate']]
                if 'rent' in wp:
                    providers['rent'] = [{'name': p['provider_name'], 'logo': f"{self.image_base_url}{p['logo_path']}"} for p in wp['rent']]
                providers['link'] = wp.get('link')

            # Fetch Similar (Strict Telugu + Same Director/Cast)
            similar = []
            people_ids = director_ids[:1] + [c['id'] for c in cast[:2]]
            people_str = "|".join(str(p) for p in people_ids if p)

            if people_str:
                similar_url = f"{self.base_url}/discover/movie"
                similar_params = {
                    'api_key': self.api_key,
                    'with_original_language': 'te',
                    'with_people': people_str, 
                    'sort_by': 'popularity.desc',
                    'page': 1,
                }
                try:
                     s_resp = self.session.get(similar_url, params=similar_params, timeout=5)
                     s_data = s_resp.json()
                     for item in s_data.get('results', [])[:12]:
                         if item['id'] == movie_id: continue # Skip self
                         similar.append({
                            'id': item['id'],
                            'title': item['title'],
                            'poster_url': f"{self.image_base_url}{item['poster_path']}" if item.get('poster_path') else None,
                            'rating': item.get('vote_average', 0)
                        })
                except Exception as e:
                    print(f"Error fetching refined similar: {e}")

            movie_data = {
                'id': data['id'],
                'title': data['title'],
                'overview': data.get('overview', ''),
                'poster_url': f"{self.image_base_url}{data['poster_path']}" if data.get('poster_path') else None,
                'backdrop_url': f"{self.backdrop_base_url}{data['backdrop_path']}" if data.get('backdrop_path') else None,
                'release_date': data.get('release_date', 'N/A'),
                'runtime': data.get('runtime', 0),
                'rating': data.get('vote_average', 0),
                'imdb_id': data.get('external_ids', {}).get('imdb_id'),
                'genres': genres,
                'directors': directors,
                'cast': cast,
                'similar': similar,
                'providers': providers
            }
            
            cache.set(cache_key, movie_data, 86400)
            return movie_data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching movie details: {e}")
            return None

    def get_person_details(self, person_id):
        if not self.api_key: return None
        
        cache_key = f'person_details_{person_id}'
        cached = cache.get(cache_key)
        if cached: return cached

        url = f"{self.base_url}/person/{person_id}"
        params = {
            'api_key': self.api_key,
            'append_to_response': 'movie_credits'
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Process Filmography
            # Combine cast and crew? Or just cast? Usually cast is what people want.
            # Let's do Cast + Directing credits
            
            credits = data.get('movie_credits', {})
            filmography = []
            
            # Cast credits
            for item in credits.get('cast', []):
                 filmography.append({
                     'id': item['id'],
                     'title': item.get('title'),
                     'poster_url': f"{self.image_base_url}{item['poster_path']}" if item.get('poster_path') else None,
                     'character': item.get('character'),
                     'year': item.get('release_date', '9999')[:4] if item.get('release_date') else 'N/A',
                     'rating': item.get('vote_average', 0),
                     'role': 'Actor'
                 })
                 
            # Crew credits (Director only to avoid noise)
            for item in credits.get('crew', []):
                if item.get('job') == 'Director':
                     filmography.append({
                     'id': item['id'],
                     'title': item.get('title'),
                     'poster_url': f"{self.image_base_url}{item['poster_path']}" if item.get('poster_path') else None,
                     'job': 'Director',
                     'year': item.get('release_date', '9999')[:4] if item.get('release_date') else 'N/A',
                     'rating': item.get('vote_average', 0),
                     'role': 'Director'
                 })

            # Sort by year desc
            filmography.sort(key=lambda x: x['year'], reverse=True)

            person_data = {
                'id': data['id'],
                'name': data['name'],
                'biography': data.get('biography', ''),
                'birthday': data.get('birthday', 'N/A'),
                'place_of_birth': data.get('place_of_birth', 'N/A'),
                'profile_url': f"{self.backdrop_base_url}{data['profile_path']}" if data.get('profile_path') else None,
                'movies': filmography
            }
            
            cache.set(cache_key, person_data, 86400)
            return person_data

        except Exception as e:
            print(f"Error fetching person: {e}")
            return None

    def search_telugu_movies(self, query):
        if not self.api_key:
            return []
            
        endpoint = f"{self.base_url}/search/movie"
        params = {
            'api_key': self.api_key,
            'query': query,
            # 'language': 'te'  # TMDB search doesn't strictly filter by lang param alone often
        }

        try:
            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            movies = []
            for item in data.get('results', []):
                # Filter strictly for Telugu content
                if item.get('original_language') != 'te': 
                    continue
                
                movies.append({
                    'id': item['id'],
                    'title': item['title'],
                    'poster_url': f"{self.image_base_url}{item['poster_path']}" if item.get('poster_path') else None,
                    'release_date': item.get('release_date', 'N/A'),
                    'overview': item.get('overview', ''),
                    'rating': item.get('vote_average', 0)
                })
            return movies
        except requests.exceptions.RequestException as e:
            print(f"Error searching movies: {e}")
            return []

    def get_movies_by_genre(self, genre_id):
        if not self.api_key: return []
        return self._fetch_movies(
            f"{self.base_url}/discover/movie",
            {
                'api_key': self.api_key, 
                'with_original_language': 'te', 
                'with_genres': genre_id,
                'sort_by': 'popularity.desc', 
                'page': 1
            },
            f'genre_{genre_id}_movies'
        )
