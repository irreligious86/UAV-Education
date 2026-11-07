/*
 * Page behaviour: progress bars, "done" badges, the done toggle and checklists.
 * Everything reads/writes through window.UAVProgress (see progress-store.js).
 * Without JS the site is fully readable; only progress tracking is missing.
 */
(function () {
  "use strict";

  function ids(attr) {
    return attr ? attr.split(",").filter(Boolean) : [];
  }

  function render(done) {
    document.querySelectorAll("[data-module-id]").forEach(function (el) {
      var isDone = done.has(el.getAttribute("data-module-id"));
      el.classList.toggle("is-done", isDone);
      var badge = el.querySelector("[data-done-badge]");
      if (badge) badge.hidden = !isDone;
    });

    var page = document.querySelector("[data-module-page]");
    if (page) {
      var badge = page.querySelector(".module-tags [data-done-badge]");
      if (badge) badge.hidden = !done.has(page.getAttribute("data-module-page"));
    }

    document.querySelectorAll("[data-progress-of]").forEach(function (bar) {
      var list = ids(bar.getAttribute("data-progress-of"));
      var n = list.filter(function (id) { return done.has(id); }).length;
      var pct = list.length ? Math.round((100 * n) / list.length) : 0;
      bar.style.setProperty("--gc-value", pct + "%");
      bar.setAttribute("aria-valuenow", String(pct));
    });

    document.querySelectorAll("[data-progress-label]").forEach(function (label) {
      var list = ids(label.getAttribute("data-progress-label"));
      var n = list.filter(function (id) { return done.has(id); }).length;
      label.textContent = list.length ? "пройдено " + n + " из " + list.length : "";
    });

    document.querySelectorAll("[data-done-toggle]").forEach(function (btn) {
      var isDone = done.has(btn.getAttribute("data-done-toggle"));
      btn.textContent = isDone ? "✓ Пройден — снять отметку" : "Отметить как пройденный";
      btn.setAttribute("variant", isDone ? "primary" : "secondary");
    });
  }

  function refresh() {
    return window.UAVProgress.getDone().then(render);
  }

  function init() {
    if (!window.UAVProgress) return;

    document.querySelectorAll("[data-done-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-done-toggle");
        window.UAVProgress.getDone()
          .then(function (done) { return window.UAVProgress.setDone(id, !done.has(id)); })
          .then(refresh);
      });
    });

    var boxes = document.querySelectorAll("input[data-check-id]");
    if (boxes.length) {
      var prefix = boxes[0].getAttribute("data-check-id").split(":")[0] + ":";
      window.UAVProgress.getChecks(prefix).then(function (checked) {
        boxes.forEach(function (box) {
          box.checked = checked.has(box.getAttribute("data-check-id"));
          box.addEventListener("change", function () {
            window.UAVProgress.setCheck(box.getAttribute("data-check-id"), box.checked);
          });
        });
      });
    }

    refresh();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
