// node --test tests/js — old positional anchors ("sec-N") resolved against the heading ids of a lesson page
// (assets/history.js legacyAnchor; the page side is covered by tests/e2e/notes.e2e.js).
const test = require("node:test");
const assert = require("node:assert");
global.window = {};
global.document = { readyState: "loading", addEventListener() {} };   // history.js starts on DOMContentLoaded
require("../../assets/history.js");
const { legacyAnchor } = window.UAVHistory;

const head = (id, text) => ({ id, cloneNode: () => ({ textContent: text, querySelectorAll: () => [] }) });
const heads = [head("teoriya", "Теория"), head("pid", "PID"), head("filtry", "Фильтры"), head("praktika", "Практика"), head("pid-2", "PID")];

test("sec-N is the N-th heading in document order", () => {
  assert.strictEqual(legacyAnchor(heads, "sec-1", ""), "teoriya");
  assert.strictEqual(legacyAnchor(heads, "sec-3", ""), "filtry");
  assert.strictEqual(legacyAnchor(heads, "sec-3", "Фильтры"), "filtry");
});

test("not an old anchor, still a real id, or no such heading: nothing to do", () => {
  assert.strictEqual(legacyAnchor(heads, "teoriya", ""), null);
  assert.strictEqual(legacyAnchor(heads, "sec-3-copy-1", ""), null);
  assert.strictEqual(legacyAnchor(heads, "sec-9", ""), null);
  assert.strictEqual(legacyAnchor([head("sec-1", "Теория")], "sec-1", ""), null);   // a page without build ids
});

test("the lesson changed: the saved heading text wins over the position (nearest match)", () => {
  // the bookmark was made on "Практика" when it was the 2nd heading; a heading was added above since
  assert.strictEqual(legacyAnchor(heads, "sec-2", "Практика"), "praktika");
  assert.strictEqual(legacyAnchor(heads, "sec-5", "PID"), "pid-2");
  assert.strictEqual(legacyAnchor(heads, "sec-1", "PID"), "pid");
  assert.strictEqual(legacyAnchor(heads, "sec-2", "Renamed heading"), "pid");      // unknown text: by position
});
