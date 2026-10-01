"""
Top-level URL configuration for the whole site.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path

# Friendlier wording than Django's default "Django administration".
admin.site.site_header = 'Heritage Media Admin'
admin.site.site_title = 'Heritage Media Admin'
admin.site.index_title = 'Manage the roster'

urlpatterns = [
    # Django's built-in admin: Skye's login (AD-1) and the roster (AD-2).
    path('admin/', admin.site.urls),
    # Everything else belongs to our app, starting at the site root.
    path('', include('heritage_media_availability.urls')),
]
