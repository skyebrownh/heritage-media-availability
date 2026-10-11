"""
Django admin setup: the screens Skye uses behind the admin login (AD-1).

- Members: the roster (AD-2)
- Months (ClosedMonth): close and reopen months (AD-8, #43)
- Submissions: a read-only history of everything the team has submitted

Django builds the add/edit/list pages for us from the models; this file
chooses which columns, filters and actions appear. The custom pieces are
one-click buttons that act at once: Deactivate / Activate on the
roster (#42), and Close / Reopen on the Months page (#43). The screens are styled by
django-unfold (#39): each admin class extends Unfold's ModelAdmin, and the
site's name, colors and sidebar are in UNFOLD in config/settings.py.
"""

from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE, DELETION, LogEntry
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import DropdownFilter
from unfold.widgets import SELECT_CLASSES, UnfoldAdminSelect2Widget

from .dashboard import month_responses
from .models import ClosedMonth, Member, Submission
from .months import month_label, shift_month, upcoming_months


# ---------------------------------------------------------------------------
# Shared pieces for the roster and Months pages: badges, name links, and
# one-click buttons that act at once and come back to the same page.
# ---------------------------------------------------------------------------

def status_badge(text, variant=None, large=False):
    """
    Unfold's badge: green for variant="success", gray with no variant.
    Used for Open/Closed months (AD-8) and Active/Inactive members (AD-2).

    large=True gives it the same height as a button beside it (the
    dashboard's month row; .badge-large in admin.css), so the pair lines up.
    """
    context = {'text': text}
    if variant:
        context['variant'] = variant
    if large:
        context['class'] = 'badge-large'
    return render_to_string('unfold/helpers/label.html', context)


def row_link(url, text):
    """
    A list's main link (a month's dashboard, a member's edit page): the
    table's normal text with a small right arrow, so it reads as a link
    without the whole column turning indigo (.row-link in admin.css).
    The arrow is decorative, so screen readers skip it.
    """
    return format_html(
        '<a class="row-link" href="{}">{}'
        '<span class="material-symbols-outlined" aria-hidden="true">arrow_forward</span></a>',
        url, text,
    )


def action_button(request, url, label, icon, next_url=None, hidden_label='', quiet=False, in_list_form=False):
    """
    A one-click button that POSTs to `url` and then returns to next_url
    (or, without one, to the page it was on; see safe_next_url).

    POST, never a link, so a browser prefetching links can't trigger it.
    Two looks, so opposite actions are told apart at a glance (Skye's call,
    2026-10-10): the main action (Close, Make inactive) is Unfold's white
    outline button; the quieter undo (Reopen, Activate) is its borderless
    "ghost" button in indigo (.quiet-action). hidden_label is read only by
    screen readers, e.g. "Close" + " November 2026", since a table of
    identical "Close" buttons wouldn't tell them apart.

    in_list_form=True is for buttons inside Django's list table, which is
    already one big form (for bulk actions), and HTML can't nest forms.
    The button then borrows that form, sending it to `url` instead
    (formaction); the form already holds the CSRF token, so no request is
    needed (pass None).
    """
    return render_to_string(
        'admin/heritage_media_availability/_action_button.html',
        {
            'url': url,
            'label': label,
            'hidden_label': hidden_label,
            'icon': icon,
            'variant': 'ghost' if quiet else 'default',
            'button_class': 'quiet-action' if quiet else '',
            'next': next_url,
            'in_list_form': in_list_form,
            'formaction_attrs': format_html('formaction="{}" formmethod="post"', url),
        },
        request=request,  # so {% csrf_token %} works in the standalone form
    )


def safe_next_url(request, default):
    """
    Where a button returns to afterwards: the page it was on.

    That's its "next" field if it sent one, or else the page the browser
    says it came from (the Referer header, which browsers send for pages on
    the same site), so the roster comes back with its filter and search.
    Only addresses on this site are followed, so a link can't use our pages
    to send Skye somewhere else; anything else goes to `default`.
    """
    for url in [request.POST.get('next'), request.GET.get('next'), request.headers.get('referer')]:
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return url
    return default


class StatusFilter(admin.SimpleListFilter):
    """
    #42: All / Active (7) / Inactive (2), as one-click tabs beside the
    roster's search box (shown there by list_filter_options), drawn like
    the Unfold demo's filter tabs (filters/segmented.html). Django's own
    Yes/No filter would read "Is active: Yes", so this one uses plain words.
    """

    title = 'status'
    parameter_name = 'status'
    template = 'admin/heritage_media_availability/filters/segmented.html'

    def lookups(self, request, model_admin):
        """The options after "All" (which Django adds first), with how many people each has."""
        active = Member.objects.filter(is_active=True).count()
        inactive = Member.objects.filter(is_active=False).count()
        return [('active', f'Active ({active})'), ('inactive', f'Inactive ({inactive})')]

    def queryset(self, request, queryset):
        """Narrow the roster to the chosen status; "All" leaves it alone."""
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        if self.value() == 'inactive':
            return queryset.filter(is_active=False)
        return queryset


@admin.register(Member)
class MemberAdmin(ModelAdmin):
    """
    Roster screen (AD-2): add people, fix names, and switch them active or
    inactive with one click (#42). The edit page's Active checkbox still
    works too, with its Save button.
    """

    list_display = ['name', 'status', 'created_at', 'action']
    # The Name column is the link to the edit page (row_link), so Django
    # doesn't add its own link to the first column as well.
    list_display_links = None
    list_filter = [StatusFilter]
    # #42: shown beside the search box rather than in the Filters panel.
    list_filter_options = {'status': {'horizontal': True}}
    search_fields = ['first_name', 'last_name']
    # The edit page only needs the fields Skye can change; created_at is automatic.
    fields = ['first_name', 'last_name', 'is_active']

    @admin.display(description='Name', ordering='first_name')
    def name(self, member):
        """
        "Grace Kim", linking to the edit page. Sorting by this column sorts
        by first name; Member's default order breaks ties by last name.
        """
        url = reverse('admin:heritage_media_availability_member_change', args=[member.pk])
        return row_link(url, str(member))

    @admin.display(description='Status', ordering='is_active')
    def status(self, member):
        """AD-2: Active (green) or Inactive (gray)."""
        return status_badge('Active', 'success') if member.is_active else status_badge('Inactive')

    @admin.display(description='Action')
    def action(self, member):
        """
        #42: Deactivate / Activate, applied at once. Returns to the
        same list afterwards (the page it came from), keeping its filter,
        search and sorting.
        """
        url = reverse('admin:heritage_media_availability_member_toggle_active', args=[member.pk])
        # Short verbs that match the Active/Inactive badges, with an X or a
        # check mark (Skye's call, 2026-10-10).
        if member.is_active:
            label, icon, quiet = 'Deactivate', 'close', False
        else:
            label, icon, quiet = 'Activate', 'check', True
        return action_button(None, url, label, icon, hidden_label=f' {member}', quiet=quiet, in_list_form=True)

    def get_urls(self):
        """
        Add the one-click toggle, e.g. .../member/7/toggle-active/. It goes
        before Django's own URLs, which would otherwise read "7/toggle-active"
        as a record ID; admin_view() puts it behind the admin login.
        """
        toggle = path(
            '<int:member_id>/toggle-active/',
            self.admin_site.admin_view(self.toggle_active_view),
            name='heritage_media_availability_member_toggle_active',
        )
        return [toggle] + super().get_urls()

    def toggle_active_view(self, request, member_id):
        """
        AD-2 (#42): switch a member active or inactive straight away.

        POST only. Recorded in the member's History (#16) as "Marked
        inactive." or "Marked active.", then back to the roster with
        "Grace Kim is now inactive."
        """
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not self.has_change_permission(request):
            raise PermissionDenied
        member = get_object_or_404(Member, pk=member_id)
        member.is_active = not member.is_active
        member.save(update_fields=['is_active'])
        state = 'active' if member.is_active else 'inactive'
        LogEntry.objects.log_actions(
            user_id=request.user.pk,
            queryset=[member],
            action_flag=CHANGE,
            change_message=f'Marked {state}.',
            single_object=True,
        )
        self.message_user(request, f'{member} is now {state}.', messages.SUCCESS)
        return redirect(safe_next_url(request, reverse('admin:heritage_media_availability_member_changelist')))

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
    """AD-8: a month's badge: Open (green) or Closed (gray)."""
    return status_badge('Closed', large=large) if closed else status_badge('Open', 'success', large=large)


def month_action(request, month, closed, next_url, short=False):
    """
    AD-8: the Close or Reopen button for one month (#43), acting at once
    with no confirmation: each is undone with one click of the other
    (Skye's call, 2026-10-10). Close is the main action (lock icon);
    Reopen is the quieter one (circular arrow). next_url is where to come
    back to (the dashboard or the Months page). short=True says
    "Close"/"Reopen" for the Months table, where the row already names the
    month; the dashboard says "Close month".
    """
    action = 'reopen' if closed else 'close'
    verb = 'Reopen' if closed else 'Close'
    return action_button(
        request,
        reverse(f'admin:heritage_media_availability_closedmonth_{action}', args=[month]),
        verb if short else f'{verb} month',
        'replay' if closed else 'lock',
        next_url,
        hidden_label=f' {month_label(month)}',
        quiet=closed,
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
                    # The month's name links to its dashboard.
                    row_link(f"{reverse('admin:index')}?{urlencode({'month': month})}", month_label(month)),
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
        """Back to the page the button was on, or the Months page."""
        return safe_next_url(request, reverse('admin:heritage_media_availability_closedmonth_changelist'))

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


class MonthFilter(DropdownFilter):
    """
    #42: pick one month's submissions from a dropdown beside the search
    box (shown there by list_filter_options), newest month first. A
    dropdown rather than buttons because the list of months keeps growing.
    """

    title = 'month'
    parameter_name = 'month'

    def lookups(self, request, model_admin):
        """Every month anyone has submitted for, as ("2026-11", "November 2026")."""
        months = Submission.objects.order_by('-month').values_list('month', flat=True).distinct()
        return [(month, month_label(month)) for month in months]

    def queryset(self, request, queryset):
        """Only the chosen month's submissions; "All" leaves the list alone."""
        if self.value():
            return queryset.filter(month=self.value())
        return queryset


@admin.register(Submission)
class SubmissionAdmin(ModelAdmin):
    """
    Read-only history of every submission, newest first.

    Lets Skye check what someone actually submitted and when ("I know I
    marked the 14th"). Submissions only ever come from the team form, so
    there's no add, edit or delete here; the history can't be changed by mistake.
    """

    list_display = ['member', 'month_name', 'kind', 'day_list', 'submitted_at']
    list_filter = [MonthFilter, 'kind', 'member']
    # #42: the month dropdown sits beside the search box; kind and member
    # stay in the Filters panel.
    list_filter_options = {'month': {'horizontal': True}}
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
