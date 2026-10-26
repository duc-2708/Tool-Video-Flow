"""Display timing only: keep captions across pauses without moving word cues."""
def display_words(words,duration):
    result=[]
    for i,(text,start,end) in enumerate(words):
        following=words[i+1][1] if i+1<len(words) else end
        result.append((text,start,min(duration,max(end,following))))
    return result


def phrase_groups(words,count=3):
    if count==1: return [[w] for w in words]
    import re
    groups=[];current=[]
    trailing={'của','cho','với','và','để','từ','trong','là','nhưng','hoặc','có'}
    for word in words:
        current.append(word)
        punct=bool(re.search(r'[.!?;:,]$',word[0]))
        end=word[0].strip('.,;:!?').casefold()
        if len(current)>=4 or len(current)>=2 and punct or len(current)>=count and end not in trailing:
            groups.append(current);current=[]
    if current: groups.append(current)
    if count>1 and len(groups)>1 and len(groups[-1])==1: groups[-2].extend(groups.pop())
    # A five-word tail is redistributed into 3+2 rather than a 1-word fragment.
    if groups and len(groups[-1])>4:
        tail=groups.pop();groups.extend([tail[:3],tail[3:]])
    return groups
