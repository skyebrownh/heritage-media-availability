"""
Views (page handlers) for the Heritage Media Availability app.

Week 1 only has a placeholder home page, which proves the app runs locally
and on Railway. The real team form (TF-*) replaces it in Week 2.
"""

from django.shortcuts import render


def home(request):
    """Show a simple placeholder page at the site root."""
    return render(request, 'heritage_media_availability/home.html')
