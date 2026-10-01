"""
Turning saved submissions into readable text.

day_ranges() collapses runs of days ([3, 4, 5, 6, 7, 20] → 3-7 and 20).
The TF-10 confirmation uses it now; Week 3's copy formats (AD-7, "Bob: 3-7, 20")
will reuse it, so both always agree on how ranges are grouped.
"""

import calendar

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
