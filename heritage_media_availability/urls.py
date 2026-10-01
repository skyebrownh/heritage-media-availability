"""
URL routes for the Heritage Media Availability app.

config/urls.py includes this file at the site root, so '' here means "/".
"""

from django.urls import path

from . import views

# Namespacing lets templates say {% url 'heritage_media_availability:team_form' %}
# without clashing with URL names from Django's own apps.
app_name = 'heritage_media_availability'

urlpatterns = [
    path('', views.team_form, name='team_form'),
    path('thanks/', views.thanks, name='thanks'),
    # TF-9: JSON used by the form's script to pre-fill an earlier submission.
    path('last-submission/', views.last_submission, name='last_submission'),
]
