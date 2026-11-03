// Motion Kit v2 - kit_photo.js
(function() {
  window.KitPhoto = {
    render: function(container, slots, tau, duration) {
      if (!slots) return "unavailable";

      var photoSrc = slots.path || slots.image_url || slots.image || slots.image_path || slots.image_uri;
      if (!photoSrc || typeof photoSrc !== 'string' || !photoSrc.trim()) {
        // Return unavailable status so caller can fallback to kit_title
        return "unavailable";
      }

      var card = document.createElement('div');
      card.className = 'kit-photo-card';

      var img = document.createElement('img');
      img.className = 'kit-photo-img';
      img.src = photoSrc;

      // Slow Ken Burns zoom 1.00 -> 1.03 across scene
      var pZoom = Math.min(1.0, Math.max(0.0, tau / Math.max(0.1, duration)));
      var scale = 1.00 + 0.03 * pZoom;
      img.style.transform = 'scale(' + scale.toFixed(4) + ')';

      card.appendChild(img);

      // Caption overlay if name, role, or credit exists
      if (slots.name || slots.role || slots.credit || slots.caption) {
        var overlay = document.createElement('div');
        overlay.className = 'kit-photo-overlay';

        if (slots.name || slots.caption) {
          var nameEl = document.createElement('div');
          nameEl.className = 'kit-photo-name';
          nameEl.textContent = String(slots.name || slots.caption);
          overlay.appendChild(nameEl);
        }

        if (slots.role) {
          var roleEl = document.createElement('div');
          roleEl.className = 'kit-photo-role';
          roleEl.textContent = String(slots.role);
          overlay.appendChild(roleEl);
        }

        if (slots.credit) {
          var creditEl = document.createElement('div');
          creditEl.className = 'kit-photo-credit';
          creditEl.textContent = String(slots.credit);
          overlay.appendChild(creditEl);
        }

        card.appendChild(overlay);
      }

      // Entrance motion
      var pEnter = Math.min(1.0, Math.max(0.0, tau / 0.7));
      var easeOut = 1.0 - Math.pow(1.0 - pEnter, 3);
      var translateY = (1.0 - easeOut) * 20.0;
      var opacity = easeOut;

      card.style.transform = 'translateY(' + translateY.toFixed(2) + 'px)';
      card.style.opacity = opacity.toFixed(3);

      container.appendChild(card);
      return "ok";
    }
  };
})();
