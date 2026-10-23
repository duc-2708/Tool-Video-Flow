"""Conservative, shared Vietnamese capitalization filter (no extra dependency).

This is a candidate detector, not proof of an entity. Grounding still compares
complete candidates with the brief. Preserve spans/order for safe replacements.
"""
import re
import unicodedata

COMMON=set("""trải nghiệm nhiều khi nếu vì mỗi hầu thực giả sử như vậy nên nhưng
và hoặc hay với thì là của trong trên dưới này đó những các một hai ba bốn năm
sáu bảy tám chín mười không có thể sẽ đã đang còn chỉ cũng rất hơn nhất người
dùng mình bạn họ chúng ta tôi nó đây đâu đầu sau trước cuối phần việc điều cách
bước cảnh câu nguồn thông tin nền số dữ liệu hình ảnh ví dụ thường nói nhìn
thử hãy đừng mặt khác tuy dù bởi do từ đến tại ở cho để về qua cùng lại chính
thật tế quy trình hệ thống máy công nghệ nhân sự giải thích phân tích đánh giá
sản phẩm công ty ngân hàng vụ kiện mất thay đổi kiểm tra chọn giữ lấy đưa tạo
thêm bỏ tránh kết mở chào cảm ơn giới thiệu nhờ chẳng hạn đồng thời ngoài ra
toàn bộ bất kỳ vài khoảng ước chừng ước tính xấp xỉ hàng chục trăm nghìn triệu
tỷ giây phút giờ ngày tháng năm hôm nay chiều tối sáng bắt đầu tiếp theo
nhẹ nhanh chậm lớn nhỏ mạnh yếu tốt xấu rõ ràng mới cũ kinh doanh học làm
nghĩ tưởng tượng giống khác biệt bằng tức bếp bánh chiếc cỗ tấm bức hồ sơ
giấy tờ trách nhiệm lợi ích tác động kết luận nhận định dù sao vốn và vốn dĩ
đặc biệt bối nội dung trực tuyến vâng nhé thật sự tất cả sắp xếp chủ đề
ai api cpu gpu tts video công cụ gợi ý ý nghĩa miễn là dẫu tuy nhiên liệu
""".split())
TOKEN=re.compile(r"[^\W\d_][^\W_]*(?:[-.][^\W_]+)*",re.UNICODE)
VOWELS="aăâeêioôơuưyàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
SYLLABLE=re.compile(r"(?:ngh|ng|gh|gi|kh|nh|ph|th|tr|ch|qu|[bcdđghklmnpqrstvx])?["+VOWELS+r"]{1,3}(?:ch|nh|ng|[cmnptk])?",re.I)


def common(word): return unicodedata.normalize("NFC",word).casefold() in COMMON


def foreign_token(word):
    if common(word): return False
    # Brands/acronyms and identifiers remain visible even at sentence start.
    if re.search(r"[a-z][A-Z]|\d|[-.]",word) or (word.isupper() and len(word)>1): return True
    return word.isascii() and not SYLLABLE.fullmatch(word)


def at_boundary(text,start):
    before=text[:start].rstrip(' \t\"“\'([{')
    return not before or before[-1] in ".!?:;—–\n\r" or bool(re.search(r"(?:^|\n)\s*(?:[-*•]|\d+[.)])\s*$",text[:start]))


def proper_names(text):
    tokens=list(TOKEN.finditer(unicodedata.normalize("NFC",text)))
    # Application JSON/narration is NFC; do not change offsets of the caller.
    if unicodedata.normalize("NFC",text)!=text: tokens=list(TOKEN.finditer(text))
    index=0
    while index<len(tokens):
        first=tokens[index];word=first[0]
        if not word[0].isupper() or common(word): index+=1;continue
        last=index
        while last+1<len(tokens):
            nxt=tokens[last+1]
            gap=text[tokens[last].end():nxt.start()]
            if not nxt[0][0].isupper() or common(nxt[0]) or not gap.isspace() or "\n" in gap: break
            last+=1
        if last>index or foreign_token(word) or not at_boundary(text,first.start()):
            # Match anchored at the actual offset; repeated names keep correct spans.
            yield re.compile(re.escape(text[first.start():tokens[last].end()])).match(text,first.start())
        index=last+1
