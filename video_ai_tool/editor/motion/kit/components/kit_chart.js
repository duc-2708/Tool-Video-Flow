// Motion Kit v2 - kit_chart.js
(function() {
  function easeOutCubic(p) {
    var clamped = Math.min(1.0, Math.max(0.0, p));
    return 1.0 - Math.pow(1.0 - clamped, 3);
  }

  function renderBarChart(slots, p) {
    var series = slots.series || [];
    if (!series.length) return null;

    var maxVal = 0;
    for (var i = 0; i < series.length; i++) {
      var v = parseFloat(series[i].value) || 0;
      if (v > maxVal) maxVal = v;
    }
    if (maxVal <= 0) maxVal = 1;

    var svgW = 840;
    var svgH = 500;
    var barCount = series.length;
    var barGap = 28;
    var totalGaps = (barCount - 1) * barGap;
    var barW = Math.min(160, Math.max(70, (svgW - 120 - totalGaps) / barCount));
    var originX = 60;
    var baseY = 420;
    var chartAreaH = 340;

    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + svgW + ' ' + svgH);
    svg.setAttribute('class', 'kit-chart-svg');

    // Horizontal baseline
    var baseLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    baseLine.setAttribute('x1', originX);
    baseLine.setAttribute('y1', baseY);
    baseLine.setAttribute('x2', svgW - 20);
    baseLine.setAttribute('y2', baseY);
    baseLine.setAttribute('stroke', '#E2E8F0');
    baseLine.setAttribute('stroke-width', '3');
    svg.appendChild(baseLine);

    var ease = easeOutCubic(p);

    for (var j = 0; j < barCount; j++) {
      var item = series[j];
      var rawVal = parseFloat(item.value) || 0;
      var targetH = (rawVal / maxVal) * chartAreaH;
      var curH = targetH * ease;
      var curX = originX + 30 + j * (barW + barGap);
      var curY = baseY - curH;

      // Bar rect
      var rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', curX);
      rect.setAttribute('y', curY);
      rect.setAttribute('width', barW);
      rect.setAttribute('height', Math.max(4, curH));
      rect.setAttribute('rx', '12');
      rect.setAttribute('fill', j === barCount - 1 ? '#2563EB' : '#94A3B8');
      svg.appendChild(rect);

      // Value text on top of bar
      if (ease > 0.3) {
        var valText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        valText.setAttribute('x', curX + barW / 2);
        valText.setAttribute('y', curY - 14);
        valText.setAttribute('text-anchor', 'middle');
        valText.setAttribute('font-family', 'Inter, sans-serif');
        valText.setAttribute('font-size', '34');
        valText.setAttribute('font-weight', '700');
        valText.setAttribute('fill', j === barCount - 1 ? '#2563EB' : '#0F172A');
        var displayVal = (rawVal * ease).toFixed(item.decimals || 0);
        valText.textContent = displayVal + (slots.unit ? ' ' + slots.unit : '');
        svg.appendChild(valText);
      }

      // Label below baseline
      var lblText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      lblText.setAttribute('x', curX + barW / 2);
      lblText.setAttribute('y', baseY + 42);
      lblText.setAttribute('text-anchor', 'middle');
      lblText.setAttribute('font-family', 'Inter, sans-serif');
      lblText.setAttribute('font-size', '32');
      lblText.setAttribute('font-weight', '600');
      lblText.setAttribute('fill', '#64748B');
      lblText.textContent = String(item.label || '');
      svg.appendChild(lblText);
    }

    return svg;
  }

  function renderLineChart(slots, p) {
    var series = slots.series || [];
    if (!series.length) return null;

    var maxVal = 0;
    for (var i = 0; i < series.length; i++) {
      var v = parseFloat(series[i].value) || 0;
      if (v > maxVal) maxVal = v;
    }
    if (maxVal <= 0) maxVal = 1;

    var svgW = 840;
    var svgH = 500;
    var originX = 60;
    var baseY = 420;
    var chartAreaH = 340;
    var stepX = (svgW - 140) / Math.max(1, series.length - 1);

    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + svgW + ' ' + svgH);
    svg.setAttribute('class', 'kit-chart-svg');

    // Grid line
    var baseLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    baseLine.setAttribute('x1', originX);
    baseLine.setAttribute('y1', baseY);
    baseLine.setAttribute('x2', svgW - 40);
    baseLine.setAttribute('y2', baseY);
    baseLine.setAttribute('stroke', '#E2E8F0');
    baseLine.setAttribute('stroke-width', '3');
    svg.appendChild(baseLine);

    var ease = easeOutCubic(p);
    var points = [];
    for (var j = 0; j < series.length; j++) {
      var x = originX + j * stepX;
      var rawVal = parseFloat(series[j].value) || 0;
      var targetY = baseY - (rawVal / maxVal) * chartAreaH;
      // Animate Y progressively
      var curY = baseY - (baseY - targetY) * ease;
      points.push({ x: x, y: curY, val: rawVal, label: series[j].label });
    }

    // Polyline
    var poly = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    var ptsStr = points.map(function(pt) { return pt.x + ',' + pt.y; }).join(' ');
    poly.setAttribute('points', ptsStr);
    poly.setAttribute('fill', 'none');
    poly.setAttribute('stroke', '#2563EB');
    poly.setAttribute('stroke-width', '6');
    poly.setAttribute('stroke-linecap', 'round');
    poly.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(poly);

    // Points and labels
    for (var k = 0; k < points.length; k++) {
      var pt = points[k];
      var dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('cx', pt.x);
      dot.setAttribute('cy', pt.y);
      dot.setAttribute('r', '9');
      dot.setAttribute('fill', '#FFFFFF');
      dot.setAttribute('stroke', '#2563EB');
      dot.setAttribute('stroke-width', '5');
      svg.appendChild(dot);

      if (ease > 0.4) {
        var vText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        vText.setAttribute('x', pt.x);
        vText.setAttribute('y', pt.y - 18);
        vText.setAttribute('text-anchor', 'middle');
        vText.setAttribute('font-family', 'Inter, sans-serif');
        vText.setAttribute('font-size', '30');
        vText.setAttribute('font-weight', '700');
        vText.setAttribute('fill', '#0F172A');
        vText.textContent = (pt.val * ease).toFixed(0) + (slots.unit ? slots.unit : '');
        svg.appendChild(vText);
      }

      var lText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      lText.setAttribute('x', pt.x);
      lText.setAttribute('y', baseY + 42);
      lText.setAttribute('text-anchor', 'middle');
      lText.setAttribute('font-family', 'Inter, sans-serif');
      lText.setAttribute('font-size', '30');
      lText.setAttribute('font-weight', '600');
      lText.setAttribute('fill', '#64748B');
      lText.textContent = String(pt.label || '');
      svg.appendChild(lText);
    }

    return svg;
  }

  function renderDonutChart(slots, p) {
    var series = slots.series || [];
    if (!series.length) return null;

    var total = 0;
    for (var i = 0; i < series.length; i++) {
      total += Math.max(0, parseFloat(series[i].value) || 0);
    }
    if (total <= 0) total = 1;

    var svgW = 840;
    var svgH = 500;
    var cx = 260;
    var cy = 250;
    var radius = 160;
    var strokeW = 44;
    var circ = 2 * Math.PI * radius;

    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + svgW + ' ' + svgH);
    svg.setAttribute('class', 'kit-chart-svg');

    var colors = ['#2563EB', '#7C3AED', '#059669', '#F59E0B', '#DC2626'];
    var ease = easeOutCubic(p);
    var accumP = 0;

    for (var j = 0; j < series.length; j++) {
      var val = Math.max(0, parseFloat(series[j].value) || 0);
      var sliceP = (val / total) * ease;
      var offset = circ * (1 - accumP);

      var circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', cx);
      circle.setAttribute('cy', cy);
      circle.setAttribute('r', radius);
      circle.setAttribute('fill', 'transparent');
      circle.setAttribute('stroke', colors[j % colors.length]);
      circle.setAttribute('stroke-width', strokeW);
      circle.setAttribute('stroke-dasharray', (circ * sliceP) + ' ' + (circ * (1 - sliceP)));
      circle.setAttribute('stroke-dashoffset', offset);
      circle.setAttribute('transform', 'rotate(-90 ' + cx + ' ' + cy + ')');
      svg.appendChild(circle);

      accumP += (val / total);

      // Legend on right
      var legY = 120 + j * 64;
      var legDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      legDot.setAttribute('cx', 540);
      legDot.setAttribute('cy', legY);
      legDot.setAttribute('r', '12');
      legDot.setAttribute('fill', colors[j % colors.length]);
      svg.appendChild(legDot);

      var legText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      legText.setAttribute('x', 570);
      legText.setAttribute('y', legY + 10);
      legText.setAttribute('font-family', 'Inter, sans-serif');
      legText.setAttribute('font-size', '34');
      legText.setAttribute('font-weight', '600');
      legText.setAttribute('fill', '#0F172A');
      legText.textContent = String(series[j].label || '') + ': ' + (val * ease).toFixed(0) + (slots.unit ? ' ' + slots.unit : '');
      svg.appendChild(legText);
    }

    return svg;
  }

  window.KitChart = {
    render: function(container, chartType, slots, tau, duration) {
      if (!slots) return;
      var card = document.createElement('div');
      card.className = 'kit-card';

      if (slots.pill) {
        var pill = document.createElement('div');
        pill.className = 'kit-pill';
        pill.textContent = String(slots.pill);
        card.appendChild(pill);
      }

      var titleText = slots.title || slots.label || slots.headline;
      if (titleText) {
        var titleEl = document.createElement('div');
        titleEl.className = 'kit-title-lg';
        titleEl.textContent = String(titleText);
        card.appendChild(titleEl);
      }

      var chartWrap = document.createElement('div');
      chartWrap.className = 'kit-chart-container';

      // Progressive draw in 0.9s from real data
      var pDraw = Math.min(1.0, Math.max(0.0, tau / 0.9));
      var svgEl = null;

      if (chartType === 'kit_chart_line') {
        svgEl = renderLineChart(slots, pDraw);
      } else if (chartType === 'kit_chart_donut') {
        svgEl = renderDonutChart(slots, pDraw);
      } else {
        svgEl = renderBarChart(slots, pDraw);
      }

      if (svgEl) {
        chartWrap.appendChild(svgEl);
      }
      card.appendChild(chartWrap);

      // Entrance motion
      var pEnter = Math.min(1.0, Math.max(0.0, tau / 0.7));
      var easeOut = 1.0 - Math.pow(1.0 - pEnter, 3);
      var translateY = (1.0 - easeOut) * 24.0;
      var opacity = easeOut;

      var pDrift = Math.min(1.0, Math.max(0.0, tau / Math.max(0.1, duration)));
      var currentScale = 1.0 + 0.02 * pDrift;

      card.style.transform = 'translateY(' + translateY.toFixed(2) + 'px) scale(' + currentScale.toFixed(4) + ')';
      card.style.opacity = opacity.toFixed(3);

      container.appendChild(card);
    }
  };
})();
