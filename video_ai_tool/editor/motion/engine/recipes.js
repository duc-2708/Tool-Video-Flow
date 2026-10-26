/* Motion Recipes (6 priority types x 3 variants) + Fixes for mock_ui_window & magnifier_check + 3 Annotations.
 * Pure deterministic functions driven by absolute time t, duration, and data.
 */
(()=>{'use strict';

const { clamp, easeOutCubic, overshoot, spring, squashAndStretch } = window.MotionEasing;
const { calculateOdometer, renderLiquidBubbles, renderSparks } = window.MotionParticles;
const { SAFE_AREA, wrapText } = window.MotionLayout;
const { hashSeed, seededRandom } = window.MotionPRNG;

const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}, text) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
  if (text !== undefined) n.textContent = String(text);
  return n;
};
const group = (parent, attrs = {}) => {
  const g = el('g', attrs);
  parent.append(g);
  return g;
};
const shape = (parent, tag, attrs = {}) => {
  const s = el(tag, attrs);
  parent.append(s);
  return s;
};

// Formats number cleanly in Vietnamese locale
const formatNum = (val) => {
  const num = Number(val || 0);
  return Number.isInteger(num) ? num.toLocaleString('vi-VN') : num.toLocaleString('vi-VN', { maximumFractionDigits: 2 });
};

// =========================================================================
// 1. STAT_NUMBER (3 Variants)
// =========================================================================
function renderStatNumber(ctx, svg, d, t, duration, variantIdx = 0) {
  const targetVal = Number(d.value ?? 50);
  const unit = d.unit || '';
  const label = d.label || d.text || 'Chỉ số quan trọng';
  const progress = clamp(t / Math.max(0.8, duration * 0.45));
  const currentNum = targetVal * easeOutCubic(progress);

  const cx = 540;
  const cy = 820;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 280,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  if (variantIdx === 0) {
    // Variant 1: odometer_bounce
    const odo = calculateOdometer(0, targetVal, progress);
    const displayStr = formatNum(odo.value) + unit;
    const bounceY = odo.bounceY;

    // Card frame
    shape(svg, 'rect', {
      x: 180, y: cy - 240, width: 720, height: 460, rx: 36,
      fill: '#101e33', stroke: 'var(--accent)', 'stroke-width': 5,
      class: 'glass-card'
    });

    // Big Odometer Number
    const gNum = group(svg, { transform: `translate(0, ${bounceY})` });
    const textEl = el('text', {
      x: cx, y: cy + 40,
      'text-anchor': 'middle',
      'font-size': '110',
      'font-weight': 'bold',
      fill: 'var(--accent)',
      class: 'stat-odometer-text'
    }, displayStr);
    gNum.append(textEl);

    // Label below
    const wrapped = wrapText(label, 22, 2);
    wrapped.forEach((line, i) => {
      const lbl = el('text', {
        x: cx, y: cy + 140 + i * 44,
        'text-anchor': 'middle',
        'font-size': '40',
        fill: '#e2e8f0',
        class: 'stat-label'
      }, line);
      svg.append(lbl);
    });

  } else if (variantIdx === 1) {
    // Variant 2: strike_replace_pop
    const oldVal = (d.bars && d.bars[0]?.value) ? d.bars[0].value : Math.round(targetVal * 0.5);
    const strikeProgress = clamp((t - 0.4) / 0.6);
    const replaceProgress = clamp((t - 1.0) / 0.7);

    // Card frame
    shape(svg, 'rect', {
      x: 160, y: cy - 250, width: 760, height: 480, rx: 36,
      fill: '#101e33', stroke: '#334155', 'stroke-width': 4
    });

    // Old number (gets struck through and fades)
    if (strikeProgress > 0) {
      const gOld = group(svg, { opacity: 1 - strikeProgress * 0.75 });
      const oldStr = formatNum(oldVal) + unit;
      gOld.append(el('text', {
        x: cx - 140, y: cy + 20,
        'text-anchor': 'middle',
        'font-size': '75',
        fill: '#94a3b8'
      }, oldStr));
      // Red strike line
      const strikeLen = Math.min(1, strikeProgress * 1.5);
      shape(gOld, 'line', {
        x1: cx - 260, y1: cy + 30,
        x2: cx - 260 + 240 * strikeLen, y2: cy - 20,
        stroke: '#ef4444', 'stroke-width': 8, 'stroke-linecap': 'round'
      });
    }

    // Arrow indicator
    if (replaceProgress > 0.2) {
      shape(svg, 'path', {
        d: `M ${cx - 10} ${cy} L ${cx + 30} ${cy} M ${cx + 15} ${cy - 15} L ${cx + 30} ${cy} L ${cx + 15} ${cy + 15}`,
        stroke: 'var(--accent)', 'stroke-width': 6, fill: 'none', 'stroke-linecap': 'round'
      });
    }

    // New number popping in with bounce
    if (replaceProgress > 0) {
      const s = overshoot(replaceProgress, 2.2);
      const gNew = group(svg, {
        transform: `translate(${cx + 180}, ${cy + 25}) scale(${s}) translate(-${cx + 180}, -${cy + 25})`,
        opacity: clamp(replaceProgress * 2)
      });
      gNew.append(el('text', {
        x: cx + 180, y: cy + 25,
        'text-anchor': 'middle',
        'font-size': '105',
        'font-weight': 'bold',
        fill: 'var(--accent)'
      }, formatNum(targetVal) + unit));
    }

    // Label
    const wrapped = wrapText(label, 22, 2);
    wrapped.forEach((line, i) => {
      svg.append(el('text', {
        x: cx, y: cy + 150 + i * 44,
        'text-anchor': 'middle', 'font-size': '40', fill: '#f8fafc'
      }, line));
    });

  } else {
    // Variant 3: count_up_glow_ring
    const radius = 210;
    const circumference = 2 * Math.PI * radius;
    const fillRatio = clamp(currentNum / Math.max(1, targetVal));

    // Outer track
    shape(svg, 'circle', {
      cx, cy: cy - 30, r: radius,
      fill: 'none', stroke: '#1e293b', 'stroke-width': 34
    });
    // Glowing active arc
    shape(svg, 'circle', {
      cx, cy: cy - 30, r: radius,
      fill: 'none', stroke: 'var(--accent)', 'stroke-width': 34,
      'stroke-linecap': 'round',
      'stroke-dasharray': `${circumference * fillRatio} ${circumference}`,
      transform: `rotate(-90 ${cx} ${cy - 30})`
    });

    // Center count
    svg.append(el('text', {
      x: cx, y: cy - 10,
      'text-anchor': 'middle', 'font-size': '95', 'font-weight': 'bold',
      fill: 'var(--accent)'
    }, formatNum(currentNum) + unit));

    // Label
    const wrapped = wrapText(label, 20, 2);
    wrapped.forEach((line, i) => {
      svg.append(el('text', {
        x: cx, y: cy + 230 + i * 44,
        'text-anchor': 'middle', 'font-size': '40', fill: '#f1f5f9'
      }, line));
    });
  }
}

// =========================================================================
// 2. BAR_COMPARE (3 Variants)
// =========================================================================
function renderBarCompare(ctx, svg, d, t, duration, variantIdx = 0) {
  const bars = (d.bars && d.bars.length >= 2) ? d.bars.slice(0, 4) : [
    { label: 'Thực tế', value: 30, unit: '%' },
    { label: 'Kỳ vọng', value: 75, unit: '%' }
  ];
  const maxVal = Math.max(1, ...bars.map(b => Number(b.value || 0)));
  const cx = 540;
  const cy = 820;

  if (variantIdx === 0) {
    // Variant 1: stagger_overshoot_crown (vertical bars)
    const barWidth = Math.min(140, 600 / bars.length);
    const spacing = 720 / bars.length;
    const startX = 180 + spacing / 2;
    const baselineY = cy + 220;
    const maxBarHeight = 440;

    bars.forEach((b, i) => {
      const p = clamp((t - 0.2 - i * 0.22) / 0.65);
      const s = overshoot(p, 1.8);
      const barHeight = Math.max(8, (Number(b.value) / maxVal) * maxBarHeight * s);
      const bx = startX + i * spacing - barWidth / 2;
      const by = baselineY - barHeight;

      // Bar rect
      const isTop = (Number(b.value) === maxVal);
      shape(svg, 'rect', {
        x: bx, y: by, width: barWidth, height: barHeight, rx: 18,
        fill: isTop ? 'var(--accent)' : '#334155',
        class: isTop ? 'bar-top-winner' : 'bar-normal'
      });

      // Number on top
      if (p > 0.3) {
        const valText = formatNum(Number(b.value) * easeOutCubic(p)) + (b.unit || '');
        svg.append(el('text', {
          x: bx + barWidth / 2, y: by - 20,
          'text-anchor': 'middle', 'font-size': '44', 'font-weight': 'bold',
          fill: isTop ? 'var(--accent)' : '#f8fafc'
        }, valText));
      }

      // Crown on top winner
      if (isTop && p > 0.8) {
        const crownY = by - 85;
        const gCrown = group(svg, {
          transform: `translate(${bx + barWidth / 2 - 24}, ${crownY}) scale(1.2)`
        });
        shape(gCrown, 'path', {
          d: 'M 0 25 L 8 0 L 20 18 L 32 0 L 40 25 Z',
          fill: '#facc15', stroke: '#ca8a04', 'stroke-width': 2
        });
      }

      // Label below baseline
      const wrapped = wrapText(b.label, 14, 2);
      wrapped.forEach((line, li) => {
        svg.append(el('text', {
          x: bx + barWidth / 2, y: baselineY + 45 + li * 38,
          'text-anchor': 'middle', 'font-size': '34', fill: '#cbd5e1'
        }, line));
      });
    });

  } else {
    // Variant 2: horizontal_slide_meter
    const startY = cy - 180;
    const rowHeight = 130;
    const maxTrackWidth = 560;

    bars.forEach((b, i) => {
      const p = clamp((t - 0.2 - i * 0.25) / 0.65);
      const s = overshoot(p, 1.6);
      const fillWidth = Math.max(10, (Number(b.value) / maxVal) * maxTrackWidth * s);
      const ry = startY + i * rowHeight;

      // Label
      svg.append(el('text', {
        x: 180, y: ry + 35,
        'font-size': '38', 'font-weight': 'bold', fill: '#f8fafc'
      }, wrapText(b.label, 16, 1)[0]));

      // Track
      shape(svg, 'rect', {
        x: 180, y: ry + 50, width: maxTrackWidth, height: 32, rx: 16,
        fill: '#1e293b'
      });
      // Fill
      shape(svg, 'rect', {
        x: 180, y: ry + 50, width: fillWidth, height: 32, rx: 16,
        fill: (i === 0) ? 'var(--accent)' : 'var(--secondary)'
      });

      // Value number at right
      if (p > 0.25) {
        svg.append(el('text', {
          x: 180 + maxTrackWidth + 40, y: ry + 76,
          'font-size': '44', 'font-weight': 'bold', fill: 'var(--accent)'
        }, formatNum(Number(b.value) * easeOutCubic(p)) + (b.unit || '')));
      }
    });
  }
}

// =========================================================================
// 3. FLOW_CHAIN (3 Variants)
// =========================================================================
function renderFlowChain(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    'Thu thập dữ liệu', 'Phân tích hệ thống', 'Đánh giá độc lập', 'Kết luận'
  ];
  const cx = 540;
  const cy = 820;

  // Stagger nodes
  const nodeCount = items.length;
  const startY = cy - (nodeCount - 1) * 90;
  const stepY = 180;

  items.forEach((item, i) => {
    const nodeT = 0.2 + i * 0.7;
    const p = clamp((t - nodeT) / 0.5);
    const ny = startY + i * stepY;
    const nx = cx;

    // Connecting line to next node
    if (i < nodeCount - 1) {
      const nextNodeT = 0.2 + (i + 1) * 0.7;
      const lineP = clamp((t - (nodeT + 0.3)) / 0.5);
      const lineLen = stepY * easeOutCubic(lineP);

      // Dashed connector
      shape(svg, 'line', {
        x1: nx, y1: ny + 45,
        x2: nx, y2: ny + 45 + lineLen,
        stroke: '#475569', 'stroke-width': 6, 'stroke-dasharray': '8 6'
      });

      // Animated glowing data packet travelling down the line
      if (lineP > 0.1 && lineP < 0.95) {
        const packetY = ny + 45 + stepY * lineP;
        shape(svg, 'circle', {
          cx: nx, cy: packetY, r: 10,
          fill: 'var(--accent)', filter: 'drop-shadow(0 0 8px var(--accent))'
        });
      }
    }

    // Node Box
    if (p > 0) {
      const s = spring(p, 14, 3.8);
      const isComplete = (t >= nodeT + 0.5);

      const gNode = group(svg, {
        transform: `translate(${nx}, ${ny}) scale(${s}) translate(-${nx}, -${ny})`,
        opacity: clamp(p * 2.5)
      });

      // Box shape
      shape(gNode, 'rect', {
        x: nx - 340, y: ny - 45, width: 680, height: 90, rx: 24,
        fill: isComplete ? '#1e293b' : '#0f172a',
        stroke: isComplete ? 'var(--accent)' : '#475569',
        'stroke-width': 4
      });

      // Step Number circle
      shape(gNode, 'circle', {
        cx: nx - 280, cy: ny, r: 26,
        fill: isComplete ? 'var(--accent)' : '#334155'
      });
      gNode.append(el('text', {
        x: nx - 280, y: ny + 10,
        'text-anchor': 'middle', 'font-size': '28', 'font-weight': 'bold',
        fill: isComplete ? '#0f172a' : '#f8fafc'
      }, String(i + 1)));

      // Step Text
      const line = wrapText(item, 28, 1)[0] || item;
      gNode.append(el('text', {
        x: nx - 220, y: ny + 12,
        'font-size': '38', 'font-weight': 'bold', fill: '#f8fafc'
      }, line));
    }
  });
}

// =========================================================================
// 4. HUB_SPOKE (3 Variants)
// =========================================================================
function renderHubSpoke(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    'Cảm biến', 'Thuật toán', 'Phần cứng', 'Kiểm định'
  ];
  const centerTitle = d.label || d.text || 'TRUNG TÂM';
  const cx = 540;
  const cy = 820;
  const spokeRadius = 310;

  // 1. Center pulsing core
  const pulseScale = 1.0 + Math.sin(t * 3) * 0.04;
  const gCenter = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${pulseScale}) translate(-${cx}, -${cy})`
  });
  // Waves radiating out
  const waveRadius = 90 + ((t * 80) % 180);
  const waveAlpha = 1 - ((t * 80) % 180) / 180;
  shape(svg, 'circle', {
    cx, cy, r: waveRadius,
    fill: 'none', stroke: 'var(--accent)', 'stroke-width': 3,
    opacity: waveAlpha * 0.5
  });

  // Core circle
  shape(gCenter, 'circle', {
    cx, cy, r: 85,
    fill: '#1e293b', stroke: 'var(--accent)', 'stroke-width': 6
  });
  gCenter.append(el('text', {
    x: cx, y: cy + 10,
    'text-anchor': 'middle', 'font-size': '34', 'font-weight': 'bold',
    fill: 'var(--accent)'
  }, wrapText(centerTitle, 10, 1)[0]));

  // 2. Spokes and satellite nodes
  items.forEach((item, i) => {
    const baseAngle = (i / items.length) * Math.PI * 2 - Math.PI / 2;
    // Gentle orbit
    const angle = baseAngle + Math.sin(t * 0.4) * 0.08;
    const px = cx + Math.cos(angle) * spokeRadius;
    const py = cy + Math.sin(angle) * spokeRadius;

    const p = clamp((t - 0.3 - i * 0.25) / 0.55);
    if (p <= 0) return;

    // Spoke ray
    shape(svg, 'line', {
      x1: cx, y1: cy,
      x2: cx + (px - cx) * easeOutCubic(p),
      y2: cy + (py - cy) * easeOutCubic(p),
      stroke: 'var(--secondary)', 'stroke-width': 4, 'stroke-dasharray': '6 4'
    });

    if (p > 0.4) {
      const s = overshoot((p - 0.4) / 0.6, 1.8);
      const gSat = group(svg, {
        transform: `translate(${px}, ${py}) scale(${s}) translate(-${px}, -${py})`
      });

      shape(gSat, 'circle', {
        cx: px, cy: py, r: 68,
        fill: '#101e33', stroke: '#64748b', 'stroke-width': 4
      });
      const lines = wrapText(item, 10, 2);
      lines.forEach((l, li) => {
        gSat.append(el('text', {
          x: px, y: py - (lines.length - 1) * 16 + li * 34 + 8,
          'text-anchor': 'middle', 'font-size': '30', fill: '#f8fafc'
        }, l));
      });
    }
  });
}

// =========================================================================
// 5. CONTAINER_FILL (3 Variants)
// =========================================================================
function renderContainerFill(ctx, svg, d, t, duration, variantIdx = 0) {
  const percent = clamp(Number(d.percent ?? d.value ?? 70) / 100);
  const label = d.label || d.text || 'Mức giới hạn';
  const fillProgress = clamp(t / Math.max(0.8, duration * 0.55));
  const currentFill = percent * overshoot(fillProgress, 1.3);

  const cx = 540;
  const cy = 820;
  const flaskW = 340;
  const flaskH = 500;
  const bx = cx - flaskW / 2;
  const by = cy - flaskH / 2;

  // 1. Container outer vessel
  shape(svg, 'rect', {
    x: bx, y: by, width: flaskW, height: flaskH, rx: 42,
    fill: '#0f172a', stroke: '#475569', 'stroke-width': 8
  });

  // 2. Liquid inside
  const liquidH = flaskH * currentFill;
  const liquidY = by + flaskH - liquidH;

  // Wave path at liquid surface
  const waveAmp = (fillProgress < 1 ? 12 : 6) * Math.sin(t * 6);
  const wavePath = `M ${bx} ${liquidY} Q ${bx + flaskW / 4} ${liquidY + waveAmp} ${bx + flaskW / 2} ${liquidY} T ${bx + flaskW} ${liquidY} L ${bx + flaskW} ${by + flaskH} L ${bx} ${by + flaskH} Z`;

  shape(svg, 'path', {
    d: wavePath,
    fill: 'url(#liquid-gradient)',
    opacity: 0.88
  });

  // Bubbles in liquid
  if (ctx) {
    renderLiquidBubbles(ctx, { x: bx, y: by, width: flaskW, height: flaskH }, t, currentFill);
  }

  // 3. Digital Gauge readout in center of container
  const displayPct = Math.round(currentFill * 100);
  svg.append(el('text', {
    x: cx, y: cy + 15,
    'text-anchor': 'middle', 'font-size': '85', 'font-weight': 'bold',
    fill: '#ffffff', filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.8))'
  }, `${displayPct}%`));

  // Label below
  const wrapped = wrapText(label, 20, 2);
  wrapped.forEach((line, i) => {
    svg.append(el('text', {
      x: cx, y: by + flaskH + 75 + i * 44,
      'text-anchor': 'middle', 'font-size': '40', 'font-weight': 'bold',
      fill: '#f8fafc'
    }, line));
  });
}

// =========================================================================
// 6. CHECKLIST (3 Variants)
// =========================================================================
function renderChecklist(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    'Kiểm định dữ liệu gốc', 'Đo đạc thực nghiệm độc lập', 'Đối chiếu thông số công bố'
  ];
  const cx = 540;
  const cy = 820;
  const startY = cy - (items.length * 130) / 2;

  items.forEach((item, i) => {
    const rowStartT = 0.2 + i * 0.7;
    const p = clamp((t - rowStartT) / 0.5);
    if (p <= 0) return;

    const ry = startY + i * 135;
    const s = overshoot(p, 1.6);
    const isChecked = (t >= rowStartT + 0.4);

    const gRow = group(svg, {
      transform: `translate(${cx}, ${ry}) scale(${s}) translate(-${cx}, -${ry})`,
      opacity: clamp(p * 2)
    });

    // Row card
    shape(gRow, 'rect', {
      x: 170, y: ry - 48, width: 740, height: 96, rx: 24,
      fill: isChecked ? '#101e33' : '#0f172a',
      stroke: isChecked ? 'var(--accent)' : '#334155',
      'stroke-width': 4
    });

    // Checkbox Circle
    shape(gRow, 'circle', {
      cx: 240, cy: ry, r: 28,
      fill: isChecked ? 'var(--accent)' : '#1e293b',
      stroke: isChecked ? 'var(--accent)' : '#64748b', 'stroke-width': 3
    });

    // Checkmark ✓ drawn with stroke or pop
    if (isChecked) {
      shape(gRow, 'path', {
        d: 'M 228 0 L 237 9 L 253 -7',
        transform: `translate(0, ${ry})`,
        stroke: '#0f172a', 'stroke-width': 5, fill: 'none', 'stroke-linecap': 'round'
      });
    }

    // Text label
    const line = wrapText(item, 26, 1)[0] || item;
    gRow.append(el('text', {
      x: 295, y: ry + 12,
      'font-size': '38', 'font-weight': 'bold', fill: '#f8fafc'
    }, line));
  });
}

// =========================================================================
// 7. MOCK_UI_WINDOW (Fixed rows, no text collisions)
// =========================================================================
function renderMockUIWindow(ctx, svg, d, t, duration) {
  const cx = 540;
  const cy = 820;
  const w = 760;
  const h = 560;
  const x = cx - w / 2;
  const y = cy - h / 2;

  // Window container
  shape(svg, 'rect', {
    x, y, width: w, height: h, rx: 28,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'mock-ui-card'
  });

  // Window header bar
  shape(svg, 'rect', {
    x, y, width: w, height: 60, rx: 28,
    fill: '#1e293b'
  });
  // Window control dots (red, yellow, green)
  shape(svg, 'circle', { cx: x + 35, cy: y + 30, r: 9, fill: '#ef4444' });
  shape(svg, 'circle', { cx: x + 62, cy: y + 30, r: 9, fill: '#eab308' });
  shape(svg, 'circle', { cx: x + 89, cy: y + 30, r: 9, fill: '#22c55e' });

  // Window Title Bar
  svg.append(el('text', {
    x: cx, y: y + 42,
    'text-anchor': 'middle', 'font-size': '28', fill: '#94a3b8'
  }, d.title || 'Hệ thống kiểm thử (Giả lập)'));

  // Content Rows (fixed slot heights, wrapText, no collisions)
  const rows = (d.items && d.items.length) ? d.items.slice(0, 4) : [
    'Khảo sát năng suất', 'Báo cáo nội bộ', 'Quy trình kiểm định', 'Xác nhận độc lập'
  ];
  const rowH = 95;
  const startRowY = y + 90;

  rows.forEach((rText, i) => {
    const ry = startRowY + i * rowH;
    const p = clamp((t - 0.2 - i * 0.2) / 0.4);
    if (p <= 0) return;

    const gRow = group(svg, { opacity: p });
    shape(gRow, 'rect', {
      x: x + 25, y: ry, width: w - 50, height: 75, rx: 16,
      fill: (i % 2 === 0) ? '#162238' : '#111c2e'
    });

    // Icon indicator
    shape(gRow, 'circle', { cx: x + 65, cy: ry + 38, r: 12, fill: 'var(--accent)' });

    // Clean wrapped text
    const cleanLine = wrapText(rText, 24, 1)[0] || rText;
    gRow.append(el('text', {
      x: x + 100, y: ry + 48,
      'font-size': '34', fill: '#f1f5f9'
    }, cleanLine));

    // Status pill on right
    shape(gRow, 'rect', {
      x: x + w - 170, y: ry + 20, width: 120, height: 36, rx: 18,
      fill: '#1e293b'
    });
    gRow.append(el('text', {
      x: x + w - 110, y: ry + 45,
      'text-anchor': 'middle', 'font-size': '22', fill: '#38bdf8'
    }, 'ONLINE'));
  });
}

// =========================================================================
// 8. MAGNIFIER_CHECK (Intentional Glide + Zoom Lens Focus)
// =========================================================================
function renderMagnifierCheck(ctx, svg, d, t, duration, context) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 5) : [
    'Dữ liệu công bố', 'Đối chiếu thực nghiệm', 'Kết quả độc lập'
  ];
  const cx = 540;
  const cy = 820;
  const w = 740;
  const h = 560;
  const x = cx - w / 2;
  const y = cy - h / 2;

  // Background Document Card
  shape(svg, 'rect', {
    x, y, width: w, height: h, rx: 32,
    fill: '#101e33', stroke: '#334155', 'stroke-width': 4
  });

  // Render rows
  const startRowY = y + 90;
  const rowSpacing = Math.min(130, (h - 130) / Math.max(1, items.length));
  const targetRowIdx = Math.min(items.length - 1, 1);

  items.forEach((item, i) => {
    const ry = startRowY + i * rowSpacing;
    const isTarget = (i === targetRowIdx);

    shape(svg, 'line', {
      x1: x + 60, y1: ry + 40, x2: x + w - 60, y2: ry + 40,
      stroke: '#334155', 'stroke-width': 2
    });

    const words = String(item || '').split(/\s+/).slice(0, 6).join(' ');
    const textEl = el('text', {
      x: x + 80, y: ry + 20,
      'font-size': isTarget ? '42' : '38',
      'font-weight': isTarget ? 'bold' : 'normal',
      fill: isTarget ? '#ffffff' : '#94a3b8',
      class: 'ill-label'
    }, words);
    svg.append(textEl);

    const mark = /\b(sai|không|giả)\b/i.test(item) ? '✗' : /đúng|xác nhận|có căn cứ/i.test(item) ? '✓' : '✓';
    const rowOp = (context && typeof context.row === 'function') ? context.row(i) : clamp((t - (0.15 + i * 0.6)) / 0.35);
    const verdictEl = el('text', {
      x: x + w - 80, y: ry + 25,
      'text-anchor': 'middle', 'font-size': '52', 'font-weight': 'bold',
      fill: mark === '✗' ? '#ef4444' : '#22c55e',
      class: 'verdict',
      opacity: rowOp
    }, mark);
    svg.append(verdictEl);
  });

  // Magnifier Intentional Motion:
  // Starts at top-right (x + w - 120, y + 80), glides smoothly to target row (cx, startRowY + targetRowIdx * rowSpacing + 20)
  const targetX = cx + 80;
  const targetY = startRowY + targetRowIdx * rowSpacing + 15;
  const startMagX = x + w - 80;
  const startMagY = y + 80;

  const glideProgress = clamp(t / Math.max(0.6, duration * 0.4));
  const currentMagX = startMagX + (targetX - startMagX) * easeOutCubic(glideProgress);
  const currentMagY = startMagY + (targetY - startMagY) * easeOutCubic(glideProgress);

  // When reached target: lens blooms and zooms
  const isLocked = (glideProgress >= 0.95);
  const lensRadius = isLocked ? 105 : 90;

  const gMag = group(svg, {
    transform: `translate(${currentMagX}, ${currentMagY})`
  });

  // Lens Glass
  shape(gMag, 'circle', {
    cx: 0, cy: 0, r: lensRadius,
    fill: '#38bdf8', 'fill-opacity': '0.15',
    stroke: 'var(--accent)', 'stroke-width': 12
  });

  // Handle
  shape(gMag, 'line', {
    x1: lensRadius * 0.7, y1: lensRadius * 0.7,
    x2: lensRadius * 1.6, y2: lensRadius * 1.6,
    stroke: 'var(--accent)', 'stroke-width': 22, 'stroke-linecap': 'round'
  });

  // When locked on target row: stamped verdict ✓ or ✗
  if (isLocked) {
    const verdictP = clamp((t - (duration * 0.45)) / 0.4);
    if (verdictP > 0) {
      const vs = overshoot(verdictP, 2.0);
      const gVerdict = group(gMag, {
        transform: `scale(${vs})`
      });
      gVerdict.append(el('text', {
        x: 0, y: 18,
        'text-anchor': 'middle', 'font-size': '60', 'font-weight': 'bold',
        fill: '#22c55e'
      }, '✓'));
    }
  }
}


// =========================================================================
// 10. VERSUS_SPLIT (3 Variants)
// =========================================================================
function renderVersusSplit(ctx, svg, d, t, duration, variantIdx = 0) {
  const bars = (d.bars && d.bars.length >= 2) ? d.bars.slice(0, 2) : [
    { label: d.items?.[0] || 'Giải pháp A', value: 40, unit: '%' },
    { label: d.items?.[1] || 'Giải pháp B', value: 85, unit: '%' }
  ];
  const cx = 540;
  const cy = 820;
  const p = clamp(t / Math.max(0.6, duration * 0.4));

  if (variantIdx === 0) {
    // Variant 1: split_screen_vs_slam
    const leftW = 420;
    const cardH = 580;
    const isWinnerB = (Number(bars[1]?.value || 0) >= Number(bars[0]?.value || 0));

    // Left card sliding in
    const leftP = clamp(t / 0.5);
    const leftX = cx - leftW - 20 - (1 - easeOutCubic(leftP)) * 200;
    const gLeft = group(svg, {
      transform: 'translate(' + leftX + ' ' + (cy - cardH / 2) + ')'
    });
    shape(gLeft, 'rect', {
      x: 0, y: 0, width: leftW, height: cardH, rx: 28,
      fill: '#101e33', stroke: (!isWinnerB && p > 0.6) ? 'var(--accent)' : '#334155', 'stroke-width': 4
    });
    gLeft.append(el('text', {
      x: leftW / 2, y: 160, 'text-anchor': 'middle', 'font-size': '44', 'font-weight': 'bold', fill: '#f8fafc'
    }, wrapText(bars[0].label, 16, 2)[0] || bars[0].label));
    if (bars[0].value !== undefined) {
      gLeft.append(el('text', {
        x: leftW / 2, y: 320, 'text-anchor': 'middle', 'font-size': '80', 'font-weight': 'bold', fill: '#94a3b8'
      }, formatNum(Number(bars[0].value) * easeOutCubic(p)) + (bars[0].unit || '')));
    }

    // Right card sliding in
    const rightP = clamp((t - 0.1) / 0.5);
    const rightX = cx + 20 + (1 - easeOutCubic(rightP)) * 200;
    const gRight = group(svg, {
      transform: 'translate(' + rightX + ' ' + (cy - cardH / 2) + ')'
    });
    shape(gRight, 'rect', {
      x: 0, y: 0, width: leftW, height: cardH, rx: 28,
      fill: '#101e33', stroke: (isWinnerB && p > 0.6) ? 'var(--accent)' : '#334155', 'stroke-width': 4
    });
    gRight.append(el('text', {
      x: leftW / 2, y: 160, 'text-anchor': 'middle', 'font-size': '44', 'font-weight': 'bold', fill: '#f8fafc'
    }, wrapText(bars[1].label, 16, 2)[0] || bars[1].label));
    if (bars[1].value !== undefined) {
      gRight.append(el('text', {
        x: leftW / 2, y: 320, 'text-anchor': 'middle', 'font-size': '80', 'font-weight': 'bold', fill: 'var(--accent)'
      }, formatNum(Number(bars[1].value) * easeOutCubic(p)) + (bars[1].unit || '')));
    }

    // VS Badge slamming down at t=0.35
    const vsP = clamp((t - 0.25) / 0.45);
    if (vsP > 0) {
      const vsS = overshoot(vsP, 2.5);
      const gVS = group(svg, {
        transform: 'translate(' + cx + ' ' + cy + ') scale(' + vsS + ')'
      });
      shape(gVS, 'circle', { cx: 0, cy: 0, r: 65, fill: '#ff007f', stroke: '#ffffff', 'stroke-width': 4 });
      gVS.append(el('text', {
        x: 0, y: 18, 'text-anchor': 'middle', 'font-size': '48', 'font-weight': 'bold', fill: '#ffffff'
      }, 'VS'));
    }

  } else if (variantIdx === 1) {
    // Variant 2: balance_scale_tilt
    const valA = Number(bars[0]?.value || 50);
    const valB = Number(bars[1]?.value || 50);
    const maxTilt = 14;
    const tiltAngle = (valB !== valA) ? Math.sign(valB - valA) * maxTilt * easeOutCubic(p) : 0;

    const gBeam = group(svg, {
      transform: 'translate(' + cx + ' ' + (cy + 40) + ') rotate(' + tiltAngle + ')'
    });
    shape(gBeam, 'line', { x1: -360, y1: 0, x2: 360, y2: 0, stroke: 'var(--accent)', 'stroke-width': 12, 'stroke-linecap': 'round' });
    shape(svg, 'path', { d: 'M ' + (cx - 40) + ' ' + (cy + 220) + ' L ' + cx + ' ' + (cy + 40) + ' L ' + (cx + 40) + ' ' + (cy + 220) + ' Z', fill: '#334155' });

    // Left plate
    const gPlateL = group(gBeam, { transform: 'translate(-320, 0)' });
    shape(gPlateL, 'rect', { x: -120, y: 40, width: 240, height: 160, rx: 18, fill: '#101e33', stroke: '#334155', 'stroke-width': 3 });
    gPlateL.append(el('text', { x: 0, y: 100, 'text-anchor': 'middle', 'font-size': '36', fill: '#ffffff' }, bars[0].label));
    gPlateL.append(el('text', { x: 0, y: 160, 'text-anchor': 'middle', 'font-size': '48', 'font-weight': 'bold', fill: 'var(--accent)' }, formatNum(valA) + (bars[0].unit || '')));

    // Right plate
    const gPlateR = group(gBeam, { transform: 'translate(320, 0)' });
    shape(gPlateR, 'rect', { x: -120, y: 40, width: 240, height: 160, rx: 18, fill: '#101e33', stroke: 'var(--accent)', 'stroke-width': 4 });
    gPlateR.append(el('text', { x: 0, y: 100, 'text-anchor': 'middle', 'font-size': '36', fill: '#ffffff' }, bars[1].label));
    gPlateR.append(el('text', { x: 0, y: 160, 'text-anchor': 'middle', 'font-size': '48', 'font-weight': 'bold', fill: 'var(--accent)' }, formatNum(valB) + (bars[1].unit || '')));

  } else {
    // Variant 3: power_meters_duel
    const meterW = 760;
    const meterH = 90;
    const startY = cy - 120;
    bars.forEach((b, i) => {
      const my = startY + i * 180;
      const bp = clamp((t - i * 0.2) / 0.6);
      const isDominant = (i === 1);

      shape(svg, 'rect', { x: cx - meterW / 2, y: my, width: meterW, height: meterH, rx: 22, fill: '#101e33', stroke: '#334155', 'stroke-width': 3 });
      shape(svg, 'rect', { x: cx - meterW / 2, y: my, width: meterW * (Number(b.value || 50) / 100) * easeOutCubic(bp), height: meterH, rx: 22, fill: isDominant ? 'var(--accent)' : '#64748b' });
      svg.append(el('text', { x: cx - meterW / 2 + 30, y: my + 58, 'font-size': '40', 'font-weight': 'bold', fill: '#ffffff' }, b.label));
      svg.append(el('text', { x: cx + meterW / 2 - 30, y: my + 58, 'text-anchor': 'end', 'font-size': '44', 'font-weight': 'bold', fill: isDominant ? 'var(--accent)' : '#cbd5e1' }, formatNum(b.value) + (b.unit || '')));
    });
  }
}

// =========================================================================
// 11. LINE_CHART_DRAW (3 Variants)
// =========================================================================
function renderLineChartDraw(ctx, svg, d, t, duration, variantIdx = 0) {
  const bars = (d.bars && d.bars.length >= 2) ? d.bars.slice(0, 5) : [
    { label: 'Tháng 1', value: 20 }, { label: 'Tháng 2', value: 38 },
    { label: 'Tháng 3', value: 45 }, { label: 'Tháng 4', value: 82 }
  ];
  const maxVal = Math.max(1, ...bars.map(b => Number(b.value || 0)));
  const cx = 540;
  const cy = 820;
  const w = 780;
  const h = 480;
  const x0 = cx - w / 2 + 50;
  const y0 = cy + h / 2 - 40;
  const chartW = w - 100;
  const chartH = h - 100;

  // Background Grid Box
  shape(svg, 'rect', { x: cx - w / 2, y: cy - h / 2, width: w, height: h, rx: 28, fill: '#101e33', stroke: '#334155', 'stroke-width': 3 });

  // Grid lines
  for (let i = 0; i < 4; i++) {
    const gy = y0 - (chartH / 3) * i;
    shape(svg, 'line', { x1: x0, y1: gy, x2: x0 + chartW, y2: gy, stroke: '#1e293b', 'stroke-width': 2 });
  }

  // Calculate Points
  const pts = bars.map((b, i) => {
    const px = x0 + (i / Math.max(1, bars.length - 1)) * chartW;
    const py = y0 - (Number(b.value) / maxVal) * chartH;
    return [px, py];
  });

  const p = clamp(t / Math.max(0.8, duration * 0.5));
  const easeP = easeOutCubic(p);

  if (variantIdx === 0) {
    // Variant 1: bezier_draw_glow_peak
    let pathD = 'M ' + pts[0][0] + ' ' + pts[0][1];
    for (let i = 1; i < pts.length; i++) {
      const pPrev = pts[i - 1];
      const pCurr = pts[i];
      const cpx1 = pPrev[0] + (pCurr[0] - pPrev[0]) / 2;
      const cpx2 = cpx1;
      pathD += ' C ' + cpx1 + ' ' + pPrev[1] + ', ' + cpx2 + ' ' + pCurr[1] + ', ' + pCurr[0] + ' ' + pCurr[1];
    }

    const strokePath = shape(svg, 'path', {
      d: pathD, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 8,
      'stroke-linecap': 'round', pathLength: 1,
      'stroke-dasharray': 1, 'stroke-dashoffset': 1 - easeP
    });

    // Milestone dots & labels appearing as line reaches them
    bars.forEach((b, i) => {
      const nodeP = clamp((p - i / bars.length) * bars.length);
      if (nodeP > 0) {
        shape(svg, 'circle', { cx: pts[i][0], cy: pts[i][1], r: 10 * overshoot(nodeP, 2), fill: '#ffffff', stroke: 'var(--accent)', 'stroke-width': 4 });
        svg.append(el('text', {
          x: pts[i][0], y: pts[i][1] - 22, 'text-anchor': 'middle', 'font-size': '36', 'font-weight': 'bold', fill: 'var(--accent)'
        }, formatNum(b.value)));
        svg.append(el('text', {
          x: pts[i][0], y: y0 + 34, 'text-anchor': 'middle', 'font-size': '32', fill: '#94a3b8'
        }, b.label));
      }
    });

  } else if (variantIdx === 1) {
    // Variant 2: step_ladder_chart
    let stepD = 'M ' + pts[0][0] + ' ' + pts[0][1];
    for (let i = 1; i < pts.length; i++) {
      stepD += ' H ' + pts[i][0] + ' V ' + pts[i][1];
    }
    shape(svg, 'path', {
      d: stepD, fill: 'none', stroke: 'var(--secondary)', 'stroke-width': 8,
      pathLength: 1, 'stroke-dasharray': 1, 'stroke-dashoffset': 1 - easeP
    });
    bars.forEach((b, i) => {
      shape(svg, 'rect', { x: pts[i][0] - 10, y: pts[i][1] - 10, width: 20, height: 20, rx: 5, fill: 'var(--secondary)' });
    });

  } else {
    // Variant 3: straight polyline with area fill
    const polyPts = pts.map(pt => pt.join(',')).join(' ');
    shape(svg, 'polyline', {
      points: polyPts, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 7,
      pathLength: 1, 'stroke-dasharray': 1, 'stroke-dashoffset': 1 - easeP
    });
  }
}

// =========================================================================
// 12. TERMINAL_TYPING & CODE_CARD (3 Variants)
// =========================================================================
function renderTerminalTyping(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 5) : [
    'npm install ai-video-tool', 'Compiling visual pipeline...', 'Ready on http://localhost:8501'
  ];
  const cx = 540;
  const cy = 820;
  const w = 820;
  const h = 540;
  const x = cx - w / 2;
  const y = cy - h / 2;

  // Window frame
  shape(svg, 'rect', { x, y, width: w, height: h, rx: 26, fill: '#0a0f1d', stroke: '#1e293b', 'stroke-width': 4 });
  shape(svg, 'rect', { x, y, width: w, height: 60, rx: 26, fill: '#141e33' });
  shape(svg, 'rect', { x, y: y + 36, width: w, height: 24, fill: '#141e33' }); // flatten bottom corners

  // 3 macOS dots
  shape(svg, 'circle', { cx: x + 40, cy: y + 30, r: 10, fill: '#ef4444' });
  shape(svg, 'circle', { cx: x + 75, cy: y + 30, r: 10, fill: '#f59e0b' });
  shape(svg, 'circle', { cx: x + 110, cy: y + 30, r: 10, fill: '#10b981' });

  // Window title
  svg.append(el('text', {
    x: cx, y: y + 38, 'text-anchor': 'middle', 'font-size': '30', fill: '#64748b'
  }, d.title || 'terminal — bash — 80x24'));

  // Typing lines
  const startLineY = y + 120;
  const lineSpacing = 75;
  const totalChars = items.reduce((acc, it) => acc + String(it).length, 0);
  const typeProgress = clamp(t / Math.max(0.8, duration * 0.6));
  const currentChars = Math.floor(totalChars * easeOutCubic(typeProgress));

  let charsAccounted = 0;
  items.forEach((item, i) => {
    const lineY = startLineY + i * lineSpacing;
    const str = String(item);
    const lineChars = Math.max(0, Math.min(str.length, currentChars - charsAccounted));
    charsAccounted += str.length;

    const prefix = (variantIdx === 2) ? '$ ' : '> ';
    const visibleText = prefix + str.slice(0, lineChars);

    const isCurrentTyping = (lineChars > 0 && lineChars < str.length) || (i === 0 && lineChars === 0);
    const cursor = (isCurrentTyping && Math.floor(t * 4) % 2 === 0) ? '▋' : '';

    svg.append(el('text', {
      x: x + 50, y: lineY, 'font-size': '38', 'font-family': 'monospace',
      fill: i === 0 ? '#38bdf8' : (i === items.length - 1 ? '#4ade80' : '#e2e8f0'),
      class: 'ill-label'
    }, visibleText + cursor));
  });
}

// =========================================================================
// 13. TIMELINE (3 Variants)
// =========================================================================
function renderTimeline(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    '2021: Khởi động', '2023: Thử nghiệm', '2025: Đột phá quy mô'
  ];
  const cx = 540;
  const cy = 820;
  const p = clamp(t / Math.max(0.8, duration * 0.5));

  if (variantIdx === 0) {
    // Variant 1: horizontal_scroll_sprout
    const w = 820;
    const x0 = cx - w / 2 + 50;
    const lineW = (w - 100) * easeOutCubic(p);

    shape(svg, 'line', { x1: x0, y1: cy, x2: x0 + lineW, y2: cy, stroke: 'var(--accent)', 'stroke-width': 10, 'stroke-linecap': 'round' });

    items.forEach((item, i) => {
      const nodeX = x0 + (i / Math.max(1, items.length - 1)) * (w - 100);
      const nodeP = clamp((p - i / items.length) * items.length);
      if (nodeP > 0) {
        const s = overshoot(nodeP, 2.2);
        shape(svg, 'circle', { cx: nodeX, cy, r: 24 * s, fill: '#101e33', stroke: 'var(--accent)', 'stroke-width': 6 });
        shape(svg, 'circle', { cx: nodeX, cy, r: 10 * s, fill: 'var(--accent)' });

        const isTop = (i % 2 === 0);
        const cardY = isTop ? cy - 120 : cy + 80;
        shape(svg, 'line', { x1: nodeX, y1: cy, x2: nodeX, y2: isTop ? cy - 40 : cy + 40, stroke: '#334155', 'stroke-width': 4 });
        svg.append(el('text', {
          x: nodeX, y: cardY, 'text-anchor': 'middle', 'font-size': '38', 'font-weight': 'bold', fill: '#ffffff', class: 'ill-label'
        }, wrapText(item, 14, 1)[0] || item));
      }
    });

  } else {
    // Variant 2: vertical_zigzag_flow
    const h = 600;
    const y0 = cy - h / 2;
    shape(svg, 'line', { x1: cx, y1: y0, x2: cx, y2: y0 + h * easeOutCubic(p), stroke: 'var(--secondary)', 'stroke-width': 8 });

    items.forEach((item, i) => {
      const ny = y0 + (i / Math.max(1, items.length - 1)) * h;
      const nodeP = clamp((p - i / items.length) * items.length);
      if (nodeP > 0) {
        shape(svg, 'circle', { cx, cy: ny, r: 18 * overshoot(nodeP, 2), fill: 'var(--secondary)' });
        const isLeft = (i % 2 === 0);
        const tx = isLeft ? cx - 40 : cx + 40;
        svg.append(el('text', {
          x: tx, y: ny + 12, 'text-anchor': isLeft ? 'end' : 'start', 'font-size': '38', fill: '#f8fafc', class: 'ill-label'
        }, item));
      }
    });
  }
}

// =========================================================================
// 14. FUNNEL (3 Variants)
// =========================================================================
function renderFunnel(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    '1.000 Tiếp cận', '350 Quan tâm', '85 Đăng ký', '12 Chuyển đổi'
  ];
  const cx = 540;
  const cy = 820;
  const h = 580;
  const startY = cy - h / 2;
  const p = clamp(t / Math.max(0.8, duration * 0.45));

  const tierH = h / items.length;
  items.forEach((item, i) => {
    const tierP = clamp((p - i * 0.18) / 0.5);
    if (tierP > 0) {
      const topW = 760 - i * 140;
      const botW = 760 - (i + 1) * 140;
      const y1 = startY + i * tierH;
      const y2 = y1 + tierH - 12;

      const polyD = 'M ' + (cx - topW / 2) + ' ' + y1 + ' L ' + (cx + topW / 2) + ' ' + y1 + ' L ' + (cx + botW / 2) + ' ' + y2 + ' L ' + (cx - botW / 2) + ' ' + y2 + ' Z';
      const isBottom = (i === items.length - 1);

      shape(svg, 'path', {
        d: polyD, fill: isBottom ? 'var(--accent)' : '#101e33',
        stroke: isBottom ? '#ffffff' : '#334155', 'stroke-width': 4,
        opacity: clamp(tierP * 2)
      });

      svg.append(el('text', {
        x: cx, y: y1 + tierH / 2 + 8, 'text-anchor': 'middle', 'font-size': '38', 'font-weight': 'bold',
        fill: isBottom ? '#000000' : '#ffffff', class: 'ill-label'
      }, item));
    }
  });
}

// =========================================================================
// 15. PROGRESS_TRACKER (3 Variants)
// =========================================================================
function renderProgressTracker(ctx, svg, d, t, duration, variantIdx = 0) {
  const steps = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    'Thu thập', 'Phân tích', 'Kiểm chứng', 'Xuất bản'
  ];
  const cx = 540;
  const cy = 820;
  const w = 780;
  const p = clamp(t / Math.max(0.8, duration * 0.5));
  const activeStepIdx = Math.min(steps.length - 1, Math.floor(p * steps.length));

  const segW = (w - (steps.length - 1) * 16) / steps.length;
  const startX = cx - w / 2;

  steps.forEach((step, i) => {
    const sx = startX + i * (segW + 16);
    const isCompleted = (i <= activeStepIdx);

    shape(svg, 'rect', {
      x: sx, y: cy - 30, width: segW, height: 40, rx: 12,
      fill: isCompleted ? 'var(--accent)' : '#1e293b',
      stroke: isCompleted ? '#ffffff' : '#334155', 'stroke-width': 3
    });

    svg.append(el('text', {
      x: sx + segW / 2, y: cy + 55, 'text-anchor': 'middle', 'font-size': '34',
      fill: isCompleted ? '#ffffff' : '#64748b', class: 'ill-label'
    }, step));
  });
}

// =========================================================================
// 16. SOURCE_BADGE (3 Variants)
// =========================================================================
function renderSourceBadge(ctx, svg, d, t, duration, variantIdx = 0) {
  const sourceName = d.source || d.text || 'Báo cáo độc lập 2025';
  const cx = 540;
  const cy = 820;
  const p = clamp(t / 0.5);
  const s = overshoot(p, 2.2);

  const g = group(svg, {
    transform: 'translate(' + cx + ' ' + cy + ') scale(' + s + ')'
  });

  shape(g, 'rect', {
    x: -280, y: -70, width: 560, height: 140, rx: 28,
    fill: '#101e33', stroke: 'var(--accent)', 'stroke-width': 4
  });

  // Shield Icon
  shape(g, 'path', {
    d: 'M -220 -25 L -200 -35 L -180 -25 V -5 C -180 15 -200 30 -200 30 C -200 30 -220 15 -220 -5 Z',
    fill: 'var(--accent)'
  });

  g.append(el('text', {
    x: -150, y: -6, 'font-size': '32', fill: '#94a3b8'
  }, 'NGUỒN KIỂM CHỨNG:'));

  g.append(el('text', {
    x: -150, y: 35, 'font-size': '40', 'font-weight': 'bold', fill: '#ffffff', class: 'ill-label'
  }, wrapText(sourceName, 18, 1)[0] || sourceName));
}

// =========================================================================
// 17. ICON_TILE (3 Variants)
// =========================================================================
function renderIconTile(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    'Hiệu năng', 'Bảo mật', 'Mở rộng', 'Tiết kiệm'
  ];
  const cx = 540;
  const cy = 820;
  const tileSize = 320;
  const gap = 40;

  items.forEach((item, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const tx = cx - tileSize - gap / 2 + col * (tileSize + gap);
    const ty = cy - tileSize - gap / 2 + row * (tileSize + gap);

    const p = clamp((t - i * 0.15) / 0.45);
    if (p > 0) {
      const s = overshoot(p, 2.0);
      const gTile = group(svg, {
        transform: 'translate(' + (tx + tileSize / 2) + ' ' + (ty + tileSize / 2) + ') scale(' + s + ') translate(-' + (tx + tileSize / 2) + ' -' + (ty + tileSize / 2) + ')'
      });

      shape(gTile, 'rect', {
        x: tx, y: ty, width: tileSize, height: tileSize, rx: 32,
        fill: '#101e33', stroke: (i === 0) ? 'var(--accent)' : '#334155', 'stroke-width': 4
      });

      // Simple geometric icon
      shape(gTile, 'circle', { cx: tx + tileSize / 2, cy: ty + 110, r: 45, fill: (i === 0) ? 'var(--accent)' : '#334155' });

      gTile.append(el('text', {
        x: tx + tileSize / 2, y: ty + 220, 'text-anchor': 'middle', 'font-size': '38', 'font-weight': 'bold', fill: '#ffffff', class: 'ill-label'
      }, item));
    }
  });
}

// =========================================================================
// 18. CHAT_BUBBLE_POLL (3 Variants)
// =========================================================================
function renderChatBubblePoll(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 3) : [
    'Công nghệ này có an toàn?', 'Đạt chuẩn 99.9% qua kiểm nghiệm độc lập.', 'Chi phí triển khai ra sao?'
  ];
  const cx = 540;
  const cy = 820;
  const startY = cy - 220;
  const spacing = 150;

  items.forEach((item, i) => {
    const p = clamp((t - i * 0.35) / 0.45);
    if (p > 0) {
      const s = overshoot(p, 2.0);
      const isRight = (i % 2 === 1);
      const bw = 560;
      const bh = 110;
      const bx = isRight ? cx + 280 - bw : cx - 280;
      const by = startY + i * spacing;

      const gBubble = group(svg, {
        transform: 'translate(' + (bx + bw / 2) + ' ' + (by + bh / 2) + ') scale(' + s + ') translate(-' + (bx + bw / 2) + ' -' + (by + bh / 2) + ')'
      });

      shape(gBubble, 'rect', {
        x: bx, y: by, width: bw, height: bh, rx: 28,
        fill: isRight ? '#1e3a8a' : '#1e293b',
        stroke: isRight ? 'var(--accent)' : '#475569', 'stroke-width': 3
      });

      gBubble.append(el('text', {
        x: bx + 35, y: by + 68, 'font-size': '36', fill: '#ffffff', class: 'ill-label'
      }, wrapText(item, 20, 1)[0] || item));
    }
  });
}

// =========================================================================
// 19. GAUGE_RING (3 Variants)
// =========================================================================
function renderGaugeRing(ctx, svg, d, t, duration, variantIdx = 0) {
  const val = Number(d.value ?? 75);
  const cx = 540;
  const cy = 820;
  const r = 260;
  const p = clamp(t / Math.max(0.8, duration * 0.5));
  const easeP = easeOutCubic(p);

  // Background ring
  const circ = 2 * Math.PI * r;
  const sweepAngle = 270;
  const arcLength = circ * (sweepAngle / 360);

  shape(svg, 'circle', {
    cx, cy, r, fill: 'none', stroke: '#1e293b', 'stroke-width': 38,
    'stroke-dasharray': arcLength + ' ' + circ,
    transform: 'rotate(135 ' + cx + ' ' + cy + ')'
  });

  // Animated colored stroke
  const currentArc = arcLength * (val / 100) * easeP;
  shape(svg, 'circle', {
    cx, cy, r, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 38,
    'stroke-linecap': 'round',
    'stroke-dasharray': currentArc + ' ' + circ,
    transform: 'rotate(135 ' + cx + ' ' + cy + ')'
  });

  // Center display
  svg.append(el('text', {
    x: cx, y: cy + 25, 'text-anchor': 'middle', 'font-size': '110', 'font-weight': 'bold', fill: '#ffffff'
  }, formatNum(val * easeP) + (d.unit || '%')));

  svg.append(el('text', {
    x: cx, y: cy + 120, 'text-anchor': 'middle', 'font-size': '40', fill: '#94a3b8', class: 'ill-label'
  }, d.label || d.text || 'Chỉ số hoàn thành'));
}

// =========================================================================
// 20. FULL 10 ANNOTATIONS
// =========================================================================
function renderAnnotation(svg, annot, targetBounds, t) {
  const atTime = Number(annot.at_sec ?? 0.6);
  const dt = t - atTime;
  if (dt < 0) return;
  const progress = clamp(dt / 0.45);
  const type = annot.type;
  const bx = targetBounds.x;
  const by = targetBounds.y;
  const bw = targetBounds.w;
  const bh = targetBounds.h;

  if (type === 'strike') {
    // 1. Dynamic drawn strike line
    const p = easeOutCubic(progress);
    shape(svg, 'line', {
      x1: bx - 15, y1: by + bh / 2 + 10,
      x2: bx - 15 + (bw + 30) * p, y2: by + bh / 2 - 10,
      stroke: '#ef4444', 'stroke-width': 10, 'stroke-linecap': 'round'
    });

  } else if (type === 'stamp') {
    // 2. Rubber stamp falling with overshoot bounce
    const s = overshoot(progress, 2.4);
    const angle = -10 + (hashSeed(annot.text || 'stamp') % 20);
    const gStamp = group(svg, {
      transform: 'translate(' + (bx + bw / 2) + ' ' + (by + bh / 2) + ') rotate(' + angle + ') scale(' + s + ') translate(-' + (bx + bw / 2) + ' -' + (by + bh / 2) + ')',
      opacity: clamp(progress * 3)
    });
    const stampW = Math.max(220, bw * 0.7);
    const stampH = 75;
    const sx = bx + bw / 2 - stampW / 2;
    const sy = by + bh / 2 - stampH / 2;
    shape(gStamp, 'rect', {
      x: sx, y: sy, width: stampW, height: stampH, rx: 14,
      fill: 'none', stroke: '#ef4444', 'stroke-width': 6, 'stroke-dasharray': '12 6'
    });
    gStamp.append(el('text', {
      x: bx + bw / 2, y: by + bh / 2 + 14,
      'text-anchor': 'middle', 'font-size': '38', 'font-weight': 'bold',
      fill: '#ef4444', 'letter-spacing': '2px'
    }, annot.text || 'ƯỚC LƯỢNG'));

  } else if (type === 'underline') {
    // 3. Handwritten neon brush underline
    const p = easeOutCubic(progress);
    const waveW = bw * p;
    shape(svg, 'path', {
      d: 'M ' + bx + ' ' + (by + bh + 12) + ' Q ' + (bx + waveW / 2) + ' ' + (by + bh + 24) + ' ' + (bx + waveW) + ' ' + (by + bh + 14),
      stroke: 'var(--accent)', 'stroke-width': 8, fill: 'none', 'stroke-linecap': 'round'
    });

  } else if (type === 'question') {
    // 4. Bouncing Question Mark with wobble
    const s = overshoot(progress, 2.6);
    const wobble = Math.sin(progress * Math.PI * 4) * 8;
    const gQ = group(svg, {
      transform: 'translate(' + (bx + bw + 35) + ' ' + (by + 20) + ') rotate(' + wobble + ') scale(' + s + ')'
    });
    gQ.append(el('text', {
      x: 0, y: 0, 'text-anchor': 'middle', 'font-size': '75', 'font-weight': 'bold', fill: '#facc15'
    }, '?'));

  } else if (type === 'check') {
    // 5. Hand-drawn checkmark stroke
    const p = easeOutCubic(progress);
    const checkD = 'M ' + (bx + bw - 20) + ' ' + (by + bh / 2) + ' L ' + (bx + bw) + ' ' + (by + bh / 2 + 25) + ' L ' + (bx + bw + 45) + ' ' + (by + bh / 2 - 30);
    shape(svg, 'path', {
      d: checkD, fill: 'none', stroke: '#22c55e', 'stroke-width': 10, 'stroke-linecap': 'round',
      pathLength: 1, 'stroke-dasharray': 1, 'stroke-dashoffset': 1 - p
    });

  } else if (type === 'cross') {
    // 6. Hand-drawn X cross
    const p = easeOutCubic(progress);
    const cx0 = bx + bw;
    const cy0 = by + bh / 2;
    shape(svg, 'line', {
      x1: cx0 - 25, y1: cy0 - 25, x2: cx0 - 25 + 50 * p, y2: cy0 - 25 + 50 * p,
      stroke: '#ef4444', 'stroke-width': 10, 'stroke-linecap': 'round'
    });
    if (progress > 0.4) {
      const p2 = easeOutCubic((progress - 0.4) / 0.6);
      shape(svg, 'line', {
        x1: cx0 + 25, y1: cy0 - 25, x2: cx0 + 25 - 50 * p2, y2: cy0 - 25 + 50 * p2,
        stroke: '#ef4444', 'stroke-width': 10, 'stroke-linecap': 'round'
      });
    }

  } else if (type === 'arrow') {
    // 7. Bezier Curved Arrow pointing at target
    const p = easeOutCubic(progress);
    const startAx = bx - 120;
    const startAy = by + bh + 60;
    const targetAx = bx - 10;
    const targetAy = by + bh / 2;
    shape(svg, 'path', {
      d: 'M ' + startAx + ' ' + startAy + ' Q ' + (startAx + 60) + ' ' + startAy + ' ' + targetAx + ' ' + targetAy,
      fill: 'none', stroke: 'var(--accent)', 'stroke-width': 7, 'stroke-linecap': 'round',
      pathLength: 1, 'stroke-dasharray': 1, 'stroke-dashoffset': 1 - p
    });
    if (p > 0.8) {
      // Arrow head
      shape(svg, 'polygon', {
        points: targetAx + ',' + targetAy + ' ' + (targetAx - 20) + ',' + (targetAy - 15) + ' ' + (targetAx - 15) + ',' + (targetAy + 15),
        fill: 'var(--accent)'
      });
    }

  } else if (type === 'circle_highlight') {
    // 8. Hand-drawn elliptical loop wrapping target
    const p = easeOutCubic(progress);
    const rx = bw / 2 + 30;
    const ry = bh / 2 + 20;
    const cx0 = bx + bw / 2;
    const cy0 = by + bh / 2;
    shape(svg, 'ellipse', {
      cx: cx0, cy: cy0, rx, ry, fill: 'none', stroke: '#f59e0b', 'stroke-width': 6,
      'stroke-linecap': 'round',
      pathLength: 1, 'stroke-dasharray': 1, 'stroke-dashoffset': 1 - p
    });

  } else if (type === 'tag') {
    // 9. Tag badge pop (e.g. x5, HOT)
    const s = overshoot(progress, 2.4);
    const gTag = group(svg, {
      transform: 'translate(' + (bx + bw + 10) + ' ' + (by - 25) + ') scale(' + s + ')'
    });
    shape(gTag, 'rect', {
      x: 0, y: 0, width: 85, height: 45, rx: 12, fill: '#ff007f'
    });
    gTag.append(el('text', {
      x: 42, y: 30, 'text-anchor': 'middle', 'font-size': '26', 'font-weight': 'bold', fill: '#ffffff'
    }, annot.text || 'x5'));

  } else if (type === 'pencil') {
    // 10. Pencil tip drawing stroke
    const p = easeOutCubic(progress);
    const lineX = bx + bw * p;
    shape(svg, 'line', {
      x1: bx, y1: by + bh + 15, x2: lineX, y2: by + bh + 15,
      stroke: 'var(--secondary)', 'stroke-width': 7, 'stroke-linecap': 'round'
    });
    // Pencil icon tip following the stroke
    const gPencil = group(svg, {
      transform: 'translate(' + lineX + ' ' + (by + bh + 15) + ') rotate(45)'
    });
    shape(gPencil, 'polygon', { points: '0,0 -8,-25 8,-25', fill: '#facc15' });
    shape(gPencil, 'polygon', { points: '0,0 -3,-8 3,-8', fill: '#000000' });
  }
}

window.MotionRecipes = {
  renderStatNumber,
  renderBarCompare,
  renderFlowChain,
  renderHubSpoke,
  renderContainerFill,
  renderChecklist,
  renderMockUIWindow,
  renderMagnifierCheck,
  renderVersusSplit,
  renderLineChartDraw,
  renderTerminalTyping,
  renderTimeline,
  renderFunnel,
  renderProgressTracker,
  renderSourceBadge,
  renderIconTile,
  renderChatBubblePoll,
  renderGaugeRing,
  renderAnnotation
};
})();
