"""Bounded scene parallelism: each worker owns its Playwright/FFmpeg/decoders."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from threading import Lock
from agents.motion_beats import prepare_motion_beats
from editor.motion.theme import load_motion_theme,mascot_uris


def scene_options(timeline,scene,theme,mascots,configured=None):
    # Previewing one scene keeps its original place in the video; it must not
    # turn every body scene into an ending with a mascot/first progress marker.
    specs=timeline.plan.scenes
    index=next(i for i,s in enumerate(specs) if s.id==scene.spec.id)
    labels=timeline.plan.render_style.progress_labels or [s.style_purpose or ("Mở đầu" if i==0 else "Kết" if i==len(specs)-1 else f"Ý {i}") for i,s in enumerate(specs)]
    return {"theme":theme,"mascots":mascots,"mascot_enabled":bool(mascots and (scene.spec.role=="hook" or index==len(specs)-1)),
        "progress_enabled":timeline.plan.render_style.progress_tracker,"progress_labels":labels,"progress_index":min(5,index*min(6,len(specs))//max(1,len(specs))),
        "transition":configured or {"whip":"slide","zoom":"fade"}.get(scene.spec.transition_out,scene.spec.transition_out)}


def render_batch(timeline,folder,size,font,settings,diagnostics,notify,*,force_scene=None):
    from pipeline.render_motion import render_scene,SUPPORTED
    from editor.render import Frames
    from editor.captions import Captions
    from editor.templates.theme import load_theme
    prepare_motion_beats(timeline)
    theme=load_motion_theme(settings.root_dir,timeline.plan,settings.motion_theme)
    timeline.warnings.extend(theme["warnings"])
    scenes=[s for s in timeline.scenes if any(q.spec.visual and q.spec.visual.template in SUPPORTED for q in s.shots)]
    values={s.spec.id:0. for s in scenes};lock=Lock()
    profile=timeline.plan.style_profile
    transition_names=getattr(profile,"transitions",[])
    configured=next((s for s in transition_names if s in {"cut","fade","slide"}),None)
    mascots=mascot_uris(settings.root_dir) if settings.mascot_enabled else {}
    amplitude={}
    if settings.motion_scenes_enabled:
        if settings.mascot_enabled: mascots=mascot_uris(settings.root_dir,states=('idle','point','shrug','surprised','think','thinking'))
        from editor.motion.amplitude import envelope
        from utils.atomic_io import write_json_atomic
        for scene in timeline.scenes:
            try:
                amplitude[scene.spec.id]=envelope(scene.audio,timeline.project/'render/amplitude')
                write_json_atomic(timeline.project/f'render/amplitude/scene_{scene.spec.id}.amplitude.json',amplitude[scene.spec.id])
            except Exception as error:
                diagnostics.record_exception(error,f'Amplitude cảnh {scene.spec.id}: dùng miệng nghỉ')
        write_json_atomic(timeline.project/'render/amplitude.json',{str(k):v for k,v in amplitude.items()})
    allowed=set();brief=None
    try:
        from schemas.research_brief import ResearchBrief
        from agents.visual_diversity import values_in
        brief=ResearchBrief.model_validate_json((timeline.project/'brief.json').read_text(encoding='utf-8'))
        allowed=values_in(' '.join((f.fact_vi or f.claim)+' '+f.claim+' '+(f.evidence_quote or '') for f in brief.facts))
    except (OSError,ValueError): pass
    def task(scene):
        frames=Frames(timeline,size,font,diagnostics,load_theme(timeline.plan.render_style.theme,settings.root_dir))
        captions=Captions(timeline,size,font)
        def fallback(t):
            shot=next((s for s in scene.shots if scene.start+t<s.start+s.duration),scene.shots[-1])
            return captions.apply(frames.frame(shot,scene.start+t),scene.start+t)
        def progress(value,message):
            with lock:
                values[scene.spec.id]=value
                notify(.05+.60*sum(values.values())/max(1,len(values)),message)
        options=scene_options(timeline,scene,theme,mascots,configured)
        facts=[brief.facts[i-1] for i in scene.spec.fact_ids if 1<=i<=len(brief.facts)] if brief else []
        scene_allowed=values_in(' '.join((f.fact_vi or f.claim)+' '+f.claim+' '+(f.evidence_quote or '') for f in facts)) if facts else set()
        options.update(illustrations_enabled=settings.motion_scenes_enabled,min_card_hold_sec=settings.min_card_hold_sec,amplitude=amplitude.get(scene.spec.id,{}),allowed_numbers=sorted(scene_allowed),source_labels=list(dict.fromkeys(f.source_name for f in facts)))
        try:
            from pipeline.hybrid_render import prepare_scene_hybrid_payload
            hybrid_info = prepare_scene_hybrid_payload(
                scene_id=scene.spec.id,
                scene_duration=scene.duration,
                project_dir=timeline.project,
                settings=settings,
                diagnostics=diagnostics,
            )
            options['scene_mode'] = hybrid_info.get('mode', 'motion')
            options['ai_backgrounds'] = hybrid_info.get('ai_backgrounds', [])
            options['ai_simulation_badge'] = bool(hybrid_info.get('badge_label'))
            if hybrid_info.get('fallback_to_motion'):
                fb_recipe = hybrid_info.get('fallback_recipe')
                fb_reason = hybrid_info.get('reason', 'Clip AI không khả dụng; fallback hoạt họa motion')
                timeline.warnings.append(f"Cảnh {scene.spec.id}: {fb_reason}.")
                if getattr(scene.spec, 'visual_plan', None) and fb_recipe:
                    if getattr(scene.spec.visual_plan, 'scene_type', None) in ('text_focus', None):
                        scene.spec.visual_plan.scene_type = fb_recipe
            # Legacy fallback
            if not options['ai_backgrounds'] and getattr(settings, 'ai_clips_per_video', 0) and (timeline.project / 'render/ai_backgrounds.json').exists():
                from pipeline.controlled_ai import backgrounds_for_scene
                options['ai_backgrounds'] = backgrounds_for_scene(scene, timeline.project)
        except Exception as error:
            diagnostics.record_exception(error, f'Clip AI nền cảnh {scene.spec.id}; dùng gradient')
            timeline.warnings.append(f'Cảnh {scene.spec.id}: không đọc được clip AI nền, dùng gradient.')
            options['scene_mode'] = 'motion'
            options['ai_backgrounds'] = []
        try:
            result=render_scene(scene,folder,size=size,font=font,caption_style=captions.style.model_copy(update={"enabled":True}) if scene.audio_silent else captions.style,
                fps=settings.motion_fps,static_frame=fallback,progress=progress,diagnostics=diagnostics,
                extra_identity={"scene":scene.spec.model_dump(mode="json")},options=options,force=force_scene==scene.spec.id)
            if result:
                result['ai_background_count']=len(options.get('ai_backgrounds',[]))
                result['scene_mode']=options.get('scene_mode','motion')
                result['ai_clip_path']=(options.get('ai_backgrounds',[{}])[0].get('clip_path')) if options.get('ai_backgrounds') else None
            return result
        finally: frames.close()
    results={}
    with ThreadPoolExecutor(max_workers=min(settings.motion_workers,max(1,len(scenes))),thread_name_prefix="motion-scene") as pool:
        futures={pool.submit(task,s):s for s in scenes}
        for future in as_completed(futures):
            scene=futures[future]
            try: result=future.result()
            except Exception as error:
                diagnostics.record_exception(error,f"Motion cảnh {scene.spec.id}: dùng Pillow")
                result=None
            if result: results[scene.spec.id]=result
            else: timeline.warnings.append(f"Cảnh {scene.spec.id}: Motion không sẵn sàng; dùng đồ họa Pillow hiện có. Kiểm tra Playwright/Chromium và logs/render_errors.log.")
    return [results[s.spec.id] for s in scenes if s.spec.id in results]
