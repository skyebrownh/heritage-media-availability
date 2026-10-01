"""
Views (page handlers) for the Heritage Media Availability app.

The team-facing form lives at the site root, with its confirmation page at
/thanks/. Skye's pages are in Django admin for now; the Week 3 views will be
added here.
"""

from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .formatting import confirmation_message
from .forms import CLOSED_MONTH_MESSAGE, TeamForm
from .models import Submission

# Session key holding the id of this visitor's latest submission, so the
# confirmation page knows what to restate without putting the id in the URL
# (where anyone could change the number to see someone else's answers).
LAST_SUBMISSION_KEY = 'last_submission_id'


@require_http_methods(['GET', 'POST'])
def team_form(request):
    """
    The team availability form at "/" (TF-1: public, no login).

    GET shows an empty form. POST checks everything on the server (TF-8):
    if anything's wrong, the form comes back with plain-language messages
    and the person's choices kept; if it's all fine, a new Submission is
    saved and the browser is sent on to the confirmation page.
    """
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            submission = form.save()
            request.session[LAST_SUBMISSION_KEY] = submission.pk
            # Post/Redirect/Get: redirecting after a successful POST means
            # refreshing the confirmation page can't submit a second time.
            return redirect('heritage_media_availability:thanks')
    else:
        form = TeamForm()

    return render(
        request,
        'heritage_media_availability/team_form.html',
        {'form': form, 'closed_month_message': CLOSED_MONTH_MESSAGE},
    )


@require_GET
def thanks(request):
    """
    TF-10: confirm what was just saved, with a button to fill out another month.

    Without a saved submission in this visitor's session (e.g. someone opens
    /thanks/ directly), there's nothing to confirm, so go back to the form.
    """
    submission_id = request.session.get(LAST_SUBMISSION_KEY)
    submission = Submission.objects.select_related('member').filter(pk=submission_id).first()
    if submission is None:
        return redirect('heritage_media_availability:team_form')

    return render(
        request,
        'heritage_media_availability/thanks.html',
        {'submission': submission, 'message': confirmation_message(submission)},
    )


def csrf_failure(request, reason=''):
    """
    Friendly page for a refused form submit (settings.CSRF_FAILURE_VIEW).

    Django refuses a POST whose security (CSRF) token doesn't match, e.g.
    the browser's cookies were cleared while the form was open, or someone
    logged into admin in another tab. Django's own page is technical, so
    volunteers get a plain explanation and a way back instead. The status
    stays 403 (refused); `reason` is Django's technical cause, not shown.
    """
    return render(request, 'heritage_media_availability/csrf_failure.html', status=403)
