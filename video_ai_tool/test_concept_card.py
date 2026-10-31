from agents.visual_diversity import concept_card
from agents.presentation import clean_semantic_label, valid_card

context = "Ngày 19 tháng 8, các cơ quan Mỹ cảnh báo tác nhân mạng nhắm vào bộ điều khiển công nghiệp. Điều này giống như việc gắn cửa cuốn tự động thông minh vào một ngôi nhà cổ kỹ thuật cũ kỹ."
used = ['Hệ thống công nghiệp', 'Phòng máy chủ', 'Cửa cuốn tự động']
res, is_clause = concept_card(context, used)
print("Result of concept_card:", repr(res), "is_clause:", is_clause)
