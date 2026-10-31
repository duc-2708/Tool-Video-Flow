import re
from pathlib import Path

vocab_file = Path("editor/motion/recipes/vocabulary.js")
code = vocab_file.read_text(encoding="utf-8")

# 1. Update cardW to 880 and cardH to at least 680
code = re.sub(r"const cardW = \d+;", "const cardW = 880;", code)
code = re.sub(r"const boxW = \d+;", "const boxW = 880;", code)

def fix_card_h(m):
    val = int(m.group(1))
    new_val = max(val, 680)
    return f"const cardH = {new_val};"

code = re.sub(r"const cardH = (\d+);", fix_card_h, code)
code = re.sub(r"const boxH = (\d+);", lambda m: f"const boxH = {max(int(m.group(1)), 680)};", code)

# 2. Update default maxWords to 6
code = code.replace("function internalSanitizeSemanticLabel(label, maxWords = 4)", "function internalSanitizeSemanticLabel(label, maxWords = 6)")
code = code.replace("const sanitizeSemanticLabel = (lbl, maxWords = 4)", "const sanitizeSemanticLabel = (lbl, maxWords = 6)")

# 3. Expand COMPOUND_PAIRS_JS
compound_block_old = """  const COMPOUND_PAIRS_JS = new Set([
    'thiết bị', 'hoạt động', 'ngân hàng', 'an ninh', 'an toàn',
    'bảo mật', 'thông tin', 'tài sản', 'tài chính', 'kỹ thuật',
    'kỹ sư', 'lỗ hổng', 'hệ thống', 'chính sách', 'trách nhiệm',
    'pháp lý', 'quốc tế', 'dữ liệu', 'máy tính', 'phần mềm',
    'tin tặc', 'quy định'
  ]);"""

compound_block_new = """  const COMPOUND_PAIRS_JS = new Set([
    'thiết bị', 'hoạt động', 'ngân hàng', 'an ninh', 'an toàn',
    'bảo mật', 'thông tin', 'tài sản', 'tài chính', 'kỹ thuật',
    'kỹ sư', 'lỗ hổng', 'hệ thống', 'chính sách', 'trách nhiệm',
    'pháp lý', 'quốc tế', 'dữ liệu', 'máy tính', 'phần mềm',
    'tin tặc', 'quy định', 'thiết kế', 'khóa cửa', 'khai thác',
    'nghiêm trọng', 'toàn cầu', 'đăng nhập', 'điểm yếu', 'tấn công',
    'đột nhập', 'xác thực', 'ngân sách', 'doanh nghiệp', 'phòng thủ', 'rủi ro'
  ]);"""

if compound_block_old in code:
    code = code.replace(compound_block_old, compound_block_new)
else:
    print("WARNING: compound_block_old not found verbatim!")

# 4. Change sanitizeSemanticLabel(labelRaw, 3) to sanitizeSemanticLabel(labelRaw, 6)
code = re.sub(r"sanitizeSemanticLabel\(([^,\)]+),\s*[234]\)", r"sanitizeSemanticLabel(\1, 6)", code)

vocab_file.write_text(code, encoding="utf-8")
print("vocabulary.js updated successfully!")
