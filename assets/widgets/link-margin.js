/*
 * <uav-link-margin>: free-space link budget vs distance.
 *
 * Prx = Ptx + Gtx + Grx − L − FSPL,  FSPL(dB) = 20·log10(d_km) + 20·log10(f_MHz) + 32.44.
 * Margin = Prx − sensitivity. Free space is the optimistic bound: terrain, Fresnel-zone blockage,
 * body shadowing and interference eat into the margin, which is why ~10 dB is kept in reserve.
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";

  class LinkMargin extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = T('<p class="gc-label gc-muted">Интерактив · бюджет линка и запас от дистанции</p>') +
        T('<p class="widget__hint gc-muted">Свободное пространство — оптимистичная граница: рельеф, зона Френеля, корпус и помехи забирают своё, поэтому в полёте держат запас ~10 дБ. Каждые 6 дБ запаса — вдвое больше дальности.</p>');
      var p = this.p = { f: 2440, ptx: 24, gtx: 2, grx: 0, loss: 4, sens: -112 };
      var c = document.createElement("div"); c.className = "widget__controls"; this.controls = c;
      var defs = [
        { k: "f", label: T("Частота"), min: 400, max: 5900, step: 10, unit: T("МГц") },
        { k: "ptx", label: T("Мощность"), min: 0, max: 33, step: 1, unit: T("дБм"), fmt: function (v) { return v + " (" + (Math.pow(10, v / 10)).toFixed(0) + T(" мВт)"); } },
        { k: "gtx", label: T("Антенна передатчика"), min: -3, max: 15, step: 0.5, unit: T("дБи") },
        { k: "grx", label: T("Антенна приёмника"), min: -3, max: 15, step: 0.5, unit: T("дБи") },
        { k: "loss", label: T("Потери (кабели, поляризация)"), min: 0, max: 20, step: 0.5, unit: T("дБ") },
        { k: "sens", label: T("Чувствительность"), min: -130, max: -80, step: 1, unit: T("дБм") }];
      defs.forEach(function (d) { c.appendChild(UAVPlot.slider({ label: d.label, min: d.min, max: d.max, step: d.step, value: p[d.k], unit: d.unit, fmt: d.fmt, onChange: function (v) { p[d.k] = v; self.update(); } }).el); });
      this.appendChild(c);
      var b = document.createElement("div"); b.className = "widget__presets";
      [[T("ELRS 2.4 ГГц 250 мВт, 150 Гц"), { f: 2440, ptx: 24, gtx: 2, grx: 0, loss: 4, sens: -112 }],
       [T("ELRS 900 МГц 100 мВт, 50 Гц"), { f: 915, ptx: 20, gtx: 2, grx: 0, loss: 4, sens: -123 }],
       [T("SiK 433 МГц 100 мВт, 64 кбит/с"), { f: 433, ptx: 20, gtx: 2, grx: 2, loss: 3, sens: -102 }],
       [T("Видео 5.8 ГГц 600 мВт"), { f: 5800, ptx: 28, gtx: 2, grx: 8, loss: 3, sens: -90 }]].forEach(function (pr) {
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
      this.plot = UAVPlot.create(cv, { xLabel: T("км (лог.)"), yLabel: T("запас, дБ"), height: 240 });
      this.update();
      window.addEventListener("resize", function () { self.update(); });
    }

    margin(dkm) {
      var p = this.p;
      return p.ptx + p.gtx + p.grx - p.loss - (20 * Math.log10(dkm) + 20 * Math.log10(p.f) + 32.44) - p.sens;
    }

    update() {
      var self = this, xs = [], ys = [], zero = [], ten = [];
      for (var lg = -1; lg <= 2.0001; lg += 0.02) { xs.push(lg); ys.push(this.margin(Math.pow(10, lg))); zero.push(0); ten.push(10); }
      var m0 = this.margin(1);                    // margin at 1 km; range for margin M: d = 10^((m0 − M)/20) km
      var dist = function (M) { return Math.pow(10, (m0 - M) / 20); };
      var fmt = function (d) { return d >= 10 ? d.toFixed(0) : d >= 1 ? d.toFixed(1) : (d * 1000).toFixed(0) + T(" м"); };
      var unit = function (d) { return d >= 1 ? T(" км") : ""; };
      var d0 = dist(0), d10 = dist(10);
      this.metricsEl.innerHTML =
        T('<span class="gc-tag" data-state="info">запас на 1 км ') + m0.toFixed(1) + T(' дБ</span>') +
        T('<span class="gc-tag" data-state="ok">с запасом 10 дБ: ') + fmt(d10) + unit(d10) + '</span>' +
        T('<span class="gc-tag" data-state="caution">предел (0 дБ): ') + fmt(d0) + unit(d0) + '</span>';
      this.plot.draw({
        x: xs, yMin: -20, yMax: 60,
        xTicks: [-1, 0, 1, 1.699, 2], xFmt: function (v) { return String(+Math.pow(10, v).toPrecision(2)); },
        series: [{ y: ys, color: "cyan", label: T("запас") }, { y: ten, color: "green", width: 1, dash: [4, 4], label: T("10 дБ") }, { y: zero, color: "red", width: 1, dash: [4, 4], label: T("0 дБ") }]
      });
    }
  }

  if (!customElements.get("uav-link-margin")) customElements.define("uav-link-margin", LinkMargin);
})();
