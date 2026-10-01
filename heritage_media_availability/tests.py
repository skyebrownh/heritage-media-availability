"""
Automated tests for the Heritage Media Availability app.

Run them with:  uv run --env-file .env python manage.py test
Django creates a separate throwaway test database, so your real data is safe.
"""

import os
import runpy
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from config.env import env_bool, env_list, env_required, parse_database_url

from .models import ClosedMonth, Member, Submission
from .months import days_in_month, month_label, month_weeks, upcoming_months, validate_month


def at_utc(*args):
    """Patch "now" to a fixed UTC moment, so date-dependent code is predictable in tests."""
    return mock.patch('django.utils.timezone.now', return_value=datetime(*args, tzinfo=UTC))


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

    def test_closed_message_text_is_on_the_page(self):
        # TF-4: exact wording. Showing and hiding it is covered by the manual test steps.
        self.assertContains(self.client.get(self.url), "This month's schedule is finalized. Please text Skye with any changes.")


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
        self.assertContains(response, 'Heritage Media Admin')

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


class ClosedMonthAdminTests(TestCase):
    """AD-8: closing (with confirmation) and reopening months in Django admin."""

    def setUp(self):
        admin_user = get_user_model().objects.create_superuser('skye', password='test-pass-123')
        self.client.force_login(admin_user)
        self.add_url = reverse('admin:heritage_media_availability_closedmonth_add')
        self.list_url = reverse('admin:heritage_media_availability_closedmonth_changelist')

    def test_add_form_uses_month_picker(self):
        response = self.client.get(self.add_url)
        self.assertContains(response, 'type="month"')
        self.assertNotContains(response, '_addanother')
        self.assertNotContains(response, '_continue')

    def test_save_shows_confirmation_without_closing(self):
        response = self.client.post(self.add_url, {'month': '2026-11'})
        self.assertContains(response, 'Close November 2026?')
        self.assertContains(response, 'Yes, close it')
        self.assertFalse(ClosedMonth.objects.exists())

    def test_confirming_closes_the_month(self):
        response = self.client.post(self.add_url, {'month': '2026-11', 'confirm': 'yes'})
        self.assertRedirects(response, self.list_url)
        self.assertTrue(ClosedMonth.objects.filter(month='2026-11').exists())

    def test_past_months_can_be_closed(self):
        self.client.post(self.add_url, {'month': '2020-01', 'confirm': 'yes'})
        self.assertTrue(ClosedMonth.objects.filter(month='2020-01').exists())

    def test_invalid_month_returns_to_form_without_confirmation(self):
        response = self.client.post(self.add_url, {'month': '2026-13'})
        self.assertNotContains(response, 'Yes, close it')
        self.assertContains(response, 'Enter a month like 2026-11')

    def test_already_closed_month_gets_friendly_error(self):
        ClosedMonth.objects.create(month='2026-11')
        # Checked on the first Save and again on confirm (e.g. closed in another tab meanwhile).
        for data in [{'month': '2026-11'}, {'month': '2026-11', 'confirm': 'yes'}]:
            with self.subTest(data=data):
                response = self.client.post(self.add_url, data)
                self.assertContains(response, 'That month is already closed.')
        self.assertEqual(ClosedMonth.objects.count(), 1)

    def test_reopen_action_deletes_selected_rows(self):
        ClosedMonth.objects.create(month='2026-11')
        ClosedMonth.objects.create(month='2026-12')
        response = self.client.post(
            self.list_url,
            {'action': 'reopen_months', '_selected_action': ['2026-11']},
            follow=True,
        )
        self.assertContains(response, 'Reopened November 2026.')
        self.assertEqual(list(ClosedMonth.objects.values_list('month', flat=True)), ['2026-12'])

    def test_list_shows_month_names_and_only_reopen_action(self):
        ClosedMonth.objects.create(month='2026-11')
        response = self.client.get(self.list_url)
        self.assertContains(response, 'November 2026')
        self.assertContains(response, 'Reopen selected months')
        self.assertNotContains(response, 'delete_selected')

    def test_edit_and_delete_are_blocked(self):
        ClosedMonth.objects.create(month='2026-11')
        change_url = reverse('admin:heritage_media_availability_closedmonth_change', args=['2026-11'])
        delete_url = reverse('admin:heritage_media_availability_closedmonth_delete', args=['2026-11'])
        with self.assertLogs('django.request', level='WARNING'):
            self.client.post(change_url, {'month': '2026-12'})
            self.client.post(delete_url, {'post': 'yes'})
        self.assertEqual(list(ClosedMonth.objects.values_list('month', flat=True)), ['2026-11'])


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
