# Mẫu đồ họa local

Sáu module trong `editor/templates/` dùng Pillow + MoviePy 2; mỗi module có
`render(data, duration, size, theme)`. Không dùng ImageMagick hay thư viện mới.

- `hook_card`: hook, từ nhấn, ease-out-back.
- `stat_card`: đếm tới `value` (số gốc), `unit`, nhãn và nguồn.
- `steps_list`: `items` tối đa bốn mục, hiện lần lượt kèm dấu tích.
- `compare_bars`: `bars` với `label`, `value`, `unit`, `fact_id`.
- `source_card`: tên nguồn, ngày, tiêu đề; gần đầu và cuối video.
- `text_focus`: kết luận và từ nhấn.

`config/themes.yaml` đặt nền gradient/giấy, màu, bo góc, bóng. `image` tùy chọn
chỉ trỏ tới ảnh trong `assets/backgrounds/`. Font ưu tiên DTPhudu Bold.
Nền stock được crop-cover, chuyển động nhẹ, blur và tối; thiếu stock dùng theme.
Nội dung thẻ được rút gọn và co chữ để không tràn vùng trung tâm.
Thẻ tiếp tục có nhịp chuyển động/điểm nhấn ba giây sau khi hiện hết các mục.

Director chọn mẫu bằng code từ brief sau khi kiểm tra kịch bản. Visual có
`data.fact_ids`; luật nhóm 1 `visual_grounding` kiểm tra số, nguồn, URL, ngày,
tên riêng. Không tạo số minh họa cho video thật. Hai nguồn/đại lượng chỉ được
so sánh khi cùng đơn vị và cùng cơ sở. Chọn thủ công cần kiểm tra ý nghĩa.
Nguồn trên thẻ có thể thay câu dẫn `Theo ...` trong kịch bản mới. Với audio cũ,
renderer giữ nguyên lời đọc đã thu, không tự cắt câu dẫn.

Trong hồ sơ phong cách có `visual_theme`, `visual_templates`, `progress_tracker`,
`progress_labels` và `captions.appearance` (`classic` hoặc `pill`). Khi tạo plan,
các tùy chọn được chép sang `render_style` và có thể chỉnh ở Edit Plan.
Thanh tiến trình tối đa sáu nhóm nhãn để đọc được trên điện thoại.
Phụ đề được chuyển xuống vùng .68–.82 chiều cao khi có mẫu đồ họa.

Preview: 540x960 (hoặc 960x540) / 15fps. Final: 1080x1920
(hoặc 1920x1080) / 30fps. H.264 + AAC + yuv420p + faststart.
Các sự kiện hiện phần tử chèn pop/whoosh nếu có file trong assets/sfx;
không có thì bỏ qua. Nhạc ưu tiên file chứa tên mood, giữ ducking/peak limiter.

Trang **Xem trước mẫu** có JSON thử và xuất hoạt ảnh trong thread; dữ liệu
minh họa không được đưa vào project. Mẫu thử không gọi API.

## Demo Barclays offline

```
python -m editor.template_demo output/auto-cong-nghe-57970c7e
```

Lệnh tạo project riêng `barclays-templates-<id>`, tái sử dụng brief và audio
đã có, hiển thị đủ sáu mẫu trong 30 giây. Khoảng 20 giây là lời đọc có sẵn;
phần còn lại là khoảng nghỉ xem thẻ (có ghi trong report), không tạo lời đọc
mới hay kéo dài kịch bản sản xuất. Không sửa project gốc, không tải stock,
không gọi Gemini/edge-tts. Đọc `render/preview.json` để xem thông số MP4.
