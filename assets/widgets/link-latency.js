/*
 * <uav-link-latency>: stick-to-motor latency chain.
 *
 * Each stage is modelled as an average delay:
 *   radio sampling   = 1/(2·rate_tx)          (half a frame on average)
 *   RF packet        = 1/rate_link             (one packet interval)
 *   RX → FC serial   = frame_bits / baud       (CRSF: ~26 bytes @ 420k ≈ 0.6 ms)
 *   RC smoothing     = user value (ms)         (Betaflight rc_smoothing / INAV filter)
 *   PID loop         = 1/(2·loop_hz)           (average wait for next loop)
 *   gyro + D filters = user value (ms)         (group delay, see ctl-signals)
 *   ESC protocol     = frame_time + 1/(2·rate) (DShot600 ≈ 0.03 ms + half interval)
 *   motor/prop       = tau (ms)                (time constant of thrust response)
 * Video chain is shown separately (typical published ranges, not measured).
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";

  var LINK = [
    { name: T("ELRS 50 Гц"), rate: 50 }, { name: T("ELRS 150 Гц"), rate: 150 }, { name: T("ELRS 250 Гц"), rate: 250 },
    { name: T("ELRS 500 Гц"), rate: 500 }, { name: "ELRS F1000", rate: 1000 }, { name: T("Crossfire 150 Гц"), rate: 150 },
    { name: T("SBUS/FrSky 111 Гц"), rate: 111 }
  ];
  var VIDEO = [
    { name: T("Аналог 5.8 ГГц"), ms: [3, 8] }, { name: T("Цифра (типичный режим)"), ms: [20, 40] }, { name: T("Цифра (low-latency)"), ms: [12, 25] }
  ];

  class LinkLatency extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = T('<p class="gc-label gc-muted">Интерактив · задержка от стика до мотора</p>') +
        T('<p class="widget__hint gc-muted">Сумма средних задержек по цепочке: пульт → радио → приёмник → FC (сглаживание, петля, фильтры) → ESC → мотор. Модель учебная: показывает, какие звенья реально весят. Видео — отдельной строкой, по типичным опубликованным диапазонам.</p>');
      var p = this.p = { link: 2, smooth: 4, loop: 8000, filt: 1.5, esc: 8000, tau: 20 };
      var sl = document.createElement("div"); sl.className = "widget__controls";
      function add(o) { var s = UAVPlot.slider(o); sl.appendChild(s.el); return s; }
      add({ label: T("Радиолинк"), min: 0, max: LINK.length - 1, step: 1, value: p.link, fmt: function (v) { return LINK[v].name; }, onChange: function (v) { p.link = v; self.update(); } });
      add({ label: "RC smoothing", min: 0, max: 20, step: 0.5, value: p.smooth, unit: T("мс"), fmt: function (v) { return (+v).toFixed(1); }, onChange: function (v) { p.smooth = v; self.update(); } });
      add({ label: "PID loop", min: 1000, max: 8000, step: 1000, value: p.loop, unit: T("Гц"), onChange: function (v) { p.loop = v; self.update(); } });
      add({ label: T("Фильтры gyro+D"), min: 0, max: 8, step: 0.25, value: p.filt, unit: T("мс"), fmt: function (v) { return (+v).toFixed(2); }, onChange: function (v) { p.filt = v; self.update(); } });
      add({ label: T("Мотор τ"), min: 5, max: 80, step: 1, value: p.tau, unit: T("мс"), onChange: function (v) { p.tau = v; self.update(); } });
      this.appendChild(sl);
      var c = document.createElement("canvas"); c.className = "widget__canvas widget__canvas--small"; this.appendChild(c);
      this.plot = UAVPlot.create(c, { xLabel: T("мс (накопленная задержка)"), yLabel: "", height: 110 });
      var tbl = document.createElement("div"); this.appendChild(tbl); this.tableEl = tbl;
      var m = document.createElement("div"); m.className = "widget__metrics"; this.appendChild(m); this.metricsEl = m;
      this.update();
      window.addEventListener("resize", function () { self.update(); });
    }

    stages() {
      var p = this.p, L = LINK[p.link];
      return [
        { name: T("Пульт (опрос стика)"), ms: 1000 / (2 * L.rate) },
        { name: T("Радио (интервал пакета)"), ms: 1000 / L.rate },
        { name: T("RX → FC (CRSF 420 кбод)"), ms: 26 * 10 / 420000 * 1000 },
        { name: "RC smoothing", ms: p.smooth },
        { name: "PID loop", ms: 1000 / (2 * p.loop) },
        { name: T("Фильтры gyro + D"), ms: p.filt },
        { name: "ESC (DShot600)", ms: 0.03 + 1000 / (2 * p.esc) },
        { name: T("Мотор / проп (τ)"), ms: p.tau }
      ];
    }

    update() {
      var st = this.stages(), total = st.reduce(function (a, s) { return a + s.ms; }, 0);
      var rows = st.map(function (s) { return "<tr><td>" + s.name + "</td><td>" + s.ms.toFixed(2) + T(" мс</td><td>") + (100 * s.ms / total).toFixed(0) + " %</td></tr>"; });
      this.tableEl.innerHTML = T('<div class="widget__table-wrap"><table class="widget__table"><thead><tr><th>Звено</th><th>Средняя задержка</th><th>Доля</th></tr></thead><tbody>') + rows.join("") + "</tbody></table></div>";
      // stacked timeline: one band per stage along x (ms)
      var x = [], y = [], acc = 0, bands = [];
      st.forEach(function (s, i) {
        x.push(acc); y.push(i + 1); x.push(acc + s.ms); y.push(i + 1);
        bands.push({ x0: acc, x1: acc + s.ms, label: "" });
        acc += s.ms;
      });
      this.plot.draw({ x: x, series: [{ y: y, label: T("звено №") }], bands: bands, xFmt: function (v) { return v.toFixed(0); } });
      var vid = VIDEO.map(function (v) { return v.name + ": " + v.ms[0] + "–" + v.ms[1] + T(" мс"); }).join(" · ");
      var biggest = st.slice().sort(function (a, b) { return b.ms - a.ms; })[0];
      this.metricsEl.innerHTML = T("<strong>Стик → мотор: ") + total.toFixed(1) + T(" мс</strong> · самое тяжёлое звено: ") + biggest.name + " (" + biggest.ms.toFixed(1) + T(" мс)<br><span class='gc-muted'>Видео, типично: ") + vid + T(". Задержка видео — отдельный контур: её видит пилот, а не PID.</span>");
    }
  }

  if (!customElements.get("uav-link-latency")) customElements.define("uav-link-latency", LinkLatency);
})();
