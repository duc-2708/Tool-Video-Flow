/* Deterministic camera 3D depth, parallax, and gentle drift.
 * Pure mathematical functions of t and duration.
 */
(()=>{'use strict';

const { clamp, easeOutCubic } = window.MotionEasing;

function calculateCamera(t, duration, cameraSpec = {}) {
  const p = clamp(t / Math.max(0.1, duration));
  const kind = cameraSpec.move || cameraSpec.kind || 'push_in';
  const baseAmount = Math.min(0.08, Math.max(0.03, cameraSpec.amount || 0.05));

  // 1. Natural breathing drift (organic Lissajous curve)
  const driftX = Math.sin(t * 0.45) * 8 + Math.cos(t * 0.23) * 5;
  const driftY = Math.cos(t * 0.38) * 10 + Math.sin(t * 0.19) * 4;

  // 2. Gentle dynamic rotation (tilt +/- 1.2 degrees)
  const tilt = Math.sin(t * 0.5) * 0.8;

  // 3. Camera moves: push_in, pull_out, pan_left, pan_right
  let zoom = 1.0;
  let panX = 0;
  let panY = 0;

  if (kind === 'push_in') {
    zoom = 1.0 + baseAmount * easeOutCubic(p);
  } else if (kind === 'pull_out') {
    zoom = 1.0 + baseAmount * (1 - easeOutCubic(p));
  } else if (kind === 'pan_left') {
    panX = -baseAmount * 600 * p;
    zoom = 1.02;
  } else if (kind === 'pan_right') {
    panX = baseAmount * 600 * p;
    zoom = 1.02;
  }

  // 4. Parallax offsets per layer
  // Background moves least (0.3x), content at 1.0x, foreground/annotations move most (1.25x)
  return {
    t,
    p,
    zoom,
    tilt,
    layers: {
      background: {
        x: (panX + driftX) * 0.3,
        y: driftY * 0.3,
        scale: 1.02,
        rotate: tilt * 0.3
      },
      content: {
        x: panX + driftX,
        y: panY + driftY,
        scale: zoom,
        rotate: tilt
      },
      foreground: {
        x: (panX + driftX) * 1.25,
        y: (panY + driftY) * 1.2,
        scale: zoom * 1.01,
        rotate: tilt * 1.15
      }
    }
  };
}

window.MotionCamera = { calculateCamera };
})();
