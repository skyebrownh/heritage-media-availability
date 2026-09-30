"""
Automated tests for the Heritage Media Availability app.

Run them with:  uv run --env-file .env python manage.py test
Django creates a separate throwaway test database, so your real data is safe.
"""

import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from config.env import env_bool, env_list, env_required, parse_database_url


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
