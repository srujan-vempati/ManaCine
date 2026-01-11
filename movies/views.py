from django.shortcuts import render, redirect, get_object_or_404
from .services import TMDBService
from reviews.models import Review
from reviews.forms import ReviewForm
from django.contrib import messages

def home(request):
    service = TMDBService()
    movies = service.get_popular_telugu_movies()
    return render(request, 'movies/home.html', {'movies': movies})

def movie_detail(request, movie_id):
    service = TMDBService()
    movie = service.get_movie_details(movie_id)
    
    reviews = Review.objects.filter(movie_id=movie_id).order_by('-created_at')
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.movie_id = movie_id
            review.save()
            messages.success(request, 'Review posted!')
            return redirect('movie-detail', movie_id=movie_id)
    else:
        form = ReviewForm()

    return render(request, 'movies/detail.html', {
        'movie': movie, 
        'reviews': reviews,
        'form': form
    })
