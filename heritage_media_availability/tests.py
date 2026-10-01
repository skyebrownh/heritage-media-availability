"""
Automated tests for the Heritage Media Availability app.

Run them with:  uv run --env-file .env python manage.py test
Django creates a separate throwaway test database, so your real data is safe.
"""

import os
import runpy
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from config.env import env_bool, env_list, env_required, parse_database_url

from .models import Member


class HomePageTests(TestCase):
    """The Week 1 placeholder page loads at the site root."""

    def test_home_page_loads(self):
        response = self.client.get(reverse('heritage_media_availability:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Heritage Media Availability')

    def test_home_is_the_site_root(self):
        # The shared team link (TF-1) will be the bare domain, so "/" must work.
        self.assertEqual(reverse('heritage_media_availability:home'), '/')


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
