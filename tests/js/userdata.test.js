// node --test tests/js — merge rules of assets/user-data.js (notes, bookmarks, history: this browser + the server).
const test = require("node:test");
const assert = require("node:assert");
const { mergeRows, mergeHistory, cleanSettings, resolve, invalid } = require("../../assets/user-data.js");

const S = (m, a, body, t, label) => ({ module_id: m, anchor: a, label: label || "", body, updated_at: t });
const T1 = "2026-11-26T10:00:00.000Z", T2 = "2026-11-26T11:00:00.000Z";

test("a guest note goes up, a server-only note comes down", () => {
  const r = mergeRows({ "a#": { m: "a", a: "", body: "mine", at: 5, dirty: true, srv: null } }, [S("b", "sec-1", "theirs", T1)]);
  assert.deepStrictEqual(r.push, ["a#"]);
  assert.strictEqual(r.rows["b#sec-1"].body, "theirs");
  assert.strictEqual(r.rows["b#sec-1"].dirty, false);
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
  const r = mergeRows({ "a#sec-2": { m: "a", a: "sec-2", label: "PID", body: big, dirty: true, srv: T1 } }, [S("a", "sec-2", big + "y", T2, "PID")],
                      { max: 8000, copyLabel: "(copy)" });
  assert.strictEqual(r.rows["a#sec-2"].body, big + "y");
  assert.strictEqual(r.rows["a#sec-2"].dirty, false);
  assert.deepStrictEqual(r.push, ["a#sec-2-copy-1"]);
  assert.deepStrictEqual([r.rows["a#sec-2-copy-1"].body, r.rows["a#sec-2-copy-1"].label, r.rows["a#sec-2-copy-1"].srv], [big, "PID (copy)", null]);
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
  assert.strictEqual(invalid({ m: "bf-pid", a: "sec-3", body: "x" }, true), "");
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
  const a = { items: [{ id: "x", at: 5, anchor: "sec-1" }, { id: "y", at: 1 }] };
  const b = { items: [{ id: "x", at: 9, anchor: "sec-4" }, { id: "z", at: 3 }, { id: 7, at: 100 }] };
  const m = mergeHistory(a, b);
  assert.deepStrictEqual(m.items.map((i) => i.id), ["x", "z", "y"]);
  assert.strictEqual(m.items[0].anchor, "sec-4");
  assert.strictEqual(m.last, "x");
  const many = { items: Array.from({ length: 40 }, (_, i) => ({ id: "m" + i, at: i })) };
  assert.strictEqual(mergeHistory(many, {}).items.length, 30);
});

test("settings: only known keys with the right types reach the server", () => {
  assert.deepStrictEqual(cleanSettings({ readyOnly: true, notesPanel: false, firmwarePath: "inav", theme: "x" }), { readyOnly: true, notesPanel: false, firmwarePath: "inav" });
  assert.deepStrictEqual(cleanSettings({ readyOnly: "no", notesPanel: 1 }), {});   // no coercion
  assert.deepStrictEqual(cleanSettings({ firmwarePath: "Bad Path" }), {});
});
