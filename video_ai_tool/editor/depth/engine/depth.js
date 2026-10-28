/**
 * Depth 3D Engine: SVG & CSS 3D Isometric Perspective Rendering
 * Deterministic seekable renderer for 1080x1920 vertical video
 */

(function () {
  'use strict';

  // Helper math & easing
  function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
  }

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function easeOutBack(t) {
    const c1 = 1.70158;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  }

  function easeInOutQuad(t) {
    return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  }

  // 1. Perspective Floor Grid (Sàn lưới phối cảnh trôi mượt mà)
  function renderPerspectiveFloor(parent, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;
    const vpX = W * 0.5; // 540
    const vpY = 680;     // Horizon vanishing point

    const container = document.createElement('div');
    container.className = 'depth-floor-container';
    container.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;pointer-events:none;overflow:hidden;z-index:2;`;

    // SVG canvas for sharp perspective lines
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;display:block;';

    // Defs for horizon fade gradient
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    defs.innerHTML = `
      <linearGradient id="floorFade" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#09041a" stop-opacity="0" />
        <stop offset="25%" stop-color="#9d4edd" stop-opacity="0.12" />
        <stop offset="65%" stop-color="#00f5d4" stop-opacity="0.22" />
        <stop offset="100%" stop-color="#00f5d4" stop-opacity="0.02" />
      </linearGradient>
      <linearGradient id="radialFade" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#9d4edd" stop-opacity="0.0" />
        <stop offset="40%" stop-color="#9d4edd" stop-opacity="0.15" />
        <stop offset="85%" stop-color="#00f5d4" stop-opacity="0.25" />
        <stop offset="100%" stop-color="#00f5d4" stop-opacity="0.05" />
      </linearGradient>
    `;
    svg.appendChild(defs);

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');

    // Radial perspective lines radiating from horizon VP
    const radialCount = 16;
    for (let i = 0; i <= radialCount; i++) {
      const targetX = -200 + (W + 400) * (i / radialCount);
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', vpX);
      line.setAttribute('y1', vpY);
      line.setAttribute('x2', targetX);
      line.setAttribute('y2', 1400);
      line.setAttribute('stroke', 'url(#radialFade)');
      line.setAttribute('stroke-width', i % 4 === 0 ? '2.0' : '1.2');
      g.appendChild(line);
    }

    // Transverse horizontal grid lines moving towards camera with time t
    const speed = 0.18; // Normalized cycle per second
    const lineCount = 14;
    for (let j = 0; j < lineCount; j++) {
      const basePhase = j / lineCount;
      const s = (basePhase + t * speed) % 1.0; // 0 (horizon) to 1 (near bottom)
      // Exponential perspective spacing: y expands as s approaches 1
      const yLine = vpY + (1360 - vpY) * Math.pow(s, 1.85);

      if (yLine > vpY + 15) {
        // Line spreads wider at bottom
        const spreadFactor = Math.pow(s, 1.2);
        const xLeft = vpX - (W * 0.75) * spreadFactor;
        const xRight = vpX + (W * 0.75) * spreadFactor;

        const hLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        hLine.setAttribute('x1', xLeft);
        hLine.setAttribute('y1', yLine);
        hLine.setAttribute('x2', xRight);
        hLine.setAttribute('y2', yLine);

        // Opacity increases as lines come closer to camera, then fades near bottom edge
        const alpha = Math.sin(s * Math.PI) * 0.28;
        hLine.setAttribute('stroke', s > 0.5 ? `rgba(0, 245, 212, ${alpha})` : `rgba(157, 78, 221, ${alpha})`);
        hLine.setAttribute('stroke-width', (1.0 + s * 1.5).toFixed(1));
        g.appendChild(hLine);
      }
    }

    svg.appendChild(g);
    container.appendChild(svg);
    parent.appendChild(container);
  }

  // 2. Parallax Depth Dust/Stars (3 tầng hạt ánh sáng)
  function renderParallaxParticles(parent, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;

    const container = document.createElement('div');
    container.className = 'depth-parallax-container';
    container.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;pointer-events:none;overflow:hidden;z-index:3;`;

    // Tier 1: Far dust (25 particles, slow 12px/s)
    const farCount = 20;
    for (let i = 0; i < farCount; i++) {
      const seedX = ((i * 137.5) % W);
      const seedY = ((i * 269.3) % H);
      const speed = 14;
      const curY = (seedY + t * speed) % H;

      const star = document.createElement('div');
      star.className = 'depth-star far';
      const sz = 1.5 + (i % 2);
      star.style.cssText = `left:${seedX.toFixed(1)}px;top:${curY.toFixed(1)}px;width:${sz}px;height:${sz}px;background:rgba(200,180,255,0.45);`;
      container.appendChild(star);
    }

    // Tier 2: Mid glowing dust (12 particles, medium 35px/s)
    const midCount = 12;
    for (let i = 0; i < midCount; i++) {
      const seedX = ((i * 189.1 + 80) % (W - 160));
      const seedY = ((i * 311.7) % H);
      const speed = 36;
      const curY = (seedY + t * speed) % H;

      const star = document.createElement('div');
      star.className = 'depth-star mid';
      const sz = 3.0 + (i % 2);
      const isCyan = i % 2 === 0;
      star.style.cssText = `left:${seedX.toFixed(1)}px;top:${curY.toFixed(1)}px;width:${sz}px;height:${sz}px;background:${isCyan ? '#00f5d4' : '#c77dff'};box-shadow:0 0 8px ${isCyan ? 'rgba(0,245,212,0.7)' : 'rgba(199,125,255,0.7)'};`;
      container.appendChild(star);
    }

    // Tier 3: Near foreground bokeh particles (5 particles, fast 75px/s, depth blurred)
    const nearCount = 5;
    for (let i = 0; i < nearCount; i++) {
      const seedX = (120 + (i * 210.3) % (W - 240));
      const seedY = ((i * 419.5) % H);
      const speed = 75;
      const curY = (seedY + t * speed) % H;

      const star = document.createElement('div');
      star.className = 'depth-star near';
      const sz = 6.0;
      star.style.cssText = `left:${seedX.toFixed(1)}px;top:${curY.toFixed(1)}px;width:${sz}px;height:${sz}px;background:#ffffff;box-shadow:0 0 14px rgba(0,245,212,0.9),0 0 5px #fff;filter:blur(0.8px);`;
      container.appendChild(star);
    }

    parent.appendChild(container);
  }

  // 3. ELEMENT 1: bar_compare 3D (Cột khối lập thể mọc lên có 3 mặt + bóng tiếp xúc)
  function renderBarCompare3D(parent, shotData, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;

    const data = shotData.data || {};
    const rawBars = data.bars || [
      { label: "Giải pháp A", value: 45, unit: "%" },
      { label: "Giải pháp B", value: 88, unit: "%" },
      { label: "Giải pháp C", value: 62, unit: "%" }
    ];

    const stage = document.createElement('div');
    stage.className = 'depth-stage-wrapper';
    stage.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;z-index:10;`;

    const world = document.createElement('div');
    world.className = 'depth-world';

    // SVG container for sharp isometric 3D bars
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;';

    // Gradients for 3-face lighting
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    defs.innerHTML = `
      <linearGradient id="barGlowA" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#9d4edd" />
        <stop offset="100%" stop-color="#5a189a" />
      </linearGradient>
      <linearGradient id="barGlowB" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#00f5d4" />
        <stop offset="100%" stop-color="#0096c7" />
      </linearGradient>
      <linearGradient id="barGlowC" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#f72585" />
        <stop offset="100%" stop-color="#b5179e" />
      </linearGradient>
      <filter id="shadowFilter" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur in="SourceAlpha" stdDeviation="6" />
        <feColorMatrix type="matrix" values="0 0 0 0 0   0 0 0 0 0   0 0 0 0 0  0 0 0 0.7 0" />
        <feOffset dx="0" dy="6" />
        <feBlend in="SourceGraphic" in2="blurOut" mode="normal" />
      </filter>
    `;
    svg.appendChild(defs);

    const barCount = rawBars.length;
    const spacing = Math.min(260, (840 / Math.max(1, barCount)));
    const totalWidth = (barCount - 1) * spacing;
    const startX = 540 - totalWidth / 2;
    const baseY = 1180; // Baseline on floor
    const maxBarH = 500;
    const barWidth = Math.min(170, spacing * 0.75);
    const depthExtrusion = 45; // 3D depth

    const colors = [
      { base: "#9d4edd", top: "#c77dff", left: "#9d4edd", right: "#5a189a", accent: "#c77dff" },
      { base: "#00f5d4", top: "#70fff0", left: "#00f5d4", right: "#0096c7", accent: "#00f5d4" },
      { base: "#f72585", top: "#ff70a6", left: "#f72585", right: "#9b1158", accent: "#ff70a6" },
      { base: "#ffd166", top: "#ffe599", left: "#ffd166", right: "#cc9a06", accent: "#ffd166" }
    ];

    // Find highest value for crown / big stat highlight
    let maxVal = -Infinity;
    rawBars.forEach(b => { if (b.value > maxVal) maxVal = b.value; });

    rawBars.forEach((bar, idx) => {
      const col = colors[idx % colors.length];
      const cx = startX + idx * spacing;
      const targetH = Math.max(90, (bar.value / 100) * maxBarH);

      // Animation stagger
      const startT = 0.25 + idx * 0.16;
      const u = clamp((t - startT) / 0.85, 0, 1);
      const easeU = easeOutBack(u);
      const curH = targetH * easeU;

      // 1. Contact shadow under each bar base
      const shadowGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      const shadowElip = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
      shadowElip.setAttribute('cx', cx + depthExtrusion * 0.35);
      shadowElip.setAttribute('cy', baseY + 18);
      shadowElip.setAttribute('rx', barWidth * 0.70);
      shadowElip.setAttribute('ry', 22);
      shadowElip.setAttribute('fill', 'rgba(3, 1, 8, 0.78)');
      shadowElip.setAttribute('filter', 'url(#shadowFilter)');
      shadowElip.setAttribute('opacity', Math.min(1.0, u * 1.5).toFixed(2));
      shadowGroup.appendChild(shadowElip);
      svg.appendChild(shadowGroup);

      // 2. 3D Isometric Bar Cuboid
      const barGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      barGroup.setAttribute('opacity', clamp(u * 2.0, 0, 1).toFixed(2));

      // Isometric projection shifts:
      // Front face: width = barWidth, height = curH
      // Side face (Right face, shaded): extends right-up by dx, dy
      const dx = depthExtrusion * 0.70;
      const dy = -depthExtrusion * 0.45;

      const x0 = cx - barWidth / 2;
      const x1 = cx + barWidth / 2;
      const yBottom = baseY;
      const yTop = baseY - curH;

      // Front Face (Left-facing relative to light)
      const frontFace = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      frontFace.setAttribute('points', `${x0},${yBottom} ${x1},${yBottom} ${x1},${yTop} ${x0},${yTop}`);
      frontFace.setAttribute('fill', col.left);
      frontFace.setAttribute('stroke', 'rgba(255,255,255,0.25)');
      frontFace.setAttribute('stroke-width', '1.5');
      barGroup.appendChild(frontFace);

      // Right Face (Shaded, -28% brightness)
      const rightFace = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      rightFace.setAttribute('points', `${x1},${yBottom} ${x1 + dx},${yBottom + dy} ${x1 + dx},${yTop + dy} ${x1},${yTop}`);
      rightFace.setAttribute('fill', col.right);
      rightFace.setAttribute('stroke', 'rgba(0,0,0,0.3)');
      rightFace.setAttribute('stroke-width', '1.5');
      barGroup.appendChild(rightFace);

      // Top Face (Lightest, +18% brightness with specular edge)
      const topFace = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      topFace.setAttribute('points', `${x0},${yTop} ${x1},${yTop} ${x1 + dx},${yTop + dy} ${x0 + dx},${yTop + dy}`);
      topFace.setAttribute('fill', col.top);
      topFace.setAttribute('stroke', '#ffffff');
      topFace.setAttribute('stroke-width', '2.5');
      topFace.style.cssText = `filter:drop-shadow(0 0 8px ${col.accent});`;
      barGroup.appendChild(topFace);

      svg.appendChild(barGroup);

      // 3. Stat Number & Label Overlay (HTML for crisp typography & unskew)
      const isHero = (bar.value === maxVal);
      const displayVal = Math.round(bar.value * clamp(u * 1.05, 0, 1));

      // Number badge floating over top face
      const numDiv = document.createElement('div');
      numDiv.className = 'depth-label-text';
      numDiv.style.cssText = `
        position:absolute;
        left:${(cx - 100).toFixed(1)}px;
        top:${(yTop + dy - (isHero ? 140 : 100)).toFixed(1)}px;
        width:200px;
        text-align:center;
        color:${isHero ? '#ffffff' : col.accent};
        font-size:${isHero ? '110px' : '76px'};
        font-weight:900;
        line-height:1;
        opacity:${clamp((u - 0.2) * 1.6, 0, 1).toFixed(2)};
        transform:scale(${clamp(0.6 + u * 0.4, 0, 1)});
        text-shadow:0 0 16px ${col.accent}, 0 4px 12px rgba(0,0,0,0.9);
      `;
      numDiv.innerHTML = `${displayVal}<span style="font-size:${isHero ? '48px' : '36px'};margin-left:4px;">${bar.unit || '%'}</span>`;
      world.appendChild(numDiv);

      // Bar Label below base on floor
      const labelDiv = document.createElement('div');
      labelDiv.className = 'depth-label-text';
      labelDiv.style.cssText = `
        position:absolute;
        left:${(cx - 120).toFixed(1)}px;
        top:${(baseY + 32).toFixed(1)}px;
        width:240px;
        text-align:center;
        color:#e2e8f0;
        font-size:36px;
        font-weight:700;
        line-height:1.2;
        opacity:${clamp((u - 0.4) * 2.0, 0, 1).toFixed(2)};
      `;
      labelDiv.textContent = bar.label;
      world.appendChild(labelDiv);
    });

    stage.appendChild(svg);
    stage.appendChild(world);
    parent.appendChild(stage);
  }

  // 4. ELEMENT 2: gauge_ring 3D (Vòng đo 3D nghiêng phối cảnh có độ dày thành + phát sáng)
  function renderGaugeRing3D(parent, shotData, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;

    const data = shotData.data || {};
    const targetVal = data.value !== undefined ? data.value : 85;
    const unit = data.unit || '%';
    const label = data.label || 'Tỷ lệ tối ưu hoá';
    const subtext = data.text || 'Độ tin cậy hạ tầng';

    const stage = document.createElement('div');
    stage.className = 'depth-stage-wrapper';
    stage.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;z-index:10;`;

    const world = document.createElement('div');
    world.className = 'depth-world';

    const cx = 540;
    const cy = 760; // Content vertical center

    // Animation progress
    const u = clamp((t - 0.2) / 1.5, 0, 1);
    const easeU = easeOutCubic(u);
    const curVal = Math.round(targetVal * easeU);

    // SVG for 3D tilted concentric ring
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;';

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    defs.innerHTML = `
      <linearGradient id="ringNeonSweep" x1="0" y1="1" x2="1" y2="0">
        <stop offset="0%" stop-color="#9d4edd" />
        <stop offset="50%" stop-color="#00f5d4" />
        <stop offset="100%" stop-color="#70fff0" />
      </linearGradient>
      <filter id="gaugeShadow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur in="SourceAlpha" stdDeviation="8" />
        <feColorMatrix type="matrix" values="0 0 0 0 0   0 0 0 0 0   0 0 0 0 0  0 0 0 0.8 0" />
      </filter>
    `;
    svg.appendChild(defs);

    // 1. Contact shadow on floor below tilted ring
    const shadowElip = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
    shadowElip.setAttribute('cx', cx);
    shadowElip.setAttribute('cy', cy + 220);
    shadowElip.setAttribute('rx', 340);
    shadowElip.setAttribute('ry', 95);
    shadowElip.setAttribute('fill', 'rgba(3, 1, 8, 0.85)');
    shadowElip.setAttribute('filter', 'url(#gaugeShadow)');
    shadowElip.setAttribute('opacity', clamp(u * 1.5, 0, 1).toFixed(2));
    svg.appendChild(shadowElip);

    // 2. 3D Ring Extrusion geometry
    // Tilted ellipse: rx = 270, ry = 145 (tilt ~58°), depth extrusion dy = 42
    const rxOuter = 270;
    const ryOuter = 145;
    const rxInner = 195;
    const ryInner = 105;
    const extrusion = 42;

    const ringGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');

    // Bottom Base Wall (Extrusion depth skirt)
    const skirtPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    // Draw outer curved cylinder side from left (-rx) through bottom (+ry) to right (+rx)
    const skirtD = `
      M ${cx - rxOuter},${cy}
      A ${rxOuter} ${ryOuter} 0 0 0 ${cx + rxOuter},${cy}
      L ${cx + rxOuter},${cy + extrusion}
      A ${rxOuter} ${ryOuter} 0 0 1 ${cx - rxOuter},${cy + extrusion}
      Z
    `;
    skirtPath.setAttribute('d', skirtD);
    skirtPath.setAttribute('fill', '#12072b');
    skirtPath.setAttribute('stroke', '#5a189a');
    skirtPath.setAttribute('stroke-width', '2');
    ringGroup.appendChild(skirtPath);

    // Track Background (Dark groove)
    const trackRing = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const trackD = `
      M ${cx - rxOuter},${cy}
      A ${rxOuter} ${ryOuter} 0 1 1 ${cx + rxOuter},${cy}
      A ${rxOuter} ${ryOuter} 0 1 1 ${cx - rxOuter},${cy}
      M ${cx - rxInner},${cy}
      A ${rxInner} ${ryInner} 0 1 0 ${cx + rxInner},${cy}
      A ${rxInner} ${ryInner} 0 1 0 ${cx - rxInner},${cy}
      Z
    `;
    trackRing.setAttribute('d', trackD);
    trackRing.setAttribute('fill', 'rgba(18, 11, 40, 0.90)');
    trackRing.setAttribute('stroke', 'rgba(157, 78, 221, 0.40)');
    trackRing.setAttribute('stroke-width', '2.5');
    ringGroup.appendChild(trackRing);

    // Active Glowing Arc Sweep (Extruded neon arc)
    // Draw arc using stroke-dasharray on mid-ellipse
    const rxMid = (rxOuter + rxInner) / 2;
    const ryMid = (ryOuter + ryInner) / 2;
    const strokeWidth = (rxOuter - rxInner) * 0.92;
    const perimeter = Math.PI * (3 * (rxMid + ryMid) - Math.sqrt((3 * rxMid + ryMid) * (rxMid + 3 * ryMid)));

    const arcSweep = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
    arcSweep.setAttribute('cx', cx);
    arcSweep.setAttribute('cy', cy);
    arcSweep.setAttribute('rx', rxMid);
    arcSweep.setAttribute('ry', ryMid);
    arcSweep.setAttribute('fill', 'none');
    arcSweep.setAttribute('stroke', 'url(#ringNeonSweep)');
    arcSweep.setAttribute('stroke-width', strokeWidth);
    arcSweep.setAttribute('stroke-linecap', 'round');

    const sweepAngleRatio = (targetVal / 100) * 0.85; // 85% of full circle
    const activeLength = perimeter * sweepAngleRatio * easeU;
    arcSweep.setAttribute('stroke-dasharray', `${activeLength.toFixed(1)} ${perimeter.toFixed(1)}`);
    arcSweep.setAttribute('stroke-dashoffset', (-perimeter * 0.25).toFixed(1)); // Start from bottom-left
    arcSweep.style.cssText = 'filter:drop-shadow(0 0 12px rgba(0, 245, 212, 0.75));';
    ringGroup.appendChild(arcSweep);

    // Specular Highlight Edge on Top Rim
    const topRim = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
    topRim.setAttribute('cx', cx);
    topRim.setAttribute('cy', cy);
    topRim.setAttribute('rx', rxOuter);
    topRim.setAttribute('ry', ryOuter);
    topRim.setAttribute('fill', 'none');
    topRim.setAttribute('stroke', 'rgba(255, 255, 255, 0.35)');
    topRim.setAttribute('stroke-width', '2');
    ringGroup.appendChild(topRim);

    svg.appendChild(ringGroup);

    // 3. Center Stat & Typography (Unskewed, upright for optimal legibility)
    const centerDiv = document.createElement('div');
    centerDiv.className = 'depth-label-text';
    centerDiv.style.cssText = `
      position:absolute;
      left:${(cx - 200).toFixed(1)}px;
      top:${(cy - 95).toFixed(1)}px;
      width:400px;
      text-align:center;
      pointer-events:none;
    `;

    const hugeNum = document.createElement('div');
    hugeNum.className = 'depth-huge-stat';
    hugeNum.style.cssText = `
      font-size:140px;
      color:#ffffff;
      text-shadow:0 0 20px rgba(0, 245, 212, 0.8), 0 6px 18px rgba(0,0,0,0.9);
      opacity:${clamp(u * 1.8, 0, 1).toFixed(2)};
      transform:scale(${clamp(0.7 + u * 0.3, 0, 1)});
    `;
    hugeNum.innerHTML = `${curVal}<span style="font-size:56px;color:#00f5d4;margin-left:4px;">${unit}</span>`;
    centerDiv.appendChild(hugeNum);

    // Label below stat
    const labelEl = document.createElement('div');
    labelEl.style.cssText = `
      font-size:38px;
      font-weight:700;
      color:#e2e8f0;
      margin-top:12px;
      text-shadow:0 3px 10px rgba(0,0,0,0.9);
      opacity:${clamp((u - 0.2) * 2.0, 0, 1).toFixed(2)};
    `;
    labelEl.textContent = label;
    centerDiv.appendChild(labelEl);

    // Subtitle note
    if (subtext) {
      const subEl = document.createElement('div');
      subEl.style.cssText = `
        font-size:28px;
        font-weight:600;
        color:#00f5d4;
        margin-top:6px;
        opacity:${clamp((u - 0.4) * 2.0, 0, 1).toFixed(2)};
      `;
      subEl.textContent = subtext;
      centerDiv.appendChild(subEl);
    }

    world.appendChild(centerDiv);

    stage.appendChild(svg);
    stage.appendChild(world);
    parent.appendChild(stage);
  }

  // 5. ELEMENT 3: versus_split 3D (Hai khối dày đối đầu có nghiêng phối cảnh + Huy hiệu VS nổi)
  function renderVersusSplit3D(parent, shotData, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;

    const data = shotData.data || {};
    const bars = data.bars || [
      { label: "Giải pháp Cũ", value: 35, unit: "%" },
      { label: "Kiến trúc Mới", value: 92, unit: "%" }
    ];

    const leftData = bars[0] || { label: "Phe A", value: 40 };
    const rightData = bars[1] || { label: "Phe B", value: 85 };

    const stage = document.createElement('div');
    stage.className = 'depth-stage-wrapper';
    stage.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;z-index:10;`;

    const world = document.createElement('div');
    world.className = 'depth-world';

    const cy = 780; // Content vertical center

    // Slamming animation: cards rush in from left and right and clash at t = 0.8s
    const clashT = 0.75;
    const isClashed = t >= clashT;
    const uIn = clamp(t / clashT, 0, 1);
    const easeIn = easeOutBack(uIn);

    // Left slab position (Team Cyan #00f5d4)
    const targetLeftX = 90;
    const curLeftX = -420 + (targetLeftX - (-420)) * easeIn;

    // Right slab position (Team Magenta #f72585)
    const targetRightX = 570;
    const curRightX = 1120 + (targetRightX - 1120) * easeIn;

    const slabW = 420;
    const slabH = 460;
    const slabY = cy - slabH / 2;

    // Shake recoil after clash
    let shakeX = 0;
    let shakeY = 0;
    if (t > clashT && t < clashT + 0.4) {
      const shakeDecay = 1 - (t - clashT) / 0.4;
      shakeX = Math.sin((t - clashT) * 45) * 5 * shakeDecay;
      shakeY = Math.cos((t - clashT) * 45) * 4 * shakeDecay;
    }

    // SVG for contact shadows under both slabs
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;';

    const leftShadow = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
    leftShadow.setAttribute('cx', curLeftX + slabW / 2 + 15);
    leftShadow.setAttribute('cy', slabY + slabH + 30);
    leftShadow.setAttribute('rx', slabW * 0.48);
    leftShadow.setAttribute('ry', 35);
    leftShadow.setAttribute('fill', 'rgba(3, 1, 8, 0.80)');
    leftShadow.setAttribute('filter', 'drop-shadow(0 0 10px rgba(0,0,0,0.8))');
    svg.appendChild(leftShadow);

    const rightShadow = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
    rightShadow.setAttribute('cx', curRightX + slabW / 2 - 15);
    rightShadow.setAttribute('cy', slabY + slabH + 30);
    rightShadow.setAttribute('rx', slabW * 0.48);
    rightShadow.setAttribute('ry', 35);
    rightShadow.setAttribute('fill', 'rgba(3, 1, 8, 0.80)');
    rightShadow.setAttribute('filter', 'drop-shadow(0 0 10px rgba(0,0,0,0.8))');
    svg.appendChild(rightShadow);

    stage.appendChild(svg);

    // Left Slab (Team Cyan) — tilted rotateY(-9deg)
    const leftSlab = document.createElement('div');
    leftSlab.className = 'depth-card-panel cuboid-3d';
    leftSlab.style.cssText = `
      left:${(curLeftX + shakeX).toFixed(1)}px;
      top:${(slabY + shakeY).toFixed(1)}px;
      width:${slabW}px;
      height:${slabH}px;
      border:3px solid #00f5d4;
      background:linear-gradient(145deg, rgba(14,24,38,0.95) 0%, rgba(6,12,22,0.98) 100%);
      box-shadow:0 25px 50px rgba(0,0,0,0.8), 0 0 25px rgba(0,245,212,0.35);
      transform:perspective(1200px) rotateY(-8deg) translateZ(-20px);
      padding:40px 30px;
      box-sizing:border-box;
      display:flex;
      flex-direction:column;
      justify-content:space-between;
    `;
    leftSlab.innerHTML = `
      <div>
        <div style="font-size:30px;color:#00f5d4;font-weight:800;letter-spacing:1px;text-transform:uppercase;">PHƯƠNG ÁN 1</div>
        <div style="font-size:42px;color:#ffffff;font-weight:800;margin-top:10px;line-height:1.2;">${leftData.label}</div>
      </div>
      <div>
        <div style="font-size:96px;font-weight:900;color:#00f5d4;line-height:1;text-shadow:0 0 16px rgba(0,245,212,0.6);">${leftData.value}<span style="font-size:40px;margin-left:4px;">${leftData.unit || '%'}</span></div>
      </div>
    `;
    world.appendChild(leftSlab);

    // Right Slab (Team Magenta) — tilted rotateY(+9deg)
    const rightSlab = document.createElement('div');
    rightSlab.className = 'depth-card-panel cuboid-3d';
    rightSlab.style.cssText = `
      left:${(curRightX - shakeX).toFixed(1)}px;
      top:${(slabY - shakeY).toFixed(1)}px;
      width:${slabW}px;
      height:${slabH}px;
      border:3px solid #f72585;
      background:linear-gradient(145deg, rgba(38,12,26,0.95) 0%, rgba(20,5,14,0.98) 100%);
      box-shadow:0 25px 50px rgba(0,0,0,0.8), 0 0 25px rgba(247,37,133,0.35);
      transform:perspective(1200px) rotateY(8deg) translateZ(-20px);
      padding:40px 30px;
      box-sizing:border-box;
      display:flex;
      flex-direction:column;
      justify-content:space-between;
    `;
    rightSlab.innerHTML = `
      <div>
        <div style="font-size:30px;color:#f72585;font-weight:800;letter-spacing:1px;text-transform:uppercase;">PHƯƠNG ÁN 2</div>
        <div style="font-size:42px;color:#ffffff;font-weight:800;margin-top:10px;line-height:1.2;">${rightData.label}</div>
      </div>
      <div>
        <div style="font-size:96px;font-weight:900;color:#f72585;line-height:1;text-shadow:0 0 16px rgba(247,37,133,0.6);">${rightData.value}<span style="font-size:40px;margin-left:4px;">${rightData.unit || '%'}</span></div>
      </div>
    `;
    world.appendChild(rightSlab);

    // Floating 3D "VS" Badge (Pop out towards camera translateZ +70px)
    const vsBadge = document.createElement('div');
    vsBadge.className = 'versus-3d-badge';

    const vsScale = isClashed
      ? clamp(1.0 + Math.sin((t - clashT) * 12) * 0.15 * Math.exp(-(t - clashT) * 4), 0.9, 1.25)
      : clamp(uIn * 0.8, 0, 1);

    vsBadge.style.cssText = `
      left:${(540 - 70).toFixed(1)}px;
      top:${(cy - 70).toFixed(1)}px;
      transform:perspective(1000px) translateZ(75px) scale(${vsScale});
      opacity:${clamp(uIn * 2.0, 0, 1).toFixed(2)};
      z-index:25;
    `;
    vsBadge.textContent = 'VS';
    world.appendChild(vsBadge);

    stage.appendChild(world);
    parent.appendChild(stage);
  }

  // Camera 3D Rig: Dolly, Pan, Tilt, Orbit and Impact Bump with strict safe bounds
  function applyDepthCamera(world, cameraSpec, t, duration) {
    if (!world) return;
    cameraSpec = cameraSpec || {};
    const move = cameraSpec.move || 'push_in';
    const amount = clamp(cameraSpec.amount || 0.05, 0, 0.10);
    const dur = Math.max(0.1, duration || 4.0);
    const u = clamp(t / dur, 0, 1);
    const easeU = easeInOutQuad(u);

    let scale = 1.0;
    let transZ = 0;
    let panX = 0;
    let panY = 0;
    let rotX = 0;
    let rotY = 0;

    switch (move) {
      case 'push_in':
      case 'dolly_in':
      case 'zoom_in':
        scale = 1.0 + amount * easeU;
        transZ = 35 * easeU;
        break;
      case 'pull_out':
      case 'dolly_out':
      case 'zoom_out':
        scale = (1.0 + amount) - amount * easeU;
        transZ = 35 * (1 - easeU);
        break;
      case 'pan_left':
        panX = -28 * easeU;
        rotY = 3 * easeU;
        break;
      case 'pan_right':
        panX = 28 * easeU;
        rotY = -3 * easeU;
        break;
      case 'orbit':
        rotY = Math.sin(u * Math.PI * 2) * 4;
        rotX = Math.cos(u * Math.PI * 2) * 2;
        break;
      default:
        scale = 1.0 + 0.03 * easeU;
        transZ = 15 * easeU;
        break;
    }

    // Impact bump if specified
    if (cameraSpec.impact_bump && t >= cameraSpec.impact_bump) {
      const dt = t - cameraSpec.impact_bump;
      if (dt >= 0 && dt < 0.3) {
        const decay = 1 - dt / 0.3;
        panY += Math.sin(dt * 60) * 5 * decay;
      }
    }

    // Strict safety clamp: prevent clipping into safe zone [70, 1010] x [240, 1330]
    panX = clamp(panX, -30, 30);
    panY = clamp(panY, -20, 20);
    rotX = clamp(rotX, -6, 6);
    rotY = clamp(rotY, -6, 6);

    world.style.transform = `translate3d(${panX.toFixed(1)}px, ${panY.toFixed(1)}px, ${transZ.toFixed(1)}px) scale(${scale.toFixed(3)}) rotateX(${rotX.toFixed(1)}deg) rotateY(${rotY.toFixed(1)}deg)`;
  }

  // 6. ELEMENT 4: hub_spoke / network_nodes 3D
  // Nút trung tâm 3D, các nút vệ tinh quay trên quỹ đạo nghiêng 58°, tia nối có nhiều gói file chạy liên tục, sóng quét highlight tuần hoàn
  function renderHubSpoke3D(parent, shotData, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;
    const data = shotData.data || {};

    const centerLabel = data.center_label || data.title || "HẠ TẦNG";
    const rawSatellites = data.satellites || data.nodes || [
      { label: "Bảo mật", value: "99.9%" },
      { label: "Tốc độ", value: "<15ms" },
      { label: "Dung lượng", value: "10 Gbps" },
      { label: "Mở rộng", value: "Tự động" }
    ];

    const stage = document.createElement('div');
    stage.className = 'depth-stage-wrapper';
    stage.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;z-index:10;`;

    const world = document.createElement('div');
    world.className = 'depth-world';

    const cx = 540;
    const cy = 760; // Content vertical center

    // Camera 3D
    applyDepthCamera(world, shotData.camera || { move: 'dolly_in', amount: 0.04 }, t, options.duration || 4.0);

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;';

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    defs.innerHTML = `
      <linearGradient id="hubBeamGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#00f5d4" stop-opacity="0.9" />
        <stop offset="100%" stop-color="#9d4edd" stop-opacity="0.4" />
      </linearGradient>
      <filter id="hubGlow" x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur in="SourceAlpha" stdDeviation="6" />
        <feColorMatrix type="matrix" values="0 0 0 0 0   0 0 0 0 0   0 0 0 0 0  0 0 0 0.85 0" />
      </filter>
    `;
    svg.appendChild(defs);

    // 1. Shadow for center hub on floor
    const centerShadow = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
    centerShadow.setAttribute('cx', cx);
    centerShadow.setAttribute('cy', cy + 130);
    centerShadow.setAttribute('rx', 180);
    centerShadow.setAttribute('ry', 45);
    centerShadow.setAttribute('fill', 'rgba(3, 1, 8, 0.85)');
    centerShadow.setAttribute('filter', 'url(#hubGlow)');
    svg.appendChild(centerShadow);

    // 2. Orbit Ring Track in 3D perspective (tilted ~58°)
    const rxOrbit = 360;
    const ryOrbit = 175;
    const orbitTrack = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
    orbitTrack.setAttribute('cx', cx);
    orbitTrack.setAttribute('cy', cy);
    orbitTrack.setAttribute('rx', rxOrbit);
    orbitTrack.setAttribute('ry', ryOrbit);
    orbitTrack.setAttribute('fill', 'none');
    orbitTrack.setAttribute('stroke', 'rgba(157, 78, 221, 0.25)');
    orbitTrack.setAttribute('stroke-width', '2');
    orbitTrack.setAttribute('stroke-dasharray', '8 6');
    svg.appendChild(orbitTrack);

    // Compute satellite positions on tilted 3D orbit
    const satCount = Math.min(5, Math.max(3, rawSatellites.length));
    const activeSatIdx = Math.floor((t * 0.9) % satCount);

    const satPositions = [];
    for (let i = 0; i < satCount; i++) {
      // Rotation angle with slow drift over time t
      const angle = (i / satCount) * Math.PI * 2 + (t * 0.15) - Math.PI / 2;
      const sx = cx + rxOrbit * Math.cos(angle);
      const sy = cy + ryOrbit * Math.sin(angle);
      satPositions.push({ x: sx, y: sy, angle: angle, idx: i });
    }

    // 3. Connectors & Streaming Data Packets
    satPositions.forEach(sat => {
      // Beam line
      const beam = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      beam.setAttribute('x1', cx);
      beam.setAttribute('y1', cy);
      beam.setAttribute('x2', sat.x);
      beam.setAttribute('y2', sat.y);
      beam.setAttribute('stroke', 'url(#hubBeamGrad)');
      beam.setAttribute('stroke-width', sat.idx === activeSatIdx ? '3.5' : '1.8');
      beam.setAttribute('stroke-opacity', sat.idx === activeSatIdx ? '0.95' : '0.5');
      svg.appendChild(beam);

      // Multiple packets traveling along the beam
      const packetCount = 2;
      for (let p = 0; p < packetCount; p++) {
        const pPhase = (t * 1.1 + p * 0.5 + sat.idx * 0.25) % 1.0;
        const px = cx + (sat.x - cx) * pPhase;
        const py = cy + (sat.y - cy) * pPhase;

        const packet = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        packet.setAttribute('cx', px);
        packet.setAttribute('cy', py);
        packet.setAttribute('r', sat.idx === activeSatIdx ? '5.5' : '4');
        packet.setAttribute('fill', sat.idx === activeSatIdx ? '#ffffff' : '#00f5d4');
        packet.style.cssText = 'filter:drop-shadow(0 0 6px #00f5d4);';
        svg.appendChild(packet);
      }
    });

    stage.appendChild(svg);

    // 4. Center 3D Hub Node (Layered 3D Cylinder/Disc)
    const hubNode = document.createElement('div');
    hubNode.className = 'hub-spoke-center-3d cuboid-3d';
    hubNode.style.cssText = `
      left:${(cx - 110).toFixed(1)}px;
      top:${(cy - 110).toFixed(1)}px;
      width:220px;
      height:220px;
      border-radius:50%;
      background:linear-gradient(135deg, rgba(30,15,60,0.95) 0%, rgba(12,5,25,0.98) 100%);
      border:3px solid #00f5d4;
      box-shadow:0 0 35px rgba(0,245,212,0.45), 0 20px 40px rgba(0,0,0,0.85);
      transform:perspective(1200px) rotateX(24deg) translateZ(40px);
      z-index:20;
    `;
    hubNode.innerHTML = `
      <div style="font-size:24px;color:#00f5d4;font-weight:800;letter-spacing:1px;text-transform:uppercase;">NÚT CHÍNH</div>
      <div style="font-size:38px;color:#ffffff;font-weight:900;margin-top:6px;line-height:1.1;">${centerLabel}</div>
    `;
    world.appendChild(hubNode);

    // 5. Satellite 3D Nodes
    satPositions.forEach(sat => {
      const item = rawSatellites[sat.idx];
      const isActive = (sat.idx === activeSatIdx);
      const satW = 180;
      const satH = 95;

      const satNode = document.createElement('div');
      satNode.className = 'satellite-node-3d cuboid-3d';
      satNode.style.cssText = `
        left:${(sat.x - satW / 2).toFixed(1)}px;
        top:${(sat.y - satH / 2).toFixed(1)}px;
        width:${satW}px;
        height:${satH}px;
        background:${isActive ? 'linear-gradient(135deg, rgba(38,15,65,0.95), rgba(20,5,35,0.98))' : 'rgba(18,11,40,0.90)'};
        border:2.5px solid ${isActive ? '#00f5d4' : 'rgba(157,78,221,0.5)'};
        box-shadow:${isActive ? '0 0 25px rgba(0,245,212,0.6), 0 15px 30px rgba(0,0,0,0.8)' : '0 10px 25px rgba(0,0,0,0.6)'};
        transform:perspective(1200px) scale(${isActive ? '1.08' : '1.0'}) translateZ(${isActive ? '35px' : '0px'});
        transition:transform 0.3s ease, border-color 0.3s ease;
        padding:12px;
        z-index:18;
      `;

      // Truncate label to <= 3 words for safe legibility
      const words = (item.label || "").split(" ");
      const shortLabel = words.length > 3 ? words.slice(0, 3).join(" ") : item.label;

      satNode.innerHTML = `
        <div style="font-size:32px;font-weight:800;color:${isActive ? '#00f5d4' : '#e2e8f0'};line-height:1.1;">${shortLabel}</div>
        <div style="font-size:26px;font-weight:700;color:#c77dff;margin-top:4px;">${item.value || ''}</div>
      `;
      world.appendChild(satNode);
    });

    stage.appendChild(world);
    parent.appendChild(stage);
  }

  // 7. ELEMENT 5: checklist / steps_ladder 3D
  // Các tấm dày xếp bậc (3D stacked slabs) trồi lên lần lượt, tấm active nhô cao (Z+35px), ✓ nảy 3D
  function renderChecklist3D(parent, shotData, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;
    const data = shotData.data || {};

    const rawItems = data.items || data.steps || [
      { text: "Khởi tạo hạ tầng điện toán đám mây", checked: true },
      { text: "Đóng gói container Docker chuẩn hoá", checked: true },
      { text: "Cấu hình chứng chỉ bảo mật SSL", checked: true },
      { text: "Kích hoạt giám sát tự động 24/7", checked: true }
    ];

    const stage = document.createElement('div');
    stage.className = 'depth-stage-wrapper';
    stage.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;z-index:10;`;

    const world = document.createElement('div');
    world.className = 'depth-world';

    // Camera 3D
    applyDepthCamera(world, shotData.camera || { move: 'dolly_in', amount: 0.03 }, t, options.duration || 4.0);

    const itemCount = Math.min(4, rawItems.length);
    const slabW = 860;
    const slabH = 108;
    const gap = 24;
    const totalH = itemCount * slabH + (itemCount - 1) * gap;
    const startY = 785 - totalH / 2; // Center y around 785
    const slabX = 540 - slabW / 2;   // 110 (safe in [70, 1010])

    // Scan progression based on time t
    const activeIdx = clamp(Math.floor((t - 0.2) / 0.75), 0, itemCount - 1);

    rawItems.slice(0, itemCount).forEach((item, idx) => {
      const curY = startY + idx * (slabH + gap);
      const startT = 0.2 + idx * 0.25;
      const u = clamp((t - startT) / 0.6, 0, 1);
      const easeU = easeOutBack(u);

      const isChecked = (t >= startT + 0.35);
      const isActive = (idx === activeIdx);

      // Contact shadow behind each slab
      const shadowDiv = document.createElement('div');
      shadowDiv.className = 'depth-contact-shadow';
      shadowDiv.style.cssText = `
        left:${slabX + 20}px;
        top:${curY + slabH - 10}px;
        width:${slabW - 40}px;
        height:35px;
        opacity:${clamp(u * 1.5, 0, 0.85).toFixed(2)};
      `;
      world.appendChild(shadowDiv);

      // 3D Slab container
      const slab = document.createElement('div');
      slab.className = 'checklist-slab-3d cuboid-3d';

      const zHeight = isActive ? 35 : (isChecked ? 15 : 0);
      const rotX = 4; // slight tilt for 3D depth

      slab.style.cssText = `
        left:${slabX}px;
        top:${curY}px;
        width:${slabW}px;
        height:${slabH}px;
        background:${isActive ? 'linear-gradient(135deg, rgba(28,14,55,0.95) 0%, rgba(14,6,28,0.98) 100%)' : 'rgba(18,11,40,0.88)'};
        border:2.5px solid ${isActive ? '#00f5d4' : (isChecked ? '#9d4edd' : 'rgba(157,78,221,0.35)')};
        box-shadow:${isActive ? '0 20px 45px rgba(0,0,0,0.85), 0 0 25px rgba(0,245,212,0.45)' : '0 12px 30px rgba(0,0,0,0.65)'};
        transform:perspective(1200px) rotateX(${rotX}deg) translateZ(${zHeight}px) scale(${clamp(0.9 + easeU * 0.1, 0, 1)});
        opacity:${clamp(u * 2.0, 0, 1).toFixed(2)};
        padding:0 30px;
        z-index:${15 + idx};
      `;

      // Checkmark icon box with bounce animation
      const checkBounce = isChecked ? clamp((t - (startT + 0.35)) / 0.3, 0, 1) : 0;
      const checkScale = isChecked ? easeOutBack(checkBounce) : 0;

      const iconBox = document.createElement('div');
      iconBox.className = 'checklist-check-icon';
      iconBox.style.cssText = `
        width:56px;
        height:56px;
        border-radius:14px;
        background:${isChecked ? 'rgba(34, 197, 94, 0.2)' : 'rgba(255,255,255,0.06)'};
        border:2px solid ${isChecked ? '#22c55e' : 'rgba(255,255,255,0.2)'};
        margin-right:24px;
      `;

      if (isChecked) {
        iconBox.innerHTML = `
          <svg width="34" height="34" viewBox="0 0 24 24" style="transform:scale(${checkScale});filter:drop-shadow(0 0 6px #22c55e);">
            <path d="M5 13l4 4L19 7" fill="none" stroke="#22c55e" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        `;
      } else {
        iconBox.innerHTML = `
          <div style="width:12px;height:12px;border-radius:50%;background:rgba(255,255,255,0.3);"></div>
        `;
      }
      slab.appendChild(iconBox);

      // Label Text (>= 36px font size)
      const textDiv = document.createElement('div');
      textDiv.className = 'depth-label-text';
      textDiv.style.cssText = `
        font-size:38px;
        font-weight:700;
        color:${isActive ? '#ffffff' : (isChecked ? '#e2e8f0' : '#94a3b8')};
        line-height:1.2;
        flex:1;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
      `;
      textDiv.textContent = item.text || item.title || "";
      slab.appendChild(textDiv);

      world.appendChild(slab);
    });

    stage.appendChild(world);
    parent.appendChild(stage);
  }

  // 8. ELEMENT 6: stat_number 3D
  // Số lớn (>= 160px) có extrusion đa lớp (text-shadow sáng/tối 45°), bệ đỡ 3D và bóng tiếp xúc trên sàn
  function renderStatNumber3D(parent, shotData, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;
    const data = shotData.data || {};

    const targetVal = data.value !== undefined ? data.value : 85;
    const unit = data.unit || "%";
    const label = data.label || data.title || "TĂNG TRƯỞNG VƯỢT TRỘI";
    const subtext = data.subtext || data.text || "Đạt chuẩn hiệu năng cao";

    const stage = document.createElement('div');
    stage.className = 'depth-stage-wrapper';
    stage.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;z-index:10;`;

    const world = document.createElement('div');
    world.className = 'depth-world';

    const cx = 540;
    const cy = 760; // Content vertical center

    // Camera 3D
    applyDepthCamera(world, shotData.camera || { move: 'dolly_in', amount: 0.05 }, t, options.duration || 4.0);

    const u = clamp((t - 0.2) / 1.4, 0, 1);
    const easeU = easeOutBack(u);
    const curVal = Math.round(targetVal * easeU);

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;';

    // 1. Contact shadow on floor under 3D pedestal
    const pedestalY = cy + 130;
    const shadowElip = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
    shadowElip.setAttribute('cx', cx);
    shadowElip.setAttribute('cy', pedestalY + 35);
    shadowElip.setAttribute('rx', 340);
    shadowElip.setAttribute('ry', 75);
    shadowElip.setAttribute('fill', 'rgba(3, 1, 8, 0.85)');
    shadowElip.setAttribute('filter', 'drop-shadow(0 0 14px rgba(0,0,0,0.9))');
    shadowElip.setAttribute('opacity', clamp(u * 1.5, 0, 1).toFixed(2));
    svg.appendChild(shadowElip);

    // 2. 3D Pedestal Base (Extruded circular disc)
    const rxPed = 300;
    const ryPed = 85;
    const pedExtrusion = 32;

    const pedGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');

    // Bottom base wall
    const pedWall = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pedWall.setAttribute('d', `
      M ${cx - rxPed},${pedestalY}
      A ${rxPed} ${ryPed} 0 0 0 ${cx + rxPed},${pedestalY}
      L ${cx + rxPed},${pedestalY + pedExtrusion}
      A ${rxPed} ${ryPed} 0 0 1 ${cx - rxPed},${pedestalY + pedExtrusion}
      Z
    `);
    pedWall.setAttribute('fill', '#12072b');
    pedWall.setAttribute('stroke', '#5a189a');
    pedWall.setAttribute('stroke-width', '2');
    pedGroup.appendChild(pedWall);

    // Top face of pedestal
    const pedTop = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
    pedTop.setAttribute('cx', cx);
    pedTop.setAttribute('cy', pedestalY);
    pedTop.setAttribute('rx', rxPed);
    pedTop.setAttribute('ry', ryPed);
    pedTop.setAttribute('fill', 'linear-gradient(135deg, #1c0e38, #0e061c)');
    pedTop.setAttribute('stroke', '#00f5d4');
    pedTop.setAttribute('stroke-width', '2.5');
    pedTop.style.cssText = 'filter:drop-shadow(0 0 10px rgba(0, 245, 212, 0.5));';
    pedGroup.appendChild(pedTop);

    svg.appendChild(pedGroup);
    stage.appendChild(svg);

    // 3. Stat Number with 3D Multi-Layer Extrusion Text-Shadow
    const statContainer = document.createElement('div');
    statContainer.style.cssText = `
      position:absolute;
      left:${(cx - 380).toFixed(1)}px;
      top:${(cy - 230).toFixed(1)}px;
      width:760px;
      text-align:center;
      pointer-events:none;
      z-index:22;
    `;

    // Category / Top tag
    const topTag = document.createElement('div');
    topTag.style.cssText = `
      font-size:32px;
      font-weight:800;
      letter-spacing:2px;
      color:#00f5d4;
      text-transform:uppercase;
      opacity:${clamp(u * 2.0, 0, 1).toFixed(2)};
    `;
    topTag.textContent = label;
    statContainer.appendChild(topTag);

    // Hero 3D Number (>= 160px)
    const heroNum = document.createElement('div');
    heroNum.className = 'stat-extrusion-hero';
    heroNum.style.cssText = `
      font-size:175px;
      color:#ffffff;
      margin-top:5px;
      transform:scale(${clamp(0.65 + easeU * 0.35, 0, 1)});
      opacity:${clamp(u * 2.0, 0, 1).toFixed(2)};
      text-shadow:
        1px 1px 0 #00f5d4,
        2px 2px 0 #00e0c2,
        3px 3px 0 #00cbb0,
        4px 4px 0 #00b69e,
        5px 5px 0 #00a18c,
        6px 6px 0 #008c7a,
        7px 7px 0 #007768,
        8px 8px 16px rgba(0,0,0,0.9),
        0 0 25px rgba(0, 245, 212, 0.65);
    `;
    heroNum.innerHTML = `${curVal}<span style="font-size:68px;color:#00f5d4;margin-left:6px;">${unit}</span>`;
    statContainer.appendChild(heroNum);

    // Subtext note
    if (subtext) {
      const sub = document.createElement('div');
      sub.style.cssText = `
        font-size:36px;
        font-weight:700;
        color:#e2e8f0;
        margin-top:15px;
        opacity:${clamp((u - 0.2) * 2.0, 0, 1).toFixed(2)};
        text-shadow:0 3px 10px rgba(0,0,0,0.9);
      `;
      sub.textContent = subtext;
      statContainer.appendChild(sub);
    }

    world.appendChild(statContainer);
    stage.appendChild(world);
    parent.appendChild(stage);
  }

  // 9. ELEMENT 7: flow_chain 3D
  // Băng chuyền / đường nối 3D phối cảnh có các trạm khối hộp cuboids và gói file chạy liên tục
  function renderFlowChain3D(parent, shotData, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;
    const data = shotData.data || {};

    const rawSteps = data.steps || data.stages || [
      { label: "Tiếp nhận Dữ liệu", detail: "Phân luồng" },
      { label: "Xử lý Logic AI", detail: "Phân tích" },
      { label: "Xuất Kết quả", detail: "Tối ưu hoá" }
    ];

    const stage = document.createElement('div');
    stage.className = 'depth-stage-wrapper';
    stage.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;z-index:10;`;

    const world = document.createElement('div');
    world.className = 'depth-world';

    // Camera 3D
    applyDepthCamera(world, shotData.camera || { move: 'pan_right', amount: 0.04 }, t, options.duration || 4.0);

    const stepCount = Math.min(3, rawSteps.length);

    // 3D Isometric positions for stations (descending zic-zac along floor)
    const stationPositions = [
      { x: 190, y: 560, z: -20 },
      { x: 540, y: 770, z: 15 },
      { x: 890, y: 980, z: 50 }
    ];

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;';

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    defs.innerHTML = `
      <linearGradient id="flowPipeGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#9d4edd" />
        <stop offset="50%" stop-color="#00f5d4" />
        <stop offset="100%" stop-color="#ffd166" />
      </linearGradient>
    `;
    svg.appendChild(defs);

    // 1. Pipe Conduits between stations
    for (let i = 0; i < stepCount - 1; i++) {
      const p1 = stationPositions[i];
      const p2 = stationPositions[i + 1];

      // Base pipe
      const pipe = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      pipe.setAttribute('x1', p1.x);
      pipe.setAttribute('y1', p1.y);
      pipe.setAttribute('x2', p2.x);
      pipe.setAttribute('y2', p2.y);
      pipe.setAttribute('stroke', 'rgba(157, 78, 221, 0.4)');
      pipe.setAttribute('stroke-width', '6');
      svg.appendChild(pipe);

      // Glowing core pipe
      const corePipe = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      corePipe.setAttribute('x1', p1.x);
      corePipe.setAttribute('y1', p1.y);
      corePipe.setAttribute('x2', p2.x);
      corePipe.setAttribute('y2', p2.y);
      corePipe.setAttribute('stroke', 'url(#flowPipeGrad)');
      corePipe.setAttribute('stroke-width', '2.5');
      svg.appendChild(corePipe);

      // Continuous data packets streaming across pipe
      const packetCount = 3;
      for (let k = 0; k < packetCount; k++) {
        const prog = (t * 1.2 + k / packetCount) % 1.0;
        const px = p1.x + (p2.x - p1.x) * prog;
        const py = p1.y + (p2.y - p1.y) * prog;

        const packet = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        packet.setAttribute('cx', px);
        packet.setAttribute('cy', py);
        packet.setAttribute('r', '6');
        packet.setAttribute('fill', '#00f5d4');
        packet.style.cssText = 'filter:drop-shadow(0 0 8px #00f5d4);';
        svg.appendChild(packet);
      }
    }

    stage.appendChild(svg);

    // 2. Station Cuboids (3D Isometric Boxes)
    rawSteps.slice(0, stepCount).forEach((step, idx) => {
      const pos = stationPositions[idx];
      const stW = 240;
      const stH = 145;

      const u = clamp((t - idx * 0.25) / 0.6, 0, 1);
      const easeU = easeOutBack(u);

      // Contact shadow
      const shadowDiv = document.createElement('div');
      shadowDiv.className = 'depth-contact-shadow';
      shadowDiv.style.cssText = `
        left:${pos.x - stW / 2 + 15}px;
        top:${pos.y + stH / 2}px;
        width:${stW - 30}px;
        height:40px;
        opacity:${clamp(u * 1.5, 0, 0.85).toFixed(2)};
      `;
      world.appendChild(shadowDiv);

      // 3D Cuboid Station
      const cuboid = document.createElement('div');
      cuboid.className = 'flow-station-cuboid cuboid-3d';
      cuboid.style.cssText = `
        left:${(pos.x - stW / 2).toFixed(1)}px;
        top:${(pos.y - stH / 2).toFixed(1)}px;
        width:${stW}px;
        height:${stH}px;
        background:linear-gradient(135deg, rgba(28,14,55,0.95) 0%, rgba(14,6,28,0.98) 100%);
        border:2.5px solid #00f5d4;
        box-shadow:0 15px 35px rgba(0,0,0,0.85), 0 0 20px rgba(0,245,212,0.35);
        transform:perspective(1200px) rotateX(12deg) rotateY(-8deg) translateZ(${pos.z}px) scale(${clamp(0.85 + easeU * 0.15, 0, 1)});
        opacity:${clamp(u * 2.0, 0, 1).toFixed(2)};
        padding:15px;
        z-index:${18 + idx};
      `;

      cuboid.innerHTML = `
        <div style="font-size:26px;color:#ffd166;font-weight:900;text-transform:uppercase;">TRẠM 0${idx + 1}</div>
        <div style="font-size:36px;color:#ffffff;font-weight:800;margin-top:6px;line-height:1.15;">${step.label}</div>
        <div style="font-size:26px;color:#00f5d4;font-weight:600;margin-top:4px;">${step.detail || ''}</div>
      `;
      world.appendChild(cuboid);
    });

    stage.appendChild(world);
    parent.appendChild(stage);
  }

  // 10. ELEMENT 8: terminal / mock_ui_window 3D
  // Cửa sổ 3D nghiêng phối cảnh nhẹ (rotateX 6°, rotateY -8°), viền mép dày 24px, specular highlight neon, bóng đổ lớn
  function renderTerminal3D(parent, shotData, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;
    const data = shotData.data || {};

    const title = data.title || "Cloud Terminal v2.4";
    const rawLines = data.lines || [
      "$ docker build -t enterprise-app:latest .",
      ">> Step 1/4: Analyzing architecture requirements...",
      ">> Step 2/4: Optimizing memory & cache layers...",
      "[SUCCESS] Deployment completed in 1.24s!"
    ];

    const stage = document.createElement('div');
    stage.className = 'depth-stage-wrapper';
    stage.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;z-index:10;`;

    const world = document.createElement('div');
    world.className = 'depth-world';

    const cx = 540;
    const cy = 760; // Content vertical center

    // Camera 3D
    applyDepthCamera(world, shotData.camera || { move: 'dolly_in', amount: 0.04 }, t, options.duration || 4.0);

    const winW = 860;
    const winH = 500;
    const winX = cx - winW / 2; // 110 (safe in [70, 1010])
    const winY = cy - winH / 2; // 510 (safe in [240, 1330])

    const u = clamp((t - 0.2) / 0.8, 0, 1);
    const easeU = easeOutBack(u);

    // 1. Large contact shadow under tilted window
    const shadowDiv = document.createElement('div');
    shadowDiv.className = 'depth-contact-shadow';
    shadowDiv.style.cssText = `
      left:${winX + 40}px;
      top:${winY + winH + 10}px;
      width:${winW - 80}px;
      height:55px;
      opacity:${clamp(u * 1.5, 0, 0.85).toFixed(2)};
    `;
    world.appendChild(shadowDiv);

    // 2. 3D Window Frame
    const win = document.createElement('div');
    win.className = 'terminal-window-3d cuboid-3d';
    win.style.cssText = `
      left:${winX}px;
      top:${winY}px;
      width:${winW}px;
      height:${winH}px;
      background:rgba(12, 6, 26, 0.96);
      border:3px solid #00f5d4;
      box-shadow:0 30px 60px rgba(0,0,0,0.9), 0 0 30px rgba(0,245,212,0.35);
      transform:perspective(1200px) rotateX(6deg) rotateY(-8deg) translateZ(10px) scale(${clamp(0.88 + easeU * 0.12, 0, 1)});
      opacity:${clamp(u * 2.0, 0, 1).toFixed(2)};
      z-index:20;
    `;

    // Titlebar
    const titlebar = document.createElement('div');
    titlebar.className = 'terminal-titlebar-3d';
    titlebar.innerHTML = `
      <div style="display:flex;gap:10px;">
        <span style="width:16px;height:16px;border-radius:50%;background:#f72585;display:inline-block;box-shadow:0 0 6px #f72585;"></span>
        <span style="width:16px;height:16px;border-radius:50%;background:#ffd166;display:inline-block;box-shadow:0 0 6px #ffd166;"></span>
        <span style="width:16px;height:16px;border-radius:50%;background:#00f5d4;display:inline-block;box-shadow:0 0 6px #00f5d4;"></span>
      </div>
      <div style="margin-left:20px;font-size:26px;font-weight:700;color:#94a3b8;letter-spacing:1px;">${title}</div>
    `;
    win.appendChild(titlebar);

    // Body Lines with Typing Animation
    const bodyDiv = document.createElement('div');
    bodyDiv.style.cssText = `
      padding:28px 32px;
      font-family:'Courier New', monospace, sans-serif;
      box-sizing:border-box;
    `;

    const totalLines = rawLines.length;
    rawLines.forEach((lineText, idx) => {
      const lineStartT = 0.5 + idx * 0.7;
      if (t < lineStartT) return;

      const lineProg = clamp((t - lineStartT) / 0.5, 0, 1);
      const charsToShow = Math.floor(lineText.length * lineProg);
      const visibleText = lineText.slice(0, charsToShow);

      const lineEl = document.createElement('div');
      const isSuccess = lineText.includes('[SUCCESS]');
      lineEl.style.cssText = `
        font-size:36px;
        font-weight:700;
        line-height:1.5;
        color:${isSuccess ? '#22c55e' : (idx === 0 ? '#00f5d4' : '#e2e8f0')};
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
      `;
      lineEl.textContent = visibleText;

      // Append blinking cursor to the current active typing line
      if (idx === Math.min(totalLines - 1, Math.floor((t - 0.5) / 0.7))) {
        const cursor = document.createElement('span');
        cursor.className = 'terminal-cursor-3d';
        cursor.style.opacity = (Math.floor(t * 4) % 2 === 0) ? '1' : '0';
        lineEl.appendChild(cursor);
      }

      bodyDiv.appendChild(lineEl);
    });

    win.appendChild(bodyDiv);
    world.appendChild(win);
    stage.appendChild(world);
    parent.appendChild(stage);
  }

  // 11. ELEMENT 9: road_tracker / timeline 3D
  // Con đường 3D Bezier ribbon uốn lượn phối cảnh, các trạm mốc cuboid có số thứ tự, marker beacon trôi dọc đường kèm ✓ nảy lên
  function renderRoadTracker3D(parent, shotData, t, options) {
    const W = options.width || 1080;
    const H = options.height || 1920;
    const data = shotData.data || {};

    const rawStations = data.stations || data.milestones || data.steps || [
      { label: "Bắt đầu", station: 1 },
      { label: "Tăng tốc", station: 2 },
      { label: "Kiểm thử", station: 3 },
      { label: "Về đích", station: 4 }
    ];

    const stage = document.createElement('div');
    stage.className = 'depth-stage-wrapper';
    stage.style.cssText = `position:absolute;top:0;left:0;width:${W}px;height:${H}px;z-index:10;`;

    const world = document.createElement('div');
    world.className = 'depth-world';

    // Camera 3D
    applyDepthCamera(world, shotData.camera || { move: 'dolly_in', amount: 0.04 }, t, options.duration || 4.0);

    const stationCount = Math.min(4, rawStations.length);

    // 3D Path Waypoints: Ribbon curves from horizon (540, 480) towards foreground (540, 1140)
    // S-curve path points for stations
    const stations = [
      { x: 380, y: 560, prog: 0.15 },
      { x: 680, y: 740, prog: 0.45 },
      { x: 340, y: 920, prog: 0.75 },
      { x: 620, y: 1100, prog: 0.98 }
    ].slice(0, stationCount);

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;';

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    defs.innerHTML = `
      <linearGradient id="roadRibbonGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#9d4edd" stop-opacity="0.3" />
        <stop offset="60%" stop-color="#00f5d4" stop-opacity="0.7" />
        <stop offset="100%" stop-color="#00f5d4" stop-opacity="0.9" />
      </linearGradient>
    `;
    svg.appendChild(defs);

    // 1. Draw 3D Bezier Road Ribbon
    const pathD = `M 540,460 C 320,560 300,660 540,740 C 780,820 740,920 480,1020 C 380,1080 480,1160 540,1180`;

    // Road Outer Bed
    const roadBed = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    roadBed.setAttribute('d', pathD);
    roadBed.setAttribute('fill', 'none');
    roadBed.setAttribute('stroke', '#12072b');
    roadBed.setAttribute('stroke-width', '50');
    svg.appendChild(roadBed);

    // Road Glowing Ribbon
    const roadRibbon = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    roadRibbon.setAttribute('d', pathD);
    roadRibbon.setAttribute('fill', 'none');
    roadRibbon.setAttribute('stroke', 'url(#roadRibbonGrad)');
    roadRibbon.setAttribute('stroke-width', '24');
    roadRibbon.style.cssText = 'filter:drop-shadow(0 0 10px rgba(0, 245, 212, 0.5));';
    svg.appendChild(roadRibbon);

    // Road Dashed Centerline
    const centerLine = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    centerLine.setAttribute('d', pathD);
    centerLine.setAttribute('fill', 'none');
    centerLine.setAttribute('stroke', '#ffffff');
    centerLine.setAttribute('stroke-width', '3');
    centerLine.setAttribute('stroke-dasharray', '12 10');
    svg.appendChild(centerLine);

    // 2. Beacon Marker Puck moving along path
    const markerProg = clamp(t / (options.duration || 4.0), 0, 1);
    // Interpolate marker position between stations
    let curPx = 540;
    let curPy = 460;
    for (let i = 0; i < stations.length; i++) {
      if (markerProg <= stations[i].prog) {
        const prev = i === 0 ? { x: 540, y: 460, prog: 0 } : stations[i - 1];
        const segU = (markerProg - prev.prog) / (stations[i].prog - prev.prog);
        curPx = prev.x + (stations[i].x - prev.x) * segU;
        curPy = prev.y + (stations[i].y - prev.y) * segU;
        break;
      } else if (i === stations.length - 1) {
        curPx = stations[i].x;
        curPy = stations[i].y;
      }
    }

    const puckMarker = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    puckMarker.setAttribute('cx', curPx);
    puckMarker.setAttribute('cy', curPy);
    puckMarker.setAttribute('r', '14');
    puckMarker.setAttribute('fill', '#ffffff');
    puckMarker.setAttribute('stroke', '#00f5d4');
    puckMarker.setAttribute('stroke-width', '4');
    puckMarker.style.cssText = 'filter:drop-shadow(0 0 16px #00f5d4);';
    svg.appendChild(puckMarker);

    stage.appendChild(svg);

    // 3. Station Cuboids along road
    stations.forEach((st, idx) => {
      const info = rawStations[idx];
      const isReached = (markerProg >= st.prog);
      const cubW = 190;
      const cubH = 88;

      const cuboid = document.createElement('div');
      cuboid.className = 'road-milestone-cuboid cuboid-3d';
      cuboid.style.cssText = `
        left:${(st.x - cubW / 2).toFixed(1)}px;
        top:${(st.y - cubH / 2).toFixed(1)}px;
        width:${cubW}px;
        height:${cubH}px;
        background:${isReached ? 'linear-gradient(135deg, rgba(28,14,55,0.95), rgba(14,6,28,0.98))' : 'rgba(18,11,40,0.85)'};
        border:2.5px solid ${isReached ? '#00f5d4' : 'rgba(157,78,221,0.4)'};
        box-shadow:${isReached ? '0 0 25px rgba(0,245,212,0.6), 0 15px 30px rgba(0,0,0,0.8)' : '0 10px 20px rgba(0,0,0,0.6)'};
        transform:perspective(1200px) rotateX(8deg) translateZ(${isReached ? '30px' : '0px'}) scale(${isReached ? '1.05' : '0.95'});
        transition:transform 0.3s ease, border-color 0.3s ease;
        padding:10px;
        z-index:${18 + idx};
      `;

      cuboid.innerHTML = `
        <div style="font-size:22px;color:${isReached ? '#00f5d4' : '#c77dff'};font-weight:900;">TRẠM 0${idx + 1}</div>
        <div style="font-size:32px;color:#ffffff;font-weight:800;margin-top:2px;line-height:1.1;">${info.label || ''}</div>
      `;
      world.appendChild(cuboid);
    });

    stage.appendChild(world);
    parent.appendChild(stage);
  }

  // Router dispatcher
  window.renderDepth3D = function (recipeType, container, shotData, t, options) {
    options = options || {};
    try {
      // 1. Render Perspective Floor Grid & Parallax Stars
      renderPerspectiveFloor(container, t, options);
      renderParallaxParticles(container, t, options);

      // 2. Dispatch to target 3D element
      switch (recipeType) {
        case 'bar_compare':
        case 'bar_grow':
        case 'compare_bars':
          renderBarCompare3D(container, shotData, t, options);
          return true;

        case 'gauge_ring':
        case 'ring':
          renderGaugeRing3D(container, shotData, t, options);
          return true;

        case 'versus_split':
        case 'versus':
          renderVersusSplit3D(container, shotData, t, options);
          return true;

        case 'hub_spoke':
        case 'network_nodes':
          renderHubSpoke3D(container, shotData, t, options);
          return true;

        case 'checklist':
        case 'steps_ladder':
        case 'steps_list':
        case 'magnifier_check':
          renderChecklist3D(container, shotData, t, options);
          return true;

        case 'stat_number':
        case 'stat_card':
        case 'numeric':
          renderStatNumber3D(container, shotData, t, options);
          return true;

        case 'flow_chain':
        case 'funnel':
          renderFlowChain3D(container, shotData, t, options);
          return true;

        case 'terminal_typing':
        case 'terminal_type':
        case 'mock_ui_window':
        case 'code_card':
          renderTerminal3D(container, shotData, t, options);
          return true;

        case 'road_tracker':
        case 'timeline':
        case 'progress_tracker':
          renderRoadTracker3D(container, shotData, t, options);
          return true;

        default:
          return false; // Fallback to 2D
      }
    } catch (e) {
      console.warn("Depth3D render error, falling back to 2D:", e);
      return false;
    }
  };

})();
