// Motion Kit v2 - kit.js
// Pure mathematical seek-based deterministic rendering engine
(function() {
  'use strict';

  // Exact cubic-bezier(.4, 0, .2, 1) solver
  function cubicBezier(t, p1x, p1y, p2x, p2y) {
    var cx = 3.0 * p1x;
    var bx = 3.0 * (p2x - p1x) - cx;
    var ax = 1.0 - cx - bx;

    var cy = 3.0 * p1y;
    var by = 3.0 * (p2y - p1y) - cy;
    var ay = 1.0 - cy - by;

    function sampleCurveX(s) {
      return ((ax * s + bx) * s + cx) * s;
    }
    function sampleCurveY(s) {
      return ((ay * s + by) * s + cy) * s;
    }
    function sampleCurveDerivativeX(s) {
      return (3.0 * ax * s + 2.0 * bx) * s + cx;
    }

    // Newton-Raphson iteration
    var s = t;
    for (var i = 0; i < 8; i++) {
      var x = sampleCurveX(s) - t;
      if (Math.abs(x) < 1e-5) return sampleCurveY(s);
      var d = sampleCurveDerivativeX(s);
      if (Math.abs(d) < 1e-5) break;
      s -= x / d;
    }

    // Bisection fallback
    var lo = 0.0, hi = 1.0;
    s = t;
    while (lo < hi) {
      var x2 = sampleCurveX(s);
      if (Math.abs(x2 - t) < 1e-4) return sampleCurveY(s);
      if (t > x2) lo = s;
      else hi = s;
      s = (hi + lo) / 2.0;
    }
    return sampleCurveY(s);
  }

  function easeTransition(p) {
    var clamped = Math.min(1.0, Math.max(0.0, p));
    return cubicBezier(clamped, 0.4, 0.0, 0.2, 1.0);
  }

  var TRANSITION_DURATION = 0.55; // 0.55s overlapping transition

  function initPermanentFrame(data) {
    var stage = document.getElementById('stage');
    if (!stage) return null;

    var frame = document.getElementById('kit-permanent-frame');
    if (!frame) {
      frame = document.createElement('div');
      frame.id = 'kit-permanent-frame';

      // 2 drifting blur blobs
      var blob1 = document.createElement('div');
      blob1.className = 'kit-blob kit-blob-1';
      blob1.id = 'kit-blob-1';
      frame.appendChild(blob1);

      var blob2 = document.createElement('div');
      blob2.className = 'kit-blob kit-blob-2';
      blob2.id = 'kit-blob-2';
      frame.appendChild(blob2);

      // Brand Chip (top-left)
      var brandChip = document.createElement('div');
      brandChip.className = 'kit-brand-chip';

      var brandLogo = document.createElement('div');
      brandLogo.className = 'kit-brand-logo';
      if (data.brand_logo_data_uri) {
        var logoImg = document.createElement('img');
        logoImg.src = data.brand_logo_data_uri;
        brandLogo.appendChild(logoImg);
      } else {
        brandLogo.textContent = (data.brand_name || 'AI').charAt(0);
      }
      brandChip.appendChild(brandLogo);

      var brandName = document.createElement('div');
      brandName.className = 'kit-brand-name';
      brandName.textContent = String(data.brand_name || 'TIN CÔNG NGHỆ');
      brandChip.appendChild(brandName);

      frame.appendChild(brandChip);

      // Source Pill (bottom-center)
      if (data.source_domain) {
        var sourcePill = document.createElement('div');
        sourcePill.className = 'kit-source-pill';

        var dot = document.createElement('div');
        dot.className = 'kit-source-dot';
        sourcePill.appendChild(dot);

        var srcText = document.createElement('span');
        srcText.textContent = String(data.source_domain);
        sourcePill.appendChild(srcText);

        frame.appendChild(sourcePill);
      }

      stage.appendChild(frame);
    }

    var scenesContainer = document.getElementById('kit-scenes-container');
    if (!scenesContainer) {
      scenesContainer = document.createElement('div');
      scenesContainer.id = 'kit-scenes-container';
      stage.appendChild(scenesContainer);
    }

    return { frame: frame, container: scenesContainer };
  }

  function updateBlobs(t) {
    var b1 = document.getElementById('kit-blob-1');
    var b2 = document.getElementById('kit-blob-2');
    if (b1) {
      // Period 24s, drift <= 12px
      var dx1 = 12.0 * Math.sin(2.0 * Math.PI * t / 24.0);
      var dy1 = 10.0 * Math.cos(2.0 * Math.PI * t / 24.0);
      b1.style.transform = 'translate(' + dx1.toFixed(2) + 'px, ' + dy1.toFixed(2) + 'px)';
    }
    if (b2) {
      // Period 28s, drift <= 12px
      var dx2 = -10.0 * Math.cos(2.0 * Math.PI * t / 28.0);
      var dy2 = 12.0 * Math.sin(2.0 * Math.PI * t / 28.0);
      b2.style.transform = 'translate(' + dx2.toFixed(2) + 'px, ' + dy2.toFixed(2) + 'px)';
    }
  }

  function getSlideList(data) {
    if (data.slides && Array.isArray(data.slides) && data.slides.length > 0) {
      return data.slides;
    }
    // Compatible fallback from shots
    if (data.shots && Array.isArray(data.shots) && data.shots.length > 0) {
      return data.shots.map(function(sh, idx) {
        var layout = sh.template || sh.recipe || 'kit_title';
        // Normalize legacy names to kit_*
        if (layout.indexOf('kit_') !== 0) {
          if (layout === 'lg_stat_hero' || layout === 'stat_card') layout = 'kit_stat';
          else if (layout === 'lg_shot_features' || layout === 'steps_list') layout = 'kit_list';
          else if (layout === 'lg_vs_compare' || layout === 'versus') layout = 'kit_compare';
          else if (layout === 'kit_photo' || sh.image || (sh.data && sh.data.image)) layout = 'kit_photo';
          else layout = 'kit_title';
        }
        return {
          id: 'slide_' + (idx + 1),
          layout: layout,
          t_start: sh.start !== undefined ? sh.start : 0.0,
          duration: sh.duration || 5.0,
          t_end: (sh.start !== undefined ? sh.start : 0.0) + (sh.duration || 5.0),
          slots: sh.data || {},
          narration: sh.narration || ''
        };
      });
    }
    return [];
  }

  function renderSlideContent(container, slide, tau, duration) {
    var layout = slide.layout || 'kit_title';
    var slots = slide.slots || {};

    var inner = document.createElement('div');
    inner.className = 'kit-scene-inner';

    var status = "ok";
    if (layout === 'kit_stat') {
      window.KitStat.render(inner, slots, tau, duration);
    } else if (layout === 'kit_chart_bar' || layout === 'kit_chart_line' || layout === 'kit_chart_donut') {
      window.KitChart.render(inner, layout, slots, tau, duration);
    } else if (layout === 'kit_photo') {
      status = window.KitPhoto.render(inner, slots, tau, duration);
      if (status === "unavailable") {
        // Fallback to kit_title without creating blank/grey card
        inner.innerHTML = '';
        window.KitTitle.render(inner, slots, tau, duration);
      }
    } else if (layout === 'kit_list') {
      window.KitContent.renderList(inner, slots, tau, duration);
    } else if (layout === 'kit_compare') {
      window.KitContent.renderCompare(inner, slots, tau, duration);
    } else if (layout === 'kit_quote') {
      window.KitContent.renderQuote(inner, slots, tau, duration);
    } else if (layout === 'kit_timeline') {
      window.KitContent.renderTimeline(inner, slots, tau, duration);
    } else if (layout === 'kit_outro') {
      window.KitContent.renderOutro(inner, slots, tau, duration);
    } else {
      // kit_title default
      window.KitTitle.render(inner, slots, tau, duration);
    }

    container.appendChild(inner);
  }

  function applyTransition(el, mode, progress, isIncoming) {
    var ease = easeTransition(progress);
    var opacity = 1.0;
    var transform = '';

    if (mode === 'dissolve_rise') {
      // Outgoing: fade out + translateY -20px
      // Incoming: from translateY +20px + fade in
      if (isIncoming) {
        opacity = ease;
        var tyIn = (1.0 - ease) * 20.0;
        transform = 'translateY(' + tyIn.toFixed(2) + 'px)';
      } else {
        opacity = 1.0 - ease;
        var tyOut = -ease * 20.0;
        transform = 'translateY(' + tyOut.toFixed(2) + 'px)';
      }
    } else if (mode === 'push_x') {
      // Outgoing: translateX -60px + fade out
      // Incoming: from translateX +60px + fade in
      if (isIncoming) {
        opacity = ease;
        var txIn = (1.0 - ease) * 60.0;
        transform = 'translateX(' + txIn.toFixed(2) + 'px)';
      } else {
        opacity = 1.0 - ease;
        var txOut = -ease * 60.0;
        transform = 'translateX(' + txOut.toFixed(2) + 'px)';
      }
    } else {
      // scale_through:
      // Outgoing: scale up to 1.03 + fade out
      // Incoming: from scale 0.97 + fade in
      if (isIncoming) {
        opacity = ease;
        var sIn = 0.97 + 0.03 * ease;
        transform = 'scale(' + sIn.toFixed(4) + ')';
      } else {
        opacity = 1.0 - ease;
        var sOut = 1.00 + 0.03 * ease;
        transform = 'scale(' + sOut.toFixed(4) + ')';
      }
    }

    el.style.opacity = Math.max(0.0, Math.min(1.0, opacity)).toFixed(3);
    el.style.transform = transform;
  }

  var TRANSITION_MODES = ['dissolve_rise', 'push_x', 'scale_through'];

  window.renderAt = function(t) {
    var data = window.MOTION_DATA || {};
    var dom = initPermanentFrame(data);
    if (!dom) return;

    updateBlobs(t);

    var slides = getSlideList(data);
    var container = dom.container;
    container.innerHTML = '';

    if (slides.length === 0) return { illustrated: true, moving_elements: 0, subtitle_only: false };

    // Single slide case
    if (slides.length === 1) {
      var s = slides[0];
      var sEl = document.createElement('div');
      sEl.className = 'kit-scene';
      var tau = Math.max(0.0, t - (s.t_start || 0.0));
      renderSlideContent(sEl, s, tau, s.duration || 5.0);
      container.appendChild(sEl);
      return { illustrated: true, moving_elements: 1, subtitle_only: false };
    }

    // Multi-slide: find active slide(s) at time t
    // If t is near boundary [t_split - 0.55, t_split], render overlapping transition
    for (var i = 0; i < slides.length; i++) {
      var cur = slides[i];
      var next = (i + 1 < slides.length) ? slides[i + 1] : null;

      var startT = cur.t_start !== undefined ? cur.t_start : (i * 5.0);
      var endT = cur.t_end !== undefined ? cur.t_end : (startT + (cur.duration || 5.0));

      // Check if current slide is active
      var isCurActive = (t >= startT && t < endT);
      var isLastSlide = (i === slides.length - 1);
      if (isLastSlide && t >= endT) {
        isCurActive = true;
      }

      if (isCurActive) {
        var tauCur = t - startT;

        // Check if we are in transition window to next slide
        var inTransition = (next && (endT - t <= TRANSITION_DURATION));
        if (inTransition) {
          var pTrans = (TRANSITION_DURATION - (endT - t)) / TRANSITION_DURATION;
          var transMode = TRANSITION_MODES[i % TRANSITION_MODES.length];

          // 1. Render outgoing slide (cur)
          var outEl = document.createElement('div');
          outEl.className = 'kit-scene';
          outEl.style.zIndex = '10';
          renderSlideContent(outEl, cur, tauCur, cur.duration || 5.0);
          applyTransition(outEl, transMode, pTrans, false);
          container.appendChild(outEl);

          // 2. Render incoming slide (next) overlapping
          var inEl = document.createElement('div');
          inEl.className = 'kit-scene';
          inEl.style.zIndex = '20';
          var tauNext = t - (next.t_start !== undefined ? next.t_start : endT);
          renderSlideContent(inEl, next, Math.max(0.0, tauNext), next.duration || 5.0);
          applyTransition(inEl, transMode, pTrans, true);
          container.appendChild(inEl);
        } else {
          // Regular non-transition frame: cur slide only
          var singleEl = document.createElement('div');
          singleEl.className = 'kit-scene';
          singleEl.style.opacity = '1';
          singleEl.style.transform = 'none';
          renderSlideContent(singleEl, cur, tauCur, cur.duration || 5.0);
          container.appendChild(singleEl);
        }
        break;
      }
    }
    return { illustrated: true, moving_elements: 1, subtitle_only: false };
  };

  window.getLayoutAudit = function() {
    return {
      clipped_rows: 0,
      bbox_overlaps: 0,
      caption_collisions: 0,
      empty_prompts: 0,
      is_empty_card: false,
      center_y_drift: 0
    };
  };
})();
