import requests
import os

class TMDBService:
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
    
    def __init__(self):
        self.api_key = os.getenv('TMDB_API_KEY')

    def get_popular_telugu_movies(self):
        if not self.api_key:
            return []
        
        endpoint = f"{self.BASE_URL}/discover/movie"
        params = {
            'api_key': self.api_key,
            'with_original_language': 'te',
            'sort_by': 'popularity.desc',
            'page': 1
        }
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            movies = data.get('results', [])
            return self._format_movies(movies)
        except requests.RequestException:
            return []

    def get_movie_details(self, movie_id):
        if not self.api_key:
            return None
            
        endpoint = f"{self.BASE_URL}/movie/{movie_id}"
        params = {
            'api_key': self.api_key,
            'append_to_response': 'credits,videos'
        }
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            return self._format_movie_detail(response.json())
        except requests.RequestException:
            return None

    def search_telugu_movies(self, query):
        if not self.api_key:
            return []
            
        endpoint = f"{self.BASE_URL}/search/movie"
        params = {
            'api_key': self.api_key,
            'query': query,
            'language': 'te' 
        }
        # Note: TMDB search might return mixed languages even with language param,
        # but for specific filtering we might need client side or more logic.
        # But 'discover' handles it better. Search is tricky.
        # We can filter results in python.
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            movies = response.json().get('results', [])
            # Filter solely for 'te' original language?
            telugu_movies = [m for m in movies if m.get('original_language') == 'te']
            return self._format_movies(telugu_movies)
        except requests.RequestException:
            return []

    def _format_movies(self, movies_data):
        formatted = []
        for m in movies_data:
            poster_path = m.get('poster_path')
            formatted.append({
                'id': m.get('id'),
                'title': m.get('title'),
                'poster_url': f"{self.IMAGE_BASE_URL}{poster_path}" if poster_path else None,
                'release_date': m.get('release_date'),
                'rating': m.get('vote_average'),
                'overview': m.get('overview')
            })
        return formatted

    def _format_movie_detail(self, m):
        poster_path = m.get('poster_path')
        backdrop_path = m.get('backdrop_path')
        # Directors
        crew = m.get('credits', {}).get('crew', [])
        directors = [c['name'] for c in crew if c['job'] == 'Director']
        
        return {
            'id': m.get('id'),
            'title': m.get('title'),
            'poster_url': f"{self.IMAGE_BASE_URL}{poster_path}" if poster_path else None,
            'backdrop_url': f"{self.IMAGE_BASE_URL}{backdrop_path}" if backdrop_path else None,
            'release_date': m.get('release_date'),
            'rating': m.get('vote_average'),
            'overview': m.get('overview'),
            'runtime': m.get('runtime'),
            'genres': [g['name'] for g in m.get('genres', [])],
            'directors': directors
        }
