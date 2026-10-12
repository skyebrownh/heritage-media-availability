"""
The data behind Skye's availability dashboard (AD-3, AD-4).

Kept apart from the view so the rules are easy to test, and so the
by-person and by-date views (#21, #22) can reuse month_responses():

- Which months the selector offers, and which one it opens on.
- Who is listed for a month, and what each person's current answer is.

Decision 2026-10-03 (SPEC.md): we only know whether someone is active *now*,
not whether they were active in a past month. So a month lists today's active
members, minus anyone added after that month ended, plus a separate
"No longer active" list of inactive members who responded to it.
"""

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from .formatting import answer_label, display_names
from .models import ClosedMonth, Member, Submission
from .months import days_in_month, month_label, split_month, upcoming_months


@dataclass
class Response:
    """One person's line for a month: who they are and their current submission (None if no response)."""

    member: Member
    name: str
    submission: Submission | None

    @property
    def responded(self):
        """AD-4 / business rules: any submission counts, even "available all month"."""
        return self.submission is not None

    @property
    def answer(self):
        """AD-5: their answer as the by-person view shows it, e.g. "3-7, 20" or "No response"."""
        return answer_label(self.submission)

    @property
    def standing(self):
        """#46: their standing availability note ("3rd Sundays only"), or "" if they have none."""
        return self.member.standing_availability

    @property
    def is_standing(self):
        """
        #46: has a standing note and hasn't responded, so nothing is owed:
        shown as Standing rather than Not responded, and not counted. Once
        they do respond, they count like anyone else.
        """
        return not self.responded and bool(self.standing)


@dataclass
class ByDate:
    """
    AD-6: who's out, grouped by day instead of by person.

    all_month: display names of people unavailable all month, A–Z. They're
    listed once here instead of on every day.
    days: (date, names) for each day anyone picked, in date order, names A–Z.
    Days nobody picked are left out.
    """

    all_month: list[str]
    days: list[tuple[date, list[str]]]

    @property
    def anyone_out(self):
        """False when nobody is unavailable at all, so there's no copy text to show."""
        return bool(self.all_month or self.days)


@dataclass
class MonthResponses:
    """Everyone listed for one month, split into active and no-longer-active people."""

    # The month these responses are for, e.g. "2026-11".
    month: str
    # Active members listed for the month, A–Z by first then last name.
    active: list[Response]
    # Inactive members who responded to the month, A–Z, shown with full names.
    # Never counted, and never in copy text.
    inactive: list[Response]

    @property
    def responded_count(self):
        """The "12" in "12 of 17 responded" (AD-4)."""
        return sum(1 for response in self.active if response.responded)

    @property
    def standing_count(self):
        """#46: the "2" in "· 2 standing": people not responding because they don't need to."""
        return sum(1 for response in self.active if response.is_standing)

    @property
    def total(self):
        """
        The "17" in "12 of 17 responded" (AD-4): everyone a response is
        expected from, so standing non-responders (#46) are left out.
        """
        return len(self.active) - self.standing_count

    @property
    def by_person(self):
        """
        AD-5 / AD-7: the active rows in by-person order: responders, then
        standing non-responders (#46), then everyone else who hasn't responded.

        Each group stays A–Z, because `active` already is and Python's sort
        is stable (rows that tie keep their order). The view and the copy
        text both use this, so they always list people in the same order.
        """
        def group(response):
            if response.responded:
                return 0
            return 1 if response.is_standing else 2

        return sorted(self.active, key=group)

    @property
    def by_date(self):
        """
        AD-6 / AD-7: active members' current answers, regrouped by day.

        Walking the rows in their A–Z order and adding each name to each of
        that person's days leaves every day's list A–Z, with no extra sorting.
        Inactive members and non-responders are never included.
        """
        Kind = Submission.Kind
        all_month = []
        names_by_day = {}
        for response in self.active:
            if response.submission is None:
                continue
            if response.submission.kind == Kind.UNAVAILABLE_ALL:
                all_month.append(response.name)
            for day in response.submission.days:  # empty unless kind is "days"
                names_by_day.setdefault(day, []).append(response.name)

        year, number = split_month(self.month)
        days = [(date(year, number, day), names) for day, names in sorted(names_by_day.items())]
        return ByDate(all_month=all_month, days=days)


def default_month():
    """The month the dashboard opens on: next month, the one Skye is usually collecting."""
    return upcoming_months()[1]


def month_options():
    """
    AD-3: the months the dashboard's selector offers, as (month, label) pairs.

    Returns (past, upcoming):
    - past: earlier months that have any submission or were ever closed,
      oldest first. Months with neither would just show an empty tracker.
    - upcoming: the current month through 6 ahead, the same window as the team form.
    Closed months get " (closed)" on the end, as on the team form (TF-3).
    """
    upcoming = upcoming_months()
    current = upcoming[0]
    # "YYYY-MM" text sorts in date order, so "<" compares months correctly.
    past = (
        set(Submission.objects.filter(month__lt=current).values_list('month', flat=True))
        | set(ClosedMonth.objects.filter(month__lt=current).values_list('month', flat=True))
    )
    closed = set(ClosedMonth.objects.values_list('month', flat=True))

    def option(month):
        label = month_label(month)
        if month in closed:
            label += ' (closed)'
        return month, label

    return [option(month) for month in sorted(past)], [option(month) for month in upcoming]


def month_responses(month):
    """
    AD-4: everyone listed for `month`, with each person's current submission.

    Active members are listed, except anyone added to the roster after the
    month ended (they weren't on the team then), unless they did submit for
    it, because any submission counts as a response. Inactive members appear
    only if they responded, in their own list (decision 2026-10-03).
    """
    # Current submissions only ("last submission wins"), keyed by member.
    current = {
        submission.member_id: submission
        for submission in Submission.objects.filter(month=month).current()
    }

    # The month's last day; "added after the month ended" compares against it
    # in Eastern time, so someone added at 11 pm on Oct 31 counts for October.
    year, number = split_month(month)
    last_day = date(year, number, days_in_month(month))

    # Member's default ordering is A–Z by first then last name, ignoring case.
    active, inactive = [], []
    for member in Member.objects.all():
        submission = current.get(member.pk)
        if member.is_active:
            added = timezone.localdate(member.created_at)
            if added <= last_day or submission is not None:
                active.append((member, submission))
        elif submission is not None:
            inactive.append((member, submission))

    # Display names only need to tell apart the people listed for this month.
    names = display_names(member for member, _ in active)
    return MonthResponses(
        month=month,
        active=[Response(member, names[member.pk], submission) for member, submission in active],
        inactive=[Response(member, str(member), submission) for member, submission in inactive],
    )
