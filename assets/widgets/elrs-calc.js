/*
 * <uav-elrs-calc>: ExpressLRS link calculator.
 *
 * Packet rate -> packet interval; telemetry ratio -> telemetry interval
 * (interval_ms = ratio * 1000 / rate, as in the ELRS "Telemetry Bandwidth" doc);
 * plus a sensitivity table for 2.4 GHz modes. Sensitivity figures are the published
 * ELRS 3.x values per mode (dBm) — treat as reference, not a measurement.
 * Range scaling: free-space, every +6 dB of link budget ≈ ×2 distance.
 */
var T = (typeof window !== "undefined" && window.T) || function (s) { return s; };   // assets/i18n.js
(function () {
  "use strict";

  // 2.4 GHz modes: name, rate (Hz), sensitivity (dBm), kind
  // Source: expresslrs.org/info/signal-health (Sensitivity Limit per mode, ELRS 3.x)
  var MODES_24 = [
    { name: "50Hz", rate: 50, sens: -115, kind: "LoRa" },
    { name: "100Hz Full", rate: 100, sens: -112, kind: T("LoRa, полное разрешение") },
    { name: "150Hz", rate: 150, sens: -112, kind: "LoRa" },
    { name: "250Hz", rate: 250, sens: -108, kind: "LoRa" },
    { name: "333Hz Full", rate: 333, sens: -105, kind: T("LoRa, полное разрешение") },
    { name: "500Hz", rate: 500, sens: -105, kind: "LoRa" },
    { name: "D250", rate: 250, sens: -104, kind: T("DVDA (пакет ×2)") },
    { name: "D500", rate: 500, sens: -104, kind: T("DVDA (пакет ×2)") },
    { name: "F500", rate: 500, sens: -104, kind: "FLRC" },
    { name: "F1000", rate: 1000, sens: -104, kind: "FLRC" }
  ];
  var MODES_900 = [
    { name: "25Hz", rate: 25, sens: -123, kind: "LoRa" },
    { name: "50Hz", rate: 50, sens: -120, kind: "LoRa" },
    { name: "100Hz", rate: 100, sens: -117, kind: "LoRa" },
    { name: "100Hz Full", rate: 100, sens: -112, kind: T("LoRa, полное разрешение") },
    { name: "200Hz", rate: 200, sens: -112, kind: "LoRa" },
    { name: "200Hz Full", rate: 200, sens: -111, kind: T("LoRa, полное разрешение") },
    { name: "250Hz", rate: 250, sens: -111, kind: "LoRa" }
  ];
  var RATIOS = [2, 4, 8, 16, 32, 64, 128, 256];

  class ElrsCalc extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = T('<p class="gc-label gc-muted">Интерактив · калькулятор линка ExpressLRS</p>') +
        T('<p class="widget__hint gc-muted">Выбери диапазон, режим, мощность и telemetry ratio. Таблица показывает интервал пакетов, интервал телеметрии и относительную дальность по чувствительности режима (каждые +6 дБ бюджета ≈ ×2 дистанции в свободном пространстве). Чувствительности — из таблицы ExpressLRS «Signal Health»; это нижняя граница RSSI, при которой линк ещё жив, предупреждение ставят на 5–10 дБ выше.</p>');
      var p = this.p = { band: "24", mode: 3, power: 100, ratio: 128 };
      var controls = document.createElement("div"); controls.className = "widget__presets";
      var bandBtns = {};
      [["24", T("2.4 ГГц")], ["900", T("900 МГц")]].forEach(function (b) {
        var btn = document.createElement("button"); btn.type = "button"; btn.className = "gc-tag"; btn.textContent = b[1];
        btn.addEventListener("click", function () { p.band = b[0]; p.mode = 0; self.update(); });
        controls.appendChild(btn); bandBtns[b[0]] = btn;
      });
      this.bandBtns = bandBtns;
      this.appendChild(controls);
      var sl = document.createElement("div"); sl.className = "widget__controls";
      var powers = [10, 25, 50, 100, 250, 500, 1000];
      this.powerSlider = UAVPlot.slider({ label: T("Мощность TX"), min: 0, max: powers.length - 1, step: 1, value: 3, unit: T("мВт"), fmt: function (v) { return powers[v]; }, onChange: function (v) { p.power = powers[v]; self.update(); } });
      sl.appendChild(this.powerSlider.el);
      this.ratioSlider = UAVPlot.slider({ label: "Telem ratio 1:", min: 0, max: RATIOS.length - 1, step: 1, value: 6, fmt: function (v) { return RATIOS[v]; }, onChange: function (v) { p.ratio = RATIOS[v]; self.update(); } });
      sl.appendChild(this.ratioSlider.el);
      this.appendChild(sl);
      var tbl = document.createElement("div"); this.appendChild(tbl); this.tableEl = tbl;
      var m = document.createElement("div"); m.className = "widget__metrics"; this.appendChild(m); this.metricsEl = m;
      this.update();
    }

    update() {
      var p = this.p, modes = p.band === "24" ? MODES_24 : MODES_900, self = this;
      Object.keys(this.bandBtns).forEach(function (k) { self.bandBtns[k].setAttribute("data-state", k === p.band ? "ok" : ""); });
      var ref = modes[p.mode];
      var txDbm = 10 * Math.log10(p.power);
      var rows = modes.map(function (m, i) {
        var budget = txDbm - m.sens;                                 // dB, antennas/path ignored (relative)
        var refBudget = txDbm - ref.sens;
        var rel = Math.pow(10, (budget - refBudget) / 20);           // ×2 per +6 dB
        var pkt = 1000 / m.rate, tel = p.ratio * 1000 / m.rate;
        return '<tr class="' + (i === p.mode ? "is-current" : "") + '" data-i="' + i + '"><td>' + m.name + "</td><td>" + m.kind + "</td><td>" + pkt.toFixed(1) + "</td><td>" + tel.toFixed(0) + "</td><td>" + m.sens + "</td><td>×" + rel.toFixed(2) + "</td></tr>";
      }).join("");
      this.tableEl.innerHTML = T('<div class="widget__table-wrap"><table class="widget__table"><thead><tr><th>Режим</th><th>Тип</th><th>Пакет, мс</th><th>Телем., мс</th><th>Чувств., дБм</th><th>Дальность отн.</th></tr></thead><tbody>') + rows + "</tbody></table></div>";
      this.tableEl.querySelectorAll("tr[data-i]").forEach(function (tr) { tr.style.cursor = "pointer"; tr.addEventListener("click", function () { p.mode = +tr.getAttribute("data-i"); self.update(); }); });
      var budget = txDbm - ref.sens;
      var linkPkt = 1000 / ref.rate, tel = p.ratio * 1000 / ref.rate;
      var tcls = tel <= 300 ? "ok" : tel <= 1000 ? "caution" : "critical";
      this.metricsEl.innerHTML =
        T('<span class="gc-tag" data-state="info">выбран ') + ref.name + " @ " + p.power + T(" мВт</span>") +
        T('<span class="gc-tag">бюджет без антенн ') + budget.toFixed(0) + T(" дБ</span>") +
        T('<span class="gc-tag">пакет каждые ') + linkPkt.toFixed(1) + T(" мс</span>") +
        '<span class="gc-tag" data-state="' + tcls + T('">телеметрия каждые ') + tel.toFixed(0) + T(" мс</span>") +
        T('<span class="gc-tag" data-state="caution">предупреждение RSSI ставь на ') + (ref.sens + 8) + T(" дБм (порог + 5…10)</span>") +
        T('<span class="gc-tag">+6 дБ мощности ≈ ×2 дальности</span>');
    }
  }

  if (!customElements.get("uav-elrs-calc")) customElements.define("uav-elrs-calc", ElrsCalc);
})();
