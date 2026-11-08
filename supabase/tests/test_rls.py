"""Access rules of supabase/migrations/0001_accounts_roles_progress.sql, tested on real Postgres.

Every cell of the access table in docs/MULTIUSER-PLAN.md has a test here. The database is created
fresh for the session from supabase_stub.sql (what Supabase provides) plus the migration.

Run: PG_DSN="host=/tmp/pgt port=54329 user=postgres" python -m pytest -q supabase/tests
(defaults to the local socket above; CI points PG_DSN at a postgres service container).
"""
import json
import os
import pathlib
import uuid

import psycopg
import pytest
from psycopg import errors

ROOT = pathlib.Path(__file__).resolve().parents[2]
ADMIN_DSN = os.environ.get("PG_DSN", "host=/tmp/pgt port=54329 user=postgres")
DB = "uav_rls_test"


@pytest.fixture(scope="session")
def dsn():
    with psycopg.connect(ADMIN_DSN + " dbname=postgres", autocommit=True) as c:
        c.execute(f"drop database if exists {DB} with (force)")
        c.execute(f"create database {DB}")
    d = f"{ADMIN_DSN} dbname={DB}"
    with psycopg.connect(d, autocommit=True) as c:
        for role in ("anon", "authenticated", "service_role"):     # roles are cluster-wide
            c.execute(f"drop owned by {role}") if _role_exists(c, role) else None
        stub = (ROOT / "supabase/tests/supabase_stub.sql").read_text()
        if _role_exists(c, "anon"):
            stub = "\n".join(l for l in stub.splitlines() if not l.startswith("create role"))
        c.execute(stub)
        c.execute((ROOT / "supabase/migrations/0001_accounts_roles_progress.sql").read_text())
    return d


def _role_exists(c, name):
    return c.execute("select 1 from pg_roles where rolname = %s", (name,)).fetchone() is not None


@pytest.fixture()
def db(dsn):
    """Connection as postgres; every test runs in a transaction that is rolled back."""
    with psycopg.connect(dsn) as c:
        yield c
        c.rollback()


def signup(db, username, email=None, confirmed=True):
    uid = uuid.uuid4()
    db.execute("insert into auth.users (id, email, raw_user_meta_data) values (%s, %s, %s)",
               (uid, email or f"{username.lower()}@example.org", json.dumps({"username": username})))
    if confirmed:   # Supabase sets email_confirmed_at when the user clicks the link (an UPDATE after the insert)
        db.execute("update auth.users set email_confirmed_at = now() where id = %s", (uid,))
    return uid


def act(db, uid):
    """Switch the transaction to the API role of a logged-in user (as PostgREST does)."""
    db.execute("set local role authenticated")
    db.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps({"sub": str(uid), "role": "authenticated"}),))


def as_postgres(db):
    db.execute("reset role")
    db.execute("select set_config('request.jwt.claims', '', true)")


@pytest.fixture()
def users(db):
    """Three students, one admin, the superadmin."""
    u = {name: signup(db, name) for name in ("alice", "bob", "carol", "adam", "boss")}
    db.execute("update public.profiles set role = 'admin' where id = %s", (u["adam"],))
    db.execute("select public.bootstrap_superadmin('boss@example.org', 'boss')")
    db.execute("update public.progress set data = %s where user_id = %s", (json.dumps({"quiz": {"f-power": {"correct": 7, "total": 8}}}), u["bob"]))
    return u


def savepoint_raises(db, exc, sql, params=()):
    with pytest.raises(exc):
        with db.transaction():
            db.execute(sql, params)


# ------------------------------------------------------------------ signup
def test_signup_creates_profile_and_progress(db):
    uid = signup(db, "Alex_86", "Alex@Example.org")
    row = db.execute("select username, email, role from public.profiles where id = %s", (uid,)).fetchone()
    assert row == ("alex_86", "Alex@Example.org", "student")
    assert db.execute("select data from public.progress where user_id = %s", (uid,)).fetchone() == ({},)


@pytest.mark.parametrize("bad", ["ab", "with space", "dash-name", "x" * 33, ""])
def test_signup_rejects_bad_username(db, bad):
    savepoint_raises(db, errors.InvalidParameterValue, "insert into auth.users (email, raw_user_meta_data) values (%s, %s)",
                     ("x@example.org", json.dumps({"username": bad})))


def test_signup_rejects_duplicate_username(db):
    signup(db, "dupe", "one@example.org")
    savepoint_raises(db, errors.UniqueViolation, "insert into auth.users (email, raw_user_meta_data) values (%s, %s)",
                     ("two@example.org", json.dumps({"username": "DUPE"})))


def test_email_change_follows_auth(db):
    uid = signup(db, "mover", "old@example.org")
    db.execute("update auth.users set email = 'new@example.org' where id = %s", (uid,))
    assert db.execute("select email from public.profiles where id = %s", (uid,)).fetchone() == ("new@example.org",)


# ------------------------------------------------------------------ anon
def test_anon_sees_nothing(db, users):
    db.execute("set local role anon")
    for table in ("public.profiles", "public.progress", "public.role_audit", "public.student_progress"):
        savepoint_raises(db, errors.InsufficientPrivilege, f"select * from {table}")


# ------------------------------------------------------------------ student
def test_student_reads_only_own_rows(db, users):
    act(db, users["alice"])
    assert db.execute("select count(*) from public.profiles").fetchone() == (1,)
    assert db.execute("select username from public.profiles").fetchone() == ("alice",)
    assert db.execute("select count(*) from public.progress").fetchone() == (1,)
    assert db.execute("select count(*) from public.student_progress").fetchone() == (1,)
    assert db.execute("select count(*) from public.role_audit").fetchone() == (0,)


def test_student_cannot_see_others_grades(db, users):
    act(db, users["alice"])
    assert db.execute("select data from public.progress where user_id = %s", (users["bob"],)).fetchall() == []


def test_student_writes_own_progress(db, users):
    act(db, users["alice"])
    data = {"done": ["f-physics"], "quiz": {"f-physics": {"correct": 8, "total": 8}}}
    n = db.execute("update public.progress set data = %s where user_id = %s", (json.dumps(data), users["alice"])).rowcount
    assert n == 1
    assert db.execute("select data from public.progress").fetchone() == (data,)


def test_student_cannot_write_others_progress(db, users):
    act(db, users["alice"])
    n = db.execute("update public.progress set data = '{\"done\": [\"all\"]}' where user_id = %s", (users["bob"],)).rowcount
    assert n == 0
    savepoint_raises(db, errors.InsufficientPrivilege, "insert into public.progress (user_id, data) values (%s, '{}')", (users["carol"],))
    n = db.execute("delete from public.progress where user_id = %s", (users["bob"],)).rowcount
    assert n == 0


def test_student_cannot_move_own_row_to_someone_else(db, users):
    act(db, users["alice"])
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.progress set user_id = %s where user_id = %s", (users["carol"], users["alice"]))


def test_student_cannot_change_role_or_email(db, users):
    act(db, users["alice"])
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.profiles set role = 'admin' where id = %s", (users["alice"],))
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.profiles set email = 'x@y.z' where id = %s", (users["alice"],))
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.set_role(%s, 'admin')", (users["alice"],))


def test_student_renames_self_only(db, users):
    act(db, users["alice"])
    assert db.execute("update public.profiles set username = 'alice2' where id = %s", (users["alice"],)).rowcount == 1
    assert db.execute("update public.profiles set username = 'hacked' where id = %s", (users["bob"],)).rowcount == 0


def test_student_cannot_bootstrap(db, users):
    act(db, users["alice"])
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.bootstrap_superadmin('alice@example.org', 'alice')")


def test_progress_must_be_object_and_bounded(db, users):
    act(db, users["alice"])
    savepoint_raises(db, errors.CheckViolation, "update public.progress set data = '[1,2]' where user_id = %s", (users["alice"],))
    big = json.dumps({"x": "a" * 400_000})
    savepoint_raises(db, errors.CheckViolation, "update public.progress set data = %s where user_id = %s", (big, users["alice"]))


# ------------------------------------------------------------------ admin
def test_admin_reads_everyone(db, users):
    act(db, users["adam"])
    assert db.execute("select count(*) from public.profiles").fetchone() == (5,)
    assert db.execute("select count(*) from public.progress").fetchone() == (5,)
    row = db.execute("select data from public.student_progress where username = 'bob'").fetchone()
    assert row[0]["quiz"]["f-power"]["correct"] == 7
    assert db.execute("select count(*) from public.role_audit").fetchone()[0] >= 1


def test_admin_cannot_change_grades(db, users):
    act(db, users["adam"])
    assert db.execute("update public.progress set data = '{}' where user_id = %s", (users["bob"],)).rowcount == 0
    assert db.execute("delete from public.progress where user_id = %s", (users["bob"],)).rowcount == 0


def test_admin_cannot_change_roles(db, users):
    act(db, users["adam"])
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.set_role(%s, 'admin')", (users["alice"],))
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.profiles set role = 'student' where id = %s", (users["adam"],))


def test_admin_cannot_rename_others(db, users):
    act(db, users["adam"])
    assert db.execute("update public.profiles set username = 'x_bob' where id = %s", (users["bob"],)).rowcount == 0


# ------------------------------------------------------------------ superadmin
def test_superadmin_promotes_and_demotes_with_audit(db, users):
    act(db, users["boss"])
    db.execute("select public.set_role(%s, 'admin')", (users["alice"],))
    db.execute("select public.set_role(%s, 'student')", (users["adam"],))
    rows = db.execute("select username, role from public.profiles where username in ('alice', 'adam') order by username").fetchall()
    assert rows == [("adam", "student"), ("alice", "admin")]
    audit = db.execute("select old_role, new_role from public.role_audit where actor = %s order by id", (users["boss"],)).fetchall()
    assert audit == [("student", "admin"), ("admin", "student")]


def test_promoted_admin_gains_read_access(db, users):
    act(db, users["boss"])
    db.execute("select public.set_role(%s, 'admin')", (users["carol"],))
    act(db, users["carol"])
    assert db.execute("select count(*) from public.progress").fetchone() == (5,)


def test_there_is_only_one_superadmin(db, users):
    act(db, users["boss"])
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.set_role(%s, 'superadmin')", (users["alice"],))
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.set_role(%s, 'student')", (users["boss"],))
    as_postgres(db)
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.bootstrap_superadmin('alice@example.org', 'alice')")
    savepoint_raises(db, errors.UniqueViolation, "update public.profiles set role = 'superadmin' where id = %s", (users["alice"],))


def test_superadmin_cannot_edit_grades_either(db, users):
    act(db, users["boss"])
    assert db.execute("update public.progress set data = '{}' where user_id = %s", (users["bob"],)).rowcount == 0


def test_set_role_unknown_user(db, users):
    act(db, users["boss"])
    savepoint_raises(db, errors.NoDataFound, "select public.set_role(%s, 'admin')", (uuid.uuid4(),))


def test_bootstrap_requires_registered_email(db):
    savepoint_raises(db, errors.NoDataFound, "select public.bootstrap_superadmin('nobody@example.org', 'nobody')")


def test_my_role_reports_caller(db, users):
    for name, role in (("alice", "student"), ("adam", "admin"), ("boss", "superadmin")):
        act(db, users[name])
        assert db.execute("select public.my_role()").fetchone() == (role,)
    db.execute("set local role anon")
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.my_role()")


# ------------------------------------------------------------------ blanket guards
def test_anon_has_no_function_or_table_access(db):
    fns = db.execute("""select proname from pg_proc where pronamespace = 'public'::regnamespace
                        and has_function_privilege('anon', oid, 'execute')""").fetchall()
    assert fns == []
    rels = db.execute("""select relname from pg_class where relnamespace = 'public'::regnamespace and relkind in ('r', 'v')
                         and (has_table_privilege('anon', oid, 'select') or has_table_privilege('anon', oid, 'insert')
                              or has_table_privilege('anon', oid, 'update') or has_table_privilege('anon', oid, 'delete'))""").fetchall()
    assert rels == []


def test_every_public_table_has_rls(db):
    rows = db.execute("""select relname from pg_class where relnamespace = 'public'::regnamespace
                         and relkind = 'r' and not relrowsecurity""").fetchall()
    assert rows == []


def test_security_definer_functions_pin_search_path(db):
    rows = db.execute("""select proname from pg_proc where pronamespace = 'public'::regnamespace and prosecdef
                         and not coalesce(proconfig::text like '%search_path=%', false)""").fetchall()
    assert rows == []


# ------------------------------------------------------------------ findings of the 2026-11-09 security review
def test_bootstrap_refuses_unconfirmed_preregistration(db):
    """M1: an attacker signs up with the owner's address before the owner does."""
    signup(db, "evil_owner", "owner@example.org", confirmed=False)
    savepoint_raises(db, errors.NoDataFound, "select public.bootstrap_superadmin('owner@example.org', 'evil_owner')")
    assert db.execute("select count(*) from public.profiles where role = 'superadmin'").fetchone() == (0,)


def test_bootstrap_requires_the_expected_username(db):
    signup(db, "evil_owner", "owner@example.org")
    savepoint_raises(db, errors.InvalidParameterValue, "select public.bootstrap_superadmin('owner@example.org', 'alex')")
    db.execute("select public.bootstrap_superadmin('owner@example.org', 'EVIL_OWNER')")   # case-insensitive match is fine


def test_bootstrap_drops_old_sessions(db):
    uid = signup(db, "owner", "owner@example.org")
    db.execute("insert into auth.sessions (user_id) values (%s), (%s)", (uid, uid))
    db.execute("select public.bootstrap_superadmin('owner@example.org', 'owner')")
    assert db.execute("select count(*) from auth.sessions where user_id = %s", (uid,)).fetchone() == (0,)


@pytest.mark.parametrize("bad", ['{"done": 1}', '{"labs": {}}', '{"labs": [null]}', '{"checks": true}',
                                 '{"quiz": []}', '{"tasks": "x"}', '{"done": [1]}', '{"labs": ["x"]}'])
def test_progress_shape_enforced(db, users, bad):
    """M2: one malformed row must not break the admin table."""
    act(db, users["alice"])
    savepoint_raises(db, errors.CheckViolation, "update public.progress set data = %s where user_id = %s", (bad, users["alice"]))


def test_unconfirmed_signups_hidden_from_admin_view(db, users):
    """L1: unverified addresses do not appear as students."""
    ghost = signup(db, "teacher_official", "victim@example.org", confirmed=False)
    act(db, users["adam"])
    names = [r[0] for r in db.execute("select username from public.student_progress").fetchall()]
    assert "teacher_official" not in names and len(names) == 5
    as_postgres(db)
    db.execute("update auth.users set email_confirmed_at = now() where id = %s", (ghost,))
    act(db, users["adam"])
    assert db.execute("select count(*) from public.student_progress").fetchone() == (6,)


def test_updated_at_cannot_be_forged(db, users):
    """L2: delete + insert with a future timestamp."""
    act(db, users["alice"])
    db.execute("delete from public.progress where user_id = %s", (users["alice"],))
    db.execute("insert into public.progress (user_id, data, updated_at) values (%s, '{}', '2099-01-01')", (users["alice"],))
    year = db.execute("select extract(year from updated_at) from public.progress where user_id = %s", (users["alice"],)).fetchone()[0]
    assert year < 2099


# ------------------------------------------------------------------ accounts are created only by their owners
@pytest.mark.parametrize("who", ["alice", "adam", "boss"])
def test_nobody_creates_accounts_for_others(db, users, who):
    """Only self-registration creates accounts; staff (even the superadmin) cannot insert users or profiles."""
    act(db, users[who])
    savepoint_raises(db, errors.InsufficientPrivilege,
                     "insert into public.profiles (id, username, email) values (gen_random_uuid(), 'made_by_staff', 'x@example.org')")
    savepoint_raises(db, errors.InsufficientPrivilege,
                     "insert into auth.users (email, raw_user_meta_data) values ('y@example.org', '{\"username\": \"made_by_staff\"}')")
    savepoint_raises(db, errors.InsufficientPrivilege, "delete from public.profiles where id = %s", (users["bob"],))


def test_superadmin_makes_admins_only_from_registered_users(db, users):
    act(db, users["boss"])
    savepoint_raises(db, errors.NoDataFound, "select public.set_role(%s, 'admin')", (uuid.uuid4(),))
    db.execute("select public.set_role(%s, 'admin')", (users["carol"],))
    assert db.execute("select role from public.profiles where id = %s", (users["carol"],)).fetchone() == ("admin",)
