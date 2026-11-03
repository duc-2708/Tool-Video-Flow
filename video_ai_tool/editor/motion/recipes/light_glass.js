/* Light Glass Motion Recipes (Style: light_glass)
 * Authentic Two-Zone Split Layouts (1080x1920) @ 30fps
 * Inspired by modern tech review formats (e.g. Simo Studio style)
 * Top Zone: Visual Evidence / Mockup / Screenshot (~35-40% height)
 * Bottom Zone: Structured Content Card (~45-50% height)
 * Safe zone compliant: x in [70, 1010], y in [240, 1330]
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

// cubic-bezier(.16, 1, .3, 1) spring-like smooth ease out
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
const easeLg = cubicBezier(0.16, 1, 0.3, 1);

// Compute standard entrance & exit motion
function computeLgMotion(t, duration) {
  // Seamless, continuous motion across 5s beats:
  // Alpha is 1.0 (never fades to 0 or blanks), zero flash reload
  return {
    alpha: 1.0,
    scale: 1.0,
    translateY: 0,
    blur: 0,
    visible: true
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

// Ensure defs and shared gradients
function ensureGradients(svg) {
  let defs = svg.querySelector('defs');
  if (!defs) {
    defs = lgEl('defs');
    svg.prepend(defs);
  }
  if (!svg.querySelector('#lg-shimmer-grad')) {
    const grad = lgEl('linearGradient', {
      id: 'lg-shimmer-grad',
      x1: '0%', y1: '0%', x2: '100%', y2: '100%'
    });
    grad.append(
      lgEl('stop', { offset: '0%', 'stop-color': '#ffffff', 'stop-opacity': '0' }),
      lgEl('stop', { offset: '50%', 'stop-color': '#ffffff', 'stop-opacity': '0.38' }),
      lgEl('stop', { offset: '100%', 'stop-color': '#ffffff', 'stop-opacity': '0' })
    );
    defs.append(grad);
  }
  if (!svg.querySelector('#lg-chart-grad')) {
    const grad = lgEl('linearGradient', {
      id: 'lg-chart-grad',
      x1: '0%', y1: '0%', x2: '0%', y2: '100%'
    });
    grad.append(
      lgEl('stop', { offset: '0%', 'stop-color': '#10b981', 'stop-opacity': '0.4' }),
      lgEl('stop', { offset: '100%', 'stop-color': '#10b981', 'stop-opacity': '0.0' })
    );
    defs.append(grad);
  }
  if (!svg.querySelector('#lg-grad-blue-purple')) {
    const grad = lgEl('linearGradient', {
      id: 'lg-grad-blue-purple',
      x1: '0%', y1: '0%', x2: '100%', y2: '0%'
    });
    grad.append(
      lgEl('stop', { offset: '0%', 'stop-color': '#2563eb' }),
      lgEl('stop', { offset: '100%', 'stop-color': '#7c3aed' })
    );
    defs.append(grad);
  }
  if (!svg.querySelector('#lg-grad-header')) {
    const grad = lgEl('linearGradient', {
      id: 'lg-grad-header',
      x1: '0%', y1: '0%', x2: '100%', y2: '100%'
    });
    grad.append(
      lgEl('stop', { offset: '0%', 'stop-color': '#3b82f6' }),
      lgEl('stop', { offset: '100%', 'stop-color': '#8b5cf6' })
    );
    defs.append(grad);
  }
  return defs;
}

// Check if an emphasis word should be highlighted at time t
function isWordHighlighted(wordText, emphasisList, t) {
  if (!emphasisList || !emphasisList.length) return false;
  const clean = String(wordText).trim().toLowerCase();
  for (const emp of emphasisList) {
    const phrase = String(emp.phrase || '').trim().toLowerCase();
    if (phrase && (phrase.includes(clean) || clean.includes(phrase))) {
      if (emp.start_sec !== undefined && emp.start_sec !== null && emp.end_sec !== undefined && emp.end_sec !== null) {
        if (t >= emp.start_sec && t <= emp.end_sec + 0.4) return true;
      } else {
        return true;
      }
    }
  }
  return false;
}

// =========================================================================
// REAL IMAGE RENDERER: Authentic Footage / Web Citation with Gentle Ken Burns & Glass Shimmer
// =========================================================================
function renderRealImageWithGentleMotion(parent, x, y, w, h, imgUrl, d, t, duration = 4, clipId = 'lg-real-img') {
  const g = lgGroup(parent);
  let defs = ensureGradients(parent.ownerSVGElement || parent.closest('svg'));

  const uniqueClip = clipId + '-' + Math.round(x) + '-' + Math.round(y);
  if (!defs.querySelector('#' + uniqueClip)) {
    const clip = lgEl('clipPath', { id: uniqueClip });
    clip.append(lgEl('rect', { x: x, y: y, width: w, height: h, rx: 28 }));
    defs.append(clip);
  }

  // Soft layered shadow behind card
  lgShape(g, 'rect', {
    x: x, y: y + 8, width: w, height: h, rx: 28,
    fill: '#0f172a', opacity: 0.08
  });

  // Image container with gentle Ken Burns motion
  const cx = x + w / 2, cy = y + h / 2;
  const progress = clamp(t / Math.max(1, duration));
  const slowZoom = 1.0 + 0.045 * progress;
  const slowPanY = -5 * progress;
  const floatWave = Math.sin(t * 1.5) * 2.5;

  const imgG = lgGroup(g, {
    'clip-path': `url(#${uniqueClip})`
  });

  // Base background in case image loads slow
  lgShape(imgG, 'rect', {
    x: x, y: y, width: w, height: h,
    fill: '#0f172a'
  });

  const imgElNode = lgEl('image', {
    href: imgUrl,
    x: x - w * 0.03, y: y - h * 0.03, width: w * 1.06, height: h * 1.06,
    preserveAspectRatio: 'xMidYMid slice',
    transform: `translate(${cx}, ${cy}) scale(${slowZoom}) translate(${-cx}, ${-cy + slowPanY + floatWave})`
  });
  imgG.append(imgElNode);

  // Delicate glass border
  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: h, rx: 28,
    fill: 'none', stroke: 'rgba(255, 255, 255, 0.85)', 'stroke-width': 2.5
  });

  // Subtle Shimmer glass light sweep in early 0.3s -> 1.8s
  if (t >= 0.3 && t <= 2.2) {
    const shimP = clamp((t - 0.3) / 1.6);
    const shimX = x - 260 + shimP * (w + 520);
    const shimG = lgGroup(g, { 'clip-path': `url(#${uniqueClip})`, opacity: 0.25 });
    lgShape(shimG, 'rect', {
      x: shimX, y: y - 50, width: 140, height: h + 100,
      fill: 'url(#lg-shimmer-grad)',
      transform: `rotate(25, ${shimX + 70}, ${y + h / 2})`
    });
  }

  // Top Headline Banner on Visual Card (Prominent context, bold white typography)
  const rawHeadline = String(d.headline || d.title || d.chip || d.pill || d.text || '').trim();
  if (rawHeadline) {
    const headG = lgGroup(g);
    let cleanHead = rawHeadline.split(/[.?!]/)[0].trim();
    if (cleanHead.length > 38) cleanHead = cleanHead.slice(0, 36) + '...';
    cleanHead = cleanHead.toUpperCase();

    const headW = Math.min(w - 64, cleanHead.length * 19 + 72);
    const headH = 56;
    const headX = x + 24, headY = y + 24;

    lgShape(headG, 'rect', {
      x: headX, y: headY, width: headW, height: headH, rx: 18,
      fill: 'rgba(15, 23, 42, 0.90)', stroke: 'rgba(255, 255, 255, 0.25)', 'stroke-width': 1.5
    });
    lgShape(headG, 'circle', {
      cx: headX + 24, cy: headY + headH / 2, r: 6,
      fill: '#38bdf8', opacity: 0.95
    });
    headG.append(lgEl('text', {
      x: headX + 42, y: headY + 38,
      fill: '#ffffff', 'font-size': 28, 'font-weight': '900',
      'letter-spacing': '0.04em', 'font-family': 'Inter, Montserrat, sans-serif'
    }, cleanHead));
  }

  // Authentic source pill badge at bottom-left
  const domainText = String(d.source || d.domain || 'finance.yahoo.com').trim();
  if (domainText) {
    const pillG = lgGroup(g);
    const pillW = Math.min(380, domainText.length * 15 + 64);
    const pillH = 40;
    const pillX = x + 24, pillY = y + h - pillH - 20;

    lgShape(pillG, 'rect', {
      x: pillX, y: pillY, width: pillW, height: pillH, rx: 20,
      fill: 'rgba(15, 23, 42, 0.85)', stroke: 'rgba(255, 255, 255, 0.25)', 'stroke-width': 1.2
    });
    // Little live pulsing cyan dot indicator
    const dotPulse = 0.7 + 0.3 * Math.sin(t * 3);
    lgShape(pillG, 'circle', { cx: pillX + 20, cy: pillY + 20, r: 5, fill: '#38bdf8', opacity: dotPulse });
    pillG.append(lgEl('text', {
      x: pillX + 36, y: pillY + 27,
      fill: '#f8fafc', 'font-size': 24, 'font-weight': '700',
      'font-family': 'Inter, sans-serif'
    }, domainText.slice(0, 26)));
  }
}

// =========================================================================
// MOCKUP: Social Media Post Card (Quote / Tweet / Statement Evidence)
// =========================================================================
function renderSocialPostMockup(parent, x, y, w, h, d, t) {
  const g = lgGroup(parent);
  const waveY = Math.sin(t * 1.8) * 3;

  const cardG = lgGroup(g, {
    transform: `translate(0, ${waveY})`
  });

  // Background Card
  lgShape(cardG, 'rect', {
    x: x, y: y, width: w, height: h, rx: 26,
    fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.95)', 'stroke-width': 1.5
  });

  // Subtle light sweep
  if (t >= 0.4 && t <= 2.0) {
    const shimP = clamp((t - 0.4) / 1.4);
    const shimX = x - 200 + shimP * (w + 400);
    lgShape(cardG, 'rect', {
      x: shimX, y: y, width: 100, height: h, rx: 26,
      fill: 'url(#lg-shimmer-grad)', opacity: 0.18
    });
  }

  // Author & Handle
  const author = String(d.author || d.name || 'Elon Musk').trim();
  const handle = '@' + author.toLowerCase().replace(/[^a-z0-9]/g, '');

  // Avatar (Circle)
  const avX = x + 50, avY = y + 52, avR = 26;
  lgShape(cardG, 'circle', {
    cx: avX, cy: avY, r: avR, fill: '#0f172a'
  });
  cardG.append(lgEl('text', {
    x: avX, y: avY + 9, 'text-anchor': 'middle',
    fill: '#ffffff', 'font-size': 26, 'font-weight': '900',
    'font-family': 'Inter, sans-serif'
  }, author.charAt(0).toUpperCase()));

  // Author Name
  cardG.append(lgEl('text', {
    x: avX + 38, y: avY + 2,
    fill: '#0f172a', 'font-size': 28, 'font-weight': '800',
    'font-family': 'Inter, sans-serif'
  }, author.slice(0, 24)));

  // Verified Badge SVG (Blue tick circle)
  const nameWidth = Math.min(260, author.length * 16);
  const tickX = avX + 44 + nameWidth, tickY = avY - 7;
  lgShape(cardG, 'circle', { cx: tickX, cy: tickY, r: 10, fill: '#1d9bf0' });
  lgShape(cardG, 'path', {
    d: `M ${tickX - 4} ${tickY} l 3 3 l 6 -6`,
    stroke: '#ffffff', 'stroke-width': 2, fill: 'none', 'stroke-linecap': 'round'
  });

  // Handle & Time
  cardG.append(lgEl('text', {
    x: avX + 38, y: avY + 28,
    fill: '#64748b', 'font-size': 24, 'font-weight': '500',
    'font-family': 'Inter, sans-serif'
  }, `${handle} · 2 giờ trước`));

  // X Logo on top right
  cardG.append(lgEl('text', {
    x: x + w - 52, y: y + 58, 'text-anchor': 'middle',
    fill: '#0f172a', 'font-size': 32, 'font-weight': '900',
    'font-family': 'Inter, sans-serif'
  }, '𝕏'));

  // Statement text verbatim from narration/quote
  const tweetText = String(d.quote || d.statement || d.repo_desc || d.text || 'Tiết kiệm tiền cho tương lai là vô nghĩa khi AI bùng nổ.').trim();
  const lines = wrapWordsMaxChars(tweetText, 26, 3);
  const textFs = 28;
  lines.forEach((line, idx) => {
    cardG.append(lgEl('text', {
      x: x + 50, y: y + 130 + idx * 42,
      fill: '#1e293b', 'font-size': textFs, 'font-weight': '600',
      'font-family': 'Inter, sans-serif'
    }, line));
  });

  // Divider line
  lgShape(cardG, 'line', {
    x1: x + 44, y1: y + h - 68, x2: x + w - 44, y2: y + h - 68,
    stroke: 'rgba(226, 232, 240, 0.8)', 'stroke-width': 1.2
  });

  // Bottom Action Row with animated Heart beat
  const footY = y + h - 26;
  const heartScale = 1.0 + 0.18 * Math.sin(t * 3.5);
  const heartG = lgGroup(cardG, {
    transform: `translate(${x + 280}, ${footY - 6}) scale(${heartScale}) translate(${-(x + 280)}, ${-(footY - 6)})`
  });
  heartG.append(lgEl('text', {
    x: x + 280, y: footY, 'text-anchor': 'middle',
    fill: '#ef4444', 'font-size': 24, 'font-weight': '700',
    'font-family': 'Inter, sans-serif'
  }, '♥ 48.6K'));

  cardG.append(lgEl('text', {
    x: x + 80, y: footY, fill: '#64748b', 'font-size': 24, 'font-weight': '600', 'font-family': 'Inter, sans-serif'
  }, '💬 3.2K'));
  cardG.append(lgEl('text', {
    x: x + 440, y: footY, fill: '#64748b', 'font-size': 24, 'font-weight': '600', 'font-family': 'Inter, sans-serif'
  }, '🔁 12.8K'));
  cardG.append(lgEl('text', {
    x: x + 600, y: footY, fill: '#64748b', 'font-size': 24, 'font-weight': '600', 'font-family': 'Inter, sans-serif'
  }, '📊 3.8M lượt xem'));
}

// =========================================================================
// MOCKUP: Dynamic Financial / Metric Chart with Smooth Drawing Spline
// =========================================================================

// =========================================================================
// MOCKUP: Dynamic Emergency Reserve Gauge Meter (3 - 6 Months Reserve)
// =========================================================================
function renderEmergencyGaugeMockup(parent, x, y, w, h, d, t) {
  const g = lgGroup(parent);
  ensureGradients(parent.ownerSVGElement || parent.closest('svg'));

  // Dark Card Background with high-contrast cyan border
  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: h, rx: 28,
    fill: '#0b111e', stroke: 'rgba(56, 189, 248, 0.40)', 'stroke-width': 2
  });

  // Top Kicker & Header
  const kicker = String(d.sub_pill || 'NGƯỠNG AN TOÀN TÀI CHÍNH').trim().toUpperCase();
  g.append(lgEl('text', {
    x: x + 48, y: y + 54,
    fill: '#38bdf8', 'font-size': 24, 'font-weight': '800',
    'letter-spacing': '0.08em', 'font-family': 'Inter, sans-serif'
  }, kicker));

  const titleText = String(d.chip || d.title || 'QUỸ DỰ PHÒNG KHẨN CẤP').trim().toUpperCase();
  g.append(lgEl('text', {
    x: x + 48, y: y + 104,
    fill: '#ffffff', 'font-size': 44, 'font-weight': '900',
    'letter-spacing': '-0.01em', 'font-family': 'Inter, sans-serif'
  }, titleText.slice(0, 32)));

  // Gauge Arc Center & Geometry
  const cx = x + w / 2, cy = y + 430, r = 210;
  const arcG = lgGroup(g);

  // Background Arc Track (240 degrees from 150 deg to 390 deg)
  const p1x = cx - r * 0.866, p1y = cy + r * 0.5;
  const p2x = cx + r * 0.866, p2y = cy + r * 0.5;
  lgShape(arcG, 'path', {
    d: `M ${p1x} ${p1y} A ${r} ${r} 0 1 1 ${p2x} ${p2y}`,
    fill: 'none', stroke: 'rgba(255, 255, 255, 0.12)', 'stroke-width': 26, 'stroke-linecap': 'round'
  });

  // Safe Zone Emerald Arc (from top to right: 3 - 6 months)
  const topX = cx, topY = cy - r;
  lgShape(arcG, 'path', {
    d: `M ${topX} ${topY} A ${r} ${r} 0 0 1 ${p2x} ${p2y}`,
    fill: 'none', stroke: '#10b981', 'stroke-width': 30, 'stroke-linecap': 'round',
    opacity: 0.95
  });

  // Animated Sweeping Needle
  const sweepP = clamp((t - 0.2) / 1.2);
  const needleAngle = -120 + 200 * easeLg(sweepP); // Sweeps into safe green zone
  const rad = (needleAngle * Math.PI) / 180;
  const nx = cx + (r - 28) * Math.sin(rad);
  const ny = cy - (r - 28) * Math.cos(rad);

  lgShape(arcG, 'line', {
    x1: cx, y1: cy, x2: nx, y2: ny,
    stroke: '#ffffff', 'stroke-width': 6, 'stroke-linecap': 'round'
  });
  // Pivot Circle
  lgShape(arcG, 'circle', { cx: cx, cy: cy, r: 18, fill: '#38bdf8', stroke: '#ffffff', 'stroke-width': 4 });
  // Needle tip glow
  lgShape(arcG, 'circle', { cx: nx, cy: ny, r: 10, fill: '#10b981', stroke: '#ffffff', 'stroke-width': 2 });

  // Giant Center Metric Display
  g.append(lgEl('text', {
    x: cx, y: cy + 120,
    'text-anchor': 'middle',
    fill: '#10b981', 'font-size': 86, 'font-weight': '900',
    'font-family': 'Inter, monospace, sans-serif'
  }, '3 – 6 THÁNG'));

  g.append(lgEl('text', {
    x: cx, y: cy + 170,
    'text-anchor': 'middle',
    fill: '#cbd5e1', 'font-size': 26, 'font-weight': '700',
    'font-family': 'Inter, sans-serif'
  }, 'CHI PHÍ SINH HOẠT AN TOÀN'));

  // 2 Comparison Badges at bottom
  const bW = (w - 120) / 2, bH = 140, bY = y + h - 175;

  // Box 1: Risk Zone (<3 months)
  const b1X = x + 44;
  lgShape(g, 'rect', {
    x: b1X, y: bY, width: bW, height: bH, rx: 20,
    fill: 'rgba(239, 68, 68, 0.12)', stroke: 'rgba(239, 68, 68, 0.45)', 'stroke-width': 1.5
  });
  g.append(lgEl('text', {
    x: b1X + 24, y: bY + 48,
    fill: '#f87171', 'font-size': 26, 'font-weight': '800',
    'font-family': 'Inter, sans-serif'
  }, 'DƯỚI 3 THÁNG'));
  g.append(lgEl('text', {
    x: b1X + 24, y: bY + 95,
    fill: '#fca5a5', 'font-size': 22, 'font-weight': '600',
    'font-family': 'Inter, sans-serif'
  }, 'Rủi ro cạn kiệt tài chính'));

  // Box 2: Safe Zone (3-6 months)
  const b2X = x + 44 + bW + 32;
  lgShape(g, 'rect', {
    x: b2X, y: bY, width: bW, height: bH, rx: 20,
    fill: 'rgba(16, 185, 129, 0.15)', stroke: 'rgba(16, 185, 129, 0.55)', 'stroke-width': 1.5
  });
  g.append(lgEl('text', {
    x: b2X + 24, y: bY + 48,
    fill: '#34d399', 'font-size': 26, 'font-weight': '800',
    'font-family': 'Inter, sans-serif'
  }, 'TỪ 3 – 6 THÁNG'));
  g.append(lgEl('text', {
    x: b2X + 24, y: bY + 95,
    fill: '#a7f3d0', 'font-size': 22, 'font-weight': '600',
    'font-family': 'Inter, sans-serif'
  }, 'Ngưỡng an toàn vững chắc'));
}

function renderFinancialChartMockup(parent, x, y, w, h, d, t) {
  const g = lgGroup(parent);
  ensureGradients(parent.ownerSVGElement || parent.closest('svg'));

  // Dark Card Background with subtle border
  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: h, rx: 28,
    fill: '#0b111e', stroke: '#1e293b', 'stroke-width': 2
  });

  // Top Kicker & Stat Header
  const labelText = String(d.label || 'TĂNG TRƯỞNG & TỐI ƯU CHI PHÍ').trim();
  g.append(lgEl('text', {
    x: x + 48, y: y + 54,
    fill: '#64748b', 'font-size': 24, 'font-weight': '700',
    'letter-spacing': '0.08em', 'font-family': 'Inter, sans-serif'
  }, labelText.slice(0, 36).toUpperCase()));

  const neonVal = String(d.neon_stat || (d.value ? `${d.value} ${d.unit || ''}` : '0 VNĐ')).trim();
  g.append(lgEl('text', {
    x: x + 48, y: y + 115,
    fill: '#10b981', 'font-size': 56, 'font-weight': '900',
    'letter-spacing': '-0.02em', 'font-family': 'Inter, monospace, sans-serif'
  }, neonVal.slice(0, 24)));

  // Dynamic SVG Spline Chart - Expanded to fill the stage
  const chartX = x + 48, chartY = y + 150, chartW = w - 96, chartH = 460;
  const drawP = clamp((t - 0.2) / 1.0);
  const e = easeLg(drawP);

  // Horizontal Grid Lines & Y-axis labels
  const gridSteps = [
    { ratio: 0.0, label: '+300%' },
    { ratio: 0.33, label: '+200%' },
    { ratio: 0.66, label: '+100%' },
    { ratio: 1.0, label: '0%' }
  ];
  gridSteps.forEach(gs => {
    const gy = chartY + chartH * gs.ratio;
    lgShape(g, 'line', {
      x1: chartX, y1: gy, x2: chartX + chartW, y2: gy,
      stroke: 'rgba(255, 255, 255, 0.08)', 'stroke-width': 1, 'stroke-dasharray': '4 6'
    });
    g.append(lgEl('text', {
      x: chartX + chartW - 6, y: gy - 6,
      'text-anchor': 'end',
      fill: '#64748b', 'font-size': 24, 'font-weight': '600',
      'font-family': 'Inter, sans-serif'
    }, gs.label));
  });

  // Points: Start, Mid1, Mid2, End (climbing curve across the full 460px height)
  const p0x = chartX, p0y = chartY + chartH - 40;
  const p1x = chartX + chartW * 0.33, p1y = chartY + chartH - 120;
  const p2x = chartX + chartW * 0.66, p2y = chartY + chartH * 0.35;
  const p3x = chartX + chartW * 0.95, p3y = chartY + 50;

  // Animated current end point
  const curEndX = p0x + (p3x - p0x) * e;
  const curEndY = p0y + (p3y - p0y) * e;

  const pathD = `M ${p0x} ${p0y} Q ${p1x} ${p1y + 20}, ${p2x} ${p2y} T ${curEndX} ${curEndY}`;
  const areaD = `${pathD} L ${curEndX} ${chartY + chartH} L ${p0x} ${chartY + chartH} Z`;

  // Fill Area with rich luminous emerald gradient
  lgShape(g, 'path', {
    d: areaD, fill: 'url(#lg-chart-grad)', opacity: 0.85
  });

  // Stroke Line
  lgShape(g, 'path', {
    d: pathD, fill: 'none', stroke: '#10b981', 'stroke-width': 5, 'stroke-linecap': 'round'
  });

  // Pulsing glow circle at end tip
  if (e > 0.08) {
    const pulseR = 8 + 5 * Math.sin(t * 4);
    lgShape(g, 'circle', {
      cx: curEndX, cy: curEndY, r: pulseR,
      fill: 'none', stroke: '#34d399', 'stroke-width': 2.5, opacity: 0.85
    });
    lgShape(g, 'circle', {
      cx: curEndX, cy: curEndY, r: 6, fill: '#ffffff'
    });
  }

  // 3 Mini Stat Boxes below chart (comfortably placed, high contrast, frosted glass)
  const boxW = 260, boxH = 140, gap = 24;
  const startX = x + 44, boxY = chartY + chartH + 35;

  const b1Num = String(d.stat_box_1 || (d.value ? `${d.value}` : '300%'));
  const b2Num = String(d.stat_box_2 || '~0 VNĐ');
  const b3Num = String(d.stat_box_3 || 'Đột phá');

  const boxes = [
    { num: b1Num, lbl: 'Năng suất', color: '#38bdf8' },
    { num: b2Num, lbl: 'Chi phí biên', color: '#34d399' },
    { num: b3Num, lbl: 'Hiệu quả AI', color: '#f59e0b' }
  ];

  boxes.forEach((b, idx) => {
    const bx = startX + idx * (boxW + gap);
    lgShape(g, 'rect', {
      x: bx, y: boxY, width: boxW, height: boxH, rx: 20,
      fill: 'rgba(24, 33, 47, 0.85)', stroke: 'rgba(56, 189, 248, 0.25)', 'stroke-width': 1.5
    });
    g.append(lgEl('text', {
      x: bx + boxW / 2, y: boxY + 62,
      'text-anchor': 'middle',
      fill: b.color, 'font-size': 38, 'font-weight': '900',
      'font-family': 'Inter, sans-serif'
    }, b.num.slice(0, 10)));
    g.append(lgEl('text', {
      x: bx + boxW / 2, y: boxY + 108,
      'text-anchor': 'middle',
      fill: '#e2e8f0', 'font-size': 24, 'font-weight': '600',
      'font-family': 'Inter, sans-serif'
    }, b.lbl));
  });
}

// =========================================================================
// MOCKUP: Tech Architecture Window with Pulsing Node Status & Mac Cursor
// =========================================================================
function renderTechArchitectureMockup(parent, x, y, w, h, d, t) {
  const g = lgGroup(parent);

  // Card Background
  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: h, rx: 24,
    fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.95)', 'stroke-width': 1.5
  });

  // Header Bar with Mac Dots
  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: 56, rx: 24,
    fill: '#f8fafc'
  });
  // 3 Mac Dots
  lgShape(g, 'circle', { cx: x + 36, cy: y + 28, r: 7, fill: '#ff5f56' });
  lgShape(g, 'circle', { cx: x + 58, cy: y + 28, r: 7, fill: '#ffbd2e' });
  lgShape(g, 'circle', { cx: x + 80, cy: y + 28, r: 7, fill: '#27c93f' });

  // URL Bar in center
  const domainText = String(d.source || d.domain || 'system.ai.tech').trim();
  const urlW = 440, urlH = 28;
  const urlX = x + (w - urlW) / 2, urlY = y + 14;
  lgShape(g, 'rect', {
    x: urlX, y: urlY, width: urlW, height: urlH, rx: 8,
    fill: '#e2e8f0'
  });
  g.append(lgEl('text', {
    x: urlX + urlW / 2, y: urlY + 22,
    'text-anchor': 'middle',
    fill: '#64748b', 'font-size': 24, 'font-weight': '600',
    'font-family': 'Inter, sans-serif'
  }, domainText.slice(0, 32)));

  // 3 Tech Architecture Rows
  const rowStartX = x + 36, rowW = w - 72;
  const rows = [
    { title: 'Tự động hóa toàn diện', stat: 'Hoạt động 99.9%', color: '#10b981' },
    { title: 'Tối ưu hóa chi phí sản xuất', stat: 'Giảm tới 90%', color: '#10b981' },
    { title: 'Đột phá năng suất tương lai', stat: 'Tăng trưởng x3', color: '#3b82f6' }
  ];

  rows.forEach((r, idx) => {
    const ry = y + 74 + idx * 56;
    lgShape(g, 'rect', {
      x: rowStartX, y: ry, width: rowW, height: 44, rx: 10,
      fill: idx % 2 === 0 ? '#f8fafc' : '#ffffff',
      stroke: 'rgba(226, 232, 240, 0.6)', 'stroke-width': 1
    });
    // Pulsing status dot
    const dotPulse = 0.6 + 0.4 * Math.sin(t * 3.5 + idx);
    lgShape(g, 'circle', { cx: rowStartX + 20, cy: ry + 22, r: 5, fill: r.color, opacity: dotPulse });
    // Title
    g.append(lgEl('text', {
      x: rowStartX + 36, y: ry + 30,
      fill: '#1e293b', 'font-size': 24, 'font-weight': '700',
      'font-family': 'Inter, sans-serif'
    }, r.title));
    // Stat
    g.append(lgEl('text', {
      x: rowStartX + rowW - 20, y: ry + 30,
      'text-anchor': 'end',
      fill: '#64748b', 'font-size': 24, 'font-weight': '600',
      'font-family': 'Inter, sans-serif'
    }, r.stat));
  });

  // Mac Cursor pointing and clicking on row 1
  const curP = clamp((t - 0.5) / 1.0);
  const curEase = easeLg(curP);
  const curX = rowStartX + 240 + (1 - curEase) * 80;
  const curY = y + 96 + (1 - curEase) * 40;
  const clickScale = (t > 1.2 && t < 1.6) ? 0.9 : 1.0;

  const curG = lgGroup(g, {
    transform: `translate(${curX}, ${curY}) scale(${clickScale})`
  });
  // Apple Cursor SVG Path
  lgShape(curG, 'path', {
    d: 'M 0 0 L 0 16 L 4.5 12.5 L 8 19 L 10.5 17.5 L 7 11.5 L 12 11.5 Z',
    fill: '#0f172a', stroke: '#ffffff', 'stroke-width': 1.5, 'stroke-linejoin': 'round'
  });

  // Black Badge at bottom left
  const bW = 220, bH = 42;
  const bX = x + 36, bY = y + h - 58;
  lgShape(g, 'rect', {
    x: bX, y: bY, width: bW, height: bH, rx: 12,
    fill: 'rgba(15, 23, 42, 0.92)'
  });
  g.append(lgEl('text', {
    x: bX + bW / 2, y: bY + 29,
    'text-anchor': 'middle',
    fill: '#ffffff', 'font-size': 24, 'font-weight': '800',
    'font-family': 'Inter, sans-serif'
  }, String(d.badge || 'Hệ sinh thái AI')));
}

// =========================================================================
// MOCKUP: AI Neural Network Architecture (Nodes & Flowing Synapses)
// =========================================================================
function renderAiNetworkMockup(parent, x, y, w, h, d, t) {
  const g = lgGroup(parent);
  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: h, rx: 32,
    fill: '#080d1a', stroke: '#1e293b', 'stroke-width': 2
  });

  const isLarge = h > 600;

  // Header Title
  g.append(lgEl('text', {
    x: x + 48, y: y + (isLarge ? 72 : 54),
    fill: '#38bdf8', 'font-size': isLarge ? 34 : 28, 'font-weight': '900',
    'letter-spacing': '1px', 'font-family': 'Inter, sans-serif'
  }, String(d.title || d.chip || 'MẠNG NƠ-RON AI & TỰ ĐỘNG HÓA').toUpperCase().slice(0, 32)));

  g.append(lgEl('text', {
    x: x + 48, y: y + (isLarge ? 112 : 86),
    fill: '#94a3b8', 'font-size': 24, 'font-weight': '600',
    'font-family': 'Inter, sans-serif'
  }, 'Xử lý tính toán song song đa tầng'));

  // Center Neural Network Nodes
  const netCx = x + w / 2, netCy = y + (isLarge ? h * 0.48 : h * 0.54);
  const spreadX = isLarge ? 280 : 220;
  const spreadY = isLarge ? 140 : 80;
  const nodes = [
    { id: 'in1', x: netCx - spreadX, y: netCy - spreadY, label: 'Dữ liệu', color: '#38bdf8' },
    { id: 'in2', x: netCx - spreadX, y: netCy, label: 'Thị trường', color: '#38bdf8' },
    { id: 'in3', x: netCx - spreadX, y: netCy + spreadY, label: 'Tự động', color: '#38bdf8' },
    { id: 'h1',  x: netCx, y: netCy - spreadY * 1.3, label: 'Lớp ẩn 1', color: '#818cf8' },
    { id: 'h2',  x: netCx, y: netCy - spreadY * 0.4, label: 'Lớp ẩn 2', color: '#818cf8' },
    { id: 'h3',  x: netCx, y: netCy + spreadY * 0.4, label: 'Lớp ẩn 3', color: '#818cf8' },
    { id: 'h4',  x: netCx, y: netCy + spreadY * 1.3, label: 'Lớp ẩn 4', color: '#818cf8' },
    { id: 'out1', x: netCx + spreadX, y: netCy - spreadY * 0.6, label: 'Năng suất', color: '#34d399' },
    { id: 'out2', x: netCx + spreadX, y: netCy + spreadY * 0.6, label: 'Tối ưu', color: '#34d399' }
  ];

  const connections = [
    ['in1', 'h1'], ['in1', 'h2'], ['in2', 'h2'], ['in2', 'h3'],
    ['in3', 'h3'], ['in3', 'h4'], ['h1', 'out1'], ['h2', 'out1'],
    ['h3', 'out2'], ['h4', 'out2'], ['h2', 'out2'], ['h3', 'out1']
  ];
  connections.forEach(([fromId, toId], idx) => {
    const fromNode = nodes.find(n => n.id === fromId);
    const toNode = nodes.find(n => n.id === toId);
    if (!fromNode || !toNode) return;
    const pulse = 0.25 + 0.35 * Math.sin(t * 3.0 + idx * 0.8);
    lgShape(g, 'line', {
      x1: fromNode.x, y1: fromNode.y, x2: toNode.x, y2: toNode.y,
      stroke: '#38bdf8', 'stroke-width': 2, opacity: pulse
    });
    const packetT = ((t * 0.8 + idx * 0.15) % 1.0);
    const px = fromNode.x + (toNode.x - fromNode.x) * packetT;
    const py = fromNode.y + (toNode.y - fromNode.y) * packetT;
    lgShape(g, 'circle', {
      cx: px, cy: py, r: 4, fill: '#ffffff', opacity: 0.9
    });
  });

  nodes.forEach(n => {
    const nodePulse = 1.0 + 0.1 * Math.sin(t * 2.5 + n.x);
    const nG = lgGroup(g, {
      transform: `translate(${n.x}, ${n.y}) scale(${nodePulse}) translate(${-n.x}, ${-n.y})`
    });
    lgShape(nG, 'circle', {
      cx: n.x, cy: n.y, r: isLarge ? 28 : 20, fill: '#131d31', stroke: n.color, 'stroke-width': 2.5
    });
    lgShape(nG, 'circle', {
      cx: n.x, cy: n.y, r: isLarge ? 12 : 8, fill: n.color, opacity: 0.85
    });
    nG.append(lgEl('text', {
      x: n.x, y: n.y + (isLarge ? 48 : 34), 'text-anchor': 'middle',
      fill: '#cbd5e1', 'font-size': 24, 'font-weight': '600',
      'font-family': 'Inter, sans-serif'
    }, n.label));
  });

  // Bottom Status Bar
  const footY = y + h - (isLarge ? 72 : 56);
  lgShape(g, 'rect', {
    x: x + 44, y: footY, width: w - 88, height: 48, rx: 16,
    fill: '#131d31', stroke: '#1e293b', 'stroke-width': 1.5
  });
  const dotP = 0.6 + 0.4 * Math.sin(t * 4);
  lgShape(g, 'circle', { cx: x + 72, cy: footY + 24, r: 6, fill: '#34d399', opacity: dotP });
  g.append(lgEl('text', {
    x: x + 92, y: footY + 32,
    fill: '#f8fafc', 'font-size': 24, 'font-weight': '700',
    'font-family': 'Inter, sans-serif'
  }, 'Mạng nơ-ron AI: Hoạt động tối đa công suất'));
}

// =========================================================================
// MOCKUP: Financial Risk & Currency Depreciation Shield
// =========================================================================
function renderRiskShieldMockup(parent, x, y, w, h, d, t) {
  const g = lgGroup(parent);
  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: h, rx: 32,
    fill: '#0f1422', stroke: '#1e293b', 'stroke-width': 2
  });

  const isLarge = h > 600;

  // Header Title
  g.append(lgEl('text', {
    x: x + 48, y: y + (isLarge ? 72 : 54),
    fill: '#f59e0b', 'font-size': isLarge ? 34 : 28, 'font-weight': '900',
    'letter-spacing': '1px', 'font-family': 'Inter, sans-serif'
  }, String(d.chip || d.title || 'CẢNH BÁO TÀI CHÍNH & LẠM PHÁT').toUpperCase().slice(0, 32)));

  g.append(lgEl('text', {
    x: x + 48, y: y + (isLarge ? 112 : 86),
    fill: '#94a3b8', 'font-size': 24, 'font-weight': '600',
    'font-family': 'Inter, sans-serif'
  }, 'Đánh giá rủi ro nắm giữ tiền mặt'));

  // Center Hexagonal Shield
  const sCx = x + w / 2, sCy = y + (isLarge ? h * 0.44 : h * 0.48);
  const pulseR = (t * 45) % 180;
  lgShape(g, 'circle', {
    cx: sCx, cy: sCy, r: 80 + pulseR, fill: 'none', stroke: '#f59e0b',
    'stroke-width': 2, opacity: Math.max(0, 1 - pulseR / 180) * 0.5
  });

  const sR = isLarge ? 120 : 90;
  const hexPoints = [];
  for (let i = 0; i < 6; i++) {
    const angle = (i * 60 - 30) * Math.PI / 180;
    hexPoints.push(`${sCx + sR * Math.cos(angle)},${sCy + sR * Math.sin(angle)}`);
  }
  lgShape(g, 'polygon', {
    points: hexPoints.join(' '),
    fill: '#182033', stroke: '#f59e0b', 'stroke-width': 4
  });

  const warnScale = 1.0 + 0.08 * Math.sin(t * 3);
  const wG = lgGroup(g, {
    transform: `translate(${sCx}, ${sCy}) scale(${warnScale}) translate(${-sCx}, ${-sCy})`
  });
  wG.append(lgEl('text', {
    x: sCx, y: sCy + (isLarge ? 28 : 20), 'text-anchor': 'middle',
    fill: '#f59e0b', 'font-size': isLarge ? 80 : 56, 'font-weight': '900',
    'font-family': 'Inter, sans-serif'
  }, '⚠'));

  // 2 Warning Alert Cards below
  const boxW = (w - 120) / 2, boxH = isLarge ? 130 : 96, boxY = y + h - (isLarge ? 160 : 110);
  const b1X = x + 44, b2X = b1X + boxW + 24;

  lgShape(g, 'rect', {
    x: b1X, y: boxY, width: boxW, height: boxH, rx: 18,
    fill: '#161e30', stroke: '#1e293b', 'stroke-width': 1.5
  });
  g.append(lgEl('text', {
    x: b1X + 24, y: boxY + (isLarge ? 40 : 32), fill: '#ef4444', 'font-size': 26, 'font-weight': '800',
    'font-family': 'Inter, sans-serif'
  }, 'TIỀN MẶT'));
  g.append(lgEl('text', {
    x: b1X + 24, y: boxY + (isLarge ? 76 : 60), fill: '#cbd5e1', 'font-size': 24, 'font-weight': '600',
    'font-family': 'Inter, sans-serif'
  }, 'Mất giá theo thời gian'));

  lgShape(g, 'rect', {
    x: b2X, y: boxY, width: boxW, height: boxH, rx: 18,
    fill: '#161e30', stroke: '#1e293b', 'stroke-width': 1.5
  });
  g.append(lgEl('text', {
    x: b2X + 24, y: boxY + (isLarge ? 40 : 32), fill: '#10b981', 'font-size': 26, 'font-weight': '800',
    'font-family': 'Inter, sans-serif'
  }, 'CÔNG NGHỆ'));
  g.append(lgEl('text', {
    x: b2X + 24, y: boxY + (isLarge ? 76 : 60), fill: '#cbd5e1', 'font-size': 24, 'font-weight': '600',
    'font-family': 'Inter, sans-serif'
  }, 'Tăng trưởng sinh lời'));
}

// Smart Mockup Selector: grounded in slide context
function renderContentSmartMockup(parent, x, y, w, h, d, t, duration = 4) {
  const combined = (String(d.text || '') + ' ' + String(d.title || '') + ' ' + String(d.author || '')).toLowerCase();
  const hasPerson = combined.includes('elon') || combined.includes('musk') || combined.includes('sam') || combined.includes('ceo') || combined.includes('tuyên bố') || combined.includes('cho rằng') || combined.includes('nói rằng') || d.author;
  const hasFinancial = d.value !== undefined || d.neon_stat || combined.includes('tỷ') || combined.includes('triệu') || combined.includes('chi phí') || combined.includes('tiền') || combined.includes('%');
  const hasAi = combined.includes('ai') || combined.includes('mạng') || combined.includes('nơ-ron') || combined.includes('bước nhảy');
  const hasRisk = combined.includes('rủi ro') || combined.includes('cảnh báo') || combined.includes('thiệt thòi') || combined.includes('hoài nghi');

  if (d.mockup_type === 'ai_network' || (hasAi && !hasPerson && !hasFinancial)) {
    renderAiNetworkMockup(parent, x, y, w, h, d, t);
  } else if (d.mockup_type === 'risk_shield' || hasRisk) {
    renderRiskShieldMockup(parent, x, y, w, h, d, t);
  } else if (d.mockup_type === 'social_post' || hasPerson) {
    renderSocialPostMockup(parent, x, y + 20, w, h - 30, d, t);
  } else if (d.mockup_type === 'financial_chart' || hasFinancial) {
    renderFinancialChartMockup(parent, x, y, w, h, d, t);
  } else {
    renderTechArchitectureMockup(parent, x, y, w, h, d, t);
  }
}

// =========================================================================
// MOCKUP GENERATOR 1: GitHub Repository Card (Visual Evidence)
// =========================================================================
function renderGithubRepoMockup(parent, x, y, w, h, d) {
  const g = lgGroup(parent);

  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: h, rx: 24,
    fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.95)', 'stroke-width': 1.5
  });

  const avX = x + 44, avY = y + 50;
  lgShape(g, 'circle', {
    cx: avX, cy: avY, r: 24, fill: '#0f172a'
  });
  lgShape(g, 'path', {
    d: `M ${avX - 8} ${avY - 8} v 16 M ${avX - 8} ${avY} h 10 a 6 6 0 0 1 6 6 v 2`,
    stroke: '#ffffff', 'stroke-width': 2.5, fill: 'none', 'stroke-linecap': 'round'
  });

  const repoName = String(d.repo_name || d.source || 'tashfeenahmed / freellmapi').trim();
  g.append(lgEl('text', {
    x: x + 82, y: y + 58,
    fill: '#1e1b4b', 'font-size': 26, 'font-weight': '800',
    'font-family': 'Inter, sans-serif'
  }, repoName.slice(0, 36)));

  const starW = 120, starH = 42;
  const starX = x + w - starW - 36, starY = y + 28;
  lgShape(g, 'rect', {
    x: starX, y: starY, width: starW, height: starH, rx: 12,
    fill: '#f8fafc', stroke: '#e2e8f0', 'stroke-width': 1.5
  });
  g.append(lgEl('text', {
    x: starX + starW / 2, y: starY + 28,
    'text-anchor': 'middle',
    fill: '#475569', 'font-size': 24, 'font-weight': '700',
    'font-family': 'Inter, sans-serif'
  }, '★ Star'));

  const desc1 = String(d.repo_desc || d.summary || '7.4 billion tokens per month, 34 free LLM providers').trim();
  const desc2 = '635 free model endpoints, all behind one single API.';
  g.append(lgEl('text', {
    x: x + 44, y: y + 120,
    fill: '#64748b', 'font-size': 24, 'font-weight': '500',
    'font-family': 'Inter, sans-serif'
  }, desc1.slice(0, 56)));
  g.append(lgEl('text', {
    x: x + 44, y: y + 158,
    fill: '#64748b', 'font-size': 24, 'font-weight': '500',
    'font-family': 'Inter, sans-serif'
  }, desc2));

  lgShape(g, 'line', {
    x1: x + 44, y1: y + h - 70, x2: x + w - 44, y2: y + h - 70,
    stroke: 'rgba(226, 232, 240, 0.8)', 'stroke-width': 1.5
  });

  const metaY = y + h - 28;
  lgShape(g, 'circle', { cx: x + 48, cy: metaY - 6, r: 6, fill: '#3b82f6' });
  g.append(lgEl('text', { x: x + 62, y: metaY, fill: '#64748b', 'font-size': 24, 'font-weight': '600', 'font-family': 'Inter, sans-serif' }, 'Python'));
  g.append(lgEl('text', { x: x + 180, y: metaY, fill: '#64748b', 'font-size': 24, 'font-weight': '600', 'font-family': 'Inter, sans-serif' }, '★ 104'));
  g.append(lgEl('text', { x: x + 280, y: metaY, fill: '#64748b', 'font-size': 24, 'font-weight': '600', 'font-family': 'Inter, sans-serif' }, '⑂ 20'));
  g.append(lgEl('text', { x: x + 380, y: metaY, fill: '#64748b', 'font-size': 24, 'font-weight': '600', 'font-family': 'Inter, sans-serif' }, 'MIT License'));
}

// =========================================================================
// MOCKUP GENERATOR 2: Dark Console Mockup Card (Stat Hero)
// =========================================================================
function renderDarkConsoleMockup(parent, x, y, w, h, d) {
  const g = lgGroup(parent);

  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: h, rx: 24,
    fill: '#0b0f19', stroke: '#1e293b', 'stroke-width': 1.5
  });

  const neonText = String(d.neon_stat || (d.value ? `~${d.value}${d.unit || ''} tokens` : '~7.4B tokens')).trim();
  g.append(lgEl('text', {
    x: x + 44, y: y + 68,
    fill: '#10b981', 'font-size': 44, 'font-weight': '900',
    'letter-spacing': '-0.02em', 'font-family': 'Inter, monospace, sans-serif'
  }, neonText.slice(0, 28)));

  const boxW = 260, boxH = 135, gap = 24;
  const startX = x + 44, boxY = y + 105;

  const boxes = [
    { num: String(d.stat_box_1 || '34'), lbl: 'Nhà cung cấp', color: '#38bdf8' },
    { num: String(d.stat_box_2 || '635'), lbl: 'Endpoints', color: '#a78bfa' },
    { num: String(d.stat_box_3 || '474'), lbl: 'Hệ thống API', color: '#34d399' }
  ];

  boxes.forEach((b, idx) => {
    const bx = startX + idx * (boxW + gap);
    lgShape(g, 'rect', {
      x: bx, y: boxY, width: boxW, height: boxH, rx: 16,
      fill: '#131d31', stroke: '#1e293b', 'stroke-width': 1.5
    });
    g.append(lgEl('text', {
      x: bx + boxW / 2, y: boxY + 62,
      'text-anchor': 'middle',
      fill: b.color, 'font-size': 40, 'font-weight': '900',
      'font-family': 'Inter, sans-serif'
    }, b.num));
    g.append(lgEl('text', {
      x: bx + boxW / 2, y: boxY + 102,
      'text-anchor': 'middle',
      fill: '#94a3b8', 'font-size': 24, 'font-weight': '600',
      'font-family': 'Inter, sans-serif'
    }, b.lbl));
  });

  g.append(lgEl('text', {
    x: x + 44, y: y + h - 28,
    fill: '#64748b', 'font-size': 24, 'font-weight': '600',
    'font-family': 'Inter, sans-serif'
  }, 'Hệ thống nhà cung cấp trực tuyến'));
}

// =========================================================================
// MOCKUP GENERATOR 3: Mac OS Web App / Dashboard Mockup Window
// =========================================================================
function renderBrowserDashboardMockup(parent, x, y, w, h, d) {
  const g = lgGroup(parent);

  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: h, rx: 24,
    fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.95)', 'stroke-width': 1.5
  });

  lgShape(g, 'rect', {
    x: x, y: y, width: w, height: 52, rx: 24,
    fill: '#f8fafc'
  });
  lgShape(g, 'circle', { cx: x + 32, cy: y + 26, r: 6, fill: '#ff5f56' });
  lgShape(g, 'circle', { cx: x + 52, cy: y + 26, r: 6, fill: '#ffbd2e' });
  lgShape(g, 'circle', { cx: x + 72, cy: y + 26, r: 6, fill: '#27c93f' });

  const urlW = 380, urlH = 28;
  const urlX = x + (w - urlW) / 2, urlY = y + 12;
  lgShape(g, 'rect', {
    x: urlX, y: urlY, width: urlW, height: urlH, rx: 8,
    fill: '#e2e8f0'
  });
  g.append(lgEl('text', {
    x: urlX + urlW / 2, y: urlY + 20,
    'text-anchor': 'middle',
    fill: '#64748b', 'font-size': 24, 'font-weight': '600',
    'font-family': 'Inter, sans-serif'
  }, String(d.domain || 'api.freellm.tech').slice(0, 28)));

  const rowStartX = x + 32, rowW = w - 64;
  const rows = [
    { title: 'OpenAI Compatibility', stat: 'Hoạt động', color: '#10b981' },
    { title: 'Automatic Failover', stat: 'Sẵn sàng', color: '#10b981' },
    { title: 'Rate Limit Optimization', stat: 'Tối ưu', color: '#3b82f6' }
  ];

  rows.forEach((r, idx) => {
    const ry = y + 70 + idx * 56;
    lgShape(g, 'rect', {
      x: rowStartX, y: ry, width: rowW, height: 44, rx: 10,
      fill: idx % 2 === 0 ? '#f8fafc' : '#ffffff',
      stroke: 'rgba(226, 232, 240, 0.6)', 'stroke-width': 1
    });
    lgShape(g, 'circle', { cx: rowStartX + 20, cy: ry + 22, r: 5, fill: r.color });
    g.append(lgEl('text', {
      x: rowStartX + 36, y: ry + 30,
      fill: '#1e293b', 'font-size': 24, 'font-weight': '700',
      'font-family': 'Inter, sans-serif'
    }, r.title));
    g.append(lgEl('text', {
      x: rowStartX + rowW - 20, y: ry + 30,
      'text-anchor': 'end',
      fill: '#64748b', 'font-size': 24, 'font-weight': '600',
      'font-family': 'Inter, sans-serif'
    }, r.stat));
  });

  const bW = 220, bH = 42;
  const bX = x + 32, bY = y + h - 56;
  lgShape(g, 'rect', {
    x: bX, y: bY, width: bW, height: bH, rx: 12,
    fill: 'rgba(15, 23, 42, 0.92)'
  });
  g.append(lgEl('text', {
    x: bX + bW / 2, y: bY + 29,
    'text-anchor': 'middle',
    fill: '#ffffff', 'font-size': 24, 'font-weight': '800',
    'font-family': 'Inter, sans-serif'
  }, String(d.badge || 'Bảng điều khiển')));
}

// =========================================================================
// MOCKUP GENERATOR 4: Floating Reaction Bubbles (Hearts & Likes)
// =========================================================================
function renderFloatingReactions(parent, cx, cy, t) {
  const g = lgGroup(parent);
  const items = [
    { type: 'heart', color: '#ef4444', icon: '♥', offsetX: -140, offsetY: -35, delay: 0.1 },
    { type: 'like', color: '#3b82f6', icon: '👍', offsetX: 130, offsetY: -45, delay: 0.25 },
    { type: 'heart', color: '#f43f5e', icon: '♥', offsetX: -110, offsetY: 70, delay: 0.4 },
    { type: 'like', color: '#2563eb', icon: '👍', offsetX: 140, offsetY: 60, delay: 0.55 },
    { type: 'heart', color: '#8b5cf6', icon: '♥', offsetX: -30, offsetY: -110, delay: 0.7 }
  ];

  items.forEach(it => {
    const wave = Math.sin((t * 2.5) + it.delay * 6.28);
    const floatY = cy + it.offsetY + wave * 8;
    const floatX = cx + it.offsetX + Math.cos(t * 2.0 + it.delay * 4) * 5;
    const r = 26;

    const bG = lgGroup(g, {
      transform: `translate(${floatX}, ${floatY})`
    });
    lgShape(bG, 'circle', {
      cx: 0, cy: 0, r: r,
      fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.9)', 'stroke-width': 1.5
    });
    bG.append(lgEl('text', {
      x: 0, y: it.type === 'heart' ? 9 : 8,
      'text-anchor': 'middle',
      fill: it.color, 'font-size': 24, 'font-weight': '900',
      'font-family': 'Inter, sans-serif'
    }, it.icon));
  });
}

// =========================================================================
// 1. lg_source_headline (Hero Full-Stage Visual Motion: [75, 1005] x [245, 1325])
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

  const stageX = 85, stageW = 910;
  const stageY = 270, stageH = 1030;

  const imgUrl = d.image_url || d.image_uri || d.image || d.clip_url;
  if (imgUrl) {
    renderRealImageWithGentleMotion(root, stageX, stageY, stageW, stageH, imgUrl, d, t, duration, 'lg-src-img');
  } else {
    renderContentSmartMockup(root, stageX, stageY, stageW, stageH, d, t, duration);
  }
}

// =========================================================================
// 2. lg_stat_hero (Hero Full-Stage Visual Motion: [75, 1005] x [245, 1325])
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

  const stageX = 85, stageW = 910;
  const stageY = 270, stageH = 1030;

  // If this beat has financial/metric data, render dynamic animated chart
  const hasChart = d.mockup_type === 'financial_chart' || d.mockup_type === 'candlestick_chart' || d.value !== undefined || d.neon_stat;
  if (hasChart) {
    renderFinancialChartMockup(root, stageX, stageY, stageW, stageH, d, t);
  } else if (d.image_url || d.image || d.chart_image) {
    const imgUrl = d.image_url || d.image || d.chart_image;
    renderRealImageWithGentleMotion(root, stageX, stageY, stageW, stageH, imgUrl, d, t, duration, 'lg-stat-img');
  } else {
    renderFinancialChartMockup(root, stageX, stageY, stageW, stageH, d, t);
  }
}

// =========================================================================
// 3. lg_shot_features (Hero Full-Stage Visual Motion: [75, 1005] x [245, 1325])
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

  const stageX = 85, stageW = 910;
  const stageY = 270, stageH = 1030;

  const imgUrl = d.image_url || d.image || d.ui_image;
  if (imgUrl) {
    renderRealImageWithGentleMotion(root, stageX, stageY, stageW, stageH, imgUrl, d, t, duration, 'lg-feat-img');
  } else {
    renderTechArchitectureMockup(root, stageX, stageY, stageW, stageH, d, t);
  }
}

// =========================================================================
// 4. lg_vs_compare (Hero Full-Stage Opposing Visuals: [75, 1005] x [245, 1325])
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

  const stageX = 85, stageW = 910;
  const stageY = 270, stageH = 1030;

  const imgUrl = d.image_url || d.image;
  if (imgUrl) {
    renderRealImageWithGentleMotion(root, stageX, stageY, stageW, stageH, imgUrl, d, t, duration, 'lg-vs-img');
    return;
  }

  const card1Y = 245, card1H = 460;
  const card2Y = 825, card2H = 495;

  const left = d.left || (Array.isArray(d.items) && d.items[0]) || (Array.isArray(d.bars) && d.bars[0]) || {};
  const right = d.right || (Array.isArray(d.items) && d.items[1]) || (Array.isArray(d.bars) && d.bars[1]) || {};

  const card1Label = (typeof left === 'object' ? (left.label || left.tag || left.kicker) : '') || d.label_left || 'TIẾT KIỆM TRUYỀN THỐNG';
  const card1Text = (typeof left === 'object' ? (left.title || left.text || left.name) : String(left)) || d.text_left || 'Cất tiền vào heo đất';

  const card2Label = (typeof right === 'object' ? (right.label || right.tag || right.kicker) : '') || d.label_right || 'TÁI ĐẦU TƯ CÔNG NGHỆ';
  const card2Text = (typeof right === 'object' ? (right.title || right.text || right.name) : String(right)) || d.text_right || 'Dòng vốn đổi mới sinh lời';

  const isWinner2 = d.winner !== 1 && d.winner !== 'left';

  // ----------------- CARD 1: TOP (TRADITIONAL) -----------------
  const c1G = lgGroup(root);
  lgShape(c1G, 'rect', {
    x: stageX, y: card1Y, width: stageW, height: card1H, rx: 32,
    fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.95)', 'stroke-width': 1.5
  });

  const p1G = lgGroup(c1G);
  const p1W = Math.min(600, card1Label.length * 16 + 48);
  lgShape(p1G, 'rect', {
    x: stageX + 44, y: card1Y + 36, width: p1W, height: 42, rx: 14,
    fill: '#f1f5f9', stroke: '#cbd5e1', 'stroke-width': 1.2
  });
  p1G.append(lgEl('text', {
    x: stageX + 44 + p1W / 2, y: card1Y + 65,
    'text-anchor': 'middle',
    fill: '#475569', 'font-size': 24, 'font-weight': '800',
    'letter-spacing': '0.5px', 'font-family': 'Inter, sans-serif'
  }, String(card1Label).trim().toUpperCase().slice(0, 26)));

  const lines1 = wrapWordsMaxChars(card1Text, 22, 2);
  const fs1 = 44;
  lines1.forEach((line, i) => {
    c1G.append(lgEl('text', {
      x: stageX + 48, y: card1Y + 140 + i * (fs1 * 1.25),
      fill: '#1e293b', 'font-size': fs1, 'font-weight': '900',
      'letter-spacing': '-0.02em', 'font-family': 'Inter, sans-serif'
    }, line));
  });

  const lIconG = lgGroup(c1G);
  const lCx = stageX + stageW - 130, lCy = card1Y + 160;
  lgShape(lIconG, 'circle', { cx: lCx, cy: lCy, r: 48, fill: '#fef2f2', stroke: '#fecaca', 'stroke-width': 2 });
  lIconG.append(lgEl('text', {
    x: lCx, y: lCy + 16, 'text-anchor': 'middle', fill: '#ef4444', 'font-size': 44, 'font-weight': '900',
    'font-family': 'Inter, sans-serif'
  }, '🔒'));

  const warnW = 340, warnH = 46;
  const warnY = card1Y + card1H - 74;
  lgShape(c1G, 'rect', {
    x: stageX + 48, y: warnY, width: warnW, height: warnH, rx: 14,
    fill: '#fef2f2', stroke: '#fecaca', 'stroke-width': 1.2
  });
  c1G.append(lgEl('text', {
    x: stageX + 48 + warnW / 2, y: warnY + 31, 'text-anchor': 'middle',
    fill: '#dc2626', 'font-size': 24, 'font-weight': '700', 'font-family': 'Inter, sans-serif'
  }, '⚠ Mất giá theo lạm phát'));

  // ----------------- CARD 2: BOTTOM (INNOVATION / WINNER) -----------------
  const c2G = lgGroup(root);
  lgShape(c2G, 'rect', {
    x: stageX, y: card2Y, width: stageW, height: card2H, rx: 32,
    fill: '#ffffff', stroke: '#10b981', 'stroke-width': 3
  });

  const p2G = lgGroup(c2G);
  const p2W = Math.min(600, card2Label.length * 16 + 48);
  lgShape(p2G, 'rect', {
    x: stageX + 44, y: card2Y + 36, width: p2W, height: 42, rx: 14,
    fill: '#ecfdf5', stroke: '#a7f3d0', 'stroke-width': 1.2
  });
  p2G.append(lgEl('text', {
    x: stageX + 44 + p2W / 2, y: card2Y + 65,
    'text-anchor': 'middle',
    fill: '#059669', 'font-size': 24, 'font-weight': '800',
    'letter-spacing': '0.5px', 'font-family': 'Inter, sans-serif'
  }, String(card2Label).trim().toUpperCase().slice(0, 26)));

  const lines2 = wrapWordsMaxChars(card2Text, 22, 2);
  const fs2 = 44;
  lines2.forEach((line, i) => {
    c2G.append(lgEl('text', {
      x: stageX + 48, y: card2Y + 140 + i * (fs2 * 1.25),
      fill: '#1e293b', 'font-size': fs2, 'font-weight': '900',
      'letter-spacing': '-0.02em', 'font-family': 'Inter, sans-serif'
    }, line));
  });

  const rIconG = lgGroup(c2G);
  const rCx = stageX + stageW - 130, rCy = card2Y + 160;
  lgShape(rIconG, 'circle', { cx: rCx, cy: rCy, r: 48, fill: '#ecfdf5', stroke: '#a7f3d0', 'stroke-width': 2 });
  rIconG.append(lgEl('text', {
    x: rCx, y: rCy + 16, 'text-anchor': 'middle', fill: '#059669', 'font-size': 44, 'font-weight': '900',
    'font-family': 'Inter, sans-serif'
  }, '🚀'));

  if (isWinner2) {
    const wG = lgGroup(c2G);
    const winW = 380, winH = 50;
    const winY = card2Y + card2H - 74;

    lgShape(wG, 'rect', {
      x: stageX + 48, y: winY, width: winW, height: winH, rx: 16,
      fill: '#ecfdf5', stroke: '#059669', 'stroke-width': 1.8
    });
    wG.append(lgEl('text', {
      x: stageX + 48 + winW / 2, y: winY + 34,
      'text-anchor': 'middle',
      fill: '#059669', 'font-size': 26, 'font-weight': '900',
      'letter-spacing': '1px', 'font-family': 'Inter, sans-serif'
    }, '★ WINNER · TĂNG TRƯỞNG'));
  }

  // ----------------- CENTER: "VS" CIRCLE -----------------
  const vsG = lgGroup(root);
  const vsCy = (card1Y + card1H + card2Y) / 2;
  const vsPulse = 1.0 + 0.08 * Math.sin(t * 3);
  const vsCircleG = lgGroup(vsG, {
    transform: `translate(540, ${vsCy}) scale(${vsPulse}) translate(-540, ${-vsCy})`
  });
  lgShape(vsCircleG, 'circle', {
    cx: 540, cy: vsCy, r: 42,
    fill: '#0f172a', stroke: '#ffffff', 'stroke-width': 3
  });
  vsCircleG.append(lgEl('text', {
    x: 540, y: vsCy + 12,
    'text-anchor': 'middle',
    fill: '#ffffff', 'font-size': 32, 'font-weight': '900',
    'font-family': 'Inter, sans-serif'
  }, 'VS'));
}

// =========================================================================
// 5. lg_note_card (Hero Full-Stage Visual Mockup / Evidence: [75, 1005] x [245, 1325])
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

  const stageX = 85, stageW = 910;
  const stageY = 270, stageH = 1030;

  // If this beat is an emergency fund or reserve gauge, render dynamic gauge chart
  const isEmergency = d.mockup_type === 'emergency_fund' || d.mockup_type === 'emergency_gauge' || /quỹ dự phòng|khẩn cấp|3 đến 6/i.test(String(d.chip || d.text || ''));
  if (isEmergency) {
    renderEmergencyGaugeMockup(root, stageX, stageY, stageW, stageH, d, t);
    return;
  }

  const imgUrl = d.image_url || d.image || d.clip_url;
  if (imgUrl) {
    renderRealImageWithGentleMotion(root, stageX, stageY, stageW, stageH, imgUrl, d, t, duration, 'lg-note-img');
  } else if (d.mockup_type === 'ai_network') {
    renderAiNetworkMockup(root, stageX, stageY, stageW, stageH, d, t);
  } else if (d.mockup_type === 'risk_shield') {
    renderRiskShieldMockup(root, stageX, stageY, stageW, stageH, d, t);
  } else {
    renderContentSmartMockup(root, stageX, stageY, stageW, stageH, d, t, duration);
  }
}

// =========================================================================
// 6. lg_cta_profile (Hero Discussion & Community Profile: [75, 1005] x [245, 1325])
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

  const stageX = 85, stageW = 910;
  const stageY = 270, stageH = 1030;

  // Background dynamic floating reactions
  renderFloatingReactions(root, 540, 780, t);

  // Center Channel Discussion Card
  const cardW = 840, cardH = 560;
  const cardX = 540 - cardW / 2, cardY = 530;

  const cardG = lgGroup(root);
  lgShape(cardG, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#ffffff', stroke: 'rgba(226, 232, 240, 0.95)', 'stroke-width': 2
  });

  // Channel Avatar with pulsing radar ring
  const avX = 540, avY = cardY + 110, avR = 54;
  const pulseR = 54 + 14 * Math.sin(t * 3);
  lgShape(cardG, 'circle', {
    cx: avX, cy: avY, r: pulseR, fill: 'none', stroke: '#2563eb', 'stroke-width': 2, opacity: 0.4
  });
  lgShape(cardG, 'circle', {
    cx: avX, cy: avY, r: avR, fill: '#0f172a'
  });
  const chanName = String(d.channel_name || 'TIN CÔNG NGHỆ').trim();
  cardG.append(lgEl('text', {
    x: avX, y: avY + 18, 'text-anchor': 'middle',
    fill: '#ffffff', 'font-size': 50, 'font-weight': '900',
    'font-family': 'Inter, sans-serif'
  }, chanName.charAt(0).toUpperCase()));

  // Channel Name & Verified Tick
  cardG.append(lgEl('text', {
    x: 540, y: cardY + 225, 'text-anchor': 'middle',
    fill: '#0f172a', 'font-size': 44, 'font-weight': '900',
    'letter-spacing': '-0.02em', 'font-family': 'Inter, sans-serif'
  }, chanName.slice(0, 24)));

  // Handle
  const chanHandle = String(d.channel_handle || '@tincongnghe').trim();
  cardG.append(lgEl('text', {
    x: 540, y: cardY + 270, 'text-anchor': 'middle',
    fill: '#64748b', 'font-size': 26, 'font-weight': '600',
    'font-family': 'Inter, sans-serif'
  }, chanHandle.slice(0, 30)));

  // CTA Pill button
  const ctaW = 440, ctaH = 64;
  const ctaX = 540 - ctaW / 2, ctaY = cardY + 325;
  lgShape(cardG, 'rect', {
    x: ctaX, y: ctaY, width: ctaW, height: ctaH, rx: 32,
    fill: '#2563eb'
  });
  cardG.append(lgEl('text', {
    x: 540, y: ctaY + 42, 'text-anchor': 'middle',
    fill: '#ffffff', 'font-size': 28, 'font-weight': '800',
    'letter-spacing': '0.5px', 'font-family': 'Inter, sans-serif'
  }, 'THẢO LUẬN NGAY'));

  // Bio / Question
  const bioText = String(d.bio || d.text || 'Khám phá công nghệ & AI tương lai cùng chúng tôi').trim();
  const bioLines = wrapWordsMaxChars(bioText, 26, 2);
  bioLines.forEach((l, idx) => {
    cardG.append(lgEl('text', {
      x: 540, y: cardY + 435 + idx * 36, 'text-anchor': 'middle',
      fill: '#475569', 'font-size': 24, 'font-weight': '600',
      'font-family': 'Inter, sans-serif'
    }, l));
  });
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
