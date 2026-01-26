from django.shortcuts import render, redirect, get_object_or_404
from .services import TMDBService
from reviews.models import Review
from reviews.forms import ReviewForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def home(request):
    service = TMDBService()
    query = request.GET.get('q')
    genre_id = request.GET.get('genre')
    
    context = {'query': query, 'genre': genre_id}
    
    # Common Telugu Genres
    genres_data = [
        {'id': 28, 'name': 'Action'},
        {'id': 35, 'name': 'Comedy'},
        {'id': 18, 'name': 'Drama'},
        {'id': 10749, 'name': 'Romance'},
        {'id': 53, 'name': 'Thriller'},
        {'id': 27, 'name': 'Horror'},
        {'id': 10751, 'name': 'Family'}
    ]
    
    # Mark active
    for g in genres_data:
        g['active'] = (str(g['id']) == str(genre_id)) if genre_id else False
        
    context['genres'] = genres_data
    
    if query:
        context['search_results'] = service.search_telugu_movies(query)
    elif genre_id:
        context['search_results'] = service.get_movies_by_genre(genre_id)
        context['is_genre_filter'] = True
        # Find genre name
        for g in context['genres']:
            if str(g['id']) == str(genre_id):
                context['genre_name'] = g['name']
                break
    else:
        # Parallel Fetch for Instant Load
        tasks = [
            ('recent', service.get_recent_releases, []),
            ('top', service.get_top_rated_telugu_movies, []),
            ('popular', service.get_popular_telugu_movies, [])
        ]
        results = service.fetch_parallel(tasks)
        
        context['recent_releases'] = results.get('recent', [])
        context['top_rated'] = results.get('top', [])
        context['popular_movies'] = results.get('popular', [])
        
    return render(request, 'movies/home.html', context)

def movie_detail(request, movie_id):
    service = TMDBService()
    movie = service.get_movie_details(movie_id)
    
    reviews = Review.objects.filter(movie_id=movie_id).order_by('-created_at')
    
    is_favorite = False
    is_watched = False
    if request.user.is_authenticated:
        from movies.models import Favorite, Watched
        is_favorite = Favorite.objects.filter(user=request.user, movie_id=movie_id).exists()
        is_watched = Watched.objects.filter(user=request.user, movie_id=movie_id).exists()
    
    
    form = ReviewForm()


    return render(request, 'movies/detail.html', {
        'movie': movie, 
        'reviews': reviews,
        'form': form,
        'is_favorite': is_favorite,
        'is_watched': is_watched
    })

@login_required
def toggle_favorite(request, movie_id):
    from movies.models import Favorite
    from movies.services import TMDBService
    
    favorite, created = Favorite.objects.get_or_create(user=request.user, movie_id=movie_id)
    if not created:
        favorite.delete()
        messages.success(request, 'Removed from favorites.')
    else:
        # Fetch metadata to save
        service = TMDBService()
        movie = service.get_movie_details(movie_id)
        if movie:
            favorite.title = movie.get('title')
            favorite.poster_url = movie.get('poster_url')
            favorite.save()
        messages.success(request, 'Added to favorites!')
    
    return redirect('movie-detail', movie_id=movie_id)

@login_required
def toggle_watched(request, movie_id):
    from movies.models import Watched
    
    watched_item = Watched.objects.filter(user=request.user, movie_id=movie_id).first()
    
    if watched_item:
        # If already watched, just remove it (Unwatch)
        watched_item.delete()
        messages.info(request, "Movie removed from watched list.")
        return redirect('movie-detail', movie_id=movie_id)
    else:
        # If adding, redirect to Quiz!
        return redirect('take-quiz', movie_id=movie_id)

@login_required
def take_quiz(request, movie_id):
    from .quiz_service import QuizService
    from movies.models import Watched
    
    # Check if already watched
    if Watched.objects.filter(user=request.user, movie_id=movie_id).exists():
        messages.info(request, "You have already watched this movie.")
        return redirect('movie-detail', movie_id=movie_id)

    # Fetch movie details
    service = TMDBService()
    movie = service.get_movie_details(movie_id)
    if not movie:
        messages.error(request, "Movie not found.")
        return redirect('home')

    if request.method == 'POST':
        # Verify Answers
        quiz_data = request.session.get(f'quiz_{movie_id}')
        if not quiz_data:
            messages.error(request, "Quiz session expired. Please refresh.")
            return redirect('take-quiz', movie_id=movie_id)
            
        score = 0
        total = len(quiz_data)
        


        for i, q in enumerate(quiz_data):
            user_answer = request.POST.get(f'question_{i}')
            correct_answer = q.get('correct_answer')
            
            # Use strip() to handle potential whitespace issues
            if user_answer and correct_answer and user_answer.strip() == correct_answer.strip():
                score += 1
        
        if score == total:
            # Success! Save with metadata
            service = TMDBService()
            movie = service.get_movie_details(movie_id)
            
            watched = Watched.objects.create(user=request.user, movie_id=movie_id)
            if movie:
                watched.title = movie.get('title')
                watched.poster_url = movie.get('poster_url')
                watched.save()
            
            if f'quiz_{movie_id}' in request.session:
                del request.session[f'quiz_{movie_id}']
            
            messages.success(request, f"Correct! Movie marked as Watched.")
            return redirect('movie-detail', movie_id=movie_id)
        else:
            # Failed - Force regenerate
            if f'quiz_{movie_id}' in request.session:
                del request.session[f'quiz_{movie_id}']
            messages.error(request, f"Incorrect answer. Generating a new question...")
            return redirect('take-quiz', movie_id=movie_id)

    else:
        # GET - Load Quiz
        quiz_data = request.session.get(f'quiz_{movie_id}')
        
        # Check if stored quiz is the "Fallback" version (starts with "Have you watched")
        # If so, force new generation because we likely fixed the API now.
        if quiz_data and len(quiz_data) > 0:
             first_q = quiz_data[0].get('question', '')
             # Clear if fallback ("Have you watched") OR Backup ("Who directed", "In which year")
             if "Have you watched" in first_q or "Who directed" in first_q or "In which year" in first_q:
                 print("DEBUG: Detected Backup/Fallback quiz in session. Forcing AI regeneration.")
                 quiz_data = None # Force null to regenerate
        
        if not quiz_data:
            quiz_service = QuizService()
            quiz_data = quiz_service.generate_quiz(movie['title'], movie['overview'])
            
            # User explicit request: "story questions only".
            # If AI fails, do NOT show metadata fallback.
            if not quiz_data:
                print("DEBUG: AI generation failed. Returning error instead of backup.")
                messages.warning(request, "AI is currently busy generating story questions. Please try again in 5 seconds.")
                return redirect('movie-detail', movie_id=movie_id)
            
            # CRITICAL FIX: Store in session
            request.session[f'quiz_{movie_id}'] = quiz_data
            request.session.save()
            print(f"DEBUG: Saved quiz to session for movie {movie_id}")
        
        print(f"DEBUG: Rendering Quiz with data: {quiz_data}") # Check structure here
        return render(request, 'movies/quiz.html', {'movie': movie, 'questions': quiz_data})

@login_required
def fan_corner(request):
    from django.contrib.auth.models import User
    from django.db.models import Count
    from movies.models import Watched

    # Leaderboard: Top 10 users with most watched movies
    leaderboard = User.objects.annotate(
        watched_count=Count('watched')
    ).order_by('-watched_count')[:10]
    
    # User's own stats
    user_stats = {
        'count': Watched.objects.filter(user=request.user).count(),
        'rank': list(leaderboard).index(request.user) + 1 if request.user in leaderboard else 'N/A'
    }

    return render(request, 'movies/fan_corner.html', {
        'leaderboard': leaderboard,
        'user_stats': user_stats
    })

def person_detail(request, person_id):
    service = TMDBService()
    person = service.get_person_details(person_id)
    return render(request, 'movies/person_detail.html', {'person': person})
