/*
 * <uav-kalman-1d>: scalar Kalman filter on a noisy measurement of a slowly drifting value.
 *
 * Truth: x_k = x_{k-1} + w, w ~ N(0, σw²); measurement z_k = x_k + v, v ~ N(0, σz²).
 * Filter (random-walk model): predict P⁻ = P + Q; K = P⁻ / (P⁻ + R); x += K·(z − x); P = (1 − K)·P⁻.
 * The filter's Q and R are sliders separate from the true noise, so the student sees what a wrong
 * Q/R costs: too small Q — the estimate lags the drift; too large — it follows the noise.
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";

  function rng(seed) {             // mulberry32 + Box–Muller: repeatable noise per seed
    var a = seed >>> 0;
    function u() { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }
    return function () { var r = Math.sqrt(-2 * Math.log(u() + 1e-12)), th = 2 * Math.PI * u(); return r * Math.cos(th); };
  }

  class Kalman1D extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = T('<p class="gc-label gc-muted">Интерактив · фильтр Калмана 1D</p>') +
        T('<p class="widget__hint gc-muted">Высота медленно дрейфует (зелёная), барометр шумит (жёлтая). Верхние два ползунка — настоящий мир, нижние два — что фильтр о нём думает (Q и R). Подбери Q и R так, чтобы оценка (голубая) шла за дрейфом, но не за шумом, и сравни ошибку с ошибкой сырого датчика.</p>');
      var p = this.p = { sz: 1.0, sw: 0.05, R: 1.0, Q: 0.0025, seed: 7, n: 120 };
      var c = document.createElement("div"); c.className = "widget__controls";
      function add(o) { c.appendChild(UAVPlot.slider(o).el); }
      var f2 = function (v) { return (+v).toFixed(2); }, f4 = function (v) { return (+v).toFixed(4); };
      add({ label: T("Шум датчика σz"), min: 0.1, max: 3, step: 0.05, value: p.sz, unit: T("м"), fmt: f2, onChange: function (v) { p.sz = v; self.update(); } });
      add({ label: T("Дрейф σw за шаг"), min: 0, max: 0.5, step: 0.01, value: p.sw, unit: T("м"), fmt: f2, onChange: function (v) { p.sw = v; self.update(); } });
      add({ label: T("Фильтр: R"), min: 0.01, max: 10, step: 0.01, value: p.R, unit: T("м²"), fmt: f2, onChange: function (v) { p.R = v; self.update(); } });
      add({ label: T("Фильтр: Q"), min: 0, max: 0.5, step: 0.0005, value: p.Q, unit: T("м²"), fmt: f4, onChange: function (v) { p.Q = v; self.update(); } });
      this.appendChild(c);
      var b = document.createElement("div"); b.className = "widget__presets";
      [[T("Q и R по правде"), function () { p.R = p.sz * p.sz; p.Q = p.sw * p.sw; }], [T("Q = 0 (модель «не меняется»)"), function () { p.Q = 0; }],
       [T("Q слишком большой"), function () { p.Q = 0.5; }], [T("Новый шум"), function () { p.seed++; }]].forEach(function (x) {
        var bt = document.createElement("button"); bt.type = "button"; bt.className = "gc-tag"; bt.textContent = x[0];
        bt.addEventListener("click", function () { x[1](); self.sync(); self.update(); }); b.appendChild(bt);
      });
      this.appendChild(b);
      var m = document.createElement("div"); m.className = "widget__metrics"; this.appendChild(m); this.metricsEl = m;
      var cv = document.createElement("canvas"); cv.className = "widget__canvas"; this.appendChild(cv);
      this.plot = UAVPlot.create(cv, { xLabel: T("шаг"), yLabel: T("м"), height: 240 });
      this.controls = c;
      this.update();
      window.addEventListener("resize", function () { self.update(); });
    }

    sync() {
      var p = this.p, keys = ["sz", "sw", "R", "Q"];
      this.controls.querySelectorAll("input").forEach(function (inp, i) { inp.value = p[keys[i]]; inp.dispatchEvent(new Event("input")); });
    }

    update() {
      var p = this.p, g = rng(p.seed), x = 10, est = 0, P = 4;
      var xs = [], truth = [], meas = [], estv = [], hi = [], lo = [], se = 0, sm = 0, K = 0;
      for (var k = 0; k < p.n; k++) {
        x += p.sw * g();
        var z = x + p.sz * g();
        var Pm = P + p.Q; K = Pm / (Pm + p.R); est += K * (z - est); P = (1 - K) * Pm;
        xs.push(k); truth.push(x); meas.push(z); estv.push(est); hi.push(est + Math.sqrt(P)); lo.push(est - Math.sqrt(P));
        if (k >= 20) { se += (est - x) * (est - x); sm += (z - x) * (z - x); }
      }
      var nn = p.n - 20, rmsE = Math.sqrt(se / nn), rmsM = Math.sqrt(sm / nn);
      var gain = rmsM / Math.max(rmsE, 1e-9);
      this.metricsEl.innerHTML =
        '<span class="gc-tag" data-state="' + (gain > 2 ? "ok" : gain > 1.2 ? "caution" : "critical") + T('">ошибка оценки ') + rmsE.toFixed(2) + T(' м</span>') +
        T('<span class="gc-tag">ошибка датчика ') + rmsM.toFixed(2) + T(' м</span>') +
        T('<span class="gc-tag" data-state="info">K в конце ') + K.toFixed(3) + '</span>' +
        '<span class="gc-tag">√P ' + Math.sqrt(P).toFixed(2) + T(' м</span>');
      this.plot.draw({ x: xs, series: [
        { y: meas, color: "amber", width: 1, label: T("датчик") },
        { y: truth, color: "green", label: T("правда") },
        { y: estv, color: "cyan", label: T("оценка") },
        { y: hi, color: "muted", width: 1, dash: [3, 3] }, { y: lo, color: "muted", width: 1, dash: [3, 3] }] });
    }
  }

  if (!customElements.get("uav-kalman-1d")) customElements.define("uav-kalman-1d", Kalman1D);
})();
