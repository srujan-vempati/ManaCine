from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Review
from .forms import ReviewForm

@login_required
def add_review(request, movie_id):
    from movies.models import Watched # Import here to avoid circular import if any
    
    if request.method == 'POST':
        # Enforce Watched check
        if not Watched.objects.filter(user=request.user, movie_id=movie_id).exists():
            messages.error(request, 'You must mark this movie as "Watched" before you can review it.')
            return redirect('movie-detail', movie_id=movie_id)

        form = ReviewForm(request.POST)
        if form.is_valid():
            # Check if user already reviewed?
            existing_review = Review.objects.filter(user=request.user, movie_id=movie_id).first()
            if existing_review:
                messages.warning(request, 'You have already reviewed this movie. Review updated.')
                existing_review.content = form.cleaned_data['content']
                existing_review.rating = form.cleaned_data['rating']
                existing_review.save()
            else:
                review = form.save(commit=False)
                review.user = request.user
                review.movie_id = movie_id
                review.save()
                messages.success(request, 'Review posted successfully!')
    
    return redirect('movie-detail', movie_id=movie_id)
