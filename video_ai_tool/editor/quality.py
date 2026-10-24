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
        'text_overflow':[q for q in checks if any(x in q['issues'] for x in ('text_overflow','text_safe_area','caption_overlap','caption_safe_area'))],
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
    report.update(duration_sec=timeline.duration,sample_interval_sec=2.5,frames=paths,contact_sheet=str(target),review_notes=timeline.plan.review_notes)
    report['warning_count']=sum(len(report[k]) for k in ('repeated_cards','still_intervals_over_3_5_sec','empty_cards_over_40_percent','text_overflow','numbers_not_in_narration','caption_gaps_over_0_6_sec'))
    write_json_atomic(timeline.project/('quality_report'+suffix+'.json'),report)
    return report
