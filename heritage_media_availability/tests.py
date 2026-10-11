"""
Automated tests for the Heritage Media Availability app.

Run them with:  uv run --env-file .env python manage.py test
Django creates a separate throwaway test database, so your real data is safe.
"""

import os
import runpy
import re
from datetime import UTC, date, datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import CommandError, call_command
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from config.env import env_bool, env_list, env_required, parse_database_url

from .dashboard import default_month, month_options, month_responses
from .formatting import (
    answer_label,
    answer_text,
    by_date_text,
    by_person_text,
    confirmation_message,
    day_ranges,
    days_list,
    display_names,
    previous_summary,
    ranges_text,
)
from .forms import CLOSED_MONTH_MESSAGE
from .models import ClosedMonth, Member, Submission
from .months import days_in_month, month_label, month_weeks, shift_month, upcoming_months, validate_month
from .seeding import SCENARIOS


def at_utc(*args):
    """Patch "now" to a fixed UTC moment, so date-dependent code is predictable in tests."""
    return mock.patch('django.utils.timezone.now', return_value=datetime(*args, tzinfo=UTC))


def visible_text(response):
    """
    A page's words with the HTML tags removed and spaces collapsed, roughly
    what a reader sees. Lets tests check wording like "5 of 7 responded"
    even when the page styles the number and the words separately.
    """
    html = re.sub(r'<script.*?</script>', ' ', response.content.decode(), flags=re.S)
    return ' '.join(re.sub(r'<[^>]+>', ' ', html).split())


class TeamFormPageTests(TestCase):
    """The team form page at "/" (TF-1 to TF-4)."""

    url = reverse('heritage_media_availability:team_form')

    def test_form_is_the_public_site_root(self):
        # TF-1: one shared link, no login. The link is the bare domain.
        self.assertEqual(self.url, '/')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Heritage Media Availability')
        self.assertContains(response, "Let the Scheduler know which days you can't serve.")

    def test_name_dropdown_lists_active_members_sorted(self):
        # TF-2: "First Last", A–Z by first then last name, active only.
        Member.objects.create(first_name='jane', last_name='Doe')
        Member.objects.create(first_name='Bob', last_name='Smith')
        Member.objects.create(first_name='Bob', last_name='Jones')
        Member.objects.create(first_name='Ann', last_name='Gone', is_active=False)
        names = [label for value, label in self.client.get(self.url).context['form'].fields['member'].choices]
        self.assertEqual(names, ['Choose your name', 'Bob Jones', 'Bob Smith', 'jane Doe'])

    def test_month_dropdown_offers_current_month_plus_six(self):
        with at_utc(2026, 10, 1, 12, 0):
            choices = self.client.get(self.url).context['form'].fields['month'].choices
        self.assertEqual(choices[0], ('', 'Choose a month'))
        self.assertEqual(
            [value for value, label in choices[1:]],
            ['2026-10', '2026-11', '2026-12', '2027-01', '2027-02', '2027-03', '2027-04'],
        )
        self.assertEqual(choices[2][1], 'November 2026')

    def test_no_month_is_preselected(self):
        response = self.client.get(self.url)
        self.assertContains(response, '<option value="" selected>Choose a month</option>', html=True)

    def test_closed_month_is_labeled_and_marked_for_the_script(self):
        # TF-3 label and the data-closed marker the TF-4 script reads.
        ClosedMonth.objects.create(month='2026-11')
        with at_utc(2026, 10, 1, 12, 0):
            response = self.client.get(self.url)
        self.assertContains(response, '<option value="2026-11" data-closed>November 2026 (closed)</option>', html=True)
        self.assertContains(response, '<option value="2026-12">December 2026</option>', html=True)

    def test_closed_message_is_ready_for_the_script(self):
        # TF-4: exact wording, defined once, plus the hint toward another month.
        # It sits in a <template> until the script copies it in; showing and
        # hiding it is covered by the manual test steps.
        self.assertEqual(CLOSED_MONTH_MESSAGE, "This month's schedule is finalized. Please text Skye with any changes.")
        html = self.client.get(self.url).content.decode()
        template = re.search(r'<template id="closed-month-template">(.*?)</template>', html, re.DOTALL).group(1)
        self.assertIn(escape(CLOSED_MONTH_MESSAGE), template)
        self.assertIn('You can choose a different month above.', template)
        # Not shown yet: the live region starts empty.
        self.assertIn('<div id="closed-month-message" role="status"></div>', html)


class TeamFormDetailsTests(TestCase):
    """The all-month choice, calendars and notes on the team form (TF-5 to TF-7)."""

    url = reverse('heritage_media_availability:team_form')

    def get(self):
        """Load the form as if today were Oct 1, 2026 (months 2026-10 to 2027-04)."""
        with at_utc(2026, 10, 1, 12, 0):
            return self.client.get(self.url)

    def fieldset(self, html, month):
        """The HTML of one month's calendar fieldset."""
        match = re.search(rf'<fieldset data-month="{month}".*?</fieldset>', html, re.DOTALL)
        self.assertIsNotNone(match, f'No calendar for {month}')
        return match.group(0)

    def test_kind_dropdown_options_and_default(self):
        # TF-6: three options, "Pick specific days" chosen by default.
        response = self.get()
        self.assertContains(response, '<option value="days" selected>Pick specific days</option>', html=True)
        self.assertContains(response, '<option value="available_all">I&#x27;m available all month</option>', html=True)
        self.assertContains(response, '<option value="unavailable_all">I&#x27;m unavailable all month</option>', html=True)

    def test_notes_are_optional_and_capped_at_500(self):
        # TF-7. The help text is linked to the box for screen readers.
        response = self.get()
        self.assertContains(response, 'maxlength="500"')
        self.assertContains(response, 'aria-describedby="id_notes_helptext"')
        self.assertContains(response, 'id="id_notes_helptext"')
        self.assertFalse(response.context['form'].fields['notes'].required)

    def test_one_calendar_per_month_all_starting_disabled(self):
        # The script enables only the chosen month's calendar, so none submit until then.
        html = self.get().content.decode()
        fieldsets = re.findall(r'<fieldset [^>]*>', html)
        self.assertEqual(len(fieldsets), 7)
        for tag in fieldsets:
            self.assertIn('hidden', tag)
            self.assertIn('disabled', tag)

    def test_february_2027_has_28_days_starting_on_monday(self):
        calendar = self.fieldset(self.get().content.decode(), '2027-02')
        self.assertEqual(len(re.findall(r'type="checkbox" name="days"', calendar)), 28)
        self.assertIn('value="28"', calendar)
        self.assertNotIn('value="29"', calendar)
        # Sunday first: one blank square, then Feb 1 under Monday.
        self.assertEqual(month_weeks('2027-02')[0][:2], [None, date(2027, 2, 1)])

    def test_days_have_full_date_labels_for_screen_readers(self):
        calendar = self.fieldset(self.get().content.decode(), '2026-10')
        self.assertIn('<span class="sr-only">Saturday, October 3</span>', calendar)
        self.assertIn('for="day-2026-10-3"', calendar)


class SubmitTests(TestCase):
    """Submitting the team form: server checks and saving (TF-8, business rules)."""

    url = reverse('heritage_media_availability:team_form')
    thanks_url = reverse('heritage_media_availability:thanks')

    def setUp(self):
        self.bob = Member.objects.create(first_name='Bob', last_name='Smith')

    def post(self, **overrides):
        """Submit the form as of Oct 1, 2026: Bob, November, days 3 and 20, unless overridden."""
        data = {'member': self.bob.pk, 'month': '2026-11', 'kind': 'days', 'days': ['3', '20'], 'notes': ''}
        data.update(overrides)
        with at_utc(2026, 10, 1, 12, 0):
            return self.client.post(self.url, data)

    def assertRejected(self, response, message):
        """The form came back (no save) showing message."""
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, message)
        self.assertFalse(Submission.objects.exists())

    def test_valid_submit_saves_and_redirects_to_confirmation(self):
        response = self.post(notes='Can do the 12th, but no rehearsal on the 11th')
        self.assertRedirects(response, self.thanks_url)
        submission = Submission.objects.get()
        self.assertEqual(
            (submission.member, submission.month, submission.kind, submission.days, submission.notes),
            (self.bob, '2026-11', 'days', [3, 20], 'Can do the 12th, but no rehearsal on the 11th'),
        )

    def test_all_month_submit_saves_with_no_days(self):
        self.post(kind='unavailable_all', days=[])
        self.assertEqual(Submission.objects.get().kind, 'unavailable_all')

    def test_resubmitting_adds_a_row_and_the_newest_is_current(self):
        self.post(days=['3'])
        self.post(kind='available_all', days=[])
        self.assertEqual(Submission.objects.count(), 2)
        self.assertEqual(Submission.objects.current().get().kind, 'available_all')

    def test_missing_pieces_get_plain_language_messages(self):
        # TF-8: name, month, and at least one day (or an all-month option).
        self.assertRejected(self.post(member=''), 'Please choose your name.')
        self.assertRejected(self.post(month=''), 'Please choose a month.')
        self.assertRejected(self.post(days=[]), 'Pick at least one day, or choose an all-month option.')

    def test_errors_are_summarized_for_screen_readers(self):
        response = self.post(member='', days=[])
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, 'Almost there! Please fix:')

    def test_ticked_days_survive_a_failed_submit(self):
        response = self.post(member='')
        html = response.content.decode()
        # Tells the script not to pre-fill over the person's edits (TF-9).
        self.assertIn('data-bound="true"', html)
        for day in ['3', '20']:
            self.assertRegex(html, rf'id="day-2026-11-{day}"[^>]*checked')
        self.assertNotRegex(html, r'id="day-2026-11-4"[^>]*checked')

    def test_closed_month_is_rejected_even_from_an_open_form(self):
        # The page was loaded before Skye closed November; the submit still fails.
        ClosedMonth.objects.create(month='2026-11')
        response = self.post()
        # escape(): Django writes the apostrophe as &#x27; in the HTML.
        self.assertRejected(response, escape(CLOSED_MONTH_MESSAGE))
        # The box is drawn by the server, with the hint toward another month.
        html = response.content.decode()
        box = re.search(r'<div id="closed-month-message" role="status">(.*?)</div>\s*</div>', html, re.DOTALL).group(1)
        self.assertIn(escape(CLOSED_MONTH_MESSAGE), box)
        self.assertIn('You can choose a different month above.', box)
        # Only the TF-4 box: no error summary or "pick a day" noise.
        self.assertNotContains(response, 'Almost there!')

    def test_refreshing_after_a_closed_month_rejection_still_rejects(self):
        # Refreshing a page that came from a POST makes the browser send the
        # same POST again ("Confirm form resubmission"). It must fail the same way.
        ClosedMonth.objects.create(month='2026-11')
        for _ in range(3):
            self.assertRejected(self.post(), escape(CLOSED_MONTH_MESSAGE))

    def test_member_made_inactive_after_page_load_is_accepted(self):
        # Decision 2026-10-01: the dropdown hides inactive people, but a stale form still saves.
        self.bob.is_active = False
        self.bob.save()
        self.assertRedirects(self.post(), self.thanks_url)
        self.assertEqual(Submission.objects.get().member, self.bob)

    def test_past_open_month_from_a_stale_form_is_accepted(self):
        # SPEC.md: a closed month is the only reason the server rejects a month.
        self.assertRedirects(self.post(month='2026-09'), self.thanks_url)

    def test_tampered_values_are_rejected(self):
        self.assertRejected(self.post(member='99999'), 'Please choose your name from the list.')
        self.assertRejected(self.post(member='abc'), 'Please choose your name from the list.')
        self.assertRejected(self.post(month='2026-13'), 'Enter a month like 2026-11')
        self.assertRejected(self.post(kind='maybe'), 'Select a valid choice.')
        self.assertRejected(self.post(days=['0']), 'Select a valid choice.')
        self.assertRejected(self.post(days=['32']), 'Select a valid choice.')
        self.assertRejected(self.post(kind='available_all', days=['3']), 'Days can only be picked')
        self.assertRejected(self.post(month='2027-02', days=['30']), 'February 2027 has no day 30.')
        self.assertRejected(self.post(notes='x' * 501), 'at most 500 characters')

    def test_only_get_and_post_are_allowed(self):
        with self.assertLogs('django.request', level='WARNING'):
            self.assertEqual(self.client.put(self.url).status_code, 405)


class CsrfFailurePageTests(TestCase):
    """A stale form token gets a friendly page instead of Django's technical 403."""

    def test_stale_token_shows_friendly_page_and_saves_nothing(self):
        bob = Member.objects.create(first_name='Bob', last_name='Smith')
        # The normal test client skips CSRF checks; this one enforces them like a browser.
        client = Client(enforce_csrf_checks=True)
        data = {'member': bob.pk, 'month': '2026-11', 'kind': 'available_all', 'csrfmiddlewaretoken': 'stale'}
        with self.assertLogs('django.security.csrf', level='WARNING'):
            response = client.post(reverse('heritage_media_availability:team_form'), data)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Your form expired.', status_code=403)
        self.assertContains(response, 'Back to the form', status_code=403)
        self.assertNotContains(response, 'CSRF verification failed', status_code=403)
        self.assertFalse(Submission.objects.exists())


class ConfirmationPageTests(TestCase):
    """TF-10: the page shown after a successful submit."""

    url = reverse('heritage_media_availability:team_form')
    thanks_url = reverse('heritage_media_availability:thanks')

    def setUp(self):
        self.bob = Member.objects.create(first_name='Bob', last_name='Smith')

    def submit(self, **overrides):
        """Submit for Bob in October 2026 and follow the redirect to the confirmation."""
        data = {'member': self.bob.pk, 'month': '2026-10', 'kind': 'days', 'days': [], 'notes': ''}
        data.update(overrides)
        with at_utc(2026, 10, 1, 12, 0):
            return self.client.post(self.url, data, follow=True)

    def test_restates_days_as_ranges_with_first_name(self):
        response = self.submit(days=['3', '4', '5', '6', '7', '20'])
        self.assertContains(response, 'Thanks, Bob! You&#x27;re unavailable Oct 3-7, and 20.')

    def test_shows_notes_and_another_month_button(self):
        response = self.submit(kind='available_all', notes='Can do the 12th, not the rehearsal')
        self.assertContains(response, 'Thanks, Bob! You&#x27;re available all of October.')
        self.assertContains(response, 'Can do the 12th, not the rehearsal')
        self.assertContains(response, f'href="{self.url}"')
        self.assertContains(response, 'Fill out another month')

    def test_refreshing_does_not_submit_again(self):
        self.submit(kind='unavailable_all')
        for _ in range(2):
            response = self.client.get(self.thanks_url)
            self.assertContains(response, 'Thanks, Bob! You&#x27;re unavailable all of October.')
        self.assertEqual(Submission.objects.count(), 1)

    def test_opening_directly_goes_back_to_the_form(self):
        self.assertRedirects(self.client.get(self.thanks_url), self.url)


class LastSubmissionLookupTests(TestCase):
    """TF-9: the JSON lookup the form's script uses to pre-fill."""

    url = reverse('heritage_media_availability:last_submission')

    def setUp(self):
        self.bob = Member.objects.create(first_name='Bob', last_name='Smith')
        self.jane = Member.objects.create(first_name='Jane', last_name='Doe')

    def lookup(self, member, month):
        """Call the lookup and return the response."""
        return self.client.get(self.url, {'member': member, 'month': month})

    def add(self, member, month, kind='days', days=(), notes='', when=datetime(2026, 10, 2, 16, 0, tzinfo=UTC)):
        """Save a submission at a given time (default Oct 2, noon Eastern)."""
        return Submission.objects.create(
            member=member, month=month, kind=kind, days=list(days), notes=notes, submitted_at=when
        )

    def test_returns_the_current_submission(self):
        self.add(self.bob, '2026-11', days=[1], when=datetime(2026, 10, 1, 16, 0, tzinfo=UTC))
        self.add(self.bob, '2026-11', days=[3, 4, 5, 6, 7, 20], notes='No rehearsal on the 11th')
        response = self.lookup(self.bob.pk, '2026-11')
        self.assertEqual(response.json(), {
            'found': True,
            'kind': 'days',
            'days': [3, 4, 5, 6, 7, 20],
            'notes': 'No rehearsal on the 11th',
            'summary': 'Your last submission (10/02/26): Nov 3-7, 20. Submitting again replaces it.',
        })

    def test_only_the_one_member_and_month(self):
        # Never another person's or another month's answer, and never the history.
        self.add(self.jane, '2026-11', kind='available_all')
        self.add(self.bob, '2026-12', kind='available_all')
        self.assertEqual(self.lookup(self.bob.pk, '2026-11').json(), {'found': False})

    def test_unknown_member_is_simply_not_found(self):
        self.assertEqual(self.lookup(99999, '2026-11').json(), {'found': False})

    def test_bad_parameters_are_rejected(self):
        for member, month in [('', '2026-11'), ('abc', '2026-11'), (self.bob.pk, ''), (self.bob.pk, '2026-13')]:
            with self.subTest(member=member, month=month):
                with self.assertLogs('django.request', level='WARNING'):
                    self.assertEqual(self.lookup(member, month).status_code, 400)

    def test_answers_are_never_cached(self):
        # A resubmission must show up straight away, not an old cached answer.
        self.assertIn('no-store', self.lookup(self.bob.pk, '2026-11')['Cache-Control'])

    def test_form_page_has_the_summary_box(self):
        response = self.client.get(reverse('heritage_media_availability:team_form'))
        self.assertContains(response, 'id="previous-summary" role="status"')
        self.assertContains(response, self.url)
        self.assertContains(response, 'data-bound="false"')


class FormattingTests(TestCase):
    """Day ranges and the TF-10 confirmation sentence."""

    def test_day_ranges(self):
        self.assertEqual(day_ranges([]), [])
        self.assertEqual(day_ranges([20]), [(20, 20)])
        self.assertEqual(day_ranges([20, 3, 4, 5, 6, 7, 5]), [(3, 7), (20, 20)])
        self.assertEqual(day_ranges(range(1, 31)), [(1, 30)])
        self.assertEqual(day_ranges([1, 3, 5]), [(1, 1), (3, 3), (5, 5)])

    def message(self, kind='days', days=(), month='2026-10'):
        """The confirmation sentence for an unsaved submission by Bob."""
        member = Member(first_name='Bob', last_name='Smith')
        return confirmation_message(Submission(member=member, month=month, kind=kind, days=list(days)))

    def test_month_is_named_once_however_many_ranges(self):
        self.assertEqual(self.message(days=[3, 4, 5, 6, 7]), "Thanks, Bob! You're unavailable Oct 3-7.")
        self.assertEqual(self.message(days=[20]), "Thanks, Bob! You're unavailable Oct 20.")
        self.assertEqual(self.message(days=[3, 4, 5, 6, 7, 20]), "Thanks, Bob! You're unavailable Oct 3-7, and 20.")
        self.assertEqual(
            self.message(days=[3, 4, 5, 6, 7, 10, 20]), "Thanks, Bob! You're unavailable Oct 3-7, 10, and 20."
        )
        self.assertEqual(self.message(days=[1, 2], month='2026-09'), "Thanks, Bob! You're unavailable Sep 1-2.")

    def test_all_month_wording(self):
        self.assertEqual(self.message('available_all', month='2026-11'), "Thanks, Bob! You're available all of November.")
        self.assertEqual(self.message('unavailable_all', month='2026-11'), "Thanks, Bob! You're unavailable all of November.")


class PreviousSummaryTests(TestCase):
    """TF-9: wording of the earlier-submission summary."""

    def summary(self, kind='days', days=(), when=datetime(2026, 10, 2, 16, 0, tzinfo=UTC)):
        """The summary for an unsaved November submission made at `when`."""
        member = Member(first_name='Bob', last_name='Smith')
        return previous_summary(Submission(member=member, month='2026-11', kind=kind, days=list(days), submitted_at=when))

    def test_days_name_the_month_once(self):
        self.assertEqual(days_list('2026-10', [3, 4, 5, 6, 7, 20]), 'Oct 3-7, 20')
        self.assertEqual(days_list('2026-10', [3, 4, 5, 6, 7, 10, 20]), 'Oct 3-7, 10, 20')
        self.assertEqual(
            self.summary(days=[3, 4, 5, 6, 7, 20]),
            'Your last submission (10/02/26): Nov 3-7, 20. Submitting again replaces it.',
        )

    def test_all_month_wording(self):
        self.assertEqual(
            self.summary('available_all'), 'Your last submission (10/02/26): available all month. Submitting again replaces it.'
        )
        self.assertEqual(
            self.summary('unavailable_all'),
            'Your last submission (10/02/26): unavailable all month. Submitting again replaces it.',
        )

    def test_date_is_in_eastern_time(self):
        # 2 am UTC on Oct 3 is still 10 pm Oct 2 in New York.
        self.assertIn('(10/02/26)', self.summary('available_all', when=datetime(2026, 10, 3, 2, 0, tzinfo=UTC)))


class MonthWeeksTests(SimpleTestCase):
    """TF-5: months laid out as Sunday-first weeks."""

    def test_october_2026_starts_on_thursday(self):
        first_week = month_weeks('2026-10')[0]
        self.assertEqual(first_week, [None, None, None, None, date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)])

    def test_every_week_has_seven_squares_and_every_day_appears_once(self):
        weeks = month_weeks('2026-11')
        self.assertTrue(all(len(week) == 7 for week in weeks))
        days = [day.day for week in weeks for day in week if day]
        self.assertEqual(days, list(range(1, 31)))


class UpcomingMonthsTests(SimpleTestCase):
    """TF-3: the month window is based on today's date in Eastern time."""

    def test_wraps_into_next_year(self):
        with at_utc(2026, 9, 15, 12, 0):
            self.assertEqual(
                upcoming_months(),
                ['2026-09', '2026-10', '2026-11', '2026-12', '2027-01', '2027-02', '2027-03'],
            )

    def test_uses_eastern_time_not_utc(self):
        # 3 am UTC on Dec 1 is still 10 pm Nov 30 in New York, so November is "current".
        with at_utc(2026, 12, 1, 3, 0):
            self.assertEqual(upcoming_months()[0], '2026-11')
        # 6 am UTC on Dec 1 is 1 am Dec 1 in New York.
        with at_utc(2026, 12, 1, 6, 0):
            self.assertEqual(upcoming_months()[0], '2026-12')


class ParseDatabaseUrlTests(SimpleTestCase):
    """DATABASE_URL is turned into Django's database settings correctly."""

    def test_full_url(self):
        config = parse_database_url('postgresql://alice:secret@db.example.com:6543/mydb')
        self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config['NAME'], 'mydb')
        self.assertEqual(config['USER'], 'alice')
        self.assertEqual(config['PASSWORD'], 'secret')
        self.assertEqual(config['HOST'], 'db.example.com')
        self.assertEqual(config['PORT'], '6543')

    def test_local_url_without_password_or_port(self):
        # The shape Homebrew Postgres uses on Skye's laptop.
        config = parse_database_url('postgresql://skye@localhost/heritage_media_availability')
        self.assertEqual(config['USER'], 'skye')
        self.assertEqual(config['PASSWORD'], '')
        self.assertEqual(config['PORT'], '')

    def test_encoded_characters_in_password_are_decoded(self):
        # "p@ss/word" must be URL-encoded inside a URL; we should get the real password back.
        config = parse_database_url('postgres://bob:p%40ss%2Fword@localhost:5432/db')
        self.assertEqual(config['PASSWORD'], 'p@ss/word')

    def test_non_postgres_url_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_database_url('sqlite:///db.sqlite3')


class EnvHelperTests(SimpleTestCase):
    """The small env-reading helpers handle missing and messy values."""

    def test_env_required_raises_when_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ImproperlyConfigured):
                env_required('SECRET_KEY')

    def test_env_bool(self):
        with mock.patch.dict(os.environ, {'FLAG': 'True'}):
            self.assertTrue(env_bool('FLAG'))
        with mock.patch.dict(os.environ, {'FLAG': 'false'}):
            self.assertFalse(env_bool('FLAG'))
        # Missing falls back to the default, which is off (the safe choice for DEBUG).
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(env_bool('FLAG'))

    def test_env_list_trims_spaces_and_blanks(self):
        with mock.patch.dict(os.environ, {'HOSTS': ' localhost, 127.0.0.1 ,,'}):
            self.assertEqual(env_list('HOSTS'), ['localhost', '127.0.0.1'])


class ProductionSettingsTests(SimpleTestCase):
    """
    With DEBUG off (as on Railway), the HTTPS protections switch on.

    Settings are computed once when Django starts, so we can't just flip DEBUG
    inside a test. Instead we run settings.py again as a plain Python file with
    a production-like environment and inspect the values it produces.
    """

    SETTINGS_FILE = Path(__file__).resolve().parent.parent / 'config' / 'settings.py'

    def load_settings(self, **env):
        """Evaluate settings.py with the given environment variables."""
        base_env = {
            'SECRET_KEY': 'test-only-key',
            'DATABASE_URL': 'postgresql://user:pw@db.internal:5432/app',
            'ALLOWED_HOSTS': 'example.up.railway.app',
            'CSRF_TRUSTED_ORIGINS': 'https://example.up.railway.app',
        }
        with mock.patch.dict(os.environ, {**base_env, **env}, clear=True):
            return runpy.run_path(str(self.SETTINGS_FILE))

    def test_production_forces_https(self):
        settings = self.load_settings(DEBUG='false')
        self.assertFalse(settings['DEBUG'])
        self.assertTrue(settings['SECURE_SSL_REDIRECT'])
        self.assertTrue(settings['SESSION_COOKIE_SECURE'])
        self.assertTrue(settings['CSRF_COOKIE_SECURE'])
        self.assertGreater(settings['SECURE_HSTS_SECONDS'], 0)
        self.assertEqual(settings['CSRF_TRUSTED_ORIGINS'], ['https://example.up.railway.app'])

    def test_missing_debug_means_production(self):
        # Forgetting to set DEBUG on Railway must still give the secure setup.
        settings = self.load_settings()
        self.assertFalse(settings['DEBUG'])
        self.assertTrue(settings['SECURE_SSL_REDIRECT'])

    def test_local_debug_keeps_plain_http(self):
        # Locally we browse http://127.0.0.1, so no redirect or HSTS there.
        settings = self.load_settings(DEBUG='true')
        self.assertFalse(settings['SECURE_SSL_REDIRECT'])
        self.assertEqual(settings['SECURE_HSTS_SECONDS'], 0)


class MemberModelTests(TestCase):
    """The roster's data rules (AD-2), enforced by the model and the database."""

    def test_new_members_start_active(self):
        member = Member.objects.create(first_name='Bob', last_name='Smith')
        self.assertTrue(member.is_active)

    def test_str_is_full_name(self):
        self.assertEqual(str(Member(first_name='Bob', last_name='Smith')), 'Bob Smith')

    def test_both_names_required(self):
        with self.assertRaises(ValidationError) as caught:
            Member(first_name='', last_name='').full_clean()
        self.assertIn('first_name', caught.exception.message_dict)
        self.assertIn('last_name', caught.exception.message_dict)

    def test_database_rejects_same_name_with_different_capitalization(self):
        Member.objects.create(first_name='Bob', last_name='Smith')
        # atomic() keeps the failed insert from breaking the rest of the test's transaction.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Member.objects.create(first_name='bob', last_name='SMITH')

    def test_validation_gives_friendly_message_for_duplicates(self):
        Member.objects.create(first_name='Bob', last_name='Smith')
        with self.assertRaises(ValidationError) as caught:
            Member(first_name='BOB', last_name='smith').full_clean()
        self.assertIn('already on the roster', str(caught.exception))

    def test_same_first_name_different_last_name_is_allowed(self):
        Member.objects.create(first_name='Bob', last_name='Smith')
        Member.objects.create(first_name='Bob', last_name='Jones')
        self.assertEqual(Member.objects.count(), 2)

    def test_sorted_by_first_name_then_last_ignoring_case(self):
        for first, last in [('jane', 'Doe'), ('Bob', 'Smith'), ('Bob', 'Jones'), ('Amy', 'Zed')]:
            Member.objects.create(first_name=first, last_name=last)
        self.assertEqual(
            [str(m) for m in Member.objects.all()],
            ['Amy Zed', 'Bob Jones', 'Bob Smith', 'jane Doe'],
        )


class RosterAdminTests(TestCase):
    """Skye's roster screens in Django admin (AD-1, AD-2)."""

    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser('skye', password='test-pass-123')
        self.client.force_login(self.admin_user)
        self.member = Member.objects.create(first_name='Bob', last_name='Smith')

    def test_admin_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('admin:heritage_media_availability_member_changelist'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response['Location'])

    def test_roster_list_shows_members(self):
        response = self.client.get(reverse('admin:heritage_media_availability_member_changelist'))
        self.assertContains(response, 'Bob')
        # #39: the site name comes from UNFOLD in settings; the tab title ends with it.
        self.assertContains(response, 'Heritage Media')
        self.assertContains(response, '| Heritage Media Availability</title>')

    def test_add_form_rejects_duplicate_with_friendly_message(self):
        response = self.client.post(
            reverse('admin:heritage_media_availability_member_add'),
            {'first_name': 'bob', 'last_name': 'smith', 'is_active': 'on'},
        )
        # 200 means the form came back with an error instead of saving (a save redirects).
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already on the roster')
        self.assertEqual(Member.objects.count(), 1)

    def test_can_mark_member_inactive(self):
        response = self.client.post(
            reverse('admin:heritage_media_availability_member_change', args=[self.member.pk]),
            {'first_name': 'Bob', 'last_name': 'Smith'},  # unticked checkbox = not sent = inactive
        )
        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)

    def test_delete_is_blocked(self):
        # AD-2: no hard delete, even for the superuser.
        # Django logs every 403 as a warning; assertLogs captures it so the
        # expected traceback doesn't clutter the test output.
        with self.assertLogs('django.request', level='WARNING'):
            response = self.client.post(
                reverse('admin:heritage_media_availability_member_delete', args=[self.member.pk]),
                {'post': 'yes'},
            )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Member.objects.filter(pk=self.member.pk).exists())

    def test_bulk_delete_action_is_not_offered(self):
        response = self.client.get(reverse('admin:heritage_media_availability_member_changelist'))
        self.assertNotContains(response, 'delete_selected')


class RosterOneClickTests(TestCase):
    """#42: the roster's badges, one-click Deactivate / Activate, name links and filter tabs."""

    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))
        self.grace = Member.objects.create(first_name='Grace', last_name='Kim')
        self.tom = Member.objects.create(first_name='Tom', last_name='Lee', is_active=False)
        self.list_url = reverse('admin:heritage_media_availability_member_changelist')

    def toggle_url(self, member):
        return reverse('admin:heritage_media_availability_member_toggle_active', args=[member.pk])

    def row(self, html, member):
        """One member's table row, found by their edit link."""
        edit_url = reverse('admin:heritage_media_availability_member_change', args=[member.pk])
        return re.search(rf'(?s)<tr[^>]*>(?:(?!</tr>).)*href="{edit_url}".*?</tr>', html).group(0)

    def test_rows_show_badge_link_and_matching_button(self):
        html = self.client.get(self.list_url).content.decode()
        grace, tom = self.row(html, self.grace), self.row(html, self.tom)
        # The name is a visible link (arrow) to the edit page.
        self.assertIn('class="row-link"', grace)
        self.assertIn('Grace Kim', grace)
        # Active member: green badge, outline "Deactivate" button with an X.
        self.assertIn('Active', grace)
        self.assertIn('close</span>', grace)
        self.assertIn('Deactivate', grace)
        self.assertIn(f'formaction="{self.toggle_url(self.grace)}"', grace)
        # Inactive member: gray badge, quiet indigo "Activate" button with a check.
        self.assertIn('Inactive', tom)
        self.assertNotIn('Deactivate', tom)
        self.assertIn('check</span>', tom)
        self.assertIn('Activate', tom)
        self.assertIn('quiet-action', tom)
        # Screen readers hear who each button is for.
        self.assertIn('<span class="sr-only"> Grace Kim</span>', grace)

    def test_no_editable_checkboxes_or_save_bar(self):
        # #42: list_editable is gone, so nothing waits for a Save button.
        response = self.client.get(self.list_url)
        self.assertNotContains(response, 'name="form-0-is_active"')
        self.assertNotContains(response, 'name="_save"')

    def test_buttons_sit_inside_the_list_form_without_nesting_forms(self):
        # The table is inside Django's changelist form; a nested <form> would
        # be dropped by the browser, so the buttons borrow it (formaction).
        html = self.client.get(self.list_url).content.decode()
        start = html.index('id="changelist-form"')
        inner = html[start:html.index('</form>', start)]
        self.assertIn('formaction=', inner)
        self.assertNotIn('<form', inner)

    def test_deactivate_applies_at_once_with_message(self):
        response = self.client.post(self.toggle_url(self.grace), follow=True)
        self.assertRedirects(response, self.list_url)
        self.assertContains(response, 'Grace Kim is now inactive.')
        self.grace.refresh_from_db()
        self.assertFalse(self.grace.is_active)

    def test_activate_applies_at_once_with_message(self):
        response = self.client.post(self.toggle_url(self.tom), follow=True)
        self.assertContains(response, 'Tom Lee is now active.')
        self.tom.refresh_from_db()
        self.assertTrue(self.tom.is_active)

    def test_returns_to_the_same_filtered_list(self):
        # The browser says which page the button was on (Referer); off-site ones are ignored.
        filtered = f'{self.list_url}?status=active&q=gr'
        response = self.client.post(self.toggle_url(self.grace), headers={'referer': f'http://testserver{filtered}'})
        self.assertRedirects(response, f'http://testserver{filtered}', fetch_redirect_response=False)
        response = self.client.post(self.toggle_url(self.grace), headers={'referer': 'https://example.com/'})
        self.assertRedirects(response, self.list_url, fetch_redirect_response=False)

    def test_toggle_is_recorded_in_history(self):
        # #16: shows on the member's History page.
        self.client.post(self.toggle_url(self.grace))
        self.client.post(self.toggle_url(self.grace))
        entries = [
            (entry.get_action_flag_display(), entry.get_change_message())
            for entry in LogEntry.objects.filter(object_id=str(self.grace.pk)).order_by('pk')
        ]
        self.assertEqual(entries, [('Change', 'Marked inactive.'), ('Change', 'Marked active.')])
        history = reverse('admin:heritage_media_availability_member_history', args=[self.grace.pk])
        self.assertContains(self.client.get(history), 'Marked inactive.')

    def test_toggle_needs_a_post_and_a_real_member(self):
        with self.assertLogs('django.request', level='WARNING'):
            self.assertEqual(self.client.get(self.toggle_url(self.grace)).status_code, 405)
            missing = reverse('admin:heritage_media_availability_member_toggle_active', args=[9999])
            self.assertEqual(self.client.post(missing).status_code, 404)
        self.grace.refresh_from_db()
        self.assertTrue(self.grace.is_active)

    def test_toggle_needs_the_admin_login(self):
        self.client.logout()
        response = self.client.post(self.toggle_url(self.grace))
        self.assertIn(reverse('admin:login'), response['Location'])
        self.grace.refresh_from_db()
        self.assertTrue(self.grace.is_active)

    def test_status_filter_tabs_beside_search(self):
        # All / Active (n) / Inactive (n) as one-click tabs, outside the Filters panel.
        response = self.client.get(self.list_url, {'q': 'k'})
        # (Anchored on the label: Unfold's class names contain ">" themselves.)
        nav = re.search(r'(?s)aria-label="Filter by status">.*?</nav>', response.content.decode()).group(0)
        tabs = re.findall(r'<a href="(\?[^"]*)"( class="active")?[^>]*>([^<]*)</a>', nav)
        self.assertEqual(
            [(text, bool(active)) for _, active, text in tabs],
            [('All', True), ('Active (1)', False), ('Inactive (1)', False)],
        )
        # Each tab keeps the search ("q") while changing the status.
        self.assertIn('status=inactive', tabs[2][0])
        self.assertIn('q=k', tabs[2][0])
        self.assertNotContains(response, 'name="status"')  # no radio buttons
        for status, shown, hidden in [('active', 'Grace Kim', 'Tom Lee'), ('inactive', 'Tom Lee', 'Grace Kim')]:
            with self.subTest(status=status):
                response = self.client.get(self.list_url, {'status': status})
                self.assertContains(response, shown)
                self.assertNotContains(response, hidden)


class SessionLengthTests(SimpleTestCase):
    """AD-1: the admin login lasts about 30 days."""

    def test_session_lasts_30_days(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 60 * 60 * 24 * 30)


class MonthHelperTests(SimpleTestCase):
    """The "YYYY-MM" helpers in months.py."""

    def test_valid_months_pass(self):
        for month in ['2026-01', '2026-11', '2027-12']:
            validate_month(month)  # raises if invalid

    def test_invalid_months_are_rejected(self):
        for month in ['2026-13', '2026-00', '2026-1', '26-11', '2026/11', '2026-11-01', '', None]:
            with self.subTest(month=month), self.assertRaises(ValidationError):
                validate_month(month)

    def test_month_label(self):
        self.assertEqual(month_label('2026-11'), 'November 2026')

    def test_days_in_month_handles_leap_years(self):
        self.assertEqual(days_in_month('2026-11'), 30)
        self.assertEqual(days_in_month('2027-02'), 28)
        self.assertEqual(days_in_month('2028-02'), 29)


class SubmissionModelTests(TestCase):
    """Submission data rules: validation messages and database constraints."""

    def setUp(self):
        self.bob = Member.objects.create(first_name='Bob', last_name='Smith')

    def submission(self, **fields):
        """An unsaved submission for Bob in November 2026, with any fields overridden."""
        values = {'member': self.bob, 'month': '2026-11', 'kind': Submission.Kind.DAYS, 'days': [3]}
        return Submission(**{**values, **fields})

    def assertDaysError(self, submission, text):
        """full_clean() fails with an error on the days field containing text."""
        with self.assertRaises(ValidationError) as caught:
            submission.full_clean()
        self.assertIn(text, ' '.join(caught.exception.message_dict['days']))

    def test_valid_submissions_pass(self):
        self.submission().full_clean()
        self.submission(kind=Submission.Kind.AVAILABLE_ALL, days=[]).full_clean()
        self.submission(kind=Submission.Kind.UNAVAILABLE_ALL, days=[], notes='x' * 500).full_clean()

    def test_days_are_sorted_and_deduplicated(self):
        submission = self.submission(days=[20, 3, 5, 3])
        submission.full_clean()
        self.assertEqual(submission.days, [3, 5, 20])

    def test_days_kind_needs_at_least_one_day(self):
        self.assertDaysError(self.submission(days=[]), 'Pick at least one day')

    def test_all_month_kinds_cannot_have_days(self):
        self.assertDaysError(self.submission(kind=Submission.Kind.AVAILABLE_ALL, days=[3]), 'Days can only be picked')

    def test_day_must_exist_in_that_month(self):
        self.assertDaysError(self.submission(month='2027-02', days=[28, 29, 30]), 'February 2027 has no day 29, 30.')
        self.submission(month='2028-02', days=[29]).full_clean()  # leap year: fine

    def test_bad_month_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            self.submission(month='2026-13').full_clean()
        self.assertIn('month', caught.exception.message_dict)

    def test_notes_over_500_characters_are_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            self.submission(notes='x' * 501).full_clean()
        self.assertIn('notes', caught.exception.message_dict)

    def test_database_rejects_bad_rows_that_skip_validation(self):
        # save() without full_clean() skips the Python checks; Postgres must still refuse.
        bad_rows = [
            {'month': '2026-13'},
            {'days': []},
            {'kind': Submission.Kind.AVAILABLE_ALL, 'days': [3]},
            {'kind': 'maybe', 'days': []},
            {'days': [0]},
            {'days': [32]},
        ]
        for fields in bad_rows:
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                self.submission(**fields).save()

    def test_current_returns_newest_per_member_and_month(self):
        now = timezone.now()
        jane = Member.objects.create(first_name='Jane', last_name='Doe')
        self.submission(days=[1], submitted_at=now - timedelta(days=2)).save()
        newest_bob_nov = self.submission(days=[2], submitted_at=now - timedelta(days=1))
        newest_bob_nov.save()
        bob_dec = self.submission(month='2026-12', days=[5], submitted_at=now - timedelta(days=3))
        bob_dec.save()
        jane_nov = self.submission(member=jane, kind=Submission.Kind.AVAILABLE_ALL, days=[], submitted_at=now)
        jane_nov.save()

        current = set(Submission.objects.current())
        self.assertEqual(current, {newest_bob_nov, bob_dec, jane_nov})
        # Every version is still stored as history.
        self.assertEqual(Submission.objects.count(), 4)

    def test_member_with_submissions_cannot_be_deleted(self):
        self.submission().save()
        with self.assertRaises(ProtectedError):
            self.bob.delete()


class ClosedMonthModelTests(TestCase):
    """ClosedMonth rows: one per closed month, valid months only."""

    def test_str_is_month_label(self):
        self.assertEqual(str(ClosedMonth(month='2026-11')), 'November 2026')

    def test_closing_twice_gives_friendly_message(self):
        ClosedMonth.objects.create(month='2026-11')
        with self.assertRaises(ValidationError) as caught:
            ClosedMonth(month='2026-11').full_clean()
        self.assertIn('That month is already closed.', caught.exception.message_dict['month'])

    def test_database_rejects_bad_month(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ClosedMonth.objects.create(month='2026-13')


class MonthsPageTests(TestCase):
    """AD-8 (#43): the Months page, and closing and reopening months (one click each)."""

    def setUp(self):
        # The months listed follow today's date, so pin it (Oct 10, 2026, Eastern).
        self.enterContext(at_utc(2026, 10, 10, 16, 0))
        admin_user = get_user_model().objects.create_superuser('skye', password='test-pass-123')
        self.client.force_login(admin_user)
        self.list_url = reverse('admin:heritage_media_availability_closedmonth_changelist')

    def close_url(self, month):
        return reverse('admin:heritage_media_availability_closedmonth_close', args=[month])

    def reopen_url(self, month):
        return reverse('admin:heritage_media_availability_closedmonth_reopen', args=[month])

    def test_lists_this_month_and_ahead_then_past_months(self):
        response = self.client.get(self.list_url)
        months = re.findall(r'class="row-link" href="[^"]*month=(\d{4}-\d{2})"', response.content.decode())
        # This month through 6 ahead, oldest first; then the 6 before, newest first.
        self.assertEqual(months, [
            '2026-10', '2026-11', '2026-12', '2027-01', '2027-02', '2027-03', '2027-04',
            '2026-09', '2026-08', '2026-07', '2026-06', '2026-05', '2026-04',
        ])
        self.assertContains(response, 'This month and ahead')
        # Past months start collapsed.
        self.assertContains(response, '<details class="months-past">')
        self.assertNotContains(response, '<details class="months-past" open')

    def test_page_is_called_months_everywhere(self):
        # The header's breadcrumb comes from the model's name, so it's
        # renamed too (#43); "Closed months" is gone from the admin.
        response = self.client.get(self.list_url)
        self.assertIn('Heritage Media chevron_right Months', visible_text(response))
        self.assertNotIn('Closed months', visible_text(response))

    def test_rows_show_status_count_and_the_right_button(self):
        ClosedMonth.objects.create(month='2026-11')
        bob = Member.objects.create(first_name='Bob', last_name='Smith')
        Member.objects.create(first_name='Jane', last_name='Doe')
        Submission.objects.create(member=bob, month='2026-12', kind='available_all')
        response = self.client.get(self.list_url)
        html = response.content.decode()
        # "1 of 2" without "responded" (the column is headed Responses).
        self.assertIn('December 2026 arrow_forward Open 1 of 2 lock Close', visible_text(response))
        # November is closed: a quiet indigo Reopen button (circular arrow), no Close.
        self.assertIn(f'action="{self.reopen_url("2026-11")}"', html)
        self.assertNotIn(f'action="{self.close_url("2026-11")}"', html)
        self.assertIn('November 2026 arrow_forward Closed 0 of 2 replay Reopen', visible_text(response))
        self.assertIn('quiet-action', html)
        # December is open: a Close button that comes back here.
        self.assertIn(f'action="{self.close_url("2026-12")}"', html)
        self.assertIn(f'name="next" value="{self.list_url}"', html)
        self.assertIn('Closed', visible_text(response))
        self.assertIn('Open', visible_text(response))
        # Each month links to its dashboard.
        self.assertIn(f'href="{reverse("admin:index")}?month=2026-12"', html)

    def test_close_needs_a_post(self):
        # No confirmation page any more (decision 2026-10-10); a link,
        # or a browser prefetching one, must never close a month.
        with self.assertLogs('django.request', level='WARNING'):
            response = self.client.get(self.close_url('2026-11'))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(ClosedMonth.objects.exists())

    def test_close_happens_at_once(self):
        response = self.client.post(self.close_url('2026-11'), follow=True)
        self.assertRedirects(response, self.list_url)
        self.assertContains(response, 'Closed November 2026.')
        self.assertTrue(ClosedMonth.objects.filter(month='2026-11').exists())

    def test_past_months_can_be_closed(self):
        # AD-8: past months too, up to 6 months back.
        self.client.post(self.close_url('2026-04'))
        self.assertTrue(ClosedMonth.objects.filter(month='2026-04').exists())

    def test_reopen_happens_at_once(self):
        ClosedMonth.objects.create(month='2026-11')
        response = self.client.post(self.reopen_url('2026-11'), follow=True)
        self.assertRedirects(response, self.list_url)
        self.assertContains(response, 'Reopened November 2026.')
        self.assertFalse(ClosedMonth.objects.exists())

    def test_reopen_needs_a_post(self):
        # A link (or a browser prefetching one) must never reopen a month.
        ClosedMonth.objects.create(month='2026-11')
        with self.assertLogs('django.request', level='WARNING'):
            response = self.client.get(self.reopen_url('2026-11'))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(ClosedMonth.objects.exists())

    def test_months_outside_the_window_are_refused(self):
        # The server checks the month in the address, not just the buttons on screen.
        for month in ['2026-03', '2027-05', 'junk']:
            with self.subTest(month=month), self.assertLogs('django.request', level='WARNING'):
                self.assertEqual(self.client.post(self.close_url(month)).status_code, 404)
                self.assertEqual(self.client.post(self.reopen_url(month)).status_code, 404)
        self.assertFalse(ClosedMonth.objects.exists())

    def test_closing_twice_or_reopening_an_open_month_is_friendly(self):
        # E.g. the same month handled in another tab meanwhile.
        ClosedMonth.objects.create(month='2026-11')
        response = self.client.post(self.close_url('2026-11'), follow=True)
        self.assertContains(response, 'November 2026 was already closed.')
        self.assertEqual(ClosedMonth.objects.count(), 1)
        response = self.client.post(self.reopen_url('2026-12'), follow=True)
        self.assertContains(response, 'December 2026 was already open.')

    def test_returns_to_next_but_never_off_site(self):
        dashboard = f"{reverse('admin:index')}?month=2026-11"
        response = self.client.post(self.close_url('2026-11'), {'next': dashboard})
        self.assertRedirects(response, dashboard, fetch_redirect_response=False)
        response = self.client.post(self.reopen_url('2026-11'), {'next': 'https://example.com/'})
        self.assertRedirects(response, self.list_url, fetch_redirect_response=False)

    def test_old_add_form_and_edit_and_delete_are_gone(self):
        ClosedMonth.objects.create(month='2026-11')
        add_url = reverse('admin:heritage_media_availability_closedmonth_add')
        change_url = reverse('admin:heritage_media_availability_closedmonth_change', args=['2026-11'])
        delete_url = reverse('admin:heritage_media_availability_closedmonth_delete', args=['2026-11'])
        with self.assertLogs('django.request', level='WARNING'):
            self.assertEqual(self.client.post(add_url, {'month': '2026-12'}).status_code, 403)
            self.client.post(change_url, {'month': '2026-12'})
            self.client.post(delete_url, {'post': 'yes'})
        self.assertEqual(list(ClosedMonth.objects.values_list('month', flat=True)), ['2026-11'])
        # No bulk actions (the old "Reopen selected months") on the page.
        response = self.client.get(self.list_url)
        self.assertNotContains(response, 'reopen_months')
        self.assertNotContains(response, '_selected_action')

    def test_closed_month_shows_closed_on_the_team_form(self):
        # Under the hood a ClosedMonth row still means closed, so the team form
        # labels it (TF-3) and rejects it (TF-4, covered by SubmitTests).
        self.client.post(self.close_url('2026-11'))
        response = Client().get(reverse('heritage_media_availability:team_form'))
        self.assertContains(response, 'November 2026 (closed)')


class DashboardCloseTests(TestCase):
    """AD-8 (#43): the dashboard's Open/Closed badge and Close month / Reopen month button."""

    def setUp(self):
        self.enterContext(at_utc(2026, 10, 10, 16, 0))
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))

    def status(self, month):
        """The month row's status area (badge and button) on the dashboard for `month`."""
        response = self.client.get(reverse('admin:index'), {'month': month})
        return re.search(r'(?s)id="month-status">(.*?)</div>', response.content.decode()).group(1)

    def test_open_month_has_close_button_coming_back_here(self):
        status = self.status('2026-11')
        self.assertIn('Open', status)
        self.assertIn('Close month', status)
        close_url = reverse('admin:heritage_media_availability_closedmonth_close', args=['2026-11'])
        self.assertIn(f'action="{close_url}"', status)
        self.assertIn('name="next" value="/admin/?month=2026-11"', status)
        # The badge is sized to match the button beside it.
        self.assertIn('badge-large', status)

    def test_closed_month_has_reopen_button(self):
        ClosedMonth.objects.create(month='2026-11')
        status = self.status('2026-11')
        self.assertIn('Closed', status)
        self.assertIn('Reopen month', status)
        self.assertIn('name="next" value="/admin/?month=2026-11"', status)

    def test_months_older_than_6_back_get_the_badge_only(self):
        ClosedMonth.objects.create(month='2026-03')
        status = self.status('2026-03')
        self.assertIn('Closed', status)
        self.assertNotIn('Reopen', status)

    def test_closing_from_the_dashboard_comes_back_with_a_message(self):
        dashboard = f"{reverse('admin:index')}?month=2026-11"
        close_url = reverse('admin:heritage_media_availability_closedmonth_close', args=['2026-11'])
        response = self.client.post(close_url, {'next': dashboard}, follow=True)
        self.assertContains(response, 'Closed November 2026.')
        self.assertContains(response, 'Availability for November 2026')
        self.assertIn('Reopen month', self.status('2026-11'))


class ClosedMonthHistoryTests(TestCase):
    """#16: closing and reopening months are recorded in admin History."""

    def setUp(self):
        self.enterContext(at_utc(2026, 10, 10, 16, 0))
        self.admin_user = get_user_model().objects.create_superuser('skye', password='test-pass-123')
        self.client.force_login(self.admin_user)

    def close(self, month):
        """Close a month with its Close button."""
        self.client.post(reverse('admin:heritage_media_availability_closedmonth_close', args=[month]))

    def reopen(self, month):
        """Reopen a month with its Reopen button."""
        self.client.post(reverse('admin:heritage_media_availability_closedmonth_reopen', args=[month]))

    def entries(self, month):
        """(action, description, user) for each History entry for a month, oldest first."""
        return [
            (entry.get_action_flag_display(), entry.get_change_message(), entry.user.username)
            for entry in LogEntry.objects.filter(object_id=month).order_by('action_time', 'pk')
        ]

    CLOSED = ('Addition', 'Closed the month.', 'skye')
    REOPENED = ('Deletion', 'Reopened the month.', 'skye')

    def test_closing_is_recorded(self):
        self.close('2026-11')
        self.assertEqual(self.entries('2026-11'), [self.CLOSED])

    def test_reopening_is_recorded(self):
        self.close('2026-11')
        self.reopen('2026-11')
        self.assertEqual(self.entries('2026-11'), [self.CLOSED, self.REOPENED])
        self.assertEqual(LogEntry.objects.get(object_id='2026-11', action_flag=DELETION).object_repr, 'November 2026')

    def test_doing_nothing_records_nothing(self):
        # Closing a closed month or reopening an open one adds no History entry.
        self.close('2026-11')
        self.close('2026-11')
        self.reopen('2026-12')
        self.assertEqual(self.entries('2026-11'), [self.CLOSED])
        self.assertEqual(self.entries('2026-12'), [])

    def test_reclosed_month_history_shows_the_whole_timeline(self):
        self.close('2026-11')
        self.reopen('2026-11')
        self.close('2026-11')
        self.assertEqual(self.entries('2026-11'), [self.CLOSED, self.REOPENED, self.CLOSED])
        history_url = reverse('admin:heritage_media_availability_closedmonth_history', args=['2026-11'])
        response = self.client.get(history_url)
        self.assertContains(response, 'Closed the month.', count=2)
        self.assertContains(response, 'Reopened the month.', count=1)


class SubmissionAdminTests(TestCase):
    """The read-only submission history in Django admin."""

    def setUp(self):
        admin_user = get_user_model().objects.create_superuser('skye', password='test-pass-123')
        self.client.force_login(admin_user)
        bob = Member.objects.create(first_name='Bob', last_name='Smith')
        self.submission = Submission.objects.create(member=bob, month='2026-11', kind='days', days=[3, 20])

    def test_history_list_shows_submissions(self):
        response = self.client.get(reverse('admin:heritage_media_availability_submission_changelist'))
        self.assertContains(response, 'Bob Smith')
        self.assertContains(response, 'November 2026')
        self.assertContains(response, '3, 20')

    def test_month_filter_beside_search(self):
        # #42: a month dropdown, newest first, that narrows the list.
        bob = Member.objects.get(first_name='Bob')
        Submission.objects.create(member=bob, month='2026-12', kind='available_all')
        url = reverse('admin:heritage_media_availability_submission_changelist')
        html = self.client.get(url).content.decode()
        select = re.search(r'(?s)<select[^>]*name="month".*?</select>', html).group(0)
        self.assertEqual(
            re.findall(r'<option value="(\d{4}-\d{2})"[^>]*>\s*([^<]*?)\s*</option>', select),
            [('2026-12', 'December 2026'), ('2026-11', 'November 2026')],
        )
        response = self.client.get(url, {'month': '2026-12'})
        self.assertContains(response, 'December 2026')
        self.assertNotContains(response, '3, 20')

    def test_history_cannot_be_added_edited_or_deleted(self):
        pk = self.submission.pk
        with self.assertLogs('django.request', level='WARNING'):
            add = self.client.get(reverse('admin:heritage_media_availability_submission_add'))
            delete = self.client.post(
                reverse('admin:heritage_media_availability_submission_delete', args=[pk]), {'post': 'yes'}
            )
        self.assertEqual(add.status_code, 403)
        self.assertEqual(delete.status_code, 403)
        # The detail page is view-only: no editable inputs for the submission's fields.
        detail = self.client.get(reverse('admin:heritage_media_availability_submission_change', args=[pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, 'name="notes"')
        self.assertTrue(Submission.objects.filter(pk=pk).exists())


class DisplayNameTests(SimpleTestCase):
    """SPEC.md "Names in admin views and copy output": short display names."""

    def names(self, *full_names):
        """Display names for unsaved members built from "First Last" strings, in the same order."""
        members = [
            Member(pk=number, first_name=name.split()[0], last_name=name.split()[1])
            for number, name in enumerate(full_names, start=1)
        ]
        result = display_names(members)
        return [result[member.pk] for member in members]

    def test_unique_first_name_alone(self):
        self.assertEqual(self.names('Bob Smith', 'Emily Jones'), ['Bob', 'Emily'])

    def test_shared_first_name_adds_last_initial(self):
        self.assertEqual(self.names('Bob Jones', 'Bob Smith', 'Emily Jones'), ['Bob J.', 'Bob S.', 'Emily'])

    def test_shared_first_name_ignores_capitalization(self):
        self.assertEqual(self.names('Bob Jones', 'bob smith'), ['Bob J.', 'bob S.'])

    def test_shared_first_name_and_initial_uses_full_last_name(self):
        # Only the colliding pair falls back to the full last name; Bob Smith keeps "Bob S.".
        self.assertEqual(
            self.names('Bob Jones', 'Bob Johnson', 'Bob Smith'),
            ['Bob Jones', 'Bob Johnson', 'Bob S.'],
        )


class DashboardAccessTests(TestCase):
    """The dashboard is behind the admin login (AD-1) and linked from the admin home."""

    def test_logged_out_visitor_goes_to_login(self):
        response = self.client.get(reverse('admin:index'))
        self.assertRedirects(
            response, f"{reverse('admin:login')}?next={reverse('admin:index')}", fetch_redirect_response=False
        )

    def test_logged_in_admin_sees_dashboard_on_the_home_page(self):
        # #40: logging in lands on the dashboard.
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Availability for')
        self.assertContains(response, 'id="tracker"')
        self.assertContains(response, 'id="by-person"')
        self.assertContains(response, 'id="by-date"')

    def test_empty_roster_draws_no_empty_card_slots(self):
        # Regression (#40): an empty {% capture %} still holds blank space, which
        # Unfold's card drew as an empty footer bar. With nobody on the roster,
        # there's no count, no Copy button, and no copy-text footer at all.
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'No one on the roster was on the team for this month.', count=3)
        self.assertNotContains(response, 'class="copy-area"')
        self.assertNotContains(response, 'data-copy-target="')  # the attribute, not the script's mentions
        self.assertNotContains(response, 'class="dashboard-count"')
        # Unfold's card footer bar (its border-top wrapper) isn't drawn.
        self.assertNotContains(response, 'border-t border-base-200 flex items-center')

    def test_month_picker_is_the_styled_dropdown(self):
        # The dashboard isn't an admin form page, so it must add Select2's
        # script itself, or the dropdown would quietly stay the native one.
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))
        response = self.client.get(reverse('admin:index'))
        select = re.search(r'<select name="month"[^>]*>', response.content.decode()).group(0)
        self.assertIn('id="month-select"', select)
        self.assertIn('unfold-admin-autocomplete', select)
        self.assertIn('data-minimum-results-for-search="Infinity"', select)
        for asset in ['select2.full', 'unfold/js/select2.init.js', 'admin/css/vendor/select2/select2']:
            with self.subTest(asset=asset):
                self.assertContains(response, asset)

    def test_old_dashboard_link_redirects_home_keeping_the_month(self):
        # #40: bookmarks of /admin/availability/ still work.
        response = self.client.get('/admin/availability/', {'month': '2026-12'})
        self.assertRedirects(response, f"{reverse('admin:index')}?month=2026-12", fetch_redirect_response=False)

    def test_dashboard_is_built_from_unfold_not_tailwind(self):
        # #40: the admin home uses Unfold's styles plus admin.css, never the team form's app.css.
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))
        response = self.client.get(reverse('admin:index'))
        self.assertNotContains(response, 'heritage_media_availability/app.css')
        self.assertContains(response, 'heritage_media_availability/admin.css')

    def test_sidebar_links_to_every_screen(self):
        # #39: Unfold's sidebar (UNFOLD["SIDEBAR"] in settings) on every admin page.
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))
        response = self.client.get(reverse('admin:heritage_media_availability_member_changelist'))
        for name in [
            'admin:index',
            'admin:heritage_media_availability_member_changelist',
            'admin:heritage_media_availability_closedmonth_changelist',
            'admin:heritage_media_availability_submission_changelist',
        ]:
            with self.subTest(name=name):
                self.assertContains(response, f'href="{reverse(name)}"')


class DashboardMonthTests(TestCase):
    """AD-3: the dashboard's month selector and the month it opens on."""

    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))
        bob = Member.objects.create(first_name='Bob', last_name='Smith')
        # August has a submission, July was closed, June has neither.
        Submission.objects.create(member=bob, month='2026-08', kind='available_all')
        ClosedMonth.objects.create(month='2026-07')
        ClosedMonth.objects.create(month='2026-11')

    def test_opens_on_next_month(self):
        with at_utc(2026, 10, 5, 16, 0):
            self.assertEqual(default_month(), '2026-11')
            response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Availability for November 2026')

    def test_options_list_past_months_with_data_then_upcoming(self):
        with at_utc(2026, 10, 5, 16, 0):
            past, upcoming = month_options()
        self.assertEqual(past, [('2026-07', 'July 2026 (closed)'), ('2026-08', 'August 2026')])
        self.assertEqual([month for month, _ in upcoming], upcoming_months_from('2026-10'))
        self.assertIn(('2026-11', 'November 2026 (closed)'), upcoming)

    def test_past_month_can_be_chosen(self):
        with at_utc(2026, 10, 5, 16, 0):
            response = self.client.get(reverse('admin:index'), {'month': '2026-08'})
        self.assertContains(response, 'Availability for August 2026')
        self.assertContains(response, '<option value="2026-08" selected>', html=False)

    def test_unlisted_or_bad_month_falls_back_to_next_month(self):
        with at_utc(2026, 10, 5, 16, 0):
            for value in ['2026-06', '2030-01', 'junk', '']:
                with self.subTest(month=value):
                    response = self.client.get(reverse('admin:index'), {'month': value})
                    self.assertContains(response, 'Availability for November 2026')


def upcoming_months_from(first):
    """The 7 months starting at `first` ("YYYY-MM"), to compare with the dashboard's options."""
    return [shift_month(first, offset) for offset in range(7)]


class TrackerTests(TestCase):
    """AD-4 and decision 2026-10-03: who's listed for a month, and their status."""

    def setUp(self):
        # Everyone joined the roster well before October 2026.
        with at_utc(2026, 9, 1, 12, 0):
            self.bob = Member.objects.create(first_name='Bob', last_name='Smith')
            self.amy = Member.objects.create(first_name='Amy', last_name='Lee')
            self.cara = Member.objects.create(first_name='Cara', last_name='Diaz')

    def submit(self, member, month='2026-10', when=(2026, 10, 2, 19, 15), **fields):
        """Save a submission at a fixed UTC time (default: Oct 2, 3:15 pm Eastern)."""
        fields.setdefault('kind', 'available_all')
        return Submission.objects.create(
            member=member, month=month, submitted_at=datetime(*when, tzinfo=UTC), **fields
        )

    def test_lists_active_members_a_to_z_with_status(self):
        self.submit(self.bob)
        responses = month_responses('2026-10')
        self.assertEqual([r.name for r in responses.active], ['Amy', 'Bob', 'Cara'])
        self.assertEqual([r.responded for r in responses.active], [False, True, False])
        self.assertEqual((responses.responded_count, responses.total), (1, 3))

    def test_page_shows_count_status_and_time(self):
        self.submit(self.bob)
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))
        response = self.client.get(reverse('admin:index'), {'month': '2026-10'})
        # The tracker's count, right after its card title. (The by-date note can
        # also say "1 of 3 responded", so a bare search could match that instead.)
        self.assertIn('Responses 1 of 3 responded', visible_text(response))
        self.assertContains(response, 'Not responded', count=2)
        # 19:15 UTC is 3:15 pm in New York.
        self.assertContains(response, 'Oct 2, 3:15 p.m.')
        self.assertNotContains(response, 'id="no-longer-active"')

    def test_any_submission_counts_as_a_response(self):
        self.submit(self.amy, kind='days', days=[3])
        self.submit(self.bob, kind='available_all')
        self.submit(self.cara, kind='unavailable_all')
        self.assertEqual(month_responses('2026-10').responded_count, 3)

    def test_newest_submission_is_the_current_one(self):
        self.submit(self.bob, kind='days', days=[3], when=(2026, 10, 1, 12, 0))
        newest = self.submit(self.bob, kind='days', days=[9], when=(2026, 10, 3, 12, 0))
        bob = month_responses('2026-10').active[1]
        self.assertEqual(bob.submission, newest)

    def test_other_months_submissions_dont_count(self):
        self.submit(self.bob, month='2026-11')
        self.assertEqual(month_responses('2026-10').responded_count, 0)

    def test_inactive_member_who_responded_is_listed_separately(self):
        self.submit(self.cara)
        self.cara.is_active = False
        self.cara.save()
        responses = month_responses('2026-10')
        self.assertEqual([r.name for r in responses.active], ['Amy', 'Bob'])
        self.assertEqual([r.name for r in responses.inactive], ['Cara Diaz'])
        self.assertEqual((responses.responded_count, responses.total), (0, 2))

        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))
        response = self.client.get(reverse('admin:index'), {'month': '2026-10'})
        self.assertContains(response, 'id="no-longer-active"')
        self.assertContains(response, 'Cara Diaz')
        self.assertIn('Responses 0 of 2 responded', visible_text(response))

    def test_inactive_member_who_didnt_respond_is_not_listed(self):
        self.cara.is_active = False
        self.cara.save()
        responses = month_responses('2026-10')
        self.assertNotIn('Cara', [r.name for r in responses.active])
        self.assertEqual(responses.inactive, [])

    def test_member_added_after_month_ended_is_not_listed(self):
        # 5 am UTC on Nov 1 is 1 am Nov 1 in New York: after October ended.
        with at_utc(2026, 11, 1, 5, 0):
            Member.objects.create(first_name='Dan', last_name='Ng')
        self.assertNotIn('Dan', [r.name for r in month_responses('2026-10').active])
        self.assertIn('Dan', [r.name for r in month_responses('2026-11').active])

    def test_member_added_on_last_evening_of_month_is_listed(self):
        # 3 am UTC on Nov 1 is still 11 pm Oct 31 in New York.
        with at_utc(2026, 11, 1, 3, 0):
            Member.objects.create(first_name='Dan', last_name='Ng')
        self.assertIn('Dan', [r.name for r in month_responses('2026-10').active])

    def test_member_added_later_who_submitted_is_listed(self):
        with at_utc(2026, 11, 1, 5, 0):
            dan = Member.objects.create(first_name='Dan', last_name='Ng')
        self.submit(dan, when=(2026, 11, 2, 12, 0))
        responses = month_responses('2026-10')
        self.assertIn('Dan', [r.name for r in responses.active])
        self.assertEqual(responses.responded_count, 1)

    def test_display_names_compare_people_listed_for_the_month(self):
        # A second Bob (lowercase, to check capitalization is ignored) joins in November.
        with at_utc(2026, 11, 1, 5, 0):
            Member.objects.create(first_name='bob', last_name='Jones')
        # October doesn't list him, so Bob Smith is just "Bob" there...
        self.assertEqual([r.name for r in month_responses('2026-10').active], ['Amy', 'Bob', 'Cara'])
        # ...but from November both Bobs need their initials. Sorted by last name too, ignoring case.
        self.assertEqual(
            [r.name for r in month_responses('2026-11').active], ['Amy', 'bob J.', 'Bob S.', 'Cara']
        )


class ShiftMonthTests(SimpleTestCase):
    """shift_month() moves forward and back across year boundaries."""

    def test_forward_and_back(self):
        self.assertEqual(shift_month('2026-10', 1), '2026-11')
        self.assertEqual(shift_month('2026-12', 1), '2027-01')
        self.assertEqual(shift_month('2026-01', -1), '2025-12')
        self.assertEqual(shift_month('2026-10', 0), '2026-10')
        self.assertEqual(shift_month('2026-10', 14), '2027-12')


def seed(*args, answer=None):
    """Run `manage.py seed` and return its output. `answer` is typed at the confirmation prompt."""
    out = StringIO()
    if answer is None:
        call_command('seed', *args, '--no-input', stdout=out)
    else:
        with mock.patch('builtins.input', return_value=answer):
            call_command('seed', *args, stdout=out)
    return out.getvalue()


# The test runner always sets DEBUG off; seed refuses without it.
@override_settings(DEBUG=True)
class SeedCommandTests(TestCase):
    """#26: `manage.py seed` resets local data and loads a scenario, safely."""

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('skye', password='test-pass-123')
        # Some existing data the reset should remove.
        old = Member.objects.create(first_name='Old', last_name='Member')
        Submission.objects.create(member=old, month='2026-11', kind='available_all')
        ClosedMonth.objects.create(month='2026-12')

    def test_refuses_when_debug_is_off(self):
        with override_settings(DEBUG=False):
            with self.assertRaisesMessage(CommandError, 'DEBUG is off'):
                seed('roster')
        self.assertTrue(Member.objects.filter(first_name='Old').exists())

    def test_refuses_on_a_database_that_isnt_local(self):
        with mock.patch.dict(connection.settings_dict, {'HOST': 'postgres.railway.internal'}):
            with self.assertRaisesMessage(CommandError, 'not this computer'):
                seed('roster')
        self.assertTrue(Member.objects.filter(first_name='Old').exists())

    def test_anything_but_yes_cancels(self):
        output = seed('roster', answer='no')
        self.assertIn('Nothing was changed', output)
        self.assertTrue(Member.objects.filter(first_name='Old').exists())

    def test_yes_resets_and_loads(self):
        output = seed('roster', answer='yes')
        self.assertIn('Loaded "roster": 9 members, 0 submissions, 0 closed months', output)
        self.assertFalse(Member.objects.filter(first_name='Old').exists())
        self.assertFalse(ClosedMonth.objects.exists())

    def test_keeps_admin_accounts_and_their_history(self):
        member = Member.objects.get(first_name='Old')
        LogEntry.objects.log_actions(self.admin.pk, [member], 1, change_message='Added.', single_object=True)
        LogEntry.objects.log_actions(self.admin.pk, [self.admin], 2, change_message='Changed.', single_object=True)
        seed('roster')
        self.assertTrue(get_user_model().objects.filter(username='skye').exists())
        # History about our tables is cleared; History about admin accounts is kept.
        self.assertEqual(list(LogEntry.objects.values_list('change_message', flat=True)), ['Changed.'])

    def test_safe_to_run_twice(self):
        seed('dashboard')
        output = seed('dashboard')
        self.assertIn('9 members, 9 submissions, 1 closed month.', output)

    def test_list_shows_every_scenario(self):
        output = seed('--list')
        for name, details in SCENARIOS.items():
            self.assertIn(f'{name}: {details.description}', output)

    def test_unknown_or_missing_scenario_is_explained(self):
        with self.assertRaisesMessage(CommandError, 'No scenario called "nope". Choose one of: roster, dashboard'):
            seed('nope')
        with self.assertRaisesMessage(CommandError, 'Name a scenario to load'):
            seed()


@override_settings(DEBUG=True)
class DashboardScenarioTests(TestCase):
    """#26: the dashboard scenario sets up #20's cases, dated from "today"."""

    def setUp(self):
        # Today is Oct 5, 2026 (noon Eastern): next month is November, last month September.
        with at_utc(2026, 10, 5, 16, 0):
            seed('dashboard')

    def test_next_month(self):
        responses = month_responses('2026-11')
        self.assertEqual(
            [r.name for r in responses.active],
            ['Amy', 'Bob Johnson', 'Bob Jones', 'Bob S.', 'emily', 'Grace', 'Jack'],
        )
        self.assertEqual((responses.responded_count, responses.total), (4, 7))
        self.assertEqual([r.name for r in responses.inactive], ['Henry Park'])
        # emily resubmitted: the newer answer counts.
        emily = next(r for r in responses.active if r.name == 'emily')
        self.assertEqual(emily.submission.days, [12, 13])

    def test_last_month_is_closed_and_hides_jack(self):
        self.assertTrue(ClosedMonth.objects.filter(month='2026-09').exists())
        responses = month_responses('2026-09')
        self.assertNotIn('Jack', [r.name for r in responses.active])
        # 9 people, minus Henry and Ivy (inactive) and Jack (joined after September): "3 of 6".
        self.assertEqual((responses.responded_count, responses.total), (3, 6))

    def test_no_upcoming_month_is_closed(self):
        # Closing and reopening upcoming months is left for manual steps to do.
        self.assertFalse(ClosedMonth.objects.filter(month__gte='2026-10').exists())


class AnswerWordingTests(SimpleTestCase):
    """AD-5 / AD-7: one person's answer, as copied and as shown on screen."""

    def test_ranges_text(self):
        self.assertEqual(ranges_text([20, 3, 4, 5, 6, 7]), '3-7, 20')
        self.assertEqual(ranges_text([13]), '13')
        # days_list (TF-9) still adds the month in front.
        self.assertEqual(days_list('2026-10', [3, 4, 5, 6, 7, 20]), 'Oct 3-7, 20')

    def test_each_kind(self):
        cases = [
            (Submission(kind='days', days=[1, 4, 10, 11]), '1, 4, 10-11', '1, 4, 10-11'),
            (Submission(kind='available_all'), 'NA', 'Available all month'),
            (Submission(kind='unavailable_all'), 'unavailable all month', 'Unavailable all month'),
            (None, 'no response', 'No response'),
        ]
        for submission, copied, shown in cases:
            with self.subTest(copied=copied):
                self.assertEqual(answer_text(submission), copied)
                self.assertEqual(answer_label(submission), shown)


# SPEC.md's by-person copy example, character for character.
SPEC_BY_PERSON_TEXT = """Bob: 3-7, 20
Emily: 13
Jane: 1, 4, 10-11, 27-31
Jim: NA
Sam: unavailable all month
Tom: no response"""


@override_settings(DEBUG=True)
class ByPersonTests(TestCase):
    """#21: the by-person view and its copy text (AD-5, AD-7)."""

    def setUp(self):
        # Today is Oct 5, 2026 for the whole test, so the next 31-day month is
        # December, and December stays in the dashboard's month list whenever
        # the tests run.
        self.enterContext(at_utc(2026, 10, 5, 16, 0))
        seed('spec-example')
        self.month = '2026-12'
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))

    def test_copy_text_matches_spec_example(self):
        self.assertEqual(by_person_text(month_responses(self.month)), SPEC_BY_PERSON_TEXT)

    def test_copy_text_leaves_out_notes_and_inactive_members(self):
        text = by_person_text(month_responses(self.month))
        self.assertNotIn('rehearsal', text)
        self.assertNotIn('Pat', text)

    def test_responders_first_then_non_responders_each_a_to_z(self):
        # A non-responder named Abe sorts first A-Z but goes after every responder.
        abe = Member.objects.create(first_name='Abe', last_name='Hart')
        names = [r.name for r in month_responses(self.month).by_person]
        self.assertEqual(names, ['Bob', 'Emily', 'Jane', 'Jim', 'Sam', 'Abe', 'Tom'])
        # Once Abe responds, he moves up among the responders, A-Z.
        Submission.objects.create(member=abe, month=self.month, kind='available_all')
        names = [r.name for r in month_responses(self.month).by_person]
        self.assertEqual(names, ['Abe', 'Bob', 'Emily', 'Jane', 'Jim', 'Sam', 'Tom'])

    def test_newest_submission_is_the_one_copied(self):
        tom = Member.objects.get(first_name='Tom')
        Submission.objects.create(
            member=tom, month=self.month, kind='days', days=[9], submitted_at=datetime(2026, 10, 1, tzinfo=UTC)
        )
        Submission.objects.create(
            member=tom, month=self.month, kind='available_all', submitted_at=datetime(2026, 10, 3, tzinfo=UTC)
        )
        self.assertIn('Tom: NA', by_person_text(month_responses(self.month)))

    def test_page_shows_answers_notes_and_copy_text(self):
        response = self.client.get(reverse('admin:index'), {'month': self.month})
        self.assertContains(response, 'No response')
        self.assertContains(response, 'Available all month')
        self.assertContains(response, escape("Can't make rehearsal on the 19th."))
        # The copy text block holds exactly the copy text, with nothing around it.
        self.assertContains(response, f'id="by-person-text" aria-labelledby="by-person-text-label">{SPEC_BY_PERSON_TEXT}</pre>')

    def test_notes_are_escaped(self):
        bob = Member.objects.get(first_name='Bob')
        Submission.objects.create(member=bob, month=self.month, kind='available_all', notes='<b>busy</b>')
        response = self.client.get(reverse('admin:index'), {'month': self.month})
        self.assertContains(response, '&lt;b&gt;busy&lt;/b&gt;')
        self.assertNotContains(response, '<b>busy</b>')

    def test_no_longer_active_shows_answers(self):
        response = self.client.get(reverse('admin:index'), {'month': self.month})
        section = response.content.decode().split('id="no-longer-active"')[1]
        self.assertIn('Pat Rivera', section)
        self.assertRegex(section, r'<th[^>]*>\s*Answer\s*</th>')
        # Pat's row reads name, then her answer (the 2nd), then her time.
        section_text = ' '.join(re.sub(r'<[^>]+>', ' ', section).split())
        self.assertRegex(section_text, r'Pat Rivera 2 Oct \d')


# The start of SPEC.md's by-date copy example, character for character.
SPEC_BY_DATE_START = """Unavailable all month: Sam
1: Jane
3: Bob
4: Bob, Jane
5: Bob"""

# The whole by-date text for the spec-example scenario (SPEC.md only shows the start).
SPEC_BY_DATE_FULL = SPEC_BY_DATE_START + """
6: Bob
7: Bob
10: Jane
11: Jane
13: Emily
20: Bob
27: Jane
28: Jane
29: Jane
30: Jane
31: Jane"""


@override_settings(DEBUG=True)
class ByDateTests(TestCase):
    """#22: the by-date view and its copy text (AD-6, AD-7)."""

    def setUp(self):
        # Today is Oct 5, 2026, so spec-example uses December 2026 (see ByPersonTests).
        self.enterContext(at_utc(2026, 10, 5, 16, 0))
        seed('spec-example')
        self.month = '2026-12'
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))

    def text(self):
        """The by-date copy text for the scenario's month, as it stands now."""
        return by_date_text(month_responses(self.month))

    def test_copy_text_starts_like_spec_example(self):
        self.assertTrue(self.text().startswith(SPEC_BY_DATE_START + '\n'))

    def test_full_copy_text(self):
        # Day 2 is missing: only Pat picked it, and Pat is inactive. Tom didn't respond.
        self.assertEqual(self.text(), SPEC_BY_DATE_FULL)

    def test_all_month_people_are_not_repeated_on_days(self):
        self.assertNotRegex(self.text(), r'\d+: .*Sam')

    def test_all_month_line_left_out_when_nobody_is(self):
        sam = Member.objects.get(first_name='Sam')
        Submission.objects.create(member=sam, month=self.month, kind='days', days=[2])
        text = self.text()
        self.assertNotIn('Unavailable all month', text)
        # Sam's newest answer counts: he's now out on the 2nd, the first line.
        self.assertTrue(text.startswith('1: Jane\n2: Sam\n3: Bob'))

    def test_page_shows_weekdays_and_copy_text(self):
        response = self.client.get(reverse('admin:index'), {'month': self.month})
        # December 4, 2026 is a Friday.
        # Unfold's table: each cell's text sits in its own <div>.
        text = visible_text(response)
        self.assertIn('Fri 4 Bob, Jane', text)
        self.assertContains(response, 'Unavailable all month:</strong> Sam')
        self.assertContains(
            response, f'id="by-date-text" aria-labelledby="by-date-text-label">{escape(SPEC_BY_DATE_FULL)}</pre>'
        )


class ByDateEmptyTests(TestCase):
    """#22: what the by-date view says when nobody is out (AD-6)."""

    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))
        self.bob = Member.objects.create(first_name='Bob', last_name='Smith')
        self.amy = Member.objects.create(first_name='Amy', last_name='Lee')

    def by_date_section(self):
        """The By date section's HTML for October 2026 (always in the month list on Oct 5, 2026)."""
        with at_utc(2026, 10, 5, 16, 0):
            response = self.client.get(reverse('admin:index'), {'month': '2026-10'})
        return response.content.decode().split('id="by-date"')[1]

    def test_no_responses_yet(self):
        section = self.by_date_section()
        self.assertIn('No responses yet.', section)
        self.assertNotIn('by-date-text', section)

    def test_only_inactive_responses_count_as_none(self):
        pat = Member.objects.create(first_name='Pat', last_name='Rivera', is_active=False)
        Submission.objects.create(member=pat, month='2026-10', kind='days', days=[2])
        self.assertIn('No responses yet.', self.by_date_section())

    def test_everyone_so_far_available_all_month(self):
        Submission.objects.create(member=self.bob, month='2026-10', kind='available_all')
        section = self.by_date_section()
        self.assertIn('Nobody is unavailable this month (1 of 2 responded).', section)
        self.assertNotIn('by-date-text', section)
        self.assertEqual(by_date_text(month_responses('2026-10')), '')


@override_settings(DEBUG=True)
class CopyButtonTests(TestCase):
    """
    #23: the Copy buttons the server sends (AD-7).

    Django's tests can't click or read the clipboard; the copying itself is
    checked by hand (see the PR's test steps).
    """

    def setUp(self):
        self.enterContext(at_utc(2026, 10, 5, 16, 0))
        seed('spec-example')
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))

    def page(self, month):
        """The dashboard's HTML for a month."""
        return self.client.get(reverse('admin:index'), {'month': month}).content.decode()

    def test_one_button_per_copy_block(self):
        html = self.page('2026-12')
        for target in ['by-person-text', 'by-date-text']:
            with self.subTest(target=target):
                self.assertEqual(html.count(f'data-copy-target="{target}"'), 1)
                self.assertIn(f'<pre class="copy-text" id="{target}"', html)
                self.assertIn(f'id="{target}-fallback" hidden>', html)

    def test_buttons_have_distinct_screen_reader_names(self):
        html = self.page('2026-12')
        self.assertIn('<span data-copy-label>Copy</span><span class="sr-only"> by-person text</span>', html)
        self.assertIn('<span data-copy-label>Copy</span><span class="sr-only"> by-date text</span>', html)

    def test_copy_text_starts_collapsed(self):
        # #40: each copy text sits in a closed "Show copy text" section, so the
        # cards stay short; the Copy button doesn't need it open.
        html = self.page('2026-12')
        for target in ['by-person-text', 'by-date-text']:
            with self.subTest(target=target):
                self.assertRegex(html, rf'<details class="copy-area">\s*<summary id="{target}-label">Show copy text</summary>')

    def test_people_column_then_dates_column(self):
        # #40: "No longer active" sits under By person (left column), before By date (right column).
        html = self.page('2026-12')
        self.assertLess(html.index('id="by-person"'), html.index('id="no-longer-active"'))
        self.assertLess(html.index('id="no-longer-active"'), html.index('id="by-date"'))

    def test_live_region_for_announcements(self):
        self.assertIn('id="copy-status" class="sr-only" role="status" aria-live="polite"', self.page('2026-12'))

    def test_no_by_date_button_without_copy_text(self):
        # Nobody in this scenario answered for November: "No responses yet." and nothing to copy.
        html = self.page('2026-11')
        self.assertNotIn('data-copy-target="by-date-text"', html)
        # By person still lists everyone ("no response"), so it keeps its button.
        self.assertIn('data-copy-target="by-person-text"', html)


class RememberNameTests(TestCase):
    """TF-11 (#10): the browser remembers the name from its last successful submit."""

    url = reverse('heritage_media_availability:team_form')

    def setUp(self):
        self.bob = Member.objects.create(first_name='Bob', last_name='Smith')
        self.amy = Member.objects.create(first_name='Amy', last_name='Lee')

    def submit(self, member, **overrides):
        """Submit the form as `member` for November 2026 (on Oct 1, 2026)."""
        data = {'member': member.pk, 'month': '2026-11', 'kind': 'available_all', 'notes': ''}
        data.update(overrides)
        with at_utc(2026, 10, 1, 12, 0):
            return self.client.post(self.url, data)

    def selected_member(self):
        """The member id preselected in the name dropdown on a fresh visit, or None."""
        with at_utc(2026, 10, 1, 12, 0):
            html = self.client.get(self.url).content.decode()
        match = re.search(r'<option value="(\d+)" selected>', html)
        return int(match.group(1)) if match else None

    def test_successful_submit_remembers_the_name(self):
        response = self.submit(self.bob)
        cookie = response.cookies['remembered_member']
        self.assertEqual(cookie.value, str(self.bob.pk))
        # Kept for a year, hidden from page scripts, sent only on same-site visits.
        self.assertEqual(cookie['max-age'], 60 * 60 * 24 * 365)
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(self.selected_member(), self.bob.pk)

    def test_failed_submit_remembers_nothing(self):
        response = self.submit(self.bob, kind='days')  # no days picked
        self.assertNotIn('remembered_member', response.cookies)
        self.assertIsNone(self.selected_member())

    def test_new_name_is_remembered_after_its_submit(self):
        self.submit(self.bob)
        self.submit(self.amy)
        self.assertEqual(self.selected_member(), self.amy.pk)

    def test_inactive_member_is_not_preselected(self):
        self.submit(self.bob)
        self.bob.is_active = False
        self.bob.save()
        self.assertIsNone(self.selected_member())

    def test_missing_or_bad_cookie_means_no_preselected_name(self):
        self.assertIsNone(self.selected_member())
        for value in ['', 'abc', '-1', '99999', '1; drop']:
            with self.subTest(value=value):
                self.client.cookies['remembered_member'] = value
                self.assertIsNone(self.selected_member())

    def test_failed_submit_shows_the_submitted_name_not_the_remembered_one(self):
        self.submit(self.bob)
        with at_utc(2026, 10, 1, 12, 0):
            html = self.client.post(
                self.url, {'member': self.amy.pk, 'month': '2026-11', 'kind': 'days', 'notes': ''}
            ).content.decode()
        self.assertIn(f'<option value="{self.amy.pk}" selected>', html)
        self.assertNotIn(f'<option value="{self.bob.pk}" selected>', html)

    @override_settings(SESSION_COOKIE_SECURE=True)
    def test_cookie_is_https_only_in_production(self):
        # Production turns SESSION_COOKIE_SECURE on (settings.py); this cookie follows it.
        self.assertTrue(self.submit(self.bob).cookies['remembered_member']['secure'])


class PrebuiltCssTests(TestCase):
    """#33: team pages use the committed, pre-built Tailwind CSS, not the CDN."""

    css_path = 'heritage_media_availability/app.css'
    url = reverse('heritage_media_availability:team_form')

    def assert_uses_prebuilt_css(self, html):
        """The page links the built stylesheet and has no in-browser Tailwind left."""
        self.assertIn(f'<link rel="stylesheet" href="/static/{self.css_path}">', html)
        self.assertNotIn('cdn.jsdelivr.net', html)
        self.assertNotIn('text/tailwindcss', html)

    def test_team_form_links_the_built_css(self):
        self.assert_uses_prebuilt_css(self.client.get(self.url).content.decode())

    def test_thanks_page_links_the_built_css(self):
        bob = Member.objects.create(first_name='Bob', last_name='Smith')
        with at_utc(2026, 10, 1, 12, 0):
            response = self.client.post(
                self.url,
                {'member': bob.pk, 'month': '2026-11', 'kind': 'available_all', 'notes': ''},
                follow=True,
            )
        self.assertContains(response, 'Thanks, Bob!')
        self.assert_uses_prebuilt_css(response.content.decode())

    def test_csrf_failure_page_links_the_built_css(self):
        # A client that enforces CSRF, posting without a token, gets the friendly 403 page.
        response = Client(enforce_csrf_checks=True).post(self.url, {})
        self.assertEqual(response.status_code, 403)
        self.assert_uses_prebuilt_css(response.content.decode())

    def test_built_css_is_found_without_collectstatic(self):
        # The file is committed inside the app's static/ folder, so Django's
        # finders locate it straight from the source tree (no build, no collectstatic).
        self.assertIsNotNone(finders.find(self.css_path))

    def test_built_css_has_the_classes_pages_rely_on(self):
        # A cheap "did you forget to rebuild?" check: a page-layout class, the
        # accent theme from tailwind/input.css, and the calendar's selected-day style.
        css = Path(finders.find(self.css_path)).read_text()
        for selector in ('.max-w-md', '.text-accent-700', r'.peer-checked\:bg-accent-200'):
            with self.subTest(selector=selector):
                self.assertIn(selector, css)

    def test_every_class_on_the_team_form_has_a_rule(self):
        # Regression (#33): the dropdown and notes classes come from forms.py,
        # not a template, and were left out of the build. Checking the rendered
        # page catches a class from any source. Tailwind escapes : / . [ ] and '
        # in its selectors, so the class names are escaped the same way.
        Member.objects.create(first_name='Bob', last_name='Smith')
        html = self.client.get(self.url).content.decode()
        css = Path(finders.find(self.css_path)).read_text()
        classes = {name for attr in re.findall(r'class="([^"]*)"', html) for name in attr.split()}
        self.assertIn('focus:border-accent-500', classes)  # sanity check: forms.py's classes were rendered
        for name in sorted(classes):
            with self.subTest(name=name):
                self.assertIn('.' + re.sub(r"([:/.\[\]'])", r'\\\1', name), css)


class UnfoldAdminTests(TestCase):
    """#39: the admin runs on django-unfold, in the app's colors, light mode only."""

    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser('skye', password='test-pass-123'))

    def test_admin_uses_unfolds_site(self):
        # Unfold replaces admin.site when Django starts, so every registration
        # and our admin_view() wrapper use it.
        from django.contrib import admin
        from unfold.sites import UnfoldAdminSite

        self.assertIsInstance(admin.site, UnfoldAdminSite)

    def test_app_has_a_readable_name(self):
        # Without a verbose_name, page titles read "Heritage_Media_Availability administration".
        response = self.client.get(reverse('admin:app_list', args=['heritage_media_availability']))
        self.assertContains(response, 'Heritage Media administration')
        self.assertNotContains(response, 'Heritage_Media_Availability')

    def test_accent_is_tailwind_indigo(self):
        # Unfold writes the COLORS setting into the page as CSS variables;
        # indigo-600 is the shade used for buttons and links.
        response = self.client.get(reverse('admin:heritage_media_availability_member_changelist'))
        self.assertContains(response, settings.TAILWIND_INDIGO['600'])

    def test_admin_stylesheet_is_loaded(self):
        # UNFOLD["STYLES"]: our plain CSS (e.g. forcing light dropdown lists) on every admin page.
        response = self.client.get(reverse('admin:heritage_media_availability_member_changelist'))
        self.assertContains(response, '/static/heritage_media_availability/admin.css')
        css = Path(finders.find('heritage_media_availability/admin.css')).read_text()
        self.assertIn('color-scheme: light', css)

    def test_light_mode_only(self):
        # THEME = "light" removes the Light/Dark switcher everywhere: on an
        # admin page (logged in) and on the login page (logged out).
        admin_page = self.client.get(reverse('admin:heritage_media_availability_member_changelist'))
        self.client.logout()
        login_page = self.client.get(reverse('admin:login'))
        for name, response in [('admin page', admin_page), ('login page', login_page)]:
            with self.subTest(page=name):
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "switchTheme('dark')")
