/*
 * Bookmarks, notes ("Конспект") and feedback to the developer on lesson pages, and the lists of bookmarks and notes
 * on the progress and account pages (docs/MULTIUSER-PLAN.md §14). Data: assets/user-data.js (window.UAVUserData).
 *
 *   lesson page (<article data-module-page>): a bar under the tags (bookmark the lesson, open the notes panel,
 *     report to the developer) and three small buttons in every section heading (bookmark, note, report).
 *     Anchors are the heading ids from assets/history.js (stable ids from the build, e.g. "teoriya"), '' = the
 *     whole lesson; rows under the old positional anchors ("sec-N") are migrated here (UAVUserData.migrateAnchors).
 *   [data-nb-list="notes" | "bookmarks"]: list with search and section filter; data-nb-compact="N" shows the
 *     newest N without tools (account page). Module titles and sections come from <script id="nb-modules">.
 *   Feedback is sent only by a signed-in user (the database also requires a confirmed email); guests see why
 *   and a link to the account page.
 * Plain text only: notes and feedback are never rendered as HTML.
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";
  var UD = window.UAVUserData;
  if (!UD) return;
  var MAX = UD.NOTE_MAX, FB_MIN = 10, FB_MAX = 4000;

  function base() { return document.body.getAttribute("data-base") || ""; }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) e.setAttribute(k, attrs[k]); });
    if (text != null) e.textContent = text;
    return e;
  }
  function btn(cls, label, text) { var b = el("button", { type: "button", class: cls, "aria-label": label, title: label }, text); return b; }
  function when(ts) { return ts ? new Date(ts).toLocaleString(document.documentElement.lang || undefined, { dateStyle: "short", timeStyle: "short" }) : ""; }
  function cssq(s) { return window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/["\\]/g, "\\$&"); }
  function counter(box, ta, max) {
    var n = ta.value.length;
    box.textContent = n > max * 0.85 ? n + " / " + max : "";
    box.setAttribute("data-state", n >= max ? "critical" : n > max * 0.95 ? "caution" : "");
  }

  // ================================================================== feedback dialog (any page)
  var dlg = null, dlgOpener = null;
  var KINDS = [["error", T("Ошибка")], ["unclear", T("Непонятно")], ["idea", T("Пожелание")], ["other", T("Другое")]];

  function feedbackDialog(ctx) {
    var A = window.UAVAccount, s = A && A.state ? A.state() : { enabled: false };
    dlgOpener = document.activeElement;
    if (dlg) dlg.remove();
    dlg = el("dialog", { class: "nb-dialog gc-panel", "aria-labelledby": "nb-fb-title" });
    var head = el("div", { class: "nb-dialog__head" });
    head.append(el("h2", { id: "nb-fb-title", class: "acc-h" }, T("Сообщить разработчику")));
    var x = btn("gc-tag nb-close", T("Закрыть"), "×"); x.addEventListener("click", function () { dlg.close(); });
    head.append(x);
    dlg.append(head);
    dlg.append(el("p", { class: "gc-muted" }, ctx.heading ? T("Урок «{t}» · раздел «{h}»", { t: ctx.title, h: ctx.heading }) : T("Урок «{t}»", { t: ctx.title })));
    if (!s.enabled || !s.user) {
      dlg.append(el("p", null, T("Отправлять сообщения могут только вошедшие пользователи с подтверждённой почтой: так разработчик может разобраться в вопросе, а сообщения не тонут в спаме.")));
      if (!s.enabled) dlg.append(el("p", { class: "gc-muted" }, T("Аккаунты ещё не подключены к серверу — как только заработают, кнопка начнёт отправлять.")));
      var row = el("div", { class: "progress-actions" });
      row.append(el("a", { class: "gc-tag", "data-state": "ok", href: base() + "pages/account.html" }, T("Войти или зарегистрироваться")));
      var c = el("button", { type: "button", class: "gc-tag" }, T("Закрыть")); c.addEventListener("click", function () { dlg.close(); });
      row.append(c); dlg.append(row);
    } else {
      var f = el("form", { class: "acc-form nb-fb-form", method: "dialog", novalidate: "" });   // own messages (spaces do not count)
      var fs = el("fieldset", { class: "nb-kinds" }); fs.append(el("legend", null, T("Что случилось")));
      KINDS.forEach(function (k, i) {
        var l = el("label", { class: "acc-check" }), r = el("input", { type: "radio", name: "kind", value: k[0] });
        if (i === 0) r.checked = true;
        l.append(r, document.createTextNode(" " + k[1])); fs.append(l);
      });
      var tl = el("label"); tl.append(el("span", null, T("Текст")));
      var ta = el("textarea", { name: "body", rows: "6", minlength: String(FB_MIN), maxlength: String(FB_MAX), required: "" });
      var cnt = el("small", { class: "gc-muted nb-counter", "aria-live": "polite" });
      ta.addEventListener("input", function () { counter(cnt, ta, FB_MAX); });
      tl.append(ta, cnt);
      var msg = el("p", { class: "acc-msg", "aria-live": "polite" });
      var row2 = el("div", { class: "progress-actions" });
      var send = el("button", { type: "submit", class: "gc-tag", "data-state": "ok" }, T("Отправить"));
      var cancel = el("button", { type: "button", class: "gc-tag" }, T("Отмена")); cancel.addEventListener("click", function () { dlg.close(); });
      row2.append(send, cancel);
      f.append(fs, tl, el("p", { class: "gc-muted" }, T("Сообщение увидит администрация курса вместе с твоим именем пользователя. Статус — в аккаунте.")), row2, msg);
      f.addEventListener("submit", function (e) {
        e.preventDefault();
        var body = ta.value;
        if (body.trim().length < FB_MIN) { msg.textContent = T("Напиши хотя бы {n} символов.", { n: FB_MIN }); msg.setAttribute("data-state", "critical"); ta.focus(); return; }
        send.disabled = true; msg.textContent = T("Отправляю…"); msg.setAttribute("data-state", "");
        A.sendFeedback({ module: ctx.module, section: ctx.section, anchor: ctx.anchor, kind: f.querySelector("input[name=kind]:checked").value,
                         body: body, lang: document.documentElement.getAttribute("data-lang") || "" })
          .then(function () {
            f.replaceWith(el("p", { class: "acc-msg", "data-state": "ok", role: "status" }, T("Спасибо! Сообщение отправлено — его статус виден в аккаунте.")));
            setTimeout(function () { if (dlg && dlg.open) dlg.close(); }, 2500);
          })
          .catch(function (err) { send.disabled = false; msg.textContent = A.humanError(err); msg.setAttribute("data-state", "critical"); });
      });
      dlg.append(f);
    }
    dlg.addEventListener("close", function () { var o = dlgOpener; dlg.remove(); dlg = null; if (o && o.focus) o.focus(); });
    document.body.append(dlg);
    dlg.showModal();      // modal: the rest of the page is inert (focus stays inside), Escape closes
    var first = dlg.querySelector("textarea") || dlg.querySelector("a, button");
    if (first) first.focus();
  }

  // ================================================================== lesson page
  function lessonPage(art) {
    var mid = art.getAttribute("data-module-page");
    var h1 = art.querySelector("h1");
    var title = h1 ? h1.textContent.trim() : document.title;
    var section = document.body.getAttribute("data-section") || "";
    var path = location.pathname.split("/").filter(Boolean).slice(-2).join("/");
    var heads = window.UAVHistory && window.UAVHistory.headings ? window.UAVHistory.headings(art) : [];
    var textOf = function (h) { return window.UAVHistory ? window.UAVHistory.headingText(h) : h.textContent.trim(); };
    // notes and bookmarks saved under the old positional anchors ("sec-N") move to the heading ids, once
    if (window.UAVHistory && window.UAVHistory.legacyAnchor && UD.migrateAnchors) {
      UD.migrateAnchors(mid, function (a, label) { return window.UAVHistory.legacyAnchor(heads, a, label); });
    }
    var meta = function (anchor) {
      var h = anchor ? document.getElementById(anchor) : null;
      return { label: h ? textOf(h).slice(0, 160) : "", title: title, path: path };
    };

    // ---- bar under the tags
    var bar = el("div", { class: "nb-bar", role: "group", "aria-label": T("Закладки и конспект") });
    var markBtn = el("button", { type: "button", class: "gc-tag nb-mark", "aria-pressed": "false" });
    var openBtn = el("button", { type: "button", class: "gc-tag", "aria-expanded": "false", "aria-controls": "nb-panel" });
    var fbBtn = el("button", { type: "button", class: "gc-tag" }, "⚑ " + T("Сообщить разработчику"));
    var barMsg = el("span", { class: "acc-msg nb-bar__msg", "aria-live": "polite" });
    bar.append(markBtn, openBtn, fbBtn, barMsg);
    var tags = art.querySelector(".module-tags");
    (tags || h1).after(bar);
    markBtn.addEventListener("click", function () { toggleMark(""); });
    openBtn.addEventListener("click", function () { panelOpen() ? closePanel() : openPanel("", openBtn); });
    fbBtn.addEventListener("click", function () { feedbackDialog({ module: mid, section: section, anchor: "", title: title, heading: "" }); });

    // ---- a bookmark button in every section heading. Notes and feedback live once per lesson, in the bar above
    // (owner's request 2026-11-27); a section that already has a note keeps a ✎ marker that opens it.
    heads.forEach(function (h) {
      var name = textOf(h);
      var tools = el("span", { class: "nb-tools" });
      var b1 = btn("nb-tool", T("Закладка на раздел «{h}»", { h: name }), "☆"); b1.setAttribute("aria-pressed", "false"); b1.setAttribute("data-nb-mark", h.id);
      var b2 = btn("nb-tool", T("Заметка к разделу «{h}»", { h: name }), "✎"); b2.setAttribute("data-nb-note", h.id); b2.hidden = true;
      b1.addEventListener("click", function () { toggleMark(h.id); });
      b2.addEventListener("click", function () { openPanel(h.id, b2); });
      tools.append(b1, b2);
      h.append(tools);
    });

    function toggleMark(anchor) {
      var ok = UD.bookmarks.get(mid, anchor) ? UD.bookmarks.remove(mid, anchor) : UD.bookmarks.set(mid, anchor, meta(anchor));
      barMsg.textContent = ok ? "" : T("Не удалось сохранить закладку: браузер не даёт хранить данные или закладок слишком много.");
      barMsg.setAttribute("data-state", ok ? "" : "critical");
      paint();
    }

    function paint() {
      var on = !!UD.bookmarks.get(mid, "");
      markBtn.setAttribute("aria-pressed", String(on));
      markBtn.textContent = on ? "★ " + T("В закладках") : "☆ " + T("В закладки");
      var n = UD.notes.list().filter(function (r) { return r.m === mid; }).length;
      openBtn.textContent = "✎ " + T("Конспект") + (n ? " · " + n : "");
      art.querySelectorAll("[data-nb-mark]").forEach(function (b) {
        var m = !!UD.bookmarks.get(mid, b.getAttribute("data-nb-mark"));
        b.setAttribute("aria-pressed", String(m)); b.textContent = m ? "★" : "☆";
      });
      art.querySelectorAll("[data-nb-note]").forEach(function (b) {
        var has = !!UD.notes.get(mid, b.getAttribute("data-nb-note"));
        b.toggleAttribute("data-has", has); b.hidden = !has;
      });
    }

    // ---- notes panel (not modal: the lesson stays readable next to it)
    var panel = null, opener = null, statusEl = null, timers = {};
    function panelOpen() { return panel && !panel.hidden; }
    function status(text, state) { if (statusEl) { statusEl.textContent = text; statusEl.setAttribute("data-state", state || ""); } }
    function savedText() {
      if (UD.signedIn()) return UD.pending() ? T("Сохранено в браузере, отправляется в аккаунт…") : T("Сохранено в аккаунте.");
      return T("Сохранено в этом браузере.");
    }

    function noteBlock(anchor) {
      var r = UD.notes.get(mid, anchor), m = meta(anchor);
      var box = el("div", { class: "nb-note", "data-anchor": anchor });
      var head = el("div", { class: "nb-note__head" });
      var id = "nb-ta-" + (anchor || "lesson");
      var lab = el("label", { for: id, class: "gc-label" }, anchor ? (m.label || (r && r.label) || anchor) : T("Весь урок"));
      head.append(lab);
      if (anchor && document.getElementById(anchor)) {   // copies ("…-copy-N") have no heading of their own
        var go = el("a", { href: "#" + encodeURIComponent(anchor), class: "gc-muted" }, T("к разделу")); head.append(go);
      }
      var del = btn("gc-tag nb-del", anchor ? T("Удалить заметку к разделу «{h}»", { h: m.label || anchor }) : T("Удалить заметку ко всему уроку"), T("удалить"));
      head.append(del);
      var ta = el("textarea", { id: id, rows: anchor ? "4" : "6", maxlength: String(MAX), spellcheck: "true" });
      ta.value = r ? r.body : "";
      var cnt = el("small", { class: "gc-muted nb-counter", "aria-live": "polite" });
      counter(cnt, ta, MAX);
      ta.addEventListener("input", function () {
        counter(cnt, ta, MAX);
        status(T("Не сохранено…"), "caution");
        clearTimeout(timers[anchor]);
        timers[anchor] = setTimeout(function () { save(anchor, ta); }, 600);
      });
      ta.addEventListener("blur", function () { if (timers[anchor]) { clearTimeout(timers[anchor]); save(anchor, ta); } });
      del.addEventListener("click", function () {
        if (ta.value.trim() && !window.confirm(T("Удалить эту заметку?"))) return;
        clearTimeout(timers[anchor]); delete timers[anchor];
        UD.notes.remove(mid, anchor); ta.value = ""; counter(cnt, ta, MAX);
        if (anchor) box.remove();
        status(T("Заметка удалена."), ""); paint();
      });
      box.append(head, ta, cnt);
      return box;
    }

    function save(anchor, ta) {
      delete timers[anchor];
      var text = ta.value;
      var ok = text.trim() ? UD.notes.set(mid, anchor, Object.assign(meta(anchor), { body: text })) : UD.notes.remove(mid, anchor);
      if (ok) status(savedText(), "ok");
      else status(T("Не сохранено: браузер не даёт хранить данные (приватный режим?) или заметок больше 2000."), "critical");
      paint();
    }
    function flushAll() {
      if (!panel) return;
      Object.keys(timers).forEach(function (a) { clearTimeout(timers[a]); var ta = panel.querySelector('.nb-note[data-anchor="' + cssq(a) + '"] textarea'); if (ta) save(a, ta); });
    }

    function build() {
      panel = el("aside", { id: "nb-panel", class: "nb-panel gc-panel", "aria-label": T("Конспект"), hidden: "" });
      var head = el("div", { class: "nb-panel__head" });
      head.append(el("h2", { class: "acc-h" }, T("Конспект")));
      var x = btn("gc-tag nb-close", T("Закрыть конспект"), "×"); x.addEventListener("click", closePanel);
      head.append(x);
      panel.append(head, el("p", { class: "gc-muted nb-panel__lesson" }, title));
      var list = el("div", { class: "nb-notes" });
      panel.append(list);
      statusEl = el("p", { class: "acc-msg nb-status", "aria-live": "polite" });
      var foot = el("div", { class: "nb-panel__foot" });
      foot.append(statusEl, el("a", { href: base() + "pages/progress.html#notes", class: "gc-muted" }, T("Все конспекты")));
      panel.append(el("p", { class: "gc-muted nb-hint" }, T("Только текст. Заметка к разделу — кнопка ✎ у заголовка.")), foot);
      panel.addEventListener("keydown", function (e) { if (e.key === "Escape") { e.preventDefault(); closePanel(); } });
      document.body.append(panel);
    }
    function fill(focusAnchor) {
      var list = panel.querySelector(".nb-notes");
      list.replaceChildren(noteBlock(""));
      var anchors = UD.notes.list().filter(function (r) { return r.m === mid && r.a; }).map(function (r) { return r.a; });
      if (focusAnchor && anchors.indexOf(focusAnchor) < 0) anchors.push(focusAnchor);
      var order = heads.map(function (h) { return h.id; });
      anchors.sort(function (a, b) { return order.indexOf(a) - order.indexOf(b); });
      anchors.forEach(function (a) { list.append(noteBlock(a)); });
      status(UD.notes.list().some(function (r) { return r.m === mid; }) ? savedText() : "", "");
    }
    function openPanel(anchor, from) {
      if (!panel) build();
      flushAll();
      opener = from || null;
      fill(anchor);
      panel.hidden = false;
      document.body.classList.add("nb-panel-open");
      openBtn.setAttribute("aria-expanded", "true");
      var ta = panel.querySelector('.nb-note[data-anchor="' + cssq(anchor) + '"] textarea');
      if (ta && from) { ta.focus(); ta.scrollIntoView({ block: "nearest" }); }
    }
    function closePanel() {
      if (!panel) return;
      flushAll();
      panel.hidden = true;
      document.body.classList.remove("nb-panel-open");
      openBtn.setAttribute("aria-expanded", "false");
      // drop empty section blocks next time; return focus where the user was
      if (opener && opener.focus) opener.focus(); else openBtn.focus();
      opener = null;
    }
    window.addEventListener("pagehide", flushAll);
    document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") flushAll(); });
    document.addEventListener("uav-userdata", function (e) {
      var w = e.detail && e.detail.what;
      if (w === "pulled") {
        paint();
        // refresh the panel only when nobody is typing in it
        if (panelOpen() && !Object.keys(timers).length && !panel.contains(document.activeElement)) fill("");
      }
      if ((w === "synced" || w === "sync-error") && panelOpen() && !Object.keys(timers).length) {
        status(w === "synced" ? savedText() : T("Сохранено в браузере; на сервер не ушло: ") + UD.error(), w === "synced" ? "ok" : "caution");
      }
    });
    paint();
    var s = UD.readSettings();
    if (s.notesPanel && window.matchMedia("(min-width: 1100px)").matches) openPanel("", null);
  }

  // ================================================================== lists (progress page, account page)
  function moduleMap() {
    var node = document.getElementById("nb-modules");
    if (!node) return {};
    try { return JSON.parse(node.textContent) || {}; } catch (e) { return {}; }
  }

  function renderList(box) {
    var kind = box.getAttribute("data-nb-list");
    var store = kind === "notes" ? UD.notes : UD.bookmarks;
    var compact = parseInt(box.getAttribute("data-nb-compact") || "0", 10);
    var map = moduleMap();
    var info = function (r) { return map[r.m] || { t: r.title || r.m, u: r.path || "m/" + r.m + ".html", s: "", st: "" }; };
    var tools = null, q = null, sel = null, list = el("ul", { class: "nb-list" });
    box.replaceChildren();
    if (!compact) {
      tools = el("div", { class: "progress-actions nb-list__tools" });
      q = el("input", { type: "search", class: "adm-filter", placeholder: kind === "notes" ? T("поиск по тексту и урокам") : T("поиск по урокам"),
                        "aria-label": kind === "notes" ? T("Поиск по конспектам") : T("Поиск по закладкам") });
      sel = el("select", { class: "adm-filter adm-cohort", "aria-label": T("Раздел курса") });
      tools.append(q, sel);
      if (kind === "notes") {
        var exp = el("button", { type: "button", class: "gc-tag" }, T("Скачать все (.md)"));
        exp.addEventListener("click", function () {
          var a = el("a", { download: "uav-notes-" + new Date().toISOString().slice(0, 10) + ".md" });
          a.href = URL.createObjectURL(new Blob([UD.exportNotes(function (m) { return (map[m] || {}).t; })], { type: "text/markdown;charset=utf-8" }));
          document.body.append(a); a.click(); a.remove();
          setTimeout(function () { URL.revokeObjectURL(a.href); }, 10000);
        });
        tools.append(exp);
      }
      q.addEventListener("input", draw); sel.addEventListener("change", draw);
      box.append(tools);
    }
    box.append(list);

    function draw() {
      var rows = store.list();
      if (sel) {
        var cur = sel.value, secs = {};
        rows.forEach(function (r) { var i = info(r); secs[i.s || "-"] = i.st || T("Другое"); });
        sel.replaceChildren(el("option", { value: "" }, T("все разделы")));
        Object.keys(secs).sort(function (a, b) { return secs[a].localeCompare(secs[b]); }).forEach(function (k) { sel.append(el("option", { value: k }, secs[k])); });
        sel.value = secs[cur] ? cur : "";
      }
      var needle = q ? q.value.trim().toLowerCase() : "", s = sel ? sel.value : "";
      var shown = rows.filter(function (r) {
        var i = info(r);
        if (s && (i.s || "-") !== s) return false;
        return !needle || (i.t + " " + (r.label || "") + " " + (r.body || "")).toLowerCase().indexOf(needle) >= 0;
      });
      if (compact) shown = shown.slice(0, compact);
      list.replaceChildren();
      if (!shown.length) {
        list.append(el("li", { class: "gc-muted" }, rows.length ? T("Ничего не нашлось.") : kind === "notes"
          ? T("Конспектов пока нет: на странице урока нажми «✎ Конспект» или ✎ у заголовка раздела.")
          : T("Закладок пока нет: на странице урока нажми «☆ В закладки» или ☆ у заголовка раздела.")));
        return;
      }
      shown.forEach(function (r) { list.append(item(r, info(r))); });
    }

    function item(r, i) {
      var li = el("li", { class: "nb-item" });
      if (i.s) li.setAttribute("data-section", i.s);
      var head = el("div", { class: "nb-item__head" });
      var a = el("a", { href: base() + i.u + (r.a ? "#" + encodeURIComponent(r.a) : "") }, i.t);
      head.append(a);
      if (r.a) head.append(el("span", { class: "gc-muted" }, " · " + (r.label || r.a)));
      if (i.st && !compact) head.append(el("span", { class: "gc-tag sec-chip" }, i.st));
      head.append(el("span", { class: "gc-muted nb-when" }, when(r.at)));
      if (r.err && !compact) head.append(el("span", { class: "gc-tag", "data-state": "caution", title: r.err }, T("не на сервере")));
      li.append(head);
      if (kind === "notes") {
        var ex = el("p", { class: "nb-excerpt" }, r.body.length > 220 ? r.body.slice(0, 220) + "…" : r.body);
        li.append(ex);
      }
      if (compact) return li;
      var row = el("div", { class: "nb-item__tools" });
      var where = (r.label ? " «" + r.label + "»" : "") + " — " + i.t;
      if (kind === "notes") {
        var open = el("button", { type: "button", class: "gc-tag", "aria-expanded": "false", "aria-label": T("Открыть заметку") + where }, T("открыть"));
        open.addEventListener("click", function () {
          var ed = li.querySelector("textarea");
          if (ed) { ed.parentNode.remove(); open.setAttribute("aria-expanded", "false"); open.textContent = T("открыть"); return; }
          var wrap = el("div", { class: "nb-edit" });
          var ta = el("textarea", { rows: "8", maxlength: String(MAX), "aria-label": T("Текст заметки") + where });
          ta.value = (store.get(r.m, r.a) || r).body;
          var cnt = el("small", { class: "gc-muted nb-counter", "aria-live": "polite" }), st = el("small", { class: "gc-muted", "aria-live": "polite" });
          var t = null;
          var saveNow = function () {
            if (!t) return;
            clearTimeout(t); t = null;
            var ok = ta.value.trim() ? store.set(r.m, r.a, { body: ta.value, label: r.label, title: r.title }) : store.remove(r.m, r.a);
            st.textContent = ok ? T("Сохранено.") : T("Не сохранено.");
            li.querySelector(".nb-excerpt").textContent = ta.value.length > 220 ? ta.value.slice(0, 220) + "…" : ta.value;
          };
          ta.addEventListener("input", function () {
            counter(cnt, ta, MAX); st.textContent = T("Не сохранено…"); clearTimeout(t);
            t = setTimeout(function () { saveNow(); }, 600);
          });
          ta.addEventListener("blur", saveNow);
          window.addEventListener("pagehide", saveNow);
          document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") saveNow(); });
          wrap.append(ta, cnt, st); li.append(wrap); ta.focus();
          open.setAttribute("aria-expanded", "true"); open.textContent = T("свернуть");
        });
        row.append(open);
      }
      var del = el("button", { type: "button", class: "gc-tag", "aria-label": (kind === "notes" ? T("Удалить заметку") : T("Убрать закладку")) + where },
                   kind === "notes" ? T("удалить") : T("убрать"));
      del.addEventListener("click", function () {
        if (kind === "notes" && !window.confirm(T("Удалить эту заметку?"))) return;
        store.remove(r.m, r.a); draw();
      });
      row.append(del); li.append(row);
      return li;
    }
    draw();
    document.addEventListener("uav-userdata", function (e) {
      if (e.detail && e.detail.what === "pulled" && !box.contains(document.activeElement)) draw();
    });
  }

  function start() {
    var art = document.querySelector("article[data-module-page]");
    if (art) lessonPage(art);
    document.querySelectorAll("[data-nb-list]").forEach(renderList);
  }
  window.UAVNotes = { feedbackDialog: feedbackDialog };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
