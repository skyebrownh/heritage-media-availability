"""
Forms for the team-facing pages.

TeamForm draws the team form's inputs and (from #8 on) checks a submission
on the server. Keeping both jobs in one class means the page and the server
always agree on which names and months are allowed.
"""

from django import forms

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


class TeamForm(forms.Form):
    """
    The team availability form.

    #6: name and month pickers. #7: all-month choice, calendar days and notes.
    #8 uses this form to validate submissions on the server.
    """

    # No colon after labels; they read like plain questions.
    label_suffix = ''

    # TF-2: active members only, shown as "First Last" (Member.__str__) and
    # sorted by first then last name (Member's default ordering).
    member = forms.ModelChoiceField(
        label='Your name',
        queryset=Member.objects.filter(is_active=True),
        empty_label='Choose your name',
        widget=forms.Select(attrs={'class': SELECT_CLASSES}),
    )
    # TF-3: choices are filled in __init__, because the months depend on today's date.
    month = forms.ChoiceField(
        label='Which month?',
        widget=MonthSelect(attrs={'class': SELECT_CLASSES}),
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
    # accepted: whole numbers 1-31. #8 adds the per-month check (no Feb 30).
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

    @property
    def calendars(self):
        """
        TF-5: one calendar per month in the dropdown, for the template.

        All of them are on the page; the script shows only the chosen month's.
        Drawing them on the server keeps the date math (which weekday the 1st
        falls on, how many days) in tested Python rather than JavaScript.
        """
        return [
            {'month': month, 'label': month_label(month), 'weeks': month_weeks(month)}
            for month in self.months
        ]
