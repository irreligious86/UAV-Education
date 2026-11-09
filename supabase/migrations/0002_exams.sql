-- UAV Student: exams with private question banks, graded by the database.
-- Module quizzes ship with the public site (their answers are in the public repository), so they can only
-- ever be self-checks. Exams are different: their questions and answers exist only in this database.
-- Students receive questions without answers from exam_start(), send answers to exam_submit(), and the
-- database grades and stores the attempt. Nobody, including staff, can write or change a score directly.
-- Design: docs/MULTIUSER-PLAN.md, section 11. Tests: supabase/tests/test_exams.py.

begin;

create table public.exams (
  id                     uuid primary key default gen_random_uuid(),
  title                  text not null check (length(title) between 3 and 200),
  module_id              text,                                   -- optional link to a course module
  pass_pct               int  not null default 80 check (pass_pct between 1 and 100),
  questions_per_attempt  int  not null default 10 check (questions_per_attempt between 1 and 100),
  time_limit_min         int  not null default 20 check (time_limit_min between 1 and 240),
  attempts_allowed       int  not null default 1 check (attempts_allowed between 1 and 20),
  show_review            boolean not null default true,          -- reveal correct answers after submitting
  opens_at               timestamptz,
  closes_at              timestamptz,
  published              boolean not null default false,
  created_by             uuid references public.profiles (id) on delete set null default auth.uid(),
  created_at             timestamptz not null default now(),
  check (closes_at is null or opens_at is null or closes_at > opens_at)
);

create table public.exam_questions (
  id        bigint generated always as identity primary key,
  exam_id   uuid not null references public.exams (id) on delete cascade,
  q         text not null check (length(q) between 3 and 2000),
  options   jsonb not null check (jsonb_typeof(options) = 'array' and jsonb_array_length(options) between 2 and 8
                                  and not jsonb_path_exists(options, '$[*] ? (@.type() != "string")')),
  answer    int not null,
  explain   text not null default '',
  check (answer >= 0 and answer < jsonb_array_length(options))
);
create index exam_questions_exam on public.exam_questions (exam_id);

create table public.exam_attempts (
  id            uuid primary key default gen_random_uuid(),
  exam_id       uuid not null references public.exams (id) on delete restrict,   -- results outlive edits
  user_id       uuid not null references public.profiles (id) on delete cascade,
  started_at    timestamptz not null default now(),
  deadline      timestamptz not null,
  question_ids  bigint[] not null,
  submitted_at  timestamptz,
  answers       jsonb,
  correct       int,
  total         int,
  score_pct     int,
  passed        boolean
);
create index exam_attempts_user on public.exam_attempts (user_id, exam_id);

-- A bank that already has attempts is frozen: editing it would silently change what was graded.
create function public.freeze_used_bank() returns trigger
language plpgsql set search_path = '' as $$
declare
  eid uuid := coalesce(new.exam_id, old.exam_id);
begin
  if exists (select 1 from public.exam_attempts a where a.exam_id = eid) then
    raise exception 'this exam already has attempts: its questions can no longer change' using errcode = '42501';
  end if;
  return coalesce(new, old);
end $$;

create trigger exam_questions_frozen before insert or update or delete on public.exam_questions
  for each row execute function public.freeze_used_bank();

-- ---------------------------------------------------------------- student RPCs
-- Start (or resume) an attempt: returns questions WITHOUT answers.
create function public.exam_start(p_exam uuid) returns jsonb
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
  select * into e from public.exams where id = p_exam and published;
  if not found then
    raise exception 'no such exam' using errcode = 'P0002';
  end if;
  if (e.opens_at is not null and now() < e.opens_at) or (e.closes_at is not null and now() > e.closes_at) then
    raise exception 'the exam is not open now' using errcode = '42501';
  end if;
  -- resume an unfinished attempt that is still running
  select * into a from public.exam_attempts
   where exam_id = p_exam and user_id = auth.uid() and submitted_at is null and deadline > now()
   order by started_at desc limit 1;
  if not found then
    select count(*) into used from public.exam_attempts where exam_id = p_exam and user_id = auth.uid();
    if used >= e.attempts_allowed then
      raise exception 'no attempts left (% of %)', used, e.attempts_allowed using errcode = '42501';
    end if;
    insert into public.exam_attempts (exam_id, user_id, deadline, question_ids)
    select p_exam, auth.uid(), now() + make_interval(mins => e.time_limit_min),
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
    join public.exam_questions q on q.id = x.qid;
  return jsonb_build_object('attempt', a.id, 'exam', e.id, 'title', e.title, 'deadline', a.deadline, 'questions', qs);
end $$;

-- Submit answers {"<question id>": <option index>, ...}; graded here. One submission per attempt,
-- before the deadline (30 s grace for the network).
create function public.exam_submit(p_attempt uuid, p_answers jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  a public.exam_attempts;
  e public.exams;
  n_correct int := 0;
  n_total int;
  review jsonb := '[]'::jsonb;
  r record;
  pick int;
begin
  if jsonb_typeof(p_answers) is distinct from 'object' then
    raise exception 'answers must be an object' using errcode = '22023';
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
  for r in select q.id, q.answer, q.explain from public.exam_questions q where q.id = any (a.question_ids) loop
    pick := case when jsonb_typeof(p_answers -> r.id::text) = 'number' then (p_answers ->> r.id::text)::int end;
    if pick = r.answer then n_correct := n_correct + 1; end if;
    review := review || jsonb_build_object('id', r.id, 'your', pick, 'answer', r.answer, 'explain', r.explain);
  end loop;
  update public.exam_attempts
     set submitted_at = now(), answers = p_answers, correct = n_correct, total = n_total,
         score_pct = round(100.0 * n_correct / greatest(n_total, 1)),
         passed = round(100.0 * n_correct / greatest(n_total, 1)) >= e.pass_pct
   where id = a.id
  returning * into a;
  return jsonb_build_object('correct', a.correct, 'total', a.total, 'score_pct', a.score_pct, 'passed', a.passed,
                            'review', case when e.show_review then review else null end);
end $$;

-- ---------------------------------------------------------------- privileges and RLS
revoke all on public.exams, public.exam_questions, public.exam_attempts from anon, authenticated;
grant select on public.exams to authenticated;
grant insert, update, delete on public.exams to authenticated;            -- RLS: staff only
grant select, insert, update, delete on public.exam_questions to authenticated;   -- RLS: staff only
grant select on public.exam_attempts to authenticated;                    -- writes only through the RPCs

revoke all on function public.exam_start(uuid), public.exam_submit(uuid, jsonb) from public, anon;
grant execute on function public.exam_start(uuid), public.exam_submit(uuid, jsonb) to authenticated;
revoke all on function public.freeze_used_bank() from public, anon, authenticated;

alter table public.exams enable row level security;
alter table public.exam_questions enable row level security;
alter table public.exam_attempts enable row level security;

create policy exams_read on public.exams for select to authenticated using (published or public.is_staff());
create policy exams_staff_insert on public.exams for insert to authenticated with check (public.is_staff());
create policy exams_staff_update on public.exams for update to authenticated using (public.is_staff()) with check (public.is_staff());
create policy exams_staff_delete on public.exams for delete to authenticated using (public.is_staff());

create policy exam_questions_staff on public.exam_questions for all to authenticated
  using (public.is_staff()) with check (public.is_staff());

create policy exam_attempts_read on public.exam_attempts for select to authenticated
  using (user_id = auth.uid() or public.is_staff());

-- Results for staff and for the student's own list. Answers of the bank never appear here.
create view public.exam_results with (security_invoker = true) as
  select a.id, a.exam_id, x.title, a.user_id, p.username, p.email, a.started_at, a.deadline, a.submitted_at,
         a.correct, a.total, a.score_pct, a.passed
    from public.exam_attempts a
    left join public.exams x on x.id = a.exam_id   -- an unpublished exam keeps the student's own result visible
    join public.profiles p on p.id = a.user_id;

revoke all on public.exam_results from anon, authenticated;
grant select on public.exam_results to authenticated;

commit;
