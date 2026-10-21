# file: app/ui_errors.py
"""Chuyển exception thành thông báo tiếng Việt và traceback đã che key."""
from utils.diagnostics import Diagnostics


def error_details(error: BaseException, diagnostics: Diagnostics) -> tuple[str, str]:
    root = error
    seen = {id(root)}
    while getattr(root,"code",None) != 400:
        parent = root.__cause__ or root.__context__
        if parent is None or id(parent) in seen:
            break
        root = parent
        seen.add(id(root))
    message = diagnostics.redact(str(root))
    code = getattr(root, "code", None)
    if code in {401, 403}:
        guidance = "Gemini từ chối xác thực hoặc quyền truy cập. Kiểm tra key và model."
    elif code == 429:
        guidance = "Gemini đang giới hạn tốc độ hoặc hết quota. Hãy thử lại sau."
    elif code == 400:
        guidance = "Gemini từ chối nội dung hoặc cấu trúc yêu cầu. Xem thông điệp gốc bên dưới."
    else:
        guidance = "Không hoàn tất thao tác. Kiểm tra cấu hình, nguồn dữ liệu hoặc kết nối mạng."
    summary = f"{guidance}\n\nNguyên nhân gốc ({type(root).__name__}): {message if code == 400 else message[:1500]}"
    # Khi exception dùng 'from None', vẫn cho UI debug thấy context gốc đã che key.
    trace = diagnostics.format_exception(error)
    if root is not error and root.__suppress_context__ is False and type(root).__name__ not in trace:
        trace = diagnostics.format_exception(root) + "\nLỗi ở pipeline:\n" + trace
    return summary, trace
