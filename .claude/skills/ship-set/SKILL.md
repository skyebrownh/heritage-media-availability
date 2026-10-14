---
name: ship-set
description: Commit one reviewed issue's work on a multi-issue branch and push it; once every issue in the set is committed, open the set's single pull request. Running /ship-set is Skye's approval to commit. Use only when Skye types /ship-set.
disable-model-invocation: true
argument-hint: "<issue#> [follow-up: <short description>]"
---

# Ship one issue of a multi-issue set (#69)

Skye typed `/ship-set $ARGUMENTS`. **That is her approval to commit** the reviewed work for that issue on the current multi-issue branch (CLAUDE.md, "Git workflow" and "Only with my explicit approval"). Then push. **Open the set's one pull request only when every issue in the set has its commit**; until then, say which are left. **Never merge**: merging deploys, and it needs `/merge` or her OK in chat.

Arguments:

- `/ship-set <N>`: the main commit for issue #N.
- `/ship-set <N> follow-up: <short description>`: a further commit for #N, e.g. a fix to #N found while testing a later issue in the set.

If the arguments don't give an issue number, ask. For a single-issue branch (`<N>-<slug>`), stop and say to use `/ship` instead.

Because the approval arrives as a typed command, possibly in a new session, **check everything first** and stop at the first problem, saying what's wrong and what to do.

## 1. Find the set

Read issue #N and its comments (`gh issue view <N> --json title,state,milestone,labels,body,comments`). Its `## Plan (approved)` comment names the branch and the set:

```
**Branch:** `unfold-admin`
**Set:** #39, #40, #42, #43
```

Stop if:

- **The current branch isn't the one the plan names**, or is `main`.
- **The plan has no `**Set:**` line.** Ask Skye which issues are in the set, and suggest adding the line to the plan comment (CLAUDE.md, "Plan comments").
- **#N isn't in the set**, or isn't open.

## 2. Check the work was reviewed

- **Main commit:** this conversation must have a handover for #N (CLAUDE.md, "Handing work over for review"). If it doesn't, offer to give one first, and wait for Skye to review it and run `/ship-set` again.
- **Follow-up commit:** the conversation must show the change and Skye's review of it (a short handover is enough).
- **Nothing to commit:** say so and stop.
- **A main commit that already exists:** if the branch already has a commit with `Part of #N.` and this isn't marked `follow-up:`, stop and ask whether it should be a follow-up.

## 3. Stage only the reviewed files

Compare `git status --short` with the files in the handover (or the follow-up change). Stage exactly those, by name. **Never `git add -A` or `git add .`** If anything else has changed or is untracked, **stop and ask**.

## 4. Re-run the checks

```sh
uv run --env-file .env python manage.py test
DEBUG=false uv run --env-file .env python manage.py check --deploy
```

If any test fails or `check --deploy` reports anything, **stop** and report it, without committing. Note the test count.

## 5. Commit and push

Rebase merging keeps every commit on `main`, so each one says which issue it's for (CLAUDE.md, "Commit messages"):

- **Title:** the issue's title for the main commit; the short description for a follow-up.
- **Body:** `Part of #N.`, then a blank line and the co-author line the conversation's attribution instructions give.

```sh
git commit -F - <<'EOF'
<title>

Part of #N.

Co-Authored-By: <the co-author line>
EOF
git push -u origin <branch>
```

Show `git log --oneline -1` and `git status --short`.

## 6. Is the set complete?

List the issues with a main commit on the branch:

```sh
git log main..HEAD --format=%B | grep -o 'Part of #[0-9]*'
```

**If any issue in the set has no commit yet:** report this commit, list the issues still to come (in the set's order), and stop. The PR waits.

**If every issue has its commit:** open the one PR (step 7).

## 7. Open the set's pull request

**Title:** a name for the whole set (CLAUDE.md: e.g. "Move the admin to Unfold"). Suggest one from the issues, and ask Skye to confirm it before creating the PR.

Write the description to a file in the scratchpad directory, following `.github/pull_request_template.md` and CLAUDE.md's PR-description conventions:

- A `Closes #N` line for **each** issue in the set, at the top.
- **What changed:** one sentence on what the set does and why it ships together, plus "Rebase merge: each commit lands on `main` as it is." Then one subsection per issue, `### #N <title> (<short commit ID>)`, listing its files with short notes. Follow-up commits go under their issue.
- **Any differences from each issue's approved plan**, said plainly.
- **Acceptance criteria:** each issue's checklist copied **word for word** under its own heading, ticked where done, with the test count on its tests line. Leave anything not done unticked, with a short italic reason.
- **How to test:** each issue's numbered steps, starting with step 0, then **combined steps that check the issues together**. Take each issue's steps from its handover in this conversation. For an issue whose handover isn't here (e.g. committed in an earlier session), draft its steps from its plan and criteria, and mark them "(drafted from the plan; please check)".
- **Checklist:** the template's three boxes, with reasons for any that don't apply.
- Keep "Merging this PR deploys to Railway.", then the PR attribution line the conversation's instructions give.

```sh
gh pr create --title "<set title>" --body-file <file> --base main \
  --milestone "<milestone>" --label <label> …
```

Use the issues' milestone (if they differ, ask which) and every label any of them has.

## 8. Check it and hand back

```sh
gh pr view <PR> --json number,url,mergeable,mergeStateStatus
```

`mergeable` can read `UNKNOWN` for a few seconds; check again shortly.

Report the commits in the set, the PR link, milestone and labels, whether GitHub says it can merge, any criterion left unticked and why, and that **merging deploys**, as a **rebase** merge. Skye can run `/merge <PR#>` or say "merge it". Then stop. Don't merge.
