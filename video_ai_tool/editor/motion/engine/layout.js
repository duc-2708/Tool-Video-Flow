/* Safe area layout bounds, font hierarchy, text wrapping and bounding-box collision repair.
 * Operates on the 1080x1920 design coordinate system.
 */
(()=>{'use strict';

const DESIGN_WIDTH = 1080;
const DESIGN_HEIGHT = 1920;

// Strict 1080x1920 Hard Layout Constants
const SAFE_AREA = {
  width: DESIGN_WIDTH, // 1080
  height: DESIGN_HEIGHT, // 1920
  // Header chip zone: y = 80 - 200
  headerTopPx: 80,
  headerBottomPx: 200,
  // Content zone: y = 240 - 1330 (height = 1090px, width = 940px, x: 70 - 1010)
  contentLeftPx: 70,
  contentRightPx: 1010,
  contentWidthPx: 940,
  contentTopPx: 240,
  contentBottomPx: 1330,
  contentHeightPx: 1090,
  contentCenterXPx: 540,
  contentCenterYPx: 785,
  contentAreaPx2: 940 * 1090, // 1,024,600 px^2
  // Subtitle / captions zone: y = 1380 - 1700
  captionTopPx: 1380,
  captionBottomPx: 1700,
  // Strict Hero Element Limits
  minHeroWidthPx: 880,
  minHeroAreaRatio: 0.45, // >= 45% of content zone (461,070 px^2)
  minHeroAreaPx2: 461070,
  minRowHeightPx: 150,
  maxListRows: 4,
  minNodeDiameterPx: 240,
  maxEmptyGapRatio: 0.12,
  // Strict Typography Limits
  minMainFontSizePx: 56,
  minSecondaryFontSizePx: 42,
  absoluteMinFontSizePx: 36,
  // Mascot zone: outside subtitle zone (y <= 1330)
  mascotMaxYPx: 1330
};

// Smart text line wrapping
function wrapText(text, maxCharsPerLine = 18, maxLines = 4) {
  if (!text) return [];
  // Take first clause and limit to at most 6 words per element (Rule 4)
  const firstSentence = String(text).trim().split(/[.!?\n]/)[0].trim();
  const words = firstSentence.split(/\s+/).filter(Boolean).slice(0, 6);
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
