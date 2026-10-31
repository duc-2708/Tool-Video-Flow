/* Motion Vocabulary Recipes (Phase 7 - Step a: 8 Core Number & Fill Recipes)
 * Deterministic SVG & Canvas rendering driven strictly by absolute time t, duration, and data.
 * Pure mathematical functions, no external side-effects, full seek support.
 */
(()=>{'use strict';

const { clamp, easeOutCubic, easeInOutCubic, spring, overshoot, squashAndStretch } = window.MotionEasing || {
  clamp: (v, min = 0, max = 1) => Math.max(min, Math.min(max, v)),
  easeOutCubic: (t) => 1 - Math.pow(1 - t, 3),
  easeInOutCubic: (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  spring: (t, freq = 6, decay = 5) => 1 - Math.exp(-decay * t) * Math.cos(freq * t * Math.PI * 2),
  overshoot: (t, s = 1.70158) => { const p = t - 1; return p * p * ((s + 1) * p + s) + 1; },
  squashAndStretch: (t) => ({ sx: 1 + 0.15 * Math.sin(t * Math.PI), sy: 1 - 0.15 * Math.sin(t * Math.PI) })
};

const TRAILING_CUTOFF_JS = new Set([
  'của', 'trong', 'trên', 'dưới', 'và', 'với', 'là', 'mà', 'để', 'cho', 'về',
  'các', 'những', 'một', 'cái', 'con', 'chiếc', 'bà', 'ông', 'đã', 'đang', 'sẽ',
  'lại', 'cũng', 'rất', 'hơn', 'nhất', 'ra', 'vào', 'lên', 'xuống', 'đột', 'cá',
  'vai', 'dàn', 'bối', 'sự', 'vụ', 'điều', 'việc', 'vì', 'do', 'bởi', 'hay',
  'hoặc', 'nếu', 'khi', 'tuy', 'dẫu', 'dở', 'bị', 'được', 'đóng', 'đặt', 'này',
  'kia', 'đó', 'đây', 'tới', 'ở', 'gặp', 'gọi', 'như', 'theo', 'hành', 'tạo', 'làm',
  'khiến', 'giúp', 'sau', 'bày', 'tỏ', 'lên', 'xuống', 'qua', 'lại', 'thường', 'có',
  'tài', 'đến', 'đi', 'giống', 'ý', 'thì', 'rằng', 'vậy', 'thế', 'nào',
  'sao', 'gì', 'ai', 'đâu', 'nữa', 'chăng', 'từ'
]);

const INCOMPLETE_TRAILING_JS = new Set([
  'thiết', 'ngân', 'an', 'bảo', 'thông', 'kỹ', 'tài', 'hệ', 'dữ', 'kinh',
  'máy', 'phần', 'tin', 'lỗ', 'thị', 'cơ', 'tổng', 'pháp', 'quốc', 'chính',
  'trách', 'quy', 'đối', 'kết', 'truy', 'bắt', 'tạm', 'xâm', 'ngăn', 'xét'
]);

const LEADING_CUTOFF_JS = new Set([
  'cố', 'việc', 'động', 'giống', 'điều', 'ngột', 'trò', 'nhạc', 'nhân', 'viên',
  'này', 'kia', 'đó', 'đây', 'thì', 'mà', 'là', 'và', 'của', 'với', 'để', 'cho',
  'về', 'bà', 'ông', 'bị', 'được', 'ra', 'vào', 'lại', 'cũng', 'hơn', 'nhất',
  'như', 'bởi', 'do', 'vì', 'đóng', 'đặt', 'tạo', 'làm', 'những', 'các', 'một',
  'khiến', 'giúp', 'sau', 'sau khi', 'trong khi', 'bởi vì', 'thay vì', 'bày', 'tỏ', 'đã', 'ý'
]);

function internalSanitizeSemanticLabel(label, maxWords = 6) {
  if (!label) return '';
  const str = String(label).trim().replace(/[.,:;!?…()“”"']/g, '');
  if (/^(?:minh họa|ý tưởng minh họa|minh họa ý tưởng|minh họa nội dung|ý chính cần nhớ)/i.test(str)) return '';

  let allWords = str.split(/\s+/).filter(Boolean);
  while (allWords.length > 0 && LEADING_CUTOFF_JS.has(allWords[0].toLowerCase())) {
    allWords.shift();
  }
  while (allWords.length > 0 && (TRAILING_CUTOFF_JS.has(allWords[allWords.length - 1].toLowerCase()) || INCOMPLETE_TRAILING_JS.has(allWords[allWords.length - 1].toLowerCase()))) {
    allWords.pop();
  }
  if (allWords.length >= 4 && allWords[2].toLowerCase() === 'từ') {
    allWords.splice(2, 1);
  }
  const COMPOUND_PAIRS_JS = new Set([
    'thiết bị', 'hoạt động', 'ngân hàng', 'an ninh', 'an toàn',
    'bảo mật', 'thông tin', 'tài sản', 'tài chính', 'kỹ thuật',
    'kỹ sư', 'lỗ hổng', 'hệ thống', 'chính sách', 'trách nhiệm',
    'pháp lý', 'quốc tế', 'dữ liệu', 'máy tính', 'phần mềm',
    'tin tặc', 'quy định', 'thiết kế', 'khóa cửa', 'khai thác',
    'nghiêm trọng', 'toàn cầu', 'đăng nhập', 'điểm yếu', 'tấn công',
    'đột nhập', 'xác thực', 'ngân sách', 'doanh nghiệp', 'phòng thủ', 'rủi ro'
  ]);
  const isTrailingWordJs = (wList) => {
    if (!wList || wList.length === 0) return false;
    const last = wList[wList.length - 1].toLowerCase();
    if (wList.length >= 2) {
      const pair = wList[wList.length - 2].toLowerCase() + ' ' + last;
      if (COMPOUND_PAIRS_JS.has(pair)) return false;
    }
    return TRAILING_CUTOFF_JS.has(last) || INCOMPLETE_TRAILING_JS.has(last);
  };
  while (isTrailingWordJs(allWords)) {
    allWords.pop();
  }
  let words = allWords.slice(0, Math.min(allWords.length, maxWords));
  const lastIsCompound = words.length >= 2 && COMPOUND_PAIRS_JS.has(words[words.length - 2].toLowerCase() + ' ' + words[words.length - 1].toLowerCase());
  if (words.length > 0 && !lastIsCompound && INCOMPLETE_TRAILING_JS.has(words[words.length - 1].toLowerCase())) {
    if (words.length < allWords.length && words.length <= 4) {
      words.push(allWords[words.length]);
      if (words.length > 4 && words.length > maxWords) {
        words.pop(); words.pop();
      }
    } else {
      words.pop();
    }
  }
  while (isTrailingWordJs(words)) {
    words.pop();
  }
  if (words.length === 0) return '';
  const res = words.join(' ');
  return res.charAt(0).toUpperCase() + res.slice(1);
}

const sanitizeSemanticLabel = (lbl, maxWords = 6) => {
  if (window.MotionLayout && typeof window.MotionLayout.sanitizeSemanticLabel === 'function') {
    return window.MotionLayout.sanitizeSemanticLabel(lbl, maxWords);
  }
  return internalSanitizeSemanticLabel(lbl, maxWords);
};

const wrapText = (txt, maxChars = 20) => {
  if (window.MotionLayout && typeof window.MotionLayout.wrapText === 'function') {
    return window.MotionLayout.wrapText(txt, maxChars);
  }
  return [txt];
};

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
// 1. SLOT_COUNTER: Máy quay số 3 cuộn lăn tít, dừng giật nấc, LED nháy
// =========================================================================
function renderSlotCounter(ctx, svg, d, t, duration = 4) {
  if (!d._is_fixture && (d.value === null || d.value === undefined || isNaN(Number(d.value)))) {
    if (window.MotionRecipes && window.MotionRecipes.renderTextFocus) {
      return window.MotionRecipes.renderTextFocus(ctx, svg, d, t, duration, 0);
    }
  }
  const rawVal = Number(d.value ?? 0);
  const unit = d.unit || '';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Khung máy trồi lên
  // Action [0.6 - 2.2s]: Cuộn số quay tít rồi dừng so le
  // Impact [2.2 - 4.0s]: Khóa vị trí, rung haptic, LED chạy vòng quanh

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.2);
  const enterAlpha = clamp(t / 0.3);

  // Background aura
  shape(svg, 'circle', {
    cx: 540, cy: 780, r: 320,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 3)
  });

  const root = group(svg, {
    transform: `translate(540, 780) scale(${enterScale}) translate(-540, -780)`,
    opacity: enterAlpha
  });

  const boxW = 880;
  const boxH = 680;
  const boxX = 540 - boxW / 2;
  const boxY = 780 - boxH / 2;

  // 3D Outer Machine Shell
  shape(root, 'rect', {
    x: boxX + 10, y: boxY + 15, width: boxW, height: boxH, rx: 32,
    fill: '#060a12', opacity: 0.7
  }); // Cast shadow

  const outerShell = shape(root, 'rect', {
    x: boxX, y: boxY, width: boxW, height: boxH, rx: 32,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4
  });

  // Machine header marquee / nameplate
  shape(root, 'rect', {
    x: boxX + 60, y: boxY - 35, width: boxW - 120, height: 70, rx: 16,
    fill: '#1e293b', stroke: 'var(--accent, #00f5d4)', 'stroke-width': 3
  });
  root.append(el('text', {
    x: 540, y: boxY + 10, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Animated LED border dots (36 dots around border)
  const numDots = 28;
  const ledSpeed = t * 6;
  for (let i = 0; i < numDots; i++) {
    let px, py;
    const perSide = numDots / 4;
    const sideIdx = Math.floor(i / perSide);
    const subIdx = i % perSide;
    const ratio = (subIdx + 0.5) / perSide;

    if (sideIdx === 0) { px = boxX + 25 + ratio * (boxW - 50); py = boxY + 20; }
    else if (sideIdx === 1) { px = boxX + boxW - 20; py = boxY + 25 + ratio * (boxH - 50); }
    else if (sideIdx === 2) { px = boxX + boxW - 25 - ratio * (boxW - 50); py = boxY + boxH - 20; }
    else { px = boxX + 20; py = boxY + boxH - 25 - ratio * (boxH - 50); }

    const isLit = (Math.floor(ledSpeed + i) % 2 === 0) || (t > 2.2 && (Math.floor(t * 8) % 2 === 0));
    shape(root, 'circle', {
      cx: px, cy: py, r: 6,
      fill: isLit ? '#fbbf24' : '#475569',
      filter: isLit ? 'url(#neon-glow)' : 'none'
    });
  }

  // 3-4 Slot Windows
  // Determine target digits
  const valStr = Math.abs(rawVal) >= 1000 ? String(Math.round(rawVal)) : String(rawVal);
  const targetChars = valStr.split('');
  const numSlots = Math.max(1, Math.min(6, targetChars.length));
  const maxSlotW = 160;
  const availW = boxW - 140;
  const slotW = Math.min(maxSlotW, (availW - (numSlots - 1) * 20) / numSlots);
  const totalSlotsW = numSlots * slotW + (numSlots - 1) * 20;
  const slotStartX = boxX + (boxW - totalSlotsW) / 2;
  const slotH = 260;
  const slotY = boxY + 80;

  // Clip path for reels
  const defs = el('defs');
  root.append(defs);

  const stopStep = Math.min(0.35, Math.max(0.12, (duration - 1.0) / Math.max(1, numSlots)));

  targetChars.forEach((ch, idx) => {
    const slotX = slotStartX + idx * (slotW + 20);
    const clipId = `slot-clip-${idx}-${Math.floor(t * 100)}`;
    const clip = el('clipPath', { id: clipId });
    clip.append(el('rect', { x: slotX, y: slotY, width: slotW, height: slotH, rx: 16 }));
    defs.append(clip);

    // Slot cavity background
    shape(root, 'rect', {
      x: slotX, y: slotY, width: slotW, height: slotH, rx: 16,
      fill: '#020617', stroke: '#1e293b', 'stroke-width': 3
    });

    // Reel spinning calculation
    // Stop times: scale with duration, finishes before shot end
    const stopTime = Math.min(duration - 0.35, 0.6 + (idx + 1) * stopStep);
    const isStopping = t >= stopTime;
    const gReel = group(root, { 'clip-path': `url(#${clipId})` });

    const targetDigit = Number.isNaN(Number(ch)) ? 0 : Number(ch);
    let offset = 0;

    // Vận tốc và pha cuộn lệch nhau để không bao giờ quay đồng bộ 1 1 1
    const spinSpeed = 1600 + idx * 320;
    const phaseOffset = idx * 270;

    if (t < 0.5) {
      offset = phaseOffset % 1200;
    } else if (t < stopTime) {
      // Spinning fast với pha so le
      offset = ((t - 0.5) * spinSpeed + phaseOffset) % 1200;
    } else {
      // Impact snap with spring bounce
      const snapElapsed = t - stopTime;
      const bounce = spring(clamp(snapElapsed / 0.5), 8, 7);
      offset = (1 - bounce) * 45; // slight mechanical overshoot
    }

    // Draw digits reel strip
    const reelGroup = group(gReel, { transform: `translate(0, ${-offset})` });

    if (isStopping) {
      // Stationary final number: hiển thị đúng chữ số đích thực tế
      const isImpact = t >= 2.2;
      reelGroup.append(el('text', {
        x: slotX + slotW / 2, y: slotY + slotH / 2 + 38,
        'text-anchor': 'middle',
        'font-size': '110', 'font-weight': '900',
        fill: isImpact ? '#fef08a' : '#ffffff',
        filter: isImpact ? 'url(#neon-glow)' : 'none',
        class: 'ill-label'
      }, ch));
    } else {
      // Blurring strip while spinning với dải số lệch pha cho từng cuộn
      const reelShift = (idx * 3 + 1) % 10;
      for (let dIdx = -2; dIdx < 12; dIdx++) {
        const dNum = (dIdx + reelShift + 20) % 10;
        reelGroup.append(el('text', {
          x: slotX + slotW / 2, y: slotY + slotH / 2 + 38 + dIdx * 110,
          'text-anchor': 'middle',
          'font-size': '100', 'font-weight': 'bold',
          fill: '#64748b', opacity: 0.7
        }, String(dNum)));
      }
    }

    // Glass reflection & inner gradient shadows (top & bottom of slot)
    shape(root, 'rect', {
      x: slotX, y: slotY, width: slotW, height: 35,
      fill: 'linear-gradient(to bottom, #020617, transparent)', opacity: 0.8
    });
    shape(root, 'rect', {
      x: slotX, y: slotY + slotH - 35, width: slotW, height: 35,
      fill: 'linear-gradient(to top, #020617, transparent)', opacity: 0.8
    });
    // Center payoff payline marker
    shape(root, 'line', {
      x1: slotX, y1: slotY + slotH / 2, x2: slotX + slotW, y2: slotY + slotH / 2,
      stroke: 'var(--accent, #00f5d4)', 'stroke-width': 1.5, opacity: 0.35
    });
  });

  // Footer Unit & Status Bar
  const footY = boxY + boxH - 55;
  if (unit) {
    root.append(el('text', {
      x: 540, y: footY + 28, 'text-anchor': 'middle',
      'font-size': '44', 'font-weight': 'bold',
      fill: '#38bdf8', class: 'ill-label'
    }, unit.toUpperCase()));
  }

  // Idle haptic pulse at impact
  if (t >= 2.2) {
    const pulseR = 340 + 20 * Math.sin((t - 2.2) * 5);
    shape(root, 'circle', {
      cx: 540, cy: 780, r: pulseR,
      fill: 'none', stroke: '#fbbf24', 'stroke-width': 2, opacity: 0.25 * Math.max(0, 1 - (t - 2.2) * 0.4)
    });
  }
}

// =========================================================================
// 2. STRIKE_REPLACE: Số cũ bị gạch đỏ chém qua + ✗ nảy lên, số mới trồi lên
// =========================================================================
function renderStrikeReplace(ctx, svg, d, t, duration = 4) {
  const rawOld = d.old_value !== undefined ? d.old_value : (d.bars && d.bars[0]?.value !== undefined ? d.bars[0].value : null);
  const rawNew = d.new_value !== undefined ? d.new_value : (d.value !== undefined ? d.value : (d.bars && d.bars[1]?.value !== undefined ? d.bars[1].value : null));
  if (!d._is_fixture && (rawOld === null || rawNew === null || isNaN(Number(rawOld)) || isNaN(Number(rawNew)))) {
    if (window.MotionRecipes && window.MotionRecipes.renderTextFocus) {
      return window.MotionRecipes.renderTextFocus(ctx, svg, d, t, duration, 0);
    }
  }
  const oldVal = Number(rawOld);
  const newVal = Number(rawNew);
  const unit = d.unit || '';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.7s]: Thẻ số cũ xám xuất hiện ở trung tâm
  // Action [0.7 - 1.8s]: Vết chém đỏ quét qua kèm ✗, số cũ tụt lùi
  // Impact [1.8 - 4.0s]: Số mới khổng lồ trồi lên bừng sáng neon

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.1);

  // Center positions
  const cx = 540;
  const cyOld = 650;
  const cyNew = 910;

  // Background aura
  shape(svg, 'circle', {
    cx, cy: 780, r: 340,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg);

  // --- 1. OLD NUMBER CARD ---
  // When t > 1.4s, old card shrinks and shifts up
  let oldCardY = cyOld;
  let oldCardScale = 1.0;
  let oldOpacity = clamp(t / 0.4);

  if (t >= 1.4) {
    const pShift = clamp((t - 1.4) / 0.6);
    oldCardY = cyOld - 110 * easeOutCubic(pShift);
    oldCardScale = 1.0 - 0.22 * easeOutCubic(pShift);
    oldOpacity = Math.max(0.35, 1.0 - 0.5 * pShift);
  }

  const gOld = group(root, {
    transform: `translate(${cx}, ${oldCardY}) scale(${oldCardScale}) translate(${-cx}, ${-oldCardY})`,
    opacity: oldOpacity
  });

  // Old Card Frame
  shape(gOld, 'rect', {
    x: cx - 360, y: oldCardY - 100, width: 720, height: 180, rx: 24,
    fill: '#1e293b', stroke: '#475569', 'stroke-width': 3,
    class: 'glass-card'
  });

  const oldText = `${formatNum(oldVal)} ${unit}`.trim();
  gOld.append(el('text', {
    x: cx, y: oldCardY + 30, 'text-anchor': 'middle',
    'font-size': '100', 'font-weight': 'bold',
    fill: '#94a3b8', class: 'ill-label'
  }, oldText));

  // Strike Slash Line [0.7s - 1.2s]
  if (t >= 0.7) {
    const slashP = clamp((t - 0.7) / 0.35);
    const slashLen = 700 * easeOutCubic(slashP);
    const x1 = cx - 330;
    const y1 = oldCardY - 60;
    const x2 = x1 + slashLen;
    const y2 = y1 + 120 * (slashLen / 700);

    shape(gOld, 'line', {
      x1, y1, x2, y2,
      stroke: '#ef4444', 'stroke-width': 10, 'stroke-linecap': 'round',
      filter: 'url(#neon-glow)'
    });

    // Cross symbol ✗ pops up
    if (t >= 0.9) {
      const crossP = clamp((t - 0.9) / 0.3);
      const crossScale = spring(crossP, 7, 6);
      const gCross = group(gOld, {
        transform: `translate(${cx + 310}, ${oldCardY - 40}) scale(${crossScale})`
      });
      shape(gCross, 'circle', { cx: 0, cy: 0, r: 36, fill: '#ef4444' });
      shape(gCross, 'line', { x1: -16, y1: -16, x2: 16, y2: 16, stroke: '#ffffff', 'stroke-width': 6, 'stroke-linecap': 'round' });
      shape(gCross, 'line', { x1: 16, y1: -16, x2: -16, y2: 16, stroke: '#ffffff', 'stroke-width': 6, 'stroke-linecap': 'round' });
    }
  }

  // --- 2. NEW NUMBER CARD [1.5s - 4.0s] ---
  if (t >= 1.4) {
    const newP = clamp((t - 1.4) / 0.6);
    const newScale = spring(newP, 6, 5);
    const newAlpha = clamp((t - 1.4) / 0.3);

    // Idle float [2.2s - 4.0s]
    const idleY = t >= 2.0 ? Math.sin((t - 2.0) * 3) * 8 : 0;
    const curNewY = cyNew + idleY;

    const gNew = group(root, {
      transform: `translate(${cx}, ${curNewY}) scale(${newScale}) translate(${-cx}, ${-curNewY})`,
      opacity: newAlpha
    });

    // Glowing New Card Frame
    shape(gNew, 'rect', {
      x: cx - 400, y: curNewY - 140, width: 800, height: 260, rx: 32,
      fill: '#0f172a', stroke: '#10b981', 'stroke-width': 6,
      filter: 'url(#neon-glow)', class: 'glass-card'
    });

    const newText = `${formatNum(newVal)} ${unit}`.trim();
    gNew.append(el('text', {
      x: cx, y: curNewY + 45, 'text-anchor': 'middle',
      'font-size': '145', 'font-weight': '900',
      fill: '#34d399', filter: 'url(#neon-glow)', class: 'ill-label'
    }, newText));

    // Checkmark Badge ✓
    if (t >= 1.8) {
      const checkP = clamp((t - 1.8) / 0.3);
      const checkScale = spring(checkP, 7, 6);
      const gCheck = group(gNew, {
        transform: `translate(${cx + 340}, ${curNewY - 80}) scale(${checkScale})`
      });
      shape(gCheck, 'circle', { cx: 0, cy: 0, r: 42, fill: '#10b981' });
      // Draw check path
      const checkPath = el('path', {
        d: 'M -18 2 L -4 16 L 20 -12',
        fill: 'none', stroke: '#ffffff', 'stroke-width': 7,
        'stroke-linecap': 'round', 'stroke-linejoin': 'round'
      });
      gCheck.append(checkPath);
    }
  }

  // Header Title Chip
  const gTitle = group(root);
  shape(gTitle, 'rect', {
    x: cx - 260, y: 440, width: 520, height: 64, rx: 16,
    fill: '#1e293b', stroke: 'var(--accent, #00f5d4)', 'stroke-width': 2
  });
  gTitle.append(el('text', {
    x: cx, y: 484, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: '#f8fafc', class: 'ill-label'
  }, label));
}

// =========================================================================
// 3. GAUGE_NEEDLE: Đồng hồ áp suất kim quay bán nguyệt 3 dải màu, rung cơ học
// =========================================================================
function renderGaugeNeedle(ctx, svg, d, t, duration = 4) {
  if (!d._is_fixture && (d.value === null || d.value === undefined || isNaN(Number(d.value)))) {
    if (window.MotionRecipes && window.MotionRecipes.renderTextFocus) {
      return window.MotionRecipes.renderTextFocus(ctx, svg, d, t, duration, 0);
    }
  }
  const targetVal = Number(d.value ?? 0);
  const maxVal = Number(d.max_val ?? (targetVal > 100 ? targetVal * 1.2 : 100));
  const unit = d.unit || '%';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.7s]: Đồng hồ bán nguyệt mở rộng
  // Action [0.7 - 2.3s]: Kim quay vọt từ 0 tới đích
  // Impact [2.3 - 4.0s]: Kim dao động nảy nhẹ ở đỉnh, còi cảnh báo phát sáng

  const enterP = clamp(t / 0.7);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 790;
  const r = 240;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2.5)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.4)
  });

  // Gauge Outer Housing Card
  shape(root, 'rect', {
    x: cx - 400, y: cy - 280, width: 800, height: 560, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Label Header
  root.append(el('text', {
    x: cx, y: cy - 215, 'text-anchor': 'middle',
    'font-size': '40', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Gauge Arc: from -135 deg to +135 deg (total 270 deg)
  // Let 0 deg be 12 o'clock, so -135 deg is bottom-left, +135 deg is bottom-right
  const startAngle = -135;
  const endAngle = 135;
  const totalSweep = endAngle - startAngle; // 270 deg

  const polarToCartesian = (centerX, centerY, radius, angleInDegrees) => {
    const angleInRadians = (angleInDegrees - 90) * Math.PI / 180.0;
    return {
      x: centerX + (radius * Math.cos(angleInRadians)),
      y: centerY + (radius * Math.sin(angleInRadians))
    };
  };

  const describeArc = (x, y, radius, startAng, endAng) => {
    const start = polarToCartesian(x, y, radius, endAng);
    const end = polarToCartesian(x, y, radius, startAng);
    const largeArcFlag = endAng - startAng <= 180 ? '0' : '1';
    return ['M', start.x, start.y, 'A', radius, radius, 0, largeArcFlag, 0, end.x, end.y].join(' ');
  };

  // 3 Color Arc Zones:
  // Green: 0% - 50% (-135 to 0)
  // Yellow: 50% - 75% (0 to +67.5)
  // Red: 75% - 100% (+67.5 to +135)
  const a0 = startAngle;
  const a1 = startAngle + totalSweep * 0.50; // 0 deg
  const a2 = startAngle + totalSweep * 0.75; // +67.5 deg
  const a3 = endAngle;                       // +135 deg

  // Track background
  shape(root, 'path', {
    d: describeArc(cx, cy, r, startAngle, endAngle),
    fill: 'none', stroke: '#1e293b', 'stroke-width': 28, 'stroke-linecap': 'round'
  });

  // Green Zone
  shape(root, 'path', {
    d: describeArc(cx, cy, r, a0, a1),
    fill: 'none', stroke: '#10b981', 'stroke-width': 26, 'stroke-linecap': 'round'
  });
  // Yellow Zone
  shape(root, 'path', {
    d: describeArc(cx, cy, r, a1, a2),
    fill: 'none', stroke: '#f59e0b', 'stroke-width': 26
  });
  // Red Zone
  shape(root, 'path', {
    d: describeArc(cx, cy, r, a2, a3),
    fill: 'none', stroke: '#ef4444', 'stroke-width': 26, 'stroke-linecap': 'round'
  });

  // Ticks along the arc
  for (let i = 0; i <= 10; i++) {
    const tickAng = startAngle + (totalSweep * (i / 10));
    const pInner = polarToCartesian(cx, cy, r - 26, tickAng);
    const pOuter = polarToCartesian(cx, cy, r - 42, tickAng);
    shape(root, 'line', {
      x1: pInner.x, y1: pInner.y, x2: pOuter.x, y2: pOuter.y,
      stroke: '#94a3b8', 'stroke-width': i % 5 === 0 ? 4 : 2
    });
  }

  // Action Needle Rotation dynamically scaled to shot duration
  const actDuration = Math.min(1.4, Math.max(0.6, duration * 0.55));
  const actStart = Math.min(0.3, duration * 0.12);
  const actEnd = actStart + actDuration;
  const targetPct = clamp(targetVal / maxVal);
  let needleAngle = startAngle;

  if (t < actStart) {
    needleAngle = startAngle;
  } else if (t < actEnd) {
    const actP = clamp((t - actStart) / actDuration);
    const curPct = targetPct * easeOutCubic(actP);
    needleAngle = startAngle + totalSweep * curPct;
  } else {
    // Impact damped spring oscillation, settling exactly at targetPct
    const impP = clamp((t - actEnd) / Math.max(0.3, duration - actEnd));
    const decay = Math.exp(-impP * 5);
    const wobble = Math.sin((t - actEnd) * 16) * 4 * decay;
    needleAngle = startAngle + totalSweep * targetPct + (impP >= 0.85 ? 0 : wobble);
  }

  // Draw Pointer Needle
  const gNeedle = group(root, {
    transform: `rotate(${needleAngle}, ${cx}, ${cy})`
  });

  // Needle Shape (long sharp blade with tip)
  const needlePath = el('path', {
    d: `M ${cx - 10} ${cy} L ${cx} ${cy - r + 15} L ${cx + 10} ${cy} Z`,
    fill: targetPct > 0.75 ? '#ef4444' : '#38bdf8',
    filter: 'url(#neon-glow)'
  });
  gNeedle.append(needlePath);

  // Center Pivot Hub
  shape(root, 'circle', {
    cx, cy, r: 32,
    fill: '#0f172a', stroke: '#e2e8f0', 'stroke-width': 6
  });
  shape(root, 'circle', {
    cx, cy, r: 14,
    fill: 'var(--accent, #00f5d4)'
  });

  // Digital readout counter at bottom of gauge - exact integer display at rest
  const currentDisplayedVal = t < actStart ? 0 : (t < actEnd ? (targetVal * easeOutCubic((t - actStart) / actDuration)) : targetVal);
  const isTargetInt = Number.isInteger(targetVal);
  const numDecimals = (t >= actEnd && isTargetInt) ? 0 : (isTargetInt ? 0 : 1);
  const formattedVal = (t >= actEnd && isTargetInt) ? String(targetVal) : formatRawViNum(currentDisplayedVal, numDecimals);
  const digitalStr = `${formattedVal} ${unit}`.trim();

  shape(root, 'rect', {
    x: cx - 180, y: cy + 120, width: 360, height: 90, rx: 20,
    fill: '#020617', stroke: targetPct > 0.75 ? '#ef4444' : '#38bdf8', 'stroke-width': 3
  });

  root.append(el('text', {
    x: cx, y: cy + 182, 'text-anchor': 'middle',
    'font-size': '64', 'font-weight': '900',
    fill: targetPct > 0.75 ? '#f87171' : '#38bdf8',
    filter: targetPct > 0.75 ? 'url(#neon-glow)' : 'none',
    class: 'ill-label'
  }, digitalStr));
}

// =========================================================================
// 4. ODOMETER: Trục số cơ khí xe hơi lăn bánh răng từng hàng đơn vị, chục, trăm
// =========================================================================
function renderOdometer(ctx, svg, d, t, duration = 4) {
  if (!d._is_fixture && (d.value === null || d.value === undefined || isNaN(Number(d.value)))) {
    if (window.MotionRecipes && window.MotionRecipes.renderTextFocus) {
      return window.MotionRecipes.renderTextFocus(ctx, svg, d, t, duration, 0);
    }
  }
  const targetVal = Number(d.value ?? 0);
  const unit = d.unit || '';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Hộp công tơ mét xuất hiện
  // Action [0.6 - 2.4s]: Bánh răng cuộn liên tục theo cấp số
  // Impact [2.4 - 4.0s]: Khóa khớp cơ học, vệt sáng phản chiếu quét ngang

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 320,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const boxW = 880;
  const boxH = 680;
  const boxX = cx - boxW / 2;
  const boxY = cy - boxH / 2;

  // Mechanical Outer Bezel
  shape(root, 'rect', {
    x: boxX, y: boxY, width: boxW, height: boxH, rx: 36,
    fill: '#0b1120', stroke: '#475569', 'stroke-width': 5,
    class: 'glass-card'
  });

  // Top Title
  root.append(el('text', {
    x: cx, y: boxY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Digits array (e.g. 0 1 2 5 0)
  const valStr = String(Math.round(targetVal));
  const numDigits = Math.max(1, Math.min(6, valStr.length));
  const paddedTarget = valStr;

  const drumW = Math.min(160, (boxW - 120 - (numDigits - 1) * 16) / numDigits);
  const totalDrumsW = numDigits * drumW + (numDigits - 1) * 16;
  const drumStartX = boxX + (boxW - totalDrumsW) / 2;
  const drumH = 220;
  const drumY = boxY + 110;

  // Action progress [0.6s - (duration - 0.4s)]
  const actDuration = Math.min(1.8, Math.max(0.6, duration - 1.0));
  const actionP = clamp((t - 0.6) / actDuration);
  const smoothedP = easeInOutCubic(actionP);

  const defs = el('defs');
  root.append(defs);

  for (let i = 0; i < numDigits; i++) {
    const drumX = drumStartX + i * (drumW + 16);
    const targetDigit = Number(paddedTarget[i]);

    // Mechanical gear ratios:
    // Rightmost digit (units) rolls fastest; leftmost rolls slowest
    const power = numDigits - 1 - i;
    // Continuous rolling value for this drum
    const totalRolls = targetDigit + (power === 0 ? 10 * (1 - smoothedP) : 0);
    const curContinuousVal = smoothedP >= 1.0 ? targetDigit : (targetDigit * smoothedP);

    const clipId = `odo-clip-${i}-${Math.floor(t * 100)}`;
    const clip = el('clipPath', { id: clipId });
    clip.append(el('rect', { x: drumX, y: drumY, width: drumW, height: drumH, rx: 14 }));
    defs.append(clip);

    // Drum cavity frame
    shape(root, 'rect', {
      x: drumX, y: drumY, width: drumW, height: drumH, rx: 14,
      fill: '#020617', stroke: '#1e293b', 'stroke-width': 2
    });

    const gDrum = group(root, { 'clip-path': `url(#${clipId})` });

    // Calculate vertical offset of number strip
    const digitH = 120;
    const currentInt = Math.floor(curContinuousVal);
    const frac = curContinuousVal - currentInt;

    // Center baseline
    const baseY = drumY + drumH / 2 + 38;

    // Draw previous, current, and next digits
    [-1, 0, 1].forEach(offset => {
      const dNum = (currentInt + offset + 20) % 10;
      const dY = baseY + (offset - frac) * digitH;
      gDrum.append(el('text', {
        x: drumX + drumW / 2, y: dY, 'text-anchor': 'middle',
        'font-size': '105', 'font-weight': 'bold',
        fill: '#f1f5f9', font_family: 'monospace', class: 'ill-label'
      }, String(dNum)));
    });

    // Cylindrical top/bottom darkening overlays for 3D barrel illusion
    shape(root, 'rect', {
      x: drumX, y: drumY, width: drumW, height: 40,
      fill: 'linear-gradient(to bottom, rgba(2,6,23,0.95), transparent)'
    });
    shape(root, 'rect', {
      x: drumX, y: drumY + drumH - 40, width: drumW, height: 40,
      fill: 'linear-gradient(to top, rgba(2,6,23,0.95), transparent)'
    });
  }

  // Bottom Unit Banner
  if (unit) {
    root.append(el('text', {
      x: cx, y: boxY + boxH - 55, 'text-anchor': 'middle',
      'font-size': '44', 'font-weight': 'bold',
      fill: '#38bdf8', class: 'ill-label'
    }, unit.toUpperCase()));
  }

  // Impact Glass Glare Sweep [2.4s - 3.4s]
  if (t >= 2.4) {
    const sweepP = clamp((t - 2.4) / 1.0);
    const glareX = boxX + sweepP * (boxW + 300) - 150;
    const glarePath = el('polygon', {
      points: `${glareX},${boxY} ${glareX + 80},${boxY} ${glareX - 40},${boxY + boxH} ${glareX - 120},${boxY + boxH}`,
      fill: '#ffffff', opacity: 0.15 * (1 - sweepP)
    });
    root.append(glarePath);
  }
}

// =========================================================================
// 5. BAR_RACE: Cuộc đua nước rút giữa các thanh tốc độ, bứt phá dẫn đầu
// =========================================================================
function renderBarRace(ctx, svg, d, t, duration = 4) {
  if (!d._is_fixture && (!d.bars || d.bars.length < 2) && (!d.items || d.items.length < 2 || typeof d.items[0] !== 'object' || d.items[0].value === undefined)) {
    if (window.MotionRecipes && window.MotionRecipes.renderTextFocus) {
      return window.MotionRecipes.renderTextFocus(ctx, svg, d, t, duration, 0);
    }
  }
  const items = d.items || [
    { label: 'Thị phần A', value: 72 },
    { label: 'Dự án cốt lõi', value: 95, highlight: true },
    { label: 'Đối thủ B', value: 58 }
  ];
  const unit = d.unit || '%';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.7s]: Làn đua và thanh xuất phát
  // Action [0.7 - 2.5s]: Các thanh tăng tốc, thanh chủ đạo bứt phá ngoạn mục
  // Impact [2.5 - 4.0s]: Cán đích, tung sao vàng / cờ chiến thắng

  const enterP = clamp(t / 0.7);
  const enterScale = overshoot(enterP, 1.1);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  // Race Arena Card
  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 32,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Arena Title
  root.append(el('text', {
    x: cx, y: cardY + 60, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Finish Line on the right side
  const finishX = cardX + cardW - 130;
  const startLaneY = cardY + 110;
  const laneHeight = 110;

  // Draw Checkered Finish Line
  for (let fRow = 0; fRow < 10; fRow++) {
    const isDark = fRow % 2 === 0;
    shape(root, 'rect', {
      x: finishX, y: startLaneY + fRow * 38, width: 20, height: 38,
      fill: isDark ? '#ffffff' : '#020617'
    });
  }

  // Action timing [0.7s - 2.5s]
  const actionP = clamp((t - 0.7) / 1.8);
  const maxBarW = finishX - (cardX + 260);

  items.slice(0, 4).forEach((item, idx) => {
    const laneY = startLaneY + idx * laneHeight;
    const isHighlight = Boolean(item.highlight || idx === 1);
    const itemLabel = sanitizeSemanticLabel(item.label || `Làn ${idx + 1}`, 6);
    const targetVal = Number(item.value || 0);

    // Track lane background
    shape(root, 'rect', {
      x: cardX + 50, y: laneY, width: cardW - 100, height: 80, rx: 18,
      fill: '#1e293b', stroke: isHighlight ? 'var(--accent, #00f5d4)' : '#334155',
      'stroke-width': isHighlight ? 2 : 1
    });

    // Lane Label
    root.append(el('text', {
      x: cardX + 70, y: laneY + 50,
      'font-size': '36', 'font-weight': 'bold',
      fill: isHighlight ? '#f8fafc' : '#94a3b8', class: 'ill-label'
    }, itemLabel));

    // Dynamic racing calculation
    // Highlighted bar catches up and overtakes at t ~ 1.8s
    let currentPct = 0;
    if (t >= 0.7) {
      if (isHighlight) {
        // Starts slower, zooms ahead in second half
        const surgeP = Math.pow(actionP, 1.8);
        currentPct = targetVal * surgeP;
      } else {
        // Starts faster, plateaus earlier
        const earlyP = Math.sin(actionP * Math.PI * 0.5);
        currentPct = targetVal * earlyP;
      }
    }

    const currentW = Math.max(30, (currentPct / 100) * maxBarW);
    const barX = cardX + 260;

    // Racing Bar
    const barColor = isHighlight ? 'var(--accent, #00f5d4)' : '#64748b';
    shape(root, 'rect', {
      x: barX, y: laneY + 12, width: currentW, height: 56, rx: 14,
      fill: barColor, filter: isHighlight ? 'url(#neon-glow)' : 'none'
    });

    // Numeric badge on bar tip
    const tipX = barX + currentW - 15;
    root.append(el('text', {
      x: Math.max(barX + 65, tipX), y: laneY + 50, 'text-anchor': 'end',
      'font-size': '36', 'font-weight': 'bold',
      fill: isHighlight ? '#020617' : '#ffffff', class: 'ill-label'
    }, `${Math.round(currentPct)}${unit}`));

    // Champion Crown / Star upon finish [2.5s - 4.0s]
    if (isHighlight && t >= 2.5) {
      const champP = clamp((t - 2.5) / 0.5);
      const starScale = spring(champP, 6, 6);
      const starX = barX + currentW + 55;
      const starY = laneY + 40;

      const gStar = group(root, {
        transform: `translate(${starX}, ${starY}) scale(${starScale})`
      });
      shape(gStar, 'polygon', {
        points: '0,-24 7,-7 25,-7 11,5 16,23 0,13 -16,23 -11,5 -25,-7 -7,-7',
        fill: '#fbbf24', stroke: '#d97706', 'stroke-width': 2,
        filter: 'url(#neon-glow)'
      });
    }
  });
}

// =========================================================================
// 6. THERMOMETER: Cột nhiệt kế dâng trào qua các vạch chia, tỏa sóng nhiệt đỏ
// =========================================================================
function renderThermometer(ctx, svg, d, t, duration = 4) {
  if (!d._is_fixture && (d.temperature === undefined || d.temperature === null) && (d.value === null || d.value === undefined || isNaN(Number(d.value)))) {
    if (window.MotionRecipes && window.MotionRecipes.renderTextFocus) {
      return window.MotionRecipes.renderTextFocus(ctx, svg, d, t, duration, 0);
    }
  }
  const targetTemp = Number(d.temperature ?? d.value ?? 0);
  const maxTemp = Number(d.max_temp ?? 100);
  const unit = d.unit || '°C';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Thân nhiệt kế xuất hiện
  // Action [0.6 - 2.2s]: Cột thủy ngân dâng cao qua các vạch chia
  // Impact [2.2 - 4.0s]: Chạm đỉnh sôi, tỏa sóng nhiệt, sủi bọt

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 340,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  // Card Container
  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Thermometer Stem & Bulb Layout
  const stemX = cardX + 180;
  const stemW = 44;
  const stemTopY = cardY + 120;
  const stemH = 420;
  const bulbRadius = 56;
  const bulbY = stemTopY + stemH + bulbRadius / 2;

  // Thermometer glass outline (Stem + Bulb)
  shape(root, 'rect', {
    x: stemX - stemW / 2, y: stemTopY, width: stemW, height: stemH, rx: stemW / 2,
    fill: '#1e293b', stroke: '#64748b', 'stroke-width': 4
  });
  shape(root, 'circle', {
    cx: stemX, cy: bulbY, r: bulbRadius,
    fill: '#1e293b', stroke: '#64748b', 'stroke-width': 4
  });

  // Action rising progress [0.6s - 2.2s]
  const actionP = clamp((t - 0.6) / 1.6);
  const currentRatio = (targetTemp / maxTemp) * easeOutCubic(actionP);
  const mercuryH = stemH * currentRatio;

  // Liquid mercury column (Red-hot gradient)
  const mercuryY = (stemTopY + stemH) - mercuryH;
  shape(root, 'rect', {
    x: stemX - stemW / 2 + 5, y: mercuryY, width: stemW - 10, height: mercuryH + bulbRadius, rx: (stemW - 10) / 2,
    fill: '#ef4444', filter: 'url(#neon-glow)'
  });
  // Bulb filled
  shape(root, 'circle', {
    cx: stemX, cy: bulbY, r: bulbRadius - 6,
    fill: '#ef4444', filter: 'url(#neon-glow)'
  });

  // Measurement Ticks along the stem
  const numTicks = 6;
  for (let i = 0; i <= numTicks; i++) {
    const tickY = (stemTopY + stemH) - (stemH * (i / numTicks));
    const isMajor = i % 2 === 0;
    shape(root, 'line', {
      x1: stemX + stemW / 2 + 10, y1: tickY,
      x2: stemX + stemW / 2 + (isMajor ? 32 : 18), y2: tickY,
      stroke: '#94a3b8', 'stroke-width': isMajor ? 3 : 2
    });
    if (isMajor) {
      const valAtTick = Math.round((maxTemp / numTicks) * i);
      root.append(el('text', {
        x: stemX + stemW / 2 + 45, y: tickY + 8,
        'font-size': '36', fill: '#94a3b8'
      }, `${valAtTick}°`));
    }
  }

  // Right Side Large Readout
  const readoutX = cardX + 540;
  const currentValDisplay = Math.round(targetTemp * (actionP <= 0 ? 0 : easeOutCubic(actionP)));

  root.append(el('text', {
    x: readoutX, y: cy + 30, 'text-anchor': 'middle',
    'font-size': '130', 'font-weight': '900',
    fill: '#ef4444', filter: 'url(#neon-glow)', class: 'ill-label'
  }, `${currentValDisplay}${unit}`));

  root.append(el('text', {
    x: readoutX, y: cy + 120, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: '#e2e8f0', class: 'ill-label'
  }, targetTemp >= 80 ? 'ĐẠT NGƯỠNG SÔI' : 'TĂNG TRƯỞNG NHIỆT'));

  // Boiling Heatwaves and Bubbles [2.2s - 4.0s]
  if (t >= 2.2) {
    const heatP = t - 2.2;
    // Emitting curved heat ripples above bulb and top
    for (let rIdx = 0; rIdx < 3; rIdx++) {
      const wavePhase = (heatP * 3 + rIdx * 0.8) % 3;
      const waveAlpha = Math.max(0, 1 - wavePhase / 3);
      shape(root, 'circle', {
        cx: stemX, cy: mercuryY, r: 25 + wavePhase * 35,
        fill: 'none', stroke: '#f97316', 'stroke-width': 2.5,
        opacity: waveAlpha * 0.7
      });
    }

    // Little boiling bubbles rising in bulb
    for (let bIdx = 0; bIdx < 4; bIdx++) {
      const bY = bulbY + 20 - ((heatP * 40 + bIdx * 25) % 60);
      const bX = stemX - 15 + (bIdx * 12);
      shape(root, 'circle', {
        cx: bX, cy: bY, r: 5,
        fill: '#fef08a', opacity: 0.8
      });
    }
  }
}

// =========================================================================
// 7. BATTERY_FILL: Thỏi pin 3D sạc từng nấc + tia sét đánh, phát xung điện quang
// =========================================================================
function renderBatteryFill(ctx, svg, d, t, duration = 4) {
  if (!d._is_fixture && (d.percentage === undefined || d.percentage === null) && (d.value === null || d.value === undefined || isNaN(Number(d.value)))) {
    if (window.MotionRecipes && window.MotionRecipes.renderTextFocus) {
      return window.MotionRecipes.renderTextFocus(ctx, svg, d, t, duration, 0);
    }
  }
  const targetPct = Number(d.percentage ?? d.value ?? 0);
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Thỏi pin rỗng xuất hiện
  // Action [0.6 - 2.3s]: Tia sét đánh vào cực dương, nạp từng nấc 25%, 50%, 75%, 100%
  // Impact [2.3 - 4.0s]: Pin đầy 100%, phát xung điện quang toàn thân pin

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2.5)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  // Outer Card
  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Card Header Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Horizontal Battery Specs
  const batW = 560;
  const batH = 220;
  const batX = cx - batW / 2 - 20;
  const batY = cy - batH / 2 + 10;
  const terminalW = 30;
  const terminalH = 90;

  // Battery Main Glass Body
  shape(root, 'rect', {
    x: batX, y: batY, width: batW, height: batH, rx: 28,
    fill: '#020617', stroke: '#64748b', 'stroke-width': 6
  });

  // Positive Terminal Tip on the right
  shape(root, 'rect', {
    x: batX + batW + 4, y: batY + (batH - terminalH) / 2, width: terminalW, height: terminalH, rx: 10,
    fill: '#94a3b8', stroke: '#475569', 'stroke-width': 4
  });

  // 4 Power Cell Segments (25% each)
  const numCells = 4;
  const pad = 16;
  const cellW = (batW - pad * (numCells + 1)) / numCells;
  const cellH = batH - pad * 2;

  // Charge progression [0.6s - 2.3s]
  const fillTime = 1.7; // seconds
  const currentRatio = clamp((t - 0.6) / fillTime);
  const activeCells = t < 0.6 ? 0 : Math.min(numCells, Math.ceil(currentRatio * numCells * (targetPct / 100)));

  for (let c = 0; c < numCells; c++) {
    const cX = batX + pad + c * (cellW + pad);
    const isCharged = c < activeCells;

    if (isCharged) {
      // Charged Cell with flash highlight
      const cellColor = targetPct >= 75 ? '#10b981' : (targetPct >= 40 ? '#f59e0b' : '#ef4444');
      shape(root, 'rect', {
        x: cX, y: batY + pad, width: cellW, height: cellH, rx: 14,
        fill: cellColor, filter: 'url(#neon-glow)'
      });
      // Gloss specular bar
      shape(root, 'rect', {
        x: cX + 8, y: batY + pad + 10, width: cellW - 16, height: 18, rx: 8,
        fill: '#ffffff', opacity: 0.35
      });
    } else {
      // Empty uncharged cell slot
      shape(root, 'rect', {
        x: cX, y: batY + pad, width: cellW, height: cellH, rx: 14,
        fill: '#1e293b', opacity: 0.5
      });
    }
  }

  // Center Lightning Bolt Symbol
  const gBolt = group(root, {
    transform: `translate(${cx - 20}, ${cy + 10})`
  });
  const boltPath = el('polygon', {
    points: '-15,-60 25,-60 5,-5 30,-5 -25,65 -5,10 -30,10',
    fill: '#fde047', stroke: '#ca8a04', 'stroke-width': 2,
    filter: 'url(#neon-glow)', opacity: t >= 0.6 ? 1 : 0.4
  });
  gBolt.append(boltPath);

  // Digital readout underneath
  const currentDisplayedPct = Math.round((t < 0.6 ? 0 : currentRatio) * targetPct);
  root.append(el('text', {
    x: cx, y: batY + batH + 85, 'text-anchor': 'middle',
    'font-size': '70', 'font-weight': '900',
    fill: '#38bdf8', class: 'ill-label'
  }, `${currentDisplayedPct}%`));

  // Impact Flash Waves [2.3s - 4.0s]
  if (t >= 2.3 && targetPct >= 90) {
    const shockP = t - 2.3;
    const shockWave = Math.sin(shockP * 8) * 10;
    shape(root, 'rect', {
      x: batX - 15 - shockWave / 2, y: batY - 15 - shockWave / 2,
      width: batW + 30 + shockWave, height: batH + 30 + shockWave, rx: 36,
      fill: 'none', stroke: '#34d399', 'stroke-width': 3,
      opacity: 0.4 * Math.max(0, 1 - shockP * 0.35)
    });
  }
}

// =========================================================================
// 8. GLASS_FILL: Ly nước rót đầy có dòng nước rót, phao nổi, bọt lăn tăn
// =========================================================================
function renderGlassFill(ctx, svg, d, t, duration = 4) {
  if (!d._is_fixture && (d.fill_percentage === undefined || d.fill_percentage === null) && (d.value === null || d.value === undefined || isNaN(Number(d.value)))) {
    if (window.MotionRecipes && window.MotionRecipes.renderTextFocus) {
      return window.MotionRecipes.renderTextFocus(ctx, svg, d, t, duration, 0);
    }
  }
  const fillPct = Number(d.fill_percentage ?? d.value ?? 0);
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Ly nước thủy tinh xuất hiện
  // Action [0.6 - 2.4s]: Dòng nước rót từ trên xuống, mực nước dâng cao
  // Impact [2.4 - 4.0s]: Ngắt dòng rót, phao nổi dập dềnh trên mặt nước, bọt khí nổi

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 790;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  // Base Card Frame
  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Header Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Glass Cup Geometry
  const topW = 340;
  const botW = 240;
  const cupH = 400;
  const topY = cardY + 140;
  const botY = topY + cupH;

  const topLeftX = cx - topW / 2;
  const topRightX = cx + topW / 2;
  const botLeftX = cx - botW / 2;
  const botRightX = cx + botW / 2;

  // Action filling progress [0.6s - 2.4s]
  const actionP = clamp((t - 0.6) / 1.8);
  const curFillFraction = (fillPct / 100) * easeInOutCubic(actionP);
  const curWaterH = cupH * curFillFraction;
  const waterSurfaceY = botY - curWaterH;

  // Water width at current surface level (linear interpolation)
  const curWaterW = botW + (topW - botW) * curFillFraction;
  const waterLeftX = cx - curWaterW / 2;
  const waterRightX = cx + curWaterW / 2;

  // Clip Path for Glass Interior
  const defs = el('defs');
  root.append(defs);

  const clipId = `glass-clip-${Math.floor(t * 100)}`;
  const clip = el('clipPath', { id: clipId });
  const glassInteriorPath = el('polygon', {
    points: `${topLeftX + 6},${topY} ${topRightX - 6},${topY} ${botRightX - 6},${botY - 8} ${botLeftX + 6},${botY - 8}`
  });
  clip.append(glassInteriorPath);
  defs.append(clip);

  // Group inside glass
  const gInside = group(root, { 'clip-path': `url(#${clipId})` });

  // 1. Water Body Polygon
  if (curWaterH > 4) {
    const waveSin = t >= 2.4 ? Math.sin((t - 2.4) * 5) * 6 : 0;
    const waterPoly = el('polygon', {
      points: `${waterLeftX},${waterSurfaceY + waveSin} ${waterRightX},${waterSurfaceY - waveSin} ${botRightX},${botY} ${botLeftX},${botY}`,
      fill: 'url(#liquid-gradient)',
      filter: 'url(#neon-glow)'
    });
    gInside.append(waterPoly);

    // Water Surface Ellipse
    shape(gInside, 'ellipse', {
      cx, cy: waterSurfaceY, rx: curWaterW / 2, ry: 14,
      fill: '#a7f3d0', opacity: 0.8
    });
  }

  // 2. Pouring Water Stream [0.6s - 2.4s]
  if (t >= 0.6 && t < 2.4) {
    const streamW = 16;
    const streamX = cx;
    const streamTop = cardY + 80;
    shape(root, 'rect', {
      x: streamX - streamW / 2, y: streamTop, width: streamW, height: Math.max(0, waterSurfaceY - streamTop),
      fill: '#38bdf8', filter: 'url(#neon-glow)', opacity: 0.85
    });

    // Splashing droplets at water contact point
    for (let s = 0; s < 4; s++) {
      const dropAngle = (s * Math.PI) / 3;
      const dropR = 12 + 8 * Math.sin(t * 15 + s);
      shape(root, 'circle', {
        cx: cx + Math.cos(dropAngle) * dropR,
        cy: waterSurfaceY - 6 + Math.sin(dropAngle) * 6,
        r: 3, fill: '#67e8f9'
      });
    }
  }

  // 3. Floating Buoy / Icon on water surface [2.4s - 4.0s]
  if (t >= 2.4 && curWaterH > 20) {
    const buoyElapsed = t - 2.4;
    const buoyBobY = Math.sin(buoyElapsed * 4) * 8;
    const buoyTilt = Math.sin(buoyElapsed * 4) * 10;

    const gBuoy = group(root, {
      transform: `translate(${cx}, ${waterSurfaceY + buoyBobY - 14}) rotate(${buoyTilt})`
    });

    // Life buoy ring shape
    shape(gBuoy, 'circle', { cx: 0, cy: 0, r: 24, fill: '#f43f5e', stroke: '#ffffff', 'stroke-width': 8 });
    shape(gBuoy, 'circle', { cx: 0, cy: 0, r: 10, fill: '#0f172a' });

    // Little bubbles rising from bottom
    for (let b = 0; b < 5; b++) {
      const bubbleY = botY - 20 - ((buoyElapsed * 50 + b * 45) % (curWaterH - 10));
      const bubbleX = cx - 40 + (b * 22);
      shape(gInside, 'circle', {
        cx: bubbleX, cy: bubbleY, r: 4,
        fill: '#ffffff', opacity: 0.6
      });
    }
  }

  // Glass Wall Outline (Drawn on top)
  shape(root, 'polygon', {
    points: `${topLeftX},${topY} ${topRightX},${topY} ${botRightX},${botY} ${botLeftX},${botY}`,
    fill: 'none', stroke: '#e2e8f0', 'stroke-width': 6, 'stroke-linejoin': 'round'
  });
  // Glass Lip Rim Ellipse
  shape(root, 'ellipse', {
    cx, cy: topY, rx: topW / 2, ry: 16,
    fill: 'none', stroke: '#e2e8f0', 'stroke-width': 4
  });
  // Glass Bottom Base Footing
  shape(root, 'rect', {
    x: botLeftX - 15, y: botY, width: botW + 30, height: 16, rx: 8,
    fill: '#334155', stroke: '#64748b', 'stroke-width': 3
  });

  // Numeric Readout Tag
  const displayVal = Math.round(curFillFraction * 100);
  root.append(el('text', {
    x: cx, y: botY + 65, 'text-anchor': 'middle',
    'font-size': '52', 'font-weight': '900',
    fill: '#38bdf8', class: 'ill-label'
  }, `${displayVal}%`));
}

// =========================================================================
// EXPORTS & GLOBAL REGISTRATION
// =========================================================================

// =========================================================================
// 9. BALANCE_SCALE: Cán cân công lý 3D nghiêng về bên nặng hơn / ưu việt hơn
// =========================================================================
function renderBalanceScale(ctx, svg, d, t, duration = 4) {
  const leftLabelRaw = d.left_label || (d.bars && d.bars[0]?.label) || (d.items && d.items[0]) || '';
  const rightLabelRaw = d.right_label || (d.bars && d.bars[1]?.label) || (d.items && d.items[1]) || '';
  const leftLabel = sanitizeSemanticLabel(leftLabelRaw, 6);
  const rightLabel = sanitizeSemanticLabel(rightLabelRaw, 6);
  const winner = d.winner || 'right'; // 'left' or 'right'
  const titleRaw = d.label || d.text || '';
  const title = sanitizeSemanticLabel(titleRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Cán cân xuất hiện ở trạng thái cân bằng
  // Action [0.6 - 2.3s]: Đặt vật nặng lên đĩa cân, cán cân nghiêng dứt khoát
  // Impact [2.3 - 4.0s]: Cán cân dao động tắt dần, bên thắng bừng sáng

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  // Housing Card Frame
  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, title));

  // Scale Center Pillar & Pivot
  const pivotX = cx;
  const pivotY = cardY + 220;
  const baseBottomY = cardY + 590;

  // Triangular Base Pedestal
  shape(root, 'polygon', {
    points: `${pivotX},${pivotY + 20} ${pivotX - 90},${baseBottomY} ${pivotX + 90},${baseBottomY}`,
    fill: '#1e293b', stroke: '#64748b', 'stroke-width': 4
  });
  // Central Vertical Mast
  shape(root, 'rect', {
    x: pivotX - 10, y: pivotY - 10, width: 20, height: baseBottomY - pivotY, rx: 8,
    fill: '#334155', stroke: '#475569', 'stroke-width': 2
  });

  // Calculate Beam Tilt Angle [0.6s - 2.3s]
  const maxTiltDeg = winner === 'left' ? -18 : 18;
  let tiltAngle = 0;

  if (t < 0.6) {
    tiltAngle = 0;
  } else if (t < 2.3) {
    const actP = clamp((t - 0.6) / 1.7);
    tiltAngle = maxTiltDeg * easeInOutCubic(actP);
  } else {
    // Damped harmonic oscillation around maxTiltDeg
    const impP = t - 2.3;
    const decay = Math.exp(-impP * 3);
    const wobble = Math.sin(impP * 8) * 3 * decay;
    tiltAngle = maxTiltDeg + wobble;
  }

  // Cross Beam (Arm length = 560px)
  const armLen = 270;
  const gBeam = group(root, {
    transform: `rotate(${tiltAngle}, ${pivotX}, ${pivotY})`
  });

  // The Beam Rod
  shape(gBeam, 'line', {
    x1: pivotX - armLen, y1: pivotY, x2: pivotX + armLen, y2: pivotY,
    stroke: '#cbd5e1', 'stroke-width': 10, 'stroke-linecap': 'round'
  });
  // Center Pivot Fulcrum Wheel
  shape(gBeam, 'circle', {
    cx: pivotX, cy: pivotY, r: 24,
    fill: '#0f172a', stroke: 'var(--accent, #00f5d4)', 'stroke-width': 5
  });

  // Hanging Pans at Left and Right ends
  // Left tip in beam local space is (pivotX - armLen, pivotY)
  // Calculate world coordinates after tiltAngle
  const rad = (tiltAngle * Math.PI) / 180.0;
  const leftTipX = pivotX - armLen * Math.cos(rad);
  const leftTipY = pivotY - armLen * Math.sin(rad);
  const rightTipX = pivotX + armLen * Math.cos(rad);
  const rightTipY = pivotY + armLen * Math.sin(rad);

  const chainH = 140;

  // --- Left Pan ---
  const gPanL = group(root, { transform: `translate(${leftTipX}, ${leftTipY})` });
  shape(gPanL, 'line', { x1: 0, y1: 0, x2: -65, y2: chainH, stroke: '#94a3b8', 'stroke-width': 2 });
  shape(gPanL, 'line', { x1: 0, y1: 0, x2: 65, y2: chainH, stroke: '#94a3b8', 'stroke-width': 2 });
  shape(gPanL, 'ellipse', { cx: 0, cy: chainH, rx: 80, ry: 18, fill: '#1e293b', stroke: '#64748b', 'stroke-width': 3 });

  // Weight block on left pan
  const isLeftWinner = winner === 'left';
  const leftWeightSize = isLeftWinner ? 75 : 45;
  shape(gPanL, 'rect', {
    x: -leftWeightSize / 2, y: chainH - leftWeightSize, width: leftWeightSize, height: leftWeightSize, rx: 8,
    fill: isLeftWinner ? 'var(--accent, #00f5d4)' : '#475569',
    filter: isLeftWinner ? 'url(#neon-glow)' : 'none'
  });
  gPanL.append(el('text', {
    x: 0, y: chainH + 46, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': 'bold',
    fill: isLeftWinner ? 'var(--accent, #00f5d4)' : '#94a3b8', class: 'ill-label'
  }, leftLabel));

  // --- Right Pan ---
  const gPanR = group(root, { transform: `translate(${rightTipX}, ${rightTipY})` });
  shape(gPanR, 'line', { x1: 0, y1: 0, x2: -65, y2: chainH, stroke: '#94a3b8', 'stroke-width': 2 });
  shape(gPanR, 'line', { x1: 0, y1: 0, x2: 65, y2: chainH, stroke: '#94a3b8', 'stroke-width': 2 });
  shape(gPanR, 'ellipse', { cx: 0, cy: chainH, rx: 80, ry: 18, fill: '#1e293b', stroke: '#64748b', 'stroke-width': 3 });

  // Weight block on right pan
  const isRightWinner = winner !== 'left';
  const rightWeightSize = isRightWinner ? 75 : 45;
  shape(gPanR, 'rect', {
    x: -rightWeightSize / 2, y: chainH - rightWeightSize, width: rightWeightSize, height: rightWeightSize, rx: 8,
    fill: isRightWinner ? 'var(--accent, #00f5d4)' : '#475569',
    filter: isRightWinner ? 'url(#neon-glow)' : 'none'
  });
  gPanR.append(el('text', {
    x: 0, y: chainH + 46, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': 'bold',
    fill: isRightWinner ? 'var(--accent, #00f5d4)' : '#94a3b8', class: 'ill-label'
  }, rightLabel));

  // Victory Badge on winning side [2.3s - 4.0s]
  if (t >= 2.3) {
    const starX = isRightWinner ? rightTipX : leftTipX;
    const starY = (isRightWinner ? rightTipY : leftTipY) + chainH - rightWeightSize - 35;
    const badgeScale = spring(clamp((t - 2.3) / 0.5), 6, 6);
    const gBadge = group(root, { transform: `translate(${starX}, ${starY}) scale(${badgeScale})` });
    shape(gBadge, 'circle', { cx: 0, cy: 0, r: 24, fill: '#fbbf24', filter: 'url(#neon-glow)' });
    shape(gBadge, 'polygon', {
      points: '0,-15 4,-4 16,-4 7,3 10,14 0,8 -10,14 -7,3 -16,-4 -4,-4',
      fill: '#ffffff'
    });
  }
}

// =========================================================================
// 10. TUG_OF_WAR: Trận kéo co giằng co thế trận, cờ lệch hẳn về phe thắng
// =========================================================================
function renderTugOfWar(ctx, svg, d, t, duration = 4) {
  const teamA = sanitizeSemanticLabel(d.team_a || (d.bars && d.bars[0]?.label) || '', 3);
  const teamB = sanitizeSemanticLabel(d.team_b || (d.bars && d.bars[1]?.label) || '', 3);
  const winner = d.winner || 'team_a';
  const titleRaw = d.label || d.text || '';
  const title = sanitizeSemanticLabel(titleRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Dây thừng và hai đội vào vị trí
  // Action [0.6 - 2.4s]: Giằng co qua lại, một bên bứt phá giật mạnh
  // Impact [2.4 - 4.0s]: Vượt qua vạch chiến thắng, cờ bừng sáng ăn mừng

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, title));

  // Tug line center and boundary lines
  const ropeY = cy + 20;
  const maxDisplacement = winner === 'team_a' ? -140 : 140;

  // Center mark line on floor
  shape(root, 'line', {
    x1: cx, y1: ropeY - 60, x2: cx, y2: ropeY + 60,
    stroke: '#475569', 'stroke-width': 3, 'stroke-dasharray': '6,6'
  });
  // Win limit markers
  shape(root, 'line', { x1: cx - 100, y1: ropeY - 40, x2: cx - 100, y2: ropeY + 40, stroke: '#ef4444', 'stroke-width': 2 });
  shape(root, 'line', { x1: cx + 100, y1: ropeY - 40, x2: cx + 100, y2: ropeY + 40, stroke: '#10b981', 'stroke-width': 2 });

  // Action displacement calculation
  let ropeOffset = 0;
  if (t < 0.6) {
    ropeOffset = 0;
  } else if (t < 2.4) {
    const actP = clamp((t - 0.6) / 1.8);
    // Dynamic back-and-forth oscillation while drifting towards winner
    const struggle = Math.sin((t - 0.6) * 12) * 25 * (1 - actP);
    const surge = maxDisplacement * easeInOutCubic(actP);
    ropeOffset = surge + struggle;
  } else {
    // Impact settled position
    ropeOffset = maxDisplacement;
  }

  // Draw The Twisted Rope
  const ropeLeft = cardX + 90;
  const ropeRight = cardX + cardW - 90;

  shape(root, 'line', {
    x1: ropeLeft, y1: ropeY, x2: ropeRight, y2: ropeY,
    stroke: '#d97706', 'stroke-width': 16, 'stroke-linecap': 'round'
  });
  // Rope spiral texture
  shape(root, 'line', {
    x1: ropeLeft, y1: ropeY, x2: ropeRight, y2: ropeY,
    stroke: '#fde68a', 'stroke-width': 6, 'stroke-dasharray': '18,12', 'stroke-linecap': 'round'
  });

  // Red Ribbon Flag at center of rope
  const flagX = cx + ropeOffset;
  const gFlag = group(root, { transform: `translate(${flagX}, ${ropeY})` });
  shape(gFlag, 'polygon', {
    points: '0,0 -20,40 0,32 20,40',
    fill: '#ef4444', filter: 'url(#neon-glow)'
  });
  shape(gFlag, 'circle', { cx: 0, cy: 0, r: 12, fill: '#ffffff', stroke: '#ef4444', 'stroke-width': 3 });

  // Team A Badge (Left)
  const isAWin = winner === 'team_a';
  const gTeamA = group(root, { transform: `translate(${cardX + 160}, ${ropeY - 110})` });
  shape(gTeamA, 'rect', {
    x: -120, y: -45, width: 240, height: 90, rx: 20,
    fill: isAWin && t >= 2.4 ? '#0284c7' : '#1e293b',
    stroke: '#38bdf8', 'stroke-width': isAWin && t >= 2.4 ? 4 : 2,
    filter: isAWin && t >= 2.4 ? 'url(#neon-glow)' : 'none'
  });
  gTeamA.append(el('text', {
    x: 0, y: 12, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': 'bold',
    fill: '#f8fafc', class: 'ill-label'
  }, teamA));

  // Team B Badge (Right)
  const isBWin = !isAWin;
  const gTeamB = group(root, { transform: `translate(${cardX + cardW - 160}, ${ropeY - 110})` });
  shape(gTeamB, 'rect', {
    x: -120, y: -45, width: 240, height: 90, rx: 20,
    fill: isBWin && t >= 2.4 ? '#059669' : '#1e293b',
    stroke: '#10b981', 'stroke-width': isBWin && t >= 2.4 ? 4 : 2,
    filter: isBWin && t >= 2.4 ? 'url(#neon-glow)' : 'none'
  });
  gTeamB.append(el('text', {
    x: 0, y: 12, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': 'bold',
    fill: '#f8fafc', class: 'ill-label'
  }, teamB));

  // Victory Banner on winner [2.4s - 4.0s]
  if (t >= 2.4) {
    const winX = isAWin ? cardX + 160 : cardX + cardW - 160;
    root.append(el('text', {
      x: winX, y: ropeY + 95, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': '900',
      fill: '#fbbf24', class: 'ill-label'
    }, 'CHIẾN THẮNG'));
  }
}

// =========================================================================
// 11. VS_FLIP_CARDS: Hai thẻ bài đối đầu lật 3D trước sau so sánh trực diện
// =========================================================================
function renderVsFlipCards(ctx, svg, d, t, duration = 4) {
  const cardA = d.card_a || (d.bars && d.bars[0] ? { title: d.bars[0].label, stat: d.bars[0].value !== undefined ? String(d.bars[0].value) : '' } : null);
  const cardB = d.card_b || (d.bars && d.bars[1] ? { title: d.bars[1].label, stat: d.bars[1].value !== undefined ? String(d.bars[1].value) : '' } : null);
  if (!d._is_fixture && (!cardA || !cardB || (!cardA.title && !cardA.stat) || (!cardB.title && !cardB.stat))) {
    if (window.MotionRecipes && window.MotionRecipes.renderTextFocus) {
      return window.MotionRecipes.renderTextFocus(ctx, svg, d, t, duration, 0);
    }
  }
  const safeCardA = cardA || { title: '', stat: '' };
  const safeCardB = cardB || { title: '', stat: '' };
  const titleA = sanitizeSemanticLabel(safeCardA.title || (d.bars && d.bars[0]?.label) || '', 4);
  const titleB = sanitizeSemanticLabel(safeCardB.title || (d.bars && d.bars[1]?.label) || '', 4);
  const statA = safeCardA.stat || (safeCardA.value !== undefined ? String(safeCardA.value) : '');
  const statB = safeCardB.stat || (safeCardB.value !== undefined ? String(safeCardB.value) : '');
  const winner = d.winner || (Number(statB) > Number(statA) ? 'card_b' : 'card_a');
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Thẻ bài 3D xuất hiện
  // Action [0.6 - 2.3s]: Lật thẻ 180° theo trục đứng hé lộ thông số
  // Impact [2.3 - 4.0s]: Thẻ thắng bung viền xanh neon, thẻ thua tối xám

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // 3D Flip progress [0.6s - 2.3s]
  const flipP = clamp((t - 0.6) / 1.7);
  // Rotation angle goes from 0 to 180 degrees
  const rotDeg = 180 * easeInOutCubic(flipP);
  // ScaleX mirrors cos(rotDeg)
  const scaleX = Math.cos((rotDeg * Math.PI) / 180.0);
  const isFront = scaleX < 0; // Front side revealed when rotated past 90 deg

  const cardItemW = 340;
  const cardItemH = 430;
  const leftCardCx = cardX + 220;
  const rightCardCx = cardX + cardW - 220;
  const cardItemY = cardY + 130;

  // --- Left Card ---
  const isAWin = winner === 'card_a';
  const gCardL = group(root, {
    transform: `translate(${leftCardCx}, ${cardItemY + cardItemH / 2}) scale(${scaleX}, 1) translate(${-leftCardCx}, ${-(cardItemY + cardItemH / 2)})`
  });

  shape(gCardL, 'rect', {
    x: leftCardCx - cardItemW / 2, y: cardItemY, width: cardItemW, height: cardItemH, rx: 24,
    fill: isFront ? (isAWin ? '#0f766e' : '#1e293b') : '#020617',
    stroke: isFront && isAWin ? '#2dd4bf' : '#475569', 'stroke-width': 4,
    class: 'glass-card'
  });

  if (isFront) {
    // Revealed Front
    gCardL.append(el('text', {
      x: leftCardCx, y: cardItemY + 80, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': 'bold',
      fill: '#94a3b8', class: 'ill-label'
    }, titleA));
    gCardL.append(el('text', {
      x: leftCardCx, y: cardItemY + 230, 'text-anchor': 'middle',
      'font-size': '80', 'font-weight': '900',
      fill: isAWin ? '#2dd4bf' : '#cbd5e1', class: 'ill-label'
    }, statA));
  } else {
    // Back Pattern
    shape(gCardL, 'circle', { cx: leftCardCx, cy: cardItemY + cardItemH / 2, r: 40, fill: '#334155' });
  }

  // --- Right Card ---
  const isBWin = !isAWin;
  const gCardR = group(root, {
    transform: `translate(${rightCardCx}, ${cardItemY + cardItemH / 2}) scale(${scaleX}, 1) translate(${-rightCardCx}, ${-(cardItemY + cardItemH / 2)})`
  });

  shape(gCardR, 'rect', {
    x: rightCardCx - cardItemW / 2, y: cardItemY, width: cardItemW, height: cardItemH, rx: 24,
    fill: isFront ? (isBWin ? '#0f766e' : '#1e293b') : '#020617',
    stroke: isFront && isBWin ? 'var(--accent, #00f5d4)' : '#475569', 'stroke-width': 4,
    class: 'glass-card'
  });

  if (isFront) {
    // Revealed Front
    gCardR.append(el('text', {
      x: rightCardCx, y: cardItemY + 80, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': 'bold',
      fill: '#f8fafc', class: 'ill-label'
    }, titleB));
    gCardR.append(el('text', {
      x: rightCardCx, y: cardItemY + 230, 'text-anchor': 'middle',
      'font-size': '80', 'font-weight': '900',
      fill: isBWin ? 'var(--accent, #00f5d4)' : '#cbd5e1',
      filter: isBWin ? 'url(#neon-glow)' : 'none', class: 'ill-label'
    }, statB));
  } else {
    // Back Pattern
    shape(gCardR, 'circle', { cx: rightCardCx, cy: cardItemY + cardItemH / 2, r: 40, fill: '#334155' });
  }

  // Center VS Badge
  const gVs = group(root, { transform: `translate(${cx}, ${cardItemY + cardItemH / 2})` });
  shape(gVs, 'circle', { cx: 0, cy: 0, r: 42, fill: '#ef4444', filter: 'url(#neon-glow)' });
  gVs.append(el('text', {
    x: 0, y: 13, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': '900',
    fill: '#ffffff', class: 'ill-label'
  }, 'VS'));
}

// =========================================================================
// 12. BEFORE_AFTER_WIPE: Thanh trượt wipe quét qua, lột xác trước và sau
// =========================================================================
function renderBeforeAfterWipe(ctx, svg, d, t, duration = 4) {
  const beforeLbl = sanitizeSemanticLabel(d.before_label || '', 6);
  const afterLbl = sanitizeSemanticLabel(d.after_label || '', 6);
  const metric = d.metric_change || (d.value ? String(d.value) : '');
  const titleRaw = d.label || d.text || '';
  const title = sanitizeSemanticLabel(titleRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Khung cảnh Before bao trùm
  // Action [0.6 - 2.4s]: Thanh trượt laser quét từ trái sang phải
  // Impact [2.4 - 4.0s]: Khung cảnh After hiện ra rực rỡ, chỉ số bừng sáng

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.05);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 280,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, title));

  const stageW = cardW - 80;
  const stageH = cardH - 140;
  const stageX = cardX + 40;
  const stageY = cardY + 100;

  // Action Wipe Sweep [0.6s - 2.4s]
  const wipeP = clamp((t - 0.6) / 1.8);
  const curWipeX = stageX + stageW * easeInOutCubic(wipeP);

  // Defs for clipping After stage
  const defs = el('defs');
  root.append(defs);

  const clipId = `wipe-clip-${Math.floor(t * 100)}`;
  const clip = el('clipPath', { id: clipId });
  clip.append(el('rect', { x: stageX, y: stageY, width: curWipeX - stageX, height: stageH, rx: 20 }));
  defs.append(clip);

  // 1. BEFORE LAYER (Background)
  const gBefore = group(root);
  shape(gBefore, 'rect', {
    x: stageX, y: stageY, width: stageW, height: stageH, rx: 20,
    fill: '#1e293b'
  });
  // Dim Before label
  gBefore.append(el('text', {
    x: stageX + stageW - 140, y: stageY + 70, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': 'bold',
    fill: '#64748b', class: 'ill-label'
  }, beforeLbl));
  gBefore.append(el('text', {
    x: stageX + stageW - 140, y: stageY + 190, 'text-anchor': 'middle',
    'font-size': '70', 'font-weight': '900',
    fill: '#475569', class: 'ill-label'
  }, 'CŨ'));

  // 2. AFTER LAYER (Revealed by clip-path)
  const gAfter = group(root, { 'clip-path': `url(#${clipId})` });
  shape(gAfter, 'rect', {
    x: stageX, y: stageY, width: stageW, height: stageH, rx: 20,
    fill: '#042f2e', stroke: 'var(--accent, #00f5d4)', 'stroke-width': 2
  });
  // Bright After label
  gAfter.append(el('text', {
    x: stageX + 160, y: stageY + 70, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': 'bold',
    fill: '#5eead4', class: 'ill-label'
  }, afterLbl));
  gAfter.append(el('text', {
    x: stageX + 160, y: stageY + 210, 'text-anchor': 'middle',
    'font-size': '90', 'font-weight': '900',
    fill: 'var(--accent, #00f5d4)', filter: 'url(#neon-glow)', class: 'ill-label'
  }, metric));

  // 3. WIPER VERTICAL LASER BAR
  shape(root, 'line', {
    x1: curWipeX, y1: stageY - 10, x2: curWipeX, y2: stageY + stageH + 10,
    stroke: '#38bdf8', 'stroke-width': 6, filter: 'url(#neon-glow)'
  });
  // Central slider handle
  shape(root, 'circle', {
    cx: curWipeX, cy: stageY + stageH / 2, r: 24,
    fill: '#0f172a', stroke: '#38bdf8', 'stroke-width': 4
  });
  shape(root, 'polygon', {
    points: `${curWipeX - 8},${stageY + stageH / 2} ${curWipeX - 2},${stageY + stageH / 2 - 8} ${curWipeX - 2},${stageY + stageH / 2 + 8}`,
    fill: '#38bdf8'
  });
  shape(root, 'polygon', {
    points: `${curWipeX + 8},${stageY + stageH / 2} ${curWipeX + 2},${stageY + stageH / 2 - 8} ${curWipeX + 2},${stageY + stageH / 2 + 8}`,
    fill: '#38bdf8'
  });
}

// =========================================================================
// 13. CONVEYOR_BELT: Băng chuyền chuyển động liên tục, robot kiểm tra đóng dấu
// =========================================================================
function renderConveyorBelt(ctx, svg, d, t, duration = 4) {
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);
  const outLabel = sanitizeSemanticLabel(d.output_label || '', 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Băng chuyền và cánh tay robot xuất hiện
  // Action [0.6 - 2.4s]: Kiện hàng trôi qua vị trí quét scanner
  // Impact [2.4 - 4.0s]: Đóng dấu PASS xanh ngọc, kiện hàng bừng sáng

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Conveyor Belt Assembly
  const beltY = cardY + 380;
  const beltW = cardW - 120;
  const beltH = 50;
  const beltX = cardX + 60;

  // Belt Bed
  shape(root, 'rect', {
    x: beltX, y: beltY, width: beltW, height: beltH, rx: 25,
    fill: '#1e293b', stroke: '#64748b', 'stroke-width': 4
  });

  // 6 Rotating Rollers
  const numRollers = 6;
  const rollerSpeed = t * 180;
  for (let r = 0; r < numRollers; r++) {
    const rx = beltX + 30 + r * ((beltW - 60) / (numRollers - 1));
    shape(root, 'circle', {
      cx: rx, cy: beltY + beltH / 2, r: 18,
      fill: '#0f172a', stroke: '#94a3b8', 'stroke-width': 3
    });
    // Roller cross spokes
    const gSpoke = group(root, {
      transform: `rotate(${rollerSpeed}, ${rx}, ${beltY + beltH / 2})`
    });
    shape(gSpoke, 'line', { x1: rx - 14, y1: beltY + beltH / 2, x2: rx + 14, y2: beltY + beltH / 2, stroke: '#64748b', 'stroke-width': 2 });
    shape(gSpoke, 'line', { x1: rx, y1: beltY + beltH / 2 - 14, x2: rx, y2: beltY + beltH / 2 + 14, stroke: '#64748b', 'stroke-width': 2 });
  }

  // Moving Package Calculation
  // Package moves from left (cardX + 100) to center (cx) during action, then exits right
  let pkgX = cardX + 140;
  if (t < 0.6) {
    pkgX = cardX + 140;
  } else if (t < 2.0) {
    const p1 = clamp((t - 0.6) / 1.4);
    pkgX = (cardX + 140) + (cx - (cardX + 140)) * easeOutCubic(p1);
  } else {
    const p2 = clamp((t - 2.4) / 1.6);
    pkgX = cx + (cardW / 2 - 100) * p2;
  }

  const pkgY = beltY - 95;
  const pkgW = 140;
  const pkgH = 95;

  // Package Box (3D Cube illusion)
  const gPkg = group(root, { transform: `translate(${pkgX - pkgW / 2}, ${pkgY})` });
  shape(gPkg, 'rect', {
    x: 0, y: 0, width: pkgW, height: pkgH, rx: 12,
    fill: '#b45309', stroke: '#f59e0b', 'stroke-width': 3
  });
  shape(gPkg, 'line', { x1: pkgW / 2, y1: 0, x2: pkgW / 2, y2: pkgH, stroke: '#d97706', 'stroke-width': 2 });
  shape(gPkg, 'line', { x1: 0, y1: pkgH / 2, x2: pkgW, y2: pkgH / 2, stroke: '#d97706', 'stroke-width': 2 });

  // Robot Scanner Overhead
  const scannerX = cx;
  const scannerY = cardY + 120;
  shape(root, 'rect', {
    x: scannerX - 70, y: scannerY, width: 140, height: 40, rx: 10,
    fill: '#334155', stroke: '#94a3b8', 'stroke-width': 3
  });

  // Scanner Laser Beam [1.2s - 2.2s]
  if (t >= 1.2 && t <= 2.2) {
    shape(root, 'polygon', {
      points: `${scannerX - 50},${scannerY + 40} ${scannerX + 50},${scannerY + 40} ${cx + 80},${beltY} ${cx - 80},${beltY}`,
      fill: 'var(--accent, #00f5d4)', opacity: 0.25
    });
    shape(root, 'line', {
      x1: cx - 75, y1: beltY - 5, x2: cx + 75, y2: beltY - 5,
      stroke: 'var(--accent, #00f5d4)', 'stroke-width': 4, filter: 'url(#neon-glow)'
    });
  }

  // Stamp PASS Stamp Impact [2.2s - 4.0s]
  if (t >= 2.2) {
    const stampP = clamp((t - 2.2) / 0.3);
    const stampScale = spring(stampP, 7, 6);
    const gStamp = group(gPkg, { transform: `translate(${pkgW / 2}, ${pkgH / 2}) scale(${stampScale})` });
    shape(gStamp, 'rect', {
      x: -45, y: -20, width: 90, height: 40, rx: 8,
      fill: '#10b981', filter: 'url(#neon-glow)'
    });
    gStamp.append(el('text', {
      x: 0, y: 8, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': '900',
      fill: '#ffffff', class: 'ill-label'
    }, 'PASS'));
  }

  // Finished output label below
  root.append(el('text', {
    x: cx, y: beltY + beltH + 60, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': 'bold',
    fill: '#38bdf8', class: 'ill-label'
  }, outLabel));
}

// =========================================================================
// 14. DOMINO_CHAIN: Chuỗi cờ domino đổ liên hoàn từ quân kích hoạt tới đích
// =========================================================================
function renderDominoChain(ctx, svg, d, t, duration = 4) {
  const steps = d.steps || d.items || [];
  const finalImpact = sanitizeSemanticLabel(d.final_impact || '', 6);
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: 4-5 quân cờ domino đứng thẳng
  // Action [0.6 - 2.3s]: Lực đẩy kích hoạt, domino đổ rạp tuần tự
  // Impact [2.3 - 4.0s]: Quân cuối va đập bật mở kết quả khổng lồ

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // 4 Domino Tiles
  const numTiles = 4;
  const floorY = cardY + 450;
  const tileW = 24;
  const tileH = 180;
  const startX = cardX + 160;
  const tileGap = 160;

  shape(root, 'line', {
    x1: cardX + 80, y1: floorY, x2: cardX + cardW - 80, y2: floorY,
    stroke: '#475569', 'stroke-width': 4, 'stroke-linecap': 'round'
  });

  steps.slice(0, 4).forEach((stepText, idx) => {
    const tileBaseX = startX + idx * tileGap;
    const triggerTime = 0.6 + idx * 0.4;
    const isTriggered = t >= triggerTime;

    let fallDeg = 0;
    if (isTriggered) {
      const fallP = clamp((t - triggerTime) / 0.35);
      fallDeg = 68 * easeInQuad(fallP);
    }

    const gTile = group(root, {
      transform: `translate(${tileBaseX}, ${floorY}) rotate(${fallDeg}) translate(${-tileBaseX}, ${-floorY})`
    });

    // Domino Slab
    const isFinal = idx === numTiles - 1;
    shape(gTile, 'rect', {
      x: tileBaseX - tileW / 2, y: floorY - tileH, width: tileW, height: tileH, rx: 6,
      fill: isFinal ? '#38bdf8' : '#e2e8f0', stroke: '#0f172a', 'stroke-width': 2
    });

    // Step label above tile
    root.append(el('text', {
      x: tileBaseX, y: floorY + 45, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': 'bold',
      fill: isTriggered ? 'var(--accent, #00f5d4)' : '#94a3b8', class: 'ill-label'
    }, sanitizeSemanticLabel(stepText, 6)));
  });

  function easeInQuad(x) { return x * x; }

  // Final Target Goal / Impact [2.3s - 4.0s]
  if (t >= 2.3) {
    const targetP = clamp((t - 2.3) / 0.5);
    const targetScale = spring(targetP, 7, 6);
    const targetX = startX + (numTiles - 1) * tileGap + 120;
    const targetY = floorY - 90;

    const gGoal = group(root, {
      transform: `translate(${targetX}, ${targetY}) scale(${targetScale})`
    });

    shape(gGoal, 'circle', { cx: 0, cy: 0, r: 60, fill: '#10b981', filter: 'url(#neon-glow)' });
    gGoal.append(el('text', {
      x: 0, y: 12, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': '900',
      fill: '#ffffff', class: 'ill-label'
    }, finalImpact));
  }
}

// =========================================================================
// 15. FUNNEL_FILTER: Chiếc phễu lọc đa tầng sàng lọc nhiều yếu tố thành tinh hoa
// =========================================================================
function renderFunnelFilter(ctx, svg, d, t, duration = 4) {
  const inCount = Number(d.input_count ?? (d.bars && d.bars[0]?.value) ?? 0);
  const outCount = Number(d.output_count ?? (d.bars && d.bars[1]?.value) ?? 0);
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Phễu thủy tinh đa tầng xuất hiện
  // Action [0.6 - 2.4s]: Hạt rơi vào phễu lọc qua các màng lưới
  // Impact [2.4 - 4.0s]: Giọt tinh hoa vàng rơi xuống đáy bừng sáng

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Funnel Geometry (3 tiers)
  const topY = cardY + 130;
  const midY = cardY + 280;
  const neckY = cardY + 440;
  const botY = cardY + 540;

  const topHalfW = 280;
  const midHalfW = 160;
  const neckHalfW = 50;

  // Funnel Glass Shell
  shape(root, 'polygon', {
    points: `${cx - topHalfW},${topY} ${cx + topHalfW},${topY} ${cx + midHalfW},${midY} ${cx + neckHalfW},${neckY} ${cx + neckHalfW},${botY} ${cx - neckHalfW},${botY} ${cx - neckHalfW},${neckY} ${cx - midHalfW},${midY}`,
    fill: '#1e293b', stroke: '#64748b', 'stroke-width': 4
  });

  // Filter Grids
  shape(root, 'line', { x1: cx - midHalfW, y1: midY, x2: cx + midHalfW, y2: midY, stroke: '#38bdf8', 'stroke-width': 3, 'stroke-dasharray': '6,4' });
  shape(root, 'line', { x1: cx - neckHalfW, y1: neckY, x2: cx + neckHalfW, y2: neckY, stroke: 'var(--accent, #00f5d4)', 'stroke-width': 3, 'stroke-dasharray': '4,4' });

  // Falling particles animation [0.6s - 2.4s]
  const numParticles = 12;
  for (let i = 0; i < numParticles; i++) {
    const pPhase = ((t - 0.6) * 1.5 + i * 0.25) % 1.8;
    if (t >= 0.6 && pPhase > 0) {
      const normY = pPhase / 1.8;
      const curY = topY + normY * (neckY - topY);
      // Particle width narrows as Y goes down
      const maxWAtY = topHalfW - (topHalfW - neckHalfW) * normY;
      const curX = cx + Math.sin(i * 3 + t * 4) * (maxWAtY * 0.7);

      shape(root, 'circle', {
        cx: curX, cy: curY, r: 5,
        fill: normY > 0.6 ? '#fde047' : '#94a3b8'
      });
    }
  }

  // Top Input Count
  root.append(el('text', {
    x: cx, y: topY - 15, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': 'bold',
    fill: '#94a3b8', class: 'ill-label'
  }, `ĐẦU VÀO: ${inCount}`));

  // Bottom Golden Drop & Output Value [2.4s - 4.0s]
  if (t >= 2.4) {
    const dropP = clamp((t - 2.4) / 0.5);
    const dropScale = spring(dropP, 7, 6);
    const gDrop = group(root, { transform: `translate(${cx}, ${botY + 40}) scale(${dropScale})` });

    shape(gDrop, 'circle', { cx: 0, cy: 0, r: 35, fill: '#f59e0b', filter: 'url(#neon-glow)' });
    gDrop.append(el('text', {
      x: 0, y: 12, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': '900',
      fill: '#ffffff', class: 'ill-label'
    }, String(outCount)));
  }
}

// =========================================================================
// 16. PIPELINE_PIPES: Đường ống công nghiệp nối các van và luồng năng lượng
// =========================================================================
function renderPipelinePipes(ctx, svg, d, t, duration = 4) {
  const throughput = d.throughput || (d.value ? String(d.value) + (d.unit || '') : '');
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Mạng lưới ống và van xuất hiện
  // Action [0.6 - 2.3s]: Van mở, dòng xung năng lượng phóng qua các khớp
  // Impact [2.3 - 4.0s]: Toàn bộ ống sáng rực, đồng hồ báo mức tối đa

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Pipe Route (Zigzag through 4 nodes)
  const p0 = { x: cardX + 120, y: cardY + 220 };
  const p1 = { x: cardX + 420, y: cardY + 220 };
  const p2 = { x: cardX + 420, y: cardY + 420 };
  const p3 = { x: cardX + 740, y: cardY + 420 };

  const pipePathD = `M ${p0.x} ${p0.y} L ${p1.x} ${p1.y} L ${p2.x} ${p2.y} L ${p3.x} ${p3.y}`;

  // Outer Pipe Tube
  shape(root, 'path', {
    d: pipePathD, fill: 'none', stroke: '#1e293b', 'stroke-width': 42,
    'stroke-linecap': 'round', 'stroke-linejoin': 'round'
  });
  shape(root, 'path', {
    d: pipePathD, fill: 'none', stroke: '#334155', 'stroke-width': 34,
    'stroke-linecap': 'round', 'stroke-linejoin': 'round'
  });

  // Flow pulse animation [0.6s - 4.0s]
  if (t >= 0.6) {
    const flowP = clamp((t - 0.6) / 1.7);
    const flowLen = flowP * 900;
    shape(root, 'path', {
      d: pipePathD, fill: 'none', stroke: 'var(--accent, #00f5d4)', 'stroke-width': 18,
      'stroke-dasharray': `${flowLen}, 9999`, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      filter: 'url(#neon-glow)'
    });
  }

  // 3 Valve Joint Nodes
  [p1, p2].forEach((p, idx) => {
    shape(root, 'circle', {
      cx: p.x, cy: p.y, r: 28,
      fill: '#0f172a', stroke: '#94a3b8', 'stroke-width': 4
    });
    // Rotating valve handle
    const valveRot = t >= 0.6 ? 90 : 0;
    const gValve = group(root, { transform: `rotate(${valveRot}, ${p.x}, ${p.y})` });
    shape(gValve, 'line', { x1: p.x - 20, y1: p.y, x2: p.x + 20, y2: p.y, stroke: '#e2e8f0', 'stroke-width': 4 });
  });

  // End Pressure Gauge at p3
  shape(root, 'circle', {
    cx: p3.x, cy: p3.y, r: 48,
    fill: '#020617', stroke: t >= 2.3 ? '#10b981' : '#64748b', 'stroke-width': 5
  });
  if (d.value !== undefined && d.value !== null) {
    root.append(el('text', {
      x: p3.x, y: p3.y + 12, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': '900',
      fill: t >= 2.3 ? '#10b981' : '#94a3b8', class: 'ill-label'
    }, String(d.value)));
  }

  // Throughput Banner
  root.append(el('text', {
    x: cx, y: cardY + cardH - 50, 'text-anchor': 'middle',
    'font-size': '44', 'font-weight': '900',
    fill: '#38bdf8', class: 'ill-label'
  }, throughput));
}

// =========================================================================
// 17. DICE_ROLL: Viên xúc xắc 3D lăn trong không gian rồi chốt mặt may mắn
// =========================================================================
function renderDiceRoll(ctx, svg, d, t, duration = 4) {
  const resultNum = Number(d.result_number ?? (d.value ?? 0));
  const prob = d.probability || '';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.5s]: Xúc xắc 3D rơi xoay từ trên cao
  // Action [0.5 - 2.2s]: Chạm bàn nảy tưng bừng, đổi mặt liên tục
  // Impact [2.2 - 4.0s]: Chốt cứng mặt thắng, tỏa hào quang vàng chói

  const enterP = clamp(t / 0.5);
  const enterScale = overshoot(enterP, 1.2);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.3)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Dice Animation Physics [0.5s - 2.2s]
  let diceRot = 0;
  let diceBounceY = 0;
  let curDotNumber = resultNum;

  if (t < 0.5) {
    diceRot = t * 720;
    diceBounceY = -120 * (1 - t / 0.5);
  } else if (t < 2.2) {
    const actP = clamp((t - 0.5) / 1.7);
    diceRot = (t - 0.5) * 540;
    diceBounceY = Math.abs(Math.sin(actP * Math.PI * 4)) * -60 * (1 - actP);
    curDotNumber = (Math.floor(t * 10) % 6) + 1;
  } else {
    // Settled
    diceRot = 0;
    diceBounceY = 0;
    curDotNumber = resultNum;
  }

  // Draw 3D Isometric Die Box
  const dieSize = 180;
  const gDie = group(root, {
    transform: `translate(${cx}, ${cy + diceBounceY}) rotate(${diceRot})`
  });

  // Front Face
  shape(gDie, 'rect', {
    x: -dieSize / 2, y: -dieSize / 2, width: dieSize, height: dieSize, rx: 28,
    fill: t >= 2.2 ? '#fef08a' : '#f1f5f9', stroke: '#020617', 'stroke-width': 6,
    filter: t >= 2.2 ? 'url(#neon-glow)' : 'none'
  });

  // Dots for numbers 1 to 6
  const dotR = 14;
  const dotColor = '#0f172a';
  const drawDot = (dx, dy) => shape(gDie, 'circle', { cx: dx, cy: dy, r: dotR, fill: dotColor });

  const dOffset = 45;
  if (curDotNumber === 1) {
    drawDot(0, 0);
  } else if (curDotNumber === 2) {
    drawDot(-dOffset, -dOffset); drawDot(dOffset, dOffset);
  } else if (curDotNumber === 3) {
    drawDot(-dOffset, -dOffset); drawDot(0, 0); drawDot(dOffset, dOffset);
  } else if (curDotNumber === 4) {
    drawDot(-dOffset, -dOffset); drawDot(dOffset, -dOffset);
    drawDot(-dOffset, dOffset); drawDot(dOffset, dOffset);
  } else if (curDotNumber === 5) {
    drawDot(-dOffset, -dOffset); drawDot(dOffset, -dOffset);
    drawDot(0, 0);
    drawDot(-dOffset, dOffset); drawDot(dOffset, dOffset);
  } else {
    // 6 dots
    drawDot(-dOffset, -dOffset); drawDot(-dOffset, 0); drawDot(-dOffset, dOffset);
    drawDot(dOffset, -dOffset); drawDot(dOffset, 0); drawDot(dOffset, dOffset);
  }

  // Probability readout tag
  root.append(el('text', {
    x: cx, y: cardY + cardH - 50, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: '#fbbf24', class: 'ill-label'
  }, `XÁC SUẤT: ${prob}`));
}

// =========================================================================
// 18. LOCK_UNLOCK: Ổ khóa cắm chìa, còng bật mở (spring snap), bừng sáng
// =========================================================================
function renderLockUnlock(ctx, svg, d, t, duration = 4) {
  const status = d.status || '';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Ổ khóa màu đỏ cam ngậm chặt xuất hiện
  // Action [0.6 - 2.1s]: Chìa khóa cắm vào xoay, còng khóa bật nảy lên (spring snap)
  // Impact [2.1 - 4.0s]: Khóa chuyển màu xanh ngọc neon, sóng an toàn lan tỏa

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.05);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 280,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  const isUnlocked = t >= 1.8;

  // Shackle (Còng khóa chữ U)
  // When unlocked, pops up 50px and rotates 25 deg
  let shackleLift = 0;
  let shackleRot = 0;
  if (t >= 1.6) {
    const snapP = clamp((t - 1.6) / 0.3);
    const snapBounce = spring(snapP, 8, 6);
    shackleLift = -55 * snapBounce;
    shackleRot = 24 * snapBounce;
  }

  const shackleX = cx;
  const shackleY = cy - 70;

  const gShackle = group(root, {
    transform: `translate(${shackleX - 60}, ${shackleY}) rotate(${shackleRot}) translate(${-(shackleX - 60)}, ${-shackleY}) translate(0, ${shackleLift})`
  });

  // U-shape thick stroke
  shape(gShackle, 'path', {
    d: `M ${cx - 70} ${cy - 30} L ${cx - 70} ${cy - 120} A 70 70 0 0 1 ${cx + 70} ${cy - 120} L ${cx + 70} ${cy - 30}`,
    fill: 'none', stroke: isUnlocked ? '#94a3b8' : '#e2e8f0', 'stroke-width': 26, 'stroke-linecap': 'round'
  });

  // Lock Main Solid Body
  const bodyW = 280;
  const bodyH = 220;
  const bodyColor = isUnlocked ? '#10b981' : '#e11d48';

  shape(root, 'rect', {
    x: cx - bodyW / 2, y: cy - 40, width: bodyW, height: bodyH, rx: 32,
    fill: bodyColor, filter: isUnlocked ? 'url(#neon-glow)' : 'none'
  });

  // Keyhole
  shape(root, 'circle', { cx, cy: cy + 50, r: 18, fill: '#020617' });
  shape(root, 'polygon', {
    points: `${cx - 8},${cy + 55} ${cx + 8},${cy + 55} ${cx + 14},${cy + 105} ${cx - 14},${cy + 105}`,
    fill: '#020617'
  });

  // Status readout below (use grounded status or label if available, no fabricated string)
  const statusTxt = status ? sanitizeSemanticLabel(status, 6) : '';
  if (statusTxt) {
    root.append(el('text', {
      x: cx, y: cy + bodyH / 2 + 100, 'text-anchor': 'middle',
      'font-size': '40', 'font-weight': '900',
      fill: isUnlocked ? '#34d399' : '#fb7185', class: 'ill-label'
    }, statusTxt));
  }
}

// =========================================================================
// 19. SHIELD_HIT: Khiên phòng thủ đỡ đòn tấn công, sóng xung kích phát sáng
// =========================================================================
function renderShieldHit(ctx, svg, d, t, duration = 4) {
  const defense = d.defense_score || (d.value ? String(d.value) + (d.unit || '%') : '');
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Tấm khiên lục giác xuất hiện bảo vệ trung tâm
  // Action [0.6 - 2.2s]: 3 tia sét đỏ đập vào khiên, khiên rung nảy haptic
  // Impact [2.2 - 4.0s]: Đòn đánh văng ra, khiên bừng sáng 100% phòng thủ

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Shield Geometry
  const shW = 260;
  const shH = 320;
  const shTop = cy - 140;

  // Shield Haptic impact shake [0.8s - 2.0s]
  let shakeX = 0;
  if (t >= 0.8 && t <= 2.0) {
    shakeX = Math.sin((t - 0.8) * 35) * 8;
  }

  const gShield = group(root, { transform: `translate(${shakeX}, 0)` });

  // Classical Crest Shield Outline
  const shieldPathD = `
    M ${cx} ${shTop}
    L ${cx + shW / 2} ${shTop + 50}
    L ${cx + shW / 2} ${shTop + 180}
    Q ${cx + shW / 2} ${shTop + 280} ${cx} ${shTop + shH}
    Q ${cx - shW / 2} ${shTop + 280} ${cx - shW / 2} ${shTop + 180}
    L ${cx - shW / 2} ${shTop + 50}
    Z
  `;

  shape(gShield, 'path', {
    d: shieldPathD,
    fill: '#022c22', stroke: 'var(--accent, #00f5d4)', 'stroke-width': 8,
    filter: 'url(#neon-glow)'
  });

  // Incoming Attack Sparks [0.8s - 2.0s]
  if (t >= 0.8 && t < 2.2) {
    const sparkPhase = ((t - 0.8) * 4) % 1;
    const sparkX = cx + shW / 2 + 100 * (1 - sparkPhase);
    const sparkY = shTop + 100;
    shape(root, 'line', {
      x1: sparkX, y1: sparkY, x2: sparkX + 40, y2: sparkY - 15,
      stroke: '#ef4444', 'stroke-width': 6, filter: 'url(#neon-glow)'
    });
    // Impact Flash at contact point
    shape(root, 'circle', {
      cx: cx + shW / 2, cy: shTop + 100, r: 18 * Math.sin(sparkPhase * Math.PI),
      fill: '#fde047', opacity: 0.9
    });
  }

  // Checkmark or Star in center of shield
  shape(gShield, 'polygon', {
    points: `${cx},${shTop + 110} ${cx + 12},${shTop + 145} ${cx + 48},${shTop + 145} ${cx + 19},${shTop + 168} ${cx + 30},${shTop + 205} ${cx},${shTop + 182} ${cx - 30},${shTop + 205} ${cx - 19},${shTop + 168} ${cx - 48},${shTop + 145} ${cx - 12},${shTop + 145}`,
    fill: '#ffffff'
  });

  // Defense Score
  root.append(el('text', {
    x: cx, y: shTop + shH + 65, 'text-anchor': 'middle',
    'font-size': '52', 'font-weight': '900',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, `BẢO VỆ: ${defense}`));
}

// =========================================================================
// 20. TRAFFIC_LIGHT: Trụ đèn tín hiệu chuyển đỏ -> vàng -> xanh bừng sáng
// =========================================================================
function renderTrafficLight(ctx, svg, d, t, duration = 4) {
  const actionText = d.action_text || '';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Trụ đèn tín hiệu xuất hiện với đèn đỏ sáng
  // Action [0.6 - 2.2s]: Đỏ tắt -> Vàng chớp -> Xanh bừng sáng rực rỡ
  // Impact [2.2 - 4.0s]: Đèn xanh chiếu chùm tia sáng, mũi tên lao vút

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Traffic Light Housing
  const houseW = 180;
  const houseH = 440;
  const houseX = cx - houseW / 2;
  const houseY = cardY + 120;

  shape(root, 'rect', {
    x: houseX, y: houseY, width: houseW, height: houseH, rx: 32,
    fill: '#020617', stroke: '#475569', 'stroke-width': 6
  });

  // Light Centers
  const redY = houseY + 80;
  const yellowY = houseY + 220;
  const greenY = houseY + 360;
  const bulbR = 50;

  // States:
  // t < 1.3s: Red lit
  // 1.3s <= t < 1.9s: Yellow lit
  // t >= 1.9s: Green lit
  const isRed = t < 1.3;
  const isYellow = t >= 1.3 && t < 1.9;
  const isGreen = t >= 1.9;

  // Red Bulb
  shape(root, 'circle', {
    cx, cy: redY, r: bulbR,
    fill: isRed ? '#ef4444' : '#450a0a',
    filter: isRed ? 'url(#neon-glow)' : 'none'
  });

  // Yellow Bulb
  shape(root, 'circle', {
    cx, cy: yellowY, r: bulbR,
    fill: isYellow ? '#f59e0b' : '#451a03',
    filter: isYellow ? 'url(#neon-glow)' : 'none'
  });

  // Green Bulb
  shape(root, 'circle', {
    cx, cy: greenY, r: bulbR,
    fill: isGreen ? '#10b981' : '#022c22',
    filter: isGreen ? 'url(#neon-glow)' : 'none'
  });

  // Beam and Action Text when Green [1.9s - 4.0s]
  if (isGreen) {
    // Green Forward Projection Beams
    shape(root, 'polygon', {
      points: `${cx},${greenY} ${cx + 320},${greenY - 60} ${cx + 320},${greenY + 60}`,
      fill: '#10b981', opacity: 0.2
    });

    root.append(el('text', {
      x: cx, y: houseY + houseH + 65, 'text-anchor': 'middle',
      'font-size': '44', 'font-weight': '900',
      fill: '#34d399', filter: 'url(#neon-glow)', class: 'ill-label'
    }, actionText));
  } else {
    root.append(el('text', {
      x: cx, y: houseY + houseH + 65, 'text-anchor': 'middle',
      'font-size': '38', 'font-weight': 'bold',
      fill: isRed ? '#f87171' : '#fbbf24', class: 'ill-label'
    }, isRed ? 'DỪNG LẠI / QUAN SÁT' : 'CHUẨN BỊ BỨT PHÁ'));
  }
}


// =========================================================================
// 21. ORBIT_SYSTEM: Hạt nhân trung tâm, 3 quỹ đạo elip vệ tinh quay & beacon
// =========================================================================
function renderOrbitSystem(ctx, svg, d, t, duration = 4) {
  const centerNode = sanitizeSemanticLabel(d.center_node || d.text || '', 6);
  const satellites = (d.satellites || d.items || []).map(s => sanitizeSemanticLabel(s, 6));
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Hạt nhân và 3 vòng quỹ đạo mở rộng
  // Action [0.6 - 2.4s]: Vệ tinh quay đều, truyền luồng tia kết nối về tâm
  // Impact [2.4 - 4.0s]: Beacon phát quang tỏa tròn, toàn hệ thống đồng bộ

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 340,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // 3 Tilted Elliptical Orbit Rings
  const orbits = [
    { rx: 290, ry: 130, rot: 25 },
    { rx: 270, ry: 120, rot: -35 },
    { rx: 310, ry: 145, rot: 75 }
  ];

  orbits.forEach((orb) => {
    shape(root, 'ellipse', {
      cx, cy, rx: orb.rx, ry: orb.ry,
      fill: 'none', stroke: '#334155', 'stroke-width': 2,
      transform: `rotate(${orb.rot}, ${cx}, ${cy})`,
      'stroke-dasharray': '8,6'
    });
  });

  // Central Core Node
  shape(root, 'circle', {
    cx, cy, r: 56,
    fill: '#020617', stroke: 'var(--accent, #00f5d4)', 'stroke-width': 6,
    filter: 'url(#neon-glow)'
  });
  root.append(el('text', {
    x: cx, y: cy + 10, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': '900',
    fill: '#ffffff', class: 'ill-label'
  }, centerNode));

  // Satellite positions along orbits
  satellites.slice(0, 3).forEach((satName, idx) => {
    const orb = orbits[idx % orbits.length];
    // Orbital rotation speed
    const orbSpeed = 0.8 + idx * 0.25;
    const theta = (t * orbSpeed + idx * (Math.PI * 2 / 3));

    // Cartesian coordinate before tilt
    const unrotX = orb.rx * Math.cos(theta);
    const unrotY = orb.ry * Math.sin(theta);

    // Apply orbit tilt rotation
    const rotRad = (orb.rot * Math.PI) / 180.0;
    const satX = cx + unrotX * Math.cos(rotRad) - unrotY * Math.sin(rotRad);
    const satY = cy + unrotX * Math.sin(rotRad) + unrotY * Math.cos(rotRad);

    // Connecting beam to center
    shape(root, 'line', {
      x1: cx, y1: cy, x2: satX, y2: satY,
      stroke: 'var(--accent, #00f5d4)', 'stroke-width': 1.5, opacity: 0.4
    });

    // Satellite body
    shape(root, 'circle', {
      cx: satX, cy: satY, r: 24,
      fill: '#1e293b', stroke: '#38bdf8', 'stroke-width': 3
    });
    // Satellite label tag
    root.append(el('text', {
      x: satX, y: satY - 32, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': 'bold',
      fill: '#f8fafc', class: 'ill-label'
    }, satName));
  });

  // Beacon Ring Pulse [2.4s - 4.0s]
  if (t >= 2.4) {
    const beaconP = (t - 2.4);
    const beaconR = 56 + (beaconP * 140) % 220;
    const beaconAlpha = Math.max(0, 1 - (beaconR - 56) / 220);
    shape(root, 'circle', {
      cx, cy, r: beaconR,
      fill: 'none', stroke: '#38bdf8', 'stroke-width': 3,
      opacity: beaconAlpha * 0.7
    });
  }
}

// =========================================================================
// 22. LAYERED_ONION: Vòng đồng tâm bóc tách từng tầng hé lộ hạt nhân cốt lõi
// =========================================================================
function renderLayeredOnion(ctx, svg, d, t, duration = 4) {
  const coreText = sanitizeSemanticLabel(d.core_text || d.text || '', 6);
  const layers = (d.layers || d.items || []).map(l => sanitizeSemanticLabel(l, 6));
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Khối cầu đồng tâm xuất hiện
  // Action [0.6 - 2.3s]: Vỏ ngoài mở tách ra, lớp giữa xoay lệch hé lộ tâm
  // Impact [2.3 - 4.0s]: Hạt nhân vàng trồi lên phát sáng rực rỡ

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Outer Shell Peeling Split [0.6s - 2.3s]
  let peelX = 0;
  if (t >= 0.6) {
    const peelP = clamp((t - 0.6) / 1.7);
    peelX = 90 * easeOutCubic(peelP);
  }

  // 1. Outer Layer (Left and Right Split halves)
  const gOuterL = group(root, { transform: `translate(${-peelX}, 0)` });
  shape(gOuterL, 'path', {
    d: `M ${cx} ${cy - 230} A 230 230 0 0 0 ${cx} ${cy + 230} Z`,
    fill: '#1e293b', stroke: '#475569', 'stroke-width': 3, opacity: Math.max(0.3, 1 - peelX / 120)
  });
  const gOuterR = group(root, { transform: `translate(${peelX}, 0)` });
  shape(gOuterR, 'path', {
    d: `M ${cx} ${cy - 230} A 230 230 0 0 1 ${cx} ${cy + 230} Z`,
    fill: '#1e293b', stroke: '#475569', 'stroke-width': 3, opacity: Math.max(0.3, 1 - peelX / 120)
  });

  // 2. Middle Layer Ring
  shape(root, 'circle', {
    cx, cy, r: 150,
    fill: '#0f2b3c', stroke: '#0284c7', 'stroke-width': 4,
    'stroke-dasharray': '16,10'
  });

  // 3. Glowing Golden Core [2.3s - 4.0s]
  let coreScale = 1.0;
  if (t >= 2.0) {
    const coreP = clamp((t - 2.0) / 0.5);
    coreScale = spring(coreP, 7, 6);
  }

  const gCore = group(root, { transform: `translate(${cx}, ${cy}) scale(${coreScale}) translate(${-cx}, ${-cy})` });
  shape(gCore, 'circle', {
    cx, cy, r: 85,
    fill: '#fbbf24', filter: 'url(#neon-glow)'
  });
  gCore.append(el('text', {
    x: cx, y: cy + 12, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': '900',
    fill: '#020617', class: 'ill-label'
  }, coreText));

  // Layer Annotation Labels
  root.append(el('text', {
    x: cx, y: cy + 285, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': 'bold',
    fill: '#38bdf8', class: 'ill-label'
  }, layers[0] || ''));
}

// =========================================================================
// 23. STACK_PILE: Tháp thẻ 3D xếp chồng lên nhau vững chãi, đỉnh phát quang
// =========================================================================
function renderStackPile(ctx, svg, d, t, duration = 4) {
  const layers = (d.layers || d.items || []).map(l => sanitizeSemanticLabel(l, 6));
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Tấm đế nền tầng 1 xuất hiện
  // Action [0.6 - 2.3s]: Các tầng tiếp theo lần lượt rơi xuống xếp chồng
  // Impact [2.3 - 4.0s]: Tầng đỉnh bung viền neon, toàn tháp hoàn thiện

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // 4 Stacked Slabs (bottom to top)
  const slabW = 600;
  const slabH = 75;
  const startBottomY = cardY + 540;
  const numSlabs = 4;

  layers.slice(0, 4).forEach((layerText, idx) => {
    // idx 0 is bottom, idx 3 is top
    const targetY = startBottomY - idx * 85;
    const dropTime = 0.5 + idx * 0.45;
    const isDropped = t >= dropTime;

    let slabY = targetY;
    if (!isDropped) {
      slabY = targetY - 300; // Waiting in air
    } else {
      const dropP = clamp((t - dropTime) / 0.35);
      slabY = (targetY - 300) + 300 * overshoot(dropP, 1.4);
    }

    const isTop = idx === numSlabs - 1;
    const gSlab = group(root, { transform: `translate(${cx}, ${slabY})` });

    shape(gSlab, 'rect', {
      x: -slabW / 2, y: 0, width: slabW, height: slabH, rx: 18,
      fill: isTop && t >= 2.3 ? '#0f766e' : '#1e293b',
      stroke: isTop && t >= 2.3 ? 'var(--accent, #00f5d4)' : '#475569',
      'stroke-width': isTop && t >= 2.3 ? 4 : 2,
      filter: isTop && t >= 2.3 ? 'url(#neon-glow)' : 'none'
    });

    gSlab.append(el('text', {
      x: 0, y: slabH / 2 + 12, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': 'bold',
      fill: isTop && t >= 2.3 ? '#ffffff' : '#cbd5e1', class: 'ill-label'
    }, layerText));
  });
}

// =========================================================================
// 24. PUZZLE_SNAP: Mảnh ghép jigsaw trượt vào khớp nối 'khấc' hoàn mỹ
// =========================================================================
function renderPuzzleSnap(ctx, svg, d, t, duration = 4) {
  const solutionText = sanitizeSemanticLabel(d.solution_text || d.text || '', 6);
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Bức tranh với ô khuyết xuất hiện
  // Action [0.6 - 2.1s]: Mảnh ghép chìa khóa trượt vào xoay khớp
  // Impact [2.1 - 4.0s]: Khớp nối đóng sập 'khấc' (spring snap), bừng sáng

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Puzzle Frame (2x2 grid, bottom-right piece is dynamic key)
  const pieceW = 240;
  const pieceH = 170;
  const pOriginX = cx - pieceW;
  const pOriginY = cy - pieceH;

  // Top-Left Piece
  shape(root, 'rect', { x: pOriginX, y: pOriginY, width: pieceW, height: pieceH, rx: 12, fill: '#1e293b', stroke: '#475569', 'stroke-width': 3 });
  // Top-Right Piece
  shape(root, 'rect', { x: pOriginX + pieceW, y: pOriginY, width: pieceW, height: pieceH, rx: 12, fill: '#1e293b', stroke: '#475569', 'stroke-width': 3 });
  // Bottom-Left Piece
  shape(root, 'rect', { x: pOriginX, y: pOriginY + pieceH, width: pieceW, height: pieceH, rx: 12, fill: '#1e293b', stroke: '#475569', 'stroke-width': 3 });

  // Missing Slot Target at Bottom-Right
  const targetX = pOriginX + pieceW;
  const targetY = pOriginY + pieceH;
  shape(root, 'rect', {
    x: targetX, y: targetY, width: pieceW, height: pieceH, rx: 12,
    fill: '#020617', stroke: '#334155', 'stroke-width': 2, 'stroke-dasharray': '8,6'
  });

  // Key Puzzle Piece sliding in [0.6s - 2.1s]
  let keyCurX = targetX + 160;
  let keyCurY = targetY + 140;
  let keyRot = 25;

  if (t < 0.6) {
    keyCurX = targetX + 160;
    keyCurY = targetY + 140;
    keyRot = 25;
  } else if (t < 2.1) {
    const snapP = clamp((t - 0.6) / 1.5);
    keyCurX = targetX + 160 * (1 - easeOutCubic(snapP));
    keyCurY = targetY + 140 * (1 - easeOutCubic(snapP));
    keyRot = 25 * (1 - easeOutCubic(snapP));
  } else {
    // Snapped
    keyCurX = targetX;
    keyCurY = targetY;
    keyRot = 0;
  }

  const isSnapped = t >= 2.1;
  const gKey = group(root, {
    transform: `translate(${keyCurX}, ${keyCurY}) rotate(${keyRot})`
  });

  shape(gKey, 'rect', {
    x: 0, y: 0, width: pieceW, height: pieceH, rx: 12,
    fill: isSnapped ? '#10b981' : '#f59e0b',
    stroke: isSnapped ? '#34d399' : '#fbbf24', 'stroke-width': 4,
    filter: isSnapped ? 'url(#neon-glow)' : 'none'
  });
  gKey.append(el('text', {
    x: pieceW / 2, y: pieceH / 2 + 10, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': '900',
    fill: '#ffffff', class: 'ill-label'
  }, isSnapped ? 'HOÀN HẢO' : 'CHÌA KHÓA'));

  // Bottom Solution Readout
  root.append(el('text', {
    x: cx, y: cardY + cardH - 50, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: '#38bdf8', class: 'ill-label'
  }, solutionText));
}

// =========================================================================
// 25. CHAT_THREAD: Khung ứng dụng tin nhắn gõ chữ real-time + reply bung nở
// =========================================================================
function renderChatThread(ctx, svg, d, t, duration = 4) {
  const userMsg = d.user_msg || (d.items && d.items[0]) || '';
  const botReply = d.bot_reply || (d.items && d.items[1]) || '';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Khung chat xuất hiện
  // Action [0.6 - 2.2s]: Ba chấm nhảy -> Bong bóng trả lời bung nở
  // Impact [2.2 - 4.0s]: Double checkmark xanh, con trỏ gõ phím nhấp nháy

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // 1. User Message (Right Side)
  const userBubbleW = 440;
  const userBubbleH = 95;
  const userX = cardX + cardW - userBubbleW - 60;
  const userY = cardY + 140;

  shape(root, 'rect', {
    x: userX, y: userY, width: userBubbleW, height: userBubbleH, rx: 20,
    fill: '#0284c7', stroke: '#38bdf8', 'stroke-width': 2
  });
  root.append(el('text', {
    x: userX + 30, y: userY + 58,
    'font-size': '36', 'font-weight': 'bold',
    fill: '#ffffff', class: 'ill-label'
  }, userMsg));

  // 2. Bot Message / Typing Indicator (Left Side)
  const botX = cardX + 60;
  const botY = cardY + 280;

  if (t >= 0.6 && t < 1.4) {
    // 3 Bouncing Typing Dots
    shape(root, 'rect', { x: botX, y: botY, width: 140, height: 70, rx: 20, fill: '#1e293b' });
    for (let dot = 0; dot < 3; dot++) {
      const dotBounce = Math.sin(t * 12 + dot * 1.5) * 8;
      shape(root, 'circle', {
        cx: botX + 40 + dot * 30, cy: botY + 35 + dotBounce, r: 6,
        fill: '#94a3b8'
      });
    }
  } else if (t >= 1.4) {
    // Revealed Bot Reply Bubble
    const botP = clamp((t - 1.4) / 0.4);
    const botScale = spring(botP, 7, 6);
    const botBubbleW = 520;
    const botBubbleH = 110;

    const gBot = group(root, {
      transform: `translate(${botX}, ${botY}) scale(${botScale})`
    });

    shape(gBot, 'rect', {
      x: 0, y: 0, width: botBubbleW, height: botBubbleH, rx: 24,
      fill: '#0f766e', stroke: 'var(--accent, #00f5d4)', 'stroke-width': 3,
      filter: 'url(#neon-glow)'
    });
    gBot.append(el('text', {
      x: 35, y: 68,
      'font-size': '36', 'font-weight': '900',
      fill: '#ffffff', class: 'ill-label'
    }, botReply));
  }

  // 3. Bottom Chat Input Bar with Blinking Cursor
  const inputY = cardY + cardH - 110;
  shape(root, 'rect', {
    x: cardX + 60, y: inputY, width: cardW - 120, height: 60, rx: 16,
    fill: '#020617', stroke: '#334155', 'stroke-width': 2
  });
  root.append(el('text', {
    x: cardX + 90, y: inputY + 40,
    'font-size': '36', fill: '#64748b', class: 'ill-label'
  }, 'Nhập phản hồi...'));

  // Blinking vertical cursor
  if (Math.floor(t * 3) % 2 === 0) {
    shape(root, 'line', {
      x1: cardX + 300, y1: inputY + 15, x2: cardX + 300, y2: inputY + 45,
      stroke: 'var(--accent, #00f5d4)', 'stroke-width': 3
    });
  }
}

// =========================================================================
// 26. MOCK_CARD_SWIPE: Thao tác quẹt thẻ sang phải chấp nhận (APPROVED)
// =========================================================================
function renderMockCardSwipe(ctx, svg, d, t, duration = 4) {
  const cardTitle = sanitizeSemanticLabel(d.card_title || d.text || '', 6);
  const decision = d.decision || '';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Thẻ bài trung tâm xuất hiện
  // Action [0.6 - 2.2s]: Thẻ nghiêng góc và bị quẹt lướt sang phải
  // Impact [2.2 - 4.0s]: Dấu mộc APPROVED đóng sập chéo, thẻ mới trồi lên

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Swipe Card Dimensions
  const swW = 440;
  const swH = 460;
  const swBaseX = cx - swW / 2;
  const swBaseY = cardY + 130;

  // Next Card Behind (Static wait)
  shape(root, 'rect', {
    x: swBaseX + 20, y: swBaseY + 20, width: swW - 40, height: swH - 40, rx: 28,
    fill: '#1e293b', stroke: '#475569', 'stroke-width': 2, opacity: 0.6
  });

  // Action Swipe Right Movement [0.6s - 2.2s]
  let swipeDx = 0;
  let swipeRot = 0;

  if (t >= 0.6) {
    const swP = clamp((t - 0.6) / 1.6);
    swipeDx = 380 * easeInQuad(swP);
    swipeRot = 22 * easeInQuad(swP);
  }

  function easeInQuad(x) { return x * x; }

  const gSwCard = group(root, {
    transform: `translate(${cx + swipeDx}, ${swBaseY + swH / 2}) rotate(${swipeRot}) translate(${-cx}, ${-(swBaseY + swH / 2)})`
  });

  // Swiping Card
  shape(gSwCard, 'rect', {
    x: swBaseX, y: swBaseY, width: swW, height: swH, rx: 28,
    fill: '#020617', stroke: '#38bdf8', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Card Content Image / Avatar Placeholder
  shape(gSwCard, 'circle', { cx, cy: swBaseY + 140, r: 65, fill: '#0f766e', stroke: 'var(--accent, #00f5d4)', 'stroke-width': 3 });
  gSwCard.append(el('text', {
    x: cx, y: swBaseY + 270, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': '900',
    fill: '#f8fafc', class: 'ill-label'
  }, cardTitle));

  // APPROVED Stamp [1.4s - 4.0s]
  if (t >= 1.4) {
    const stampP = clamp((t - 1.4) / 0.3);
    const stampScale = spring(stampP, 7, 6);
    const gStamp = group(gSwCard, {
      transform: `translate(${cx - 40}, ${swBaseY + 130}) rotate(-18) scale(${stampScale})`
    });

    shape(gStamp, 'rect', {
      x: -110, y: -35, width: 220, height: 70, rx: 12,
      fill: 'none', stroke: '#10b981', 'stroke-width': 6, filter: 'url(#neon-glow)'
    });
    gStamp.append(el('text', {
      x: 0, y: 13, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': '900',
      fill: '#10b981', filter: 'url(#neon-glow)', class: 'ill-label'
    }, decision));
  }
}

// =========================================================================
// 27. FORM_FILL_SUBMIT: Form biểu mẫu tự động điền + nút bấm nảy haptic
// =========================================================================
function renderFormFillSubmit(ctx, svg, d, t, duration = 4) {
  const fields = (d.fields || d.items || []).map(f => sanitizeSemanticLabel(f, 6));
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Cửa sổ form xuất hiện
  // Action [0.6 - 2.2s]: Các dòng chữ tự động điền, thanh tiến độ 100%
  // Impact [2.2 - 4.0s]: Nút SUBMIT bị bấm nảy xuống, bật huy hiệu SUCCESS

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // 3 Form Input Fields
  const fieldW = cardW - 140;
  const fieldH = 70;
  const startFldY = cardY + 120;
  const fldGap = 100;

  fields.slice(0, 3).forEach((fldName, idx) => {
    const fY = startFldY + idx * fldGap;
    const fillTime = 0.6 + idx * 0.45;
    const isFilled = t >= fillTime;

    shape(root, 'rect', {
      x: cardX + 70, y: fY, width: fieldW, height: fieldH, rx: 14,
      fill: '#020617', stroke: isFilled ? '#38bdf8' : '#334155', 'stroke-width': 2
    });

    // Label on top
    root.append(el('text', {
      x: cardX + 90, y: fY - 10,
      'font-size': '36', fill: '#94a3b8', class: 'ill-label'
    }, fldName));

    if (isFilled) {
      // Completed Checkmark
      shape(root, 'circle', { cx: cardX + fieldW + 30, cy: fY + fieldH / 2, r: 16, fill: '#10b981' });
      root.append(el('text', {
        x: cardX + 100, y: fY + 46,
        'font-size': '36', 'font-weight': 'bold',
        fill: '#f8fafc', class: 'ill-label'
      }, '✓ Đã hoàn tất'));
    }
  });

  // Submit Button Impact [2.2s - 4.0s]
  const btnY = cardY + cardH - 120;
  const btnW = 320;
  const btnH = 65;
  const isSubmitted = t >= 2.2;
  const btnBounce = isSubmitted ? Math.sin((t - 2.2) * 12) * 4 * Math.exp(-(t - 2.2) * 4) : 0;

  const gBtn = group(root, { transform: `translate(${cx}, ${btnY + btnBounce})` });
  shape(gBtn, 'rect', {
    x: -btnW / 2, y: 0, width: btnW, height: btnH, rx: 16,
    fill: isSubmitted ? '#10b981' : 'var(--accent, #00f5d4)',
    filter: isSubmitted ? 'url(#neon-glow)' : 'none'
  });
  gBtn.append(el('text', {
    x: 0, y: 44, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': '900',
    fill: '#020617', class: 'ill-label'
  }, isSubmitted ? '✓ ĐÃ XÁC NHẬN' : 'GỬI YÊU CẦU'));
}

// =========================================================================
// 28. TERMINAL_COMMAND_RUN: Cửa sổ dòng lệnh Terminal gõ lệnh + SUCCESS bừng sáng
// =========================================================================
function renderTerminalCommandRun(ctx, svg, d, t, duration = 4) {
  const cmd = d.command || (d.text ? String(d.text) : '');
  const outLog = d.output || '';
  const labelRaw = d.label || d.text || '';
  const label = sanitizeSemanticLabel(labelRaw, 6);

  // Stages:
  // Enter [0.0 - 0.6s]: Cửa sổ Terminal đen bóng xuất hiện
  // Action [0.6 - 2.2s]: Gõ lệnh $ sau dấu nhắc, thanh tiến độ 100%
  // Impact [2.2 - 4.0s]: Dòng log SUCCESS bừng sáng xanh neon

  const enterP = clamp(t / 0.6);
  const enterScale = overshoot(enterP, 1.15);

  const cx = 540;
  const cy = 780;

  // Background aura
  shape(svg, 'circle', {
    cx, cy, r: 330,
    fill: 'url(#neon-radial)',
    opacity: 0.15 + 0.1 * Math.sin(t * 2)
  });

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    opacity: clamp(t / 0.35)
  });

  const cardW = 880;
  const cardH = 680;
  const cardX = cx - cardW / 2;
  const cardY = cy - cardH / 2;

  shape(root, 'rect', {
    x: cardX, y: cardY, width: cardW, height: cardH, rx: 36,
    fill: '#0f172a', stroke: '#334155', 'stroke-width': 4,
    class: 'glass-card'
  });

  // Title
  root.append(el('text', {
    x: cx, y: cardY + 65, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold',
    fill: 'var(--accent, #00f5d4)', class: 'ill-label'
  }, label));

  // Terminal Window Frame
  const termW = cardW - 80;
  const termH = cardH - 140;
  const termX = cardX + 40;
  const termY = cardY + 100;

  shape(root, 'rect', {
    x: termX, y: termY, width: termW, height: termH, rx: 20,
    fill: '#020617', stroke: '#1e293b', 'stroke-width': 2
  });

  // Top Window Buttons
  shape(root, 'circle', { cx: termX + 30, cy: termY + 30, r: 8, fill: '#ef4444' });
  shape(root, 'circle', { cx: termX + 55, cy: termY + 30, r: 8, fill: '#f59e0b' });
  shape(root, 'circle', { cx: termX + 80, cy: termY + 30, r: 8, fill: '#10b981' });

  // Typed Command String Calculation [0.6s - 1.8s]
  let typedLen = 0;
  if (t >= 0.6) {
    const typeP = clamp((t - 0.6) / 1.2);
    typedLen = Math.floor(typeP * cmd.length);
  }
  const currentTypedCmd = cmd.substring(0, typedLen);

  root.append(el('text', {
    x: termX + 30, y: termY + 100,
    'font-size': '36', 'font-weight': 'bold',
    fill: '#38bdf8', font_family: 'monospace', class: 'ill-label'
  }, `$ ${currentTypedCmd}`));

  // Blinking block cursor
  if (t < 2.0 && Math.floor(t * 4) % 2 === 0) {
    const cursorX = termX + 75 + typedLen * 18;
    shape(root, 'rect', { x: cursorX, y: termY + 75, width: 14, height: 30, fill: 'var(--accent, #00f5d4)' });
  }

  // Progress Bar [1.4s - 2.2s]
  if (t >= 1.4) {
    const progP = clamp((t - 1.4) / 0.8);
    const progW = (termW - 60) * progP;
    shape(root, 'rect', { x: termX + 30, y: termY + 150, width: termW - 60, height: 16, rx: 8, fill: '#1e293b' });
    shape(root, 'rect', { x: termX + 30, y: termY + 150, width: progW, height: 16, rx: 8, fill: '#0284c7' });
  }

  // Success Output Log [2.2s - 4.0s]
  if (t >= 2.2) {
    const outP = clamp((t - 2.2) / 0.4);
    const gOut = group(root, { opacity: outP });
    shape(gOut, 'rect', {
      x: termX + 30, y: termY + 205, width: termW - 60, height: 80, rx: 14,
      fill: '#064e3b', stroke: '#10b981', 'stroke-width': 2, filter: 'url(#neon-glow)'
    });
    gOut.append(el('text', {
      x: termX + 60, y: termY + 255,
      'font-size': '36', 'font-weight': '900',
      fill: '#34d399', font_family: 'monospace', class: 'ill-label'
    }, outLog));
  }
}

// =============================================================================
// 12 RECIPES MỚI THEO YÊU CẦU A3
// =============================================================================

// 29. BEFORE_AFTER_SPLIT: So sánh trực quan Before / After với thanh trượt kép
function renderBeforeAfterSplit(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const enterScale = overshoot(enterP, 1.1);
  const cx = 540, cy = 780;
  const w = 940, h = 480;
  const x = cx - w / 2, y = cy - h / 2;

  const leftLbl = sanitizeSemanticLabel(d.left_label || d.label || '', 6);
  const rightLbl = sanitizeSemanticLabel(d.right_label || d.text || '', 6);

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${enterScale}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  // Nền phân tách 2 nửa
  shape(root, 'rect', { x, y, width: w / 2, height: h, rx: 24, fill: '#1e293b', stroke: '#334155', 'stroke-width': 3 });
  shape(root, 'rect', { x: cx, y, width: w / 2, height: h, rx: 24, fill: '#0f172a', stroke: '#334155', 'stroke-width': 3 });

  // Thanh ngăn cách trung tâm animated
  const splitP = clamp((t - 0.5) / 1.5);
  const barX = cx + Math.sin(splitP * Math.PI) * 40;
  shape(root, 'line', { x1: barX, y1: y + 20, x2: barX, y2: y + h - 20, stroke: 'var(--accent)', 'stroke-width': 6, 'stroke-linecap': 'round' });

  // Nhãn Before & After
  root.append(el('text', {
    x: x + w * 0.25, y: cy - 30, 'text-anchor': 'middle',
    'font-size': '44', 'font-weight': '900', fill: '#94a3b8', class: 'ill-label'
  }, leftLbl));

  root.append(el('text', {
    x: x + w * 0.75, y: cy - 30, 'text-anchor': 'middle',
    'font-size': '44', 'font-weight': '900', fill: 'var(--accent)', class: 'ill-label'
  }, rightLbl));

  // Badge trạng thái phía dưới
  if (d.number_text || d.value !== null && d.value !== undefined) {
    const numDisplay = String(d.number_text || d.value);
    root.append(el('text', {
      x: x + w * 0.75, y: cy + 60, 'text-anchor': 'middle',
      'font-size': '64', 'font-weight': '900', fill: '#38bdf8', class: 'ill-label'
    }, numDisplay));
  }
}

// 30. TIMELINE_MILESTONES: Trục thời gian mốc sự kiện phát sáng
function renderTimelineMilestones(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 780;
  const w = 940, h = 460;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.08)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  // Bảng nền
  shape(root, 'rect', { x, y, width: w, height: h, rx: 28, fill: '#0d1527ee', stroke: '#1e293b', 'stroke-width': 3 });

  // Trục ngang
  const lineY = cy + 20;
  shape(root, 'line', { x1: x + 80, y1: lineY, x2: x + w - 80, y2: lineY, stroke: '#334155', 'stroke-width': 6, 'stroke-linecap': 'round' });

  // Tia sáng chạy dọc trục
  const pulseP = clamp((t - 0.4) / (duration - 0.8));
  const lightX = x + 80 + (w - 160) * easeInOutCubic(pulseP);
  shape(root, 'line', { x1: x + 80, y1: lineY, x2: lightX, y2: lineY, stroke: 'var(--accent)', 'stroke-width': 6, 'stroke-linecap': 'round' });

  const items = (d.items && d.items.length) ? d.items.slice(0, 3) : [d.label, d.text].filter(Boolean);
  const stepX = (w - 200) / Math.max(1, items.length - 1);

  items.forEach((item, idx) => {
    const nodeX = x + 100 + idx * stepX;
    const nodeAt = 0.3 + idx * 0.4;
    const nodeP = clamp((t - nodeAt) / 0.3);
    const nodeScale = overshoot(nodeP, 1.25);

    // Vòng tròn node
    shape(root, 'circle', {
      cx: nodeX, cy: lineY, r: 18 * nodeScale,
      fill: (pulseP >= idx / (items.length - 1)) ? 'var(--accent)' : '#1e293b',
      stroke: 'var(--accent)', 'stroke-width': 4
    });

    // Nhãn mốc
    const lbl = sanitizeSemanticLabel(item, 6);
    root.append(el('text', {
      x: nodeX, y: (idx % 2 === 0) ? lineY - 45 : lineY + 65,
      'text-anchor': 'middle', 'font-size': '36', 'font-weight': '900',
      fill: (pulseP >= idx / (items.length - 1)) ? '#f4f7ff' : '#94a3b8',
      class: 'ill-label', opacity: nodeP
    }, lbl));
  });
}

// 31. MAP_LOCATION_PIN: Bản đồ radar định vị địa điểm & ghim tọa độ
function renderMapLocationPin(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 770;
  const w = 940, h = 500;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.1)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  shape(root, 'rect', { x, y, width: w, height: h, rx: 28, fill: '#0a101f', stroke: '#1e293b', 'stroke-width': 3 });

  // Lưới radar
  for (let r = 80; r <= 220; r += 70) {
    shape(root, 'circle', { cx, cy: cy - 20, r, fill: 'none', stroke: '#38bdf822', 'stroke-width': 2 });
  }
  shape(root, 'line', { x1: cx - 220, y1: cy - 20, x2: cx + 220, y2: cy - 20, stroke: '#38bdf822', 'stroke-width': 2 });
  shape(root, 'line', { x1: cx, y1: cy - 240, x2: cx, y2: cy + 200, stroke: '#38bdf822', 'stroke-width': 2 });

  // Sóng xung kích tỏa ra
  const waveP = (t * 1.5) % 1;
  shape(root, 'circle', {
    cx, cy: cy - 20, r: 40 + waveP * 180, fill: 'none',
    stroke: '#38bdf8', 'stroke-width': 3 * (1 - waveP), opacity: 1 - waveP
  });

  // Ghim vị trí (Drop pin)
  const pinDropP = clamp((t - 0.2) / 0.4);
  const pinY = (cy - 70) - (1 - overshoot(pinDropP, 1.3)) * 120;
  const pinGroup = group(root, { transform: `translate(${cx}, ${pinY})` });
  shape(pinGroup, 'circle', { cx: 0, cy: 0, r: 24, fill: '#f43f5e', stroke: '#fff', 'stroke-width': 4 });
  shape(pinGroup, 'circle', { cx: 0, cy: 0, r: 8, fill: '#fff' });

  // Nhãn địa danh
  const locationName = sanitizeSemanticLabel(d.label || d.text || '', 6);
  root.append(el('text', {
    x: cx, y: cy + 140, 'text-anchor': 'middle',
    'font-size': '44', 'font-weight': '900', fill: '#f4f7ff', class: 'ill-label'
  }, locationName));
}

// 32. PROFILE_DOSSIER: Thẻ hồ sơ đối tượng / nhân vật với avatar quét nhận diện
function renderProfileDossier(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 780;
  const w = 940, h = 500;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.08)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  shape(root, 'rect', { x, y, width: w, height: h, rx: 24, fill: '#0b1329', stroke: '#3b82f644', 'stroke-width': 3 });

  // Khung ảnh bên trái
  const imgBoxX = x + 60, imgBoxY = y + 70, imgBoxW = 260, imgBoxH = 340;
  shape(root, 'rect', { x: imgBoxX, y: imgBoxY, width: imgBoxW, height: imgBoxH, rx: 16, fill: '#1e293b', stroke: '#475569', 'stroke-width': 2 });
  // Avatar silhouette icon
  shape(root, 'circle', { cx: imgBoxX + imgBoxW / 2, cy: imgBoxY + 120, r: 65, fill: '#475569' });
  shape(root, 'ellipse', { cx: imgBoxX + imgBoxW / 2, cy: imgBoxY + 280, rx: 100, ry: 80, fill: '#475569' });

  // Laser quét dọc ảnh
  const scanP = (t * 0.8) % 1;
  const scanY = imgBoxY + scanP * imgBoxH;
  shape(root, 'line', { x1: imgBoxX, y1: scanY, x2: imgBoxX + imgBoxW, y2: scanY, stroke: '#38bdf8', 'stroke-width': 3, opacity: 0.8 });

  // Thông tin hồ sơ bên phải
  const infoX = imgBoxX + imgBoxW + 60;
  const nameText = sanitizeSemanticLabel(d.name || d.label || d.text || '', 6);
  root.append(el('text', {
    x: infoX, y: y + 130,
    'font-size': '44', 'font-weight': '900', fill: '#f4f7ff', class: 'ill-label'
  }, nameText));

  // Dòng trạng thái (nếu có từ dữ liệu thật)
  const statusRaw = d.status || (d.number_text ? String(d.number_text) : '');
  if (statusRaw) {
    const statusText = sanitizeSemanticLabel(statusRaw, 6);
    root.append(el('text', {
      x: infoX, y: y + 210,
      'font-size': '38', 'font-weight': '800', fill: '#f43f5e', class: 'ill-label'
    }, statusText));
  }

  // Dấu mộc đóng xuống nếu có badge từ dữ liệu thật
  if (d.badge || d.stamp) {
    const stampAt = 0.8;
    if (t >= stampAt) {
      const stampP = clamp((t - stampAt) / 0.25);
      const stampScale = overshoot(stampP, 1.3);
      const stampGroup = group(root, {
        transform: `translate(${x + w - 180}, ${y + h - 120}) rotate(-14) scale(${stampScale})`
      });
      shape(stampGroup, 'rect', { x: -110, y: -35, width: 220, height: 70, rx: 12, fill: 'none', stroke: '#ef4444', 'stroke-width': 4 });
      stampGroup.append(el('text', {
        x: 0, y: 12, 'text-anchor': 'middle',
        'font-size': '36', 'font-weight': '900', fill: '#ef4444', class: 'ill-label'
      }, sanitizeSemanticLabel(d.badge || d.stamp, 6)));
    }
  }
}

// 33. DOCUMENT_PAGE_FLIP: Tài liệu lật trang 3D
function renderDocumentPageFlip(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 780;
  const w = 940, h = 480;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.08)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  // Trang dưới
  shape(root, 'rect', { x: x + 40, y: y + 20, width: w - 80, height: h - 40, rx: 20, fill: '#1e293b', stroke: '#334155', 'stroke-width': 3 });

  // Trang lật phía trên
  const flipP = clamp((t - 0.6) / 1.8);
  const flipAngle = easeInOutCubic(flipP) * -45;
  const pageGroup = group(root, {
    transform: `translate(${x + 40}, ${y + 20}) rotate(${flipAngle})`
  });
  shape(pageGroup, 'rect', { x: 0, y: 0, width: w - 80, height: h - 40, rx: 20, fill: '#0f172a', stroke: 'var(--accent)', 'stroke-width': 3 });

  // Các dòng chữ mô phỏng trên trang
  const docTitle = sanitizeSemanticLabel(d.title || d.label || d.text || '', 6);
  pageGroup.append(el('text', {
    x: 60, y: 80, 'font-size': '42', 'font-weight': '900', fill: 'var(--accent)', class: 'ill-label'
  }, docTitle));

  for (let i = 0; i < 4; i++) {
    shape(pageGroup, 'rect', { x: 60, y: 130 + i * 55, width: (w - 200) * (0.9 - i * 0.1), height: 16, rx: 8, fill: '#334155' });
  }
}

// 34. CAMERA_SURVEILLANCE_SCAN: Khung ngắm camera giám sát & tia quét
function renderCameraSurveillanceScan(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 780;
  const w = 940, h = 480;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.05)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  shape(root, 'rect', { x, y, width: w, height: h, rx: 24, fill: '#030712ee', stroke: '#1f2937', 'stroke-width': 3 });

  // 4 góc ngắm Viewfinder
  const bLen = 60, bW = 6;
  // Góc trên trái
  shape(root, 'line', { x1: x + 40, y1: y + 40, x2: x + 40 + bLen, y2: y + 40, stroke: 'var(--accent)', 'stroke-width': bW });
  shape(root, 'line', { x1: x + 40, y1: y + 40, x2: x + 40, y2: y + 40 + bLen, stroke: 'var(--accent)', 'stroke-width': bW });
  // Góc trên phải
  shape(root, 'line', { x1: x + w - 40, y1: y + 40, x2: x + w - 40 - bLen, y2: y + 40, stroke: 'var(--accent)', 'stroke-width': bW });
  shape(root, 'line', { x1: x + w - 40, y1: y + 40, x2: x + w - 40, y2: y + 40 + bLen, stroke: 'var(--accent)', 'stroke-width': bW });
  // Góc dưới trái
  shape(root, 'line', { x1: x + 40, y1: y + h - 40, x2: x + 40 + bLen, y2: y + h - 40, stroke: 'var(--accent)', 'stroke-width': bW });
  shape(root, 'line', { x1: x + 40, y1: y + h - 40, x2: x + 40, y2: y + h - 40 - bLen, stroke: 'var(--accent)', 'stroke-width': bW });
  // Góc dưới phải
  shape(root, 'line', { x1: x + w - 40, y1: y + h - 40, x2: x + w - 40 - bLen, y2: y + h - 40, stroke: 'var(--accent)', 'stroke-width': bW });
  shape(root, 'line', { x1: x + w - 40, y1: y + h - 40, x2: x + w - 40, y2: y + h - 40 - bLen, stroke: 'var(--accent)', 'stroke-width': bW });

  // REC nhấp nháy
  const recBlink = Math.sin(t * 5) > 0;
  shape(root, 'circle', { cx: x + 80, cy: y + 80, r: 12, fill: recBlink ? '#ef4444' : '#7f1d1d' });
  root.append(el('text', {
    x: x + 110, y: y + 90, 'font-size': '36', 'font-weight': '900', fill: '#ef4444', class: 'ill-label'
  }, 'REC'));

  // Tia laser quét dọc
  const laserP = (t * 0.9) % 1;
  const laserY = y + 50 + laserP * (h - 100);
  shape(root, 'line', { x1: x + 40, y1: laserY, x2: x + w - 40, y2: laserY, stroke: '#f43f5e', 'stroke-width': 3, opacity: 0.75 });

  // Nhãn đối tượng mục tiêu
  const targetLbl = sanitizeSemanticLabel(d.label || d.text || '', 6);
  root.append(el('text', {
    x: cx, y: cy + 30, 'text-anchor': 'middle',
    'font-size': '44', 'font-weight': '900', fill: '#f4f7ff', class: 'ill-label'
  }, targetLbl));
}

// 35. EVIDENCE_BOARD: Bảng chứng cứ điều tra với dây chỉ đỏ liên kết
function renderEvidenceBoard(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 780;
  const w = 940, h = 500;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.08)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  shape(root, 'rect', { x, y, width: w, height: h, rx: 24, fill: '#0d1527', stroke: '#334155', 'stroke-width': 3 });

  // 3 thẻ chứng cứ tại 3 góc
  const pA = { x: x + 180, y: y + 130 };
  const pB = { x: x + w - 180, y: y + 130 };
  const pC = { x: cx, y: y + h - 110 };

  const rawItems = (d.items && d.items.length) ? d.items : [d.label, d.text, d.title].filter(Boolean);
  const lblA = sanitizeSemanticLabel(rawItems[0] || '', 6);
  const lblB = sanitizeSemanticLabel(rawItems[1] || '', 6);
  const lblC = sanitizeSemanticLabel(rawItems[2] || '', 6);

  // Dây chỉ đỏ nối
  const lineP = clamp((t - 0.4) / 1.2);
  shape(root, 'line', { x1: pA.x, y1: pA.y, x2: pA.x + (pB.x - pA.x) * lineP, y2: pA.y + (pB.y - pA.y) * lineP, stroke: '#ef4444', 'stroke-width': 4 });
  if (lineP > 0.5) {
    const p2 = (lineP - 0.5) * 2;
    shape(root, 'line', { x1: pB.x, y1: pB.y, x2: pB.x + (pC.x - pB.x) * p2, y2: pB.y + (pC.y - pB.y) * p2, stroke: '#ef4444', 'stroke-width': 4 });
  }

  // Vẽ các thẻ chứng cứ và ghim bấm
  const renderCard = (pt, lbl, delay) => {
    const cP = clamp((t - delay) / 0.3);
    const cScale = overshoot(cP, 1.2);
    const cg = group(root, { transform: `translate(${pt.x}, ${pt.y}) scale(${cScale})` });
    shape(cg, 'rect', { x: -130, y: -45, width: 260, height: 90, rx: 14, fill: '#1e293b', stroke: '#475569', 'stroke-width': 2 });
    shape(cg, 'circle', { cx: 0, cy: -45, r: 10, fill: '#ef4444', stroke: '#fff', 'stroke-width': 2 });
    cg.append(el('text', {
      x: 0, y: 12, 'text-anchor': 'middle', 'font-size': '36', 'font-weight': '900', fill: '#f4f7ff', class: 'ill-label'
    }, lbl));
  };

  renderCard(pA, lblA, 0.1);
  renderCard(pB, lblB, 0.4);
  renderCard(pC, lblC, 0.8);
}

// 36. NETWORK_GRAPH: Mạng lưới liên kết đa nút & xung điện truyền động
function renderNetworkGraph(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 780;
  const w = 940, h = 500;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.08)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  shape(root, 'rect', { x, y, width: w, height: h, rx: 24, fill: '#0a101f', stroke: '#1e293b', 'stroke-width': 3 });

  // 4 nút vệ tinh quanh tâm
  const satCoords = [
    { x: cx - 280, y: cy - 110 },
    { x: cx + 280, y: cy - 110 },
    { x: cx - 240, y: cy + 120 },
    { x: cx + 240, y: cy + 120 }
  ];

  satCoords.forEach((pt, i) => {
    // Đường liên kết
    shape(root, 'line', { x1: cx, y1: cy, x2: pt.x, y2: pt.y, stroke: '#38bdf844', 'stroke-width': 3 });
    // Xung điện chạy dọc
    const pulseP = (t * 1.2 + i * 0.25) % 1;
    const px = cx + (pt.x - cx) * pulseP;
    const py = cy + (pt.y - cy) * pulseP;
    shape(root, 'circle', { cx: px, cy: py, r: 6, fill: '#38bdf8' });

    // Vệ tinh node
    shape(root, 'circle', { cx: pt.x, cy: pt.y, r: 35, fill: '#1e293b', stroke: '#38bdf8', 'stroke-width': 3 });
  });

  // Nút trung tâm lớn
  shape(root, 'circle', { cx, cy, r: 90, fill: '#0f172a', stroke: 'var(--accent)', 'stroke-width': 5 });
  const centerLbl = sanitizeSemanticLabel(d.label || d.text || '', 6);
  root.append(el('text', {
    x: cx, y: cy + 12, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': '900', fill: 'var(--accent)', class: 'ill-label'
  }, centerLbl));
}

// 37. COUNTDOWN_TIMER: Đồng hồ đếm ngược với kim quét & số lật
function renderCountdownTimer(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 760;
  const w = 940, h = 480;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.1)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  shape(root, 'rect', { x, y, width: w, height: h, rx: 28, fill: '#0b1329', stroke: '#1e293b', 'stroke-width': 3 });

  // Vòng tròn đồng hồ lớn
  const r = 140;
  shape(root, 'circle', { cx, cy: cy - 20, r, fill: '#0f172a', stroke: '#334155', 'stroke-width': 8 });

  // Vòng quét tiến độ
  const sweepP = clamp(t / duration);
  const circ = 2 * Math.PI * r;
  shape(root, 'circle', {
    cx, cy: cy - 20, r, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 10,
    'stroke-dasharray': circ, 'stroke-dashoffset': circ * (1 - sweepP),
    transform: `rotate(-90 ${cx} ${cy - 20})`, 'stroke-linecap': 'round'
  });

  // Số đếm ngược ở tâm
  if (!d._is_fixture && (d.value === null || d.value === undefined || isNaN(Number(d.value)))) { if (window.MotionRecipes && window.MotionRecipes.renderTextFocus) return window.MotionRecipes.renderTextFocus(ctx, svg, d, t, duration, 0); }
  const targetNum = Number(d.value);
  const currentNum = Math.max(0, Math.round(targetNum * (1 - sweepP * 0.7)));
  root.append(el('text', {
    x: cx, y: cy, 'text-anchor': 'middle',
    'font-size': '72', 'font-weight': '900', fill: '#f4f7ff', class: 'ill-label'
  }, String(currentNum)));

  // Nhãn thời hạn
  const timeLbl = sanitizeSemanticLabel(d.label || d.text || '', 6);
  root.append(el('text', {
    x: cx, y: cy + 170, 'text-anchor': 'middle',
    'font-size': '40', 'font-weight': '900', fill: 'var(--accent)', class: 'ill-label'
  }, timeLbl));
}

// 38. COURTROOM_BALANCE: Tòa án / Cán cân công lý đa lớp & búa quan tòa
function renderCourtroomBalance(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 780;
  const w = 940, h = 500;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.08)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  shape(root, 'rect', { x, y, width: w, height: h, rx: 28, fill: '#0a0f1d', stroke: '#334155', 'stroke-width': 3 });

  // Trụ cán cân
  shape(root, 'line', { x1: cx, y1: cy - 130, x2: cx, y2: cy + 130, stroke: '#e2e8f0', 'stroke-width': 8 });
  shape(root, 'rect', { x: cx - 60, y: cy + 130, width: 120, height: 20, rx: 6, fill: '#cbd5e1' });

  // Đòn cân nghiêng
  const tiltAngle = Math.sin(t * 2) * 7;
  const beamW = 420;
  const beamGroup = group(root, { transform: `translate(${cx}, ${cy - 120}) rotate(${tiltAngle})` });
  shape(beamGroup, 'line', { x1: -beamW / 2, y1: 0, x2: beamW / 2, y2: 0, stroke: 'var(--accent)', 'stroke-width': 8, 'stroke-linecap': 'round' });

  // Hai đĩa cân
  const leftX = cx - (beamW / 2) * Math.cos(tiltAngle * Math.PI / 180);
  const leftY = (cy - 120) - (beamW / 2) * Math.sin(tiltAngle * Math.PI / 180);
  shape(root, 'line', { x1: leftX, y1: leftY, x2: leftX, y2: leftY + 110, stroke: '#94a3b8', 'stroke-width': 3 });
  shape(root, 'ellipse', { cx: leftX, cy: leftY + 110, rx: 80, ry: 16, fill: '#1e293b', stroke: 'var(--accent)', 'stroke-width': 3 });

  const rightX = cx + (beamW / 2) * Math.cos(tiltAngle * Math.PI / 180);
  const rightY = (cy - 120) + (beamW / 2) * Math.sin(tiltAngle * Math.PI / 180);
  shape(root, 'line', { x1: rightX, y1: rightY, x2: rightX, y2: rightY + 110, stroke: '#94a3b8', 'stroke-width': 3 });
  shape(root, 'ellipse', { cx: rightX, cy: rightY + 110, rx: 80, ry: 16, fill: '#1e293b', stroke: 'var(--accent)', 'stroke-width': 3 });

  // Nhãn 2 đĩa cân
  const leftLbl = sanitizeSemanticLabel(d.left_label || d.label || '', 6);
  const rightLbl = sanitizeSemanticLabel(d.right_label || d.text || '', 6);
  root.append(el('text', {
    x: leftX, y: leftY + 165, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': '900', fill: '#f43f5e', class: 'ill-label'
  }, leftLbl));
  root.append(el('text', {
    x: rightX, y: rightY + 165, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': '900', fill: '#38bdf8', class: 'ill-label'
  }, rightLbl));
}

// 39. CODE_TERMINAL_WINDOW: Cửa sổ lệnh terminal quét dữ liệu / điều tra
function renderCodeTerminalWindow(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 780;
  const w = 940, h = 480;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.08)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  // Khung terminal
  shape(root, 'rect', { x, y, width: w, height: h, rx: 20, fill: '#090d16', stroke: '#1e293b', 'stroke-width': 3 });
  // Thanh tiêu đề header
  shape(root, 'rect', { x, y, width: w, height: 60, rx: 20, fill: '#1e293b' });
  // 3 nút macOS
  shape(root, 'circle', { cx: x + 40, cy: y + 30, r: 10, fill: '#ef4444' });
  shape(root, 'circle', { cx: x + 70, cy: y + 30, r: 10, fill: '#f59e0b' });
  shape(root, 'circle', { cx: x + 100, cy: y + 30, r: 10, fill: '#10b981' });

  // Dòng lệnh gõ
  const cmdRaw = d.command ? d.command : (d.label ? `inspect --${d.label.toLowerCase().replace(/[^a-z0-9]/g, '')}` : 'run --check');
  root.append(el('text', {
    x: x + 45, y: y + 140,
    'font-size': '38', 'font-weight': '900', fill: 'var(--accent)', font_family: 'monospace', class: 'ill-label'
  }, `> ${cmdRaw}`));

  // Kết quả quét
  const resultLines = (d.items && d.items.length) ? d.items.slice(0, 3) : ((d.lines && d.lines.length) ? d.lines.slice(0, 3) : []);
  resultLines.forEach((line, idx) => {
    const lineP = clamp((t - (0.6 + idx * 0.4)) / 0.3);
    if (lineP > 0) {
      root.append(el('text', {
        x: x + 45, y: y + 220 + idx * 60,
        'font-size': '36', 'font-weight': '800', fill: '#34d399', font_family: 'monospace',
        class: 'ill-label', opacity: lineP
      }, sanitizeSemanticLabel(line, 5)));
    }
  });
}

// 40. QUOTE_DIALOG_CARD: Thẻ trích dẫn câu hỏi / tuyên bố nổi bật
function renderQuoteDialogCard(ctx, svg, d, t, duration = 4) {
  const enterP = clamp(t / 0.5);
  const cx = 540, cy = 780;
  const w = 940, h = 460;
  const x = cx - w / 2, y = cy - h / 2;

  const root = group(svg, {
    transform: `translate(${cx}, ${cy}) scale(${overshoot(enterP, 1.08)}) translate(${-cx}, ${-cy})`,
    class: 'motion-element'
  });

  shape(root, 'rect', { x, y, width: w, height: h, rx: 28, fill: '#0d1527ee', stroke: 'var(--accent)', 'stroke-width': 3 });

  // Dấu ngoặc kép đôi lớn
  root.append(el('text', {
    x: x + 70, y: y + 130,
    'font-size': '120', 'font-weight': '900', fill: 'var(--accent)', opacity: 0.35,
    font_family: 'Georgia, serif'
  }, '“'));

  // Nội dung trích dẫn
  const quoteText = sanitizeSemanticLabel(d.text || d.label || '', 6);
  root.append(el('text', {
    x: cx, y: cy + 15, 'text-anchor': 'middle',
    'font-size': '44', 'font-weight': '900', fill: '#f4f7ff', class: 'ill-label'
  }, quoteText));

  // Người phát ngôn / nguồn
  const speaker = sanitizeSemanticLabel(d.source || d.label || '', 6);
  shape(root, 'line', { x1: cx - 120, y1: cy + 85, x2: cx + 120, y2: cy + 85, stroke: '#475569', 'stroke-width': 3 });
  root.append(el('text', {
    x: cx, y: cy + 140, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': '800', fill: '#94a3b8', class: 'ill-label'
  }, `— ${speaker}`));
}


const vocabularyMap = {
  slot_counter: renderSlotCounter,
  strike_replace: renderStrikeReplace,
  gauge_needle: renderGaugeNeedle,
  odometer: renderOdometer,
  bar_race: renderBarRace,
  thermometer: renderThermometer,
  battery_fill: renderBatteryFill,
  glass_fill: renderGlassFill,
  balance_scale: renderBalanceScale,
  tug_of_war: renderTugOfWar,
  vs_flip_cards: renderVsFlipCards,
  before_after_wipe: renderBeforeAfterWipe,
  conveyor_belt: renderConveyorBelt,
  domino_chain: renderDominoChain,
  funnel_filter: renderFunnelFilter,
  pipeline_pipes: renderPipelinePipes,
  dice_roll: renderDiceRoll,
  lock_unlock: renderLockUnlock,
  shield_hit: renderShieldHit,
  traffic_light: renderTrafficLight,
  orbit_system: renderOrbitSystem,
  layered_onion: renderLayeredOnion,
  stack_pile: renderStackPile,
  puzzle_snap: renderPuzzleSnap,
  chat_thread: renderChatThread,
  mock_card_swipe: renderMockCardSwipe,
  form_fill_submit: renderFormFillSubmit,
  terminal_command_run: renderTerminalCommandRun,
  before_after_split: renderBeforeAfterSplit,
  timeline_milestones: renderTimelineMilestones,
  map_location_pin: renderMapLocationPin,
  profile_dossier: renderProfileDossier,
  document_page_flip: renderDocumentPageFlip,
  camera_surveillance_scan: renderCameraSurveillanceScan,
  evidence_board: renderEvidenceBoard,
  network_graph: renderNetworkGraph,
  countdown_timer: renderCountdownTimer,
  courtroom_balance: renderCourtroomBalance,
  code_terminal_window: renderCodeTerminalWindow,
  quote_dialog_card: renderQuoteDialogCard,
};

window.MotionVocabulary = Object.assign(window.MotionVocabulary || {}, vocabularyMap);

if (window.MotionRecipes) {
  window.MotionRecipes.renderSlotCounter = renderSlotCounter;
  window.MotionRecipes.renderStrikeReplace = renderStrikeReplace;
  window.MotionRecipes.renderGaugeNeedle = renderGaugeNeedle;
  window.MotionRecipes.renderOdometer = renderOdometer;
  window.MotionRecipes.renderBarRace = renderBarRace;
  window.MotionRecipes.renderThermometer = renderThermometer;
  window.MotionRecipes.renderBatteryFill = renderBatteryFill;
  window.MotionRecipes.renderGlassFill = renderGlassFill;
  window.MotionRecipes.renderBalanceScale = renderBalanceScale;
  window.MotionRecipes.renderTugOfWar = renderTugOfWar;
  window.MotionRecipes.renderVsFlipCards = renderVsFlipCards;
  window.MotionRecipes.renderBeforeAfterWipe = renderBeforeAfterWipe;
  window.MotionRecipes.renderConveyorBelt = renderConveyorBelt;
  window.MotionRecipes.renderDominoChain = renderDominoChain;
  window.MotionRecipes.renderFunnelFilter = renderFunnelFilter;
  window.MotionRecipes.renderPipelinePipes = renderPipelinePipes;
  window.MotionRecipes.renderDiceRoll = renderDiceRoll;
  window.MotionRecipes.renderLockUnlock = renderLockUnlock;
  window.MotionRecipes.renderShieldHit = renderShieldHit;
  window.MotionRecipes.renderTrafficLight = renderTrafficLight;
  window.MotionRecipes.renderOrbitSystem = renderOrbitSystem;
  window.MotionRecipes.renderLayeredOnion = renderLayeredOnion;
  window.MotionRecipes.renderStackPile = renderStackPile;
  window.MotionRecipes.renderPuzzleSnap = renderPuzzleSnap;
  window.MotionRecipes.renderChatThread = renderChatThread;
  window.MotionRecipes.renderMockCardSwipe = renderMockCardSwipe;
  window.MotionRecipes.renderFormFillSubmit = renderFormFillSubmit;
  window.MotionRecipes.renderTerminalCommandRun = renderTerminalCommandRun;
}

})();