with open('.env.example', 'r', encoding='utf-8') as f:
    text = f.read()

new_lines = '''
# GIAI ĐOẠN 8: SCENE DIRECTOR + HYBRID CLIP
SCENE_DIRECTOR_ENABLED=true
AI_CLIPS_MAX_PER_VIDEO=2
AI_CLIP_MODE=off
AI_CLIP_AUTO_APPROVE=false
AI_CLIP_DAILY_LIMIT=5
'''

if 'SCENE_DIRECTOR_ENABLED' not in text:
    text += new_lines
    with open('.env.example', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated .env.example')

import os
if os.path.isfile('.env'):
    with open('.env', 'r', encoding='utf-8') as f:
        env_text = f.read()
    added = []
    for k, v in [
        ('SCENE_DIRECTOR_ENABLED', 'true'),
        ('AI_CLIPS_MAX_PER_VIDEO', '2'),
        ('AI_CLIP_MODE', 'off'),
        ('AI_CLIP_AUTO_APPROVE', 'false'),
        ('AI_CLIP_DAILY_LIMIT', '5')
    ]:
        if k not in env_text:
            added.append(f"{k}={v}")
    if added:
        env_text += "\n" + "\n".join(added) + "\n"
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_text)
        print('Updated .env without leaking any credentials')
