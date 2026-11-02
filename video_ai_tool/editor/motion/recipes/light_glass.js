/* Light Glass Motion Recipes (Style: light_glass)
 * Pastel light background, card layouts driven per narration sentence.
 * 9:16 vertical video (1080x1920) @ 30fps.
 * Deterministic pure mathematical function of time t and duration.
 */
(()=>{'use strict';

const NS = 'http://www.w3.org/2000/svg';

function lgEl(tag, attrs = {}, text) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
  if (text !== undefined && text !== null) n.textContent = String(text);
  return n;
}

function lgGroup(parent, attrs = {}) {
  const g = lgEl('g', attrs);
  parent.append(g);
  return g;
}

function lgShape(parent, tag, attrs = {}) {
  const s = lgEl(tag, attrs);
  parent.append(s);
  return s;
}

function clamp(v, min = 0, max = 1) {
  return Math.max(min, Math.min(max, v));
}

// cubic-bezier(.22, 1, .36, 1) exact solver
function cubicBezier(p1x, p1y, p2x, p2y) {
  return function(t) {
    if (t <= 0) return 0;
    if (t >= 1) return 1;
    let u = t;
    for (let i = 0; i < 8; i++) {
      const u2 = u * u, u3 = u2 * u;
      const oneMinusU = 1 - u, oneMinusU2 = oneMinusU * oneMinusU;
      const x = 3 * oneMinusU2 * u * p1x + 3 * oneMinusU * u2 * p2x + u3;
      const dx = 3 * oneMinusU2 * p1x + 6 * oneMinusU * u * (p2x - p1x) + 3 * u2 * (1 - p2x);
      const diff = x - t;
      if (Math.abs(diff) < 1e-5) break;
      u -= diff / (dx || 1);
    }
    u = Math.max(0, Math.min(1, u));
    return 3 * (1 - u) * (1 - u) * u * p1y + 3 * (1 - u) * u * u * p2y + u * u * u;
  };
}
const easeLg = cubicBezier(0.22, 1, 0.36, 1);

// Compute standard entrance & exit motion
function computeLgMotion(t, duration) {
  const enterDur = 0.35;
  const exitWindow = 0.70;
  const fadeOutDur = 0.30;

  let enterAlpha = 1.0, enterScale = 1.0, enterY = 0, enterBlur = 0;
  if (t < enterDur) {
    const p = clamp(t / enterDur);
    const e = easeLg(p);
    enterAlpha = e;
    enterBlur = Math.round(14 * (1 - e));
    enterY = Math.round(24 * (1 - e));
    enterScale = 0.96 + 0.04 * e;
  }

  let exitAlpha = 1.0;
  if (t > duration - exitWindow) {
    const exitTime = t - (duration - exitWindow);
    if (exitTime <= fadeOutDur) {
      const p = clamp(exitTime / fadeOutDur);
      exitAlpha = 1.0 - easeLg(p);
    } else {
      exitAlpha = 0.0; // empty background for ~0.4s before next shot
    }
  }

  const finalAlpha = Math.max(0, Math.min(1, enterAlpha * exitAlpha));
  return {
    alpha: finalAlpha,
    scale: enterScale,
    translateY: enterY,
    blur: enterBlur,
    visible: finalAlpha > 0.001
  };
}

// Wrap text without ellipsis (...), respecting character limit per line
function wrapWordsMaxChars(text, maxCharsPerLine = 14, maxLines = 3) {
  if (!text) return [];
  const words = String(text).trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [];

  const lines = [];
  let currentLine = '';

  for (let i = 0; i < words.length; i++) {
    const word = words[i];
    const candidate = currentLine ? currentLine + ' ' + word : word;
    if (candidate.length <= maxCharsPerLine) {
      currentLine = candidate;
    } else {
      if (currentLine) {
        lines.push(currentLine);
        currentLine = word;
      } else {
        lines.push(word);
        currentLine = '';
      }
      if (lines.length === maxLines - 1) {
        // Collect all remaining words into the last line
        const rest = words.slice(i + 1).join(' ');
        if (rest) currentLine = currentLine ? currentLine + ' ' + rest : rest;
        break;
      }
    }
  }
  if (currentLine && lines.length < maxLines) {
    lines.push(currentLine);
  }
  return lines.slice(0, maxLines);
}

// Add defs if not present
function ensureGradients(svg) {
  let defs = svg.querySelector('defs');
  if (!defs) {
    defs = lgEl('defs');
    svg.prepend(defs);
  }
  if (!svg.querySelector('#lg-grad-blue-purple')) {
    const grad = lgEl('linearGradient', {
      id: 'lg-grad-blue-purple',
      x1: '0%', y1: '0%', x2: '100%', y2: '0%'
    });
    grad.append(
      lgEl('stop', { offset: '0%', 'stop-color': '#2563eb' }),
      lgEl('stop', { offset: '100%', 'stop-color': '#3d2bb0' })
    );
    defs.append(grad);
  }
  if (!svg.querySelector('#lg-card-shadow')) {
    const filter = lgEl('filter', {
      id: 'lg-card-shadow',
      x: '-10%', y: '-10%', width: '120%', height: '125%'
    });
    filter.append(
      lgEl('feDropShadow', {
        dx: '0', dy: '16', stdDeviation: '20',
        'flood-color': '#1a1446', 'flood-opacity': '0.08'
      })
    );
    defs.append(filter);
  }
  return defs;
}

// =========================================================================
// 1. lg_source_headline
// Ảnh nguồn bo 28px (x82..998, y255..770), pill ngắn (<=28 ký tự),
// tiêu đề tối đa 3 dòng (<=14 ký tự/dòng, màu navy #1a1446), thanh gradient xanh-tím
// =========================================================================
function renderLgSourceHeadline(ctx, svg, d, t, duration = 4) {
  d = d || {};
  const mot = computeLgMotion(t, duration);
  if (!mot.visible) return;

  ensureGradients(svg);

  const root = lgGroup(svg, {
    class: 'lg-recipe lg-source-headline',
    transform: `translate(0, ${mot.translateY}) scale(${mot.scale})`,
    opacity: mot.alpha,
    filter: mot.blur > 0 ? `blur(${mot.blur}px)` : ''
  });

  const cardX = 82, cardY = 255, cardW = 916, cardH = 515;

  // Shadow card
  lgShape(root, 'rect', {
    x: cardX, y: cardY + 8, width: cardW, height: cardH, rx: 28,
    fill: '#1a1446', opacity: 0.05
  });

  // Main Image Card
  const imgCard = lgShape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 28,
    fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.8)', 'stroke-width': 1.5
  });

  // Source Image / Media
  const imgUrl = d.image_url || d.image_uri || d.image || d.clip_url;
  if (imgUrl) {
    const clipId = 'lg-source-img-clip';
    let defs = ensureGradients(svg);
    if (!svg.querySelector('#' + clipId)) {
      const clip = lgEl('clipPath', { id: clipId });
      clip.append(lgEl('rect', { x: cardX, y: cardY, width: cardW, height: cardH, rx: 28 }));
      defs.append(clip);
    }
    const img = lgEl('image', {
      href: imgUrl,
      x: cardX, y: cardY, width: cardW, height: cardH,
      preserveAspectRatio: 'xMidYMid slice',
      'clip-path': `url(#${clipId})`
    });
    root.append(img);
  } else {
    // Elegant fallback news visual (no manufactured text)
    const gArt = lgGroup(root);
    lgShape(gArt, 'rect', {
      x: cardX, y: cardY, width: cardW, height: cardH, rx: 28,
      fill: 'linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)'
    });
    lgShape(gArt, 'circle', {
      cx: cardX + cardW / 2, cy: cardY + cardH / 2, r: 80,
      fill: '#2563eb', opacity: 0.1
    });
    lgShape(gArt, 'path', {
      d: `M ${cardX + cardW / 2 - 40} ${cardY + cardH / 2 - 30} h 80 v 60 h -80 Z M ${cardX + cardW / 2 - 25} ${cardY + cardH / 2 - 10} h 50 M ${cardX + cardW / 2 - 25} ${cardY + cardH / 2 + 10} h 35`,
      stroke: '#2563eb', 'stroke-width': 4, fill: 'none', 'stroke-linecap': 'round'
    });
  }

  // Pill ngắn (<= 28 ký tự)
  let curY = 820;
  const pillRaw = d.pill || d.badge || d.kicker || '';
  if (pillRaw && String(pillRaw).trim()) {
    const pillText = String(pillRaw).trim().slice(0, 28);
    const pillG = lgGroup(root);
    const padX = 22, padY = 8;
    const fs = 32;
    // measure approx width: ~18px per char
    const estW = Math.min(800, pillText.length * 18 + padX * 2);

    lgShape(pillG, 'rect', {
      x: cardX, y: curY, width: estW, height: 48, rx: 24,
      fill: 'rgba(37, 99, 235, 0.08)', stroke: 'rgba(37, 99, 235, 0.25)', 'stroke-width': 1.5
    });
    const pillTxtEl = lgEl('text', {
      x: cardX + padX, y: curY + 34,
      fill: '#2563eb', 'font-size': fs, 'font-weight': '700',
      'font-family': 'Inter, sans-serif'
    }, pillText);
    pillG.append(pillTxtEl);
    curY += 76;
  }

  // Tiêu đề (<= 3 dòng, <= 14 ký tự/dòng, màu navy #1a1446)
  const titleRaw = d.title || d.headline || d.text || '';
  if (titleRaw && String(titleRaw).trim()) {
    // Entrance stagger: title enters ~0.5s after shot start
    const titleP = clamp((t - 0.5) / 0.35);
    const titleE = easeLg(titleP);
    const titleYOffset = Math.round(18 * (1 - titleE));

    const titleG = lgGroup(root, {
      opacity: titleE,
      transform: `translate(0, ${titleYOffset})`
    });

    const lines = wrapWordsMaxChars(titleRaw, 14, 3);
    let titleFs = 82;
    if (lines.length === 3) titleFs = 74;
    const lineHeight = titleFs * 1.22;

    lines.forEach((line, idx) => {
      const lineY = curY + idx * lineHeight + titleFs * 0.9;
      const textEl = lgEl('text', {
        x: cardX, y: lineY,
        fill: '#1a1446', 'font-size': titleFs, 'font-weight': '900',
        'letter-spacing': '-0.02em', 'font-family': 'Inter, sans-serif'
      }, line);
      titleG.append(textEl);
    });

    curY += lines.length * lineHeight + 20;

    // Thanh gradient xanh-tím dưới tiêu đề (kéo rộng 0.4s)
    const gradP = clamp((t - 0.7) / 0.4);
    const gradE = easeLg(gradP);
    const gradWidth = Math.round(280 * gradE);

    if (gradWidth > 4) {
      lgShape(root, 'rect', {
        x: cardX, y: curY, width: gradWidth, height: 7, rx: 3.5,
        fill: 'url(#lg-grad-blue-purple)'
      });
    }
  }
}

// =========================================================================
// 2. lg_stat_hero
// Ảnh số liệu phía trên, số lớn màu #2563eb (~200px, tối đa 2 dòng),
// câu phụ 60px đậm, pill phụ 52px xám; số đếm lên nếu là số thuần
// =========================================================================
function renderLgStatHero(ctx, svg, d, t, duration = 4) {
  d = d || {};
  const mot = computeLgMotion(t, duration);
  if (!mot.visible) return;

  ensureGradients(svg);

  const root = lgGroup(svg, {
    class: 'lg-recipe lg-stat-hero',
    transform: `translate(0, ${mot.translateY}) scale(${mot.scale})`,
    opacity: mot.alpha,
    filter: mot.blur > 0 ? `blur(${mot.blur}px)` : ''
  });

  const cardX = 82, cardY = 260, cardW = 916, cardH = 380;

  // Ảnh số liệu / biểu đồ phía trên
  const imgUrl = d.image_url || d.image || d.chart_image;
  if (imgUrl) {
    const clipId = 'lg-stat-img-clip';
    let defs = ensureGradients(svg);
    if (!svg.querySelector('#' + clipId)) {
      const clip = lgEl('clipPath', { id: clipId });
      clip.append(lgEl('rect', { x: cardX, y: cardY, width: cardW, height: cardH, rx: 24 }));
      defs.append(clip);
    }
    lgShape(root, 'rect', {
      x: cardX, y: cardY + 6, width: cardW, height: cardH, rx: 24,
      fill: '#1a1446', opacity: 0.05
    });
    const img = lgEl('image', {
      href: imgUrl,
      x: cardX, y: cardY, width: cardW, height: cardH,
      preserveAspectRatio: 'xMidYMid slice',
      'clip-path': `url(#${clipId})`
    });
    root.append(img);
  } else {
    // Clean SVG graphic panel for data hero
    const chartG = lgGroup(root);
    lgShape(chartG, 'rect', {
      x: cardX, y: cardY, width: cardW, height: cardH, rx: 24,
      fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.8)', 'stroke-width': 1.5
    });
    // Aesthetic subtle wave line
    const waveProgress = clamp((t - 0.2) / 0.8);
    const waveE = easeLg(waveProgress);
    const pathD = `M ${cardX + 40} ${cardY + 280} Q ${cardX + 240} ${cardY + 120}, ${cardX + 460} ${cardY + 220} T ${cardX + cardW - 40} ${cardY + 90}`;
    lgShape(chartG, 'path', {
      d: pathD, fill: 'none', stroke: '#2563eb', 'stroke-width': 5,
      'stroke-linecap': 'round', opacity: 0.6 * waveE
    });
  }

  let curY = cardY + cardH + 70;

  // Số lớn màu #2563eb (~200px, tối đa 2 dòng, đếm lên nếu là số thuần)
  const valRaw = d.value;
  if (valRaw !== undefined && valRaw !== null && String(valRaw).trim() !== '') {
    const unit = d.unit || '';
    let displayVal = String(valRaw);
    const num = parseFloat(String(valRaw).replace(/,/g, ''));

    if (!isNaN(num)) {
      // countUp animation from t=0.4 to 1.4s
      const countP = clamp((t - 0.4) / 1.0);
      const countE = easeLg(countP);
      const curNum = countP >= 0.99 ? num : (num * countE);
      const precision = Number.isInteger(num) ? 0 : Math.min(2, (String(num).split('.')[1] || '').length);
      displayVal = curNum.toLocaleString('vi-VN', {
        minimumFractionDigits: 0,
        maximumFractionDigits: precision
      });
    }

    const numStr = displayVal + (unit ? ' ' + unit : '');
    const numFs = 190;
    const numEl = lgEl('text', {
      x: cardX, y: curY + numFs * 0.82,
      fill: '#2563eb', 'font-size': numFs, 'font-weight': '900',
      'letter-spacing': '-0.03em', 'font-family': 'Inter, sans-serif'
    }, numStr);
    root.append(numEl);

    curY += numFs + 30;
  }

  // Câu phụ 60px đậm
  const subtextRaw = d.text || d.label || d.subtext || '';
  if (subtextRaw && String(subtextRaw).trim()) {
    const subFs = 60;
    const lines = wrapWordsMaxChars(subtextRaw, 24, 2);
    lines.forEach((line, idx) => {
      const lineY = curY + idx * (subFs * 1.25) + subFs * 0.8;
      const textEl = lgEl('text', {
        x: cardX, y: lineY,
        fill: '#1a1446', 'font-size': subFs, 'font-weight': '800',
        'letter-spacing': '-0.01em', 'font-family': 'Inter, sans-serif'
      }, line);
      root.append(textEl);
    });
    curY += lines.length * (subFs * 1.25) + 30;
  }

  // Pill phụ 52px xám
  const subPillRaw = d.sub_pill || d.pill || d.note || '';
  if (subPillRaw && String(subPillRaw).trim()) {
    const pillG = lgGroup(root);
    const pillTxt = String(subPillRaw).trim();
    const fs = 52;
    const estW = Math.min(860, pillTxt.length * 28 + 48);

    lgShape(pillG, 'rect', {
      x: cardX, y: curY, width: estW, height: 74, rx: 24,
      fill: 'rgba(100, 116, 139, 0.12)'
    });
    const txtEl = lgEl('text', {
      x: cardX + 24, y: curY + 52,
      fill: '#64748b', 'font-size': fs, 'font-weight': '600',
      'font-family': 'Inter, sans-serif'
    }, pillTxt);
    pillG.append(txtEl);
  }
}

// =========================================================================
// 3. lg_shot_features
// Ảnh giao diện + nhãn nhỏ nền tối bo tròn góc dưới trái ảnh;
// thẻ trắng viền xanh nhạt với tiêu đề tím #3d2bb0, đường kẻ, tối đa 3 ý (hiện theo nhịp)
// =========================================================================
function renderLgShotFeatures(ctx, svg, d, t, duration = 4) {
  d = d || {};
  const mot = computeLgMotion(t, duration);
  if (!mot.visible) return;

  ensureGradients(svg);

  const root = lgGroup(svg, {
    class: 'lg-recipe lg-shot-features',
    transform: `translate(0, ${mot.translateY}) scale(${mot.scale})`,
    opacity: mot.alpha,
    filter: mot.blur > 0 ? `blur(${mot.blur}px)` : ''
  });

  const cardX = 82, cardY = 260, cardW = 916, cardH = 420;

  // Ảnh giao diện
  const imgUrl = d.image_url || d.image || d.ui_image;
  if (imgUrl) {
    const clipId = 'lg-feat-img-clip';
    let defs = ensureGradients(svg);
    if (!svg.querySelector('#' + clipId)) {
      const clip = lgEl('clipPath', { id: clipId });
      clip.append(lgEl('rect', { x: cardX, y: cardY, width: cardW, height: cardH, rx: 24 }));
      defs.append(clip);
    }
    lgShape(root, 'rect', {
      x: cardX, y: cardY + 6, width: cardW, height: cardH, rx: 24,
      fill: '#1a1446', opacity: 0.05
    });
    const img = lgEl('image', {
      href: imgUrl,
      x: cardX, y: cardY, width: cardW, height: cardH,
      preserveAspectRatio: 'xMidYMid slice',
      'clip-path': `url(#${clipId})`
    });
    root.append(img);
  } else {
    // Mock UI Window
    const uiG = lgGroup(root);
    lgShape(uiG, 'rect', {
      x: cardX, y: cardY, width: cardW, height: cardH, rx: 24,
      fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.8)', 'stroke-width': 1.5
    });
    // Header bar with 3 dots
    lgShape(uiG, 'rect', {
      x: cardX, y: cardY, width: cardW, height: 60, rx: 24,
      fill: '#f8fafc'
    });
    [0, 1, 2].forEach(i => {
      lgShape(uiG, 'circle', {
        cx: cardX + 36 + i * 24, cy: cardY + 30, r: 7,
        fill: ['#cbd5e1', '#e2e8f0', '#94a3b8'][i]
      });
    });
    // Code / UI lines mock
    [0, 1, 2, 3].forEach(i => {
      lgShape(uiG, 'rect', {
        x: cardX + 40, y: cardY + 90 + i * 45, width: [420, 560, 360, 640][i], height: 18, rx: 9,
        fill: '#f1f5f9'
      });
    });
  }

  // Nhãn nhỏ nền tối bo tròn ở góc dưới trái ảnh
  const badgeRaw = d.badge || d.tag || d.label || '';
  if (badgeRaw && String(badgeRaw).trim()) {
    const badgeText = String(badgeRaw).trim();
    const bgX = cardX + 24, bgY = cardY + cardH - 58;
    const estW = Math.min(600, badgeText.length * 16 + 32);

    const bG = lgGroup(root);
    lgShape(bG, 'rect', {
      x: bgX, y: bgY, width: estW, height: 42, rx: 14,
      fill: 'rgba(15, 23, 42, 0.85)'
    });
    const bTxt = lgEl('text', {
      x: bgX + 16, y: bgY + 28,
      fill: '#ffffff', 'font-size': 24, 'font-weight': '700',
      'letter-spacing': '0.5px', 'font-family': 'Inter, sans-serif'
    }, badgeText);
    bG.append(bTxt);
  }

  // Thẻ trắng viền xanh nhạt
  const panelY = 720;
  const panelH = 590;

  lgShape(root, 'rect', {
    x: cardX, y: panelY + 10, width: cardW, height: panelH, rx: 28,
    fill: '#1a1446', opacity: 0.06
  });

  const panel = lgShape(root, 'rect', {
    x: cardX, y: panelY, width: cardW, height: panelH, rx: 28,
    fill: '#ffffff', stroke: 'rgba(37, 99, 235, 0.2)', 'stroke-width': 1.5
  });

  let curY = panelY + 65;

  // Tiêu đề tím #3d2bb0
  const titleRaw = d.title || d.headline || d.text || '';
  if (titleRaw && String(titleRaw).trim()) {
    const titleFs = 48;
    const textEl = lgEl('text', {
      x: cardX + 40, y: curY,
      fill: '#3d2bb0', 'font-size': titleFs, 'font-weight': '800',
      'letter-spacing': '-0.01em', 'font-family': 'Inter, sans-serif'
    }, String(titleRaw).trim().slice(0, 36));
    root.append(textEl);
    curY += 35;
  }

  // Đường kẻ phân cách
  lgShape(root, 'line', {
    x1: cardX + 40, y1: curY, x2: cardX + cardW - 40, y2: curY,
    stroke: 'rgba(37, 99, 235, 0.15)', 'stroke-width': 1.5
  });

  curY += 50;

  // Tối đa 3 ý (mỗi ý hiện đúng lúc nói tới)
  const items = Array.isArray(d.items) ? d.items.slice(0, 3) : [];
  items.forEach((item, idx) => {
    const itemText = String(item).trim();
    if (!itemText) return;

    // Stagger time: item 0 at 0.5s, item 1 at 0.8s, item 2 at 1.1s
    const itemT = 0.5 + idx * 0.3;
    const p = clamp((t - itemT) / 0.25);
    const e = easeLg(p);
    const alpha = e;
    const yOff = Math.round(16 * (1 - e));

    const itemG = lgGroup(root, {
      opacity: alpha,
      transform: `translate(0, ${yOff})`
    });

    const rowY = curY + idx * 125;

    // Bullet icon / checkmark
    lgShape(itemG, 'circle', {
      cx: cardX + 60, cy: rowY + 10, r: 16,
      fill: 'rgba(37, 99, 235, 0.12)'
    });
    lgShape(itemG, 'circle', {
      cx: cardX + 60, cy: rowY + 10, r: 7,
      fill: '#2563eb'
    });

    // Item text
    const fs = 42;
    const lines = wrapWordsMaxChars(itemText, 26, 2);
    lines.forEach((line, lIdx) => {
      const lineEl = lgEl('text', {
        x: cardX + 105, y: rowY + lIdx * 48 + 22,
        fill: '#1a1446', 'font-size': fs, 'font-weight': '600',
        'letter-spacing': '-0.01em', 'font-family': 'Inter, sans-serif'
      }, line);
      itemG.append(lineEl);
    });
  });
}

// =========================================================================
// 4. lg_vs_compare
// 2 thẻ chồng dọc, nhãn nhỏ viết hoa + dòng chính 2 dòng;
// chữ "vs" xám giữa hai thẻ; thẻ thắng viền xanh ngọc + chip WINNER (khi có trong slot)
// =========================================================================
function renderLgVsCompare(ctx, svg, d, t, duration = 4) {
  d = d || {};
  const mot = computeLgMotion(t, duration);
  if (!mot.visible) return;

  ensureGradients(svg);

  const root = lgGroup(svg, {
    class: 'lg-recipe lg-vs-compare',
    transform: `translate(0, ${mot.translateY}) scale(${mot.scale})`,
    opacity: mot.alpha,
    filter: mot.blur > 0 ? `blur(${mot.blur}px)` : ''
  });

  const cardX = 82, cardW = 916, cardH = 400;
  const card1Y = 280;
  const card2Y = 760;

  // Extract slot data for 2 cards
  const left = d.left || (Array.isArray(d.items) && d.items[0]) || (Array.isArray(d.bars) && d.bars[0]) || {};
  const right = d.right || (Array.isArray(d.items) && d.items[1]) || (Array.isArray(d.bars) && d.bars[1]) || {};

  const card1Label = (typeof left === 'object' ? (left.label || left.tag || left.kicker) : '') || d.label_left || '';
  const card1Text = (typeof left === 'object' ? (left.title || left.text || left.name) : String(left)) || d.text_left || '';

  const card2Label = (typeof right === 'object' ? (right.label || right.tag || right.kicker) : '') || d.label_right || '';
  const card2Text = (typeof right === 'object' ? (right.title || right.text || right.name) : String(right)) || d.text_right || '';

  // Winner logic: check slot
  const isWinner1 = d.winner === 1 || d.winner === 'left' || (typeof left === 'object' && left.winner);
  const isWinner2 = d.winner === 2 || d.winner === 'right' || (typeof right === 'object' && right.winner);

  function renderCard(cY, labelText, mainText, isWinner, cardIndex) {
    const cg = lgGroup(root);

    // Shadow
    lgShape(cg, 'rect', {
      x: cardX, y: cY + 8, width: cardW, height: cardH, rx: 28,
      fill: isWinner ? '#059669' : '#1a1446', opacity: isWinner ? 0.08 : 0.05
    });

    // Box
    lgShape(cg, 'rect', {
      x: cardX, y: cY, width: cardW, height: cardH, rx: 28,
      fill: '#ffffff',
      stroke: isWinner ? '#059669' : 'rgba(226, 232, 240, 0.8)',
      'stroke-width': isWinner ? 3.5 : 1.5
    });

    let tY = cY + 60;

    // Nhãn nhỏ viết hoa
    if (labelText && String(labelText).trim()) {
      const lblEl = lgEl('text', {
        x: cardX + 44, y: tY,
        fill: '#64748b', 'font-size': 32, 'font-weight': '700',
        'letter-spacing': '1.5px', 'font-family': 'Inter, sans-serif'
      }, String(labelText).trim().toUpperCase());
      cg.append(lblEl);
      tY += 50;
    }

    // Dòng chính tối đa 2 dòng
    if (mainText && String(mainText).trim()) {
      const fs = 56;
      const lines = wrapWordsMaxChars(mainText, 22, 2);
      lines.forEach((line, i) => {
        const textEl = lgEl('text', {
          x: cardX + 44, y: tY + i * (fs * 1.25) + fs * 0.8,
          fill: '#1a1446', 'font-size': fs, 'font-weight': '800',
          'letter-spacing': '-0.02em', 'font-family': 'Inter, sans-serif'
        }, line);
        cg.append(textEl);
      });
    }

    // Chip WINNER (chỉ khi có trong slot)
    if (isWinner) {
      const chipG = lgGroup(cg);
      const chipW = 150, chipH = 46;
      const chipX = cardX + cardW - chipW - 32;
      const chipY = cY + 36;
      lgShape(chipG, 'rect', {
        x: chipX, y: chipY, width: chipW, height: chipH, rx: 14,
        fill: '#059669'
      });
      chipG.append(lgEl('text', {
        x: chipX + chipW / 2, y: chipY + 31,
        'text-anchor': 'middle',
        fill: '#ffffff', 'font-size': 26, 'font-weight': '800',
        'letter-spacing': '1px', 'font-family': 'Inter, sans-serif'
      }, 'WINNER'));
    }
  }

  // Render Card 1 & 2
  renderCard(card1Y, card1Label, card1Text, isWinner1, 1);
  renderCard(card2Y, card2Label, card2Text, isWinner2, 2);

  // Chữ "vs" xám giữa hai thẻ
  const vsG = lgGroup(root);
  const vsCy = 720;
  lgShape(vsG, 'circle', {
    cx: 540, cy: vsCy, r: 40,
    fill: '#f1f5f9', stroke: '#e2e8f0', 'stroke-width': 2
  });
  vsG.append(lgEl('text', {
    x: 540, y: vsCy + 13,
    'text-anchor': 'middle',
    fill: '#64748b', 'font-size': 36, 'font-weight': '900',
    'font-family': 'Inter, sans-serif'
  }, 'vs'));
}

// =========================================================================
// 5. lg_note_card
// 1 thẻ giữa màn hình, chip chủ đề phía trên, câu nhận định tối đa 3 dòng, căn giữa
// =========================================================================
function renderLgNoteCard(ctx, svg, d, t, duration = 4) {
  d = d || {};
  const mot = computeLgMotion(t, duration);
  if (!mot.visible) return;

  ensureGradients(svg);

  const root = lgGroup(svg, {
    class: 'lg-recipe lg-note-card',
    transform: `translate(0, ${mot.translateY}) scale(${mot.scale})`,
    opacity: mot.alpha,
    filter: mot.blur > 0 ? `blur(${mot.blur}px)` : ''
  });

  const cardX = 82, cardY = 440, cardW = 916, cardH = 680;

  // Shadow
  lgShape(root, 'rect', {
    x: cardX, y: cardY + 16, width: cardW, height: cardH, rx: 32,
    fill: '#1a1446', opacity: 0.06
  });

  // Main Glass Card
  lgShape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 32,
    fill: 'rgba(255, 255, 255, 0.95)',
    stroke: 'rgba(255, 255, 255, 0.8)', 'stroke-width': 2
  });

  let curY = cardY + 90;

  // Chip chủ đề phía trên
  const chipRaw = d.chip || d.tag || d.label || d.topic || '';
  if (chipRaw && String(chipRaw).trim()) {
    const chipText = String(chipRaw).trim();
    const chipG = lgGroup(root);
    const fs = 34;
    const estW = Math.min(760, chipText.length * 20 + 48);
    const chipX = 540 - estW / 2;

    lgShape(chipG, 'rect', {
      x: chipX, y: curY, width: estW, height: 56, rx: 24,
      fill: 'rgba(37, 99, 235, 0.08)', stroke: 'rgba(37, 99, 235, 0.2)', 'stroke-width': 1.5
    });
    chipG.append(lgEl('text', {
      x: 540, y: curY + 39,
      'text-anchor': 'middle',
      fill: '#2563eb', 'font-size': fs, 'font-weight': '700',
      'letter-spacing': '-0.01em', 'font-family': 'Inter, sans-serif'
    }, chipText));

    curY += 120;
  } else {
    curY += 70;
  }

  // Câu nhận định tối đa 3 dòng, căn giữa
  const stmtRaw = d.text || d.title || d.statement || d.quote || '';
  if (stmtRaw && String(stmtRaw).trim()) {
    const lines = wrapWordsMaxChars(stmtRaw, 20, 3);
    let fs = 68;
    if (lines.length === 3) fs = 62;
    const lineHeight = fs * 1.35;

    lines.forEach((line, idx) => {
      const lineY = curY + idx * lineHeight + fs * 0.8;
      const textEl = lgEl('text', {
        x: 540, y: lineY,
        'text-anchor': 'middle',
        fill: '#1a1446', 'font-size': fs, 'font-weight': '900',
        'letter-spacing': '-0.02em', 'font-family': 'Inter, sans-serif'
      }, line);
      root.append(textEl);
    });
  }
}

// =========================================================================
// 6. lg_cta_profile
// Pill nhấn ở trên, thẻ hồ sơ (header gradient, avatar bật lên, tên, link,
// nút Theo dõi -> Đã theo dõi, hàng Thích/Bình luận/Chia sẻ), biểu tượng thích bay lên
// =========================================================================
function renderLgCtaProfile(ctx, svg, d, t, duration = 4) {
  d = d || {};
  const mot = computeLgMotion(t, duration);
  if (!mot.visible) return;

  ensureGradients(svg);

  const root = lgGroup(svg, {
    class: 'lg-recipe lg-cta-profile',
    transform: `translate(0, ${mot.translateY}) scale(${mot.scale})`,
    opacity: mot.alpha,
    filter: mot.blur > 0 ? `blur(${mot.blur}px)` : ''
  });

  // Pill nhấn ở trên
  const pillRaw = d.pill || d.kicker || d.action_pill || '';
  if (pillRaw && String(pillRaw).trim()) {
    const pillTxt = String(pillRaw).trim();
    const pillG = lgGroup(root);
    const estW = Math.min(800, pillTxt.length * 22 + 56);
    const pillX = 540 - estW / 2;
    const pillY = 300;

    lgShape(pillG, 'rect', {
      x: pillX, y: pillY, width: estW, height: 60, rx: 30,
      fill: 'url(#lg-grad-blue-purple)'
    });
    pillG.append(lgEl('text', {
      x: 540, y: pillY + 41,
      'text-anchor': 'middle',
      fill: '#ffffff', 'font-size': 36, 'font-weight': '800',
      'letter-spacing': '0.5px', 'font-family': 'Inter, sans-serif'
    }, pillTxt));
  }

  // Thẻ hồ sơ
  const cardX = 82, cardY = 410, cardW = 916, cardH = 860;

  // Shadow
  lgShape(root, 'rect', {
    x: cardX, y: cardY + 16, width: cardW, height: cardH, rx: 32,
    fill: '#1a1446', opacity: 0.08
  });

  // Card Body
  lgShape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 32,
    fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.8)', 'stroke-width': 1.5
  });

  // Header Gradient
  const headerClipId = 'lg-profile-hdr-clip';
  let defs = ensureGradients(svg);
  if (!svg.querySelector('#' + headerClipId)) {
    const clip = lgEl('clipPath', { id: headerClipId });
    clip.append(lgEl('rect', { x: cardX, y: cardY, width: cardW, height: 210, rx: 32 }));
    defs.append(clip);
  }
  lgShape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: 210,
    fill: 'url(#lg-grad-blue-purple)',
    'clip-path': `url(#${headerClipId})`
  });

  // Avatar bật lên ở giữa ranh giới header (y = 620)
  const avatarY = 620;
  const avatarR = 80;

  // Avatar bounce animation
  const avP = clamp((t - 0.25) / 0.4);
  const avE = easeLg(avP);
  const avScale = 0.8 + 0.2 * avE;

  const avG = lgGroup(root, {
    transform: `translate(540, ${avatarY}) scale(${avScale}) translate(-540, -${avatarY})`
  });

  // White border
  lgShape(avG, 'circle', {
    cx: 540, cy: avatarY, r: avatarR + 6,
    fill: '#ffffff'
  });

  const avatarUrl = d.avatar_url || d.avatar || d.logo_url;
  if (avatarUrl) {
    const avClipId = 'lg-avatar-clip';
    if (!svg.querySelector('#' + avClipId)) {
      const clip = lgEl('clipPath', { id: avClipId });
      clip.append(lgEl('circle', { cx: 540, cy: avatarY, r: avatarR }));
      defs.append(clip);
    }
    const img = lgEl('image', {
      href: avatarUrl,
      x: 540 - avatarR, y: avatarY - avatarR, width: avatarR * 2, height: avatarR * 2,
      preserveAspectRatio: 'xMidYMid slice',
      'clip-path': `url(#${avClipId})`
    });
    avG.append(img);
  } else {
    lgShape(avG, 'circle', {
      cx: 540, cy: avatarY, r: avatarR,
      fill: 'linear-gradient(135deg, #2563eb, #3d2bb0)'
    });
    const nameChar = ((d.name || d.brand_name || 'T').trim().charAt(0) || 'T').toUpperCase();
    avG.append(lgEl('text', {
      x: 540, y: avatarY + 28,
      'text-anchor': 'middle',
      fill: '#ffffff', 'font-size': 76, 'font-weight': '900',
      'font-family': 'Inter, sans-serif'
    }, nameChar));
  }

  // Tên
  const nameRaw = d.name || d.title || d.brand_name || '';
  if (nameRaw && String(nameRaw).trim()) {
    root.append(lgEl('text', {
      x: 540, y: 760,
      'text-anchor': 'middle',
      fill: '#1a1446', 'font-size': 54, 'font-weight': '900',
      'letter-spacing': '-0.02em', 'font-family': 'Inter, sans-serif'
    }, String(nameRaw).trim().slice(0, 32)));
  }

  // Link
  const linkRaw = d.link || d.handle || d.website || '';
  if (linkRaw && String(linkRaw).trim()) {
    root.append(lgEl('text', {
      x: 540, y: 820,
      'text-anchor': 'middle',
      fill: '#2563eb', 'font-size': 36, 'font-weight': '600',
      'font-family': 'Inter, sans-serif'
    }, String(linkRaw).trim().slice(0, 40)));
  }

  // Nút "Theo dõi" -> "Đã theo dõi"
  const isFollowed = t >= 1.2;
  const btnW = 340, btnH = 74;
  const btnX = 540 - btnW / 2, btnY = 880;

  const btnG = lgGroup(root);
  if (!isFollowed) {
    // "Theo dõi" (Blue button)
    lgShape(btnG, 'rect', {
      x: btnX, y: btnY, width: btnW, height: btnH, rx: 37,
      fill: '#2563eb'
    });
    btnG.append(lgEl('text', {
      x: 540, y: btnY + 50,
      'text-anchor': 'middle',
      fill: '#ffffff', 'font-size': 36, 'font-weight': '800',
      'font-family': 'Inter, sans-serif'
    }, '+ Theo dõi'));
  } else {
    // "Đã theo dõi" (Gray active button with green check)
    lgShape(btnG, 'rect', {
      x: btnX, y: btnY, width: btnW, height: btnH, rx: 37,
      fill: '#e2e8f0'
    });
    btnG.append(lgEl('text', {
      x: 540, y: btnY + 50,
      'text-anchor': 'middle',
      fill: '#334155', 'font-size': 36, 'font-weight': '700',
      'font-family': 'Inter, sans-serif'
    }, '✓ Đã theo dõi'));
  }

  // Hàng Thích / Bình luận / Chia sẻ
  const rowY = 1040;
  lgShape(root, 'line', {
    x1: cardX + 60, y1: rowY, x2: cardX + cardW - 60, y2: rowY,
    stroke: 'rgba(226, 232, 240, 0.8)', 'stroke-width': 1.5
  });

  const actions = [
    { label: 'Thích', icon: '♥' },
    { label: 'Bình luận', icon: '💬' },
    { label: 'Chia sẻ', icon: '↗' }
  ];
  actions.forEach((act, idx) => {
    const actX = cardX + 160 + idx * 290;
    const actG = lgGroup(root);
    actG.append(lgEl('text', {
      x: actX, y: rowY + 68,
      'text-anchor': 'middle',
      fill: '#64748b', 'font-size': 34, 'font-weight': '700',
      'font-family': 'Inter, sans-serif'
    }, act.icon + ' ' + act.label));
  });

  // Biểu tượng thích/tim bay lên cuối cảnh
  if (t > duration - 1.8) {
    const heartProgress = clamp((t - (duration - 1.8)) / 1.5);
    const likeBtnX = cardX + 160;
    const likeBtnY = rowY + 40;

    [0, 1, 2, 3].forEach(i => {
      const delay = i * 0.2;
      const hp = clamp((heartProgress - delay) / 0.8);
      if (hp > 0 && hp < 1) {
        const floatY = likeBtnY - Math.round(hp * 260);
        const floatX = likeBtnX + Math.sin(hp * Math.PI * 2 + i) * 35;
        const alpha = Math.sin(hp * Math.PI);
        const scale = 0.8 + 0.6 * Math.sin(hp * Math.PI);

        const hG = lgGroup(root, {
          transform: `translate(${floatX}, ${floatY}) scale(${scale})`,
          opacity: alpha
        });
        hG.append(lgEl('text', {
          x: 0, y: 0, 'text-anchor': 'middle',
          fill: i % 2 ? '#f43f5e' : '#8b5cf6', 'font-size': 44
        }, '♥'));
      }
    });
  }
}

// Export light glass recipes
const lightGlassRecipes = {
  lg_source_headline: renderLgSourceHeadline,
  lg_stat_hero: renderLgStatHero,
  lg_shot_features: renderLgShotFeatures,
  lg_vs_compare: renderLgVsCompare,
  lg_note_card: renderLgNoteCard,
  lg_cta_profile: renderLgCtaProfile
};

window.MotionVocabulary = Object.assign(window.MotionVocabulary || {}, lightGlassRecipes);
if (window.MotionRecipes) {
  Object.assign(window.MotionRecipes, lightGlassRecipes);
}

})();
