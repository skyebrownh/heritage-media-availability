"""
Django admin setup: the screens Skye uses behind the admin login (AD-1).

- Members: the roster (AD-2)
- Months (ClosedMonth): close and reopen months (AD-8, #43)
- Submissions: a read-only history of everything the team has submitted

Django builds the add/edit/list pages for us from the models; this file
chooses which columns, filters and actions appear. The one custom screen is
the Months page, with its Close and Reopen buttons. The screens are styled by
django-unfold (#39): each admin class extends Unfold's ModelAdmin, and the
site's name, colors and sidebar are in UNFOLD in config/settings.py.
"""

from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.admin.models import DELETION, LogEntry
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from unfold.admin import ModelAdmin
from unfold.widgets import SELECT_CLASSES, UnfoldAdminSelect2Widget

from .dashboard import month_responses
from .models import ClosedMonth, Member, Submission
from .months import month_label, shift_month, upcoming_months


@admin.register(Member)
class MemberAdmin(ModelAdmin):
    """Roster screen: add people, fix names, and switch them active or inactive."""

    list_display = ['first_name', 'last_name', 'is_active', 'created_at']
    # Clicking a name opens that person's edit page.
    list_display_links = ['first_name', 'last_name']
    # AD-2: tick or untick "active" right in the list, then press Save,
    # without opening each person's page.
    list_editable = ['is_active']
    list_filter = ['is_active']
    search_fields = ['first_name', 'last_name']
    # The edit page only needs the fields Skye can change; created_at is automatic.
    fields = ['first_name', 'last_name', 'is_active']

    def has_delete_permission(self, request, obj=None):
        """
        AD-2: no hard delete in v1.

        Returning False removes the Delete button, the delete page, and the
        bulk "Delete selected" action, even for a superuser. Deleting a member
        would also wipe their submission history, which the spec says to keep.
        """
        return False


def month_dropdown(attrs=None):
    """
    The admin's month dropdown: Unfold's styled Select2 list instead of the
    browser's native one (#39, #40), with its search box hidden because the
    lists are short (13 months or so). Select2 ships with Django's admin, so
    nothing extra is installed. It's still a real <select> underneath, so
    forms submit and validate exactly as before.

    Used by the dashboard's month picker.
    """
    return UnfoldAdminSelect2Widget(attrs={
        # Select2 reads its options from data- attributes:
        # never show the search box, and fill the space it's given.
        'data-minimum-results-for-search': 'Infinity',
        'data-width': '100%',
        # Until Select2 takes over (a moment after the page loads), the plain
        # <select> shows. Unfold's regular select styling makes that moment
        # look the same instead of flashing a bare browser dropdown.
        'class': ' '.join(SELECT_CLASSES),
        **(attrs or {}),
    })


# AD-8 lets Skye close past months too; 6 months back covers any realistic
# catch-up (decision 2026-10-09), mirroring the 6 months ahead the team can submit.
MONTHS_BACK_TO_CLOSE = 6


def closable_months():
    """
    AD-8: the months Skye can close or reopen, as (upcoming, past).

    upcoming is this month through 6 ahead, oldest first (the team form's
    months); past is the 6 months before that, newest first, so the month
    most likely to need closing is at the top. E.g. on Oct 10, 2026:
    upcoming Oct 2026 to Apr 2027, past Sep 2026 back to Apr 2026.
    The Months page shows these, the dashboard only offers buttons for
    them, and the close and reopen pages refuse any other month.
    """
    upcoming = upcoming_months()
    past = [shift_month(upcoming[0], -offset) for offset in range(1, MONTHS_BACK_TO_CLOSE + 1)]
    return upcoming, past


def month_status_label(closed, large=False):
    """
    AD-8: Unfold's badge for a month: Open (green) or Closed (gray).

    large=True gives it the same height as the button beside it on the
    dashboard (.month-badge-large in admin.css), so the pair lines up.
    """
    context = {'text': 'Closed'} if closed else {'text': 'Open', 'variant': 'success'}
    if large:
        context['class'] = 'month-badge-large'
    return render_to_string('unfold/helpers/label.html', context)


def month_action(request, month, closed, next_url, short=False):
    """
    AD-8: the Close or Reopen button for one month (#43).

    Both are small forms that post straight away, with no confirmation:
    each is undone with one click of the other (Skye's call, 2026-10-10).
    next_url is where to come back to afterwards (the dashboard or the
    Months page). short=True says "Close"/"Reopen" for the Months table,
    where the row already names the month; the dashboard says "Close month".
    """
    action = 'reopen' if closed else 'close'
    return render_to_string(
        'admin/heritage_media_availability/closedmonth/_month_action.html',
        {
            'action_url': reverse(f'admin:heritage_media_availability_closedmonth_{action}', args=[month]),
            'verb': 'Reopen' if closed else 'Close',
            'verb_suffix': '' if short else ' month',
            # Told apart at a glance (Skye's call, 2026-10-10): Close is
            # Unfold's white outline button with a padlock; Reopen is quieter,
            # its borderless "ghost" button in indigo (.month-reopen in
            # admin.css) with a circular arrow. A gray fill was too close to
            # the gray Closed badge and the table's row hover.
            'icon': 'replay' if closed else 'lock',
            'variant': 'ghost' if closed else 'default',
            'button_class': 'month-reopen' if closed else '',
            'next': next_url,
            'month_label': month_label(month),
        },
        request=request,  # so {% csrf_token %} works in the form
    )


@admin.register(ClosedMonth)
class ClosedMonthAdmin(ModelAdmin):
    """
    AD-8: the Months page, where Skye closes and reopens months (#43).

    A ClosedMonth row still means "closed": closing adds one and
    reopening deletes it. Rather than Django's
    add-a-record form and list, the list page is replaced by a table of
    months, each with a Close or Reopen button, and those buttons (here
    and on the dashboard) go to the two pages added in get_urls().
    """

    def has_add_permission(self, request):
        """No add-a-record form: the Close buttons replace it (#43)."""
        return False

    def has_change_permission(self, request, obj=None):
        """
        No editing. The month is the primary key, and changing a primary key in
        admin silently creates a second row instead of renaming the first.
        To fix a mistake, reopen the wrong month and close the right one.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """Hide Django's generic Delete button and action, so Reopen is the one way to reopen."""
        return False

    def get_urls(self):
        """
        Add the close and reopen pages, e.g. .../closedmonth/2026-11/close/.

        They go before Django's own URLs, which would otherwise read
        "2026-11/close" as a record's ID. admin_view() puts them behind the
        admin login and Django's CSRF check, like every other admin page.
        """
        def url(action, view):
            return path(
                f'<str:month>/{action}/',
                self.admin_site.admin_view(view),
                name=f'heritage_media_availability_closedmonth_{action}',
            )

        return [url('close', self.close_view), url('reopen', self.reopen_view)] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        """
        AD-8: the Months page, in place of Django's list of ClosedMonth rows.

        This month and ahead first, then the past months (collapsed in the
        template). Each row: the month (linking to its dashboard), Open or
        Closed, how many have responded, and a Close or Reopen button.
        """
        if not self.has_view_permission(request):
            raise PermissionDenied
        closed = set(ClosedMonth.objects.values_list('month', flat=True))
        upcoming, past = closable_months()
        here = request.path

        def table(months):
            rows = []
            for month in months:
                responses = month_responses(month)
                rows.append([
                    # The month's name links to its dashboard; the small right
                    # arrow (decorative, so hidden from screen readers) shows it's a link.
                    format_html(
                        '<a class="months-link" href="{}?{}">{}'
                        '<span class="material-symbols-outlined" aria-hidden="true">arrow_forward</span></a>',
                        reverse('admin:index'), urlencode({'month': month}), month_label(month),
                    ),
                    month_status_label(month in closed),
                    # "5 of 6" (the column header says Responses); a dash before anyone was on the team.
                    f'{responses.responded_count} of {responses.total}' if responses.total else '–',
                    month_action(request, month, month in closed, here, short=True),
                ])
            return {'headers': ['Month', 'Status', 'Responses', 'Action'], 'rows': rows}

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Months',
            'upcoming_table': table(upcoming),
            'past_table': table(past),
            **(extra_context or {}),
        }
        return TemplateResponse(request, 'admin/heritage_media_availability/closedmonth/months.html', context)

    def check_month(self, request, month, permission):
        """
        Refuse anything outside the Months page's window (404) or without
        the right permission (403). The URL is just text, so the server
        checks it rather than trusting the button that sent it.
        """
        upcoming, past = closable_months()
        if month not in upcoming + past:
            raise Http404('That month can’t be closed or reopened here.')
        if not request.user.has_perm(f'heritage_media_availability.{permission}_closedmonth'):
            raise PermissionDenied

    def next_url(self, request):
        """
        Where to go after closing or reopening: the page the button was on.

        Only addresses on this site are followed, so a link can't use the
        page to send Skye somewhere else; anything else goes to the Months page.
        """
        url = request.POST.get('next') or request.GET.get('next')
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return url
        return reverse('admin:heritage_media_availability_closedmonth_changelist')

    def close_view(self, request, month):
        """
        AD-8: close a month straight away. No confirmation (decision
        2026-10-10): reopening is one click if it was a mistake. POST only,
        so a link or a browser prefetching pages can never close a month.
        If it was closed meanwhile (another tab), Skye gets a note instead.
        """
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        self.check_month(request, month, 'add')
        label = month_label(month)
        # get_or_create: if two tabs close at once, only one row is made
        # and only that one is recorded in History.
        closed_month, created = ClosedMonth.objects.get_or_create(month=month)
        if created:
            # #16: shows in the month's History as "Closed the month."
            self.log_addition(request, closed_month, 'Closed the month.')
            self.message_user(request, f'Closed {label}.', messages.SUCCESS)
        else:
            self.message_user(request, f'{label} was already closed.', messages.INFO)
        return redirect(self.next_url(request))

    def reopen_view(self, request, month):
        """
        AD-8: reopen a month straight away, like closing. POST only, so a
        link or a browser prefetching pages can never reopen a month.
        """
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        self.check_month(request, month, 'delete')
        label = month_label(month)
        rows = ClosedMonth.objects.filter(month=month)
        if rows.exists():
            # #16: record the reopen in History before the row is gone.
            # Like Django's log_deletions(), but with a description; the
            # History page leaves the Action column blank for deletions without one.
            LogEntry.objects.log_actions(
                user_id=request.user.pk,
                queryset=rows,
                action_flag=DELETION,
                change_message='Reopened the month.',
            )
            rows.delete()
            self.message_user(request, f'Reopened {label}.', messages.SUCCESS)
        else:
            self.message_user(request, f'{label} was already open.', messages.INFO)
        return redirect(self.next_url(request))


@admin.register(Submission)
class SubmissionAdmin(ModelAdmin):
    """
    Read-only history of every submission, newest first.

    Lets Skye check what someone actually submitted and when ("I know I
    marked the 14th"). Submissions only ever come from the team form, so
    there's no add, edit or delete here; the history can't be changed by mistake.
    """

    list_display = ['member', 'month_name', 'kind', 'day_list', 'submitted_at']
    list_filter = ['month', 'kind', 'member']
    search_fields = ['member__first_name', 'member__last_name']
    # Fetch each row's member in the same query instead of one query per row.
    list_select_related = ['member']

    @admin.display(description='Month', ordering='month')
    def month_name(self, submission):
        """Show "November 2026" instead of "2026-11"."""
        return month_label(submission.month)

    @admin.display(description='Days')
    def day_list(self, submission):
        """Days as "3, 4, 5, 20", or a dash for all-month choices."""
        return ', '.join(map(str, submission.days)) or '–'

    def has_add_permission(self, request):
        """Submissions come only from the team form."""
        return False

    def has_change_permission(self, request, obj=None):
        """History is never edited; resubmitting adds a new row instead."""
        return False

    def has_delete_permission(self, request, obj=None):
        """History is kept (SPEC.md business rules)."""
        return False
