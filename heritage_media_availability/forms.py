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
from .months import month_label, month_name, month_weeks, upcoming_months

# #41: the dropdowns' look, from Tailwind Plus's "simple native" select menu.
# appearance-none hides the browser's own arrow; the template draws the
# block's chevron on top instead (pr-8 leaves room for it), and the phone's
# native picker still opens on tap. 16px text at every width (text-base,
# decision 2026-10-12, instead of the block's 14px from 640px up); it also
# stops iPhones zooming in when a field is tapped, so it's set here on the
# field itself rather than left to the page's size. Focus draws an indigo
# outline. Two additions to the block:
# - has-[...]: while the empty "Choose..." option is the chosen one, the text
#   is gray-500, so the placeholder looks lighter than a real choice (gray-500
#   is the lightest gray with AA contrast on white). *:text-gray-900 keeps
#   the options in the open list dark, since some browsers copy the select's
#   color onto them.
# - *:data-closed: closed months (MonthSelect's data-closed) are gray in the
#   open list where the browser allows it (desktop Chrome and Firefox; phone
#   pickers ignore option colors). Their "(closed)" text says it either way.
SELECT_CLASSES = (
    'col-start-1 row-start-1 w-full appearance-none rounded-md bg-white py-1.5 pr-8 pl-3 '
    'text-base text-gray-900 outline-1 -outline-offset-1 outline-gray-300 '
    'focus:outline-2 focus:-outline-offset-2 focus:outline-indigo-600 '
    "has-[option[value='']:checked]:text-gray-500 *:text-gray-900 *:data-closed:text-gray-500"
)


# #41: the notes box, from Tailwind Plus's "simple" textarea, with the same
# outline, indigo focus and 16px text as the dropdowns.
TEXTAREA_CLASSES = (
    'block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 '
    'outline-1 -outline-offset-1 outline-gray-300 '
    'focus:outline-2 focus:-outline-offset-2 focus:outline-indigo-600'
)


# #36: each "Your availability" choice card's radio button, from Tailwind
# Plus's "stacked cards" radio group. The radio is invisible
# (appearance-none) and stretched over its whole card (absolute inset-0), so
# a tap anywhere on the card picks it, while it stays a real radio for the
# keyboard (arrow keys) and screen readers. The card itself is drawn in
# team_form.html and styles itself from the radio (has-checked:).
RADIO_CARD_CLASSES = 'absolute inset-0 cursor-pointer appearance-none focus:outline-none'


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


class MemberSelect(forms.Select):
    """
    The name dropdown, marking people who have a standing availability note
    for the page script (TF-12, #46).

    Their options carry the note in a `data-standing` attribute. The script
    reads it when the name changes (or is preselected, TF-11) and shows the
    reminder that they only need to submit if it won't work this month,
    with no extra trip to the server. Django escapes the note in the HTML.
    """

    def create_option(self, name, value, *args, **kwargs):
        """Build one <option>, adding data-standing if that member has a note."""
        option = super().create_option(name, value, *args, **kwargs)
        # Django wraps each choice's value so it still knows the Member it came from.
        member = getattr(value, 'instance', None)
        if member is not None and member.standing_availability:
            option['attrs']['data-standing'] = member.standing_availability
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
        widget=MemberSelect(attrs={'class': SELECT_CLASSES}),
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
    # Submission.Kind. "Pick specific days" is the default. #36: shown as
    # three choice cards (radio buttons) rather than a dropdown, so the
    # chosen one is always visible.
    kind = forms.ChoiceField(
        label='Your availability',
        choices=[
            (Submission.Kind.DAYS, 'Pick specific days'),
            (Submission.Kind.AVAILABLE_ALL, "I'm available all month"),
            (Submission.Kind.UNAVAILABLE_ALL, "I'm unavailable all month"),
        ],
        initial=Submission.Kind.DAYS,
        widget=forms.RadioSelect(attrs={'class': RADIO_CARD_CLASSES}),
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
                # #36: for the all-month panel, "You're available all of November."
                'name': month_name(month),
                'weeks': month_weeks(month),
                'checked': checked if month == submitted_month else set(),
            }
            for month in self.months
        ]
