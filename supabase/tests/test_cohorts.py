"""Cohorts (supabase/migrations/0003_cohorts.sql): staff manage groups, a student sees only their own groups,
nobody else's membership, and cannot join or leave by themselves."""
import pytest
from psycopg import errors

from conftest import act, as_postgres, savepoint_raises


def cohort(db, staff_uid, name="Группа А", members=()):
    act(db, staff_uid)
    cid = db.execute("insert into public.cohorts (name) values (%s) returning id", (name,)).fetchone()[0]
    for m in members:
        db.execute("insert into public.cohort_members (cohort_id, user_id) values (%s, %s)", (cid, m))
    as_postgres(db)
    return cid


@pytest.mark.parametrize("who", ["adam", "boss"])
def test_staff_create_groups_and_add_students(db, users, who):
    cid = cohort(db, users[who], members=(users["alice"], users["bob"]))
    act(db, users[who])
    assert db.execute("select count(*) from public.cohort_members where cohort_id = %s", (cid,)).fetchone() == (2,)
    row = db.execute("select created_by from public.cohorts where id = %s", (cid,)).fetchone()
    assert row == (users[who],)


def test_student_sees_own_groups_only(db, users):
    a = cohort(db, users["adam"], "Группа А", (users["alice"], users["bob"]))
    cohort(db, users["adam"], "Группа Б", (users["carol"],))
    act(db, users["alice"])
    assert [r[0] for r in db.execute("select name from public.cohorts").fetchall()] == ["Группа А"]
    rows = db.execute("select cohort_id, user_id from public.cohort_members").fetchall()
    assert rows == [(a, users["alice"])], "a student must not see the other members of their group"


def test_student_cannot_create_join_or_leave(db, users):
    cid = cohort(db, users["adam"], members=(users["bob"],))
    act(db, users["alice"])
    savepoint_raises(db, errors.InsufficientPrivilege, "insert into public.cohorts (name) values ('my own group')")
    savepoint_raises(db, errors.InsufficientPrivilege,
                     "insert into public.cohort_members (cohort_id, user_id) values (%s, %s)", (cid, users["alice"]))
    act(db, users["bob"])
    assert db.execute("delete from public.cohort_members where user_id = %s", (users["bob"],)).rowcount == 0
    assert db.execute("update public.cohorts set name = 'renamed by bob' where id = %s", (cid,)).rowcount == 0
    assert db.execute("delete from public.cohorts where id = %s", (cid,)).rowcount == 0


def test_staff_remove_members_and_delete_groups(db, users):
    cid = cohort(db, users["adam"], members=(users["alice"], users["bob"]))
    act(db, users["adam"])
    assert db.execute("delete from public.cohort_members where cohort_id = %s and user_id = %s", (cid, users["alice"])).rowcount == 1
    assert db.execute("update public.cohorts set name = 'Группа А2' where id = %s", (cid,)).rowcount == 1
    assert db.execute("delete from public.cohorts where id = %s", (cid,)).rowcount == 1
    assert db.execute("select count(*) from public.cohort_members where cohort_id = %s", (cid,)).fetchone() == (0,)


def test_names_unique_ignoring_case_and_shape_checked(db, users):
    cohort(db, users["adam"], "Весна-2027")
    act(db, users["adam"])
    savepoint_raises(db, errors.UniqueViolation, "insert into public.cohorts (name) values (' весна-2027 ')")
    savepoint_raises(db, errors.CheckViolation, "insert into public.cohorts (name) values ('  x ')")


def test_member_added_once(db, users):
    cid = cohort(db, users["adam"], members=(users["alice"],))
    act(db, users["adam"])
    savepoint_raises(db, errors.UniqueViolation,
                     "insert into public.cohort_members (cohort_id, user_id) values (%s, %s)", (cid, users["alice"]))


def test_audit_columns_cannot_be_forged(db, users):
    act(db, users["adam"])
    cid = db.execute("insert into public.cohorts (name, created_by, created_at) values ('forged', %s, '2000-01-01') returning id",
                     (users["boss"],)).fetchone()[0]
    db.execute("insert into public.cohort_members (cohort_id, user_id, added_by, added_at) values (%s, %s, %s, '2000-01-01')",
               (cid, users["alice"], users["boss"]))
    c = db.execute("select created_by, created_at > now() - interval '1 hour' from public.cohorts where id = %s", (cid,)).fetchone()
    m = db.execute("select added_by, added_at > now() - interval '1 hour' from public.cohort_members where cohort_id = %s", (cid,)).fetchone()
    assert c == (users["adam"], True) and m == (users["adam"], True)
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.cohorts set created_by = %s where id = %s", (users["boss"], cid))


def test_demoted_admin_loses_group_access(db, users):
    cohort(db, users["adam"], members=(users["alice"],))
    act(db, users["boss"])
    db.execute("select public.set_role(%s, 'student')", (users["adam"],))
    act(db, users["adam"])
    assert db.execute("select count(*) from public.cohorts").fetchone() == (0,)
    assert db.execute("select count(*) from public.cohort_members").fetchone() == (0,)
    savepoint_raises(db, errors.InsufficientPrivilege, "insert into public.cohorts (name) values ('still admin?')")


def test_deleting_a_user_removes_membership(db, users):
    cid = cohort(db, users["adam"], members=(users["alice"], users["bob"]))
    db.execute("delete from auth.users where id = %s", (users["alice"],))
    assert db.execute("select count(*) from public.cohort_members where cohort_id = %s", (cid,)).fetchone() == (1,)


def test_anon_has_no_cohort_access(db, users):
    cohort(db, users["adam"], members=(users["alice"],))
    db.execute("set local role anon")
    for t in ("public.cohorts", "public.cohort_members"):
        savepoint_raises(db, errors.InsufficientPrivilege, f"select * from {t}")
