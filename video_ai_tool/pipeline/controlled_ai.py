"""Optional AI illustration behind cards, reusing durable gateway jobs/locks."""
import hashlib
from pathlib import Path
from providers.video_gateway import VideoRequest,MODELS
from agents.video_prompt_writer import sanitize_video_prompt,fallback_prompt
from agents.visual_diversity import values_in
from pipeline.ai_video import create_job,resume_job,diagnostics_for,load_job
from utils.atomic_io import read_json_atomic,write_json_atomic
from utils.file_lock import file_lock
from utils.cache import cache_key

DATA_TEMPLATES={'stat_card','ring_percent','line_growth','compare_bars','strike_replace','timeline','steps_list','versus','source_card','quote_card'}


def eligible_slots(plan):
    result=[]
    for index,scene in enumerate(plan.scenes):
        if index!=0 and not any(w in (str(scene.style_purpose or '')+' '+str(getattr(scene,'information_kind',''))).casefold() for w in ('cao trào','climax','surprise','twist')): continue
        for number,shot in enumerate(scene.shots,1):
            v=shot.visual
            if not v or v.template in DATA_TEMPLATES: continue
            if values_in(shot.card_text or v.data.text) or v.data.value is not None or v.data.bars: continue
            result.append((scene,number,shot));break  # at most one clip per eligible scene
    return result


def estimate(plan,settings,count=None):
    count=settings.ai_clips_per_video if count is None else count
    model=settings.ai_clip_model or settings.gateway_video_model
    options=[n for n in MODELS[model] if n<=settings.ai_clip_max_sec]
    if not options: raise ValueError('AI_CLIP_MAX_SEC thấp hơn thời lượng model hỗ trợ; dùng nền gradient.')
    seconds=next((n for n in options if n>=settings.ai_clip_seconds),options[-1])
    slots=eligible_slots(plan)[:min(count,settings.ai_clip_max_per_run)]
    request=VideoRequest(model=model,seconds=seconds,format=plan.format,prompt=fallback_prompt(plan.title))
    return {'count':len(slots),'model':model,'seconds':seconds,'estimated_vnd_per_job':request.estimated_cost_vnd,
        'estimated_vnd_max_with_retry':len(slots)*2*request.estimated_cost_vnd,'slots':[(s.id,n) for s,n,_ in slots],
        'price_notice':'Giá tham khảo từ code, chưa xác minh hóa đơn; generation_failed có thể thêm 1 job có phí.'}


def background_prompt(plan,shot):
    if shot.ai_prompt: return sanitize_video_prompt(shot.ai_prompt)
    prompt=fallback_prompt(plan.title)
    category=getattr(getattr(plan,'style_profile',None),'category_id','') or ''
    if category=='cong-nghe': prompt=prompt.replace('warm light','cool light')
    return sanitize_video_prompt(prompt)


def create_backgrounds(project,settings,*,confirmed=False,count=None,progress=None):
    from schemas.assets import ResolvedEditPlan
    project=Path(project).resolve();plan=ResolvedEditPlan.model_validate_json((project/'edit_plan.resolved.json').read_text(encoding='utf-8'))
    info=estimate(plan,settings,count)
    if not info['count']: return {'clips':[],'warnings':[],'estimate':info}
    if not confirmed: raise ValueError('Cần xác nhận chi phí Clip AI trước khi gửi job.')
    diagnostics=diagnostics_for(settings);notify=progress or (lambda fraction,message:None)
    target=project/'render/ai_backgrounds.json';target.parent.mkdir(exist_ok=True)
    with file_lock(project/'render/ai_backgrounds.lock'):
        previous=read_json_atomic(target) if target.exists() else {'clips':[],'warnings':[]}
        result={'clips':[],'warnings':[],'estimate':info,'disclosure':'Nội dung có hình AI'}
        for scene,index,shot in eligible_slots(plan)[:info['count']]:
            # Keep valid Director-authored prompts. The shared sanitizer strips
            # brands and unsafe details; no new text-model request at Render.
            prompt=background_prompt(plan,shot)
            request=VideoRequest(model=info['model'],seconds=info['seconds'],format=plan.format,prompt=prompt)
            old=next((x for x in previous['clips'] if x['scene_id']==scene.id and x['shot_id']==index),None)
            try:
                if old and old.get('request')!=request.model_dump(mode='json'):
                    raise ValueError('Prompt/model đã đổi sau job cũ; kiểm tra dashboard, không tạo thêm tự động.')
                identity=cache_key(request.model_dump(mode='json'))
                receipt=project/f'ai_video/background_slot_{scene.id}_{index}.receipt'
                if receipt.exists() and read_json_atomic(receipt)['request_hash']!=identity and not (project/f'ai_video/{identity}.json').exists():
                    raise ValueError('Slot nền đã gửi prompt/model khác, có thể đang tính phí. Kiểm tra dashboard và xác nhận job mới trên AI Video; không POST lại tự động.')
                write_json_atomic(receipt,{'scene_id':scene.id,'shot_id':index,'request_hash':identity})
                job_path=create_job(project,request,settings)
                job=resume_job(job_path,settings,progress=notify,wait_sec=300)
                effective=Path(job.get('effective_job_path',job_path))
                clip=project/job['clip_path']
                result['clips'].append({'scene_id':scene.id,'shot_id':index,'path':str(clip.relative_to(project)),
                    'sha256':hashlib.sha256(clip.read_bytes()).hexdigest(),'request':request.model_dump(mode='json'),
                    'job_path':str(effective.relative_to(project)),'remote_id':job['remote_id'],
                    'model':request.model,'seconds':request.seconds,'clip_path':job['clip_path'],'duration_sec':job['duration_sec'],
                    'actual_cost_vnd':job.get('actual_cost_vnd'),'estimated_cost_vnd':request.estimated_cost_vnd})
            except Exception as error:
                diagnostics.record_exception(error,f'Clip AI nền cảnh {scene.id}; dùng gradient, không dừng render')
                result['warnings'].append(f'Cảnh {scene.id}: {diagnostics.redact(str(error))}; dùng nền gradient.')
            write_json_atomic(target,result)
        return result


def backgrounds_for_scene(scene,project):
    """Decode only successful, SHA-verified local jobs. No network at Render."""
    import base64,io
    from editor.runtime import VideoFileClip
    from PIL import Image,ImageFilter,ImageEnhance
    from editor.timeline import confined
    path=Path(project)/'render/ai_backgrounds.json'
    if not path.exists(): return []
    entries=read_json_atomic(path).get('clips',[]);result=[]
    for entry in entries:
        if entry['scene_id']!=scene.spec.id: continue
        clip_path=confined(project,entry['path']);job=load_job(confined(project,entry['job_path']))
        if not job.get('clip_path') or confined(project,job['clip_path'])!=clip_path or hashlib.sha256(clip_path.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Clip AI nền không khớp job/hash; dùng gradient.')
        shot=next((s for s in scene.shots if s.shot_id==entry['shot_id']),None)
        if not shot or not shot.spec.visual or shot.spec.visual.template in DATA_TEMPLATES: continue
        frames=[];fps=8
        with VideoFileClip(str(clip_path),audio=False) as video:
            for i in range(max(1,int(min(30,video.duration)*fps))):
                frame=Image.fromarray(video.get_frame(i/fps));frame.thumbnail((270,480))
                frame=ImageEnhance.Brightness(frame.filter(ImageFilter.GaussianBlur(9))).enhance(.5)
                stream=io.BytesIO();frame.save(stream,format='JPEG',quality=60)
                frames.append('data:image/jpeg;base64,'+base64.b64encode(stream.getvalue()).decode('ascii'))
        result.append({'start':shot.start-scene.start,'duration':shot.duration,'frames':frames,'fps':fps})
    return result
