"""Evidence controls length, never the reverse."""
import math
from collections import Counter

def content_count(duration,facts):
    return min(max(2,facts),max(2,math.ceil(max(0,duration-6)/8)))


def duration_for_brief(brief,requested):
    count=len(brief.facts)
    if not count: return 0.
    capacity=15 if count==1 else 35 if count==2 else 45 if count==3 else 52 if count==4 else 60+(count-5)*8 if count<10 else 90+(count-10)*8
    words=sum(len((fact.fact_vi or fact.claim).split()) for fact in brief.facts)
    evidence_seconds=max(6,(words*1.6+12)/2.5)
    return round(min(float(requested),capacity,evidence_seconds),2)


def fact_schedule(blueprint,count):
    return {row["id"]:[index%count+1] for index,row in enumerate(blueprint)}


def validate_reuse(scenes):
    from agents.validation_rules import repeated,Context
    from types import SimpleNamespace
    return repeated(Context(SimpleNamespace(scenes=scenes),None,phase="outline"))
