/*
 * <uav-filter-response>: magnitude and phase delay of a Betaflight-like gyro filter chain.
 *
 * Chain (as in Betaflight 4.x): optional RPM notches (3 harmonics) -> dynamic notch -> LPF1 (PT1) -> LPF2 (PT1).
 * Everything is computed analytically in the s-domain at the chosen loop rate; the group delay
 * at a reference frequency (default 20 Hz, "control band") is shown in ms — that's the cost the
 * filters module talks about. Motor band is drawn from the motor-frequency slider.
 *
 * PT1:    H(s) = 1 / (1 + s/ωc)
 * Notch:  H(s) = (s² + ω0²) / (s² + (ω0/Q)·s + ω0²)
 */
(function () {
  "use strict";

  function pt1(f, fc) { // returns {re, im}
    var x = f / fc; var den = 1 + x * x;
    return { re: 1 / den, im: -x / den };
  }
  function notch(f, f0, q) {
    var w = 2 * Math.PI * f, w0 = 2 * Math.PI * f0;
    var numRe = w0 * w0 - w * w, numIm = 0;
    var denRe = w0 * w0 - w * w, denIm = (w0 / q) * w;
    var d = denRe * denRe + denIm * denIm;
    return { re: (numRe * denRe + numIm * denIm) / d, im: (numIm * denRe - numRe * denIm) / d };
  }
  function mul(a, b) { return { re: a.re * b.re - a.im * b.im, im: a.re * b.im + a.im * b.re }; }
  function mag(c) { return Math.sqrt(c.re * c.re + c.im * c.im); }
  function phase(c) { return Math.atan2(c.im, c.re); }

  function response(p, f) {
    var h = { re: 1, im: 0 };
    if (p.lpf1 > 0) h = mul(h, pt1(f, p.lpf1));
    if (p.lpf2 > 0) h = mul(h, pt1(f, p.lpf2));
    if (p.rpm) for (var k = 1; k <= 3; k++) h = mul(h, notch(f, p.motor * k, p.rpmQ));
    if (p.dyn) h = mul(h, notch(f, p.dynF, p.dynQ));
    return h;
  }

  function groupDelayMs(p, f) {
    var df = 0.5;
    var ph1 = phase(response(p, f - df)), ph2 = phase(response(p, f + df));
    var dphi = ph2 - ph1;
    while (dphi > Math.PI) dphi -= 2 * Math.PI; while (dphi < -Math.PI) dphi += 2 * Math.PI;
    return -dphi / (2 * Math.PI * 2 * df) * 1000;
  }

  class FilterResponse extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = '<p class="gc-label gc-muted">Интерактив · АЧХ цепочки фильтров гироскопа</p>' +
        '<p class="widget__hint gc-muted">Цепочка как в Betaflight: RPM-notch (3 гармоники) → dynamic notch → LPF1 → LPF2. Жёлтая полоса — шум моторов (±8 %: обороты гуляют, поэтому подавление считается по полосе, а не в точке). Внизу — задержка, которую фильтры добавляют полезному сигналу управления (20 Гц). Двигай срезы и смотри, как подавление в полосе моторов покупается задержкой.</p>';
      var p = this.p = { lpf1: 250, lpf2: 500, rpm: 1, rpmQ: 500 / 100, motor: 180, dyn: 1, dynF: 300, dynQ: 300 / 100, loop: 8000 };
      var controls = document.createElement("div"); controls.className = "widget__controls";
      var defs = [
        { k: "lpf1", label: "Gyro LPF1", min: 0, max: 600, step: 10, unit: "Гц", fmt: function (v) { return v === 0 ? "выкл" : v; } },
        { k: "lpf2", label: "Gyro LPF2", min: 0, max: 1000, step: 10, unit: "Гц", fmt: function (v) { return v === 0 ? "выкл" : v; } },
        { k: "motor", label: "Частота моторов", min: 40, max: 500, step: 5, unit: "Гц" },
        { k: "rpmQ", label: "RPM notch Q", min: 1, max: 10, step: 0.5 },
        { k: "dynF", label: "Dyn notch центр", min: 60, max: 600, step: 10, unit: "Гц" },
        { k: "dynQ", label: "Dyn notch Q", min: 1, max: 10, step: 0.5 }
      ];
      defs.forEach(function (d) {
        controls.appendChild(UAVPlot.slider({ label: d.label, min: d.min, max: d.max, step: d.step, value: p[d.k], unit: d.unit, fmt: d.fmt, onChange: function (v) { p[d.k] = v; self.update(); } }).el);
      });
      var toggles = document.createElement("div"); toggles.className = "widget__presets";
      [["rpm", "RPM-фильтр"], ["dyn", "Dynamic notch"]].forEach(function (t) {
        var b = document.createElement("button"); b.type = "button"; b.className = "gc-tag"; b.setAttribute("data-state", "ok"); b.textContent = t[1] + ": вкл";
        b.addEventListener("click", function () { p[t[0]] = p[t[0]] ? 0 : 1; b.textContent = t[1] + (p[t[0]] ? ": вкл" : ": выкл"); b.setAttribute("data-state", p[t[0]] ? "ok" : ""); self.update(); });
        toggles.appendChild(b);
      });
      this.appendChild(controls); this.appendChild(toggles);
      var c1 = document.createElement("canvas"); c1.className = "widget__canvas"; this.appendChild(c1);
      this.plot = UAVPlot.create(c1, { xLabel: "Гц", yLabel: "дБ", height: 240 });
      var m = document.createElement("div"); m.className = "widget__metrics"; this.appendChild(m); this.metricsEl = m;
      var presets = document.createElement("div"); presets.className = "widget__presets";
      [["5\" дефолт", { lpf1: 250, lpf2: 500, motor: 300, dynF: 350, rpm: 1, dyn: 1 }], ["10\" медленные моторы", { lpf1: 250, lpf2: 500, motor: 90, dynF: 150, rpm: 1, dyn: 1 }], ["RPM-фильтр мимо (min_hz выше моторов)", { lpf1: 250, lpf2: 500, motor: 90, dynF: 350, rpm: 0, dyn: 1 }], ["Только LPF 100 Гц", { lpf1: 100, lpf2: 0, rpm: 0, dyn: 0 }], ["Без фильтров", { lpf1: 0, lpf2: 0, rpm: 0, dyn: 0 }]].forEach(function (pr) {
        var b = document.createElement("button"); b.type = "button"; b.className = "gc-tag"; b.textContent = pr[0];
        b.addEventListener("click", function () {
          Object.keys(pr[1]).forEach(function (k) { p[k] = pr[1][k]; });
          toggles.querySelectorAll("button").forEach(function (bt, i) { var key = i === 0 ? "rpm" : "dyn"; bt.textContent = (i === 0 ? "RPM-фильтр" : "Dynamic notch") + (p[key] ? ": вкл" : ": выкл"); bt.setAttribute("data-state", p[key] ? "ok" : ""); });
          controls.querySelectorAll("input").forEach(function (inp, i) { inp.value = p[defs[i].k]; inp.dispatchEvent(new Event("input")); });
        });
        presets.appendChild(b);
      });
      this.appendChild(presets);
      this.update();
      window.addEventListener("resize", function () { self.update(); });
    }

    update() {
      var p = this.p, xs = [], ys = [];
      for (var f = 10; f <= 1000; f *= 1.03) { xs.push(f); ys.push(20 * Math.log10(Math.max(mag(response(p, f)), 1e-3))); }
      // log x axis: map to log10 for plotting
      var lx = xs.map(function (v) { return Math.log10(v); });
      var motorBand = [Math.log10(p.motor * 0.85), Math.log10(p.motor * 1.15)];
      this.plot.draw({
        x: lx, series: [{ y: ys, color: "cyan", label: "усиление, дБ" }], yMin: -60, yMax: 5,
        xTicks: [1, 1.301, 1.699, 2, 2.301, 2.699, 3], xFmt: function (v) { return String(Math.round(Math.pow(10, v))); },
        bands: [{ x0: motorBand[0], x1: motorBand[1], label: "моторы" }, { x0: Math.log10(10), x1: Math.log10(30), color: "rgba(155,229,100,0.10)", label: "управление" }]
      });
      function bandAtt(f0) {  // mean attenuation over ±8 % around f0: motors never sit exactly on the notch
        var s = 0, n = 0;
        for (var k = -0.08; k <= 0.0801; k += 0.02) { s += -20 * Math.log10(Math.max(mag(response(p, f0 * (1 + k))), 1e-3)); n++; }
        return Math.min(60, s / n);
      }
      var att = bandAtt(p.motor), att2 = bandAtt(p.motor * 2);
      var delay = groupDelayMs(p, 20);
      var cls = function (v, good, ok) { return v >= good ? "ok" : v >= ok ? "caution" : "critical"; };
      var dcls = function (v) { return v <= 2 ? "ok" : v <= 4 ? "caution" : "critical"; };
      this.metricsEl.innerHTML =
        '<span class="gc-tag" data-state="' + cls(att, 20, 10) + '">подавление на моторах ' + (att >= 60 ? '>60' : att.toFixed(0)) + " дБ</span>" +
        '<span class="gc-tag" data-state="' + cls(att2, 20, 10) + '">на 2-й гармонике ' + (att2 >= 60 ? '>60' : att2.toFixed(0)) + " дБ</span>" +
        '<span class="gc-tag" data-state="' + dcls(delay) + '">задержка на 20 Гц ' + delay.toFixed(1) + " мс</span>";
    }
  }

  if (!customElements.get("uav-filter-response")) customElements.define("uav-filter-response", FilterResponse);
})();
