from django.db import models
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = CloudinaryField('image', default='https://res.cloudinary.com/djgau34yl/image/upload/v1/default_avatar.png')
    banner_url = models.URLField(blank=True, null=True, max_length=500)
    bio = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.user.username} Profile'
