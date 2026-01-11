from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='movie-home'),
    path('movie/<int:movie_id>/', views.movie_detail, name='movie-detail'),
]
