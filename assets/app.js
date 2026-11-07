/*
 * Page behaviour: status chips, progress bars, done toggle, checklists.
 * Reads through window.UAVGrading.load() (which reads window.UAVProgress).
 * Without JS the site is fully readable; only progress tracking is missing.
 */
(function () {
  "use strict";

  function ids(attr) { return attr ? attr.split(",").filter(Boolean) : []; }

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
        badge.textContent = label === "ОСВОЕН" && caps[el.getAttribute("data-module-id")] ? "СДАН" : label;
        badge.setAttribute("data-state", window.UAVGrading.statusState(g) || "ok");
      }
    });

    var page = document.querySelector("[data-module-page]");
    if (page) {
      var id = page.getAttribute("data-module-page"), g = gradeOf(id);
      var badge = page.querySelector(".module-tags [data-done-badge]");
      if (badge && g) {
        var label = window.UAVGrading.statusLabel(g);
        badge.hidden = !label; badge.textContent = (label === "ОСВОЕН" && caps[id]) ? "СДАН" : label;
        badge.setAttribute("data-state", window.UAVGrading.statusState(g) || "ok");
      }
      var sc = document.querySelector("[data-module-score]");
      if (sc && grades[id]) {
        var gr = grades[id], parts = [];
        if (gr.hasQuiz) parts.push("квиз " + (gr.quizPct === null ? "—" : gr.quizPct + "%"));
        if (gr.labTotal) parts.push("лаба " + gr.labDone + "/" + gr.labTotal);
        sc.textContent = "Балл модуля: " + gr.score + "/100 · " + parts.join(" · ");
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
      label.textContent = list.length ? "освоено " + gg.passed + " из " + gg.total + " · балл " + gg.score : "";
    });

    document.querySelectorAll("[data-done-toggle]").forEach(function (btn) {
      var id = btn.getAttribute("data-done-toggle"), g = gradeOf(id);
      var isCap = !!caps[id];
      var earned = g && g.status === "passed" && !g.selfMarked;
      var marked = G.state.done.has(id);
      if (earned && !marked) {
        btn.textContent = isCap ? "✓ Сдан по критериям" : "✓ Освоен: квиз сдан, лабораторная выполнена";
        btn.setAttribute("variant", "primary"); btn.setAttribute("disabled", "");
      } else {
        btn.removeAttribute("disabled");
        btn.textContent = marked ? "✓ Отмечен вручную — снять отметку" : (isCap ? "Отметить сданным без критериев" : "Отметить пройденным без квиза и лабы");
        btn.setAttribute("variant", marked ? "primary" : "secondary");
      }
    });
  }

  var base = document.body.getAttribute("data-base") || "";

  function refresh() {
    return window.UAVGrading.load(base).then(render).catch(function () { /* no grading meta (offline/file://): page stays readable */ });
  }

  function init() {
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
