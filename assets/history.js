/* Reading history: remembers the lesson and the section you were reading, for guests and signed-in users alike.
 * Stored in this browser (localStorage "uav-student:history:v1"); a signed-in account will sync it later
 * (docs/MULTIUSER-PLAN.md). Used by:
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
  function hrefOf(item) { return base() + item.path + (item.anchor ? "#" + encodeURIComponent(item.anchor) : ""); }

  // ------------------------------------------------------------------ lesson page: record
  function trackLesson(article) {
    var parts = location.pathname.split("/").filter(Boolean);
    if (parts.length < 2) return;
    var path = parts.slice(-2).join("/");                 // "m/bf-pid.html", "cap/…", "projects/…"
    var h1 = article.querySelector("h1");
    var item = { id: article.getAttribute("data-module-page"), path: path, title: h1 ? h1.textContent.trim() : document.title,
                 anchor: "", heading: "", at: Date.now() };
    // section headings of the lesson; ones without an id get a positional one ("sec-3") so a link can return there
    var heads = Array.prototype.slice.call(article.querySelectorAll(".module-body h2, .module-body h3, .module-body h4.md-subheading"));
    heads.forEach(function (el, i) { if (!el.id) el.id = "sec-" + (i + 1); });
    if (location.hash) { var target = document.getElementById(decodeURIComponent(location.hash.slice(1))); if (target) setTimeout(function () { target.scrollIntoView(); }, 0); }

    function save() {
      item.at = Date.now();
      var h = read();
      h.items = [item].concat(h.items.filter(function (x) { return x.id !== item.id; })).slice(0, MAX);
      h.last = item.id;
      write(h);
    }
    function current() {
      var top = 120, best = null;
      heads.forEach(function (el) { if (el.getBoundingClientRect().top <= top) best = el; });
      item.anchor = best ? best.id : "";
      item.heading = best ? best.textContent.replace(/[#¶]\s*$/, "").trim() : "";
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
  window.UAVHistory = { read: read };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
