"""
Template tags for the link preview (#37).

Chat apps like iMessage fetch a link's preview image themselves, from their
own servers, so og:image and og:url must be full addresses
("https://example.com/static/..."), not paths like "/static/...". These
tags build them from the current request, so production and staging each
point at their own address and no domain is written into the code.

Behind Railway's proxy the app itself is reached over plain http, but
SECURE_PROXY_SSL_HEADER (config/settings.py) tells Django the visitor used
https, so the addresses come out as https://.

Use with {% load link_preview %}. Both tags need the request in the template
context, which the "request" context processor provides on every page.
"""

from django import template
from django.templatetags.static import static
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def absolute_static(context, path):
    """A static file's full URL, e.g. {% absolute_static 'heritage_media_availability/link-preview.png' %}."""
    return context['request'].build_absolute_uri(static(path))


@register.simple_tag(takes_context=True)
def absolute_url(context, view_name):
    """A page's full URL by its URL name, e.g. {% absolute_url 'heritage_media_availability:team_form' %}."""
    return context['request'].build_absolute_uri(reverse(view_name))
