"""Group-2 presentation timing AFTER audio; never changes a factual claim."""
import math
import re
import unicodedata
from schemas.visual import VisualBeat
from utils.word_timing import align_words,read_words,timing_source


def token(text):
    text=unicodedata.normalize("NFD",str(text).casefold()).replace("đ","d")
    return "".join(c for c in text if c.isalnum() and not unicodedata.combining(c))


def max_gap(beats,duration):
    points=sorted({0.,float(duration),*(max(0.,min(duration,b["at_sec"])) for b in beats if b.get("at_sec") is not None)})
    return max((b-a for a,b in zip(points,points[1:])),default=0.)


def shot_beats(shot,words,start,duration,*,purpose="",pace=3.):
    """All seconds/indexes are scene-local. Match the whole phrase, then tokens.

    A missing keyword is explicitly distributed; no claim of speech alignment.
    """
    end=start+duration;visual=shot.visual
    if visual is None: return [],[]
    notes=[];matches=[];aligned=set()
    data=visual.data
    items=data.items if visual.template in {"steps_list","timeline","progress_tracker"} else [b.label for b in data.bars] if visual.template in {"compare_bars","line_growth","strike_replace","versus"} and data.bars else data.items if visual.template=="versus" else []
    keys=[shot.card_text or data.text or data.label,*items]
    normalized=[token(w["text"]) for w in words]
    for key in keys:
        terms=[token(w) for w in str(key).split() if token(w)]
        found=None
        for i in range(len(words)):
            if terms and normalized[i:i+len(terms)]==terms and start-.2<=words[i]["start"]<end: found=i;break
        if found is None:
            candidates=[i for i,w in enumerate(words) if start<=w["start"]<end and normalized[i] in terms and len(normalized[i])>2]
            if candidates: found=candidates[0]
        matches.append(found)
        if found is None and key: notes.append(f"motion_beats nhóm 2: không khớp từ khóa {str(key)!r}; chia nhịp theo shot.")
    beats=[]
    for index,key in enumerate(keys):
        if not key: continue
        match=matches[index]
        # Independently find matching tokens when one item had no phrase match.
        if match is None:
            terms={token(w) for w in str(key).split()}
            match=next((i for i,w in enumerate(words) if start<=w["start"]<end and token(w["text"]) in terms and len(token(w["text"]))>2),None)
        at=words[match]["start"] if match is not None else start+index*min(pace,duration/max(1,len(keys)))
        action="reveal" if index==0 else f"reveal_item_{index-1}"
        beats.append({"at_sec":round(max(start,min(end-1e-4,at)),6),"at_word_index":match,"action":action})
        if match is not None: aligned.add(action)
    numeric=next((i for i,w in enumerate(words) if start<=w["start"]<end and re.search(r"\d",w["text"])),None)
    if data.value is not None or visual.template in {"ring_percent","stat_card","line_growth","compare_bars","strike_replace"}:
        beats.append({"at_sec":words[numeric]["start"] if numeric is not None else start,"at_word_index":numeric,"action":"count_up"})
        if numeric is not None: beats.append({"at_sec":min(end-1e-4,words[numeric]["end"]),"at_word_index":numeric,"action":"count_end"})
    from agents.director_numbers import normalized_numbers
    targets=[("",data.value)] if data.value is not None else []
    targets.extend((f"_item_{i}",bar.value) for i,bar in enumerate(data.bars))
    for suffix,value in targets:
        found=None
        for i,w in enumerate(words):
            if not start<=w["start"]<end: continue
            for width in (1,2,3):
                span=words[i:i+width]
                if span[-1]["end"]>end+.001: continue
                numbers=normalized_numbers(" ".join(x["text"] for x in span),ignore_current_year=False)
                if any(abs(float(n.rstrip("%"))-value)<1e-6 for n in numbers): found=(i,span[-1]["end"]);break
            if found: break
        if found:
            action="count_up"+suffix;beats=[b for b in beats if b["action"] not in {action,"count_end"+suffix}]
            beats.extend([{"at_sec":words[found[0]]["start"],"at_word_index":found[0],"action":action},
                {"at_sec":min(end-1e-4,found[1]),"at_word_index":found[0],"action":"count_end"+suffix}])
            aligned.update((action,"count_end"+suffix))
            if data.value is None and suffix=="_item_0":
                beats=[b for b in beats if b["action"] not in {"count_up","count_end"}]
                beats.extend([{"at_sec":words[found[0]]["start"],"at_word_index":found[0],"action":"count_up"},
                    {"at_sec":min(end-1e-4,found[1]),"at_word_index":found[0],"action":"count_end"}]);aligned.update(("count_up","count_end"))
            if visual.template=="strike_replace" and suffix=="_item_1": beats.append({"at_sec":words[found[0]]["start"],"at_word_index":found[0],"action":"replace_value"})
    for i in range(len(words)-1):
        if start<=words[i]["start"]<end and (token(words[i]["text"]),token(words[i+1]["text"])) in {("thay","vi"),("khong","phai")}:
            beats.append({"at_sec":words[i]["start"],"at_word_index":i,"action":"strike_replace"})
    # Preserve valid authored actions; strip invalid seconds/indexes locally.
    for beat in visual.beats:
        if beat.action in aligned:
            target=next(b["at_sec"] for b in beats if b["action"]==beat.action)
            if beat.at_sec is not None and abs(beat.at_sec-target)>.2:
                notes.append(f"motion_beats nhóm 2: căn lại beat {beat.action} cũ từ {beat.at_sec:.3f}s về {target:.3f}s theo từ đã khớp.")
            continue
        at=beat.at_sec
        if at is None and beat.at_word_index is not None and 0<=beat.at_word_index<len(words): at=words[beat.at_word_index]["start"]
        if at is not None and math.isfinite(at) and start<=at<end: beats.append({"at_sec":at,"at_word_index":beat.at_word_index,"action":beat.action})
    state="surprised" if purpose=="hook" else "thinking" if re.search("phản|hệ quả|ý nghĩa|kết|cta",purpose,re.I) else "point"
    beats.append({"at_sec":start+min(.55,duration*.5),"action":"mascot_"+state})
    points=sorted({start,end,*[b["at_sec"] for b in beats]})
    for a,b in zip(points,points[1:]):
        if b-a>3.5:
            n=math.ceil((b-a)/min(3.,max(.5,pace)))
            beats.extend({"at_sec":a+(b-a)*i/n,"action":"refresh"} for i in range(1,n))
    return sorted({(round(b["at_sec"],6),b["action"]):b for b in beats}.values(),key=lambda b:b["at_sec"]),notes


def prepare_motion_beats(timeline):
    plan=timeline.plan;notes=[]
    profile=getattr(plan,"style_profile",None)
    pace=getattr(getattr(profile,"shot_seconds",None),"mean",3.)
    density=getattr(profile,"shots_per_10_sec",0)
    if density: pace=min(pace,10/density)
    for scene in timeline.scenes:
        words,method=align_words(scene.spec.narration,scene.duration,read_words(scene.audio.with_suffix(".words.json")))
        for shot in scene.shots:
            if not shot.spec.visual or shot.spec.visual.template=="stock": continue
            beats,fixes=shot_beats(shot.spec,words,shot.start-scene.start,shot.duration,purpose=scene.spec.role,pace=min(3.,max(.5,pace)))
            shot.spec.visual.beats=[VisualBeat.model_validate(b) for b in beats]
            notes.extend(f"Cảnh {scene.spec.id}, shot {shot.shot_id}: {n}" for n in fixes)
        origin=timing_source(scene.audio.with_suffix(".words.json"))
        if origin!="word_boundary" or method!="word_boundary":
            notes.append(f"Cảnh {scene.spec.id}: timing từ {origin}/{method}; beats khớp sidecar, chưa chứng minh sai số audio ≤0,2s.")
    for note in dict.fromkeys(notes):
        if note not in plan.review_notes: plan.review_notes.append(note)
    return list(dict.fromkeys(notes))


def resolved_beats(plan,manifest,project):
    from types import SimpleNamespace as NS
    records={s.scene_id:s for s in manifest.scenes};scenes=[];clock=0.
    for scene in plan.scenes:
        record=records.get(scene.id)
        if not record or not record.audio_path: continue
        duration=record.audio_duration_sec;local=0.;shots=[]
        for index,shot in enumerate(scene.shots,1):
            length=duration*shot.duration_sec/scene.duration_sec
            shots.append(NS(spec=shot,start=clock+local,duration=length,shot_id=index));local+=length
        scenes.append(NS(spec=scene,audio=project/record.audio_path,duration=duration,start=clock,shots=shots));clock+=duration
    return prepare_motion_beats(NS(plan=plan,scenes=scenes))
