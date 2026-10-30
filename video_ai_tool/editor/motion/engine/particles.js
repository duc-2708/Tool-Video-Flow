/* Deterministic particles and visual micro-effects based on absolute time t and seed.
 * No timers, no CSS transitions, zero Math.random().
 */
(()=>{'use strict';

const { seededRandom, hashSeed } = window.MotionPRNG;
const { clamp, easeOutCubic, overshoot } = window.MotionEasing;

// 1. Bokeh Background Particles
function renderBokeh(ctx, width, height, t, count = 18, seed = 'bokeh_bg') {
  const baseSeed = hashSeed(seed);
  for (let i = 0; i < count; i++) {
    const s1 = seededRandom(baseSeed, i * 4);
    const s2 = seededRandom(baseSeed, i * 4 + 1);
    const s3 = seededRandom(baseSeed, i * 4 + 2);
    const s4 = seededRandom(baseSeed, i * 4 + 3);

    const radius = 35 + s1 * 75;
    // Slow organic drift using sine/cosine harmonics
    const speedX = 0.15 + s2 * 0.25;
    const speedY = 0.12 + s3 * 0.2;
    const x = (s1 * width + Math.sin(t * speedX + i * 1.5) * 60 + width) % width;
    const y = (s2 * height + Math.cos(t * speedY + i * 1.2) * 80 + height) % height;

    const pulse = 0.35 + 0.25 * Math.sin(t * 1.5 + i);
    const alpha = (0.04 + s4 * 0.08) * pulse;

    const grad = ctx.createRadialGradient(x, y, 0, x, y, radius);
    grad.addColorStop(0, `rgba(130, 210, 255, ${alpha})`);
    grad.addColorStop(0.6, `rgba(180, 140, 255, ${alpha * 0.5})`);
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
  }
}

// 2. Liquid Bubbles for container_fill
function renderLiquidBubbles(ctx, bounds, t, fillPercent, count = 14, seed = 'liquid_bubbles') {
  if (fillPercent <= 0.05) return;
  const baseSeed = hashSeed(seed);
  const liquidHeight = bounds.height * fillPercent;
  const liquidTop = bounds.y + bounds.height - liquidHeight;

  ctx.save();
  // Clip to container bounds
  ctx.beginPath();
  ctx.rect(bounds.x, liquidTop, bounds.width, liquidHeight);
  ctx.clip();

  for (let i = 0; i < count; i++) {
    const s1 = seededRandom(baseSeed, i * 3);
    const s2 = seededRandom(baseSeed, i * 3 + 1);
    const s3 = seededRandom(baseSeed, i * 3 + 2);

    const speed = 0.3 + s1 * 0.5;
    const lifetime = 2.5 / speed;
    const cycle = (t * speed + s2 * lifetime) % lifetime;
    const progress = cycle / lifetime; // 0 (bottom) -> 1 (surface)

    const r = 4 + s3 * 8;
    const x = bounds.x + bounds.width * (0.15 + 0.7 * s1) + Math.sin(t * 3 + i) * 12;
    const y = bounds.y + bounds.height - progress * liquidHeight;

    const alpha = progress < 0.85 ? 0.6 : (1 - progress) * 4; // fade at surface

    ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.65})`;
    ctx.strokeStyle = `rgba(255, 255, 255, ${alpha * 0.9})`;
    ctx.lineWidth = 1.5;

    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Bubble highlight reflection dot
    ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.95})`;
    ctx.beginPath();
    ctx.arc(x - r * 0.35, y - r * 0.35, r * 0.25, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

// 3. Sparks & Confetti burst
function renderSparks(ctx, originX, originY, t, burstTime, count = 20, seed = 'sparks') {
  const dt = t - burstTime;
  if (dt < 0 || dt > 1.2) return;
  const p = dt / 1.2;
  const baseSeed = hashSeed(seed);
  const colors = ['#00e5ff', '#ff007f', '#ffc83b', '#00ff88', '#ffffff'];

  ctx.save();
  for (let i = 0; i < count; i++) {
    const s1 = seededRandom(baseSeed, i * 4);
    const s2 = seededRandom(baseSeed, i * 4 + 1);
    const s3 = seededRandom(baseSeed, i * 4 + 2);

    const angle = s1 * Math.PI * 2;
    const distance = (40 + s2 * 180) * easeOutCubic(p);
    const gravity = p * p * 90;

    const x = originX + Math.cos(angle) * distance;
    const y = originY + Math.sin(angle) * distance + gravity;
    const alpha = (1 - p) * 0.95;
    const size = (3 + s3 * 6) * (1 - p * 0.6);

    ctx.fillStyle = colors[i % colors.length];
    ctx.globalAlpha = alpha;
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

// 4. Screen Shake / Impact
function calculateScreenShake(t, hitTimes = [], maxIntensity = 10) {
  let dx = 0, dy = 0;
  for (const hit of hitTimes) {
    const dt = t - hit;
    if (dt >= 0 && dt < 0.45) {
      const decay = 1 - dt / 0.45;
      const freq = 28;
      dx += Math.sin(dt * freq * Math.PI) * maxIntensity * decay;
      dy += Math.cos(dt * freq * Math.PI * 1.3) * maxIntensity * 0.7 * decay;
    }
  }
  return { dx, dy };
}

// 5. Odometer Number Calculation
function calculateOdometer(currentValue, targetValue, progress) {
  const p = clamp(progress);
  if (p >= 1) return { value: targetValue, display: targetValue, bounceY: 0 };
  const smoothP = easeOutCubic(p);
  const val = currentValue + (targetValue - currentValue) * smoothP;
  // Subtle vertical bounce settling at end
  let bounceY = 0;
  if (p > 0.8) {
    const bp = (p - 0.8) / 0.2;
    bounceY = Math.sin(bp * Math.PI) * -8;
  }
  return {
    value: val,
    bounceY
  };
}

// 6. Light Sweep / Sheen across glass cards
function renderLightSweep(ctx, width, height, t, sweepTimes = [0.8, 2.5], widthPx = 180) {
  for (const sweepTime of sweepTimes) {
    const dt = t - sweepTime;
    if (dt >= 0 && dt < 0.6) {
      const p = dt / 0.6;
      const x = -widthPx + (width + widthPx * 2) * easeOutCubic(p);
      ctx.save();
      const grad = ctx.createLinearGradient(x, 0, x + widthPx, height);
      grad.addColorStop(0, 'rgba(255, 255, 255, 0)');
      grad.addColorStop(0.5, 'rgba(255, 255, 255, 0.22)');
      grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, width, height);
      ctx.restore();
    }
  }
}

// 7. Breathing Pulse Glow around main bounds
function renderPulseGlow(ctx, bounds, t, color = 'var(--accent)') {
  const pulse = 0.5 + 0.5 * Math.sin(t * 3.5);
  const glowRadius = 25 + pulse * 20;
  ctx.save();
  ctx.shadowColor = color === 'var(--accent)' ? 'rgba(0, 229, 255, 0.6)' : color;
  ctx.shadowBlur = glowRadius;
  ctx.strokeStyle = 'rgba(255, 255, 255, ' + (0.1 + pulse * 0.15) + ')';
  ctx.lineWidth = 2;
  ctx.strokeRect(bounds.x, bounds.y, bounds.width, bounds.height);
  ctx.restore();
}

// 8. Glitch Cut (chromatic horizontal lines)
function renderGlitchCut(ctx, width, height, t, glitchTime = 0, duration = 0.18) {
  const dt = t - glitchTime;
  if (dt < 0 || dt > duration) return;
  const p = dt / duration;
  const baseSeed = hashSeed('glitch_' + Math.floor(t * 30));
  const sliceCount = 8;
  ctx.save();
  for (let i = 0; i < sliceCount; i++) {
    const sy = seededRandom(baseSeed, i * 3) * height;
    const sh = 10 + seededRandom(baseSeed, i * 3 + 1) * 35;
    const offset = (seededRandom(baseSeed, i * 3 + 2) - 0.5) * 45 * (1 - p);
    ctx.fillStyle = i % 2 === 0 ? 'rgba(0, 229, 255, 0.25)' : 'rgba(255, 0, 127, 0.25)';
    ctx.fillRect(offset, sy, width, sh);
  }
  ctx.restore();
}

window.MotionParticles = {
  renderBokeh,
  renderLiquidBubbles,
  renderSparks,
  calculateScreenShake,
  calculateOdometer,
  renderLightSweep,
  renderPulseGlow,
  renderGlitchCut
};
})();
