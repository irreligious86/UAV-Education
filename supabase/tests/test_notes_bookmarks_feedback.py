"""Personal study data and feedback (supabase/migrations/0007_notes_bookmarks_feedback_settings.sql).

Notes, bookmarks, settings and reading history belong to their owner only (staff included in "nobody else");
feedback is created only by send_feedback() from a confirmed account, rate-limited; staff change status and their
internal note, never the text. Access matrix: docs/MULTIUSER-PLAN.md, section 14.
"""
import json

import pytest
from psycopg import errors

from conftest import act, as_postgres, savepoint_raises, signup

PERSONAL = ("public.user_notes", "public.user_bookmarks", "public.user_settings", "public.user_history")


def note(db, module="bf-pid", anchor="", body="Kp first, then D.", label=""):
    return db.execute("insert into public.user_notes (user_id, module_id, anchor, label, body) values (auth.uid(), %s, %s, %s, %s)",
                      (module, anchor, label, body))


def send(db, body="The formula in section 3 has a sign error.", kind="error", module="bf-pid", section="betaflight", anchor="sec-3", lang="ru"):
    return db.execute("select public.send_feedback(%s, %s, %s, %s, %s, %s)", (module, section, anchor, kind, body, lang)).fetchone()[0]


# ------------------------------------------------------------------ notes, bookmarks: owner CRUD
def test_owner_crud_notes(db, users):
    act(db, users["alice"])
    note(db)
    note(db, anchor="sec-2", body="D term amplifies noise", label="D-term")
    assert db.execute("select count(*) from public.user_notes").fetchone() == (2,)
    # the browser's upsert: insert … on conflict do update
    db.execute("""insert into public.user_notes (user_id, module_id, anchor, label, body) values (auth.uid(), 'bf-pid', '', '', 'v2')
                  on conflict (user_id, module_id, anchor) do update set body = excluded.body, label = excluded.label""")
    assert db.execute("select body from public.user_notes where anchor = ''").fetchone() == ("v2",)
    assert db.execute("delete from public.user_notes where anchor = 'sec-2'").rowcount == 1
    assert db.execute("select count(*) from public.user_notes").fetchone() == (1,)


def test_owner_crud_bookmarks(db, users):
    act(db, users["alice"])
    db.execute("insert into public.user_bookmarks (user_id, module_id, anchor, label) values (auth.uid(), 'bf-pid', 'sec-4', 'I-term relax')")
    db.execute("insert into public.user_bookmarks (user_id, module_id) values (auth.uid(), 'f-power')")
    assert db.execute("select module_id, anchor from public.user_bookmarks order by module_id").fetchall() == [("bf-pid", "sec-4"), ("f-power", "")]
    assert db.execute("delete from public.user_bookmarks where module_id = 'f-power'").rowcount == 1


def test_server_sets_timestamps(db, users):
    act(db, users["alice"])
    savepoint_raises(db, errors.InsufficientPrivilege,
                     "insert into public.user_notes (user_id, module_id, body, updated_at) values (auth.uid(), 'x', 'y', '2000-01-01')")
    savepoint_raises(db, errors.InsufficientPrivilege,
                     "insert into public.user_notes (user_id, module_id, body, created_at) values (auth.uid(), 'x', 'y', '2000-01-01')")
    note(db)
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.user_notes set updated_at = '2000-01-01'")
    assert db.execute("select updated_at > now() - interval '1 minute' from public.user_notes").fetchone() == (True,)


@pytest.mark.parametrize("who", ["bob", "adam", "boss"])
def test_nobody_else_reads_or_writes_personal_data(db, users, who):
    act(db, users["alice"])
    note(db)
    db.execute("insert into public.user_bookmarks (user_id, module_id) values (auth.uid(), 'bf-pid')")
    db.execute("insert into public.user_settings (user_id, data) values (auth.uid(), '{\"notesPanel\": true}')")
    db.execute("insert into public.user_history (user_id, items) values (auth.uid(), '[{\"id\": \"bf-pid\", \"at\": 1}]')")
    act(db, users[who])                 # another student, an admin, the superadmin: the same — nothing
    for t in PERSONAL:
        assert db.execute(f"select count(*) from {t}").fetchone() == (0,), t
        assert db.execute(f"delete from {t} where user_id = %s", (users["alice"],)).rowcount == 0
    assert db.execute("update public.user_notes set body = 'hacked' where user_id = %s", (users["alice"],)).rowcount == 0
    assert db.execute("update public.user_settings set data = '{}' where user_id = %s", (users["alice"],)).rowcount == 0
    savepoint_raises(db, errors.InsufficientPrivilege,
                     "insert into public.user_notes (user_id, module_id, body) values (%s, 'bf-pid', 'planted')", (users["alice"],))
    savepoint_raises(db, errors.InsufficientPrivilege,
                     "insert into public.user_bookmarks (user_id, module_id) values (%s, 'bf-pid')", (users["alice"],))
    # moving one's own row to someone else is refused by with check
    note(db, module="f-power")
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.user_notes set user_id = %s", (users["alice"],))
    as_postgres(db)
    assert db.execute("select body from public.user_notes where user_id = %s", (users["alice"],)).fetchall() == [("Kp first, then D.",)]


def test_anon_has_no_access(db, users):
    db.execute("set local role anon")
    for t in PERSONAL + ("public.feedback",):
        savepoint_raises(db, errors.InsufficientPrivilege, f"select * from {t}")
        savepoint_raises(db, errors.InsufficientPrivilege, f"delete from {t}")
    savepoint_raises(db, errors.InsufficientPrivilege, "insert into public.user_notes (user_id, module_id, body) values (gen_random_uuid(), 'a', 'b')")
    for fn in ("public.send_feedback('bf-pid', '', '', 'error', 'long enough text', 'ru')", "public.feedback_for_staff()",
               "public.feedback_set(1, 'done', null)", "public.feedback_delete(1)"):
        savepoint_raises(db, errors.InsufficientPrivilege, f"select {fn}")


# ------------------------------------------------------------------ shape and size limits
@pytest.mark.parametrize("module,anchor,body,label", [
    ("BF-PID", "", "x", ""),                 # upper case module id
    ("bf pid", "", "x", ""),
    ("x" * 65, "", "x", ""),
    ("bf-pid", "sec 3", "x", ""),            # anchors are ids
    ("bf-pid", "a" * 81, "x", ""),
    ("bf-pid", "", "", ""),                  # empty note: deleted, not stored
    ("bf-pid", "", "x" * 8001, ""),
    ("bf-pid", "", "x", "l" * 161),
])
def test_note_shape_limits(db, users, module, anchor, body, label):
    act(db, users["alice"])
    savepoint_raises(db, errors.CheckViolation, "insert into public.user_notes (user_id, module_id, anchor, label, body) values (auth.uid(), %s, %s, %s, %s)",
                     (module, anchor, label, body))


def test_note_at_size_limit_is_accepted(db, users):
    act(db, users["alice"])
    note(db, body="я" * 8000, label="л" * 160, anchor="a" * 80)
    assert db.execute("select char_length(body) from public.user_notes").fetchone() == (8000,)


def test_settings_known_keys_only(db, users):
    act(db, users["alice"])
    good = {"readyOnly": True, "resumeOnOpen": False, "notesPanel": True, "firmwarePath": "betaflight"}
    db.execute("insert into public.user_settings (user_id, data) values (auth.uid(), %s)", (json.dumps(good),))
    db.execute("""insert into public.user_settings (user_id, data) values (auth.uid(), '{"firmwarePath": ""}')
                  on conflict (user_id) do update set data = excluded.data""")
    assert db.execute("select data from public.user_settings").fetchone() == ({"firmwarePath": ""},)
    for bad in ({"theme": "dark"}, {"readyOnly": "yes"}, {"notesPanel": 1}, {"firmwarePath": "Betaflight; drop"},
                {"firmwarePath": True}, {"resumeOnOpen": None}, ["readyOnly"], {"firmwarePath": "x" * 65}):
        savepoint_raises(db, errors.CheckViolation, "update public.user_settings set data = %s", (json.dumps(bad),))


def test_history_shape(db, users):
    act(db, users["alice"])
    items = [{"id": f"m{i}", "path": f"m/m{i}.html", "title": "t", "anchor": "sec-1", "heading": "h", "at": 1700000000000 + i} for i in range(30)]
    db.execute("insert into public.user_history (user_id, items) values (auth.uid(), %s)", (json.dumps(items),))
    for bad in (items + [items[0]], [{"id": "a"}], [{"at": 1}], [{"id": 5, "at": 1}], ["m1"], {"items": []}, [{"id": "a", "at": "1"}]):
        savepoint_raises(db, errors.CheckViolation, "update public.user_history set items = %s", (json.dumps(bad),))


# ------------------------------------------------------------------ row caps
def test_note_row_cap(db, users):
    db.execute("insert into public.user_notes (user_id, module_id, anchor, body) select %s, 'm', 's' || g, 'x' from generate_series(1, 1999) g",
               (users["alice"],))
    act(db, users["alice"])
    note(db, module="m", anchor="last")                            # 2000th
    savepoint_raises(db, errors.ProgramLimitExceeded, "insert into public.user_notes (user_id, module_id, body) values (auth.uid(), 'n', 'one too many')")
    # editing an existing note through the upsert still works at the cap
    db.execute("""insert into public.user_notes (user_id, module_id, anchor, body) values (auth.uid(), 'm', 's1', 'edited')
                  on conflict (user_id, module_id, anchor) do update set body = excluded.body""")
    assert db.execute("select body from public.user_notes where anchor = 's1'").fetchone() == ("edited",)
    act(db, users["bob"])                                          # the cap is per user
    note(db)


def test_bookmark_row_cap(db, users):
    db.execute("insert into public.user_bookmarks (user_id, module_id, anchor) select %s, 'm', 's' || g from generate_series(1, 1000) g", (users["alice"],))
    act(db, users["alice"])
    savepoint_raises(db, errors.ProgramLimitExceeded, "insert into public.user_bookmarks (user_id, module_id) values (auth.uid(), 'n')")


# ------------------------------------------------------------------ feedback
def test_confirmed_user_sends_feedback_and_sees_status(db, users):
    act(db, users["alice"])
    fid = send(db)
    row = db.execute("select user_id, module_id, section_key, anchor, kind, status, page_lang from public.feedback where id = %s", (fid,)).fetchone()
    assert row == (users["alice"], "bf-pid", "betaflight", "sec-3", "error", "new", "ru")
    # the internal staff note is not readable by the author
    savepoint_raises(db, errors.InsufficientPrivilege, "select staff_note from public.feedback")
    savepoint_raises(db, errors.InsufficientPrivilege, "select * from public.feedback")


def test_feedback_only_from_signed_in_confirmed_users(db, users):
    pending = signup(db, "newbie", confirmed=False)
    act(db, pending)
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.send_feedback('bf-pid', '', '', 'error', 'long enough text', 'ru')")
    db.execute("reset role")
    db.execute("set local role authenticated")
    db.execute("select set_config('request.jwt.claims', '', true)")     # authenticated role without a user
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.send_feedback('bf-pid', '', '', 'error', 'long enough text', 'ru')")


def test_feedback_has_no_direct_writes(db, users):
    act(db, users["alice"])
    fid = send(db)
    savepoint_raises(db, errors.InsufficientPrivilege,
                     "insert into public.feedback (user_id, module_id, kind, body) values (auth.uid(), 'bf-pid', 'idea', 'direct insert here')")
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.feedback set body = 'changed my mind' where id = %s", (fid,))
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.feedback set status = 'done' where id = %s", (fid,))
    savepoint_raises(db, errors.InsufficientPrivilege, "delete from public.feedback where id = %s", (fid,))


@pytest.mark.parametrize("args", [
    ("bf-pid", "", "", "bug", "long enough text", "ru"),             # unknown kind
    ("bf-pid", "", "", "error", "too short", "ru"),                    # < 10 characters
    ("bf-pid", "", "", "error", "          x         ", "ru"),        # padding does not count
    ("bf-pid", "", "", "error", "x" * 4001, "ru"),
    ("", "", "", "error", "long enough text", "ru"),                   # no module and no section
    ("bf-pid", "", "sec 3", "error", "long enough text", "ru"),
    ("bf-pid", "", "", "error", "long enough text", "russian"),
    ("Bf-pid", "", "", "error", "long enough text", "ru"),
])
def test_feedback_shape(db, users, args):
    act(db, users["alice"])
    savepoint_raises(db, errors.CheckViolation, "select public.send_feedback(%s, %s, %s, %s, %s, %s)", args)


def test_feedback_for_a_whole_section(db, users):
    act(db, users["alice"])
    fid = send(db, module="", section="betaflight", anchor="", kind="idea", body="More about RPM filter please")
    assert db.execute("select module_id, section_key from public.feedback where id = %s", (fid,)).fetchone() == (None, "betaflight")


def test_feedback_rate_limit_per_hour(db, users):
    act(db, users["alice"])
    for i in range(10):
        send(db, body=f"message number {i}")
    savepoint_raises(db, errors.ProgramLimitExceeded, "select public.send_feedback('bf-pid', '', '', 'other', 'eleventh message', 'ru')")
    act(db, users["bob"])                                          # per user
    send(db)


def test_feedback_rate_limit_per_day(db, users):
    db.execute("""insert into public.feedback (user_id, module_id, kind, body, created_at)
                  select %s, 'bf-pid', 'other', 'older message here', now() - interval '2 hours' - g * interval '1 minute'
                  from generate_series(1, 49) g""", (users["alice"],))
    db.execute("""insert into public.feedback (user_id, module_id, kind, body, created_at)
                  select %s, 'bf-pid', 'other', 'yesterday message', now() - interval '25 hours' from generate_series(1, 20) g""", (users["alice"],))
    act(db, users["alice"])
    send(db)                                                       # 50th in 24 h
    savepoint_raises(db, errors.ProgramLimitExceeded, "select public.send_feedback('bf-pid', '', '', 'other', 'fifty-first message', 'ru')")


def test_student_reads_only_own_feedback(db, users):
    act(db, users["bob"])
    send(db, body="bob's message about PID")
    act(db, users["alice"])
    send(db)
    assert db.execute("select count(*) from public.feedback").fetchone() == (1,)
    savepoint_raises(db, errors.InsufficientPrivilege, "select * from public.feedback_for_staff()")


@pytest.mark.parametrize("staff", ["adam", "boss"])
def test_staff_list_and_update_status_not_body(db, users, staff):
    act(db, users["alice"])
    fid = send(db)
    act(db, users[staff])
    rows = db.execute("select id, username, body, status, staff_note from public.feedback_for_staff()").fetchall()
    assert rows == [(fid, "alice", "The formula in section 3 has a sign error.", "new", "")]
    assert db.execute("select count(*) from public.feedback").fetchone() == (1,)    # staff also read the table (without staff_note)
    db.execute("select public.feedback_set(%s, 'in_progress', 'checked: sign is wrong')", (fid,))
    db.execute("select public.feedback_set(%s, 'done', null)", (fid,))           # null keeps the note
    assert db.execute("select status, staff_note from public.feedback_for_staff()").fetchone() == ("done", "checked: sign is wrong")
    savepoint_raises(db, errors.CheckViolation, "select public.feedback_set(%s, 'closed', null)", (fid,))
    savepoint_raises(db, errors.CheckViolation, "select public.feedback_set(%s, null, %s)", (fid, "n" * 2001))
    savepoint_raises(db, errors.NoDataFound, "select public.feedback_set(-1, 'done', null)")
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.feedback set body = 'edited by staff' where id = %s", (fid,))
    savepoint_raises(db, errors.InsufficientPrivilege, "update public.feedback set status = 'rejected' where id = %s", (fid,))
    act(db, users["alice"])                                        # the author sees the new status
    assert db.execute("select status, body from public.feedback where id = %s", (fid,)).fetchone() == ("done", "The formula in section 3 has a sign error.")


def test_student_cannot_change_status(db, users):
    act(db, users["alice"])
    fid = send(db)
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.feedback_set(%s, 'done', null)", (fid,))
    assert db.execute("select status from public.feedback where id = %s", (fid,)).fetchone() == ("new",)


def test_demoted_admin_loses_feedback_access(db, users):
    act(db, users["alice"])
    send(db)
    act(db, users["boss"])
    db.execute("select public.set_role(%s, 'student')", (users["adam"],))
    act(db, users["adam"])
    savepoint_raises(db, errors.InsufficientPrivilege, "select * from public.feedback_for_staff()")
    assert db.execute("select count(*) from public.feedback").fetchone() == (0,)


def test_only_superadmin_deletes_feedback(db, users):
    act(db, users["alice"])
    fid = send(db)
    for who in ("alice", "adam"):
        act(db, users[who])
        savepoint_raises(db, errors.InsufficientPrivilege, "select public.feedback_delete(%s)", (fid,))
    act(db, users["boss"])
    db.execute("select public.feedback_delete(%s)", (fid,))
    assert db.execute("select count(*) from public.feedback_for_staff()").fetchone() == (0,)


# ------------------------------------------------------------------ account deletion
def test_account_deletion_removes_personal_data_and_anonymises_feedback(db, users):
    act(db, users["alice"])
    note(db)
    db.execute("insert into public.user_bookmarks (user_id, module_id) values (auth.uid(), 'bf-pid')")
    db.execute("insert into public.user_settings (user_id, data) values (auth.uid(), '{\"readyOnly\": true}')")
    db.execute("insert into public.user_history (user_id, items) values (auth.uid(), '[{\"id\": \"bf-pid\", \"at\": 1}]')")
    fid = send(db)
    as_postgres(db)
    db.execute("delete from auth.users where id = %s", (users["alice"],))
    for t in PERSONAL:
        assert db.execute(f"select count(*) from {t} where user_id = %s", (users["alice"],)).fetchone() == (0,), t
    assert db.execute("select user_id, body from public.feedback where id = %s", (fid,)).fetchone() == (None, "The formula in section 3 has a sign error.")
    act(db, users["adam"])
    assert db.execute("select username from public.feedback_for_staff() where id = %s", (fid,)).fetchone() == (None,)


# ------------------------------------------------------------------ review fixes (2026-11-26)
def test_cap_trigger_does_not_reveal_other_users_cap(db, users):
    """R1: inserting a row for someone else is refused by RLS the same way whether or not they are at the cap."""
    db.execute("insert into public.user_bookmarks (user_id, module_id, anchor) select %s, 'm', 's' || g from generate_series(1, 1000) g", (users["bob"],))
    act(db, users["alice"])
    for victim in ("bob", "carol"):     # bob is at the cap, carol is not
        savepoint_raises(db, errors.InsufficientPrivilege, "insert into public.user_bookmarks (user_id, module_id) values (%s, 'n')", (users[victim],))


@pytest.mark.parametrize("body", ["\n" * 12, "\t" * 12, " " * 12, " 　﻿" * 4, " \n\t abc  \n defgh  ", "\r\n" * 8])
def test_feedback_body_white_space_of_any_kind_does_not_count(db, users, body):
    """R2: fewer than 10 non-space characters is refused, whatever the spaces are."""
    act(db, users["alice"])
    savepoint_raises(db, errors.CheckViolation, "select public.send_feedback('bf-pid', '', '', 'other', %s, 'ru')", (body,))


def test_feedback_body_counts_letters_between_spaces(db, users):
    act(db, users["alice"])
    send(db, body="\n\n a b c d e f g h i j \n")      # 10 letters among spaces


def save_note(db, body, expected, module="bf-pid", anchor=""):
    return db.execute("select public.save_note(%s, %s, '', %s, %s)", (module, anchor, body, expected)).fetchone()[0]


def test_save_note_refuses_to_overwrite_a_newer_version(db, users):
    """R3: a save carries the version the browser last saw; a different stored version comes back instead."""
    act(db, users["alice"])
    r1 = save_note(db, "laptop v1", None)
    assert r1["conflict"] is False
    t1 = r1["updated_at"]
    again = save_note(db, "phone, never saw it", None)              # another device that did not know the row
    assert again == {"conflict": True, "body": "laptop v1", "label": "", "updated_at": t1}
    r2 = save_note(db, "laptop v2", t1)                               # the right base: saved
    assert r2["conflict"] is False
    stale = save_note(db, "phone edit on v1", t1)                     # stale base: refused, v2 kept
    assert stale["conflict"] is True and stale["body"] == "laptop v2"
    assert db.execute("select body from public.user_notes").fetchone() == ("laptop v2",)


def test_save_note_respects_rls_and_limits(db, users):
    act(db, users["alice"])
    save_note(db, "alice's", None)
    act(db, users["bob"])
    assert save_note(db, "bob's own", None)["conflict"] is False         # bob gets his own row, alice's is invisible
    savepoint_raises(db, errors.CheckViolation, "select public.save_note('bf-pid', 'x', '', %s, null)", ("x" * 8001,))
    as_postgres(db)
    assert db.execute("select count(*) from public.user_notes where body = 'alice''s'").fetchone() == (1,)
    db.execute("set local role anon")
    savepoint_raises(db, errors.InsufficientPrivilege, "select public.save_note('bf-pid', '', '', 'x', null)")


def test_staff_feedback_pages(db, users):
    """R7: staff page through older messages."""
    db.execute("""insert into public.feedback (user_id, module_id, kind, body, created_at)
                  select %s, 'bf-pid', 'other', 'message number ' || g, now() - g * interval '1 minute' from generate_series(1, 7) g""", (users["alice"],))
    act(db, users["adam"])
    first = db.execute("select body, created_at from public.feedback_for_staff(null, 3)").fetchall()
    assert [b for b, _ in first] == ["message number 1", "message number 2", "message number 3"]
    rest = db.execute("select body from public.feedback_for_staff(%s, 10)", (first[-1][1],)).fetchall()
    assert [b for (b,) in rest] == [f"message number {i}" for i in range(4, 8)]
