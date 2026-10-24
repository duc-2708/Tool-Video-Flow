"""Display timing only: keep captions across pauses without moving word cues."""
def display_words(words,duration):
    result=[]
    for i,(text,start,end) in enumerate(words):
        following=words[i+1][1] if i+1<len(words) else end
        result.append((text,start,min(duration,max(end,following))))
    return result


def phrase_groups(words,count=3):
    groups=[words[i:i+count] for i in range(0,len(words),count)]
    if count>1 and len(groups)>1 and len(groups[-1])==1: groups[-2].extend(groups.pop())
    return groups
