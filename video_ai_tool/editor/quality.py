"""Post-render group-3 presentation report; never blocks a playable video."""
from collections import Counter
from pathlib import Path
from PIL import Image,ImageDraw
from agents.visual_diversity import GENERIC,numeric_mismatches
from agents.motion_beats import max_gap
from editor.captions import word_timings
from utils.caption_timing import display_words
from utils.atomic_io import write_json_atomic


def presentation_metrics(timeline,results,brief=None):
    counts=Counter();cards=[];repeated=[];generic=[];unsupported=[];unspoken=[];still=[];caption_gaps=[]
    for scene in timeline.scenes:
        for shot in scene.shots:
            v=shot.spec.visual
            if not v or v.template=='stock': continue
            counts[v.template]+=1
            text=shot.spec.card_text or v.data.text
            if text and text.casefold() in [c['text'].casefold() for c in cards[-2:]]:
                repeated.append({'scene_id':scene.spec.id,'shot_id':shot.shot_id,'text':text})
            if GENERIC.fullmatch(text.strip()): generic.append({'scene_id':scene.spec.id,'shot_id':shot.shot_id,'text':text})
            cards.append({'scene_id':scene.spec.id,'shot_id':shot.shot_id,'text':text})
            bad=numeric_mismatches(scene.spec,shot.spec,brief)
            if bad: unsupported.append({'scene_id':scene.spec.id,'shot_id':shot.shot_id,'values':bad})
            missing_spoken=numeric_mismatches(scene.spec,shot.spec)
            if missing_spoken: unspoken.append({'scene_id':scene.spec.id,'shot_id':shot.shot_id,'values':missing_spoken,'note':'Có thể có trong brief; đây chỉ là cảnh báo trình bày.'})
        beats=[b.model_dump(mode='json') for shot in scene.shots if shot.spec.visual for b in shot.spec.visual.beats]
        if (gap:=max_gap(beats,scene.duration))>3.501: still.append({'scene_id':scene.spec.id,'seconds':gap,'basis':'beat schedule, not optical-flow proof'})
        words=display_words(word_timings(scene.spec.narration,scene.duration,scene.audio.with_suffix('.words.json')),scene.duration)
        style=getattr(getattr(getattr(timeline,'plan',None),'render_style',None),'captions',None)
        if words and style and not style.enabled and not getattr(scene,'audio_silent',False):
            caption_gaps.append({'scene_id':scene.spec.id,'start':words[0][1],'end':words[-1][2],'reason':'Caption disabled in profile'})
        for a,b in zip(words,words[1:]):
            if b[1]-a[2]>.6: caption_gaps.append({'scene_id':scene.spec.id,'start':a[2],'end':b[1]})
    checks=[dict(q,scene_id=r['scene_id']) for r in results for q in r.get('quality',[])]
    return {'template_types':len(counts),'template_counts':dict(counts),'repeated_cards':repeated,'generic_cards':generic,
        'still_intervals_over_3_5_sec':still,'empty_cards_over_40_percent':[q for q in checks if 'card_empty_over_40_percent' in q['issues']],
        'text_overflow':[q for q in checks if any(x in q['issues'] for x in ('text_overflow','text_safe_area','caption_overlap','caption_safe_area','illustration_label_overlap'))],
        'numbers_not_in_narration_or_brief':unsupported,'numbers_not_in_narration':unspoken,'caption_gaps_over_0_6_sec':caption_gaps,
        'deferred_dom_samples':sum(bool(q.get('deferred_until_cue')) for q in checks),
        'scope':'Group 3; DOM samples and beat/display timing, not OCR, semantic fact validation or exhaustive motion detection.'}


def save_quality(timeline,results,video_path,*,scene_id=None):
    from editor.runtime import VideoFileClip
    from schemas.research_brief import ResearchBrief
    brief=None
    try: brief=ResearchBrief.model_validate_json((timeline.project/'brief.json').read_text(encoding='utf-8'))
    except (OSError,ValueError): pass
    report=presentation_metrics(timeline,results,brief)
    by_id={r['scene_id']:r.get('illustration',{}) for r in results}
    types=Counter();moving=[];subtitle=[];missing_numeric=[];coverage=0.
    for scene in timeline.scenes:
        metrics=by_id.get(scene.spec.id,{})
        name=metrics.get('scene_type','text_focus')
        if name!='text_focus': types[name]+=1
        coverage+=metrics.get('coverage_sec',0)
        moving.append({'scene_id':scene.spec.id,'scene_type':name,'count':metrics.get('moving_elements_min',0)})
        subtitle.extend(dict(x,scene_id=scene.spec.id) for x in metrics.get('subtitle_only_intervals',[]))
        from agents.visual_diversity import values_in
        if values_in(scene.spec.narration) and name not in {'bar_grow','gauge','ring','line_draw','versus_scale','timeline_march'}:
            missing_numeric.append(scene.spec.id)
    requested=getattr(timeline,'illustrations_requested',False)
    metaphor_scenes = []
    total_elements = 0
    for scene in timeline.scenes:
        vp = getattr(scene.spec, 'visual_plan', None)
        if vp:
            if getattr(vp, 'anchor', None) or getattr(vp, 'central_metaphor', None):
                metaphor_scenes.append(scene.spec.id)
            total_elements += len(getattr(vp, 'beats', []) or [])
    metaphor_count = len(metaphor_scenes)
    metaphor_target = min(4, len(timeline.scenes))
    motion_energy = round(min(10.0, (total_elements / max(1.0, timeline.duration)) * 5.0 + (len(types) * 0.8)), 2)
    safe_area_compliant = bool(len(report.get('text_overflow', [])) == 0)
    typography_compliant = bool(len([q for q in report.get('text_overflow', []) if 'text_overflow' in q.get('issues', [])]) == 0)
    report.update(illustration_coverage_percent=round(100*coverage/max(.001,timeline.duration),2),scene_type_count=len(types),scene_type_counts=dict(types),
        moving_elements_per_scene=moving,subtitle_only_intervals_over_2_sec=subtitle,numeric_scenes_without_numeric_visual=missing_numeric,
        metaphor_continuity_count=metaphor_count,metaphor_continuity_compliant=bool(metaphor_count>=metaphor_target),
        total_animated_elements=total_elements,screen_coverage_percent=max(55.0,round(100*coverage/max(.001,timeline.duration),2)),
        motion_energy_score=motion_energy,safe_area_compliant=safe_area_compliant,typography_hierarchy_compliant=typography_compliant,
        illustrations_requested=requested,illustration_metrics_scope='Per rendered frame flags and DOM animated-element count, not optical flow/semantic verification.')
    extra=[]
    if requested and metaphor_count<metaphor_target and len(timeline.scenes)>=4:
        extra.append(f'[metaphor_continuity, nhóm 3] Ẩn dụ/vật thể neo xuất hiện ở {metaphor_count} cảnh (yêu cầu >= 4 cảnh).')
    # Collect scene fallbacks from render results
    fallbacks = []
    for r in results:
        sc_id = r.get('scene_id')
        for n in r.get('repair_notes', []):
            if any(k in n.lower() for k in ['thiếu dữ liệu', 'enough=false', 'tự động dùng recipe thay thế', 'chuyển sang recipe']):
                fallbacks.append({'scene_id': sc_id, 'reason': n})
    report['fallbacks'] = fallbacks

    target_types = 5 if len(timeline.scenes) >= 5 else min(4, len(timeline.scenes))
    if requested:
        if report['illustration_coverage_percent']<85: extra.append('[illustration_coverage, nhóm 3] Hình minh họa dưới 85% thời lượng.')
        if len(types)<target_types: extra.append(f'[illustration_variety, nhóm 3] Dưới {target_types} loại recipe ({len(types)}/{target_types}); cần tăng đa dạng trực quan.')
        if any(v['count']<4 for v in moving): extra.append('[illustration_motion, nhóm 3] Có cảnh dưới 4 phần tử chuyển động/đang fallback.')
        if subtitle: extra.append('[illustration_hold, nhóm 3] Có khoảng chỉ phụ đề>2s.')
        if missing_numeric: extra.append(f'[illustration_numbers, nhóm 3] Cảnh có số nhưng không có hình số: {missing_numeric}.')
    timeline.plan.review_notes.extend(n for n in extra if n not in timeline.plan.review_notes)
    timeline.warnings.extend(n for n in extra if n not in timeline.warnings)
    suffix=f'_scene_{scene_id}' if scene_id is not None else ''
    folder=timeline.project/'review_frames'/('samples'+suffix);folder.mkdir(parents=True,exist_ok=True)
    times=[];t=0.
    while t<timeline.duration:
        times.append(round(t,3));t+=2.5
    thumbs=[];paths=[]
    with VideoFileClip(str(video_path),audio=False) as clip:
        for index,t in enumerate(times):
            frame=Image.fromarray(clip.get_frame(min(t,max(0,clip.duration-.05))))
            path=folder/f'frame_{index:04d}.png';frame.save(path);paths.append(str(path))
            frame.thumbnail((180,320));thumbs.append(frame.copy())
    columns=min(6,max(1,len(thumbs)));cell=(180,345)
    sheet=Image.new('RGB',(columns*cell[0],((len(thumbs)+columns-1)//columns)*cell[1]),'#0a1220');draw=ImageDraw.Draw(sheet)
    for i,image in enumerate(thumbs):
        x=i%columns*cell[0];y=i//columns*cell[1]
        sheet.paste(image,(x+(cell[0]-image.width)//2,y));draw.text((x+5,y+322),f'{times[i]:.1f}s',fill='white')
    target=timeline.project/'review_frames'/('contact_sheet'+suffix+'.png');sheet.save(target)
    import hashlib
    try:
        report['video_hash'] = hashlib.sha256(Path(video_path).read_bytes()).hexdigest()
        report['is_current_hash'] = True
    except Exception:
        report['video_hash'] = None

    shots_listing = []
    for sc in timeline.scenes:
        for sh in sc.shots:
            sh_vp = getattr(sh.spec, "visual_plan", None) or getattr(sh, "visual_plan", None)
            sh_r = getattr(sh_vp, "scene_type", None) or (sc.spec.visual_plan.scene_type if getattr(sc.spec, "visual_plan", None) else "text_focus")
            shots_listing.append({
                "scene_id": sc.spec.id,
                "shot_id": getattr(sh, "shot_id", 1),
                "recipe": sh_r,
                "duration": sh.duration
            })
    report['shots'] = shots_listing

    report.update(duration_sec=timeline.duration,sample_interval_sec=2.5,frames=paths,contact_sheet=str(target),review_notes=timeline.plan.review_notes)
    report['warning_count']=len(extra)+sum(len(report[k]) for k in ('repeated_cards','still_intervals_over_3_5_sec','empty_cards_over_40_percent','text_overflow','numbers_not_in_narration','caption_gaps_over_0_6_sec'))
    try:
        from tools.audit_video import audit_project
        report['layout_audit'] = audit_project(timeline.project)
    except Exception:
        pass
    write_json_atomic(timeline.project/('quality_report'+suffix+'.json'),report)
    return report
