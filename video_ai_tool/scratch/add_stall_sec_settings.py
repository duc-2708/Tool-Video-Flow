with open('config/settings.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''    ai_clip_daily_limit: int = Field(default=5, ge=0, le=100)
    scene_director_enabled: bool = Field(default=True)'''

replacement = '''    ai_clip_daily_limit: int = Field(default=5, ge=0, le=100)
    ai_clip_stall_sec: int = Field(default=120, ge=30, le=600)
    scene_director_enabled: bool = Field(default=True)'''

assert target in text, 'target not found'
text = text.replace(target, replacement, 1)

with open('config/settings.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully added ai_clip_stall_sec to config/settings.py')
