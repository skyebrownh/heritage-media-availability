# Heritage Media Availability

A small, mobile-friendly web app where Heritage church media team volunteers submit the days they can't serve each month. The admin sees every response in one place and copies the results into the scheduling template.

It replaces the monthly group-chat thread. The app only **collects and displays** availability; it never schedules anyone.

- **Team side:** one shared link with no login. Pick your name and a month, tap the days you're out (or choose "available/unavailable all month"), and submit. A new submission replaces your old one.
- **Admin side:** a password-protected roster, a tracker of who has responded, by-person and by-date views with copy buttons, and closing/reopening months.

See [SPEC.md](SPEC.md) for the full requirements (with IDs like TF-3 and AD-2, plus their status) and [CLAUDE.md](CLAUDE.md) for working conventions and the decision log.

## Status

v1 is in development, with launch to the full team planned for **October 25, 2026**.

| Week | Dates | Focus | Status |
| --- | --- | --- | --- |
| 1 | Sep 28 – Oct 4 | Setup, roster, deploy | ✅ Done |
| 2 | Oct 5 – Oct 11 | Team form | Up next |
| 3 | Oct 12 – Oct 18 | Admin views | |
| 4 | Oct 19 – Oct 24 | Pilot with 3–5 people | |

## Tech stack

- Python 3.13, Django (server-rendered templates)
- Postgres everywhere (local and production), configured with `DATABASE_URL`
- Tailwind CSS via CDN and a little vanilla JavaScript
- gunicorn + WhiteNoise in production
- Hosted on [Railway](https://railway.com), deployed automatically from `main`
- [uv](https://docs.astral.sh/uv/) for Python packages and commands

## Local setup

**Prerequisites:** [uv](https://docs.astral.sh/uv/getting-started/installation/) and Postgres. On macOS with Homebrew:

```sh
brew install postgresql@17
brew services start postgresql@17
createdb heritage_media_availability
```

**Then:**

```sh
git clone git@github.com:skyebrownh/heritage-media-availability.git
cd heritage-media-availability

cp .env.example .env     # then edit .env (see below)
uv sync                  # installs Python and the exact packages from uv.lock

uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py createsuperuser
uv run --env-file .env python manage.py runserver
```

Open http://127.0.0.1:8000/ for the site and http://127.0.0.1:8000/admin/ for the roster.

### Environment variables

Settings come from environment variables, never from code. Locally they live in `.env`, which git ignores. Every command loads it with `uv run --env-file .env …`.

| Variable | Local value | Production value |
| --- | --- | --- |
| `SECRET_KEY` | Any long random string (see below) | A different long random string |
| `DEBUG` | `true` | `false` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | The app's domain, e.g. `example.up.railway.app` |
| `CSRF_TRUSTED_ORIGINS` | *(empty)* | `https://` + the app's domain |
| `DATABASE_URL` | `postgresql://<your-mac-username>@localhost:5432/heritage_media_availability` | Railway reference: `${{Postgres.DATABASE_URL}}` |

To generate a secret key:

```sh
uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

## Common commands

| Task | Command |
| --- | --- |
| Run the dev server | `uv run --env-file .env python manage.py runserver` |
| Run the tests | `uv run --env-file .env python manage.py test` |
| Create migrations after model changes | `uv run --env-file .env python manage.py makemigrations` |
| Apply migrations | `uv run --env-file .env python manage.py migrate` |
| Check production settings | `DEBUG=false uv run --env-file .env python manage.py check --deploy` |
| Add a Python package | `uv add <package>` |

Tests use Django's built-in test runner. They run against a temporary Postgres database that's created and deleted automatically.

## Project layout

```
config/                       Django project: settings, URLs, WSGI
  env.py                      Reads settings from environment variables
heritage_media_availability/  The app: models, admin, views, templates, tests
gunicorn.conf.py              Production web server settings
railway.json                  Railway build/deploy commands
SPEC.md                       Requirements (source of truth)
CLAUDE.md                     Conventions and decision log
```

## Deployment

Merging to `main` deploys to Railway automatically. **Treat every merge to `main` as a release.** Work happens on short-lived branches, one per step.

On each deploy, Railway:

1. **Builds** with Railpack, installing exactly what's in `uv.lock`.
2. **Pre-deploy:** runs `python manage.py migrate`. If it fails, the deploy is cancelled and the previous version keeps running.
3. **Starts:** `migrate --check` (refuses to start if any migration is missing), then `collectstatic`, then gunicorn.

**Creating or resetting the production admin account** uses the [Railway CLI](https://docs.railway.com/guides/cli):

```sh
railway link     # one time: choose the project, environment and service
railway ssh      # opens a shell inside the running app
python manage.py createsuperuser     # or: python manage.py changepassword <username>
exit
```

> **Note:** Railway stops reading `railway.json` on **2026-12-01**. Before then, these commands need to move to Railway's Infrastructure as Code or the dashboard. This is tracked in CLAUDE.md.
