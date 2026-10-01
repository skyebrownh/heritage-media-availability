"""
Views (page handlers) for the Heritage Media Availability app.

The team-facing form lives at the site root, with its confirmation page at
/thanks/ and a small JSON lookup for pre-filling (/last-submission/). Skye's pages are in Django admin for now; the Week 3 views will be
added here.
"""

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .formatting import confirmation_message, previous_summary
from .forms import CLOSED_MONTH_MESSAGE, TeamForm
from .models import Submission
from .months import validate_month

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


@never_cache
@require_GET
def last_submission(request):
    """
    TF-9: the current submission for one member and month, as JSON.

    Called by the team form's script (GET /last-submission/?member=12&month=2026-11)
    when a name and month are both picked, so the form can pre-fill without
    reloading (decision 2026-09-28). Returns only the newest submission for
    that one member and month, never the history:

        {"found": true, "kind": "days", "days": [3, 4, 20], "notes": "...",
         "summary": "Your last submission (10/02/26): Oct 3-4, 20. Submitting again replaces it."}

    or {"found": false}. Anyone with the link could look up any name, which
    matches v1's trusted-identity rule (SPEC.md business rules): the data is
    only names and dates. never_cache stops the browser reusing an old answer
    after someone resubmits.
    """
    member_id = request.GET.get('member', '')
    month = request.GET.get('month', '')
    try:
        validate_month(month)
    except ValidationError:
        return JsonResponse({'error': 'Invalid month.'}, status=400)
    if not member_id.isdigit():
        return JsonResponse({'error': 'Invalid member.'}, status=400)

    # Newest first, so .first() is the current one ("last submission wins").
    submission = (
        Submission.objects.select_related('member')
        .filter(member_id=int(member_id), month=month)
        .order_by('-submitted_at')
        .first()
    )
    if submission is None:
        return JsonResponse({'found': False})

    return JsonResponse({
        'found': True,
        'kind': submission.kind,
        'days': submission.days,
        'notes': submission.notes,
        'summary': previous_summary(submission),
    })
