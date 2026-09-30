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
5. **Keep this file current.** When we add a command or make a lasting decision, update the Commands or Decisions section below.

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

- Run locally: *TBD*
- Run tests: *TBD*
- Create admin user: *TBD*

### Decisions

\<!-- Record lasting decisions here with a date. -->

- 2026-09-28: Admin login uses a Django superuser (stored in the database, password hashed). SPEC.md updated to match.
- 2026-09-29: The by-date view (AD-6) and the by-date copy text both skip days with nobody out. (Replaces a 2026-09-28 decision to show every day in the view.)
- 2026-09-28: Close and Reopen month happen inside Django admin (AD-8), not on the custom dashboard. They're available for past months too.
- 2026-09-28: The server rejects a submission only when its month is closed. Past months should normally be closed, but that's left flexible for exceptions.
- 2026-09-29: Months are closed manually by Skye; nothing closes automatically. The team month dropdown is always current month through +6; reopened past months are never offered.
- 2026-09-29: `ClosedMonth` model and its admin are built in Week 2 (with the team form), not Week 1.
- 2026-09-29: Approved packages: django, psycopg[binary], gunicorn, whitenoise. `DATABASE_URL` is parsed with the standard library (no dj-database-url); local `.env` is loaded with `uv run --env-file .env` (no python-dotenv).
- 2026-09-28: `Submission.days` uses Postgres `ArrayField` (django.contrib.postgres).
- 2026-09-28: TF-9 pre-fill loads the earlier submission with a small JS fetch, with no page reload.
- 2026-09-28: Member names are unique regardless of capitalization ("bob" and "Bob" count as duplicates).
- 2026-09-28: By-person copy lists responders A–Z, then non-responders A–Z.
- 2026-09-28: TF-6 all-month choice is a dropdown (specific days / available all month / unavailable all month) instead of toggles.
- 2026-09-28: To review later: weekly database backups (NFR). Check what Railway Hobby provides when we reach deployment hardening.
