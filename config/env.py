"""
Helpers for reading settings from environment variables.

Every secret and every value that differs between your laptop and Railway
(SECRET_KEY, DEBUG, DATABASE_URL, ALLOWED_HOSTS, ...) comes from the
environment, never from code. These small functions turn the raw strings
the environment gives us into the Python types Django expects.

They live in their own module (instead of inside settings.py) so tests can
import and check them without loading all of Django's settings.
"""

import os
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured


def env_required(name):
    """Return the variable's value, or stop startup with a clear message if it's missing."""
    value = os.environ.get(name)
    if not value:
        # Failing loudly beats silently running with a missing secret or database.
        raise ImproperlyConfigured(
            f'The {name} environment variable is not set. '
            'Locally, copy .env.example to .env and run commands with '
            '`uv run --env-file .env ...`.'
        )
    return value


def env_bool(name, default=False):
    """Read a true/false flag such as DEBUG. Only "true", "1", "yes" and "on" count as true."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'true', '1', 'yes', 'on'}


def env_list(name, default=''):
    """Read a comma-separated list such as "localhost,127.0.0.1", ignoring blanks and spaces."""
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(',') if item.strip()]


def parse_database_url(url):
    """
    Turn a DATABASE_URL into the dict Django's DATABASES setting expects.

    Local Postgres and Railway Postgres both hand us one URL shaped like:
        postgresql://user:password@host:5432/dbname
    urlsplit() already breaks that into parts, so we only need to map each
    part onto Django's key names. This avoids adding the dj-database-url
    package for something the standard library does in a few lines.
    """
    parts = urlsplit(url)
    if parts.scheme not in {'postgres', 'postgresql'}:
        raise ImproperlyConfigured(
            f'DATABASE_URL must start with postgres:// or postgresql://, got "{parts.scheme}://".'
        )

    return {
        'ENGINE': 'django.db.backends.postgresql',
        # The path is "/dbname"; drop the leading slash.
        'NAME': unquote(parts.path.lstrip('/')),
        # unquote() because special characters in passwords arrive URL-encoded
        # (e.g. "@" is sent as "%40" so it isn't mistaken for the host separator).
        'USER': unquote(parts.username or ''),
        'PASSWORD': unquote(parts.password or ''),
        'HOST': parts.hostname or '',
        # Empty string tells Django to use Postgres's default port (5432).
        'PORT': str(parts.port or ''),
    }
