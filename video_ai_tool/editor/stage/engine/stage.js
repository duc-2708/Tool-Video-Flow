/* Stage Engine Runtime - Deterministic Isometric Scene Graph & Timeline */
(function() {
  'use strict';

  const SCRIPT = window.STAGE_SCRIPT || { hud: { steps: [] }, actors: [], scenes: [] };
  const cos30 = 0.86602540378;
  const sin30 = 0.5;
  const originX = 540;
  const originY = 920;

  function toScreen(x, y, z) {
    return {
      x: originX + (x - y) * cos30,
      y: originY + (x + y) * sin30 - (z || 0)
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

    // Ambient dust particles
    const dustGroup = document.getElementById('grid-dust-group');
    if (dustGroup) {
      let dustSvg = '';
      for (let i = 0; i < 28; i++) {
        const px = 80 + ((i * 137.5) % 920);
        const py = 320 + ((i * 229.3) % 1150);
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

  // Render SVG Isometric Actors
  function renderLaptopSvg(state, typingText, isGlow) {
    const baseW = 180;
    const baseH = 140;
    // Base plate points in isometric 2D
    const p1 = toScreen(-baseW / 2, -baseH / 2, 0);
    const p2 = toScreen(baseW / 2, -baseH / 2, 0);
    const p3 = toScreen(baseW / 2, baseH / 2, 0);
    const p4 = toScreen(-baseW / 2, baseH / 2, 0);

    // Thickness
    const p1_b = toScreen(-baseW / 2, -baseH / 2, -10);
    const p4_b = toScreen(-baseW / 2, baseH / 2, -10);
    const p3_b = toScreen(baseW / 2, baseH / 2, -10);

    // Screen lid: angle depends on state
    const isOpen = (state !== 'closed');
    const lidHeight = isOpen ? 120 : 0;
    const lidZ = isOpen ? 105 : 0;

    const s1 = toScreen(-baseW / 2, -baseH / 2, 0);
    const s2 = toScreen(baseW / 2, -baseH / 2, 0);
    const s3 = toScreen(baseW / 2, -baseH / 2 - (isOpen ? 20 : 0), lidZ);
    const s4 = toScreen(-baseW / 2, -baseH / 2 - (isOpen ? 20 : 0), lidZ);

    const glowFilter = isGlow ? 'filter="url(#neon-glow-filter)" stroke="#00f5d4" stroke-width="3"' : '';

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
        <text x="${s4.x + 18}" y="${s4.y + 44}" font-family="Courier, monospace" font-size="16" font-weight="700" fill="#00f5d4" filter="drop-shadow(0 0 4px #00f5d4)">$ ${typingText}<tspan fill="#ffffff" opacity="${Math.sin(Date.now() / 150) > 0 ? 1 : 0}">_</tspan></text>
      ` : `
        <!-- Closed lid -->
        <polygon points="${p1.x},${p1.y} ${p2.x},${p2.y} ${p3.x},${p3.y} ${p4.x},${p4.y}" fill="#160c30" stroke="#9d4edd" stroke-width="2" />
        <circle cx="${(p1.x+p3.x)/2}" cy="${(p1.y+p3.y)/2}" r="10" fill="none" stroke="#00f5d4" stroke-width="1.5" opacity="0.6" />
      `}
    `;
  }

  function renderVpsServerSvg(state, isBusy, isContainerStacked) {
    const w = 150;
    const d = 150;
    const h = 180;

    // Base isometric box
    const b1 = toScreen(-w/2, -d/2, 0);
    const b2 = toScreen(w/2, -d/2, 0);
    const b3 = toScreen(w/2, d/2, 0);
    const b4 = toScreen(-w/2, d/2, 0);

    const t1 = toScreen(-w/2, -d/2, h);
    const t2 = toScreen(w/2, -d/2, h);
    const t3 = toScreen(w/2, d/2, h);
    const t4 = toScreen(-w/2, d/2, h);

    const isOn = (state === 'on' || state === 'busy');
    const ledColor = state === 'busy' ? '#f72585' : (isOn ? '#00f5d4' : '#552233');
    const rackGlow = isOn ? 'filter="url(#neon-glow-filter)" stroke="#00f5d4" stroke-width="2"' : 'stroke="#9d4edd" stroke-width="1.5"';

    let dockerSvg = '';
    if (isContainerStacked) {
      // Docker container cube on top
      const cW = 120, cD = 120, cH = 80;
      const ct1 = toScreen(-cW/2, -cD/2, h + cH);
      const ct2 = toScreen(cW/2, -cD/2, h + cH);
      const ct3 = toScreen(cW/2, cD/2, h + cH);
      const ct4 = toScreen(-cW/2, cD/2, h + cH);

      const cb1 = toScreen(-cW/2, -cD/2, h);
      const cb2 = toScreen(cW/2, -cD/2, h);
      const cb3 = toScreen(cW/2, cD/2, h);
      const cb4 = toScreen(-cW/2, cD/2, h);

      dockerSvg = `
        <g id="docker-container-box">
          <!-- Docker Cube Left face -->
          <polygon points="${cb4.x},${cb4.y} ${cb3.x},${cb3.y} ${ct3.x},${ct3.y} ${ct4.x},${ct4.y}" fill="#0077b6" stroke="#00f5d4" stroke-width="1.5" />
          <!-- Docker Cube Right face -->
          <polygon points="${cb3.x},${cb3.y} ${cb2.x},${cb2.y} ${ct2.x},${ct2.y} ${ct3.x},${ct3.y}" fill="#023e8a" stroke="#00f5d4" stroke-width="1.5" />
          <!-- Docker Cube Top face -->
          <polygon points="${ct1.x},${ct1.y} ${ct2.x},${ct2.y} ${ct3.x},${ct3.y} ${ct4.x},${ct4.y}" fill="#0096c7" stroke="#ffffff" stroke-width="1.5" />
          <!-- Docker Whale / Label text -->
          <text x="${(cb3.x+ct4.x)/2}" y="${(cb3.y+ct4.y)/2 + 6}" font-size="18" font-weight="800" fill="#ffffff" text-anchor="middle">🐳 DOCKER</text>
        </g>
      `;
    }

    return `
      <!-- Server Shadow -->
      <polygon points="${b1.x},${b1.y + 14} ${b2.x},${b2.y + 14} ${b3.x},${b3.y + 14} ${b4.x},${b4.y + 14}" fill="rgba(3,1,8,0.7)" />
      <!-- Chassis Left Face (Front rack) -->
      <polygon points="${b4.x},${b4.y} ${b3.x},${b3.y} ${t3.x},${t3.y} ${t4.x},${t4.y}" fill="#13092b" ${rackGlow} />
      <!-- Chassis Right Face (Side depth) -->
      <polygon points="${b3.x},${b3.y} ${b2.x},${b2.y} ${t2.x},${t2.y} ${t3.x},${t3.y}" fill="#0b041c" stroke="#9d4edd" stroke-width="1.5" />
      <!-- Chassis Top Face -->
      <polygon points="${t1.x},${t1.y} ${t2.x},${t2.y} ${t3.x},${t3.y} ${t4.x},${t4.y}" fill="#221144" stroke="#9d4edd" stroke-width="1.5" />

      <!-- Rack bays & Status LEDs on front face -->
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

  // Master renderAt evaluation function
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

    // 2. Camera interpolation
    const camTarget = activeScene.camera || { x: 540, y: 920, zoom: 1.0, tilt: 0 };
    const vp = document.getElementById('world-viewport');
    if (vp) {
      const zoom = camTarget.zoom || 1.0;
      const tilt = camTarget.tilt || 0;
      const panX = camTarget.x - 540;
      const panY = camTarget.y - 920;
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
        highlightColor: null,
        opacity: 0,
        label: act.label,
        sublabel: act.sublabel
      };
    });

    let activePacket = null;
    let cableConnected = false;

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
            }
          } else if (act.verb === 'highlight') {
            const tgt = actorStates[act.target];
            if (tgt) {
              tgt.isGlow = true;
              tgt.highlightColor = act.params?.color || '#00f5d4';
            }
          }
        }
      });
    });

    // 4. Render Actors Layer in SVG
    const actorsLayer = document.getElementById('actors-layer');
    const connectionsLayer = document.getElementById('connections-layer');
    const packetsLayer = document.getElementById('packets-layer');

    let actorsHtml = '';
    let connectionHtml = '';
    let packetHtml = '';

    // Ports for connection
    const laptopPos = actorStates['laptop_client']?.pos || [-220, 40, 0];
    const vpsPos = actorStates['vps_server']?.pos || [220, -40, 0];

    const pFrom = toScreen(laptopPos[0] + 60, laptopPos[1] - 40, 10);
    const pTo = toScreen(vpsPos[0] - 60, vpsPos[1] + 20, 30);

    // Cable rendering
    if (cableConnected) {
      const midX = (pFrom.x + pTo.x) / 2;
      const midY = (pFrom.y + pTo.y) / 2 + 70;
      const pathD = `M ${pFrom.x} ${pFrom.y} Q ${midX} ${midY} ${pTo.x} ${pTo.y}`;
      connectionHtml = `
        <path d="${pathD}" class="connection-cable" />
        <path d="${pathD}" class="connection-pulse" stroke-dashoffset="${-t * 80}" />
      `;

      // Packet flying along cable
      if (activePacket && activePacket.progress < 1.0) {
        const u = activePacket.progress;
        // Quadratic Bezier interpolation
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
    SCRIPT.actors.forEach(act => {
      const st = actorStates[act.id];
      if (!st || !st.visible || st.opacity <= 0) return;

      const screenPos = toScreen(st.pos[0], st.pos[1], st.pos[2]);
      let itemContent = '';

      if (act.type === 'laptop') {
        itemContent = renderLaptopSvg(st.state, st.typingText, st.isGlow);
      } else if (act.type === 'vps_server') {
        itemContent = renderVpsServerSvg(st.state, st.state === 'busy', st.isContainerStacked);
      }

      actorsHtml += `
        <g class="actor-group" id="actor-${act.id}" transform="translate(${screenPos.x}, ${screenPos.y})" opacity="${st.opacity}">
          ${itemContent}
          <!-- Label & Sublabel -->
          <text x="0" y="85" class="actor-label-text">${st.label || ''}</text>
          <text x="0" y="118" class="actor-sublabel-text">${st.sublabel || ''}</text>
        </g>
      `;
    });

    if (actorsLayer) actorsLayer.innerHTML = actorsHtml;
    if (connectionsLayer) connectionsLayer.innerHTML = connectionHtml;
    if (packetsLayer) packetsLayer.innerHTML = packetHtml;

    // 5. Update HUD (Step title, Station Tracker, Subtitles)
    const stepChip = document.getElementById('hud-step-chip');
    const stepHeading = document.getElementById('hud-step-title-text');
    const subtitleBox = document.getElementById('hud-subtitle-text');
    const trackerFill = document.getElementById('tracker-fill-bar');

    if (stepChip) stepChip.textContent = `BƯỚC ${activeScene.step_index + 1}`;
    if (stepHeading) {
      // Highlight keywords in title
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
      packet_flying: activePacket !== null
    };
  };

  // Layout audit measurement function for testing & QC
  window.getLayoutAudit = function() {
    const headings = document.querySelectorAll('.step-heading');
    const labels = document.querySelectorAll('.actor-label-text');
    const sublabels = document.querySelectorAll('.actor-sublabel-text');

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

    return {
      min_heading_font_size: minHeadingSize === 999 ? 0 : minHeadingSize,
      min_label_font_size: minLabelSize === 999 ? 0 : minLabelSize,
      min_sublabel_font_size: minSublabelSize === 999 ? 0 : minSublabelSize,
      step_title_compliant: minHeadingSize >= 56,
      label_font_compliant: minLabelSize >= 30,
      sublabel_font_compliant: minSublabelSize >= 24,
      total_actors_on_stage: document.querySelectorAll('.actor-group').length
    };
  };

  // Run initial setup
  document.addEventListener('DOMContentLoaded', () => {
    initGrid();
    initHUD();
    window.renderAt(0);
  });
})();
