/* Deterministic PRNG using Mulberry32 algorithm.
 * Pure mathematical functions of seed and index. No Math.random().
 */
(()=>{'use strict';

function mulberry32(a) {
  return function() {
    let t = a += 0x6D2B79F5;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashSeed(str) {
  let hash = 0;
  if (!str) return 1337;
  const s = String(str);
  for (let i = 0; i < s.length; i++) {
    const char = s.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0;
  }
  return Math.abs(hash) || 1337;
}

function seededRandom(seed, index = 0) {
  const rng = mulberry32(hashSeed(seed) + index * 997);
  return rng();
}

window.MotionPRNG = { mulberry32, hashSeed, seededRandom };
})();
