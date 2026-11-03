// Motion Kit v2 - kit_stat.js
(function() {
  function formatMonotonicValue(rawTarget, p) {
    if (rawTarget === null || rawTarget === undefined) return "";
    var targetStr = String(rawTarget).trim().replace(/,/g, '');
    var num = parseFloat(targetStr);
    if (isNaN(num)) {
      return String(rawTarget);
    }
    // Check if integer or has decimal
    var hasDecimal = targetStr.indexOf('.') !== -1;
    var decimals = hasDecimal ? (targetStr.split('.')[1] || '').length : 0;
    
    // EaseOutCubic: strictly monotonic non-decreasing in [0, 1]
    var clampedP = Math.min(1.0, Math.max(0.0, p));
    var easeVal = 1.0 - Math.pow(1.0 - clampedP, 3);
    var currentVal = num * easeVal;
    
    if (hasDecimal && decimals > 0) {
      return currentVal.toFixed(decimals);
    } else {
      return Math.round(currentVal).toLocaleString('vi-VN');
    }
  }

  window.KitStat = {
    render: function(container, slots, tau, duration) {
      if (!slots) return;
      var card = document.createElement('div');
      card.className = 'kit-card';

      // 1. Optional Pill
      if (slots.pill) {
        var pill = document.createElement('div');
        pill.className = 'kit-pill';
        pill.textContent = String(slots.pill);
        card.appendChild(pill);
      }

      var statContainer = document.createElement('div');
      statContainer.className = 'kit-stat-container';

      // 2. Stat Row: Number + Unit + Optional Delta
      var row = document.createElement('div');
      row.className = 'kit-stat-row';

      // Monotonic count up in <= 1.2s
      var pCount = Math.min(1.0, Math.max(0.0, tau / 1.2));
      var targetVal = slots.value !== undefined ? slots.value : (slots.number !== undefined ? slots.number : null);

      if (targetVal !== null) {
        var numEl = document.createElement('span');
        numEl.className = 'kit-stat-number';
        numEl.textContent = formatMonotonicValue(targetVal, pCount);
        row.appendChild(numEl);
      }

      if (slots.unit) {
        var unitEl = document.createElement('span');
        unitEl.className = 'kit-stat-unit';
        unitEl.textContent = String(slots.unit);
        row.appendChild(unitEl);
      }

      if (slots.delta) {
        var deltaEl = document.createElement('span');
        var deltaObj = typeof slots.delta === 'object' ? slots.delta : { text: String(slots.delta) };
        var isDown = deltaObj.direction === 'down' || String(deltaObj.text).indexOf('-') !== -1;
        deltaEl.className = 'kit-stat-delta ' + (isDown ? 'down' : 'up');
        deltaEl.textContent = String(deltaObj.text || '');
        row.appendChild(deltaEl);
      }

      statContainer.appendChild(row);

      // 3. Caption / Label
      var labelText = slots.label || slots.title || slots.note || slots.text;
      if (labelText) {
        var labelEl = document.createElement('div');
        labelEl.className = 'kit-body';
        labelEl.style.fontSize = '52px';
        labelEl.style.fontWeight = '600';
        labelEl.textContent = String(labelText);
        statContainer.appendChild(labelEl);
      }

      // 4. Secondary note if distinct
      if (slots.subnote && slots.subnote !== labelText) {
        var subEl = document.createElement('div');
        subEl.className = 'kit-caption';
        subEl.style.marginTop = '16px';
        subEl.textContent = String(slots.subnote);
        statContainer.appendChild(subEl);
      }

      card.appendChild(statContainer);

      // Entrance motion in first 0.7s, hold, subtle one-way drift
      var pEnter = Math.min(1.0, Math.max(0.0, tau / 0.7));
      var easeOut = 1.0 - Math.pow(1.0 - pEnter, 3);
      var translateY = (1.0 - easeOut) * 24.0;
      var opacity = easeOut;

      var pDrift = Math.min(1.0, Math.max(0.0, tau / Math.max(0.1, duration)));
      var currentScale = 1.0 + 0.02 * pDrift;

      card.style.transform = 'translateY(' + translateY.toFixed(2) + 'px) scale(' + currentScale.toFixed(4) + ')';
      card.style.opacity = opacity.toFixed(3);

      container.appendChild(card);
    }
  };
})();
