"""
Turning saved submissions into readable text.

day_ranges() collapses runs of days ([3, 4, 5, 6, 7, 20] → 3-7 and 20).
The TF-10 confirmation and TF-9 summary use it now; Week 3's copy formats
(AD-7, "Bob: 3-7, 20") will reuse it, so all agree on how ranges are grouped.

display_names() gives the short names ("Bob", "Bob J.") that Skye's
dashboard and copy text use, and by_person_text() builds the by-person
copy text (AD-7), and by_date_text() the by-date copy text.
"""

import calendar
from collections import Counter


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


def ranges_text(days):
    """The days as compact ranges with no month: [3, 4, 5, 6, 7, 20] → "3-7, 20"."""
    return ', '.join(format_range(first, last) for first, last in day_ranges(days))


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
    _, number = split_month(month)
    return f'{calendar.month_abbr[number]} {ranges_text(days)}'


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
    TF-9: someone's current answer for a month, for the team form's
    "Your last answer" reminder: "Nov 3-7, 20", "Available all month" or
    "Unavailable all month".

    It stands on its own line in large text (#41), so it starts with a
    capital. No submission date: volunteers need what they said, not when
    (decision 2026-10-12); the dashboard still shows Skye the time.
    """
    if submission.kind == Submission.Kind.AVAILABLE_ALL:
        return 'Available all month'
    if submission.kind == Submission.Kind.UNAVAILABLE_ALL:
        return 'Unavailable all month'
    return days_list(submission.month, submission.days)


def answer_text(submission):
    """
    AD-7: one person's answer as the by-person copy text writes it.

    "3-7, 20" for days, "NA" for available all month, "unavailable all month",
    or "no response" when `submission` is None. Wording is exactly SPEC.md's.
    """
    if submission is None:
        return 'no response'
    if submission.kind == Submission.Kind.AVAILABLE_ALL:
        return 'NA'
    if submission.kind == Submission.Kind.UNAVAILABLE_ALL:
        return 'unavailable all month'
    return ranges_text(submission.days)


def answer_label(submission):
    """
    AD-5: one person's answer as the by-person view shows it on screen.

    Same ranges as the copy text, but the all-month and missing answers are
    spelled out ("Available all month" rather than "NA"), since the view is
    read, not pasted.
    """
    if submission is None:
        return 'No response'
    if submission.kind == Submission.Kind.AVAILABLE_ALL:
        return 'Available all month'
    if submission.kind == Submission.Kind.UNAVAILABLE_ALL:
        return 'Unavailable all month'
    return ranges_text(submission.days)


def by_person_text(responses):
    """
    AD-7: the by-person copy text for a month, e.g.

        Bob: 3-7, 20
        Jim: NA
        Grace: (3rd Sundays only)
        Tom: no response

    One line per active member, in MonthResponses.by_person order
    (responders, then standing, then non-responders, each A–Z). Notes and
    inactive members are never included (SPEC.md copy formats; decision
    2026-10-03). Someone with a standing note who hasn't responded gets
    their note in parentheses instead of "no response" (#46), e.g.
    "Grace: (3rd Sundays only)"; once they respond, only their answer shows.
    """
    lines = []
    for response in responses.by_person:
        answer = f'({response.standing})' if response.is_standing else answer_text(response.submission)
        lines.append(f'{response.name}: {answer}')
    return '\n'.join(lines)


def by_date_text(responses):
    """
    AD-7: the by-date copy text for a month, e.g.

        Unavailable all month: Sam
        1: Jane
        4: Bob, Jane

    The "Unavailable all month" line comes first, and is left out entirely
    when nobody is. Then one line per day anyone is out, in date order.
    Returns "" when nobody is out at all.
    """
    by_date = responses.by_date
    lines = []
    if by_date.all_month:
        lines.append(f'Unavailable all month: {", ".join(by_date.all_month)}')
    for day, names in by_date.days:
        lines.append(f'{day.day}: {", ".join(names)}')
    return '\n'.join(lines)
