"""Exact allowed citations and legacy spoken aliases, derived only from brief."""
import re
import unicodedata
from agents.vietnamese_tts import spoken_to_digits
from utils.source_credits import publisher_name


def allowed_sources(brief):
    return list(dict.fromkeys(name for f in brief.facts for name in (f.source_name,publisher_name(f.source_url)) if name))


def source_key(text):
    text=spoken_to_digits(text).casefold()
    text=re.sub(r"\s*(?:&|\bvà\b)\s*"," ",text)
    text=unicodedata.normalize("NFKD",text).replace("đ","d")
    return "".join(c for c in text if c.isalnum() and not unicodedata.combining(c))


def canonical_sources(text,brief):
    names={source_key(name):name for name in reversed(allowed_sources(brief))}
    def fix(match):
        canonical=names.get(source_key(match[1]))
        return "Theo "+canonical+"," if canonical else match[0]
    text=re.sub(r"\bTheo\s+([^,!?;\n]+),",fix,text,flags=re.I)
    for name in names.values():
        text=re.sub(r"(?:\bTheo\s+"+re.escape(name)+r",\s*){2,}","Theo "+name+", ",text,flags=re.I)
    return text


def number_names(brief):
    # A product/version is authorized as a whole name, never as an unrelated price.
    text=brief.topic+" "+" ".join((f.fact_vi or f.claim) for f in brief.facts)
    products=re.findall(r"\b[A-Z][A-Za-z-]+(?:\s+[A-Z][A-Za-z-]+)*\s+\d+(?:[.,]\d+)*(?:[A-Za-z]+)?\b",text)
    products=[name for name in products if name.split()[0].upper() not in {"USD","VND","EUR","GBP","PRICE","COST","TOP"}]
    return sorted(set(allowed_sources(brief)+products),key=len,reverse=True)


def normalize_source_names(plan,brief,diagnostics=None):
    for scene in plan.scenes:
        fixed=canonical_sources(scene.narration,brief)
        if fixed!=scene.narration:
            scene.narration=fixed
            message=f"Cảnh {scene.id}: khôi phục tên nguồn từ alias TTS về đúng danh sách nguồn trong brief."
            if message not in plan.review_notes: plan.review_notes.append(message)
            if diagnostics: diagnostics.record(message)
