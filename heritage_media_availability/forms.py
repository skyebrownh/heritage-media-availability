"""
Forms for the team-facing pages.

TeamForm draws the team form's inputs and (from #8 on) checks a submission
on the server. Keeping both jobs in one class means the page and the server
always agree on which names and months are allowed.
"""

from django import forms

from .models import ClosedMonth, Member
from .months import month_label, upcoming_months

# Shared look for the dropdowns: full width, at least 44px tall (tap target),
# 16px text (also stops iPhones zooming in when a field is tapped), and a
# clear pastel-blue ring when focused with a keyboard or finger.
SELECT_CLASSES = (
    'block w-full min-h-11 rounded-xl border border-neutral-300 bg-white px-3 py-2 text-base '
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

    #6 covers the name and month pickers. The calendar, all-month choice and
    notes are added in #7, and #8 uses this form to validate submissions.
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

    def __init__(self, *args, **kwargs):
        """Fill the month dropdown with this month through 6 ahead, marking closed ones."""
        super().__init__(*args, **kwargs)
        months = upcoming_months()
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
