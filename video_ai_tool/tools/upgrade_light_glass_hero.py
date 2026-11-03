"""Update light_glass.js to Hero Full-Stage Visual Motion with safe area strict compliance."""
from pathlib import Path

target_file = Path("editor/motion/recipes/light_glass.js")
code_norm = target_file.read_text(encoding="utf-8").replace("\r\n", "\n")

# Locate renderAiNetworkMockup or renderContentSmartMockup
start_tag = "// =========================================================================\n// MOCKUP: AI Neural Network Architecture"
if start_tag not in code_norm:
    start_tag = "// Smart Mockup Selector: grounded in slide context"

end_tag = "// Export light glass recipes"

idx1 = code_norm.find(start_tag)
idx2 = code_norm.find(end_tag)

print(f"Replacing region: {idx1} to {idx2}")

hero_module = """// =========================================================================
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

  const imgUrl = d.image_url || d.image || d.chart_image;
  if (imgUrl) {
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

"""

code_norm = code_norm[:idx1] + hero_module + code_norm[idx2:]
target_file.write_text(code_norm, encoding="utf-8")
print("Saved light_glass.js with safe area strict compliance successfully!")
