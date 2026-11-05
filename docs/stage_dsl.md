# Stage Engine DSL (Kịch bản chuyển động Sân khấu)

Tài liệu đặc tả hợp đồng dữ liệu cho Stage Engine (Giai đoạn 5a).
Được sinh từ Pydantic Schema `editor.stage.schema.StageScript`.

## 1. Khái niệm cốt lõi

Khác với mô hình chuyển cảnh cũ (mỗi cảnh dựng lại từ đầu và xoá sạch trạng thái), **Stage Engine** coi toàn bộ video là:
- **SÂN KHẤU (Stage)**: Một không gian thế giới duy nhất với góc nhìn phối cảnh đẳng cự (Isometric 30°), hệ toạ độ không gian, camera có thể lia (pan), phóng thu (zoom), nghiêng (tilt) và trôi nhẹ (drift).
- **DIỄN VIÊN (Actors)**: Các thành phần đồ hoạ vector (SVG/CSS) tồn tại liên tục xuyên suốt các cảnh cho đến khi có hành động `exit`. Mỗi actor sở hữu các cổng kết nối (ports) để nối dây truyền dữ liệu và các trạng thái nội tại (states).
- **KỊCH BẢN HÀNH ĐỘNG (Actions & Verbs)**: Danh sách lệnh điều khiển theo thời gian tuyệt đối `t` (hoặc mốc từ `at_phrase` trong `words.json`).
- **HUD CỐ ĐỊNH**: Khung HUD 2D cố định trên màn hình (thương hiệu, thanh trạm tiến độ, tiêu đề bước, phụ đề đồng bộ, chú thích "hình mô phỏng").

---

## 2. Danh mục Verbs (Hành động)

| Verb | Mục đích | Tham số chính (`params`) |
|---|---|---|
| `enter` | Đưa actor vào sân khấu với hiệu ứng xuất hiện | `transition` (drop, pop, fade), `duration` |
| `exit` | Đưa actor ra khỏi sân khấu | `transition` (dissolve, shrink, drop), `duration` |
| `move_to` | Di chuyển actor đến vị trí mới trong lưới isometric | `to_pos`: `[x, y, z]` hoặc tên zone |
| `set_state` | Thay đổi trạng thái hiển thị của actor | `state`: chuỗi trạng thái (ví dụ laptop `open`/`typing`/`glow`) |
| `connect` | Vẽ đường cáp / đường nối giữa cổng 2 actor | `from_actor`, `from_port`, `to_actor`, `to_port`, `style` |
| `send_packet` | Bắn gói dữ liệu phát sáng chạy dọc theo đường nối | `connection_id`, `speed`, `color`, `label` |
| `type` | Gõ văn bản từng ký tự vào màn hình/terminal của actor | `text`, `speed`, `cursor` |
| `check` | Vẽ dấu tích xanh ✓ hoạt họa chứng thực hoàn thành | `target_station` hoặc `target_actor` |
| `open` / `close` | Gập mở nắp laptop hoặc mở/đóng cửa sổ | `duration` |
| `highlight` | Kích hoạt viền sáng / hào quang pulse glow xung quanh actor | `color`, `pulse_count` |
| `focus_camera` | Chuyển góc nhìn camera đến vị trí actor | `x`, `y`, `zoom`, `duration` |
| `label` | Cập nhật nhãn chú thích cho actor (kèm nhãn phụ "ví dụ") | `text`, `sublabel` |
| `blur_dissolve` | Chuyển cảnh mờ nhoè nghệ thuật | `duration` |
| `glitch` | Hiệu ứng giật tín hiệu lỗi RGB split | `intensity`, `duration` |
| `stamp` | Đóng mộc con dấu xác thực hoặc cảnh báo | `text`, `color` |

---

## 3. Cấu trúc JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "StageScript",
  "type": "object",
  "properties": {
    "theme": {
      "type": "object",
      "properties": {
        "name": {"type": "string", "default": "neon_purple"},
        "primary": {"type": "string"},
        "secondary": {"type": "string"},
        "accent": {"type": "string"},
        "bg": {"type": "string"},
        "grid": {"type": "string"},
        "text": {"type": "string"},
        "glow": {"type": "string"}
      }
    },
    "hud": {
      "type": "object",
      "properties": {
        "brand": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "active_step": {"type": "integer"},
        "completed_steps": {"type": "array", "items": {"type": "integer"}},
        "tracker_style": {"type": "string", "enum": ["stations", "road"]},
        "footer_note": {"type": "string"}
      },
      "required": ["brand", "steps"]
    },
    "actors": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "type": {"type": "string"},
          "pos": {"anyOf": [{"type": "array", "items": {"type": "number"}}, {"type": "string"}]},
          "state": {"type": "string"},
          "label": {"type": "string"},
          "sublabel": {"type": "string"}
        },
        "required": ["id", "type"]
      }
    },
    "scenes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "scene_id": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
          "step_index": {"type": "integer"},
          "title": {"type": "string"},
          "duration_sec": {"type": "number"},
          "camera": {"type": "object"},
          "actions": {"type": "array", "items": {"type": "object"}}
        },
        "required": ["scene_id", "step_index", "title", "duration_sec", "actions"]
      }
    },
    "recap": {
      "type": "object",
      "properties": {
        "morph_tracker_to": {"type": "string", "enum": ["road"]}
      }
    }
  },
  "required": ["hud", "actors", "scenes"]
}
```

---

## 4. Nguồn Sự thật Danh mục (Catalog Single Source of Truth)

Từ **Giai đoạn 8-W2b-1**, toàn bộ danh mục diễn viên và thế giới isometric được quản lý thống nhất tại một nguồn duy nhất: `editor/stage/catalog.json`.
Cả Python (schema Pydantic `StageScript`, `ActorDef`, Visual Bible `schemas/visual_bible.py`, `agents/visual_bible.py`) và runtime JavaScript (`editor/stage/engine/stage.js`) đều đọc và đối chiếu trực tiếp từ file catalog này.

### 4.1 Danh mục Diễn viên (28 Actors)
- **Thiết bị & Giao diện**: `laptop`, `terminal_window`, `browser_window`, `note_board`.
- **Hạ tầng & Đám mây**: `vps_server`, `docker_container`, `container_box`, `cloud`, `datacenter`.
- **Dữ liệu & Luồng**: `code_repo`, `git_repo`, `pipeline_node`, `clock_timer`, `database_cylinder`, `gauge_meter`.
- **An ninh & Bảo mật**: `lock_shield`, `bug_virus`, `key_vault`, `firewall_wall`, `alert_beacon`, `magnifier_scan`, `shield_broken`.
- **Pháp lý & Tư pháp**: `balance_scale`, `document_paper`, `folder_stack`, `gavel_court`.
- **Nhân vật & Mascot**: `user_figure`, `mascot` (Robot trợ lý isometric với 4 trạng thái: `idle`, `pointing`, `wave`, `alert`).

Mỗi diễn viên có $\ge 3$ trạng thái hiển thị, kích thước mặc định 3D, các cổng kết nối dữ liệu `ports`, nhãn chữ lớn $\ge 36$px và đảm bảo nằm an toàn trong khung $[70, 1010] 	imes [240, 1330]$.

### 4.2 Danh mục Thế giới (7 Worlds)
- `secure_building`: Tòa nhà An ninh & Trung tâm Dữ liệu (Sàn lưới cyber, ranh giới an toàn Level 4, 3 zones: cổng an ninh, phòng máy chủ, khu quản trị).
- `data_pipeline`: Hạ tầng Luồng Dữ liệu & Mạng (Ống dẫn cáp quang, trạm API, bể dữ liệu).
- `courtroom`: Khán phòng Tòa án & Pháp lý (Bục gỗ tư pháp, vành móng ngựa, bàn thẩm phán, khu tranh tụng).
- `city_road`: Đại lộ Đô thị & Giao thông (Đường băng nhựa đường 3D, vạch kẻ đường, trạm dừng).
- `generic_stage`: Sân khấu Isometric Đa năng (Lưới neon không gian).
- `workshop`: Xưởng Chế tạo Kỹ thuật.
- `lab`: Phòng Thí nghiệm & Nghiên cứu.
