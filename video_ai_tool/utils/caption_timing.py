"""Display timing only: keep captions across pauses without moving word cues."""

def display_words(words, duration):
    result = []
    for i, (text, start, end) in enumerate(words):
        following = words[i+1][1] if i+1 < len(words) else end
        result.append((text, start, min(duration, max(end, following))))
    return result


def phrase_groups(words, count=3, min_group_duration=0.70):
    if count == 1:
        return [[w] for w in words]
    import re
    groups = []
    current = []
    trailing = {'của', 'cho', 'với', 'và', 'để', 'từ', 'trong', 'là', 'nhưng', 'hoặc', 'có', 'bị', 'được', 'các', 'những', 'một'}

    for word in words:
        current.append(word)
        punct = bool(re.search(r'[.!?;:,]$', word[0]))
        end = word[0].strip('.,;:!?').casefold()
        dur = current[-1][2] - current[0][1]
        # Group ends when reached max 4 words, or punctuation with at least 0.7s (or >= 2 words), or count met and not trailing
        if len(current) >= 4 or (len(current) >= 2 and punct and dur >= min_group_duration) or (len(current) >= count and end not in trailing and dur >= min_group_duration):
            groups.append(current)
            current = []

    if current:
        groups.append(current)

    # Clean up single-word or tiny fragments (< 0.7s) by merging with previous group if total <= 4
    i = len(groups) - 1
    while i > 0:
        dur = groups[i][-1][2] - groups[i][0][1]
        if (len(groups[i]) == 1 or dur < min_group_duration) and (len(groups[i-1]) + len(groups[i]) <= 4):
            groups[i-1].extend(groups.pop(i))
        i -= 1

    # Ensure display end time covers min_group_duration up to next group's start
    adjusted = []
    for idx, grp in enumerate(groups):
        if not grp: continue
        start_t = grp[0][1]
        next_start = groups[idx+1][0][1] if idx+1 < len(groups) else (grp[-1][2] + min_group_duration)
        target_end = min(next_start, max(grp[-1][2], start_t + min_group_duration))
        # Extend the last word's end if needed for display persistence
        last_word = grp[-1]
        if target_end > last_word[2]:
            new_grp = list(grp[:-1]) + [(last_word[0], last_word[1], target_end)]
            adjusted.append(new_grp)
        else:
            adjusted.append(grp)

    return adjusted
