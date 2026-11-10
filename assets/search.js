/*
 * Client-side search over api/v1/search.json (built by scripts/build_site.py).
 * Scoring: title match > tags/headings > summary > body; all query words must match
 * somewhere (AND), prefix matching so "фильтр" finds "фильтры" and "rpm_filter".
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";
  var input = document.getElementById("q");
  var status = document.getElementById("search-status");
  var out = document.getElementById("search-results");
  if (!input) return;

  var docs = null;
  function norm(s) {
    // lower-case, ё→е, punctuation to spaces (keep _ and - inside identifiers)
    return (s || "").toLowerCase().replace(/ё/g, "е").replace(/[^\p{L}\p{N}_\-\s]/gu, " ").replace(/\s+/g, " ");
  }

  function prep(d) {
    d._title = norm(d.title); d._tags = norm(d.tags + " " + d.headings);
    d._summary = norm(d.summary); d._text = norm(d.text);
    return d;
  }

  // Word-prefix match: "фильтр" hits "фильтры", "rpm" hits "rpm_filter_min_hz",
  // but "ned" does not hit "снижение". Identifiers count as one word.
  function has(field, w) {
    return field.indexOf(" " + w) !== -1 || field.indexOf(w) === 0;
  }

  function score(d, words) {
    var total = 0;
    for (var i = 0; i < words.length; i++) {
      var w = words[i], s = 0;
      if (has(d._title, w)) s += 10;
      if (has(d._tags, w)) s += 5;
      if (has(d._summary, w)) s += 3;
      if (has(d._text, w)) s += 1;
      if (!s) return 0;           // every word must match somewhere
      total += s;
    }
    if (d.type === "term") total += 2;
    return total;
  }

  function snippet(d, words) {
    var src = d.summary || d.text || "";
    var low = norm(src), pos = -1;
    for (var i = 0; i < words.length && pos === -1; i++) pos = low.indexOf(words[i]);
    if (pos === -1) return src.slice(0, 160);
    var start = Math.max(0, pos - 60);
    return (start ? "…" : "") + src.slice(start, start + 180) + "…";
  }

  function render(q) {
    var words = norm(q).split(/\s+/).filter(function (w) { return w.length >= 2; });
    out.innerHTML = "";
    if (!words.length) { status.textContent = T("Начни вводить запрос."); return; }
    var hits = docs.map(function (d) { return { d: d, s: score(d, words) }; })
      .filter(function (h) { return h.s > 0; })
      .sort(function (a, b) { return b.s - a.s; })
      .slice(0, 30);
    status.textContent = hits.length ? T("Найдено: ") + hits.length : T("Ничего не найдено. Попробуй другое слово или термин на английском.");
    var base = document.body.getAttribute("data-base") || "../";
    hits.forEach(function (h) {
      var d = h.d;
      var a = document.createElement("a");
      a.className = "gc-card search-hit"; a.href = base + d.url;
      var kind = d.type === "term" ? T("термин") : d.type === "capstone" ? T("итоговый проект") : T("модуль");
      a.innerHTML = '<p class="gc-label gc-muted">' + kind + (d.group ? " · " + d.group : "") + (d.level ? " · " + d.level : "") + "</p>" +
        "<strong></strong><p class=\"search-hit__snippet\"></p>";
      a.querySelector("strong").textContent = d.title;
      a.querySelector(".search-hit__snippet").textContent = snippet(d, words);
      out.appendChild(a);
    });
  }

  var timer = null;
  input.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(function () { if (docs) render(input.value); }, 120);
  });

  var base = document.body.getAttribute("data-base") || "../";
  fetch(base + "api/v1/search.json").then(function (r) { return r.json(); }).then(function (list) {
    docs = list.map(prep);
    var q = new URLSearchParams(location.search).get("q");
    if (q) { input.value = q; }
    render(input.value);
    input.focus();
  }).catch(function () { status.textContent = T("Индекс поиска недоступен."); });
})();
