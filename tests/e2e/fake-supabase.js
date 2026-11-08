/*
 * In-memory stand-in for the slice of supabase-js that assets/account.js uses, persisted in
 * localStorage so it survives page navigation. Injected by tests/e2e/accounts.e2e.js before page scripts.
 * It mimics the access rules loosely (own rows for students, all rows for staff, set_role for the
 * superadmin) so the UI flows can be exercised; the real rules are tested in supabase/tests.
 */
(function () {
  var DBK = "fake-supabase-db", SK = "fake-supabase-session";
  function load() { return JSON.parse(localStorage.getItem(DBK) || '{"users":[],"progress":{},"audit":[]}'); }
  function save(db) { localStorage.setItem(DBK, JSON.stringify(db)); }
  function sess() { return JSON.parse(localStorage.getItem(SK) || "null"); }
  function setSess(s) { if (s) localStorage.setItem(SK, JSON.stringify(s)); else localStorage.removeItem(SK); }
  function me(db) { var s = sess(); return s ? db.users.filter(function (u) { return u.id === s.user.id; })[0] : null; }
  function staff(u) { return u && (u.role === "admin" || u.role === "superadmin"); }
  function ok(data) { return Promise.resolve({ data: data, error: null }); }
  function fail(m) { return Promise.resolve({ data: null, error: { message: m } }); }
  var listeners = [];
  function emit(ev, s) { listeners.forEach(function (cb) { cb(ev, s); }); }
  window.__fakeCalls = [];

  function rowsFor(table, db, u) {
    if (table === "profiles") return db.users.filter(function (x) { return staff(u) || (u && x.id === u.id); })
      .map(function (x) { return { id: x.id, username: x.username, email: x.email, role: x.role, created_at: x.created_at }; });
    if (table === "progress") return Object.keys(db.progress).filter(function (k) { return staff(u) || (u && k === u.id); })
      .map(function (k) { return { user_id: k, data: db.progress[k].data, updated_at: db.progress[k].updated_at }; });
    if (table === "student_progress") return rowsFor("profiles", db, u).map(function (p) {
      var g = db.progress[p.id] || {}; return Object.assign({}, p, { data: g.data || {}, updated_at: g.updated_at || null }); });
    if (table === "role_audit") return staff(u) ? db.audit.slice() : [];
    return [];
  }

  function query(table) {
    var filters = [], mode = "select", payload = null, single = null, ord = null, lim = null;
    var q = {
      select: function () { return q; },
      eq: function (k, v) { filters.push([k, v]); return q; },
      order: function (k, o) { ord = [k, !o || o.ascending !== false]; return q; },
      limit: function (n) { lim = n; return q; },
      single: function () { single = "single"; return q; },
      maybeSingle: function () { single = "maybe"; return q; },
      upsert: function (row) { mode = "upsert"; payload = row; return q; },
      update: function (row) { mode = "update"; payload = row; return q; },
      then: function (res, rej) { return run().then(res, rej); }
    };
    function run() {
      var db = load(), u = me(db);
      window.__fakeCalls.push({ table: table, mode: mode, payload: payload });
      if (mode === "upsert") {
        if (!u || payload.user_id !== u.id) return fail("new row violates row-level security policy");
        db.progress[u.id] = { data: payload.data, updated_at: new Date().toISOString() }; save(db); return ok(null);
      }
      if (mode === "update") {
        var id = (filters.filter(function (f) { return f[0] === "id"; })[0] || [])[1];
        if (!u || id !== u.id) return ok(null);
        if (db.users.some(function (x) { return x.username === payload.username && x.id !== u.id; })) return fail("duplicate key value violates unique constraint");
        u.username = payload.username; save(db); return ok(null);
      }
      var rows = rowsFor(table, db, u).filter(function (r) { return filters.every(function (f) { return String(r[f[0]]) === String(f[1]); }); });
      if (ord) rows.sort(function (a, b) { return (a[ord[0]] > b[ord[0]] ? 1 : -1) * (ord[1] ? 1 : -1); });
      if (lim) rows = rows.slice(0, lim);
      if (single === "single") return rows.length === 1 ? ok(rows[0]) : fail("JSON object requested, multiple (or no) rows returned");
      if (single === "maybe") return ok(rows[0] || null);
      return ok(rows);
    }
    return q;
  }

  var client = {
    auth: {
      getSession: function () { return ok({ session: sess() }); },
      onAuthStateChange: function (cb) { listeners.push(cb); return { data: { subscription: { unsubscribe: function () {} } } }; },
      signUp: function (o) {
        var db = load();
        if (db.users.some(function (x) { return x.email === o.email; })) return fail("User already registered");
        var un = o.options.data.username;
        if (db.users.some(function (x) { return x.username === un; })) return fail("Database error saving new user");
        var u = { id: "u-" + Math.random().toString(36).slice(2, 10), email: o.email, username: un, password: o.password, role: "student", created_at: new Date().toISOString() };
        db.users.push(u); db.progress[u.id] = { data: {}, updated_at: u.created_at }; save(db);
        var s = { user: { id: u.id, email: u.email } }; setSess(s); emit("SIGNED_IN", s);
        return ok({ user: s.user, session: s });
      },
      signInWithPassword: function (o) {
        var db = load(), u = db.users.filter(function (x) { return x.email === o.email && x.password === o.password; })[0];
        if (!u) return fail("Invalid login credentials");
        var s = { user: { id: u.id, email: u.email } }; setSess(s); emit("SIGNED_IN", s);
        return ok({ user: s.user, session: s });
      },
      signOut: function () { setSess(null); emit("SIGNED_OUT", null); return ok(null); },
      resetPasswordForEmail: function () { return ok({}); },
      updateUser: function () { return ok({}); }
    },
    from: query,
    rpc: function (name, args) {
      var db = load(), u = me(db);
      window.__fakeCalls.push({ rpc: name, args: args });
      if (name !== "set_role") return fail("unknown rpc");
      if (!u || u.role !== "superadmin") return fail("only the superadmin can change roles");
      var t = db.users.filter(function (x) { return x.id === args.target; })[0];
      if (!t || t.role === "superadmin" || args.new_role === "superadmin") return fail("not allowed");
      db.audit.unshift({ id: db.audit.length + 1, actor: u.id, target: t.id, old_role: t.role, new_role: args.new_role, at: new Date().toISOString() });
      t.role = args.new_role; save(db); return ok(null);
    }
  };

  window.UAV_BACKEND = { enabled: true, url: "fake", anonKey: "fake", client: client };
  window.__fakeSeed = function (users, progress) {
    var db = load();
    users.forEach(function (u) { if (!db.users.some(function (x) { return x.id === u.id; })) { db.users.push(u); db.progress[u.id] = { data: (progress && progress[u.id]) || {}, updated_at: new Date().toISOString() }; } });
    save(db);
  };
})();
