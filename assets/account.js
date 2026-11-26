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
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";

  var CFG = window.UAV_BACKEND || { enabled: false };
  var KEY = "uav-student:progress:v1";
  var PENDING = "uav-student:sync-pending";
  var OWNER = "uav-student:owner";            // whose progress sits in this browser (shared computers)
  var PRIVATE = ["uav-student:notes:v1", "uav-student:bookmarks:v1", "uav-student:history:v1", "uav-student:userdata-sync"];   // assets/user-data.js
  // personal tables (0007) and the columns the browser reads back
  var DATA_TABLES = { user_notes: "module_id,anchor,label,body,updated_at", user_bookmarks: "module_id,anchor,label,updated_at" };
  var DOC_TABLES = { user_settings: "data", user_history: "items" };
  var USERNAME_RE = /^[a-z0-9_]{3,32}$/;
  var MIN_PASSWORD = 10;

  // ------------------------------------------------------------------ pure merge (unit-tested)
  // tolerate anything: the document may come from another device, an old version or a hostile edit
  function arr(x) { return Array.isArray(x) ? x : []; }
  function obj(x) { return x && typeof x === "object" && !Array.isArray(x) ? x : {}; }
  function isStr(x) { return typeof x === "string"; }
  function norm(d) {
    d = obj(d);
    return { done: arr(d.done).filter(isStr), checks: arr(d.checks).filter(isStr), quiz: obj(d.quiz), tasks: obj(d.tasks),
             labs: arr(d.labs).filter(function (l) { return l && typeof l === "object" && !Array.isArray(l); }) };
  }

  function ratio(q) { return q && q.total ? q.correct / q.total : -1; }

  function merge(a, b) {
    a = norm(a); b = norm(b);
    var out = { done: [], checks: [], quiz: {}, tasks: {}, labs: [] };
    out.done = Array.from(new Set(a.done.concat(b.done))).sort();
    out.checks = Array.from(new Set(a.checks.concat(b.checks))).sort();
    Object.keys(a.quiz).concat(Object.keys(b.quiz)).forEach(function (k) {
      var x = obj(a.quiz[k]), y = obj(b.quiz[k]);
      if (!Object.keys(x).length) x = null;
      if (!Object.keys(y).length) y = null;
      var best = !x ? y : !y ? x : ratio(x) > ratio(y) ? x : ratio(y) > ratio(x) ? y : ((x.ts || 0) >= (y.ts || 0) ? x : y);
      var r = Object.assign({}, best);
      var att = Math.max((x && x.attempts) || 0, (y && y.attempts) || 0);
      if (att) r.attempts = att;
      var last = Math.max((x && x.last) || 0, (y && y.last) || 0);
      if (last) r.last = last;
      out.quiz[k] = r;
    });
    Object.keys(a.tasks).concat(Object.keys(b.tasks)).forEach(function (m) {
      var t = Object.assign({}, obj(a.tasks[m]), obj(b.tasks[m]));
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
  // keepUnsynced: the session ended by itself (expired, revoked) — notes and bookmarks that never reached the server
  // stay, with the owner mark, so the same account pushes them at its next login and any other account wipes them
  function clearLocal(keepUnsynced) {
    var kept = keepUnsynced && window.UAVUserData && window.UAVUserData.keepUnsynced ? window.UAVUserData.keepUnsynced() : 0;
    try {
      localStorage.removeItem(KEY); localStorage.removeItem(PENDING);
      if (!kept) localStorage.removeItem(OWNER);
      // exam picks of this account must not stay for the next person on a shared browser (review 2026-11-09, L5)
      Object.keys(localStorage).forEach(function (k) { if (k.indexOf("uav-student:exam-draft:") === 0) localStorage.removeItem(k); });
      // notes, bookmarks and reading history are personal too (they are on the server); settings stay
      if (!kept) PRIVATE.forEach(function (k) { localStorage.removeItem(k); });
    } catch (e) { /* ignore */ }
  }
  // Progress of another account left in this browser is wiped, never merged into the next account;
  // anonymous (ownerless) progress is merged on first login, as intended.
  function claimLocal(id) {
    try { var o = localStorage.getItem(OWNER); if (o && o !== id) clearLocal(); localStorage.setItem(OWNER, id); } catch (e) { /* ignore */ }
  }
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

  function base() { return (document.body && document.body.getAttribute("data-base")) || ""; }   // the language tree
  function root() { return (document.body && (document.body.getAttribute("data-root") || document.body.getAttribute("data-base"))) || ""; }   // shared assets

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script"); s.src = src; s.onload = resolve;
      s.onerror = function () { reject(new Error(T("не удалось загрузить ") + src)); };
      document.head.appendChild(s);
    });
  }

  function getClient() {
    if (CFG.client) return Promise.resolve(CFG.client);
    var make = function () {
      return window.supabase.createClient(CFG.url, CFG.anonKey, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } });
    };
    if (window.supabase && window.supabase.createClient) return Promise.resolve(make());
    return loadScript(root() + "assets/vendor/supabase/supabase.js").then(make);
  }

  // ------------------------------------------------------------------ errors in plain Russian
  function humanError(err) {
    var m = (err && (err.message || err.error_description || String(err))) || T("неизвестная ошибка");
    if (/invalid login credentials/i.test(m)) return T("Неверная почта или пароль.");
    if (/already registered|already exists/i.test(m)) return T("Эта почта уже зарегистрирована. Войди или восстанови пароль.");
    if (/email not confirmed/i.test(m)) return T("Почта не подтверждена: открой ссылку из письма.");
    if (/database error saving new user|username/i.test(m)) return T("Имя пользователя занято или не подходит (3–32 символа: a-z, 0-9, _).");
    if (/feedback rate limit/i.test(m)) return T("Слишком много сообщений: не больше 10 в час и 50 в сутки. Попробуй позже.");
    if (/user_notes limit reached/i.test(m)) return T("Достигнут предел: не больше 2000 заметок на аккаунт.");
    if (/user_bookmarks limit reached/i.test(m)) return T("Достигнут предел: не больше 1000 закладок на аккаунт.");
    if (/feedback_body_check|feedback_kind_check|feedback_target/i.test(m)) return T("Сообщение: от 10 до 4000 символов и тип из списка.");
    if (/feedback_(anchor|page_lang|module_id|section_key)_check/i.test(m)) return T("Сообщение не принято: неверная ссылка на урок или раздел.");
    if (/user_(notes|bookmarks)_(module_id|anchor)_check|bad module or anchor/i.test(m)) return T("Заметка или закладка с неверной ссылкой на урок — сервер её не примет.");
    if (/user_notes_body_check|bad note text/i.test(m)) return T("Заметка пустая или длиннее 8000 символов.");
    if (/rate limit|too many/i.test(m)) return T("Слишком много попыток, подожди минуту.");
    if (/no attempts left/i.test(m)) return T("Попытки на этот экзамен закончились.");
    if (/time is up/i.test(m)) return T("Время вышло: попытка не принята.");
    if (/not open now/i.test(m)) return T("Экзамен сейчас закрыт (вне окна сдачи).");
    if (/already submitted/i.test(m)) return T("Эта попытка уже сдана.");
    if (/already has attempts/i.test(m)) return T("По экзамену уже есть попытки: вопросы и сам экзамен менять нельзя, можно только снять с публикации.");
    if (/confirmed account/i.test(m)) return T("Нужен вход с подтверждённой почтой.");
    if (/cohorts_name_unique/i.test(m)) return T("Группа с таким названием уже есть.");
    if (/cohort_members_pkey/i.test(m)) return T("Студент уже в этой группе.");
    if (/cohorts_name_check/i.test(m)) return T("Название группы — от 2 до 100 символов.");
    if (/no such exam/i.test(m)) return T("Экзамен не найден или не опубликован.");
    if (/failed to fetch|network/i.test(m)) return T("Нет связи с сервером. Прогресс сохраняется локально и уйдёт позже.");
    if (/password/i.test(m) && /least|short|weak/i.test(m)) return T("Пароль слишком простой: минимум ") + MIN_PASSWORD + T(" символов.");
    return m;
  }

  function check(res) {
    if (res && res.error) throw res.error;
    return res ? res.data : null;
  }

  // ------------------------------------------------------------------ profile and sync
  function uid() { return st.session && st.session.user ? st.session.user.id : null; }

  function loadProfile() {
    return st.client.from("profiles").select("id,username,email,role,created_at,lang").eq("id", uid()).single()
      .then(check).then(function (p) { st.profile = p; applyLanguage(); });
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

  var loginHooks = [];
  function syncDown() {
    claimLocal(uid());
    loginHooks.forEach(function (cb) { try { cb(uid()); } catch (e) { console.error(e); } });   // assets/user-data.js
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

  // ------------------------------------------------------------------ account language (docs/I18N.md)
  // The account's language wins over the browser's: after login the site moves to it on any device.
  // An account without a language yet takes the one the visitor is using now.
  function applyLanguage() {
    var I = window.UAVI18N, p = st.profile;
    if (!I || !p) return;
    if (!p.lang) { setLanguage(I.chosen() || I.lang); return; }
    I.remember(p.lang);
    if (p.lang !== I.lang) { var u = I.urlFor(p.lang); if (u) location.replace(u + location.search + location.hash); }
  }

  function setLanguage(code) {
    if (!st.client || !uid() || !st.profile) return Promise.resolve();
    if (st.profile.lang === code) return Promise.resolve();
    st.profile.lang = code;
    return st.client.from("profiles").update({ lang: code }).eq("id", uid()).then(check)
      .catch(function (e) { st.error = humanError(e); notify(); });
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
    a.textContent = st.profile ? "👤 " + st.profile.username : T("Войти");
    var ex = document.getElementById("nav-exams");
    if (st.profile && !ex) { ex = document.createElement("a"); ex.id = "nav-exams"; ex.textContent = T("Экзамены"); ex.href = base() + "pages/exam.html"; nav.appendChild(ex); }
    if (!st.profile && ex) ex.remove();
    var adm = document.getElementById("nav-admin");
    var staff = snapshot().isStaff;
    if (staff && !adm) { adm = document.createElement("a"); adm.id = "nav-admin"; adm.textContent = T("Админка"); adm.href = base() + "pages/admin.html"; nav.appendChild(adm); }
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
        // a logout of ours wipes everything; an expired or revoked session keeps what never reached the server
        if (event === "SIGNED_OUT") clearLocal(!st.leaving);
        setSession(session);
      });
      return c.auth.getSession();
    }).then(function (res) { return setSession(res && res.data ? res.data.session : null); })
      .then(snapshot)
      .catch(function (e) { st.error = humanError(e); notify(); return snapshot(); });
    window.addEventListener("online", function () { if (uid() && isPending()) push(readLocal()); });
    return ready;
  }

  function need() { if (!st.client) throw new Error(T("аккаунты выключены")); }

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
      if (!USERNAME_RE.test(username)) return Promise.reject(new Error(T("Имя пользователя: 3–32 символа, a-z, 0-9, _.")));
      if (String(password || "").length < MIN_PASSWORD) return Promise.reject(new Error(T("Пароль: минимум ") + MIN_PASSWORD + T(" символов.")));
      return st.client.auth.signUp({ email: email, password: password,
        options: { data: { username: username }, emailRedirectTo: location.origin + location.pathname } })
        .then(check).then(function (d) { return { needsConfirmation: !(d && d.session) }; });
    },
    signIn: function (email, password) {
      need();
      return st.client.auth.signInWithPassword({ email: email, password: password }).then(check)
        .then(function (d) { return setSession(d.session); }).then(snapshot);
    },
    // Refuses to drop unsynced progress unless force=true (offline logout would lose it).
    signOut: function (force) {
      need();
      clearTimeout(pushTimer);
      var flush = isPending() ? push(readLocal()) : Promise.resolve();
      var UD = window.UAVUserData, udOk = true;
      if (UD && UD.flush) flush = flush.then(function () { return UD.flush(); }).then(function (ok) { udOk = ok; }, function () { udOk = false; });
      return flush.then(function () {
        if ((isPending() || !udOk) && !force) {
          var e = new Error(isPending() || !UD.error() ? T("Нет связи: часть прогресса ещё не на сервере. Выйти сейчас — эти изменения пропадут.")
            : T("Часть заметок или закладок не сохранилась на сервере: ") + UD.error() + T(" Выйти сейчас — эти изменения пропадут."));
          e.unsynced = true; throw e;
        }
        st.leaving = true;
        return st.client.auth.signOut({ scope: "local" });
      }).then(function () {
        st.leaving = false; clearLocal(); st.recovery = false; return setSession(null);
      }, function (err) { st.leaving = false; throw err; });
    },
    resetPassword: function (email) {
      need();
      return st.client.auth.resetPasswordForEmail(email, { redirectTo: location.origin + location.pathname }).then(check);
    },
    updatePassword: function (password) {
      need();
      if (String(password || "").length < MIN_PASSWORD) return Promise.reject(new Error(T("Пароль: минимум ") + MIN_PASSWORD + T(" символов.")));
      return st.client.auth.updateUser({ password: password }).then(check).then(function () { st.recovery = false; notify(); });
    },
    setLanguage: setLanguage,
    rename: function (username) {
      need();
      username = String(username || "").trim().toLowerCase();
      if (!USERNAME_RE.test(username)) return Promise.reject(new Error(T("Имя пользователя: 3–32 символа, a-z, 0-9, _.")));
      return st.client.from("profiles").update({ username: username }).eq("id", uid()).then(check).then(loadProfile).then(notify);
    },
    syncNow: function () {
      need();
      return Promise.all([push(readLocal()), window.UAVUserData ? window.UAVUserData.syncAll() : null]);
    },
    onLogin: function (cb) { loginHooks.push(cb); if (uid() && st.profile) { try { cb(uid()); } catch (e) { console.error(e); } } },

    // personal data (docs/MULTIUSER-PLAN.md §14): own rows only, the database enforces it
    userRows: function (table) {
      need();
      if (!DATA_TABLES[table]) return Promise.reject(new Error("unknown table " + table));
      return st.client.from(table).select(DATA_TABLES[table]).eq("user_id", uid()).then(check).then(function (r) { return r || []; });
    },
    upsertRows: function (table, rows) {
      need();
      if (!DATA_TABLES[table]) return Promise.reject(new Error("unknown table " + table));
      var me = uid();
      return st.client.from(table).upsert(rows.map(function (r) { return Object.assign({ user_id: me }, r); }))
        .select("module_id,anchor,updated_at").then(check);
    },
    // expected: delete only that version (a note edited on another device meanwhile stays and comes back at the next pull)
    deleteRow: function (table, moduleId, anchor, expected) {
      need();
      if (!DATA_TABLES[table]) return Promise.reject(new Error("unknown table " + table));
      var q = st.client.from(table).delete().eq("user_id", uid()).eq("module_id", moduleId).eq("anchor", anchor || "");
      if (expected) q = q.eq("updated_at", expected);
      return q.then(check);
    },
    // saves over the version this browser last saw, or returns {conflict: true, body, label, updated_at} (0007 save_note)
    saveNote: function (moduleId, anchor, label, body, expected) {
      need();
      return st.client.rpc("save_note", { p_module: moduleId, p_anchor: anchor || "", p_label: label || "", p_body: body, p_expected: expected || null }).then(check);
    },
    getDoc: function (table) {
      need();
      if (!DOC_TABLES[table]) return Promise.reject(new Error("unknown table " + table));
      return st.client.from(table).select(DOC_TABLES[table] + ",updated_at").eq("user_id", uid()).maybeSingle().then(check);
    },
    putDoc: function (table, value) {
      need();
      if (!DOC_TABLES[table]) return Promise.reject(new Error("unknown table " + table));
      var row = { user_id: uid() }; row[DOC_TABLES[table]] = value;
      return st.client.from(table).upsert(row).select("updated_at").single().then(check);
    },

    // feedback (§14): only signed-in users with a confirmed email; the database checks both and the rate limit
    sendFeedback: function (f) {
      need();
      if (!uid()) return Promise.reject(new Error("log in with a confirmed account"));
      return st.client.rpc("send_feedback", { p_module: f.module || "", p_section: f.section || "", p_anchor: f.anchor || "",
        p_kind: f.kind, p_body: f.body, p_lang: f.lang || "" }).then(check);
    },
    myFeedback: function () {
      need();
      return st.client.from("feedback").select("id,module_id,section_key,anchor,kind,body,status,created_at,updated_at")
        .eq("user_id", uid()).order("created_at", { ascending: false }).limit(100).then(check);
    },
    staffFeedback: function (before, limit) { need(); return st.client.rpc("feedback_for_staff", { p_before: before || null, p_limit: limit || 500 }).then(check); },
    setFeedback: function (id, status, note) { need(); return st.client.rpc("feedback_set", { p_id: id, p_status: status, p_staff_note: note }).then(check); },
    deleteFeedback: function (id) { need(); return st.client.rpc("feedback_delete", { p_id: id }).then(check); },

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
    },

    // exams (docs/MULTIUSER-PLAN.md §11): questions and answers live only in the database
    listExams: function () {
      need();
      return Promise.all([
        st.client.from("exams").select("id,title,module_id,pass_pct,questions_per_attempt,time_limit_min,attempts_allowed,show_review,opens_at,closes_at,published").order("title").then(check),
        st.client.from("exam_results").select("id,exam_id,started_at,deadline,submitted_at,correct,total,score_pct,passed").eq("user_id", uid()).then(check)
      ]).then(function (r) {
        return r[0].map(function (e) {
          var mine = r[1].filter(function (a) { return a.exam_id === e.id; });
          return Object.assign({}, e, { attempts: mine });
        });
      });
    },
    startExam: function (examId) { need(); return st.client.rpc("exam_start", { p_exam: examId }).then(check); },
    submitExam: function (attemptId, answers) { need(); return st.client.rpc("exam_submit", { p_attempt: attemptId, p_answers: answers }).then(check); },
    examResults: function () {
      need();
      return st.client.from("exam_results").select("id,exam_id,title,user_id,username,email,started_at,submitted_at,correct,total,score_pct,passed").order("started_at", { ascending: false }).then(check);
    },
    staffExams: function () {
      need();
      return st.client.from("exams").select("id,title,pass_pct,questions_per_attempt,time_limit_min,attempts_allowed,show_review,opens_at,closes_at,published,created_at").order("created_at", { ascending: false }).then(check);
    },
    // bank: {title, pass_pct?, questions_per_attempt?, time_limit_min?, attempts_allowed?, show_review?,
    //        questions: [{q, options: [..], answer, explain?}]} — a course quiz file also fits
    createExam: function (bank) {
      need();
      var qs = (bank && bank.questions) || [];
      if (!bank.title || qs.length < 1) return Promise.reject(new Error(T("Нужны название и хотя бы один вопрос.")));
      var row = { title: String(bank.title).slice(0, 200), published: false };
      ["pass_pct", "questions_per_attempt", "time_limit_min", "attempts_allowed", "show_review", "module_id"].forEach(function (k) { if (bank[k] != null) row[k] = bank[k]; });
      if (row.questions_per_attempt == null) row.questions_per_attempt = Math.min(10, qs.length);
      return st.client.from("exams").insert(row).select("id").single().then(check).then(function (e) {
        var items = qs.map(function (q) { return { exam_id: e.id, q: q.q, options: q.options, answer: q.answer, explain: q.explain || "" }; });
        return st.client.from("exam_questions").insert(items).then(check).then(function () { return e.id; })
          .catch(function (err) {   // keep the database clean if the bank was rejected
            return st.client.from("exams").delete().eq("id", e.id).then(function () { throw err; });
          });
      });
    },
    // cohorts (docs/MULTIUSER-PLAN.md §12): staff see every group, a student only their own
    listCohorts: function () {
      need();
      return Promise.all([
        st.client.from("cohorts").select("id,name,created_at").order("name").then(check),
        st.client.from("cohort_members").select("cohort_id,user_id").then(check)
      ]).then(function (r) { return { cohorts: r[0] || [], members: r[1] || [] }; });
    },
    createCohort: function (name) {
      need();
      name = String(name || "").trim();
      if (name.length < 2 || name.length > 100) return Promise.reject(new Error("cohorts_name_check"));
      return st.client.from("cohorts").insert({ name: name }).select("id").single().then(check).then(function (c) { return c.id; });
    },
    deleteCohort: function (id) { need(); return st.client.from("cohorts").delete().eq("id", id).then(check); },
    addToCohort: function (cohortId, userId) { need(); return st.client.from("cohort_members").insert({ cohort_id: cohortId, user_id: userId }).then(check); },
    removeFromCohort: function (cohortId, userId) {
      need(); return st.client.from("cohort_members").delete().eq("cohort_id", cohortId).eq("user_id", userId).then(check);
    },
    setExamPublished: function (id, on) { need(); return st.client.from("exams").update({ published: !!on }).eq("id", id).then(check); },
    deleteExam: function (id) { need(); return st.client.from("exams").delete().eq("id", id).then(check); }
  };

  window.UAVAccount = api;
  // accounts off: still show where the sign-in will be, so the account page (preview) is reachable
  if (!CFG.enabled && typeof document !== "undefined") {
    var addEntry = function () {
      var nav = document.querySelector(".site-header .gc-nav");
      if (!nav || document.getElementById("nav-account")) return;
      var a = document.createElement("a"); a.id = "nav-account"; a.href = base() + "pages/account.html"; a.textContent = T("Войти");
      if (/\/pages\/account\.html$/.test(location.pathname)) a.setAttribute("aria-current", "page");
      nav.appendChild(a);
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", addEntry); else addEntry();
  }
  if (CFG.enabled) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
  }
  if (typeof module !== "undefined" && module.exports) module.exports = { merge: merge };
})();
