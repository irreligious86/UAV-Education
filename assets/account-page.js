/* pages/account.html: register, log in, reset password, profile. Logic lives in account.js (UAVAccount). */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";

  var ROLE = { student: T("студент"), admin: T("админ"), superadmin: T("суперадмин") };
  var SYNC = { idle: "—", loading: T("загрузка"), saving: T("сохраняю"), saved: T("сохранено"), offline: T("нет связи, сохранится позже") };

  function $(sel) { return document.querySelector(sel); }
  function show(name) {
    document.querySelectorAll("[data-acc]").forEach(function (el) { el.hidden = el.getAttribute("data-acc") !== name; });
  }
  function msg(text, state) {
    var el = $("[data-acc-msg]");
    el.textContent = text || "";
    el.setAttribute("data-state", state || "");
  }
  function busy(form, on) { form.querySelectorAll("gc-button, input").forEach(function (b) { b.toggleAttribute("disabled", on); }); }

  // gc-button is not form-associated: submit by hand, and on Enter in any field
  function wireSubmit(form, handler) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!form.reportValidity()) return;
      var data = Object.fromEntries(new FormData(form).entries());
      busy(form, true); msg("");
      Promise.resolve().then(function () { return handler(data); })
        .then(function (text) { if (text) msg(text, "ok"); })
        .catch(function (err) { msg(window.UAVAccount.humanError(err), "critical"); })
        .then(function () { busy(form, false); });
    });
    form.querySelectorAll("gc-button[type=submit]").forEach(function (b) { b.addEventListener("click", function () { form.requestSubmit(); }); });
    form.addEventListener("keydown", function (e) { if (e.key === "Enter" && e.target.tagName === "INPUT") { e.preventDefault(); form.requestSubmit(); } });
  }

  // the student's own groups (RLS returns only those); fetched once per signed-in user
  var groupsFor = null;
  function loadGroups(s) {
    var uidNow = s.user && s.user.id;
    if (!uidNow || groupsFor === uidNow || !window.UAVAccount.listCohorts) return;
    groupsFor = uidNow;
    window.UAVAccount.listCohorts().then(function (r) {
      var mine = r.members.filter(function (m) { return m.user_id === uidNow; }).map(function (m) { return m.cohort_id; });
      var names = r.cohorts.filter(function (c) { return mine.indexOf(c.id) >= 0; }).map(function (c) { return c.name; });
      $("[data-acc-group-names]").textContent = names.join(", ");
      $("[data-acc-groups]").hidden = names.length === 0;
    }).catch(function () { groupsFor = null; });
  }

  function render(s) {
    if (!s.enabled) return;
    if (s.recovery && s.user) return show("recovery");
    if (!s.user) return show("guest");
    show("user");
    var p = s.profile || {};
    $("[data-acc-username]").textContent = p.username || "…";
    $("[data-acc-email]").textContent = p.email || (s.user && s.user.email) || "";
    var role = $("[data-acc-role]");
    role.textContent = ROLE[p.role] || "";
    role.setAttribute("data-state", p.role === "superadmin" ? "critical" : p.role === "admin" ? "caution" : "ok");
    var sync = $("[data-acc-sync]");
    sync.textContent = SYNC[s.sync] || s.sync;
    sync.setAttribute("data-state", s.sync === "saved" ? "ok" : s.sync === "offline" ? "caution" : "");
    $("[data-acc-admin]").hidden = !s.isStaff;
    loadGroups(s);
    var rename = document.querySelector('[data-form="rename"] input');
    if (rename && !rename.value && p.username) rename.value = p.username;
  }

  function wireTabs() {
    document.querySelectorAll("[data-tab]").forEach(function (t) {
      t.addEventListener("click", function () {
        var name = t.getAttribute("data-tab");
        document.querySelectorAll("[data-tab]").forEach(function (x) { x.setAttribute("data-state", x === t ? "ok" : ""); });
        document.querySelectorAll(".acc-forms [data-form]").forEach(function (f) { f.hidden = f.getAttribute("data-form") !== name; });
        msg("");
      });
    });
  }

  // ------------------------------------------------------------------ settings (this browser; synced once accounts are on)
  var SETTINGS = "uav-student:settings";
  function readSettings() { try { var v = JSON.parse(localStorage.getItem(SETTINGS) || "{}"); return v && typeof v === "object" ? v : {}; } catch (e) { return {}; } }
  function wireSettings() {
    var cur = readSettings();
    var note = $("[data-setting-saved]");
    document.querySelectorAll("[data-setting]").forEach(function (el) {
      var key = el.getAttribute("data-setting");
      if (el.type === "checkbox") el.checked = !!cur[key]; else if (cur[key] != null) el.value = cur[key];
      el.addEventListener("change", function () {
        var next = readSettings();
        next[key] = el.type === "checkbox" ? el.checked : el.value;
        try { localStorage.setItem(SETTINGS, JSON.stringify(next)); if (note) note.textContent = T("Сохранено в этом браузере."); }
        catch (e) { if (note) note.textContent = T("Браузер не даёт сохранить настройки (приватный режим?)."); }
      });
    });
  }

  // ------------------------------------------------------------------ preview: the server is not connected yet
  function preview() {
    show("guest");
    $("[data-acc-preview]").hidden = false;
    wireTabs();
    document.querySelectorAll(".acc-forms [data-form]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        msg(T("Аккаунты ещё не подключены к серверу. Как только заработают, этой же формой можно будет войти."), "caution");
      });
      form.querySelectorAll("gc-button[type=submit]").forEach(function (b) { b.addEventListener("click", function () { form.requestSubmit(); }); });
    });
    var demoBtn = $("[data-acc-demo]"), demo = false;
    demoBtn.addEventListener("click", function () {
      demo = !demo;
      if (demo) {
        show("user");
        $("[data-acc-demo-note]").hidden = false;
        $("[data-acc-username]").textContent = "pilot_demo";
        $("[data-acc-email]").textContent = "pilot@example.com";
        var role = $("[data-acc-role]"); role.textContent = ROLE.student; role.setAttribute("data-state", "ok");
        var sync = $("[data-acc-sync]"); sync.textContent = SYNC.saved; sync.setAttribute("data-state", "ok");
        var rn = document.querySelector('[data-form="rename"] input'); if (rn) rn.value = "pilot_demo";
        demoBtn.textContent = T("Вернуться к форме входа");
      } else {
        show("guest");
        demoBtn.textContent = T("Показать пример кабинета");
      }
      msg("");
    });
    document.querySelectorAll("[data-acc-sync-now], [data-acc-logout]").forEach(function (b) {
      b.addEventListener("click", function () { msg(T("Это пример: в предпросмотре кнопка ничего не делает."), "caution"); });
    });
    var rename = $('[data-form="rename"]');
    if (rename) rename.addEventListener("submit", function (e) { e.preventDefault(); msg(T("Это пример: в предпросмотре имя не меняется."), "caution"); });
  }

  function start() {
    var A = window.UAVAccount;
    wireSettings();
    if (!A || !A.enabled) return preview();
    show("loading");
    wireTabs();
    wireSubmit($('[data-form="login"]'), function (d) { return A.signIn(d.email, d.password).then(function () { return ""; }); });
    wireSubmit($('[data-form="register"]'), function (d) {
      return A.signUp(d.email, d.username, d.password).then(function (r) {
        return r.needsConfirmation ? T("Готово. Открой письмо и подтверди почту, потом войди.") : T("Аккаунт создан.");
      });
    });
    wireSubmit($('[data-form="forgot"]'), function (d) {
      return A.resetPassword(d.email).then(function () { return T("Если такая почта есть, ссылка для смены пароля уже в пути."); });
    });
    wireSubmit($('[data-form="newpass"]'), function (d) { return A.updatePassword(d.password).then(function () { return T("Пароль обновлён."); }); });
    wireSubmit($('[data-form="rename"]'), function (d) { return A.rename(d.username).then(function () { return T("Имя сохранено."); }); });
    var armed = false;   // second click forces logout when progress is not synced
    $("[data-acc-logout]").addEventListener("click", function () {
      A.signOut(armed).then(function () { armed = false; msg(T("Вышел. Копия прогресса в этом браузере стёрта."), "ok"); })
        .catch(function (e) { if (e.unsynced) { armed = true; msg(e.message + T(" Нажми «Выйти» ещё раз, чтобы выйти всё равно."), "critical"); } else msg(A.humanError(e), "critical"); });
    });
    $("[data-acc-sync-now]").addEventListener("click", function () { A.syncNow(); });
    // language of the account: saved in the profile, then the page moves to that language
    var langSel = $("[data-acc-lang]");
    if (langSel && window.UAVI18N) langSel.addEventListener("change", function () { window.UAVI18N.switchTo(langSel.value); });
    A.onChange(render);
    A.init().then(render);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
