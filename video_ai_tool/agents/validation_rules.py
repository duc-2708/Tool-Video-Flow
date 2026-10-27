"""Director policy registry: only effective group 1 may raise/retry Gemini.

Checks return findings; repairs contain no model/network calls. Add a Rule row
to RULES to register a new check, repair and default group in every validator.
"""
from dataclasses import dataclass,field
from collections import Counter
from pathlib import Path
import math
import re
import unicodedata
import yaml
from config.settings import ROOT_DIR
from schemas.validation import ValidationEvent

DEFAULT_VALIDATION=ROOT_DIR/"config/validation.yaml"

@dataclass
class Finding:
    scene_id: int | None
    message: str

@dataclass
class Context:
    obj: object
    brief: object
    request: object = None
    blueprint: list | None = None
    phase: str = "plan"
    diagnostics: object = None
    audit_issues: list = field(default_factory=list)
    check_style: bool = True
    style_cache: dict | None = None
    allow_merge: bool = True
    @property
    def outline(self): return self.obj if self.phase=="outline" else self.obj.story_outline
    @property
    def plan(self): return None if self.phase=="outline" else self.obj

@dataclass(frozen=True)
class Rule:
    id: str
    group: int
    description: str
    check: object
    repair: object = None

class RuleViolation(ValueError):
    def __init__(self,events):
        self.events=events
        self.scene_ids={e.scene_id for e in events if e.scene_id is not None}
        super().__init__("; ".join((f"Cảnh {e.scene_id}" if e.scene_id is not None else "Video")+f" [{e.rule_id}, nhóm 1]: {e.message}" for e in events))

def groups(path=None):
    result={r.id:r.group for r in RULES}
    source=Path(path or DEFAULT_VALIDATION)
    if source.exists():
        document=yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        for key,value in document.get("rules",{}).items():
            group=value.get("group") if isinstance(value,dict) else value
            if key not in result or type(group) is not int or group not in (1,2,3):
                raise RuleViolation([ValidationEvent(rule_id="schema_basic",group=1,action="error",message=f"Cấu hình validation không hợp lệ: {key}; cần ID đã đăng ký và group 1/2/3.")])
            result[key]=group
    return result

def sid(scene): return getattr(scene,"id",getattr(scene,"scene_id",None))
def fact_text(fact): return fact.fact_vi or fact.claim
def textkey(text):
    text=unicodedata.normalize("NFKD",text.casefold().replace("đ","d"))
    return " ".join(re.findall(r"[a-z0-9]+","".join(c for c in text if not unicodedata.combining(c))))
STOP=set("tai sao vi nhu the nao la cua va mot nhung cac co duoc khong thi khi nay do voi trong cho de ban minh gi viec tu hay truoc sau dau theo chuyen dieu".split())
def terms(text): return set(textkey(text).split())-STOP
def related(text,fact): return len(terms(text)&terms(fact_text(fact)))

def emit(ctx,rule,group,finding,action):
    message=ctx.diagnostics.redact(finding.message) if ctx.diagnostics else finding.message
    event=ValidationEvent(rule_id=rule.id,group=group,scene_id=finding.scene_id,phase=ctx.phase,action=action,message=message)
    if event not in ctx.obj.validation_events: ctx.obj.validation_events.append(event)
    label=f"[{rule.id}, nhóm {group}, {action}] {message}"
    if ctx.plan:
        if finding.scene_id is None:
            if label not in ctx.plan.review_notes: ctx.plan.review_notes.append(label)
        else:
            scene=next((s for s in ctx.plan.scenes if s.id==finding.scene_id),None)
            if scene:
                from schemas.edit_plan import ReviewNotes
                if scene.review_notes is None: scene.review_notes=ReviewNotes(fact_ids=scene.fact_ids,source_count=0,confidence=None,facts=[])
                if label not in scene.review_notes.warnings: scene.review_notes.warnings.append(label)
    if ctx.diagnostics: ctx.diagnostics.record(f"đối tượng={finding.scene_id or 'video'} "+label)
    return event

def fact_ids(ctx):
    issues=[]
    for scene in ctx.obj.scenes:
        invalid=[i for i in scene.fact_ids if type(i) is not int or not 1<=i<=len(ctx.brief.facts)]
        if invalid: issues.append(Finding(sid(scene),f"fact_id không tồn tại: {invalid}."))
        from agents.explainer_guard import is_v2
        if not scene.fact_ids and not is_v2(ctx.obj) and (ctx.phase=="outline" or scene.role!="cta"):
            issues.append(Finding(sid(scene),"Cảnh nội dung có 0 fact tham chiếu."))
    return issues

def unsupported_numbers(ctx):
    if not ctx.plan: return []
    from agents.director_numbers import normalized_numbers
    from utils.source_credits import publisher_name
    from agents.director_sources import canonical_sources,number_names
    allowed=normalized_numbers(" ".join(fact_text(f) for f in ctx.brief.facts),ignore_current_year=False)
    issues=[]
    for scene in ctx.plan.scenes:
        from agents.explainer_guard import is_v2,event_text
        from agents.visual_policy import content_type
        content=canonical_sources(event_text(scene) if is_v2(ctx.plan) else scene.narration,ctx.brief)+". "+". ".join(s.text_overlay or "" for s in scene.shots if not is_v2(ctx.plan) or content_type(scene,s)=="event")
        for name in number_names(ctx.brief):
            content=re.sub(r"\bTheo\s+"+re.escape(name)+r"(?=[,\s])[,\s]*","",content,flags=re.I)
            content=re.sub(r"(?<!\w)"+re.escape(name)+r"(?!\w)"," ",content,flags=re.I)
        # Hypothetical exemption is per sentence, explicitly spoken to viewers.
        parts=re.split(r"(?<=[!?;])\s+|(?<=[.])\s+(?=[A-ZÀ-Ỹ])",content)
        asserted=" ".join(p for p in parts if not re.match(r"\s*(?:giả sử|giả định|ví dụ minh họa)\b",p,re.I))
        actual=normalized_numbers(asserted,ignore_current_year=False)
        from validation.grounding import numbers_match, get_grounding_mode, repair_grounding
        missing=[a for a in actual if not any(numbers_match(a, al) for al in allowed)]
        if ctx.diagnostics: ctx.diagnostics.record(f"đối tượng=cảnh {scene.id}, luật=grounding_numbers, số={sorted(actual)}, tập số brief={sorted(allowed)}")
        if missing:
            issues.append(Finding(scene.id,f"Số liệu không có trong brief và chưa đánh dấu giả định: {sorted(missing)}; số hợp lệ: {sorted(allowed)}."))
    return issues

def fix_grounding_numbers(ctx):
    if not ctx.plan: return ""
    from validation.grounding import repair_grounding
    fixes = repair_grounding(ctx.plan, ctx.brief)
    return "; ".join(fixes) if fixes else "Đã tự sửa số liệu theo căn cứ fact."


ORDINARY=set("Bạn Mình Theo Nhưng Đầu Sau Riêng Còn Ở Chỗ Điểm Với Đến Nhìn Mạch Chọn Người Các Công Thành Một Hai Không Tại Số Nội Năm Hãy Đây Đó Vì Vậy Khi Nếu Cách Phần Dựng Trong Cắt Ghép Video Chào Có Thử Vấn Từ Trước Giả Ví Kết Bước Giữ Sắp Tốc Tư Làm Kiểm Bắt Cảnh Nguồn Nhịp Bản Thông Việc Về Dữ Nó Điều So Cuối Ta Chúng Xem Như Thế Trên Và Để TTS Khoảng Hơn Nhiều Hiện Đợt Sự Mức Dường Khả Đặc Toàn Tỷ Triệu Hàng Mỗi Bản Giữa Ngay Lúc Ngoài Dù Mặc Do Bởi Nhờ Tuy Rằng Cứ Đã Đang Sẽ Vừa Vẫn Cùng".split())
from agents.proper_names import proper_names

def names_quotes(ctx):
    if not ctx.plan: return []
    from utils.source_credits import publisher_name
    from agents.director_sources import allowed_sources,source_key,canonical_sources
    source_names={source_key(n) for n in allowed_sources(ctx.brief)}
    base=ctx.brief.topic+" "+" ".join(fact_text(f)+" "+f.claim+" "+(f.evidence_quote or "")+" "+f.source_name+" "+publisher_name(f.source_url) for f in ctx.brief.facts)
    allowed=textkey(base);issues=[]
    for scene in ctx.plan.scenes:
        from agents.explainer_guard import is_v2,event_text
        from agents.visual_policy import content_type
        fields=[s.text for s in scene.sentences if s.type=="event"] if is_v2(ctx.plan) else [scene.narration]
        fields.extend(s.text_overlay for s in scene.shots if s.text_overlay and (not is_v2(ctx.plan) or content_type(scene,s)=="event"))
        for part in (part for value in fields for part in re.split(r"(?<=[.!?])\s+",canonical_sources(value,ctx.brief))):
            for cited in re.findall(r"\bTheo\s+([^,]+),",part):
                if source_key(cited) not in source_names and any(source_key(name) not in source_names for name in re.split(r"\s+và\s+",cited,flags=re.I)):
                    issues.append(Finding(scene.id,f"Nguồn trích dẫn không có trong brief: {cited}."))
            part=re.sub(r"^(?:Theo [^,]+,\s*)+","",part)
            if re.match(r"\s*(?:giả sử|giả định|ví dụ minh họa)\b",part,re.I): continue
            for quote in re.findall(r'[“"]([^”"]{3,200})[”"]',part):
                if textkey(quote) not in allowed: issues.append(Finding(scene.id,f"Trích dẫn không có trong brief: {quote!r}."))
            for match in proper_names(part):
                name=match.group(0)
                if name=="Mỹ" and "đô la Mỹ" in part and re.search(r"\$|USD|đô la",base,re.I): continue
                words=name.split()
                if all(w in ORDINARY for w in words): continue
                if textkey(name) not in allowed and not all(w in ORDINARY or textkey(w) in allowed.split() for w in words):
                    from validation.grounding import entity_matches, extract_entities, get_grounding_mode
                    brief_entities = extract_entities(base, sentence_boundary=False)
                    if not any(entity_matches(name, be.raw) for be in brief_entities):
                        issues.append(Finding(scene.id,f"Tên riêng không có trong brief: {name}."))
    return issues

FORBIDDEN=r"chưa\s+(?:được\s+)?(?:kiểm\s+chứng|xác\s+minh)|cần\s+xác\s+minh"
def forbidden(ctx):
    if not ctx.plan: return []
    return [Finding(s.id,"Cụm cấm còn sót trong narration/on_screen_text.") for s in ctx.plan.scenes
        if re.search(FORBIDDEN,s.narration+" "+" ".join(x.text_overlay or "" for x in s.shots),re.I)]
def clean_forbidden(ctx):
    for s in ctx.plan.scenes:
        if s.sentences:
            from agents.explainer_guard import sync_narration
            for sentence in s.sentences: sentence.text=re.sub(FORBIDDEN,"",sentence.text,flags=re.I).strip(" ,:;-") or "Thông tin từ nguồn."
            sync_narration(ctx.plan)
        s.narration=re.sub(r"Theo\s+thông\s+tin\s+sơ\s+bộ\s+(?:"+FORBIDDEN+r")","",s.narration,flags=re.I)
        s.narration=re.sub(FORBIDDEN,"",s.narration,flags=re.I).strip(" ,:;-") or (fact_text(ctx.brief.facts[s.fact_ids[0]-1]) if s.fact_ids and 1<=s.fact_ids[0]<=len(ctx.brief.facts) else "Thông tin từ nguồn.")
        for shot in s.shots:
            if shot.text_overlay: shot.text_overlay=re.sub(FORBIDDEN,"",shot.text_overlay,flags=re.I).strip(" ,:;-") or None

def open_loop(ctx):
    from agents.explainer_guard import is_v2
    if is_v2(ctx.obj): return []  # Semantic payoff is checked by Explainer's LoopReview.
    outline=ctx.outline
    if not outline or not outline.open_loop: return []
    last=ctx.obj.scenes[-1]
    candidates=[i for i in outline.payoff_fact_ids if 1<=i<=len(ctx.brief.facts)]
    if not candidates or not set(candidates)<=set(last.fact_ids) or not any(related(outline.open_loop,ctx.brief.facts[i-1]) for i in candidates):
        return [Finding(sid(last),"Cảnh cuối chưa dùng fact giải đáp open loop.")]
    return []
def fix_open_loop(ctx):
    outline=ctx.outline;last=ctx.obj.scenes[-1]
    question=outline.open_loop
    used={i for s in ctx.obj.scenes for i in s.fact_ids}
    ranked=sorted(range(1,len(ctx.brief.facts)+1),key=lambda i:(related(question,ctx.brief.facts[i-1]),i not in used),reverse=True)
    chosen=ranked[0] if ranked and related(question,ctx.brief.facts[ranked[0]-1])>0 else None
    if chosen:
        last.fact_ids=list(dict.fromkeys(last.fact_ids+[chosen]))
        outline.payoff_fact_ids=[chosen];outline.payoff=fact_text(ctx.brief.facts[chosen-1])
        target=next((s for s in outline.scenes if s.scene_id==sid(last)),None)
        if target:
            target.fact_ids=list(last.fact_ids)
            point=next((p for p in outline.main_points if p.id==target.point_id),None)
            if point: point.fact_ids=list(dict.fromkeys(point.fact_ids+[chosen]))
        if ctx.plan and textkey(outline.payoff) not in textkey(last.narration): last.narration+=" "+outline.payoff
        return f"Đã gán fact #{chosen} có liên quan tới câu hỏi cho cảnh cuối; giữ căn cứ từ brief."
    outline.open_loop="";outline.payoff="";outline.payoff_fact_ids=[]
    outline.hook=re.sub(r"[^.!?]*\?","",outline.hook).strip() or fact_text(ctx.brief.facts[0])
    if ctx.plan:
        hook=ctx.plan.scenes[0]
        hook.narration=re.sub(r"[^.!?]*\?","",hook.narration).strip() or fact_text(ctx.brief.facts[hook.fact_ids[0]-1] if hook.fact_ids and 1<=hook.fact_ids[0]<=len(ctx.brief.facts) else ctx.brief.facts[0])
    return "Không có fact liên quan thật; đã bỏ open loop và câu hỏi khỏi hook, thay bằng fact có nguồn."

def repeated(ctx):
    from agents.explainer_guard import is_v2
    if is_v2(ctx.obj): return []
    uses=Counter(i for s in ctx.obj.scenes for i in set(s.fact_ids))
    return [Finding(sid(s),f"Fact #{i} dùng {uses[i]} lần, mục tiêu tối đa 2.") for s in ctx.obj.scenes for i in set(s.fact_ids) if uses[i]>2]
def fix_repeated(ctx):
    if not ctx.allow_merge: return "Hoãn gộp cảnh tới sau audit để giữ đúng ID khi retry; không đổi căn cứ."
    uses=Counter(i for s in ctx.obj.scenes for i in set(s.fact_ids))
    for scene in ctx.obj.scenes:
        scene.fact_ids=list(dict.fromkeys(scene.fact_ids))
        for k,i in enumerate(scene.fact_ids):
            if not 1<=i<=len(ctx.brief.facts) or uses[i]<=2: continue
            equivalent=next((j for j,f in enumerate(ctx.brief.facts,1) if j not in scene.fact_ids and uses[j]<2 and textkey(fact_text(f))==textkey(fact_text(ctx.brief.facts[i-1]))),None)
            if equivalent: scene.fact_ids[k]=equivalent;uses[equivalent]+=1;uses[i]-=1
    merged=[]
    if ctx.plan:
        while True:
            uses=Counter(i for s in ctx.obj.scenes for i in set(s.fact_ids))
            over=next((i for i,count in uses.items() if count>2),None)
            if over is None: break
            candidates=[s for s in ctx.plan.scenes if over in s.fact_ids and s.role!="hook"]
            if len(candidates)<2: break
            donor=next((s for s in candidates if s.role!="cta"),candidates[0])
            target=next(s for s in candidates if s is not donor)
            before=ctx.plan.scenes.index(donor)<ctx.plan.scenes.index(target)
            if textkey(donor.narration)!=textkey(target.narration): target.narration=(donor.narration+" "+target.narration) if before else (target.narration+" "+donor.narration)
            sentences=[];seen=set()
            for sentence in re.split(r"(?<=[.!?])\s+",target.narration):
                identity=textkey(re.sub(r"^(?:Theo [^,]+,\s*)+","",sentence))
                if identity not in seen: sentences.append(sentence);seen.add(identity)
            target.narration=" ".join(sentences)
            from utils.source_credits import publisher_name
            for name in {f.source_name if f.fact_vi else publisher_name(f.source_url) for f in ctx.brief.facts}:
                matches=list(re.finditer(r"\bTheo\s+"+re.escape(name)+r",\s*",target.narration))
                for match in reversed(matches[1:]): target.narration=target.narration[:match.start()]+target.narration[match.end():]
            target.shots=(donor.shots+target.shots) if before else (target.shots+donor.shots)
            target.fact_ids=list(dict.fromkeys(target.fact_ids+donor.fact_ids))
            ctx.plan.scenes.remove(donor);merged.append(f"{donor.id} → {target.id}")
            if ctx.outline:
                ctx.outline.scenes=[s for s in ctx.outline.scenes if s.scene_id!=donor.id]
                for s in ctx.outline.scenes:
                    if s.scene_id==target.id: s.fact_ids=list(target.fact_ids)
    return "Đã khử ID trùng, ưu tiên fact tương đương; "+("gộp cảnh "+", ".join(merged)+", giữ shot/thời lượng và các khẳng định có căn cứ." if merged else "không đổi sang fact khác nghĩa; dàn ý ít fact được ghi chú, plan sẽ gộp cảnh nếu cần.")

def duration(ctx):
    if not ctx.plan or not ctx.request: return []
    from agents.explainer_guard import is_v2
    if is_v2(ctx.plan): return []
    if ctx.plan.content_timed:
        from agents.content_plan import scene_seconds
        return [Finding(s.id,"Timing cần đồng bộ với số từ lời đọc.") for s in ctx.plan.scenes if abs(s.duration_sec-scene_seconds(s))>.01 or len(s.shots)>4]
    target=ctx.plan.target_duration_sec if ctx.plan.adaptive and ctx.plan.target_duration_sec else ctx.request.duration_sec
    if abs(ctx.plan.duration_sec-target)>target*.1: return [Finding(None,f"Tổng thời lượng {ctx.plan.duration_sec:g}s lệch yêu cầu {target:g}s.")]
    return []
def fix_duration(ctx):
    if ctx.plan.content_timed:
        from agents.content_plan import fit_content_timing
        fit_content_timing(ctx.plan)
        return "Đã căn thời lượng theo số từ / 2.6 + 0.8 giây, tối thiểu 2.5 giây; tối đa 4 shot/cảnh."
    target=ctx.plan.target_duration_sec if ctx.plan.adaptive and ctx.plan.target_duration_sec else ctx.request.duration_sec
    plan=ctx.plan
    if target<1.5*len(plan.scenes):
        plan.target_duration_sec=plan.duration_sec;plan.adaptive=True
        return "Đã dùng thời lượng thực vì không thể ép mọi cảnh xuống dưới 1.5s; không xóa nội dung có căn cứ."
    hook=min(3.,target/len(plan.scenes))
    rest=sum(s.duration_sec for s in plan.scenes[1:])
    from schemas.edit_plan import Shot
    for index,scene in enumerate(plan.scenes):
        length=hook if index==0 else (target-hook)*scene.duration_sec/rest
        count=max(1,math.ceil(length/4))
        count=min(max(count,len(scene.shots)),max(1,math.floor(length/1.5)))
        scene.shots=[Shot.model_validate({**scene.shots[i%len(scene.shots)].model_dump(mode="json"),"duration_sec":length/count}) for i in range(count)]
    return f"Đã căn duration/shot bằng code về tổng {target:g}s, giữ lời đọc và fact_ids; Assets còn căn theo audio thật."

def format_issues(ctx):
    if not ctx.plan or not ctx.request: return []
    return [Finding(None,"Khổ video khác yêu cầu.")] if ctx.plan.format!=ctx.request.video_format else []
def fix_format(ctx): ctx.plan.format=ctx.request.video_format;return "Đã đồng bộ format theo cấu hình lượt chạy."

def freshness(ctx):
    if not ctx.plan or not ctx.plan.brief_hash: return []
    from agents.director import brief_hash
    return [Finding(None,"Brief đã đổi; cần kiểm tra lại căn cứ.")] if ctx.plan.brief_hash!=brief_hash(ctx.brief) else []
def rebind(ctx):
    from agents.director import brief_hash
    ctx.plan.brief_hash=brief_hash(ctx.brief)
    return "Đã cập nhật hash; mọi fact_id, số liệu, tên và trích dẫn tiếp tục được kiểm tra với brief hiện tại."

def attribution(ctx):
    if not ctx.plan: return []
    from agents.explainer_guard import is_v2
    if is_v2(ctx.plan): return []  # Source cards carry provenance, no per-beat spoken prefix.
    from agents.director import review_notes_for,has_attribution
    from agents.visual_planner import covered_sources
    covered=covered_sources(ctx.plan)
    result=[]
    for scene in ctx.plan.scenes:
        if any(not 1<=i<=len(ctx.brief.facts) for i in scene.fact_ids): continue
        notes=review_notes_for(scene.fact_ids,ctx.brief)
        required={f.sources[0].name for f in notes.facts if f.source_count==1}-covered
        if any(not has_attribution(scene.narration,name) for name in required): result.append(Finding(scene.id,"Thiếu nhãn Theo <nguồn> cho fact nguồn đơn."))
        if notes.facts and not required and any(has_attribution(scene.narration,s.name) for f in notes.facts for s in f.sources): result.append(Finding(scene.id,"Fact có nhiều nguồn; đồng bộ nhãn nêu nguồn."))
    return result
def fix_attribution(ctx):
    from agents.director import review_notes_for,has_attribution
    from agents.visual_planner import covered_sources
    covered=covered_sources(ctx.plan)
    for scene in ctx.plan.scenes:
        if any(not 1<=i<=len(ctx.brief.facts) for i in scene.fact_ids): continue
        notes=review_notes_for(scene.fact_ids,ctx.brief)
        required=list(dict.fromkeys(f.sources[0].name for f in notes.facts if f.source_count==1 and f.sources[0].name not in covered))
        if required:
            for name in required:
                if not has_attribution(scene.narration,name): scene.narration=f"Theo {name}, "+scene.narration
        else:
            for f in notes.facts:
                for source in f.sources: scene.narration=re.sub(r"\bTheo\s+"+re.escape(source.name)+r"[,\s]*","",scene.narration,flags=re.I)
    return "Đã đồng bộ cách nêu nguồn với metadata brief, không thêm claim."

def style_matching(*patterns):
    def check(ctx):
        if not ctx.plan or not ctx.check_style: return []
        from agents.story_style import style_issues
        if ctx.style_cache is None: ctx.style_cache=style_issues(ctx.plan)
        return [Finding(key,message) for key,messages in ctx.style_cache.items() for message in messages if any(p in message for p in patterns)]
    return check
def thin_scenes(ctx):
    if not ctx.plan or not ctx.request: return []
    from agents.explainer_guard import is_v2
    if is_v2(ctx.plan):
        return [Finding(None,"Explainer dưới 5 beat; dữ liệu mỏng, không ép thêm cảnh rỗng.")] if ctx.request.duration_sec>=45 and len(ctx.plan.scenes)<5 else []
    target=2 if len(ctx.brief.facts)==1 else min(len(ctx.brief.facts)+2,max(4,round(ctx.request.duration_sec/8)))
    return [Finding(None,f"Số cảnh {len(ctx.plan.scenes)} dưới mục tiêu {target}; không thêm cảnh rỗng.")] if len(ctx.plan.scenes)<target else []
def unclear_loop(ctx):
    outline=ctx.outline
    return [Finding(None,"Open loop không rõ ràng hoặc đã bỏ vì thiếu căn cứ.")] if outline and (not outline.open_loop or len(terms(outline.open_loop))<2) else []
def depth(ctx):
    if not ctx.plan: return []
    from agents.director_numbers import normalized_numbers
    has_numbers=any(normalized_numbers(fact_text(f)) for f in ctx.brief.facts)
    if has_numbers and not any(normalized_numbers(s.narration) for s in ctx.plan.scenes):
        return [Finding(None,"Brief có số liệu nhưng lời đọc thiếu ví dụ/số liệu cụ thể.")]
    return []
def structure_notes(ctx): return []  # Runs at raw JSON boundary; imported into events below.
def audit_claims(ctx): return [finding for key,finding in ctx.audit_issues if key=="grounding_claims"]


def originality(ctx):
    if not ctx.plan:
        return []
    from pipeline.style_profile import copying_scenes
    return [Finding(scene_id, f"Lời đọc giống đoạn tham chiếu {score:.0%}, vượt 60%; cần viết mới riêng cảnh, giữ fact_ids.")
            for scene_id, score in copying_scenes(ctx.plan)]

def outline_shape(ctx):
    if ctx.phase!="outline": return []
    outline=ctx.obj;ids={r["id"] for r in ctx.blueprint or []};points={p.id for p in outline.main_points}
    if ({s.scene_id for s in outline.scenes}!=ids or len(outline.scenes)!=len(ids)
        or len(points)!=len(outline.main_points) or any(s.point_id not in points for s in outline.scenes)
        or outline.angle_index>len(ctx.brief.story_angles or ctx.brief.angle_candidates)):
        return [Finding(None,"Dàn ý/blueprint/điểm/góc kể chưa đồng bộ.")]
    return []
def fix_outline_shape(ctx):
    from schemas.story import OutlineScene,StoryPoint
    outline=ctx.obj;existing={s.scene_id:s for s in outline.scenes}
    points={p.id:p for p in outline.main_points}
    if not points: points[1]=StoryPoint(id=1,idea="Thông tin từ brief",fact_ids=[1])
    outline.main_points=list(points.values())
    outline.angle_index=min(outline.angle_index,max(1,len(ctx.brief.story_angles or ctx.brief.angle_candidates)))
    result=[]
    for index,row in enumerate(ctx.blueprint or []):
        scene=existing.get(row["id"])
        if scene is None: scene=OutlineScene(scene_id=row["id"],point_id=next(iter(points)),fact_ids=[index%len(ctx.brief.facts)+1],purpose="Triển khai fact có trong brief")
        if scene.point_id not in points: scene.point_id=next(iter(points))
        points[scene.point_id].fact_ids=list(dict.fromkeys(points[scene.point_id].fact_ids+scene.fact_ids))
        result.append(scene)
    outline.scenes=result
    return "Đã đồng bộ dàn ý theo blueprint bằng code, không tạo lời đọc hay dữ kiện mới."

def title(ctx):
    if not ctx.plan: return []
    from agents.director_title import title_numbers
    result=title_numbers(ctx.plan,ctx.brief)
    if ctx.diagnostics: ctx.diagnostics.record(f"đối tượng=tiêu đề: số={sorted(result['actual'])}; tập số hợp lệ={sorted(result['allowed'])}; sai={sorted(result['invalid'])}")
    from agents.content_plan import vietnamese_title
    if not vietnamese_title(ctx.plan.title): return [Finding(None,"Tiêu đề cần viết bằng tiếng Việt.")]
    return [Finding(None,"Tiêu đề có số ngoài tập được phép.")] if result["invalid"] else []
def fix_title(ctx):
    from agents.director_title import ensure_title
    ensure_title(ctx.plan,ctx.brief,diagnostics=ctx.diagnostics)
    return "Đã sửa riêng tiêu đề bằng code/chủ đề dự phòng, giữ các cảnh."
def ai_prompt(ctx):
    if not ctx.plan: return []
    from agents.video_prompt_writer import validate_ai_prompt
    issues=[]
    for scene in ctx.plan.scenes:
        for shot in scene.shots:
            if shot.ai_prompt:
                try: validate_ai_prompt(shot.ai_prompt)
                except ValueError as error: issues.append(Finding(scene.id,str(error)))
    return issues
def fix_ai_prompt(ctx):
    from agents.video_prompt_writer import validate_ai_prompt,fallback_prompt
    for scene in ctx.plan.scenes:
        for shot in scene.shots:
            if shot.ai_prompt:
                try: validate_ai_prompt(shot.ai_prompt)
                except ValueError: shot.ai_prompt=fallback_prompt(scene.narration)
    return "Đã dùng prompt AI dự phòng an toàn, chưa gửi job trả phí."

def visual_grounding(ctx):
    if not ctx.plan: return []
    from agents.visual_planner import visual_issues
    return [Finding(scene,message) for scene,message in visual_issues(ctx.plan,ctx.brief)]

def fix_visual_grounding(ctx):
    if not ctx.plan: return ""
    from validation.grounding import repair_grounding
    fixes = repair_grounding(ctx.plan, ctx.brief)
    return "; ".join(fixes) if fixes else "Đã tự sửa đồ họa sang bản định tính trung tính theo căn cứ brief."



def visual_background(ctx):
    if not ctx.plan: return []
    from agents.visual_policy import background_warnings
    return [Finding(scene,message) for scene,message in background_warnings(ctx.plan,ctx.brief)]


def visual_structure(ctx):
    if not ctx.plan: return []
    from agents.visual_policy import repair_label_order
    return [Finding(scene,message) for scene,message in repair_label_order(ctx.plan.model_copy(deep=True))]


def fix_visual_structure(ctx):
    from agents.visual_policy import repair_label_order
    changes=repair_label_order(ctx.plan)
    return "; ".join(message for _,message in changes)


def explainer_sentences(ctx):
    if not ctx.plan: return []
    from agents.explainer_guard import sentence_issues
    return [Finding(scene,message) for scene,message in sentence_issues(ctx.plan,ctx.brief)]


def fix_explainer_names(ctx):
    from agents.explainer_guard import repair_event_names, repair_cta_sentences
    repaired=repair_event_names(ctx.plan,ctx.brief)
    cta_repaired=repair_cta_sentences(ctx.plan,ctx.brief)
    all_repaired=[*repaired, *cta_repaired]
    if all_repaired:
        # Keep automatically generated graphics in sync with the repaired sentence.
        for scene in ctx.plan.scenes:
            for shot in scene.shots:
                visual=shot.visual
                if not visual or not visual.auto_generated or not visual.sentence_index: continue
                if visual.sentence_index>len(scene.sentences): continue
                sentence=scene.sentences[visual.sentence_index-1]
                if sentence.type!="event": continue
                from schemas.visual import VisualData
                from agents.visual_planner import excerpt
                visual.template="text_focus"
                visual.data=VisualData(text=excerpt(sentence.text,18),fact_ids=sentence.fact_ids[:])
                shot.text_overlay=None
    return "; ".join(f"Cảnh {sid}: {message}" for sid,message in all_repaired)


def explainer_background_names(ctx):
    if not ctx.plan: return []
    from agents.explainer_guard import sentence_background_warnings
    return [Finding(scene,message) for scene,message in sentence_background_warnings(ctx.plan,ctx.brief)]


def card_text_shape(ctx):
    if not ctx.plan: return []
    from agents.presentation import normalize_cards
    return [Finding(s,m) for s,m in normalize_cards(ctx.plan.model_copy(deep=True),ctx.brief)]


def fix_card_text(ctx):
    from agents.presentation import normalize_cards
    return "; ".join(m for _,m in normalize_cards(ctx.plan,ctx.brief,diagnostics=ctx.diagnostics))


def presentation_voice(ctx):
    if not ctx.plan: return []
    from agents.presentation import quality_findings
    return [Finding(s,m) for s,m in quality_findings(ctx.plan)]


# Single source of rule IDs, default groups, checks and local repair functions.
RULES=(
    Rule("card_text",2,"Thẻ 3–6 từ, emphasis 1–2 từ; không cắt lời đọc",card_text_shape,fix_card_text),
    Rule("presentation_voice",3,"Hạn chế rào đón lặp và hook câu hỏi chung",presentation_voice),
    Rule("sentence_grounding",1,"Nhãn câu khớp lời đọc; event có fact, nền không giả làm sự kiện",explainer_sentences,fix_explainer_names),
    Rule("sentence_background_names",3,"Tên riêng trong ví dụ nền chỉ cảnh báo",explainer_background_names),
    Rule("visual_structure",2,"Giữ nhãn đồ họa đúng thứ tự lời đọc",visual_structure,fix_visual_structure),
    Rule("visual_grounding",1,"Số liệu, tên, ngày, URL trong đồ họa có căn cứ brief",visual_grounding,fix_visual_grounding),
    Rule("visual_background",3,"Ví dụ nền trong đồ họa cần kiểm tra, không chặn",visual_background),
    Rule("schema_basic",1,"JSON/schema cơ bản không sửa được",structure_notes),
    Rule("outline_structure",2,"Đồng bộ dàn ý/blueprint",outline_shape,fix_outline_shape),
    Rule("open_loop",2,"Gán fact payoff liên quan hoặc bỏ câu hỏi",open_loop,fix_open_loop),
    Rule("fact_ids",1,"ID fact hợp lệ; cảnh nội dung có căn cứ",fact_ids),
    Rule("forbidden_editorial",1,"Cụm kiểm chứng bị cấm còn sót sau xóa",forbidden,clean_forbidden),
    Rule("grounding_numbers",1,"Số liệu trong lời đọc/overlay có trong brief hoặc giả định rõ",unsupported_numbers,fix_grounding_numbers),
    Rule("grounding_names_quotes",1,"Tên riêng/trích dẫn có căn cứ",names_quotes),
    Rule("grounding_claims",1,"Khẳng định/nhân quả được audit đối chiếu fact",audit_claims),
    Rule("originality",1,"Không sao chép lời đọc video mẫu",originality),
    Rule("shot_structure",2,"Chuẩn hóa mảng/shot/role/schema trình bày",structure_notes),
    Rule("broll_query",2,"Query stock hợp lệ và khác nhau",structure_notes),
    Rule("ai_prompt",2,"Chuẩn hóa prompt AI trước khi cho gọi gateway",ai_prompt,fix_ai_prompt),
    Rule("title",2,"Tiêu đề cấp video hợp lệ",title,fix_title),
    Rule("duration",2,"Căn tổng thời lượng bằng code",duration,fix_duration),
    Rule("format",2,"Đồng bộ format",format_issues,fix_format),
    Rule("brief_binding",2,"Cập nhật metadata brief và kiểm tra lại",freshness,rebind),
    Rule("attribution",2,"Định dạng nguồn Theo ...",attribution,fix_attribution),
    Rule("fact_reuse",2,"Giảm lặp ID, ưu tiên fact tương đương",repeated,fix_repeated),
    Rule("hook_length",3,"Độ dài hook",style_matching("Hook quá dài")),
    Rule("hook_strength",3,"Hook hấp dẫn/cách mở",style_matching("Hook cần","Hook dùng")),
    Rule("cliches",3,"Cụm sáo rỗng",style_matching("sáo rỗng")),
    Rule("sentence_length",3,"Câu dài/cấu trúc câu",style_matching("28 từ","2–4 câu")),
    Rule("transitions",3,"Chuyển ý/mở cảnh bị lặp",style_matching("Lạm dụng","cùng cấu trúc")),
    Rule("repeated_ideas",3,"Lặp lời/ý",style_matching("Lặp nguyên")),
    Rule("pattern_interrupt",3,"Thiếu pattern interrupt",style_matching("pattern interrupt")),
    Rule("ending_style",3,"Kết video đúng kiểu",style_matching("Kết bằng")),
    Rule("word_budget",3,"Lượng từ lệch quá khoảng ±20%",style_matching("Tổng ","Lượng chữ")),
    Rule("tts_format",3,"Cách đọc số/đơn vị/viết tắt",style_matching("Viết số")),
    Rule("overlay_style",3,"Độ dài/ý nghĩa overlay",style_matching("Overlay phải")),
    Rule("examples",3,"Thiếu ví dụ/số liệu cụ thể",depth),
    Rule("open_loop_clarity",3,"Câu hỏi mở không rõ",unclear_loop),
    Rule("scene_target",3,"Số cảnh dưới mục tiêu",thin_scenes),
    Rule("audit_clarity",3,"Audit không giải thích kết luận",structure_notes),
)

def run_rules(obj,brief,request=None,*,phase="plan",blueprint=None,diagnostics=None,config_path=None,check_style=True,audit_issues=None,allow_merge=True):
    ctx=Context(obj,brief,request,blueprint,phase,diagnostics,audit_issues or [],check_style)
    ctx.allow_merge=allow_merge and not getattr(obj,"content_timed",False)
    policy=groups(config_path);hard=[]
    # Metadata must remain valid even when a fact rule is configured as warning.
    for rule in RULES:
        if rule.id=="fact_reuse" and (hard or not allow_merge): continue  # Keep scene IDs until factual audit is complete.
        findings=rule.check(ctx)
        if findings and rule.repair:
            result=rule.repair(ctx)
            remaining=rule.check(ctx)
            if rule.id!="sentence_grounding" or result:
                for item in findings: emit(ctx,rule,policy[rule.id],Finding(item.scene_id,result or "Đã tự sửa bằng code."),"fixed")
            findings=remaining
        from validation.grounding import get_grounding_mode, repair_grounding
        grounding_mode = get_grounding_mode()
        grounding_auto_repair_rules = {"visual_grounding", "grounding_numbers"}
        if findings and rule.id in grounding_auto_repair_rules:
            if grounding_mode == "fix":
                if ctx.plan:
                    repair_grounding(ctx.plan, ctx.brief)
                findings = rule.check(ctx)
                if findings:
                    for item in findings:
                        emit(ctx, rule, 3, Finding(item.scene_id, f"[grounding, tự sửa] {item.message}"), "warning")
                    continue
            elif grounding_mode == "warn":
                for item in findings:
                    emit(ctx, rule, 3, item, "warning")
                continue
        for item in findings:
            event=emit(ctx,rule,policy[rule.id],item,"error" if policy[rule.id]==1 else "warning")
            if policy[rule.id]==1: hard.append(event)
    if ctx.plan:
        from agents.director import review_notes_for
        # Drafts/checkpoints retain old diagnostics. Resolved false positives
        # must not remain visible as active group-1 errors after revalidation.
        unresolved={f.scene_id for f in explainer_sentences(ctx)}
        obj.validation_events=[e for e in obj.validation_events if not
            (e.rule_id=="sentence_grounding" and e.action=="error" and e.scene_id not in unresolved)]
        for scene in obj.scenes:
            previous=list(scene.review_notes.warnings) if scene.review_notes else []
            if scene.id not in unresolved:
                previous=[w for w in previous if not w.startswith("[sentence_grounding, nhóm 1, error]")]
            scene.review_notes=review_notes_for(scene.fact_ids,brief)
            scene.review_notes.warnings=list(dict.fromkeys(previous+scene.review_notes.warnings))
            for message in list(scene.review_notes.warnings if scene.review_notes else []):
                if not message.startswith("[") and ("chuẩn hóa cấu trúc" in message or "sửa b-roll query" in message):
                    rule=next(r for r in RULES if r.id==("broll_query" if "query" in message else "shot_structure"))
                    emit(ctx,rule,policy[rule.id],Finding(scene.id,message),"fixed")
    for key,item in ctx.audit_issues:
        if key=="grounding_claims": continue
        rule=next(r for r in RULES if r.id==key)
        event=emit(ctx,rule,policy[key],item,"error" if policy[key]==1 else "warning")
        if policy[key]==1: hard.append(event)
    if hard: raise RuleViolation(hard)
    return obj

def audit_findings(issues):
    result=[]
    for issue in issues:
        message=issue if isinstance(issue,str) else issue.reason
        scene_id=getattr(issue,"scene_id",None)
        if scene_id is None:
            match=re.search(r"[Cc]ảnh\s*#?\s*(\d+)",message)
            if match: scene_id=int(match[1])
        lower=message.casefold()
        explicit=re.search(r"\[([a-z_]+)\]",lower)
        key=explicit[1] if explicit and explicit[1] in {r.id for r in RULES} else None
        if not key:
            mapping=[("open_loop_clarity",("open loop","open_loop","payoff","câu hỏi mở")),
                ("hook_length",("hook dài","hook quá dài")),("hook_strength",("hook","mở đầu",)),("cliches",("sáo rỗng",)),
                ("sentence_length",("câu quá dài","28 từ")),("pattern_interrupt",("pattern interrupt",)),
                ("word_budget",("lượng từ","lượng chữ","thiếu chữ","thừa chữ")),
                ("repeated_ideas",("lặp ý","lặp lời")),("ending_style",("kiểu kết","kết video",)),
                ("transitions",("chuyển ý","cùng cấu trúc",)),("examples",("thiếu ví dụ","thiếu chi tiết","ít nhất 2 fact","ít nhất hai fact",)),
                ("scene_target",("số cảnh","ít cảnh",)),("overlay_style",("overlay dài","overlay quá",)),
                ("tts_format",("khó đọc","tts",))]
            key=next((key for key,patterns in mapping if any(p in lower for p in patterns)),None)
            if key is None:
                factual=("căn cứ","khẳng định","fact","brief","bịa","dữ kiện","số liệu","sai số","trích dẫn","tên riêng","hỗ trợ","nguồn","unsupported","fabricat")
                key="grounding_claims" if any(p in lower for p in factual) else "audit_clarity"
        result.append((key,Finding(scene_id,message)))
    return result

def schema_events(error,payload=None,phase="plan"):
    events=[]
    if hasattr(error,"errors"):
        for entry in error.errors(include_input=False,include_url=False):
            loc=entry["loc"];scene_id=None
            if len(loc)>1 and loc[0]=="scenes" and isinstance(loc[1],int):
                scenes=(payload or {}).get("scenes",[])
                if loc[1]<len(scenes): scene_id=scenes[loc[1]].get("id",scenes[loc[1]].get("scene_id"))
            if type(scene_id) is not int: scene_id=None
            events.append(ValidationEvent(rule_id="schema_basic",group=1,scene_id=scene_id,phase=phase,action="error",message=f"{loc}: {entry['msg']}"))
    return events or [ValidationEvent(rule_id="schema_basic",group=1,phase=phase,action="error",message=str(error))]
