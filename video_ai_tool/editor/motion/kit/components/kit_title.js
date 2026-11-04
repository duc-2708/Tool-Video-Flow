// Motion Kit v2 - kit_title.js
(function() {
  window.KitTitle = {
    render: function(container, slots, tau, duration) {
      if (!slots) return;
      var card = document.createElement('div');
      card.className = 'kit-card';

      // 1. Optional Pill / Tag
      if (slots.pill) {
        var pill = document.createElement('div');
        pill.className = 'kit-pill';
        pill.textContent = String(slots.pill);
        card.appendChild(pill);
      }

      // Max 2 ideas per scene: 1 main headline + 1 supporting sub-line
      // Idea 1: Large Headline / Title (font-size >= 64px via kit-title-hero)
      var headline = slots.headline || slots.title || '';
      if (headline) {
        var title = document.createElement('div');
        title.className = 'kit-title-hero';
        title.textContent = String(headline);
        card.appendChild(title);
      }

      // Idea 2: Supporting Sub-line
      var sub = slots.subtitle || slots.sub || slots.text || '';
      if (sub && sub !== headline) {
        var subEl = document.createElement('div');
        subEl.className = 'kit-subtitle';
        subEl.textContent = String(sub);
        card.appendChild(subEl);
      }

      // Explicit Icon ONLY when planner selected icon WITH a reason (no default lightbulb)
      if (slots.icon && slots.icon_reason && slots.icon_uri) {
        var iconWrap = document.createElement('div');
        iconWrap.style.marginTop = '20px';
        var iconImg = document.createElement('img');
        iconImg.src = slots.icon_uri;
        iconImg.style.width = '48px';
        iconImg.style.height = '48px';
        iconWrap.appendChild(iconImg);
        card.appendChild(iconWrap);
      }

      // 4. Optional Thumbnail
      var thumbSrc = slots.thumbnail || slots.image || slots.image_url;
      if (thumbSrc) {
        var imgWrapper = document.createElement('div');
        imgWrapper.style.width = '100%';
        imgWrapper.style.height = '340px';
        imgWrapper.style.borderRadius = '20px';
        imgWrapper.style.overflow = 'hidden';
        imgWrapper.style.marginTop = '28px';
        imgWrapper.style.border = '1px solid var(--kit-card-border)';
        var img = document.createElement('img');
        img.src = String(thumbSrc);
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
