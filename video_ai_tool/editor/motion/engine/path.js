/* Deterministic path calculation: Bezier curves and motion-along-path with banking.
 * Pure mathematical functions of progress p in [0, 1].
 */
(()=>{'use strict';

const clamp = (x, min = 0, max = 1) => Math.max(min, Math.min(max, x));

// Quadratic Bezier: P(p) = (1-p)^2 P0 + 2(1-p)p P1 + p^2 P2
function bezier2(p, p0, p1, p2) {
  p = clamp(p);
  const inv = 1 - p;
  const x = inv * inv * p0.x + 2 * inv * p * p1.x + p * p * p2.x;
  const y = inv * inv * p0.y + 2 * inv * p * p1.y + p * p * p2.y;
  // Derivative for tangent vector
  const dx = 2 * inv * (p1.x - p0.x) + 2 * p * (p2.x - p1.x);
  const dy = 2 * inv * (p1.y - p0.y) + 2 * p * (p2.y - p1.y);
  const angle = Math.atan2(dy, dx) * (180 / Math.PI);
  return { x, y, dx, dy, angle };
}

// Cubic Bezier: P(p) = (1-p)^3 P0 + 3(1-p)^2 p P1 + 3(1-p)p^2 P2 + p^3 P3
function bezier3(p, p0, p1, p2, p3) {
  p = clamp(p);
  const inv = 1 - p;
  const inv2 = inv * inv;
  const inv3 = inv2 * inv;
  const p2_ = p * p;
  const p3_ = p2_ * p;

  const x = inv3 * p0.x + 3 * inv2 * p * p1.x + 3 * inv * p2_ * p2.x + p3_ * p3.x;
  const y = inv3 * p0.y + 3 * inv2 * p * p1.y + 3 * inv * p2_ * p2.y + p3_ * p3.y;

  const dx = 3 * inv2 * (p1.x - p0.x) + 6 * inv * p * (p2.x - p1.x) + 3 * p2_ * (p3.x - p2.x);
  const dy = 3 * inv2 * (p1.y - p0.y) + 6 * inv * p * (p2.y - p1.y) + 3 * p2_ * (p3.y - p2.y);
  const angle = Math.atan2(dy, dx) * (180 / Math.PI);

  return { x, y, dx, dy, angle };
}

// Motion-along-path helper with banking (tilt factor)
function motionAlongPath(p, points, bankingFactor = 12) {
  if (!points || points.length < 2) return { x: 0, y: 0, angle: 0, tilt: 0 };
  p = clamp(p);

  // If 3 points: use quadratic bezier
  let pos;
  if (points.length === 3) {
    pos = bezier2(p, points[0], points[1], points[2]);
  } else if (points.length >= 4) {
    pos = bezier3(p, points[0], points[1], points[2], points[3]);
  } else {
    // Linear
    const x = points[0].x + (points[1].x - points[0].x) * p;
    const y = points[0].y + (points[1].y - points[0].y) * p;
    const dx = points[1].x - points[0].x;
    const dy = points[1].y - points[0].y;
    pos = { x, y, dx, dy, angle: Math.atan2(dy, dx) * (180 / Math.PI) };
  }

  // Banking: derivative of curvature (rate of turn)
  const curvature = Math.sin(p * Math.PI) * bankingFactor;
  return {
    ...pos,
    tilt: curvature
  };
}

// Generates SVG path string for connection lines with smooth curves
function createCurvedConnectionPath(start, end, curvature = 0.2) {
  const mx = (start.x + end.x) / 2;
  const my = (start.y + end.y) / 2;
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const cx = mx - dy * curvature;
  const cy = my + dx * curvature;
  return `M ${start.x} ${start.y} Q ${cx} ${cy} ${end.x} ${end.y}`;
}

window.MotionPath = {
  bezier2,
  bezier3,
  motionAlongPath,
  createCurvedConnectionPath
};
})();
