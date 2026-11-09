"""Races that need committed data and several connections (review 2026-11-09, H1). Runs last (file name) and
removes everything it committed, so the rolled-back tests never see these rows."""
import json
import threading
import time

import psycopg
import pytest

from conftest import act, signup


@pytest.fixture()
def race(dsn):
    made = {"users": [], "exams": []}

    def setup(tag, attempts=1, n=6, per=3):
        with psycopg.connect(dsn, autocommit=True) as c:
            stu, adm = signup(c, f"stu_{tag}"), signup(c, f"adm_{tag}")
            made["users"] += [stu, adm]
            c.execute("update public.profiles set role = 'admin' where id = %s", (adm,))
            act(c, adm)
            eid = c.execute("""insert into public.exams (title, questions_per_attempt, attempts_allowed, published, pass_pct)
                               values ('race exam', %s, %s, true, 60) returning id""", (per, attempts)).fetchone()[0]
            for i in range(n):
                c.execute("insert into public.exam_questions (exam_id, q, options, answer) values (%s, %s, %s, %s)",
                          (eid, f"Q{i}?", json.dumps(["a", "b", "c"]), i % 3))
            made["exams"].append(eid)
        return stu, eid

    yield setup
    with psycopg.connect(dsn, autocommit=True) as c:
        for u in made["users"]:
            c.execute("delete from auth.users where id = %s", (u,))       # cascades to profiles and attempts
        for e in made["exams"]:
            c.execute("delete from public.exams where id = %s", (e,))


def count(dsn, eid):
    with psycopg.connect(dsn, autocommit=True) as c:
        return c.execute("select count(*) from public.exam_attempts where exam_id = %s", (eid,)).fetchone()[0]


def test_second_exam_start_waits_and_resumes(dsn, race):
    stu, eid = race("two")
    c1, c2 = psycopg.connect(dsn), psycopg.connect(dsn)
    try:
        act(c1, stu); act(c2, stu)
        a1 = c1.execute("select public.exam_start(%s)", (eid,)).fetchone()[0]      # not committed yet
        out = []
        t = threading.Thread(target=lambda: out.append(c2.execute("select public.exam_start(%s)", (eid,)).fetchone()[0]))
        t.start(); time.sleep(0.5)
        assert t.is_alive(), "the second call must wait for the first"
        c1.commit(); t.join(10); c2.commit()
        assert out and out[0]["attempt"] == a1["attempt"]
        assert count(dsn, eid) == 1
    finally:
        c1.close(); c2.close()


def test_parallel_exam_start_stores_one_attempt(dsn, race):
    stu, eid = race("many")
    barrier, ids = threading.Barrier(8), []

    def go():
        with psycopg.connect(dsn) as c:
            act(c, stu); barrier.wait()
            ids.append(c.execute("select public.exam_start(%s)", (eid,)).fetchone()[0]["attempt"]); c.commit()

    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]; [t.join(20) for t in ts]
    assert len(ids) == 8 and len(set(ids)) == 1
    assert count(dsn, eid) == 1


def test_concurrent_submit_only_one_wins(dsn, race):
    stu, eid = race("submit")
    with psycopg.connect(dsn) as c:
        act(c, stu); a = c.execute("select public.exam_start(%s)", (eid,)).fetchone()[0]; c.commit()
    c1, c2 = psycopg.connect(dsn), psycopg.connect(dsn)
    try:
        act(c1, stu); act(c2, stu)
        c1.execute("select public.exam_submit(%s, '{}')", (a["attempt"],))
        err = []

        def second():
            try:
                c2.execute("select public.exam_submit(%s, '{}')", (a["attempt"],)); c2.commit()
            except psycopg.Error as e:
                err.append(type(e).__name__); c2.rollback()

        t = threading.Thread(target=second); t.start(); time.sleep(0.5)
        assert t.is_alive()
        c1.commit(); t.join(10)
        assert err == ["InsufficientPrivilege"]
    finally:
        c1.close(); c2.close()
