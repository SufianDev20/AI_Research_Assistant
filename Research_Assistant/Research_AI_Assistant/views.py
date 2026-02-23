from django.shortcuts import render
from django.conf import settings
from pyalex import config

config.email = settings.OPENALEX_EMAIL

# Create your views here.
