"""
Django admin setup: the screens Skye uses behind the admin login (AD-1).

- Members: the roster (AD-2)
- Closed months: close and reopen months (AD-8)
- Submissions: a read-only history of everything the team has submitted

Django builds the add/edit/list pages for us from the models; this file
chooses which columns, filters and actions appear, and adds the one custom
step (confirming before a month is closed).
"""

from django import forms
from django.contrib import admin, messages
from django.template.response import TemplateResponse

from .models import ClosedMonth, Member, Submission
from .months import month_label


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
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


class MonthInput(forms.TextInput):
    """
    A browser month picker (<input type="month">).

    It submits exactly "YYYY-MM", the format we store. Browsers without a
    month picker show a plain text box instead, and the server still checks it.
    """

    input_type = 'month'


class ClosedMonthForm(forms.ModelForm):
    """The "close a month" form: just the month, with a month picker."""

    class Meta:
        model = ClosedMonth
        fields = ['month']
        widgets = {'month': MonthInput(attrs={'placeholder': '2026-11'})}


@admin.register(ClosedMonth)
class ClosedMonthAdmin(admin.ModelAdmin):
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
        """Reopen months by deleting their rows; the team can submit again right away."""
        labels = ', '.join(str(closed_month) for closed_month in queryset)
        queryset.delete()
        self.message_user(request, f'Reopened {labels}.', messages.SUCCESS)

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
class SubmissionAdmin(admin.ModelAdmin):
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
