"""
Skye's availability dashboard, shown as the admin home page (#40).

django-unfold calls dashboard_callback() (UNFOLD["DASHBOARD_CALLBACK"] in
config/settings.py) every time the admin home page is drawn, and our
templates/admin/index.html displays what it adds. Because the admin home
is already behind the admin login, the dashboard needs no view or URL of
its own (AD-1).

The page is built from Unfold's own components (cards, tables, labels,
buttons), so this module prepares data in the shapes they take: a table is
{"headers": [...], "rows": [[cell, ...], ...]}, where a cell is plain text
(Django escapes it) or HTML we've built safely with format_html().
"""

from urllib.parse import urlencode

from django.template.defaultfilters import date as date_filter
from django.template.defaultfilters import linebreaksbr
from django.template.loader import render_to_string
from django.utils.html import format_html, format_html_join
from django.urls import reverse
from django.utils.timezone import localtime

from .admin import closable_months, month_action, month_dropdown, month_status_label
from .dashboard import default_month, month_options, month_responses
from .formatting import by_date_text, by_person_text
from .models import ClosedMonth
from .months import month_label

# How submission times read on the dashboard, in Eastern time: "Oct 2, 3:15 p.m."
TIME_FORMAT = 'M j, g:i a'


def chosen_month(request):
    """
    AD-3: the month to show, from ?month=2026-11.

    A missing or unlisted month falls back to next month (the one usually
    being collected), so an old bookmark or a typo still shows something
    useful. Returns (month, past_options, upcoming_options).
    """
    past, upcoming = month_options()
    month = request.GET.get('month')
    if month not in {value for value, _ in past + upcoming}:
        month = default_month()
    return month, past, upcoming


def month_select(month, past, upcoming):
    """
    AD-3: the month dropdown (the admin's styled month list, see month_dropdown).

    Grouped "Past months" then "Coming up", like before. The id lets the
    page's script submit the form as soon as a month is picked. Returns the
    HTML and the widget's media (the Select2 script and styles), which the
    page must include itself because it isn't an admin form page.
    """
    widget = month_dropdown({'id': 'month-select'})
    widget.choices = ([('Past months', past)] if past else []) + [('Coming up', upcoming)]
    return widget.render('month', month), widget.media


def status_label(response):
    """
    AD-4: Unfold's label (badge) helper. The words carry the meaning; color only helps scanning.

    #46: someone with a standing note who hasn't responded gets a gray
    Standing badge with their note beside it, since nothing is owed.
    """
    if response.responded:
        return render_to_string('unfold/helpers/label.html', {'text': 'Responded', 'variant': 'success'})
    if response.is_standing:
        badge = render_to_string('unfold/helpers/label.html', {'text': 'Standing'})
        return format_html('{}<span class="tracker-standing">{}</span>', badge, response.standing)
    return render_to_string('unfold/helpers/label.html', {'text': 'Not responded', 'variant': 'danger'})


def submitted_time(response):
    """When they last submitted, in Eastern time, or a dash if they haven't."""
    if not response.responded:
        return '–'
    return date_filter(localtime(response.submission.submitted_at), TIME_FORMAT)


def standing_line(response, alone=False):
    """
    #46: someone's standing availability note as By person shows it on
    screen: upright, quiet text after a repeat icon (.answer-standing), so it
    can't be confused with the team form's notes (italic, .answer-notes).
    Screen readers hear "Standing: 3rd Sundays only". alone=True when it's
    the whole cell (no answer above it), so it gets no gap above.
    """
    return format_html(
        '<span class="answer-standing{}">'
        '<span class="material-symbols-outlined" aria-hidden="true">event_repeat</span>'
        '<span><span class="sr-only">Standing: </span>{}</span></span>',
        ' answer-standing-alone' if alone else '',
        response.standing,
    )


def answer_with_notes(response):
    """
    AD-5: the answer, with any notes on their own quieter line underneath.

    #46: anyone with a standing note gets it on its own line (standing_line)
    under the answer, whether or not they've responded, so Skye can spot an
    answer that only partly overlaps it. A standing member who hasn't
    responded shows only that line, since no response is owed. (The copy
    text writes their note in parentheses instead; that's formatting.py.)
    The team form's notes come last.

    Volunteers type the notes, so they're escaped (format_html, and
    linebreaksbr with autoescape), keeping their line breaks.
    """
    if response.is_standing:
        return standing_line(response, alone=True)
    parts = [format_html('{}', response.answer)]
    if response.standing:
        parts.append(standing_line(response))
    notes = response.submission.notes if response.submission else ''
    if notes:
        parts.append(format_html('<span class="answer-notes">{}</span>', linebreaksbr(notes, autoescape=True)))
    if len(parts) == 1:
        return response.answer
    return format_html_join('', '{}', ((part,) for part in parts))


def copy_button_attrs(target, message):
    """
    AD-7: the data attributes the copy script reads: which text block to copy
    and what to announce afterwards. Passed to Unfold's button as extra_attrs.
    """
    return format_html('data-copy-target="{}" data-copied-message="{}"', target, message)


def close_controls(request, month):
    """
    AD-8 (#43): the chosen month's Open/Closed badge and Close month or
    Reopen month button, for the month row at the top of the dashboard.

    Months outside the Months page's window (older than 6 back) get the
    badge only. Afterwards the button comes back here, to the same month.
    Returns (badge_html, button_html); the button is "" when there's none.
    """
    closed = ClosedMonth.objects.filter(month=month).exists()
    upcoming, past = closable_months()
    if month not in upcoming + past:
        return month_status_label(closed, large=True), ''
    here = f"{reverse('admin:index')}?{urlencode({'month': month})}"
    return month_status_label(closed, large=True), month_action(request, month, closed, here)


def dashboard_callback(request, context):
    """Add the chosen month's responses to the admin home page (AD-3 to AD-7)."""
    month, past, upcoming = chosen_month(request)
    select_html, select_media = month_select(month, past, upcoming)
    responses = month_responses(month)
    by_date = responses.by_date
    month_status, month_button = close_controls(request, month)

    context.update({
        # Unfold shows the title in the page header and the browser tab.
        'title': f'Availability for {month_label(month)}',
        'month': month,
        'month_select': select_html,
        'month_select_media': select_media,
        'month_status': month_status,
        'month_button': month_button,
        'responses': responses,
        'by_date': by_date,
        # AD-4: active members A-Z.
        'tracker_table': {
            'headers': ['Name', 'Status', 'Last submitted'],
            'rows': [[r.name, status_label(r), submitted_time(r)] for r in responses.active],
        },
        # AD-5: same order as the copy text (responders A-Z, then non-responders A-Z).
        'by_person_table': {
            'headers': ['Name', 'Answer'],
            'rows': [[r.name, answer_with_notes(r)] for r in responses.by_person],
        },
        # AD-6: one row per day anyone is out, with the weekday on screen only ("Fri 4").
        'by_date_table': {
            'headers': ['Day', "Who's out"],
            'rows': [[date_filter(day, 'D j'), ', '.join(names)] for day, names in by_date.days],
        },
        # Decision 2026-10-03: inactive members who responded, by full name.
        'inactive_table': {
            'headers': ['Name', 'Answer', 'Last submitted'],
            'rows': [[r.name, answer_with_notes(r), submitted_time(r)] for r in responses.inactive],
        },
        # AD-7: exactly the text each Copy button copies. by_date_text is "" when nobody is out.
        'by_person_text': by_person_text(responses),
        'by_date_text': by_date_text(responses),
        'by_person_copy_attrs': copy_button_attrs('by-person-text', 'By-person text copied.'),
        'by_date_copy_attrs': copy_button_attrs('by-date-text', 'By-date text copied.'),
    })
    return context
