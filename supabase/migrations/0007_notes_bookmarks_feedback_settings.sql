-- UAV Student: personal study data (notes, bookmarks, settings, reading history) and feedback to the developer.
-- Design, access matrix and sync rules: docs/MULTIUSER-PLAN.md, section 14. Tests: supabase/tests/test_notes_bookmarks_feedback.py.
--
-- Personal data (user_notes, user_bookmarks, user_settings, user_history) belongs to its owner only: staff have no
-- access, the same as anyone else. Deleting the account deletes it (cascade from profiles).
-- Feedback is sent only through send_feedback() by a signed-in user with a confirmed email (rate-limited); the author
-- reads their own messages and their status, staff read all of them and change only status and staff_note;
-- the superadmin may delete one (spam). Deleting the account keeps the message without its author (set null).
-- Anchors are the ids of section headings on a lesson page ("sec-3", assets/history.js), '' = the whole lesson.

begin;

-- ---------------------------------------------------------------- tables
create table public.user_notes (
  user_id     uuid not null references public.profiles (id) on delete cascade,
  module_id   text not null check (module_id ~ '^[a-z0-9-]{1,64}$'),
  anchor      text not null default '' check (anchor ~ '^[A-Za-z0-9_-]{0,80}$'),
  label       text not null default '' check (char_length(label) <= 160),     -- heading text when the note was written
  body        text not null check (char_length(body) between 1 and 8000),     -- plain text; an empty note is deleted instead
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  primary key (user_id, module_id, anchor)
);

create table public.user_bookmarks (
  user_id     uuid not null references public.profiles (id) on delete cascade,
  module_id   text not null check (module_id ~ '^[a-z0-9-]{1,64}$'),
  anchor      text not null default '' check (anchor ~ '^[A-Za-z0-9_-]{0,80}$'),
  label       text not null default '' check (char_length(label) <= 160),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  primary key (user_id, module_id, anchor)
);

-- Known keys only; the browser keeps them in localStorage "uav-student:settings" (+ "uav-student:ready-only").
-- firmwarePath is a course path id or '' (a pattern, not a list: a new path must not need a migration).
create table public.user_settings (
  user_id     uuid primary key references public.profiles (id) on delete cascade,
  data        jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now(),
  constraint user_settings_shape check (
    jsonb_typeof(data) = 'object' and pg_column_size(data) < 16384 and
    (data - array['readyOnly', 'resumeOnOpen', 'notesPanel', 'firmwarePath']) = '{}'::jsonb and
    (not data ? 'readyOnly'    or jsonb_typeof(data -> 'readyOnly')    = 'boolean') and
    (not data ? 'resumeOnOpen' or jsonb_typeof(data -> 'resumeOnOpen') = 'boolean') and
    (not data ? 'notesPanel'   or jsonb_typeof(data -> 'notesPanel')   = 'boolean') and
    (not data ? 'firmwarePath' or (jsonb_typeof(data -> 'firmwarePath') = 'string' and data ->> 'firmwarePath' ~ '^[a-z0-9-]{0,64}$')))
);

-- Reading history, the browser's "uav-student:history:v1" items: [{id, path, title, anchor, heading, at}], newest first.
-- Its own owner-only row, not progress.data: staff read progress, and what someone reads is not a grade.
create table public.user_history (
  user_id     uuid primary key references public.profiles (id) on delete cascade,
  items       jsonb not null default '[]'::jsonb,
  updated_at  timestamptz not null default now(),
  constraint user_history_shape check (
    jsonb_typeof(items) = 'array' and jsonb_array_length(items) <= 30 and pg_column_size(items) < 32768 and
    not jsonb_path_exists(items, '$[*] ? (@.type() != "object")') and
    not jsonb_path_exists(items, '$[*] ? (!exists(@.id ? (@.type() == "string")) || !exists(@.at ? (@.type() == "number")))'))
);

create table public.feedback (
  id           bigint generated always as identity primary key,
  user_id      uuid references public.profiles (id) on delete set null,    -- null: the author deleted their account
  module_id    text check (module_id ~ '^[a-z0-9-]{1,64}$'),
  section_key  text check (section_key ~ '^[a-z0-9-]{1,64}$'),           -- course section, e.g. 'betaflight'
  anchor       text not null default '' check (anchor ~ '^[A-Za-z0-9_-]{0,80}$'),
  kind         text not null check (kind in ('error', 'unclear', 'idea', 'other')),
  -- at least 10 characters that are not white space of any kind (newlines, tabs, NBSP and other Unicode spaces)
  body         text not null check (
                 char_length(regexp_replace(body, '[[:space:]\u00a0\u1680\u2000-\u200b\u2028\u2029\u202f\u205f\u3000\ufeff]', '', 'g')) >= 10
                 and char_length(body) <= 4000),
  page_lang    text check (page_lang ~ '^[a-z]{2,3}(-[A-Z]{2})?(-[a-z0-9]{5,8})?$'),
  status       text not null default 'new' check (status in ('new', 'in_progress', 'done', 'rejected')),
  staff_note   text not null default '' check (char_length(staff_note) <= 2000),   -- internal: not shown to the author
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint feedback_target check (module_id is not null or section_key is not null)
);
create index feedback_by_user on public.feedback (user_id, created_at desc);
create index feedback_by_status on public.feedback (status, created_at desc);

-- ---------------------------------------------------------------- triggers
-- updated_at is the server's clock and doubles as the row version the browser saves against (save_note):
-- clock_timestamp(), not now(), so two saves in one transaction are still two versions
create function public.touch_version() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at := clock_timestamp();
  return new;
end $$;
create trigger user_notes_touch before insert or update on public.user_notes for each row execute function public.touch_version();
create trigger user_bookmarks_touch before insert or update on public.user_bookmarks for each row execute function public.touch_version();
create trigger user_settings_touch before insert or update on public.user_settings for each row execute function public.touch_version();
create trigger user_history_touch before insert or update on public.user_history for each row execute function public.touch_version();
create trigger feedback_touch before update on public.feedback for each row execute function public.touch_progress();

-- Per-user row cap (argument: the limit). Serialised per (table, user) so parallel inserts cannot overshoot;
-- an upsert of a row that already exists is an update and passes at the cap. A row for another user is left to
-- RLS (which rejects it): the trigger runs before RLS, and must not reveal whether that user is at the cap.
create function public.user_rows_cap() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  lim int := tg_argv[0]::int;
  n int;
  same int;
begin
  if auth.uid() is not null and new.user_id is distinct from auth.uid() then
    return new;
  end if;
  perform pg_advisory_xact_lock(hashtextextended('user_rows_cap:' || tg_table_name || ':' || new.user_id::text, 0));
  execute format('select count(*), count(*) filter (where module_id = $2 and anchor = $3) from public.%I where user_id = $1', tg_table_name)
    into n, same using new.user_id, new.module_id, new.anchor;
  if same = 0 and n >= lim then
    raise exception '% limit reached: at most % rows per user', tg_table_name, lim using errcode = '54000';
  end if;
  return new;
end $$;

create trigger user_notes_cap before insert on public.user_notes for each row execute function public.user_rows_cap('2000');
create trigger user_bookmarks_cap before insert on public.user_bookmarks for each row execute function public.user_rows_cap('1000');

-- ---------------------------------------------------------------- notes: save only over the version the browser saw
-- p_expected = the updated_at the browser last saw (null for a note it never saw on the server). If the stored row
-- is a different version (another device saved in between), nothing is written and the stored version comes back,
-- so the browser can merge instead of overwriting. SECURITY INVOKER: RLS and the column grants apply as usual.
create function public.save_note(p_module text, p_anchor text, p_label text, p_body text, p_expected timestamptz)
returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare
  cur public.user_notes;
  t timestamptz;
begin
  select * into cur from public.user_notes where user_id = auth.uid() and module_id = p_module and anchor = p_anchor for update;
  if found then
    if p_expected is distinct from cur.updated_at then
      return jsonb_build_object('conflict', true, 'body', cur.body, 'label', cur.label, 'updated_at', cur.updated_at);
    end if;
    update public.user_notes set body = p_body, label = coalesce(p_label, '')
     where user_id = auth.uid() and module_id = p_module and anchor = p_anchor returning updated_at into t;
    return jsonb_build_object('conflict', false, 'updated_at', t);
  end if;
  begin
    insert into public.user_notes (user_id, module_id, anchor, label, body)
    values (auth.uid(), p_module, p_anchor, coalesce(p_label, ''), p_body) returning updated_at into t;
  exception when unique_violation then          -- another device created it a moment ago
    select * into cur from public.user_notes where user_id = auth.uid() and module_id = p_module and anchor = p_anchor;
    return jsonb_build_object('conflict', true, 'body', cur.body, 'label', cur.label, 'updated_at', cur.updated_at);
  end;
  return jsonb_build_object('conflict', false, 'updated_at', t);
end $$;

-- ---------------------------------------------------------------- feedback functions
-- The only way to create feedback: the author is the caller, the email is confirmed, at most 10 per hour and 50 per day.
create function public.send_feedback(p_module text, p_section text, p_anchor text, p_kind text, p_body text, p_lang text)
returns bigint
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  n_hour int;
  n_day int;
  new_id bigint;
begin
  if uid is null then
    raise exception 'log in with a confirmed account' using errcode = '42501';
  end if;
  -- the row lock serialises one user's parallel calls, so the rate limit holds under concurrency
  perform 1 from public.profiles where id = uid and confirmed_at is not null for update;
  if not found then
    raise exception 'log in with a confirmed account' using errcode = '42501';
  end if;
  select count(*) filter (where created_at > now() - interval '1 hour'), count(*) into n_hour, n_day
    from public.feedback where user_id = uid and created_at > now() - interval '1 day';
  if n_hour >= 10 or n_day >= 50 then
    raise exception 'feedback rate limit: at most 10 per hour and 50 per day' using errcode = '54000';
  end if;
  insert into public.feedback (user_id, module_id, section_key, anchor, kind, body, page_lang)
  values (uid, nullif(p_module, ''), nullif(p_section, ''), coalesce(p_anchor, ''), p_kind, p_body, nullif(p_lang, ''))
  returning id into new_id;
  return new_id;
end $$;

-- Staff list with the author's username and the internal note (which authenticated cannot select directly).
create function public.feedback_for_staff(p_before timestamptz default null, p_limit int default 500)
returns table (id bigint, user_id uuid, username text, module_id text, section_key text, anchor text, kind text, body text,
               page_lang text, status text, staff_note text, created_at timestamptz, updated_at timestamptz)
language plpgsql stable security definer set search_path = '' as $$
begin
  if not public.is_staff() then
    raise exception 'only staff can read all feedback' using errcode = '42501';
  end if;
  return query
    select f.id, f.user_id, p.username, f.module_id, f.section_key, f.anchor, f.kind, f.body, f.page_lang, f.status, f.staff_note,
           f.created_at, f.updated_at
      from public.feedback f left join public.profiles p on p.id = f.user_id
     where p_before is null or f.created_at < p_before
     order by f.created_at desc, f.id desc
     limit least(greatest(coalesce(p_limit, 500), 1), 2000);
end $$;

-- Staff change status and the internal note, nothing else (null keeps the current value).
create function public.feedback_set(p_id bigint, p_status text, p_staff_note text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_staff() then
    raise exception 'only staff can change feedback' using errcode = '42501';
  end if;
  update public.feedback set status = coalesce(p_status, status), staff_note = coalesce(p_staff_note, staff_note) where id = p_id;
  if not found then
    raise exception 'no such feedback' using errcode = 'P0002';
  end if;
end $$;

-- Spam removal: the superadmin only.
create function public.feedback_delete(p_id bigint) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if public.my_role() is distinct from 'superadmin' then
    raise exception 'only the superadmin can delete feedback' using errcode = '42501';
  end if;
  delete from public.feedback where id = p_id;
end $$;

-- ---------------------------------------------------------------- privileges
revoke all on public.user_notes, public.user_bookmarks, public.user_settings, public.user_history, public.feedback from anon, authenticated;
-- the browser upserts (insert … on conflict do update sets every sent column), hence update on the key columns too;
-- the policies' with check keeps user_id the caller's. created_at / updated_at are the database's.
grant select, delete on public.user_notes, public.user_bookmarks, public.user_settings, public.user_history to authenticated;
grant insert (user_id, module_id, anchor, label, body), update (user_id, module_id, anchor, label, body) on public.user_notes to authenticated;
grant insert (user_id, module_id, anchor, label), update (user_id, module_id, anchor, label) on public.user_bookmarks to authenticated;
grant insert (user_id, data), update (user_id, data) on public.user_settings to authenticated;
grant insert (user_id, items), update (user_id, items) on public.user_history to authenticated;
-- the author reads their messages without staff_note; no insert/update/delete: the functions above do that
grant select (id, user_id, module_id, section_key, anchor, kind, body, page_lang, status, created_at, updated_at) on public.feedback to authenticated;
revoke all on all sequences in schema public from anon, authenticated;

revoke all on function public.user_rows_cap(), public.touch_version() from public, anon, authenticated;
revoke all on function public.save_note(text, text, text, text, timestamptz) from public, anon;
grant execute on function public.save_note(text, text, text, text, timestamptz) to authenticated;
revoke all on function public.send_feedback(text, text, text, text, text, text), public.feedback_for_staff(timestamptz, int),
                       public.feedback_set(bigint, text, text), public.feedback_delete(bigint) from public, anon;
grant execute on function public.send_feedback(text, text, text, text, text, text), public.feedback_for_staff(timestamptz, int),
                          public.feedback_set(bigint, text, text), public.feedback_delete(bigint) to authenticated;

-- ---------------------------------------------------------------- row level security
alter table public.user_notes enable row level security;
alter table public.user_bookmarks enable row level security;
alter table public.user_settings enable row level security;
alter table public.user_history enable row level security;
alter table public.feedback enable row level security;

create policy user_notes_own on public.user_notes for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy user_bookmarks_own on public.user_bookmarks for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy user_settings_own on public.user_settings for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy user_history_own on public.user_history for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy feedback_read on public.feedback for select to authenticated
  using (user_id = auth.uid() or public.is_staff());

commit;
