"""
`manage.py load_snapshot`: replace this site's data with a copy of production's (#45).

Used to refresh the staging site, so testers see the real roster and
answers. Two steps, run from Skye's computer (exact commands in CLAUDE.md):

1. Copy production's data to a file, with Django's own read-only
   `dumpdata`, limited to the app's three tables (SNAPSHOT_MODELS):
       railway ssh --environment production -- python manage.py dumpdata \\
           heritage_media_availability.member heritage_media_availability.submission \\
           heritage_media_availability.closedmonth > production-snapshot.json
2. Load it into staging, piped in (the "-"):
       railway ssh --environment staging -- python manage.py load_snapshot - --no-input \\
           < production-snapshot.json

Deletes all members, submissions and closed months (and their admin
History) first, like `seed`, then loads the file, all or nothing. It runs
only on staging or a local database (staging.unsafe_reason), never on
production, and only accepts the app's three tables, so a file with
admin logins or anything else in it is refused before anything changes.
"""

import json
import sys

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from ...models import ClosedMonth, Member, Submission
from ...seeding import reset
from ...staging import unsafe_reason

# The only tables a snapshot may contain, as dumpdata names them. Not admin
# accounts, sessions or History: staging keeps its own login, and no
# password hashes leave production.
SNAPSHOT_MODELS = {
    'heritage_media_availability.member',
    'heritage_media_availability.submission',
    'heritage_media_availability.closedmonth',
}


class Command(BaseCommand):
    """Replace this site's members, submissions and closed months with a snapshot."""

    help = "Replace members, submissions and closed months with a dumpdata file (\"-\" reads it piped in). Staging or local only."

    def add_arguments(self, parser):
        """The file to load (or "-" for piped input), and --no-input."""
        parser.add_argument('path', help='The dumpdata JSON file, or "-" to read it piped in.')
        # Same flag names as Django's own `flush` command. Piped input needs
        # it, since the pipe is the file, not someone typing "yes".
        parser.add_argument(
            '--noinput', '--no-input', action='store_false', dest='interactive',
            help="Don't ask for confirmation.",
        )

    def handle(self, *args, path, interactive=True, **options):
        """Check it's safe, read and check the file, confirm, then replace the data in one transaction."""
        reason = unsafe_reason(connection.settings_dict)
        if reason:
            raise CommandError(reason)

        objects = self.read(path)

        if interactive:
            answer = input(
                'This replaces all members, submissions and closed months in the '
                f'"{connection.settings_dict["NAME"]}" database with the snapshot. Type \'yes\' to continue: '
            )
            if answer.strip().lower() != 'yes':
                self.stdout.write('Cancelled. Nothing was changed.')
                return

        # All or nothing: if loading fails part-way, the reset is undone too.
        with transaction.atomic():
            reset()
            for obj in objects:
                obj.save()
            # Records arrive with their production IDs, so move Postgres's
            # ID counters past them; otherwise the next member added here
            # would be given an ID that's already taken. (Django's
            # `loaddata` does the same after loading.) no_style(): the SQL
            # helper takes a "style" for printing SQL, and the command's own
            # style adds terminal color codes, which would end up inside the
            # SQL sent to Postgres and break it.
            models = [Member, Submission, ClosedMonth]
            with connection.cursor() as cursor:
                for sql in connection.ops.sequence_reset_sql(no_style(), models):
                    cursor.execute(sql)

        self.stdout.write(self.style.SUCCESS(
            f'Loaded the snapshot: {Member.objects.count()} members, '
            f'{Submission.objects.count()} submissions, {ClosedMonth.objects.count()} closed months.'
        ))

    def read(self, path):
        """
        Read the snapshot and turn it into unsaved records, refusing it
        (before anything is deleted) if it isn't valid JSON or contains
        anything other than the three app tables.
        """
        try:
            if path == '-':
                text = sys.stdin.read()
            else:
                with open(path, encoding='utf-8') as file:
                    text = file.read()
            data = json.loads(text)
        except FileNotFoundError:
            raise CommandError(f'No file called "{path}".')
        except json.JSONDecodeError as error:
            raise CommandError(f'The snapshot isn\'t valid JSON ({error}). Was the dumpdata step cut short?')

        if not isinstance(data, list) or not data:
            raise CommandError('The snapshot is empty. Nothing was changed.')
        others = sorted({str(item.get('model')) for item in data if item.get('model') not in SNAPSHOT_MODELS})
        if others:
            raise CommandError(
                f'The snapshot contains {", ".join(others)}. Only members, submissions and '
                'closed months can be loaded. Nothing was changed.'
            )
        # Django's own reader for dumpdata files: builds each record without saving it yet.
        return list(serializers.deserialize('json', text))
