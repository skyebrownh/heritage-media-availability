"""
Django admin setup: the screens Skye uses behind the admin login (AD-1).

- Members: the roster (AD-2)
- Closed months: close and reopen months (AD-8)
- Submissions: a read-only history of everything the team has submitted

Django builds the add/edit/list pages for us from the models; this file
chooses which columns, filters and actions appear, and adds the one custom
step (confirming before a month is closed). The screens are styled by
django-unfold (#39): each admin class extends Unfold's ModelAdmin, and the
site's name, colors and sidebar are in UNFOLD in config/settings.py.
"""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.models import DELETION, LogEntry
from django.template.response import TemplateResponse
from unfold.admin import ModelAdmin
from unfold.widgets import SELECT_CLASSES, UnfoldAdminSelect2Widget

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

    Used by the close-month form here and the dashboard's month picker.
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


def closable_month_choices():
    """
    The "close a month" dropdown's options: 6 months back through 6 ahead.

    Grouped like the dashboard's month selector, oldest first, e.g. on
    Oct 9, 2026: "Past months" Apr 2026 to Sep 2026, then "This month and
    ahead" Oct 2026 to Apr 2027. Months that are already closed are still
    listed, marked "(closed)", so choosing one gets the friendly "already
    closed" message instead of a puzzling gap in the list.
    """
    closed = set(ClosedMonth.objects.values_list('month', flat=True))

    def option(month):
        label = month_label(month)
        return (month, f'{label} (closed)' if month in closed else label)

    coming_up = upcoming_months()
    past = [shift_month(coming_up[0], -offset) for offset in range(MONTHS_BACK_TO_CLOSE, 0, -1)]
    return [
        ('', 'Choose a month'),
        ('Past months', [option(month) for month in past]),
        ('This month and ahead', [option(month) for month in coming_up]),
    ]


class ClosedMonthForm(forms.ModelForm):
    """
    The "close a month" form: one dropdown of months.

    A dropdown rather than a browser month picker (#39): it looks the same in
    every browser (desktop Safari has no month picker at all) and matches the
    dashboard's month selector (see month_dropdown).
    """

    month = forms.ChoiceField(label='Month', widget=month_dropdown())

    class Meta:
        model = ClosedMonth
        fields = ['month']

    def __init__(self, *args, **kwargs):
        """Build the month list when the form is made, so it follows today's date."""
        super().__init__(*args, **kwargs)
        self.fields['month'].choices = closable_month_choices()


@admin.register(ClosedMonth)
class ClosedMonthAdmin(ModelAdmin):
    """
    AD-8: close and reopen months, including past ones.

    Closing = adding a row (after a confirmation page).
    Reopening = the "Reopen selected months" action, which deletes rows.
    """

    form = ClosedMonthForm
    list_display = ['label', 'closed_at']
    actions = ['reopen_months']

    @admin.display(description='Month', ordering='month')
    def label(self, closed_month):
        """Show "November 2026" instead of "2026-11" in the list."""
        return month_label(closed_month.month)

    def has_change_permission(self, request, obj=None):
        """
        No editing. The month is the primary key, and changing a primary key in
        admin silently creates a second row instead of renaming the first.
        To fix a mistake, reopen the wrong month and close the right one.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Hide Django's generic Delete button and action so "Reopen selected
        months" is the one, clearly named way to reopen.
        """
        return False

    @admin.action(description='Reopen selected months')
    def reopen_months(self, request, queryset):
        """
        Reopen months by deleting their rows; the team can submit again right away.

        #16: record each reopen in admin's History and "Recent actions" first
        (it must happen before the rows are gone). Closing is recorded by
        Django's add view, so together they show who closed or reopened a
        month and when. A month's ID is the month itself ("2026-11"), so if it
        is closed again later, its History page shows the whole timeline.
        """
        labels = ', '.join(str(closed_month) for closed_month in queryset)
        # Like Django's log_deletions(), but with a description; the History
        # page leaves the Action column blank for deletions without one.
        LogEntry.objects.log_actions(
            user_id=request.user.pk,
            queryset=queryset,
            action_flag=DELETION,
            change_message='Reopened the month.',
        )
        queryset.delete()
        self.message_user(request, f'Reopened {labels}.', messages.SUCCESS)

    def construct_change_message(self, request, form, formsets, add=False):
        """
        #16: describe a close in History as "Closed the month." rather than
        Django's generic "Added." (Editing is off, so adding is the only case.)
        """
        return 'Closed the month.'

    def add_view(self, request, form_url='', extra_context=None):
        """
        AD-8: closing asks for confirmation.

        Pressing Save first shows a confirmation page instead of saving. That
        page posts the same month back with a "confirm" field, and only then
        does Django's normal add view run and save the row. The form is
        validated both times, so a month closed in another tab in the
        meantime still gets the "already closed" error.
        """
        if request.method == 'POST' and 'confirm' not in request.POST:
            form = self.get_form(request)(request.POST)
            if form.is_valid():
                month = form.cleaned_data['month']
                context = {
                    **self.admin_site.each_context(request),
                    'opts': self.model._meta,
                    'title': f'Close {month_label(month)}?',
                    'month': month,
                    'month_label': month_label(month),
                }
                return TemplateResponse(
                    request, 'admin/heritage_media_availability/closedmonth/confirm_close.html', context
                )

        # Only one Save button: "Save and add another" / "Save and continue
        # editing" would skip past the point of a single, deliberate close.
        extra_context = {
            **(extra_context or {}),
            'show_save_and_add_another': False,
            'show_save_and_continue': False,
        }
        return super().add_view(request, form_url, extra_context)


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
