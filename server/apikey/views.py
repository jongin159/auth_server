from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
from apikey.models import APIKEY

def index(request):
    return HttpResponse(APIKEY.objects.all())