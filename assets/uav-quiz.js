/*
 * <uav-quiz src="../quiz/bf-failsafe.json" module="bf-failsafe"></uav-quiz>
 *
 * Multiple-choice quiz for one module. Loads a JSON question bank, shows one question
 * at a time, explains every answer, and stores the result through window.UAVProgress
 * (getQuiz / setQuiz). Styling uses Ground Control tokens via light DOM, no Shadow DOM,
 * so .gc-* classes apply.
 *
 * Bank format (content/quiz/<module>.json):
 * {
 *   "module": "bf-failsafe",
 *   "pass": 80,
 *   "questions": [
 *     { "q": "...", "options": ["...", "..."], "answer": 1, "explain": "..." }
 *   ]
 * }
 */
(function () {
  "use strict";

  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "class") el.className = attrs[k];
      else if (k === "text") el.textContent = attrs[k];
      else if (k.indexOf("on") === 0) el.addEventListener(k.slice(2), attrs[k]);
      else el.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) el.appendChild(c); });
    return el;
  }

  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  class UavQuiz extends HTMLElement {
    connectedCallback() {
      if (this._init) return;
      this._init = true;
      this.classList.add("uav-quiz");
      this._module = this.getAttribute("module");
      this.innerHTML = "";
      this.appendChild(h("p", { class: "gc-muted", text: "Загружаю вопросы…" }));
      var self = this;
      fetch(this.getAttribute("src"))
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (bank) { self._bank = bank; self.renderIntro(); })
        .catch(function () {
          self.innerHTML = "";
          self.appendChild(h("p", { class: "gc-muted", text: "Квиз для этого модуля пока недоступен." }));
        });
    }

    store() { return window.UAVProgress || null; }

    renderIntro() {
      var self = this, bank = this._bank;
      this.innerHTML = "";
      var head = h("div", { class: "uav-quiz__head" }, [
        h("p", { class: "gc-label gc-muted", text: "Проверь себя" }),
        h("p", { text: bank.questions.length + " вопросов · проходной балл " + (bank.pass || 80) + "%" })
      ]);
      this.appendChild(head);
      var start = h("gc-button", { text: "Начать квиз", onclick: function () { self.start(); } });
      this.appendChild(start);
      var s = this.store();
      if (s && s.getQuiz) {
        s.getQuiz(this._module).then(function (res) {
          if (!res) return;
          var pct = Math.round(100 * res.correct / res.total);
          var ok = pct >= (bank.pass || 80);
          head.appendChild(h("p", { class: "gc-tag", "data-state": ok ? "ok" : "caution",
            text: (ok ? "СДАН " : "НЕ СДАН ") + pct + "%" }));
        });
      }
    }

    start() {
      this._order = shuffle(this._bank.questions.map(function (_, i) { return i; }));
      this._pos = 0;
      this._correct = 0;
      this.renderQuestion();
    }

    renderQuestion() {
      var self = this, q = this._bank.questions[this._order[this._pos]];
      this.innerHTML = "";
      this.appendChild(h("p", { class: "gc-label gc-muted",
        text: "Вопрос " + (this._pos + 1) + " из " + this._order.length }));
      this.appendChild(h("p", { class: "uav-quiz__q", text: q.q }));
      var list = h("div", { class: "uav-quiz__options", role: "group" });
      var answered = false;
      // Shuffle option order per render so the correct answer's position carries no signal.
      var order = shuffle(q.options.map(function (_, i) { return i; }));
      order.forEach(function (origIdx, pos) {
        var btn = h("button", { type: "button", class: "uav-quiz__opt", text: q.options[origIdx], onclick: function () {
          if (answered) return;
          answered = true;
          var right = origIdx === q.answer;
          if (right) self._correct++;
          Array.prototype.forEach.call(list.children, function (b, j) {
            b.disabled = true;
            if (order[j] === q.answer) b.setAttribute("data-state", "ok");
            else if (j === pos) b.setAttribute("data-state", "critical");
          });
          var box = h("div", { class: "gc-callout", "data-state": right ? "ok" : "caution" }, [
            h("strong", { text: right ? "Верно. " : "Неверно. " }),
            h("span", { text: q.explain || "" })
          ]);
          self.appendChild(box);
          var next = h("gc-button", { variant: "secondary",
            text: self._pos + 1 < self._order.length ? "Дальше" : "Результат",
            onclick: function () { self._pos++; self._pos < self._order.length ? self.renderQuestion() : self.renderResult(); } });
          self.appendChild(h("div", { class: "uav-quiz__nav" }, [next]));
        } });
        list.appendChild(btn);
      });
      this.appendChild(list);
    }

    renderResult() {
      var self = this, total = this._order.length, pct = Math.round(100 * this._correct / total);
      var ok = pct >= (this._bank.pass || 80);
      this.innerHTML = "";
      this.appendChild(h("p", { class: "gc-label gc-muted", text: "Результат" }));
      this.appendChild(h("p", { class: "uav-quiz__score", text: this._correct + " из " + total + " · " + pct + "%" }));
      this.appendChild(h("div", { class: "gc-callout", "data-state": ok ? "ok" : "caution" }, [
        h("strong", { text: ok ? "Квиз сдан. " : "Пока не сдан. " }),
        h("span", { text: ok ? "Засчитан лучший результат. Модуль станет «освоен», когда выполнена и лабораторная." : "Перечитай теорию и диагностику, затем попробуй ещё раз. Засчитывается лучшая попытка." })
      ]));
      this.appendChild(h("div", { class: "uav-quiz__nav" }, [
        h("gc-button", { variant: "secondary", text: "Пройти ещё раз", onclick: function () { self.start(); } })
      ]));
      var s = this.store();
      if (s && s.setQuiz) s.setQuiz(this._module, { correct: this._correct, total: total, ts: Date.now() })
        .then(function () { document.dispatchEvent(new CustomEvent("uav-quiz-result")); });
    }
  }

  if (!customElements.get("uav-quiz")) customElements.define("uav-quiz", UavQuiz);
})();
