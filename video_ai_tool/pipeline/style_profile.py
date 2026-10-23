"""Deterministic aggregation: reusable style goes to prompts, reference text does not."""
import argparse
from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from statistics import mean
import unicodedata
from config.settings import get_settings
from schemas.style import AnalysisRecord, StyleProfile, PaceRange, RuleFrequency
from utils.atomic_io import write_json_atomic
from utils.console import configure_console
from utils.text import slugify


def key(text):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def frequent(values):
    labels, counts = {}, Counter()
    for video_values in values:
        unique = {key(v): v.strip() for v in video_values if v.strip()}
        for identity, label in unique.items():
            labels.setdefault(identity, label)
            counts[identity] += 1
    return [(labels[k], n) for k, n in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def value_range(values, default):
    values = [v for v in values if v is not None and v > 0] or [default]
    return PaceRange(mean=mean(values), minimum=min(values), maximum=max(values))


def profile_folder(settings):
    folder = settings.root_dir / "config/style_presets"
    if not folder.resolve().is_relative_to(settings.root_dir.resolve()) or folder.is_symlink():
        raise ValueError("Preset phải nằm trong config/style_presets/.")
    return folder


def profile_path(settings, name):
    if not name or any(c in name for c in ("/", "\\", "..")):
        raise ValueError("Tên preset không được là đường dẫn.")
    slug = slugify(name)
    path = profile_folder(settings) / f"{slug}.json"
    if path.resolve().parent != profile_folder(settings).resolve():
        raise ValueError("Đường dẫn preset không hợp lệ.")
    return path


def load_profile(settings, name):
    if name.startswith("@"):
        from pipeline.category_style import load_token
        return load_token(settings,name)
    path = profile_path(settings, name)
    if not path.is_file():
        raise ValueError(f"Chưa có phong cách mẫu '{name}'. Phân tích video và lưu preset trước.")
    return StyleProfile.model_validate_json(path.read_text(encoding="utf-8"))


def list_profiles(settings):
    result = []
    for path in sorted(profile_folder(settings).glob("*.json")):
        try:
            if path.resolve().parent == profile_folder(settings).resolve():
                result.append(StyleProfile.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return result


def aggregate(records, name):
    # Identical file bytes count as one reference, regardless of renamed copies.
    records = list({r.file_hash: r for r in records}.values())
    if not records:
        raise ValueError("Chọn ít nhất một video đã phân tích hợp lệ.")
    analyses = [r.analysis for r in records]
    rule_counts = frequent([a.reusable_rules for a in analyses])
    common = lambda rows: [v for v, _ in frequent(rows)]
    # Select the most common observed sequence, average its matching section lengths.
    sequences = Counter(tuple(key(s.name) for s in a.structure) for a in analyses)
    winner = sequences.most_common(1)[0][0]
    chosen = next(a for a in analyses if tuple(key(s.name) for s in a.structure) == winner)
    structure = []
    for section in chosen.structure:
        shares = [s.duration_sec / sum(p.duration_sec for p in a.structure)
                  for a in analyses for s in a.structure if key(s.name) == key(section.name)]
        structure.append({"name": section.name, "fraction": mean(shares)})
    total = sum(s["fraction"] for s in structure)
    for section in structure:
        section["fraction"] /= total
    typical = max(analyses, key=lambda a: sum(key(rule) in {key(r) for r, n in rule_counts if n > 1} for rule in a.reusable_rules))
    captions = typical.captions.model_copy(deep=True)
    audio = typical.audio.model_copy(deep=True)
    # Most common presentation choices, independent of which reference came first.
    for field in ("enabled", "mode", "font_description", "color", "highlight_color", "stroke_color", "position", "emphasis", "shadow"):
        setattr(captions, field, Counter(getattr(a.captions, field) for a in analyses).most_common(1)[0][0])
    captions.font_scale = mean(a.captions.font_scale for a in analyses)
    captions.stroke_width_ratio = mean(a.captions.stroke_width_ratio for a in analyses)
    audio.mood = common([[a.audio.mood] for a in analyses])[0]
    audio.sfx_types = common([a.audio.sfx_types for a in analyses])
    audio.ducking = Counter(a.audio.ducking for a in analyses).most_common(1)[0][0]
    audio.music_volume = mean(a.audio.music_volume for a in analyses)
    audio.sfx_per_10_sec = mean(a.audio.sfx_per_10_sec for a in analyses)
    narration = common([["Xưng hô: " + "/".join(a.narration_style.pronouns),
                         "Mức thân mật: " + a.narration_style.intimacy,
                         "Câu hỏi tu từ: " + a.narration_style.rhetorical_questions,
                         "Cảm xúc giọng: " + a.narration_style.voice_emotion,
                         "Mức hài hước: " + a.narration_style.humor] for a in analyses])
    lengths = [a.narration_style.average_sentence_words for a in analyses if a.narration_style.average_sentence_words]
    if lengths:
        narration.append(f"Câu dài trung bình khoảng {mean(lengths):.0f} từ; xen câu ngắn và dài theo ý.")
    templates = common([[a.hook.template] if "{topic}" in a.hook.template else [] for a in analyses])
    result=StyleProfile(name=name.strip(), slug=slugify(name), reference_hashes=[r.file_hash for r in records],
        video_count=len(records),confidence_label="ổn" if len(records)>=3 else "yếu" if len(records)==1 else "đang tích lũy",
        reference_files=[r.filename for r in records],reference_entities=list(dict.fromkeys(e for a in analyses for e in a.entities_in_video)),
        reference_texts=[p.summary for a in analyses for p in a.transcript_outline],
        hook_templates=templates, hook_techniques=common([[a.hook.technique] for a in analyses]),
        structure=structure, shot_seconds=value_range([a.pacing.average_shot_sec for a in analyses], 3),
        speech_words_per_sec=value_range([a.narration_style.words_per_sec for a in analyses], 2.6),
        narration_rules=narration, broll_patterns=common([a.visual_style.types for a in analyses]),
        visual_effects=common([a.visual_style.camera_effects for a in analyses]),
        transitions=common([a.visual_style.transitions for a in analyses]), captions=captions, audio=audio,
        ending_techniques=common([[a.cta_ending.technique] for a in analyses]),
        reusable_rules=[r for r, _ in rule_counts], rule_frequencies=[RuleFrequency(rule=r, video_count=n) for r, n in rule_counts])
    from pipeline.style_safety import sanitize_profile
    return sanitize_profile(result)


def save_profile(settings, profile):
    from pipeline.style_safety import sanitize_profile
    profile = sanitize_profile(StyleProfile.model_validate(profile))
    if profile.category_id or profile.slug=="@default":
        from pipeline.category_style import profile_file
        path=profile_file(settings,profile.category_id,profile.video_type)
        write_json_atomic(path,profile.model_dump(mode="json"))
        return path
    path = profile_path(settings, profile.name)
    write_json_atomic(path, profile.model_dump(mode="json"))
    write_json_atomic(settings.root_dir / "config/style_profile.json", profile.model_dump(mode="json"))
    return path


def build_profile(settings, name, videos):
    from pipeline.style_learner import reference_path, digest_file
    from pipeline.style_library import record_path
    records = []
    for video in dict.fromkeys(videos):
        path = reference_path(settings, video)
        record = AnalysisRecord.model_validate_json(record_path(settings,video).read_text(encoding="utf-8"))
        if record.file_hash != digest_file(path):
            raise ValueError(f"{path.name} đã thay đổi; phân tích lại trước khi tổng hợp.")
        from utils.cache import cache_key
        notes = path.with_suffix(".txt")
        if notes.resolve().parent != path.parent:
            raise ValueError("Ghi chú video nằm ngoài thư mục mẫu.")
        if record.notes_hash != cache_key(notes.read_text(encoding="utf-8")[:8000] if notes.is_file() else ""):
            raise ValueError(f"Ghi chú {path.name} đã đổi; phân tích lại hoặc bỏ video này khỏi preset.")
        records.append(record)
    return aggregate(records, name)


def guidance(profile):
    if profile is None:
        return None
    from pipeline.style_safety import sanitize_profile
    data=sanitize_profile(profile).model_dump(mode="json", exclude={"name","slug","reference_texts","reference_entities", "reference_files", "reference_hashes", "rule_frequencies","source_signature","warnings","locked_fields"})
    # Raw observations/repair diagnostics stay local, never become writing rules.
    for section in ("captions","audio"):
        data[section].pop("analysis_warnings",None)
        data[section].pop("color_note",None)
    return data


def speech_budget(duration, profile=None):
    import math
    speed = min(3.5, max(1.5, profile.speech_words_per_sec.mean)) if profile else 2.6
    return {"min_words": math.ceil(duration * (speed-.2)), "max_words": math.floor(duration * (speed+.2)+1e-8)}


def copying_scenes(plan, threshold=.60):
    profile = plan.style_profile
    if profile is None:
        return []
    references = [key(text).split() for text in profile.reference_texts]
    found = []
    for scene in plan.scenes:
        for sentence in re.split(r"(?<=[.!?])\s+", scene.narration):
            # Common short hooks/attribution are not distinctive copied passages.
            sentence = re.sub(r"^Theo [^,]+,\s*", "", sentence, flags=re.I)
            words = key(sentence).split()
            if len(words) < 7:
                continue
            grams = {tuple(words[i:i+4]) for i in range(len(words)-3)}
            score = 0.
            for ref in references:
                refgrams = {tuple(ref[i:i+4]) for i in range(max(0, len(ref)-3))}
                score = max(score, len(grams & refgrams)/len(grams), SequenceMatcher(None, words, ref, autojunk=False).ratio())
            if score > threshold:
                found.append((scene.id, score))
                break
    return found


def apply_defaults(plan, profile):
    """Called once on new generation; later manual changes stay authoritative."""
    if profile is None:
        return plan
    from schemas.style import StyleRenderDefaults
    plan.style_preset = profile.slug
    plan.style_profile = profile.model_copy(deep=True)
    plan.render_style = StyleRenderDefaults(captions=profile.captions.model_copy(deep=True), ducking=profile.audio.ducking,
        theme=profile.visual_theme,visual_templates=profile.visual_templates,progress_tracker=profile.progress_tracker,progress_labels=profile.progress_labels)
    plan.music.mood = profile.audio.mood or "calm"
    plan.music.volume = profile.audio.music_volume
    allowed_fx = [v for v in profile.visual_effects if v in {"none", "zoom_in", "zoom_out", "pan_left", "pan_right"}] or ["none"]
    transitions = [v for v in profile.transitions if v in {"cut", "fade", "zoom", "whip"}] or ["cut"]
    sfx = [v for v in profile.audio.sfx_types if v in {"whoosh", "pop"}]
    elapsed, last_sfx = 0., -100.
    interval = 10/profile.audio.sfx_per_10_sec if profile.audio.sfx_per_10_sec else float("inf")
    for index, scene in enumerate(plan.scenes):
        scene.transition_out = transitions[index % len(transitions)]
        pattern=None
        if profile.scene_patterns:
            midpoint=(elapsed+scene.duration_sec/2)/plan.duration_sec
            cumulative=0.
            for candidate in profile.scene_patterns:
                cumulative+=candidate.fraction
                if midpoint<=cumulative+1e-8:
                    pattern=candidate
                    break
            if pattern:
                value=pattern.transition.casefold()
                scene.transition_out=next((v for words,v in [(("fade","mờ"),"fade"),(("whip","whoosh"),"whip"),(("zoom",),"zoom")] if any(w in value for w in words)),"cut")
        scene.sfx = sfx[index % len(sfx)] if sfx and elapsed-last_sfx >= interval else "none"
        if scene.sfx != "none":
            last_sfx = elapsed
        for shot_index, shot in enumerate(scene.shots):
            shot.effect = allowed_fx[(index + shot_index) % len(allowed_fx)]
            if pattern and pattern.effects:
                value=pattern.effects[shot_index%len(pattern.effects)].casefold()
                shot.effect=next((v for words,v in [(("pan_left","pan left","trái"),"pan_left"),(("pan_right","pan right","phải"),"pan_right"),(("zoom_out","zoom out","thu nhỏ"),"zoom_out"),(("zoom",),"zoom_in")] if any(w in value for w in words)),shot.effect)
        elapsed += scene.duration_sec
    return plan


def main():
    configure_console()
    parser = argparse.ArgumentParser(description="Tổng hợp phân tích video thành preset local")
    parser.add_argument("--name")
    parser.add_argument("--videos", nargs="+")
    parser.add_argument("--category")
    parser.add_argument("--rebuild",action="store_true")
    parser.add_argument("--type",choices=["news","review","story"])
    args = parser.parse_args()
    settings = None
    try:
        settings = get_settings()
        if args.category:
            from pipeline.category_style import rebuild_category,profile_file
            profile=rebuild_category(settings,args.category,force=args.rebuild,video_type=args.type)
            print(f"Đã tổng hợp {profile.video_count} video · {profile.confidence_label}: {profile_file(settings,args.category,args.type)}")
            for warning in profile.warnings:
                print("Cảnh báo: "+warning)
            return 0
        if not args.name or not args.videos:
            parser.error("Cần --category --rebuild hoặc --name và --videos.")
        path = save_profile(settings, build_profile(settings, args.name, args.videos))
        print(f"Đã lưu preset: {path}")
        return 0
    except Exception as error:
        from pipeline.style_learner import style_diagnostics
        if settings is None:
            print("Không nạp được cấu hình. Kiểm tra theo .env.example; không in cấu hình bí mật.")
            return 1
        diagnostics = style_diagnostics(settings)
        diagnostics.record_exception(error, "Tổng hợp preset")
        print(diagnostics.redact(str(error)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
