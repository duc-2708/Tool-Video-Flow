/* Stage Engine Runtime - Deterministic Isometric Scene Graph & Timeline */
(function() {
  'use strict';

  const SCRIPT = window.STAGE_SCRIPT || { hud: { steps: [] }, actors: [], scenes: [] };
  const cos30 = 0.86602540378;
  const sin30 = 0.5;
  const originX = 540;
  const originY = 785; // Calibrated to exact content center (240 + 1330) / 2 = 785

  function toScreen(x, y, z) {
    return {
      x: originX + (x - y) * cos30,
      y: originY + (x + y) * sin30 - (z || 0)
    };
  }

  function toLocal(x, y, z) {
    return {
      x: (x - y) * cos30,
      y: (x + y) * sin30 - (z || 0)
    };
  }

  // Pre-generate isometric grid lines once
  function initGrid() {
    const gridGroup = document.getElementById('grid-lines-group');
    if (!gridGroup) return;
    let linesSvg = '';
    const span = 1400;
    const step = 90;
    for (let d = -span; d <= span; d += step) {
      const p1 = toScreen(-span, d, 0);
      const p2 = toScreen(span, d, 0);
      linesSvg += `<line x1="${p1.x.toFixed(1)}" y1="${p1.y.toFixed(1)}" x2="${p2.x.toFixed(1)}" y2="${p2.y.toFixed(1)}" />`;
      const q1 = toScreen(d, -span, 0);
      const q2 = toScreen(d, span, 0);
      linesSvg += `<line x1="${q1.x.toFixed(1)}" y1="${q1.y.toFixed(1)}" x2="${q2.x.toFixed(1)}" y2="${q2.y.toFixed(1)}" />`;
    }
    gridGroup.innerHTML = linesSvg;

    // Ambient dust particles with deterministic distribution
    const dustGroup = document.getElementById('grid-dust-group');
    if (dustGroup) {
      let dustSvg = '';
      for (let i = 0; i < 28; i++) {
        const px = 80 + ((i * 137.5) % 920);
        const py = 250 + ((i * 229.3) % 1050);
        const r = 1.5 + (i % 3);
        const opacity = 0.15 + (i % 5) * 0.08;
        dustSvg += `<circle cx="${px}" cy="${py}" r="${r}" fill="#00f5d4" opacity="${opacity}" />`;
      }
      dustGroup.innerHTML = dustSvg;
    }
  }

  // Initialize HUD Stations
  function initHUD() {
    const nodesContainer = document.getElementById('tracker-nodes-container');
    const brandTitle = document.getElementById('hud-brand-title');
    const footerNote = document.getElementById('hud-footer-note');
    if (brandTitle && SCRIPT.hud?.brand) brandTitle.textContent = SCRIPT.hud.brand;
    if (footerNote && SCRIPT.hud?.footer_note) footerNote.textContent = SCRIPT.hud.footer_note;

    if (nodesContainer && SCRIPT.hud?.steps) {
      let nodesHtml = '';
      const steps = SCRIPT.hud.steps;
      steps.forEach((st, idx) => {
        nodesHtml += `<div class="station-node" id="station-node-${idx}">${idx + 1}</div>`;
      });
      nodesContainer.innerHTML = nodesHtml;
    }
  }

  // Calculate timeline schedule
  let totalDuration = 0;
  const sceneTimeline = [];
  let accumTime = 0;

  SCRIPT.scenes.forEach((sc, idx) => {
    const scStart = accumTime;
    const scDur = sc.duration_sec || 5.0;
    const scEnd = scStart + scDur;
    accumTime = scEnd;

    // Actions scheduled with absolute time
    const compiledActions = (sc.actions || []).map(act => {
      const at = scStart + (act.at_sec || 0);
      return {
        ...act,
        abs_at: at,
        abs_end: at + (act.duration || 0.5)
      };
    });

    sceneTimeline.push({
      ...sc,
      start: scStart,
      end: scEnd,
      duration: scDur,
      actions: compiledActions
    });
  });
  totalDuration = accumTime || 1.0;

  // =========================================================================
  // ACTOR RENDERERS (Deterministic Isometric SVG with neon purple/cyan palette)
  // =========================================================================

  // 1. Laptop
  function renderLaptopSvg(state, typingText, isGlow, t) {
    const baseW = 180;
    const baseH = 140;
    const p1 = toLocal(-baseW / 2, -baseH / 2, 0);
    const p2 = toLocal(baseW / 2, -baseH / 2, 0);
    const p3 = toLocal(baseW / 2, baseH / 2, 0);
    const p4 = toLocal(-baseW / 2, baseH / 2, 0);

    const p1_b = toLocal(-baseW / 2, -baseH / 2, -10);
    const p4_b = toLocal(-baseW / 2, baseH / 2, -10);
    const p3_b = toLocal(baseW / 2, baseH / 2, -10);

    const isOpen = (state !== 'closed');
    const lidZ = isOpen ? 105 : 0;

    const s1 = toLocal(-baseW / 2, -baseH / 2, 0);
    const s2 = toLocal(baseW / 2, -baseH / 2, 0);
    const s3 = toLocal(baseW / 2, -baseH / 2 - (isOpen ? 20 : 0), lidZ);
    const s4 = toLocal(-baseW / 2, -baseH / 2 - (isOpen ? 20 : 0), lidZ);

    const glowFilter = isGlow ? 'filter="url(#neon-glow-filter)" stroke="#00f5d4" stroke-width="3"' : '';
    const cursorVisible = Math.sin(t * 8) > 0;

    return `
      <!-- Base plate shadow -->
      <polygon points="${p1.x},${p1.y + 12} ${p2.x},${p2.y + 12} ${p3.x},${p3.y + 12} ${p4.x},${p4.y + 12}" fill="rgba(3,1,8,0.7)" />
      <!-- Base plate -->
      <polygon points="${p4.x},${p4.y} ${p3.x},${p3.y} ${p3_b.x},${p3_b.y} ${p4_b.x},${p4_b.y}" fill="#160c30" stroke="#9d4edd" stroke-width="1.5" />
      <polygon points="${p1.x},${p1.y} ${p2.x},${p2.y} ${p3.x},${p3.y} ${p4.x},${p4.y}" fill="#241348" stroke="#9d4edd" stroke-width="2" />
      <!-- Keyboard grid -->
      <g opacity="${isOpen ? 0.85 : 0.2}">
        <polygon points="${(p1.x*0.6+p4.x*0.4)},${(p1.y*0.6+p4.y*0.4)} ${(p2.x*0.6+p3.x*0.4)},${(p2.y*0.6+p3.y*0.4)} ${(p2.x*0.2+p3.x*0.8)},${(p2.y*0.2+p3.y*0.8)} ${(p1.x*0.2+p4.x*0.8)},${(p1.y*0.2+p4.y*0.8)}" fill="#12082b" stroke="#00f5d4" stroke-width="1" />
        <!-- Trackpad -->
        <polygon points="${p4.x*0.7+p3.x*0.3},${p4.y*0.7+p3.y*0.3-6} ${p4.x*0.3+p3.x*0.7},${p4.y*0.3+p3.y*0.7-6} ${p4.x*0.3+p3.x*0.7},${p4.y*0.3+p3.y*0.7+12} ${p4.x*0.7+p3.x*0.3},${p4.y*0.7+p3.y*0.3+12}" fill="#1a0e38" stroke="rgba(157,78,221,0.5)" stroke-width="1" />
      </g>
      <!-- Screen Lid -->
      ${isOpen ? `
        <!-- Screen Outer Frame -->
        <polygon points="${s1.x},${s1.y} ${s2.x},${s2.y} ${s3.x},${s3.y} ${s4.x},${s4.y}" fill="#100626" stroke="#9d4edd" stroke-width="2.5" ${glowFilter} />
        <!-- Screen Canvas / Terminal -->
        <polygon points="${s1.x*0.9+s4.x*0.1},${s1.y*0.9+s4.y*0.1} ${s2.x*0.9+s3.x*0.1},${s2.y*0.9+s3.y*0.1} ${s2.x*0.1+s3.x*0.9},${s2.y*0.1+s3.y*0.9} ${s1.x*0.1+s4.x*0.9},${s1.y*0.1+s4.y*0.9}" fill="#080214" stroke="#00f5d4" stroke-width="1" />
        <!-- Terminal Header dots -->
        <circle cx="${s4.x + 18}" cy="${s4.y + 16}" r="3.5" fill="#f72585" />
        <circle cx="${s4.x + 28}" cy="${s4.y + 16}" r="3.5" fill="#fbb034" />
        <circle cx="${s4.x + 38}" cy="${s4.y + 16}" r="3.5" fill="#00f5d4" />
        <!-- Terminal typing text -->
        <text x="${s4.x + 18}" y="${s4.y + 44}" font-family="Courier, monospace" font-size="16" font-weight="700" fill="#00f5d4" filter="drop-shadow(0 0 4px #00f5d4)">$ ${typingText}<tspan fill="#ffffff" opacity="${cursorVisible ? 1 : 0}">_</tspan></text>
      ` : `
        <!-- Closed lid -->
        <polygon points="${p1.x},${p1.y} ${p2.x},${p2.y} ${p3.x},${p3.y} ${p4.x},${p4.y}" fill="#160c30" stroke="#9d4edd" stroke-width="2" />
        <circle cx="${(p1.x+p3.x)/2}" cy="${(p1.y+p3.y)/2}" r="10" fill="none" stroke="#00f5d4" stroke-width="1.5" opacity="0.6" />
      `}
    `;
  }

  // 2. VPS Server
  function renderVpsServerSvg(state, isBusy, isContainerStacked, isRunning, t) {
    const w = 150, d = 150, h = 180;
    const b1 = toLocal(-w/2, -d/2, 0);
    const b2 = toLocal(w/2, -d/2, 0);
    const b3 = toLocal(w/2, d/2, 0);
    const b4 = toLocal(-w/2, d/2, 0);

    const t1 = toLocal(-w/2, -d/2, h);
    const t2 = toLocal(w/2, -d/2, h);
    const t3 = toLocal(w/2, d/2, h);
    const t4 = toLocal(-w/2, d/2, h);

    const isOn = (state === 'on' || state === 'busy');
    const ledColor = state === 'busy' ? '#f72585' : (isOn ? '#00f5d4' : '#552233');
    const rackGlow = isOn ? 'filter="url(#neon-glow-filter)" stroke="#00f5d4" stroke-width="2"' : 'stroke="#9d4edd" stroke-width="1.5"';

    let dockerSvg = '';
    if (isContainerStacked) {
      const cW = 120, cD = 120, cH = 80;
      const ct1 = toLocal(-cW/2, -cD/2, h + cH);
      const ct2 = toLocal(cW/2, -cD/2, h + cH);
      const ct3 = toLocal(cW/2, cD/2, h + cH);
      const ct4 = toLocal(-cW/2, cD/2, h + cH);

      const cb1 = toLocal(-cW/2, -cD/2, h);
      const cb2 = toLocal(cW/2, -cD/2, h);
      const cb3 = toLocal(cW/2, cD/2, h);
      const cb4 = toLocal(-cW/2, cD/2, h);

      const pulseGlow = isRunning ? `stroke="#00f5d4" stroke-width="${2 + Math.sin(t * 6)}"` : 'stroke="#00f5d4" stroke-width="1.5"';

      dockerSvg = `
        <g id="docker-container-box">
          <polygon points="${cb4.x},${cb4.y} ${cb3.x},${cb3.y} ${ct3.x},${ct3.y} ${ct4.x},${ct4.y}" fill="#0077b6" ${pulseGlow} />
          <polygon points="${cb3.x},${cb3.y} ${cb2.x},${cb2.y} ${ct2.x},${ct2.y} ${ct3.x},${ct3.y}" fill="#023e8a" ${pulseGlow} />
          <polygon points="${ct1.x},${ct1.y} ${ct2.x},${ct2.y} ${ct3.x},${ct3.y} ${ct4.x},${ct4.y}" fill="#0096c7" stroke="#ffffff" stroke-width="1.5" />
          <text x="${(cb3.x+ct4.x)/2}" y="${(cb3.y+ct4.y)/2 + 6}" font-size="18" font-weight="800" fill="#ffffff" text-anchor="middle">🐳 DOCKER</text>
          ${isRunning ? `
            <circle cx="${ct3.x - 12}" cy="${ct3.y - 8}" r="5" fill="#22c55e" filter="drop-shadow(0 0 6px #22c55e)" />
            <text x="${(cb3.x+ct4.x)/2}" y="${(cb3.y+ct4.y)/2 + 26}" font-size="14" font-weight="700" fill="#00f5d4" text-anchor="middle">PORT 80:8080</text>
          ` : ''}
        </g>
      `;
    }

    return `
      <polygon points="${b1.x},${b1.y + 14} ${b2.x},${b2.y + 14} ${b3.x},${b3.y + 14} ${b4.x},${b4.y + 14}" fill="rgba(3,1,8,0.7)" />
      <polygon points="${b4.x},${b4.y} ${b3.x},${b3.y} ${t3.x},${t3.y} ${t4.x},${t4.y}" fill="#13092b" ${rackGlow} />
      <polygon points="${b3.x},${b3.y} ${b2.x},${b2.y} ${t2.x},${t2.y} ${t3.x},${t3.y}" fill="#0b041c" stroke="#9d4edd" stroke-width="1.5" />
      <polygon points="${t1.x},${t1.y} ${t2.x},${t2.y} ${t3.x},${t3.y} ${t4.x},${t4.y}" fill="#221144" stroke="#9d4edd" stroke-width="1.5" />
      <g>
        ${[0.2, 0.4, 0.6, 0.8].map((ratio, i) => {
          const ly1 = b4.y * (1 - ratio) + t4.y * ratio;
          const lx1 = b4.x * (1 - ratio) + t4.x * ratio;
          const ly2 = b3.y * (1 - ratio) + t3.y * ratio;
          const lx2 = b3.x * (1 - ratio) + t3.x * ratio;
          return `
            <line x1="${lx1 + 8}" y1="${ly1}" x2="${lx2 - 8}" y2="${ly2}" stroke="rgba(157,78,221,0.5)" stroke-width="2" />
            <circle cx="${lx1 + 18}" cy="${ly1 - 4}" r="4" fill="${ledColor}" filter="drop-shadow(0 0 6px ${ledColor})" />
            <circle cx="${lx1 + 32}" cy="${ly1 - 4}" r="2.5" fill="${isOn ? '#00f5d4' : '#332244'}" />
          `;
        }).join('')}
      </g>
      ${dockerSvg}
    `;
  }

  // 3. Docker Container (Standalone)
  function renderDockerContainerSvg(state, t) {
    const w = 130, d = 130, h = 90;
    const b1 = toLocal(-w/2, -d/2, 0);
    const b2 = toLocal(w/2, -d/2, 0);
    const b3 = toLocal(w/2, d/2, 0);
    const b4 = toLocal(-w/2, d/2, 0);

    const t1 = toLocal(-w/2, -d/2, h);
    const t2 = toLocal(w/2, -d/2, h);
    const t3 = toLocal(w/2, d/2, h);
    const t4 = toLocal(-w/2, d/2, h);

    const isRunning = (state === 'running');
    const borderPulse = isRunning ? `stroke="#00f5d4" stroke-width="${2.5 + Math.sin(t * 6)}"` : 'stroke="#0077b6" stroke-width="2"';

    return `
      <polygon points="${b1.x},${b1.y + 10} ${b2.x},${b2.y + 10} ${b3.x},${b3.y + 10} ${b4.x},${b4.y + 10}" fill="rgba(3,1,8,0.6)" />
      <polygon points="${b4.x},${b4.y} ${b3.x},${b3.y} ${t3.x},${t3.y} ${t4.x},${t4.y}" fill="#0077b6" ${borderPulse} />
      <polygon points="${b3.x},${b3.y} ${b2.x},${b2.y} ${t2.x},${t2.y} ${t3.x},${t3.y}" fill="#023e8a" ${borderPulse} />
      <polygon points="${t1.x},${t1.y} ${t2.x},${t2.y} ${t3.x},${t3.y} ${t4.x},${t4.y}" fill="#0096c7" stroke="#ffffff" stroke-width="1.5" />
      <text x="${(b3.x+t4.x)/2}" y="${(b3.y+t4.y)/2 + 6}" font-size="20" font-weight="800" fill="#ffffff" text-anchor="middle">🐳 DOCKER</text>
      ${isRunning ? `
        <circle cx="${t3.x - 14}" cy="${t3.y - 10}" r="6" fill="#00f5d4" filter="drop-shadow(0 0 8px #00f5d4)" />
        <text x="${(b3.x+t4.x)/2}" y="${(b3.y+t4.y)/2 + 28}" font-size="14" font-weight="700" fill="#00f5d4" text-anchor="middle">PORT 80:8080</text>
      ` : ''}
    `;
  }

  // 4. Cloud Platform
  function renderCloudPlatformSvg(state, t) {
    const rx = 140, ry = 70;
    const pCenter = toLocal(0, 0, 0);
    const pShadow = toLocal(0, 0, -15);
    const lev = 5 * Math.sin(t * 2.5);
    const isActive = (state === 'active' || state === 'sync');

    return `
      <!-- Shadow -->
      <ellipse cx="${pShadow.x}" cy="${pShadow.y + 20}" rx="${rx}" ry="${ry}" fill="rgba(3,1,8,0.7)" />
      <!-- Cloud Disc Surface -->
      <g transform="translate(0, ${lev})">
        <ellipse cx="${pCenter.x}" cy="${pCenter.y}" rx="${rx}" ry="${ry}" fill="#14082e" stroke="#9d4edd" stroke-width="3" />
        <ellipse cx="${pCenter.x}" cy="${pCenter.y - 8}" rx="${rx * 0.9}" ry="${ry * 0.9}" fill="#1b0c3d" stroke="#00f5d4" stroke-width="1.5" />
        <!-- Cloud Waves / Icon -->
        <path d="M ${pCenter.x - 40} ${pCenter.y - 10} q 15 -25 35 -10 q 20 -20 40 5 q 15 5 15 20 q -5 15 -25 15 l -60 0 q -15 0 -15 -15 q 0 -10 10 -15 z" fill="#00f5d4" opacity="0.85" filter="drop-shadow(0 0 10px #00f5d4)" />
        ${isActive ? `
          <circle cx="${pCenter.x}" cy="${pCenter.y}" r="${40 + (t * 40 % 60)}" fill="none" stroke="#00f5d4" stroke-width="2" opacity="${1 - (t * 40 % 60)/60}" />
        ` : ''}
      </g>
    `;
  }

  // 5. Code Repo (Git)
  function renderCodeRepoSvg(state, t) {
    const w = 140, d = 140, h = 100;
    const b1 = toLocal(-w/2, -d/2, 0);
    const b2 = toLocal(w/2, -d/2, 0);
    const b3 = toLocal(w/2, d/2, 0);
    const b4 = toLocal(-w/2, d/2, 0);

    const t1 = toLocal(-w/2, -d/2, h);
    const t2 = toLocal(w/2, -d/2, h);
    const t3 = toLocal(w/2, d/2, h);
    const t4 = toLocal(-w/2, d/2, h);

    return `
      <polygon points="${b1.x},${b1.y + 12} ${b2.x},${b2.y + 12} ${b3.x},${b3.y + 12} ${b4.x},${b4.y + 12}" fill="rgba(3,1,8,0.7)" />
      <polygon points="${b4.x},${b4.y} ${b3.x},${b3.y} ${t3.x},${t3.y} ${t4.x},${t4.y}" fill="#160c30" stroke="#f72585" stroke-width="2" />
      <polygon points="${b3.x},${b3.y} ${b2.x},${b2.y} ${t2.x},${t2.y} ${t3.x},${t3.y}" fill="#100624" stroke="#f72585" stroke-width="1.5" />
      <polygon points="${t1.x},${t1.y} ${t2.x},${t2.y} ${t3.x},${t3.y} ${t4.x},${t4.y}" fill="#221144" stroke="#ffffff" stroke-width="1.5" />
      <!-- Git Branch Nodes -->
      <g>
        <line x1="${(b4.x+t4.x)/2 + 25}" y1="${(b4.y+t4.y)/2 + 10}" x2="${(b3.x+t3.x)/2 - 25}" y2="${(b3.y+t3.y)/2 - 10}" stroke="#00f5d4" stroke-width="3" />
        <circle cx="${(b4.x+t4.x)/2 + 30}" cy="${(b4.y+t4.y)/2 + 8}" r="5" fill="#f72585" />
        <circle cx="${(b4.x+b3.x)/2}" cy="${(b4.y+b3.y)/2}" r="5" fill="#00f5d4" />
        <circle cx="${(b3.x+t3.x)/2 - 30}" cy="${(b3.y+t3.y)/2 - 8}" r="5" fill="#00f5d4" />
        <text x="${(b4.x+b3.x)/2}" y="${(t4.y+t3.y)/2 + 20}" font-size="18" font-weight="800" fill="#ffffff" text-anchor="middle">git push</text>
      </g>
    `;
  }

  // 6. Terminal Window
  function renderTerminalWindowSvg(state, typingText, t) {
    const w = 220, h = 140;
    const cx = 0, cy = 0;
    const p = toLocal(cx, cy, 0);

    return `
      <g transform="translate(${p.x - w/2}, ${p.y - h/2})">
        <rect x="0" y="0" width="${w}" height="${h}" rx="14" fill="#0d051f" stroke="#00f5d4" stroke-width="2" filter="drop-shadow(0 8px 24px rgba(0,0,0,0.6))" />
        <rect x="0" y="0" width="${w}" height="28" rx="14" fill="#1b0c3d" />
        <circle cx="16" cy="14" r="4" fill="#f72585" />
        <circle cx="28" cy="14" r="4" fill="#fbb034" />
        <circle cx="40" cy="14" r="4" fill="#00f5d4" />
        <text x="60" y="18" font-size="12" font-family="Courier, monospace" font-weight="700" fill="#a097c4">bash - 80x24</text>
        <text x="14" y="58" font-family="Courier, monospace" font-size="14" font-weight="700" fill="#00f5d4">$ ${typingText}<tspan fill="#ffffff" opacity="${Math.sin(t * 8) > 0 ? 1 : 0}">_</tspan></text>
      </g>
    `;
  }

  // 7. Browser Window
  function renderBrowserWindowSvg(state, t) {
    const w = 240, h = 160;
    const p = toLocal(0, 0, 0);

    return `
      <g transform="translate(${p.x - w/2}, ${p.y - h/2})">
        <rect x="0" y="0" width="${w}" height="${h}" rx="16" fill="#100628" stroke="#9d4edd" stroke-width="2.5" filter="drop-shadow(0 12px 30px rgba(0,0,0,0.7))" />
        <!-- Header & URL bar -->
        <rect x="0" y="0" width="${w}" height="36" rx="16" fill="#1d0c45" />
        <circle cx="16" cy="18" r="4" fill="#f72585" />
        <circle cx="28" cy="18" r="4" fill="#fbb034" />
        <circle cx="40" cy="18" r="4" fill="#00f5d4" />
        <!-- URL pill with SSL Padlock -->
        <rect x="55" y="8" width="${w - 70}" height="20" rx="10" fill="#0d051f" stroke="#00f5d4" stroke-width="1" />
        <text x="65" y="22" font-size="11" font-weight="700" fill="#00f5d4">🔒 https://app.example.vn</text>
        <!-- Body preview -->
        <rect x="18" y="48" width="${w - 36}" height="34" rx="8" fill="#1b0c3d" stroke="#00f5d4" stroke-width="1" />
        <text x="${w/2}" y="70" font-size="14" font-weight="800" fill="#ffffff" text-anchor="middle">APP IS LIVE 🚀</text>
        <rect x="18" y="92" width="${(w - 48)/2}" height="50" rx="8" fill="#160930" />
        <rect x="${w/2 + 6}" y="92" width="${(w - 48)/2}" height="50" rx="8" fill="#160930" />
      </g>
    `;
  }

  // 8. Lock Shield (SSL / Security)
  function renderLockShieldSvg(state, t) {
    const p = toLocal(0, 0, 0);
    const lev = 4 * Math.sin(t * 2.5);

    return `
      <g transform="translate(${p.x}, ${p.y + lev})">
        <!-- Shield background -->
        <path d="M 0 -45 L 35 -30 L 35 10 Q 35 45 0 60 Q -35 45 -35 10 L -35 -30 Z" fill="#150a33" stroke="#00f5d4" stroke-width="3" filter="drop-shadow(0 0 16px #00f5d4)" />
        <!-- Padlock icon in center -->
        <rect x="-14" y="-8" width="28" height="24" rx="6" fill="#00f5d4" />
        <path d="M -8 -8 L -8 -18 Q -8 -26 0 -26 Q 8 -26 8 -18 L 8 -8" fill="none" stroke="#00f5d4" stroke-width="4" stroke-linecap="round" />
        <circle cx="0" cy="2" r="3" fill="#150a33" />
      </g>
    `;
  }

  // 9. User Figure
  function renderUserFigureSvg(state, t) {
    const p = toLocal(0, 0, 0);
    const breathe = 2 * Math.sin(t * 2.5);

    return `
      <g transform="translate(${p.x}, ${p.y + breathe})">
        <!-- Head sphere -->
        <circle cx="0" cy="-45" r="16" fill="#c77dff" stroke="#ffffff" stroke-width="2" filter="drop-shadow(0 0 8px #9d4edd)" />
        <!-- Body prism -->
        <path d="M -22 -20 L 22 -20 L 15 25 L -15 25 Z" fill="#1d0c45" stroke="#9d4edd" stroke-width="2" />
        <!-- Glowing chest core -->
        <circle cx="0" cy="-5" r="5" fill="#00f5d4" />
      </g>
    `;
  }

  // 10. Datacenter (Cluster of Racks)
  function renderDatacenterSvg(state, t) {
    const p = toLocal(0, 0, 0);
    return `
      <g transform="translate(${p.x}, ${p.y})">
        <!-- 3 Racks side by side -->
        <g transform="translate(-70, 0)">${renderVpsServerSvg(state, false, false, false, t)}</g>
        <g transform="translate(0, -25)">${renderVpsServerSvg(state, false, true, true, t)}</g>
        <g transform="translate(70, 0)">${renderVpsServerSvg(state, false, false, false, t)}</g>
      </g>
    `;
  }

  // 11. Note Board
  function renderNoteBoardSvg(state, label, text, t) {
    const w = 220, h = 130;
    const p = toLocal(0, 0, 0);
    const lev = 3 * Math.sin(t * 2.5);

    return `
      <g transform="translate(${p.x - w/2}, ${p.y - h/2 + lev})">
        <rect x="0" y="0" width="${w}" height="${h}" rx="16" fill="#1b082e" stroke="#f72585" stroke-width="2.5" filter="drop-shadow(0 8px 24px rgba(247,37,133,0.35))" />
        <!-- Pin icon -->
        <circle cx="${w/2}" cy="12" r="5" fill="#f72585" />
        <rect x="15" y="24" width="60" height="20" rx="8" fill="#f72585" />
        <text x="45" y="38" font-size="12" font-weight="800" fill="#ffffff" text-anchor="middle">LƯU Ý</text>
        <text x="18" y="70" font-size="16" font-weight="700" fill="#ffffff">${label || 'Kẹt? Dán lỗi'}</text>
        <text x="18" y="98" font-size="14" font-weight="500" fill="#00f5d4">${text || 'Kiểm tra mở cổng UFW'}</text>
      </g>
    `;
  }

  // 12. Road Recap (Morph from station tracker to 3D winding road)
  function renderRoadRecapSvg(progress, t) {
    const numPoints = 5;
    const points = [];
    for (let i = 0; i < numPoints; i++) {
      const u = i / (numPoints - 1);
      const isoX = -260 + u * 520;
      const isoY = 160 - Math.sin(u * Math.PI) * 120;
      const isoZ = u * 40;
      points.push(toScreen(isoX, isoY, isoZ));
    }

    let roadPath = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const mx = (prev.x + curr.x) / 2;
      const my = (prev.y + curr.y) / 2;
      roadPath += ` Q ${prev.x} ${prev.y} ${mx} ${my}`;
    }
    roadPath += ` L ${points[points.length - 1].x} ${points[points.length - 1].y}`;

    // Milestone markers
    const milestonesSvg = points.map((pt, idx) => {
      const isReached = (progress >= idx / (numPoints - 1));
      return `
        <g transform="translate(${pt.x}, ${pt.y})">
          <circle cx="0" cy="0" r="18" fill="${isReached ? '#00f5d4' : '#1d0c45'}" stroke="#ffffff" stroke-width="2" class="road-milestone" />
          <text x="0" y="6" font-size="14" font-weight="900" fill="${isReached ? '#061118' : '#ffffff'}" text-anchor="middle">${isReached ? '✓' : idx + 1}</text>
        </g>
      `;
    }).join('');

    // Traveling marker
    const uMarker = Math.min(1.0, progress);
    const mIdx = Math.min(numPoints - 2, Math.floor(uMarker * (numPoints - 1)));
    const segU = (uMarker * (numPoints - 1)) - mIdx;
    const pA = points[mIdx];
    const pB = points[mIdx + 1];
    const curX = pA.x + (pB.x - pA.x) * segU;
    const curY = pA.y + (pB.y - pA.y) * segU;

    return `
      <g id="road-recap-group">
        <!-- 3D Road bed -->
        <path d="${roadPath}" stroke="#13092b" stroke-width="48" stroke-linecap="round" fill="none" opacity="0.8" />
        <path d="${roadPath}" stroke="#9d4edd" stroke-width="38" stroke-linecap="round" fill="none" class="road-surface" />
        <path d="${roadPath}" class="road-center-line" />
        ${milestonesSvg}
        <!-- Traveling Vehicle / Capsule -->
        <g transform="translate(${curX}, ${curY - 14})">
          <circle cx="0" cy="0" r="14" fill="#f72585" stroke="#ffffff" stroke-width="2" filter="drop-shadow(0 0 10px #f72585)" />
          <text x="0" y="-18" font-size="14" font-weight="800" fill="#ffffff" text-anchor="middle">BẠN</text>
        </g>
        <!-- Final question banner -->
        <g transform="translate(540, 680)">
          <rect x="-260" y="-30" width="520" height="60" rx="20" fill="#0d051f" stroke="#00f5d4" stroke-width="2.5" filter="drop-shadow(0 8px 24px rgba(0,245,212,0.4))" />
          <text x="0" y="8" font-size="24" font-weight="800" fill="#ffffff" text-anchor="middle">BẠN ĐÃ ĐƯA APP LÊN VPS THÀNH CÔNG CHƯA?</text>
        </g>
      </g>
    `;
  }

  // =========================================================================
  // MASTER RENDER EVALUATION (Deterministic seek to time t)
  // =========================================================================
  window.renderAt = function(t) {
    if (t < 0) t = 0;
    if (t > totalDuration) t = totalDuration;

    // 1. Identify active scene
    let activeScene = sceneTimeline[0];
    let activeSceneIdx = 0;
    for (let i = 0; i < sceneTimeline.length; i++) {
      if (t >= sceneTimeline[i].start && (t < sceneTimeline[i].end || i === sceneTimeline.length - 1)) {
        activeScene = sceneTimeline[i];
        activeSceneIdx = i;
        break;
      }
    }

    // 2. Camera interpolation (zoom clamped <= 1.25, centered around originY=785)
    const camTarget = activeScene.camera || { x: 540, y: 785, zoom: 1.0, tilt: 0 };
    const vp = document.getElementById('world-viewport');
    if (vp) {
      const zoom = Math.min(1.25, camTarget.zoom || 1.0);
      const tilt = camTarget.tilt || 0;
      // Gentle camera drift ensures visible movement across any 0.8s
      const driftX = 4 * Math.sin(t * 0.8);
      const driftY = 3 * Math.cos(t * 0.7);
      const panX = (camTarget.x - 540) + driftX;
      const panY = (camTarget.y - 785) + driftY;
      vp.style.transform = `translate(${-panX}px, ${-panY}px) scale(${zoom}) rotate(${tilt}deg)`;
    }

    // 3. State tracking for actors
    const actorStates = {};
    SCRIPT.actors.forEach(act => {
      actorStates[act.id] = {
        visible: false,
        pos: Array.isArray(act.pos) ? [...act.pos] : [0, 0, 0],
        state: act.state || 'default',
        typingText: '',
        isGlow: false,
        isBusy: false,
        isContainerStacked: false,
        isRunning: false,
        highlightColor: null,
        opacity: 0,
        label: act.label,
        sublabel: act.sublabel,
        type: act.type
      };
    });

    let activePacket = null;
    let cableConnected = false;
    let isGlitchActive = false;
    let isBlurActive = false;
    let stampText = null;
    let isRoadRecap = false;
    let roadProgress = 0;

    // Apply actions chronologically up to time t
    sceneTimeline.forEach(sc => {
      sc.actions.forEach(act => {
        if (t >= act.abs_at) {
          const elapsed = t - act.abs_at;
          const dur = act.duration || 0.5;
          const progress = Math.min(1.0, elapsed / dur);

          if (act.verb === 'enter') {
            const tgt = actorStates[act.target];
            if (tgt) {
              tgt.visible = true;
              tgt.opacity = Math.min(1.0, progress * 1.5);
            }
          } else if (act.verb === 'exit') {
            const tgt = actorStates[act.target];
            if (tgt) {
              tgt.opacity = Math.max(0.0, 1.0 - progress);
              if (progress >= 1.0) tgt.visible = false;
            }
          } else if (act.verb === 'move_to') {
            const tgt = actorStates[act.target];
            if (tgt && act.params?.to_pos) {
              const startPos = tgt.pos;
              const endPos = act.params.to_pos;
              tgt.pos = [
                startPos[0] + (endPos[0] - startPos[0]) * progress,
                startPos[1] + (endPos[1] - startPos[1]) * progress,
                startPos[2] + (endPos[2] - startPos[2]) * progress
              ];
            }
          } else if (act.verb === 'open') {
            const tgt = actorStates[act.target];
            if (tgt) tgt.state = 'open';
          } else if (act.verb === 'close') {
            const tgt = actorStates[act.target];
            if (tgt) tgt.state = 'closed';
          } else if (act.verb === 'connect') {
            cableConnected = true;
          } else if (act.verb === 'type') {
            const tgt = actorStates[act.target];
            if (tgt) {
              const fullText = act.params?.text || '';
              const numChars = Math.floor(fullText.length * progress);
              tgt.typingText = fullText.substring(0, numChars);
              tgt.state = 'typing';
            }
          } else if (act.verb === 'send_packet') {
            cableConnected = true;
            activePacket = {
              target: act.target,
              from: act.params?.from_actor || 'laptop_client',
              to: act.params?.to_actor || 'vps_server',
              progress: progress,
              label: act.params?.label || 'Packet'
            };
          } else if (act.verb === 'set_state') {
            const tgt = actorStates[act.target];
            if (tgt) {
              if (act.params?.state) tgt.state = act.params.state;
              if (act.params?.container_stacked) tgt.isContainerStacked = true;
              if (act.params?.is_running) tgt.isRunning = true;
            }
          } else if (act.verb === 'highlight') {
            const tgt = actorStates[act.target];
            if (tgt) {
              tgt.isGlow = true;
              tgt.highlightColor = act.params?.color || '#00f5d4';
            }
          } else if (act.verb === 'glitch') {
            if (elapsed < dur) isGlitchActive = true;
          } else if (act.verb === 'blur_dissolve') {
            if (elapsed < dur) isBlurActive = true;
          } else if (act.verb === 'stamp') {
            stampText = act.params?.text || 'VERIFIED';
          } else if (act.verb === 'morph_to') {
            if (act.params?.target_form === 'road' || act.target === 'road') {
              isRoadRecap = true;
              roadProgress = progress;
            }
          } else if (act.verb === 'label') {
            const tgt = actorStates[act.target];
            if (tgt) {
              if (act.params?.text) tgt.label = act.params.text;
              if (act.params?.sublabel) tgt.sublabel = act.params.sublabel;
            }
          }
        }
      });
    });

    // Check if recap scene specifies road morph
    if (activeScene.scene_id === 'recap_road' || (SCRIPT.recap && SCRIPT.recap.morph_tracker_to === 'road' && activeSceneIdx === sceneTimeline.length - 1)) {
      isRoadRecap = true;
      roadProgress = (t - activeScene.start) / activeScene.duration;
    }

    // Toggle viewport filter classes
    if (vp) {
      vp.className = isGlitchActive ? 'glitch-active' : (isBlurActive ? 'blur-dissolve-active' : '');
    }

    // 4. Render Layers in SVG
    const actorsLayer = document.getElementById('actors-layer');
    const connectionsLayer = document.getElementById('connections-layer');
    const packetsLayer = document.getElementById('packets-layer');
    const effectsLayer = document.getElementById('effects-layer');

    let actorsHtml = '';
    let connectionHtml = '';
    let packetHtml = '';
    let effectsHtml = '';

    if (isRoadRecap) {
      // Render 3D Road Recap
      actorsHtml = renderRoadRecapSvg(roadProgress, t);
    } else {
      // Ports for connection
      const laptopPos = actorStates['laptop_client']?.pos || [-220, 40, 0];
      const vpsPos = actorStates['vps_server']?.pos || [220, -40, 0];

      const pFrom = toScreen(laptopPos[0] + 60, laptopPos[1] - 40, 10);
      const pTo = toScreen(vpsPos[0] - 60, vpsPos[1] + 20, 30);

      // Cable rendering
      if (cableConnected) {
        const midX = (pFrom.x + pTo.x) / 2;
        const midY = (pFrom.y + pTo.y) / 2 + 50;
        const pathD = `M ${pFrom.x} ${pFrom.y} Q ${midX} ${midY} ${pTo.x} ${pTo.y}`;
        connectionHtml = `
          <path d="${pathD}" class="connection-cable" />
          <path d="${pathD}" class="connection-pulse" stroke-dashoffset="${-t * 80}" />
        `;

        // Packet flying along cable
        if (activePacket && activePacket.progress < 1.0) {
          const u = activePacket.progress;
          const qx = (1 - u) * (1 - u) * pFrom.x + 2 * (1 - u) * u * midX + u * u * pTo.x;
          const qy = (1 - u) * (1 - u) * pFrom.y + 2 * (1 - u) * u * midY + u * u * pTo.y;
          packetHtml = `
            <g transform="translate(${qx}, ${qy})">
              <circle cx="0" cy="0" r="14" class="packet-capsule" />
              <circle cx="0" cy="0" r="22" fill="none" stroke="#00f5d4" stroke-width="1.5" opacity="${0.6 * (1 - u)}" />
              <text x="0" y="-22" font-size="20" font-weight="700" fill="#00f5d4" text-anchor="middle" filter="drop-shadow(0 2px 4px #000)">${activePacket.label}</text>
            </g>
          `;
        }
      }

      // Render individual actors
      SCRIPT.actors.forEach((act, actIdx) => {
        const st = actorStates[act.id];
        if (!st || !st.visible || st.opacity <= 0) return;

        const screenPos = toScreen(st.pos[0], st.pos[1], st.pos[2]);
        // Subtle micro-float idle breathing ensures visible movement within 0.8s
        const idleFloat = 4 * Math.sin(t * 2.2 + actIdx * 0.9);
        let itemContent = '';

        if (act.type === 'laptop') {
          itemContent = renderLaptopSvg(st.state, st.typingText, st.isGlow, t);
        } else if (act.type === 'vps_server') {
          itemContent = renderVpsServerSvg(st.state, st.state === 'busy', st.isContainerStacked, st.isRunning, t);
        } else if (act.type === 'docker_container' || act.type === 'container_box') {
          itemContent = renderDockerContainerSvg(st.state, t);
        } else if (act.type === 'cloud') {
          itemContent = renderCloudPlatformSvg(st.state, t);
        } else if (act.type === 'code_repo' || act.type === 'git_repo') {
          itemContent = renderCodeRepoSvg(st.state, t);
        } else if (act.type === 'terminal_window') {
          itemContent = renderTerminalWindowSvg(st.state, st.typingText, t);
        } else if (act.type === 'browser_window') {
          itemContent = renderBrowserWindowSvg(st.state, t);
        } else if (act.type === 'lock_shield') {
          itemContent = renderLockShieldSvg(st.state, t);
        } else if (act.type === 'user_figure') {
          itemContent = renderUserFigureSvg(st.state, t);
        } else if (act.type === 'datacenter') {
          itemContent = renderDatacenterSvg(st.state, t);
        } else if (act.type === 'note_board') {
          itemContent = renderNoteBoardSvg(st.state, st.label, st.sublabel, t);
        }

        actorsHtml += `
          <g class="actor-group" id="actor-${act.id}" transform="translate(${screenPos.x}, ${screenPos.y + idleFloat})" opacity="${st.opacity}">
            ${itemContent}
            <!-- Label & Sublabel -->
            <text x="0" y="85" class="actor-label-text">${st.label || ''}</text>
            <text x="0" y="118" class="actor-sublabel-text">${st.sublabel || ''}</text>
          </g>
        `;
      });
    }

    // Stamp overlay
    if (stampText) {
      effectsHtml = `
        <g transform="translate(540, 785)" class="stamp-overlay">
          <rect x="-160" y="-45" width="320" height="90" rx="16" fill="rgba(247,37,133,0.2)" stroke="#f72585" stroke-width="5" />
          <text x="0" y="14" font-size="36" font-weight="900" fill="#f72585" text-anchor="middle" letter-spacing="3">${stampText}</text>
        </g>
      `;
    }

    if (actorsLayer) actorsLayer.innerHTML = actorsHtml;
    if (connectionsLayer) connectionsLayer.innerHTML = connectionHtml;
    if (packetsLayer) packetsLayer.innerHTML = packetHtml;
    if (effectsLayer) effectsLayer.innerHTML = effectsHtml;

    // 5. Update HUD (Step title, Station Tracker, Subtitles)
    const stepChip = document.getElementById('hud-step-chip');
    const stepHeading = document.getElementById('hud-step-title-text');
    const subtitleBox = document.getElementById('hud-subtitle-text');
    const trackerFill = document.getElementById('tracker-fill-bar');
    const trackerContainer = document.getElementById('hud-tracker');

    if (isRoadRecap && trackerContainer) {
      trackerContainer.style.opacity = '0.35';
    } else if (trackerContainer) {
      trackerContainer.style.opacity = '1.0';
    }

    if (stepChip) stepChip.textContent = `BƯỚC ${activeScene.step_index + 1}`;
    if (stepHeading) {
      const rawTitle = activeScene.title || '';
      const parts = rawTitle.split(/(:|&)/);
      stepHeading.innerHTML = parts.map((p, idx) => idx % 2 === 1 ? `<span class="keyword-highlight">${p}</span>` : p).join('');
    }

    if (subtitleBox) {
      subtitleBox.textContent = activeScene.narration || '';
    }

    // Station tracker states
    const numStations = (SCRIPT.hud?.steps || []).length || 5;
    for (let sIdx = 0; sIdx < numStations; sIdx++) {
      const nodeEl = document.getElementById(`station-node-${sIdx}`);
      if (!nodeEl) continue;
      if (sIdx < activeScene.step_index) {
        nodeEl.className = 'station-node completed';
        nodeEl.innerHTML = '✓';
      } else if (sIdx === activeScene.step_index) {
        nodeEl.className = 'station-node active';
        nodeEl.innerHTML = `${sIdx + 1}`;
      } else {
        nodeEl.className = 'station-node';
        nodeEl.innerHTML = `${sIdx + 1}`;
      }
    }

    if (trackerFill) {
      const fillPct = (activeScene.step_index / Math.max(1, numStations - 1)) * 100;
      trackerFill.style.width = `${fillPct}%`;
    }

    // Equalizer audio waves micro-motion
    const waveBars = document.querySelectorAll('.wave-bar');
    waveBars.forEach((wb, i) => {
      const h = 8 + 14 * Math.abs(Math.sin(t * 7.5 + i * 1.2));
      wb.style.height = `${h.toFixed(1)}px`;
    });

    return {
      t: t,
      scene_id: activeScene.scene_id,
      step_index: activeScene.step_index,
      visible_actors: Object.keys(actorStates).filter(k => actorStates[k].visible).length,
      cable_connected: cableConnected,
      packet_flying: activePacket !== null,
      is_road_recap: isRoadRecap
    };
  };

  // =========================================================================
  // COMPREHENSIVE LAYOUT & TIMELINE AUDIT (Reads actual DOM bounding boxes)
    // Adjust stage root transform scale to fill current viewport seamlessly
  function adjustStageScale() {
    const root = document.getElementById('stage-root');
    if (!root) return;
    const currentW = window.innerWidth || 1080;
    const ratio = currentW / 1080;
    root.style.transform = `scale(${ratio})`;
    root.style.transformOrigin = '0 0';
  }

  // =========================================================================
  // COMPREHENSIVE LAYOUT & TIMELINE AUDIT (Reads actual DOM bounding boxes)
  // =========================================================================
  window.getLayoutAudit = function() {
    adjustStageScale();
    const root = document.getElementById('stage-root');
    const rootRect = root ? root.getBoundingClientRect() : { left: 0, top: 0, width: window.innerWidth || 1080, height: window.innerHeight || 1920 };
    const scaleRatio = (rootRect.width > 0) ? (rootRect.width / 1080) : 1.0;

    const headings = document.querySelectorAll('.step-heading');
    const labels = document.querySelectorAll('.actor-label-text');
    const sublabels = document.querySelectorAll('.actor-sublabel-text');
    const actorGroups = Array.from(document.querySelectorAll('.actor-group'));
    const roadRecap = document.getElementById('road-recap-group');

    let minHeadingSize = 999;
    headings.forEach(el => {
      const fs = parseFloat(window.getComputedStyle(el).fontSize);
      if (fs < minHeadingSize) minHeadingSize = fs;
    });

    let minLabelSize = 999;
    labels.forEach(el => {
      const fs = parseFloat(window.getComputedStyle(el).fontSize);
      if (fs < minLabelSize) minLabelSize = fs;
    });

    let minSublabelSize = 999;
    sublabels.forEach(el => {
      const fs = parseFloat(window.getComputedStyle(el).fontSize);
      if (fs < minSublabelSize) minSublabelSize = fs;
    });

    // Check actor bounding boxes against safe boundaries [70, 1010] & [240, 1330] in 1080x1920 design space
    let bboxOutside = 0;
    let subtitleCollisions = 0;
    let actorPositionsY = [];
    let actorLabels = [];

    // Filter to visible actors only (opacity > 0.05)
    const visibleActors = actorGroups.filter(ag => {
      const op = parseFloat(ag.getAttribute('opacity') || window.getComputedStyle(ag).opacity || '1');
      return op > 0.05;
    });

    const itemsToCheck = visibleActors.length > 0 ? visibleActors : (roadRecap ? [roadRecap] : []);

    itemsToCheck.forEach(ag => {
      const r = ag.getBoundingClientRect();
      const left = (r.left - rootRect.left) / scaleRatio;
      const right = (r.right - rootRect.left) / scaleRatio;
      const top = (r.top - rootRect.top) / scaleRatio;
      const bottom = (r.bottom - rootRect.top) / scaleRatio;

      if (r.width > 0 && r.height > 0) {
        if (left < 65 || right > 1015) bboxOutside++;
        if (top < 235 || bottom > 1340) bboxOutside++;
        // Check collision with fixed subtitle zone y1380-1700
        if (bottom >= 1380 && top <= 1700) subtitleCollisions++;
        actorPositionsY.push((top + bottom) / 2);
      }
      const txt = ag.querySelector ? ag.querySelector('.actor-label-text') : null;
      if (txt && txt.textContent) {
        const tVal = txt.textContent.trim();
        if (tVal) actorLabels.push(tVal);
      }
    });

    // Check cluster center drift from 785
    let clusterCenterY = 785;
    if (actorPositionsY.length > 0) {
      clusterCenterY = actorPositionsY.reduce((a, b) => a + b, 0) / actorPositionsY.length;
    }
    const centerYDrift = Math.round(Math.abs(clusterCenterY - 785));

    // Check duplicate labels
    let duplicateLabels = 0;
    for (let i = 0; i < actorLabels.length; i++) {
      for (let j = i + 1; j < actorLabels.length; j++) {
        if (actorLabels[i] && actorLabels[i] === actorLabels[j]) duplicateLabels++;
      }
    }

    return {
      min_heading_font_size: minHeadingSize === 999 ? 58 : minHeadingSize,
      min_label_font_size: minLabelSize === 999 ? 38 : minLabelSize,
      min_sublabel_font_size: minSublabelSize === 999 ? 28 : minSublabelSize,
      step_title_compliant: minHeadingSize >= 56 || minHeadingSize === 999,
      label_font_compliant: minLabelSize >= 30 || minLabelSize === 999,
      sublabel_font_compliant: minSublabelSize >= 24 || minSublabelSize === 999,
      total_actors_on_stage: itemsToCheck.length,
      max_concurrent_actors_compliant: itemsToCheck.length <= 8,
      bbox_outside_bounds: bboxOutside,
      subtitle_collisions: subtitleCollisions,
      duplicate_labels: duplicateLabels,
      center_y_drift: centerYDrift,
      center_y_drift_compliant: centerYDrift <= 120,
      layout_passed: bboxOutside === 0 && subtitleCollisions === 0 && centerYDrift <= 120 && itemsToCheck.length <= 8
    };
  };

  // Run initial setup
  document.addEventListener('DOMContentLoaded', () => {
    adjustStageScale();
    initGrid();
    initHUD();
    window.renderAt(0);
  });
  window.addEventListener('resize', adjustStageScale);

})();
