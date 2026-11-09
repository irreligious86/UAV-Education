"""Shared fixtures for the database tests: a fresh database from the Supabase stub plus every migration."""
import json
import os
import pathlib
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ADMIN_DSN = os.environ.get("PG_DSN", "host=/tmp/pgt port=54329 user=postgres")
DB = "uav_rls_test"


def _role_exists(c, name):
    return c.execute("select 1 from pg_roles where rolname = %s", (name,)).fetchone() is not None


@pytest.fixture(scope="session")
def dsn():
    with psycopg.connect(ADMIN_DSN + " dbname=postgres", autocommit=True) as c:
        c.execute(f"drop database if exists {DB} with (force)")
        c.execute(f"create database {DB}")
    d = f"{ADMIN_DSN} dbname={DB}"
    with psycopg.connect(d, autocommit=True) as c:
        stub = (ROOT / "supabase/tests/supabase_stub.sql").read_text()
        if _role_exists(c, "anon"):                       # roles are cluster-wide
            stub = "\n".join(l for l in stub.splitlines() if not l.startswith("create role"))
        c.execute(stub)
        for mig in sorted((ROOT / "supabase/migrations").glob("*.sql")):
            c.execute(mig.read_text())
    return d


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


def savepoint_raises(db, exc, sql, params=()):
    with pytest.raises(exc):
        with db.transaction():
            db.execute(sql, params)


@pytest.fixture()
def users(db):
    """Three students, one admin, the superadmin."""
    u = {name: signup(db, name) for name in ("alice", "bob", "carol", "adam", "boss")}
    db.execute("update public.profiles set role = 'admin' where id = %s", (u["adam"],))
    db.execute("select public.bootstrap_superadmin('boss@example.org', 'boss')")
    db.execute("update public.progress set data = %s where user_id = %s", (json.dumps({"quiz": {"f-power": {"correct": 7, "total": 8}}}), u["bob"]))
    return u
