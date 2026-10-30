with open('agents/illustrations.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Khôi phục TYPES chuẩn và bổ sung RECIPE_TYPES
old_types = '''TYPES=(
    'versus_scale','bar_grow','gauge','ring','line_draw','flow_chain','magnifier_check','funnel_filter','checklist','terminal_type','timeline_march','stack_cards','network_nodes',
    'slot_counter','strike_replace','gauge_needle','odometer','bar_race','thermometer','battery_fill','glass_fill','balance_scale','tug_of_war','vs_flip_cards','before_after_wipe',
    'conveyor_belt','domino_chain','pipeline_pipes','dice_roll','lock_unlock','shield_hit','traffic_light','orbit_system','layered_onion','stack_pile','puzzle_snap','chat_thread',
    'mock_card_swipe','form_fill_submit','terminal_command_run','stat_number','bar_compare','container_fill','steps_ladder','hub_spoke','mock_ui_window','code_card','versus_split'
)'''

new_types = '''TYPES=(
    'versus_scale','bar_grow','gauge','ring','line_draw','flow_chain','magnifier_check','funnel_filter','checklist','terminal_type','timeline_march','stack_cards','network_nodes'
)

RECIPE_TYPES=(
    'slot_counter','strike_replace','gauge_needle','odometer','bar_race','thermometer','battery_fill','glass_fill','balance_scale','tug_of_war','vs_flip_cards','before_after_wipe',
    'conveyor_belt','domino_chain','pipeline_pipes','dice_roll','lock_unlock','shield_hit','traffic_light','orbit_system','layered_onion','stack_pile','puzzle_snap','chat_thread',
    'mock_card_swipe','form_fill_submit','terminal_command_run','stat_number','bar_compare','container_fill','steps_ladder','hub_spoke','mock_ui_window','code_card','versus_split'
)

ALL_TYPES = TYPES + RECIPE_TYPES'''

assert old_types in text, 'old_types not found'
text = text.replace(old_types, new_types, 1)

# 2. Cập nhật spoken_stat regex để bắt cả tech_units và cụm tiếng Việt (phần trăm, tỷ USD, etc.)
old_spoken = '''    # Match potential number phrases including tech units (nm, Hz, TB) and currency/scale
    display_matches = re.finditer(
        r"(?<!\\w)(\\d+(?:[.,]\\d+)*\\s*(?:[A-Za-z%€$đ]+)?)(?!\\w)",
        text,
        re.I,
    )'''

new_spoken = '''    # Match potential number phrases including tech units (nm, Hz, TB), currency/scale, and Vietnamese units
    from editor.format_number import TECH_UNITS_MAP
    tech_units_pattern = "|".join(TECH_UNITS_MAP.keys())
    display_matches = re.finditer(
        r"(?<!\\w)(\\d+(?:[.,]\\d+)*\\s*(?:tỷ|tỉ|triệu|nghìn|ngàn|b|m|k|%)?\\s*(?:usd|\\$|vnd|đ|eur|€|phần trăm|" + tech_units_pattern + r")?)(?!\\w)",
        text,
        re.I,
    )'''

assert old_spoken in text, 'old_spoken not found'
text = text.replace(old_spoken, new_spoken, 1)

# 3. Cập nhật enough check để check ALL_TYPES
old_enough_return = '    return n >= 2 if name in TYPES else False'
new_enough_return = '    return n >= 2 if (name in TYPES or name in RECIPE_TYPES) else False'
assert old_enough_return in text, 'old_enough_return not found'
text = text.replace(old_enough_return, new_enough_return, 1)

with open('agents/illustrations.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully fixed TYPES and spoken_stat in agents/illustrations.py')
