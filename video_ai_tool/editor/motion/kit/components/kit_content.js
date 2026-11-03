// Motion Kit v2 - kit_content.js
(function() {
  function easeOutCubic(p) {
    var clamped = Math.min(1.0, Math.max(0.0, p));
    return 1.0 - Math.pow(1.0 - clamped, 3);
  }

  window.KitContent = {
    renderList: function(container, slots, tau, duration) {
      if (!slots) return;
      var card = document.createElement('div');
      card.className = 'kit-card';

      if (slots.pill) {
        var pill = document.createElement('div');
        pill.className = 'kit-pill';
        pill.textContent = String(slots.pill);
        card.appendChild(pill);
      }

      var titleText = slots.title || slots.headline;
      if (titleText) {
        var titleEl = document.createElement('div');
        titleEl.className = 'kit-title-lg';
        titleEl.textContent = String(titleText);
        card.appendChild(titleEl);
      }

      var listWrap = document.createElement('div');
      listWrap.className = 'kit-list-container';

      var items = slots.items || [];
      var maxItems = Math.min(4, items.length);

      for (var i = 0; i < maxItems; i++) {
        var itemEl = document.createElement('div');
        itemEl.className = 'kit-list-item';

        var icon = document.createElement('div');
        icon.className = 'kit-list-icon';
        icon.textContent = String(i + 1);
        itemEl.appendChild(icon);

        var textEl = document.createElement('div');
        textEl.className = 'kit-list-text';
        textEl.textContent = String(items[i]);
        itemEl.appendChild(textEl);

        // Staggered reveal in first 0.7s (stagger <= 0.12s)
        var startT = i * 0.12;
        var pItem = Math.min(1.0, Math.max(0.0, (tau - startT) / 0.4));
        var itemEase = easeOutCubic(pItem);

        itemEl.style.transform = 'translateY(' + ((1.0 - itemEase) * 16.0).toFixed(2) + 'px)';
        itemEl.style.opacity = itemEase.toFixed(3);

        listWrap.appendChild(itemEl);
      }

      card.appendChild(listWrap);

      var pEnter = Math.min(1.0, Math.max(0.0, tau / 0.7));
      var easeOut = easeOutCubic(pEnter);
      var translateY = (1.0 - easeOut) * 20.0;
      var pDrift = Math.min(1.0, Math.max(0.0, tau / Math.max(0.1, duration)));
      var currentScale = 1.0 + 0.02 * pDrift;

      card.style.transform = 'translateY(' + translateY.toFixed(2) + 'px) scale(' + currentScale.toFixed(4) + ')';
      card.style.opacity = easeOut.toFixed(3);

      container.appendChild(card);
    },

    renderCompare: function(container, slots, tau, duration) {
      if (!slots) return;
      var card = document.createElement('div');
      card.className = 'kit-card';

      if (slots.pill) {
        var pill = document.createElement('div');
        pill.className = 'kit-pill';
        pill.textContent = String(slots.pill);
        card.appendChild(pill);
      }

      var titleText = slots.title || slots.headline;
      if (titleText) {
        var titleEl = document.createElement('div');
        titleEl.className = 'kit-title-lg';
        titleEl.textContent = String(titleText);
        card.appendChild(titleEl);
      }

      var grid = document.createElement('div');
      grid.className = 'kit-compare-grid';

      var leftData = slots.left || {};
      var rightData = slots.right || {};

      var leftCol = document.createElement('div');
      leftCol.className = 'kit-compare-col' + (leftData.winner ? ' winner' : '');
      if (leftData.title) {
        var lTitle = document.createElement('div');
        lTitle.className = 'kit-compare-title';
        lTitle.textContent = String(leftData.title);
        leftCol.appendChild(lTitle);
      }
      if (leftData.text) {
        var lText = document.createElement('div');
        lText.className = 'kit-compare-text';
        lText.textContent = String(leftData.text);
        leftCol.appendChild(lText);
      }
      grid.appendChild(leftCol);

      var rightCol = document.createElement('div');
      rightCol.className = 'kit-compare-col' + (rightData.winner ? ' winner' : '');
      if (rightData.title) {
        var rTitle = document.createElement('div');
        rTitle.className = 'kit-compare-title';
        rTitle.textContent = String(rightData.title);
        rightCol.appendChild(rTitle);
      }
      if (rightData.text) {
        var rText = document.createElement('div');
        rText.className = 'kit-compare-text';
        rText.textContent = String(rightData.text);
        rightCol.appendChild(rText);
      }
      grid.appendChild(rightCol);

      card.appendChild(grid);

      var pEnter = Math.min(1.0, Math.max(0.0, tau / 0.7));
      var easeOut = easeOutCubic(pEnter);
      var translateY = (1.0 - easeOut) * 20.0;
      var pDrift = Math.min(1.0, Math.max(0.0, tau / Math.max(0.1, duration)));
      var currentScale = 1.0 + 0.02 * pDrift;

      card.style.transform = 'translateY(' + translateY.toFixed(2) + 'px) scale(' + currentScale.toFixed(4) + ')';
      card.style.opacity = easeOut.toFixed(3);

      container.appendChild(card);
    },

    renderQuote: function(container, slots, tau, duration) {
      if (!slots) return;
      var card = document.createElement('div');
      card.className = 'kit-card';

      if (slots.pill) {
        var pill = document.createElement('div');
        pill.className = 'kit-pill';
        pill.textContent = String(slots.pill);
        card.appendChild(pill);
      }

      var qMark = document.createElement('div');
      qMark.className = 'kit-quote-mark';
      qMark.textContent = '“';
      card.appendChild(qMark);

      var qText = slots.quote || slots.text || slots.title;
      if (qText) {
        var quoteEl = document.createElement('div');
        quoteEl.className = 'kit-quote-text';
        quoteEl.textContent = String(qText);
        card.appendChild(quoteEl);
      }

      if (slots.author) {
        var authorEl = document.createElement('div');
        authorEl.className = 'kit-quote-author';
        authorEl.textContent = String(slots.author);
        card.appendChild(authorEl);
      }

      if (slots.role || slots.source) {
        var roleEl = document.createElement('div');
        roleEl.className = 'kit-quote-role';
        roleEl.textContent = String(slots.role || slots.source);
        card.appendChild(roleEl);
      }

      var pEnter = Math.min(1.0, Math.max(0.0, tau / 0.7));
      var easeOut = easeOutCubic(pEnter);
      var translateY = (1.0 - easeOut) * 20.0;
      var pDrift = Math.min(1.0, Math.max(0.0, tau / Math.max(0.1, duration)));
      var currentScale = 1.0 + 0.02 * pDrift;

      card.style.transform = 'translateY(' + translateY.toFixed(2) + 'px) scale(' + currentScale.toFixed(4) + ')';
      card.style.opacity = easeOut.toFixed(3);

      container.appendChild(card);
    },

    renderTimeline: function(container, slots, tau, duration) {
      if (!slots) return;
      var card = document.createElement('div');
      card.className = 'kit-card';

      if (slots.pill) {
        var pill = document.createElement('div');
        pill.className = 'kit-pill';
        pill.textContent = String(slots.pill);
        card.appendChild(pill);
      }

      var titleText = slots.title || slots.headline;
      if (titleText) {
        var titleEl = document.createElement('div');
        titleEl.className = 'kit-title-lg';
        titleEl.textContent = String(titleText);
        card.appendChild(titleEl);
      }

      var tlWrap = document.createElement('div');
      tlWrap.className = 'kit-timeline-container';

      var milestones = slots.milestones || slots.items || [];
      var maxItems = Math.min(5, milestones.length);

      for (var i = 0; i < maxItems; i++) {
        var mItem = milestones[i];
        var itemEl = document.createElement('div');
        itemEl.className = 'kit-timeline-item';

        var node = document.createElement('div');
        node.className = 'kit-timeline-node';
        itemEl.appendChild(node);

        var content = document.createElement('div');
        content.className = 'kit-timeline-content';

        var timeStr = typeof mItem === 'object' ? (mItem.time || mItem.year || mItem.date || '') : '';
        if (timeStr) {
          var timeEl = document.createElement('div');
          timeEl.className = 'kit-timeline-time';
          timeEl.textContent = String(timeStr);
          content.appendChild(timeEl);
        }

        var labelStr = typeof mItem === 'object' ? (mItem.label || mItem.text || '') : String(mItem);
        var labelEl = document.createElement('div');
        labelEl.className = 'kit-timeline-label';
        labelEl.textContent = labelStr;
        content.appendChild(labelEl);

        itemEl.appendChild(content);

        // Staggered reveal in 0.7s
        var startT = i * 0.12;
        var pItem = Math.min(1.0, Math.max(0.0, (tau - startT) / 0.4));
        var itemEase = easeOutCubic(pItem);

        itemEl.style.transform = 'translateY(' + ((1.0 - itemEase) * 16.0).toFixed(2) + 'px)';
        itemEl.style.opacity = itemEase.toFixed(3);

        tlWrap.appendChild(itemEl);
      }

      card.appendChild(tlWrap);

      var pEnter = Math.min(1.0, Math.max(0.0, tau / 0.7));
      var easeOut = easeOutCubic(pEnter);
      var translateY = (1.0 - easeOut) * 20.0;
      var pDrift = Math.min(1.0, Math.max(0.0, tau / Math.max(0.1, duration)));
      var currentScale = 1.0 + 0.02 * pDrift;

      card.style.transform = 'translateY(' + translateY.toFixed(2) + 'px) scale(' + currentScale.toFixed(4) + ')';
      card.style.opacity = easeOut.toFixed(3);

      container.appendChild(card);
    },

    renderOutro: function(container, slots, tau, duration) {
      if (!slots) return;
      var card = document.createElement('div');
      card.className = 'kit-card';

      var outroWrap = document.createElement('div');
      outroWrap.className = 'kit-outro-container';

      var logo = document.createElement('div');
      logo.className = 'kit-outro-logo';
      if (slots.logo_url) {
        var img = document.createElement('img');
        img.src = slots.logo_url;
        logo.appendChild(img);
      } else {
        logo.textContent = String(slots.channel_name || 'AI').charAt(0);
      }
      outroWrap.appendChild(logo);

      if (slots.channel_name) {
        var chEl = document.createElement('div');
        chEl.className = 'kit-outro-channel';
        chEl.textContent = String(slots.channel_name);
        outroWrap.appendChild(chEl);
      }

      if (slots.call_to_action || slots.cta || slots.text) {
        var ctaEl = document.createElement('div');
        ctaEl.className = 'kit-outro-cta';
        ctaEl.textContent = String(slots.call_to_action || slots.cta || slots.text);
        outroWrap.appendChild(ctaEl);
      }

      if (slots.button_text) {
        var btn = document.createElement('div');
        btn.className = 'kit-outro-btn';
        btn.textContent = String(slots.button_text);
        outroWrap.appendChild(btn);
      }

      card.appendChild(outroWrap);

      var pEnter = Math.min(1.0, Math.max(0.0, tau / 0.7));
      var easeOut = easeOutCubic(pEnter);
      var translateY = (1.0 - easeOut) * 20.0;
      var pDrift = Math.min(1.0, Math.max(0.0, tau / Math.max(0.1, duration)));
      var currentScale = 1.0 + 0.02 * pDrift;

      card.style.transform = 'translateY(' + translateY.toFixed(2) + 'px) scale(' + currentScale.toFixed(4) + ')';
      card.style.opacity = easeOut.toFixed(3);

      container.appendChild(card);
    }
  };
})();
