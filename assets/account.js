/*
 * Accounts and server sync (docs/MULTIUSER-PLAN.md). Off unless assets/backend-config.js enables it:
 * with the flag off this file only defines window.UAVAccount with enabled=false and touches nothing.
 *
 * With the flag on:
 *   - Supabase Auth (email + password, username stored in the profile);
 *   - progress stays in localStorage (offline works), and every local write is pushed to the
 *     progress row of the logged-in user (debounced); on login the local and server documents are
 *     merged so nothing studied anonymously is lost;
 *   - logout clears this browser's copy (shared computers).
 * Access rules are enforced by the database (RLS); nothing here is a security boundary.
 *
 * Test hook: window.UAV_BACKEND.client may hold a ready client object with the same surface.
 */
(function () {
  "use strict";

  var CFG = window.UAV_BACKEND || { enabled: false };
  var KEY = "uav-student:progress:v1";
  var PENDING = "uav-student:sync-pending";
  var USERNAME_RE = /^[a-z0-9_]{3,32}$/;
  var MIN_PASSWORD = 10;

  // ------------------------------------------------------------------ pure merge (unit-tested)
  function norm(d) {
    d = d || {};
    return { done: d.done || [], checks: d.checks || [], quiz: d.quiz || {}, tasks: d.tasks || {}, labs: d.labs || [] };
  }

  function ratio(q) { return q && q.total ? q.correct / q.total : -1; }

  function merge(a, b) {
    a = norm(a); b = norm(b);
    var out = { done: [], checks: [], quiz: {}, tasks: {}, labs: [] };
    out.done = Array.from(new Set(a.done.concat(b.done))).sort();
    out.checks = Array.from(new Set(a.checks.concat(b.checks))).sort();
    Object.keys(a.quiz).concat(Object.keys(b.quiz)).forEach(function (k) {
      var x = a.quiz[k], y = b.quiz[k];
      var best = !x ? y : !y ? x : ratio(x) > ratio(y) ? x : ratio(y) > ratio(x) ? y : ((x.ts || 0) >= (y.ts || 0) ? x : y);
      var r = Object.assign({}, best);
      var att = Math.max((x && x.attempts) || 0, (y && y.attempts) || 0);
      if (att) r.attempts = att;
      var last = Math.max((x && x.last) || 0, (y && y.last) || 0);
      if (last) r.last = last;
      out.quiz[k] = r;
    });
    Object.keys(a.tasks).concat(Object.keys(b.tasks)).forEach(function (m) {
      var t = Object.assign({}, a.tasks[m] || {}, b.tasks[m] || {});
      Object.keys(t).forEach(function (id) { if (!t[id]) delete t[id]; });
      out.tasks[m] = t;
    });
    var seen = {};
    a.labs.concat(b.labs).forEach(function (l) {
      var key = l.key || JSON.stringify(l);
      if (!seen[key]) { seen[key] = true; out.labs.push(l); }
    });
    out.labs.sort(function (x, y) { return String(y.ts || "").localeCompare(String(x.ts || "")); });
    return out;
  }

  function same(a, b) { return JSON.stringify(merge(a, {})) === JSON.stringify(merge(b, {})); }

  // ------------------------------------------------------------------ local storage helpers
  function readLocal() { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; } }
  function writeLocal(d) { try { localStorage.setItem(KEY, JSON.stringify(d)); } catch (e) { /* storage off */ } }
  function clearLocal() { try { localStorage.removeItem(KEY); localStorage.removeItem(PENDING); } catch (e) { /* ignore */ } }
  function setPending(v) { try { if (v) localStorage.setItem(PENDING, "1"); else localStorage.removeItem(PENDING); } catch (e) { /* ignore */ } }
  function isPending() { try { return localStorage.getItem(PENDING) === "1"; } catch (e) { return false; } }

  // ------------------------------------------------------------------ state and events
  var st = { client: null, session: null, profile: null, recovery: false, sync: "idle", error: "" };
  var listeners = [];
  function notify() { listeners.forEach(function (cb) { try { cb(snapshot()); } catch (e) { console.error(e); } }); renderNav(); }
  function snapshot() {
    return { enabled: !!CFG.enabled, user: st.session ? st.session.user : null, profile: st.profile,
             recovery: st.recovery, sync: st.sync, error: st.error,
             isStaff: !!(st.profile && (st.profile.role === "admin" || st.profile.role === "superadmin")),
             isSuperadmin: !!(st.profile && st.profile.role === "superadmin") };
  }

  function base() { return (document.body && document.body.getAttribute("data-base")) || ""; }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script"); s.src = src; s.onload = resolve;
      s.onerror = function () { reject(new Error("не удалось загрузить " + src)); };
      document.head.appendChild(s);
    });
  }

  function getClient() {
    if (CFG.client) return Promise.resolve(CFG.client);
    var make = function () {
      return window.supabase.createClient(CFG.url, CFG.anonKey, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } });
    };
    if (window.supabase && window.supabase.createClient) return Promise.resolve(make());
    return loadScript(base() + "assets/vendor/supabase/supabase.js").then(make);
  }

  // ------------------------------------------------------------------ errors in plain Russian
  function humanError(err) {
    var m = (err && (err.message || err.error_description || String(err))) || "неизвестная ошибка";
    if (/invalid login credentials/i.test(m)) return "Неверная почта или пароль.";
    if (/already registered|already exists/i.test(m)) return "Эта почта уже зарегистрирована. Войди или восстанови пароль.";
    if (/email not confirmed/i.test(m)) return "Почта не подтверждена: открой ссылку из письма.";
    if (/database error saving new user|username/i.test(m)) return "Имя пользователя занято или не подходит (3–32 символа: a-z, 0-9, _).";
    if (/rate limit|too many/i.test(m)) return "Слишком много попыток, подожди минуту.";
    if (/failed to fetch|network/i.test(m)) return "Нет связи с сервером. Прогресс сохраняется локально и уйдёт позже.";
    if (/password/i.test(m) && /least|short|weak/i.test(m)) return "Пароль слишком простой: минимум " + MIN_PASSWORD + " символов.";
    return m;
  }

  function check(res) {
    if (res && res.error) throw res.error;
    return res ? res.data : null;
  }

  // ------------------------------------------------------------------ profile and sync
  function uid() { return st.session && st.session.user ? st.session.user.id : null; }

  function loadProfile() {
    return st.client.from("profiles").select("id,username,email,role,created_at").eq("id", uid()).single()
      .then(check).then(function (p) { st.profile = p; });
  }

  var pushTimer = null;
  function push(data) {
    if (!uid()) return Promise.resolve();
    st.sync = "saving"; notify();
    return st.client.from("progress").upsert({ user_id: uid(), data: norm(data) }).then(check)
      .then(function () { setPending(false); st.sync = "saved"; st.error = ""; notify(); })
      .catch(function (e) { setPending(true); st.sync = "offline"; st.error = humanError(e); notify(); });
  }
  function schedulePush() {
    if (!uid()) return;
    setPending(true);
    clearTimeout(pushTimer);
    pushTimer = setTimeout(function () { push(readLocal()); }, 1200);
  }

  function syncDown() {
    st.sync = "loading"; notify();
    return st.client.from("progress").select("data,updated_at").eq("user_id", uid()).maybeSingle().then(check)
      .then(function (row) {
        var server = row ? row.data : {};
        var local = readLocal();
        var merged = merge(local, server);
        writeLocal(merged);
        if (!same(merged, server) || isPending()) return push(merged);
        st.sync = "saved"; notify();
      })
      .catch(function (e) { st.sync = "offline"; st.error = humanError(e); notify(); });
  }

  function setSession(session) {
    var before = uid();
    st.session = session || null;
    if (!st.session) { st.profile = null; notify(); return Promise.resolve(); }
    if (before === uid() && st.profile) { notify(); return Promise.resolve(); }
    return loadProfile().then(syncDown).catch(function (e) { st.error = humanError(e); notify(); });
  }

  function patchStore() {
    var store = window.UAVProgress;
    if (!store || store.__accountPatched) return;
    var write = store._write, reset = store.reset;
    store._write = function (d) { write.call(store, d); schedulePush(); };
    store.reset = function () { return reset.call(store).then(function () { if (uid()) return push({}); }); };
    store.__accountPatched = true;
  }

  // ------------------------------------------------------------------ nav link
  function renderNav() {
    if (!CFG.enabled) return;
    var nav = document.querySelector(".site-header .gc-nav");
    if (!nav) return;
    var a = document.getElementById("nav-account");
    if (!a) { a = document.createElement("a"); a.id = "nav-account"; nav.appendChild(a); }
    a.href = base() + "pages/account.html";
    a.textContent = st.profile ? "👤 " + st.profile.username : "Войти";
    var adm = document.getElementById("nav-admin");
    var staff = snapshot().isStaff;
    if (staff && !adm) { adm = document.createElement("a"); adm.id = "nav-admin"; adm.textContent = "Админка"; adm.href = base() + "pages/admin.html"; nav.appendChild(adm); }
    if (!staff && adm) adm.remove();
  }

  // ------------------------------------------------------------------ public API
  var ready;
  function init() {
    if (ready) return ready;
    if (!CFG.enabled) { ready = Promise.resolve(snapshot()); return ready; }
    patchStore();
    ready = getClient().then(function (c) {
      st.client = c;
      c.auth.onAuthStateChange(function (event, session) {
        if (event === "PASSWORD_RECOVERY") st.recovery = true;
        setSession(session);
      });
      return c.auth.getSession();
    }).then(function (res) { return setSession(res && res.data ? res.data.session : null); })
      .then(snapshot)
      .catch(function (e) { st.error = humanError(e); notify(); return snapshot(); });
    window.addEventListener("online", function () { if (uid() && isPending()) push(readLocal()); });
    return ready;
  }

  function need() { if (!st.client) throw new Error("аккаунты выключены"); }

  var api = {
    get enabled() { return !!CFG.enabled; },
    USERNAME_RE: USERNAME_RE, MIN_PASSWORD: MIN_PASSWORD,
    merge: merge, humanError: humanError,
    init: init,
    state: snapshot,
    onChange: function (cb) { listeners.push(cb); },

    signUp: function (email, username, password) {
      need();
      username = String(username || "").trim().toLowerCase();
      if (!USERNAME_RE.test(username)) return Promise.reject(new Error("Имя пользователя: 3–32 символа, a-z, 0-9, _."));
      if (String(password || "").length < MIN_PASSWORD) return Promise.reject(new Error("Пароль: минимум " + MIN_PASSWORD + " символов."));
      return st.client.auth.signUp({ email: email, password: password,
        options: { data: { username: username }, emailRedirectTo: location.origin + location.pathname } })
        .then(check).then(function (d) { return { needsConfirmation: !(d && d.session) }; });
    },
    signIn: function (email, password) {
      need();
      return st.client.auth.signInWithPassword({ email: email, password: password }).then(check)
        .then(function (d) { return setSession(d.session); }).then(snapshot);
    },
    signOut: function () {
      need();
      clearTimeout(pushTimer);
      var flush = isPending() ? push(readLocal()) : Promise.resolve();
      return flush.then(function () { return st.client.auth.signOut(); }).then(function () {
        clearLocal(); st.recovery = false; return setSession(null);
      });
    },
    resetPassword: function (email) {
      need();
      return st.client.auth.resetPasswordForEmail(email, { redirectTo: location.origin + location.pathname }).then(check);
    },
    updatePassword: function (password) {
      need();
      if (String(password || "").length < MIN_PASSWORD) return Promise.reject(new Error("Пароль: минимум " + MIN_PASSWORD + " символов."));
      return st.client.auth.updateUser({ password: password }).then(check).then(function () { st.recovery = false; notify(); });
    },
    rename: function (username) {
      need();
      username = String(username || "").trim().toLowerCase();
      if (!USERNAME_RE.test(username)) return Promise.reject(new Error("Имя пользователя: 3–32 символа, a-z, 0-9, _."));
      return st.client.from("profiles").update({ username: username }).eq("id", uid()).then(check).then(loadProfile).then(notify);
    },
    syncNow: function () { need(); return push(readLocal()); },

    // staff
    listStudents: function () {
      need();
      return st.client.from("student_progress").select("id,username,email,role,created_at,data,updated_at").order("username").then(check);
    },
    audit: function () {
      need();
      return st.client.from("role_audit").select("id,actor,target,old_role,new_role,at").order("at", { ascending: false }).limit(100).then(check);
    },
    setRole: function (target, role) {
      need();
      return st.client.rpc("set_role", { target: target, new_role: role }).then(check);
    }
  };

  window.UAVAccount = api;
  if (CFG.enabled) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
  }
  if (typeof module !== "undefined" && module.exports) module.exports = { merge: merge };
})();
