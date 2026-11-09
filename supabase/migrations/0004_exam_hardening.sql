-- UAV Student: exam hardening after the security review docs/reviews/security-2026-11-09-exams-cohorts.md.
-- H1  exam_start is serialised per (user, exam) and every attempt has a unique number: parallel calls can no
--     longer create more attempts than allowed (and harvest the answer key from one of them).
-- M1  the bank freeze checks the old and the new exam of a question; a question cannot be moved out of a
--     frozen bank; grading and question lookup also match the attempt's exam.
-- L1  an attempt's deadline never runs past the exam's closes_at.
-- L2  submitted answers are size-limited and filtered to small integer picks; only those are stored.
-- L3  title and grading settings of an exam with attempts are frozen; authorship is set by the database.
-- L4  the review (answer key) is returned only after the last allowed attempt or once the exam has closed.
-- Hygiene: browser roles get no sequence privileges.
-- Policy kept on purpose: unpublishing hides an exam from new starts, a running attempt can still be submitted;
-- attempts_allowed, show_review, the window and published may change on an exam with attempts.
-- Tests: supabase/tests/test_exams.py, supabase/tests/test_zz_concurrency.py.

begin;
-- H1: per-(user, exam) serialisation + a unique attempt number as a backstop
alter table public.exam_attempts add column attempt_no int;
update public.exam_attempts a set attempt_no = s.n
  from (select id, row_number() over (partition by exam_id, user_id order by started_at, id) n from public.exam_attempts) s
 where s.id = a.id;
alter table public.exam_attempts alter column attempt_no set not null;
alter table public.exam_attempts add constraint exam_attempts_no_unique unique (exam_id, user_id, attempt_no);

create or replace function public.exam_start(p_exam uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  e public.exams;
  a public.exam_attempts;
  used int;
  qs jsonb;
begin
  if auth.uid() is null or not exists (select 1 from public.profiles where id = auth.uid() and confirmed_at is not null) then
    raise exception 'log in with a confirmed account' using errcode = '42501';
  end if;
  -- one exam_start per (user, exam) at a time; the next statement sees what the previous call committed
  perform pg_advisory_xact_lock(hashtextextended('exam_start:' || p_exam::text || ':' || auth.uid()::text, 0));
  select * into e from public.exams where id = p_exam and published for share;   -- bank edits wait for us (freeze trigger)
  if not found then
    raise exception 'no such exam' using errcode = 'P0002';
  end if;
  if (e.opens_at is not null and now() < e.opens_at) or (e.closes_at is not null and now() > e.closes_at) then
    raise exception 'the exam is not open now' using errcode = '42501';
  end if;
  select * into a from public.exam_attempts
   where exam_id = p_exam and user_id = auth.uid() and submitted_at is null and deadline > now()
   order by started_at desc limit 1;
  if not found then
    select count(*) into used from public.exam_attempts where exam_id = p_exam and user_id = auth.uid();
    if used >= e.attempts_allowed then
      raise exception 'no attempts left (% of %)', used, e.attempts_allowed using errcode = '42501';
    end if;
    insert into public.exam_attempts (exam_id, user_id, attempt_no, deadline, question_ids)
    select p_exam, auth.uid(), used + 1,
           least(now() + make_interval(mins => e.time_limit_min), coalesce(e.closes_at, 'infinity')),   -- L1
           coalesce(array_agg(id), '{}')
      from (select id from public.exam_questions where exam_id = p_exam order by random() limit e.questions_per_attempt) s
    returning * into a;
    if cardinality(a.question_ids) = 0 then
      raise exception 'the exam has no questions' using errcode = 'P0002';
    end if;
  end if;
  select coalesce(jsonb_agg(jsonb_build_object('id', q.id, 'q', q.q, 'options', q.options) order by x.ord), '[]'::jsonb)
    into qs
    from unnest(a.question_ids) with ordinality as x(qid, ord)
    join public.exam_questions q on q.id = x.qid and q.exam_id = a.exam_id;
  return jsonb_build_object('attempt', a.id, 'exam', e.id, 'title', e.title, 'deadline', a.deadline, 'questions', qs);
end $$;

create or replace function public.exam_submit(p_attempt uuid, p_answers jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  a public.exam_attempts;
  e public.exams;
  n_correct int := 0;
  n_total int;
  review jsonb := '[]'::jsonb;
  kept jsonb := '{}'::jsonb;
  r record;
  v jsonb;
  pick int;
  used int;
begin
  if jsonb_typeof(p_answers) is distinct from 'object' then
    raise exception 'answers must be an object' using errcode = '22023';
  end if;
  if pg_column_size(p_answers) > 65536 then                               -- L2
    raise exception 'answers too large' using errcode = '22023';
  end if;
  select * into a from public.exam_attempts where id = p_attempt and user_id = auth.uid() for update;
  if not found then
    raise exception 'no such attempt' using errcode = 'P0002';
  end if;
  if a.submitted_at is not null then
    raise exception 'this attempt is already submitted' using errcode = '42501';
  end if;
  if now() > a.deadline + interval '30 seconds' then
    raise exception 'time is up' using errcode = '42501';
  end if;
  select * into e from public.exams where id = a.exam_id;
  n_total := cardinality(a.question_ids);
  for r in select q.id, q.answer, q.explain from public.exam_questions q
            where q.id = any (a.question_ids) and q.exam_id = a.exam_id loop   -- M1
    v := p_answers -> r.id::text;
    pick := case when jsonb_typeof(v) = 'number' and v::text ~ '^[0-9]{1,2}$' then v::text::int end;   -- L2
    if pick is not null then kept := kept || jsonb_build_object(r.id::text, pick); end if;
    if pick = r.answer then n_correct := n_correct + 1; end if;
    review := review || jsonb_build_object('id', r.id, 'your', pick, 'answer', r.answer, 'explain', r.explain);
  end loop;
  update public.exam_attempts
     set submitted_at = now(), answers = kept, correct = n_correct, total = n_total,
         score_pct = round(100.0 * n_correct / greatest(n_total, 1)),
         passed = round(100.0 * n_correct / greatest(n_total, 1)) >= e.pass_pct
   where id = a.id
  returning * into a;
  select count(*) into used from public.exam_attempts where exam_id = a.exam_id and user_id = a.user_id;
  return jsonb_build_object('correct', a.correct, 'total', a.total, 'score_pct', a.score_pct, 'passed', a.passed,
                            -- L4: the answer key only after the last attempt (or once the exam has closed)
                            'review', case when e.show_review and (used >= e.attempts_allowed or now() > e.closes_at) then review end);
end $$;

-- M1: freeze checks both the old and the new exam; exam_id/id of a question cannot change
create or replace function public.freeze_used_bank() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op <> 'INSERT' then
    perform 1 from public.exams where id = old.exam_id for update;      -- waits for a concurrent exam_start
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

-- L3: graded settings and authorship of an exam with attempts are frozen
create function public.guard_exam() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'INSERT' then
    new.created_by := auth.uid(); new.created_at := now(); return new;
  end if;
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

-- hygiene: sequences inherited Supabase default grants
revoke all on all sequences in schema public from anon, authenticated;
commit;
