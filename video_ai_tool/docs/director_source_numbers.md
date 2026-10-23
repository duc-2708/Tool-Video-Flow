# Nguồn trong hồ sơ mẫu và số dùng để kiểm tra

`grounding_names_quotes` vẫn là nhóm 1. Tên trích dẫn được đối chiếu đúng danh sách `source_name`/tên báo từ URL của brief, không dựa vào việc một tên tình cờ xuất hiện trong nội dung fact. Tên báo chứa chữ “và” được kiểm tra nguyên tên trước khi xem xét nhiều nguồn cùng câu.

Mọi lượt Director và retry riêng cảnh nhận `allowed_sources` từ brief. Prompt buộc chép chính xác tên nguồn, giữ chữ số trong tên riêng. Hồ sơ mẫu được làm sạch khi tổng hợp, khi lưu và ngay trước khi chuyển thành guidance; tên riêng và dữ kiện trong trường mô tả được thay bằng `{topic}`, `{source}`, `{number}`. Nhịp, thời lượng, số shot và thông số render dạng số vẫn được giữ. Bản thô/tóm tắt mẫu giữ tại máy để đối chiếu và chống sao chép, bị loại khỏi mọi prompt Director. Không cần gọi Gemini để làm sạch hồ sơ cũ. Hồ sơ danh mục có phiên bản chữ ký mới để tự tổng hợp lại tại máy.

Director giữ narration ở dạng số chuẩn, kiểm tra/audit rồi mới lưu. Chỉ `pipeline.assets` chuyển số và đơn vị sang cách đọc ngay trước `tts.synthesize`; văn bản đã chuyển không ghi ngược vào narration của Edit Plan. Tên nguồn và tên sản phẩm có số đã có trong brief/chủ đề được bảo vệ khi đổi cách đọc. Caption vẫn hiển thị lời đọc chuẩn của kế hoạch.

Để sửa và kiểm tra dự án cũ, bộ số vẫn hiểu số tiếng Việt. “hai mươi bốn” được đọc nguyên cụm thành 24; các từ nối ngày/tháng/năm tách riêng, không gộp “mười năm hai nghìn…” thành 12026. Các định dạng d/m/yyyy, m/yyyy và dấu chấm/gạch ngang của ngày được tách trước khi nhận dạng dấu nghìn/thập phân. `1.000`, `1,5`, `0,10`, `$0.10`, triệu/M và phần trăm giữ quy tắc so sánh theo giá trị.

Tên có số chỉ được miễn kiểm tra số khi là toàn bộ tên đã được cho phép; tên sản phẩm chứa phiên bản không cho phép dùng cùng số đó như một giá tiền không có căn cứ.

Với `auto-tin-tuc-ee3f1898`, brief thực tế có “Tin tức 24h”. Lỗi nguồn là alias TTS cũ “Tin tức hai mươi bốnh”. Code chỉ khôi phục alias về tên thật khi chính nguồn đó có trong brief, gộp nhãn nguồn bị lặp; nguồn không được phép vẫn bị chặn nhóm 1. Bản nháp gốc được giữ nguyên; test đọc đúng file để đối chiếu, không gọi API.
