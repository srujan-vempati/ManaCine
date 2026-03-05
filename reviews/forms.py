from django import forms
from .models import Review

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'content', 'music_rating', 'direction_rating', 'acting_rating', 'cinematography_rating']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Write your review here...'}),
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'music_rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'direction_rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'acting_rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'cinematography_rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
        }
