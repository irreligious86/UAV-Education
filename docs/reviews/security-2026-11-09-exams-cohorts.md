# Security review: exams and study groups (2026-11-09)

Scope: `supabase/migrations/0002_exams.sql`, `supabase/migrations/0003_cohorts.sql`, how they interact with
`0001_accounts_roles_progress.sql` (`is_staff()`, `my_role()`, profiles, grants), `assets/account.js`,
`assets/admin-page.js`, `assets/exam-page.js`, `assets/account-page.js`, `supabase/tests/*`. Checked against
`docs/MULTIUSER-PLAN.md` §3, §11, §12.
Method: an independent reviewer (separate agent) ran attacks on Postgres 16 with the Supabase stub, as the
`authenticated` / `anon` roles with JWT claims set. Races were run with two or more connections, both by
interleaving them by hand and by firing 8 parallel autocommit calls, which is what parallel PostgREST requests do.
Every finding below was reproduced. The proposed fixes were applied to a scratch database: they stop every
reproduction, and the existing 82 database tests still pass with them.

Verdict: one **high** issue. `exam_start` has no lock, so a student who fires parallel requests gets more attempts
than `attempts_allowed`. With `show_review` on, they submit one attempt blank, read the answer key from its
review, and score 100 % on another. One **medium** issue: staff can get around the bank freeze by moving questions
to another exam, and that changes how running attempts are graded. Five low issues. The cohorts migration and
the read side of the exam access matrix hold.

| # | Severity | Finding | Fix (summary) |
|---|---|---|---|
| H1 | high | concurrent `exam_start` exceeds `attempts_allowed`, which leaks the answer key and gives a free 100 % | per-(user, exam) advisory lock + unique `attempt_no` |
| M1 | medium | the freeze trigger checks only `new.exam_id`; moving questions out of a frozen exam lets staff edit or delete them, which regrades running attempts | check old and new exam, no `UPDATE (exam_id)`, `exam_submit` joins on `exam_id` |
| L1 | low | the attempt deadline ignores `closes_at`; `exam_submit` accepts work after the window closes | `deadline = least(now()+limit, closes_at)` |
| L2 | low | `p_answers` is stored verbatim and unbounded (5 MB accepted); a non-integer number aborts the submit | size cap; store only the filtered picks |
| L3 | low | staff can change the title, `pass_pct`, `questions_per_attempt`, `created_by` and `created_at` of an exam that already has attempts | `guard_exam` trigger |
| L4 | low | with `attempts_allowed > 1` and `show_review`, the review of attempt 1 is the answer key for overlapping questions in attempt 2 | review only after the last attempt or after `closes_at` |
| L5 | low | exam drafts (`uav-student:exam-draft:*`) survive logout and account switch on a shared browser | wipe them in `clearLocal()` |

---

## H1 — concurrent `exam_start` creates several attempts (attempts limit, answer leak)

File: `supabase/migrations/0002_exams.sql` lines 90–103 (`exam_start`: resume lookup, `count(*)`, `insert`).

Under READ COMMITTED, two calls running at the same time both find no running attempt, both count `used = 0`, and
both insert. Nothing locks them against each other, and no constraint stops it. The student can read every attempt
id through `exam_attempts` (own rows) and submit each one through the RPC.

Impact: the attempt limit is broken. A student can also beat a one-attempt exam outright: submit one attempt with
`{}`, take `answer` from its `review`, and submit the other one perfectly. If `questions_per_attempt` is smaller than
the bank, N parallel attempts give the key to N random subsets. All it takes is
`Promise.all([sb.rpc('exam_start',…), sb.rpc('exam_start',…)])` from devtools.

Reproduction (two connections, `attempts_allowed = 1`):

```python
c1 = psycopg.connect(dsn); c2 = psycopg.connect(dsn); act(c1, stu); act(c2, stu)
a1 = c1.execute("select public.exam_start(%s)", (eid,)).fetchone()[0]   # not committed yet
a2 = c2.execute("select public.exam_start(%s)", (eid,)).fetchone()[0]   # does not see c1's row
c1.commit(); c2.commit()
# -> 2 rows in exam_attempts for (eid, stu); a1["attempt"] != a2["attempt"]
key = {str(r["id"]): r["answer"] for r in submit(c1, a1, {})["review"]}
submit(c2, a2, key)   # -> score_pct 100, passed true
```

With 8 parallel autocommit calls (barrier, no manual interleaving), 6–8 attempts were stored on three runs.

Fix: serialise `exam_start` per (user, exam), and add a constraint as a backstop:

```sql
alter table public.exam_attempts add column attempt_no int;
update public.exam_attempts a set attempt_no = s.n
  from (select id, row_number() over (partition by exam_id, user_id order by started_at, id) n from public.exam_attempts) s
 where s.id = a.id;
alter table public.exam_attempts alter column attempt_no set not null;
alter table public.exam_attempts add constraint exam_attempts_no_unique unique (exam_id, user_id, attempt_no);

-- in exam_start, right after the confirmed-account check:
perform pg_advisory_xact_lock(hashtextextended('exam_start:' || p_exam::text || ':' || auth.uid()::text, 0));
select * into e from public.exams where id = p_exam and published for share;   -- see M1: bank edits wait
-- ... and insert attempt_no = used + 1
```

The function is VOLATILE, so the statement after the lock takes a fresh snapshot and sees the attempt the other
call committed. With this in place, the second call waits, then resumes the same attempt, and the parallel run
stores exactly 1 attempt. Regression tests: the two-connection interleave above, which needs a `lock_timeout` or a
thread because the second call now blocks, and the 8-thread barrier run asserting `count(*) = 1`.

`exam_submit` is sound against the same race: `select … for update` makes the second submit wait, and it then sees
`submitted_at` and fails with `InsufficientPrivilege`. Verified with two connections.

## M1 — the bank freeze can be bypassed by moving questions; that regrades running attempts

Files: `0002_exams.sql` line 59 (`eid := coalesce(new.exam_id, old.exam_id)`), line 162 (table-wide
`UPDATE` on `exam_questions`), line 143 (the `exam_submit` loop does not filter by `exam_id`).

On UPDATE the trigger checks only `new.exam_id`. Staff can run
`update exam_questions set exam_id = <unused exam> where exam_id = <frozen exam>`, and the trigger lets it through
because the target exam has no attempts. After that the rows are no longer frozen and can be edited or deleted.
`exam_submit` grades by `q.id = any(a.question_ids)` without checking the exam, so the edited answers apply to every
attempt still running on the frozen exam. Deleting the moved rows leaves submitted attempts pointing at questions
that no longer exist, and leaves the frozen exam with an empty bank. This breaks "staff cannot forge scores" and
"freezes a bank once anyone has taken it" (§11).

Reproduction:

```python
act(db, adam)
db.execute("update public.exam_questions set exam_id = %s where exam_id = %s", (scratch, frozen))   # 2 rows
db.execute("update public.exam_questions set answer = 1 where exam_id = %s", (scratch,))
act(db, alice)
db.execute("select public.exam_submit(%s, %s)", (attempt, json.dumps({qid: 0 for qid in ids})))
# -> correct 0 of 2 (0 was the correct answer when the attempt started)
```

Fix:

```sql
create or replace function public.freeze_used_bank() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op <> 'INSERT' then
    perform 1 from public.exams where id = old.exam_id for update;   -- waits for a concurrent exam_start (FOR SHARE)
    if exists (select 1 from public.exam_attempts a where a.exam_id = old.exam_id) then
      raise exception 'this exam already has attempts: its questions can no longer change' using errcode = '42501';
    end if;
  end if;
  if tg_op <> 'DELETE' then
    perform 1 from public.exams where id = new.exam_id for update;
    if exists (select 1 from public.exam_attempts a where a.exam_id = new.exam_id) then
      raise exception 'this exam already has attempts: its questions can no longer change' using errcode = '42501';
    end if;
  end if;
  return coalesce(new, old);
end $$;
revoke all on function public.freeze_used_bank() from public, anon, authenticated;
revoke update on public.exam_questions from authenticated;
grant update (q, options, answer, explain) on public.exam_questions to authenticated;
-- exam_submit loop and the exam_start question join: add  and q.exam_id = a.exam_id
```

The row lock on `exams`, paired with `for share` in `exam_start`, also closes a narrow TOCTOU window. Without it,
a bank edit that commits while an `exam_start` is still uncommitted passes the freeze check. Making the trigger
SECURITY DEFINER means the freeze no longer depends on the staff member's RLS view of `exam_attempts`.
Regression test: the reproduction above must raise `InsufficientPrivilege` at the `exam_id` update.

## L1 — the deadline ignores `closes_at`; the window is not enforced at submit

File: `0002_exams.sql` line 100 (`deadline = now() + time_limit`), lines 135–140 (`exam_submit`).

An attempt started one minute before `closes_at` with a 240-minute limit gets a deadline about 4 h after the close.
`exam_submit` also accepts it after staff unpublish the exam. Reproduced: deadline 05:00 against closes_at 01:01,
and the submit was accepted after the close and after unpublishing.

Fix (in `exam_start`): `least(now() + make_interval(mins => e.time_limit_min), coalesce(e.closes_at, 'infinity'))`.
Whether unpublishing should stop running attempts is a policy choice. If it should, add `and e.published` in
`exam_submit`. Either way, document it in §11.

## L2 — `p_answers` stored verbatim, unbounded; malformed numbers abort the submit

File: `0002_exams.sql` lines 144, 149.

Any object is stored in `exam_attempts.answers`. A 5 MB object with 5,000 junk keys was accepted, about 75 KB
after TOAST compression. That bloats storage and can be repeated once per attempt. `{"<qid>": 1.5}` fails with
`InvalidTextRepresentation`, and `{"<qid>": 1e12}` fails with `NumericValueOutOfRange`. In both cases the submit
aborts instead of grading that question as unanswered. No information leaks: the cast runs for every key whatever
the answer is. Duplicate JSON keys collapse to the last one, which is harmless.

Fix (validated):

```sql
if pg_column_size(p_answers) > 65536 then raise exception 'answers too large' using errcode = '22023'; end if;
-- in the loop:
v := p_answers -> r.id::text;
pick := case when jsonb_typeof(v) = 'number' and v::text ~ '^[0-9]{1,2}$' then v::text::int end;
if pick is not null then kept := kept || jsonb_build_object(r.id::text, pick); end if;
-- store answers = kept instead of p_answers
```

## L3 — staff can rewrite the graded settings and authorship of an exam with attempts

File: `0002_exams.sql` lines 161, 175 (table-wide `UPDATE` on `exams`).

Stored `passed` and `score_pct` do not change. But the title shown in every result and CSV can be changed after the
fact (for example "Final" to "Practice"). Changing `pass_pct` or `questions_per_attempt` changes how in-flight
attempts are graded. `created_by` and `created_at` can be forged. Reproduced as admin on an exam with a submitted
attempt.

Fix (validated; `humanError` already maps "already has attempts"):

```sql
create function public.guard_exam() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'INSERT' then new.created_by := auth.uid(); new.created_at := now(); return new; end if;
  new.id := old.id; new.created_by := old.created_by; new.created_at := old.created_at;
  if (new.title, new.module_id, new.pass_pct, new.questions_per_attempt, new.time_limit_min)
       is distinct from (old.title, old.module_id, old.pass_pct, old.questions_per_attempt, old.time_limit_min)
     and exists (select 1 from public.exam_attempts a where a.exam_id = old.id) then
    raise exception 'this exam already has attempts: its grading settings can no longer change' using errcode = '42501';
  end if;
  return new;
end $$;
create trigger exams_guard before insert or update on public.exams for each row execute function public.guard_exam();
revoke all on function public.guard_exam() from public, anon, authenticated;
```

`published`, `opens_at`, `closes_at`, `attempts_allowed` and `show_review` stay editable.

## L4 — the review of an earlier attempt is the answer key for the next one

File: `0002_exams.sql` line 155.

With `attempts_allowed = 2`, a bank of 4 and 3 questions per attempt, at least 2 of the questions in attempt 2 are
already answered by attempt 1's review (reproduced). Without H1 this is the documented `show_review` behaviour,
but it makes every attempt after the first worth much less as an exam.

Fix (validated; the existing tests use `attempts_allowed = 1` and still pass):

```sql
select count(*) into used from public.exam_attempts where exam_id = a.exam_id and user_id = a.user_id;
-- 'review', case when e.show_review and (used >= e.attempts_allowed or now() > e.closes_at) then review end
```

`assets/exam-page.js` already shows "Разбор ответов для этого экзамена скрыт." when `review` is null. Update the
fake backend in `tests/e2e/fake-supabase.js` if it mirrors the old rule.

## L5 — exam drafts survive logout on a shared browser

Files: `assets/exam-page.js` lines 274, 282, 384; `assets/account.js` line 74 (`clearLocal` removes only the
progress, pending and owner keys).

`uav-student:exam-draft:<attempt>` holds `{question_id: pick}`. The draft is removed only after a successful
submit. If the auto-submit fails, or the student logs out mid-exam, it stays in the browser. The next person on that
browser can read the previous student's picks by question id, and a later attempt on the same bank shares those ids.

Fix (`account.js`, so it also runs on `SIGNED_OUT` and on owner change through `claimLocal`):

```js
function clearLocal() {
  try {
    localStorage.removeItem(KEY); localStorage.removeItem(PENDING); localStorage.removeItem(OWNER);
    Object.keys(localStorage).forEach(function (k) { if (k.indexOf("uav-student:exam-draft:") === 0) localStorage.removeItem(k); });
  } catch (e) { /* ignore */ }
}
```

Regression: an e2e step that starts an exam, picks an answer, logs out, and asserts that no `exam-draft` key is left.

---

## Checked and sound

- **Answers before submit:** a student reads 0 rows of `exam_questions`. `exam_start` returns only `id`, `q` and
  `options`. `exam_results` and `exam_attempts` hold no bank data. Errors are fixed strings and leak nothing.
  Timing does not depend on whether an answer is right.
- **Scores:** no INSERT, UPDATE or DELETE grant on `exam_attempts` for anyone, including the superadmin. Only the
  two SECURITY DEFINER RPCs write it. Both pin `search_path = ''`, check `auth.uid()`, and return only the caller's
  data. Attempts belong to their owner (`user_id = auth.uid()`), so submitting someone else's attempt fails. A second
  submit, a submit past the deadline, the expired-attempt count, unpublished exams, the open window at start and
  unconfirmed accounts are all rejected (existing tests, and the concurrent submit was verified).
- **Exam deletion:** `on delete restrict` from attempts plus the freeze trigger keep exams that have attempts. The
  admin UI hides the delete button, but the database is what enforces it.
- **`exam_results`:** `security_invoker = true`, so the RLS of `exam_attempts`, `exams` and `profiles` applies. A
  student sees only their own rows, and the title of an unpublished exam shows as null. Staff see all rows.
  Revoked from anon.
- **Cohorts:** `cohorts_read` uses a subquery on `cohort_members`, whose policy does not reference `cohorts`, so
  there is no recursion. A student sees only their own groups and only their own membership row. A student cannot
  create, rename, delete, join or leave a group. Probing a group name with an INSERT returns the RLS error, not
  `UniqueViolation`, because the WITH CHECK runs before the index is updated. `added_by`, `added_at`, `created_by`
  and `created_at` are set by triggers. Only `name` is updatable. A demoted admin loses access immediately because
  the policies call `is_staff()` on each query.
- **Grants and default privileges:** the stub mirrors Supabase's `alter default privileges … grant all` on tables,
  functions and sequences. After the migrations, anon can execute no function in `public`, and authenticated can
  execute only `set_role`, `my_role`, `is_staff`, `exam_start` and `exam_submit`, all SECURITY DEFINER with
  `search_path=""`. Trigger functions are revoked, and Postgres refuses to call them outside a trigger anyway.
  Hygiene note: `exam_questions_id_seq` and `role_audit_id_seq` keep USAGE for anon and authenticated from the
  default privileges. PostgREST cannot reach `nextval()`, so this is not exploitable, but
  `revoke all on all sequences in schema public from anon, authenticated;` tidies it up.
- **Role requirements:** accounts are created only by self-registration; there is one superadmin, and only they
  appoint admins. Unchanged by 0002/0003; `test_rls.py` still covers it.
- **XSS:** every database string (exam title, question text, options, explanation, username, email, group name,
  lab fields) goes through `esc()` or `textContent`. The remaining unescaped values are integers from the database,
  or numbers computed by `UAVGrading`, which yields numbers or NaN even when `progress.data` holds hostile strings.
  `data-name` is read back with `getAttribute` into `confirm()`, which is plain text.
- **CSV:** cells starting with `= + - @ \t \r` are prefixed. Usernames and emails cannot carry line breaks.
  Hardening for staff-entered group names and titles: add `\r` to the quoting regex (`/[",\r\n]/`).
