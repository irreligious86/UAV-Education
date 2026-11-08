/*
 * Grading model. Pure functions over ProgressStore data + api/v1/grading.json.
 * Used by app.js (badges, bars) and pages/progress.html (full table).
 * A future server computes the same from the same inputs — keep this free of DOM.
 *
 * Module score (0..100):
 *   quiz part  = 40 * (best quiz % / 100)         — 0 when no quiz exists for the module
 *   lab part   = 60 * (checked criteria / total)  — 0..60; modules without lab: quiz counts 100%
 *   with numeric tasks (meta.tasks > 0): quiz 30 + tasks 30 * (solved / total) + lab 40
 *   bonus      = module checklist is informational, not graded
 *
 * Module status:
 *   "passed"   quiz >= pass (80) AND all lab criteria checked AND all numeric tasks solved (or self-marked)
 *   "active"   anything started (any quiz attempt, any check)
 *   "none"     untouched
 *   A manual "done" mark counts as passed but is flagged selfMarked=true; it is shown
 *   differently (ОТМЕЧЕН) so honest students see the difference from earned ОСВОЕН.
 *
 * Group score = mean of module scores over published modules; group passed = all passed.
 * Capstone: passed when all criteria checked or marked done.
 */
(function () {
  "use strict";

  var QUIZ_WEIGHT = 40, LAB_WEIGHT = 60, PASS = 80;

  function moduleGrade(meta, state) {
    // meta: {id, quiz: bool, lab: int(criteria count)}  state: {quiz: {correct,total}|null, checks: Set, done: Set}
    var hasQuiz = !!meta.quiz, labN = meta.lab || 0, taskN = meta.tasks || 0;
    var quizPct = state.quiz && state.quiz.total ? Math.round(100 * state.quiz.correct / state.quiz.total) : null;
    var labDone = 0;
    for (var i = 0; i < labN; i++) if (state.checks.has(meta.id + ":lab:" + i)) labDone++;
    var tasksDone = 0;
    if (taskN && state.tasks) tasksDone = Math.min(taskN, Object.keys(state.tasks).filter(function (k) { return state.tasks[k]; }).length);

    // weights of the parts that exist, renormalised to 100
    var parts = [];
    if (hasQuiz) parts.push([taskN ? 30 : QUIZ_WEIGHT, (quizPct || 0) / 100]);
    if (taskN) parts.push([30, tasksDone / taskN]);
    if (labN) parts.push([taskN ? 40 : LAB_WEIGHT, labDone / labN]);
    var wsum = 0, acc = 0;
    parts.forEach(function (p) { wsum += p[0]; acc += p[0] * p[1]; });
    var score = wsum ? Math.round(100 * acc / wsum) : 0;

    var quizOk = !hasQuiz || (quizPct !== null && quizPct >= PASS);
    var labOk = !labN || labDone === labN;
    var tasksOk = !taskN || tasksDone === taskN;
    var earned = (hasQuiz || labN || taskN) && quizOk && labOk && tasksOk;
    var selfMarked = state.done.has(meta.id) && !earned;
    var started = (quizPct !== null) || labDone > 0 || tasksDone > 0 || state.done.has(meta.id);

    return {
      id: meta.id, score: score, quizPct: quizPct, labDone: labDone, labTotal: labN, hasQuiz: hasQuiz,
      tasksDone: tasksDone, tasksTotal: taskN,
      status: (earned || selfMarked) ? "passed" : started ? "active" : "none",
      earned: !!earned, selfMarked: selfMarked
    };
  }

  function groupGrade(ids, grades) {
    var list = ids.map(function (id) { return grades[id]; }).filter(Boolean);
    if (!list.length) return { score: 0, passed: 0, total: 0, allPassed: false };
    var sum = 0, passed = 0;
    list.forEach(function (g) { sum += g.score; if (g.status === "passed") passed++; });
    return { score: Math.round(sum / list.length), passed: passed, total: list.length, allPassed: passed === list.length };
  }

  function capstoneGrade(cap, state) {
    var n = cap.criteria || 0, done = 0;
    for (var i = 0; i < n; i++) if (state.checks.has(cap.id + ":cap:" + i)) done++;
    var passed = (n && done === n) || state.done.has(cap.id);
    return { id: cap.id, done: done, total: n, passed: passed, selfMarked: state.done.has(cap.id) && !(n && done === n) };
  }

  function statusLabel(g) {
    if (g.status === "passed") return g.selfMarked ? "ОТМЕЧЕН" : "ОСВОЕН";
    if (g.status === "active") return "В РАБОТЕ";
    return "";
  }

  function statusState(g) {
    if (g.status === "passed") return g.selfMarked ? "info" : "ok";
    if (g.status === "active") return "caution";
    return "";
  }

  // Load everything once: grading meta + store snapshot -> {meta, grades, caps, state}
  function load(base) {
    var store = window.UAVProgress;
    return Promise.all([
      fetch(base + "api/v1/grading.json").then(function (r) { return r.json(); }),
      store.getDone(), store.getChecks(""), store.getAllQuiz ? store.getAllQuiz() : Promise.resolve({}),
      store.getAllTasks ? store.getAllTasks() : Promise.resolve({})
    ]).then(function (res) {
      var meta = res[0], done = res[1], checks = res[2], quiz = res[3], tasks = res[4] || {};
      var state = { done: done, checks: checks, quiz: quiz, tasks: tasks };
      var grades = {};
      meta.modules.forEach(function (m) {
        grades[m.id] = moduleGrade(m, { quiz: quiz[m.id] || null, checks: checks, done: done, tasks: tasks[m.id] || {} });
      });
      var caps = {};
      meta.capstones.forEach(function (c) { caps[c.id] = capstoneGrade(c, state); });
      return { meta: meta, grades: grades, caps: caps, state: state };
    });
  }

  window.UAVGrading = { moduleGrade: moduleGrade, groupGrade: groupGrade, capstoneGrade: capstoneGrade,
                        statusLabel: statusLabel, statusState: statusState, load: load, PASS: PASS };
})();
