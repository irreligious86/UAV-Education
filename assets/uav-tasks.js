/*
 * <uav-tasks src="../tasks/f-physics.json" module="f-physics"></uav-tasks>
 *
 * Numeric-answer tasks for one module. Each task has several precomputed variants
 * (built by scripts/build_site.py from content/tasks/<module>.json); the student gets a
 * random variant, types a number, and the element checks it against the stored answer
 * with a relative tolerance. A solved task is remembered through window.UAVProgress
 * (setTask / getTasks) and counts toward the module score (see grading.js).
 *
 * Published bank format (tasks/<module>.json):
 * { "module": "...", "tasks": [ { "id", "title", "unit", "tol", "abs", "solution",
 *     "variants": [ { "statement": "<html>", "answer": 12.3 } ] } ] }
 */
(function () {
  "use strict";

  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "class") el.className = attrs[k];
      else if (k === "text") el.textContent = attrs[k];
      else if (k === "html") el.innerHTML = attrs[k];
      else if (k.indexOf("on") === 0) el.addEventListener(k.slice(2), attrs[k]);
      else el.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) el.appendChild(c); });
    return el;
  }

  function parseNumber(s) {
    s = String(s).trim().replace(/\s+/g, "").replace(",", ".");
    if (!s) return NaN;
    return Number(s);
  }

  function fmt(v) {
    if (!isFinite(v)) return "—";
    var a = Math.abs(v);
    if (a === 0) return "0";
    if (a >= 1000) return String(Math.round(v));
    if (a >= 100) return v.toFixed(1).replace(/\.0$/, "");
    if (a >= 1) return v.toFixed(2).replace(/\.?0+$/, "");
    return Number(v.toPrecision(3)).toString();
  }

  class UavTasks extends HTMLElement {
    connectedCallback() {
      if (this._init) return;
      this._init = true;
      this.classList.add("uav-tasks");
      this._module = this.getAttribute("module");
      this._variant = {};
      this.appendChild(h("p", { class: "gc-muted", text: "Загружаю задачи…" }));
      var self = this;
      Promise.all([
        fetch(this.getAttribute("src")).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }),
        this.store() ? this.store().getTasks(this._module) : Promise.resolve({})
      ]).then(function (res) { self._bank = res[0]; self._solved = res[1] || {}; self.render(); })
        .catch(function () {
          self.innerHTML = "";
          self.appendChild(h("p", { class: "gc-muted", text: "Задачи для этого модуля пока недоступны." }));
        });
    }

    store() { return window.UAVProgress || null; }

    pickVariant(t) {
      var i = Math.floor(Math.random() * t.variants.length);
      this._variant[t.id] = i;
      return t.variants[i];
    }

    render() {
      var self = this, bank = this._bank;
      this.innerHTML = "";
      var solvedN = bank.tasks.filter(function (t) { return self._solved[t.id]; }).length;
      this.appendChild(h("p", { class: "gc-muted uav-tasks__status", text: "Решено " + solvedN + " из " + bank.tasks.length + ". Числа в условии меняются при каждой загрузке; ответ принимается с допуском." }));
      bank.tasks.forEach(function (t, idx) { self.appendChild(self.renderTask(t, idx)); });
    }

    renderTask(t, idx) {
      var self = this, v = this.pickVariant(t), solved = !!this._solved[t.id];
      var input = h("input", { type: "text", inputmode: "decimal", class: "gc-input uav-tasks__input", "aria-label": "Ответ", placeholder: t.unit ? "ответ, " + t.unit : "ответ" });
      var feedback = h("div", { class: "uav-tasks__feedback", "aria-live": "polite" });
      var card = h("div", { class: "uav-tasks__task gc-card", "data-task": t.id, "data-solved": solved ? "1" : "0" });
      var head = h("div", { class: "uav-tasks__head" }, [
        h("strong", { text: (idx + 1) + ". " + t.title }),
        h("span", { class: "gc-tag", "data-state": solved ? "ok" : "", text: solved ? "РЕШЕНА" : "", hidden: !solved ? "" : null })
      ]);
      if (!solved) head.lastChild.hidden = true;
      var statement = h("p", { class: "uav-tasks__statement", html: v.statement });

      var revealed = false;

      function check() {
        var x = parseNumber(input.value);
        if (!isFinite(x)) { feedback.textContent = "Введите число (десятичный разделитель — точка или запятая)."; feedback.setAttribute("data-state", "caution"); return; }
        var ans = v.answer, tol = Math.max(Math.abs(ans) * (t.tol || 0.03), t.abs || 0, 1e-9);
        var ok = Math.abs(x - ans) <= tol;
        if (ok && revealed) {
          feedback.textContent = "Верно, но решение этого варианта уже показано — возьмите новый вариант, чтобы задача засчиталась.";
          feedback.setAttribute("data-state", "info");
          return;
        }
        if (ok) {
          feedback.innerHTML = "<strong>Верно.</strong> Ответ " + fmt(ans) + (t.unit ? " " + t.unit : "") + ". " + (t.solution || "");
          feedback.setAttribute("data-state", "ok");
          card.setAttribute("data-solved", "1");
          var tag = head.lastChild; tag.textContent = "РЕШЕНА"; tag.setAttribute("data-state", "ok"); tag.hidden = false;
          self._solved[t.id] = true;
          if (self.store()) self.store().setTask(self._module, t.id, true).then(function () {
            document.dispatchEvent(new CustomEvent("uav-quiz-result"));
          });
          var st = self.querySelector(".uav-tasks__status");
          if (st) { var n = Object.keys(self._solved).filter(function (k) { return self._solved[k]; }).length; st.textContent = "Решено " + n + " из " + self._bank.tasks.length + "."; }
        } else {
          var hint = "";
          var ratio = Math.abs(ans) > 1e-9 ? Math.abs(x / ans) : 0;
          if (ratio > 0 && Math.abs(Math.log10(ratio) % 3) < 0.03) hint = " Похоже на ошибку в единицах (множитель 1000).";
          else if (Math.abs(x * 2 - ans) <= tol || Math.abs(x / 2 - ans) <= tol) hint = " Ровно в два раза — проверьте множитель 2 или «туда и обратно».";
          else if (Math.abs(1 / x - ans) <= tol) hint = " Это обратная величина.";
          feedback.textContent = "Неверно." + hint + " Проверьте единицы и порядок величины.";
          feedback.setAttribute("data-state", "danger");
        }
      }

      var btnCheck = h("gc-button", { variant: "primary", text: "Проверить", onclick: check });
      var btnNew = h("gc-button", { variant: "secondary", text: "Новый вариант", onclick: function () {
        revealed = false; v = self.pickVariant(t); statement.innerHTML = v.statement; input.value = ""; feedback.textContent = ""; feedback.removeAttribute("data-state");
      } });
      var btnShow = h("gc-button", { variant: "secondary", text: "Показать решение", onclick: function () {
        revealed = true;
        feedback.innerHTML = "Ответ для этого варианта: <strong>" + fmt(v.answer) + (t.unit ? " " + t.unit : "") + "</strong>. " + (t.solution || "") + " Решите новый вариант, чтобы задача засчиталась.";
        feedback.setAttribute("data-state", "info");
      } });
      input.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); check(); } });

      card.appendChild(head);
      card.appendChild(statement);
      card.appendChild(h("div", { class: "uav-tasks__row" }, [input, t.unit ? h("span", { class: "gc-muted uav-tasks__unit", text: t.unit }) : null, btnCheck, btnNew, btnShow]));
      card.appendChild(feedback);
      return card;
    }
  }

  if (!customElements.get("uav-tasks")) customElements.define("uav-tasks", UavTasks);
})();
