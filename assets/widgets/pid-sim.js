/*
 * <uav-pid-sim>: step-response simulator for a single rate axis.
 *
 * Plant: rigid body with inertia and aerodynamic drag, torque-limited (motor saturation):
 *   J·ω' = τ − c·ω,  τ = clamp(u, ±τmax)
 * Controller (Betaflight-like rate PID with feedforward, D on measurement, gyro noise):
 *   u = P·e + I·∫e − D·dω/dt + FF·dsp/dt,  e = setpoint − ω_measured
 * Gyro noise is white, scaled by the "noise" slider; motor output shows how D amplifies it.
 *
 * Metrics shown match the course's tuning module: entry lag (50% of setpoint), overshoot,
 * bounce-back after the step ends, settle time, motor noise (std of u above 40 Hz ~ high-pass).
 * This is a teaching model: numbers are qualitative, trends are real.
 */
(function () {
  "use strict";

  var DT = 0.0005;           // 2 kHz loop
  var T_END = 0.6;           // s
  var STEP_ON = 0.05, STEP_OFF = 0.35, SP = 300;  // °/s step from 50 ms to 350 ms

  // Plant: motor/prop thrust lag (1st order, tau ~20 ms) driving a rigid axis with small drag.
  // That lag is what makes the loop second-order, so D has something to damp.
  var ACC = 120, DRAG = 0.3, MOTOR_TAU = 0.02, LOOP_DELAY_S = 0.002, D_LPF = 100;
  var K_I = 3.0, K_D = 1.4 * 0.01, K_FF = 0.25, FF_TAU = 0.03;

  function simulate(p) {
    var n = Math.round(T_END / DT), t = new Array(n), sp = new Array(n), w = new Array(n), u = new Array(n);
    var omega = 0, integ = 0, filt = 0, dfilt = 0, prevF = 0, prevSp = 0, thrust = 0, ffs = 0;
    var a = (2 * Math.PI * p.lpf * DT) / (1 + 2 * Math.PI * p.lpf * DT);
    var ad = (2 * Math.PI * D_LPF * DT) / (1 + 2 * Math.PI * D_LPF * DT);
    var am = DT / MOTOR_TAU, fa = DT / FF_TAU;
    var dl = Math.round(LOOP_DELAY_S / DT), buf = [], seed = 12345;
    for (var k = 0; k <= dl; k++) buf.push(0);
    function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff - 0.5; }
    for (var i = 0; i < n; i++) {
      var time = i * DT;
      var setp = (time >= STEP_ON && time < STEP_OFF) ? SP : 0;
      var meas = omega + rnd() * p.noise * 2;
      filt += a * (meas - filt);
      var e = setp - filt;
      integ += e * DT;
      dfilt += ad * ((filt - prevF) / DT - dfilt);
      ffs += (setp - prevSp) * K_FF - ffs * fa;
      var out = (p.P * e + p.I * integ * K_I - p.D * dfilt * K_D + p.FF * ffs) / 100;
      if (out > 100) { out = 100; integ -= e * DT; } else if (out < -100) { out = -100; integ -= e * DT; }
      buf.push(out); var ue = buf.shift();
      thrust += am * (ue - thrust);
      omega += (ACC * thrust - DRAG * omega) * DT;
      t[i] = time * 1000; sp[i] = setp; w[i] = omega; u[i] = out;
      prevF = filt; prevSp = setp;
    }
    return { t: t, sp: sp, w: w, u: u };
  }

  function metrics(r) {
    var iOn = Math.round(STEP_ON / DT), iOff = Math.round(STEP_OFF / DT);
    var lag = null, peak = 0, settle = null;
    for (var i = iOn; i < iOff; i++) {
      if (lag === null && r.w[i] >= SP * 0.3) lag = (i - iOn) * DT * 1000;
      if (r.w[i] > peak) peak = r.w[i];
    }
    for (var j = iOff - 1; j >= iOn; j--) { if (Math.abs(r.w[j] - SP) > SP * 0.05) { settle = (j + 1 - iOn) * DT * 1000; break; } }
    var bounce = 0;
    for (var k = iOff; k < Math.min(r.w.length, iOff + Math.round(0.15 / DT)); k++) if (-r.w[k] > bounce) bounce = -r.w[k];
    var prev = r.u[iOn + 200], acc = 0, cnt = 0;
    for (var m = iOn + 200; m < iOff; m++) { var d = r.u[m] - prev; prev = r.u[m]; acc += d * d; cnt++; }
    return { lag: lag, overshoot: Math.max(0, (peak - SP) / SP * 100), bounce: bounce / SP * 100, settle: settle === null ? 0 : settle, noise: Math.sqrt(acc / Math.max(cnt, 1)) * 10 };
  }

  class PidSim extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = '<p class="gc-label gc-muted">Интерактив · step response одной оси</p>' +
        '<p class="widget__hint gc-muted">Setpoint — ступенька 300 °/с на 300 мс по одной оси. Модель учебная: моторы с запаздыванием ~20 мс, петля 2 кГц, D на отфильтрованном гироскопе. Крути P, I, D, FF, шум и фильтр: смотри перелёт, bounce-back после остановки и как D превращает шум в дрожание моторов. Тренды честные, абсолютные цифры — нет.</p>';
      var p = this.p = { P: 45, I: 60, D: 25, FF: 60, noise: 2, lpf: 150 };
      var controls = document.createElement("div"); controls.className = "widget__controls";
      var defs = [
        { k: "P", label: "P", min: 0, max: 150, value: p.P },
        { k: "I", label: "I", min: 0, max: 200, value: p.I },
        { k: "D", label: "D", min: 0, max: 80, value: p.D },
        { k: "FF", label: "FF", min: 0, max: 250, value: p.FF },
        { k: "noise", label: "Шум гиро", min: 0, max: 15, value: p.noise, unit: "°/с" },
        { k: "lpf", label: "Gyro LPF", min: 30, max: 500, step: 10, value: p.lpf, unit: "Гц" }
      ];
      defs.forEach(function (d) {
        controls.appendChild(UAVPlot.slider({ label: d.label, min: d.min, max: d.max, step: d.step, value: d.value, unit: d.unit, onChange: function (v) { p[d.k] = v; self.update(); } }).el);
      });
      this.appendChild(controls);
      var c1 = document.createElement("canvas"); c1.className = "widget__canvas"; this.appendChild(c1);
      var c2 = document.createElement("canvas"); c2.className = "widget__canvas widget__canvas--small"; this.appendChild(c2);
      this.plot1 = UAVPlot.create(c1, { xLabel: "мс", yLabel: "°/с", height: 220 });
      this.plot2 = UAVPlot.create(c2, { xLabel: "мс", yLabel: "выход PID", height: 120 });
      var m = document.createElement("div"); m.className = "widget__metrics"; this.appendChild(m); this.metricsEl = m;
      var presets = document.createElement("div"); presets.className = "widget__presets";
      [["Базис", { P: 45, I: 60, D: 25, FF: 60, lpf: 150 }], ["Мало D", { P: 45, I: 60, D: 5, FF: 60 }], ["Много D + шум", { P: 45, I: 60, D: 70, FF: 60, noise: 8 }], ["Много P", { P: 130, I: 60, D: 25, FF: 60 }], ["Много I", { P: 45, I: 200, D: 25, FF: 60 }], ["Много FF", { P: 45, I: 60, D: 25, FF: 200 }], ["Тяжёлый фильтр", { P: 45, I: 60, D: 25, FF: 60, lpf: 40 }]].forEach(function (pr) {
        var b = document.createElement("button"); b.type = "button"; b.className = "gc-tag"; b.textContent = pr[0];
        b.addEventListener("click", function () {
          Object.keys(pr[1]).forEach(function (k) { p[k] = pr[1][k]; });
          if (!("noise" in pr[1])) p.noise = 2;
          if (!("lpf" in pr[1])) p.lpf = 150;
          controls.querySelectorAll("input").forEach(function (inp, i) { inp.value = p[defs[i].k]; inp.dispatchEvent(new Event("input")); });
        });
        presets.appendChild(b);
      });
      this.appendChild(presets);
      this.update();
      window.addEventListener("resize", function () { self.update(); });
    }

    update() {
      var r = simulate(this.p), mt = metrics(r);
      var stride = 4, x = [], sp = [], w = [], u = [];
      for (var i = 0; i < r.t.length; i += stride) { x.push(r.t[i]); sp.push(r.sp[i]); w.push(r.w[i]); u.push(r.u[i]); }
      this.plot1.draw({ x: x, series: [{ y: sp, color: "muted", label: "setpoint", dash: [4, 4] }, { y: w, color: "cyan", label: "gyro" }], yMin: -120, yMax: 420 });
      this.plot2.draw({ x: x, series: [{ y: u, color: "green", label: "команда моторам, %" }], yMin: -100, yMax: 100 });
      var cls = function (v, warn, bad) { return v >= bad ? "critical" : v >= warn ? "caution" : "ok"; };
      this.metricsEl.innerHTML =
        '<span class="gc-tag" data-state="' + (mt.lag === null ? "critical" : cls(mt.lag, 24, 30)) + '">entry lag ' + (mt.lag === null ? "—" : Math.round(mt.lag) + " мс") + "</span>" +
        '<span class="gc-tag" data-state="' + cls(mt.overshoot, 8, 20) + '">перелёт ' + mt.overshoot.toFixed(0) + "%</span>" +
        '<span class="gc-tag" data-state="' + cls(mt.bounce, 5, 12) + '">bounce-back ' + mt.bounce.toFixed(0) + "%</span>" +
        '<span class="gc-tag" data-state="' + cls(mt.settle, 120, 200) + '">установление ' + Math.round(mt.settle) + " мс</span>" +
        '<span class="gc-tag" data-state="' + cls(mt.noise, 20, 50) + '">шум моторов ' + mt.noise.toFixed(0) + "</span>";
    }
  }

  if (!customElements.get("uav-pid-sim")) customElements.define("uav-pid-sim", PidSim);
})();
