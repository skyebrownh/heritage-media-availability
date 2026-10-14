# Heritage Media Availability

A small, mobile-friendly web app where Heritage church media team volunteers submit the days they can't serve each month. The admin sees every response in one place and copies the results into the scheduling template.

It replaces the monthly group-chat thread. The app only **collects and displays** availability; it never schedules anyone.

- **Team side:** one shared link with no login. Pick your name and a month, tap the days you're out (or choose "available/unavailable all month"), and submit. A new submission replaces your old one.
- **Admin side:** a password-protected roster, a tracker of who has responded, by-person and by-date views with copy buttons, and closing/reopening months.

See [SPEC.md](SPEC.md) for the full requirements (with IDs like TF-3 and AD-2, plus a decision log) and [CLAUDE.md](CLAUDE.md) for working conventions and architecture notes. Work is tracked in [GitHub Issues](../../issues), grouped by [milestone](../../milestones).

## Status

v1 is in development, with launch to the full team planned for **October 25, 2026**. Week 1 (setup, roster, deploy) is done. Progress on the rest is tracked by [milestone](../../milestones): Week 2 (team form), Week 3 (admin views), Week 4 (pilot), and Post-launch.

## How work happens

1. Each unit of work is a GitHub issue with a directive and acceptance criteria (templates in `.github/ISSUE_TEMPLATE/`).
2. Work happens on a branch named `<issue#>-<short-slug>`.
3. A pull request with `Closes #<issue>` is **squash merged** into `main`, which closes the issue and deploys.

## Tech stack

- Python 3.13, Django (server-rendered templates)
- Postgres everywhere (local and production), configured with `DATABASE_URL`
- Tailwind CSS (from the CDN for now; pre-built CSS before launch, see #14) and a little vanilla JavaScript
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
backup/                       Weekly production database backups, run on Skye's Mac
railway.json                  Railway build/deploy commands
SPEC.md                       Requirements and decisions (source of truth)
CLAUDE.md                     Conventions and architecture notes
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

> **Note:** Railway stops reading `railway.json` on **2026-12-01**. Before then, these commands need to move to Railway's Infrastructure as Code or the dashboard. This is tracked as a Post-launch issue.

## Backups

Railway's Hobby plan has no database backups, so Skye's Mac makes them (#3). Once a week, a scheduled job runs `pg_dump` inside production's Postgres service through the Railway CLI and saves a compressed copy in `~/Backups/heritage-media-availability/`, keeping the newest 8 (about two months). No database password is stored anywhere; it uses the Railway CLI's own login.

The backups hold real names and the admin's hashed password, so they stay on the Mac (in a folder only Skye's account can open) and are never committed.

### Setting it up

Prerequisites: the [Railway CLI](https://docs.railway.com/guides/cli), logged in (`railway login`) and linked to this project (`railway link`).

```sh
bash backup/install.sh
```

This copies `backup/backup.sh` into the backup folder and installs a `launchd` job (macOS's scheduler) that checks every day at 10am and at login. It only makes a backup when the newest one is 7 or more days old, so a week missed while the Mac was off is caught up the next day it's on. Rerun the installer after changing `backup/backup.sh`. To stop the job (backups are kept): `bash backup/install.sh --uninstall`.

### Day to day

| Task | Command |
| --- | --- |
| See how backups are doing | `~/Backups/heritage-media-availability/backup.sh status` |
| Back up right now | `~/Backups/heritage-media-availability/backup.sh now` |

- **A banner, "Heritage backup saved"**, about once a week means it worked.
- **An alert, "Heritage backup failed"**, stays on screen until dismissed. It says what went wrong and how old the newest good backup is. The most common cause is an expired Railway login: run `railway login`, then `backup.sh now`. Railway's own messages from the latest attempt are in `last-run-output.log` in the backup folder.
- `backup.log` has one line per attempt; daily "Checked … nothing to do" lines show the job is running.
- macOS shows the notifications as coming from "Script Editor". If they don't appear, allow Script Editor in System Settings → Notifications.
- To test the failure alert without touching anything: `RAILWAY_PROJECT_ID=00000000-0000-0000-0000-000000000000 ~/Backups/heritage-media-availability/backup.sh now`

### Practice restore

Do this now and then to make sure the backups really work. It restores into a throwaway local database, never production or staging. Production runs Postgres 18, so the practice uses Postgres 18 too (`brew install postgresql@18`), started on port 5433 so it doesn't clash with the everyday local Postgres.

```sh
# Start Postgres 18 just for this, and make an empty database
PG18=/opt/homebrew/opt/postgresql@18/bin
LC_ALL=en_US.UTF-8 $PG18/pg_ctl -D /opt/homebrew/var/postgresql@18 -o "-p 5433" -l /tmp/pg18.log -w start
$PG18/createdb -p 5433 heritage_restore_test

# Load the newest backup (ON_ERROR_STOP stops at the first error instead of carrying on)
F=$(ls ~/Backups/heritage-media-availability/heritage-*.sql.gz | sort | tail -1)
gunzip -c "$F" | $PG18/psql -p 5433 -d heritage_restore_test -v ON_ERROR_STOP=1 -q -o /dev/null

# Count members in the copy, then in production (read-only); they should match
# (also try heritage_media_availability_submission and _closedmonth)
$PG18/psql -p 5433 -d heritage_restore_test -At -c "select count(*) from heritage_media_availability_member"
railway ssh --service Postgres --environment production -- psql -At -c "select count(*) from heritage_media_availability_member"

# Clean up
$PG18/dropdb -p 5433 heritage_restore_test
$PG18/pg_ctl -D /opt/homebrew/var/postgresql@18 -w stop
```

Counts can differ by a few submissions if someone submitted since the backup was made.

Last tested 2026-10-14: restored with no errors, and members (17), submissions (0) and closed months (2) matched production.

### Emergency restore into Railway

Only if production's data is lost or damaged, and only after talking it through first. The outline: put Railway in a safe state (e.g. close the months being collected, so nobody submits mid-restore), make a fresh backup of what's there now with `backup.sh now`, empty or replace production's database, then load the chosen backup with Railway's own `psql`:

```sh
gunzip -c ~/Backups/heritage-media-availability/heritage-YYYY-MM-DD-HHMM.sql.gz \
  | railway ssh --service Postgres --environment production -- psql -v ON_ERROR_STOP=1
```

Then check the dashboard and the roster look right.
