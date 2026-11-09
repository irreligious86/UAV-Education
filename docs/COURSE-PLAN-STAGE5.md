# Stage 5 plan: people on the platform, deeper practice

Stage 4 (depth, 14 new modules, charts, widgets, link and ROS 2 pass) is done — `COURSE-PLAN-STAGE4.md`.
Stage 5 turns the course from a single-reader site into a platform with accounts, and closes the
practice-depth debt the Stage 4 audit found.

## Iterations

| # | Iteration | Content | Done when |
|---|---|---|---|
| 1 ✅ | Accounts and roles, database | Supabase schema, roles student / admin / single superadmin, RLS, audit, bootstrap — `docs/MULTIUSER-PLAN.md`, `supabase/` | 32 policy tests green in CI on Postgres 16 |
| 2 ✅ | Accounts UI behind a flag | account page, server progress with merge, admin page with grades, CSV and role management | 7 merge tests + 11-step Chromium e2e green in CI; site unchanged with the flag off |
| 3 | Go live | Alex creates the Supabase project and enables the flag (`MULTIUSER-PLAN.md` §8); smoke test with three real accounts (student, admin, superadmin) | registration email arrives, roles behave as the access table says |
| 4 | Server-side grading | Edge Function grades quizzes (answers off the client), signed grader results for labs; admin sees "verified" vs "self-reported" | a student cannot raise their own score from the browser |
| 5 | Cohorts | groups, admin sees own group, deadlines, CSV per group | — |
| 6 ✅ | Practice depth pass — all 41 modules done; fact-check `stage5-practice-depth.md` (7 findings applied); validator enforces 150 words | 41 modules have under 150 words of practice prose (code excluded); add expected outputs, numbers to record and a worked result per step, thinnest first: comp-mavlink, bf-cli-automation, ap-sitl, ops-field, data-python, px4-intro, f-motors-esc, ap-logs, f-components-choice, px4-architecture | every published module ≥ 150 words of practice prose or a justified exception |
| 7 | SITL in CI | postponed by Alex (runs SITL locally); revisit after iteration 6 | — |

Done outside the table on 2026-11-09: comp-raspberry and per-tracking deepened (the last two thin modules
from the Stage 4 audit), PIDtoolbox replaced by PIDscope, tracks ordered by prerequisites with a validator rule.
