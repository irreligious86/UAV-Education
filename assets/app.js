/*
 * Page behaviour: status chips, progress bars, done toggle, checklists.
 * Reads through window.UAVGrading.load() (which reads window.UAVProgress).
 * Without JS the site is fully readable; only progress tracking is missing.
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";

  function ids(attr) { return attr ? attr.split(",").filter(Boolean) : []; }

  /* --- Firmware paths: independent, parallel progress ---------------------
   * Which path the student is "in" comes from ?path=<id> on the URL; it is
   * remembered per browser so the next click keeps the same context.
   * «Продолжить» = first published step of that path not yet passed.      */
  var PATH_KEY = "uav-student:active-path";
  function activePath() {
    var q = /[?&]path=([a-z0-9-]+)/.exec(location.search);
    if (q) { try { localStorage.setItem(PATH_KEY, q[1]); } catch (e) { /* storage unavailable */ } return q[1]; }
    try { return localStorage.getItem(PATH_KEY) || ""; } catch (e) { return ""; }
  }
  function steps(attr) {
    return (attr || "").split(";;").filter(Boolean).map(function (s) { var i = s.indexOf("|"); return { id: s.slice(0, i), title: s.slice(i + 1) }; });
  }
  function renderPaths(G) {
    var grades = G.grades;
    document.querySelectorAll("[data-path-continue]").forEach(function (el) {
      var pid = el.getAttribute("data-path-continue"), list = steps(el.getAttribute("data-path-steps"));
      if (!list.length) return;
      var passed = 0, next = null;
      list.forEach(function (s) { var g = grades[s.id]; if (g && g.status === "passed") passed++; else if (!next) next = s; });
      var isCard = el.tagName === "A";
      var href = base + "m/" + (next ? next.id : list[list.length - 1].id) + ".html?path=" + pid;
      el.hidden = false;
      if (isCard) {
        el.setAttribute("href", href);
        el.innerHTML = next
          ? '<span class="gc-label gc-muted">' + (passed ? T("Продолжить · шаг ") + (list.indexOf(next) + 1) + T(" из ") + list.length : T("Начать путь")) + '</span><br><strong>' + next.title + "</strong>"
          : T('<span class="gc-label gc-muted">Все шаги пройдены</span><br><strong>Повторить последний шаг</strong>');
      } else {
        el.textContent = next ? (passed ? T("Продолжить: ") : T("Начать: ")) + next.title : T("Все шаги пройдены");
        el.setAttribute("data-next-href", href);
      }
    });
    // home cards: a click on «Продолжить» goes straight to the step
    document.querySelectorAll("[data-path-card]").forEach(function (card) {
      var cont = card.querySelector("[data-path-continue]");
      if (cont && cont.getAttribute("data-next-href") && !card.getAttribute("data-path-bound")) {
        card.setAttribute("data-path-bound", "1");
        cont.classList.add("path-card__link");
        cont.addEventListener("click", function (e) { e.preventDefault(); location.href = cont.getAttribute("data-next-href"); });
      }
    });
  }
  function applyPathContext() {
    var pid = activePath();
    var pagers = document.querySelectorAll("[data-path-pager]");
    if (!pagers.length) return;
    var match = null;
    pagers.forEach(function (n) { if (n.getAttribute("data-path-pager") === pid) match = n; });
    var trackPager = document.querySelector("[data-track-pager]");
    if (match) {
      match.hidden = false;
      if (trackPager) trackPager.hidden = true;
      document.querySelectorAll("[data-path-pos]").forEach(function (li) { li.classList.toggle("is-active", li.getAttribute("data-path-pos") === pid); });
    }
  }

  function render(G) {
    var grades = G.grades, caps = G.caps;

    function gradeOf(id) { return grades[id] || (caps[id] ? { status: caps[id].passed ? "passed" : (caps[id].done ? "active" : "none"), selfMarked: caps[id].selfMarked, score: caps[id].total ? Math.round(100 * caps[id].done / caps[id].total) : 0 } : null); }

    document.querySelectorAll("[data-module-id]").forEach(function (el) {
      var g = gradeOf(el.getAttribute("data-module-id"));
      if (!g) return;
      el.classList.toggle("is-done", g.status === "passed");
      var badge = el.querySelector("[data-done-badge]");
      if (badge) {
        var label = window.UAVGrading.statusLabel(g);
        badge.hidden = !label;
        badge.textContent = label === T("ОСВОЕН") && caps[el.getAttribute("data-module-id")] ? T("СДАН") : label;
        badge.setAttribute("data-state", window.UAVGrading.statusState(g) || "ok");
      }
    });

    var page = document.querySelector("[data-module-page]");
    if (page) {
      var id = page.getAttribute("data-module-page"), g = gradeOf(id);
      var badge = page.querySelector(".module-tags [data-done-badge]");
      if (badge && g) {
        var label = window.UAVGrading.statusLabel(g);
        badge.hidden = !label; badge.textContent = (label === T("ОСВОЕН") && caps[id]) ? T("СДАН") : label;
        badge.setAttribute("data-state", window.UAVGrading.statusState(g) || "ok");
      }
      var sc = document.querySelector("[data-module-score]");
      if (sc && grades[id]) {
        var gr = grades[id], parts = [];
        if (gr.hasQuiz) parts.push(T("квиз ") + (gr.quizPct === null ? "—" : gr.quizPct + "%"));
        if (gr.tasksTotal) parts.push(T("задачи ") + gr.tasksDone + "/" + gr.tasksTotal);
        if (gr.labTotal) parts.push(T("лаба ") + gr.labDone + "/" + gr.labTotal);
        sc.textContent = T("Балл модуля: ") + gr.score + "/100 · " + parts.join(" · ");
      }
    }

    document.querySelectorAll("[data-progress-of]").forEach(function (bar) {
      var list = ids(bar.getAttribute("data-progress-of"));
      var gg = window.UAVGrading.groupGrade(list, grades);
      bar.style.setProperty("--gc-value", gg.score + "%");
      bar.setAttribute("aria-valuenow", String(gg.score));
    });

    document.querySelectorAll("[data-progress-label]").forEach(function (label) {
      var list = ids(label.getAttribute("data-progress-label"));
      var gg = window.UAVGrading.groupGrade(list, grades);
      label.textContent = list.length ? T("освоено ") + gg.passed + T(" из ") + gg.total + T(" · балл ") + gg.score : "";
    });

    renderPaths(G);

    document.querySelectorAll("[data-done-toggle]").forEach(function (btn) {
      var id = btn.getAttribute("data-done-toggle"), g = gradeOf(id);
      var isCap = !!caps[id];
      var earned = g && g.status === "passed" && !g.selfMarked;
      var marked = G.state.done.has(id);
      if (earned && !marked) {
        btn.textContent = isCap ? T("✓ Сдан по критериям") : (g.tasksTotal ? T("✓ Освоен: квиз сдан, задачи решены, лабораторная выполнена") : T("✓ Освоен: квиз сдан, лабораторная выполнена"));
        btn.setAttribute("variant", "primary"); btn.setAttribute("disabled", "");
      } else {
        btn.removeAttribute("disabled");
        btn.textContent = marked ? T("✓ Отмечен вручную — снять отметку") : (isCap ? T("Отметить сданным без критериев") : T("Отметить пройденным без квиза и лабы"));
        btn.setAttribute("variant", marked ? "primary" : "secondary");
      }
    });
  }

  var base = document.body.getAttribute("data-base") || "";

  function refresh() {
    return window.UAVGrading.load(base).then(render).catch(function () { /* no grading meta (offline/file://): page stays readable */ });
  }

  var READY_KEY = "uav-student:ready-only";
  function initReadyFilter() {
    var boxes = document.querySelectorAll("[data-ready-only]");
    var on = false;
    try { on = localStorage.getItem(READY_KEY) === "1"; } catch (e) { /* storage unavailable */ }
    document.body.classList.toggle("ready-only", on);
    boxes.forEach(function (box) {
      box.checked = on;
      box.addEventListener("change", function () {
        document.body.classList.toggle("ready-only", box.checked);
        try { localStorage.setItem(READY_KEY, box.checked ? "1" : "0"); } catch (e) { /* storage unavailable */ }
      });
    });
  }

  function init() {
    initReadyFilter();
    applyPathContext();
    if (!window.UAVProgress || !window.UAVGrading) return;

    document.querySelectorAll("[data-done-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (btn.hasAttribute("disabled")) return;
        var id = btn.getAttribute("data-done-toggle");
        window.UAVProgress.getDone()
          .then(function (done) { return window.UAVProgress.setDone(id, !done.has(id)); })
          .then(refresh);
      });
    });

    var boxes = document.querySelectorAll("input[data-check-id]");
    if (boxes.length) {
      window.UAVProgress.getChecks("").then(function (checked) {
        boxes.forEach(function (box) {
          box.checked = checked.has(box.getAttribute("data-check-id"));
          box.addEventListener("change", function () {
            window.UAVProgress.setCheck(box.getAttribute("data-check-id"), box.checked).then(refresh);
          });
        });
      });
    }

    document.addEventListener("uav-quiz-result", refresh);
    refresh();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
