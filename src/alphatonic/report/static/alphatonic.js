/* alphatonic: draws the charts of a tearsheet with Observable Plot, which needs d3.

   Python writes what to draw as JSON, one specification per chart under the id of the element that
   holds it (report/figures.py and report/ts_figures.py). Every number is computed there; this file
   only draws. Colours are CSS variables (--at-c1 ... --at-context), so the page's light, dark and
   print colours apply as they stand, and nothing is redrawn when they change. A chart is drawn
   whenever its element has a width: when the page loads, when the window is resized, when a closed
   panel opens or a tab is shown. A value that is missing (null) is a gap, never a zero. */
(() => {
  const specs = JSON.parse(document.getElementById('chart-data').textContent);
  const colour = slot => (slot === 'context' ? 'var(--at-context)' : `var(--at-c${slot})`);
  const style = {background: 'transparent', color: 'var(--pico-color)', fontSize: '12px'};
  const DAY = 86400000;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  const format = (value, code, unit = '') =>
    value === null || value === undefined ? '–' : (code ? d3.format(code)(value) : String(value)) + unit;
  // Category axes keep every month and every asset, so a gap in the data stays visible; only the
  // labels are thinned, to what fits.
  const thin = (count, width, per) => {
    const every = Math.max(1, Math.ceil(count / Math.max(1, Math.floor(width / per))));
    return (label, i) => (i % every ? '' : label);
  };
  const label = (spec, panel) => [spec.label, panel && panel.title].filter(Boolean).join(' · ');
  function described(svg, text) {
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', text);
    return svg;
  }

  function legend(items) {
    const key = el('p', 'key');
    for (const item of items) {
      const swatch = el('span', `swatch ${item.shape || 'line'}`);
      swatch.style.setProperty('--swatch', colour(item.color));
      if (item.width) swatch.style.setProperty('--thickness', `${item.width}px`);
      key.append(swatch, item.name);
    }
    return key;
  }

  function linePanel(spec, panel, width) {
    const time = spec.x.type === 'utc';
    const when = panel.x.map(x => (time ? new Date(x) : x));
    const stamp = time ? d3.utcFormat(panel.x.every(x => x % DAY === 0) ? '%Y-%m-%d' : '%Y-%m-%d %H:%M') : x => `${spec.x.tip || ''} ${x}`.trim();
    const rows = panel.series.flatMap((series, s) => when.map((x, i) => ({s, x, y: series.y[i], i})));
    const text = d => {
      const series = panel.series[d.s];
      const lines = [stamp(d.x), `${series.name}: ${format(d.y, panel.y.tip || panel.y.format, panel.y.unit)}`];
      for (const column of series.columns || []) lines.push(`${column.name}: ${format(column.values[d.i], column.format)}`);
      return lines.join('\n');
    };
    const marks = [];
    if (panel.reference !== null && panel.reference !== undefined) {
      marks.push(Plot.ruleY([panel.reference], {stroke: 'var(--at-zero)', strokeDasharray: '2,3'}));
    }
    panel.series.forEach((series, s) => {
      const own = rows.filter(row => row.s === s);
      // Lines break where y is missing: a gap in the data is a gap in the line.
      marks.push(Plot.line(own, {x: 'x', y: 'y', stroke: colour(series.color), strokeWidth: series.width || 1.5}));
      if (series.markers) marks.push(Plot.dot(own, {x: 'x', y: 'y', fill: colour(series.color), r: 3.5}));
    });
    marks.push(Plot.tip(rows.filter(row => row.y !== null), Plot.pointer({x: 'x', y: 'y', title: text})));
    if (panel.empty) marks.push(Plot.text([panel.empty], {frameAnchor: 'middle', fill: 'var(--pico-muted-color)'}));
    const x = time
      ? {type: 'utc', label: spec.x.label, labelArrow: 'none'}
      : {label: spec.x.label, labelArrow: 'none', ticks: spec.x.ticks, tickFormat: 'd', inset: 14};
    const plot = Plot.plot({
      width, height: panel.height, style,
      marginTop: panel.y.label ? 26 : 8, marginRight: 14, marginBottom: spec.x.label ? 44 : 30, marginLeft: 52,
      x,
      y: {label: panel.y.label, labelArrow: 'none', grid: true, zero: panel.y.zero, domain: panel.y.domain || undefined, tickFormat: panel.y.format || undefined},
      marks,
    });
    const wrap = el('div', 'panel');
    if (panel.title) wrap.append(el('h4', 'panel-title', panel.title));
    wrap.append(described(plot, label(spec, panel)));
    return wrap;
  }

  function lines(spec, width) {
    const columns = spec.columns || 1;
    const gap = 24;
    const grid = el('div', 'panels');
    grid.style.gridTemplateColumns = `repeat(${columns}, minmax(0, 1fr))`;
    const panelWidth = Math.floor((width - gap * (columns - 1)) / columns);
    for (const panel of spec.panels) grid.append(linePanel(spec, panel, panelWidth));
    return [...(spec.legend && spec.legend.length ? [legend(spec.legend)] : []), grid];
  }

  // The chart of one asset out of many, chosen in a menu above it (select[data-chart]).
  function rolling(spec, width, state) {
    if (!spec.assets.length) return [el('p', 'unavailable', 'No rolling estimates are available.')];
    const asset = spec.assets[Math.min(state.choice, spec.assets.length - 1)];
    return lines({
      label: spec.label, x: spec.x, columns: 1, legend: [],
      panels: [{
        title: asset.name, height: spec.height, x: asset.x, reference: 0, empty: null, y: spec.y,
        series: [{name: asset.name, color: 1, width: 1.5, y: asset.y, columns: asset.columns}],
      }],
    }, width);
  }

  // Each cell mixes the neutral middle with a pole of the diverging scale, in CSS: the page's
  // variables choose the colours, so a theme change needs no redraw.
  const mix = v => {
    const share = Math.round(Math.min(1, Math.abs(v)) * 100);
    return `color-mix(in oklab, var(${v < 0 ? '--at-low' : '--at-high'}) ${share}%, var(--at-mid))`;
  };

  function heatmap(spec, width) {
    const cells = [];
    spec.rows.forEach((row, r) => spec.months.forEach((month, m) => {
      const value = spec.z[r][m];
      if (value === null || value === undefined) return;   // unavailable stays empty, never zero
      cells.push({row, month, value, count: spec.counts[r][m]});
    }));
    const text = c => [...(spec.tip.first === 'month' ? [c.month, c.row] : [c.row, c.month]),
      `${spec.tip.value}: ${format(c.value, '.3f')}`, `${spec.tip.count}: ${format(c.count)}`].join('\n');
    const marginLeft = 14 + 6.6 * Math.max(1, ...spec.rows.map(row => row.length));
    const rowHeight = Math.max(24, Math.min(48, 240 / spec.rows.length));
    const plot = Plot.plot({
      width, height: Math.round(spec.rows.length * rowHeight + 56), style, color: {type: 'identity'},
      marginLeft, marginRight: 12, marginTop: 8, marginBottom: 40,
      x: {domain: spec.months, padding: 0, label: null, tickSize: 0, tickFormat: thin(spec.months.length, width - marginLeft, 62)},
      y: {domain: spec.rows, padding: 0, label: null, tickSize: 0},
      marks: [Plot.cell(cells, {x: 'month', y: 'row', fill: c => mix(c.value), inset: 0.5, title: text, tip: true})],
    });
    const ramp = el('div', 'ramp');
    ramp.append(el('span', 'bar'));
    const ticks = el('span', 'ticks');
    ticks.append(el('span', '', '−1'), el('span', '', '0'), el('span', '', '+1'));
    ramp.append(ticks);
    return [described(plot, spec.label), ramp];
  }

  function bars(spec, width) {
    const categories = spec.categories;
    const rows = spec.series.flatMap((series, s) => categories.map((c, i) => ({c, s, value: series.values[i]})));
    const tallest = d3.max(categories, (c, i) => d3.sum(spec.series, series => series.values[i] || 0)) || 0;
    // Whole numbers only: these are counts.
    const ticks = tallest <= 10 ? d3.range(0, tallest + 1) : d3.ticks(0, tallest, 8).filter(Number.isInteger);
    const plot = Plot.plot({
      width, height: spec.height, style, color: {type: 'identity'},
      marginTop: 26, marginRight: 14, marginBottom: spec.x.label ? 44 : 30, marginLeft: 52,
      x: {domain: categories, label: spec.x.label, labelArrow: 'none', tickFormat: thin(categories.length, width - 66, 62)},
      y: {label: spec.y.label, labelArrow: 'none', grid: true, ticks, tickFormat: 'd'},
      marks: [
        Plot.barY(rows, {
          x: 'c', y: 'value', z: 's', fill: row => colour(spec.series[row.s].color), inset: 0.5,
          title: row => `${row.c}\n${spec.series[row.s].name}: ${format(row.value, 'd')}`, tip: true,
        }),
        Plot.ruleY([0]),
      ],
    });
    const items = spec.series.length > 1 || spec.totals
      ? [legend(spec.series.map(series => ({
        name: spec.totals ? `${series.name} · ${format(d3.sum(series.values), ',d')}` : series.name,
        color: series.color, shape: 'box',
      })))] : [];
    return [...items, described(plot, spec.label)];
  }

  function intervals(spec, width) {
    const rows = spec.rows;
    const text = d => [d.label, `Spearman IC: ${format(d.estimate, '.3f')}`,
      `95% CI: ${format(d.lower, '.3f')} to ${format(d.upper, '.3f')}`, `Pairs: ${format(d.pairs)}`].join('\n');
    const plot = Plot.plot({
      width, height: Math.max(300, 22 * rows.length + 90), style,
      marginTop: 8, marginRight: 16, marginBottom: 44, marginLeft: 14 + 6.6 * Math.max(1, ...rows.map(row => row.label.length)),
      x: {domain: spec.x.domain, label: spec.x.label, labelArrow: 'none', grid: true},
      y: {domain: rows.map(row => row.label), label: null, tickSize: 0},
      marks: [
        Plot.ruleX([0], {stroke: 'var(--at-zero)', strokeDasharray: '2,3'}),
        Plot.ruleY(rows, {y: 'label', x1: 'lower', x2: 'upper', stroke: 'var(--at-context)', strokeWidth: 3}),
        Plot.dot(rows, {y: 'label', x: 'estimate', r: 4.5, fill: 'var(--at-c1)', stroke: 'none', title: text, tip: true}),
      ],
    });
    return [legend(spec.legend), described(plot, spec.label)];
  }

  // The kinds a specification can have: report/figures.py writes them, and tests/test_report.py
  // checks that it writes no other.
  const kinds = {lines, rolling, heatmap, bars, intervals};

  const hosts = [...document.querySelectorAll('[data-chart]:not(select)')];
  const drawn = new Map();
  function draw(host, force = false) {
    const width = host.clientWidth;
    if (!width || (!force && drawn.get(host) === width)) return;
    drawn.set(host, width);
    try {
      const spec = specs[host.dataset.chart];
      host.replaceChildren(...kinds[spec.kind](spec, width, {choice: Number(host.dataset.choice || 0)}));
    } catch (error) {
      console.error(`The chart ${host.dataset.chart} could not be drawn`, error);
      host.replaceChildren(el('p', 'unavailable', 'This chart could not be drawn.'));
    }
  }

  // A menu above a chart picks what it shows. The browser may restore a menu on reload: read it first.
  document.querySelectorAll('select[data-chart]').forEach(select => {
    const host = document.getElementById(select.dataset.chart);
    host.dataset.choice = select.value;
    select.addEventListener('change', () => { host.dataset.choice = select.value; draw(host, true); });
  });
  hosts.forEach(host => new ResizeObserver(() => draw(host)).observe(host));
  // Before printing, panels that were closed or hidden are opened: draw them without waiting.
  window.alphatonic = {drawCharts: () => hosts.forEach(host => draw(host))};
})();
