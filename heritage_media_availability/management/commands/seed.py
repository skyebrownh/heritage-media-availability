"""
`manage.py seed <scenario>`: reset the local database to a known test setup (#26).

    uv run --env-file .env python manage.py seed dashboard
    uv run --env-file .env python manage.py seed --list

Deletes all members, submissions and closed months (and their admin History),
then loads one scenario from seeding.SCENARIOS. Admin accounts are kept, so
you stay logged in. It only runs on a local development database.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from ...models import ClosedMonth, Member, Submission
from ...months import month_label, shift_month
from ...seeding import SCENARIOS, reset, this_month

# Database hosts that mean "this computer". An empty host connects through
# a local socket file, which is also this computer.
LOCAL_HOSTS = {'', 'localhost', '127.0.0.1', '::1'}


def unsafe_reason(debug, database):
    """
    Why seeding here would be unsafe, or None if it's fine.

    Two independent checks, so one mistake isn't enough to wipe real data:
    production runs with DEBUG off, and Railway's database is never on
    localhost. Even `railway ssh` into the live app fails both.
    """
    if not debug:
        return 'DEBUG is off. seed only runs in local development (DEBUG=true in .env).'
    host = database.get('HOST') or ''
    if host not in LOCAL_HOSTS:
        return f'The database host is "{host}", not this computer. seed only runs on a local database.'
    return None


def counted(number, noun):
    """E.g. "1 closed month", "9 members"."""
    return f'{number} {noun}' if number == 1 else f'{number} {noun}s'


class Command(BaseCommand):
    """Reset local data and load a named test scenario."""

    help = 'Delete all members, submissions and closed months, then load a test scenario. Local only.'

    def add_arguments(self, parser):
        """Define the command's options: the scenario name, --list, and --no-input."""
        parser.add_argument('scenario', nargs='?', help='Which scenario to load (see --list).')
        parser.add_argument(
            '--list', action='store_true', dest='list_scenarios', help='List the scenarios and exit.',
        )
        # Same flag names as Django's own `flush` command.
        parser.add_argument(
            '--noinput', '--no-input', action='store_false', dest='interactive',
            help="Don't ask for confirmation.",
        )

    def handle(self, *args, scenario=None, list_scenarios=False, interactive=True, **options):
        """Check it's safe, confirm, then reset and load the scenario in one transaction."""
        if list_scenarios:
            for name, details in SCENARIOS.items():
                self.stdout.write(f'{name}: {details.description}')
            return

        if scenario not in SCENARIOS:
            names = ', '.join(SCENARIOS)
            if scenario is None:
                raise CommandError(f'Name a scenario to load: {names}. Use --list for descriptions.')
            raise CommandError(f'No scenario called "{scenario}". Choose one of: {names}.')

        reason = unsafe_reason(settings.DEBUG, connection.settings_dict)
        if reason:
            raise CommandError(reason)

        if interactive:
            answer = input(
                'This deletes all members, submissions and closed months in the '
                f'"{connection.settings_dict["NAME"]}" database. Type \'yes\' to continue: '
            )
            if answer.strip().lower() != 'yes':
                self.stdout.write('Cancelled. Nothing was changed.')
                return

        # All or nothing: if loading fails part-way, the reset is undone too.
        with transaction.atomic():
            reset()
            SCENARIOS[scenario].load()

        counts = ', '.join([
            counted(Member.objects.count(), 'member'),
            counted(Submission.objects.count(), 'submission'),
            counted(ClosedMonth.objects.count(), 'closed month'),
        ])
        self.stdout.write(self.style.SUCCESS(
            f'Loaded "{scenario}": {counts}. Next month is {month_label(shift_month(this_month(), 1))}.'
        ))
