/*
 * <uav-attitude-3d>: wireframe quad rotated by roll/pitch/yaw sliders, with the equivalent
 * quaternion and rotation matrix shown live. Pure canvas, no dependencies.
 *
 * Conventions: body axes FRD (x forward, y right, z down), angles applied as yaw → pitch → roll
 * (ZYX), i.e. the usual aerospace Euler sequence. The quaternion is (w, x, y, z), unit norm.
 * Gimbal lock is demonstrated at pitch = ±90°: roll and yaw sliders then move the model the same way.
 */
(function () {
  "use strict";

  function eulerToQuat(r, p, y) {         // radians, ZYX
    var cr = Math.cos(r / 2), sr = Math.sin(r / 2), cp = Math.cos(p / 2), sp = Math.sin(p / 2), cy = Math.cos(y / 2), sy = Math.sin(y / 2);
    return [cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy];
  }
  function quatToMat(q) {                 // body -> world rotation matrix
    var w = q[0], x = q[1], y = q[2], z = q[3];
    return [
      [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
      [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
      [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]
    ];
  }
  function mul(M, v) { return [M[0][0] * v[0] + M[0][1] * v[1] + M[0][2] * v[2], M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2], M[2][0] * v[0] + M[2][1] * v[1] + M[2][2] * v[2]]; }

  // model in body frame (FRD): arms, arrow forward, motor circles
  var ARMS = [[[0.7, 0.7, 0], [-0.7, -0.7, 0]], [[0.7, -0.7, 0], [-0.7, 0.7, 0]]];
  var ARROW = [[0, 0, 0], [1.1, 0, 0]], ARROW_HEAD = [[[1.1, 0, 0], [0.9, 0.12, 0]], [[1.1, 0, 0], [0.9, -0.12, 0]]];
  var DOWN = [[0, 0, 0], [0, 0, 0.5]];
  var MOTORS = [[0.7, 0.7, 0], [0.7, -0.7, 0], [-0.7, -0.7, 0], [-0.7, 0.7, 0]];

  class Attitude3D extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = '<p class="gc-label gc-muted">Интерактив · ориентация: углы Эйлера ↔ кватернион</p>' +
        '<p class="widget__hint gc-muted">Крути roll/pitch/yaw (последовательность ZYX, оси FRD: x вперёд, y вправо, z вниз). Справа — кватернион (w, x, y, z) и матрица поворота. Поставь pitch = 90°: roll и yaw начинают вращать модель вокруг одной и той же оси — это gimbal lock, которого у кватерниона нет.</p>';
      var p = this.p = { roll: 20, pitch: 10, yaw: 30 };
      var sl = document.createElement("div"); sl.className = "widget__controls";
      ["roll", "pitch", "yaw"].forEach(function (k) {
        sl.appendChild(UAVPlot.slider({ label: k, min: -180, max: 180, step: 1, value: p[k], unit: "°", onChange: function (v) { p[k] = v; self.update(); } }).el);
      });
      this.appendChild(sl);
      var row = document.createElement("div"); row.className = "widget__row";
      var c = document.createElement("canvas"); c.className = "widget__canvas widget__canvas--cube"; row.appendChild(c); this.canvas = c;
      var info = document.createElement("div"); info.className = "widget__metrics"; row.appendChild(info); this.info = info;
      this.appendChild(row);
      var presets = document.createElement("div"); presets.className = "widget__presets";
      [["Горизонт", { roll: 0, pitch: 0, yaw: 0 }], ["Крен 45°", { roll: 45, pitch: 0, yaw: 0 }], ["Gimbal lock (pitch 90°)", { roll: 30, pitch: 90, yaw: 0 }], ["Переворот", { roll: 180, pitch: 0, yaw: 0 }]].forEach(function (pr) {
        var b = document.createElement("button"); b.type = "button"; b.className = "gc-tag"; b.textContent = pr[0];
        b.addEventListener("click", function () { Object.assign(p, pr[1]); sl.querySelectorAll("input").forEach(function (inp, i) { inp.value = p[["roll", "pitch", "yaw"][i]]; inp.dispatchEvent(new Event("input")); }); });
        presets.appendChild(b);
      });
      this.appendChild(presets);
      this.update();
      window.addEventListener("resize", function () { self.update(); });
    }

    update() {
      var p = this.p, d2r = Math.PI / 180;
      var q = eulerToQuat(p.roll * d2r, p.pitch * d2r, p.yaw * d2r), M = quatToMat(q);
      var c = this.canvas, dpr = window.devicePixelRatio || 1;
      var w = c.clientWidth || 300, h = 220; c.width = w * dpr; c.height = h * dpr; c.style.height = h + "px";
      var ctx = c.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
      var css = getComputedStyle(document.documentElement);
      var ink = css.getPropertyValue("--gc-ink").trim() || "#ddd", accent = css.getPropertyValue("--gc-accent").trim() || "#5ef", muted = css.getPropertyValue("--gc-ink-muted").trim() || "#888";
      // camera: world FRD -> screen. Look from behind-above-left: screen x = east-ish, screen y = up.
      var s = Math.min(w, h) * 0.32, cx = w / 2, cy = h / 2;
      function proj(v) { var wv = mul(M, v); // body -> world (x north, y east, z down)
        var xs = wv[1] * 0.9 - wv[0] * 0.45, ys = -(-wv[2]) * 0.9 + wv[0] * 0.3;  // simple oblique projection
        return [cx + xs * s, cy + ys * s]; }
      function line(a, b, color, width) { var A = proj(a), B = proj(b); ctx.strokeStyle = color; ctx.lineWidth = width; ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke(); }
      // ground reference (world frame, not rotated): a horizon line and world axes
      ctx.strokeStyle = muted; ctx.lineWidth = 1; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(cx - s * 1.4, cy); ctx.lineTo(cx + s * 1.4, cy); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = muted; ctx.font = "11px monospace"; ctx.fillText("горизонт", cx + s * 1.1, cy - 4);
      ARMS.forEach(function (a) { line(a[0], a[1], ink, 3); });
      line(ARROW[0], ARROW[1], accent, 3); ARROW_HEAD.forEach(function (a) { line(a[0], a[1], accent, 3); });
      line(DOWN[0], DOWN[1], "#e66", 2);
      MOTORS.forEach(function (m, i) { var P = proj(m); ctx.fillStyle = i % 2 ? ink : accent; ctx.beginPath(); ctx.arc(P[0], P[1], 5, 0, Math.PI * 2); ctx.fill(); });
      var f = function (v) { return (v >= 0 ? " " : "") + v.toFixed(3); };
      var lock = Math.abs(Math.abs(p.pitch) - 90) < 0.5;
      this.info.innerHTML = "<code>q = (" + f(q[0]) + "," + f(q[1]) + "," + f(q[2]) + "," + f(q[3]) + ")</code><br>" +
        "<code>R = [" + M.map(function (r) { return r.map(f).join(" "); }).join(" ; ") + "]</code><br>" +
        "<span class='gc-muted'>норма |q| = " + Math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]).toFixed(3) + " · стрелка — нос, красный отрезок — «вниз» в осях аппарата</span>" +
        (lock ? "<br><strong>Gimbal lock:</strong> при pitch = ±90° roll и yaw неразличимы для углов Эйлера; кватернион остаётся однозначным." : "");
    }
  }

  if (!customElements.get("uav-attitude-3d")) customElements.define("uav-attitude-3d", Attitude3D);
})();
