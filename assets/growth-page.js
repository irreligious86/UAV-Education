/* Course growth page (curriculum/growth.html). Reads docs/activity/activity.json built by
   scripts/build_activity.py and draws plain SVG charts; no libraries. */
(function () {
  'use strict';
  var SVGNS = 'http://www.w3.org/2000/svg';
  var KINDS = ['new', 'deepen', 'fix', 'i18n', 'visual', 'infra'];
  var KIND_NAME = { new: 'Новый модуль', deepen: 'Углубление', fix: 'Исправление', i18n: 'Перевод', visual: 'Диаграммы', infra: 'Инфраструктура' };
  var SECTION_ORDER = ['foundation', 'betaflight', 'inav', 'ardupilot', 'px4', 'companion', 'link', 'electronics', 'estimation', 'math', 'ros2', 'design', 'tools'];
  var PAGE = 40;
  var state = { kind: '', section: '', shown: PAGE };
  var data = null;
  var titles = {};

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function svgEl(tag, attrs) { var e = document.createElementNS(SVGNS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); return e; }
  function fmt(n) { return Math.round(n).toLocaleString('ru-RU'); }
  function short(n) { return n >= 1e6 ? (n / 1e6).toFixed(2).replace('.', ',') + ' млн' : n >= 1e4 ? Math.round(n / 1e3) + ' тыс.' : fmt(n); }
  function dayLabel(d) { return d.slice(8, 10) + '.' + d.slice(5, 7); }
  function secVar(s) { return SECTION_ORDER.indexOf(s) >= 0 ? 'var(--s-' + s + ')' : 'var(--k-infra)'; }
  function kindVar(k) { return 'var(--k-' + (KIND_NAME[k] ? k : 'infra') + ')'; }

  var tip = null;
  function showTip(ev, html) {
    tip.replaceChildren();
    html.forEach(function (line) { var p = el('div'); line.forEach(function (part) { p.append(part.b ? el('b', null, part.t) : document.createTextNode(part.t)); }); tip.append(p); });
    tip.hidden = false;
    var x = Math.min(window.innerWidth - tip.offsetWidth - 8, ev.clientX + 12);
    var y = Math.max(8, ev.clientY - tip.offsetHeight - 10);
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  function hideTip() { tip.hidden = true; }

  function summary() {
    var d = data.daily, last = d[d.length - 1];
    var cut = new Date(Date.parse(last.day + 'T00:00:00Z') - 7 * 864e5).toISOString().slice(0, 10);
    var before = d.filter(function (r) { return r.day <= cut; }).pop() || { modules_total: 0, words_total: 0, diagrams_total: 0 };
    var recent = d.filter(function (r) { return r.day > cut; });
    function sum(rs, k) { return rs.reduce(function (s, r) { return s + (r[k] || 0); }, 0); }
    return {
      last: last,
      modules7: last.modules_total - before.modules_total,
      words7: last.words_total - before.words_total,
      diagrams7: last.diagrams_total - before.diagrams_total,
      commits: data.commits.length,
      commits7: data.commits.filter(function (c) { return c.day > cut; }).length,
      errors: sum(d, 'fc_errors'), imprecise: sum(d, 'fc_imprecise'), nits: sum(d, 'fc_nits'),
      errors7: sum(recent, 'fc_errors')
    };
  }

  function renderHead(s) {
    var lede = $('gr-lede'); lede.replaceChildren();
    var parts = [['Сейчас в курсе '], [fmt(s.last.modules_total), 1], [' модулей и '], [short(s.last.words_total), 1], [' слов. За последние 7 дней прибавилось '], ['+' + short(s.words7), 1], [' слов, а проверки фактов нашли и исправили '], [fmt(s.errors7), 1], [' ошибок.']];
    parts.forEach(function (p) { lede.append(p[1] ? el('b', null, p[0]) : document.createTextNode(p[0])); });
    $('gr-meta').textContent = 'Данные на ' + data.generated_at.replace('T', ' ').slice(0, 16) + ' UTC, коммит ' + data.head + '.';
    var k = $('gr-kpis'); k.replaceChildren();
    [['Модулей', fmt(s.last.modules_total), s.modules7], ['Слов', short(s.last.words_total), s.words7], ['Диаграмм', fmt(s.last.diagrams_total), s.diagrams7], ['Коммитов', fmt(s.commits), s.commits7]].forEach(function (c) {
      var card = el('div', 'gr-kpi');
      card.append(el('span', 'gr-kpi-label', c[0]), el('span', 'gr-kpi-value', c[1]));
      card.append(el('span', 'gr-kpi-delta' + (c[2] > 0 ? '' : ' flat'), c[2] > 0 ? '+' + (c[0] === 'Слов' ? short(c[2]) : fmt(c[2])) + ' за 7 дней' : 'без изменений за 7 дней'));
      k.append(card);
    });
    var fc = el('div', 'gr-kpi');
    fc.append(el('span', 'gr-kpi-label', 'Найдено проверками'), el('span', 'gr-kpi-value', fmt(s.errors) + ' ошибок'), el('span', 'gr-kpi-delta flat', fmt(s.imprecise) + ' неточностей и ' + fmt(s.nits) + ' мелочей'));
    k.append(fc);
  }

  function lastSections() {
    var day = data.daily[data.daily.length - 1].day;
    var rows = data.sections.filter(function (r) { return r.day === day; });
    rows.sort(function (a, b) { return b.words - a.words; });
    return rows;
  }

  function renderSections() {
    var box = $('gr-sections'); box.replaceChildren();
    var rows = lastSections();
    var max = Math.max.apply(null, rows.map(function (r) { return r.words; }));
    rows.forEach(function (r) {
      var b = el('button', 'gr-sec'); b.type = 'button';
      b.style.setProperty('--sec', secVar(r.section));
      b.setAttribute('aria-pressed', state.section === r.section ? 'true' : 'false');
      var sw = el('span', 'gr-sec-swatch');
      var bar = el('span', 'gr-sec-bar'); var fill = el('i'); fill.style.width = (100 * r.words / max).toFixed(1) + '%'; bar.append(fill);
      b.append(sw, el('span', 'gr-sec-name', r.title), el('span', 'gr-sec-mods', fmt(r.modules) + ' мод.'), bar, el('span', 'gr-sec-words', short(r.words) + ' слов'));
      b.addEventListener('click', function () {
        state.section = state.section === r.section ? '' : r.section;
        $('gr-section').value = state.section; state.shown = PAGE;
        renderSections(); renderFeed();
      });
      box.append(b);
    });
  }

  function frame(box, H, label, padLeft) {
    var W = Math.max(320, box.clientWidth || 600);
    var m = { t: 10, r: 12, b: 26, l: padLeft || 46 };
    var svg = svgEl('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': label });
    box.replaceChildren(svg);
    return { svg: svg, W: W, H: H, m: m };
  }
  function yAxis(f, max, ticks, fmtTick) {
    var g = svgEl('g', { class: 'grid' }), a = svgEl('g', { class: 'axis' });
    for (var i = 0; i <= ticks; i++) {
      var v = max * i / ticks, y = f.H - f.m.b - (f.H - f.m.t - f.m.b) * i / ticks;
      g.append(svgEl('line', { x1: f.m.l, x2: f.W - f.m.r, y1: y, y2: y }));
      var t = svgEl('text', { x: f.m.l - 6, y: y + 4, 'text-anchor': 'end' }); t.textContent = fmtTick(v); a.append(t);
    }
    f.svg.append(g, a);
  }
  function niceMax(v) { if (v <= 0) return 1; var p = Math.pow(10, Math.floor(Math.log10(v))); var n = v / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p; }
  function xLabels(f, days, xAt) {
    var a = svgEl('g', { class: 'axis' });
    var every = Math.max(1, Math.ceil(days.length / Math.max(2, Math.floor((f.W - f.m.l) / 52))));
    days.forEach(function (d, i) {
      if (i % every && i !== days.length - 1) return;
      var t = svgEl('text', { x: xAt(i), y: f.H - 8, 'text-anchor': 'middle' }); t.textContent = dayLabel(d); a.append(t);
    });
    f.svg.append(a);
  }

  function renderArea() {
    var box = $('gr-area');
    var days = data.daily.map(function (r) { return r.day; });
    var secs = SECTION_ORDER.filter(function (s) { return data.sections.some(function (r) { return r.section === s; }); });
    data.sections.forEach(function (r) { if (secs.indexOf(r.section) < 0) secs.push(r.section); });
    var by = {}; data.sections.forEach(function (r) { (by[r.day] = by[r.day] || {})[r.section] = r.words; });
    var f = frame(box, 300, 'Слова по разделам курса на каждый день с коммитами', 58);
    var max = niceMax(Math.max.apply(null, data.daily.map(function (r) { return r.words_total; })));
    yAxis(f, max, 4, short);
    var iw = f.W - f.m.l - f.m.r, ih = f.H - f.m.t - f.m.b;
    function x(i) { return f.m.l + (days.length === 1 ? iw / 2 : iw * i / (days.length - 1)); }
    function y(v) { return f.H - f.m.b - ih * v / max; }
    var base = days.map(function () { return 0; });
    secs.forEach(function (s) {
      var top = days.map(function (d, i) { return base[i] + ((by[d] || {})[s] || 0); });
      var pts = days.map(function (d, i) { return x(i) + ',' + y(top[i]); }).concat(days.map(function (d, i) { return x(days.length - 1 - i) + ',' + y(base[days.length - 1 - i]); }));
      var poly = svgEl('polygon', { points: pts.join(' ') }); poly.style.fill = secVar(s); poly.style.fillOpacity = '0.85'; poly.style.stroke = 'var(--card)'; poly.style.strokeWidth = '0.5';
      f.svg.append(poly);
      base = top;
    });
    xLabels(f, days, x);
    var cursor = svgEl('line', { y1: f.m.t, y2: f.H - f.m.b, stroke: 'var(--text)', 'stroke-opacity': '0.35', visibility: 'hidden' });
    f.svg.append(cursor);
    var hit = svgEl('rect', { x: f.m.l, y: f.m.t, width: iw, height: ih, fill: 'transparent' });
    hit.addEventListener('pointermove', function (ev) {
      var r = f.svg.getBoundingClientRect(), px = (ev.clientX - r.left) * f.W / r.width;
      var i = Math.max(0, Math.min(days.length - 1, Math.round((px - f.m.l) / (iw / Math.max(1, days.length - 1)))));
      cursor.setAttribute('x1', x(i)); cursor.setAttribute('x2', x(i)); cursor.setAttribute('visibility', 'visible');
      var d = days[i], lines = [[{ t: dayLabel(d) + ': ' }, { t: short(data.daily[i].words_total) + ' слов', b: 1 }]];
      secs.slice().reverse().forEach(function (s) { var v = (by[d] || {})[s]; if (v) lines.push([{ t: (titles[s] || s) + ' ' }, { t: short(v), b: 1 }]); });
      showTip(ev, lines);
    });
    hit.addEventListener('pointerleave', function () { cursor.setAttribute('visibility', 'hidden'); hideTip(); });
    f.svg.append(hit);
  }

  function stackedBars(box, rows, keys, colorOf, nameOf, label) {
    var f = frame(box, 240, label, 36);
    var totals = rows.map(function (r) { return keys.reduce(function (s, k) { return s + (r[k] || 0); }, 0); });
    var max = niceMax(Math.max.apply(null, totals.concat([1])));
    yAxis(f, max, 4, function (v) { return String(Math.round(v)); });
    var iw = f.W - f.m.l - f.m.r, ih = f.H - f.m.t - f.m.b, step = iw / rows.length, bw = Math.max(3, step * 0.7);
    function xc(i) { return f.m.l + step * (i + 0.5); }
    rows.forEach(function (r, i) {
      var acc = 0;
      keys.forEach(function (k) {
        var v = r[k] || 0; if (!v) return;
        var y1 = f.H - f.m.b - ih * (acc + v) / max, h = ih * v / max;
        var rect = svgEl('rect', { x: xc(i) - bw / 2, y: y1, width: bw, height: Math.max(0, h), rx: 1.5 }); rect.style.fill = colorOf(k);
        rect.addEventListener('pointermove', function (ev) {
          var lines = [[{ t: dayLabel(r.day) + ': ' }, { t: String(totals[i]), b: 1 }]];
          keys.forEach(function (kk) { if (r[kk]) lines.push([{ t: nameOf(kk) + ' ' }, { t: String(r[kk]), b: 1 }]); });
          showTip(ev, lines);
        });
        rect.addEventListener('pointerleave', hideTip);
        f.svg.append(rect);
        acc += v;
      });
    });
    xLabels(f, rows.map(function (r) { return r.day; }), xc);
  }

  function legend(box, keys, colorOf, nameOf) {
    box.replaceChildren();
    keys.forEach(function (k) { var s = el('span'); var i = el('i'); i.style.background = colorOf(k); s.append(i, document.createTextNode(nameOf(k))); box.append(s); });
  }

  function renderKinds() {
    var by = {};
    data.commits.forEach(function (c) { var r = by[c.day] = by[c.day] || { day: c.day }; r[c.kind] = (r[c.kind] || 0) + 1; });
    var rows = Object.keys(by).sort().map(function (d) { return by[d]; });
    legend($('gr-kinds-legend'), KINDS, kindVar, function (k) { return KIND_NAME[k]; });
    stackedBars($('gr-kinds'), rows, KINDS, kindVar, function (k) { return KIND_NAME[k]; }, 'Коммиты по видам работы за каждый день с коммитами');
  }

  function renderFc() {
    var rows = data.daily.filter(function (r) { return r.fc_errors + r.fc_imprecise + r.fc_nits > 0; })
      .map(function (r) { return { day: r.day, e: r.fc_errors, i: r.fc_imprecise, n: r.fc_nits }; });
    var names = { e: 'Ошибки', i: 'Неточности', n: 'Мелочи' }, cols = { e: 'var(--bad)', i: 'var(--warn)', n: 'var(--nit)' };
    legend($('gr-fc-legend'), ['e', 'i', 'n'], function (k) { return cols[k]; }, function (k) { return names[k]; });
    if (!rows.length) { $('gr-fc').replaceChildren(el('p', 'gr-empty', 'Пока нет коммитов с итогами проверки.')); return; }
    stackedBars($('gr-fc'), rows, ['e', 'i', 'n'], function (k) { return cols[k]; }, function (k) { return names[k]; }, 'Ошибки, неточности и мелочи, найденные проверками фактов, по дням');
  }

  function renderFeed() {
    var list = data.commits.slice().reverse().filter(function (c) {
      return (!state.kind || c.kind === state.kind) && (!state.section || c.section === state.section);
    });
    $('gr-count').textContent = fmt(list.length) + ' коммитов';
    var ol = $('gr-feed'); ol.replaceChildren();
    if (!list.length) { ol.append(el('li', 'gr-empty', 'Коммитов с такими условиями нет.')); }
    list.slice(0, state.shown).forEach(function (c) {
      var li = el('li', 'gr-item');
      li.style.setProperty('--sec', secVar(c.section));
      var top = el('div', 'gr-item-top');
      var pill = el('span', 'gr-pill', KIND_NAME[c.kind] || c.kind); pill.style.color = kindVar(c.kind);
      top.append(pill);
      if (c.section) { var sp = el('span', 'gr-pill', titles[c.section] || c.section); sp.style.color = secVar(c.section); top.append(sp); }
      top.append(el('span', null, c.date.replace('T', ' ').slice(0, 16) + ' UTC'));
      var a = el('a', 'gr-sha', c.sha); a.href = 'https://github.com/irreligious86/UAV-Education/commit/' + encodeURIComponent(c.sha); a.target = '_blank'; a.rel = 'noopener';
      top.append(a);
      var nums = el('span', 'gr-item-nums');
      var bits = [];
      if (c.modules_touched) bits.push(c.modules_touched + ' мод.');
      if (c.content_lines_added) bits.push('+' + fmt(c.content_lines_added) + ' строк');
      nums.textContent = bits.join(' · ');
      if (c.fc_errors || c.fc_imprecise) { var b = el('span', 'bad', (bits.length ? ' · ' : '') + 'проверка: ' + c.fc_errors + ' ош., ' + c.fc_imprecise + ' неточн.'); nums.append(b); }
      top.append(nums);
      li.append(el('span', 'gr-item-stripe'), top, el('div', 'gr-item-subject', c.subject));
      if (c.modules && c.modules.length) li.append(el('div', 'gr-item-mods', c.modules.slice(0, 10).join(', ') + (c.modules.length > 10 ? ' …' : '')));
      ol.append(li);
    });
    $('gr-more').hidden = list.length <= state.shown;
  }

  function fillFilters() {
    var k = $('gr-kind'); KINDS.forEach(function (x) { var o = el('option', null, KIND_NAME[x]); o.value = x; k.append(o); });
    var s = $('gr-section'); lastSections().forEach(function (r) { var o = el('option', null, r.title); o.value = r.section; s.append(o); });
    k.addEventListener('change', function () { state.kind = k.value; state.shown = PAGE; renderFeed(); });
    s.addEventListener('change', function () { state.section = s.value; state.shown = PAGE; renderSections(); renderFeed(); });
    $('gr-more').addEventListener('click', function () { state.shown += PAGE; renderFeed(); });
  }

  function renderCharts() { renderArea(); renderKinds(); renderFc(); }

  function start(json) {
    data = json;
    data.sections.forEach(function (r) { titles[r.section] = r.title; });
    var s = summary();
    renderHead(s); renderSections(); fillFilters(); renderCharts(); renderFeed();
    var t = null;
    window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(renderCharts, 150); });
  }

  document.addEventListener('DOMContentLoaded', function () {
    tip = $('gr-tip');
    fetch('../docs/activity/activity.json', { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(start)
      .catch(function (e) { $('gr-lede').textContent = 'Не удалось загрузить данные о росте курса (' + e.message + '). Обнови страницу позже.'; });
  });
})();
