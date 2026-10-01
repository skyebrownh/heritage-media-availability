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
