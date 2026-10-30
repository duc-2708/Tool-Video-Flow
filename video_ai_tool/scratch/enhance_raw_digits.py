with open('agents/visual_diversity.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''            bad=numeric_mismatches(scene,shot,brief)
            if not bad: continue
            v=shot.visual;v.template='text_focus'
            v.data.value=None;v.data.number_text='';v.data.bars=[];v.data.unit=''
            text,_=concept_card(re.sub(r'\\d+(?:[.,]\\d+)*','',shot_context(scene,shot)))
            v.data.text=text;v.data.label='';shot.card_text=text
            notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id}, shot {index}: số {bad} không có trong lời đọc/brief; đổi thẻ chữ, không đếm tới số giả.')'''

replacement = '''            # Tự động chuẩn hóa chuỗi số thô > 6 chữ số sang quy mô rút gọn (triệu, tỷ)
            v = shot.visual
            if v and v.data:
                raw_num = str(v.data.number_text or (v.data.value if v.data.value is not None else ""))
                if re.search(r'\\b\\d{7,}\\b', raw_num):
                    from editor.format_number import parse_display_number
                    parsed = parse_display_number(f"{raw_num} {v.data.unit or ''}")
                    if parsed:
                        v.data.value = parsed.value
                        v.data.number_text = parsed.formatted_number
                        v.data.unit = parsed.unit_display
                        notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id}, shot {index}: chuẩn hóa chuỗi số thô {raw_num} thành {parsed.formatted_text}.')

            bad=numeric_mismatches(scene,shot,brief)
            if not bad: continue
            v=shot.visual;v.template='text_focus'
            v.data.value=None;v.data.number_text='';v.data.bars=[];v.data.unit=''
            text,_=concept_card(re.sub(r'\\d+(?:[.,]\\d+)*','',shot_context(scene,shot)))
            v.data.text=text;v.data.label='';shot.card_text=text
            notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id}, shot {index}: số {bad} không có trong lời đọc/brief; đổi thẻ chữ, không đếm tới số giả.')'''

assert target in text, 'Target not found'
text = text.replace(target, replacement, 1)

# Thêm tương tự cho vp.data
target_vp = '''        vp = getattr(scene, 'visual_plan', None)
        if vp and getattr(vp, 'data', None):'''

replacement_vp = '''        vp = getattr(scene, 'visual_plan', None)
        if vp and getattr(vp, 'data', None):
            raw_vp_num = str(vp.data.number_text or (vp.data.value if vp.data.value is not None else ""))
            if re.search(r'\\b\\d{7,}\\b', raw_vp_num):
                from editor.format_number import parse_display_number
                parsed = parse_display_number(f"{raw_vp_num} {vp.data.unit or ''}")
                if parsed:
                    vp.data.value = parsed.value
                    vp.data.number_text = parsed.formatted_number
                    vp.data.unit = parsed.unit_display
                    notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id} visual_plan: chuẩn hóa chuỗi số thô {raw_vp_num} thành {parsed.formatted_text}.')'''

assert target_vp in text, 'Target vp not found'
text = text.replace(target_vp, replacement_vp, 1)

with open('agents/visual_diversity.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully enhanced raw digit normalization in agents/visual_diversity.py')
