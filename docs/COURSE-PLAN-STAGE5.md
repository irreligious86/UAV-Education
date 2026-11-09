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
| 4 | Server-side grading → exams with private banks | the repository is public, so module quizzes can never hide their answers; real grading needs question banks that live only in the database: admins upload exam banks, students get questions without answers, the database grades and records the result (see iteration 9) | a student cannot read answers or write their own exam score |
| 5 | Cohorts | groups, admin sees own group, deadlines, CSV per group | — |
| 6 ✅ | Practice depth pass — all 41 modules done; fact-check `stage5-practice-depth.md` (7 findings applied); validator enforces 150 words | 41 modules have under 150 words of practice prose (code excluded); add expected outputs, numbers to record and a worked result per step, thinnest first: comp-mavlink, bf-cli-automation, ap-sitl, ops-field, data-python, px4-intro, f-motors-esc, ap-logs, f-components-choice, px4-architecture | every published module ≥ 150 words of practice prose or a justified exception |
| 7 | SITL in CI | postponed by Alex (runs SITL locally); revisit after iteration 6 | — |

Done outside the table on 2026-11-09: comp-raspberry and per-tracking deepened (the last two thin modules
from the Stage 4 audit), PIDtoolbox replaced by PIDscope, tracks ordered by prerequisites with a validator rule.

## Continuation plan (2026-11-09 audit)

Open items found: go-live (needs Alex), SITL in CI (postponed by Alex), 52 module quizzes below the
8-question standard, 82 modules without numeric tasks (about 20 of them are quantitative and should have
them), glossary (116 terms) missing the Stage 4–5 vocabulary, the Jazzy Docker image never built, no
real server-side grading, no cohorts.

| # | Iteration | Content | Done when |
|---|---|---|---|
| 8 | Build the ROS 2 image in CI | workflow builds `examples/ros2-docker` ros image (Jazzy default, Humble fallback) on changes and on demand — Docker Hub is reachable from GitHub Actions | image builds green for both distros |
| 9 | Exams with private banks | tables for exams, questions (answers only in the DB), attempts; RPCs `exam_start` (questions without answers), `exam_submit` (graded in the database, one attempt per window); admin page uploads banks and sees results; student exam page; RLS tests, e2e with the fake backend, security review | 0 ways to read answers or write a score from the browser in tests |
| 10 | Numeric tasks for quantitative modules | task banks (`content/tasks/`) for the Stage 4 modules and other modules with formulas (weather, guidance, sysid, KiCad, telemetry, plane tuning, ESC, multi-vehicle, maintenance, DroneCAN, attitude, altitude, measurement…) | every module with a worked formula has a task bank |
| 11 | Quizzes to 8 questions | 52 banks below 8; same bias rule (correct answer longest in ≤ 34 %) | all banks ≥ 8 |
| 12 | Glossary | terms introduced by Stage 4–5 modules, each linked to its module | new terms searchable on the glossary page |
| 13 | Cohorts | groups created by admins, students added to groups, filter and CSV per group on the admin page; access matrix unchanged | admin page filters by group, RLS tests extended |
| 14 | Verification | independent fact-check of 10–12, security review of 9 and 13, CI green, report | findings applied |
