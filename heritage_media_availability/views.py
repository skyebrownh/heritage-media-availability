"""
Views (page handlers) for the Heritage Media Availability app.

The team-facing form lives at the site root. Skye's pages are in Django
admin for now; the Week 3 views will be added here.
"""

from django.shortcuts import render

from .forms import TeamForm


def team_form(request):
    """
    The team availability form at "/" (TF-1: public, no login).

    #6 only draws the empty form; saving a submission arrives in #8.
    """
    return render(request, 'heritage_media_availability/team_form.html', {'form': TeamForm()})
