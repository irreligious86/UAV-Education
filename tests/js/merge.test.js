// node --test tests/js — pure merge rules of assets/account.js (local progress + server progress).
const test = require("node:test");
const assert = require("node:assert");
global.window = {};
const { merge } = require("../../assets/account.js");

test("union of done, checks and solved tasks", () => {
  const m = merge({ done: ["a"], checks: ["a:lab:0"], tasks: { a: { t1: true } } },
                  { done: ["b", "a"], checks: ["b:lab:1"], tasks: { a: { t2: true }, b: { t1: true } } });
  assert.deepStrictEqual(m.done, ["a", "b"]);
  assert.deepStrictEqual(m.checks, ["a:lab:0", "b:lab:1"]);
  assert.deepStrictEqual(m.tasks, { a: { t1: true, t2: true }, b: { t1: true } });
});

test("best quiz result wins, attempts and last keep the maximum", () => {
  const m = merge({ quiz: { q: { correct: 6, total: 8, ts: 5, attempts: 3, last: 9 } } },
                  { quiz: { q: { correct: 7, total: 8, ts: 2, attempts: 1, last: 2 } } });
  assert.strictEqual(m.quiz.q.correct, 7);
  assert.strictEqual(m.quiz.q.attempts, 3);
  assert.strictEqual(m.quiz.q.last, 9);
});

test("equal scores: newer result kept", () => {
  const m = merge({ quiz: { q: { correct: 8, total: 8, ts: 1 } } }, { quiz: { q: { correct: 8, total: 8, ts: 4 } } });
  assert.strictEqual(m.quiz.q.ts, 4);
});

test("lab results deduplicated by key, newest first", () => {
  const m = merge({ labs: [{ key: "x", ts: "2026-11-01" }] }, { labs: [{ key: "x", ts: "2026-11-01" }, { key: "y", ts: "2026-11-05" }] });
  assert.deepStrictEqual(m.labs.map(l => l.key), ["y", "x"]);
});

test("empty and missing documents", () => {
  assert.deepStrictEqual(merge(null, undefined), { done: [], checks: [], quiz: {}, tasks: {}, labs: [] });
  const local = { done: ["a"], quiz: { a: { correct: 1, total: 2 } } };
  assert.deepStrictEqual(merge(local, {}), merge({}, local));
});

test("merge is idempotent", () => {
  const a = { done: ["a"], checks: ["c"], quiz: { a: { correct: 5, total: 8, ts: 1 } }, tasks: { a: { t: true } }, labs: [{ key: "k" }] };
  const once = merge(a, a);
  assert.deepStrictEqual(merge(once, once), once);
});

test("false task flags dropped", () => {
  assert.deepStrictEqual(merge({ tasks: { a: { t1: false } } }, {}).tasks, { a: {} });
});

test("malformed documents never throw (security review M2)", () => {
  for (const bad of [{ done: 1 }, { labs: {} }, { labs: [null, "x", [1]] }, { checks: true }, { quiz: [] }, { tasks: "x" },
                     { done: [1, "a"] }, { quiz: { q: "x" } }, { tasks: { a: "y" } }, "string", 42, null, []]) {
    const m = merge(bad, { done: ["ok"] });
    assert.deepStrictEqual(m.done.includes("ok"), true);
  }
  assert.deepStrictEqual(merge({ done: [1, "a"] }, {}).done, ["a"]);
});
