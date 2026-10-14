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

- **Milestones** are the build weeks ("Week 2: Team form", "Week 3: Admin views", "Week 4: Pilot"), then "Pilot and launch" (the pilot rounds and fixes before Oct 25) and "Post-launch". Every issue gets one.
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
- Leave changes uncommitted until I've reviewed them in my editor. When the work is ready, suggest a commit message and wait for my OK (in chat, or by running `/ship` or `/ship-set`) before committing.
- Every PR uses `.github/pull_request_template.md` and includes `Closes #<issue>` for each issue, so merging closes them. For a multi-issue branch, the PR opens once every issue in the set is committed. `/ship` and `/ship-set` open PRs this way (see Conventions).
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
- Creating a release or pushing a tag (see Releases)

Running `/ship` or `/ship-set` is my approval to commit, and `/merge <PR#>` is my approval to merge (#69). Saying it in chat still works. These skills only start when I type them.

### Releases (#53)

Releases name the meaningful points in the app's life, so there's a record of exactly what the pilot used, what launched, and what changed since. They're lightweight on purpose: Railway already deploys every merge, so a release adds a name and notes, not a deploy step.

- **What a release is:** a git tag on a commit that's already on `main`, plus a GitHub Release page. Its notes are written by GitHub from the PRs merged since the previous release (`--generate-notes`), so there's no CHANGELOG file to keep up.
- **When:** at meaningful points only, never for every merge.
  - `v1.0.0-pilot`, a pre-release, when pilot round 1 starts (what the testers used).
  - `v1.0.0` on launch day (Oct 25), on the commit the team first uses.
  - After launch, one release per batch of work, e.g. when a milestone wraps up.
- **Naming:** `vMAJOR.MINOR.PATCH`. A new MINOR (`v1.1.0`) for new features, a PATCH (`v1.0.1`) for a fix-only batch, and a new MAJOR only for a big change in how people use the app. A suffix like `-pilot` marks a pre-release.
- **What it doesn't do:** a release never deploys, and it isn't how to roll back. To undo a bad deploy, redeploy an earlier deployment in the Railway dashboard (or fix forward with a new PR).
- **Comparing:** `git diff v1.0.0-pilot..v1.0.0` shows everything that changed between two releases (run `git fetch --tags` first).
- I suggest when a release is due and draft its title; creating it needs your approval, since it publishes a tag and page on GitHub.

### Conventions we've settled on

Formats and routines for each step of the loop above. Recent issues and PRs (e.g. #9 and PR #19) show them in practice.

- **Plan comments.** Post the approved plan on the issue under a `## Plan (approved)` heading. Put any decisions made while planning first (with the date if they belong in SPEC.md), then the branch name (on a multi-issue branch, followed by a `**Set:** #A, #B, #C` line listing every issue in the set, which `/ship-set` reads), then numbered steps by file, then what's deliberately not included. If the build has to differ from the plan, say so in the handover and the PR.
- **Handing work over for review.** Before asking to commit, give me:
  - what changed, as a short list with a link to each file;
  - the automated test result (count, pass or fail) and that `check --deploy` is clean;
  - numbered manual test steps, saying exactly what to click and what I should see. They start with "0. Run `seed <scenario>`" and refer to the seeded people by name (see Test data below);
  - a suggested commit message.

  Then wait. If testing turns something up, fix it on the same branch, and add a regression test when it's a bug.
- **Test data.** `manage.py seed <scenario>` resets my local database to a known starting state (scenarios live in `heritage_media_availability/seeding.py`). Seed the setup, not the behavior under test: anything a manual step exists to check (submitting, resubmitting, closing or reopening a month, marking someone inactive), I do by hand during the steps, and the steps say so. When an issue needs a different starting state, it adds or updates a scenario in its own PR.
- **Committing and opening the PR.** `/ship` on a single-issue branch, or `/ship-set <issue#>` (`follow-up: <description>` for a further commit) on a multi-issue branch, checks there's a handover and only reviewed files, re-runs the checks, commits (the issue's title, or a short description for a follow-up; `Part of #N.` on a multi-issue branch; the co-author line last), pushes, and opens the PR from the template (`Closes` lines, What changed by file, criteria copied and ticked with the test count, How to test, the checklist with reasons, the issues' milestone and labels). The steps are in `.claude/skills/ship/` and `.claude/skills/ship-set/`.
- **Merging and after.** `/merge <PR#>` waits out GitHub's `UNKNOWN` state, squash merges a single-issue PR (subject `<issue title> (#<PR number>)`) or rebase merges a multi-issue PR, runs the after-merge clean-up (update `main`, check the branch diff is empty, delete the local branch, prune, check the issues closed), and lists what to check on Railway. A conflict is resolved by merging `main` into the branch, never rebasing or force-pushing. The steps are in `.claude/skills/merge/`.
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
- `INSTALLED_APPS` order matters for templates: our app, then `unfold` and `unfold.contrib.filters` (Unfold's list filters, part of the same package), then `django.contrib.admin` (reasons in `config/settings.py`).
- `DATABASE_URL` is parsed with the standard library (`config/env.py`), not dj-database-url. Local `.env` is loaded with `uv run --env-file .env`, not python-dotenv.
- Static files use WhiteNoise's `CompressedStaticFilesStorage` (no filename hashing), so tests don't need `collectstatic` first. Static files are the admin's, Unfold's (CSS, fonts, scripts, all self-hosted), plus our built `app.css` and the icon and link-preview PNGs.
- The app icon and link preview image (#37) are drawn as SVGs in `branding/` (not served) and turned into PNGs in `static/heritage_media_availability/` by `branding/build.sh`, which uses macOS's built-in `sips`. Commit the PNGs with the SVG change. The team pages' Open Graph tags are in `base.html`; `og:image` and `og:url` are built from the request (`templatetags/link_preview.py`), never a hard-coded domain.
- Railway's Hobby plan has no database backups, so Skye's Mac makes them weekly (#3): `backup/install.sh` sets up a `launchd` job that runs `backup/backup.sh` (`pg_dump` inside production's Postgres service via `railway ssh`, so its version matches the server's). Backups live in `~/Backups/heritage-media-availability/`, outside Documents and iCloud (macOS privacy protection can block a background job there), and are never committed (`.gitignore` covers `*.sql*`). Local Postgres is 18, matching production, so practice restores use the everyday local server. Details in README's Backups section.
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
- Members with a standing availability note (e.g. "3rd Sundays only") don't owe a response: until they respond, they show as Standing, aren't counted ("· 2 standing" instead), and sit between responders and non-responders in By person. The app never works out dates from the note.
- Copy output formats must match SPEC.md exactly (by-person and by-date).
- Out of scope for v1. Do not build: notifications, phone login, recurring availability rules, export, time-of-day availability, roles, scheduling.

### Design rules

- Mobile first: design at 375px wide, then scale up.
- Follow Tailwind Plus defaults, with one exception: team pages use `text-base` (16px) at every width, so drop the blocks' `sm:text-sm` and `sm:size-4` (decision 2026-10-12). The blue info boxes are smaller on purpose: a `text-xs` label, a 16px value, and a `text-sm` explanation. Otherwise use its control and button sizes, its gray palette, and its default indigo accent. Contrast meets WCAG AA.
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
- Rebuild the icon and link preview PNGs (after changing an SVG in `branding/`): `sh branding/build.sh`
- Backups (#3): install or update the weekly job with `bash backup/install.sh` (`--uninstall` stops it); check on it with `~/Backups/heritage-media-availability/backup.sh status`; back up now with `~/Backups/heritage-media-availability/backup.sh now`. Practice restore steps are in README's Backups section. Before running anything against production, check with Skye.
- Pilot feedback (#67): in Claude Code, `/pilot-feedback round <1|2> <pasted notes>` turns a tester's notes into draft bug or feature issues, "won't do" items with reasons, duplicates of existing issues, or questions, following PILOT.md. It creates nothing until I approve; "won't do" items reach PILOT.md through their own documentation issue. Only I start it (`disable-model-invocation`). The skill is `.claude/skills/pilot-feedback/SKILL.md`.
- Ship and merge (#69): `/ship` commits, pushes and opens the PR for a single-issue branch; `/ship-set <issue#> [follow-up: <description>]` does the same on a multi-issue branch, opening the set's PR once every issue is committed; `/merge <PR#>` merges (this deploys) and runs the after-merge clean-up. Running each is my approval. Only I start them (`disable-model-invocation`).
- Make migrations after changing models: `uv run --env-file .env python manage.py makemigrations`
- Create an issue: `gh issue create --template <feature.md|bug.md>` (or `--title`/`--body-file` with `--milestone` and `--label`)
- Open a PR: `gh pr create --fill` then edit, or `--title`/`--body-file`
- Production readiness check: `DEBUG=false uv run --env-file .env python manage.py check --deploy` (should report no issues)
- Create the pilot pre-release (on the newest commit on `main`): `gh release create v1.0.0-pilot --prerelease --target main --generate-notes --title "Pilot"`
- Create a release: `gh release create v1.0.0 --target main --generate-notes --title "Launch"` (title it after what it marks)
- List releases: `gh release list`

Deploying: pushing/merging to `main` deploys on Railway. `railway.json` (JSON, so it can't hold comments) tells Railway to:
- build with Railpack, which installs exactly what's in `uv.lock` and uses `.python-version`;
- run `python manage.py migrate` before each deploy (a failed migration cancels the deploy, and the old version keeps running);
- start with `migrate --check` (fails the deploy if any migration wasn't applied), then `collectstatic`, then `gunicorn config.wsgi` (gunicorn options live in `gunicorn.conf.py`).
- The pre-deploy command is also set in the Railway dashboard (Settings → Deploy → Pre-deploy Command), because the first deploy didn't pick it up from `railway.json`.
- Railway checks `/healthz/` on each new deploy and only switches visitors over once it answers `ok`; otherwise the deploy fails and the old version keeps running (#60). It's set in the dashboard (Settings → Deploy → Healthcheck Path) on both production and staging, not in `railway.json`. The `health_check` middleware answers it first in `MIDDLEWARE`, before the HTTPS redirect and host check, because Railway's checker uses plain HTTP and `Host: healthcheck.railway.app`. Don't add that host to `ALLOWED_HOSTS`: staging's `seed` and `load_snapshot` need every allowed host to contain "staging".
- `railway.json` stops being read on 2026-12-01; the migration is tracked as a Post-launch issue.

### Staging (#45)

A second copy of the app on Railway, the `staging` environment, with its own Postgres and address (`https://heritage-media-availability-staging.up.railway.app`). Testers use it so nothing they enter touches real data. The pilot's runbook (rounds, tester steps, Skye's checklist) is [PILOT.md](PILOT.md) (#54).

- It deploys automatically from `main`, like production, so it always runs the live code. There's no staging branch, and PRs still only target `main`.
- Its variables are set in Railway (its own `SECRET_KEY`, `DEBUG=false`, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` for its address, its own `DATABASE_URL`), plus `STAGING=true`, which shows a "Test site" banner on every page and lets `seed` and `load_snapshot` run there.
- Every Railway command for staging names it with `--environment staging`. Without it, the CLI uses the linked environment, which is production.
- Create its admin login: `railway ssh --environment staging`, then `python manage.py createsuperuser`, then `exit`.
- Reset it to a test scenario: `railway ssh --environment staging -- python manage.py seed <scenario> --no-input`
- Refresh it with a copy of production's data (members, submissions, closed months only; not logins or History):
  1. `railway ssh --environment production -- python manage.py dumpdata heritage_media_availability.member heritage_media_availability.submission heritage_media_availability.closedmonth > production-snapshot.json` (read-only; the file is git-ignored)
  2. `railway ssh --environment staging -- python manage.py load_snapshot - --no-input < production-snapshot.json`
  3. `rm production-snapshot.json` (it holds real names and availability)
- `seed` and `load_snapshot` only run where `staging.unsafe_reason()` allows: staging (`STAGING=true` and every `ALLOWED_HOSTS` entry contains "staging") or local development. Never production.
- Not set up (decided 2026-10-11): previewing a branch on staging before merging. A possible future option is `railway up --environment staging`, which uploads the local folder to staging; a long-lived `staging` branch may be reconsidered with a workflow change instead.
