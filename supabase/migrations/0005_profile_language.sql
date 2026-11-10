-- UAV Student: the interface language of an account (docs/I18N.md).
-- A guest's language lives in the browser (localStorage "uav-lang"); a signed-in account's language is this
-- column: assets/account.js applies it on every device after login and the header switcher writes it here.
-- NULL means "not chosen yet": the first switch (or the language of the page at first login) fills it.
-- Tests: supabase/tests/test_language.py.

begin;

alter table public.profiles
  add column lang text check (lang ~ '^[a-z]{2}(-[A-Z]{2})?$');

-- the owner may change only their username and their language (RLS profiles_rename_self limits rows to their own)
grant update (lang) on public.profiles to authenticated;

commit;
