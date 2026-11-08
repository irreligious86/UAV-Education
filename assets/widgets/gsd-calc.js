/*
 * <uav-gsd-calc>: survey planning from camera and altitude.
 *
 * GSD = H · sensor_width / (focal · image_width_px); footprint W = GSD · px_w, L = GSD · px_h
 * (px_h from the aspect ratio, the long side across track). Trigger distance = L · (1 − front overlap),
 * line spacing = W · (1 − side overlap), photo interval = trigger distance / ground speed.
 * Pinhole camera over flat ground, nadir view — the same model as the mapping module.
 */
(function () {
  "use strict";

  class GsdCalc extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = '<p class="gc-label gc-muted">Интерактив · GSD, перекрытия и шаг съёмки</p>' +
        '<p class="widget__hint gc-muted">Камера в надир над ровной землёй. Длинная сторона кадра — поперёк маршрута. Красная метка — если камера не успевает снимать с нужным интервалом (типично 1–2 с на кадр у компактных камер).</p>';
      var p = this.p = { sw: 13.2, f: 8.8, px: 5472, aspect: 1.5, h: 100, fo: 75, so: 65, v: 10, minInt: 2 };
      var c = document.createElement("div"); c.className = "widget__controls"; this.controls = c;
      var f1 = function (v) { return (+v).toFixed(1); };
      var defs = [
        { k: "sw", label: "Ширина сенсора", min: 4, max: 36, step: 0.1, unit: "мм", fmt: f1 },
        { k: "f", label: "Фокус", min: 2, max: 50, step: 0.1, unit: "мм", fmt: f1 },
        { k: "px", label: "Ширина кадра", min: 1280, max: 9504, step: 16, unit: "px" },
        { k: "h", label: "Высота", min: 10, max: 300, step: 1, unit: "м" },
        { k: "fo", label: "Продольное перекрытие", min: 50, max: 90, step: 1, unit: "%" },
        { k: "so", label: "Поперечное перекрытие", min: 30, max: 85, step: 1, unit: "%" },
        { k: "v", label: "Скорость", min: 2, max: 25, step: 0.5, unit: "м/с", fmt: f1 },
        { k: "minInt", label: "Мин. интервал камеры", min: 0.5, max: 5, step: 0.1, unit: "с", fmt: f1 }];
      defs.forEach(function (d) { c.appendChild(UAVPlot.slider({ label: d.label, min: d.min, max: d.max, step: d.step, value: p[d.k], unit: d.unit, fmt: d.fmt, onChange: function (v) { p[d.k] = v; self.update(); } }).el); });
      this.appendChild(c);
      var b = document.createElement("div"); b.className = "widget__presets";
      [["1\" 20 Мп, 8.8 мм", { sw: 13.2, f: 8.8, px: 5472 }], ["1/2.3\" 12 Мп, 4.5 мм", { sw: 6.17, f: 4.5, px: 4000 }],
       ["APS-C 24 Мп, 24 мм", { sw: 23.5, f: 24, px: 6000 }], ["FPV 1280 px, HFOV 120°", { sw: 6.4, f: 1.85, px: 1280 }]].forEach(function (pr) {
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
      this.plot = UAVPlot.create(cv, { xLabel: "высота, м", yLabel: "GSD, см/px", height: 220 });
      this.update();
      window.addEventListener("resize", function () { self.update(); });
    }

    update() {
      var p = this.p;
      var gsd = function (h) { return h * (p.sw / 1000) / ((p.f / 1000) * p.px); };   // m/px
      var g = gsd(p.h), W = g * p.px, L = W / p.aspect;
      var trig = L * (1 - p.fo / 100), line = W * (1 - p.so / 100), interval = trig / p.v;
      var areaPerKm = line * 1000 / 10000;            // ha per km of flight line
      this.metricsEl.innerHTML =
        '<span class="gc-tag" data-state="info">GSD ' + (g * 100).toFixed(2) + ' см/px</span>' +
        '<span class="gc-tag">кадр ' + W.toFixed(0) + ' × ' + L.toFixed(0) + ' м</span>' +
        '<span class="gc-tag">снимок каждые ' + trig.toFixed(1) + ' м</span>' +
        '<span class="gc-tag" data-state="' + (interval >= p.minInt ? "ok" : "critical") + '">интервал ' + interval.toFixed(2) + ' с</span>' +
        '<span class="gc-tag">галсы через ' + line.toFixed(1) + ' м</span>' +
        '<span class="gc-tag">' + areaPerKm.toFixed(1) + ' га на 1 км галса</span>';
      var xs = [], ys = [];
      for (var h = 10; h <= 300; h += 5) { xs.push(h); ys.push(gsd(h) * 100); }
      this.plot.draw({ x: xs, yMin: 0, series: [{ y: ys, color: "cyan", label: "GSD" }],
        bands: [{ x0: Math.max(10, p.h - 3), x1: Math.min(300, p.h + 3), color: "rgba(255,181,71,0.35)", label: (g * 100).toFixed(1) + " см" }] });
    }
  }

  if (!customElements.get("uav-gsd-calc")) customElements.define("uav-gsd-calc", GsdCalc);
})();
