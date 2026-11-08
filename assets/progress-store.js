/*
 * Progress storage behind a small async interface.
 *
 * Today: LocalProgressStore keeps completed module ids in this browser (localStorage).
 * Later: an ApiProgressStore with the same methods will talk to our own server
 * (e.g. GET/PUT /api/v1/progress). Pages only use window.UAVProgress, so swapping the
 * implementation is a one-line change at the bottom of this file.
 *
 * Interface (all methods return Promises):
 *   getDone()                -> Promise<Set<string>>   ids of completed modules
 *   setDone(id, isDone)      -> Promise<void>
 *   getChecks(prefix)        -> Promise<Set<string>>   checked checklist items
 *   setCheck(id, isChecked)  -> Promise<void>
 *   getQuiz(moduleId)        -> Promise<{correct,total,ts}|null>  best quiz result
 *   setQuiz(moduleId, res)   -> Promise<void>                       keeps the best of old/new
 *   getAllQuiz()             -> Promise<{moduleId: result}>
 *   getTasks(moduleId)       -> Promise<{taskId: true}>              solved numeric tasks
 *   setTask(moduleId, taskId, solved) -> Promise<void>
 *   getAllTasks()            -> Promise<{moduleId: {taskId: true}}>
 *   addLabResult(summary)    -> Promise<boolean>  imported grader result (uav-lab-result/1 summary);
 *                                                  ticks summary.marks, false if already imported
 *   getLabResults()          -> Promise<Array>    imported grader results, newest first
 *   reset()                  -> Promise<void>                       wipe everything (student asked)
 */
(function () {
  "use strict";

  var KEY = "uav-student:progress:v1";

  function LocalProgressStore() {}

  LocalProgressStore.prototype._read = function () {
    try {
      var raw = window.localStorage.getItem(KEY);
      var data = raw ? JSON.parse(raw) : {};
      return { done: data.done || [], checks: data.checks || [], quiz: data.quiz || {}, tasks: data.tasks || {},
               labs: data.labs || [] };
    } catch (e) {
      return { done: [], checks: [], quiz: {}, tasks: {}, labs: [] };
    }
  };

  LocalProgressStore.prototype._write = function (data) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(data));
    } catch (e) {
      /* private mode or storage disabled: progress simply isn't remembered */
    }
  };

  LocalProgressStore.prototype.getDone = function () {
    return Promise.resolve(new Set(this._read().done));
  };

  LocalProgressStore.prototype.setDone = function (id, isDone) {
    var data = this._read();
    var set = new Set(data.done);
    if (isDone) set.add(id); else set.delete(id);
    data.done = Array.from(set);
    this._write(data);
    return Promise.resolve();
  };

  LocalProgressStore.prototype.getChecks = function (prefix) {
    var all = this._read().checks;
    return Promise.resolve(new Set(all.filter(function (c) { return c.indexOf(prefix) === 0; })));
  };

  LocalProgressStore.prototype.setCheck = function (id, isChecked) {
    var data = this._read();
    var set = new Set(data.checks);
    if (isChecked) set.add(id); else set.delete(id);
    data.checks = Array.from(set);
    this._write(data);
    return Promise.resolve();
  };

  LocalProgressStore.prototype.getQuiz = function (moduleId) {
    return Promise.resolve(this._read().quiz[moduleId] || null);
  };

  LocalProgressStore.prototype.setQuiz = function (moduleId, result) {
    var data = this._read();
    var old = data.quiz[moduleId];
    var better = !old || (result.correct / result.total) >= (old.correct / old.total);
    if (better) data.quiz[moduleId] = result;
    data.quiz[moduleId].attempts = (old && old.attempts ? old.attempts : 0) + 1;
    data.quiz[moduleId].last = result.ts;
    this._write(data);
    return Promise.resolve();
  };

  LocalProgressStore.prototype.getAllQuiz = function () {
    return Promise.resolve(this._read().quiz);
  };

  LocalProgressStore.prototype.getTasks = function (moduleId) {
    return Promise.resolve(this._read().tasks[moduleId] || {});
  };

  LocalProgressStore.prototype.setTask = function (moduleId, taskId, solved) {
    var data = this._read();
    var m = data.tasks[moduleId] || {};
    if (solved) m[taskId] = true; else delete m[taskId];
    data.tasks[moduleId] = m;
    this._write(data);
    return Promise.resolve();
  };

  LocalProgressStore.prototype.getAllTasks = function () {
    return Promise.resolve(this._read().tasks);
  };

  LocalProgressStore.prototype.addLabResult = function (r) {
    var data = this._read();
    var key = r.grader + "|" + r.labs.join(",") + "|" + r.sha256;
    if (data.labs.some(function (x) { return x.key === key; })) return Promise.resolve(false);
    data.labs.unshift(Object.assign({ key: key }, r));
    var set = new Set(data.checks);
    r.marks.forEach(function (m) { set.add(m); });
    data.checks = Array.from(set);
    this._write(data);
    return Promise.resolve(true);
  };

  LocalProgressStore.prototype.getLabResults = function () {
    return Promise.resolve(this._read().labs);
  };

  LocalProgressStore.prototype.reset = function () {
    try { window.localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
    return Promise.resolve();
  };

  window.UAVProgress = new LocalProgressStore();
})();
