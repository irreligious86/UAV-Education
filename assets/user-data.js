/*
 * Personal study data: notes, bookmarks, settings, reading history (docs/MULTIUSER-PLAN.md, section 14).
 * Offline-first: everything lives in this browser (localStorage) for guests and signed-in users alike.
 * With accounts on and a user signed in, rows are merged with the server after login (and when the tab comes back
 * into focus), and every local change is pushed (debounced). Server tables: user_notes, user_bookmarks,
 * user_settings, user_history (supabase/migrations/0007_notes_bookmarks_feedback_settings.sql).
 * Nothing here is a security boundary.
 *
 * Local shapes:
 *   uav-student:notes:v1      {"<module>#<anchor>": {m, a, label, title, body, at, dirty, srv, del, err}}
 *   uav-student:bookmarks:v1  {"<module>#<anchor>": {m, a, label, title, at, dirty, srv, del, err}}
 *     at = local edit time (ms), srv = server updated_at of the version this browser last saw, dirty = not on the
 *     server yet, del = deleted here, the server row still to delete, err = why the server refused this row.
 *     anchor "" = the whole lesson.
 *   uav-student:settings, uav-student:ready-only   (assets/account-page.js, assets/app.js)
 *   uav-student:settings-owner  user id whose settings these are ('' or absent = a guest's)
 *   uav-student:history:v1    (assets/history.js)
 *   uav-student:userdata-sync {settings: {dirty, srv, at}, history: {dirty}}
 *
 * Notes are never lost (resolve(), unit-tested in tests/js/userdata.test.js). The server's updated_at is the row
 * version; it is compared only with the version this browser last saw, never with the browser's clock.
 *   - at login / focus (mergeRows): a clean local row takes the server version; a dirty one over an unchanged server
 *     row is pushed; when both changed, resolve() decides;
 *   - on every push: save_note() writes only over the version this browser saw, otherwise it returns the stored
 *     version and resolve() decides — so two signed-in devices never overwrite each other blindly;
 *   - resolve(): equal texts -> nothing to do; otherwise one note with both texts (server first, then this device's
 *     under a marker line); if that would exceed 8000 characters the server note stays as it is and this device's
 *     text becomes a separate note "<anchor>-copy-N" next to it. Bookmarks have no text: a set, last write wins.
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";

  var NOTES = "uav-student:notes:v1", MARKS = "uav-student:bookmarks:v1", META = "uav-student:userdata-sync";
  var SETTINGS = "uav-student:settings", READY = "uav-student:ready-only", HISTORY = "uav-student:history:v1";
  var SETTINGS_OWNER = "uav-student:settings-owner";
  var NOTE_MAX = 8000, NOTE_ROWS = 2000, MARK_ROWS = 1000, LABEL_MAX = 160, HISTORY_MAX = 30;
  var MODULE_RE = /^[a-z0-9-]{1,64}$/, ANCHOR_RE = /^[A-Za-z0-9_-]{0,80}$/;   // the server's checks (0007)

  // ------------------------------------------------------------------ pure merge (no DOM, no storage)
  function key(m, a) { return m + "#" + (a || ""); }
  function isRow(r) { return !!r && typeof r === "object" && !Array.isArray(r); }

  // a free anchor for a copy of a note: "<anchor>-copy-N" ("copy-N" for the whole lesson), within the anchor pattern
  function copyAnchor(a, taken) {
    var stem = (a ? a.slice(0, 64) + "-" : "") + "copy-";
    for (var n = 1; ; n++) if (!taken(stem + n)) return stem + n;
  }

  // L: the local dirty row, S: the server row {module_id, anchor, label, body, updated_at}; taken(anchor) -> bool.
  // Returns rows to store by key and the keys to push.
  function resolve(L, S, opts, taken) {
    opts = opts || {};
    var k = key(L.m, L.a), rows = {}, push = [];
    var server = { m: L.m, a: L.a, label: S.label || "", title: L.title || "", body: S.body, at: Date.parse(S.updated_at) || 0,
                   dirty: false, srv: S.updated_at, del: false };
    if (S.body === L.body) { rows[k] = server; return { rows: rows, push: push }; }
    var sep = "\n\n" + (opts.marker ? opts.marker(new Date(L.at || Date.now())) : "--- this device ---") + "\n";
    var both = S.body + sep + L.body;
    if (both.length <= (opts.max || NOTE_MAX)) {
      rows[k] = Object.assign({}, server, { body: both, dirty: true, at: Math.max(L.at || 0, server.at) });
      push.push(k);
      return { rows: rows, push: push };
    }
    // too long for one note: the server note stays untouched, this device's text becomes its own note
    rows[k] = server;
    var ca = copyAnchor(L.a, function (a) { return taken(a) || rows[key(L.m, a)]; });
    var label = ((L.label || S.label || "") + " " + (opts.copyLabel || "(copy)")).trim().slice(0, LABEL_MAX);
    rows[key(L.m, ca)] = { m: L.m, a: ca, label: label, title: L.title || "", body: L.body, at: L.at || Date.now(), dirty: true, srv: null, del: false };
    push.push(key(L.m, ca));
    return { rows: rows, push: push };
  }

  // local: {key: row}; server: [{module_id, anchor, label, body?, updated_at}]
  function mergeRows(local, server, opts) {
    local = isRow(local) ? local : {};
    var out = {}, push = [], del = [];
    var srv = {};
    (server || []).forEach(function (s) { srv[key(s.module_id, s.anchor)] = s; });
    var keys = Object.keys(local).concat(Object.keys(srv)).filter(function (k, i, all) { return all.indexOf(k) === i; });
    var taken = function (m) { return function (a) { var k = key(m, a); return !!(local[k] || srv[k] || out[k]); }; };
    keys.forEach(function (k) {
      var L = isRow(local[k]) ? local[k] : null, S = srv[k];
      if (out[k]) return;                                    // a copy created earlier in this loop
      var fromS = S && { m: S.module_id, a: S.anchor || "", label: S.label || "", title: L && L.title || "", at: Date.parse(S.updated_at) || 0,
                         dirty: false, srv: S.updated_at, del: false };
      if (S && "body" in S) fromS.body = S.body;
      if (!L) { out[k] = fromS; return; }
      if (!S) {
        if (L.del) return;                                   // deleted here and gone there
        if (!L.dirty && L.srv) return;                       // deleted on another device
        out[k] = Object.assign({}, L, { dirty: true }); push.push(k); return;
      }
      if (!L.dirty) { out[k] = fromS; return; }
      if (L.srv && L.srv === S.updated_at) {                 // server unchanged since we last saw it: ours goes up
        out[k] = L; (L.del ? del : push).push(k); return;
      }
      // both sides changed
      if (L.del) { out[k] = fromS; return; }                 // edited elsewhere after our delete: keep their text
      if (!("body" in S)) { out[k] = Object.assign(fromS, { title: L.title || "" }); return; }   // bookmark: a set
      var r = resolve(L, S, opts, taken(L.m));
      Object.assign(out, r.rows); push = push.concat(r.push);
    });
    return { rows: out, push: push, del: del };
  }

  // history: newest "at" wins per lesson, at most HISTORY_MAX, newest first
  function mergeHistory(a, b) {
    var by = {};
    [].concat((a && a.items) || [], (b && b.items) || []).forEach(function (it) {
      if (!it || typeof it.id !== "string" || typeof it.at !== "number") return;
      if (!by[it.id] || by[it.id].at < it.at) by[it.id] = it;
    });
    var items = Object.keys(by).map(function (k) { return by[k]; }).sort(function (x, y) { return y.at - x.at; }).slice(0, HISTORY_MAX);
    return { items: items, last: items.length ? items[0].id : undefined };
  }

  // settings as the server stores them: known keys only, right types
  function cleanSettings(s) {
    var o = {};
    s = isRow(s) ? s : {};
    ["readyOnly", "resumeOnOpen", "notesPanel"].forEach(function (k) { if (typeof s[k] === "boolean") o[k] = s[k]; });
    if (typeof s.firmwarePath === "string" && /^[a-z0-9-]{0,64}$/.test(s.firmwarePath)) o.firmwarePath = s.firmwarePath;
    return o;
  }

  // a row the server would refuse by shape: stays local, with the reason
  function invalid(r, withBody) {
    if (!MODULE_RE.test(r.m || "") || !ANCHOR_RE.test(r.a || "")) return "bad module or anchor";
    if (withBody && !r.del && !(typeof r.body === "string" && r.body.length >= 1 && r.body.length <= NOTE_MAX)) return "bad note text";
    return "";
  }

  var pure = { mergeRows: mergeRows, mergeHistory: mergeHistory, cleanSettings: cleanSettings, resolve: resolve, key: key, invalid: invalid };
  if (typeof module !== "undefined" && module.exports) module.exports = pure;
  if (typeof document === "undefined") return;

  // ------------------------------------------------------------------ storage
  function get(k, dflt) { try { var v = JSON.parse(localStorage.getItem(k) || "null"); return v == null ? dflt : v; } catch (e) { return dflt; } }
  function put(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function emit(what) { try { document.dispatchEvent(new CustomEvent("uav-userdata", { detail: { what: what } })); } catch (e) { /* old browser */ } }

  function rowsStore(name, max, hasBody) {
    function all() {
      var v = get(name, {}), out = {};
      if (!isRow(v)) return out;
      Object.keys(v).forEach(function (k) { if (isRow(v[k])) out[k] = v[k]; });   // corrupted storage: drop junk rows
      return out;
    }
    function live() { var a = all(); return Object.keys(a).map(function (k) { return a[k]; }).filter(function (r) { return !r.del; }); }
    function save(a, why) { var ok = put(name, a); emit(why || name); schedule(); return ok; }
    return {
      all: all,
      list: function () { return live().sort(function (x, y) { return (y.at || 0) - (x.at || 0); }); },
      get: function (m, a) { var r = all()[key(m, a)]; return r && !r.del ? r : null; },
      // returns false when the browser refused (storage off / full) or the row cap is reached
      set: function (m, a, fields) {
        var s = all(), k = key(m, a), old = s[k];
        if ((!old || old.del) && live().length >= max) return false;
        var row = Object.assign({}, old || { m: m, a: a || "", srv: null }, fields, { at: Date.now(), dirty: true, del: false });
        delete row.err;
        row.label = String(row.label || "").slice(0, LABEL_MAX);
        if (hasBody) row.body = String(row.body || "").slice(0, NOTE_MAX);
        s[k] = row;
        return save(s);
      },
      remove: function (m, a) {
        var s = all(), k = key(m, a), old = s[k];
        if (!old) return true;
        if (old.srv) s[k] = Object.assign({}, old, { del: true, dirty: true, at: Date.now() }); else delete s[k];
        return save(s);
      },
      replace: function (rows) { put(name, rows); emit(name); }
    };
  }

  var notes = rowsStore(NOTES, NOTE_ROWS, true);
  var marks = rowsStore(MARKS, MARK_ROWS, false);

  function meta() { var m = get(META, {}); return isRow(m) ? m : {}; }
  function setMeta(part, v) { var m = meta(); m[part] = Object.assign({}, m[part] || {}, v); put(META, m); }

  function readSettings() {
    var s = cleanSettings(get(SETTINGS, {}));
    try { var r = localStorage.getItem(READY); if (r != null) s.readyOnly = r === "1"; } catch (e) { /* storage off */ }
    return s;
  }
  function applySettings(s) {
    var cur = get(SETTINGS, {});
    if (!isRow(cur)) cur = {};
    ["resumeOnOpen", "notesPanel", "firmwarePath"].forEach(function (k) { if (k in s) cur[k] = s[k]; else delete cur[k]; });
    put(SETTINGS, cur);
    var ready = !!s.readyOnly;
    try { localStorage.setItem(READY, ready ? "1" : "0"); } catch (e) { /* storage off */ }
    document.body.classList.toggle("ready-only", ready);
    document.querySelectorAll("[data-ready-only]").forEach(function (b) { b.checked = ready; });
    document.querySelectorAll("[data-setting]").forEach(function (el) {
      var k = el.getAttribute("data-setting");
      if (el.type === "checkbox") el.checked = !!s[k]; else el.value = s[k] != null ? s[k] : "";
    });
    emit("settings");
  }

  // ------------------------------------------------------------------ sync
  function A() { return window.UAVAccount; }
  function me() { var a = A(), s = a && a.enabled && a.state ? a.state() : null; return s && s.user ? s.user.id : null; }
  function signedIn() { return !!me(); }
  var timer = null, histTimer = null, syncing = null, lastError = "", lastPull = 0;

  function schedule() {
    if (!signedIn()) return;
    clearTimeout(timer);
    timer = setTimeout(function () { pushAll(); }, 1500);
  }
  function marker(d) { return T("— копия с этого устройства, {d} —", { d: d.toLocaleString() }); }
  var OPTS = { marker: marker, max: NOTE_MAX, copyLabel: T("(копия с другого устройства)") };

  // one failed row never blocks the others: each row is its own request; the first error is reported
  function pushRows(table, store, withBody) {
    var a = A(), s = store.all(), errors = [];
    var jobs = Object.keys(s).filter(function (k) { return s[k].dirty; }).map(function (k) {
      var r = s[k], why = invalid(r, withBody);
      var mark = function (fields) {                         // apply to the current row if it was not edited meanwhile
        var cur = store.all();
        if (cur[k] && cur[k].at === r.at) { cur[k] = Object.assign({}, cur[k], fields); store.replace(cur); }
      };
      var fail = function (e) { var msg = a.humanError(e); errors.push(msg); mark({ err: msg }); };
      if (why) { fail(new Error(why)); return null; }
      if (r.del) {
        return a.deleteRow(table, r.m, r.a, withBody ? r.srv : null).then(function () {
          var cur = store.all();
          if (cur[k] && cur[k].del && cur[k].at === r.at) { delete cur[k]; store.replace(cur); }
        }, fail);
      }
      if (!withBody) {
        return a.upsertRows(table, [{ module_id: r.m, anchor: r.a, label: r.label || "" }]).then(function (back) {
          var b = (back || [])[0];
          mark({ srv: b ? b.updated_at : r.srv, dirty: false, err: undefined });
        }, fail);
      }
      return a.saveNote(r.m, r.a, r.label || "", r.body, r.srv || null).then(function (res) {
        if (!res.conflict) { mark({ srv: res.updated_at, dirty: false, err: undefined }); return; }
        // someone else saved this note since this browser last saw it: merge, never overwrite
        var cur = store.all();
        if (!cur[k] || cur[k].at !== r.at) return;           // edited again meanwhile: the next push retries
        var out = resolve(cur[k], { module_id: r.m, anchor: r.a, label: res.label, body: res.body, updated_at: res.updated_at }, OPTS,
                          function (an) { return !!cur[key(r.m, an)]; });
        Object.assign(cur, out.rows); store.replace(cur);
        if (out.push.length) schedule();
      }, fail);
    }).filter(Boolean);
    return Promise.all(jobs).then(function () { if (errors.length) throw new Error(errors[0]); });
  }

  function pushSettings() {
    var m = meta().settings || {};
    if (!m.dirty) return Promise.resolve();
    var at = m.at;
    return A().putDoc("user_settings", readSettings()).then(function (row) {
      setMeta("settings", { srv: row && row.updated_at, dirty: (meta().settings || {}).at !== at });
      put(SETTINGS_OWNER, me());
    });
  }
  function pushHistory() {
    if (!(meta().history || {}).dirty) return Promise.resolve();
    var h = get(HISTORY, { items: [] });
    return A().putDoc("user_history", mergeHistory(h, {}).items).then(function () { setMeta("history", { dirty: false }); });
  }

  function pushAll() {
    if (!signedIn()) return Promise.resolve(false);
    var parts = [pushRows("user_notes", notes, true), pushRows("user_bookmarks", marks, false), pushSettings(), pushHistory()];
    return Promise.all(parts.map(function (p) { return p.then(function () { return null; }, function (e) { return e; }); }))
      .then(function (errs) {
        var e = errs.filter(Boolean)[0];
        lastError = e ? A().humanError(e) : "";
        emit(e ? "sync-error" : "synced");
        return !e;
      });
  }

  function pullAll() {
    var a = A(), uid = me();
    if (!uid) return Promise.resolve();
    return Promise.all([a.userRows("user_notes"), a.userRows("user_bookmarks"), a.getDoc("user_settings"), a.getDoc("user_history")]).then(function (r) {
      lastPull = Date.now();
      notes.replace(mergeRows(notes.all(), r[0], OPTS).rows);
      marks.replace(mergeRows(marks.all(), r[1], {}).rows);
      // settings: last write wins; settings left by another account in this browser never go into this one
      var sm = meta().settings || {}, srow = r[2], owner = get(SETTINGS_OWNER, "");
      var foreign = !!owner && owner !== uid;
      if (srow && (foreign || !sm.dirty || (sm.srv !== srow.updated_at && Date.parse(srow.updated_at) > (sm.at || 0)))) {
        applySettings(cleanSettings(srow.data)); setMeta("settings", { dirty: false, srv: srow.updated_at }); put(SETTINGS_OWNER, uid);
      } else if (!srow && foreign) {
        applySettings({}); setMeta("settings", { dirty: false }); put(SETTINGS_OWNER, uid);
      } else if (!srow || sm.dirty) setMeta("settings", { dirty: true });
      var local = get(HISTORY, { items: [] }), merged = mergeHistory(local, { items: r[3] ? r[3].items : [] });
      put(HISTORY, merged);
      if (JSON.stringify(merged.items) !== JSON.stringify(r[3] ? r[3].items : [])) setMeta("history", { dirty: true });
      emit("pulled");
    });
  }

  function syncAll() {
    if (!signedIn()) return Promise.resolve(false);
    if (syncing) return syncing;
    syncing = pullAll().then(pushAll).catch(function (e) { lastError = A().humanError(e); emit("sync-error"); return false; })
      .then(function (ok) { syncing = null; return ok; });
    return syncing;
  }

  function dirtyCount() {
    var n = 0;
    [notes.all(), marks.all()].forEach(function (s) { Object.keys(s).forEach(function (k) { if (s[k].dirty) n++; }); });
    var m = meta();
    if ((m.settings || {}).dirty) n++;
    if ((m.history || {}).dirty) n++;
    return n;
  }

  // ------------------------------------------------------------------ hooks into the rest of the site
  // settings controls (account page, ready-only filter anywhere): mark dirty, push; a guest's change makes them a guest's
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (!t || !t.matches || !t.matches("[data-setting], [data-ready-only]")) return;
    setMeta("settings", { dirty: true, at: Date.now() });
    put(SETTINGS_OWNER, me() || "");
    schedule();
  });
  window.addEventListener("online", function () { if (dirtyCount()) pushAll(); });
  // another device may have written meanwhile: pull again when the tab comes back (at most once a minute)
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && signedIn() && Date.now() - lastPull > 60000) syncAll();
  });

  function hookAccount() {
    var a = A();
    if (!a || !a.enabled || !a.onLogin) return;
    a.onLogin(function () { syncAll(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", hookAccount); else hookAccount();

  // plain-text export of every note (progress page): lesson, section, text
  function exportNotes(titleOf) {
    var out = [T("Конспекты UAV Student · {d}", { d: new Date().toISOString().slice(0, 10) }), ""];
    notes.list().sort(function (x, y) { return (x.m + "#" + x.a).localeCompare(y.m + "#" + y.a); }).forEach(function (r) {
      out.push("### " + ((titleOf && titleOf(r.m)) || r.title || r.m) + (r.a ? " · " + (r.label || r.a) : ""));
      out.push(r.body, "");
    });
    return out.join("\n");
  }

  // The session ended without a logout (expired or revoked): keep what never reached the server, drop the rest.
  // account.js keeps the owner mark, so only the same account merges these rows at its next login.
  function keepUnsynced() {
    var kept = 0;
    [[NOTES, notes], [MARKS, marks]].forEach(function (p) {
      var s = p[1].all(), out = {};
      Object.keys(s).forEach(function (k) { if (s[k].dirty && !s[k].del) { out[k] = s[k]; kept++; } });
      put(p[0], out);
    });
    try { localStorage.removeItem(HISTORY); localStorage.removeItem(META); } catch (e) { /* storage off */ }
    emit("pulled");
    return kept;
  }

  window.UAVUserData = Object.assign({
    NOTE_MAX: NOTE_MAX, notes: notes, bookmarks: marks,
    readSettings: readSettings, syncAll: syncAll, signedIn: signedIn,
    pending: dirtyCount, error: function () { return lastError; },
    keepUnsynced: keepUnsynced,
    // before logout: push what is waiting; resolves true when nothing is left behind
    flush: function () { clearTimeout(timer); return (dirtyCount() ? pushAll() : Promise.resolve(true)).then(function () { return dirtyCount() === 0; }); },
    // history.js after each save
    touched: function (what) {
      if (what !== "history" || !signedIn()) return;
      setMeta("history", { dirty: true });
      clearTimeout(histTimer);
      histTimer = setTimeout(pushAll, 10000);
    },
    exportNotes: exportNotes
  }, pure);
})();
