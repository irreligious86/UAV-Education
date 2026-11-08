/*
 * <uav-wire-drop>: voltage drop and heat in a copper wire run.
 *
 * R = ρ·L/S with ρ(Cu, 20 °C) = 0.0172 Ω·mm²/m; the return conductor doubles the
 * length (ΔU over + and −). P = I²·R. AWG cross-sections from the standard table.
 */
(function () {
  "use strict";

  var RHO = 0.0172; // Ω·mm²/m
  var AWG = [
    { awg: 10, mm2: 5.26 }, { awg: 12, mm2: 3.31 }, { awg: 14, mm2: 2.08 }, { awg: 16, mm2: 1.31 },
    { awg: 18, mm2: 0.823 }, { awg: 20, mm2: 0.518 }, { awg: 22, mm2: 0.326 }, { awg: 24, mm2: 0.205 },
    { awg: 26, mm2: 0.129 }, { awg: 28, mm2: 0.081 }
  ];

  class WireDrop extends HTMLElement {
    connectedCallback() {
      if (this._init) return; this._init = true;
      var self = this;
      this.classList.add("widget");
      this.innerHTML = '<p class="gc-label gc-muted">Интерактив · падение напряжения на проводе</p>' +
        '<p class="widget__hint gc-muted">Ток, длина одного провода (туда; обратный учитывается автоматически) и напряжение шины. Таблица — падение и тепло для каждого калибра. Правило: падение ≤ 2–3 % шины, тепло — не более нескольких ватт на коротком отрезке; на длинных жгутах крыла берут калибр крупнее.</p>';
      var p = this.p = { i: 60, len: 0.2, volts: 22.2, awg: 2 };
      var sl = document.createElement("div"); sl.className = "widget__controls";
      function add(o) { var s = UAVPlot.slider(o); sl.appendChild(s.el); return s; }
      add({ label: "Ток", min: 1, max: 200, step: 1, value: p.i, unit: "А", onChange: function (v) { p.i = v; self.update(); } });
      add({ label: "Длина", min: 0.05, max: 3, step: 0.05, value: p.len, unit: "м", fmt: function (v) { return (+v).toFixed(2); }, onChange: function (v) { p.len = v; self.update(); } });
      add({ label: "Шина", min: 3.7, max: 52, step: 0.1, value: p.volts, unit: "В", fmt: function (v) { return (+v).toFixed(1); }, onChange: function (v) { p.volts = v; self.update(); } });
      this.appendChild(sl);
      var tbl = document.createElement("div"); this.appendChild(tbl); this.tableEl = tbl;
      var m = document.createElement("div"); m.className = "widget__metrics"; this.appendChild(m); this.metricsEl = m;
      this.update();
    }

    update() {
      var p = this.p, self = this;
      var rows = AWG.map(function (w, idx) {
        var r = RHO * (2 * p.len) / w.mm2;        // Ω, both conductors
        var drop = p.i * r, heat = p.i * p.i * r, pct = 100 * drop / p.volts;
        var state = pct > 5 ? "critical" : pct > 2.5 ? "caution" : "ok";
        return '<tr class="' + (idx === p.awg ? "is-current" : "") + '" data-i="' + idx + '"><td>' + w.awg + "</td><td>" + w.mm2.toFixed(2) + "</td><td>" + (r * 1000).toFixed(1) + "</td><td>" + drop.toFixed(2) + "</td><td>" + pct.toFixed(1) + "</td><td>" + heat.toFixed(1) + '</td><td><span class="gc-tag" data-state="' + state + '">' + (state === "ok" ? "норма" : state === "caution" ? "много" : "нельзя") + "</span></td></tr>";
      }).join("");
      this.tableEl.innerHTML = '<div class="widget__table-wrap"><table class="widget__table"><thead><tr><th>AWG</th><th>мм²</th><th>R, мОм</th><th>ΔU, В</th><th>% шины</th><th>Тепло, Вт</th><th></th></tr></thead><tbody>' + rows + "</tbody></table></div>";
      this.tableEl.querySelectorAll("tr[data-i]").forEach(function (tr) { tr.style.cursor = "pointer"; tr.addEventListener("click", function () { p.awg = +tr.getAttribute("data-i"); self.update(); }); });
      var w = AWG[p.awg], r = RHO * (2 * p.len) / w.mm2, drop = p.i * r;
      this.metricsEl.innerHTML =
        '<span class="gc-tag" data-state="info">' + w.awg + " AWG · " + p.i + " А · " + p.len.toFixed(2) + " м</span>" +
        '<span class="gc-tag">R = ' + (r * 1000).toFixed(1) + " мОм (оба провода)</span>" +
        '<span class="gc-tag">ΔU = ' + drop.toFixed(2) + " В</span>" +
        '<span class="gc-tag">P = ' + (p.i * p.i * r).toFixed(1) + " Вт тепла</span>" +
        '<span class="gc-tag gc-muted">ρ меди 0.0172 Ом·мм²/м при 20 °C; при 60 °C — ещё +16 %</span>';
    }
  }

  if (!customElements.get("uav-wire-drop")) customElements.define("uav-wire-drop", WireDrop);
})();
