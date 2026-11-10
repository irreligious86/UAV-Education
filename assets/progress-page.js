/* Fills pages/progress.html from UAVGrading.load(); export / import / reset. */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";
  var base = document.body.getAttribute("data-base") || "../";
  var G = window.UAVGrading;

  var verified = {};   // module id -> number of lab criteria confirmed by an imported grader result

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }

  function fillLabs(list) {
    verified = {};
    var seen = {};
    list.forEach(function (r) {
      if (!r.pass && !r.marks.length) return;
      r.marks.forEach(function (m) { if (!seen[m]) { seen[m] = 1; var id = m.split(":")[0]; verified[id] = (verified[id] || 0) + 1; } });
    });
    var box = document.querySelector("[data-lab-results]");
    if (!box) return;
    box.innerHTML = list.length ? list.map(function (r) {
      return '<li><span class="gc-tag" data-state="' + (r.pass ? "ok" : "caution") + '">' + (r.pass ? "PASS" : "FAIL") + "</span> " +
        "<code>" + esc(r.grader) + " --lab " + esc(r.labs.join(",")) + "</code> · " + esc(r.name) + " · " + esc(r.generated.slice(0, 10)) +
        ' · <span class="gc-muted">sha256 ' + esc(r.sha256.slice(0, 12)) + "…</span>" +
        (r.marks.length ? T(" · отмечено: ") + r.marks.map(function (m) { return "<code>" + esc(m) + "</code>"; }).join(", ") : "") + "</li>";
    }).join("") : T('<li class="gc-muted">Пока нет. Запусти грейдер с <code>--json result.json</code> и загрузи файл.</li>');
  }

  // Validate a uav-lab-result/1 file against the grading meta; returns a summary or throws with a reason.
  function parseLabResult(data, meta) {
    if (!data || data.schema !== "uav-lab-result/1") throw new Error(T("это не файл результата грейдера (нет schema uav-lab-result/1)"));
    var labN = {};
    meta.modules.forEach(function (m) { labN[m.id] = m.lab || 0; });
    var marks = (data.marks || []).filter(function (m) {
      var p = /^([a-z0-9-]+):lab:(\d+)$/.exec(m);
      return p && labN[p[1]] > Number(p[2]);
    });
    if (!data.input || !/^[0-9a-f]{64}$/.test(data.input.sha256 || "")) throw new Error(T("нет контрольной суммы входного лога"));
    return { grader: String(data.grader || "?"), labs: (data.labs || []).map(function (l) { return String(l.lab); }),
             pass: !!data.pass, generated: String(data.generated || ""), name: String(data.input.name || ""),
             sha256: data.input.sha256, marks: marks, ignored: (data.marks || []).length - marks.length };
  }

  function fill(R) {
    var grades = R.grades, caps = R.caps;
    document.querySelectorAll("[data-row]").forEach(function (tr) {
      var g = grades[tr.getAttribute("data-row")];
      if (!g) return;
      tr.querySelector('[data-cell="quiz"]').textContent = (g.hasQuiz ? (g.quizPct === null ? "—" : g.quizPct + "%") : T("нет")) + (g.tasksTotal ? T(" · з. ") + g.tasksDone + "/" + g.tasksTotal : "");
      var v = verified[g.id] || 0;
      tr.querySelector('[data-cell="lab"]').textContent = g.labTotal ? g.labDone + "/" + g.labTotal + (v ? " · ⚙" + v : "") : T("нет");
      tr.querySelector('[data-cell="score"]').textContent = g.score;
      var st = tr.querySelector('[data-cell="status"]');
      var label = G.statusLabel(g);
      st.innerHTML = label ? '<span class="gc-tag" data-state="' + G.statusState(g) + '">' + label + "</span>" : "";
    });
    document.querySelectorAll("[data-group-summary]").forEach(function (el) {
      var ids = el.getAttribute("data-group-summary").split(",").filter(Boolean);
      var gg = G.groupGrade(ids, grades);
      el.textContent = T("Освоено ") + gg.passed + T(" из ") + gg.total + T(" · средний балл ") + gg.score + (gg.allPassed ? T(" · ✓ всё освоено") : "");
    });
    document.querySelectorAll("[data-progress-of]").forEach(function (bar) {
      var ids = bar.getAttribute("data-progress-of").split(",").filter(Boolean);
      var gg = G.groupGrade(ids, grades);
      bar.style.setProperty("--gc-value", gg.score + "%"); bar.setAttribute("aria-valuenow", String(gg.score));
    });
    document.querySelectorAll("[data-cap]").forEach(function (li) {
      var c = caps[li.getAttribute("data-cap")], tag = li.querySelector("[data-cap-status]");
      if (!c) return;
      tag.textContent = c.passed ? (c.selfMarked ? T("ОТМЕЧЕН") : T("СДАН")) : (c.done ? c.done + "/" + c.total : T("не начат"));
      tag.setAttribute("data-state", c.passed ? (c.selfMarked ? "info" : "ok") : (c.done ? "caution" : ""));
    });
  }

  var lastMeta = null;

  function refresh() {
    var labs = window.UAVProgress.getLabResults ? window.UAVProgress.getLabResults() : Promise.resolve([]);
    return labs.then(fillLabs).then(function () { return G.load(base); }).then(function (R) { lastMeta = R.meta; fill(R); }).catch(function () {
      var h = document.querySelector(".progress-headline");
      if (h) h.textContent = T("Не удалось загрузить данные оценок.");
    });
  }

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
      }).catch(function () { alert(T("Не удалось прочитать файл прогресса.")); });
    });
    var labIn = document.querySelector("[data-lab-import]");
    if (labIn) labIn.addEventListener("change", function () {
      var f = labIn.files[0], msg = document.querySelector("[data-lab-msg]");
      if (!f) return;
      f.text().then(function (txt) {
        var data = JSON.parse(txt);
        var meta = lastMeta ? Promise.resolve(lastMeta) : fetch(base + "api/v1/grading.json").then(function (r) { return r.json(); });
        return meta.then(function (m) {
          var r = parseLabResult(data, m);
          return window.UAVProgress.addLabResult(r).then(function (added) {
            if (msg) msg.textContent = !added ? T("Этот результат уже загружен.") :
              (r.marks.length ? T("Отмечено пунктов лабораторных: ") + r.marks.length + "." : T("Результат сохранён; пункты не отмечены — проверки не пройдены.")) +
              (r.ignored ? T(" Неизвестных пунктов пропущено: ") + r.ignored + "." : "");
            return refresh();
          });
        });
      }).catch(function (e) { if (msg) msg.textContent = T("Не удалось загрузить: ") + (e && e.message ? e.message : T("неверный файл")); });
      labIn.value = "";
    });
    var rst = document.querySelector("[data-reset]");
    if (rst) rst.addEventListener("click", function () {
      if (confirm(T("Стереть весь прогресс в этом браузере?"))) window.UAVProgress.reset().then(refresh);
    });
  });
})();
