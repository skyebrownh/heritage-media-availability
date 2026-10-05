# Heritage Media Availability Form — Spec

Sep 26, 2026 · @Skye Brown

## Overview

The Heritage Media Availability Form is a mobile-friendly web form where Heritage media team members submit the days they're unavailable each month, and Skye sees every response in one place. It replaces the monthly group-chat text and the manual copy into the Google Doc scheduling template.

**Today:** Near the end of each month, Skye texts the group chat asking for next month's unavailable dates. Replies arrive scattered across the thread and get retyped by hand into the template.

**Goal:** Collect availability in one structured place, show who has and hasn't responded, and produce text that pastes straight into the template.

**Success for v1:** Team members can submit the form and Skye can view the responses. Getting about 90% of availability through the form instead of texts counts as a win; last-minute changes after a month closes can still come by text.

## Users and roles

Two roles: team members submit, and Skye collects. The team side needs no login, so it stays as simple as possible for less tech-comfortable volunteers.

| Role        | Who                                                                              | How they get in                                   | What they can do                                                                                      |
| ----------- | -------------------------------------------------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Team member | Fewer than 20 media volunteers, mostly on phones, many not comfortable with tech | One shared link; picks their name from a dropdown | Submit or resubmit unavailable days for any open month, up to 6 months ahead                          |
| Admin       | Skye only                                                                        | Password-protected admin page                     | Manage the roster, track responses, view by date and by person, copy results, close and reopen months |

## Scope

v1 covers collecting and viewing whole-day availability. Anything that assigns people to serve is out of scope.

### In v1

- One shareable link, mobile-first design
- Name dropdown of active roster members
- Month picker covering the current month through 6 months ahead; one submission covers one person and one month
- Tap-to-select calendar of every day in the month
- "Available all month" and "Unavailable all month" options
- Optional notes field
- Resubmission, where the latest submission wins
- Admin: password login, simple roster (name + active), response tracker, by-date and by-person views with copy buttons, close and reopen months

### Later

- Phone-number login
- Notifications and reminders, including alerts to Skye about changes
- Recurring availability rules (e.g. only 3rd Sundays, never weekday nights)
- Advanced reporting and export
- Time-of-day or service-level availability
- Fitting into the larger volunteer scheduling app

### Non-goals

- Scheduling. The app only collects and displays availability; it never assigns people to dates.
- Roles or positions on the roster. Those belong to the scheduling side.

## Functional requirements

IDs let you reference each requirement when prompting an AI coding tool or testing the pilot. Build status for each requirement lives in GitHub Issues, not here.

### Team form

| ID | Requirement |
| --- | --- |
| TF-1 | The form lives at one public link with no account or password. |
| TF-2 | The user picks their name from a dropdown of active roster members, shown as "First Last" and sorted A–Z by first name (then last name). |
| TF-3 | The user picks a month from the current month through 6 months ahead. No month is preselected, so the user always picks one deliberately. Closed months show a "(closed)" label. Past months are never offered, even if reopened. |
| TF-4 | Picking a closed month hides the form and shows: "This month's schedule is finalized. Please text Skye with any changes." with a hint underneath: "You can choose a different month above." |
| TF-5 | An open month shows a calendar of every day in that month. Tapping a day toggles it unavailable; tap targets are at least 44 px. |
| TF-6 | Above the calendar, a dropdown offers "Pick specific days" (default), "I'm available all month", and "I'm unavailable all month". Choosing either all-month option clears and disables the calendar; switching back to "Pick specific days" re-enables it. |
| TF-7 | An optional notes field accepts up to 500 characters. |
| TF-8 | Submit requires a name, a month, and either at least one day or an all-month option. Missing pieces get a plain-language message. |
| TF-9 | If the person already submitted for that month, the form pre-fills with it: the calendar days (or all-month choice) and notes start from the earlier submission, so they only change what's different. A read-only summary of that earlier submission stays visible above the calendar as a reference while they edit, e.g. "Your last submission (10/02/26): Oct 3-7, 20. Submitting again replaces it." For all-month choices it reads "available all month" or "unavailable all month". |
| TF-10 | After submitting, a confirmation restates what was saved, greeting by first name, with a button to fill out another month. Days name the month once, then list ranges: "Thanks, Bob! You're unavailable Oct 3-7, and 20." (one range: "Oct 3-7"; three or more: "Oct 3-7, 10, and 20"). All-month choices read "Thanks, Bob! You're available all of November." and "Thanks, Bob! You're unavailable all of November." |
| TF-11 | Nice-to-have: the device remembers the last name selected so returning users skip the dropdown. |

### Admin

| ID | Requirement |
| --- | --- |
| AD-1 | The admin area sits at a separate path behind Django's admin login (one superuser account, Skye). The login lasts about 30 days per device. |
| AD-2 | Roster: add a person (first and last name, both required), edit their name, toggle active or inactive. The first + last name pair is unique regardless of capitalization. Inactive people leave the dropdown and tracker, but their past submissions stay. No hard delete in v1. |
| AD-3 | A month selector covers past months (read-only reference) through 6 months ahead. Past months are offered if they have any submission or were ever closed. The dashboard opens on next month, the one usually being collected. |
| AD-4 | The response tracker lists every active member as Responded or Not responded, with the last-submitted time and a count like "12 of 17 responded." Members added to the roster after a month ended aren't listed for it, unless they submitted for it. Inactive members who submitted for the month appear in a separate "No longer active" section at the bottom, by full name, with their answer and notes; they're left out of the count and all copy text. |
| AD-5 | The by-person view lists each member's unavailable days in compact ranges, any all-month choice, and their notes (on a line under the answer). It uses the same order as the by-person copy text: responders A–Z, then non-responders A–Z. |
| AD-6 | The by-date view lists each day of the month that has anyone unavailable, with who's out. Days with nobody out are skipped, matching the copy text below. People marked "unavailable all month" are not repeated on each day; they're listed once in a note at the top of the view. |
| AD-7 | The by-person and by-date views each have a copy button that copies their text format below to the clipboard. |
| AD-8 | Close month and Reopen month happen in Django admin, for any month including past ones. Closing asks for confirmation. Nothing closes automatically; Skye closes months by hand. |

### Names in admin views and copy output

The tracker, by-person and by-date views, and both copy formats show each person's **display name**: their first name only, plus their last initial when another active member listed for that month shares that first name (ignoring capitalization), e.g. "Bob J." and "Bob S.". If two of them also share a last initial (Bob Jones and Bob Johnson), those two show their full last name instead. Lists are sorted A–Z by first name, then last name. The "No longer active" section uses full names ("Bob Smith"), since it's never part of copy text.

### Copy formats

**By person:** one line per active member, by display name. Responders come first, A–Z by first name, then non-responders, also A–Z by first name. Consecutive days collapse into ranges, and "NA" means available all month.

```
Bob: 3-7, 20
Emily: 13
Jane: 1, 4, 10-11, 27-31
Jim: NA
Sam: unavailable all month
Tom: no response
```

**By date:** one line per day that has anyone out, in date order with display names A–Z by first name. Days with nobody out are skipped. People unavailable all month appear once on the first line instead of on every day. The start of the output for the same responses:

```
Unavailable all month: Sam
1: Jane
3: Bob
4: Bob, Jane
5: Bob
```

## Key user flows

### Team member submits

![Team Member Workflow](./team_member_workflow.png)

A closed month stops the flow with a text-Skye message. On an open month, choosing "available all month" or "unavailable all month" replaces tapping days, and any earlier submission for that month is pre-filled.

### Skye's monthly cycle

1. Before building a schedule, open that month's tracker and see who hasn't responded.
2. Text anyone missing directly, since v1 has no notifications.
3. Tap Copy on the by-person and by-date views and paste each into the Google Doc template.
4. Finalize the schedule, then close the month. Changes after that come by text.
5. If a month was closed by mistake, reopen it.

Roster upkeep happens as needed: add new volunteers and mark people inactive when they step away.

## Business rules

These rules must hold on the server, not just in the form, so a stale browser tab can't break them.

- **One current submission per person per month.** A new submission replaces the old one everywhere Skye looks. Every earlier version stays in the database with its timestamp, for checking "I know I marked the 14th."
- **Months are open by default.** There's no step to open a month. The team can submit for the current month through 6 months ahead.
- **Closing locks a month completely.** The server rejects submissions for a closed month, even from a form that was already open. Reopening restores normal submissions. A closed month is the only reason the server rejects a month. Past months should normally be closed, but Skye does that by hand, which leaves room for exceptions.
- **All-month options are exclusive.** A submission is exactly one of: specific days, available all month, or unavailable all month.
- **Any submission counts as a response.** That includes "available all month."
- **Whole days only.** Dates are calendar days with no times, and month boundaries use Eastern time.
- **Identity is trusted.** Anyone with the link could pick any name. That's acceptable in v1 because the data is only names and dates, and the stored history makes mistakes easy to spot.
- **Inactive people are hidden, not deleted.** They leave the dropdown, tracker, and copy output, but their history stays.

## Data model

Three tables cover v1. Keeping every submission, and reading the newest per person and month, gives "last submission wins" plus history for free.

### members

| Field        | Type      | Notes                                                                                   |
| ------------ | --------- | --------------------------------------------------------------------------------------- |
| id           | integer   | Primary key                                                                             |
| first\_name  | text      | Required                                                                                |
| last\_name   | text      | Required. The (first\_name, last\_name) pair is unique regardless of capitalization ("bob smith" = "Bob Smith") |
| is\_active   | boolean   | Default true                                                                            |
| created\_at  | timestamp |                                                                                         |

### submissions

| Field          | Type                                   | Notes                                                          |
| -------------- | -------------------------------------- | -------------------------------------------------------------- |
| id             | integer                                | Primary key                                                    |
| member\_id     | integer                                | Links to members                                               |
| month          | text, YYYY-MM                          | e.g. 2026-11                                                   |
| kind           | text                                   | `days`, `available_all`, or `unavailable_all`                  |
| days           | list of integers (Postgres `ArrayField`) | Day numbers, e.g. `[3, 4, 5, 20]`; empty unless kind is `days` |
| notes          | text                                   | Optional, up to 500 characters                                 |
| submitted\_at  | timestamp                              | The newest per member and month is the current one             |

### closed\_months

| Field       | Type          | Notes                                             |
| ----------- | ------------- | ------------------------------------------------- |
| month       | text, YYYY-MM | Primary key; a row here means the month is closed |
| closed\_at  | timestamp     |                                                   |

Reopening a month deletes its row. The admin login is a Django superuser account (Skye), stored in Django's built-in user table with a hashed password.

The model leaves room for later ideas without rework. Phone login adds a phone column to members, and recurring rules would be a new table linked to members.

## Non-functional requirements

The bar is "easy on an older volunteer's phone," cheap to run, and safe enough for names and dates.

- **Mobile first.** Design at 375 px wide first, and test on iPhone Safari and Android Chrome. Base text is at least 16 px, with high contrast and tap targets of at least 44 px.
- **Plain language.** Labels read like a person talking ("Which days can't you serve?"), with no jargon and one decision per screen section.
- **Accessible.** Every input has a label, and calendar days work with a keyboard and screen reader.
- **Look and feel.** Clean cards, generous white space, and a soft pastel blue accent on an otherwise neutral palette, in the spirit of Airtable and Zapier forms.
- **Fast.** Pages load in under 2 seconds on mobile data, and the form never "wakes up" slowly after sitting idle.
- **Secure enough.** HTTPS everywhere, the admin password stored hashed by Django (never in code), and input validated on the server.
- **Cost.** $10 a month or less, ideally near $0.
- **Backups.** The database is backed up at least weekly, by the host or a simple export.

## Technical approach

Recommendation: one Django app with server-rendered pages and Postgres, hosted on Railway's Hobby plan for about $5 a month. It's one codebase, one deploy, and no separate frontend, which keeps the project small enough to finish in a month.

| Layer             | Choice                            | Why                                                                                                                             |
| ----------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Backend           | Django (Python)                   | The built-in admin handles the roster and closed months with almost no code, and built-in login protects the admin pages        |
| Pages | Django templates + Tailwind (CDN now; pre-built CSS before launch) | Server-rendered HTML is fast on phones and simple to vibe-code; pre-built CSS avoids building styles on every phone |
| Calendar and copy | Small vanilla JS, or Alpine.js    | Day toggles and the clipboard copy don't need a framework                                                                       |
| Database          | Postgres on Railway               | Managed, backed up, one click to add                                                                                            |
| Hosting           | Railway Hobby                     | $5/month including $5 of usage, which a 20-person form won't exceed ([Railway pricing](https://docs.railway.com/pricing/plans)) |

Django's admin login uses a username and password rather than a bare password, which still meets AD-1. Skye's dashboard views (tracker, by-date, by-person, copy) are custom pages behind that same login.

**All-JavaScript alternative:** Next.js on Vercel with a hosted Postgres free tier. It can run near $0, but you'd build the admin login, roster screens, and month controls yourself.

**Avoid** free hosting tiers that sleep when idle. A volunteer opening the link once a month would wait through a slow wake-up and may assume it's broken.

## Timeline, pilot, and open questions

The form launches October 25, the day November availability requests normally go out.

Three build weeks and a pilot week before launch (2026):

| Week | Dates | Focus |
| --- | --- | --- |
| 1 | Sep 28 – Oct 4 | Setup, roster, deploy |
| 2 | Oct 5 – Oct 11 | Build the team form |
| 3 | Oct 12 – Oct 18 | Build admin views |
| 4 | Oct 19 – Oct 24 | Pilot with 3–5 people |
| Launch | Oct 25 | Launch to full team |

Week 1 gets a bare app deployed early, so hosting surprises show up before the real features exist. Each later week ends with something usable.

### Pilot plan

1. Pick 3–5 people, including at least one of the least tech-comfortable volunteers. Watch one of them use it in person if you can.
2. Have each person submit for November and one later month, then resubmit once.
3. Check that everyone finished without help, the all-month options made sense, and the copy output pasted cleanly into the Google Doc.
4. Fix what comes up, then share the link with the full team in the group chat.

### Open questions

None for v1. Copy labels, non-responders, the by-date copy button, the launch date, the app name, and the accent color are settled in the sections above.

## Decisions

Spec decisions that aren't captured in a requirement above, with the date they were made. Decisions that change a requirement are made by editing that requirement directly.

- 2026-09-28: TF-9 pre-fill loads the earlier submission with a small JavaScript fetch, so picking a name and month doesn't reload the page.
- 2026-10-01: If someone is marked inactive while their form is open, their submission is still accepted. The name dropdown shows active members only, but the server accepts any member on the roster.
- 2026-10-03: The app only stores whether someone is active *now*, so a past month can't know who was active then. Rather than add a table tracking when people became inactive (only works going forward), the dashboard lists today's active members minus anyone added after the month ended, plus a "No longer active" section for inactive members who responded to that month (AD-4). Accepted gap: an inactive member who didn't respond to a past month isn't shown as "Not responded".
