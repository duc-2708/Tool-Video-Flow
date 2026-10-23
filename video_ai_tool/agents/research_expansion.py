"""One bounded attempt to improve thin research; every new fact is re-grounded."""
from urllib.parse import urlsplit
from schemas.research_brief import SearchQuery
from schemas.languages import REGIONS


def thin_research(brief):
    return brief is None or len(brief.facts)<6 or len({(urlsplit(str(f.source_url)).hostname or "").removeprefix("www.") for f in brief.facts})<=1


def expansion_queries(topic,queries):
    result=[]
    for lang in dict.fromkeys(q.source_lang for q in queries):
        base=next(q.query for q in queries if q.source_lang==lang)
        if len(base)>220: base=base[:220].rsplit(" ",1)[0]
        suffixes={"en":("background details impact","latest developments evidence"),
            "vi":("diễn biến nguyên nhân tác động","chi tiết số liệu cập nhật"),
            "zh":("背景 详情 影响","最新进展 数据 证据"),"ko":("배경 세부 정보 영향","최신 동향 근거"),
            "ja":("背景 詳細 影響","最新動向 証拠")}[lang]
        for suffix in suffixes:
            query=(base+" "+suffix).strip()[:300]
            if query not in {q.query for q in queries}:
                result.append(SearchQuery(source_lang=lang,query=query,region=REGIONS[lang]))
    return result[:4]


def expand_sources_once(topic,sources,queries,collector,diagnostics,progress):
    seen={str(s.url) for s in sources};new=[];warnings=[];used=[]
    for query in expansion_queries(topic,queries):
        used.append(query)
        progress("Mở rộng Research 1/1: "+query.query)
        try:
            documents,notices=collector.collect(query.query,4,query.source_lang)
            warnings.extend(notices)
            for source in documents:
                if str(source.url) not in seen:
                    seen.add(str(source.url));new.append(source)
        except Exception as error:
            diagnostics.record_exception(error,"Mở rộng nguồn một lần; giữ nguồn/fact đã kiểm chứng")
            warnings.append("Không lấy được một truy vấn mở rộng; giữ dữ liệu đã kiểm chứng.")
        if len(new)>=4: break
    existing={(urlsplit(str(s.url)).hostname or "").removeprefix("www.") for s in sources}
    new.sort(key=lambda s:((urlsplit(str(s.url)).hostname or "").removeprefix("www.") in existing,not bool(s.published_at)))
    return new[:4],used,warnings


def merge_grounded_briefs(original,expanded):
    if original is None: return expanded
    result=original.model_copy(deep=True)
    keys={(f.fact_vi or f.claim,str(f.source_url)) for f in result.facts}
    mapping={}
    for i,fact in enumerate(expanded.facts,1):
        key=(fact.fact_vi or fact.claim,str(fact.source_url))
        if key not in keys:
            result.facts.append(fact);keys.add(key)
        mapping[i]=next(j for j,f in enumerate(result.facts,1) if (f.fact_vi or f.claim,str(f.source_url))==key)
    for field in ("key_numbers","timeline","why_it_matters","counterpoints","glossary"):
        old=getattr(result,field)
        for detail in getattr(expanded,field):
            value=detail.model_copy(update={"fact_ids":[mapping[i] for i in detail.fact_ids if i in mapping]})
            if value.fact_ids and value not in old: old.append(value)
    result.risks=list(dict.fromkeys(result.risks+expanded.risks))
    return result
