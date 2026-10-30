"""Optional deterministic Chromium -> FFmpeg scene cache; never edits Render inputs."""
from contextlib import contextmanager
import base64
import hashlib
import io
import json
import math
import re
from pathlib import Path
import subprocess
from tempfile import TemporaryFile
import time
from functools import lru_cache
from uuid import uuid4

from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image
import numpy as np
from utils.atomic_io import discard_temp_file,replace_file_retry,write_json_atomic
from utils.cache import cache_key
from utils.file_lock import file_lock
from utils.word_timing import align_words,read_words,timing_source

MOTION_DIR=Path(__file__).resolve().parents[1]/"editor/motion"
SUPPORTED={"hook_card","steps_list","compare_bars","stat_card","source_card","text_focus",
    "progress_tracker","ring_percent","line_growth","strike_replace","quote_card","timeline","versus","icon_card","cta_card",
    "slot_counter","gauge_needle","odometer","bar_race","thermometer","battery_fill",
    "glass_fill","balance_scale","tug_of_war","vs_flip_cards","before_after_wipe",
    "conveyor_belt","domino_chain","funnel_filter","pipeline_pipes","dice_roll",
    "lock_unlock","shield_hit","traffic_light","orbit_system","layered_onion",
    "stack_pile","puzzle_snap","chat_thread","mock_card_swipe","form_fill_submit",
    "terminal_command_run","stat_number","bar_compare","container_fill","steps_ladder",
    "stack_cards","flow_chain","network_nodes","terminal_type","magnifier_check",
    "versus_scale","versus_split","code_card","timeline_march","mock_ui_window",
    "checklist","hub_spoke"}


@lru_cache(maxsize=4)
def background_images(size,top="#101b30",bottom="#080c17"):
    """Pre-rasterize gradients: Chromium CSS-gradient dithering varies by paint."""
    width,height=size
    y,x=np.mgrid[0:height,0:width]
    mix=(y/height)[...,None]
    from PIL import ImageColor
    base=np.array(ImageColor.getrgb(top))*(1-mix)+np.array(ImageColor.getrgb(bottom))*mix
    base=np.broadcast_to(base,(height,width,3)).copy()
    glow=np.maximum(0,1-np.sqrt(((x-width*.15)/width)**2+((y-height*.18)/height)**2)/.8)[...,None]
    base+=glow*np.array([5,14,17])
    radius=np.sqrt(((x:=np.arange(180)[None,:])-90)**2+((y:=np.arange(180)[:,None])-90)**2)
    orb=np.zeros((180,180,4),dtype=np.uint8);orb[:,:,:3]=[138,213,223];orb[:,:,3]=np.maximum(0,1-radius/90)**2*36
    def uri(pixels):
        buffer=io.BytesIO();Image.fromarray(pixels).save(buffer,format="PNG")
        return "data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode("ascii")
    return uri(np.clip(base,0,255).astype(np.uint8)),uri(orb)


def scene_payload(scene,size,caption_style,options=None):
    words,method=align_words(scene.spec.narration,scene.duration,read_words(scene.audio.with_suffix(".words.json")))
    origin=timing_source(scene.audio.with_suffix(".words.json"))
    payload={"width":size[0],"height":size[1],"duration":scene.duration,"words":words,"timing_source":origin if origin!="word_boundary" else method,
        "captions":caption_style.model_dump(mode="json"),"shots":[{
            "start":s.start-scene.start,"duration":s.duration,
            "template":s.spec.visual.template if s.spec.visual else "stock",
            "data":s.spec.visual.data.model_dump(mode="json") if s.spec.visual else {},
            "beats":[b.model_dump(mode="json") for b in s.spec.visual.beats] if s.spec.visual else [],
            "visual_plan":(s.spec.visual_plan.model_dump(mode="json") if hasattr(s.spec, "visual_plan") and s.spec.visual_plan else (s.visual_plan.model_dump(mode="json") if hasattr(s, "visual_plan") and s.visual_plan else getattr(s, "visual_plan", None)))
        } for s in scene.shots]}
    payload.update(options or {})
    # Intercept MOTION_FORCE_RECIPES override for recipe path verification
    import os
    force_env = os.environ.get("MOTION_FORCE_RECIPES", "").strip()
    forced_recipe = None
    if force_env:
        force_list = [r.strip() for r in force_env.split(",") if r.strip()]
        sc_idx = (getattr(scene.spec, 'id', None) or 1) - 1
        if 0 <= sc_idx < len(force_list):
            forced_recipe = force_list[sc_idx]

    spec=getattr(scene, 'visual_plan', None) or getattr(scene.spec,'visual_plan',None)
    notes=list(getattr(spec, 'repair_notes', [])) if spec else []
    if forced_recipe:
        from schemas.visual_v3 import MotionScenePlan
        if not spec:
            spec = MotionScenePlan(
                scene_type=forced_recipe,
                layout="center_hero",
                beats=[],
                data={"text": scene.spec.narration[:30]}
            )
        else:
            spec.scene_type = forced_recipe
    payload['visual_plan']=None
    if spec:
        payload['anchor'] = {
            'anchor_element': getattr(spec, 'anchor', None),
            'metaphor_name': getattr(spec, 'central_metaphor', None),
            'state': getattr(spec, 'metaphor_state', None),
        }
    from config.settings import get_settings
    settings = get_settings()
    illustrations_enabled = payload.get('illustrations_enabled', False) or bool(forced_recipe) or getattr(settings, 'motion_recipes_enabled', True)
    if spec and illustrations_enabled:
        from agents.illustrations import scene_data,enough
        from agents.visual_diversity import values_in
        rebound=scene_data(scene.spec)
        allowed=set(payload.get('allowed_numbers',[]))|values_in(scene.spec.narration)
        for shot in scene.shots:
            v=shot.spec.visual
            if not v or v.template in {'stock','source_card'}: continue
            date_value=bool(v.data.number_text and re.search(r'(?:ngày|tháng)\s+'+re.escape(v.data.number_text.strip())+r'\b',scene.spec.narration,re.I))
            if rebound.value is None and v.data.value is not None and not date_value and values_in(str(v.data.value))<=allowed:
                rebound.value=v.data.value;rebound.unit=v.data.unit;rebound.number_text=v.data.number_text;rebound.label=v.data.label or v.data.text
            if len(v.data.bars)>=2 and all(values_in(str(b.value))<=allowed for b in v.data.bars): rebound.bars=v.data.bars[:]
        if rebound.value is None:
            from agents.illustrations import spoken_stat
            if found:=spoken_stat(scene.spec.narration,payload.get('allowed_numbers',[])):
                rebound.value,rebound.unit,rebound.number_text=found
                rebound.label=next((x for x in rebound.items if re.search(r'năng suất|tỷ lệ|doanh thu|chi phí|quy mô',x,re.I)),rebound.items[0] if rebound.items else rebound.text)
                rebound.source=next(iter(payload.get('source_labels',[])),rebound.source)
        # Inherit valid data from spec if available
        if hasattr(spec, 'data') and spec.data:
            s_data = spec.data if isinstance(spec.data, dict) else spec.data.model_dump(mode='json')
            if rebound.value is None and s_data.get('value') is not None:
                rebound.value = s_data['value']
                rebound.unit = s_data.get('unit') or rebound.unit
                rebound.number_text = s_data.get('number_text') or rebound.number_text
                rebound.label = s_data.get('label') or s_data.get('title') or rebound.label
            if not rebound.bars and s_data.get('bars'):
                rebound.bars = list(s_data['bars'])
            if not rebound.items and s_data.get('items'):
                rebound.items = list(s_data['items'])

        if forced_recipe:
            rebound_dict = rebound.model_dump(mode='json') if hasattr(rebound, 'model_dump') else dict(rebound)
            rebound_dict['_is_fixture'] = False
            from editor.format_number import parse_display_number
            p_num = parse_display_number(scene.spec.narration)
            if p_num:
                if rebound_dict.get('value') is None:
                    rebound_dict['value'] = p_num.value
                    rebound_dict['unit'] = p_num.unit_display
                    rebound_dict['number_text'] = p_num.formatted_number
            # Cảnh báo đỏ nếu MOTION_FORCE_RECIPES được bật trong luồng chạy thật
            force_warn = f"🚨 CẢNH BÁO ĐỎ [motion_debug]: MOTION_FORCE_RECIPES đang được bật ('{forced_recipe}')! Bỏ qua Visual Planner, chỉ dùng cho kiểm thử/công cụ nội bộ, không dùng cho sản xuất."
            notes.append(force_warn)
            if forced_recipe == "glass_fill" and rebound_dict.get('value') is not None:
                rebound_dict['fill_percentage'] = min(100, max(15, rebound_dict['value'] if rebound_dict['value'] <= 100 else 60))
            elif forced_recipe == "gauge_needle" and rebound_dict.get('value') is not None:
                rebound_dict['max_val'] = 100
                rebound_dict['unit'] = rebound_dict.get('unit') or '%'

            beats = [
                {"at_sec": 0.5, "action": f"enter_{forced_recipe}"},
                {"at_sec": 1.8, "action": f"action_{forced_recipe}_step"},
                {"at_sec": 3.2, "action": f"impact_{forced_recipe}_glow"},
            ]
            dur = scene.duration
            last_t = 3.2
            while dur - last_t > 2.5:
                inject_t = round(last_t + 2.0, 2)
                if inject_t < dur:
                    beats.append({"at_sec": inject_t, "action": "action_progression"})
                last_t = inject_t

            payload['visual_plan'] = {
                'scene_type': forced_recipe,
                'recipe': forced_recipe,
                'depth_3d': False,
                'data': rebound_dict,
                'beats': beats,
                'annotations': [a.model_dump(mode='json') if hasattr(a, 'model_dump') else a for a in getattr(spec, 'annotations', [])]
            }
        elif enough(spec.scene_type,rebound):
            resolved=spec.model_copy(update={'data':rebound})
            from agents.motion_beats import shot_beats
            from schemas.visual import Visual
            dummy=scene.shots[0].spec.model_copy(deep=True)
            dummy.visual=Visual(template='steps_list',data=rebound);dummy.card_text=rebound.text
            if getattr(spec, 'beats', None):
                beats=[b.model_dump(mode='json') for b in spec.beats]
            else:
                beats,_=shot_beats(dummy,words,0.,scene.duration,purpose=scene.spec.role)
            annots = getattr(spec, 'annotations', [])
            annots_json = [a.model_dump(mode='json') if hasattr(a, 'model_dump') else a for a in annots]
            payload['visual_plan']={**resolved.model_dump(mode='json'),'beats':beats,'annotations':annots_json}
        else:
            # Fallback dùng kết quả suggest_metaphor_recipe, chọn recipe theo lời đọc, tránh trùng cảnh liền kề, KHÔNG luôn trả balance_scale
            from editor.motion.scheduler import suggest_metaphor_recipe
            prev_r = getattr(scene, 'previous_recipe', None) or (options.get('previous_recipe') if options else None)
            cand_alt = suggest_metaphor_recipe(scene.spec.narration, previous_recipe=prev_r)
            NUMERIC_RECIPES = {
                "slot_counter", "strike_replace", "gauge_needle", "odometer",
                "thermometer", "stat_number", "bar_race", "gauge_ring", "bar_compare"
            }
            if cand_alt in NUMERIC_RECIPES and rebound.value is None:
                qualitative_pool = ["conveyor_belt", "domino_chain", "stack_pile", "lock_unlock", "orbit_system", "puzzle_snap", "traffic_light", "shield_hit", "balance_scale"]
                chosen_alt = next((r for r in qualitative_pool if r != spec.scene_type and r != prev_r), "conveyor_belt")
            else:
                if cand_alt == spec.scene_type or cand_alt == prev_r:
                    alt_pool = ["domino_chain", "stack_pile", "conveyor_belt", "orbit_system", "lock_unlock", "shield_hit"]
                    chosen_alt = next((r for r in alt_pool if r != spec.scene_type and r != prev_r), "conveyor_belt")
                else:
                    chosen_alt = cand_alt

            rebound_dict = rebound.model_dump(mode='json') if hasattr(rebound, 'model_dump') else dict(rebound)
            if not rebound_dict.get('label'):
                from agents.presentation import card_phrase
                clean_lbl = card_phrase(rebound.label or rebound.text, scene.spec.narration)
                rebound_dict['label'] = clean_lbl

            alt_beats = [
                {"at_sec": 0.5, "action": f"enter_{chosen_alt}"},
                {"at_sec": 1.8, "action": f"action_{chosen_alt}_step"},
                {"at_sec": 3.2, "action": f"impact_{chosen_alt}_glow"},
            ]
            annots_json = [a.model_dump(mode='json') if hasattr(a, 'model_dump') else a for a in getattr(spec, 'annotations', [])]
            payload['visual_plan'] = {
                'scene_type': chosen_alt,
                'recipe': chosen_alt,
                'depth_3d': False,
                'data': rebound_dict,
                'beats': alt_beats,
                'annotations': annots_json
            }
            fallback_msg = f"Cảnh {scene.spec.id}: Recipe '{spec.scene_type}' thiếu số liệu (enough=False); tự động dùng recipe thay thế '{chosen_alt}' theo nội dung lời đọc."
            payload['illustration_fallback'] = fallback_msg
            notes.append(fallback_msg)
    from utils.caption_timing import display_words
    payload['caption_words']=[{'text':text,'start':start,'end':end} for text,start,end in
        display_words([(w['text'],w['start'],w['end']) for w in words],scene.duration)]
    from editor.motion.icons import icon_for,chip_text
    root=MOTION_DIR.parents[1]
    payload['chip']={'text':chip_text(scene.spec)}
    payload['chip']['name'],payload['chip']['uri']=icon_for(root,scene.spec.narration)
    for shot in payload['shots']:
        shot['icon_name'],shot['icon_uri']=icon_for(root,str(shot['data'].get('text',''))+' '+scene.spec.narration)
    from agents.presentation import card_phrase,vietnamese_terms
    # Keep existing repair_notes in notes list
    for shot,spec in zip(payload["shots"],scene.shots):
        data=shot["data"];name=shot["template"]
        if payload.get('illustration_fallback') and name not in {'source_card','stock'}:
            shot['template']='text_focus';name='text_focus';data['value']=None;data['bars']=[]
        if name not in {"stock","source_card"}:
            data["text"]=card_phrase(getattr(spec.spec,"card_text",None) or data.get("text") or data.get("label"),scene.spec.narration)
            data["highlight"]=getattr(spec.spec,"emphasis",[]) or data.get("highlight",[])
        valid_bars=len(data.get("bars",[]))>=2 and all(b.get("label","").strip() and math.isfinite(b["value"]) for b in data["bars"])
        valid_items=len(data.get("items",[]))>=2 and all(str(s).strip() for s in data["items"])
        enough={"ring_percent":data.get("value") is not None and 0<=data["value"]<=100,
            "stat_card":data.get("value") is not None and math.isfinite(data["value"]),
            "line_growth":valid_bars,"strike_replace":valid_bars,
            "versus":valid_bars or valid_items,"timeline":valid_items,
            "steps_list":valid_items,"compare_bars":valid_bars,
            "progress_tracker":bool(data.get("items")),"source_card":bool(data.get("source")),
            "quote_card":bool(data.get("source") and data.get("source_url") and data.get("text"))}.get(name,True)
        if not enough:
            shot["template"]="text_focus";notes.append(f"motion_data nhóm 2: {name} thiếu dữ liệu, dùng text_focus.")
        if name=="source_card": data["source"]=" · ".join(data.get("source","").split(" · ")[:2])
        if name=="quote_card":
            # Display only an explicitly supplied, short quotation, never manufacture it.
            raw=spec.spec.visual.data.text
            if not 3<=len(raw.split())<=6: shot["template"]="text_focus";notes.append("motion_data nhóm 2: quote không phải cụm 3–6 từ; dùng thẻ ý chính, không dựng trích dẫn giả.")
            else: data["text"]=raw
    payload["repair_notes"]=notes
    from utils.caption_timing import phrase_groups
    payload['caption_groups']=[[{'text':s,'start':a,'end':b} for s,a,b in group] for group in phrase_groups([(w['text'],w['start'],w['end']) for w in payload['caption_words']])]
    return payload


def html_document(payload,font):
    # Embed a single local font: no HTTP/file-origin font access, no remote resources.
    encoded=base64.b64encode(Path(font).read_bytes()).decode("ascii")
    css=(MOTION_DIR/"base.css").read_text(encoding="utf-8").replace("__FONT__","data:font/otf;base64,"+encoded)
    theme=payload.get("theme",{})
    bg,orb=background_images((payload["width"],payload["height"]),theme.get("top","#101b30"),theme.get("bottom","#080c17"))
    css+=f'#stage{{background-image:url("{bg}");background-size:100% 100%}}.orb{{background-image:url("{orb}");background-size:100% 100%}}.bar-fill{{background:var(--accent)}}'
    data=json.dumps(payload,ensure_ascii=True).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    js=(MOTION_DIR/"runtime.js").read_text(encoding="utf-8")
    from editor.motion.scenes import bundle
    scene_css,scene_js,_=bundle()
    themes_css = (MOTION_DIR/"themes/themes.css").read_text(encoding="utf-8") if (MOTION_DIR/"themes/themes.css").is_file() else ""
    try:
        from editor.motion.engine import bundle_engine
        engine_css, engine_js, _ = bundle_engine()
    except Exception:
        engine_css, engine_js = "", ""
    try:
        from editor.depth import bundle_depth
        depth_css, depth_js, _ = bundle_depth()
    except Exception:
        depth_css, depth_js = "", ""
    css += '\n' + scene_css + '\n' + themes_css + '\n' + engine_css + '\n' + depth_css
    js = depth_js + '\n' + engine_js + '\n' + scene_js + '\n' + js
    t_name = str(theme.get('name', 'studio'))
    depth_enabled = bool(payload.get("depth_3d", False))
    if not depth_enabled:
        try:
            from config.settings import get_settings
            depth_enabled = bool(get_settings().depth_3d_enabled)
        except Exception:
            depth_enabled = False
    flag_script = f"window.DEPTH_3D_ENABLED = {'true' if depth_enabled else 'false'};"
    return f'<!doctype html><meta charset="utf-8"><style>{css}</style><div id="stage" class="theme-{t_name}"></div><script>window.MOTION_DATA={data};{flag_script}</script><script>{js}</script>'


@contextmanager
def browser_page(size):
    """Imported only on a motion cache miss. Missing package/browser is recoverable."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(headless=True,timeout=20000,
            args=["--disable-gpu","--disable-lcd-text","--force-color-profile=srgb"])
        try:
            context=browser.new_context(viewport={"width":size[0],"height":size[1]},device_scale_factor=1,
                locale="vi-VN",color_scheme="dark",reduced_motion="reduce",service_workers="block")
            context.route("**/*",lambda route:route.abort())
            page=context.new_page()
            page.set_default_timeout(15000)
            yield page
        finally:
            browser.close()


def capture(page,payload,font,*,png=False):
    page.set_content(html_document(payload,font),wait_until="load")
    page.evaluate("() => document.fonts.ready")
    page.evaluate("""async () => {
        const sources=[...Object.values(MOTION_DATA.mascots||{}),MOTION_DATA.chip?.uri,
            ...MOTION_DATA.shots.map(s=>s.icon_uri),...(MOTION_DATA.ai_backgrounds||[]).flatMap(b=>b.frames)].filter(Boolean);
        window._motionImages=[];
        await Promise.all([...new Set(sources)].map(src=>new Promise(resolve=>{
            const image=new Image();window._motionImages.push(image);image.onload=resolve;image.onerror=resolve;image.src=src;
        })));
    }""")
    page.evaluate("() => window.renderAt(0)")


def render_scene(scene,cache_dir,*,size,font,caption_style,fps=30,static_frame=None,
                 progress=None,diagnostics=None,extra_identity=None,options=None,force=False):
    """Return cache result or None on engine failure; caller retains Pillow path.

    Unsupported templates are rendered by the existing frame callback, not by an
    imitation HTML template. Beat seconds/word indexes are scene-local/zero-based.
    """
    payload=scene_payload(scene,size,caption_style,options)
    if not any(s["template"] in SUPPORTED for s in payload["shots"]): return None
    sources=[]
    for shot in scene.shots:
        path=shot.path
        sources.append((str(path),path.stat().st_size,path.stat().st_mtime_ns) if path and path.is_file() else None)
    dependencies=[Path(__file__),MOTION_DIR/"runtime.js",MOTION_DIR/"base.css",
        MOTION_DIR.parents[1]/"editor/layout.py",MOTION_DIR.parents[1]/"editor/templates/core.py",
        MOTION_DIR.parents[1]/"editor/captions.py",MOTION_DIR.parents[1]/"editor/graphics.py",
        MOTION_DIR.parents[1]/"agents/presentation.py",MOTION_DIR/"theme.py",
        MOTION_DIR.parents[1]/"agents/motion_beats.py",Path(font)]
    from editor.motion.scenes import bundle
    from editor.motion.engine import bundle_engine
    _,_,scene_digest=bundle()
    _,_,engine_digest=bundle_engine()
    identity={"payload":payload,"fps":fps,"sources":sources,"extra":extra_identity,'scene_engine':scene_digest,
        'engine_motion':engine_digest,
        "engine":hashlib.sha256(b"".join(p.read_bytes() for p in dependencies)).hexdigest()}
    key=cache_key(identity);folder=Path(cache_dir);destination=folder/(key+".mp4");meta=folder/(key+".json")
    started=time.perf_counter();notify=progress or (lambda value,message:None)
    temporary=None;process=None
    try:
        folder.mkdir(parents=True,exist_ok=True)
        with file_lock(folder/(key+".lock"),timeout=180):
            started=time.perf_counter()
            if not force and destination.is_file() and meta.is_file():
                record=json.loads(meta.read_text(encoding="utf-8"))
                if destination.stat().st_size==record.get("size_bytes") and record.get("sha256")==hashlib.sha256(destination.read_bytes()).hexdigest():
                    notify(1.,f"Motion cảnh {scene.spec.id}: dùng cache")
                    return dict(record,path=str(destination),cache_hit=True,render_seconds=0.)
            temporary=folder/(uuid4().hex+".tmp.mp4")
            count=max(1,math.ceil(scene.duration*fps));last=0.;illustrated_frames=0;moving_counts=[];subtitle_start=None;subtitle_only=[]
            with browser_page(size) as page, TemporaryFile() as errors:
                capture(page,payload,font)

                # AUDIT VÀ TỰ SỬA TRƯỚC KHI ĐẨY KHUNG VÀO FFMPEG (dựng thử >= 3 mốc thời gian)
                t_checkpoints = [
                    round(min(0.5, scene.duration * 0.15), 2),
                    round(min(scene.duration * 0.5, 2.0), 2),
                    round(max(0.5, scene.duration - 0.5), 2),
                ]
                def _eval_layout_audit():
                    audit_res = None
                    for tc in t_checkpoints:
                        page.evaluate("t => window.renderAt(t)", tc)
                        res = page.evaluate("() => window.getLayoutAudit ? window.getLayoutAudit() : null")
                        if res:
                            audit_res = res
                            if any([
                                res.get("clipped_rows", 0) > 0,
                                res.get("bbox_overlaps", 0) > 0,
                                res.get("caption_collisions", 0) > 0,
                                res.get("empty_prompts", 0) > 0,
                                res.get("center_y_drift", 0) > 120,
                            ]):
                                break
                    return audit_res

                layout_audit = _eval_layout_audit()
                audit_passed = bool(
                    layout_audit and
                    layout_audit.get("clipped_rows", 0) == 0 and
                    layout_audit.get("bbox_overlaps", 0) == 0 and
                    layout_audit.get("caption_collisions", 0) == 0 and
                    layout_audit.get("empty_prompts", 0) == 0 and
                    layout_audit.get("center_y_drift", 0) <= 120
                )
                audit_retries = 0
                payload_repaired = False
                while not audit_passed and audit_retries < 2:
                    audit_retries += 1
                    if audit_retries == 1:
                        page.evaluate(r"""() => {
                            if (window.MOTION_DATA && window.MOTION_DATA.visual_plan && window.MOTION_DATA.visual_plan.data) {
                                const d = window.MOTION_DATA.visual_plan.data;
                                if (d.items) {
                                    d.items = d.items.map(s => String(s).split(/(?<!\d)[.!?\n]|[.!?\n](?!\d)/)[0].split(/\s+/).slice(0, 5).join(' '));
                                }
                            }
                        }""")
                        payload_repaired = True
                    elif audit_retries == 2:
                        # Lượt 2: Sửa nhẹ (co cỡ chữ, rút ngắn nhãn/items, sửa va chạm), KHÔNG biến thành text_focus
                        page.evaluate(r"""() => {
                            if (window.MOTION_DATA && window.MOTION_DATA.visual_plan && window.MOTION_DATA.visual_plan.data) {
                                const d = window.MOTION_DATA.visual_plan.data;
                                if (d.items) {
                                    d.items = d.items.map(s => String(s).split(/(?<!\d)[.!?\n]|[.!?\n](?!\d)/)[0].split(/\s+/).slice(0, 4).join(' '));
                                }
                                if (d.label) {
                                    d.label = String(d.label).split(/\s+/).slice(0, 3).join(' ');
                                }
                            }
                            const allTexts = document.querySelectorAll('.title, .bar-label, text, .ill-label, .row');
                            allTexts.forEach(el => {
                                const curSize = parseFloat(window.getComputedStyle(el).fontSize) || 40;
                                if (curSize > 32) {
                                    el.style.fontSize = Math.max(32, Math.round(curSize * 0.88)) + 'px';
                                }
                            });
                        }""")
                        payload_repaired = True
                    layout_audit = _eval_layout_audit()
                    audit_passed = bool(
                        layout_audit and
                        layout_audit.get("clipped_rows", 0) == 0 and
                        layout_audit.get("bbox_overlaps", 0) == 0 and
                        layout_audit.get("caption_collisions", 0) == 0 and
                        layout_audit.get("empty_prompts", 0) == 0 and
                        layout_audit.get("center_y_drift", 0) <= 120
                    )

                final_source = next((s for s in reversed(payload["shots"]) if s["template"] == "source_card"), None)
                review_time = final_source["start"] + min(.8, final_source["duration"] * .5) if final_source else min(scene.duration - .01, scene.duration * .5)
                page.evaluate("t => renderAt(t)", review_time)
                review_path = folder / (key + ".review.png")
                page.screenshot(path=str(review_path), type="png")

                # BẮT ĐẦU ENCODE SAU KHI AUDIT / TỰ SỬA HOÀN TẤT
                process=subprocess.Popen([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y",
                    "-f","image2pipe","-vcodec","mjpeg","-framerate",str(fps),"-i","pipe:0","-an",
                    "-c:v","libx264","-preset","veryfast","-crf","20","-threads","2","-pix_fmt","yuv420p","-movflags","+faststart",str(temporary)],
                    stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors)
                try:
                    for i in range(count):
                        t=min(i/fps,scene.duration-1e-6)
                        shot=next((s for s in payload["shots"] if s["start"]<=t<s["start"]+s["duration"]),payload["shots"][-1])
                        if shot["template"] in SUPPORTED:
                            state=page.evaluate("t => window.renderAt(t)",t) or {}
                            if state.get('illustrated'):
                                illustrated_frames+=1;moving_counts.append(state.get('moving_elements',0))
                            if state.get('subtitle_only') and subtitle_start is None: subtitle_start=t
                            if not state.get('subtitle_only') and subtitle_start is not None:
                                if t-subtitle_start>2: subtitle_only.append({'start':subtitle_start,'end':t})
                                subtitle_start=None
                            frame=page.screenshot(type="jpeg",quality=92,animations="disabled",caret="hide",timeout=15000)
                        elif static_frame:
                            buf=io.BytesIO();Image.fromarray(static_frame(t)).save(buf,format="JPEG",quality=92);frame=buf.getvalue()
                        else:
                            raise ValueError("Thiếu callback renderer tĩnh cho mẫu không hỗ trợ motion.")
                        process.stdin.write(frame)
                        now=time.perf_counter()
                        if now-last>.5 or i==count-1:
                            elapsed=now-started;remaining=elapsed/(i+1)*(count-i-1)
                            notify((i+1)/count,f"Motion cảnh {scene.spec.id}: {i+1}/{count} khung · còn khoảng {remaining:.0f}s")
                            last=now
                    process.stdin.close()
                    code=process.wait(timeout=90)
                    if code:
                        errors.seek(0);raise RuntimeError("FFmpeg motion: "+errors.read().decode("utf-8",errors="replace")[:2000])
                finally:
                    if process.poll() is None: process.kill();process.wait(timeout=15)
                quality=[]
                for index,shot in enumerate(payload["shots"],1):
                    if shot["template"] not in SUPPORTED: continue
                    cues=[b["at_sec"] for b in shot["beats"] if b.get("at_sec") is not None and (b["action"].startswith("reveal") or b["action"].startswith("count_end") or b["action"]=="replace_value")]
                    sample=min(shot["start"]+shot["duration"]-.23,max(shot["start"]+min(.65,shot["duration"]*.5),max(cues,default=shot["start"])+.17))
                    page.evaluate("t => renderAt(t)",max(shot["start"],sample))
                    check=page.evaluate("() => checkMotionQuality()")
                    quality.append(dict(check,shot_id=index,template=shot["template"],rule_id="motion_layout",group=3))
            replace_file_retry(temporary,destination)
            if subtitle_start is not None and scene.duration-subtitle_start>2: subtitle_only.append({'start':subtitle_start,'end':scene.duration})
            result={"path":str(destination),"cache_hit":False,"scene_id":scene.spec.id,"width":size[0],"height":size[1],
                "fps":fps,"duration_sec":scene.duration,"render_seconds":round(time.perf_counter()-started,3),
                "size_bytes":destination.stat().st_size,"sha256":hashlib.sha256(destination.read_bytes()).hexdigest(),"timing_source":payload["timing_source"],
                'illustration':{'scene_type':(payload.get('visual_plan') or {}).get('scene_type','text_focus'),'coverage_sec':min(scene.duration,illustrated_frames/fps),'moving_elements_min':min(moving_counts,default=0),'subtitle_only_intervals':subtitle_only},
                "layout_audit":layout_audit,"audit_failed":not audit_passed,"audit_retries":audit_retries,
                "quality":quality,"repair_notes":payload["repair_notes"]+(["motion_layout nhóm 2: fit thẻ theo nội dung, co chữ và dời caption trong một lượt layout."] if payload_repaired else []),"review_frame":str(review_path)}
            write_json_atomic(meta,result)
            return result
    except Exception as error:
        if diagnostics: diagnostics.record_exception(error,f"Motion cảnh {scene.spec.id}: dùng renderer Pillow dự phòng")
        notify(1.,f"Motion cảnh {scene.spec.id} chưa dùng được; chuyển đồ họa Pillow hiện có")
        return None
    finally:
        if temporary: discard_temp_file(temporary)