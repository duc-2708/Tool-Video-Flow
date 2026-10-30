"""Test kiểm tra làm sạch vocabulary.js: không chứa nhãn/số mặc định bịa đặt."""
import re
from pathlib import Path


def test_vocabulary_no_hardcoded_vietnamese_fallbacks():
    """Vocabulary.js không được chứa các nhãn/cụm từ tiếng Việt gán cứng làm fallback mặc định."""
    vocab_path = Path(__file__).parent.parent / "editor" / "motion" / "recipes" / "vocabulary.js"
    assert vocab_path.exists(), f"File {vocab_path} không tồn tại"
    
    code = vocab_path.read_text(encoding="utf-8")
    
    # Loại bỏ comments // và /* ... */
    code_no_comments = re.sub(r"//.*?\n", "\n", code)
    code_no_comments = re.sub(r"/\*.*?\*/", "", code_no_comments, flags=re.DOTALL)
    
    # Các từ cấm tuyệt đối theo yêu cầu
    forbidden_phrases = [
        "Giải pháp cũ",
        "Giải pháp mới",
        "Kích hoạt",
        "Lan truyền",
        "Tăng tốc",
        "Bùng nổ",
        "Chỉ số bứt phá",
        "KẾT QUẢ ĐỘT PHÁ",
        "Bước chuyển đổi",
        "THAY ĐỔI VƯỢT BẬC",
        "Mức độ cảnh báo",
        "CHỈ SỐ ĐO LƯỜNG",
        "Chỉ số tích lũy",
        "CÔNG TƠ MÉT",
        "Cuộc đua tốc độ",
        "CUỘC ĐUA BỨT PHÁ",
        "Nhiệt lượng thị trường",
        "NHIỆT ĐỘ TĂNG CAO",
        "Nạp đầy năng lượng",
        "TIẾN ĐỘ HOÀN THÀNH",
        "Dung tích chứa",
        "MỨC ĐỘ ĐỔ ĐẦY",
        "So sánh lợi ích",
        "CÁN CÂN SO SÁNH",
        "Đội Xanh",
        "Đội Đỏ",
        "GIẰNG CO THỊ PHẦN",
        "Phương án A",
        "Phương án B",
        "Đối đầu trực diện",
        "SO SÁNH ĐỐI ĐẦU",
        "Trước đây",
        "Sau tối ưu",
        "Lột xác toàn diện",
        "CHUYỂN ĐỔI NGOẠN MỤC",
        "Quy trình sản xuất",
        "BĂNG CHUYỀN TỰ ĐỘNG",
        "Phản ứng dây chuyền",
        "HIỆU ỨNG DÂY CHUYỀN",
        "Sàng lọc cốt lõi",
        "PHỄU CHUYỂN ĐỔI",
        "Mạng lưới liên thông",
        "HẠ TẦNG KẾT NỐI",
        "Xác suất may rủi",
        "XÁC SUẤT ĐẦU TƯ",
        "Mở khóa then chốt",
        "GIẢI MÃ THEN CHỐT",
        "Phòng thủ vững chắc",
        "BẢO MẬT TUYỆT ĐỐI",
        "Tín hiệu thị trường",
        "TÍN HIỆU ĐÈN GIAO THÔNG",
        "HẠT NHÂN AI",
        "Hệ sinh thái liên kết",
        "HỆ SINH THÁI ĐỒNG BỘ",
        "Bản chất",
        "Bóc tách bản chất",
        "BÓC TÁCH ĐA TẦNG",
        "Ngăn xếp công nghệ",
        "THÁP NĂNG LỰC",
        "MẢNH GHÉP HOÀN HẢO",
        "Khớp nối giải pháp",
        "MẢNH GHÉP QUYẾT ĐỊNH",
        "Hội thoại thông minh",
        "HỘI THOẠI TRỰC QUAN",
        "Quyết định lựa chọn",
        "LỰA CHỌN CHIẾN LƯỢC",
        "Xử lý hồ sơ",
        "BIỂU MẪU TỰ ĐỘNG",
        "Thực thi câu lệnh",
        "DÒNG LỆNH HỆ THỐNG",
    ]
    
    found_violations = []
    for phrase in forbidden_phrases:
        if phrase in code_no_comments:
            found_violations.append(phrase)
            
    assert not found_violations, f"Phát hiện nhãn tiếng Việt mặc định trong vocabulary.js: {found_violations}"


def test_vocabulary_no_hardcoded_numeric_fallbacks():
    """Vocabulary.js không được chứa các số mặc định gán cứng làm fallback khi thiếu dữ liệu."""
    vocab_path = Path(__file__).parent.parent / "editor" / "motion" / "recipes" / "vocabulary.js"
    code = vocab_path.read_text(encoding="utf-8")
    
    # Loại bỏ comments
    code_no_comments = re.sub(r"//.*?\n", "\n", code)
    code_no_comments = re.sub(r"/\*.*?\*/", "", code_no_comments, flags=re.DOTALL)
    
    # Cấm các fallback số ảo cụ thể
    assert "d.value ?? 777" not in code_no_comments
    assert "d.value ?? 1250" not in code_no_comments
    assert "d.value ?? 82" not in code_no_comments
    assert "d.value ?? 92" not in code_no_comments
    assert "d.value ?? 95" not in code_no_comments
    assert "d.bars[0]?.value) ?? 30" not in code_no_comments
    assert "(1 - smoothedP) * 3" not in code_no_comments
