/*
 * Offline support: registers the generated service worker (sw.js at site root) and shows a one-line
 * status in the footer. Progress stays in localStorage, so the whole course works without network
 * once the first visit has finished precaching.
 */
(function () {
  "use strict";
  if (!("serviceWorker" in navigator)) return;
  var base = document.body.getAttribute("data-base") || "";
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
    navigator.serviceWorker.register(base + "sw.js").then(function (reg) {
      if (reg.active && !reg.installing) note("Офлайн-режим готов: курс открывается без сети.");
    }).catch(function () { /* file:// or unsupported: nothing to do */ });
    navigator.serviceWorker.addEventListener("message", function (ev) {
      if (ev.data && ev.data.type === "offline-ready") note("Офлайн-режим готов: " + ev.data.files + " файлов сохранено для работы без сети.");
    });
  });
  window.addEventListener("offline", function () { note("Нет сети — работаем из кэша."); });
  window.addEventListener("online", function () { note("Сеть восстановлена."); });
})();
