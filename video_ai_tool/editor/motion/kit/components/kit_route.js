// Motion Kit v2 - kit_route.js
// Horizontal route diagram component for sequential stations/stops
(function() {
  'use strict';

  function easeOutCubic(p) {
    var c = Math.min(1.0, Math.max(0.0, p));
    return 1.0 - Math.pow(1.0 - c, 3);
  }

  window.KitRoute = {
    render: function(container, slots, tau, duration) {
      if (!slots) return;
      var card = document.createElement('div');
      card.className = 'kit-card kit-route-card';

      // 1. Pill
      var pillText = slots.pill || "SƠ ĐỒ TUYẾN";
      var pill = document.createElement('div');
      pill.className = 'kit-pill';
      pill.textContent = String(pillText);
      card.appendChild(pill);

      // 2. Title
      var titleText = slots.title || slots.headline || "Hành trình tuyến metro ngầm";
      var title = document.createElement('div');
      title.className = 'kit-title';
      title.style.fontSize = '68px';
      title.style.fontWeight = '800';
      title.style.lineHeight = '1.2';
      title.style.marginBottom = '24px';
      title.textContent = String(titleText);
      card.appendChild(title);

      // 3. Distance / Summary badge if present
      var distanceText = slots.distance || slots.length || "";
      if (distanceText) {
        var distBadge = document.createElement('div');
        distBadge.className = 'kit-route-distance-badge';
        distBadge.textContent = "Chiều dài: " + String(distanceText);
        card.appendChild(distBadge);
      }

      // 4. Stations Route Canvas / Track
      var rawStations = slots.stations || slots.stops || slots.items || [];
      var stations = Array.isArray(rawStations) ? rawStations.slice(0, 5) : [];
      var numStations = stations.length;

      var routeContainer = document.createElement('div');
      routeContainer.className = 'kit-route-container';

      // Track line (horizontal)
      var trackBg = document.createElement('div');
      trackBg.className = 'kit-route-track-bg';
      routeContainer.appendChild(trackBg);

      // Total track animation progress
      var maxAnimTime = Math.max(0.5, (numStations - 1) * 0.5);
      var pTotalLine = Math.min(1.0, Math.max(0.0, tau / maxAnimTime));
      var pTotalLineEase = easeOutCubic(pTotalLine);

      var trackActive = document.createElement('div');
      trackActive.className = 'kit-route-track-active';
      trackActive.style.width = (pTotalLineEase * 100.0).toFixed(2) + '%';
      routeContainer.appendChild(trackActive);

      // Station Nodes Container
      var nodesRow = document.createElement('div');
      nodesRow.className = 'kit-route-nodes-row';

      for (var i = 0; i < numStations; i++) {
        var nodeWrapper = document.createElement('div');
        nodeWrapper.className = 'kit-route-node-wrapper';

        // Staggered timing: node i activates at i * 0.5s
        var nodeT = tau - (i * 0.5);
        var pNode = Math.min(1.0, Math.max(0.0, nodeT / 0.35));
        var nodeEase = easeOutCubic(pNode);

        // Circular Station Pin
        var pin = document.createElement('div');
        pin.className = 'kit-route-pin';
        pin.style.transform = 'scale(' + nodeEase.toFixed(3) + ')';
        pin.style.opacity = nodeEase.toFixed(2);

        var pinDot = document.createElement('div');
        pinDot.className = 'kit-route-pin-dot';
        pin.appendChild(pinDot);

        var pinNum = document.createElement('div');
        pinNum.className = 'kit-route-pin-num';
        pinNum.textContent = String(i + 1);
        pin.appendChild(pinNum);

        nodeWrapper.appendChild(pin);

        // Station Name Label: Font size >= 48px
        var label = document.createElement('div');
        label.className = 'kit-route-station-label';
        label.style.fontSize = numStations <= 3 ? '52px' : '48px';
        label.style.fontWeight = '700';
        label.style.opacity = nodeEase.toFixed(2);
        var ty = (1.0 - nodeEase) * 16.0;
        label.style.transform = 'translateY(' + ty.toFixed(2) + 'px)';
        label.textContent = String(stations[i]);

        nodeWrapper.appendChild(label);
        nodesRow.appendChild(nodeWrapper);
      }

      routeContainer.appendChild(nodesRow);
      card.appendChild(routeContainer);

      // Card entrance motion in first 0.7s
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
