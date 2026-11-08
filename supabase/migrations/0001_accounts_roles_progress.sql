-- UAV Student: accounts, roles (student / admin / single superadmin) and per-user progress.
-- Target: Supabase (Postgres 15+). Run once in the SQL editor, or with `supabase db push`.
-- Access rules live here, in the database (Row Level Security); the browser holds only the anon key.
-- Design and access matrix: docs/MULTIUSER-PLAN.md. Tests: supabase/tests/test_rls.py.

begin;

-- ---------------------------------------------------------------- types and tables
create type public.app_role as enum ('student', 'admin', 'superadmin');

create table public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  username    text not null unique check (username ~ '^[a-z0-9_]{3,32}$'),
  email       text not null,
  role        public.app_role not null default 'student',
  confirmed_at timestamptz,            -- copied from auth.users.email_confirmed_at; unconfirmed sign-ups stay out of the admin view
  created_at  timestamptz not null default now()
);

-- exactly one superadmin at most: a unique index over a constant for the superadmin rows
create unique index profiles_single_superadmin on public.profiles ((true)) where role = 'superadmin';

create table public.progress (
  user_id     uuid primary key references public.profiles (id) on delete cascade,
  data        jsonb not null default '{}'::jsonb
              check (jsonb_typeof(data) = 'object' and pg_column_size(data) < 262144),
  -- shape the pages rely on; one malformed row must not break the admin table for everyone
  constraint progress_shape check (
    (not data ? 'done'   or jsonb_typeof(data -> 'done')   = 'array') and
    (not data ? 'checks' or jsonb_typeof(data -> 'checks') = 'array') and
    (not data ? 'labs'   or jsonb_typeof(data -> 'labs')   = 'array') and
    (not data ? 'quiz'   or jsonb_typeof(data -> 'quiz')   = 'object') and
    (not data ? 'tasks'  or jsonb_typeof(data -> 'tasks')  = 'object') and
    not jsonb_path_exists(data, '$.done[*] ? (@.type() != "string")') and
    not jsonb_path_exists(data, '$.checks[*] ? (@.type() != "string")') and
    not jsonb_path_exists(data, '$.labs[*] ? (@.type() != "object")')),
  updated_at  timestamptz not null default now()
);

create table public.role_audit (
  id        bigint generated always as identity primary key,
  actor     uuid references public.profiles (id) on delete set null,
  target    uuid references public.profiles (id) on delete set null,
  old_role  public.app_role,
  new_role  public.app_role not null,
  at        timestamptz not null default now()
);

-- ---------------------------------------------------------------- helpers
-- Role of the caller. SECURITY DEFINER so policies on profiles can call it without recursion.
create function public.my_role() returns public.app_role
language sql stable security definer set search_path = '' as $$
  select p.role from public.profiles p where p.id = auth.uid()
$$;

create function public.is_staff() returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(public.my_role() in ('admin', 'superadmin'), false)
$$;

-- ---------------------------------------------------------------- signup: profile from auth metadata
-- The browser calls supabase.auth.signUp({ email, password, options: { data: { username } } }).
create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  uname text := lower(trim(coalesce(new.raw_user_meta_data ->> 'username', '')));
begin
  if uname !~ '^[a-z0-9_]{3,32}$' then
    raise exception 'username must be 3-32 characters: a-z, 0-9, _' using errcode = '22023';
  end if;
  insert into public.profiles (id, username, email, confirmed_at) values (new.id, uname, new.email, new.email_confirmed_at);
  insert into public.progress (user_id) values (new.id);
  return new;
end $$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- keep profiles.email in step when a user changes their email in Auth
create function public.handle_user_email() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.profiles set email = new.email where id = new.id;
  return new;
end $$;

create trigger on_auth_user_email after update of email on auth.users
  for each row when (old.email is distinct from new.email) execute function public.handle_user_email();

create function public.handle_user_confirmed() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.profiles set confirmed_at = new.email_confirmed_at where id = new.id;
  return new;
end $$;

create trigger on_auth_user_confirmed after update of email_confirmed_at on auth.users
  for each row when (old.email_confirmed_at is distinct from new.email_confirmed_at) execute function public.handle_user_confirmed();

create function public.touch_progress() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end $$;

create trigger progress_touch before insert or update on public.progress
  for each row execute function public.touch_progress();

-- ---------------------------------------------------------------- role management
-- Only the superadmin changes roles; never their own row; never to or from superadmin.
create function public.set_role(target uuid, new_role public.app_role) returns void
language plpgsql security definer set search_path = '' as $$
declare
  old public.app_role;
begin
  if public.my_role() is distinct from 'superadmin' then
    raise exception 'only the superadmin can change roles' using errcode = '42501';
  end if;
  if new_role = 'superadmin' then
    raise exception 'there is exactly one superadmin' using errcode = '42501';
  end if;
  select role into old from public.profiles where id = target for update;
  if not found then
    raise exception 'no such user' using errcode = 'P0002';
  end if;
  if old = 'superadmin' then
    raise exception 'the superadmin role cannot be changed' using errcode = '42501';
  end if;
  if old = new_role then
    return;
  end if;
  update public.profiles set role = new_role where id = target;
  insert into public.role_audit (actor, target, old_role, new_role) values (auth.uid(), target, old, new_role);
end $$;

-- One-time bootstrap from the SQL editor (postgres / service_role only). Requires a *confirmed* email and the
-- username the owner chose, so an attacker who pre-registered the owner's address cannot be promoted.
create function public.bootstrap_superadmin(user_email text, expected_username text) returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid; uname text; n int;
begin
  if exists (select 1 from public.profiles where role = 'superadmin') then
    raise exception 'a superadmin already exists' using errcode = '42501';
  end if;
  select count(*), min(p.id::text)::uuid, min(p.username) into n, uid, uname
    from public.profiles p join auth.users u on u.id = p.id
   where lower(u.email) = lower(user_email) and u.email_confirmed_at is not null;
  if n <> 1 then
    raise exception 'need exactly one confirmed account with this email (found %)', n using errcode = 'P0002';
  end if;
  if uname <> lower(expected_username) then
    raise exception 'this email belongs to username %, not %', uname, expected_username using errcode = '22023';
  end if;
  delete from auth.sessions where user_id = uid;   -- sessions issued before the promotion
  update public.profiles set role = 'superadmin' where id = uid;
  insert into public.role_audit (actor, target, old_role, new_role) values (null, uid, 'student', 'superadmin');
end $$;

-- ---------------------------------------------------------------- privileges
-- Supabase grants ALL on public tables to anon/authenticated by default; take that back and grant
-- only what the policies below are meant to allow.
revoke all on public.profiles, public.progress, public.role_audit from anon, authenticated;
grant select on public.profiles to authenticated;
grant update (username) on public.profiles to authenticated;
grant select, insert, update, delete on public.progress to authenticated;
grant select on public.role_audit to authenticated;

revoke all on function public.bootstrap_superadmin(text, text) from public, anon, authenticated;
revoke all on function public.handle_new_user(), public.handle_user_email(), public.handle_user_confirmed(), public.touch_progress() from public, anon, authenticated;
revoke all on function public.set_role(uuid, public.app_role) from public, anon;
grant execute on function public.set_role(uuid, public.app_role) to authenticated;
revoke all on function public.my_role(), public.is_staff() from public, anon;
grant execute on function public.my_role(), public.is_staff() to authenticated;

-- ---------------------------------------------------------------- row level security
alter table public.profiles enable row level security;
alter table public.progress enable row level security;
alter table public.role_audit enable row level security;

create policy profiles_read on public.profiles for select to authenticated
  using (id = auth.uid() or public.is_staff());
create policy profiles_rename_self on public.profiles for update to authenticated
  using (id = auth.uid()) with check (id = auth.uid());

create policy progress_read on public.progress for select to authenticated
  using (user_id = auth.uid() or public.is_staff());
create policy progress_insert_own on public.progress for insert to authenticated
  with check (user_id = auth.uid());
create policy progress_update_own on public.progress for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy progress_delete_own on public.progress for delete to authenticated
  using (user_id = auth.uid());

create policy role_audit_staff on public.role_audit for select to authenticated
  using (public.is_staff());

-- ---------------------------------------------------------------- admin view (RLS of both tables applies)
create view public.student_progress with (security_invoker = true) as
  select p.id, p.username, p.email, p.role, p.created_at, g.data, g.updated_at
  from public.profiles p left join public.progress g on g.user_id = p.id
  where p.confirmed_at is not null;

revoke all on public.student_progress from anon, authenticated;
grant select on public.student_progress to authenticated;

commit;
