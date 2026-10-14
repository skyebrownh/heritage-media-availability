---
name: ship
description: Commit the reviewed work on a single-issue branch, push it, and open its pull request, after Skye's review. Running /ship is her approval to commit. Use only when Skye types /ship.
disable-model-invocation: true
argument-hint: "(no arguments; works on the current branch)"
---

# Ship a single-issue branch (#69)

Skye typed `/ship`. **That is her approval to commit** the work on the current branch, which she has reviewed in her editor (CLAUDE.md, "Only with my explicit approval"). Then push the branch and open its pull request, which CLAUDE.md lets you do on your own once the commit is approved. **Never merge**: merging deploys, and it needs `/merge` or her OK in chat.

For a multi-issue branch, stop and say to use `/ship-set` instead.

Because the approval arrives as a typed command, possibly in a new session, **check everything first** and stop at the first problem, saying what's wrong and what to do. Don't fix problems silently.

## 1. Check before doing anything

Run `git status` and `git branch --show-current`, then stop if:

- **The branch is `main`.** Work never gets committed to `main`.
- **There's nothing to commit.** Say so; there may be nothing left to ship.
- **The branch name doesn't start with an issue number** (`<N>-<slug>`, e.g. `69-ship-merge-skills`). It may be a multi-issue branch (`/ship-set`), or a branch that doesn't follow the convention.
- **The issue isn't open:** `gh issue view <N> --json title,state,milestone,labels,body,comments`.
- **This conversation has no handover for issue #N** (CLAUDE.md, "Handing work over for review"): what changed, test results, manual test steps, and a suggested commit message. Without one, there's no sign the work was reviewed, so don't commit. Offer to give the handover first, and wait for Skye to review it and run `/ship` again.

## 2. Stage only the reviewed files

Compare `git status --short` with the files listed in the handover's "What changed".

- Stage exactly those, by name (`git add <file> …`). **Never `git add -A` or `git add .`**
- If anything else has changed or is untracked (a stray file, a scratch file, something not in the handover), **stop and ask** whether it belongs in this commit. Don't guess.
- If a file from the handover has changed again since the handover, say so and ask whether Skye has reviewed the newer version.

## 3. Re-run the checks

```sh
uv run --env-file .env python manage.py test
DEBUG=false uv run --env-file .env python manage.py check --deploy
```

Note the test count for the PR. If any test fails or `check --deploy` reports anything, **stop** and report it, without committing.

## 4. Commit

The message is the issue's title, exactly, then a blank line and the co-author line the conversation's attribution instructions give (CLAUDE.md: "The co-author line always ends the message"):

```sh
git commit -F - <<'EOF'
<issue title>

Co-Authored-By: <the co-author line>
EOF
```

Then `git log --oneline -1` and `git status --short`, to show the commit and confirm nothing reviewed was left behind.

## 5. Push

```sh
git push -u origin <branch>
```

## 6. Open the pull request

Write the description to a file in the scratchpad directory, following `.github/pull_request_template.md` and CLAUDE.md's PR-description conventions:

- `Closes #N` on the first line.
- **What changed:** one plain-language sentence on what the PR does and why, then each file with a short note (from the handover).
- **Any difference from the approved plan** (the `## Plan (approved)` comment on the issue), said plainly. CLAUDE.md: "If the build has to differ from the plan, say so in the handover and the PR."
- **Acceptance criteria:** the issue's checklist copied **word for word**, ticked where done. Add the test count to the tests line, e.g. "(238 tests, 3 new)". Leave anything not done unticked, with a short italic reason (e.g. a step that can only happen after merging).
- **How to test:** the handover's numbered steps, starting with step 0.
- **Checklist:** the template's three boxes. Tick what applies; for any that don't, leave it unticked with a reason (e.g. "not applicable, no model changes").
- Keep the template's closing line, "Merging this PR deploys to Railway.", then the PR attribution line the conversation's instructions give.

```sh
gh pr create --title "<issue title>" --body-file <file> --base main \
  --milestone "<issue's milestone>" --label <label> --label <label>
```

Use every label the issue has.

## 7. Check it and hand back

```sh
gh pr view <PR> --json number,url,mergeable,mergeStateStatus
```

`mergeable` can read `UNKNOWN` for a few seconds after creation; check again shortly rather than reporting it as a problem.

Then report, briefly:

- the commit (short ID and title) and the branch pushed;
- the PR link, its milestone and labels, and whether GitHub says it can merge;
- any criterion left unticked, and why;
- that **merging deploys** to production and staging (say so even when the PR doesn't change the running app), and that Skye can run `/merge <PR#>` or say "merge it" to approve.

Then stop. Don't merge.
