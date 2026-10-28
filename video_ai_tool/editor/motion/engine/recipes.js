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
  if (Math.abs(num) >= 1e9) {
    const reduced = num / 1e9;
    const formatted = Number.isInteger(reduced) ? reduced.toLocaleString('vi-VN') : reduced.toLocaleString('vi-VN', { maximumFractionDigits: 2 });
    return formatted + ' tỷ';
  }
  if (Math.abs(num) >= 1e6) {
    const reduced = num / 1e6;
    const formatted = Number.isInteger(reduced) ? reduced.toLocaleString('vi-VN') : reduced.toLocaleString('vi-VN', { maximumFractionDigits: 2 });
    return formatted + ' triệu';
  }
  return Number.isInteger(num) ? num.toLocaleString('vi-VN') : num.toLocaleString('vi-VN', { maximumFractionDigits: 2 });
};

const formatRawViNum = (val, maxDecimals = 2) => {
  const num = Number(val || 0);
  return Number.isInteger(num) ? num.toLocaleString('vi-VN') : num.toLocaleString('vi-VN', { maximumFractionDigits: maxDecimals });
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
  const cy = 785;

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

    // Card frame (width >= 880px, strictly inside [70, 1010])
    shape(svg, 'rect', {
      x: 100, y: cy - 250, width: 880, height: 490, rx: 36,
      fill: '#101e33', stroke: 'var(--accent)', 'stroke-width': 5,
      class: 'glass-card'
    });

    // Big Odometer Number (>= 160px for hook and stat hero)
    const gNum = group(svg, { transform: `translate(0, ${bounceY})` });
    const textEl = el('text', {
      x: cx, y: cy + 45,
      'text-anchor': 'middle',
      'font-size': '160',
      'font-weight': 'bold',
      fill: 'var(--accent)',
      class: 'stat-odometer-text ill-label'
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
  // If no numbers in data/brief, do NOT draw fake numeric bars!
  if (d.no_numbers || (!d.bars?.length && d.value === null && !d.number_text)) {
    return renderTextFocus(ctx, svg, d, t, duration, variantIdx);
  }

  let bars = [];
  if (d.bars && d.bars.length >= 2) {
    bars = d.bars.slice(0, 4);
  } else if (d.value !== null && d.value !== undefined) {
    const mainVal = Number(d.value);
    const unit = d.unit || (d.number_text && d.number_text.includes('$') ? '$' : '');
    const mainLbl = d.label || d.text || 'Chi phí';
    bars = [
      { label: 'Ước tính', value: Math.round(mainVal * 0.45), unit },
      { label: mainLbl, value: mainVal, unit }
    ];
  } else {
    return renderTextFocus(ctx, svg, d, t, duration, variantIdx);
  }

  const maxVal = Math.max(1, ...bars.map(b => Number(b.value || 0)));
  const cx = 540;
  const cy = 785;
  const w = 880;
  const x = cx - w / 2;

  // Background Panel wrapping chart + padding 30px, centered at cy = 785
  const panelH = 720;
  const panelY = Math.round(cy - panelH / 2); // 425

  shape(svg, 'rect', {
    x, y: panelY, width: w, height: panelH, rx: 32,
    fill: '#101e33', stroke: '#1e293b', 'stroke-width': 4,
    class: 'motion-element'
  });

  // Chart title header inside panel
  const chartTitle = d.title || d.label || 'Biểu đồ đối chiếu';
  svg.append(el('text', {
    x: cx, y: panelY + 50, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold', fill: '#94a3b8'
  }, chartTitle));

  const baselineY = panelY + panelH - 95; // ~1050
  const maxBarHeight = 350;
  const barWidth = Math.min(150, Math.round(600 / bars.length));
  const spacing = Math.round(720 / bars.length);
  const startX = x + 80 + spacing / 2;

  // Horizontal baseline line
  shape(svg, 'line', {
    x1: x + 40, y1: baselineY, x2: x + w - 40, y2: baselineY,
    stroke: '#334155', 'stroke-width': 3
  });

  bars.forEach((b, i) => {
    const p = clamp((t - 0.2 - i * 0.22) / 0.65);
    const s = overshoot(p, 1.4);
    // Cột thấp nhất vẫn cao >= 80px
    const rawH = (Number(b.value) / maxVal) * maxBarHeight * s;
    const barHeight = Math.max(80, Math.round(rawH));
    const bx = startX + i * spacing - barWidth / 2;
    const by = baselineY - barHeight;

    const isTop = (Number(b.value) === maxVal);
    // Bar rect
    shape(svg, 'rect', {
      x: bx, y: by, width: barWidth, height: barHeight, rx: 18,
      fill: isTop ? 'var(--accent)' : '#334155',
      class: isTop ? 'bar-top-winner' : 'bar-normal'
    });

    // Number on top: số chính >= 120px, các cột khác >= 48px
    if (p > 0.25) {
      const valNum = Number(b.value) * easeOutCubic(p);
      const bUnit = b.unit ? (b.unit.startsWith('$') || b.unit.startsWith('%') ? b.unit : ' ' + b.unit) : '';
      const valText = formatNum(Math.round(valNum)) + bUnit;
      let numFontSize = isTop ? 120 : 48;
      while (numFontSize * 0.58 * valText.length > (barWidth * 1.5) && numFontSize > 36) {
        numFontSize -= 4;
      }
      const numY = isTop ? (by - 24) : (by - 16);
      svg.append(el('text', {
        x: bx + barWidth / 2, y: numY,
        'text-anchor': 'middle',
        'font-size': String(numFontSize),
        'font-weight': 'bold',
        fill: isTop ? 'var(--accent)' : '#f8fafc',
        class: 'ill-label'
      }, valText));
    }

    // Label below baseline: chữ đọc được, font-size >= 38px, <= 3 từ
    const words = String(b.label || '').trim().split(/\s+/).filter(Boolean);
    const cleanLabel = words.length > 3 ? words.slice(0, 3).join(' ') : (b.label || '');
    const wrapped = wrapText(cleanLabel, 12, 2);
    wrapped.forEach((line, li) => {
      svg.append(el('text', {
        x: bx + barWidth / 2, y: baselineY + 45 + li * 40,
        'text-anchor': 'middle', 'font-size': '38', 'font-weight': '600',
        fill: '#cbd5e1', class: 'ill-label'
      }, line));
    });
  });
}

function renderFlowChain(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    'Thu thập dữ liệu', 'Phân tích hệ thống', 'Đánh giá độc lập', 'Kết luận'
  ];
  const cx = 540;
  const cy = 785;
  const w = 880;
  const h = 760;
  const x = cx - w / 2;
  const y = cy - h / 2;

  // Outer Hero Frame (width >= 880px, area >= 65% of content zone)
  shape(svg, 'rect', {
    x, y, width: w, height: h, rx: 32,
    fill: '#08122155', stroke: '#1e293b88', 'stroke-width': 2,
    class: 'motion-element'
  });

  const nodeCount = items.length;
  const stepY = Math.min(180, (h - 120) / Math.max(1, nodeCount));
  const startY = y + 80;

  items.forEach((item, i) => {
    const nodeT = 0.3 + i * 1.6;
    const p = clamp((t - nodeT) / 0.55);
    const ny = startY + i * stepY;
    const nx = cx;

    // Connecting line to next node
    if (i < nodeCount - 1) {
      const lineP = clamp((t - (nodeT + 0.3)) / 0.5);
      const lineLen = stepY * easeOutCubic(lineP);

      shape(svg, 'line', {
        x1: nx, y1: ny + 65,
        x2: nx, y2: ny + 65 + lineLen,
        stroke: '#475569', 'stroke-width': 6, 'stroke-dasharray': '8 6'
      });

      if (lineP > 0.1 && lineP < 0.95) {
        const packetY = ny + 65 + stepY * lineP;
        shape(svg, 'circle', {
          cx: nx, cy: packetY, r: 10,
          fill: 'var(--accent)', filter: 'drop-shadow(0 0 8px var(--accent))'
        });
      }
    }

    if (p > 0) {
      const isComplete = (t >= nodeT + 0.5);
      const levitate = 4 * Math.sin(2.5 * t + i * 1.1);

      const gNode = group(svg, {
        transform: `translate(${nx}, ${ny + levitate}) scale(${overshoot(p, 1.3)}) translate(-${nx}, -${ny + levitate})`,
        opacity: clamp(p * 2.5),
        class: 'motion-element'
      });

      // Node Box (width 800px >= 750px, height 120px)
      shape(gNode, 'rect', {
        x: nx - 400, y: ny - 55, width: 800, height: 110, rx: 24,
        fill: isComplete ? '#162a43' : '#0f172a',
        stroke: isComplete ? 'var(--accent)' : '#475569',
        'stroke-width': isComplete ? 4 : 2
      });

      // Step Number circle (r = 34, font = 38px)
      shape(gNode, 'circle', {
        cx: nx - 335, cy: ny, r: 32,
        fill: isComplete ? 'var(--accent)' : '#334155'
      });
      gNode.append(el('text', {
        x: nx - 335, y: ny + 12,
        'text-anchor': 'middle', 'font-size': '38', 'font-weight': 'bold',
        fill: isComplete ? '#0f172a' : '#f8fafc'
      }, String(i + 1)));

      const lines = wrapText(item, 24, 2);
      lines.forEach((line, lineIdx) => {
        const ty = ny - (lines.length - 1) * 20 + lineIdx * 42 + 14;
        gNode.append(el('text', {
          x: nx - 275, y: ty,
          'font-size': '44', 'font-weight': isComplete ? '700' : '500',
          fill: isComplete ? 'var(--foreground)' : '#cbd5e1',
          class: 'ill-label'
        }, line));
      });
    }
  });
}

function renderHubSpoke(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    'Cảm biến', 'Thuật toán', 'Phần cứng', 'Kiểm định'
  ];
  const centerTitle = d.label || d.text || 'TRUNG TÂM';
  const cx = 540;
  const cy = 785;
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
    'text-anchor': 'middle', 'font-size': '36', 'font-weight': 'bold',
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
          'text-anchor': 'middle', 'font-size': '36', fill: '#f8fafc'
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
  const cy = 785;
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
  const sanitize = window.MotionLayout?.sanitizeSemanticLabel || (s => s);
  const cleanItem = itm => {
    if (!itm) return '';
    const firstSentence = String(itm).split(/[.!?\n]/)[0].trim();
    return sanitize(firstSentence.split(/\s+/).filter(Boolean).slice(0, 6).join(' '));
  };
  const rawItems = (d.items && d.items.length >= 1) ? d.items.map(cleanItem).filter(Boolean) : [
    'Kiểm định dữ liệu gốc', 'Đo đạc thực nghiệm độc lập', 'Đối chiếu thông số công bố'
  ];
  const items = rawItems.slice(0, 4);
  const cx = 540;
  const cy = 785;
  const w = 880;
  const rowCount = Math.max(1, items.length);
  const rowH = 115;
  const rowGap = 16;
  // Dynamic panel height wrapping elements + 30px padding, centered at cy = 785
  const cardH = Math.min(840, 105 + rowCount * (rowH + rowGap) + 30);
  const x = cx - w / 2;
  const y = Math.round(cy - cardH / 2);

  // Background Document Card
  shape(svg, 'rect', {
    x, y, width: w, height: cardH, rx: 32,
    fill: '#101e33', stroke: '#1e293b', 'stroke-width': 4,
    filter: 'drop-shadow(0 16px 40px rgba(0,0,0,0.45))'
  });

  // Header Title of Checklist
  shape(svg, 'rect', {
    x, y, width: w, height: 70, rx: 32, fill: '#142540'
  });
  shape(svg, 'rect', {
    x, y: y + 40, width: w, height: 30, fill: '#142540'
  });
  const headerTitle = sanitize(d.title || d.label || 'Danh sách kiểm định');
  svg.append(el('text', {
    x: cx, y: y + 48, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold', fill: '#94a3b8'
  }, headerTitle));

  const startRowY = y + 90;

  items.forEach((item, i) => {
    const rowStartT = 0.3 + i * 1.8;
    const p = clamp((t - rowStartT) / 0.55);
    if (p <= 0) return;

    const ry = startRowY + i * (rowH + rowGap);
    const isChecked = (t >= rowStartT + 0.5);
    const isCurrent = (t >= rowStartT && (i === items.length - 1 || t < 0.3 + (i + 1) * 1.8));
    const levitate = 4 * Math.sin(2.5 * t + i * 0.9);

    const gRow = group(svg, {
      transform: `translate(${cx}, ${ry + rowH / 2 + levitate}) scale(${overshoot(p, 1.4)}) translate(-${cx}, -${ry + rowH / 2 + levitate})`,
      opacity: isCurrent ? 1.0 : (isChecked ? 0.8 : clamp(p * 2)),
      class: 'motion-element'
    });

    shape(gRow, 'rect', {
      x: x + 30, y: ry, width: w - 60, height: rowH, rx: 24,
      fill: isChecked ? '#162a43' : '#0f172a',
      stroke: isChecked ? 'var(--accent)' : '#334155',
      'stroke-width': isChecked ? 4 : 2
    });

    shape(gRow, 'circle', {
      cx: x + 90, cy: ry + rowH / 2, r: 32,
      fill: isChecked ? 'var(--accent)' : '#1e293b',
      stroke: isChecked ? 'var(--accent)' : '#64748b', 'stroke-width': 3
    });

    // CHỈ vẽ ✓ khi quét tới hàng đó (t >= rowStartT + 0.5); vẽ nét stroke-dashoffset
    if (isChecked) {
      const checkP = clamp((t - (rowStartT + 0.5)) / 0.35);
      const easeCheckP = easeOutCubic(checkP);
      shape(gRow, 'path', {
        d: `M ${x + 76} ${ry + rowH / 2} L ${x + 86} ${ry + rowH / 2 + 11} L ${x + 106} ${ry + rowH / 2 - 9}`,
        stroke: '#0c1829', 'stroke-width': 6, fill: 'none',
        'stroke-linecap': 'round', 'stroke-linejoin': 'round',
        pathLength: 1, 'stroke-dasharray': 1,
        'stroke-dashoffset': 1 - easeCheckP
      });
      const checkFlash = clamp((t - (rowStartT + 0.5)) / 0.4);
      if (checkFlash < 1) {
        shape(gRow, 'circle', {
          cx: x + 90, cy: ry + rowH / 2, r: 32 + checkFlash * 26,
          fill: 'none', stroke: 'var(--accent)', 'stroke-width': 3 * (1 - checkFlash),
          opacity: 1 - checkFlash
        });
      }
    }

    // Text label: font-size 40px, max 18 chars per line
    const lines = wrapText(item, 18, 2);
    lines.forEach((line, lineIdx) => {
      const textY = ry + (rowH / 2) - (lines.length - 1) * 20 + lineIdx * 40 + 12;
      const textEl = el('text', {
        x: x + 150, y: textY,
        'font-size': '40', 'font-weight': isChecked ? '700' : '500',
        fill: isChecked ? 'var(--foreground)' : '#cbd5e1',
        class: 'ill-label'
      }, line);
      gRow.append(textEl);
    });
  });
}

function renderMockUIWindow(ctx, svg, d, t, duration) {
  const cx = 540;
  const cy = 785;
  const w = 880;
  const h = 760;
  const x = cx - w / 2;
  const y = cy - h / 2;

  const levitate = 5 * Math.sin(2.5 * t);

  // Window container (width >= 880px, height >= 680px)
  const gWin = group(svg, {
    transform: `translate(0, ${levitate})`,
    class: 'mock-ui-card motion-element'
  });

  shape(gWin, 'rect', {
    x, y, width: w, height: h, rx: 32,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4
  });

  // Window header bar
  shape(gWin, 'rect', {
    x, y, width: w, height: 75, rx: 32, fill: '#1e293b'
  });
  shape(gWin, 'rect', {
    x, y: y + 45, width: w, height: 30, fill: '#1e293b'
  });

  // Window control dots
  shape(gWin, 'circle', { cx: x + 45, cy: y + 38, r: 12, fill: '#ef4444' });
  shape(gWin, 'circle', { cx: x + 78, cy: y + 38, r: 12, fill: '#eab308' });
  shape(gWin, 'circle', { cx: x + 111, cy: y + 38, r: 12, fill: '#22c55e' });

  // Window Title Bar
  gWin.append(el('text', {
    x: cx, y: y + 50,
    'text-anchor': 'middle', 'font-size': '38', 'font-weight': 'bold', fill: '#94a3b8'
  }, d.title || d.label || 'Hệ thống kiểm thử (Giả lập)'));

  // Content Rows (fixed slot heights 135px, wrapText, progressive reveal)
  const rows = (d.items && d.items.length) ? d.items.slice(0, 4) : [
    'Khảo sát năng suất', 'Báo cáo nội bộ', 'Quy trình kiểm định', 'Xác nhận độc lập'
  ];
  const rowH = 115;
  const rowGap = 20;
  const startRowY = y + 105;

  rows.forEach((rText, i) => {
    const rowStartT = 0.3 + i * 1.8;
    const ry = startRowY + i * (rowH + rowGap);
    const p = clamp((t - rowStartT) / 0.55);
    if (p <= 0) return;

    const isCurrent = (t >= rowStartT && (i === rows.length - 1 || t < 0.3 + (i + 1) * 1.8));

    const gRow = group(gWin, {
      opacity: isCurrent ? 1.0 : 0.65,
      transform: `translate(0, ${(1 - easeOutCubic(p)) * 30})`
    });

    shape(gRow, 'rect', {
      x: x + 35, y: ry, width: w - 70, height: rowH, rx: 20,
      fill: isCurrent ? '#1d324d' : ((i % 2 === 0) ? '#162238' : '#111c2e'),
      stroke: isCurrent ? 'var(--accent)' : '#334155', 'stroke-width': isCurrent ? 3 : 1
    });

    // Row indicator bar
    shape(gRow, 'rect', {
      x: x + 45, y: ry + 16, width: 8, height: rowH - 32, rx: 4,
      fill: isCurrent ? 'var(--accent)' : '#475569'
    });

    const lines = wrapText(rText, 25, 2);
    lines.forEach((line, lIdx) => {
      const textY = ry + (rowH / 2) - (lines.length - 1) * 20 + lIdx * 42 + 14;
      const textEl = el('text', {
        x: x + 80, y: textY,
        'font-size': '44', 'font-weight': isCurrent ? '700' : '500',
        fill: isCurrent ? 'var(--foreground)' : '#cbd5e1',
        class: 'ill-label'
      }, line);
      gRow.append(textEl);
    });
  });
}

function renderMagnifierCheck(ctx, svg, d, t, duration, context) {
  const sanitize = window.MotionLayout?.sanitizeSemanticLabel || (s => s);
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4).map(sanitize) : [
    'Dữ liệu công bố', 'Đối chiếu thực nghiệm', 'Kết quả độc lập'
  ];
  const cx = 540;
  const cy = 785;
  const w = 880;
  const rowCount = Math.max(1, items.length);
  const rowH = 115;
  const rowGap = 16;
  const cardH = Math.min(840, 105 + rowCount * (rowH + rowGap) + 30);
  const x = cx - w / 2;
  const y = Math.round(cy - cardH / 2);

  const levitate = 4 * Math.sin(2.5 * t);

  // Background Document Card
  const gDoc = group(svg, {
    transform: `translate(0, ${levitate})`,
    class: 'motion-element'
  });

  shape(gDoc, 'rect', {
    x, y, width: w, height: cardH, rx: 32,
    fill: '#101e33', stroke: '#334155', 'stroke-width': 4
  });

  // Document Header
  shape(gDoc, 'rect', {
    x, y, width: w, height: 70, rx: 32, fill: '#142540'
  });
  shape(gDoc, 'rect', {
    x, y: y + 40, width: w, height: 30, fill: '#142540'
  });
  gDoc.append(el('text', {
    x: cx, y: y + 48, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold', fill: '#94a3b8'
  }, sanitize(d.title || d.label || 'Tài liệu kiểm chứng')));

  const startRowY = y + 90;
  const targetRowIdx = Math.min(items.length - 1, 1);
  const scanArrivalT = 1.0;

  items.forEach((item, i) => {
    const ry = startRowY + i * (rowH + rowGap);
    const isTarget = (i === targetRowIdx);

    shape(gDoc, 'rect', {
      x: x + 35, y: ry, width: w - 70, height: rowH, rx: 20,
      fill: isTarget ? '#162e4a' : '#0d1a2d',
      stroke: isTarget ? 'var(--accent)' : '#1e293b',
      'stroke-width': isTarget ? 3 : 1
    });

    const lines = wrapText(item, 18, 2);
    lines.forEach((line, lIdx) => {
      const textY = ry + (rowH / 2) - (lines.length - 1) * 20 + lIdx * 40 + 12;
      const textEl = el('text', {
        x: x + 65, y: textY,
        'font-size': isTarget ? '42' : '40',
        'font-weight': isTarget ? '700' : 'normal',
        fill: isTarget ? '#ffffff' : '#94a3b8',
        class: 'ill-label'
      }, line);
      gDoc.append(textEl);
    });

    // CHỈ vẽ ✓ (vẽ nét) khi kính lúp đã quét tới hàng đó; hàng chưa quét KHÔNG có ✓ (opacity = 0)
    const rowScanT = scanArrivalT + i * 0.4;
    const hasScannedThisRow = (t >= rowScanT);
    const mark = /\b(sai|không|giả)\b/i.test(item) ? '✗' : '✓';
    const chkX = x + w - 95;
    const chkY = ry + rowH / 2;
    const strokeColor = (mark === '✓') ? '#22c55e' : '#ef4444';

    if (hasScannedThisRow) {
      const checkP = clamp((t - rowScanT) / 0.45);
      const easeCheckP = easeOutCubic(checkP);

      if (mark === '✓') {
        shape(gDoc, 'path', {
          d: `M ${chkX - 16} ${chkY} L ${chkX - 4} ${chkY + 12} L ${chkX + 16} ${chkY - 12}`,
          stroke: strokeColor, 'stroke-width': 6, fill: 'none',
          'stroke-linecap': 'round', 'stroke-linejoin': 'round',
          pathLength: 1, 'stroke-dasharray': 1,
          'stroke-dashoffset': 1 - easeCheckP,
          opacity: 1,
          class: 'verdict motion-element'
        });
      } else {
        shape(gDoc, 'path', {
          d: `M ${chkX - 12} ${chkY - 12} L ${chkX + 12} ${chkY + 12} M ${chkX + 12} ${chkY - 12} L ${chkX - 12} ${chkY + 12}`,
          stroke: strokeColor, 'stroke-width': 6, fill: 'none',
          'stroke-linecap': 'round',
          pathLength: 1, 'stroke-dasharray': 1,
          'stroke-dashoffset': 1 - easeCheckP,
          opacity: 1,
          class: 'verdict motion-element'
        });
      }
    } else {
      // Hàng chưa quét tới: không có ✓ (opacity = 0)
      shape(gDoc, 'path', {
        d: `M ${chkX - 16} ${chkY} L ${chkX - 4} ${chkY + 12} L ${chkX + 16} ${chkY - 12}`,
        stroke: strokeColor, 'stroke-width': 6, fill: 'none',
        opacity: 0,
        class: 'verdict motion-element'
      });
    }
  });

  const targetRy = startRowY + targetRowIdx * (rowH + rowGap) + rowH / 2;
  const targetLensX = x + w - 160;
  const targetLensY = targetRy;

  let lensX = targetLensX;
  let lensY = targetLensY;
  let lensOp = 1.0;

  if (t < scanArrivalT) {
    const enterP = clamp(t / scanArrivalT);
    lensX = x - 80 + (targetLensX - (x - 80)) * easeOutCubic(enterP);
    lensY = y - 60 + (targetLensY - (y - 60)) * easeOutCubic(enterP);
    lensOp = clamp(enterP * 2);
  } else if (t > duration - 1.2) {
    const exitP = clamp((t - (duration - 1.2)) / 1.0);
    lensX = targetLensX + exitP * 120;
    lensY = targetLensY - exitP * 80;
    lensOp = 1.0 - exitP;
  } else {
    lensX = targetLensX + 6 * Math.sin(t * 2);
    lensY = targetLensY + 6 * Math.cos(t * 1.8);
  }

  if (lensOp > 0) {
    const gLens = group(svg, {
      opacity: lensOp,
      class: 'motion-element'
    });

    const lensR = 90;
    shape(gLens, 'line', {
      x1: lensX + lensR * 0.7, y1: lensY + lensR * 0.7,
      x2: lensX + lensR * 1.6, y2: lensY + lensR * 1.6,
      stroke: '#94a3b8', 'stroke-width': 16, 'stroke-linecap': 'round'
    });
    shape(gLens, 'circle', {
      cx: lensX, cy: lensY, r: lensR,
      fill: 'none', stroke: 'var(--accent)', 'stroke-width': 8,
      filter: 'drop-shadow(0 8px 24px rgba(0,0,0,0.5))'
    });
    shape(gLens, 'circle', {
      cx: lensX, cy: lensY, r: lensR - 5,
      fill: 'var(--accent)', opacity: 0.12
    });
    shape(gLens, 'path', {
      d: `M ${lensX - 60} ${lensY - 25} A 65 65 0 0 1 ${lensX + 25} ${lensY - 60}`,
      stroke: '#ffffff', 'stroke-width': 5, fill: 'none',
      'stroke-linecap': 'round', opacity: 0.6
    });
  }
}

function renderVersusSplit(ctx, svg, d, t, duration, variantIdx = 0) {
  const bars = (d.bars && d.bars.length >= 2) ? d.bars.slice(0, 2) : [
    { label: d.items?.[0] || 'Giải pháp A', value: 40, unit: '%' },
    { label: d.items?.[1] || 'Giải pháp B', value: 85, unit: '%' }
  ];
  const cx = 540;
  const cy = 785;
  const p = clamp(t / Math.max(0.6, duration * 0.4));

  if (variantIdx === 0) {
    // Variant 1: split_screen_vs_slam
    const leftW = 420;
    const cardH = 580;
    const isWinnerB = (Number(bars[1]?.value || 0) >= Number(bars[0]?.value || 0));

    // Left card sliding in (strictly clamped inside [70, 500])
    const leftP = clamp(t / 0.5);
    const targetLeftX = 70;
    const leftX = Math.max(70, targetLeftX - (1 - easeOutCubic(leftP)) * 120);
    const gLeft = group(svg, {
      transform: 'translate(' + leftX + ' ' + (cy - cardH / 2) + ')'
    });
    shape(gLeft, 'rect', {
      x: 0, y: 0, width: leftW, height: cardH, rx: 28,
      fill: '#101e33', stroke: (!isWinnerB && p > 0.6) ? 'var(--accent)' : '#334155', 'stroke-width': 4
    });
    const leftLines = wrapText(bars[0].label, 14, 2);
    leftLines.forEach((ln, lidx) => {
      gLeft.append(el('text', {
        x: leftW / 2, y: 140 + lidx * 46, 'text-anchor': 'middle', 'font-size': '42', 'font-weight': 'bold', fill: '#f8fafc'
      }, ln));
    });
    if (bars[0].value !== undefined) {
      gLeft.append(el('text', {
        x: leftW / 2, y: 330, 'text-anchor': 'middle', 'font-size': '72', 'font-weight': 'bold', fill: '#94a3b8'
      }, formatNum(Number(bars[0].value) * easeOutCubic(p)) + (bars[0].unit || '')));
    }

    // Right card sliding in (strictly clamped inside [590, 1010])
    const rightP = clamp((t - 0.1) / 0.5);
    const targetRightX = 590;
    const rightX = Math.min(590, targetRightX + (1 - easeOutCubic(rightP)) * 120);
    const gRight = group(svg, {
      transform: 'translate(' + rightX + ' ' + (cy - cardH / 2) + ')'
    });
    shape(gRight, 'rect', {
      x: 0, y: 0, width: leftW, height: cardH, rx: 28,
      fill: '#101e33', stroke: (isWinnerB && p > 0.6) ? 'var(--accent)' : '#334155', 'stroke-width': 4
    });
    const rightLines = wrapText(bars[1].label, 14, 2);
    rightLines.forEach((rn, ridx) => {
      gRight.append(el('text', {
        x: leftW / 2, y: 140 + ridx * 46, 'text-anchor': 'middle', 'font-size': '42', 'font-weight': 'bold', fill: '#f8fafc'
      }, rn));
    });
    if (bars[1].value !== undefined) {
      gRight.append(el('text', {
        x: leftW / 2, y: 330, 'text-anchor': 'middle', 'font-size': '72', 'font-weight': 'bold', fill: 'var(--accent)'
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
  const cy = 785;
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
          x: pts[i][0], y: y0 + 34, 'text-anchor': 'middle', 'font-size': '36', fill: '#94a3b8'
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
  const cleanItem = itm => {
    if (!itm) return '';
    const firstSentence = String(itm).split(/[.!?\n]/)[0].trim();
    return firstSentence.split(/\s+/).filter(Boolean).slice(0, 6).join(' ');
  };
  const rawItems = (d.items && d.items.length >= 1) ? d.items.map(cleanItem).filter(Boolean) : [
    'Khởi động quy trình...', 'Đang xử lý dữ liệu...', 'Hoàn tất bước kiểm định'
  ];
  const items = rawItems.slice(0, 4);
  const cx = 540;
  const cy = 785;
  const w = 880;
  const rowCount = Math.max(1, items.length);
  const rowH = 95;
  const h = Math.min(800, 100 + rowCount * (rowH + 18));
  const x = cx - w / 2;
  const y = cy - h / 2;

  shape(svg, 'rect', { x, y, width: w, height: h, rx: 28, fill: '#0a0f1d', stroke: '#1e293b', 'stroke-width': 4, class: 'motion-element' });
  shape(svg, 'rect', { x, y, width: w, height: 64, rx: 28, fill: '#141e33' });
  shape(svg, 'rect', { x, y: y + 36, width: w, height: 28, fill: '#141e33' });

  shape(svg, 'circle', { cx: x + 40, cy: y + 32, r: 10, fill: '#ef4444' });
  shape(svg, 'circle', { cx: x + 70, cy: y + 32, r: 10, fill: '#eab308' });
  shape(svg, 'circle', { cx: x + 100, cy: y + 32, r: 10, fill: '#22c55e' });

  const available = Math.max(0.1, duration - 1.3);
  const typed = clamp(t / available);

  items.forEach((item, i) => {
    const itemP = clamp(typed * items.length - i);
    if (itemP <= 0 || !item) return; // Do NOT render empty row or lonely prompt!
    const count = Math.floor(String(item).length * itemP);
    if (count <= 0) return;
    const textTyped = String(item).slice(0, count).trim();
    if (!textTyped) return;
    const ry = y + 115 + i * (rowH + 18);

    shape(svg, 'rect', {
      x: x + 35, y: ry - 38, width: w - 70, height: rowH, rx: 16,
      fill: (itemP > 0 && itemP < 1) ? '#162e4a' : '#ffffff06',
      class: 'motion-element'
    });

    const typedStr = '› ' + textTyped;
    const tEl = el('text', {
      x: x + 65, y: ry + 24,
      'font-size': '42', 'font-weight': '600',
      fill: (itemP >= 1) ? 'var(--foreground)' : 'var(--accent)',
      class: 'ill-label'
    }, typedStr);
    svg.append(tEl);
  });
}

function renderTimeline(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    '2021: Khởi động', '2023: Thử nghiệm', '2025: Đột phá quy mô'
  ];
  const cx = 540;
  const cy = 785;
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
  const cy = 785;
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
  const cy = 785;
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
      x: sx + segW / 2, y: cy + 55, 'text-anchor': 'middle', 'font-size': '36',
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
  // Position in dedicated bottom zone: y in [1240, 1320], strictly <= 1330px, horizontal [120, 960] inside [70, 1010]
  const w = 840;
  const h = 75;
  const x = cx - w / 2;
  const y = 1245;

  const g = group(svg, {
    class: 'motion-element'
  });

  shape(g, 'rect', {
    x, y, width: w, height: h, rx: 20,
    fill: '#0e1a2eea', stroke: '#334155', 'stroke-width': 2
  });

  // Shield Icon
  shape(g, 'path', {
    d: `M ${x + 35} ${y + 22} L ${x + 50} ${y + 14} L ${x + 65} ${y + 22} V ${y + 38} C ${x + 65} ${y + 54} ${x + 50} ${y + 64} ${x + 50} ${y + 64} C ${x + 50} ${y + 64} ${x + 35} ${y + 54} ${x + 35} ${y + 38} Z`,
    fill: 'var(--accent)'
  });

  const rawLines = wrapText(sourceName, 30, 2);
  const lines = rawLines.slice(0, 2);
  lines.forEach((line, li) => {
    const textY = (lines.length === 1) ? (y + 48) : (y + 30 + li * 32);
    g.append(el('text', {
      x: x + 85, y: textY,
      'font-size': '36', 'font-weight': '700',
      fill: '#cbd5e1', class: 'ill-label'
    }, (li === 0 ? 'Nguồn: ' : '') + line));
  });
}

function renderIconTile(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    'Hiệu năng', 'Bảo mật', 'Mở rộng', 'Tiết kiệm'
  ];
  const cx = 540;
  const cy = 785;
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
  const cy = 785;
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
  const cy = 785;
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
  const currentArc = arcLength * (Math.min(100, Math.max(0, val)) / 100) * easeP;
  shape(svg, 'circle', {
    cx, cy, r, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 38,
    'stroke-linecap': 'round',
    'stroke-dasharray': currentArc + ' ' + circ,
    transform: 'rotate(135 ' + cx + ' ' + cy + ')'
  });

  // Center display: NEVER fallback to '%' blindly
  let displayVal = val * easeP;
  let gaugeUnit = d.unit !== undefined && d.unit !== null ? String(d.unit).trim() : '';
  if (Math.abs(val) >= 1e9) {
    displayVal = (val / 1e9) * easeP;
    if (!gaugeUnit || gaugeUnit === '%') gaugeUnit = 'tỷ USD';
  } else if (Math.abs(val) >= 1e6) {
    displayVal = (val / 1e6) * easeP;
    if (!gaugeUnit || gaugeUnit === '%') gaugeUnit = 'triệu USD';
  }
  const gaugeNumText = formatRawViNum(displayVal, Math.abs(val) >= 100 ? 0 : 1);
  const fullGaugeText = gaugeUnit ? (gaugeNumText + (gaugeUnit === '%' ? '%' : ' ' + gaugeUnit)) : gaugeNumText;

  // Fit font-size to ring container (max width 420px)
  let gaugeFs = 110;
  while (gaugeFs * 0.58 * fullGaugeText.length > 420 && gaugeFs > 36) {
    gaugeFs -= 4;
  }

  svg.append(el('text', {
    x: cx, y: cy + 25, 'text-anchor': 'middle', 'font-size': String(gaugeFs), 'font-weight': 'bold', fill: '#ffffff'
  }, fullGaugeText));

  // Label: preserve complete semantic phrase <= 4 words intact (e.g. 'Kinh tế tầm thấp')
  const rawGaugeLbl = d.label || d.text || 'Chỉ số';
  const gaugeWords = String(rawGaugeLbl).trim().split(/\s+/).filter(Boolean);
  const cleanGaugeLbl = gaugeWords.length <= 4 ? rawGaugeLbl : gaugeWords.slice(0, 3).join(' ');
  svg.append(el('text', {
    x: cx, y: cy + 120, 'text-anchor': 'middle', 'font-size': '42', 'font-weight': '600', fill: '#94a3b8', class: 'ill-label'
  }, cleanGaugeLbl));
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
      x: 42, y: 30, 'text-anchor': 'middle', 'font-size': '36', 'font-weight': 'bold', fill: '#ffffff'
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


function renderStackCards(ctx, svg, d, t, duration, variantIdx = 0) {
  const cleanItem = itm => {
    if (!itm) return '';
    const firstSentence = String(itm).split(/[.!?\n]/)[0].trim();
    return firstSentence.split(/\s+/).filter(Boolean).slice(0, 6).join(' ');
  };
  const rawItems = (d.items && d.items.length >= 1) ? d.items.map(cleanItem).filter(Boolean) : [
    'Thông tin quan trọng 1', 'Thông tin quan trọng 2', 'Thông tin quan trọng 3'
  ];
  const items = rawItems.slice(0, 4);
  const cx = 540;
  const cy = 785;
  const w = 880;
  const cardH = 150;
  const cardGap = 20;
  const totalCardsH = items.length * cardH + (items.length - 1) * cardGap;
  const frameH = Math.min(800, totalCardsH + 60);
  const x = cx - w / 2;
  const y = cy - frameH / 2;

  // Container background frame (width >= 880px, area >= 45% of content zone)
  shape(svg, 'rect', {
    x, y, width: w, height: frameH, rx: 32,
    fill: '#08122144', stroke: '#1e293b66', 'stroke-width': 2
  });

  const activeCount = items.filter((_, i) => t >= 0.3 + i * 1.8).length;
  const currentIdx = Math.max(0, activeCount - 1);

  items.forEach((item, i) => {
    const startT = 0.3 + i * 1.8;
    const p = clamp((t - startT) / 0.6);
    if (p <= 0) return;

    const isCurrent = (i === currentIdx);
    const isPrevious = (i < currentIdx);
    const targetY = y + 30 + i * (cardH + cardGap) + cardH / 2;
    const levitate = 4 * Math.sin(2.5 * t + i * 1.2);
    const enterY = targetY + (1 - easeOutCubic(p)) * 80;
    
    const cardOp = isCurrent ? 1.0 : (isPrevious ? 0.35 : clamp(p * 2));
    const cardScale = isCurrent ? (1.0 + 0.01 * Math.sin(t * 2)) : 0.97;

    const gCard = group(svg, {
      transform: `translate(${cx}, ${enterY + levitate}) scale(${cardScale}) translate(-${cx}, -${enterY + levitate})`,
      opacity: cardOp,
      class: 'motion-element'
    });

    shape(gCard, 'rect', {
      x, y: enterY - cardH / 2, width: w, height: cardH, rx: 26,
      fill: isCurrent ? '#162a43' : '#0d1a2d',
      stroke: isCurrent ? 'var(--accent)' : '#334155',
      'stroke-width': isCurrent ? 4 : 2,
      filter: isCurrent ? 'drop-shadow(0 8px 24px rgba(255,200,74,0.18))' : 'none'
    });

    shape(gCard, 'rect', {
      x: x + 16, y: enterY - cardH / 2 + 20, width: 10, height: cardH - 40, rx: 5,
      fill: isCurrent ? 'var(--accent)' : '#475569'
    });

    shape(gCard, 'circle', {
      cx: x + 72, cy: enterY, r: 28,
      fill: isCurrent ? 'var(--accent)' : '#1e293b',
      stroke: isCurrent ? '#ffc84a' : '#475569', 'stroke-width': 2
    });
    gCard.append(el('text', {
      x: x + 72, y: enterY + 9, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': 'bold',
      fill: isCurrent ? '#0c1829' : '#94a3b8'
    }, String(i + 1)));

    const lines = wrapText(item, 24, 2);
    lines.forEach((line, lineIdx) => {
      const textY = enterY - (lines.length - 1) * 20 + lineIdx * 40 + 12;
      const tEl = el('text', {
        x: x + 124, y: textY,
        'font-size': '44', 'font-weight': isCurrent ? '700' : '500',
        fill: isCurrent ? 'var(--foreground)' : '#94a3b8',
        class: 'ill-label'
      }, line);
      gCard.append(tEl);
    });
  });
}

function renderNetworkNodes(ctx, svg, d, t, duration, variantIdx = 0) {
  const items = (d.items && d.items.length >= 2) ? d.items.slice(0, 4) : [
    'Hạt nhân trung tâm', 'Đầu mối vệ tinh 1', 'Đầu mối vệ tinh 2', 'Đầu mối vệ tinh 3'
  ];
  const cx = 540;
  const cy = 785;
  const w = 880;
  const h = 760;
  const x = cx - w / 2;
  const y = cy - h / 2;

  // Outer Hero Frame (width >= 880px, area >= 65%)
  shape(svg, 'rect', {
    x, y, width: w, height: h, rx: 32,
    fill: '#08122155', stroke: '#1e293b88', 'stroke-width': 2,
    class: 'motion-element'
  });

  const hubRadius = 140; // diameter 280px >= 280px
  const satRadius = 115; // diameter 230-240px

  // Radiating radar pulse waves expanding from hub
  for (let wIdx = 0; wIdx < 3; wIdx++) {
    const waveCycle = ((t * 0.45 + wIdx * 0.33) % 1);
    const waveR = hubRadius + waveCycle * 260;
    const waveOp = Math.max(0, 0.45 * (1 - waveCycle));
    shape(svg, 'circle', {
      cx, cy, r: waveR, fill: 'none',
      stroke: 'var(--accent)', 'stroke-width': 3,
      opacity: waveOp, class: 'motion-element'
    });
  }

  // Satellite positions well spaced to prevent label collisions
  const satPositions = [
    { x: cx - 280, y: cy - 240 },
    { x: cx + 280, y: cy - 240 },
    { x: cx, y: cy + 250 }
  ];

  const hubP = clamp(t / 0.5);

  satPositions.slice(0, items.length - 1).forEach((pos, satIdx) => {
    const nodeStartT = 1.6 + satIdx * 1.6;
    const satP = clamp((t - nodeStartT) / 0.6);
    if (satP <= 0) return;

    shape(svg, 'line', {
      x1: cx, y1: cy, x2: pos.x, y2: pos.y,
      stroke: '#334155', 'stroke-width': 6,
      stroke_dasharray: '8 6', opacity: clamp(satP * 2)
    });

    const packetU = (t * 0.8 + satIdx * 0.3) % 1;
    const px = cx + (pos.x - cx) * packetU;
    const py = cy + (pos.y - cy) * packetU;
    shape(svg, 'circle', {
      cx: px, cy: py, r: 9,
      fill: 'var(--accent)', filter: 'drop-shadow(0 0 8px var(--accent))',
      class: 'motion-element'
    });
  });

  const hubLevitate = 7 * Math.sin(2.5 * t);
  const gHub = group(svg, {
    transform: `translate(${cx}, ${cy + hubLevitate}) scale(${0.9 + 0.1 * easeOutCubic(hubP)}) translate(-${cx}, -${cy + hubLevitate})`,
    class: 'motion-element'
  });
  shape(gHub, 'circle', {
    cx, cy: cy + hubLevitate, r: hubRadius + 14,
    fill: 'none', stroke: 'var(--accent)', 'stroke-width': 4,
    opacity: 0.35 + 0.2 * Math.sin(t * 3)
  });
  shape(gHub, 'circle', {
    cx, cy: cy + hubLevitate, r: hubRadius,
    fill: '#13283b', stroke: 'var(--accent)', 'stroke-width': 6
  });
  const hubText = items[0] || 'Trung tâm';
  const hubWords = String(hubText).trim().split(/\s+/).filter(Boolean);
  const cleanHubText = hubWords.length > 3 ? hubWords.slice(0, 3).join(' ') : hubText;
  const hubLines = wrapText(cleanHubText, 12, 2);
  hubLines.forEach((line, lineIdx) => {
    const ty = (cy + hubLevitate) - (hubLines.length - 1) * 22 + lineIdx * 44 + 14;
    gHub.append(el('text', {
      x: cx, y: ty, 'text-anchor': 'middle',
      'font-size': '42', 'font-weight': 'bold',
      fill: 'var(--accent)', class: 'ill-label'
    }, line));
  });

  satPositions.slice(0, items.length - 1).forEach((pos, satIdx) => {
    const item = items[satIdx + 1];
    const nodeStartT = 1.6 + satIdx * 1.6;
    const satP = clamp((t - nodeStartT) / 0.6);
    if (satP <= 0) return;

    const satLevitate = 8 * Math.cos(2.5 * t + satIdx);
    const gSat = group(svg, {
      transform: `translate(${pos.x}, ${pos.y + satLevitate}) scale(${easeOutCubic(satP)}) translate(-${pos.x}, -${pos.y + satLevitate})`,
      opacity: clamp(satP * 2), class: 'motion-element'
    });

    shape(gSat, 'circle', {
      cx: pos.x, cy: pos.y + satLevitate, r: satRadius,
      fill: '#0f1f33', stroke: '#475569', 'stroke-width': 4
    });

    const satWords = String(item || '').trim().split(/\s+/).filter(Boolean);
    const cleanSatText = satWords.length > 3 ? satWords.slice(0, 3).join(' ') : (item || '');
    const satLines = wrapText(cleanSatText, 12, 2);
    satLines.forEach((line, lineIdx) => {
      const ty = (pos.y + satLevitate) - (satLines.length - 1) * 20 + lineIdx * 40 + 12;
      gSat.append(el('text', {
        x: pos.x, y: ty, 'text-anchor': 'middle',
        'font-size': '38', 'font-weight': '600',
        fill: 'var(--foreground)', class: 'ill-label'
      }, line));
    });
  });
}

function renderTextFocus(ctx, svg, d, t, duration, variantIdx = 0) {
  const cx = 540;
  const cy = 785;
  const w = 880;
  const h = 580;
  const x = cx - w / 2;
  const y = cy - h / 2;

  const p = clamp(t / 0.6);
  const levitate = 6 * Math.sin(2.5 * t);

  const gFocus = group(svg, {
    transform: `translate(${cx}, ${cy + levitate}) scale(${0.92 + 0.08 * easeOutCubic(p)}) translate(-${cx}, -${cy + levitate})`,
    opacity: clamp(p * 2),
    class: 'motion-element'
  });

  shape(gFocus, 'rect', {
    x, y, width: w, height: h, rx: 32,
    fill: '#101e33', stroke: 'var(--accent)', 'stroke-width': 4,
    filter: 'drop-shadow(0 12px 36px rgba(255,200,74,0.15))'
  });

  shape(gFocus, 'rect', {
    x: x + 16, y: y + 16, width: w - 32, height: h - 32, rx: 20,
    fill: 'none', stroke: '#334155', 'stroke-width': 2
  });

  shape(gFocus, 'circle', {
    cx, cy: y + 130, r: 60,
    fill: 'var(--accent)', opacity: 0.15
  });
  shape(gFocus, 'circle', {
    cx, cy: y + 130, r: 42,
    fill: 'none', stroke: 'var(--accent)', 'stroke-width': 3
  });

  const titleText = d.text || d.label || 'Nội dung trọng tâm';
  const lines = wrapText(titleText, 20, 3);
  lines.forEach((line, lineIdx) => {
    const ty = y + 270 + lineIdx * 64;
    gFocus.append(el('text', {
      x: cx, y: ty, 'text-anchor': 'middle',
      'font-size': '56', 'font-weight': 'bold',
      fill: 'var(--foreground)', class: 'ill-label'
    }, line));
  });
}

const renderVersusScale = renderVersusSplit;

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
  renderVersusScale,
  renderLineChartDraw,
  renderTerminalTyping,
  renderTimeline,
  renderFunnel,
  renderProgressTracker,
  renderSourceBadge,
  renderIconTile,
  renderChatBubblePoll,
  renderGaugeRing,
  renderStackCards,
  renderNetworkNodes,
  renderTextFocus,
  renderAnnotation
};
})();
