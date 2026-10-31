from pathlib import Path
p = Path('editor/motion/recipes/vocabulary.js')
text = p.read_text(encoding='utf-8')

# 1. Pipeline pipes safe bounds
old_pipes = """  const enterP = clamp(t / 0.6);
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

  const cardW = 860;
  const cardH = 580;"""

new_pipes = """  const enterP = clamp(t / 0.6);
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

  const cardW = 800;
  const cardH = 520;"""

assert old_pipes in text, "old_pipes not found"
text = text.replace(old_pipes, new_pipes, 1)

# Remove 'MAX' hardcoded text in pipeline_pipes
old_max = """  root.append(el('text', {
    x: p3.x, y: p3.y + 12, 'text-anchor': 'middle',
    'font-size': '36', 'font-weight': '900',
    fill: t >= 2.3 ? '#10b981' : '#94a3b8', class: 'ill-label'
  }, 'MAX'));"""

new_max = """  if (d.value !== undefined && d.value !== null) {
    root.append(el('text', {
      x: p3.x, y: p3.y + 12, 'text-anchor': 'middle',
      'font-size': '36', 'font-weight': '900',
      fill: t >= 2.3 ? '#10b981' : '#94a3b8', class: 'ill-label'
    }, String(d.value)));
  }"""

assert old_max in text, "old_max not found"
text = text.replace(old_max, new_max, 1)

# 2. Lock unlock safe bounds and remove 'ĐANG KHÓA CHẶT' hardcoded text
old_lock = """  const enterP = clamp(t / 0.6);
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

  const cardW = 820;
  const cardH = 620;"""

new_lock = """  const enterP = clamp(t / 0.6);
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

  const cardW = 800;
  const cardH = 520;"""

assert old_lock in text, "old_lock not found"
text = text.replace(old_lock, new_lock, 1)

old_lock_status = """  // Status readout below
  root.append(el('text', {
    x: cx, y: cy + bodyH / 2 + 115, 'text-anchor': 'middle',
    'font-size': '44', 'font-weight': '900',
    fill: isUnlocked ? '#34d399' : '#fb7185', class: 'ill-label'
  }, isUnlocked ? 'MỞ KHÓA THÀNH CÔNG' : 'ĐANG KHÓA CHẶT'));"""

new_lock_status = """  // Status readout below (use grounded status or label if available, no fabricated string)
  const statusTxt = status ? sanitizeSemanticLabel(status, 4) : '';
  if (statusTxt) {
    root.append(el('text', {
      x: cx, y: cy + bodyH / 2 + 100, 'text-anchor': 'middle',
      'font-size': '40', 'font-weight': '900',
      fill: isUnlocked ? '#34d399' : '#fb7185', class: 'ill-label'
    }, statusTxt));
  }"""

assert old_lock_status in text, "old_lock_status not found"
text = text.replace(old_lock_status, new_lock_status, 1)

p.write_text(text, encoding='utf-8')
print("Successfully updated pipeline_pipes and lock_unlock safe bounds!")
