-- UAV Student: cohorts (study groups). Staff create groups and put students in them; the admin page filters
-- grades and exports CSV per group. The access matrix does not change: staff already see every student,
-- a student sees only the groups they belong to (names, not the other members).
-- Design: docs/MULTIUSER-PLAN.md, section 12. Tests: supabase/tests/test_cohorts.py.

begin;

create table public.cohorts (
  id          uuid primary key default gen_random_uuid(),
  name        text not null check (length(btrim(name)) between 2 and 100),
  created_by  uuid references public.profiles (id) on delete set null default auth.uid(),
  created_at  timestamptz not null default now()
);
create unique index cohorts_name_unique on public.cohorts (lower(btrim(name)));

create table public.cohort_members (
  cohort_id  uuid not null references public.cohorts (id) on delete cascade,
  user_id    uuid not null references public.profiles (id) on delete cascade,
  added_by   uuid references public.profiles (id) on delete set null default auth.uid(),
  added_at   timestamptz not null default now(),
  primary key (cohort_id, user_id)
);
create index cohort_members_user on public.cohort_members (user_id);

-- Who added whom is recorded by the database, not taken from the client.
create function public.stamp_cohort_member() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.added_by := auth.uid();
  new.added_at := now();
  return new;
end $$;
create trigger cohort_members_stamp before insert on public.cohort_members
  for each row execute function public.stamp_cohort_member();

create function public.stamp_cohort() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'INSERT' then
    new.created_by := auth.uid();
    new.created_at := now();
  else
    new.created_by := old.created_by;
    new.created_at := old.created_at;
  end if;
  return new;
end $$;
create trigger cohorts_stamp before insert or update on public.cohorts
  for each row execute function public.stamp_cohort();

-- ---------------------------------------------------------------- privileges and RLS
revoke all on public.cohorts, public.cohort_members from anon, authenticated;
grant select, insert, delete on public.cohorts to authenticated;          -- RLS: writes by staff only
grant update (name) on public.cohorts to authenticated;                   -- rename only
grant select, insert, delete on public.cohort_members to authenticated;   -- RLS: writes by staff only
revoke all on function public.stamp_cohort_member(), public.stamp_cohort() from public, anon, authenticated;

alter table public.cohorts enable row level security;
alter table public.cohort_members enable row level security;

create policy cohorts_read on public.cohorts for select to authenticated
  using (public.is_staff() or exists (select 1 from public.cohort_members m where m.cohort_id = cohorts.id and m.user_id = auth.uid()));
create policy cohorts_staff_insert on public.cohorts for insert to authenticated with check (public.is_staff());
create policy cohorts_staff_update on public.cohorts for update to authenticated using (public.is_staff()) with check (public.is_staff());
create policy cohorts_staff_delete on public.cohorts for delete to authenticated using (public.is_staff());

create policy cohort_members_read on public.cohort_members for select to authenticated
  using (user_id = auth.uid() or public.is_staff());
create policy cohort_members_staff_insert on public.cohort_members for insert to authenticated with check (public.is_staff());
create policy cohort_members_staff_delete on public.cohort_members for delete to authenticated using (public.is_staff());

commit;
