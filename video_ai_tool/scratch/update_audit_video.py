import re
from pathlib import Path

audit_path = Path("tools/audit_video.py")
code = audit_path.read_text(encoding="utf-8")

# Update METRICS_SPEC
if '"center_y_drift"' not in code:
    code = code.replace(
        '"caption_collisions": {"target": "== 0", "check": lambda v: v == 0},\n}',
        '"caption_collisions": {"target": "== 0", "check": lambda v: v == 0},\n    "center_y_drift": {"target": "<= 120px", "check": lambda v: v <= 120},\n}'
    )

# Update audit_data reading
if 'center_y_drift = audit_data.get("center_y_drift", 0)' not in code:
    code = code.replace(
        'caption_collisions = audit_data.get("caption_collisions", 0)',
        'caption_collisions = audit_data.get("caption_collisions", 0)\n            center_y_drift = audit_data.get("center_y_drift", 0)'
    )
    code = code.replace(
        'caption_collisions = 0\n\n        # Check duplicate',
        'caption_collisions = 0\n            center_y_drift = 0\n\n        # Check duplicate'
    )
    code = code.replace(
        '"caption_collisions": caption_collisions,',
        '"caption_collisions": caption_collisions,\n            "center_y_drift": center_y_drift,'
    )

# Update table keys
if '("center_y_drift", "px")' not in code:
    code = code.replace(
        '("duplicate_labels", ""),',
        '("duplicate_labels", ""),\n        ("caption_collisions", ""),\n        ("empty_prompts", ""),\n        ("center_y_drift", "px"),'
    )

audit_path.write_text(code, encoding="utf-8")
print("Updated tools/audit_video.py")
