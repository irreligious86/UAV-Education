/*
 * Offline support: registers the generated service worker (sw.js at site root) and shows a one-line
 * status in the footer. Progress stays in localStorage, so the whole course works without network
 * once the first visit has finished precaching.
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";
  if (!("serviceWorker" in navigator)) return;
  var root = document.body.getAttribute("data-root") || document.body.getAttribute("data-base") || "";   // sw.js is shared by all languages
  function note(text) {
    var el = document.querySelector("[data-offline-status]");
    if (!el) {
      el = document.createElement("p"); el.className = "gc-muted offline-status"; el.setAttribute("data-offline-status", "");
      var footer = document.querySelector("footer") || document.querySelector("main");
      if (footer) footer.appendChild(el);
    }
    el.textContent = text;
  }
  window.addEventListener("load", function () {
    navigator.serviceWorker.register(root + "sw.js?lang=" + (document.documentElement.getAttribute("data-lang") || "ru")).then(function (reg) {
      if (reg.active && !reg.installing) note(T("Офлайн-режим готов: курс открывается без сети."));
    }).catch(function () { /* file:// or unsupported: nothing to do */ });
    navigator.serviceWorker.addEventListener("message", function (ev) {
      if (ev.data && ev.data.type === "offline-ready") note(T("Офлайн-режим готов: ") + ev.data.files + T(" файлов сохранено для работы без сети."));
    });
  });
  window.addEventListener("offline", function () { note(T("Нет сети — работаем из кэша.")); });
  window.addEventListener("online", function () { note(T("Сеть восстановлена.")); });
})();
