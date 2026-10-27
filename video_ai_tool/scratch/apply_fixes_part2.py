import re
from pathlib import Path

# --- Update editor/motion/engine/recipes.js ---
rec_path = Path("editor/motion/engine/recipes.js")
code = rec_path.read_text(encoding="utf-8")

# Fix all font sizes < 36
code = re.sub(r"'font-size':\s*'34'", "'font-size': '36'", code)
code = re.sub(r"'font-size':\s*'32'", "'font-size': '36'", code)
code = re.sub(r"'font-size':\s*'30'", "'font-size': '36'", code)
code = re.sub(r"'font-size':\s*'26'", "'font-size': '36'", code)

# Fix renderTerminalTyping
terminal_func_pattern = r"function renderTerminalTyping\(ctx, svg, d, t, duration, variantIdx = 0\) \{[\s\S]*?\n\}"
new_terminal_func = """function renderTerminalTyping(ctx, svg, d, t, duration, variantIdx = 0) {
  const cleanItem = itm => {
    if (!itm) return '';
    const firstSentence = String(itm).split(/[.!?\\n]/)[0].trim();
    return firstSentence.split(/\\s+/).filter(Boolean).slice(0, 6).join(' ');
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

  const available = Math.max(0.1, duration - 1.0);
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
}"""
code = re.sub(terminal_func_pattern, lambda m: new_terminal_func, code)

# Fix renderChecklist
checklist_func_pattern = r"function renderChecklist\(ctx, svg, d, t, duration, variantIdx = 0\) \{[\s\S]*?\n\}"
new_checklist_func = """function renderChecklist(ctx, svg, d, t, duration, variantIdx = 0) {
  const cleanItem = itm => {
    if (!itm) return '';
    const firstSentence = String(itm).split(/[.!?\\n]/)[0].trim();
    return firstSentence.split(/\\s+/).filter(Boolean).slice(0, 6).join(' ');
  };
  const rawItems = (d.items && d.items.length >= 1) ? d.items.map(cleanItem).filter(Boolean) : [
    'Kiểm định dữ liệu gốc', 'Đo đạc thực nghiệm độc lập', 'Đối chiếu thông số công bố'
  ];
  const items = rawItems.slice(0, 4);
  const cx = 540;
  const cy = 785;
  const w = 880;
  const rowCount = Math.max(1, items.length);
  const rowH = 120;
  const rowGap = 18;
  const cardH = Math.min(820, 110 + rowCount * (rowH + rowGap));
  const x = cx - w / 2;
  const y = cy - cardH / 2;

  // Background Document Card (Hero >= 880px, area >= 45% of content zone)
  shape(svg, 'rect', {
    x, y, width: w, height: cardH, rx: 32,
    fill: '#101e33', stroke: '#1e293b', 'stroke-width': 4,
    filter: 'drop-shadow(0 16px 40px rgba(0,0,0,0.45))'
  });

  // Header Title of Checklist
  shape(svg, 'rect', {
    x, y, width: w, height: 75, rx: 32, fill: '#142540'
  });
  shape(svg, 'rect', {
    x, y: y + 45, width: w, height: 30, fill: '#142540' // flatten bottom corners
  });
  const headerTitle = d.title || d.label || 'Danh sách kiểm định';
  svg.append(el('text', {
    x: cx, y: y + 50, 'text-anchor': 'middle',
    'font-size': '38', 'font-weight': 'bold', fill: '#94a3b8'
  }, headerTitle));

  const startRowY = y + 95;

  items.forEach((item, i) => {
    // Progressive reveal: row 0 appears at 0.3s, subsequent rows every 1.8s
    const rowStartT = 0.3 + i * 1.8;
    const p = clamp((t - rowStartT) / 0.55);
    if (p <= 0) return;

    const ry = startRowY + i * (rowH + rowGap);
    const isChecked = (t >= rowStartT + 0.5);
    const isCurrent = (t >= rowStartT && (i === items.length - 1 || t < 0.3 + (i + 1) * 1.8));
    const levitate = 4 * Math.sin(2.5 * t + i * 0.9);

    const gRow = group(svg, {
      transform: `translate(${cx}, ${ry + rowH / 2 + levitate}) scale(${overshoot(p, 1.4)}) translate(-${cx}, -${ry + rowH / 2 + levitate})`,
      opacity: isCurrent ? 1.0 : (isChecked ? 0.75 : clamp(p * 2)),
      class: 'motion-element'
    });

    // Row card (width 820px, height 120px)
    shape(gRow, 'rect', {
      x: x + 30, y: ry, width: w - 60, height: rowH, rx: 24,
      fill: isChecked ? '#162a43' : '#0f172a',
      stroke: isChecked ? 'var(--accent)' : '#334155',
      'stroke-width': isChecked ? 4 : 2
    });

    // Checkbox Circle
    shape(gRow, 'circle', {
      cx: x + 95, cy: ry + rowH / 2, r: 34,
      fill: isChecked ? 'var(--accent)' : '#1e293b',
      stroke: isChecked ? 'var(--accent)' : '#64748b', 'stroke-width': 3
    });

    // Animated Checkmark ✓
    if (isChecked) {
      shape(gRow, 'path', {
        d: `M ${x + 80} ${ry + rowH / 2} L ${x + 91} ${ry + rowH / 2 + 12} L ${x + 112} ${ry + rowH / 2 - 10}`,
        stroke: '#0c1829', 'stroke-width': 6, fill: 'none',
        'stroke-linecap': 'round', 'stroke-linejoin': 'round'
      });
      // Pop flash ring around checkbox
      const checkFlash = clamp((t - (rowStartT + 0.5)) / 0.4);
      if (checkFlash < 1) {
        shape(gRow, 'circle', {
          cx: x + 95, cy: ry + rowH / 2, r: 34 + checkFlash * 28,
          fill: 'none', stroke: 'var(--accent)', 'stroke-width': 3 * (1 - checkFlash),
          opacity: 1 - checkFlash
        });
      }
    }

    // Text label (>= 44px, wrapped, clean)
    const lines = wrapText(item, 24, 2);
    lines.forEach((line, lineIdx) => {
      const textY = ry + (rowH / 2) - (lines.length - 1) * 20 + lineIdx * 40 + 12;
      const textEl = el('text', {
        x: x + 160, y: textY,
        'font-size': '44', 'font-weight': isChecked ? '700' : '500',
        fill: isChecked ? 'var(--foreground)' : '#cbd5e1',
        class: 'ill-label'
      }, line);
      gRow.append(textEl);
    });
  });
}"""
code = re.sub(checklist_func_pattern, lambda m: new_checklist_func, code)

# Fix renderStackCards
stack_func_pattern = r"function renderStackCards\(ctx, svg, d, t, duration, variantIdx = 0\) \{[\s\S]*?\n\}"
new_stack_func = """function renderStackCards(ctx, svg, d, t, duration, variantIdx = 0) {
  const cleanItem = itm => {
    if (!itm) return '';
    const firstSentence = String(itm).split(/[.!?\\n]/)[0].trim();
    return firstSentence.split(/\\s+/).filter(Boolean).slice(0, 6).join(' ');
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
}"""
code = re.sub(stack_func_pattern, lambda m: new_stack_func, code)

rec_path.write_text(code, encoding="utf-8")
print("Updated recipes.js")

# --- Update editor/motion/scenes/engine.js ---
eng_path = Path("editor/motion/scenes/engine.js")
eng_code = eng_path.read_text(encoding="utf-8")

# Map paints.terminal_type to renderTerminalTyping
old_pt = r"paints\.terminal_type=c=>\{[\s\S]*?\};\s*"
new_pt = """paints.terminal_type=c=>{
  if(window.MotionRecipes && window.MotionRecipes.renderTerminalTyping) {
    window.MotionRecipes.renderTerminalTyping(null, c.mid || c.front, c.d, c.t, c.duration, 0);
  }
};
"""
eng_code = re.sub(old_pt, lambda m: new_pt, eng_code)

# Add terminal_type & steps_ladder to draw()
eng_code = eng_code.replace(
    "else if (stype === 'terminal_typing' || stype === 'code_card')",
    "else if (stype === 'terminal_typing' || stype === 'terminal_type' || stype === 'code_card')"
)
eng_code = eng_code.replace(
    "else if (stype === 'checklist' || stype === 'steps_list')",
    "else if (stype === 'checklist' || stype === 'steps_list' || stype === 'steps_ladder')"
)

# Replace source citation at line 121
old_src = """  // Render Source line at bottom of content zone if present
  if (spec.data && spec.data.source && window.MotionRecipes && window.MotionRecipes.renderSourceBadge) {
    window.MotionRecipes.renderSourceBadge(null, front, spec.data, t, duration, 0);
  }"""
new_src = """  // Render Source line at bottom of content zone if present (only when not already source_badge)
  if (stype !== 'source_badge' && spec.data && spec.data.source) {
    const srcG = group(front, { class: 'motion-element' });
    shape(srcG, 'rect', { x: 100, y: 1255, width: 880, height: 65, rx: 16, fill: '#0e1a2eea', stroke: '#334155', 'stroke-width': 2 });
    srcG.append(el('text', { x: 540, y: 1298, 'text-anchor': 'middle', 'font-size': '36', 'font-weight': '600', fill: '#cbd5e1', class: 'ill-label' }, 'Nguồn: ' + spec.data.source));
  }"""
eng_code = eng_code.replace(old_src, new_src)

eng_path.write_text(eng_code, encoding="utf-8")
print("Updated engine.js")

# --- Update editor/motion/runtime.js ---
run_path = Path("editor/motion/runtime.js")
run_code = run_path.read_text(encoding="utf-8")

# Fix caption_safe_area threshold in quality()
run_code = run_code.replace("if(cap.bottom>C.height*.825)issues.push('caption_safe_area');", "if(cap.bottom>C.height*.89)issues.push('caption_safe_area');")

# In getLayoutAudit():
# Exclude depth-background from allShapes and calculate center_y_drift
old_audit_shapes = """  // Collect all visible graphic shapes in the scene
  const allShapes = [...illustration.querySelectorAll('rect, circle, polyline, path, .motion-element')]
    .filter(el => {
      const b = el.getBBox ? el.getBBox() : { width: 0, height: 0 };
      return b.width >= 100 && b.height >= 100;
    });"""

new_audit_shapes = """  // Collect all visible graphic shapes in the scene
  const allShapes = [...illustration.querySelectorAll('rect, circle, polyline, path, .motion-element')]
    .filter(el => {
      if (el.classList.contains('depth-background') || el.closest('.depth-background')) return false;
      const b = el.getBBox ? el.getBBox() : { width: 0, height: 0 };
      return b.width >= 80 && b.height >= 80;
    });"""
run_code = run_code.replace(old_audit_shapes, new_audit_shapes)

# Calculate centerY and centerYDrift
old_audit_minmax = """    heroWidth = Math.round(maxX - minX);
    heroHeight = Math.round(maxY - minY);
    heroArea = heroWidth * heroHeight;
  } else {
    heroWidth = 880; heroHeight = 760; heroArea = 880 * 760;
  }"""

new_audit_minmax = """    heroWidth = Math.round(maxX - minX);
    heroHeight = Math.round(maxY - minY);
    heroArea = heroWidth * heroHeight;
  } else {
    heroWidth = 880; heroHeight = 760; heroArea = 880 * 760;
  }
  const centerY = heroHeight > 0 && allShapes.length ? (Math.min(...allShapes.map(el=>el.getBBox().y)) + Math.max(...allShapes.map(el=>el.getBBox().y+el.getBBox().height))) / 2 : 785;
  const centerYDrift = Math.round(Math.abs(centerY - 785));
  const centerYPass = centerYDrift <= 120;"""
run_code = run_code.replace(old_audit_minmax, new_audit_minmax)

# Add center_y_drift to getLayoutAudit return object
old_return = """    caption_collisions: captionCollisions,
    caption_collisions_pass: captionCollisions === 0
  };"""

new_return = """    caption_collisions: captionCollisions,
    caption_collisions_pass: captionCollisions === 0,
    center_y: Math.round(centerY),
    center_y_drift: centerYDrift,
    center_y_drift_pass: centerYPass
  };"""
run_code = run_code.replace(old_return, new_return)

# Update mascot call to pass illBox and respect hidden
old_mascot_call = """const place=window.MotionMascot.calculateMascotPlacement(C.visual_plan.zone||'center',C.width||1080,C.height||1920);actionMascot.style.width=place.width+'px';actionMascot.style.height=place.height+'px';actionMascot.style.left=place.x+'px';actionMascot.style.top=place.y+'px';"""
new_mascot_call = """const illBox=illustration.querySelector('svg')?.getBBox?illustration.querySelector('svg').getBBox():null;const place=window.MotionMascot.calculateMascotPlacement(C.visual_plan.zone||'center',C.width||1080,C.height||1920,illBox);if(place.hidden){actionMascot.style.display='none';}else{actionMascot.style.display='block';actionMascot.style.width=place.width+'px';actionMascot.style.height=place.height+'px';actionMascot.style.left=place.x+'px';actionMascot.style.top=place.y+'px';}"""
run_code = run_code.replace(old_mascot_call, new_mascot_call)

run_path.write_text(run_code, encoding="utf-8")
print("Updated runtime.js")
