with open('agents/visual_diversity.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''        vp = getattr(scene, 'visual_plan', None)
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
                notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id} visual_plan: số {bad} không có trong lời đọc/brief; đổi sang text_focus.')'''

replacement = '''        vp = getattr(scene, 'visual_plan', None)
        if vp and getattr(vp, 'data', None):
            has_percent_evidence = ('%' in base) or ('phần trăm' in base.lower())
            if vp.data.unit == '%' and not has_percent_evidence:
                vp.data.unit = ''
                notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id} visual_plan: đơn vị % không có căn cứ; xóa đơn vị %.')
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
                vp.data.unit = ''
                notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id} visual_plan: số {bad} không có trong lời đọc/brief; đổi sang text_focus.')
            elif vp.data.value is None:
                vp.data.unit = '' '''

assert target in text, 'Target not found'
text = text.replace(target, replacement, 1)

with open('agents/visual_diversity.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully updated agents/visual_diversity.py')
