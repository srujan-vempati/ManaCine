from django.shortcuts import render, redirect, get_object_or_404
from .services import TMDBService
from reviews.models import Review
from reviews.forms import ReviewForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def home(request):
    service = TMDBService()
    query = request.GET.get('q')
    
    
    context = {'query': query}
    
    choice_list = []
    
    if query:
        context['search_results'] = service.search_telugu_movies(query)
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
        score = 0
        total = 2
        
        quiz_data = request.session.get(f'quiz_{movie_id}')
        if not quiz_data:
            messages.error(request, "Quiz session expired. Please refresh.")
            return redirect('take-quiz', movie_id=movie_id)

        for i, q in enumerate(quiz_data):
            user_answer = request.POST.get(f'question_{i}')
            if user_answer == q['correct_answer']:
                score += 1
        
        if score == total:
            # Success!
            Watched.objects.create(user=request.user, movie_id=movie_id)
            if f'quiz_{movie_id}' in request.session:
                del request.session[f'quiz_{movie_id}']
            
            messages.success(request, f"Correct! You scored {score}/{total}. Movie marked as Watched.")
            return redirect('movie-detail', movie_id=movie_id)
        else:
            messages.error(request, f"Failed. You scored {score}/{total}. You need 2/2 correct to verify.")
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
        
        print(f"DEBUG: Rendering Quiz with data: {quiz_data}") # Check structure here
        return render(request, 'movies/quiz.html', {'movie': movie, 'questions': quiz_data})

def person_detail(request, person_id):
    service = TMDBService()
    person = service.get_person_details(person_id)
    return render(request, 'movies/person_detail.html', {'person': person})
