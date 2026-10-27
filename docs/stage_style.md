# Stage Style Guide (Quy chuẩn phong cách Isometric Neon Sân khấu)

Hướng dẫn thiết kế mỹ thuật và quy chuẩn hiển thị cho Stage Engine (dựa theo ngôn ngữ thị giác video mẫu công nghệ `cong_nghe_5`).

## 1. Hệ trục toạ độ Isometric 30°

- **Góc chiếu**: Góc nghiêng chuẩn $30^\circ$ so với phương ngang.
- **Biến đổi toạ độ từ 3D sang 2D màn hình**:
  $$x_{\text{screen}} = x_{\text{origin}} + (x - y) \cdot \cos(30^\circ)$$
  $$y_{\text{screen}} = y_{\text{origin}} + (x + y) \cdot \sin(30^\circ) - z$$
- **Lưới toạ độ (Isometric Grid)**:
  - Màu lưới: `rgba(157, 78, 221, 0.18)` đến `rgba(0, 245, 212, 0.12)`.
  - Khoảng cách ô lưới: $60\text{px}$.
  - Nền không gian: Gradient tối sâu từ `#09041a` (tím đêm) sang `#030108` (đen vũ trụ), kết hợp các đốm sáng bokeh neon mờ ảo.

---

## 2. Bảng màu chủ đạo (Neon Purple Palette)

- **Màu nền (Background)**: `#09041a` / `#12072b`.
- **Màu neon chủ đạo (Primary Accent)**: `#9d4edd` (Tím dạ quang sáng) và `#c77dff`.
- **Màu dữ liệu & tín hiệu (Cyan/Teal Data)**: `#00f5d4` (Xanh ngọc phát sáng - biểu trưng cho kết nối, gói tin, Docker, cổng mạng).
- **Màu cảnh báo & hành động (Hot Pink/Magenta)**: `#f72585` (Hồng dạ quang - biểu trưng cho lỗi, điểm nhấn, con dấu).
- **Màu bề mặt khối (Isometric Faces)**:
  - Mặt trên (Top face - sáng nhất): Gradient sáng 15% so với màu nền khối.
  - Mặt trái (Left face - trung bình): Gradient tối hơn 10%.
  - Mặt phải (Right face - đổ bóng): Gradient tối hơn 25%.
- **Nét vẽ (Stroke)**: Độ dày nét $2\text{px} - 3\text{px}$, hiệu ứng phát sáng `filter: drop-shadow(0 0 6px rgba(0, 245, 212, 0.6))`.

---

## 3. Phân vùng an toàn và Typography (Khung 1080x1920)

- **Vùng HUD trên (Top HUD)**: $y = 60 - 240\text{px}$.
  - Huy hiệu thương hiệu / kênh: cao $50\text{px}$, biểu tượng + chữ $+ \text{sóng âm equalizer}$.
  - Thanh trạm tiến độ (Station Tracker): $y = 150 - 230\text{px}$, 5 nút trạm tròn $\ge 40\text{px}$, đường nối phát sáng.
- **Vùng tiêu đề bước (Step Title)**: $y = 250 - 360\text{px}$.
  - Cỡ chữ tiêu đề chính: $\ge 56\text{px}$, font Bold, hiệu ứng trượt mờ và tô sáng từ khoá theo lời đọc.
- **VÙNG SÂN KHẤU CHÍNH (Stage World Safe Area)**:
  - $y = 380 - 1460\text{px}$ (Chiều cao $1080\text{px}$, chiều rộng $940\text{px}$).
  - Tâm sân khấu: $cx = 540, cy = 920$.
  - Cỡ chữ nhãn actor chính: $\ge 30\text{px}$.
  - Cỡ chữ nhãn phụ / thông số / "ví dụ": $\ge 24\text{px}$.
- **Vùng phụ đề và ghi chú chân trang (Bottom Safe Zone)**:
  - Viên thuốc phụ đề đồng bộ (Subtitle Pill): $y = 1500 - 1720\text{px}$, cỡ chữ $38\text{px} - 44\text{px}$.
  - Chân trang: $y = 1750 - 1860\text{px}$, dòng chữ mờ "hình mô phỏng" ($\ge 24\text{px}$) và các chấm tiến độ nhỏ.

---

## 4. Tài liệu trạng thái của 5 Actor ban đầu

1. **`laptop` (Máy tính cá nhân)**:
   - Thân máy góc isometric $30^\circ$, bàn phím phát sáng, trackpad.
   - Nắp màn hình:
     - `closed`: nắp gập sát thân máy, logo phát sáng mờ.
     - `open`: nắp mở góc $115^\circ$, màn hình hiển thị code/giao diện.
     - `typing`: con trỏ nhấp nháy, các dòng lệnh hiển thị dần với ánh sáng cyan.
     - `glow`: màn hình phát hào quang tím/xanh rực rỡ khi kết nối thành công.
   - Cổng kết nối (Ports): `net_out` (bên hông phải, toạ độ tương đối $[+110, +20, +15]$).
2. **`vps_server` (Máy chủ ảo / Rack Server)**:
   - Thùng máy isometric 3 chiều dạng khối lập phương kéo dài.
   - Các khay đĩa (drive bays) viền neon, quạt tản nhiệt mặt sau.
   - Dàn đèn LED trạng thái (Status LEDs):
     - `off`: đèn xám/đỏ mờ, rack tối.
     - `on`: dàn đèn LED xanh ngọc `#00f5d4` nhấp nháy tuần hoàn, hào quang xanh sáng.
     - `busy`: đèn cam/hồng `#f72585` quét liên tục biểu thị đang biên dịch/cài đặt.
   - Cổng kết nối (Ports): `net_in` (mặt trước bên trái), `ssh_port` (mặt trên).
3. **`data_packet` (Gói dữ liệu / File)**:
   - Khối đa diện phát sáng hoặc viên nang dạ quang có vệt đuôi (trail effect).
   - `idle`: trôi nổi bồng bềnh tại cổng.
   - `flying`: bay lướt dọc theo đường cong kết nối với vận tốc xác định.
4. **`connection_path` (Đường nối mạng)**:
   - Dây cáp mạng isometric nối giữa 2 cổng của 2 actor.
   - Hiệu ứng: các xung sóng ánh sáng (pulses) chạy liên tục dọc theo dây cáp.
5. **`progress_tracker` (Thanh trạm tiến độ)**:
   - Chế độ `stations`: thanh 2D ngang trên HUD gồm 5 trạm tròn, đường nối dâng màu, dấu tích ✓ hoàn tất.
   - Chế độ `road`: biến hình (morph) thành con đường 3D isometric uốn lượn chạy về chiều sâu phối cảnh trong màn tổng kết recap.
