"""Exams with private banks (supabase/migrations/0002_exams.sql): answers never reach students, only the
database grades, nobody writes scores directly."""
import json
import uuid

import pytest
from psycopg import errors

from conftest import act, as_postgres, savepoint_raises, signup


def make_exam(db, staff_uid, n=5, per_attempt=3, attempts=1, published=True, minutes=20, show_review=True):
    act(db, staff_uid)
    eid = db.execute("""insert into public.exams (title, pass_pct, questions_per_attempt, time_limit_min,
                        attempts_allowed, published, show_review)
                        values ('Final: power', 60, %s, %s, %s, %s, %s) returning id""",
                     (per_attempt, minutes, attempts, published, show_review)).fetchone()[0]
    for i in range(n):
        db.execute("insert into public.exam_questions (exam_id, q, options, answer, explain) values (%s, %s, %s, %s, %s)",
                   (eid, f"Question {i}?", json.dumps([f"a{i}", f"b{i}", f"c{i}"]), i % 3, f"because {i}"))
    as_postgres(db)
    return eid


def start(db, uid, eid):
    act(db, uid)
    return db.execute("select public.exam_start(%s)", (eid,)).fetchone()[0]


def answer_key(db, attempt):
    """What the database knows (test helper, run as postgres)."""
    as_postgres(db)
    rows = db.execute("""select q.id, q.answer from public.exam_attempts a
                         join public.exam_questions q on q.id = any (a.question_ids) where a.id = %s""", (attempt,)).fetchall()
    return {str(i): a for i, a in rows}


# ------------------------------------------------------------------ answers stay in the database
def test_student_cannot_read_the_bank(db, users):
    eid = make_exam(db, users["adam"])
    act(db, users["alice"])
    assert db.execute("select count(*) from public.exam_questions").fetchone() == (0,)
    assert db.execute("select count(*) from public.exams where id = %s", (eid,)).fetchone() == (1,)


def test_exam_start_returns_questions_without_answers(db, users):
    eid = make_exam(db, users["adam"], n=5, per_attempt=3)
    r = start(db, users["alice"], eid)
    assert len(r["questions"]) == 3
    for q in r["questions"]:
        assert set(q) == {"id", "q", "options"}
    assert "answer" not in json.dumps(r) and "explain" not in json.dumps(r)


def test_resume_returns_same_attempt(db, users):
    eid = make_exam(db, users["adam"])
    a = start(db, users["alice"], eid)
    b = start(db, users["alice"], eid)
    assert a["attempt"] == b["attempt"] and [q["id"] for q in a["questions"]] == [q["id"] for q in b["questions"]]


# ------------------------------------------------------------------ grading happens only in the database
def test_submit_grades_and_records(db, users):
    eid = make_exam(db, users["adam"], n=5, per_attempt=5)
    r = start(db, users["alice"], eid)
    key = answer_key(db, r["attempt"])
    answers = dict(key); first = next(iter(answers)); answers[first] = (answers[first] + 1) % 3   # one wrong
    act(db, users["alice"])
    res = db.execute("select public.exam_submit(%s, %s)", (r["attempt"], json.dumps(answers))).fetchone()[0]
    assert (res["correct"], res["total"], res["score_pct"], res["passed"]) == (4, 5, 80, True)
    assert len(res["review"]) == 5
    row = db.execute("select correct, score_pct, passed from public.exam_results where id = %s", (r["attempt"],)).fetchone()
    assert row == (4, 80, True)


def test_review_hidden_when_disabled(db, users):
    eid = make_exam(db, users["adam"], show_review=False)
    r = start(db, users["alice"], eid)
    res = db.execute("select public.exam_submit(%s, '{}')", (r["attempt"],)).fetchone()[0]
    assert res["review"] is None and res["correct"] == 0


def test_no_second_submission(db, users):
    eid = make_exam(db, users["adam"])
    r = start(db, users["alice"], eid)
    db.execute("select public.exam_submit(%s, '{}')", (r["attempt"],))
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.exam_submit(%s, '{}')", (r["attempt"],))


def test_deadline_enforced(db, users):
    eid = make_exam(db, users["adam"])
    r = start(db, users["alice"], eid)
    as_postgres(db)
    db.execute("update public.exam_attempts set deadline = now() - interval '1 minute' where id = %s", (r["attempt"],))
    act(db, users["alice"])
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.exam_submit(%s, '{}')", (r["attempt"],))


def test_attempt_limit(db, users):
    eid = make_exam(db, users["adam"], attempts=1)
    r = start(db, users["alice"], eid)
    db.execute("select public.exam_submit(%s, '{}')", (r["attempt"],))
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.exam_start(%s)", (eid,))


def test_expired_unsubmitted_attempt_counts(db, users):
    eid = make_exam(db, users["adam"], attempts=1)
    r = start(db, users["alice"], eid)
    as_postgres(db)
    db.execute("update public.exam_attempts set deadline = now() - interval '1 minute' where id = %s", (r["attempt"],))
    act(db, users["alice"])
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.exam_start(%s)", (eid,))


@pytest.mark.parametrize("who", ["alice", "adam", "boss"])
def test_nobody_writes_attempts_directly(db, users, who):
    eid = make_exam(db, users["adam"])
    r = start(db, users["alice"], eid)
    act(db, users[who])
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.exam_attempts set score_pct = 100, passed = true where id = %s", (r["attempt"],))
    savepoint_raises(db, errors.InsufficientPrivilege,
                     "insert into public.exam_attempts (exam_id, user_id, deadline, question_ids, score_pct, passed) values (%s, %s, now(), '{}', 100, true)",
                     (eid, users[who]))
    savepoint_raises(db, errors.InsufficientPrivilege, "delete from public.exam_attempts where id = %s", (r["attempt"],))


def test_cannot_submit_someone_elses_attempt(db, users):
    eid = make_exam(db, users["adam"])
    r = start(db, users["alice"], eid)
    act(db, users["bob"])
    savepoint_raises(db, errors.NoDataFound, "select public.exam_submit(%s, '{}')", (r["attempt"],))


def test_malformed_answers_rejected(db, users):
    eid = make_exam(db, users["adam"])
    r = start(db, users["alice"], eid)
    savepoint_raises(db, errors.InvalidParameterValue, "select public.exam_submit(%s, '[1,2]')", (r["attempt"],))
    res = db.execute("select public.exam_submit(%s, %s)", (r["attempt"], json.dumps({"x": "y", "99999": 1}))).fetchone()[0]
    assert res["correct"] == 0


# ------------------------------------------------------------------ visibility
def test_unpublished_exam_invisible_and_closed(db, users):
    eid = make_exam(db, users["adam"], published=False)
    act(db, users["alice"])
    assert db.execute("select count(*) from public.exams").fetchone() == (0,)
    savepoint_raises(db, errors.NoDataFound, "select public.exam_start(%s)", (eid,))


def test_exam_window(db, users):
    eid = make_exam(db, users["adam"])
    as_postgres(db)
    db.execute("update public.exams set opens_at = now() + interval '1 day' where id = %s", (eid,))
    act(db, users["alice"])
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.exam_start(%s)", (eid,))


def test_unconfirmed_account_cannot_take_exams(db, users):
    eid = make_exam(db, users["adam"])
    ghost = signup(db, "ghost_user", confirmed=False)
    act(db, ghost)
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.exam_start(%s)", (eid,))


def test_students_see_only_own_results_staff_see_all(db, users):
    eid = make_exam(db, users["adam"], n=3, per_attempt=3)
    for who in ("alice", "bob"):
        r = start(db, users[who], eid)
        db.execute("select public.exam_submit(%s, '{}')", (r["attempt"],))
    act(db, users["alice"])
    assert [r[0] for r in db.execute("select username from public.exam_results").fetchall()] == ["alice"]
    act(db, users["adam"])
    assert db.execute("select count(*) from public.exam_results").fetchone() == (2,)


# ------------------------------------------------------------------ staff
def test_students_cannot_create_or_edit_exams(db, users):
    eid = make_exam(db, users["adam"])
    act(db, users["alice"])
    savepoint_raises(db, errors.InsufficientPrivilege, "insert into public.exams (title) values ('fake exam')")
    assert db.execute("update public.exams set pass_pct = 1 where id = %s", (eid,)).rowcount == 0
    savepoint_raises(db, errors.InsufficientPrivilege,
                     "insert into public.exam_questions (exam_id, q, options, answer) values (%s, 'q??', '[\"a\",\"b\"]', 0)", (eid,))


def test_bank_frozen_after_first_attempt(db, users):
    eid = make_exam(db, users["adam"])
    start(db, users["alice"], eid)
    act(db, users["adam"])
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.exam_questions set answer = 0 where exam_id = %s", (eid,))
    savepoint_raises(db, errors.InsufficientPrivilege, "delete from public.exams where id = %s", (eid,))


def test_bank_shape_validated(db, users):
    act(db, users["adam"])
    eid = db.execute("insert into public.exams (title) values ('shape test') returning id").fetchone()[0]
    savepoint_raises(db, errors.CheckViolation,
                     "insert into public.exam_questions (exam_id, q, options, answer) values (%s, 'q one', '[\"a\",\"b\"]', 2)", (eid,))
    savepoint_raises(db, errors.CheckViolation,
                     "insert into public.exam_questions (exam_id, q, options, answer) values (%s, 'q one', '[\"a\", 1]', 0)", (eid,))


def test_anon_has_no_exam_access(db, users):
    make_exam(db, users["adam"])
    db.execute("set local role anon")
    for t in ("public.exams", "public.exam_questions", "public.exam_attempts", "public.exam_results"):
        savepoint_raises(db, errors.InsufficientPrivilege, f"select * from {t}")
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.exam_start(%s)", (uuid.uuid4(),))


# ------------------------------------------------------------------ review 2026-11-09 (migration 0004)
def test_question_cannot_leave_a_frozen_bank(db, users):
    """M1: moving questions to an unused exam used to dodge the freeze and regrade running attempts."""
    eid = make_exam(db, users["adam"], n=2, per_attempt=2)
    act(db, users["adam"])
    other = db.execute("insert into public.exams (title) values ('scratch') returning id").fetchone()[0]
    start(db, users["alice"], eid)
    act(db, users["adam"])
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.exam_questions set exam_id = %s where exam_id = %s", (other, eid))
    savepoint_raises(db, errors.InsufficientPrivilege, "delete from public.exam_questions where exam_id = %s", (eid,))


def test_question_exam_id_is_not_writable(db, users):
    eid = make_exam(db, users["adam"], n=1, per_attempt=1)
    act(db, users["adam"])
    other = db.execute("insert into public.exams (title) values ('scratch') returning id").fetchone()[0]
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.exam_questions set exam_id = %s where exam_id = %s", (other, eid))
    assert db.execute("update public.exam_questions set q = 'Edited question?' where exam_id = %s", (eid,)).rowcount == 1


def test_deadline_never_passes_closes_at(db, users):
    """L1"""
    eid = make_exam(db, users["adam"], minutes=240)
    as_postgres(db)
    db.execute("update public.exams set closes_at = now() + interval '5 minutes' where id = %s", (eid,))
    r = start(db, users["alice"], eid)
    as_postgres(db)
    dl, cl = db.execute("""select a.deadline, e.closes_at from public.exam_attempts a join public.exams e on e.id = a.exam_id
                           where a.id = %s""", (r["attempt"],)).fetchone()
    assert dl <= cl


def test_answers_filtered_and_bounded(db, users):
    """L2: odd numbers do not abort the submit, junk is not stored, huge payloads are refused."""
    eid = make_exam(db, users["adam"], n=3, per_attempt=3)
    r = start(db, users["alice"], eid)
    savepoint_raises(db, errors.InvalidParameterValue, "select public.exam_submit(%s, %s)",
                     (r["attempt"], json.dumps({f"k{i}": "x" * 1000 for i in range(200)})))
    ids = [str(q["id"]) for q in r["questions"]]
    res = db.execute("select public.exam_submit(%s, %s)",
                     (r["attempt"], json.dumps({ids[0]: 1.5, ids[1]: 10 ** 12, ids[2]: 1, "junk": 0}))).fetchone()[0]
    assert res["total"] == 3
    as_postgres(db)
    stored = db.execute("select answers from public.exam_attempts where id = %s", (r["attempt"],)).fetchone()[0]
    assert stored == {ids[2]: 1}


def test_exam_settings_frozen_after_attempts(db, users):
    """L3: an exam that has been taken cannot be turned into something else; authorship is the database's."""
    eid = make_exam(db, users["adam"])
    start(db, users["alice"], eid)
    act(db, users["adam"])
    for col, val in (("title", "Practice only"), ("pass_pct", 1), ("questions_per_attempt", 50), ("time_limit_min", 240)):
        savepoint_raises(db, errors.InsufficientPrivilege, f"update public.exams set {col} = %s where id = %s", (val, eid))
    assert db.execute("update public.exams set published = false, attempts_allowed = 3 where id = %s", (eid,)).rowcount == 1
    db.execute("update public.exams set created_by = %s, created_at = '2000-01-01' where id = %s", (users["boss"], eid))
    assert db.execute("select created_by from public.exams where id = %s", (eid,)).fetchone() == (users["adam"],)
    forged = db.execute("insert into public.exams (title, created_by) values ('forged author', %s) returning created_by",
                        (users["boss"],)).fetchone()[0]
    assert forged == users["adam"]


def test_review_only_after_the_last_attempt(db, users):
    """L4: with two attempts allowed, the first review would be the key for the second."""
    eid = make_exam(db, users["adam"], n=4, per_attempt=3, attempts=2)
    r1 = start(db, users["alice"], eid)
    assert db.execute("select public.exam_submit(%s, '{}')", (r1["attempt"],)).fetchone()[0]["review"] is None
    r2 = start(db, users["alice"], eid)
    assert len(db.execute("select public.exam_submit(%s, '{}')", (r2["attempt"],)).fetchone()[0]["review"]) == 3


def test_attempts_are_numbered(db, users):
    eid = make_exam(db, users["adam"], attempts=2)
    r1 = start(db, users["alice"], eid)
    db.execute("select public.exam_submit(%s, '{}')", (r1["attempt"],))
    start(db, users["alice"], eid)
    as_postgres(db)
    assert [n for (n,) in db.execute("select attempt_no from public.exam_attempts where exam_id = %s order by attempt_no", (eid,))] == [1, 2]


def test_browser_roles_have_no_sequence_privileges(db):
    rows = db.execute("""select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
                         where n.nspname = 'public' and c.relkind = 'S'
                           and (has_sequence_privilege('anon', c.oid, 'usage') or has_sequence_privilege('authenticated', c.oid, 'usage'))""").fetchall()
    assert rows == []
