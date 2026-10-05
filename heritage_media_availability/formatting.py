"""
Turning saved submissions into readable text.

day_ranges() collapses runs of days ([3, 4, 5, 6, 7, 20] → 3-7 and 20).
The TF-10 confirmation and TF-9 summary use it now; Week 3's copy formats
(AD-7, "Bob: 3-7, 20") will reuse it, so all agree on how ranges are grouped.

display_names() gives the short names ("Bob", "Bob J.") that Skye's
dashboard and copy text use.
"""

import calendar
from collections import Counter

from django.utils import timezone

from .models import Submission
from .months import split_month


def day_ranges(days):
    """
    Group day numbers into runs of consecutive days, as (first, last) pairs.

    [20, 3, 4, 5, 6, 7] → [(3, 7), (20, 20)]. A lone day is a run of one,
    so its first and last are the same. Input order and repeats don't matter.
    """
    ranges = []
    for day in sorted(set(days)):
        # Extend the current run if this day follows straight on from it.
        if ranges and day == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], day)
        else:
            ranges.append((day, day))
    return ranges


def format_range(first, last):
    """One run as text: "20" for a single day, "3-7" for several (a plain hyphen, as in the copy formats)."""
    return str(first) if first == last else f'{first}-{last}'


def days_phrase(month, days):
    """
    TF-10: the days in a sentence, naming the month only once.

    One run:   "Oct 3-7"
    Two:       "Oct 3-7, and 20"
    Three+:    "Oct 3-7, 10, and 20"
    """
    pieces = [format_range(first, last) for first, last in day_ranges(days)]
    if len(pieces) == 1:
        listed = pieces[0]
    else:
        listed = ', '.join(pieces[:-1]) + ', and ' + pieces[-1]
    _, number = split_month(month)
    return f'{calendar.month_abbr[number]} {listed}'


def confirmation_message(submission):
    """
    TF-10: restate what was saved, greeting the person by first name.

    "Thanks, Bob! You're unavailable Oct 3-7, and 20."
    "Thanks, Bob! You're available all of November."
    "Thanks, Bob! You're unavailable all of November."
    """
    greeting = f'Thanks, {submission.member.first_name}!'
    _, number = split_month(submission.month)
    month_name = calendar.month_name[number]

    if submission.kind == Submission.Kind.AVAILABLE_ALL:
        return f"{greeting} You're available all of {month_name}."
    if submission.kind == Submission.Kind.UNAVAILABLE_ALL:
        return f"{greeting} You're unavailable all of {month_name}."
    return f"{greeting} You're unavailable {days_phrase(submission.month, submission.days)}."


def days_list(month, days):
    """
    TF-9: the days as a compact list, naming the month once: "Oct 3-7, 20".

    Shorter than the TF-10 sentence (no "and"), since it's a reference line.
    """
    pieces = [format_range(first, last) for first, last in day_ranges(days)]
    _, number = split_month(month)
    return f'{calendar.month_abbr[number]} {", ".join(pieces)}'


def display_names(members):
    """
    SPEC.md "Names in admin views and copy output": a short name for each member.

    Returns {member id: name}. Each person gets their first name only, unless
    another member in `members` shares it (ignoring capitalization), in which
    case they get their last initial too: "Bob J." and "Bob S.". If two people
    share both the first name and the last initial (Bob Jones, Bob Johnson),
    those two get their full last name instead, so no two names on a page match.

    Pass active members only: the rule compares against the active roster,
    so an inactive Bob doesn't turn an active "Bob" into "Bob S.".
    """
    members = list(members)

    def first_key(member):
        # casefold() is a stronger lower(): "Bob" and "bob" compare equal.
        return member.first_name.casefold()

    def initial_key(member):
        return (first_key(member), member.last_name[:1].casefold())

    # How many people share each first name, and each first name + initial.
    first_counts = Counter(first_key(member) for member in members)
    initial_counts = Counter(initial_key(member) for member in members)

    names = {}
    for member in members:
        if first_counts[first_key(member)] == 1:
            names[member.pk] = member.first_name
        elif initial_counts[initial_key(member)] == 1:
            names[member.pk] = f'{member.first_name} {member.last_name[:1].upper()}.'
        else:
            names[member.pk] = f'{member.first_name} {member.last_name}'
    return names


def previous_summary(submission):
    """
    TF-9: the read-only reminder of someone's current submission for a month.

    "Your last submission (10/02/26): Oct 3-7, 20. Submitting again replaces it."
    "Your last submission (10/02/26): available all month. Submitting again replaces it."
    The date is the day it was submitted, in Eastern time (settings.TIME_ZONE),
    as MM/DD/YY so it doesn't read as part of the days that follow
    ("(Oct 2): Oct 3-7" put two month names side by side).
    """
    when = timezone.localtime(submission.submitted_at).strftime('%m/%d/%y')

    if submission.kind == Submission.Kind.AVAILABLE_ALL:
        what = 'available all month'
    elif submission.kind == Submission.Kind.UNAVAILABLE_ALL:
        what = 'unavailable all month'
    else:
        what = days_list(submission.month, submission.days)
    return f'Your last submission ({when}): {what}. Submitting again replaces it.'
