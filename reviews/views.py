from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Review
from .forms import ReviewForm

@login_required
def add_review(request, movie_id):
    from movies.models import Watched  # Import here to avoid circular import if any

    if request.method == 'POST':
        # Enforce Watched check
        if not Watched.objects.filter(user=request.user, movie_id=movie_id).exists():
            messages.error(request, 'You must mark this movie as "Watched" before you can review it.')
            return redirect('movie-detail', movie_id=movie_id)

        # Block duplicate reviews — user must use edit instead
        if Review.objects.filter(user=request.user, movie_id=movie_id).exists():
            messages.warning(request, 'You have already reviewed this movie. Use the edit option to update your review.')
            return redirect('movie-detail', movie_id=movie_id)

        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.movie_id = movie_id
            review.save()
            messages.success(request, 'Review posted successfully!')

    return redirect('movie-detail', movie_id=movie_id)


@login_required
def edit_review(request, review_id):
    review = get_object_or_404(Review, id=review_id, user=request.user)

    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your review has been updated!')
        else:
            messages.error(request, 'There was an error updating your review.')

    return redirect('movie-detail', movie_id=review.movie_id)
