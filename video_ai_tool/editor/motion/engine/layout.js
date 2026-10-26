/* Safe area layout bounds, font hierarchy, text wrapping and bounding-box collision repair.
 * Operates on the 1080x1920 design coordinate system.
 */
(()=>{'use strict';

const DESIGN_WIDTH = 1080;
const DESIGN_HEIGHT = 1920;

// Safe Area Constants
const SAFE_AREA = {
  width: DESIGN_WIDTH,
  height: DESIGN_HEIGHT,
  // Top 8% reserved for Section Header Chip
  topReservedPct: 0.08,
  topReservedPx: DESIGN_HEIGHT * 0.08, // 153.6px
  // Bottom 22% reserved for Captions & Footer Progress
  bottomReservedPct: 0.22,
  bottomStartPx: DESIGN_HEIGHT * (1 - 0.22), // 1497.6px
  // Content Zone: Y from 153.6px to 1497.6px (70% total height = 1344px)
  contentHeightPx: DESIGN_HEIGHT * 0.70, // 1344px
  contentTopPx: DESIGN_HEIGHT * 0.08,
  contentBottomPx: DESIGN_HEIGHT * 0.78,
  // Minimum Element Coverage
  minWidthRatio: 0.60, // >= 60% of width = 648px
  minWidthPx: DESIGN_WIDTH * 0.60,
  minContentHeightRatio: 0.35, // >= 35% of content height = 470.4px
  minContentHeightPx: DESIGN_HEIGHT * 0.70 * 0.35,
  // Max vertical empty space ratio
  maxEmptyGapRatio: 0.12, // 12% of screen height = 230.4px
  maxEmptyGapPx: DESIGN_HEIGHT * 0.12,
  // Font Size Rules
  minMainFontSizePx: 38,
  minSecondaryFontSizePx: 32
};

// Smart text line wrapping
function wrapText(text, maxCharsPerLine = 18, maxLines = 4) {
  if (!text) return [];
  const words = String(text).trim().split(/\s+/);
  const lines = [];
  let currentLine = '';

  for (const word of words) {
    if (!currentLine) {
      currentLine = word;
    } else if ((currentLine + ' ' + word).length <= maxCharsPerLine) {
      currentLine += ' ' + word;
    } else {
      lines.push(currentLine);
      currentLine = word;
      if (lines.length >= maxLines - 1) {
        break;
      }
    }
  }
  if (currentLine) {
    lines.push(currentLine);
  }

  // If there were remaining words beyond maxLines, add ellipsis to the last line
  const totalWordsInLines = lines.join(' ').split(/\s+/).length;
  if (totalWordsInLines < words.length && lines.length > 0) {
    lines[lines.length - 1] = lines[lines.length - 1].replace(/[.,!?;:]*$/, '') + '…';
  }

  return lines.slice(0, maxLines);
}

// Bounding box collision detection between 2 rectangles
function checkRectOverlap(r1, r2, thresholdRatio = 0.10) {
  const overlapX = Math.max(0, Math.min(r1.x + r1.w, r2.x + r2.w) - Math.max(r1.x, r2.x));
  const overlapY = Math.max(0, Math.min(r1.y + r1.h, r2.y + r2.h) - Math.max(r1.y, r2.y));
  const overlapArea = overlapX * overlapY;
  if (overlapArea <= 0) return 0;
  const minArea = Math.min(r1.w * r1.h, r2.w * r2.h);
  return overlapArea / Math.max(1, minArea);
}

// Automatic 1-pass layout repair for text box overlaps
function repairCollisions(boxes) {
  if (!boxes || boxes.length < 2) return boxes;
  const repaired = boxes.map(b => ({ ...b }));

  // Sort boxes vertically
  repaired.sort((a, b) => a.y - b.y);

  for (let i = 0; i < repaired.length - 1; i++) {
    const cur = repaired[i];
    const nxt = repaired[i + 1];
    const overlapRatio = checkRectOverlap(cur, nxt, 0.08);

    if (overlapRatio > 0.08) {
      // Overlap detected: push next box down to create a safe 16px buffer
      const requiredY = cur.y + cur.h + 16;
      const shift = requiredY - nxt.y;
      if (shift > 0) {
        nxt.y = requiredY;
        // If pushing pushes it beyond content bottom, shrink both slightly
        if (nxt.y + nxt.h > SAFE_AREA.contentBottomPx) {
          const excess = (nxt.y + nxt.h) - SAFE_AREA.contentBottomPx;
          cur.y = Math.max(SAFE_AREA.contentTopPx, cur.y - excess * 0.5);
          cur.h = Math.max(40, cur.h * 0.9);
          nxt.y = cur.y + cur.h + 12;
          nxt.h = Math.max(40, nxt.h * 0.9);
        }
      }
    }
  }

  return repaired;
}

window.MotionLayout = {
  SAFE_AREA,
  wrapText,
  checkRectOverlap,
  repairCollisions
};
})();
