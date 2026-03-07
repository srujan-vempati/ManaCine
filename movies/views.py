from django.shortcuts import render, redirect, get_object_or_404
from .services import TMDBService
from reviews.models import Review
from reviews.forms import ReviewForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg, Max, Min
from django.utils import timezone
from datetime import timedelta

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
    user_review = None
    if request.user.is_authenticated:
        from movies.models import Favorite, Watched
        is_favorite = Favorite.objects.filter(user=request.user, movie_id=movie_id).exists()
        is_watched = Watched.objects.filter(user=request.user, movie_id=movie_id).exists()
        user_review = Review.objects.filter(user=request.user, movie_id=movie_id).first()
    
    form = ReviewForm()

    return render(request, 'movies/detail.html', {
        'movie': movie, 
        'reviews': reviews,
        'form': form,
        'is_favorite': is_favorite,
        'is_watched': is_watched,
        'user_review': user_review,
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

            # Award FDFS Badge check
            release_date_str = movie.get('release_date')
            if release_date_str and release_date_str != 'N/A':
                try:
                    from datetime import datetime
                    from django.utils import timezone
                    release_date = datetime.strptime(release_date_str, '%Y-%m-%d').date()
                    now = timezone.now().date()
                    days_diff = (now - release_date).days
                    if 0 <= days_diff <= 7:
                        request.user.profile.fdfs_badge = True
                        request.user.profile.save()
                        messages.success(request, "Congratulations! You earned the FDFS Badge! 🎉")
                except ValueError:
                    pass

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
            
            watches_exist = Watched.objects.filter(user=request.user, movie_id=movie_id).exists()
            if not watches_exist:
                watched = Watched.objects.create(user=request.user, movie_id=movie_id)
                if movie:
                    watched.title = movie.get('title')
                    watched.poster_url = movie.get('poster_url')
                    watched.save()
                    
                    # Award FDFS Badge check
                    release_date_str = movie.get('release_date')
                    if release_date_str and release_date_str != 'N/A':
                        try:
                            from datetime import datetime
                            from django.utils import timezone
                            release_date = datetime.strptime(release_date_str, '%Y-%m-%d').date()
                            now = timezone.now().date()
                            days_diff = (now - release_date).days
                            if 0 <= days_diff <= 7:
                                request.user.profile.fdfs_badge = True
                                request.user.profile.save()
                                messages.success(request, "Congratulations! You earned the FDFS Badge! 🎉")
                        except ValueError:
                            pass
            
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


@staff_member_required
def admin_dashboard(request):
    from django.contrib.auth.models import User
    from movies.models import Favorite, Watched
    from django.db.models.functions import TruncDate, TruncMonth

    now = timezone.now()
    today = now.date()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # ── User Analytics ──────────────────────────────────────────────
    total_users = User.objects.count()
    active_users = User.objects.filter(last_login__gte=thirty_days_ago).count()
    new_users_7d = User.objects.filter(date_joined__gte=seven_days_ago).count()
    new_users_30d = User.objects.filter(date_joined__gte=thirty_days_ago).count()
    staff_users = User.objects.filter(is_staff=True).count()
    superusers = User.objects.filter(is_superuser=True).count()
    inactive_users = total_users - active_users

    # Users registered per day (last 14 days)
    user_growth = (
        User.objects
        .filter(date_joined__gte=now - timedelta(days=14))
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    # ── Review Analytics ─────────────────────────────────────────────
    total_reviews = Review.objects.count()
    reviews_7d = Review.objects.filter(created_at__gte=seven_days_ago).count()
    avg_rating = Review.objects.aggregate(avg=Avg('rating'))['avg'] or 0
    avg_music = Review.objects.aggregate(avg=Avg('music_rating'))['avg'] or 0
    avg_direction = Review.objects.aggregate(avg=Avg('direction_rating'))['avg'] or 0
    avg_acting = Review.objects.aggregate(avg=Avg('acting_rating'))['avg'] or 0
    avg_cinematography = Review.objects.aggregate(avg=Avg('cinematography_rating'))['avg'] or 0

    # Rating distribution
    rating_distribution = (
        Review.objects
        .values('rating')
        .annotate(count=Count('id'))
        .order_by('rating')
    )
    rating_dist_map = {r['rating']: r['count'] for r in rating_distribution}
    rating_dist_list = [rating_dist_map.get(i, 0) for i in range(1, 6)]

    # Most reviewed movies
    most_reviewed_movies = (
        Review.objects
        .values('movie_id')
        .annotate(review_count=Count('id'), avg_rating=Avg('rating'))
        .order_by('-review_count')[:10]
    )

    # Top reviewers
    top_reviewers = (
        User.objects
        .annotate(review_count=Count('review'))
        .filter(review_count__gt=0)
        .order_by('-review_count')[:10]
    )

    # ── Favorites Analytics ───────────────────────────────────────────
    total_favorites = Favorite.objects.count()
    favorites_7d = Favorite.objects.filter(created_at__gte=seven_days_ago).count()

    most_favorited = (
        Favorite.objects
        .values('movie_id', 'title')
        .annotate(fav_count=Count('id'))
        .order_by('-fav_count')[:10]
    )

    users_with_most_favorites = (
        User.objects
        .annotate(fav_count=Count('favorite'))
        .filter(fav_count__gt=0)
        .order_by('-fav_count')[:10]
    )

    # ── Watched Analytics ─────────────────────────────────────────────
    total_watched = Watched.objects.count()
    watched_7d = Watched.objects.filter(created_at__gte=seven_days_ago).count()

    most_watched_movies = (
        Watched.objects
        .values('movie_id', 'title')
        .annotate(watch_count=Count('id'))
        .order_by('-watch_count')[:10]
    )

    top_watchers = (
        User.objects
        .annotate(watch_count=Count('watched'))
        .filter(watch_count__gt=0)
        .order_by('-watch_count')[:10]
    )

    # ── FDFS Badge holders ────────────────────────────────────────────
    from users.models import Profile
    fdfs_badge_count = Profile.objects.filter(fdfs_badge=True).count()
    fdfs_badge_holders = Profile.objects.filter(fdfs_badge=True).select_related('user')[:20]

    # ── Recent Activity ───────────────────────────────────────────────
    recent_reviews_list = Review.objects.select_related('user').order_by('-created_at')[:15]
    recent_favorites_list = Favorite.objects.select_related('user').order_by('-created_at')[:15]
    recent_watched_list = Watched.objects.select_related('user').order_by('-created_at')[:15]
    recent_users_list = User.objects.order_by('-date_joined')[:15]

    # ── All Users Management ──────────────────────────────────────────
    search_user = request.GET.get('search_user', '').strip()
    if search_user:
        all_users = User.objects.filter(
            username__icontains=search_user
        ).annotate(
            review_count=Count('review'),
            fav_count=Count('favorite'),
            watch_count=Count('watched')
        ).order_by('-date_joined')
    else:
        all_users = User.objects.annotate(
            review_count=Count('review'),
            fav_count=Count('favorite'),
            watch_count=Count('watched')
        ).order_by('-date_joined')[:50]

    # Handle admin actions (toggle staff / delete user)
    if request.method == 'POST':
        action = request.POST.get('action')
        target_user_id = request.POST.get('user_id')
        if target_user_id:
            try:
                target_user = User.objects.get(pk=target_user_id)
                if action == 'toggle_staff' and not target_user.is_superuser:
                    target_user.is_staff = not target_user.is_staff
                    target_user.save()
                    messages.success(request, f"Staff status updated for {target_user.username}.")
                elif action == 'delete_user' and not target_user.is_superuser and target_user != request.user:
                    target_user.delete()
                    messages.success(request, f"User deleted.")
                elif action == 'toggle_active' and not target_user.is_superuser:
                    target_user.is_active = not target_user.is_active
                    target_user.save()
                    messages.success(request, f"Active status updated for {target_user.username}.")
            except User.DoesNotExist:
                messages.error(request, "User not found.")
        return redirect('admin-dashboard')

    context = {
        # User stats
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'new_users_7d': new_users_7d,
        'new_users_30d': new_users_30d,
        'staff_users': staff_users,
        'superusers': superusers,
        'user_growth': list(user_growth),
        # Review stats
        'total_reviews': total_reviews,
        'reviews_7d': reviews_7d,
        'avg_rating': round(avg_rating, 2),
        'avg_music': round(avg_music, 2),
        'avg_direction': round(avg_direction, 2),
        'avg_acting': round(avg_acting, 2),
        'avg_cinematography': round(avg_cinematography, 2),
        'rating_dist_list': rating_dist_list,
        'most_reviewed_movies': most_reviewed_movies,
        'top_reviewers': top_reviewers,
        # Favorites stats
        'total_favorites': total_favorites,
        'favorites_7d': favorites_7d,
        'most_favorited': most_favorited,
        'users_with_most_favorites': users_with_most_favorites,
        # Watched stats
        'total_watched': total_watched,
        'watched_7d': watched_7d,
        'most_watched_movies': most_watched_movies,
        'top_watchers': top_watchers,
        # FDFS
        'fdfs_badge_count': fdfs_badge_count,
        'fdfs_badge_holders': fdfs_badge_holders,
        # Recent activity
        'recent_reviews_list': recent_reviews_list,
        'recent_favorites_list': recent_favorites_list,
        'recent_watched_list': recent_watched_list,
        'recent_users_list': recent_users_list,
        # User management
        'all_users': all_users,
        'search_user': search_user,
        'now': now,
    }

    return render(request, 'movies/admin_dashboard.html', context)
