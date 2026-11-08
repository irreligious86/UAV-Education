/*
 * <uav-tw-calc>: thrust-to-weight and flight-time calculator.
 *
 * T/W = n·Tmax / m; hover throttle ≈ 1/(T/W) (thrust ~ throttle to first order);
 * hover power = (m/n) / efficiency [g/W] per motor; current = P / (cells·3.7 V);
 * flight time = usable capacity / current. Numbers are first-order estimates:
 * efficiency at hover from the motor's thrust table is the input that matters most.
 */
(function () {
  "use strict";

  class TwCalc extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = '<p class="gc-label gc-muted">Интерактив · T/W и время полёта</p>' +
        '<p class="widget__hint gc-muted">Введи взлётную массу с АКБ, число моторов, максимальную тягу одного мотора из таблицы производителя, эффективность на висении (г/Вт из той же таблицы для тяги ≈ масса/число моторов) и АКБ. График — время полёта против добавленной нагрузки: видно, где аппарат перестаёт быть полезным.</p>';
      var p = this.p = { mass: 1400, n: 4, tmax: 1200, eff: 6.5, cells: 6, cap: 4000, aux: 0.8, usable: 0.8 };
      var sl = document.createElement("div"); sl.className = "widget__controls";
      function add(o) { var s = UAVPlot.slider(o); sl.appendChild(s.el); return s; }
      add({ label: "Масса, г", min: 200, max: 12000, step: 50, value: p.mass, unit: "г", onChange: function (v) { p.mass = v; self.update(); } });
      add({ label: "Моторов", min: 3, max: 8, step: 1, value: p.n, onChange: function (v) { p.n = v; self.update(); } });
      add({ label: "Tmax/мотор", min: 100, max: 6000, step: 50, value: p.tmax, unit: "г", onChange: function (v) { p.tmax = v; self.update(); } });
      add({ label: "г/Вт висение", min: 2, max: 25, step: 0.5, value: p.eff, unit: "г/Вт", onChange: function (v) { p.eff = v; self.update(); } });
      add({ label: "Ячеек S", min: 2, max: 14, step: 1, value: p.cells, unit: "S", onChange: function (v) { p.cells = v; self.update(); } });
      add({ label: "Ёмкость", min: 500, max: 40000, step: 100, value: p.cap, unit: "мА·ч", onChange: function (v) { p.cap = v; self.update(); } });
      add({ label: "Борт, А", min: 0, max: 5, step: 0.1, value: p.aux, unit: "А", fmt: function (v) { return (+v).toFixed(1); }, onChange: function (v) { p.aux = v; self.update(); } });
      this.appendChild(sl);
      var m = document.createElement("div"); m.className = "widget__metrics"; this.appendChild(m); this.metricsEl = m;
      var canvas = document.createElement("canvas"); canvas.className = "widget__canvas"; this.appendChild(canvas);
      this.plot = UAVPlot.create(canvas, { xLabel: "добавленная нагрузка, г", yLabel: "время, мин", height: 220 });
      this.update();
    }

    calc(mass) {
      var p = this.p;
      var tw = p.n * p.tmax / mass;
      var hoverPerMotor = mass / p.n;                      // g
      var powerMotors = hoverPerMotor / p.eff * p.n;       // W (eff in g/W)
      var volts = p.cells * 3.7;
      var current = powerMotors / volts + p.aux;           // A
      var minutes = (p.cap / 1000) * p.usable / current * 60;
      return { tw: tw, throttle: 100 / tw, current: current, power: powerMotors, minutes: minutes };
    }

    update() {
      var p = this.p, r = this.calc(p.mass);
      var twState = r.tw < 1.6 ? "critical" : r.tw < 2.2 ? "caution" : "ok";
      var thrState = r.throttle > 60 ? "critical" : r.throttle > 45 ? "caution" : "ok";
      this.metricsEl.innerHTML =
        '<span class="gc-tag" data-state="' + twState + '">T/W ' + r.tw.toFixed(2) + "</span>" +
        '<span class="gc-tag" data-state="' + thrState + '">газ висения ≈ ' + r.throttle.toFixed(0) + " %</span>" +
        '<span class="gc-tag">моторы ' + r.power.toFixed(0) + " Вт</span>" +
        '<span class="gc-tag">ток ' + r.current.toFixed(1) + " А</span>" +
        '<span class="gc-tag" data-state="info">висение ≈ ' + r.minutes.toFixed(1) + " мин (80 % ёмкости)</span>" +
        '<span class="gc-tag gc-muted">манёвры и ветер — минус 20–40 %</span>';
      var xs = [], ys = [], twLine = [];
      var maxAdd = Math.max(200, Math.round(p.mass));
      for (var i = 0; i <= 40; i++) {
        var add = maxAdd * i / 40, c = this.calc(p.mass + add);
        xs.push(add); ys.push(c.tw < 1.2 ? 0 : c.minutes); twLine.push(c.tw);
      }
      var limit = null;
      for (var j = 0; j < xs.length; j++) { if (twLine[j] < 2) { limit = xs[j]; break; } }
      this.plot.draw({
        x: xs,
        series: [{ label: "время висения, мин", y: ys }],
        bands: limit !== null ? [{ x0: limit, x1: xs[xs.length - 1], label: "T/W < 2" }] : [],
        yMin: 0, xFmt: function (v) { return v.toFixed(0); }
      });
    }
  }

  if (!customElements.get("uav-tw-calc")) customElements.define("uav-tw-calc", TwCalc);
})();
