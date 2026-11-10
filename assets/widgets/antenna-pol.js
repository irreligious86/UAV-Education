/*
 * <uav-antenna-pol>: extra path loss from antenna orientation.
 *
 * Polarization mismatch: linear–linear at angle θ → −20·log10|cos θ|; linear–circular → 3 dB at any θ;
 * circular–circular, same hand → ~0 dB, opposite hand → ~20 dB in practice (axial ratio limits it).
 * Vertical half-wave dipole elevation pattern: E(ψ) = cos(π/2·cos ψ)/sin ψ, ψ from the dipole axis —
 * a null straight up/down: the "aircraft overhead" dropout.
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";

  function polLoss(type, deg) {
    var c = Math.abs(Math.cos(deg * Math.PI / 180));
    if (type === "ll") return Math.min(40, -20 * Math.log10(Math.max(c, 1e-2)));
    if (type === "lc") return 3;
    if (type === "cc") return 0;
    return 20;   // opposite circular hand
  }
  function dipoleLossDb(elevDeg) {          // elevation above the horizon for a vertical dipole
    var psi = (90 - elevDeg) * Math.PI / 180;
    if (Math.abs(Math.sin(psi)) < 1e-3) return 40;
    var e = Math.cos(Math.PI / 2 * Math.cos(psi)) / Math.sin(psi);
    return Math.min(40, -20 * Math.log10(Math.max(Math.abs(e), 1e-2)));
  }

  class AntennaPol extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = T('<p class="gc-label gc-muted">Интерактив · поляризация и ноль диполя</p>') +
        T('<p class="widget__hint gc-muted">Крен аппарата поворачивает его линейную антенну относительно наземной; угол места — насколько аппарат высоко над антенной на земле. Вертикальный диполь «не видит» прямо вверх. Сравни линейную пару с круговой поляризацией и посмотри, сколько дБ съедает пролёт над головой.</p>');
      var p = this.p = { type: "ll", roll: 30, elev: 20 };
      var c = document.createElement("div"); c.className = "widget__controls";
      c.appendChild(UAVPlot.slider({ label: T("Крен аппарата"), min: 0, max: 90, step: 1, value: p.roll, unit: "°", onChange: function (v) { p.roll = v; self.update(); } }).el);
      c.appendChild(UAVPlot.slider({ label: T("Угол места аппарата"), min: 0, max: 90, step: 1, value: p.elev, unit: "°", onChange: function (v) { p.elev = v; self.update(); } }).el);
      this.appendChild(c);
      var b = document.createElement("div"); b.className = "widget__presets";
      [["ll", T("линейная ↔ линейная")], ["lc", T("линейная ↔ круговая")], ["cc", T("круговая, одна рука")], ["co", "RHCP ↔ LHCP"]].forEach(function (t) {
        var bt = document.createElement("button"); bt.type = "button"; bt.className = "gc-tag"; bt.textContent = t[1];
        bt.addEventListener("click", function () { p.type = t[0]; b.querySelectorAll("button").forEach(function (x) { x.setAttribute("data-state", ""); }); bt.setAttribute("data-state", "ok"); self.update(); });
        if (t[0] === p.type) bt.setAttribute("data-state", "ok");
        b.appendChild(bt);
      });
      this.appendChild(b);
      var m = document.createElement("div"); m.className = "widget__metrics"; this.appendChild(m); this.metricsEl = m;
      var cv = document.createElement("canvas"); cv.className = "widget__canvas"; this.appendChild(cv);
      this.plot = UAVPlot.create(cv, { xLabel: T("крен, °"), yLabel: T("потери, дБ"), height: 220 });
      this.update();
      window.addEventListener("resize", function () { self.update(); });
    }

    update() {
      var p = this.p, pl = polLoss(p.type, p.roll), dl = dipoleLossDb(p.elev), tot = pl + dl;
      var range = Math.pow(10, -tot / 20);
      this.metricsEl.innerHTML =
        T('<span class="gc-tag">поляризация ') + pl.toFixed(1) + T(' дБ</span>') +
        T('<span class="gc-tag">диаграмма диполя ') + dl.toFixed(1) + T(' дБ</span>') +
        '<span class="gc-tag" data-state="' + (tot < 6 ? "ok" : tot < 12 ? "caution" : "critical") + T('">итого ') + tot.toFixed(1) + T(' дБ → дальность × ') + range.toFixed(2) + '</span>';
      var xs = [], a = [], cur = [];
      for (var r = 0; r <= 90; r += 1) { xs.push(r); a.push(polLoss(p.type, r) + dl); cur.push(null); }
      this.plot.draw({ x: xs, yMin: 0, yMax: 40, series: [{ y: a, color: "cyan", label: T("потери при текущем угле места") }],
        bands: [{ x0: Math.max(0, p.roll - 1), x1: Math.min(90, p.roll + 1), color: "rgba(255,181,71,0.45)", label: p.roll + "°" }] });
    }
  }

  if (!customElements.get("uav-antenna-pol")) customElements.define("uav-antenna-pol", AntennaPol);
})();
