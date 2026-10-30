"""Stage 5: local MoviePy 2 editor. Inputs are immutable; all products go in render/."""
from utils.atomic_io import discard_temp_file, replace_file_retry, write_text_atomic
import argparse
from collections import OrderedDict
from pathlib import Path
import json
import os
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
            if not has_vp:
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
                        state_path=timeline.project / "director_state.visual_v3.json",
                    )
                    timeline.plan = new_plan
                    for sc, p_sc in zip(timeline.scenes, new_plan.scenes):
                        sc.spec.visual_plan = p_sc.visual_plan
                        for sh, p_sh in zip(sc.shots, p_sc.shots):
                            sh.spec.visual_plan = getattr(p_sh, 'visual_plan', None)
                            sh.visual_plan = getattr(p_sh, 'visual_plan', None)
                except Exception as vp_err:
                    diagnostics.record_exception(vp_err, "Tự bổ sung visual_plan v3 khi render lỗi")

            # Đảm bảo mọi shot trong timeline đều có visual_plan được lập lịch riêng
            any_shot_missing_vp = any(getattr(sh.spec, 'visual_plan', None) is None for sc in timeline.scenes for sh in sc.shots)
            if any_shot_missing_vp:
                try:
                    from editor.motion.scheduler import schedule_shots_no_repeat
                    from schemas.motion_scene import MotionScenePlan
                    from schemas.visual import VisualBeat, VisualData
                    all_tl_shots = []
                    tl_coords = []
                    for sc_idx, sc in enumerate(timeline.scenes):
                        for sh_idx, sh in enumerate(sc.shots):
                            sh_vp = getattr(sh.spec, "visual_plan", None) or getattr(sh, "visual_plan", None)
                            raw_r = sh_vp.scene_type if sh_vp else (sc.spec.visual_plan.scene_type if getattr(sc.spec, 'visual_plan', None) else "")
                            sh_text = sh.spec.card_text or (sh.spec.visual.data.text if sh.spec.visual and sh.spec.visual.data else "") or sc.spec.narration
                            all_tl_shots.append({
                                "recipe": raw_r,
                                "text": sh_text,
                                "narration": sc.spec.narration,
                                "duration": sh.duration,
                                "duration_sec": sh.duration,
                                "scene_id": sc.spec.id,
                                "shot_id": sh.shot_id
                            })
                            tl_coords.append((sc_idx, sh_idx))
                    if all_tl_shots:
                        target_dist = min(8, len(all_tl_shots)) if len(all_tl_shots) >= 8 else min(6, len(all_tl_shots))
                        scheduled_tl_shots, tl_notes = schedule_shots_no_repeat(
                            all_tl_shots,
                            min_distinct=target_dist,
                            min_dist=3,
                            max_freq=max(2, (len(all_tl_shots) // 6) + 1)
                        )
                        timeline.plan.review_notes.extend([n for n in tl_notes if n not in timeline.plan.review_notes])
                        theme_cur = timeline.plan.render_style.theme if timeline.plan.render_style else "neon_dark"
                        for sh_data, (sc_idx, sh_idx) in zip(scheduled_tl_shots, tl_coords):
                            target_sc = timeline.scenes[sc_idx]
                            target_sh = target_sc.shots[sh_idx]
                            chosen_r = sh_data["recipe"]
                            beats = [
                                VisualBeat(at_sec=b["at_sec"], action=b["action"]) if isinstance(b, dict) else b
                                for b in sh_data.get("beats", [])
                            ]
                            vp_obj = MotionScenePlan(
                                scene_type=chosen_r,
                                layout=target_sc.spec.visual_plan.layout if getattr(target_sc.spec, 'visual_plan', None) else "center_hero",
                                theme=theme_cur,
                                data=target_sc.spec.visual_plan.data if getattr(target_sc.spec, 'visual_plan', None) and target_sc.spec.visual_plan.data else VisualData(),
                                beats=beats,
                            )
                            target_sh.spec.visual_plan = vp_obj
                            target_sh.visual_plan = vp_obj
                except Exception as tl_sched_err:
                    diagnostics.record_exception(tl_sched_err, "Lập lịch recipe theo shot khi render lỗi")

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
            if settings.motion_enabled and timeline.plan.render_style.visual_templates:
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
