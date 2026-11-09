/*
 * pages/admin.html: grades of all students (admin, superadmin), study groups (staff) and role management (superadmin).
 * The database decides what this page may read or change (RLS, set_role); the page only shows it.
 * Scores are computed with the same UAVGrading.moduleGrade the student sees.
 */
(function () {
  "use strict";

  var ROLE = { student: "студент", admin: "админ", superadmin: "суперадмин" };
  var base = "../";
  var model = { rows: [], meta: null, titles: {}, me: null, cohorts: [], members: [] };

  function $(sel) { return document.querySelector(sel); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function msg(text, state) { var el = $("[data-acc-msg]"); el.textContent = text || ""; el.setAttribute("data-state", state || ""); }
  function when(ts) { return ts ? new Date(ts).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" }) : "—"; }

  function gradeStudent(data) {
    data = window.UAVAccount.merge(data, {});
    var done = new Set(data.done), checks = new Set(data.checks);
    var grades = {}, sum = 0, mastered = 0;
    model.meta.modules.forEach(function (m) {
      var g = window.UAVGrading.moduleGrade(m, { quiz: data.quiz[m.id] || null, checks: checks, done: done, tasks: data.tasks[m.id] || {} });
      grades[m.id] = g; sum += g.score; if (g.earned) mastered++;
    });
    return { grades: grades, score: Math.round(sum / model.meta.modules.length), mastered: mastered, total: model.meta.modules.length };
  }

  function roleCell(r) {
    var me = model.me;
    if (me.isSuperadmin && r.role !== "superadmin" && r.id !== me.profile.id) {
      return '<select data-role-of="' + esc(r.id) + '" aria-label="Роль ' + esc(r.username) + '">' +
        ["student", "admin"].map(function (k) { return '<option value="' + k + '"' + (r.role === k ? " selected" : "") + ">" + ROLE[k] + "</option>"; }).join("") + "</select>";
    }
    return '<span class="gc-tag" data-state="' + (r.role === "superadmin" ? "critical" : r.role === "admin" ? "caution" : "ok") + '">' + ROLE[r.role] + "</span>";
  }

  // ------------------------------------------------------------------ cohorts
  function cohortName(id) { var c = model.cohorts.filter(function (x) { return x.id === id; })[0]; return c ? c.name : "?"; }
  function groupsOf(uid) {
    return model.members.filter(function (m) { return m.user_id === uid; }).map(function (m) { return m.cohort_id; })
      .sort(function (a, b) { return cohortName(a).localeCompare(cohortName(b), "ru"); });
  }

  function groupCell(r) {
    var mine = groupsOf(r.id);
    var chips = mine.map(function (cid) {
      return '<button type="button" class="gc-tag" data-unjoin="' + esc(cid) + '" data-user="' + esc(r.id) + '" title="убрать из группы">' + esc(cohortName(cid)) + " ×</button>";
    }).join(" ");
    var free = model.cohorts.filter(function (c) { return mine.indexOf(c.id) < 0; });
    var add = free.length ? ' <select data-join-of="' + esc(r.id) + '" aria-label="Добавить ' + esc(r.username) + ' в группу"><option value="">+ группа</option>' +
      free.map(function (c) { return '<option value="' + esc(c.id) + '">' + esc(c.name) + "</option>"; }).join("") + "</select>" : "";
    return (chips || (model.cohorts.length ? "" : '<span class="gc-muted">—</span>')) + add;
  }

  function renderCohorts() {
    var sel = $("[data-adm-cohort]"), cur = sel.value;
    sel.innerHTML = '<option value="">все группы</option><option value="-">без группы</option>' + model.cohorts.map(function (c) {
      return '<option value="' + esc(c.id) + '">' + esc(c.name) + "</option>";
    }).join("");
    sel.value = model.cohorts.some(function (c) { return c.id === cur; }) || cur === "-" ? cur : "";
    $("[data-adm-cohorts]").innerHTML = model.cohorts.length ? model.cohorts.map(function (c) {
      var n = model.members.filter(function (m) { return m.cohort_id === c.id; }).length;
      return "<li><strong>" + esc(c.name) + "</strong> · студентов: " + n +
        ' <button type="button" class="gc-tag" data-cohort-del="' + esc(c.id) + '" data-name="' + esc(c.name) + '">удалить группу</button></li>';
    }).join("") : '<li class="gc-muted">Групп пока нет</li>';
  }

  function visibleRows() {
    var q = ($("[data-adm-filter]").value || "").trim().toLowerCase();
    var g = $("[data-adm-cohort]").value;
    return model.rows.filter(function (r) {
      if (q && r.username.indexOf(q) < 0 && String(r.email).toLowerCase().indexOf(q) < 0) return false;
      var mine = groupsOf(r.id);
      if (g === "-") return mine.length === 0;
      return !g || mine.indexOf(g) >= 0;
    });
  }

  function renderRows() {
    var rows = visibleRows();
    $("[data-adm-rows]").innerHTML = rows.map(function (r) {
      return "<tr>" +
        '<td data-label="Имя"><button type="button" class="gc-tag" data-detail="' + esc(r.id) + '">' + esc(r.username) + "</button></td>" +
        '<td data-label="Почта">' + esc(r.email) + "</td>" +
        '<td data-label="Роль">' + roleCell(r) + "</td>" +
        '<td data-label="Группы">' + groupCell(r) + "</td>" +
        '<td data-label="Освоено">' + r.g.mastered + " / " + r.g.total + "</td>" +
        '<td data-label="Балл">' + r.g.score + "</td>" +
        '<td data-label="Активность">' + when(r.updated_at) + "</td></tr>";
    }).join("") || '<tr><td colspan="7" class="gc-muted">Никого не нашлось</td></tr>';
  }

  function renderDetail(id) {
    var r = model.rows.filter(function (x) { return x.id === id; })[0];
    var box = $("[data-adm-detail]");
    if (!r) { box.hidden = true; return; }
    var list = Object.keys(r.g.grades).map(function (k) { return r.g.grades[k]; }).filter(function (g) { return g.status !== "none"; })
      .sort(function (a, b) { return b.score - a.score; });
    var labs = (r.data && r.data.labs) || [];
    box.hidden = false;
    box.innerHTML = '<p class="gc-label gc-muted">' + esc(r.username) + " — модули в работе и освоенные</p>" +
      (list.length ? '<div class="md-table-wrap"><table class="md-table"><thead><tr><th>Модуль</th><th>Статус</th><th>Квиз</th><th>Задачи</th><th>Лаб.</th><th>Балл</th></tr></thead><tbody>' +
        list.map(function (g) {
          return '<tr><td data-label="Модуль"><a href="' + base + "m/" + esc(g.id) + '.html">' + esc(model.titles[g.id] || g.id) + "</a></td>" +
            '<td data-label="Статус"><span class="gc-tag" data-state="' + window.UAVGrading.statusState(g) + '">' + (window.UAVGrading.statusLabel(g) || "—") + "</span></td>" +
            '<td data-label="Квиз">' + (g.hasQuiz ? (g.quizPct === null ? "—" : g.quizPct + " %") : "нет") + "</td>" +
            '<td data-label="Задачи">' + (g.tasksTotal ? g.tasksDone + " / " + g.tasksTotal : "нет") + "</td>" +
            '<td data-label="Лаб.">' + (g.labTotal ? g.labDone + " / " + g.labTotal : "нет") + "</td>" +
            '<td data-label="Балл">' + g.score + "</td></tr>";
        }).join("") + "</tbody></table></div>" : '<p class="gc-muted">Пока ничего не начато.</p>') +
      (labs.length ? '<p class="gc-label gc-muted">Результаты грейдеров</p><ul class="progress-labs">' + labs.map(function (l) {
        return "<li>" + esc(l.grader || "грейдер") + " · " + esc((Array.isArray(l.labs) ? l.labs : []).join(", ")) + " · " + esc(l.ts || "") + "</li>";
      }).join("") + "</ul>" : "");
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function download(rows, name) {
    var lines = rows.map(function (r) {
      return r.map(function (v) {
        v = String(v == null ? "" : v);
        if (/^[=+\-@\t\r]/.test(v)) v = "'" + v;      // no formulas when the CSV is opened in a spreadsheet
        return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
      }).join(",");
    });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv" }));
    a.download = name + "-" + new Date().toISOString().slice(0, 10) + ".csv";
    a.click();
  }

  // ASCII file names: browsers fall back to "download" for some non-ASCII names
  var TR = { "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
             "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
             "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "і": "i", "ї": "yi", "є": "ye", "ґ": "g" };
  function slug(s) {
    return String(s).toLowerCase().replace(/[^\u0000-\u007f]/g, function (c) { return TR[c] != null ? TR[c] : "-"; })
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
  }

  // exports what the table shows: the search and the group filter apply
  function csv() {
    var g = $("[data-adm-cohort]").value;
    var tag = g === "-" ? "-no-group" : g ? "-" + (slug(cohortName(g)) || "group") : "";
    download([["username", "email", "role", "groups", "mastered", "total", "score", "updated_at"]].concat(visibleRows().map(function (r) {
      return [r.username, r.email, r.role, groupsOf(r.id).map(cohortName).join("; "), r.g.mastered, r.g.total, r.g.score, r.updated_at || ""];
    })), "uav-students" + tag);
  }

  function renderAudit(items) {
    var names = {}; model.rows.forEach(function (r) { names[r.id] = r.username; });
    $("[data-adm-audit]").innerHTML = items.length ? items.map(function (a) {
      return "<li>" + when(a.at) + " · " + esc(names[a.actor] || (a.actor ? "?" : "система")) + ": " + esc(names[a.target] || "?") + " " +
        esc(ROLE[a.old_role] || "—") + " → " + esc(ROLE[a.new_role]) + "</li>";
    }).join("") : '<li class="gc-muted">Пусто</li>';
  }

  // ------------------------------------------------------------------ exams
  function loadExams() {
    var A = window.UAVAccount;
    return Promise.all([A.staffExams(), A.examResults()]).then(function (r) {
      model.exams = r[0]; model.examResults = r[1];
      $("[data-adm-exams]").innerHTML = r[0].length ? r[0].map(function (e) {
        var n = r[1].filter(function (x) { return x.exam_id === e.id; }).length;
        return "<li><strong>" + esc(e.title) + "</strong> · " + e.questions_per_attempt + " вопр., " + e.time_limit_min + " мин, порог " + e.pass_pct +
          " %, попыток " + e.attempts_allowed + " · попыток сдано: " + n + " " +
          '<button type="button" class="gc-tag" data-state="' + (e.published ? "ok" : "") + '" data-exam-pub="' + esc(e.id) + '" data-on="' + (e.published ? 0 : 1) + '">' +
          (e.published ? "опубликован — снять" : "черновик — опубликовать") + "</button>" +
          (n ? "" : ' <button type="button" class="gc-tag" data-exam-del="' + esc(e.id) + '">удалить</button>') + "</li>";
      }).join("") : '<li class="gc-muted">Экзаменов нет</li>';
      $("[data-adm-exam-results]").innerHTML = r[1].length ? r[1].map(function (x) {
        return '<tr><td data-label="Экзамен">' + esc(x.title || "—") + '</td><td data-label="Студент">' + esc(x.username) +
          '</td><td data-label="Результат">' + (x.submitted_at ? x.correct + " / " + x.total + " · " + x.score_pct + " %" : "не сдан") +
          '</td><td data-label="Сдан">' + (x.passed ? "да" : "нет") + '</td><td data-label="Когда">' + when(x.submitted_at || x.started_at) + "</td></tr>";
      }).join("") : '<tr><td colspan="5" class="gc-muted">Попыток пока нет</td></tr>';
    });
  }

  function examsCsv() {
    var rows = [["exam", "username", "email", "correct", "total", "score_pct", "passed", "submitted_at"]].concat((model.examResults || []).map(function (x) {
      return [x.title, x.username, x.email, x.correct, x.total, x.score_pct, x.passed, x.submitted_at || ""];
    }));
    download(rows, "uav-exam-results");
  }

  function load(note) {
    var A = window.UAVAccount;
    if (typeof note !== "string") note = "";
    if (!note) msg("Загружаю…");
    return Promise.all([A.listStudents(), A.audit(), A.listCohorts()]).then(function (res) {
      model.rows = res[0].map(function (r) { try { r.g = gradeStudent(r.data); } catch (e) { r.g = gradeStudent({}); } return r; });
      model.cohorts = res[2].cohorts; model.members = res[2].members;
      renderCohorts(); renderRows(); renderAudit(res[1]); if (note) msg(note, "ok"); else msg("");
    }).catch(function (e) { msg(A.humanError(e), "critical"); });
  }

  function start() {
    var A = window.UAVAccount;
    if (!A || !A.enabled) return;
    Promise.all([
      A.init(),
      fetch(base + "api/v1/grading.json").then(function (r) { return r.json(); }),
      fetch(base + "api/v1/curriculum.json").then(function (r) { return r.json(); })
    ]).then(function (res) {
      var s = res[0]; model.meta = res[1];
      res[2].groups.forEach(function (g) { g.modules.forEach(function (m) { model.titles[m.id] = m.title; }); });
      if (!s.isStaff) return;
      model.me = s;
      $('[data-adm="off"]').hidden = true; $('[data-adm="on"]').hidden = false;
      $("[data-adm-filter]").addEventListener("input", renderRows);
      $("[data-adm-cohort]").addEventListener("change", renderRows);
      function fail(err) { msg(A.humanError(err), "critical"); }
      $("[data-adm-cohort-form]").addEventListener("submit", function (e) {
        e.preventDefault();
        var inp = $("[data-adm-cohort-name]");
        A.createCohort(inp.value).then(function () { inp.value = ""; return load("Группа создана."); }).catch(fail);
      });
      $("[data-adm-cohorts]").addEventListener("click", function (e) {
        var d = e.target.closest("[data-cohort-del]"); if (!d) return;
        if (!window.confirm("Удалить группу «" + d.getAttribute("data-name") + "»? Студенты и их оценки останутся.")) return;
        A.deleteCohort(d.getAttribute("data-cohort-del")).then(function () { return load("Группа удалена."); }).catch(fail);
      });
      $("[data-adm-reload]").addEventListener("click", load);
      $("[data-adm-csv]").addEventListener("click", csv);
      $("[data-adm-exam-csv]").addEventListener("click", examsCsv);
      $("[data-adm-exam-file]").addEventListener("change", function (e) {
        var f = e.target.files[0]; if (!f) return;
        f.text().then(function (t) {
          var bank = JSON.parse(t);
          if (!bank.title) bank.title = f.name.replace(/\.json$/i, "");
          return A.createExam(bank);
        }).then(function () { msg("Экзамен загружен черновиком — проверь и опубликуй.", "ok"); return loadExams(); })
          .catch(function (err) { msg(err instanceof SyntaxError ? "Это не JSON." : A.humanError(err), "critical"); })
          .then(function () { e.target.value = ""; });
      });
      $("[data-adm-exams]").addEventListener("click", function (e) {
        var p = e.target.closest("[data-exam-pub]"), d = e.target.closest("[data-exam-del]");
        if (p) A.setExamPublished(p.getAttribute("data-exam-pub"), p.getAttribute("data-on") === "1").then(loadExams).catch(function (err) { msg(A.humanError(err), "critical"); });
        if (d) A.deleteExam(d.getAttribute("data-exam-del")).then(loadExams).catch(function (err) { msg(A.humanError(err), "critical"); });
      });
      $("[data-adm-rows]").addEventListener("click", function (e) {
        var b = e.target.closest("[data-detail]"); if (b) renderDetail(b.getAttribute("data-detail"));
        var u = e.target.closest("[data-unjoin]");
        if (u) A.removeFromCohort(u.getAttribute("data-unjoin"), u.getAttribute("data-user")).then(function () { return load("Убран из группы."); }).catch(fail);
      });
      $("[data-adm-rows]").addEventListener("change", function (e) {
        var j = e.target.closest("[data-join-of]");
        if (j) {
          if (!j.value) return;
          j.disabled = true;
          A.addToCohort(j.value, j.getAttribute("data-join-of")).then(function () { return load("Добавлен в группу."); })
            .catch(function (err) { var t = A.humanError(err); return load().then(function () { msg(t, "critical"); }); });
          return;
        }
        var sel = e.target.closest("[data-role-of]"); if (!sel) return;
        sel.disabled = true;
        A.setRole(sel.getAttribute("data-role-of"), sel.value).then(function () { return load("Роль изменена."); })
          .catch(function (err) { var t = A.humanError(err); return load().then(function () { msg(t, "critical"); }); });
      });
      return Promise.all([load(), loadExams()]);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
