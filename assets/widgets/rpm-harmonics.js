/*
 * <uav-rpm-harmonics>: where motor noise lives in the gyro spectrum vs throttle.
 *
 * Loaded speed ≈ KV · V · throttle · η (η ≈ 0.8: a loaded prop runs below no-load speed).
 * Fundamental f1 = rpm / 60, harmonics k·f1. Compared with the Betaflight filter settings that
 * decide whether the noise is caught: rpm_filter_min_hz (notches are not placed below it),
 * dynamic notch range and the gyro low-pass cutoff. A first-order estimate — the RPM filter
 * itself follows real eRPM from bidirectional DShot.
 */
(function () {
  "use strict";

  class RpmHarmonics extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = '<p class="gc-label gc-muted">Интерактив · гармоники моторов против фильтров</p>' +
        '<p class="widget__hint gc-muted">Линии — частоты 1-й, 2-й и 3-й гармоники моторов от газа. Горизонтали — настройки фильтров Betaflight. Если основная гармоника на рабочем газу ниже rpm_filter_min_hz, RPM-фильтр её не ловит — это кейс медленных моторов 10" из модуля.</p>';
      var p = this.p = { kv: 1950, cells: 6, eta: 0.8, minHz: 100, dmin: 100, dmax: 600, lpf: 250 };
      var c = document.createElement("div"); c.className = "widget__controls"; this.controls = c;
      var defs = [
        { k: "kv", label: "KV мотора", min: 100, max: 5000, step: 10, unit: "об/мин/В" },
        { k: "cells", label: "Ячеек S", min: 1, max: 12, step: 1, unit: "S" },
        { k: "eta", label: "Обороты под нагрузкой", min: 0.6, max: 0.95, step: 0.01, fmt: function (v) { return Math.round(v * 100) + " %"; } },
        { k: "minHz", label: "RPM min_hz", min: 50, max: 200, step: 5, unit: "Гц" },
        { k: "dmin", label: "Dyn notch min", min: 50, max: 250, step: 5, unit: "Гц" },
        { k: "dmax", label: "Dyn notch max", min: 200, max: 1000, step: 10, unit: "Гц" },
        { k: "lpf", label: "Gyro LPF1", min: 50, max: 600, step: 10, unit: "Гц" }];
      defs.forEach(function (d) { c.appendChild(UAVPlot.slider({ label: d.label, min: d.min, max: d.max, step: d.step, value: p[d.k], unit: d.unit, fmt: d.fmt, onChange: function (v) { p[d.k] = v; self.update(); } }).el); });
      this.appendChild(c);
      var b = document.createElement("div"); b.className = "widget__presets";
      [["5\" 2207 1950KV 6S", { kv: 1950, cells: 6 }], ["7\" 2806.5 1300KV 6S", { kv: 1300, cells: 6 }],
       ["10\" 3115 900KV 6S", { kv: 900, cells: 6 }], ["3\" 1404 4600KV 4S", { kv: 4600, cells: 4 }]].forEach(function (pr) {
        var bt = document.createElement("button"); bt.type = "button"; bt.className = "gc-tag"; bt.textContent = pr[0];
        bt.addEventListener("click", function () {
          Object.keys(pr[1]).forEach(function (k) { p[k] = pr[1][k]; });
          c.querySelectorAll("input").forEach(function (inp, i) { inp.value = p[defs[i].k]; inp.dispatchEvent(new Event("input")); });
        });
        b.appendChild(bt);
      });
      this.appendChild(b);
      var m = document.createElement("div"); m.className = "widget__metrics"; this.appendChild(m); this.metricsEl = m;
      var cv = document.createElement("canvas"); cv.className = "widget__canvas"; this.appendChild(cv);
      this.plot = UAVPlot.create(cv, { xLabel: "газ, %", yLabel: "Гц", height: 240 });
      this.update();
      window.addEventListener("resize", function () { self.update(); });
    }

    update() {
      var p = this.p, V = p.cells * 3.7;
      var f1 = function (u) { return p.kv * V * (u / 100) * p.eta / 60; };
      var xs = [], h1 = [], h2 = [], h3 = [], mn = [], dn = [], dx = [], lp = [];
      for (var u = 10; u <= 100; u += 2) { xs.push(u); h1.push(f1(u)); h2.push(2 * f1(u)); h3.push(3 * f1(u)); mn.push(p.minHz); dn.push(p.dmin); dx.push(p.dmax); lp.push(p.lpf); }
      var hover = f1(30), full = f1(100);
      var missed = hover < p.minHz;
      var wc = 2 * Math.PI * p.lpf, w20 = 2 * Math.PI * 20;
      var lpfDelay = 1000 / wc / (1 + (w20 / wc) * (w20 / wc));   // PT1 group delay, ms
      this.metricsEl.innerHTML =
        '<span class="gc-tag" data-state="info">1-я гармоника: ' + hover.toFixed(0) + ' Гц на 30 % газа, ' + full.toFixed(0) + ' Гц на 100 %</span>' +
        '<span class="gc-tag" data-state="' + (missed ? "critical" : "ok") + '">' + (missed ? "на 30 % газа ниже rpm_filter_min_hz — RPM-фильтр не ловит" : "RPM-фильтр покрывает рабочий газ") + '</span>' +
        '<span class="gc-tag" data-state="' + (lpfDelay > 1 ? "caution" : "ok") + '">PT1 ' + p.lpf + ' Гц: задержка ≈ ' + lpfDelay.toFixed(2) + ' мс на 20 Гц</span>';
      this.plot.draw({ x: xs, yMin: 0, series: [
        { y: h1, color: "cyan", label: "1×" }, { y: h2, color: "cyan", width: 1, label: "2×" }, { y: h3, color: "cyan", width: 1, dash: [3, 3], label: "3×" },
        { y: mn, color: "red", width: 1, dash: [5, 3], label: "rpm min" }, { y: dn, color: "amber", width: 1, dash: [2, 3], label: "dyn" },
        { y: dx, color: "amber", width: 1, dash: [2, 3] }, { y: lp, color: "green", width: 1, dash: [6, 3], label: "LPF" }] });
    }
  }

  if (!customElements.get("uav-rpm-harmonics")) customElements.define("uav-rpm-harmonics", RpmHarmonics);
})();
