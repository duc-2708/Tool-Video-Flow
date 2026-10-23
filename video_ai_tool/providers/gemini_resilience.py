"""Bounded transient retries and smaller prompts, preserving referenced facts."""
import json
import httpx
from providers.research_payload import bounded_sources


def error_code(error):
    code=getattr(error,"code",None) or getattr(getattr(error,"response",None),"status_code",None)
    try: return int(code)
    except (ValueError,TypeError):
        message=str(error).upper()
        if "DEADLINE_EXCEEDED" in message: return 504
        if "UNAVAILABLE" in message: return 503
        return "TIMEOUT" if isinstance(error,(TimeoutError,httpx.TimeoutException)) else type(error).__name__


def transient_gemini(error):
    code=error_code(error)
    if code in {400,401,403,404}: return False
    return code in {408,429,500,502,503,504,"TIMEOUT"} or isinstance(error,(httpx.TimeoutException,httpx.NetworkError,TimeoutError))


def compact_prompt(prompt):
    """Keep IDs/checked statements; trim style metadata and unused evidence first."""
    prefix,marker,payload=prompt.partition("\nINPUT_DATA_JSON:\n")
    if not marker:
        # Do not blindly cut prose/JSON: that can remove grounding instructions.
        return prompt
    try: data=json.loads(payload)
    except (ValueError,TypeError): return prompt
    if not isinstance(data,dict): return prompt
    referenced=set()
    def references(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in {"fact_ids","payoff_fact_ids"} and isinstance(item,list):
                    referenced.update(i for i in item if type(i) is int)
                else: references(item)
        elif isinstance(value,list):
            for item in value: references(item)
    references({k:v for k,v in data.items() if k not in {"facts","style_profile"}})
    def shrink(value):
        if isinstance(value,list): return [shrink(v) for v in value]
        if not isinstance(value,dict): return value
        result={}
        for key,item in value.items():
            if key in {"validation_events","review_notes","source_review","reference_texts","reference_files","reference_hashes"}: continue
            if key=="style_profile" and isinstance(item,dict):
                result[key]={k:shrink(v[:6] if isinstance(v,list) else v) for k,v in item.items()
                    if k in {"name","reusable_rules","narration_rules","connective_phrases","shot_seconds","speech_words_per_sec","hook_techniques"}}
            elif key=="sources" and isinstance(item,list): result[key]=bounded_sources(item,12000)
            elif key=="facts" and isinstance(item,list):
                # Never renumber fact IDs. Required facts are retained even above the soft cap.
                selected=[f for f in item if isinstance(f,dict) and f.get("id") in referenced]
                remaining=[f for f in item if f not in selected]
                selected+=remaining[:max(0,12-len(selected))]
                result[key]=[shrink(f) for f in selected]
            elif key in {"risks","angles","story_angles"} and isinstance(item,list): result[key]=shrink(item[:3])
            else: result[key]=shrink(item)
        return result
    compact=prefix+marker+json.dumps(shrink(data),ensure_ascii=False)
    return compact if len(compact)<len(prompt) else prompt
