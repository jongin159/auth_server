from django.db import models

# Create your models here.
class APIKEY(models.Model):
    apikey = models.TextField()

    def __str__(self):
        return self.apikey