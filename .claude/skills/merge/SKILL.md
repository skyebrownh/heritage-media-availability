---
name: merge
description: Merge an approved pull request into main (which deploys to Railway), then run the after-merge clean-up and say what to check on Railway. Running /merge is Skye's approval to merge. Use only when Skye types /merge.
disable-model-invocation: true
argument-hint: "<PR#>"
---

# Merge a pull request (#69)

Skye typed `/merge $ARGUMENTS`. **That is her approval to merge** that pull request (CLAUDE.md, "Only with my explicit approval"). **Merging deploys** to production and staging, since Railway deploys from `main`.

If no PR number was given, ask for it. Don't guess from the current branch.

Check everything first, and stop at the first problem, saying what's wrong and what to do. **If anything fails before or during the merge, stop and report it before any clean-up.**

## 1. Check the pull request

```sh
gh pr view <PR> --json number,title,state,baseRefName,headRefName,isDraft,mergeable,mergeStateStatus,closingIssuesReferences,body
```

Stop if:

- **It isn't open**, it's a draft, or its base isn't `main`.
- **It closes no issue.** Every PR here has `Closes #N` (CLAUDE.md, "Git workflow"); ask how to proceed.

**Wait out `UNKNOWN`:** just after a push or another merge, GitHub often reports `mergeable` as `UNKNOWN` while it recalculates. Check again every few seconds for up to about a minute. Don't merge while it's `UNKNOWN`.

- **`MERGEABLE`:** carry on.
- **`CONFLICTING`:** stop. Explain which files conflict (`gh pr view <PR> --json files`, or try the merge locally without committing) and how this project resolves it: **merge `main` into the branch**, keeping both sides (e.g. two SPEC.md Decisions entries, kept oldest first), and push normally. **Never rebase or force-push** (CLAUDE.md: "Commits are never rewritten once committed"). That merge commit is a commit, so it needs Skye's approval like any other.
- **Still `UNKNOWN` after a minute,** or a `mergeStateStatus` that blocks merging: stop and report it.

## 2. Merge

Count `closingIssuesReferences`:

- **One issue: a single-issue PR. Squash merge**, with the subject `<issue title> (#<PR number>)` (CLAUDE.md, "Git workflow"):

  ```sh
  gh issue view <N> --json title
  gh pr merge <PR> --squash --subject "<issue title> (#<PR>)"
  ```

- **More than one issue: a multi-issue PR. Rebase merge**, so `main` keeps each commit as it is:

  ```sh
  gh pr merge <PR> --rebase
  ```

If the merge command fails, **stop and report it**. Don't run any of the clean-up.

## 3. Clean up after the merge

Run each step and report its result:

1. Update `main`: `git checkout main && git pull --ff-only`
2. Confirm nothing was left behind: `git diff main <branch>` should be empty. If it isn't, stop and report what differs before deleting anything.
3. Delete the local branch: `git branch -D <branch>`. This is needed because squash and rebase merging both make new commits, so git doesn't see the branch as merged.
4. Prune: `git fetch --prune`. GitHub deletes the remote branch automatically.
5. Check that every issue the PR closes is now closed: `gh issue view <N> --json state`. GitHub's issue *lists* can lag for a few seconds; trust `gh issue view`.
6. Show `git log --oneline -1` (the new commit on `main`).

## 4. Say what to check on Railway

**Don't check the live sites yourself.** Skye checks the deploy, and offering to check is enough. List what she should look at:

- the new deployment succeeded in **both** production and staging;
- the deploy log shows the **health check** (`/healthz/`) passing;
- if the PR has migrations, the pre-deploy `migrate` step succeeded;
- anything the PR's "How to test" says to do **after merging** (e.g. a dashboard setting, a page to open on staging).

If the PR changes nothing in the running app (only docs or skills), say so: the sites should look the same.

## 5. Wrap up

Briefly report: the merge (commit and subject), each clean-up result, and the Railway checklist.

Then mention what's next if it's clear. For example, if this merge leaves the PR's milestone with no open issues, say so (`gh issue list --milestone "<milestone>" --state open`). If that looks like a point CLAUDE.md's Releases section names (e.g. launch day, or a milestone wrapping up after launch), suggest a release and draft its title, but **never create one**: a release needs Skye's separate approval.
