# tools/apply_light_glass_v8.py
"""Applies full Light Glass V8 upgrades to editor/motion/recipes/light_glass.js."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
LG_FILE = ROOT / "editor" / "motion" / "recipes" / "light_glass.js"

def update_light_glass_js():
    txt = LG_FILE.read_text(encoding="utf-8")

    # 1. computeLgMotion: seamless continuity, no 5s blank reload
    old_motion_pattern = r"function computeLgMotion\(t, duration\) \{[\s\S]*?return \{[\s\S]*?\};\s*\}"
    new_motion = """function computeLgMotion(t, duration) {
  // Seamless, continuous motion across 5s beats:
  // Alpha is 1.0 (never fades to 0 or blanks), continuous Ken Burns scale and subtle drift
  const progress = clamp(t / Math.max(0.1, duration));
  const scale = 1.0 + 0.040 * progress;
  const driftY = -6 * progress;
  const floatWave = Math.sin(t * 1.5) * 2.5;

  return {
    alpha: 1.0,
    scale: scale,
    translateY: driftY + floatWave,
    blur: 0,
    visible: true
  };
}"""
    txt = re.sub(old_motion_pattern, new_motion, txt, count=1)

    # 2. Add renderEmergencyGaugeMockup
    emergency_gauge_func = """
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
"""
    if "function renderEmergencyGaugeMockup" not in txt:
        txt = txt.replace("function renderFinancialChartMockup(parent, x, y, w, h, d, t) {", emergency_gauge_func + "\nfunction renderFinancialChartMockup(parent, x, y, w, h, d, t) {")

    # 3. Enhance renderRealImageWithGentleMotion with headline banner
    old_domain_pill = "  // Authentic source pill badge at bottom-left\n  const domainText = String(d.source || d.domain || '').trim();"
    headline_and_pill = """  // Top Headline Banner on Visual Card (Prominent context, bold white typography)
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
  const domainText = String(d.source || d.domain || 'finance.yahoo.com').trim();"""
    
    if old_domain_pill in txt:
        txt = txt.replace(old_domain_pill, headline_and_pill, 1)

    # 4. Update renderLgStatHero: ensure financial_chart renders dynamic chart!
    old_stat_hero = """function renderLgStatHero(ctx, svg, d, t, duration = 4) {
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

  const imgUrl = d.image_url || d.image || d.chart_image;
  if (imgUrl) {
    renderRealImageWithGentleMotion(root, stageX, stageY, stageW, stageH, imgUrl, d, t, duration, 'lg-stat-img');
  } else {
    renderFinancialChartMockup(root, stageX, stageY, stageW, stageH, d, t);
  }
}"""

    new_stat_hero = """function renderLgStatHero(ctx, svg, d, t, duration = 4) {
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
}"""
    if old_stat_hero in txt:
        txt = txt.replace(old_stat_hero, new_stat_hero, 1)

    # 5. Update renderLgNoteCard to route emergency fund to renderEmergencyGaugeMockup
    old_note_card = """  const imgUrl = d.image_url || d.image || d.clip_url;
  if (imgUrl) {
    renderRealImageWithGentleMotion(root, stageX, stageY, stageW, stageH, imgUrl, d, t, duration, 'lg-note-img');
  } else if (d.mockup_type === 'ai_network') {"""

    new_note_card = """  // If this beat is an emergency fund or reserve gauge, render dynamic gauge chart
  const isEmergency = d.mockup_type === 'emergency_fund' || d.mockup_type === 'emergency_gauge' || /quỹ dự phòng|khẩn cấp|3 đến 6/i.test(String(d.chip || d.text || ''));
  if (isEmergency) {
    renderEmergencyGaugeMockup(root, stageX, stageY, stageW, stageH, d, t);
    return;
  }

  const imgUrl = d.image_url || d.image || d.clip_url;
  if (imgUrl) {
    renderRealImageWithGentleMotion(root, stageX, stageY, stageW, stageH, imgUrl, d, t, duration, 'lg-note-img');
  } else if (d.mockup_type === 'ai_network') {"""

    if old_note_card in txt:
        txt = txt.replace(old_note_card, new_note_card, 1)

    LG_FILE.write_text(txt, encoding="utf-8")
    print("light_glass.js updated successfully with seamless motion, headline banner, and dynamic charts!")

if __name__ == "__main__":
    update_light_glass_js()
