# Workflow facts

<!--
Facts about this project that Skye's personal skills (/ship, /merge) read,
so the skills themselves stay the same in every project. Written by
/setup-project; edit by hand any time. Keep each section's heading exactly as
it is: the skills find facts by heading.
-->

## Default branch

`main`

## Checks before committing

<!-- Every command must pass before /ship commits. One per line. -->

```sh
uv run --env-file .env python manage.py test
DEBUG=false uv run --env-file .env python manage.py check --deploy
```

## Pull requests

- Template: `.github/pull_request_template.md`
- Copy the issue's milestone and labels onto the PR: yes

## Merging

- Single-issue PR: squash, subject `<issue title> (#<PR>)`
- Multi-issue PR: rebase
- Merging deploys: yes
- Where it deploys: Railway production and staging, both from `main`

## After a deploy, check

<!-- What Skye looks at once a merge has deployed. /merge lists these; it never checks them itself. Delete the section if nothing deploys. -->

- the new deployment succeeded in both production and staging
- the deploy log shows the health check (`/healthz/`) passing
- if the PR has migrations, the pre-deploy `migrate` step succeeded
- anything the PR's "How to test" says to do after merging

## Releases

<!-- Optional. When /merge should suggest a release (it never creates one). Delete the section if this project doesn't do releases. -->

- on launch day (Oct 25, 2026): `v1.0.0`, on the commit the team first uses
- after launch: when a milestone has no open issues left, a new MINOR version (`v1.1.0`) for features, or a PATCH (`v1.0.1`) for a fix-only batch
