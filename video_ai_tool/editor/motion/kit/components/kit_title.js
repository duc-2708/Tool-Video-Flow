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

      // 4. Optional Thumbnail / Image (check first to determine typography)
      var thumbSrc = slots.thumbnail || slots.image || slots.image_url;
      var hasImage = Boolean(thumbSrc);

      // Max 2 ideas per scene: 1 main headline + 1 supporting sub-line
      // Idea 1: Large Headline / Title
      // Requirement 5: headline >= 88px (tối đa 3 dòng via kit-title-lg); cảnh không ảnh thì headline phóng lớn >= 104px (kit-title-hero)
      var headline = slots.headline || slots.title || '';
      if (!headline) {
        headline = slots.quote || slots.subtitle || slots.sub || slots.narration || '';
      }
      if (headline) {
        var title = document.createElement('div');
        title.className = hasImage ? 'kit-title-lg' : 'kit-title-hero';
        if (headline.length > 70) {
          title.style.fontSize = hasImage ? '76px' : '88px';
        } else if (headline.length > 50) {
          title.style.fontSize = hasImage ? '82px' : '96px';
        }
        title.textContent = String(headline);
        card.appendChild(title);
      }

      // Idea 2: Supporting Sub-line (câu phụ >= 48px/52px via kit-subtitle)
      var sub = slots.subtitle || slots.sub || slots.text || '';
      if (!sub && !hasImage) {
        sub = slots.narration || slots.description || '';
      }
      if (sub && sub !== headline) {
        var normH = String(headline).toLowerCase().replace(/[^\w\s]/g, '').trim();
        var normS = String(sub).toLowerCase().replace(/[^\w\s]/g, '').trim();
        if (!normH || (normH !== normS && !normH.includes(normS) && !normS.includes(normH))) {
          var subEl = document.createElement('div');
          subEl.className = 'kit-subtitle';
          subEl.textContent = String(sub);
          card.appendChild(subEl);
        }
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

      // Requirement 3: ảnh nếu có cao >= 520px
      if (hasImage) {
        var imgWrapper = document.createElement('div');
        imgWrapper.style.width = '100%';
        imgWrapper.style.height = '540px';
        imgWrapper.style.borderRadius = '24px';
        imgWrapper.style.overflow = 'hidden';
        imgWrapper.style.marginTop = '24px';
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
