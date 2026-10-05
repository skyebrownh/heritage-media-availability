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


@dataclass
class MonthResponses:
    """Everyone listed for one month, split into active and no-longer-active people."""

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
    def total(self):
        """The "17" in "12 of 17 responded" (AD-4)."""
        return len(self.active)

    @property
    def by_person(self):
        """
        AD-5 / AD-7: the active rows in by-person order: responders, then non-responders.

        Each group stays A–Z, because `active` already is and Python's sort
        is stable (rows that tie keep their order). The view and the copy
        text both use this, so they always list people in the same order.
        """
        return sorted(self.active, key=lambda response: not response.responded)


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
        active=[Response(member, names[member.pk], submission) for member, submission in active],
        inactive=[Response(member, str(member), submission) for member, submission in inactive],
    )
