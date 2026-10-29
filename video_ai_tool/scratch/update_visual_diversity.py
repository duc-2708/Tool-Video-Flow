with open("agents/visual_diversity.py", "r", encoding="utf-8") as f:
    c = f.read()

pos = c.find("def values_in(text):")
assert pos != -1
end_pos = c.find("def select_templates(", pos)
assert end_pos != -1

new_code = '''def values_in(text):
    allowed = {n.rstrip('%') for n in normalized_numbers(text, ignore_current_year=False)}
    from editor.format_number import parse_display_number
    import re
    # Extract raw tokens
    for token in re.findall(r'\\b\\d+(?:[.,]\\d+)*\\b', text):
        clean = token.replace('.', '').replace(',', '.')
        try:
            val = float(clean)
            allowed.add(str(int(val)) if val.is_integer() else str(val))
        except ValueError:
            pass
    # Extract parsed display numbers
    for m in re.finditer(r'(?<!\\w)(\\d+(?:[.,]\\d+)*\\s*(?:[A-Za-z%€$đ]+)?)(?!\\w)', text):
        p = parse_display_number(m.group(1))
        if p:
            allowed.add(str(int(p.value)) if p.value.is_integer() else str(p.value))
            allowed.add(str(int(p.full_numeric_value)) if p.full_numeric_value.is_integer() else str(p.full_numeric_value))
    return allowed


def numeric_mismatches(scene,shot,brief=None):
    v=shot.visual
    if not v or v.template not in {'stat_card','ring_percent','line_growth','strike_replace','compare_bars'}: return []
    base=scene.narration
    if brief: base+=' '+' '.join((f.fact_vi or f.claim)+' '+f.claim+' '+(f.evidence_quote or '') for f in brief.facts)
    allowed=values_in(base)
    actual=[]
    if v.data.value is not None: actual.append(v.data.value)
    actual.extend(b.value for b in v.data.bars)
    return [x for x in actual if not values_in(f'{x:.10f}'.rstrip('0').rstrip('.'))<=allowed]


def repair_numeric_cards(plan,brief=None):
    """Render only, AFTER existing provenance review. No bypass of Director group 1."""
    notes=[]
    for scene in plan.scenes:
        base = scene.narration
        if brief: base += ' ' + ' '.join((f.fact_vi or f.claim) + ' ' + f.claim + ' ' + (f.evidence_quote or '') for f in brief.facts)
        allowed = values_in(base)

        for index,shot in enumerate(scene.shots,1):
            bad=numeric_mismatches(scene,shot,brief)
            if not bad: continue
            v=shot.visual;v.template='text_focus'
            v.data.value=None;v.data.number_text='';v.data.bars=[];v.data.unit=''
            text,_=concept_card(re.sub(r'\\d+(?:[.,]\\d+)*','',shot_context(scene,shot)))
            v.data.text=text;v.data.label='';shot.card_text=text
            notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id}, shot {index}: số {bad} không có trong lời đọc/brief; đổi thẻ chữ, không đếm tới số giả.')

        vp = getattr(scene, 'visual_plan', None)
        if vp and getattr(vp, 'data', None):
            actual = []
            if getattr(vp.data, 'value', None) is not None:
                actual.append(vp.data.value)
            if getattr(vp.data, 'bars', None):
                actual.extend(b.value for b in vp.data.bars)
            bad = [x for x in actual if not values_in(f'{x:.10f}'.rstrip('0').rstrip('.')) <= allowed]
            if bad:
                vp.scene_type = 'text_focus'
                vp.data.value = None
                vp.data.bars = []
                notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id} visual_plan: số {bad} không có trong lời đọc/brief; đổi sang text_focus.')

    plan.review_notes.extend(n for n in notes if n not in plan.review_notes)
    return notes

'''

c = c[:pos] + new_code + c[end_pos:]
with open("agents/visual_diversity.py", "w", encoding="utf-8") as f:
    f.write(c)

print("Successfully updated visual_diversity.py via script!")
