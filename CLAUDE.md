# CLAUDE.md

## Heritage Media Availability Form

A small web app where Heritage church media team members submit the days they're unavailable each month, and the admin (Skye) views all responses. **SPEC.md is the source of truth** for what the app does and why (requirements, business rules, data model). **GitHub Issues** hold the work: each issue is one unit to build, with a directive and acceptance criteria. Read SPEC.md and the issue before starting any task, and cite requirement IDs (TF-#, AD-#) and the issue number (#N) in plans and summaries.

This app only collects and displays availability. It never schedules anyone.

@SPEC.md

### About me

- I have a computer science background but I'm new to vibe coding and to Django.
- Explain what you did and why in plain language after each step. Keep it short.
- If the spec is unclear or two requirements conflict, ask me. Don't guess.

### How we work

Every piece of work follows this loop. `gh` (GitHub CLI) is installed and authenticated for the repo.

1. **Draft the issue.** You draft it in chat using the matching template in `.github/ISSUE_TEMPLATE/` (feature or bug). I approve or edit it. Then you create it with `gh issue create`, with a milestone and area label.
2. **Plan.** Before writing code, show a short plan (files to create or change, and why) and wait for my approval. Once approved, post the plan as a comment on the issue (`gh issue comment`) so the reasoning stays with the work.
3. **Build in small steps.** One issue = one requirement or a small group of related ones. Usually one issue = one branch = one PR; issues that must ship together share a branch and PR (see Git workflow). Never build ahead of the current issue; anything else becomes a new issue.
4. **Tell me how to test.** When the work is done, run the automated tests and give me exact manual test steps (what to click, what I should see), mapped to the issue's acceptance criteria.
5. **Dependencies.** Ask before adding any package. Prefer the standard library and Django built-ins.
6. **Keep docs current.** If a decision changes what the app does, update the requirement in SPEC.md in the same PR. Decisions that don't fit any requirement get a dated entry in SPEC.md's Decisions section. Discussion and context live in the issue. This file holds only conventions, standards, and architectural context; update it when those change or when we add a command.

### Issues, milestones and labels

- **Milestones** are the build weeks ("Week 2: Team form", "Week 3: Admin views", "Week 4: Pilot") plus "Post-launch". Every issue gets one.
- **Area labels:** `team-form`, `admin`, `infra`, `documentation`. Type labels: `feature`, `bug`, `accessibility`.
- An issue's **acceptance criteria** are a checklist of things you can see or a test can check. Tick them in the PR, not the issue.
- Status lives in GitHub (open/closed issues, milestone progress), never in the docs.

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

- The local repo is the working copy. GitHub (`origin`) is the upstream. **Railway deploys automatically from `main`, so merging to `main` is deploying.**
- Never commit directly to `main`. Branches start from an up-to-date `main`. Every branch has one of two shapes:
  - **Single-issue branch** (the default): one issue, one branch named `<issue#>-<short-slug>` (e.g. `12-closed-month-admin`), one PR, **squash merged**, so it becomes one commit on `main` titled after the issue.
  - **Multi-issue branch**: for issues that must ship together (e.g. one would leave the live site half-finished without the next). The issues are built one after another on one branch named after the set (e.g. `unfold-admin`), with one PR that closes them all, **rebase merged**, so `main` keeps each commit. An issue can have more than one commit (e.g. a fix to the first issue found while testing the second). Each issue still gets its own plan, handover, and review; I'll name the set when we decide to batch.
- Leave changes uncommitted until I've reviewed them in my editor. When the work is ready, suggest a commit message and wait for my OK before committing.
- Open a PR with `gh pr create` using `.github/pull_request_template.md`. The description must include `Closes #<issue>` for each issue, so merging closes them. For a multi-issue branch, open the PR once every issue in the set is committed.
- Commits are never rewritten once committed. Something wrong after a merge becomes a new bug issue.

**What you may do on your own:**
- Create issues I've approved
- Push feature branches and open PRs, once I've approved the commits on them (none of these deploy)
- Comment on issues and PRs

**Only with my explicit approval:**
- Committing (I review uncommitted changes first)
- Merging a PR (this deploys). Remind me of that before asking.
- Pushing to `main` by any route
- Closing an issue any way other than merging its PR
- Changing repo settings, deleting branches on GitHub, or editing milestones and labels beyond adding new ones I've agreed to

### Conventions we've settled on

Formats and routines for each step of the loop above. Recent issues and PRs (e.g. #9 and PR #19) show them in practice.

- **Plan comments.** Post the approved plan on the issue under a `## Plan (approved)` heading. Put any decisions made while planning first (with the date if they belong in SPEC.md), then the branch name, then numbered steps by file, then what's deliberately not included. If the build has to differ from the plan, say so in the handover and the PR.
- **Handing work over for review.** Before asking to commit, give me:
  - what changed, as a short list with a link to each file;
  - the automated test result (count, pass or fail) and that `check --deploy` is clean;
  - numbered manual test steps, saying exactly what to click and what I should see. They start with "0. Run `seed <scenario>`" and refer to the seeded people by name (see Test data below);
  - a suggested commit message.

  Then wait. If testing turns something up, fix it on the same branch, and add a regression test when it's a bug.
- **Test data.** `manage.py seed <scenario>` resets my local database to a known starting state (scenarios live in `heritage_media_availability/seeding.py`). Seed the setup, not the behavior under test: anything a manual step exists to check (submitting, resubmitting, closing or reopening a month, marking someone inactive), I do by hand during the steps, and the steps say so. When an issue needs a different starting state, it adds or updates a scenario in its own PR.
- **Commit messages.** The co-author line always ends the message.
  - Single-issue branch: the issue's title.
  - Multi-issue branch: the issue's title for its main commit; any further commit gets a short description of the change. Every commit's body says which issue it's for (`Part of #39.`), since rebase merging keeps these commits on `main`.
- **PR descriptions.** Follow the template:
  - `Closes #N` (one line per issue on a multi-issue branch);
  - "What changed" by file (grouped by issue on a multi-issue branch);
  - each issue's acceptance criteria copied and ticked, with the test count on the tests line;
  - numbered "How to test" steps; a multi-issue PR ends with steps that check the issues together;
  - the checklist, with a reason for any box that doesn't apply (e.g. "no model changes").

  Use the issues' milestone and labels. A multi-issue PR's title names the set (e.g. "Move the admin to Unfold").
- **Merging.**
  - Single-issue PR: squash, titled `<issue title> (#<PR number>)`, e.g. `gh pr merge 19 --squash --subject "Pre-fill a person's earlier submission for the month (#19)"`.
  - Multi-issue PR: rebase, e.g. `gh pr merge 43 --rebase`. The branch's commits land on `main` as they are.
- **After a merge:**
  1. `git checkout main && git pull --ff-only`
  2. Confirm `git diff main <branch>` is empty.
  3. `git branch -D <branch>` (needed because squash and rebase merging both create new commits, so git doesn't see the branch as merged).
  4. `git fetch --prune`
  5. Check the issue (or every issue in the set) closed.
  6. Remind me what to check on Railway.

  GitHub deletes the remote branch automatically.
- **Ideas that come up mid-issue** become a new issue, or a comment on an existing one (e.g. design ideas go on the polish issue, #14), never extra scope on the current branch.
- **Long text for `gh`** (issue bodies, plan comments, PR descriptions) goes in a file in the scratchpad directory, passed with `--body-file`, so quotes and backticks survive the shell.

### Stack (do not change without asking)

- Repo and folder: `heritage-media-availability`
- Django project package: `config`. Django app: `heritage_media_availability` (underscores, because Python module names can't contain hyphens)
- Python 3.12+ and current stable Django
- Server-rendered Django templates; no React, Vue, or other SPA framework
- Tailwind CSS v4.3.3, pre-built with Tailwind's standalone CLI (a single binary, no Node or npm). The input is `tailwind/input.css`; the output, `heritage_media_availability/static/heritage_media_availability/app.css`, is committed and served by WhiteNoise. Never edit the output by hand. Rebuild it whenever template classes or the input change, and commit it with them. Dark mode is off (`dark:` classes never apply).
- Tailwind Plus Application UI blocks (Skye's license; HTML version only, kept outside the repo) are the starting point for UI. Adapt them into templates. Blocks using `<el-*>` tags need the Tailwind Plus Elements JavaScript, which needs approval first.
- Small vanilla JavaScript (or Alpine.js if I approve) for the calendar toggles and copy buttons
- Postgres everywhere: my local Postgres for development, Railway Postgres in production, both via `DATABASE_URL`
- Hosting: Railway (Hobby plan), deployed from GitHub
- gunicorn serves the app in production; WhiteNoise serves static files (CSS, JS, admin styles)
- Django's built-in test runner for tests
- Approved packages: `django`, `psycopg[binary]`, `gunicorn`, `whitenoise`, `django-unfold`. Anything else needs approval first.
- The admin is styled by django-unfold (#39). Its settings (site name, colors, light-only theme, sidebar links) are the `UNFOLD` block at the end of `config/settings.py`. Admin pages use Unfold's components and templates, not our Tailwind `app.css`; anything Unfold's stylesheet lacks is plain CSS loaded through `UNFOLD["STYLES"]`. Unfold is pre-1.0 and `uv.lock` pins it: upgrade deliberately with `uv lock --upgrade-package django-unfold`, then run the tests and click through the admin.
- Skye's availability dashboard is the admin home page (#40): `heritage_media_availability/admin_dashboard.py` (`UNFOLD["DASHBOARD_CALLBACK"]`) prepares the data, and `templates/admin/index.html` draws it with Unfold components. The dashboard's own styles are in `static/heritage_media_availability/admin.css`.
- `INSTALLED_APPS` order matters for templates: our app, then `unfold`, then `django.contrib.admin` (reasons in `config/settings.py`).
- `DATABASE_URL` is parsed with the standard library (`config/env.py`), not dj-database-url. Local `.env` is loaded with `uv run --env-file .env`, not python-dotenv.
- Static files use WhiteNoise's `CompressedStaticFilesStorage` (no filename hashing), so tests don't need `collectstatic` first. Static files are the admin's, Unfold's (CSS, fonts, scripts, all self-hosted), plus our built `app.css`.
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
- Any submission counts as a response. Inactive members are hidden from the dropdown, tracker, and copy output, but their history stays. On Skye's dashboard, inactive members who responded to the selected month appear in a separate "No longer active" section (never counted or copied), and members added after a month ended aren't listed for it.
- Copy output formats must match SPEC.md exactly (by-person and by-date).
- Out of scope for v1. Do not build: notifications, phone login, recurring availability rules, export, time-of-day availability, roles, scheduling.

### Design rules

- Mobile first: design at 375px wide, then scale up.
- Follow Tailwind Plus defaults, with no exceptions: `text-base sm:text-sm` (16px on phones, 14px from 640px up), its control and button sizes, its gray palette, and its default indigo accent. Contrast meets WCAG AA.
- Clean cards and generous white space, as in the Tailwind Plus blocks.
- Plain, friendly wording (e.g. "Which days can't you serve?"). Many users are older and not comfortable with tech.
- Every input has a label, and calendar days work with a keyboard and screen reader.

### Commands

All commands load local settings from `.env` (copy `.env.example` first).

- Run locally: `uv run --env-file .env python manage.py runserver` → http://127.0.0.1:8000/
- Run tests: `uv run --env-file .env python manage.py test`
- Apply database migrations: `uv run --env-file .env python manage.py migrate`
- Create admin user (local): `uv run --env-file .env python manage.py createsuperuser`
- Create admin user (Railway): `railway ssh`, then `python manage.py createsuperuser` (or `changepassword <username>` to reset), then `exit`
- Reset local data to a test scenario: `uv run --env-file .env python manage.py seed <scenario>` (`seed --list` shows them). Deletes all members, submissions and closed months first; keeps admin accounts. Refuses unless `DEBUG` is on and the database is local.
- Get the Tailwind CLI (once per machine; `bin/` is git-ignored): `mkdir -p bin && curl -sSL -o bin/tailwindcss https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.3/tailwindcss-macos-arm64 && chmod +x bin/tailwindcss`
- Build the CSS (after changing template classes or `tailwind/input.css`): `bin/tailwindcss -i tailwind/input.css -o heritage_media_availability/static/heritage_media_availability/app.css --minify` (add `--watch` to rebuild on save while developing)
- Make migrations after changing models: `uv run --env-file .env python manage.py makemigrations`
- Create an issue: `gh issue create --template <feature.md|bug.md>` (or `--title`/`--body-file` with `--milestone` and `--label`)
- Open a PR: `gh pr create --fill` then edit, or `--title`/`--body-file`
- Production readiness check: `DEBUG=false uv run --env-file .env python manage.py check --deploy` (should report no issues)

Deploying: pushing/merging to `main` deploys on Railway. `railway.json` (JSON, so it can't hold comments) tells Railway to:
- build with Railpack, which installs exactly what's in `uv.lock` and uses `.python-version`;
- run `python manage.py migrate` before each deploy (a failed migration cancels the deploy, and the old version keeps running);
- start with `migrate --check` (fails the deploy if any migration wasn't applied), then `collectstatic`, then `gunicorn config.wsgi` (gunicorn options live in `gunicorn.conf.py`).
- The pre-deploy command is also set in the Railway dashboard (Settings → Deploy → Pre-deploy Command), because the first deploy didn't pick it up from `railway.json`.
- `railway.json` stops being read on 2026-12-01; the migration is tracked as a Post-launch issue.
