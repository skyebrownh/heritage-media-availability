"""
Small helpers for months stored as "YYYY-MM" text (e.g. "2026-11").

SPEC.md stores months as text rather than dates because a month has no day:
"2026-11" is exactly one value, can't be confused with "Nov 1", and sorts
correctly as plain text. These helpers check and describe those strings.
They're used by the models now and by the team form later (#6, #8).
"""

import calendar
import re

from django.core.exceptions import ValidationError
from django.utils import timezone

# TF-3: the team can submit for the current month plus this many months ahead.
MONTHS_AHEAD = 6

# Four-digit year, a dash, then 01–12. Shared with the database CHECK
# constraints in models.py so Python and Postgres agree on what's valid.
MONTH_PATTERN = r'^\d{4}-(0[1-9]|1[0-2])$'


def validate_month(value):
    """Raise ValidationError unless value is a real month like "2026-11"."""
    if not isinstance(value, str) or not re.fullmatch(MONTH_PATTERN, value):
        raise ValidationError(
            'Enter a month like 2026-11 (year, dash, two-digit month).',
            code='invalid_month',
        )


def split_month(month):
    """Return (year, month_number) as integers for a "YYYY-MM" string."""
    year, number = month.split('-')
    return int(year), int(number)


def month_label(month):
    """Friendly name for a month: "2026-11" → "November 2026"."""
    year, number = split_month(month)
    return f'{calendar.month_name[number]} {year}'


def days_in_month(month):
    """Number of days in a month, e.g. 30 for "2026-11" and 29 for "2028-02"."""
    year, number = split_month(month)
    # monthrange returns (weekday of the 1st, number of days); we need the second.
    return calendar.monthrange(year, number)[1]


def shift_month(month, offset):
    """
    The month `offset` months after `month` (or before, if negative).

    shift_month("2026-12", 1) → "2027-01"; shift_month("2026-01", -1) → "2025-12".
    """
    year, number = split_month(month)
    # Count months from year 0 so adding an offset rolls over the year
    # naturally: December (index 11) + 1 becomes January of the next year.
    index = year * 12 + (number - 1) + offset
    year, number = divmod(index, 12)
    return f'{year}-{number + 1:02d}'


def upcoming_months():
    """
    TF-3: the months the team form offers, oldest first.

    The current month plus MONTHS_AHEAD more, e.g. on Oct 1, 2026:
    ["2026-10", "2026-11", ..., "2027-04"]. Past months are never included.

    "Current" uses today's date in Eastern time (settings.TIME_ZONE), so at
    11 pm Eastern on Nov 30 it's still November, even though it's already
    December 1 in UTC, which is how the server stores times.
    """
    current = timezone.localdate().strftime('%Y-%m')
    return [shift_month(current, offset) for offset in range(MONTHS_AHEAD + 1)]


def month_weeks(month):
    """
    TF-5: a month laid out as calendar rows, weeks starting on Sunday.

    Returns a list of weeks; each week is 7 items, either a date in the month
    or None for the blank squares before the 1st and after the last day.
    E.g. October 2026 starts on a Thursday, so its first week is
    [None, None, None, None, Oct 1, Oct 2, Oct 3].
    """
    year, number = split_month(month)
    # firstweekday=6 makes weeks start on Sunday, as on US paper calendars.
    # monthdatescalendar fills the edge squares with days from the next and
    # previous months; we blank those out so only this month's days show.
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(year, number)
    return [[day if day.month == number else None for day in week] for week in weeks]
