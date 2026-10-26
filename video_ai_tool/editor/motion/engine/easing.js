/* Deterministic animation principles & easing functions.
 * All functions are pure mathematical mappings from progress p in [0, 1] to values.
 */
(()=>{'use strict';

const clamp = (x, min = 0, max = 1) => Math.max(min, Math.min(max, x));

// Standard easings
const linear = p => clamp(p);
const easeInQuad = p => { p = clamp(p); return p * p; };
const easeOutQuad = p => { p = clamp(p); return p * (2 - p); };
const easeInOutQuad = p => { p = clamp(p); return p < 0.5 ? 2 * p * p : -1 + (4 - 2 * p) * p; };

const easeInCubic = p => { p = clamp(p); return p * p * p; };
const easeOutCubic = p => { p = clamp(p) - 1; return p * p * p + 1; };
const easeInOutCubic = p => { p = clamp(p); return p < 0.5 ? 4 * p * p * p : (p - 1) * (2 * p - 2) * (2 * p - 2) + 1; };

// Animation Principles
// 1. Anticipation: slight pull back before leaping forward
const anticipation = (p, s = 1.70158) => {
  p = clamp(p);
  return p * p * ((s + 1) * p - s);
};

// 2. Overshoot / Elastic spring: overshoot target and snap back
const overshoot = (p, s = 1.70158) => {
  p = clamp(p) - 1;
  return p * p * ((s + 1) * p + s) + 1;
};

// 3. Squash and Stretch: maintains area (sx * sy ~= 1) during motion impact
const squashAndStretch = (p, intensity = 0.22) => {
  p = clamp(p);
  // Peaks at p = 0.5 with maximum compression along velocity axis
  const delta = Math.sin(p * Math.PI) * intensity;
  return {
    scaleX: 1 + delta,
    scaleY: 1 - delta
  };
};

// 4. Spring: damped harmonic oscillation
const spring = (p, tension = 16, friction = 4) => {
  p = clamp(p);
  if (p >= 1) return 1;
  return 1 - Math.exp(-friction * p * 6) * Math.cos(tension * p * Math.PI);
};

// 5. Slow In / Out
const slowInOut = p => easeInOutCubic(p);

// 6. Follow-through: secondary action with lag
const followThrough = (p, lag = 0.15) => {
  const pLagged = clamp((p - lag) / (1 - lag));
  return overshoot(pLagged, 1.4);
};

// 7. Arc: curved trajectory between points (x0, y0) and (x1, y1)
const arcPoint = (p, x0, y0, x1, y1, curvature = 0.25) => {
  p = clamp(p);
  const mx = (x0 + x1) / 2;
  const my = (y0 + y1) / 2;
  const dx = x1 - x0;
  const dy = y1 - y0;
  // Perpendicular offset for arc
  const cx = mx - dy * curvature;
  const cy = my + dx * curvature;
  // Quadratic bezier
  const inv = 1 - p;
  const x = inv * inv * x0 + 2 * inv * p * cx + p * p * x1;
  const y = inv * inv * y0 + 2 * inv * p * cy + p * p * y1;
  return { x, y };
};

// 8. Stagger: computes local progress for item i out of count items
const staggerProgress = (t, startSec, i, count, itemDuration = 0.45, interval = 0.15) => {
  const itemStart = startSec + i * interval;
  return clamp((t - itemStart) / Math.max(0.05, itemDuration));
};

// Animation Presets
const presets = {
  // ENTRANCE PRESETS
  pop_spring: p => ({
    opacity: clamp(p * 2),
    scale: p <= 0 ? 0 : spring(p, 14, 3.5),
    translateY: 0
  }),
  slide_overshoot: (p, distance = 60, dir = 'up') => {
    const s = overshoot(p, 1.8);
    const offset = (1 - s) * distance;
    return {
      opacity: clamp(p * 2.5),
      translateX: dir === 'left' ? -offset : dir === 'right' ? offset : 0,
      translateY: dir === 'up' ? offset : dir === 'down' ? -offset : 0,
      scale: 0.95 + 0.05 * clamp(s)
    };
  },
  draw_stroke: p => ({
    dashOffset: 1 - easeOutCubic(p),
    opacity: clamp(p * 3)
  }),
  unfold: p => ({
    scaleY: easeOutCubic(p),
    scaleX: 0.8 + 0.2 * easeOutCubic(p),
    opacity: clamp(p * 2)
  }),
  drop_bounce: p => {
    p = clamp(p);
    let y = 0;
    if (p < 0.6) {
      y = (1 - easeInQuad(p / 0.6)) * -120;
    } else if (p < 0.8) {
      const b1 = (p - 0.6) / 0.2;
      y = -Math.sin(b1 * Math.PI) * 25;
    } else {
      const b2 = (p - 0.8) / 0.2;
      y = -Math.sin(b2 * Math.PI) * 8;
    }
    return {
      translateY: y,
      opacity: clamp(p * 3),
      scale: 1 + Math.sin(p * Math.PI * 2) * 0.04
    };
  },
  zoom_blur_in: p => ({
    opacity: easeOutQuad(p),
    scale: 0.7 + 0.3 * overshoot(p, 1.5)
  }),

  // EMPHASIS PRESETS
  punch_scale: p => {
    p = clamp(p);
    // quick pop to 1.15x then settle back to 1.0x
    const s = 1 + Math.sin(p * Math.PI) * 0.16;
    return { scale: s };
  },
  wobble: p => {
    p = clamp(p);
    const angle = Math.sin(p * Math.PI * 4) * (1 - p) * 6; // decaying angle
    return { rotate: angle };
  },
  glow_flash: p => {
    p = clamp(p);
    const intensity = Math.sin(p * Math.PI);
    return {
      filter: `drop-shadow(0 0 ${intensity * 25}px var(--accent))`
    };
  },
  pulse_ring: p => {
    p = clamp(p);
    return {
      ringScale: 1 + p * 0.8,
      ringOpacity: (1 - p) * 0.8
    };
  },
  shake: p => {
    p = clamp(p);
    const decay = 1 - p;
    const dx = Math.sin(p * Math.PI * 8) * 12 * decay;
    const dy = Math.cos(p * Math.PI * 6) * 8 * decay;
    return { translateX: dx, translateY: dy };
  },
  shine_sweep: p => ({
    sweepX: -100 + clamp(p) * 300 // percentage across container
  }),

  // EXIT PRESETS
  fade_slide: p => {
    p = clamp(p);
    return {
      opacity: 1 - p,
      translateY: -p * 45
    };
  },
  shrink_pop: p => {
    p = clamp(p);
    return {
      opacity: 1 - easeInCubic(p),
      scale: 1 - 0.4 * easeInCubic(p)
    };
  },
  wipe_out: p => ({
    clipPath: `inset(0 0 0 ${clamp(p) * 100}%)`,
    opacity: 1 - p * 0.5
  })
};

window.MotionEasing = {
  clamp,
  linear,
  easeInQuad,
  easeOutQuad,
  easeInOutQuad,
  easeInCubic,
  easeOutCubic,
  easeInOutCubic,
  anticipation,
  overshoot,
  squashAndStretch,
  spring,
  slowInOut,
  followThrough,
  arcPoint,
  staggerProgress,
  presets
};
})();
