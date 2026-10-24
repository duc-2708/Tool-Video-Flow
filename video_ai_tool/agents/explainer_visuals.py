"""Ideas, not camera suffixes, drive stock queries and graphics in v2."""
import math
import re
from schemas.visual import Visual,VisualData
from agents.broll_queries import BRANDS,latin

VIEWS={"aerial","wide","closeup","night","daylight","panoramic","interior","exterior","detail","documentary","sunset","morning"}


def semantic_query(value,context=""):
    vi={"ngan","hang","nhan","su","cong","nghe","phong","ho","so","du","lieu","may","tinh","vu","viec","lam","cua","cac","mot","va","la","voi","cho","khong"}
    words=list(dict.fromkeys(w for w in re.findall(r"[a-z]+",latin(value)) if w not in BRANDS and w not in VIEWS and w not in vi))[:4]
    return " ".join(words) if len(words)>=2 else contextual_queries(context,1)[0]


def contextual_queries(text,count):
    # Semantic clusters are selected by the current paragraph, never a global rotating pool.
    cues=[(r"hồ sơ|giấy tờ|thủ tục|documents",["employee sorting documents","automated document processing","customer application review"]),
        (r"đào tạo|học|kỹ năng|training",["employee training classroom","colleague teaching computer","professional learning workshop"]),
        (r"nhân sự|việc làm|người|vai trò|đội ngũ|employee",["office employee discussion","human resources meeting","employee organizing workspace"]),
        (r"ngân hàng|tín dụng|vay|bank",["bank teller counter","customer loan application","financial analyst meeting"]),
        (r"dữ liệu|phần mềm|tự động|công nghệ|máy|computer",["automated document processing","computer data processing","engineer checking system"]),
        (r"bánh|bếp|quán|cỗ máy|dây chuyền",["baker preparing ingredients","kitchen workflow planning","worker checking production"])]
    choices=[]
    for pattern,queries in cues:
        if re.search(pattern,text,re.I): choices.extend(q for q in queries if q not in choices)
    if not choices:
        from agents.broll_queries import keywords
        base=keywords(text)
        choices=[base if len(base.split())>=2 else "person explaining concept"]
    # If the idea has only one visual, keep its query and change graphics, not a fake new camera angle.
    return [choices[min(i,len(choices)-1)] for i in range(count)]


def build_v2_shots(plan,brief):
    from schemas.edit_plan import Shot
    from agents.visual_planner import number_detail,excerpt
    all_ids=list(dict.fromkeys(i for scene in plan.scenes for sentence in scene.sentences for i in sentence.fact_ids))
    sources=list(dict.fromkeys(brief.facts[i-1].source_name for i in all_ids if 1<=i<=len(brief.facts)))
    mean=plan.style_profile.shot_seconds.mean if plan.style_profile else 3.1
    if plan.style_profile and plan.style_profile.shots_per_10_sec>0: mean=(mean+10/plan.style_profile.shots_per_10_sec)/2
    mean=max(2.5,min(3.5,mean))
    used=set()
    speed=max(2.5,min(3.,plan.style_profile.speech_words_per_sec.mean if plan.style_profile else 2.7))
    for scene in plan.scenes:
        duration=max(2.5,len(scene.narration.split())/speed+.8)
        duration=max(duration,math.ceil(duration/4)*2.5)
        count=max(math.ceil(duration/4),min(max(1,round(duration/mean)),max(1,math.floor(duration/2.5))))
        old=[s.query for s in scene.shots]
        old_cards=[(s.card_text,s.emphasis) for s in scene.shots]
        queries=contextual_queries(scene.narration,count)
        lengths=[len(s.text.split()) for s in scene.sentences];total=sum(lengths) or 1
        shots=[]
        for index in range(count):
            midpoint=(index+.5)/count*total;accum=0;sentence=scene.sentences[-1]
            for part,length in zip(scene.sentences,lengths):
                accum+=length
                if midpoint<=accum: sentence=part;break
            q=contextual_queries(sentence.text+" "+brief.topic,count)[index]
            if q in used:
                alternatives=contextual_queries(sentence.text+" "+scene.narration,count+2)
                q=next((a for a in alternatives if a not in used),q)
            used.add(q)
            from agents.presentation import card_phrase
            card,emphasis=old_cards[index] if index<len(old_cards) else (None,[])
            card=card_phrase(card or "",sentence.text)
            data=VisualData(text=card,highlight=emphasis or card.split()[-2:],fact_ids=sentence.fact_ids[:])
            name="hook_card" if scene is plan.scenes[0] and index==0 else "text_focus"
            kind=sentence.type
            if kind=="event" and sentence.fact_ids and (number:=number_detail(sentence.text)) and name!="hook_card":
                name="stat_card";data.value,data.number_text,data.unit=number;data.label=card
                data.source=brief.facts[sentence.fact_ids[0]-1].source_name
            elif len(scene.sentences)>=2 and scene.information_kind in {"mechanism","cause"} and index%2:
                name="steps_list";data.items=[card_phrase("",s.text) for s in scene.sentences[:4]]
                # Do not mix a grounded event into a background card's free text.
                data.items=[card_phrase("",s.text) for s in scene.sentences if s.type==kind][:4]
                if len(data.items)<2: name="text_focus";data.items=[]
            visual=Visual(template=name,data=data,content_type=kind,sentence_index=scene.sentences.index(sentence)+1,auto_generated=True)
            shots.append(Shot(type="stock_video",semantic_query=True,query=q,planning_duration=True,duration_sec=duration/count,effect="zoom_in",text_overlay=None,visual=visual,card_text=card,emphasis=data.highlight))
        scene.shots=shots
    slots=[(s,shot) for s in plan.scenes for shot in s.shots]
    if sources and len(slots)>2:
        for position in (len(slots)-1,):
            _,shot=slots[position]
            f=brief.facts[all_ids[0]-1]
            shot.visual=Visual(template="source_card",content_type="event",auto_generated=True,
                data=VisualData(source=" · ".join(sources[:2]),source_url=str(f.source_url),date=f.published_at or "",fact_ids=all_ids))
    from agents.presentation import normalize_cards,source_card_once
    source_card_once(plan,brief);normalize_cards(plan,brief)
    from agents.visual_diversity import select_templates
    select_templates(plan,brief)
    plan.target_duration_sec=plan.duration_sec
    return plan
