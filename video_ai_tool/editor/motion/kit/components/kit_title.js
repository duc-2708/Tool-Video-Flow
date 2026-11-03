// Motion Kit v2 - kit_title.js
(function() {
  window.KitTitle = {
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

      // 2. Large Headline / Title (Required in kit_title)
      if (slots.title) {
        var title = document.createElement('div');
        title.className = 'kit-title-hero';
        title.textContent = String(slots.title);
        card.appendChild(title);
      }

      // 3. Optional Subtitle
      if (slots.subtitle || slots.text) {
        var sub = document.createElement('div');
        sub.className = 'kit-subtitle';
        sub.textContent = String(slots.subtitle || slots.text);
        card.appendChild(sub);
      }

      // 4. Optional Thumbnail
      if (slots.thumbnail || slots.image) {
        var imgWrapper = document.createElement('div');
        imgWrapper.style.width = '100%';
        imgWrapper.style.height = '340px';
        imgWrapper.style.borderRadius = '20px';
        imgWrapper.style.overflow = 'hidden';
        imgWrapper.style.marginTop = '28px';
        imgWrapper.style.border = '1px solid var(--kit-card-border)';
        var img = document.createElement('img');
        img.src = String(slots.thumbnail || slots.image);
        img.style.width = '100%';
        img.style.height = '100%';
        img.style.objectFit = 'cover';
        imgWrapper.appendChild(img);
        card.appendChild(imgWrapper);
      }

      // Motion in first 0.7s, then hold
      var pEnter = Math.min(1.0, Math.max(0.0, tau / 0.7));
      var easeOut = 1.0 - Math.pow(1.0 - pEnter, 3);
      var translateY = (1.0 - easeOut) * 24.0;
      var opacity = easeOut;

      // Subtle one-way drift across full duration (max 2.5% scale or 6px translation)
      var pDrift = Math.min(1.0, Math.max(0.0, tau / Math.max(0.1, duration)));
      var currentScale = 1.0 + 0.02 * pDrift;

      card.style.transform = 'translateY(' + translateY.toFixed(2) + 'px) scale(' + currentScale.toFixed(4) + ')';
      card.style.opacity = opacity.toFixed(3);

      container.appendChild(card);
    }
  };
})();
