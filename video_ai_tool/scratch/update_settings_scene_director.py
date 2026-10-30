with open('config/settings.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''    ai_clips_per_video: int = Field(default=0,ge=0,le=20)

    ai_clip_model: str = ""'''

replacement = '''    ai_clips_per_video: int = Field(default=0,ge=0,le=20)
    ai_clips_max_per_video: int = Field(default=2, ge=0, le=10)
    ai_clip_mode: str = Field(default="off")
    ai_clip_auto_approve: bool = Field(default=False)
    ai_clip_daily_limit: int = Field(default=5, ge=0, le=100)
    scene_director_enabled: bool = Field(default=True)

    ai_clip_model: str = ""'''

assert target in text, 'target not found'
text = text.replace(target, replacement, 1)

validator_target = '''    @field_validator('ai_clip_model')'''
validator_replacement = '''    @field_validator('ai_clip_mode')
    @classmethod
    def validate_ai_clip_mode(cls, value):
        v = str(value or "off").strip().lower()
        if v not in {"off", "auto", "manual"}:
            return "off"
        return v

    @field_validator('ai_clip_model')'''

assert validator_target in text, 'validator_target not found'
text = text.replace(validator_target, validator_replacement, 1)

with open('config/settings.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully updated settings.py with Scene Director & AI clip settings')
