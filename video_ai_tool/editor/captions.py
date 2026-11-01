"""Vietnamese karaoke captions rasterized with Pillow, no ImageMagick."""
from pathlib import Path
import json
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def find_font(root):
    folder = Path(root) / "assets/fonts"
    priority = [
        "Montserrat-Bold.ttf",
        "Montserrat-ExtraBold.ttf",
        "Inter-Bold.ttf",
        "DTPhudu-Bold.otf",
        "SpaceGrotesk-Bold.ttf",
        "DTPhudu-Black.otf",
        "Montserrat-Black.ttf",
        "Inter-Black.ttf",
    ]
    for name in priority:
        candidate = folder / name
        if candidate.is_file():
            return candidate
    candidates = sorted(folder.glob("*Bold*")) + sorted(folder.glob("*.ttf")) + sorted(folder.glob("*.otf"))
    candidates += [Path("C:/Windows/Fonts/arialbd.ttf"), Path("C:/Windows/Fonts/arial.ttf")]
    for path in candidates:
        if path.suffix.lower() in {".ttf", ".otf"} and path.is_file():
            return path
    raise ValueError("Thiếu font. Thêm font tiếng Việt .ttf/.otf vào assets/fonts/ hoặc cài Arial Bold.")


def is_standout_word(word_str):
    raw = str(word_str).strip()
    if not raw:
        return False
    w = raw.lower()
    if re.search(r"\d", w) or any(c in w for c in ("%", "$", "tỷ", "triệu", "nghìn", "usd", "vnđ", "+")):
        return True
    impact = {
        "kỷ lục", "đột phá", "bùng nổ", "bí mật", "nguy hiểm", "cảnh báo", "quan trọng",
        "thành công", "thất bại", "khủng", "siêu", "top", "hot", "sốc", "bất ngờ", "đặc biệt",
        "tuyệt đối", "cực kỳ", "vượt trội", "hàng đầu", "số 1", "kỷ", "lục", "đột", "phá",
        "nguy", "hiểm", "chấn", "động"
    }
    cleaned = re.sub(r"[^\w\s%$\+\-]", "", w)
    if cleaned in impact:
        return True
    for token in cleaned.split():
        if token in impact:
            return True
    if len(raw) >= 2 and raw.isupper() and raw.isalpha():
        return True
    return False


def wrap_lines(text, font, max_width):
    lines, line = [], ""
    for word in text.split():
        pieces, piece = [], ""
        for character in word:
            if piece and font.getlength(piece + character) > max_width:
                pieces.append(piece)
                piece = ""
            piece += character
        pieces.append(piece)
        for piece in pieces:
            candidate = f"{line} {piece}".strip()
            if line and font.getlength(candidate) > max_width:
                lines.append(line)
                line = piece
            else:
                line = candidate
    if line:
        lines.append(line)
    return lines


def word_timings(text, duration, timing_path=None):
    words = text.split()
    if timing_path and Path(timing_path).is_file():
        try:
            entries = json.loads(Path(timing_path).read_text(encoding="utf-8"))
            entries = entries.get("words", []) if isinstance(entries, dict) else entries
            if entries and [e.get("text") for e in entries] == words:
                result = [(e["text"], float(e["start"]), float(e["end"])) for e in entries]
                if all(0 <= a < b <= duration + 0.05 for _, a, b in result) and all(
                    result[i][1] >= result[i - 1][2] for i in range(1, len(result))
                ):
                    return result
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass
    weights = [max(1, len(word)) for word in words]
    total, start, result = sum(weights), 0.0, []
    for word, weight in zip(words, weights):
        end = start + duration * weight / total
        result.append((word, start, end))
        start = end
    return result


class Captions:
    def __init__(self, timeline, size, font_path):
        self.timeline = timeline
        from schemas.style import CaptionStyle

        render_style = getattr(timeline.plan, "render_style", None)
        self.style = render_style.captions if render_style else CaptionStyle()
        self.size = size
        self.font = ImageFont.truetype(str(font_path), max(24, min(54, round(size[0] * self.style.font_scale))))
        self.entries, self.cache = [], {}
        if not self.style.enabled and not any(getattr(scene, "audio_silent", False) for scene in timeline.scenes):
            return
        for scene in timeline.scenes:
            if not self.style.enabled and not getattr(scene, "audio_silent", False):
                continue
            timing = scene.audio.with_suffix(".words.json")
            timing = timing if timing.resolve().is_relative_to(scene.audio.parent.resolve()) else None
            text = scene.spec.narration
            if getattr(scene, "audio_silent", False):
                timing = None
                if not any(c.isalnum() for c in text):
                    text = "Không có nội dung lời đọc."
            from utils.caption_timing import display_words, phrase_groups

            words = display_words(word_timings(text, scene.duration, timing), scene.duration)
            mode = "phrase" if any(getattr(s.spec, "visual", None) and s.spec.visual.template != "stock" for s in scene.shots) else self.style.mode
            count = 1 if mode == "word" else 3
            if mode == "sentence":
                groups, current = [], []
                for word in words:
                    current.append(word)
                    if re.search(r"[.!?]$", word[0]) or len(current) >= 18:
                        groups.append(current)
                        current = []
                if current:
                    groups.append(current)
            else:
                groups = phrase_groups(words, count)
            if mode == "phrase" and len(groups) > 1 and len(groups[-1]) == 1:
                groups[-2].extend(groups.pop())
            for group in groups:
                for active, (_, start, end) in enumerate(group):
                    self.entries.append((scene.start + start, scene.start + end, tuple(w[0] for w in group), active))

    def overlay(self, time):
        entry = next((e for e in self.entries if e[0] <= time < e[1]), None)
        if entry is None:
            return None
        scene = next((s for s in self.timeline.scenes if s.start <= time < s.start + s.duration), None)
        visual = (
            next((getattr(s.spec, "visual", None) for s in getattr(scene, "shots", []) if s.start <= time < s.start + s.duration), None)
            if scene
            else None
        )
        key = entry[2:] + (visual.template if visual else "stock",)
        if key in self.cache:
            return self.cache[key]
        width, height = self.size
        font = self.font
        if visual and visual.template != "stock":
            font = ImageFont.truetype(font.path, max(24, min(48, round(width * self.style.font_scale))))
        lines = wrap_lines(" ".join(entry[2]), font, width * 0.76)
        band = 0.15 if visual and visual.template != "stock" else 0.18
        while len(lines) * font.size * 1.35 > height * band and font.size > 14:
            font = ImageFont.truetype(font.path, font.size - 1)
            lines = wrap_lines(" ".join(entry[2]), font, width * 0.76)
        step = round(font.size * 1.35)
        layer = Image.new("RGBA", self.size)
        draw = ImageDraw.Draw(layer)
        top = min(height * 0.70, height * 0.80 - len(lines) * step)
        if self.style.position == "center":
            top = (height - len(lines) * step) / 2
        elif self.style.position == "top":
            top = height * 0.12
        if visual and visual.template != "stock":
            from editor.layout import caption_box

            _, top, _, _ = caption_box(self.size, visual.template)
        consumed = 0
        white_color = self.style.color or "#FFFFFF"
        yellow_color = self.style.highlight_color or "#FFE14A"
        red_color = getattr(self.style, "standout_color", None) or "#FF3344"

        for index, line in enumerate(lines):
            x = (width - font.getlength(line)) / 2
            for word in line.split():
                is_active = (consumed == entry[3])
                standout = is_standout_word(word)
                if is_active:
                    color = red_color if standout else yellow_color
                else:
                    color = white_color

                stroke = max(2, round(width * self.style.stroke_width_ratio))
                if self.style.appearance == "pill" and is_active:
                    padding = max(3, round(width * 0.009))
                    draw.rounded_rectangle(
                        (x - padding, top + index * step - padding, x + font.getlength(word) + padding, top + index * step + font.size + padding),
                        radius=padding * 2,
                        fill=color,
                    )
                    color = "#101826"
                    stroke = 0
                elif is_active:
                    # Subtle animated glow effect for active words
                    glow_color = (255, 51, 68, 140) if standout else (255, 225, 74, 130)
                    for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        draw.text((x + ox, top + index * step + oy), word, font=font, fill=glow_color, anchor="lt")

                draw.text(
                    (x, top + index * step),
                    word,
                    font=font,
                    fill=color,
                    stroke_width=stroke,
                    stroke_fill=self.style.stroke_color or "#000000",
                    anchor="lt",
                )
                x += font.getlength(word + " ")
                consumed += 1
        if len(self.cache) >= 12:
            self.cache.clear()
        self.cache[key] = layer
        return layer

    def apply(self, frame, time):
        overlay = self.overlay(time)
        if overlay is None:
            return frame
        return np.asarray(Image.alpha_composite(Image.fromarray(frame).convert("RGBA"), overlay).convert("RGB"))
