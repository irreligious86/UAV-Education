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
 */
(function () {
  "use strict";

  var KEY = "uav-student:progress:v1";

  function LocalProgressStore() {}

  LocalProgressStore.prototype._read = function () {
    try {
      var raw = window.localStorage.getItem(KEY);
      var data = raw ? JSON.parse(raw) : {};
      return { done: data.done || [], checks: data.checks || [] };
    } catch (e) {
      return { done: [], checks: [] };
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

  window.UAVProgress = new LocalProgressStore();
})();
