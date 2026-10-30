with open('.env.example', 'r', encoding='utf-8') as f:
    text = f.read()

if 'AI_CLIP_STALL_SEC' not in text:
    text = text.replace('AI_CLIP_DAILY_LIMIT=5', 'AI_CLIP_DAILY_LIMIT=5\nAI_CLIP_STALL_SEC=120')
    with open('.env.example', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated .env.example with AI_CLIP_STALL_SEC')
