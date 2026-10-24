"""Word sidecars shared by TTS, captions and deterministic motion rendering."""
import json
import math
from pathlib import Path
from utils.atomic_io import write_json_atomic


def estimate_words(text, duration):
    words = text.split()
    total = sum(max(1, len(w)) for w in words)
    cursor, result = 0., []
    for word in words:
        end = cursor + duration * max(1, len(word)) / total
        result.append({"text": word, "start": cursor, "end": end})
        cursor = end
    return result


def read_words(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data.get("words", []) if isinstance(data, dict) else data
    except (OSError, ValueError, TypeError):
        return []


def timing_source(path):
    try:
        data=json.loads(Path(path).read_text(encoding="utf-8"))
        return data.get("timing_source","word_boundary") if isinstance(data,dict) else "word_boundary"
    except (OSError,ValueError,TypeError): return "estimated_characters"


def align_words(text, duration, observed=()):
    """Keep exact tokens; distribute split/combined service boundaries by characters.

    Numbers expanded for speech cannot be force-aligned without an aligner. Their
    proportional projection is explicitly marked, never advertised as exact.
    """
    expected = text.split()
    try:
        source = [{"text": str(w["text"]), "start": float(w["start"]), "end": float(w["end"])} for w in observed]
        valid = bool(source) and all(math.isfinite(w["start"]) and math.isfinite(w["end"])
            and 0 <= w["start"] < w["end"] <= duration + .08 for w in source)
        valid = valid and all(b["start"] >= a["end"] - .001 for a, b in zip(source, source[1:]))
        if valid:
            # Edge may emit a phrase as one boundary. Split it, preserving gaps.
            expanded = []
            for w in source:
                expanded.extend({"text": x["text"], "start": x["start"] + w["start"],
                    "end": min(duration, x["end"] + w["start"])} for x in estimate_words(w["text"], w["end"] - w["start"]))
            norm = lambda s: "".join(c.casefold() for c in s if c.isalnum())
            if [norm(w["text"]) for w in expanded] == [norm(w) for w in expected]:
                return [dict(w, text=token) for w, token in zip(expanded, expected)], "word_boundary"
            # Speech transformations (e.g. 30 -> ba mươi) retain approximate cadence.
            weights = sum(max(1, len(w["text"])) for w in source)
            def at(fraction):
                position = fraction * weights
                for w in source:
                    size = max(1, len(w["text"]))
                    if position <= size:
                        return min(duration, w["start"] + (w["end"] - w["start"]) * position / size)
                    position -= size
                return min(duration, source[-1]["end"])
            estimated = estimate_words(text, 1.)
            return [dict(w, start=at(w["start"]), end=at(w["end"])) for w in estimated], "boundary_projected"
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    return estimate_words(text, duration), "estimated_characters"


def save_words(path, text, duration, observed=(), *, source=None):
    words, method = align_words(text, duration, observed)
    write_json_atomic(path, {"version": 1, "timing_source": source or method,
        "duration_sec": duration, "words": words})
    return words
