"""Bounded, neutral stock keywords; no research search strings in stock slots."""
import json
import re
import unicodedata
from pydantic import Field
from schemas.base import StrictModel

class BrollQueryResponse(StrictModel):
    query: str = Field(min_length=1)

def latin(text):
    text=unicodedata.normalize("NFKD",str(text or "").casefold().replace("đ","d"))
    return "".join(c for c in text if not unicodedata.combining(c))

# A conservative stock vocabulary also drops unknown people and product names.
VOCAB=set("""rocket launch night engineers control room engine spacecraft assembly hangar pad tower ocean recovery mission testing factory workers machinery laboratory science research technology abstract data center server computer laptop smartphone screen equipment electronic circuit board energy solar wind city skyline street traffic building office business meeting team working people market shop shopping money finance travel landscape mountain beach forest nature healthy lifestyle doctor hospital medical sports training stadium running game gaming controller fashion clothing fabric designer studio camera filming editing video software timeline animation detail news newspaper globe network satellite space orbit earth clouds sky sunrise sunset daylight interior exterior aerial closeup wide view workshop industrial production robotic robot arm mechanical system catch reusable booster landing flight launchpad steel metal construction tunnel aircraft airport railway train transport ship harbor field agriculture farming food cooking kitchen restaurant tourism hotel road bridge coast desert music concert audience hands typing keyboard monitor desk creative design planning drawing education classroom students teacher digital electric vehicle driving highway battery charging water climate environment rain storm rescue emergency community home family walking portrait athlete fitness exercise retail warehouse logistics package shipping telescope stars universe astronaut capsule smoke fire exhaust platform communication analysis financial economic rural urban mobile green sustainable panels turbine power quantum computing semiconductor processor chip automation drone tree park light close up panoramic landscape infrastructure concrete excavation crane engineer technician automation manufacturing test air fuel weather documentary presentation human professional workspace interface innovation journalism security airport station passenger pet animal wildlife birds cycling swimming football basketball tennis hiking camping maps map learning workshop blueprint coffee bread farm farmer launch vehicle support operations precision measurement workshop construction machinery spacecraft vessel horizon crane research engineering docking launch return countdown propulsion fueling motor booster logistics""".split())
BRANDS=set("spacex starship tesla elon musk openai chatgpt gemini google microsoft apple iphone samsung galaxy nvidia meta facebook instagram tiktok anthropic claude gpt reuters trump biden bezos amazon blueorigin intel amd capcut premiere adobe".split())
TRANSLATE={"phong dieu khien":"control room","ky su":"engineers","ten lua":"rocket","phong":"launch", "ban phong":"launch pad",
    "dong co":"engine", "lap rap":"assembly", "nha may":"factory", "may chu":"server", "trung tam du lieu":"data center",
    "may tinh":"computer", "dien thoai":"smartphone", "thanh pho":"city", "duong pho":"street", "phong thi nghiem":"laboratory",
    "du lich":"travel landscape", "y te":"medical hospital", "dung video":"video editing", "cong nghe":"technology"}
POOLS={
    "rocket":["rocket launch night","engineers control room","rocket engine closeup","spacecraft assembly hangar","launch tower daylight","spacecraft ocean recovery","launch pad aerial","mission control interior","engine testing workshop","booster landing platform"],
    "editing":["video editing","editing software","camera filming studio","editor computer desk","hands keyboard typing","creative studio planning","video timeline closeup"],
    "medical":["healthy lifestyle","doctor hospital","medical laboratory","people exercising park","research scientist laboratory"],
    "travel":["city skyline","travel landscape","mountain sunrise","beach aerial","tourism city street"],
    "technology":["technology abstract","data center","engineers laboratory","electronic circuit board","computer processor closeup","factory machinery","robotic arm assembly","server equipment interior"],
    "general":["city skyline","news studio","office team meeting","people walking street","industrial factory","globe network","urban traffic aerial","research laboratory"]}
VOCAB.update(word for pool in POOLS.values() for query in pool for word in query.split())
TRANSLATE.update({"trung tam du lieu":"data center","nang luong":"energy power","kho han":"drought water",
    "tri tue nhan tao":"computing technology","may hoc":"machine learning","the thao":"sports training",
    "thoi trang":"fashion clothing","kinh doanh":"business finance","tro choi":"gaming controller",
    "han han":"drought water","nuoc":"water","dien":"electric power","moi truong":"environment",
    "khi hau":"climate","phat thai":"carbon emissions","nha kinh":"greenhouse emissions",
    "gia dien":"electricity power","hoa don":"energy bill","dong song":"river water",
    "san xuat chip":"semiconductor manufacturing","chip":"semiconductor chip","may tinh":"computer",
    "ky thuat vien":"technician","dan cu":"community","tai nguyen":"natural resources",
    "dong vat":"wildlife animals","cau di bo":"pedestrian bridge","am nhac":"music concert",
    "dien thoai gap":"smartphone folding","pin":"battery","dau tu":"business investment"})
VOCAB.update("drought electricity bill river carbon emissions greenhouse natural resources investment pedestrian folding animals".split())
VOCAB.update("aerial wide closeup interior exterior panoramic detail documentary night daylight sunset sunrise view daytime morning evening".split())
VOCAB.update("machine learning".split())

def category(context):
    text=latin(context)
    for name,cues in [("rocket",("rocket","starship","spacex","ten lua","spacecraft")),("editing",("editing","dung video","ghep","cat canh")),
        ("medical",("medical","suc khoe","benh vien","hospital")),("travel",("travel","du lich","tourism")),
        ("technology",("technology","cong nghe","server","may tinh","data","ai "))]:
        if any(cue in text for cue in cues): return name
    return "general"

def keywords(query):
    text=latin(query)
    for vi,en in sorted(TRANSLATE.items(),key=lambda pair:-len(pair[0])):
        text=re.sub(r"\b"+re.escape(vi)+r"\b",en,text)
    tokens=list(dict.fromkeys(t for t in re.findall(r"[a-z]+",text) if t in VOCAB and t not in BRANDS))
    if len(tokens)>4:
        concrete=set("rocket launch engine engineers control room tower spacecraft factory laboratory hospital server computer chip city street mountain beach camera filming editing vehicle assembly landing ocean".split())
        tokens=sorted(enumerate(tokens),key=lambda pair:(pair[1] not in concrete,pair[0]))[:4]
        tokens=[t for _,t in sorted(tokens)]
    return " ".join(tokens)

def sanitize_broll_query(query, scene_context="", *, provider=None, diagnostics=None):
    cleaned=keywords(query)
    if len(cleaned.split())<2 and provider is not None:
        prompt=("Repair only this stock b-roll query, JSON {query:...}. Return 2-4 English words, one generic stock scene; "
            "no brands, products, real people, numbers or topic title. Do not rewrite narration or shots.\nINPUT_DATA_JSON:\n"+
            json.dumps({"query":str(query or "")[:400],"scene_context":str(scene_context)[:500]},ensure_ascii=False))
        try: cleaned=keywords(BrollQueryResponse.model_validate_json(provider.generate_json(prompt,BrollQueryResponse)).query)
        except Exception as error:
            if diagnostics: diagnostics.record_exception(error,"Sửa riêng b-roll query một lần; dùng stock query dự phòng")
    if 2<=len(cleaned.split())<=4: return cleaned
    contextual=keywords(scene_context)
    return contextual if 2<=len(contextual.split())<=4 else POOLS[category(scene_context)][0]

def unique_query(query,scene_context,used):
    if query not in used: return query
    # Keep the scene's subject; vary framing rather than rotate unrelated media.
    views=("aerial","wide","closeup","interior","exterior","panoramic","detail","documentary")
    settings=("night","daylight","sunset","sunrise","view","daytime","morning","evening")
    VOCAB.update((*views,*settings))
    bases=list(dict.fromkeys([" ".join(query.split()[:2])," ".join(keywords(scene_context).split()[:2])]))
    for base in bases:
        if len(base.split())<2: continue
        for view in views:
            candidate=f"{base} {view}"
            if candidate not in used: return candidate
        for view in views:
            for setting in settings:
                candidate=f"{base} {view} {setting}"
                if candidate not in used: return candidate
    return query
