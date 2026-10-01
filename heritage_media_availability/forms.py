"""
Forms for the team-facing pages.

TeamForm both draws the team form's inputs and checks a submission on the
server before saving it. Keeping both jobs in one class means the page and
the server agree on the rules, and every rule is enforced on the server
(CLAUDE.md: "Validate everything on the server").
"""

from django import forms
from django.core.exceptions import ValidationError

from .models import ClosedMonth, Member, Submission
from .months import month_label, month_weeks, upcoming_months

# Shared look for the dropdowns: full width, at least 44px tall (tap target),
# 16px text (also stops iPhones zooming in when a field is tapped), and a
# clear pastel-blue ring when focused with a keyboard or finger.
SELECT_CLASSES = (
    'block w-full min-h-11 rounded-xl border border-neutral-300 bg-white px-3 py-2 text-base '
    'focus:border-accent-500 focus:outline-none focus:ring-4 focus:ring-accent-200'
)


# Same look for the notes box, just taller.
TEXTAREA_CLASSES = (
    'block w-full rounded-xl border border-neutral-300 bg-white px-3 py-2 text-base '
    'focus:border-accent-500 focus:outline-none focus:ring-4 focus:ring-accent-200'
)


# TF-4: shown when a month is closed, both by the page script (as soon as the
# month is picked) and by the server (if a stale form is submitted anyway).
CLOSED_MONTH_MESSAGE = "This month's schedule is finalized. Please text Skye with any changes."


class AnyMemberChoiceField(forms.ModelChoiceField):
    """
    A name dropdown that lists active members but accepts any member.

    The dropdown shows active people only (TF-2). But if Skye marks someone
    inactive while their form is open, their submission is still accepted
    (decision 2026-10-01), so the server looks the name up among everyone.
    """

    def to_python(self, value):
        """Find the submitted member among all members, active or not."""
        if value in self.empty_values:
            return None
        try:
            return Member.objects.get(pk=value)
        except (ValueError, TypeError, Member.DoesNotExist):
            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')


class AnyMonthChoiceField(forms.ChoiceField):
    """
    A month dropdown that lists 7 months but accepts any real month.

    SPEC.md: "A closed month is the only reason the server rejects a month."
    So a form opened on Sept 30 and sent on Oct 1 for September still saves.
    The month's format is checked by the model (validate_month), and closed
    months by TeamForm.clean_month().
    """

    def valid_value(self, value):
        """Skip ChoiceField's "must be one of the listed options" check."""
        return True


class MonthSelect(forms.Select):
    """
    A month dropdown that marks closed months for the page script (TF-4).

    Closed options get a `data-closed` attribute. The script reads it when
    the month changes and shows the "schedule is finalized" message instead
    of the rest of the form, with no extra trip to the server.
    """

    def __init__(self, *args, **kwargs):
        """Start with no closed months; TeamForm fills in closed_months."""
        super().__init__(*args, **kwargs)
        self.closed_months = set()

    def create_option(self, name, value, *args, **kwargs):
        """Build one <option>, adding data-closed if its month is closed."""
        option = super().create_option(name, value, *args, **kwargs)
        if value in self.closed_months:
            option['attrs']['data-closed'] = ''
        return option


class TeamForm(forms.ModelForm):
    """
    The team availability form (TF-2 to TF-8).

    A ModelForm: after its own field checks, Django runs the Submission
    model's checks (Submission.clean: days vs. all-month choice, days that
    exist in the month) and shows any errors on the matching fields.
    form.save() then creates a new Submission row; old rows are never changed.
    """

    class Meta:
        model = Submission
        fields = ['member', 'month', 'kind', 'days', 'notes']

    # No colon after labels; they read like plain questions.
    label_suffix = ''

    # TF-2: active members only, shown as "First Last" (Member.__str__) and
    # sorted by first then last name (Member's default ordering).
    member = AnyMemberChoiceField(
        label='Your name',
        queryset=Member.objects.filter(is_active=True),
        empty_label='Choose your name',
        widget=forms.Select(attrs={'class': SELECT_CLASSES}),
        # TF-8: plain-language messages for each missing piece.
        error_messages={
            'required': 'Please choose your name.',
            'invalid_choice': 'Please choose your name from the list.',
        },
    )
    # TF-3: choices are filled in __init__, because the months depend on today's date.
    month = AnyMonthChoiceField(
        label='Which month?',
        widget=MonthSelect(attrs={'class': SELECT_CLASSES}),
        error_messages={'required': 'Please choose a month.'},
    )

    # TF-6: the three answers, worded for the team. The stored values match
    # Submission.Kind. "Pick specific days" is the default.
    kind = forms.ChoiceField(
        label='Your availability',
        choices=[
            (Submission.Kind.DAYS, 'Pick specific days'),
            (Submission.Kind.AVAILABLE_ALL, "I'm available all month"),
            (Submission.Kind.UNAVAILABLE_ALL, "I'm unavailable all month"),
        ],
        initial=Submission.Kind.DAYS,
        widget=forms.Select(attrs={'class': SELECT_CLASSES}),
    )
    # TF-5: day numbers ticked on the calendar. The template draws the
    # calendar itself (one per month), so this field only defines what's
    # accepted: whole numbers 1-31. The model checks each day exists in the
    # chosen month (no Feb 30).
    days = forms.TypedMultipleChoiceField(
        choices=[(day, str(day)) for day in range(1, 32)],
        coerce=int,
        required=False,
    )
    # TF-7: optional. Notes are for what the calendar can't capture (times,
    # rehearsals), so the example steers away from repeating unavailable days.
    # max_length=500 also adds maxlength="500" to the box,
    # so the browser stops typing at 500 characters.
    notes = forms.CharField(
        label='Anything else? (optional)',
        help_text=(
            "For anything the calendar can't show, like "
            '"Available the 12th, but can\'t make rehearsal on the 11th." Up to 500 characters.'
        ),
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 3, 'class': TEXTAREA_CLASSES}),
    )

    def __init__(self, *args, **kwargs):
        """Fill the month dropdown with this month through 6 ahead, marking closed ones."""
        super().__init__(*args, **kwargs)
        self.months = months = upcoming_months()
        closed = set(ClosedMonth.objects.filter(month__in=months).values_list('month', flat=True))

        # The placeholder comes first with an empty value, so no month is
        # preselected: people must pick one deliberately (TF-3).
        choices = [('', 'Choose a month')]
        for month in months:
            label = month_label(month)
            if month in closed:
                label += ' (closed)'  # TF-3
            choices.append((month, label))

        self.fields['month'].choices = choices
        self.fields['month'].widget.closed_months = closed

    def clean_month(self):
        """
        Reject closed months, even from a form opened before the month closed.

        The page script already hides the form for a closed month, but a
        stale tab can still send one, so the server has the final word.
        """
        month = self.cleaned_data['month']
        if ClosedMonth.objects.filter(month=month).exists():
            raise ValidationError(CLOSED_MONTH_MESSAGE, code='month_closed')
        return month

    def _post_clean(self):
        """
        Run the model's checks, unless the month is closed.

        For a closed month, the only useful message is "text Skye"; errors
        about missing days would just be noise, so skip the model's checks.
        """
        if self.has_error('month', code='month_closed'):
            return
        super()._post_clean()

    @property
    def month_closed(self):
        """True if this (submitted) form was rejected because its month is closed."""
        return self.has_error('month', code='month_closed')

    @property
    def calendars(self):
        """
        TF-5: one calendar per month in the dropdown, for the template.

        All of them are on the page; the script shows only the chosen month's.
        Drawing them on the server keeps the date math (which weekday the 1st
        falls on, how many days) in tested Python rather than JavaScript.
        """
        # After a failed submit, re-tick the days the person had chosen so
        # they only need to fix the problem, not start over.
        submitted_month, checked = None, set()
        if self.is_bound:
            submitted_month = self.data.get('month')
            checked = {value for value in self.data.getlist('days') if value.isdigit()}
            checked = {int(value) for value in checked}

        return [
            {
                'month': month,
                'label': month_label(month),
                'weeks': month_weeks(month),
                'checked': checked if month == submitted_month else set(),
            }
            for month in self.months
        ]
