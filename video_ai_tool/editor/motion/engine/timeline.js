/* Master Timeline: Coordinates the 6 visual layers and enforces minimum 3 simultaneous moving layers.
 * Driven strictly by absolute time t.
 */
(()=>{'use strict';

const { calculateCamera } = window.MotionCamera;
const { calculateScreenShake, renderBokeh } = window.MotionParticles;
const { clamp } = window.MotionEasing;

class MasterTimeline {
  constructor(stageEl, options = {}) {
    this.stage = stageEl;
    this.options = options;
    this.layers = {};
    this.setupLayers();
  }

  setupLayers() {
    this.stage.classList.add('master-scene-container');
    this.stage.replaceChildren();

    // 1. Background Layer (Canvas for Bokeh / Gradients)
    this.bgCanvas = document.createElement('canvas');
    this.bgCanvas.className = 'layer-background';
    this.bgCanvas.width = 1080;
    this.bgCanvas.height = 1920;
    this.bgCtx = this.bgCanvas.getContext('2d');

    // 2. SVG Root for Content & Annotations
    this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    this.svg.setAttribute('viewBox', '0 0 1080 1920');
    this.svg.className = 'layer-svg-root';

    // SVG Defs (glow filters, gradients)
    this.svg.innerHTML = `
      <defs>
        <radialGradient id="neon-radial" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.35"/>
          <stop offset="60%" stop-color="var(--accent)" stop-opacity="0.08"/>
          <stop offset="100%" stop-color="transparent" stop-opacity="0"/>
        </radialGradient>
        <linearGradient id="liquid-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.95"/>
          <stop offset="100%" stop-color="var(--secondary)" stop-opacity="0.75"/>
        </linearGradient>
        <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="8" result="blur"/>
          <feMerge>
            <feMergeNode in="blur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>
    `;

    // Content Layer Group
    this.gContent = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    this.gContent.setAttribute('class', 'layer-content');

    // Annotations Layer Group
    this.gAnnotations = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    this.gAnnotations.setAttribute('class', 'layer-annotations');

    this.svg.append(this.gContent, this.gAnnotations);

    // 3. Captions Layer Container
    this.captionsEl = document.createElement('div');
    this.captionsEl.className = 'layer-captions';

    // 4. FX / Post Layer Overlay
    this.fxEl = document.createElement('div');
    this.fxEl.className = 'layer-fx-overlay';

    this.stage.append(this.bgCanvas, this.svg, this.captionsEl, this.fxEl);
  }

  seek(t, spec, duration = 5, words = [], annotations = []) {
    t = Math.max(0, Math.min(duration, t));

    // 1. Calculate Camera & Parallax
    const cam = calculateCamera(t, duration, spec.camera || {});
    const hitTimes = (spec.beats || [])
      .filter(b => b.action === 'beat_hit' || b.action === 'stamp')
      .map(b => b.at_sec || 0);

    const shake = calculateScreenShake(t, hitTimes, 12);

    // Apply Camera transform to Stage root (drifts + shake)
    this.stage.style.transform = `translate(${shake.dx}px, ${shake.dy}px) rotate(${cam.tilt}deg)`;

    // 2. Background Layer (Layer 1 moving continuously)
    this.bgCtx.clearRect(0, 0, 1080, 1920);
    renderBokeh(this.bgCtx, 1080, 1920, t, 16, spec.scene_type || 'scene');
    if (window.MotionParticles && window.MotionParticles.renderLightSweep) {
      window.MotionParticles.renderLightSweep(this.bgCtx, 1080, 1920, t, hitTimes);
    }
    if (spec.transition === 'glitch_cut' && window.MotionParticles && window.MotionParticles.renderGlitchCut) {
      window.MotionParticles.renderGlitchCut(this.bgCtx, 1080, 1920, t, 0, 0.18);
    }

    // 3. Content Layer (Layer 2 moving)
    this.gContent.replaceChildren();
    const sceneType = spec.scene_type || 'stat_number';
    const d = spec.data || {};
    const variantIdx = (spec.variant_index ?? 0) % 3;

    let depthHandled = false;
    const depthEnabled = Boolean(window.DEPTH_3D_ENABLED || spec.depth_3d || (window.MOTION_DATA && window.MOTION_DATA.depth_3d));
    let depthHost = this.stage.querySelector('.depth-host-container');
    if (depthHost) {
      depthHost.replaceChildren();
    }
    if (depthEnabled && window.renderDepth3D) {
      if (!depthHost) {
        depthHost = document.createElement('div');
        depthHost.className = 'depth-host-container';
        depthHost.style.cssText = 'position:absolute;top:0;left:0;width:1080px;height:1920px;pointer-events:none;z-index:6;';
        this.stage.insertBefore(depthHost, this.captionsEl);
      }
      depthHandled = window.renderDepth3D(sceneType, depthHost, { data: d }, t, { width: 1080, height: 1920, duration, variant_index: variantIdx });
    }

    if (depthHandled) {
      // 3D Engine handled this scene, 2D recipe skipped
    } else if (window.MotionVocabulary && typeof window.MotionVocabulary[sceneType] === 'function') {
      window.MotionVocabulary[sceneType](this.bgCtx, this.gContent, d, t, duration);
    } else if (sceneType === 'stat_number' || sceneType === 'numeric') {
      window.MotionRecipes.renderStatNumber(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'bar_compare' || sceneType === 'bar_grow' || sceneType === 'compare_bars') {
      window.MotionRecipes.renderBarCompare(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'flow_chain') {
      window.MotionRecipes.renderFlowChain(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'hub_spoke' || sceneType === 'network_nodes') {
      window.MotionRecipes.renderHubSpoke(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'container_fill') {
      window.MotionRecipes.renderContainerFill(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'checklist') {
      window.MotionRecipes.renderChecklist(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'mock_ui_window') {
      window.MotionRecipes.renderMockUIWindow(this.bgCtx, this.gContent, d, t, duration);
    } else if (sceneType === 'magnifier_check') {
      window.MotionRecipes.renderMagnifierCheck(this.bgCtx, this.gContent, d, t, duration);
    } else if (sceneType === 'versus_split') {
      window.MotionRecipes.renderVersusSplit(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'line_chart_draw') {
      window.MotionRecipes.renderLineChartDraw(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'terminal_typing' || sceneType === 'code_card') {
      window.MotionRecipes.renderTerminalTyping(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'timeline') {
      window.MotionRecipes.renderTimeline(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'funnel') {
      window.MotionRecipes.renderFunnel(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'progress_tracker') {
      window.MotionRecipes.renderProgressTracker(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'source_badge') {
      window.MotionRecipes.renderSourceBadge(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'icon_tile') {
      window.MotionRecipes.renderIconTile(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'chat_bubble_poll') {
      window.MotionRecipes.renderChatBubblePoll(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (sceneType === 'gauge_ring') {
      window.MotionRecipes.renderGaugeRing(this.bgCtx, this.gContent, d, t, duration, variantIdx);
    } else if (window.MotionScenes && window.MotionScenes.paint && window.MotionScenes.paint[sceneType]) {
      // Legacy fallback renderer
      const context = {
        svg: this.svg,
        mid: this.gContent,
        front: this.gAnnotations,
        d, t, p: clamp(t / duration),
        duration,
        type: sceneType,
        hold: 1.2,
        numberProgress: clamp(t / (duration * 0.5)),
        row: i => clamp((t - (0.2 + i * 0.5)) / 0.35)
      };
      window.MotionScenes.paint[sceneType](context);
    } else {
      // General text_focus
      window.MotionRecipes.renderStatNumber(this.bgCtx, this.gContent, d, t, duration, 0);
    }

    // 4. Annotations Layer (Layer 3 moving)
    this.gAnnotations.replaceChildren();
    if (annotations && annotations.length) {
      annotations.forEach(annot => {
        const bounds = { x: 300, y: 760, w: 480, h: 120 };
        window.MotionRecipes.renderAnnotation(this.gAnnotations, annot, bounds, t);
      });
    }

    // 5. Captions Layer (Synchronized words)
    this.captionsEl.replaceChildren();
    if (words && words.length) {
      const activeWord = words.find(w => t >= w.start && t < w.end);
      const span = document.createElement('span');
      span.className = 'caption-text';
      if (activeWord) {
        span.textContent = activeWord.text;
        span.style.color = 'var(--accent)';
      }
      this.captionsEl.append(span);
    }

    // Count moving layers:
    // Layer 1 (background bokeh): always active.
    // Layer 2 (content layer): always active.
    // Layer 3 (camera / drift / shake): always active.
    // Layer 4 (annotations or captions): active when present.
    return {
      t,
      moving_layers: 3 + (annotations.length ? 1 : 0) + (words.length ? 1 : 0),
      moving_elements: this.gContent.querySelectorAll('*').length + this.gAnnotations.querySelectorAll('*').length
    };
  }
}

window.MotionEngine = {
  MasterTimeline
};
})();
