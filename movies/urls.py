from django.urls import path
from . import views
from reviews import views as review_views

urlpatterns = [
    path('', views.home, name='movie-home'),
    path('movie/<int:movie_id>/', views.movie_detail, name='movie-detail'),
    path('toggle-favorite/<int:movie_id>/', views.toggle_favorite, name='toggle-favorite'),
    path('toggle-watched/<int:movie_id>/', views.toggle_watched, name='toggle-watched'),
    path('quiz/<int:movie_id>/', views.take_quiz, name='take-quiz'),
    path('movie/<int:movie_id>/review/', review_views.add_review, name='add-review'),
    path('person/<int:person_id>/', views.person_detail, name='person-detail'),
]
