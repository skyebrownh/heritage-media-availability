"""
Top-level URL configuration for the whole site.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

# The admin's name and look come from django-unfold's UNFOLD settings (#39).

urlpatterns = [
    # The availability dashboard moved to the admin home page (#40). This old
    # address forwards there, keeping ?month=, so bookmarks still work. It
    # must come before 'admin/', or the admin would claim it as "not found".
    path(
        'admin/availability/',
        RedirectView.as_view(pattern_name='admin:index', query_string=True),
        name='availability',
    ),
    # Django's built-in admin, styled by django-unfold: Skye's login (AD-1),
    # the roster (AD-2), and closed months (AD-8).
    path('admin/', admin.site.urls),
    # Everything else belongs to our app, starting at the site root.
    path('', include('heritage_media_availability.urls')),
]
