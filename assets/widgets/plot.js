/*
 * Minimal canvas line plot used by all widgets. Theme-aware via --gc-* tokens,
 * HiDPI-aware, no dependencies.
 *
 *   var plot = UAVPlot.create(canvasEl, { xLabel: "мс", yLabel: "°/с" });
 *   plot.draw({ x: [..], series: [{ y: [..], color: "cyan", label: "gyro" }], xTicks, yTicks, bands: [{x0,x1,label}] });
 */
(function () {
  "use strict";

  function token(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  var COLORS = {
    ink: function () { return token("--gc-ink", "#e6ebe4"); },
    muted: function () { return token("--gc-ink-muted", "#8a948a"); },
    line: function () { return token("--gc-line", "#2a332b"); },
    cyan: function () { return token("--gc-signal-cyan", "#5ad0ff"); },
    green: function () { return token("--gc-accent-hud", "#9be564"); },
    amber: function () { return token("--gc-signal-amber", "#ffb547"); },
    red: function () { return token("--gc-signal-red", "#ff5d5d"); }
  };

  function create(canvas, opts) {
    opts = opts || {};
    var ctx = canvas.getContext("2d");
    var pad = { l: 44, r: 12, t: 12, b: 30 };

    function size() {
      var dpr = window.devicePixelRatio || 1;
      var w = canvas.clientWidth || 320, h = opts.height || 220;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { w: w, h: h };
    }

    function niceTicks(min, max, n) {
      var span = max - min || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
      var norm = raw / mag, step = norm < 1.5 ? 1 : norm < 3.5 ? 2 : norm < 7.5 ? 5 : 10;
      step *= mag;
      var out = [], t = Math.ceil(min / step) * step;
      for (; t <= max + 1e-9; t += step) out.push(+t.toFixed(6));
      return out;
    }

    function draw(d) {
      var s = size(), w = s.w, h = s.h;
      var x = d.x, xmin = d.xMin != null ? d.xMin : x[0], xmax = d.xMax != null ? d.xMax : x[x.length - 1];
      var ymin = d.yMin, ymax = d.yMax;
      if (ymin == null || ymax == null) {
        ymin = Infinity; ymax = -Infinity;
        d.series.forEach(function (sr) { sr.y.forEach(function (v) { if (isFinite(v)) { if (v < ymin) ymin = v; if (v > ymax) ymax = v; } }); });
        if (!isFinite(ymin)) { ymin = 0; ymax = 1; }
        var m = (ymax - ymin) * 0.08 || 1; ymin -= m; ymax += m;
        if (d.yMin != null) ymin = d.yMin; if (d.yMax != null) ymax = d.yMax;
      }
      var X = function (v) { return pad.l + (v - xmin) / (xmax - xmin) * (w - pad.l - pad.r); };
      var Y = function (v) { return h - pad.b - (v - ymin) / (ymax - ymin) * (h - pad.t - pad.b); };

      ctx.clearRect(0, 0, w, h);
      // bands
      (d.bands || []).forEach(function (b) {
        ctx.fillStyle = b.color || "rgba(255,181,71,0.12)";
        ctx.fillRect(X(b.x0), pad.t, X(b.x1) - X(b.x0), h - pad.t - pad.b);
        if (b.label) { ctx.fillStyle = COLORS.amber(); ctx.font = "11px " + token("--gc-font-mono", "monospace"); ctx.fillText(b.label, X(b.x0) + 4, pad.t + 12); }
      });
      // grid + ticks
      ctx.strokeStyle = COLORS.line(); ctx.lineWidth = 1; ctx.fillStyle = COLORS.muted();
      ctx.font = "11px " + token("--gc-font-mono", "monospace");
      var yt = d.yTicks || niceTicks(ymin, ymax, 4), xt = d.xTicks || niceTicks(xmin, xmax, 5);
      yt.forEach(function (t) { var yy = Y(t); ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(w - pad.r, yy); ctx.stroke(); ctx.textAlign = "right"; ctx.fillText(d.yFmt ? d.yFmt(t) : String(t), pad.l - 6, yy + 4); });
      xt.forEach(function (t) { var xx = X(t); ctx.beginPath(); ctx.moveTo(xx, pad.t); ctx.lineTo(xx, h - pad.b); ctx.stroke(); ctx.textAlign = "center"; ctx.fillText(d.xFmt ? d.xFmt(t) : String(t), xx, h - pad.b + 16); });
      if (opts.xLabel) { ctx.textAlign = "right"; ctx.fillText(opts.xLabel, w - pad.r, h - 4); }
      if (opts.yLabel) { ctx.textAlign = "left"; ctx.fillText(opts.yLabel, 4, pad.t + 4); }
      // series
      d.series.forEach(function (sr) {
        ctx.strokeStyle = COLORS[sr.color] ? COLORS[sr.color]() : (sr.color || COLORS.ink());
        ctx.lineWidth = sr.width || 2; ctx.setLineDash(sr.dash || []);
        ctx.beginPath(); var started = false;
        for (var i = 0; i < sr.y.length; i++) {
          var v = sr.y[i]; if (!isFinite(v)) { started = false; continue; }
          var px = X(x[i]), py = Math.max(pad.t - 2, Math.min(h - pad.b + 2, Y(v)));
          if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
        }
        ctx.stroke(); ctx.setLineDash([]);
      });
      // legend
      var lx = pad.l + 6, ly = pad.t + 6;
      d.series.forEach(function (sr) {
        if (!sr.label) return;
        ctx.fillStyle = COLORS[sr.color] ? COLORS[sr.color]() : (sr.color || COLORS.ink());
        ctx.fillRect(lx, ly + 3, 14, 3); ctx.fillStyle = COLORS.ink(); ctx.textAlign = "left";
        ctx.fillText(sr.label, lx + 18, ly + 8); lx += 18 + ctx.measureText(sr.label).width + 14;
      });
    }

    return { draw: draw, size: size };
  }

  // Shared slider row builder: label, range input, live value
  function slider(opts) {
    var row = document.createElement("label"); row.className = "widget__slider";
    var name = document.createElement("span"); name.className = "widget__slider-name"; name.textContent = opts.label;
    var input = document.createElement("input"); input.type = "range";
    input.min = opts.min; input.max = opts.max; input.step = opts.step || 1; input.value = opts.value;
    var val = document.createElement("span"); val.className = "widget__slider-val gc-tag";
    function show() { val.textContent = (opts.fmt ? opts.fmt(+input.value) : input.value) + (opts.unit ? " " + opts.unit : ""); }
    input.addEventListener("input", function () { show(); opts.onChange(+input.value); });
    show();
    row.appendChild(name); row.appendChild(input); row.appendChild(val);
    return { el: row, input: input, refresh: show };
  }

  window.UAVPlot = { create: create, slider: slider, colors: COLORS };
})();
