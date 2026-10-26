/* Articulated Mascot Engine: Breathing, blinking, head tilt, pointing, lip-sync.
 * Driven deterministically by absolute time t and audio amplitude.
 */
(()=>{'use strict';

const { clamp, easeOutCubic, overshoot } = window.MotionEasing;

function calculateMascotPlacement(specZone = 'center', width = 1080, height = 1920) {
  // Mascot size: 240x288 px (22.2% of width >= 18%)
  const mascotW = 240;
  const mascotH = 288;

  // Safe area: content is in [154, 1498], captions start at 1498.
  // We place mascot near bottom of content zone, safely away from captions.
  let x = width - mascotW - 40; // Default bottom-right
  let y = 1200;

  if (specZone === 'left') {
    // Primary content is on left -> Mascot goes to right
    x = width - mascotW - 50;
    y = 1220;
  } else if (specZone === 'right') {
    // Primary content is on right -> Mascot goes to left
    x = 50;
    y = 1220;
  } else if (specZone === 'top') {
    // Content is at top -> Mascot goes to bottom-right
    x = width - mascotW - 50;
    y = 1220;
  } else if (specZone === 'bottom') {
    // Content is at bottom -> Mascot hovers mid-right
    x = width - mascotW - 40;
    y = 680;
  }

  return { x, y, width: mascotW, height: mascotH };
}

function animateMascot(svgElement, state = 'idle', t = 0, amplitudeLevel = 0, targetCoords = null) {
  if (!svgElement) return;

  // 1. Organic Breathing (sinusoidal scale on body and head)
  const breath = Math.sin(t * 2.8) * 0.025;
  const bodyEl = svgElement.querySelector('#body') || svgElement.querySelector('rect[fill="#315879"]');
  if (bodyEl) {
    bodyEl.setAttribute('transform', `scale(1, ${1 + breath})`);
  }

  // 2. Head Tilt & Bobbing
  const headEl = svgElement.querySelector('#head') || svgElement.querySelector('rect[fill="#8be4ee"]');
  const headTilt = (state === 'think') ? -7 : Math.sin(t * 1.4) * 4.5;
  const headBob = Math.cos(t * 2.8) * 3;
  if (headEl) {
    headEl.setAttribute('transform', `translate(0, ${headBob}) rotate(${headTilt} 100 70)`);
  }

  // 3. Periodic Natural Blinking (every ~3.2 seconds for 0.14s)
  const blinkCycle = t % 3.2;
  const isBlinking = blinkCycle < 0.14;
  const eyeL = svgElement.querySelector('#eye-l') || svgElement.querySelector('circle[cx="73"]');
  const eyeR = svgElement.querySelector('#eye-r') || svgElement.querySelector('circle[cx="129"]');

  if (eyeL && eyeR) {
    if (state === 'surprised') {
      eyeL.setAttribute('r', '11');
      eyeR.setAttribute('r', '11');
      eyeL.setAttribute('transform', 'none');
      eyeR.setAttribute('transform', 'none');
    } else if (isBlinking) {
      eyeL.setAttribute('transform', 'scale(1, 0.1) translate(0, 560)');
      eyeR.setAttribute('transform', 'scale(1, 0.1) translate(0, 560)');
    } else {
      eyeL.setAttribute('r', '7');
      eyeR.setAttribute('r', '7');
      eyeL.setAttribute('transform', 'none');
      eyeR.setAttribute('transform', 'none');
    }
  }

  // 4. Lip-sync Mouth with Audio Amplitude Level (0 to 1)
  const mouth = svgElement.querySelector('#mouth');
  if (mouth) {
    if (state === 'surprised') {
      mouth.setAttribute('rx', '9');
      mouth.setAttribute('ry', '14');
    } else {
      const openY = 2 + 16 * clamp(amplitudeLevel);
      const openX = 10 + 4 * clamp(amplitudeLevel);
      mouth.setAttribute('ry', String(openY));
      mouth.setAttribute('rx', String(openX));
    }
  }

  // 5. Articulated Arm Movements
  const armL = svgElement.querySelector('#arm-l') || svgElement.querySelectorAll('path[stroke-linecap="round"]')[0];
  const armR = svgElement.querySelector('#arm-r') || svgElement.querySelectorAll('path[stroke-linecap="round"]')[1];

  if (armR) {
    if (state === 'point') {
      // Arm points up-left towards primary content
      const pointP = clamp(t / 0.5);
      const angle = -35 * easeOutCubic(pointP);
      armR.setAttribute('transform', `rotate(${angle} 145 145)`);
    } else if (state === 'shrug') {
      const shrugH = Math.sin(t * 3.5) * 8;
      armR.setAttribute('transform', `translate(0, ${-shrugH})`);
      if (armL) armL.setAttribute('transform', `translate(0, ${-shrugH})`);
    } else if (state === 'think') {
      // Right hand touches chin
      armR.setAttribute('transform', 'translate(-25, -45) rotate(-35 145 145)');
    } else {
      // Idle natural arm sway
      const armSway = Math.sin(t * 1.5) * 5;
      armR.setAttribute('transform', `rotate(${armSway} 145 145)`);
      if (armL) armL.setAttribute('transform', `rotate(${-armSway} 55 145)`);
    }
  }
}

window.MotionMascot = {
  calculateMascotPlacement,
  animateMascot
};
})();
