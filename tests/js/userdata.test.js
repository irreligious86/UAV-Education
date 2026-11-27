// node --test tests/js — merge rules of assets/user-data.js (notes, bookmarks, history: this browser + the server).
const test = require("node:test");
const assert = require("node:assert");
const { mergeRows, mergeHistory, cleanSettings, resolve, invalid, migrateRows } = require("../../assets/user-data.js");

const S = (m, a, body, t, label) => ({ module_id: m, anchor: a, label: label || "", body, updated_at: t });
const T1 = "2026-11-26T10:00:00.000Z", T2 = "2026-11-26T11:00:00.000Z";

test("a guest note goes up, a server-only note comes down", () => {
  const r = mergeRows({ "a#": { m: "a", a: "", body: "mine", at: 5, dirty: true, srv: null } }, [S("b", "teoriya", "theirs", T1)]);
  assert.deepStrictEqual(r.push, ["a#"]);
  assert.strictEqual(r.rows["b#teoriya"].body, "theirs");
  assert.strictEqual(r.rows["b#teoriya"].dirty, false);
});

test("a clean local row takes the server version; a dirty one over an unchanged server row is pushed", () => {
  const r = mergeRows({ "a#": { m: "a", a: "", body: "old", dirty: false, srv: T1 }, "b#": { m: "b", a: "", body: "edited", dirty: true, srv: T1 } },
                      [S("a", "", "new", T2), S("b", "", "old b", T1)]);
  assert.strictEqual(r.rows["a#"].body, "new");
  assert.strictEqual(r.rows["b#"].body, "edited");
  assert.deepStrictEqual(r.push, ["b#"]);
});

test("both sides edited: the note keeps both texts and is pushed", () => {
  const r = mergeRows({ "a#": { m: "a", a: "", body: "local text", at: 1, dirty: true, srv: T1 } }, [S("a", "", "server text", T2)],
                      { marker: () => "--- copy ---" });
  assert.strictEqual(r.rows["a#"].body, "server text\n\n--- copy ---\nlocal text");
  assert.deepStrictEqual(r.push, ["a#"]);
});

test("a guest note over an existing server note is not lost either", () => {
  const r = mergeRows({ "a#": { m: "a", a: "", body: "guest", dirty: true, srv: null } }, [S("a", "", "account", T1)], { marker: () => "|" });
  assert.match(r.rows["a#"].body, /account[\s\S]*guest/);
});

test("too long to combine: the server note stays untouched, ours becomes a separate copy note", () => {
  const big = "x".repeat(5000);
  const r = mergeRows({ "a#pid": { m: "a", a: "pid", label: "PID", body: big, dirty: true, srv: T1 } }, [S("a", "pid", big + "y", T2, "PID")],
                      { max: 8000, copyLabel: "(copy)" });
  assert.strictEqual(r.rows["a#pid"].body, big + "y");
  assert.strictEqual(r.rows["a#pid"].dirty, false);
  assert.deepStrictEqual(r.push, ["a#pid-copy-1"]);
  assert.deepStrictEqual([r.rows["a#pid-copy-1"].body, r.rows["a#pid-copy-1"].label, r.rows["a#pid-copy-1"].srv], [big, "PID (copy)", null]);
});

test("copy anchors stay free and within the server's anchor pattern", () => {
  const big = "x".repeat(5000);
  const L = { m: "a", a: "", body: big, dirty: true, srv: T1 };
  const r = resolve(L, S("a", "", big + "y", T2), { max: 8000 }, (an) => an === "copy-1");
  assert.ok(r.rows["a#copy-2"]);
  const long = resolve(Object.assign({}, L, { a: "z".repeat(80) }), S("a", "z".repeat(80), big + "y", T2), { max: 8000 }, () => false);
  const ca = Object.keys(long.rows).map((k) => k.split("#")[1]).find((x) => /copy/.test(x));
  assert.match(ca, /^[A-Za-z0-9_-]{0,80}$/);
});

test("a push conflict merges the same way (save_note returned a newer version)", () => {
  const r = resolve({ m: "a", a: "", body: "laptop", at: 1, dirty: true, srv: T1 }, S("a", "", "phone", T2), { marker: () => "|" }, () => false);
  assert.strictEqual(r.rows["a#"].body, "phone\n\n|\nlaptop");
  assert.strictEqual(r.rows["a#"].srv, T2);           // the next save goes over the version it now contains
  assert.deepStrictEqual(r.push, ["a#"]);
});

test("rows the server would refuse are recognised before sending", () => {
  assert.strictEqual(invalid({ m: "bf-pid", a: "slaydery-betaflight-4-3", body: "x" }, true), "");
  assert.strictEqual(invalid({ m: "bf-pid", a: "sec-3", body: "x" }, true), "");   // old anchors still pass until migrated
  assert.ok(invalid({ m: "BF PID", a: "", body: "x" }, true));
  assert.ok(invalid({ m: "bf-pid", a: "sec 3", body: "x" }, true));
  assert.ok(invalid({ m: "bf-pid", a: "", body: "" }, true));
  assert.strictEqual(invalid({ m: "bf-pid", a: "", del: true }, true), "");
});

test("deletes: here and on an unchanged server row -> delete there; deleted elsewhere -> gone here; edited elsewhere -> kept", () => {
  const r = mergeRows({
    "a#": { m: "a", a: "", body: "x", dirty: true, del: true, srv: T1 },
    "b#": { m: "b", a: "", body: "x", dirty: false, srv: T1 },
    "c#": { m: "c", a: "", body: "x", dirty: true, del: true, srv: T1 },
    "d#": { m: "d", a: "", body: "unsynced edit", dirty: true, srv: T1 }
  }, [S("a", "", "x", T1), S("c", "", "edited there", T2)]);
  assert.deepStrictEqual(r.del, ["a#"]);
  assert.strictEqual(r.rows["b#"], undefined);
  assert.strictEqual(r.rows["c#"].body, "edited there");
  assert.strictEqual(r.rows["d#"].body, "unsynced edit");        // deleted on the server, edited here: ours survives
  assert.ok(r.push.includes("d#"));
});

test("bookmarks (no body) merge as a set", () => {
  const r = mergeRows({ "a#": { m: "a", a: "", dirty: true, srv: null } }, [{ module_id: "a", anchor: "", label: "", updated_at: T1 }]);
  assert.strictEqual(r.rows["a#"].dirty, false);
  assert.deepStrictEqual(r.push, []);
});

test("history: newest at per lesson, newest first, at most 30", () => {
  const a = { items: [{ id: "x", at: 5, anchor: "teoriya" }, { id: "y", at: 1 }] };
  const b = { items: [{ id: "x", at: 9, anchor: "praktika" }, { id: "z", at: 3 }, { id: 7, at: 100 }] };
  const m = mergeHistory(a, b);
  assert.deepStrictEqual(m.items.map((i) => i.id), ["x", "z", "y"]);
  assert.strictEqual(m.items[0].anchor, "praktika");
  assert.strictEqual(m.last, "x");
  const many = { items: Array.from({ length: 40 }, (_, i) => ({ id: "m" + i, at: i })) };
  assert.strictEqual(mergeHistory(many, {}).items.length, 30);
});

test("settings: only known keys with the right types reach the server", () => {
  assert.deepStrictEqual(cleanSettings({ readyOnly: true, notesPanel: false, firmwarePath: "inav", theme: "x" }), { readyOnly: true, notesPanel: false, firmwarePath: "inav" });
  assert.deepStrictEqual(cleanSettings({ readyOnly: "no", notesPanel: 1 }), {});   // no coercion
  assert.deepStrictEqual(cleanSettings({ firmwarePath: "Bad Path" }), {});
});

// ---- old positional anchors ("sec-N") -> heading ids (migrateRows; the lesson page supplies `to`)
const HEADS = ["teoriya", "pid", "filtry", "praktika"];            // sec-1 … sec-4 in document order
const byPos = (a) => { const m = /^sec-(\d+)$/.exec(a); return m && HEADS[m[1] - 1] || null; };

test("migration: an old sec-3 bookmark becomes the id of heading 3; other lessons are left alone", () => {
  const rows = { "bf-pid#sec-3": { m: "bf-pid", a: "sec-3", label: "Фильтры", at: 1, dirty: false, srv: null },
                 "bf-cli#sec-3": { m: "bf-cli", a: "sec-3", label: "", at: 1, dirty: false, srv: null } };
  const r = migrateRows(rows, "bf-pid", byPos);
  assert.strictEqual(r.moved, 1);
  assert.deepStrictEqual(Object.keys(r.rows).sort(), ["bf-cli#sec-3", "bf-pid#filtry"]);
  assert.deepStrictEqual([r.rows["bf-pid#filtry"].a, r.rows["bf-pid#filtry"].label, r.rows["bf-pid#filtry"].dirty], ["filtry", "Фильтры", true]);
});

test("migration is idempotent and keeps rows that are not old anchors or have no heading any more", () => {
  const rows = { "a#sec-2": { m: "a", a: "sec-2", body: "n", at: 1, dirty: true, srv: null },
                 "a#": { m: "a", a: "", body: "whole", at: 1 },
                 "a#copy-1": { m: "a", a: "copy-1", body: "c", at: 1 },
                 "a#sec-9": { m: "a", a: "sec-9", body: "gone", at: 1 } };
  const once = migrateRows(rows, "a", byPos);
  const twice = migrateRows(once.rows, "a", byPos);
  assert.strictEqual(twice.moved, 0);
  assert.deepStrictEqual(twice.rows, once.rows);
  assert.deepStrictEqual(Object.keys(once.rows).sort(), ["a#", "a#copy-1", "a#pid", "a#sec-9"]);
});

test("migration of a synced row: the new anchor goes up, the old server row is deleted — never both live", () => {
  const rows = { "a#sec-1": { m: "a", a: "sec-1", body: "text", label: "Теория", at: 1, dirty: false, srv: T1 } };
  const r = migrateRows(rows, "a", byPos, { now: 42 });
  assert.deepStrictEqual(r.rows["a#teoriya"], { m: "a", a: "teoriya", body: "text", label: "Теория", at: 1, dirty: true, srv: null, del: false });
  assert.deepStrictEqual(r.rows["a#sec-1"], { m: "a", a: "sec-1", body: "text", label: "Теория", at: 42, dirty: true, srv: T1, del: true });
  // what the next push does: one upsert under the new anchor, one delete of the old one
  const live = Object.values(r.rows).filter((x) => !x.del).map((x) => x.a);
  assert.deepStrictEqual(live, ["teoriya"]);
  // at the next login merge the deletion goes up and the moved note is pushed
  const m = mergeRows(r.rows, [S("a", "sec-1", "text", T1, "Теория")]);
  assert.deepStrictEqual(m.del, ["a#sec-1"]);
  assert.deepStrictEqual(m.push, ["a#teoriya"]);
});

test("migration: a pending local deletion under an old anchor stays a deletion of that anchor", () => {
  const rows = { "a#sec-1": { m: "a", a: "sec-1", body: "x", at: 1, dirty: true, del: true, srv: T1 } };
  assert.strictEqual(migrateRows(rows, "a", byPos).moved, 0);
});

test("migration: copies follow their heading, and a taken place never loses a text", () => {
  const rows = {
    "a#sec-2-copy-1": { m: "a", a: "sec-2-copy-1", body: "copy", label: "PID (copy)", at: 1 },
    "a#sec-4": { m: "a", a: "sec-4", body: "old device", label: "Практика", at: 1 },
    "a#praktika": { m: "a", a: "praktika", body: "new device", label: "Практика", at: 2, srv: T2 },
    "b#sec-1": { m: "b", a: "sec-1", label: "Теория", at: 1 },                       // bookmark already there
    "b#teoriya": { m: "b", a: "teoriya", label: "Теория", at: 2, srv: T2 }
  };
  const a = migrateRows(rows, "a", byPos, { copyLabel: "(copy)" });
  assert.strictEqual(a.rows["a#pid-copy-1"].body, "copy");
  assert.strictEqual(a.rows["a#praktika"].body, "new device");
  assert.deepStrictEqual([a.rows["a#praktika-copy-1"].body, a.rows["a#praktika-copy-1"].label], ["old device", "Практика (copy)"]);
  assert.ok(!a.rows["a#sec-4"] && !a.rows["a#sec-2-copy-1"]);
  const b = migrateRows(rows, "b", byPos);
  assert.deepStrictEqual(Object.keys(b.rows).filter((k) => k[0] === "b"), ["b#teoriya"]);
  assert.strictEqual(b.rows["b#teoriya"].srv, T2);
  for (const k of Object.keys(a.rows)) assert.match(a.rows[k].a, /^[A-Za-z0-9_-]{0,80}$/);
});

test("migration: `to` is asked once per old anchor, with the original's label; its copies follow it", () => {
  const seen = [];
  const moved = (an, label) => { seen.push([an, label]); return label === "PID" ? "praktika" : byPos(an); };   // the lesson changed
  const r = migrateRows({ "a#sec-2": { m: "a", a: "sec-2", label: "PID", body: "x" },
                          "a#sec-2-copy-3": { m: "a", a: "sec-2-copy-3", label: "PID (copy)", body: "y" } }, "a", moved);
  assert.deepStrictEqual(seen, [["sec-2", "PID"]]);
  assert.deepStrictEqual(Object.keys(r.rows).sort(), ["a#praktika", "a#praktika-copy-3"]);
});

test("migration: a copy whose original is gone goes by the copy label without its (copy …) suffix", () => {
  const seen = [];
  const r = migrateRows({ "a#sec-2-copy-1": { m: "a", a: "sec-2-copy-1", label: "Протокол (по данным) (копия с другого устройства)", body: "y" } },
                        "a", (an, label) => { seen.push(label); return byPos(an); });
  assert.deepStrictEqual(seen, ["Протокол (по данным)"]);
  assert.ok(r.rows["a#pid-copy-1"]);
});

test("migration: no double copy marker, no leftover error on the deletion, a legacy-looking target is refused", () => {
  const rows = { "a#sec-4": { m: "a", a: "sec-4", body: "old", label: "Практика (copy)", at: 1, srv: T1, err: "x" },
                 "a#praktika": { m: "a", a: "praktika", body: "new", label: "Практика", at: 2, srv: T2 } };
  const r = migrateRows(rows, "a", byPos, { copyLabel: "(copy)" });
  assert.strictEqual(r.rows["a#praktika-copy-1"].label, "Практика (copy)");
  assert.strictEqual(r.rows["a#sec-4"].del, true);
  assert.ok(!("err" in r.rows["a#sec-4"]));
  // an old cached page has runtime "sec-K" ids: never migrate onto another positional anchor
  assert.strictEqual(migrateRows({ "a#sec-9": { m: "a", a: "sec-9", body: "z" } }, "a", () => "sec-3").moved, 0);
});
