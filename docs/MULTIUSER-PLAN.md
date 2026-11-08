# Multi-user system: accounts, roles, progress on a server

Status: phases 1–2 implemented behind a feature flag (2026-11-09). The site keeps working exactly as
before until a backend is configured in `assets/backend-config.js`.

## 1. Requirements (from Alex)

- A person registers with **email, username (login) and password**.
- Their grades (quizzes, numeric tasks, labs, completed modules) are visible **to them and to the
  administration**, nobody else.
- Roles: **student**, **admin**, **superadmin**. There is exactly **one** superadmin.
- Different access per role.

## 2. Backend choice

The site is static (GitHub Pages) and offline-first. A multi-user system needs a server that owns
identities and enforces access. Options considered:

| Option | Auth | Access control | Cost / ops | Verdict |
|---|---|---|---|---|
| **Supabase** (hosted Postgres + Auth) | email + password, email confirmation, password reset built in | Postgres Row Level Security — enforced in the database, not in the browser | free tier fits a course; no server to run | **chosen** |
| Firebase | built in | Firestore rules (own language) | free tier; vendor lock-in, no SQL for admin reports | no |
| Own server (FastAPI/Node + Postgres on a VPS or Alex's Raspberry Pi) | write it ourselves | write it ourselves | a machine online 24/7, backups, TLS, patching | later, if ever |
| PocketBase (single binary) | built in | rules per collection | still needs a host | fallback if leaving Supabase |

Why Supabase: the security model lives in SQL (`supabase/migrations/`) that we test in CI against a
real Postgres; the browser only gets the public *anon* key, which is safe to publish because every
table is protected by RLS. Moving to self-hosted Supabase or plain Postgres later keeps the same SQL.

## 3. Roles and access

| Action | student | admin | superadmin |
|---|---|---|---|
| Register, log in, reset password | ✓ | ✓ | ✓ |
| Read / write **own** progress | ✓ | ✓ | ✓ |
| Read own profile, change own username | ✓ | ✓ | ✓ |
| Read **all** profiles and progress (grades table) | — | ✓ | ✓ |
| Change anyone's progress | — | — | — |
| Make a user admin / back to student | — | — | ✓ |
| Change the superadmin's role, create a second superadmin | — | — | — (impossible by design) |
| See the role-change audit log | — | ✓ | ✓ |

Rules enforced in the database:
- `profiles.role` cannot be changed by an UPDATE from the browser (column privileges); only
  `set_role()` changes it, and only when the caller is the superadmin.
- A unique partial index allows at most one row with `role = 'superadmin'`.
- `set_role()` refuses to touch the superadmin row and refuses to grant `superadmin`.
- The first superadmin is assigned once from the Supabase SQL editor with
  `bootstrap_superadmin(email, username)`, which the browser roles cannot execute. It accepts only a
  *confirmed* email whose account has exactly that username, drops sessions issued before the promotion,
  and refuses to run once a superadmin exists.
- `progress.data` must have the shape the pages expect (arrays of strings, objects of objects), so one
  malformed row cannot break the admin table; `updated_at` is set by the server on insert and update.
- Unconfirmed sign-ups do not appear in the admin view.
- Progress rows are writable only by their owner; admins read them, nobody else.

## 4. Data model

```
auth.users (Supabase)            1 ── 1  profiles(id, username, email, role, created_at)
                                         │
                                         1 ── 1  progress(user_id, data jsonb, updated_at)
role_audit(id, actor, target, old_role, new_role, at)
view student_progress (security_invoker): profiles ⋈ progress — RLS of both tables applies
```

`progress.data` has the same shape as the browser store (`done`, `checks`, `quiz`, `tasks`, `labs`), so the
existing pages keep their interface (`window.UAVProgress`).

## 5. Sync rules (browser ↔ server)

- Logged out: `LocalProgressStore` as today.
- Logged in: `ServerProgressStore` keeps a local copy for offline use and pushes the merged document.
- First login on a device merges local and server progress: union of done modules, checks, solved tasks
  and imported lab results; best quiz result per module. Nothing is lost when a student who studied
  anonymously creates an account.

## 6. Honest limitation: grades are self-reported

Quizzes and numeric tasks are graded in the browser, and their answers ship with the page. A determined
student can write any score into their own progress row. That is fine for self-study and fine for an
admin who wants to see who is working; it is **not** an exam. Phase 3 moves grading for scored work to a
server function (answers stay on the server, the function writes the score), and lab results already
carry the grader's JSON (`uav-lab-result/1`) that a server can re-verify.

## 7. Phases

| # | Phase | Done when |
|---|---|---|
| 1 ✅ | Schema, roles, RLS, superadmin rules — `supabase/migrations/`, tests in CI against Postgres 16 | policy tests pass for every cell of the access table |
| 2 ✅ | Account page (register/login/logout/reset), server progress store with merge, admin page (grades table, per-student detail), superadmin role management — behind the feature flag | Playwright tests with a fake backend pass; site unchanged with the flag off |
| 3 | Server-side grading of quizzes (Edge Function), lab result verification | scored work cannot be written from the browser |
| 4 | Groups/cohorts (admin sees own group), CSV export, deadlines | — |

## 8. Going live (what Alex does, ~20 minutes)

Order matters: the superadmin is created **before** the anon key is published, so nobody can race the
owner's registration (the database also refuses unconfirmed or mismatched accounts).

1. Create a project at supabase.com (free tier), region close to students.
2. SQL editor → run `supabase/migrations/0001_accounts_roles_progress.sql`.
3. Authentication → Providers → Email: keep "Confirm email" on; minimum password length ≥ 10.
   Authentication → Emails → SMTP: set a custom SMTP sender — the built-in sender only delivers to the
   project team and is heavily rate-limited, students would never get the confirmation mail.
4. Authentication → URL configuration: Site URL `https://irreligious86.github.io/UAV-Education/`;
   Redirect URLs exactly `https://irreligious86.github.io/UAV-Education/pages/account.html` and, for
   step 5 only, `http://localhost:8765/pages/account.html` (no wildcards).
5. Locally, **without committing**: put the Project URL and the **anon** key into
   `assets/backend-config.js` with `enabled: true`, run `python3 -m http.server 8765`, open
   `http://localhost:8765/pages/account.html`, register with `irreligious86@gmail.com` and your username,
   confirm the email, log in and check the username shown.
6. SQL editor → `select public.bootstrap_superadmin('irreligious86@gmail.com', '<your username>');`
7. Remove the localhost redirect URL, commit `assets/backend-config.js`, run `python scripts/publish.py`, push.
   Never put the `service_role` key in the repository.

Known limits: sign-up requires a username, so dashboard invites, magic links and OAuth sign-ups are
rejected by the profile trigger (by design for now). Usernames can be probed through rename errors —
accepted: it reveals who is enrolled, not emails or grades.

## 9. Files

| Piece | File |
|---|---|
| Schema, roles, RLS | `supabase/migrations/0001_accounts_roles_progress.sql` |
| Policy tests (Postgres 16, CI job `database-access-rules`) | `supabase/tests/test_rls.py`, `supabase/tests/supabase_stub.sql` |
| Feature flag and keys | `assets/backend-config.js` |
| Auth, sync, merge, staff API | `assets/account.js` (merge rules tested in `tests/js/merge.test.js`) |
| Pages | `pages/account.html` + `assets/account-page.js`, `pages/admin.html` + `assets/admin-page.js` |
| supabase-js 2.45.4 (MIT), vendored, loaded only when enabled | `assets/vendor/supabase/` |
| UI end-to-end with an in-memory fake backend | `tests/e2e/accounts.e2e.js`, `tests/e2e/fake-supabase.js` |

Login is by email; the username is the public handle shown to the administration (logging in by
username would need a lookup that reveals which emails exist).

## 10. Security review (2026-11-09)

An independent review (`docs/reviews/security-2026-11-09.md`) found no way to exceed the access matrix
and six edge issues, all fixed with tests: bootstrap could promote an unconfirmed pre-registration of the
owner's email (M1); a malformed progress row could blank the admin table (M2); another account's local
progress on a shared browser could merge into the next account (M3); unconfirmed sign-ups listed as
students and CSV formula injection (L1); forged `updated_at` (L2); username probing accepted (L3).
