with open('docs/PROCESS.md', 'r', encoding='utf-8') as f:
    text = f.read()

entry_sec2 = '''| 2026-10-29 | Giai đoạn 8 - Bước (a): Scene Director + Validator + Hợp nhất Visual Planner: (1) Tạo module Scene Director (agents/scene_director.py, schemas/scene_director.py) nhận kịch bản, xác định chế độ trình bày (motion, ai_clip, hybrid) và sinh motion brief (visual_idea, recipe_candidates, key_beats, emphasis); (2) Bộ kiểm định và tự sửa guardrails: ai_clip+hybrid <= 30% số cảnh và <= AI_CLIPS_MAX (mặc định 2), cấm 2 clip AI liền kề (hạ cảnh sau về motion), cảnh có số liệu chủ thể ép về motion, lọc sạch từ khóa cấm trong prompt_en (chữ, số, logo, tên người thật, thương hiệu), tự gán fallback_recipe khi thiếu; (3) Cấu hình hệ thống: bổ sung SCENE_DIRECTOR_ENABLED, AI_CLIPS_MAX_PER_VIDEO, AI_CLIP_MODE, AI_CLIP_AUTO_APPROVE, AI_CLIP_DAILY_LIMIT trong settings.py, .env.example, .env; (4) Hợp nhất với Visual Planner: nhúng [Scene Director Motion Brief] vào prompts/visual_planner.md và render_visual_prompt trong agents/visual_planner_v3.py làm gợi ý bắt buộc xem xét; (5) Kết xuất scene_plan.json thành công cho dự án thực tế auto-cong-nghe-d56d3ebe (macbook-pro-oled) đạt 100% quy chuẩn; (6) Bộ test pytest tests/test_scene_director.py đạt 6/6 passed, toàn bộ suite 46/46 passed 100%. | APP/agents/scene_director.py, schemas/scene_director.py, prompts/scene_director.md, prompts/visual_planner.md, agents/visual_planner_v3.py, config/settings.py, tests/test_scene_director.py, .env.example, output/auto-cong-nghe-d56d3ebe/scene_plan.json; ROOT/docs/PROCESS.md | Hoàn thành Bước (a) Giai đoạn 8: Scene Director, bộ kiểm định guardrails và hợp nhất kế hoạch hình ảnh |'''

# Marker trong mục 2
marker2 = '| 2026-10-29 | Ưu tiên tuyệt đối - Chống bịa số & Nối Motion Vocabulary vào pipeline:'
assert marker2 in text, 'marker2 not found'
text = text.replace(marker2, f'{entry_sec2}\n{marker2}', 1)

# Marker trong mục 15
marker15 = '| 2026-10-29 | Ưu tiên tuyệt đối - Chống bịa số & Nối Motion Vocabulary vào pipeline:'
assert marker15 in text, 'marker15 not found'
text = text.replace(marker15, f'{entry_sec2}\n{marker15}', 1)

with open('docs/PROCESS.md', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully updated PROCESS.md changelog in section 2 and section 15 for Phase 8 step (a)')
