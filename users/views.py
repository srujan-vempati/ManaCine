from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import UserRegisterForm, ProfileUpdateForm
from django.contrib.auth.decorators import login_required

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now login.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})

@login_required
def profile(request):
    if request.method == 'POST':
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        if p_form.is_valid():
            p_form.save()
            messages.success(request, f'Your account has been updated!')
            return redirect('profile')
    else:
        p_form = ProfileUpdateForm(instance=request.user.profile)

    # Fetch Stats
    from reviews.models import Review
    from movies.models import Favorite, Watched
    
    watched_count = Watched.objects.filter(user=request.user).count()
    watched_movies = Watched.objects.filter(user=request.user).order_by('-created_at')[:10] # Get recent 10
    
    reviews = Review.objects.filter(user=request.user)
    # reviews_count no longer primary metric for 'watched', but we can still show it or keep variable name if needed.
    # User wanted "Watched" stat to update when clicking Watch button.
    
    recent_reviews = reviews.order_by('-created_at')[:5]
    
    favorites = Favorite.objects.filter(user=request.user)
    favorites_count = favorites.count()

    context = {
        'p_form': p_form,
        'reviews_count': watched_count, # Mapping 'Watched' UI label to this count
        'recent_reviews': recent_reviews,
        'favorites': favorites,
        'favorites_count': favorites_count,
        'watched_movies': watched_movies
    }

    return render(request, 'users/profile.html', context)

@login_required
def set_banner(request, movie_id):
    from movies.services import TMDBService
    service = TMDBService()
    movie = service.get_movie_details(movie_id)
    
    if movie and movie.get('backdrop_url'):
        request.user.profile.banner_url = movie['backdrop_url']
        request.user.profile.save()
        messages.success(request, f"Profile banner updated to {movie['title']}!")
    else:
        messages.error(request, "Could not set banner from this movie.")
    
    return redirect('profile')
