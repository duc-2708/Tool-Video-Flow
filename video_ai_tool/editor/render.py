"""Stage 5: local MoviePy 2 editor. Inputs are immutable; all products go in render/."""
from utils.atomic_io import discard_temp_file, replace_file_retry, write_text_atomic
import argparse
from collections import OrderedDict
from pathlib import Path
import json
import os
import re
import subprocess
import time
import uuid

import numpy as np
from PIL import Image,ImageFilter,ImageEnhance
from proglog import ProgressBarLogger

from config.settings import get_settings
from editor.timeline import build_timeline, confined
from editor.effects import cover, color_card, transition
from editor.captions import Captions, find_font
from editor.audio_mix import build_audio
from editor.runtime import VideoClip, VideoFileClip
from editor.templates.core import Card
from editor.templates.theme import load_theme
from editor.graphics import prepare_graphics,ProgressTracker
from utils.cache import write_json
from utils.console import configure_console
from utils.diagnostics import Diagnostics
from utils.file_lock import file_lock
from utils.text import slugify


class RenderProgress(ProgressBarLogger):
    def __init__(self, notify):
        super().__init__()
        self.notify,self.last = notify,0.

    def bars_callback(self,bar,attr,value,old_value=None):
        if attr != "index":
            return
        total = self.bars[bar].get("total",1) or 1
        now = time.monotonic()
        if now-self.last > .3 or value >= total:
            fraction = min(1.,value/total)
            self.notify((.18+.78*fraction) if bar == "frame_index" else (.08+.10*fraction),
                        "Đang dựng hình" if bar == "frame_index" else "Đang ghép âm thanh")
            self.last = now


class Frames:
    """At most two decoders/cards resident, including during scene transitions."""
    def __init__(self,timeline,size,font,diagnostics,theme=None):
        self.timeline,self.size,self.font,self.diagnostics = timeline,size,font,diagnostics
        self.cache = OrderedDict()
        self.theme=theme or load_theme()
        self.cards=OrderedDict()
        self.failed_cards=set()
        self.motion_paths={}
        self.motion_readers=OrderedDict()

    def close(self):
        for reader in self.motion_readers.values(): reader.close()
        self.motion_readers.clear()
        for source in self.cache.values():
            if isinstance(source,VideoFileClip):
                source.close()
        self.cache.clear()
        self.cards.clear()

    def frame(self,shot,t):
        if shot.scene_id in self.motion_paths:
            if shot.scene_id not in self.motion_readers:
                if len(self.motion_readers)>=2:
                    _,old=self.motion_readers.popitem(last=False);old.close()
                self.motion_readers[shot.scene_id]=VideoFileClip(str(self.motion_paths[shot.scene_id]),audio=False)
            self.motion_readers.move_to_end(shot.scene_id)
            reader=self.motion_readers[shot.scene_id]
            scene=next(s for s in self.timeline.scenes if s.spec.id==shot.scene_id)
            return reader.get_frame(min(max(0,t-scene.start),max(0,reader.duration-1/reader.fps)))
        key = (shot.scene_id,shot.shot_id)
        visual=shot.spec.visual
        if visual and visual.template!="stock" and (not self.timeline.plan.render_style or self.timeline.plan.render_style.visual_templates):
            # Graphics use the theme by default. Never decode unverified/irrelevant
            # stock (including faces/entertainment) behind factual cards.
            if key in self.failed_cards:
                return color_card(self.size,shot.spec.card_text or "Ý chính cần nhớ",self.font,shot.scene_id)
            try: return self.graphic_frame(shot,key,visual,None,max(0.,t-shot.start))
            except Exception as error:
                self.diagnostics.record_exception(error,f"Đồ họa cảnh {shot.scene_id}, shot {shot.shot_id}; nền dự phòng")
                self.failed_cards.add(key)
                self.timeline.warnings.append(f"Cảnh {shot.scene_id}, shot {shot.shot_id}: mẫu đồ họa không dựng được, dùng nền màu trung tính.")
                return color_card(self.size,shot.spec.card_text or "Ý chính cần nhớ",self.font,shot.scene_id)
        text = shot.spec.text_overlay or next(s.spec.narration for s in self.timeline.scenes if s.spec.id == shot.scene_id)
        if key not in self.cache:
            while len(self.cache) >= 2:
                _,old = self.cache.popitem(last=False)
                if isinstance(old,VideoFileClip):
                    old.close()
            try:
                if shot.fallback:
                    source = color_card(self.size,text,self.font,shot.scene_id)
                elif shot.path.suffix.lower() in {".mp4",".mov",".webm",".mkv"}:
                    source = VideoFileClip(str(shot.path),audio=False)
                    if not source.duration or source.duration <= 0:
                        source.close()
                        raise ValueError("Clip nguồn không có thời lượng hợp lệ.")
                else:
                    with Image.open(shot.path) as image:
                        source = np.asarray(image.convert("RGB"))
                self.cache[key] = source
            except Exception as error:
                self.diagnostics.record_exception(error,f"Đọc clip cảnh {shot.scene_id}, shot {shot.shot_id}; chuyển nền màu")
                warning = f"Cảnh {shot.scene_id}, shot {shot.shot_id}: clip hỏng, dùng nền màu."
                if warning not in self.timeline.warnings:
                    self.timeline.warnings.append(warning)
                self.cache[key] = color_card(self.size,text,self.font,shot.scene_id)
        self.cache.move_to_end(key)
        source = self.cache[key]
        local = max(0.,min(t-shot.start,shot.duration))
        if isinstance(source,VideoFileClip):
            # Slight shortage: smooth slowdown. Larger shortage: deterministic loop.
            sample = local*source.duration/shot.duration if source.duration < shot.duration <= source.duration*1.25 else local % source.duration
            frame = source.get_frame(min(sample,max(0.,source.duration-1/source.fps)))
        else:
            frame = source
        visual=shot.spec.visual
        if visual and visual.template!="stock" and (not self.timeline.plan.render_style or self.timeline.plan.render_style.visual_templates):
            if key in self.failed_cards:
                return color_card(self.size,"Tìm hiểu diễn biến và tác động",self.font,shot.scene_id)
            try:
                return self.graphic_frame(shot,key,visual,frame,local)
            except Exception as error:
                self.diagnostics.record_exception(error,f"Mẫu đồ họa cảnh {shot.scene_id}, shot {shot.shot_id}; chuyển nền an toàn")
                warning=f"Cảnh {shot.scene_id}, shot {shot.shot_id}: mẫu đồ họa không dựng được, dùng nền màu trung tính."
                if warning not in self.timeline.warnings: self.timeline.warnings.append(warning)
                self.failed_cards.add(key)
                return color_card(self.size,"Tìm hiểu diễn biến và tác động",self.font,shot.scene_id)
        return cover(frame,self.size,shot.spec.effect,local/shot.duration)

    def graphic_frame(self,shot,key,visual,frame,local):
        if key not in self.cards:
            if len(self.cards)>=2: self.cards.popitem(last=False)
            from editor.templates.core import NAMES
            self.cards[key]=Card(visual.template if visual.template in NAMES else "text_focus",visual.data,shot.duration,self.size,self.theme)
        card=self.cards[key]
        if shot.fallback or frame is None:
            return card.frame(local)
        # Stock is a supporting, darkened moving background, never foreground.
        base=cover(frame,self.size,"zoom_in",local/shot.duration)
        base=ImageEnhance.Brightness(Image.fromarray(base).filter(ImageFilter.GaussianBlur(max(1,self.size[0]/180)))).enhance(.32).convert("RGBA")
        return np.asarray(Image.alpha_composite(base,card.frame(local,transparent=True)).convert("RGB"))

    def at(self,t):
        scene_index = next((i for i,s in enumerate(self.timeline.scenes) if t < s.start+s.duration),len(self.timeline.scenes)-1)
        scene = self.timeline.scenes[scene_index]
        shot = next((s for s in scene.shots if t < s.start+s.duration),scene.shots[-1])
        frame = self.frame(shot,t)
        remaining = scene.start+scene.duration-t
        if scene_index+1 < len(self.timeline.scenes) and remaining < .22 and scene.spec.transition_out != "cut":
            following = self.timeline.scenes[scene_index+1].shots[0]
            # Transition consumes the outgoing tail, never overlaps narration or shortens scenes.
            next_frame = self.frame(following,following.start)
            frame = transition(frame,next_frame,1-remaining/.22,scene.spec.transition_out)
        return frame


def run_render(plan_path,*,mode="preview",settings=None,progress=None,diagnostics=None,scene_id=None,force_scene=None):
    if mode not in {"preview","final"}:
        raise ValueError("Chế độ phải là preview hoặc final.")
    settings = settings or get_settings()
    # Draft FPS is independent of the 30fps final export contract.
    if mode=='final' and settings.motion_enabled:
        settings=settings.model_copy(update={'motion_fps':30})
    diagnostics = diagnostics or Diagnostics(settings.logs_dir,filename="render_errors.log")
    notify = progress or (lambda value,message: None)
    resources,frames,video = [],None,None
    started = time.perf_counter()
    temporary = None
    try:
        notify(.01,"Đang kiểm tra audio và timeline")
        timeline = build_timeline(Path(plan_path))
        if settings.motion_enabled:
            from editor.motion.source import ensure_source_slot
            ensure_source_slot(timeline)
        # Tự động chạy Visual Planner v3 nếu timeline thiếu visual_plan (kể cả tạo theo danh mục hoặc dùng lại assets)
        if settings.motion_enabled and getattr(settings, 'motion_recipes_enabled', True):
            has_vp = any(getattr(sc, 'visual_plan', None) is not None for sc in timeline.plan.scenes)
            has_brief = (timeline.project / "brief.json").is_file()
            if not has_vp and has_brief:
                try:
                    from agents.visual_planner_v3 import create_visual_plan_v3
                    from utils.word_timing import read_words
                    from schemas.research_brief import ResearchBrief
                    from utils.atomic_io import read_json_atomic
                    brief_file = timeline.project / "brief.json"
                    brief_obj = ResearchBrief.model_validate(read_json_atomic(brief_file)) if brief_file.is_file() else None
                    words_map = {}
                    for sc in timeline.plan.scenes:
                        words_file = timeline.project / "audio" / f"scene_{sc.id}.words.json"
                        if words_file.is_file():
                            words_map[sc.id] = read_words(words_file)
                    new_plan = create_visual_plan_v3(
                        timeline.plan,
                        words_by_scene=words_map,
                        brief=brief_obj,
                        settings=settings,
                        diagnostics=diagnostics,
                        state_path=timeline.project / "render" / "director_state.visual_v3.json",
                    )
                    timeline.plan = new_plan
                    for sc, p_sc in zip(timeline.scenes, new_plan.scenes):
                        sc.spec.visual_plan = p_sc.visual_plan
                        for sh, p_sh in zip(sc.shots, p_sc.shots):
                            sh.spec.visual_plan = getattr(p_sh, 'visual_plan', None)
                            sh.visual_plan = getattr(p_sh, 'visual_plan', None)
                except Exception as vp_err:
                    diagnostics.record_exception(vp_err, "Tự bổ sung visual_plan v3 khi render lỗi")

            # Motion Kit v2 / Slide Script Resolution
            is_slide_motion = (
                (settings.motion_theme in ("auto", "light_glass", "kit", "motion_kit_v2"))
                or getattr(settings, "motion_enabled", False)
                or (getattr(getattr(timeline.plan, "render_style", None), "theme", None) in ("light_glass", "kit", "motion_kit_v2"))
                or (getattr(getattr(timeline.plan, "style_profile", None), "category_id", None) == "cong-nghe")
                or (timeline.project / "slide_script.json").is_file()
            )
            slide_script_file = timeline.project / "slide_script.json"
            if is_slide_motion:
                try:
                    import json
                    from schemas.slide_script import SlideScript
                    from schemas.motion_scene import MotionScenePlan
                    from schemas.visual import VisualBeat, VisualData, Visual
                    from schemas.edit_plan import Scene, Shot
                    from editor.timeline import TimelineScene, TimelineShot
                    from imageio_ffmpeg import get_ffmpeg_exe
                    from utils.word_timing import read_words

                    slide_script_obj = None
                    if slide_script_file.is_file():
                        try:
                            cand = SlideScript.model_validate_json(slide_script_file.read_text(encoding="utf-8"))
                            if cand and cand.slides:
                                all_valid_durations = all(
                                    3.0 <= (s.duration if s.duration > 0 else (s.t_end - s.t_start)) <= 7.0
                                    for s in cand.slides
                                )
                                if all_valid_durations and len(cand.slides) >= max(4, round(timeline.duration / 6.5)):
                                    slide_script_obj = cand
                        except Exception as e:
                            diagnostics.record_exception(e, "Lỗi đọc slide_script.json")

                    if not slide_script_obj or not slide_script_obj.slides:
                        from editor.motion.light_glass_slots import create_heuristic_slide_script
                        from editor.motion.slide_grounding import verify_and_ground_slides

                        sentences = []
                        cur_t = 0.0
                        for sc in timeline.scenes:
                            w_file = timeline.project / "audio" / f"scene_{sc.spec.id}.words.json"
                            sc_words = read_words(w_file) if w_file.is_file() else []
                            if sc.spec.sentences and len(sc.spec.sentences) > 1:
                                w_idx = 0
                                sent_starts = []
                                for s_idx, sent in enumerate(sc.spec.sentences):
                                    s_words = sent.text.split()
                                    w_start = sc_words[w_idx]["start"] if w_idx < len(sc_words) else 0.0
                                    sent_starts.append(w_start)
                                    w_idx = min(len(sc_words), w_idx + len(s_words))

                                for s_idx, sent in enumerate(sc.spec.sentences):
                                    w_start = 0.0 if s_idx == 0 else sent_starts[s_idx]
                                    w_end = sc.duration if s_idx == len(sc.spec.sentences) - 1 else sent_starts[s_idx + 1]
                                    sentences.append({
                                        "id": len(sentences) + 1,
                                        "scene_id": sc.spec.id,
                                        "text": sent.text,
                                        "start": cur_t + w_start,
                                        "end": cur_t + w_end,
                                        "duration": max(0.1, w_end - w_start),
                                    })
                            else:
                                sentences.append({
                                    "id": len(sentences) + 1,
                                    "scene_id": sc.spec.id,
                                    "text": sc.spec.narration,
                                    "start": cur_t,
                                    "end": cur_t + sc.duration,
                                    "duration": sc.duration,
                                })
                            cur_t += sc.duration

                        brief_data = {}
                        if (timeline.project / "brief.json").is_file():
                            try:
                                brief_data = json.loads((timeline.project / "brief.json").read_text(encoding="utf-8"))
                            except Exception:
                                pass

                        slide_script_obj = create_heuristic_slide_script(
                            sentences=sentences,
                            brief=brief_data,
                            total_duration=timeline.duration,
                            brand_name=getattr(settings, "brand_name", ""),
                        )
                        slide_script_obj = verify_and_ground_slides(slide_script_obj, {s["id"]: s for s in sentences}, brief_data)
                        try:
                            slide_script_file.write_text(slide_script_obj.model_dump_json(indent=2), encoding="utf-8")
                        except Exception:
                            pass

                    if slide_script_obj and slide_script_obj.slides:
                        try:
                            from pipeline.slide_image_resolver import resolve_images_for_slide_script
                            resolve_images_for_slide_script(timeline.project, slide_script_obj)
                        except Exception as res_err:
                            diagnostics.record_exception(res_err, "Lỗi resolve images cho slide_script")

                        settings = settings.model_copy(update={"motion_enabled": True, "motion_theme": "light_glass"})
                        if timeline.plan.render_style:
                            timeline.plan.render_style.theme = "light_glass"

                        from editor.timeline import TimelineScene, TimelineShot
                        from schemas.motion_scene import MotionScenePlan
                        from schemas.visual import VisualBeat, VisualData, Visual
                        from schemas.edit_plan import Scene, Shot
                        from imageio_ffmpeg import get_ffmpeg_exe
                        from utils.word_timing import read_words

                        # Gather all words from all original scenes with global timestamps
                        all_global_words = []
                        for sc in timeline.scenes:
                            w_file = timeline.project / "audio" / f"scene_{sc.spec.id}.words.json"
                            sc_words = read_words(w_file) if w_file.is_file() else []
                            for w in sc_words:
                                all_global_words.append({
                                    "text": w["text"],
                                    "start": round(sc.start + float(w["start"]), 3),
                                    "end": round(sc.start + float(w["end"]), 3),
                                })

                        slide_audio_dir = timeline.project / "render" / "slide_audio"
                        slide_audio_dir.mkdir(parents=True, exist_ok=True)
                        master_audio_path = slide_audio_dir / "master_narration.wav"
                        ffmpeg_bin = get_ffmpeg_exe()
                        concat_txt = slide_audio_dir / "concat_scenes.txt"
                        concat_lines = ["ffconcat version 1.0"]
                        for sc in timeline.scenes:
                            p_clean = str(sc.audio.resolve()).replace("\\", "/").replace("'", "'\\''")
                            concat_lines.extend([f"file '{p_clean}'", f"duration {sc.duration:.9f}"])
                        concat_txt.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
                        try:
                            subprocess.run(
                                [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-ac", "2", "-ar", "44100", str(master_audio_path)],
                                check=True, capture_output=True, timeout=120
                            )
                        except Exception as cat_err:
                            diagnostics.record_exception(cat_err, "Concat audio for slides")

                        new_timeline_scenes = []
                        valid_vkeys = set(VisualData.model_fields.keys())
                        cur_clock = 0.0

                        for k, slide in enumerate(slide_script_obj.slides):
                            s_audio_path = slide_audio_dir / f"slide_{k+1}.mp3"
                            s_words_path = slide_audio_dir / f"slide_{k+1}.words.json"

                            if master_audio_path.is_file():
                                try:
                                    subprocess.run(
                                        [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{slide.t_start:.3f}", "-t", f"{slide.duration:.3f}", "-i", str(master_audio_path), "-c:a", "libmp3lame", "-q:a", "2", str(s_audio_path)],
                                        check=True, capture_output=True, timeout=60
                                    )
                                except Exception as slice_err:
                                    diagnostics.record_exception(slice_err, f"Slice audio slide {k+1}")
                            if not s_audio_path.is_file():
                                s_audio_path = timeline.scenes[min(k, len(timeline.scenes)-1)].audio

                            # Filter and offset words for this slide
                            slide_words = []
                            for w in all_global_words:
                                if slide.t_start - 0.05 <= w["start"] < slide.t_end:
                                    slide_words.append({
                                        "text": w["text"],
                                        "start": max(0.0, round(w["start"] - slide.t_start, 3)),
                                        "end": min(slide.duration, round(w["end"] - slide.t_start, 3)),
                                    })
                            if not slide_words:
                                narr_tokens = slide.narration.split()
                                dur_per_token = slide.duration / max(1, len(narr_tokens))
                                for t_i, tok in enumerate(narr_tokens):
                                    slide_words.append({
                                        "text": tok,
                                        "start": round(t_i * dur_per_token, 3),
                                        "end": round((t_i + 1) * dur_per_token, 3),
                                    })
                            s_words_path.write_text(json.dumps(slide_words, ensure_ascii=False, indent=2), encoding="utf-8")

                            clean_slots = slide.slots.copy()
                            if "winner" in clean_slots and clean_slots["winner"] is not None:
                                clean_slots["winner"] = str(clean_slots["winner"])
                            if "value" in clean_slots and clean_slots["value"] is not None:
                                try:
                                    clean_slots["value"] = float(str(clean_slots["value"]).replace(",", "").replace("%", "").strip())
                                except Exception:
                                    pass

                            shot_data = VisualData(**{key: v for key, v in clean_slots.items() if key in valid_vkeys and v is not None})
                            beats = [
                                VisualBeat(at_sec=0.35, action=f"enter_{slide.layout}"),
                                VisualBeat(at_sec=1.5, action=f"action_{slide.layout}_step"),
                            ]
                            vp_obj = MotionScenePlan(
                                scene_type=slide.layout,
                                layout=slide.layout,
                                theme="light_glass",
                                data=shot_data,
                                beats=beats,
                                transition="morph_anchor",
                            )
                            new_vis = Visual(template=slide.layout, data=shot_data, beats=beats)
                            sh_spec = Shot(
                                type="text_card",
                                query=slide.layout or "motion slide",
                                effect="none",
                                text_overlay=None,
                                planning_duration=True,
                                duration_sec=slide.duration,
                                card_text=slide.narration,
                                visual=new_vis,
                                visual_plan=vp_obj,
                            )
                            tl_shot = TimelineShot(
                                scene_id=k + 1,
                                shot_id=1,
                                start=cur_clock,
                                duration=slide.duration,
                                spec=sh_spec,
                                path=None,
                                fallback=False,
                            )
                            role = "hook" if k == 0 else "cta" if k == len(slide_script_obj.slides) - 1 else "body"
                            sc_spec = Scene(
                                id=k + 1,
                                role=role,
                                narration=slide.narration,
                                visual_plan=vp_obj,
                                transition_out="fade",
                                sfx="none",
                                shots=[sh_spec],
                            )
                            tl_scene = TimelineScene(
                                spec=sc_spec,
                                start=cur_clock,
                                duration=slide.duration,
                                audio=s_audio_path,
                                shots=[tl_shot],
                            )
                            cur_clock += slide.duration
                            new_timeline_scenes.append(tl_scene)

                        timeline.scenes = new_timeline_scenes
                        timeline.plan.scenes = [s.spec for s in new_timeline_scenes]
                        timeline.duration = cur_clock
                except Exception as lg_err:
                    diagnostics.record_exception(lg_err, "Lỗi kích hoạt SlideScript Light Glass khi render")

            pass
        prepare_graphics(timeline,diagnostics)
        timeline.illustrations_requested=bool(settings.motion_enabled and settings.motion_scenes_enabled)
        if scene_id is not None:
            selected=next((s for s in timeline.scenes if s.spec.id==scene_id),None)
            if selected is None: raise ValueError(f"Không có cảnh {scene_id} trong project.")
            origin=selected.start
            for shot in selected.shots: shot.start-=origin
            selected.start=0.;timeline.scenes=[selected];timeline.duration=selected.duration
        suffix=f"_scene_{scene_id}" if scene_id is not None else ""
        render_dir = confined(timeline.project,"render")
        render_dir.mkdir(exist_ok=True)
        # Avoid simultaneous CLI/UI writers for this project; inputs never locked/modified.
        with file_lock(render_dir/"editor.lock"):
            portrait = timeline.plan.format == "tiktok"
            full=(settings.render_width,settings.render_height) if portrait else (settings.render_height,settings.render_width)
            scale=settings.motion_scale if settings.motion_enabled and mode=="preview" else .5 if mode=="preview" else 1.
            size=tuple(max(2,round(n*scale/2)*2) for n in full)
            if settings.motion_enabled:
                estimate=max(3,timeline.duration*settings.motion_fps/(14 if scale<=.5 else 8))*2/max(1,settings.motion_workers)
                notify(.02,f'Ước tính render khoảng {estimate*.7:.0f}–{estimate*1.7:.0f} giây; phụ thuộc cảnh/cache và tải máy.')
            font = find_font(settings.root_dir)
            theme=load_theme(timeline.plan.render_style.theme,settings.root_dir)
            captions = Captions(timeline,size,font)
            frames = Frames(timeline,size,font,diagnostics,theme)
            motion_results=[]
            if settings.motion_enabled and (getattr(timeline.plan.render_style, 'visual_templates', True) is not False):
                from pipeline.motion_batch import render_batch
                motion_results=render_batch(timeline,render_dir/"motion_cache",size,font,settings,diagnostics,notify,force_scene=force_scene)
                frames.motion_paths={r["scene_id"]:r["path"] for r in motion_results}
                write_json(render_dir/("motion_plan"+suffix+".json"),timeline.plan.model_dump(mode="json"))
                from editor.motion.sfx import ensure_sfx
                ensure_sfx(settings.root_dir/"assets/sfx")
            tracker=ProgressTracker(timeline,size,theme)
            notify(.68 if settings.motion_enabled else .05,"Đang chuẩn hóa giọng đọc và trộn nhạc")
            audio,music = build_audio(timeline,settings.root_dir/"assets",resources,motion=settings.motion_enabled)
            resources.append(audio)
            fps=15 if mode=="preview" else 30
            if settings.motion_enabled: fps=settings.motion_fps
            def composite(t):
                scene=next((s for s in timeline.scenes if t<s.start+s.duration),timeline.scenes[-1])
                frame=frames.at(t)
                if scene.spec.id not in frames.motion_paths:
                    frame=captions.apply(frame,t)
                    return tracker.apply(frame,t)
                return frame  # HTML already includes its own caption/progress layers.
            filename = f"{slugify(timeline.plan.title)}_{timeline.plan.format}{suffix}_{mode}.mp4"
            destination = confined(render_dir,filename)
            temporary = confined(render_dir,f".{uuid.uuid4().hex}.mp4")
            temp_audio = confined(render_dir,f".{uuid.uuid4().hex}.m4a")
            try:
                fast_motion=bool(motion_results and len(motion_results)==len(timeline.scenes))
                if fast_motion:
                    from editor.motion.finish import mux_scenes
                    mux_scenes(motion_results,timeline,audio,temporary,render_dir,fps,mode,notify)
                else:
                    video = VideoClip(composite,duration=timeline.duration).with_audio(audio).with_fps(fps)
                    video.write_videofile(str(temporary),fps=fps,codec="libx264",audio_codec="aac",
                        audio_bitrate="192k",preset="ultrafast" if mode == "preview" else "medium",
                        threads=min(8,os.cpu_count() or 2),temp_audiofile=str(temp_audio),
                        ffmpeg_params=["-crf","27" if mode == "preview" else "20","-movflags","+faststart"],
                        pixel_format="yuv420p",logger=RenderProgress((lambda value,message:notify(.65+.35*value,message)) if settings.motion_enabled else notify))
                replace_file_retry(temporary, destination)
            finally:
                discard_temp_file(temp_audio)
            original_credits = confined(timeline.project,"credits.txt")
            credits = original_credits.read_text(encoding="utf-8") if original_credits.is_file() else "Chưa có credits.txt của Assets.\n"
            credits += f"\n--- Render ---\nFont: {font.name}\nNhạc nền: {music.name if music else 'Không sử dụng'}\n"
            if settings.motion_enabled: credits+='Lucide icons: ISC/MIT notices in assets/icons/LICENSE. anime.js 3.2.2: MIT, assets/vendor/anime/LICENSE. Original geometric scenes/mascot: CC0, assets/illustrations/LICENSE and assets/mascot/LICENSE.\n'
            ai_scenes = [r.get('scene_id') for r in motion_results if r.get('ai_background_count', 0) > 0 or r.get('scene_mode') in ('hybrid', 'ai_clip')]
            ai_used = len(ai_scenes)
            if ai_used: credits+='\nNội dung có hỗ trợ AI — hình mô phỏng tạo bằng AI/nhập tay, không phải hình ảnh chứng cứ của sự kiện.\n'
            write_text_atomic(confined(render_dir,"credits.txt"), credits)
            result = {"path":str(destination),"filename":filename,"mode":mode,"duration_sec":timeline.duration,
                "width":size[0],"height":size[1],"fps":fps,"size_bytes":destination.stat().st_size,
                "render_seconds":round(time.perf_counter()-started,3),"warnings":timeline.warnings,
                "caption_timing":"Word sidecar nếu hợp lệ; còn lại ước lượng theo số ký tự"}
            result.update(ai_backgrounds_used=ai_used,ai_disclosure='nội dung có hỗ trợ AI' if ai_used else '',ai_scenes=ai_scenes,description='nội dung có hỗ trợ AI' if ai_used else '')
            if settings.motion_enabled:
                from editor.motion.finish import save_review
                quality=save_review(timeline,motion_results,destination,scene_id=scene_id)
                result.update(motion_enabled=True,motion_scenes=motion_results,motion_scale=scale,motion_workers=settings.motion_workers,
                    illustrations_requested=timeline.illustrations_requested,
                    mascot_enabled=settings.mascot_enabled,motion_theme=settings.motion_theme,fast_motion_mux=fast_motion,
                    contact_sheet=quality["contact_sheet"],review_notes=quality["review_notes"],warnings=timeline.warnings)
            if scene_id is not None: result["scene_id"]=scene_id
            try:
                from editor.quality import save_quality
                qc=save_quality(timeline,motion_results,destination,scene_id=scene_id)
                result.update(quality_report=str(timeline.project/("quality_report"+suffix+".json")),quality_summary={k:qc[k] for k in ('template_types','template_counts','warning_count','deferred_dom_samples','illustration_coverage_percent','scene_type_count')},contact_sheet=qc['contact_sheet'])
                for key in ('repeated_cards','still_intervals_over_3_5_sec','empty_cards_over_40_percent','text_overflow','numbers_not_in_narration','caption_gaps_over_0_6_sec'):
                    if qc[key]: timeline.warnings.append(f'[visual_quality, nhóm 3] {key}: {len(qc[key])}; xem quality_report{suffix}.json.')
            except Exception as error:
                diagnostics.record_exception(error,'QC nhóm 3 sau Render; giữ MP4 đã dựng')
                timeline.warnings.append('QC nhóm 3 chưa hoàn tất; MP4 vẫn có, xem render_errors.log.')
            result['total_seconds']=round(time.perf_counter()-started,3)
            write_json(confined(render_dir,f"{mode}{suffix}.json"),result)
            reviews=getattr(timeline,"visual_review",[])
            write_json(confined(render_dir,"visual_review.json"),{"shots":reviews,"warnings":timeline.warnings})
            write_text_atomic(confined(render_dir,"report.md"),"# Kiểm tra đồ họa khi Render\n\n"+
                "\n".join(f"- {message}" for message in timeline.warnings)+"\n\n## Motion review_notes\n\n"+
                "\n".join("- "+n for n in result.get("review_notes",[]))+"\n\nĐầu vào Edit Plan, audio, clips và credits được giữ nguyên.\n")
            notify(1.,"Render hoàn tất")
            return result
    except Exception as error:
        diagnostics.record_exception(error,"Editor render thất bại")
        if isinstance(error,subprocess.CalledProcessError) and error.stderr:
            diagnostics.record("FFmpeg stderr:\n"+error.stderr.decode("utf-8",errors="replace"))
        raise
    finally:
        if video:
            video.close()
        if frames:
            frames.close()
        for resource in reversed(resources):
            resource.close()
        if temporary:
            discard_temp_file(temporary)


def main():
    configure_console()
    parser = argparse.ArgumentParser(description="Dựng video local từ resolved plan; không thay đổi Assets.")
    parser.add_argument("plan",type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--mode",choices=["preview","final"],default="preview")
    modes.add_argument("--preview",action="store_true")
    modes.add_argument("--final",action="store_true")
    parser.add_argument("--debug",action="store_true")
    parser.add_argument("--scene",type=int)
    parser.add_argument("--force-scene",type=int)
    parser.add_argument("--motion",action="store_true")
    parser.add_argument('--no-scenes',action='store_true',help='Chỉ dùng thẻ Motion cũ, không dùng cảnh hoạt họa')
    parser.add_argument('--fps',type=int,choices=[24,30])
    parser.add_argument("--scale",type=float,choices=[.25,.5,1.])
    args = parser.parse_args()
    try:
        settings = get_settings()
        options={}
        if args.motion: options["motion_enabled"]=True
        if args.no_scenes: options['motion_scenes_enabled']=False
        if args.fps is not None: options['motion_fps']=args.fps
        if args.scale is not None: options["motion_scale"]=args.scale
        if options: settings=settings.model_copy(update=options)
    except Exception:
        print("Cấu hình không hợp lệ. Kiểm tra kiểu và khoảng giá trị theo .env.example; không in nội dung cấu hình.")
        raise SystemExit(1) from None
    diagnostics = Diagnostics(settings.logs_dir,debug=args.debug,filename="render_errors.log")
    last = [-1]
    def progress(value,message):
        percent = int(value*100)
        if percent >= last[0]+5 or percent == 100:
            print(f"{percent:3d}% · {message}",flush=True)
            last[0] = percent
    try:
        result = run_render(args.plan,mode="final" if args.final else args.mode,settings=settings,diagnostics=diagnostics,progress=progress,
            scene_id=args.scene,force_scene=args.force_scene)
        print(f"Đã lưu: {result['path']}\nThời lượng: {result['duration_sec']:.2f}s · {result['width']}x{result['height']} · Render: {result['render_seconds']:.1f}s")
        for warning in result["warnings"]:
            print(diagnostics.redact(warning))
    except Exception as error:
        print("Render thất bại: "+diagnostics.redact(str(error)))
        print("Xem lỗi gốc trong logs/render_errors.log; thêm --debug để xem traceback.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
