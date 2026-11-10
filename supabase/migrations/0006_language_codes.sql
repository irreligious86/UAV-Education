-- UAV Student: language codes with a variant subtag (docs/I18N.md). 0005 allowed "xx" and "xx-YY" only;
-- the course now also has dialects such as "uk-galych" (BCP 47 variant subtag, 5-8 letters/digits).
-- Tests: supabase/tests/test_language.py.

begin;

alter table public.profiles drop constraint profiles_lang_check;
alter table public.profiles
  add constraint profiles_lang_check check (lang ~ '^[a-z]{2,3}(-[A-Z]{2})?(-[a-z0-9]{5,8})?$');

commit;
