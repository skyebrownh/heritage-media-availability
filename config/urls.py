"""
Top-level URL configuration for the whole site.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django's built-in admin: Skye's login (AD-1) and, later, the roster (AD-2).
    path('admin/', admin.site.urls),
    # Everything else belongs to our app, starting at the site root.
    path('', include('heritage_media_availability.urls')),
]
