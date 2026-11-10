/*
 * pages/exam.html: exams graded by the database (docs/MULTIUSER-PLAN.md §11).
 * The page never sees correct answers before submitting; it only shows what exam_start() returns,
 * keeps the student's picks in localStorage (resume after a reload) and submits them.
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";

  var DRAFT = "uav-student:exam-draft:";
  var A, timer = null, current = null;

  function $(s) { return document.querySelector(s); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function msg(t, st) { var el = $("[data-acc-msg]"); el.textContent = t || ""; el.setAttribute("data-state", st || ""); }
  function show(name) { document.querySelectorAll("[data-ex]").forEach(function (el) { el.hidden = el.getAttribute("data-ex") !== name; }); }
  function readDraft(id) { try { return JSON.parse(localStorage.getItem(DRAFT + id) || "{}"); } catch (e) { return {}; } }
  function writeDraft(id, d) { try { localStorage.setItem(DRAFT + id, JSON.stringify(d)); } catch (e) { /* ignore */ } }
  function dropDraft(id) { try { localStorage.removeItem(DRAFT + id); } catch (e) { /* ignore */ } }
  function when(ts) { return ts ? new Date(ts).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" }) : ""; }

  function stateOf(e) {
    var now = Date.now();
    var used = e.attempts.length;
    var running = e.attempts.filter(function (a) { return !a.submitted_at && new Date(a.deadline).getTime() > now; })[0];
    var best = e.attempts.reduce(function (b, a) { return a.score_pct != null && (b == null || a.score_pct > b) ? a.score_pct : b; }, null);
    var closed = (e.opens_at && now < new Date(e.opens_at).getTime()) || (e.closes_at && now > new Date(e.closes_at).getTime());
    return { used: used, running: running, best: best, closed: closed, left: e.attempts_allowed - used,
             passed: e.attempts.some(function (a) { return a.passed; }) };
  }

  function renderList(exams) {
    show("list");
    var box = $("[data-ex-list]");
    if (!exams.length) { box.innerHTML = T('<p class="gc-muted">Опубликованных экзаменов пока нет.</p>'); return; }
    box.innerHTML = exams.map(function (e) {
      var s = stateOf(e);
      var can = !s.closed && (s.running || s.left > 0);
      var status = s.passed ? T('<span class="gc-tag" data-state="ok">сдан') + (s.best != null ? " · " + s.best + " %" : "") + "</span>"
        : s.best != null ? T('<span class="gc-tag" data-state="caution">лучший результат ') + s.best + " %</span>" : "";
      return '<div class="gc-panel exam-card"><p class="progress-headline">' + esc(e.title) + " " + status + "</p>" +
        '<p class="gc-muted">' + e.questions_per_attempt + T(" вопросов · ") + e.time_limit_min + T(" мин · порог ") + e.pass_pct +
        T(" % · попытки: ") + s.used + T(" из ") + e.attempts_allowed + (e.closes_at ? T(" · до ") + when(e.closes_at) : "") + "</p>" +
        (can ? '<gc-button data-start="' + esc(e.id) + '">' + (s.running ? T("Продолжить") : T("Начать")) + "</gc-button>"
             : '<p class="gc-muted">' + (s.closed ? T("Сейчас закрыт.") : T("Попытки закончились.")) + "</p>") + "</div>";
    }).join("");
  }

  function renderExam(r) {
    current = r;
    show("run");
    $("[data-ex-title]").textContent = r.title;
    var draft = readDraft(r.attempt);
    $("[data-ex-questions]").innerHTML = r.questions.map(function (q, i) {
      return '<fieldset class="exam-q"><legend>' + (i + 1) + ". " + esc(q.q) + "</legend>" +
        q.options.map(function (o, k) {
          return '<label class="exam-opt"><input type="radio" name="q' + q.id + '" value="' + k + '"' + (draft[q.id] === k ? " checked" : "") +
            ' data-q="' + q.id + '"> ' + esc(o) + "</label>";
        }).join("") + "</fieldset>";
    }).join("");
    tick();
    clearInterval(timer); timer = setInterval(tick, 1000);
  }

  function tick() {
    if (!current) return;
    var left = Math.floor((new Date(current.deadline).getTime() - Date.now()) / 1000);
    var el = $("[data-ex-timer]");
    if (left <= 0) { el.textContent = T("время вышло"); clearInterval(timer); submit(true); return; }
    el.textContent = Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
    el.setAttribute("data-state", left < 60 ? "critical" : left < 300 ? "caution" : "info");
  }

  function picks() {
    var a = {};
    document.querySelectorAll("[data-ex-questions] input:checked").forEach(function (i) { a[i.getAttribute("data-q")] = +i.value; });
    return a;
  }

  var sending = false;
  function submit(auto) {
    if (!current || sending) return;
    var a = picks();
    var missing = current.questions.length - Object.keys(a).length;
    if (!auto && missing > 0 && !confirm(T("Без ответа: ") + missing + T(". Сдать всё равно?"))) return;
    sending = true; clearInterval(timer);
    A.submitExam(current.attempt, a).then(function (res) {
      dropDraft(current.attempt);
      renderResult(res);
    }).catch(function (e) { msg(A.humanError(e), "critical"); }).then(function () { sending = false; });
  }

  function renderResult(res) {
    show("result");
    var q = {}; current.questions.forEach(function (x) { q[x.id] = x; });
    $("[data-ex-score]").innerHTML = '<span class="gc-tag" data-state="' + (res.passed ? "ok" : "critical") + '">' +
      (res.passed ? T("Сдан") : T("Не сдан")) + "</span> " + res.correct + T(" из ") + res.total + " · " + res.score_pct + " %";
    $("[data-ex-review]").innerHTML = res.review ? res.review.map(function (r) {
      var x = q[r.id] || { q: "?", options: [] };
      var ok = r.your === r.answer;
      return '<li><strong>' + esc(x.q) + "</strong><br>" + (ok ? "✓ " : "✗ ") + T("твой ответ: ") + esc(r.your == null ? "—" : x.options[r.your]) +
        (ok ? "" : T(" · верно: ") + esc(x.options[r.answer])) + (r.explain ? '<br><span class="gc-muted">' + esc(r.explain) + "</span>" : "") + "</li>";
    }).join("") : T('<li class="gc-muted">Разбор ответов скрыт: он появится после последней попытки или когда экзамен закроется (если преподаватель его включил).</li>');
    current = null;
  }

  function load() { msg(""); return A.listExams().then(renderList).catch(function (e) { msg(A.humanError(e), "critical"); }); }

  function start() {
    A = window.UAVAccount;
    if (!A || !A.enabled) return show("off");
    A.init().then(function (s) {
      if (!s.user) return show("guest");
      $("[data-ex-list]").addEventListener("click", function (e) {
        var b = e.target.closest("[data-start]"); if (!b) return;
        A.startExam(b.getAttribute("data-start")).then(renderExam).catch(function (err) { msg(A.humanError(err), "critical"); });
      });
      $("[data-ex-questions]").addEventListener("change", function (e) {
        var i = e.target.closest("input[data-q]"); if (!i || !current) return;
        var d = readDraft(current.attempt); d[i.getAttribute("data-q")] = +i.value; writeDraft(current.attempt, d);
      });
      $("[data-ex-submit]").addEventListener("click", function () { submit(false); });
      $("[data-ex-back]").addEventListener("click", load);
      return load();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
