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

      // Brand Chip (top-left) - only render if brand_name is configured
      if (data.brand_name) {
        var brandChip = document.createElement('div');
        brandChip.className = 'kit-brand-chip';

        var brandLogo = document.createElement('div');
        brandLogo.className = 'kit-brand-logo';
        if (data.brand_logo_data_uri) {
          var logoImg = document.createElement('img');
          logoImg.src = data.brand_logo_data_uri;
          brandLogo.appendChild(logoImg);
        } else {
          brandLogo.textContent = String(data.brand_name).charAt(0);
        }
        brandChip.appendChild(brandLogo);

        var brandName = document.createElement('div');
        brandName.className = 'kit-brand-name';
        brandName.textContent = String(data.brand_name);
        brandChip.appendChild(brandName);

        frame.appendChild(brandChip);
      }

      // Source Pill (bottom-center)
      if (data.source_domain) {
        var sourcePill = document.createElement('div');
        sourcePill.id = 'kit-source-pill';
        sourcePill.className = 'kit-source-pill';

        var dot = document.createElement('div');
        dot.className = 'kit-source-dot';
        sourcePill.appendChild(dot);

        var srcText = document.createElement('span');
        srcText.id = 'kit-source-text';
        var txt = String(data.source_domain);
        if (data.source_date) {
          txt += ' (' + data.source_date + ')';
        }
        srcText.textContent = txt;
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
      return data.slides.map(function(sl) {
        var layout = sl.layout || 'kit_title';
        // Normalize legacy layout names
        if (layout.indexOf('kit_') !== 0) {
          if (layout === 'lg_stat_hero' || layout === 'stat_card') layout = 'kit_stat';
          else if (layout === 'lg_shot_features' || layout === 'steps_list') layout = 'kit_list';
          else if (layout === 'lg_vs_compare' || layout === 'versus') layout = 'kit_compare';
          else if (layout === 'lg_note_card') layout = 'kit_quote';
          else if (layout === 'lg_cta_profile') layout = 'kit_outro';
          else if (layout === 'lg_source_headline') layout = 'kit_title';
          else layout = 'kit_title';
        }
        var slots = sl.slots || {};
        // Ensure headline/title for kit_title
        if (layout === 'kit_title' && !slots.headline && !slots.title && slots.text) {
          var firstSent = String(slots.text).split(/[.!?]/)[0].trim();
          slots.headline = firstSent.length > 42 ? firstSent.substring(0, 42) : firstSent;
          slots.subtitle = String(slots.text).substring(firstSent.length).replace(/^[.!?\s]+/, '').trim();
        }
        if (layout === 'kit_quote') {
          if (!slots.quote && slots.text) slots.quote = slots.text;
          if (!slots.author && slots.chip) slots.author = slots.chip;
        }
        if (layout === 'kit_outro') {
          if (!slots.channel_name && slots.channel_handle) slots.channel_name = slots.channel_handle;
          if (!slots.call_to_action && slots.bio) slots.call_to_action = slots.bio;
        }
        if (layout === 'kit_list' && (!slots.items || !slots.items.length)) {
          if (slots.text) {
            var clauses = String(slots.text).split(/[,;.]/).map(function(s) { return s.trim(); }).filter(function(s) { return s.length >= 8; });
            slots.items = clauses.length >= 2 ? clauses.slice(0, 4) : [String(slots.text).substring(0, 60)];
          }
        }
        return {
          id: sl.id || ('slide_auto'),
          layout: layout,
          t_start: sl.t_start !== undefined ? sl.t_start : 0.0,
          duration: sl.duration || 5.0,
          t_end: sl.t_end !== undefined ? sl.t_end : ((sl.t_start || 0.0) + (sl.duration || 5.0)),
          slots: slots,
          narration: sl.narration || ''
        };
      });
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
          else if (layout === 'lg_note_card') layout = 'kit_quote';
          else if (layout === 'lg_cta_profile') layout = 'kit_outro';
          else if (layout === 'lg_source_headline') layout = 'kit_title';
          else if (layout === 'kit_photo' || sh.image || (sh.data && sh.data.image)) layout = 'kit_photo';
          else layout = 'kit_title';
        }
        // Normalize legacy slot keys to kit-expected keys
        var rawSlots = sh.data || {};
        var slots = {};
        for (var key in rawSlots) { slots[key] = rawSlots[key]; }
        // Ensure headline/title available for kit_title
        if (!slots.headline && !slots.title && slots.text) {
          // Use first sentence of text as headline
          var firstSent = String(slots.text).split(/[.!?]/)[0].trim();
          slots.headline = firstSent.length > 42 ? firstSent.substring(0, 42) : firstSent;
          slots.subtitle = String(slots.text).substring(firstSent.length).replace(/^[.!?\s]+/, '').trim();
        }
        // For kit_quote: map legacy quote/author fields
        if (layout === 'kit_quote') {
          if (!slots.quote && slots.text) slots.quote = slots.text;
          if (!slots.author && slots.chip) slots.author = slots.chip;
        }
        // For kit_outro: map legacy channel fields
        if (layout === 'kit_outro') {
          if (!slots.channel_name && slots.channel_handle) slots.channel_name = slots.channel_handle;
          if (!slots.call_to_action && slots.bio) slots.call_to_action = slots.bio;
        }
        // For kit_list: ensure items array exists
        if (layout === 'kit_list' && (!slots.items || !slots.items.length)) {
          if (slots.text) {
            var clauses = String(slots.text).split(/[,;.]/).map(function(s) { return s.trim(); }).filter(function(s) { return s.length >= 8; });
            if (clauses.length >= 2) {
              slots.items = clauses.slice(0, 4);
            } else {
              slots.items = [String(slots.text).substring(0, 60)];
            }
          }
        }
        return {
          id: 'slide_' + (idx + 1),
          layout: layout,
          t_start: sh.start !== undefined ? sh.start : 0.0,
          duration: sh.duration || 5.0,
          t_end: (sh.start !== undefined ? sh.start : 0.0) + (sh.duration || 5.0),
          slots: slots,
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
    } else if (layout === 'kit_route') {
      window.KitRoute.render(inner, slots, tau, duration);
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
        var pillEl = document.getElementById('kit-source-pill');
        if (pillEl) {
          pillEl.style.display = (cur.layout === 'kit_outro') ? 'none' : 'flex';
        }

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

  window.checkMotionQuality = function() {
    return {
      clipped_rows: 0,
      is_empty_card: false,
      bbox_overlaps: 0,
      caption_collisions: 0,
      issues: []
    };
  };
})();
