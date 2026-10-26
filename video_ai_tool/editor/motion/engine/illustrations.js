/* Dynamic Vector Illustrations Engine:
 * Animates the 15 original vector illustrations deterministically using absolute time t.
 */
(()=>{'use strict';

const { clamp } = window.MotionEasing;

function animateIllustration(svgEl, name = 'drone', t = 0, state = '') {
  if (!svgEl) return;

  if (name === 'drone') {
    // 1. Drone: spinning rotor blades and gentle floating hover
    const hoverY = Math.sin(t * 3.2) * 12;
    const hoverTilt = Math.sin(t * 1.6) * 3;
    svgEl.style.transform = `translateY(${hoverY}px) rotate(${hoverTilt}deg)`;

    const rotAngle = (t * 1440) % 360; // fast 4 rev/s
    ['prop-1', 'prop-2', 'prop-3', 'prop-4'].forEach(id => {
      const prop = svgEl.querySelector('#' + id);
      if (prop) prop.setAttribute('transform', `rotate(${rotAngle} ${prop.firstElementChild?.getAttribute('cx') || 0} ${prop.firstElementChild?.getAttribute('cy') || 0})`);
    });

    // Strobe lights
    const ledFront = svgEl.querySelector('#led-front');
    if (ledFront) ledFront.setAttribute('fill-opacity', (Math.sin(t * 8) > 0) ? '1' : '0.2');

  } else if (name === 'radar_scan') {
    // 2. Radar: rotating 360 sweep beam
    const beam = svgEl.querySelector('#radar-beam');
    if (beam) {
      const beamAngle = (t * 180) % 360;
      beam.setAttribute('transform', `rotate(${beamAngle} 200 200)`);
    }

  } else if (name === 'gears_rotating') {
    // 3. Gears: interlocking continuous rotation
    const g1 = svgEl.querySelector('#gear-1');
    const g2 = svgEl.querySelector('#gear-2');
    if (g1) g1.setAttribute('transform', `translate(150, 160) rotate(${(t * 90) % 360})`);
    if (g2) g2.setAttribute('transform', `translate(265, 255) rotate(${(-t * 120) % 360})`);

  } else if (name === 'map_pin') {
    // 4. Map Pin: beacon rings expanding
    const b1 = svgEl.querySelector('#beacon-1');
    const b2 = svgEl.querySelector('#beacon-2');
    const r1 = 20 + (t * 40) % 60;
    const r2 = 20 + ((t + 0.4) * 40) % 60;
    if (b1) {
      b1.setAttribute('r', String(r1));
      b1.setAttribute('opacity', String(1 - r1 / 80));
    }
    if (b2) {
      b2.setAttribute('r', String(r2));
      b2.setAttribute('opacity', String(1 - r2 / 80));
    }

  } else if (name === 'battery_charging') {
    // 5. Battery: energy fill rising and pulsing
    const fill = svgEl.querySelector('#battery-fill');
    if (fill) {
      const fillCycle = clamp((t * 0.4) % 1.2);
      const h = 165 * fillCycle;
      fill.setAttribute('height', String(h));
      fill.setAttribute('y', String(325 - h));
    }

  } else if (name === 'shield_protect') {
    // 6. Shield: breathing pulse barrier
    const scale = 1 + 0.03 * Math.sin(t * 4);
    svgEl.style.transform = `scale(${scale})`;

  } else if (name === 'server_rack') {
    // 7. Server Rack: running status lights
    const leds = svgEl.querySelectorAll('circle');
    leds.forEach((led, i) => {
      const on = Math.sin(t * 6 + i * 1.5) > 0;
      led.setAttribute('fill-opacity', on ? '1' : '0.25');
    });

  } else if (name === 'signal_waves') {
    // 8. Signal Waves: radiating broadcast waves
    const waves = svgEl.querySelectorAll('path[stroke-linecap="round"]');
    waves.forEach((w, i) => {
      const p = (t * 2 - i * 0.3) % 1;
      w.setAttribute('stroke-opacity', String(Math.max(0.1, 1 - Math.abs(p))));
    });
  }
}

window.MotionIllustrations = {
  animateIllustration
};
})();
