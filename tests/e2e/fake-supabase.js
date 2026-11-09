/*
 * In-memory stand-in for the slice of supabase-js that assets/account.js uses, persisted in
 * localStorage so it survives page navigation. Injected by tests/e2e/accounts.e2e.js before page scripts.
 * It mimics the access rules loosely (own rows for students, all rows for staff, set_role for the
 * superadmin) so the UI flows can be exercised; the real rules are tested in supabase/tests.
 */
(function () {
  var DBK = "fake-supabase-db", SK = "fake-supabase-session";
  function load() {
    var d = JSON.parse(localStorage.getItem(DBK) || '{"users":[],"progress":{},"audit":[]}');
    d.exams = d.exams || []; d.cohorts = d.cohorts || []; d.cohort_members = d.cohort_members || []; d.exam_questions = d.exam_questions || []; d.exam_attempts = d.exam_attempts || [];
    return d;
  }
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
    if (table === "cohorts") return db.cohorts.filter(function (c) {
      return staff(u) || (u && db.cohort_members.some(function (m) { return m.cohort_id === c.id && m.user_id === u.id; })); });
    if (table === "cohort_members") return db.cohort_members.filter(function (m) { return staff(u) || (u && m.user_id === u.id); });
    if (table === "exams") return db.exams.filter(function (e) { return e.published || staff(u); });
    if (table === "exam_questions") return staff(u) ? db.exam_questions.slice() : [];
    if (table === "exam_results") return db.exam_attempts.filter(function (a) { return staff(u) || (u && a.user_id === u.id); }).map(function (a) {
      var e = db.exams.filter(function (x) { return x.id === a.exam_id; })[0] || {};
      var p = db.users.filter(function (x) { return x.id === a.user_id; })[0] || {};
      return Object.assign({ title: e.title, username: p.username, email: p.email }, a);
    });
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
      insert: function (row) { mode = "insert"; payload = row; return q; },
      delete: function () { mode = "delete"; return q; },
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
      if (mode === "insert") {
        if (!staff(u)) return fail("new row violates row-level security policy");
        var rows = Array.isArray(payload) ? payload : [payload], made = [];
        if (table === "cohorts") {
          for (var ci = 0; ci < rows.length; ci++) {
            var nm = String(rows[ci].name || "").trim();
            if (nm.length < 2) return fail('new row violates check constraint "cohorts_name_check"');
            if (db.cohorts.some(function (c) { return c.name.toLowerCase() === nm.toLowerCase(); })) return fail('duplicate key value violates unique constraint "cohorts_name_unique"');
            var c = { id: "c-" + Math.random().toString(36).slice(2, 9), name: nm, created_by: u.id, created_at: new Date().toISOString() };
            db.cohorts.push(c); made.push(c);
          }
        }
        if (table === "cohort_members") {
          for (var mi = 0; mi < rows.length; mi++) {
            var r0 = rows[mi];
            if (db.cohort_members.some(function (m) { return m.cohort_id === r0.cohort_id && m.user_id === r0.user_id; })) return fail('duplicate key value violates unique constraint "cohort_members_pkey"');
            var mm = { cohort_id: r0.cohort_id, user_id: r0.user_id, added_by: u.id, added_at: new Date().toISOString() };
            db.cohort_members.push(mm); made.push(mm);
          }
        }
        if (table === "exams") rows.forEach(function (r) {
          var e = Object.assign({ id: "e-" + Math.random().toString(36).slice(2, 9), pass_pct: 80, questions_per_attempt: 10, time_limit_min: 20,
                                  attempts_allowed: 1, show_review: true, published: false, created_at: new Date().toISOString() }, r);
          db.exams.push(e); made.push(e);
        });
        if (table === "exam_questions") {
          for (var i = 0; i < rows.length; i++) {
            var r = rows[i];
            if (!Array.isArray(r.options) || r.answer < 0 || r.answer >= r.options.length) return fail("new row violates check constraint");
            if (db.exam_attempts.some(function (a) { return a.exam_id === r.exam_id; })) return fail("this exam already has attempts");
          }
          rows.forEach(function (r) { var x = Object.assign({ id: db.exam_questions.length + 1 }, r); db.exam_questions.push(x); made.push(x); });
        }
        save(db);
        return single ? ok(made[0]) : ok(made);
      }
      if (mode === "delete") {
        var did = (filters.filter(function (f) { return f[0] === "id"; })[0] || [])[1];
        if ((table === "cohorts" || table === "cohort_members") && staff(u)) {
          var hit = function (r) { return filters.every(function (f) { return String(r[f[0]]) === String(f[1]); }); };
          if (table === "cohorts") {
            db.cohort_members = db.cohort_members.filter(function (m) { return m.cohort_id !== did; });
            db.cohorts = db.cohorts.filter(function (c) { return !hit(c); });
          } else db.cohort_members = db.cohort_members.filter(function (m) { return !hit(m); });
          save(db); return ok(null);
        }
        if (table !== "exams" || !staff(u)) return ok(null);
        if (db.exam_attempts.some(function (a) { return a.exam_id === did; })) return fail("violates foreign key constraint");
        db.exams = db.exams.filter(function (e) { return e.id !== did; });
        db.exam_questions = db.exam_questions.filter(function (x) { return x.exam_id !== did; });
        save(db); return ok(null);
      }
      if (mode === "update" && table === "exams") {
        var xid = (filters.filter(function (f) { return f[0] === "id"; })[0] || [])[1];
        if (!staff(u)) return ok(null);
        db.exams.forEach(function (e) { if (e.id === xid) Object.assign(e, payload); }); save(db); return ok(null);
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
      if (name === "exam_start") {
        if (!u) return fail("log in with a confirmed account");
        var e = db.exams.filter(function (x) { return x.id === args.p_exam && x.published; })[0];
        if (!e) return fail("no such exam");
        var now = Date.now();
        var run = db.exam_attempts.filter(function (a) { return a.exam_id === e.id && a.user_id === u.id && !a.submitted_at && new Date(a.deadline).getTime() > now; })[0];
        if (!run) {
          var used = db.exam_attempts.filter(function (a) { return a.exam_id === e.id && a.user_id === u.id; }).length;
          if (used >= e.attempts_allowed) return fail("no attempts left (" + used + " of " + e.attempts_allowed + ")");
          var ids = db.exam_questions.filter(function (x) { return x.exam_id === e.id; }).map(function (x) { return x.id; }).slice(0, e.questions_per_attempt);
          run = { id: "a-" + Math.random().toString(36).slice(2, 9), exam_id: e.id, user_id: u.id, started_at: new Date().toISOString(),
                  deadline: new Date(now + e.time_limit_min * 60000).toISOString(), question_ids: ids, submitted_at: null };
          db.exam_attempts.push(run); save(db);
        }
        var qs = run.question_ids.map(function (id) { var x = db.exam_questions.filter(function (y) { return y.id === id; })[0]; return { id: x.id, q: x.q, options: x.options }; });
        return ok({ attempt: run.id, exam: e.id, title: e.title, deadline: run.deadline, questions: qs });
      }
      if (name === "exam_submit") {
        var a = db.exam_attempts.filter(function (x) { return x.id === args.p_attempt && u && x.user_id === u.id; })[0];
        if (!a) return fail("no such attempt");
        if (a.submitted_at) return fail("this attempt is already submitted");
        var ex = db.exams.filter(function (x) { return x.id === a.exam_id; })[0];
        var correct = 0, review = [];
        a.question_ids.forEach(function (id) {
          var x = db.exam_questions.filter(function (y) { return y.id === id; })[0];
          var pick = typeof args.p_answers[id] === "number" ? args.p_answers[id] : null;
          if (pick === x.answer) correct++;
          review.push({ id: id, your: pick, answer: x.answer, explain: x.explain });
        });
        a.submitted_at = new Date().toISOString(); a.correct = correct; a.total = a.question_ids.length;
        a.score_pct = Math.round(100 * correct / Math.max(1, a.total)); a.passed = a.score_pct >= ex.pass_pct; save(db);
        return ok({ correct: a.correct, total: a.total, score_pct: a.score_pct, passed: a.passed, review: ex.show_review ? review : null });
      }
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
