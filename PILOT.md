# Pilot testing plan (#54)

How the app is tried out before it launches to the whole media team on **October 25**, when November's availability requests normally go out. SPEC.md's "Pilot plan" has the summary; this file is the runbook.

## The approach

Two rounds, both on the **staging site**, a practice copy of the app with its own database and a yellow "Test site" banner:

**https://heritage-media-availability-staging.up.railway.app**

| Round | Who | Goal |
|---|---|---|
| 1 | One younger, tech-comfortable member | Find bugs and confusing spots before anyone else sees the app |
| 2 | The media team lead | Decide together whether this is how the team collects availability going forward |

Only two rounds, on purpose. Real volunteers never have to fill the form out on staging and then again on production, which would be confusing. After launch, problems found on production become new issues (decision 2026-10-13).

Staging holds a copy of production's roster, so testers find their own names. October is already closed there (as on production), so testers start with **November**. Picking October shows the "schedule is finalized" message, which is expected.

## Round 1: a tech-comfortable member

About 10–15 minutes, on their **phone**.

**What they do:**

1. Pick their name and **November**. Tap a few days they can't serve, add a short note, and submit.
2. Open the link again. Their answers should already be filled in. Change one day and submit again.
3. Pick **December**, choose "I'm unavailable all month", then switch to "I'm available all month", and submit.
4. Try to break it: submit with something missing, pick October (closed), or anything else they're curious about.

**What to ask afterwards:**

- Was anything confusing, or a moment where you had to stop and think?
- Did anything look broken or off?
- About how long did it take, and was it easier than replying in the group chat?
- Anything you expected that wasn't there?

## Round 2: the lead

Two parts.

1. **As a team member:** he fills out the form on his phone for November, then comes back and changes something (round 1's steps 1–2).
2. **Skye's side, as a walkthrough:** Skye shows him the dashboard (who has responded, By person, By date), the copy buttons pasting into the Google Doc template, and closing and reopening a month. He doesn't need an admin login; Skye drives.

**What to ask him:**

- Would this work as our way of collecting availability each month?
- Anything you'd want it to do that it doesn't?
- Any concerns about using it with the whole team?

## Skye's checklist

### Before round 1

- [ ] #53 is merged, and the `v1.0.0-pilot` pre-release is created on what's live (CLAUDE.md, Releases).
- [ ] Staging is refreshed from production (CLAUDE.md, Staging). Refresh again if the roster has changed since.
- [ ] Smoke test: open the staging link on a phone and submit once. Then refresh staging so that answer is gone.
- [ ] Send the round 1 email.

### During round 1

- [ ] If possible, sit with them for part of it. Note anywhere they pause, hesitate, or ask a question.

### After round 1

- [ ] Each piece of feedback becomes an issue on the "Pilot and launch" milestone (bug or feature), or is noted as "won't do" with a reason.
- [ ] Fix anything you wouldn't want the lead to see before round 2.
- [ ] Don't refresh staging between rounds. The tester's answers make the dashboard walkthrough look like a real month.

### Round 2

- [ ] Send the round 2 email, and set up the walkthrough.
- [ ] Note his answers to the three questions. Anything he asks for becomes an issue (on "Pilot and launch" if it's needed before launch, otherwise "Post-launch").

### Launch day (October 25)

- [ ] Every "Pilot and launch" issue that must be fixed before launch is closed.
- [ ] Production's roster is current: names, active or inactive, and standing notes.
- [ ] Months you don't want answers for are closed on production.
- [ ] Create the `v1.0.0` release (CLAUDE.md, Releases).
- [ ] Post the **production** link in the group chat with a short "how to" message, and check that its preview card shows.
- [ ] From then on, problems found on production become new issues.
