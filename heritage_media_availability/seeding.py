"""
Known starting data for manual testing on a local database (#26).

`manage.py seed <scenario>` (management/commands/seed.py) calls reset() and
then one scenario from SCENARIOS. Every date is worked out from today, in
Eastern time, so "next month" in a scenario is always the real next month
and scenarios never go stale.

Rule for scenarios: seed the setup, not the behavior under test. A scenario
holds the data a manual test *starts* from. Anything the test exists to check
(submitting, closing or reopening a month, marking someone inactive) is done
by hand during the test, so scenarios never seed it.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from django.contrib.admin.models import LogEntry
from django.utils import timezone

from .models import ClosedMonth, Member, Submission
from .months import days_in_month, shift_month

# Our app's label in Django, used to find its History entries.
APP_LABEL = 'heritage_media_availability'


def reset():
    """
    Delete all members, submissions and closed months, and their admin History.

    Submissions go first: a member with submissions can't be deleted
    (on_delete=PROTECT keeps history safe in normal use). History entries
    for our tables go too, so "Recent actions" on the admin home doesn't
    point at deleted data. Admin accounts, and History about them, are kept.
    """
    Submission.objects.all().delete()
    ClosedMonth.objects.all().delete()
    Member.objects.all().delete()
    LogEntry.objects.filter(content_type__app_label=APP_LABEL).delete()


def this_month():
    """Today's month in Eastern time, e.g. "2026-10"."""
    return timezone.localdate().strftime('%Y-%m')


def days_ago(days):
    """A timestamp `days` days before now, for submitted_at and created_at."""
    return timezone.now() - timedelta(days=days)


def add_member(first_name, last_name, *, active=True, added_days_ago=90, standing=''):
    """
    Add one person to the roster, as if added `added_days_ago` days ago,
    with an optional standing availability note (#46).

    created_at uses auto_now_add, which ignores any value passed to create(),
    so the date is set with a separate update() afterwards.
    """
    member = Member.objects.create(
        first_name=first_name, last_name=last_name, is_active=active, standing_availability=standing,
    )
    Member.objects.filter(pk=member.pk).update(created_at=days_ago(added_days_ago))
    return member


def add_submission(member, month, kind, *, days=(), notes='', submitted_days_ago=3):
    """Save one submission, as if sent `submitted_days_ago` days ago."""
    return Submission.objects.create(
        member=member,
        month=month,
        kind=kind,
        days=list(days),
        notes=notes,
        submitted_at=days_ago(submitted_days_ago),
    )


def load_roster():
    """
    The base roster: nine people, each covering a display-name or tracker case.

    Returns them by first name (Bob Smith as 'bob', Bob Jones as 'bob_jones',
    Bob Johnson as 'bob_johnson') for scenarios to add submissions to.
    """
    return {
        # #46: Amy has a standing note but answers anyway (her answer, note and
        # form notes all show in By person).
        'amy': add_member('Amy', 'Lee', standing='1st and 3rd Sundays'),
        # Three Bobs: "Bob S.", plus Jones and Johnson, who share an initial
        # too and so show with full last names.
        'bob': add_member('Bob', 'Smith'),
        'bob_jones': add_member('Bob', 'Jones'),
        'bob_johnson': add_member('Bob', 'Johnson'),
        # Typed in lowercase: should still sort as "Emily" (between Bob and Grace).
        'emily': add_member('emily', 'carter'),
        # #46: Grace has a standing note and doesn't answer next month, so she
        # shows as Standing, not counted, and "(3rd Sundays only)" in copy text.
        'grace': add_member('Grace', 'Kim', standing='3rd Sundays only'),
        # Inactive. Henry responds in the dashboard scenario ("No longer active");
        # Ivy never does, so she should appear nowhere.
        'henry': add_member('Henry', 'Park', active=False),
        'ivy': add_member('Ivy', 'Chen', active=False),
        # Added today: after last month ended, so not listed for last month.
        'jack': add_member('Jack', 'Moore', added_days_ago=0),
    }


def load_dashboard():
    """
    The roster plus next month's and last month's answers, for the dashboard (#20).

    Next month: a mix of every kind, a resubmission, an inactive responder,
    and two non-responders (Grace, Bob Johnson).
    Last month: a few answers, and the month is closed.
    """
    people = load_roster()
    Kind = Submission.Kind
    next_month = shift_month(this_month(), 1)
    last_month = shift_month(this_month(), -1)

    add_submission(
        people['amy'], next_month, Kind.DAYS, days=[3, 4, 5, 6, 7, 20],
        notes="Can't make rehearsal on the 19th.",
    )
    add_submission(people['bob'], next_month, Kind.AVAILABLE_ALL)
    add_submission(people['bob_jones'], next_month, Kind.UNAVAILABLE_ALL, submitted_days_ago=2)
    # emily resubmits: only the newer answer (12-13) should count.
    add_submission(people['emily'], next_month, Kind.DAYS, days=[10], submitted_days_ago=5)
    add_submission(people['emily'], next_month, Kind.DAYS, days=[12, 13], submitted_days_ago=1)
    add_submission(people['henry'], next_month, Kind.DAYS, days=[10, 11], submitted_days_ago=4)

    # Days 1-28 exist in every month, so these are valid whatever last month was.
    add_submission(people['amy'], last_month, Kind.DAYS, days=[1, 2], submitted_days_ago=35)
    add_submission(people['bob'], last_month, Kind.AVAILABLE_ALL, submitted_days_ago=34)
    add_submission(people['grace'], last_month, Kind.UNAVAILABLE_ALL, submitted_days_ago=33)
    ClosedMonth.objects.create(month=last_month)


def next_31_day_month():
    """The first month after this one with 31 days (at most two months away), e.g. "2026-12" in October."""
    offset = 1
    while days_in_month(shift_month(this_month(), offset)) != 31:
        offset += 1
    return shift_month(this_month(), offset)


def load_spec_example():
    """
    The people and answers from SPEC.md's copy-format examples, so the copy
    text on the dashboard can be compared with the spec line by line.

    Uses the next 31-day month, because Jane's "27-31" needs a day 31.
    Extras the spec's example doesn't show, which must not change the copy text:
    Bob's note (notes are never copied) and Pat (inactive, so never copied).
    """
    Kind = Submission.Kind
    month = next_31_day_month()
    bob = add_member('Bob', 'Smith')
    emily = add_member('Emily', 'Davis')
    jane = add_member('Jane', 'Lopez')
    jim = add_member('Jim', 'Brown')
    sam = add_member('Sam', 'Wilson')
    add_member('Tom', 'Clark')  # Tom doesn't respond.
    pat = add_member('Pat', 'Rivera', active=False)

    add_submission(bob, month, Kind.DAYS, days=[3, 4, 5, 6, 7, 20], notes="Can't make rehearsal on the 19th.")
    add_submission(emily, month, Kind.DAYS, days=[13])
    add_submission(jane, month, Kind.DAYS, days=[1, 4, 10, 11, 27, 28, 29, 30, 31])
    add_submission(jim, month, Kind.AVAILABLE_ALL)
    add_submission(sam, month, Kind.UNAVAILABLE_ALL)
    add_submission(pat, month, Kind.DAYS, days=[2])


@dataclass
class Scenario:
    """One named starting state: what `seed --list` says about it, and the function that loads it."""

    description: str
    load: Callable[[], object]


# Every scenario `manage.py seed` knows. Issues add theirs here when they
# need a different starting state for their manual test steps.
SCENARIOS = {
    'roster': Scenario('The base roster only: nine people, no submissions or closed months.', load_roster),
    'dashboard': Scenario(
        "The roster plus next month's answers (every kind, a resubmission, two non-responders) "
        'and a closed last month with a few answers. For the dashboard (#20).',
        load_dashboard,
    ),
    'spec-example': Scenario(
        "SPEC.md's copy-format example (Bob, Emily, Jane, Jim, Sam, Tom) in the next 31-day month, "
        'plus a note and an inactive responder that must not appear in copy text. For #21 and #22.',
        load_spec_example,
    ),
}
