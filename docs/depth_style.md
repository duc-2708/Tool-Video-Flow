# Depth Style Guide (Quy chuẩn Lớp Chiều sâu 3D & Phối cảnh Isometric)

Hướng dẫn thiết kế mỹ thuật và quy chuẩn hiển thị lớp chiều sâu 3D cho video dọc 1080x1920 (Giai đoạn 6), áp dụng đồng bộ cho cả **Motion Engine** và **Stage Engine**.

---

## 1. Hệ sinh thái Chiều sâu 3D & Quy tắc 3 Mặt (3-Face Shading Rule)

### 1.1 Hướng sáng cố định (Fixed Light Source)
- **Vị trí nguồn sáng**: Trên - Trái (Top-Left), góc chiếu ánh sáng chuẩn $45^\circ$ từ phía trước bên trái rọi xuống.
- Mọi vật thể trong cùng khung hình đều tuân theo cùng một hướng sáng duy nhất nhằm giữ vững tính nhất quán thị giác.

### 1.2 Quy tắc 3 mặt (3-Face Lighting)
Khi một vật thể được nâng lên dạng khối lập thể 3D (Isometric/Perspective Cuboid):
1. **Mặt trên (Top Face)**:
   - Hứng sáng trực tiếp, là **mặt sáng nhất**.
   - Màu sắc: Tăng độ sáng $+15\%$ so với màu gốc (hoặc gradient phản quang specular nhẹ ở mép đón sáng).
   - Viền đón sáng: Viền neon $2 - 3\text{px}$ sắc nét (`rgba(255, 255, 255, 0.4)` kết hợp màu accent).
2. **Mặt trái (Left Face)**:
   - Hứng sáng xiên, là **mặt trung bình (Midtone)**.
   - Màu sắc: Giữ màu nền gốc hoặc giảm nhẹ $-10\%$ độ sáng.
3. **Mặt phải / Mặt đáy (Right / Shaded Face)**:
   - Khuất sáng, là **mặt đổ bóng tối (Shadowed Face)**.
   - Màu sắc: Giảm $-25\%$ đến $-30\%$ độ sáng để tạo cảm giác dày khối rõ rệt.

### 1.3 Độ dày Extrusion (Extrusion Depth)
Độ dày khối được chuẩn hóa theo kích thước vật thể:
- **Cột biểu đồ / Thanh đo / Ring (bar_compare, gauge_ring)**: Độ dày $35\text{px} - 55\text{px}$.
- **Tấm thẻ / Khối đối đầu (versus_split, slab card)**: Độ dày $45\text{px} - 75\text{px}$.
- **Huy hiệu nổi / Biểu tượng trung tâm (VS badge, milestone)**: Chiều sâu nhô về phía camera $z = +50\text{px}$ đến $+80\text{px}$.

### 1.4 Bóng đổ & Bóng tiếp xúc (Contact Shadow)
- **Bóng tiếp xúc (Contact Shadow)**: Dưới đáy mỗi vật thể 3D luôn có một bóng elip dẹp bám sát chân vật thể trên mặt sàn phối cảnh:
  - Màu sắc: `rgba(0, 0, 0, 0.65)` đến `rgba(0, 0, 0, 0.85)`.
  - Biến đổi: `scale(1, 0.32) rotate(-15deg)` đồng bộ góc chiếu isometric.
  - Khi vật thể nảy lên cao, bóng tiếp xúc co nhỏ lại và mờ dần (`opacity` giảm tỉ lệ với độ cao $z$).
- **Bóng đổ mềm (Soft Ambient Shadow)**: Trải nhẹ về góc dưới-phải (hướng đối diện nguồn sáng).
- **Viền sáng Neon (Edge Neon Glow)**: Viền dạ quang $2 - 3\text{px}$, độ loang nhẹ `drop-shadow(0 0 10px rgba(accent, 0.45))`.

---

## 2. Nền 3D: Sàn Lưới Phối cảnh & Parallax

### 2.1 Sàn lưới phối cảnh (Perspective Floor Grid)
- **Điểm tụ (Vanishing Point)**: Cố định tại $cx = 540\text{px}, cy = 700\text{px}$ (vùng chân trời phối cảnh).
- **Hệ lưới sàn**:
  - Các đường toả (radial lines) phát xuất từ điểm tụ chạy về phía đáy màn hình.
  - Các đường ngang (transverse lines) có khoảng cách dãn dần theo luật phối cảnh 3D.
  - Màu lưới: `rgba(157, 78, 221, 0.16)` ở xa, đậm dần lên `rgba(0, 245, 212, 0.22)` ở gần.
- **Chuyển động trôi (Drift Motion)**:
  - Lưới sàn trôi nhẹ nhàng và mượt mà về phía camera theo trục $z$/$y$.
  - Tính toán chuyển động tuyệt đối theo thời gian $t$ (`offset = (t * speed) % gridStep`), hoàn toàn deterministic và seekable.
  - Chân trời mờ dần vào nền đen sâu (fade horizon) bằng gradient dọc mượt mà, **tuyệt đối không để lại quầng tròn mờ đứng yên gây cảm giác "vết bẩn"**.

### 2.2 Đa tầng Parallax (3-Tier Parallax Depth)
1. **Lớp xa (Far Depth Layer)**:
   - Bụi sao/hạt vi mô kích thước $1 - 2\text{px}$, độ mờ $30\%$, vận tốc trôi chậm ($10\text{px/s}$).
2. **Lớp giữa (Mid Depth Layer)**:
   - Các hạt neon dạ quang kích thước $3 - 4\text{px}$, độ mờ $60\%$, vận tốc trôi trung bình ($30\text{px/s}$).
3. **Lớp gần (Near Depth Layer)**:
   - Vài hạt ánh sáng nổi bật kích thước $5 - 7\text{px}$, độ mờ $85\%$, vận tốc trôi nhanh ($70\text{px/s}$) tạo chiều sâu mạnh mẽ cho khung hình.

---

## 3. Quy chuẩn 3 Element Cốt lõi (Bước a)

### 3.1 `bar_compare` 3D (Cột khối lập thể)
- Mỗi cột là một khối lăng trụ 3D (Cuboid) gồm 3 mặt rõ rệt (`face-top`, `face-left`, `face-right`).
- Hiệu ứng mọc: Cột nhô cao từ sàn lưới lên giá trị mục tiêu với easing nảy nhẹ (overshoot bounce).
- Đỉnh cột: Mặt trên phát sáng neon, số liệu chính ($\ge 120\text{px}$ cho số nổi bật) đặt ngay trên đỉnh cột, luôn thẳng đứng hoặc nghiêng góc $\le 10^\circ$ để đọc rõ ràng.
- Bóng tiếp xúc elip bám dưới chân từng cột.
- Thẻ ghi chú `source_badge` đặt ở khu vực riêng (dưới đáy hoặc góc trên), không che lên thân cột.

### 3.2 `gauge_ring` 3D (Vòng đo 3D nghiêng phối cảnh)
- Vòng tròn đồng hồ đo được đặt nằm trên mặt phẳng nghiêng phối cảnh ($rotateX \approx 42^\circ, rotateZ \approx -12^\circ$).
- Độ dày thành (Extrusion depth $35\text{px} - 45\text{px}$) gồm 2 vành trên-dưới và dải thành bên nối liền.
- Rãnh quét tiến độ (Arc sweep) phát sáng rực rỡ; khi đạt đích hoặc $100\%$ kích hoạt hiệu ứng xung nhịp ánh sáng (glow pulse).
- Số phần trăm to ở tâm vòng, chữ không bị xoay nghiêng quá $12^\circ$.

### 3.3 `versus_split` 3D (Hai khối đối đầu & Huy hiệu VS nổi)
- Hai tấm thẻ dày (3D slabs, độ dày $45\text{px} - 65\text{px}$) đối đầu từ 2 phía, nghiêng góc phối cảnh đối xứng ($-10^\circ$ và $+10^\circ$).
- Mặt trước và các cạnh bên có viền neon màu đối lập (Cyan vs Magenta/Purple).
- Hai khối trượt vào va chạm (slam/clash), tạo xung sóng ánh sáng nhẹ.
- Huy hiệu "VS" ở giữa là khối 3D độc lập nhô hẳn ra phía trước camera ($translateZ \approx +65\text{px}$), phát hào quang nổi bật.

---

## 4. Quy chuẩn 6 Element Nâng cao & Camera 3D (Bước b)

### 4.1 `hub_spoke` / `network_nodes` 3D (Mạng lưới Vệ tinh & Quỹ đạo Phối cảnh)
- **Nút trung tâm 3D**: Khối hình trụ dẹp 3D (Cylinder / Disc) đặt tại tâm $cx = 540\text{px}, cy = 760\text{px}$, độ dày extrusion $30\text{px}$, nắp sáng đón hướng Top-Left, nhãn trung tâm $\ge 38\text{px}$.
- **Quỹ đạo phối cảnh nghiêng $58^\circ$**: Elip nghiêng $rx = 360\text{px}, ry = 175\text{px}$ với đường nét đứt dạ quang.
- **Vệ tinh 3D**: 3 đến 5 khối vệ tinh cuboid bo góc ($180\text{px} \times 95\text{px}$), trôi nhẹ nhàng trên quỹ đạo, nằm gọn trong $[110, 970]$ ngang (cách mép an toàn $\ge 40\text{px}$), nhãn $\ge 32\text{px}$ ($\le 3$ từ).
- **Tia nối & Luồng dữ liệu (Data Stream)**: Tia nối SVG phát sáng, trên mỗi tia có 2-3 gói file (data packets) chạy tuần hoàn liên tục từ trung tâm ra vệ tinh.
- **Sóng quét Highlight tuần hoàn**: Chu kỳ quét beacon kích hoạt từng vệ tinh bừng sáng (glow pulse, scale 1.08, viền neon cyan rực rỡ).

### 4.2 `checklist` / `steps_ladder` 3D (Tấm dày Xếp bậc & ✓ Nảy 3D)
- **3D Stacked Slabs**: Các tấm chữ nhật dày ($860\text{px} \times 108\text{px}$, độ dày $24\text{px}$) xếp chồng theo chiều dọc ($y \in [530, 1040]$, căn tâm $cy \approx 785\text{px}$).
- **Trồi lên theo nhịp $t$**: Các tấm slab xuất hiện so le (stagger $0.25\text{s}$) với hiệu ứng nảy overshoot mượt mà.
- **Tấm Active nổi bật**: Tấm đang được đọc nhô cao hơn về phía camera ($translateZ = +35\text{px}$), viền neon cyan rực rỡ và bóng đổ tiếp xúc dạt ra phía sau.
- **Dấu $\checkmark$ nảy 3D**: Khi quét tới hàng, dấu $\checkmark$ nảy bật từ mặt tấm (bounce scale $0 \to 1.35 \to 1.0$), vẽ nét stroke neon xanh `#22c55e`. Chữ nhãn $\ge 38\text{px}$ đọc rõ ràng.

### 4.3 `stat_number` 3D (Số Lớn Extrusion Đa tầng & Bệ đỡ 3D)
- **Hero Stat Number**: Số lớn nổi bật ($\ge 160\text{px}$, $175\text{px}$) căn giữa tại $cx = 540\text{px}, cy = 760\text{px}$.
- **Extrusion đa tầng $45^\circ$**: Đổ bóng khối 3D sắc nét bằng chuỗi `text-shadow` 8 tầng chuyển màu dần từ cyan sáng sang bóng đen sâu, kết hợp viền dạ quang neon.
- **Bệ đỡ 3D (3D Pedestal Base)**: Đĩa elip dẹp 3D ($rx = 300\text{px}, ry = 85\text{px}$, độ dày $32\text{px}$) đỡ dưới chân số, có bóng tiếp xúc elip bám sàn phối cảnh.
- **Đếm số mượt mà**: Chạy số theo nhịp $t$ với easing out back; nhãn tiêu đề trên $\ge 32\text{px}$ và chú thích dưới $\ge 36\text{px}$.

### 4.4 `flow_chain` 3D (Băng chuyền Trạm Khối & Dòng Gói File)
- **3 Trạm khối Isometric (Station Cuboids)**: Kích thước $240\text{px} \times 145\text{px}$, bố trí zic-zac phối cảnh trên sàn lưới ($y \in [560, 980]$), tuân theo quy tắc 3 mặt sáng-tối.
- **Ống dẫn / Băng chuyền 3D**: Đường dẫn phát sáng nối liên tục giữa các trạm.
- **Dòng gói file (Stream Packets)**: Các hạt năng lượng neon chạy liên tục qua các trạm (`(t * speed) % 1.0`), thể hiện dòng xử lý dữ liệu liên tục không ngắt quãng.
- **Nhãn trạm**: Số thứ tự trạm lớn ($26\text{px}$ bold), tên trạm $\ge 36\text{px}$ và chi tiết $\ge 26\text{px}$.

### 4.5 `terminal` / `mock_ui_window` 3D (Cửa sổ Phối cảnh & Gõ phím)
- **Phối cảnh nghiêng nhẹ**: Cửa sổ kích thước $860\text{px} \times 500\text{px}$, nghiêng phối cảnh `perspective(1200px) rotateX(6deg) rotateY(-8deg)`.
- **Viền mép Bezel 3D**: Thành viền dày $24\text{px}$ có specular highlight neon `#00f5d4` và bóng đổ tiếp xúc lớn dưới đáy.
- **Titlebar 3D**: Thanh tiêu đề với 3 nút bấm tròn MacOS phong cách dạ quang (đỏ, vàng, xanh) và nhãn tiêu đề phiên bản.
- **Hiệu ứng gõ phím**: Từng ký tự dòng lệnh xuất hiện tuần tự theo $t$, con trỏ nhấp nháy 3D nhịp nhàng; chữ dòng lệnh $\ge 36\text{px}$ rõ nét.

### 4.6 `road_tracker` 3D (Con đường Bezier Phối cảnh & Trạm Mốc)
- **Con đường 3D Bezier Ribbon**: Dải đường uốn lượn phối cảnh từ xa ($y \approx 460\text{px}$, hẹp) mở rộng dần về gần ($y \approx 1180\text{px}$, rộng $140\text{px}$), có dải vạch kẻ đứt tim đường.
- **Trạm mốc Cuboid**: 3-4 trạm mốc 3D dọc theo đường có số trạm và nhãn $\ge 32\text{px}$.
- **Marker Puck / Beacon phát sáng**: Con trỏ dạ quang chạy dọc theo quỹ đạo cong Bezier; khi chạm tới trạm mốc nào thì trạm đó bừng sáng viền neon và nhô lên.

### 4.7 Hệ thống Camera 3D (`depth_camera`)
- **Bộ chuyển động mượt mà**:
  - Dolly-in/out: scale $1.0 \to 1.05$, translateZ $0 \to 35\text{px}$.
  - Pan ngang: $X \pm 28\text{px}$.
  - Pan dọc: $Y \pm 20\text{px}$.
  - Nghiêng nhẹ: rotateX $\le 6^\circ$, rotateY $\le 6^\circ$.
  - Orbit chậm: $\le 4^\circ$.
  - Impact bump: $\le 5\text{px}$ (decay nhanh trong $0.3\text{s}$).
- **Ràng buộc an toàn tuyệt đối**: Kẹp chặt các thông số biến đổi để mọi vật thể luôn nằm gọn trong $[70, 1010]$ ngang và $y \in [240, 1330]$, **tuyệt đối KHÔNG xâm lấn vùng phụ đề $y \in [1380, 1700]$ kể cả bóng đổ hay glow**.

---

## 5. Ràng buộc Kỹ thuật & Bố cục An toàn (1080x1920)

- **Vùng nội dung an toàn**: Sau mọi phép chiếu và biến đổi 3D, bounding box thực tế của toàn bộ vật thể phải nằm gọn trong $[70, 1010]$ ngang và $y \in [240, 1330]$.
- **Vùng phụ đề cố định**: $y \in [1380, 1700]$ — cấm mọi vật thể, bóng đổ hoặc glow lấn vào.
- **Typography an toàn**:
  - Tiêu đề chính $\ge 56\text{px}$.
  - Nhãn số & nhãn quan trọng $\ge 36\text{px}$.
  - Góc nghiêng chữ trên mặt 3D $\le 12^\circ$ (nếu mặt vật thể nghiêng nhiều hơn, chữ được bù góc `un-rotate` để giữ khả năng đọc tối ưu).
- **Mật độ phần tử**: Tối đa 8 khối 3D hiển thị cùng một lúc để tránh rối mắt và bảo toàn hiệu năng.
- **Deterministic**: Tuyệt đối seekable theo thời gian $t$, không dùng `requestAnimationFrame` phụ thuộc wall-clock, RNG có seed.
- **Cơ chế Fallback**: Khi `DEPTH_3D_ENABLED=false` hoặc khi có lỗi render/audit đỏ, tự động chuyển về renderer phẳng 2D an toàn.
