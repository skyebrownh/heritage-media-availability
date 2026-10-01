"""
Database models (tables) for the Heritage Media Availability app.

Week 1 has only the roster (`Member`). Submissions and closed months
arrive in Week 2 with the team form.
"""

from django.db import models
from django.db.models.functions import Lower


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
