/* Articulated Mascot Engine: Breathing, blinking, head tilt, pointing, lip-sync.
 * Driven deterministically by absolute time t and audio amplitude.
 */
(()=>{'use strict';

const { clamp, easeOutCubic, overshoot } = window.MotionEasing;

function calculateMascotPlacement(specZone = 'center', width = 1080, height = 1920, contentBounds = null) {
  const mascotW = 160;
  const mascotH = 190;
  
  // Safe zone for mascot: strictly y <= 1330, and y >= 240
  // Default placement in top safe corner y in [240, 500]
  let x = 75;
  let y = 250;
  let hidden = false;

  if (contentBounds) {
    // If content fills both horizontally (width >= 720) and vertically (y <= 450 and y + h >= 1150)
    // Then no safe corner exists without overlapping -> hide mascot
    if (contentBounds.width >= 720 && contentBounds.y <= 450 && (contentBounds.y + contentBounds.height) >= 1150) {
      hidden = true;
    } else if (contentBounds.y > 480) {
      // Content starts low -> top corner is completely free!
      x = 80;
      y = 250;
    } else if (contentBounds.x > 320) {
      // Left side is free
      x = 75;
      y = 550;
    } else if (contentBounds.x + contentBounds.width < 760) {
      // Right side is free
      x = width - mascotW - 75;
      y = 550;
    } else {
      // Try top right corner if top left is occupied
      x = width - mascotW - 75;
      y = 250;
      if (contentBounds.x + contentBounds.width > x && contentBounds.y < y + mascotH) {
        hidden = true; // Still overlapping
      }
    }
  } else {
    // Default top-left corner
    x = 75;
    y = 250;
  }

  // Double check bounds: never exceed y + mascotH > 1330 or y < 240
  if (y + mascotH > 1330) {
    y = 1330 - mascotH;
  }
  if (y < 240) {
    y = 240;
  }

  return { x, y, width: mascotW, height: mascotH, hidden };
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
