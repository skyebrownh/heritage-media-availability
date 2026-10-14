"""
Middleware for the Heritage Media Availability app.

health_check (#60) answers Railway's deploy health check. During each deploy,
Railway loads /healthz/ on the new version and only switches visitors over
once it gets a 2xx answer. If it never does, the deploy fails and the old
version keeps running, so a broken deploy can't replace a working one.
"""

from django.http import HttpResponse

# The one address Railway checks (Settings → Deploy → Healthcheck Path).
HEALTH_CHECK_PATH = '/healthz/'


def health_check(get_response):
    """
    Answer /healthz/ with "ok" before any of Django's security checks run.

    Railway's checker sends `Host: healthcheck.railway.app` over plain HTTP,
    so normally Django would reject it twice: SecurityMiddleware would
    redirect it to HTTPS (Railway wants a 2xx, not a 301), and the host
    check would answer 400 because that host isn't in ALLOWED_HOSTS. We
    can't add it to ALLOWED_HOSTS, because staging.unsafe_reason() only
    lets seed and load_snapshot run when every allowed host has "staging"
    in it. So this middleware sits first in MIDDLEWARE and answers before
    the others see the request. It never calls request.get_host(), which is
    where Django's host check happens.

    It's safe to skip those checks here because this one address reads no
    data, sets no cookies, and always returns the same two letters.

    It also deliberately skips the database: a brief database hiccup during
    a deploy shouldn't fail a deploy of code that's otherwise fine.
    """

    def middleware(request):
        if request.path == HEALTH_CHECK_PATH:
            return HttpResponse('ok', content_type='text/plain')
        return get_response(request)

    return middleware
