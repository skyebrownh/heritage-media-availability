# CLAUDE.md

## Heritage Media Availability Form

A small web app where Heritage church media team members submit the days they're unavailable each month, and the admin (Skye) views all responses. **SPEC.md is the source of truth.** Read it before starting any task, and cite requirement IDs (TF-#, AD-#) in plans and summaries.

This app only collects and displays availability. It never schedules anyone.

@SPEC.md

### About me

- I have a computer science background but I'm new to vibe coding and to Django.
- Explain what you did and why in plain language after each step. Keep it short.
- If the spec is unclear or two requirements conflict, ask me. Don't guess.

### How we work

1. **Plan first.** For every task, show a short plan (files to create or change, and why) and wait for my approval before writing code.
2. **Small steps.** Build one requirement or a small group of related ones at a time. Never build ahead of the current step.
3. **Tell me how to test.** After each step, give me exact manual test steps (what to click, what I should see) and run the automated tests.
4. **Dependencies.** Ask before adding any package. Prefer the standard library and Django built-ins.
5. **Keep docs current.** Spec decisions (what the app does) go in SPEC.md: update the requirement itself, and log the decision with a date in SPEC.md's Decisions section. This file holds only conventions, standards, and architectural context; update it when those change or when we add a command.

### Code comments

Write good explanatory comments throughout. I'll be reading this code to learn from it.

- Every module, class, and function gets a docstring saying what it's for.
- Comment non-obvious logic with *why* it works this way, not just what it does.
- Reference requirement IDs where code implements them (e.g. `# TF-6: all-month options clear the calendar`).
- Templates and JavaScript get comments too, explaining each section's purpose.
- Don't restate obvious code (e.g. no `# increment i`).

### Python tooling: uv only

- Use uv for everything Python. Never use pip, pipenv, or manual virtualenv activation.
- Add packages with `uv add <package>` (dev-only tools with `uv add --dev`). This keeps `pyproject.toml` and `uv.lock` in sync.
- Run commands with `uv run`, e.g. `uv run python manage.py runserver`.
- Commit `uv.lock`. Set up deployment so Railway installs from it.

### Git workflow

- The local repo is the working copy. GitHub (`origin`) is the upstream. Railway deploys automatically from `main`.
- Work on a short-lived branch per step (e.g. `week1-models`), never directly on `main`.
- When a step works and tests pass, suggest a commit message. Only commit, push, or merge when I say so.
- Merging to `main` means deploying. Remind me of that before any merge.

### Stack (do not change without asking)

- Repo and folder: `heritage-media-availability`
- Django project package: `config`. Django app: `heritage_media_availability` (underscores, because Python module names can't contain hyphens)
- Python 3.12+ and current stable Django
- Server-rendered Django templates; no React, Vue, or other SPA framework
- Tailwind CSS via CDN; small vanilla JavaScript (or Alpine.js if I approve) for the calendar toggles and copy buttons
- Postgres everywhere: my local Postgres for development, Railway Postgres in production, both via `DATABASE_URL`
- Hosting: Railway (Hobby plan), deployed from GitHub
- gunicorn serves the app in production; WhiteNoise serves static files (CSS, JS, admin styles)
- Django's built-in test runner for tests
- Approved packages: `django`, `psycopg[binary]`, `gunicorn`, `whitenoise`. Anything else needs approval first.
- `DATABASE_URL` is parsed with the standard library (`config/env.py`), not dj-database-url. Local `.env` is loaded with `uv run --env-file .env`, not python-dotenv.
- Static files use WhiteNoise's `CompressedStaticFilesStorage` (no filename hashing), so tests don't need `collectstatic` first. Only the admin has static files; Tailwind comes from the CDN.
- `check --deploy` warnings mail.E001, security.W005 and security.W021 are silenced on purpose (reasons in `config/settings.py`). Revisit if we add a custom domain.

### Secrets and security

- Never put secrets in code, commits, or chat. Read them from environment variables: `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`.
- Keep `.env` in `.gitignore`. Provide a `.env.example` with placeholder values only.
- The admin area uses Django's built-in login (one superuser, Skye). Sessions last about 30 days (AD-1).
- Validate everything on the server. Never rely on the form alone.

### Business rules (summary; full detail in SPEC.md)

- Months are stored as `YYYY-MM`. Time zone is `America/New_York`. Dates are whole days, with no times.
- The team can submit for the current month through 6 months ahead. There's no step to "open" a month.
- A closed month rejects submissions on the server, even from a form that was already open. Admin can reopen.
- Every submission is kept. The newest per member and month is the current one ("last submission wins").
- A submission's `kind` is exactly one of `days`, `available_all`, or `unavailable_all`. `days` is empty unless kind is `days`.
- Any submission counts as a response. Inactive members are hidden from the dropdown, tracker, and copy output, but their history stays.
- Copy output formats must match SPEC.md exactly (by-person and by-date).
- Out of scope for v1. Do not build: notifications, phone login, recurring availability rules, export, time-of-day availability, roles, scheduling.

### Design rules

- Mobile first: design at 375px wide, then scale up.
- Base text at least 16px, tap targets at least 44px, high contrast.
- Neutral palette with one soft pastel blue accent. Clean cards and generous white space, in the spirit of Airtable and Zapier forms.
- Plain, friendly wording (e.g. "Which days can't you serve?"). Many users are older and not comfortable with tech.
- Every input has a label, and calendar days work with a keyboard and screen reader.

### Commands

\<!-- Fill in as the project is set up. -->

All commands load local settings from `.env` (copy `.env.example` first).

- Run locally: `uv run --env-file .env python manage.py runserver` → http://127.0.0.1:8000/
- Run tests: `uv run --env-file .env python manage.py test`
- Apply database migrations: `uv run --env-file .env python manage.py migrate`
- Create admin user (local): `uv run --env-file .env python manage.py createsuperuser`
- Create admin user (Railway): `railway ssh`, then `python manage.py createsuperuser` (or `changepassword <username>` to reset), then `exit`
- Make migrations after changing models: `uv run --env-file .env python manage.py makemigrations`
- Production readiness check: `DEBUG=false uv run --env-file .env python manage.py check --deploy` (should report no issues)

Deploying: pushing/merging to `main` deploys on Railway. `railway.json` (JSON, so it can't hold comments) tells Railway to:
- build with Railpack, which installs exactly what's in `uv.lock` and uses `.python-version`;
- run `python manage.py migrate` before each deploy (a failed migration cancels the deploy, and the old version keeps running);
- start with `migrate --check` (fails the deploy if any migration wasn't applied), then `collectstatic`, then `gunicorn config.wsgi` (gunicorn options live in `gunicorn.conf.py`).
- Note (2026-10-01): the first deploy skipped the file's pre-deploy migrate, so the same command is also set in the dashboard (Settings → Deploy → Pre-deploy Command). Root cause still being checked.
- To do before 2026-12-01: Railway stops reading `railway.json` (Config as Code) on that date in favor of Infrastructure as Code (`.railway/railway.ts`, which needs a Node package; a Python version is in beta). Decide after launch whether to migrate or move these commands into the Railway dashboard.
