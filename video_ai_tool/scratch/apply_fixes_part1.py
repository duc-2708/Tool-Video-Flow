import re
from pathlib import Path

# 1. Update editor/motion/engine/layout.js
layout_path = Path("editor/motion/engine/layout.js")
layout_code = layout_path.read_text(encoding="utf-8")
old_wrap = """function wrapText(text, maxCharsPerLine = 18, maxLines = 4) {
  if (!text) return [];
  const words = String(text).trim().split(/\\s+/);
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
  const totalWordsInLines = lines.join(' ').split(/\\s+/).length;
  if (totalWordsInLines < words.length && lines.length > 0) {
    lines[lines.length - 1] = lines[lines.length - 1].replace(/[.,!?;:]*$/, '') + '…';
  }

  return lines.slice(0, maxLines);
}"""

new_wrap = """function wrapText(text, maxCharsPerLine = 18, maxLines = 4) {
  if (!text) return [];
  // Take first clause and limit to at most 6 words per element (Rule 4)
  const firstSentence = String(text).trim().split(/[.!?\\n]/)[0].trim();
  const words = firstSentence.split(/\\s+/).filter(Boolean).slice(0, 6);
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
}"""

if old_wrap in layout_code:
    layout_code = layout_code.replace(old_wrap, new_wrap)
    layout_path.write_text(layout_code, encoding="utf-8")
    print("Updated layout.js wrapText")
else:
    # Regex fallback if CRLF differs
    pattern = r"function wrapText\(text, maxCharsPerLine = 18, maxLines = 4\) \{[\s\S]*?return lines\.slice\(0, maxLines\);\s*\}"
    layout_code = re.sub(pattern, new_wrap, layout_code)
    layout_path.write_text(layout_code, encoding="utf-8")
    print("Updated layout.js wrapText via regex")

# 2. Update editor/motion/engine/mascot.js
mascot_path = Path("editor/motion/engine/mascot.js")
mascot_code = mascot_path.read_text(encoding="utf-8")
new_mascot_func = """function calculateMascotPlacement(specZone = 'center', width = 1080, height = 1920, contentBounds = null) {
  const mascotW = 160;
  const mascotH = 190;
  
  // Safe zone for mascot: strictly y <= 1330, and y >= 240
  // Default placement in top safe corner y in [240, 500]
  let x = 75;
  let y = 250;
  let hidden = false;

  if (contentBounds) {
    // If content fills both horizontally (width >= 720) and vertically (y <= 450 and y + h >= 1150)
    // Then no safe corner exists without overlapping -> hide mascot
    if (contentBounds.width >= 720 && contentBounds.y <= 450 && (contentBounds.y + contentBounds.height) >= 1150) {
      hidden = true;
    } else if (contentBounds.y > 480) {
      // Content starts low -> top corner is completely free!
      x = 80;
      y = 250;
    } else if (contentBounds.x > 320) {
      // Left side is free
      x = 75;
      y = 550;
    } else if (contentBounds.x + contentBounds.width < 760) {
      // Right side is free
      x = width - mascotW - 75;
      y = 550;
    } else {
      // Try top right corner if top left is occupied
      x = width - mascotW - 75;
      y = 250;
      if (contentBounds.x + contentBounds.width > x && contentBounds.y < y + mascotH) {
        hidden = true; // Still overlapping
      }
    }
  } else {
    // Default top-left corner
    x = 75;
    y = 250;
  }

  // Double check bounds: never exceed y + mascotH > 1330 or y < 240
  if (y + mascotH > 1330) {
    y = 1330 - mascotH;
  }
  if (y < 240) {
    y = 240;
  }

  return { x, y, width: mascotW, height: mascotH, hidden };
}"""

pattern = r"function calculateMascotPlacement\(specZone = 'center', width = 1080, height = 1920\) \{[\s\S]*?return \{ x, y, width: mascotW, height: mascotH \};\s*\}"
mascot_code = re.sub(pattern, new_mascot_func, mascot_code)
mascot_path.write_text(mascot_code, encoding="utf-8")
print("Updated mascot.js calculateMascotPlacement")

# 3. Update editor/motion/scenes/scenes.css
css_path = Path("editor/motion/scenes/scenes.css")
css_code = css_path.read_text(encoding="utf-8")
css_code = re.sub(r"\.scene-source\{[^}]+\}", ".scene-source{position:absolute;left:70px;top:1255px;width:940px;font-size:36px;font-weight:700;text-align:center;color:#cbd5e1;background:#0e1a2eea;padding:10px 20px;border-radius:18px;border:1px solid #334155;max-height:75px;overflow:hidden;box-sizing:border-box;z-index:10}", css_code)
css_code = re.sub(r"\.action-mascot\{[^}]+\}", ".action-mascot{position:absolute;left:80px;top:250px;width:160px;height:190px;pointer-events:none;z-index:8}", css_code)
css_path.write_text(css_code, encoding="utf-8")
print("Updated scenes.css")
