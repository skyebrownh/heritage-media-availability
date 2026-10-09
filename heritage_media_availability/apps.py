"""App configuration for the Heritage Media Availability app."""

from django.apps import AppConfig


class HeritageMediaAvailabilityConfig(AppConfig):
    """Registers the app with Django, and names it for the admin."""

    name = 'heritage_media_availability'
    # Shown in admin page titles and URLs' app pages; without it Django
    # falls back to the code name, "Heritage_Media_Availability" (#39).
    verbose_name = 'Heritage Media'
