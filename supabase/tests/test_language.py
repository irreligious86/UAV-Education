"""Account language (supabase/migrations/0005_profile_language.sql): the owner sets it, nobody else can,
and it stays a short language code."""
import pytest
from psycopg import errors

from conftest import act, savepoint_raises


def test_owner_sets_own_language(db, users):
    act(db, users["alice"])
    assert db.execute("select lang from public.profiles where id = %s", (users["alice"],)).fetchone() == (None,)
    assert db.execute("update public.profiles set lang = 'uk' where id = %s", (users["alice"],)).rowcount == 1
    assert db.execute("select lang from public.profiles where id = %s", (users["alice"],)).fetchone() == ("uk",)


@pytest.mark.parametrize("who", ["bob", "adam", "boss"])
def test_nobody_sets_someone_elses_language(db, users, who):
    act(db, users[who])
    assert db.execute("update public.profiles set lang = 'en' where id = %s", (users["alice"],)).rowcount == 0


@pytest.mark.parametrize("good", ["en", "uk", "pt-BR", "uk-galych"])
def test_language_code_accepts_variants(db, users, good):
    act(db, users["alice"])
    assert db.execute("update public.profiles set lang = %s where id = %s", (good, users["alice"])).rowcount == 1


@pytest.mark.parametrize("bad", ["ukrainian", "U", "uk; drop", "", "UK", "uk-ga", "uk-galych-x", "uk-Galych"])
def test_language_code_shape(db, users, bad):
    act(db, users["alice"])
    savepoint_raises(db, errors.CheckViolation, "update public.profiles set lang = %s where id = %s", (bad, users["alice"]))


def test_language_update_does_not_open_other_columns(db, users):
    act(db, users["alice"])
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.profiles set lang = 'en', role = 'admin' where id = %s", (users["alice"],))


def test_anon_cannot_read_or_set_language(db, users):
    db.execute("set local role anon")
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.profiles set lang = 'en'")
