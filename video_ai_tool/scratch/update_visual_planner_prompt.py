with open('prompts/visual_planner.md', 'r', encoding='utf-8') as f:
    text = f.read()

rule_target = '11. Chú thích phải đúng nghĩa (xem phong cách); poll/câu hỏi phải khớp với các lựa chọn và nội dung video.'
rule_replacement = '''11. Chú thích phải đúng nghĩa (xem phong cách); poll/câu hỏi phải khớp với các lựa chọn và nội dung video.
12. HỢP NHẤT SCENE DIRECTOR: Nếu kịch bản có [Scene Director Motion Brief] (ý tưởng hình, recipe đề xuất, key beats), BẮT BUỘC xem xét đề xuất này để lựa chọn recipe và cấu trúc sự kiện; chỉ được đổi sang recipe khác nếu cần tránh lặp họ chuyển động hoặc để đảm bảo quy tắc lập lịch không lặp.'''

assert rule_target in text, 'rule_target not found'
text = text.replace(rule_target, rule_replacement, 1)

with open('prompts/visual_planner.md', 'w', encoding='utf-8') as f:
    f.write(text)
print('Updated prompts/visual_planner.md with Scene Director integration')
