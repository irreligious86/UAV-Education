/* Fills pages/progress.html from UAVGrading.load(); export / import / reset. */
(function () {
  "use strict";
  var base = document.body.getAttribute("data-base") || "../";
  var G = window.UAVGrading;

  function fill(R) {
    var grades = R.grades, caps = R.caps;
    document.querySelectorAll("[data-row]").forEach(function (tr) {
      var g = grades[tr.getAttribute("data-row")];
      if (!g) return;
      tr.querySelector('[data-cell="quiz"]').textContent = g.hasQuiz ? (g.quizPct === null ? "—" : g.quizPct + "%") : "нет";
      tr.querySelector('[data-cell="lab"]').textContent = g.labTotal ? g.labDone + "/" + g.labTotal : "нет";
      tr.querySelector('[data-cell="score"]').textContent = g.score;
      var st = tr.querySelector('[data-cell="status"]');
      var label = G.statusLabel(g);
      st.innerHTML = label ? '<span class="gc-tag" data-state="' + G.statusState(g) + '">' + label + "</span>" : "";
    });
    document.querySelectorAll("[data-group-summary]").forEach(function (el) {
      var ids = el.getAttribute("data-group-summary").split(",").filter(Boolean);
      var gg = G.groupGrade(ids, grades);
      el.textContent = "Освоено " + gg.passed + " из " + gg.total + " · средний балл " + gg.score + (gg.allPassed ? " · ✓ всё освоено" : "");
    });
    document.querySelectorAll("[data-progress-of]").forEach(function (bar) {
      var ids = bar.getAttribute("data-progress-of").split(",").filter(Boolean);
      var gg = G.groupGrade(ids, grades);
      bar.style.setProperty("--gc-value", gg.score + "%"); bar.setAttribute("aria-valuenow", String(gg.score));
    });
    document.querySelectorAll("[data-cap]").forEach(function (li) {
      var c = caps[li.getAttribute("data-cap")], tag = li.querySelector("[data-cap-status]");
      if (!c) return;
      tag.textContent = c.passed ? (c.selfMarked ? "ОТМЕЧЕН" : "СДАН") : (c.done ? c.done + "/" + c.total : "не начат");
      tag.setAttribute("data-state", c.passed ? (c.selfMarked ? "info" : "ok") : (c.done ? "caution" : ""));
    });
  }

  function refresh() { return G.load(base).then(fill); }

  document.addEventListener("DOMContentLoaded", function () {
    refresh();
    var exp = document.querySelector("[data-export]");
    if (exp) exp.addEventListener("click", function () {
      var raw = "{}";
      try { raw = window.localStorage.getItem("uav-student:progress:v1") || "{}"; } catch (e) {}
      var blob = new Blob([raw], { type: "application/json" });
      var a = document.createElement("a"); a.href = URL.createObjectURL(blob);
      a.download = "uav-student-progress-" + new Date().toISOString().slice(0, 10) + ".json"; a.click();
    });
    var imp = document.querySelector("[data-import]");
    if (imp) imp.addEventListener("change", function () {
      var f = imp.files[0]; if (!f) return;
      f.text().then(function (txt) {
        var data = JSON.parse(txt);
        if (!data || typeof data !== "object") throw new Error("bad");
        try { window.localStorage.setItem("uav-student:progress:v1", JSON.stringify(data)); } catch (e) {}
        return refresh();
      }).catch(function () { alert("Не удалось прочитать файл прогресса."); });
    });
    var rst = document.querySelector("[data-reset]");
    if (rst) rst.addEventListener("click", function () {
      if (confirm("Стереть весь прогресс в этом браузере?")) window.UAVProgress.reset().then(refresh);
    });
  });
})();
