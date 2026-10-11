"""
Database models (tables) for the Heritage Media Availability app.

Three tables, matching SPEC.md's data model:
- Member: the roster (AD-2)
- Submission: every form submission ever made (last one per month wins)
- ClosedMonth: one row per month Skye has closed (AD-8)
"""

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from .months import MONTH_PATTERN, days_in_month, month_label, validate_month


class Member(models.Model):
    """
    One person on the media team roster (AD-2).

    Skye manages these in Django admin. People are never deleted, only marked
    inactive, so their past submissions keep pointing at a real member.
    """

    # Both names are required (Django CharFields are required unless blank=True).
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    # AD-2: inactive people drop out of the dropdown, tracker and copy output,
    # but stay in the database with their history.
    is_active = models.BooleanField(
        'active',
        default=True,
        help_text='Untick when someone steps away. Their past submissions are kept.',
    )
    created_at = models.DateTimeField('added', auto_now_add=True)

    class Meta:
        # TF-2 and the admin views sort by first name, then last name.
        # Lower() makes the order ignore capitalization ("amy" sorts next to "Amy").
        ordering = [Lower('first_name'), Lower('last_name')]
        constraints = [
            # AD-2: "Bob Smith" and "bob smith" are the same person.
            # A plain unique_together would treat those as different, so we
            # make Postgres enforce uniqueness on the lowercased pair instead.
            # Being in the database, it also stops duplicates that slip past
            # the form (e.g. two admin tabs saving at the same moment).
            models.UniqueConstraint(
                Lower('first_name'),
                Lower('last_name'),
                name='unique_member_name_ignoring_case',
                violation_error_message='Someone with this first and last name is already on the roster.',
            ),
        ]

    def __str__(self):
        """Full name, e.g. "Bob Smith". Used by Django admin and, later, the TF-2 dropdown."""
        return f'{self.first_name} {self.last_name}'


class SubmissionQuerySet(models.QuerySet):
    """Extra queries for submissions, available as Submission.objects.<name>()."""

    def current(self):
        """
        The newest submission per member and month ("last submission wins").

        Uses Postgres DISTINCT ON: rows are sorted newest-first within each
        (member, month) group, and DISTINCT ON keeps only the first row of each
        group. One query, no matter how many times people resubmitted.
        Postgres requires the ORDER BY to start with the DISTINCT ON columns,
        so re-sort the results in Python if you need a different order.
        """
        return self.order_by('member_id', 'month', '-submitted_at').distinct('member_id', 'month')


class Submission(models.Model):
    """
    One form submission: a member's availability for one month.

    Rows are never updated or deleted. Resubmitting adds a new row, and the
    newest per member and month is the current one. Older rows stay as
    history (SPEC.md business rules: "One current submission per person per month").
    """

    class Kind(models.TextChoices):
        """The three mutually exclusive answers (TF-6). Stored as the left-hand value."""

        DAYS = 'days', 'Specific days'
        AVAILABLE_ALL = 'available_all', 'Available all month'
        UNAVAILABLE_ALL = 'unavailable_all', 'Unavailable all month'

    # PROTECT makes the database refuse to delete a member who has submissions,
    # a second guard (after the admin's disabled Delete) for keeping history.
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name='submissions')
    month = models.CharField(max_length=7, validators=[validate_month], help_text='YYYY-MM, e.g. 2026-11')
    kind = models.CharField('choice', max_length=20, choices=Kind.choices)
    # Day numbers within the month, e.g. [3, 4, 5, 20]. Empty unless kind is "days".
    days = ArrayField(models.PositiveSmallIntegerField(), default=list, blank=True)
    # TF-7: optional, up to 500 characters (max_length is enforced by Postgres too).
    notes = models.CharField(max_length=500, blank=True)
    # default=timezone.now (rather than auto_now_add) records the time on save
    # but still lets tests set an exact time to check "newest wins".
    submitted_at = models.DateTimeField('submitted', default=timezone.now, editable=False)

    objects = SubmissionQuerySet.as_manager()

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            # Speeds up current(), which groups by member and month, newest first.
            models.Index(fields=['member', 'month', '-submitted_at'], name='submission_member_month_newest'),
        ]
        constraints = [
            # Database-level backups for the rules clean() explains in friendlier words.
            # They catch bad rows from any code path that skips validation.
            models.CheckConstraint(
                condition=Q(month__regex=MONTH_PATTERN),
                name='submission_month_format',
            ),
            # "All-month options are exclusive": days only (and at least one) for kind "days".
            # This also limits kind to the three allowed values.
            models.CheckConstraint(
                condition=(
                    Q(kind='days', days__len__gt=0)
                    | Q(kind__in=['available_all', 'unavailable_all'], days__len=0)
                ),
                name='submission_kind_matches_days',
            ),
            # No month has a day 0 or 32. clean() does the exact per-month check (e.g. Feb 30).
            models.CheckConstraint(
                condition=Q(days__contained_by=list(range(1, 32))),
                name='submission_days_in_range',
            ),
        ]

    def __str__(self):
        """E.g. "Bob Smith – November 2026"."""
        return f'{self.member} – {month_label(self.month)}'

    def clean(self):
        """
        Check the kind/days rules with plain-language messages, and tidy the days.

        Django calls this from full_clean(), which forms run before saving.
        """
        # Store days in order with no repeats, so [5, 3, 5] becomes [3, 5].
        self.days = sorted(set(self.days or []))

        if self.kind == self.Kind.DAYS and not self.days:
            raise ValidationError({'days': 'Pick at least one day, or choose an all-month option.'})
        if self.kind != self.Kind.DAYS and self.days:
            raise ValidationError({'days': 'Days can only be picked with "Pick specific days".'})

        # The per-month day check needs a valid month; if the month itself is bad,
        # its own field error is already being reported, so skip this check.
        try:
            validate_month(self.month)
        except ValidationError:
            return
        last_day = days_in_month(self.month)
        bad_days = [day for day in self.days if not 1 <= day <= last_day]
        if bad_days:
            raise ValidationError({
                'days': f'{month_label(self.month)} has no day {", ".join(map(str, bad_days))}.',
            })


class ClosedMonth(models.Model):
    """
    A month Skye has closed (AD-8). A row here means the month is closed.

    Months are open by default; there's no "open" row. Reopening deletes the row.
    The server rejects team submissions for any month listed here.
    """

    # The month itself is the primary key, so the database guarantees a month
    # can't be closed twice.
    month = models.CharField(
        primary_key=True,
        max_length=7,
        validators=[validate_month],
        error_messages={'unique': 'That month is already closed.'},
    )
    closed_at = models.DateTimeField('closed', auto_now_add=True)

    class Meta:
        ordering = ['-month']  # "YYYY-MM" sorts correctly as text, so newest first.
        # The admin calls these "Months" (#43): the Months page lists every
        # month, open or closed. Only the label changes; the table doesn't.
        verbose_name = 'month'
        verbose_name_plural = 'months'
        constraints = [
            models.CheckConstraint(condition=Q(month__regex=MONTH_PATTERN), name='closed_month_format'),
        ]

    def __str__(self):
        """E.g. "November 2026"."""
        return month_label(self.month)
