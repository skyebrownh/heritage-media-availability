---
name: pilot-feedback
description: Turn a pilot tester's feedback into draft GitHub issues (bug or feature), "won't do" items with reasons, or questions for Skye, following PILOT.md. Creates nothing until Skye approves. Only for the pilot, before launch on October 25, 2026.
disable-model-invocation: true
argument-hint: "[round 1|2] <pasted feedback notes>"
---

# Pilot feedback → draft issues (#67)

Skye ran this with notes from a pilot tester:

$ARGUMENTS

Turn every piece of that feedback into exactly one outcome (a draft issue, a "won't do", a duplicate, or a question), show them all together, and **create nothing until Skye approves**. Then create only what she approved.

## Ground rules

- **Never create, edit, comment on or close anything before Skye approves.** Reading issues and files is fine.
- **Never plan or build a fix.** Each approved issue goes through the normal workflow later (CLAUDE.md, "How we work").
- **Never name the tester** in issue titles, bodies or PILOT.md. Write "the round 1 tester" or "the lead (round 2)".
- **Never edit PILOT.md yourself.** "Won't do" items are recorded through their own documentation issue (step 8).
- **Only for the pilot.** If the feedback is about production after launch (October 25, 2026), say that it should be a normal bug issue (`.github/ISSUE_TEMPLATE/bug.md`) and stop.
- If anything in the notes is unclear, ask. Don't guess what the tester meant (CLAUDE.md: "If the spec is unclear… ask me").

## Steps

### 1. Read the sources

Read these before deciding anything:

- `PILOT.md`: the rounds, and the milestone rules in "After round 1" and "Round 2".
- `SPEC.md`: the requirements (TF-#, AD-#), **Scope → Later** and **Non-goals** (out of scope for v1), Business rules, and **Decisions**.
- `CLAUDE.md`: the out-of-scope list under "Business rules", and the issue, milestone and label conventions.
- `.github/ISSUE_TEMPLATE/bug.md` and `feature.md`: every draft follows one of these exactly.

### 2. Confirm the round

Use the round from the arguments ("round 1" or "round 2"). If none was given, **ask before going further**, because the round decides the milestone.

### 3. Split the notes into items

Break the notes into separate pieces of feedback, one idea each. Number them and restate each in one plain line, so Skye can see how it was understood. Skip pure praise or chit-chat, but mention that you skipped it ("Also said the form was quick; nothing to do").

### 4. Check for duplicates

For each item, search **open and closed** issues before drafting:

```sh
gh issue list --state all --limit 300 --json number,title,state,milestone
gh issue list --state all --search "<a few key words>" --json number,title,state
gh issue view <N> --json title,body,state,comments
```

If an item matches an existing issue, say "matches #N (open/closed)" instead of drafting a new one, and suggest what to do: a comment on the open issue, or a new issue that links to the closed one if the problem came back.

Also check whether it was **already decided**: SPEC.md's Decisions, and closed issues' discussions (design decisions are mostly on #14). Examples: By date stays a list, not a calendar grid; field and choice-card borders stay Tailwind Plus's gray-300, unless a tester actually struggled to see them.

### 5. Classify each item

Give each item exactly one outcome:

| Outcome | When |
| --- | --- |
| **Bug** | The app doesn't do what SPEC.md says (cite the requirement, e.g. TF-8), or something is broken. |
| **Feature** | A change or addition to what the app does, or a wording or design change. |
| **Won't do** | It's out of scope for v1, already decided, or not worth doing, with a one-sentence reason. |
| **Question** | You can't tell what the tester meant, or what Skye would want. Ask her a specific question. |

**Out of scope for v1:** if an item is on SPEC.md's **Later** or **Non-goals** list (or CLAUDE.md's "Out of scope for v1": notifications, phone login, recurring availability rules, export, time-of-day availability, roles, scheduling), quote the spec line and offer both options: **"won't do"**, or a **Post-launch feature issue**. Let Skye pick.

### 6. Choose milestones and labels

Milestones (PILOT.md):

- **Round 1:** every issue goes on **"Pilot and launch"**.
- **Round 2:** **"Pilot and launch"** only if it must be fixed before launch, otherwise **"Post-launch"**. Say which you chose and why.

Labels: one type label (`bug` or `feature`, plus `accessibility` if it's about access) and one area label (`team-form`, `admin`, `infra` or `documentation`).

### 7. Show every draft together, then wait

Post one message with all the items, in order:

- **Bugs and features:** the full draft: title, milestone, labels, and the body filled in from the template (every heading kept). For a bug, "Where" is the staging site plus the tester's device and browser, if known. The feature template's "Delivers" names the requirement IDs it changes, or says "None".
- **Won't do:** the feedback in one line, and the reason.
- **Duplicates:** which issue it matches, and the suggested comment or link.
- **Questions:** the question for Skye.
- **If there are any "won't do" items:** also draft the documentation issue from step 8, so it's approved together with the rest.

End with a short summary (e.g. "3 issues, 2 won't do, 1 question") and **stop**. Skye may approve all, some, or edit them. Treat anything she doesn't mention as not approved, and ask.

### 8. The "won't do" documentation issue

Approved "won't do" items are recorded in PILOT.md's **"Pilot feedback: won't do"** section by **one documentation issue per round**, which goes through the normal workflow (plan, branch, PR). Draft it with the feature template:

- **Title:** `Record round N's pilot won't-do decisions in PILOT.md`
- **Milestone:** "Pilot and launch". **Labels:** `feature`, `documentation`.
- **Directive:** add round N's "won't do" items to PILOT.md's "Pilot feedback: won't do" table.
- **Delivers:** None (documentation)
- **Acceptance criteria:** one checkbox per item, giving the row to add (Round · Feedback · Reason · Date). Leave out "Automated tests cover the new behavior" (it's documentation only), and keep "Automated tests pass".
- **Out of scope:** any change to the app.

If an issue like this is already open for the same round (from an earlier run), suggest adding the new items to it with a comment instead of opening another.

### 9. Create what was approved

Only after Skye approves:

- Write each body to a file in the scratchpad directory, then:
  `gh issue create --title "<title>" --body-file <file> --milestone "<milestone>" --label <type> --label <area>`
- Create only the approved drafts, with any edits she asked for.
- Post any approved comments on existing issues (`gh issue comment <N> --body-file <file>`).

Then reply with a list of what was created (links), what's recorded as "won't do" (through which issue), and anything still waiting on an answer. For **round 1**, point out which new issues PILOT.md says to fix before round 2 ("Fix anything you wouldn't want the lead to see"), and suggest an order. Don't start planning them.
