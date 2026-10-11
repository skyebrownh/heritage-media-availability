"""
The staging site (#45): a second copy of the app on Railway, with its own
database, where testers can try anything without touching real data.

Staging runs the same code as production. The one difference is the
STAGING setting (STAGING=true in staging's Railway variables), which:
- shows a "Test site" banner on every page, so nobody mistakes it for the
  real site (context processor below, plus Unfold's environment label);
- lets the data-replacing commands (seed, load_snapshot) run there.
"""

from django.conf import settings

# Database hosts that mean "this computer". An empty host connects through
# a local socket file, which is also this computer.
LOCAL_HOSTS = {'', 'localhost', '127.0.0.1', '::1'}


def unsafe_reason(database):
    """
    Why replacing all the app's data here would be unsafe, or None if it's fine.

    Used by `seed` and `load_snapshot`, which delete every member,
    submission and closed month. Each route needs two independent signs,
    so one wrong setting is never enough to wipe production:
    - staging: STAGING is on, and every address the site answers to
      (ALLOWED_HOSTS) has "staging" in it;
    - local development: DEBUG is on, and the database is on this computer.
    Production fails both: STAGING and DEBUG are off there, its address
    has no "staging", and its database isn't on localhost.
    """
    if settings.STAGING:
        hosts = settings.ALLOWED_HOSTS
        not_staging = [host for host in hosts if 'staging' not in host]
        if not hosts or not_staging:
            shown = ', '.join(not_staging) or '(none)'
            return (
                f'STAGING is on, but this site also answers to {shown}, which isn\'t a staging '
                'address. Refusing, in case this is production with STAGING set by mistake.'
            )
        return None
    if not settings.DEBUG:
        return 'DEBUG is off. This only runs in local development (DEBUG=true in .env) or on staging.'
    host = database.get('HOST') or ''
    if host not in LOCAL_HOSTS:
        return f'The database host is "{host}", not this computer. This only runs on a local database.'
    return None


def staging_context(request):
    """Context processor: lets every template check {% if is_staging %} for the banner."""
    return {'is_staging': settings.STAGING}


def environment_label(request):
    """
    UNFOLD["ENVIRONMENT"]: Unfold's label in the admin header, as
    [text, color]. None on production, which shows no label.
    """
    return ['Test site', 'warning'] if settings.STAGING else None


def environment_title_prefix(request):
    """UNFOLD["ENVIRONMENT_TITLE_PREFIX"]: "[TEST]" before every admin tab title, on staging only."""
    return '[TEST]' if settings.STAGING else None
