/* Reading history: remembers the lesson and the section you were reading, for guests and signed-in users alike.
 * Stored in this browser (localStorage "uav-student:history:v1"); for a signed-in account assets/user-data.js syncs it
 * (table user_history, docs/MULTIUSER-PLAN.md §14). Used by:
 *   - lesson pages (<article data-module-page>): records the lesson and the heading in view;
 *   - the home page ([data-resume]): a "continue where you stopped" card, and an optional jump to the last
 *     lesson when the course is opened (setting resumeOnOpen on the account page);
 *   - the progress page ([data-history-list]): the recent lessons.
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";
  var KEY = "uav-student:history:v1";
  var SETTINGS = "uav-student:settings";
  var MAX = 30;

  function read() {
    try { var v = JSON.parse(localStorage.getItem(KEY) || "{}"); return v && Array.isArray(v.items) ? v : { items: [] }; }
    catch (e) { return { items: [] }; }
  }
  function write(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) { /* storage off: history is a convenience */ } }
  function setting(name) { try { return !!(JSON.parse(localStorage.getItem(SETTINGS) || "{}") || {})[name]; } catch (e) { return false; } }
  function base() { return (document.body && document.body.getAttribute("data-base")) || ""; }

  function ago(ts) {
    var s = Math.max(0, (Date.now() - ts) / 1000);
    if (s < 90) return T("только что");
    if (s < 3600) return Math.round(s / 60) + " " + T("мин назад");
    if (s < 86400) return Math.round(s / 3600) + " " + T("ч назад");
    return Math.round(s / 86400) + " " + T("дн назад");
  }
  // Section headings of a lesson body. The build gives each a stable id from its text (scripts/content_pipeline.py
  // assign_heading_ids), the same in every language where the structure matches; notes, bookmarks and feedback
  // (assets/notes.js) use the same ids. A heading without one (a page built before that) gets the old positional id
  // ("sec-3"). Idempotent.
  function headings(article) {
    var heads = Array.prototype.slice.call(article.querySelectorAll(".module-body h2, .module-body h3, .module-body h4.md-subheading"));
    heads.forEach(function (el, i) { if (!el.id) el.id = "sec-" + (i + 1); });
    return heads;
  }
  // heading text without the buttons notes.js puts inside it
  function headingText(el) {
    var c = el.cloneNode(true);
    c.querySelectorAll(".nb-tools").forEach(function (t) { t.remove(); });
    return c.textContent.replace(/[#¶]\s*$/, "").trim();
  }
  // Anchors saved before the build ids existed were positional: "sec-N" = the N-th heading of the selector above,
  // in document order. legacyAnchor(heads, "sec-3", label) -> the id that place has now, or null when the anchor is
  // not an old one (or still exists as it is: an old page) or there is no such heading any more. When the lesson
  // changed since, the saved heading text (label) wins over the position: the heading with that text nearest to
  // the old position, else the N-th heading.
  var LEGACY = /^sec-(\d+)$/;
  function legacyAnchor(heads, anchor, label) {
    var m = LEGACY.exec(anchor || "");
    if (!m || heads.some(function (h) { return h.id === anchor; })) return null;
    var n = parseInt(m[1], 10) - 1, at = heads[n] || null;
    label = String(label || "").trim().slice(0, 160);
    if (label) {
      var text = function (h) { return headingText(h).slice(0, 160); };
      if (at && text(at) === label) return at.id;
      var best = null;
      heads.forEach(function (h, i) { if (text(h) === label && (!best || Math.abs(i - n) < Math.abs(best.i - n))) best = { h: h, i: i }; });
      if (best) return best.h.id;
    }
    return at ? at.id : null;
  }
  // The heading text saved with an old anchor of this lesson, if this browser has one: a history entry ("heading"),
  // or a note / bookmark not migrated yet ("label"; notes.js migrates them after this runs). Lets an old link land
  // by text when the lesson changed since, like the migration does.
  function savedLabel(moduleId, anchor) {
    var it = read().items.filter(function (x) { return x.id === moduleId && x.anchor === anchor && x.heading; })[0];
    if (it) return it.heading;
    var k = moduleId + "#" + anchor, label = "";
    ["uav-student:bookmarks:v1", "uav-student:notes:v1"].forEach(function (store) {
      try { var r = (JSON.parse(localStorage.getItem(store) || "{}") || {})[k]; if (!label && r && r.label) label = String(r.label); } catch (e) { /* storage off */ }
    });
    return label;
  }
  function hashAnchor() {
    var a = location.hash.slice(1);
    try { a = decodeURIComponent(a); } catch (e) { /* keep as typed */ }
    return a;
  }
  // only an old "#sec-N" that is no id of this page needs resolving; every other hash is the browser's business
  function isLegacyHash() { var a = hashAnchor(); return LEGACY.test(a) && !document.getElementById(a); }
  // the element an old "#sec-N" link of this page means now (and the address is fixed to its id), or null
  function hashTarget(heads, moduleId) {
    if (!location.hash || !isLegacyHash()) return null;
    var a = hashAnchor();
    var id = legacyAnchor(heads, a, savedLabel(moduleId, a));
    if (!id) return null;
    try { history.replaceState(history.state, "", "#" + encodeURIComponent(id)); } catch (e) { /* file:// or old browser */ }
    return document.getElementById(id);
  }
  function hrefOf(item) { return base() + item.path + (item.anchor ? "#" + encodeURIComponent(item.anchor) : ""); }

  // ------------------------------------------------------------------ lesson page: record
  function trackLesson(article) {
    var parts = location.pathname.split("/").filter(Boolean);
    if (parts.length < 2) return;
    var path = parts.slice(-2).join("/");                 // "m/bf-pid.html", "cap/…", "projects/…"
    var h1 = article.querySelector("h1");
    var item = { id: article.getAttribute("data-module-page"), path: path, title: h1 ? h1.textContent.trim() : document.title,
                 anchor: "", heading: "", at: Date.now() };
    var heads = headings(article);
    // an old link (history, bookmark lists, feedback) may still say "#sec-N": land on that heading and fix the address
    var go = function (target) { if (target) setTimeout(function () { target.scrollIntoView(); }, 0); };
    go(location.hash ? hashTarget(heads, item.id) || document.getElementById(hashAnchor()) : null);   // at load, as before
    window.addEventListener("hashchange", function () { if (isLegacyHash()) go(hashTarget(heads, item.id)); });

    function save() {
      item.at = Date.now();
      var h = read();
      h.items = [item].concat(h.items.filter(function (x) { return x.id !== item.id; })).slice(0, MAX);
      h.last = item.id;
      write(h);
      if (window.UAVUserData) window.UAVUserData.touched("history");
    }
    function current() {
      var top = 120, best = null;
      heads.forEach(function (el) { if (el.getBoundingClientRect().top <= top) best = el; });
      item.anchor = best ? best.id : "";
      item.heading = best ? headingText(best) : "";
    }
    var timer = null;
    window.addEventListener("scroll", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { current(); save(); }, 400);
    }, { passive: true });
    window.addEventListener("pagehide", function () { current(); save(); });
    document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") { current(); save(); } });
    save();
  }

  // ------------------------------------------------------------------ home page: continue card, optional jump
  function resumeCard(box) {
    var h = read();
    var last = h.items.filter(function (x) { return x.id === h.last; })[0] || h.items[0];
    if (!last) return;
    if (setting("resumeOnOpen")) {
      var jumped = false;
      try { jumped = sessionStorage.getItem("uav-student:resumed") === "1"; sessionStorage.setItem("uav-student:resumed", "1"); } catch (e) { jumped = true; }
      if (!jumped && !location.hash) { location.replace(hrefOf(last)); return; }
    }
    box.href = hrefOf(last);
    box.replaceChildren();
    var label = document.createElement("span"); label.className = "gc-label gc-muted"; label.textContent = T("Продолжить с того места, где остановился");
    var title = document.createElement("strong"); title.textContent = last.title;
    var meta = document.createElement("div"); meta.className = "gc-muted";
    meta.textContent = (last.heading ? T("раздел") + " «" + last.heading + "» · " : "") + ago(last.at);
    box.append(label, title, meta);
    box.hidden = false;
  }

  // ------------------------------------------------------------------ progress page: recent lessons
  function historyList(box) {
    var h = read();
    box.replaceChildren();
    if (!h.items.length) {
      var p = document.createElement("p"); p.className = "gc-muted"; p.textContent = T("История пуста: открой любой урок, и он появится здесь.");
      box.append(p); return;
    }
    var ol = document.createElement("ol"); ol.className = "history-list";
    h.items.forEach(function (it) {
      var li = document.createElement("li");
      var a = document.createElement("a"); a.href = hrefOf(it); a.textContent = it.title;
      var m = document.createElement("span"); m.className = "gc-muted";
      m.textContent = " · " + (it.heading ? "«" + it.heading + "» · " : "") + ago(it.at);
      li.append(a, m); ol.append(li);
    });
    var clear = document.createElement("button"); clear.type = "button"; clear.className = "gc-tag"; clear.textContent = T("Очистить историю");
    clear.addEventListener("click", function () { write({ items: [] }); historyList(box); });
    box.append(ol, clear);
  }

  function start() {
    var art = document.querySelector("article[data-module-page]");
    if (art) trackLesson(art);
    document.querySelectorAll("[data-resume]").forEach(resumeCard);
    document.querySelectorAll("[data-history-list]").forEach(historyList);
  }
  window.UAVHistory = { read: read, headings: headings, headingText: headingText, legacyAnchor: legacyAnchor };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
