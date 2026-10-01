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


def upcoming_months():
    """
    TF-3: the months the team form offers, oldest first.

    The current month plus MONTHS_AHEAD more, e.g. on Oct 1, 2026:
    ["2026-10", "2026-11", ..., "2027-04"]. Past months are never included.

    "Current" uses today's date in Eastern time (settings.TIME_ZONE), so at
    11 pm Eastern on Nov 30 it's still November, even though it's already
    December 1 in UTC, which is how the server stores times.
    """
    today = timezone.localdate()
    months = []
    for offset in range(MONTHS_AHEAD + 1):
        # Count months from year 0 so adding an offset rolls over the year
        # naturally: December (index 11) + 1 becomes January of the next year.
        index = today.year * 12 + (today.month - 1) + offset
        year, number = divmod(index, 12)
        months.append(f'{year}-{number + 1:02d}')
    return months
