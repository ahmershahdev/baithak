from django.contrib.auth.models import AbstractUser
from django.db import models


# A custom user model can only be swapped in before the first migration, so it exists now even
# though sign-up and sign-in come later in M1.
class User(AbstractUser):
    email = models.EmailField(unique=True)
