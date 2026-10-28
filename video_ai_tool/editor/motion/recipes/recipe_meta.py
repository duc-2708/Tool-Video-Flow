"""Metadata and descriptor schema for Motion Vocabulary Recipes."""
from dataclasses import dataclass, field, asdict
from typing import Any, List, Dict
from pathlib import Path
import json


@dataclass
class RecipeStage:
    name: str  # e.g., "enter", "action", "impact"
    start_sec: float
    end_sec: float
    description: str


@dataclass
class RecipeMetadata:
    name: str
    category: str  # "number_stat", "fill_level", "compare_vs", "process_flow", "risk_prob", "concept_relation", "mock_ui"
    meaning: str  # Ý nghĩa, dùng khi nào
    metaphor: str  # Ẩn dụ hình ảnh chủ đạo
    max_words: int = 3  # Nhãn tối đa <= 3 từ
    stages: List[Dict[str, Any]] = field(default_factory=list)
    idle_motion: str = "Thở nhẹ hoặc gợn sóng phát quang tuần hoàn"
    default_bbox: List[int] = field(default_factory=lambda: [100, 380, 880, 760])  # [x, y, w, h] kẹp trong 70..1010 x 240..1330
    status: str = "active"
    params_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


# 8 Core Recipes for Step (a)
RECIPES_PHASE_A: Dict[str, RecipeMetadata] = {
    "slot_counter": RecipeMetadata(
        name="slot_counter",
        category="number_stat",
        meaning="Dùng khi công bố số liệu đột phá, tỷ lệ tăng trưởng ấn tượng hoặc kết quả ngẫu nhiên may mắn",
        metaphor="Trục quay số máy đánh bạc (slot machine reel)",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Hộp máy kim loại 3D trồi lên, đèn viền bật sáng"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.2, "description": "Các cuộn số quay tít với vệt mờ motion blur từ 000 tăng vọt"},
            {"name": "impact", "start_sec": 2.2, "end_sec": 4.0, "description": "Từng cột số dừng lại 'cạch-cạch-cạch', rung nhẹ và bừng sáng neon"}
        ],
        idle_motion="Đèn LED viền nhấp nháy chạy vòng quanh khung máy",
        default_bbox=[140, 480, 800, 560],
        params_schema={"value": "float", "unit": "str", "label": "str", "digits": "int"}
    ),
    "strike_replace": RecipeMetadata(
        name="strike_replace",
        category="number_stat",
        meaning="Dùng khi bác bỏ số liệu cũ, phủ định định mức lạc hậu hoặc đưa ra mức giá/con số mới vượt trội",
        metaphor="Gạch bỏ sai lầm và vinh danh chân lý",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.7, "description": "Thẻ số cũ màu xám mờ xuất hiện ở vị trí trung tâm"},
            {"name": "action", "start_sec": 0.7, "end_sec": 1.8, "description": "Vết gạch chéo đỏ quét xoẹt qua kèm dấu ✗ nảy lên, số cũ tụt lùi"},
            {"name": "impact", "start_sec": 1.8, "end_sec": 4.0, "description": "Con số mới khổng lồ bừng sáng trồi lên từ phía sau, hào quang vàng rực"}
        ],
        idle_motion="Số mới bồng bềnh nhẹ, viền hào quang co giãn",
        default_bbox=[120, 460, 840, 600],
        params_schema={"old_value": "float", "new_value": "float", "unit": "str", "label": "str"}
    ),
    "gauge_needle": RecipeMetadata(
        name="gauge_needle",
        category="number_stat",
        meaning="Dùng khi đo lường mức độ rủi ro, áp lực, hiệu suất hoặc đo lường chỉ số trên ngưỡng an toàn/nguy hiểm",
        metaphor="Đồng hồ đo áp suất kim quay công nghiệp",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.7, "description": "Mặt đồng hồ bán nguyệt 3 màu (xanh-vàng-đỏ) mở rộng"},
            {"name": "action", "start_sec": 0.7, "end_sec": 2.3, "description": "Kim đo cơ học quay vọt từ 0 vượt qua dải an toàn hướng đến vùng đỏ"},
            {"name": "impact", "start_sec": 2.3, "end_sec": 4.0, "description": "Kim dao động nảy nhẹ ở đỉnh, còi/đèn cảnh báo phát sáng nhịp nhàng"}
        ],
        idle_motion="Kim đo rung nhẹ như có xung áp suất thật",
        default_bbox=[160, 440, 760, 680],
        params_schema={"value": "float", "max_val": "float", "unit": "str", "label": "str", "warning_threshold": "float"}
    ),
    "odometer": RecipeMetadata(
        name="odometer",
        category="number_stat",
        meaning="Dùng khi thể hiện tích lũy số lượng, quãng đường, thời gian hoặc chi phí lăn bánh tăng dần",
        metaphor="Trục số công-tơ-mét xe hơi cơ khí",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Cụm cửa sổ cơ khí bo tròn viền kim loại xuất hiện"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.4, "description": "Các bánh răng lăn liên tục, số hàng đơn vị cuộn nhanh kéo theo hàng chục và hàng trăm"},
            {"name": "impact", "start_sec": 2.4, "end_sec": 4.0, "description": "Trục số khớp vào vị trí đích với độ nảy cơ khí, số phát sáng"}
        ],
        idle_motion="Vệt sáng phản chiếu kim loại quét ngang mặt kính",
        default_bbox=[140, 500, 800, 520],
        params_schema={"value": "float", "unit": "str", "label": "str", "start_val": "float"}
    ),
    "bar_race": RecipeMetadata(
        name="bar_race",
        category="number_stat",
        meaning="Dùng khi so sánh sự bứt phá tốc độ, thị phần thay đổi hoặc đối tượng dẫn đầu vượt mặt đối thủ",
        metaphor="Cuộc đua nước rút giữa các thanh tốc độ",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.7, "description": "Các đường chạy và thanh đua xuất xưởng tại vạch xuất phát"},
            {"name": "action", "start_sec": 0.7, "end_sec": 2.5, "description": "Các thanh đồng loạt tăng tốc, thanh chủ đạo bứt phá ngoạn mục vươn lên dẫn đầu"},
            {"name": "impact", "start_sec": 2.5, "end_sec": 4.0, "description": "Thanh về nhất cán đích, bung cờ vinh danh hoặc huy hiệu ngôi sao"}
        ],
        idle_motion="Hạt tia lửa tốc độ phụt ra sau đuôi thanh dẫn đầu",
        default_bbox=[100, 420, 880, 720],
        params_schema={"items": "list", "highlight_index": "int", "unit": "str"}
    ),
    "thermometer": RecipeMetadata(
        name="thermometer",
        category="number_stat",
        meaning="Dùng khi diễn tả độ nóng của thị trường, căng thẳng leo thang, biến đổi khí hậu hoặc chỉ số tăng nhiệt",
        metaphor="Cột nhiệt kế thủy ngân dâng trào nhiệt lượng",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Ống thủy tinh bóng bẩy cùng bầu nhiệt kế xuất hiện"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.2, "description": "Cột dung dịch đỏ rực dâng trào mạnh mẽ qua các vạch chia độ"},
            {"name": "impact", "start_sec": 2.2, "end_sec": 4.0, "description": "Cột chạm đỉnh sôi, tỏa sóng nhiệt đỏ rực xung quanh kèm bong bóng nảy"}
        ],
        idle_motion="Bọt nhiệt sôi lăn tăn trong bầu dung dịch",
        default_bbox=[220, 360, 640, 820],
        params_schema={"temperature": "float", "max_temp": "float", "unit": "str", "label": "str"}
    ),
    "battery_fill": RecipeMetadata(
        name="battery_fill",
        category="number_stat",
        meaning="Dùng khi nói về tích lũy năng lượng, dung lượng pin, tiến độ hoàn thành hoặc khả năng chịu tải",
        metaphor="Thỏi pin năng lượng sạc điện thần tốc",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Thỏi pin 3D viền kính với cực dương nhô ra xuất hiện ở trạng thái cạn"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.3, "description": "Tia sét năng lượng đánh vào, từng khối năng lượng xanh neon nạp đầy 25%, 50%, 75%, 100%"},
            {"name": "impact", "start_sec": 2.3, "end_sec": 4.0, "description": "Pin đầy 100%, phát xung điện quang tỏa sáng toàn thân pin"}
        ],
        idle_motion="Tia sét nhỏ phóng điện tuần hoàn giữa hai cực",
        default_bbox=[180, 460, 720, 600],
        params_schema={"percentage": "float", "label": "str", "status": "str"}
    ),
    "glass_fill": RecipeMetadata(
        name="glass_fill",
        category="fill_level",
        meaning="Dùng khi diễn tả 'đổ đầy ly nước', dung lượng đã đầy, giới hạn chịu đựng hoặc mức độ đạt mục tiêu",
        metaphor="Ly nước thủy tinh đón dòng nước rót từ trên xuống",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Chiếc ly thủy tinh trong suốt xuất hiện với mặt bàn vững chãi"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.4, "description": "Dòng nước xanh biếc rót từ trên xuống, mực nước dâng cao sóng sánh có bọt khí"},
            {"name": "impact", "start_sec": 2.4, "end_sec": 4.0, "description": "Nước đầy đúng vạch mục tiêu, vật nổi (phao/icon) nhấp nhô trên mặt nước"}
        ],
        idle_motion="Mặt nước gợn sóng hình sin nhẹ nhàng, bọt khí nổi lững lờ",
        default_bbox=[200, 400, 680, 760],
        params_schema={"fill_percentage": "float", "floating_icon": "str", "label": "str"}
    )
}



# 12 Recipes for Step (b): Compare + Process + Risk
RECIPES_PHASE_B: Dict[str, RecipeMetadata] = {
    "balance_scale": RecipeMetadata(
        name="balance_scale",
        category="compare_vs",
        meaning="Dùng khi so sánh tương quan lực lượng, lợi ích vượt trội hoặc đánh đổi giữa hai giải pháp",
        metaphor="Cán cân công lý 3D nghiêng về bên nặng ký hơn",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Trục cân kim loại và hai đĩa cân xuất hiện ở trạng thái cân bằng"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.3, "description": "Vật nặng đặt lên đĩa cân, cán cân nghiêng dứt khoát về bên ưu thế"},
            {"name": "impact", "start_sec": 2.3, "end_sec": 4.0, "description": "Cán cân nhấp nhô tắt dần, nhãn bên thắng bừng sáng hào quang"}
        ],
        idle_motion="Đĩa cân dao động điều hòa nhẹ nhàng quanh vị trí cân bằng mới",
        default_bbox=[140, 440, 800, 680],
        params_schema={"left_label": "str", "right_label": "str", "winner": "str", "left_weight": "float", "right_weight": "float"}
    ),
    "tug_of_war": RecipeMetadata(
        name="tug_of_war",
        category="compare_vs",
        meaning="Dùng khi mô tả cuộc cạnh tranh thị phần gay gắt, giằng co thế trận giữa hai thế lực lớn",
        metaphor="Trận kéo co căng thẳng giằng co vạch cờ",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Hai đội và sợi dây thừng căng ngang xuất hiện với cờ đỏ ở giữa"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.4, "description": "Hai bên giằng co qua lại, một bên bất ngờ bứt phá giật mạnh dây"},
            {"name": "impact", "start_sec": 2.4, "end_sec": 4.0, "description": "Cờ đỏ vượt qua vạch chiến thắng, biểu tượng chiến thắng bừng sáng"}
        ],
        idle_motion="Sợi dây rung nhẹ nhịp thở, phe thắng nhấp nhô ăn mừng",
        default_bbox=[100, 500, 880, 560],
        params_schema={"team_a": "str", "team_b": "str", "winner": "str", "label": "str"}
    ),
    "vs_flip_cards": RecipeMetadata(
        name="vs_flip_cards",
        category="compare_vs",
        meaning="Dùng khi so sánh đối chiếu hai phương án, lật mở mặt trái/mặt phải hoặc ưu nhược điểm",
        metaphor="Hai thẻ bài 3D lật xoay đối đầu trực diện",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Hai thẻ bài 3D xuất hiện úp mặt đối xứng qua huy hiệu VS"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.3, "description": "Hai thẻ đồng loạt lật xoay 180° theo trục đứng hé lộ thông số cốt lõi"},
            {"name": "impact", "start_sec": 2.3, "end_sec": 4.0, "description": "Thẻ vượt trội bung viền neon sáng rực, thẻ đối thủ xám mờ lùi sau"}
        ],
        idle_motion="Hai thẻ bồng bềnh 3D ngược pha nhau nhẹ nhàng",
        default_bbox=[100, 460, 880, 640],
        params_schema={"card_a": "dict", "card_b": "dict", "winner": "str", "label": "str"}
    ),
    "before_after_wipe": RecipeMetadata(
        name="before_after_wipe",
        category="compare_vs",
        meaning="Dùng khi minh họa sự chuyển đổi ngoạn mục, lột xác trước và sau khi áp dụng giải pháp",
        metaphor="Thanh quét thần kỳ phân chia quá khứ và tương lai",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Khung cảnh 'Trước' xám tối, hỗn loạn xuất hiện bao trùm"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.4, "description": "Thanh trượt thẳng đứng quét ngang màn hình từ trái qua phải mang lại ánh sáng"},
            {"name": "impact", "start_sec": 2.4, "end_sec": 4.0, "description": "Khung cảnh 'Sau' hiện ra rực rỡ hiện đại, tia sáng quét ngang mặt kính"}
        ],
        idle_motion="Thanh trượt rung nhẹ tia laser, vùng mới tỏa ánh hào quang",
        default_bbox=[120, 440, 840, 680],
        params_schema={"before_label": "str", "after_label": "str", "metric_change": "str", "label": "str"}
    ),
    "conveyor_belt": RecipeMetadata(
        name="conveyor_belt",
        category="process_flow",
        meaning="Dùng khi trình bày dây chuyền tự động hóa, quy trình sản xuất hàng loạt hoặc xử lý liên tục",
        metaphor="Băng chuyền nhà máy thông minh luân chuyển sản phẩm",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Băng chuyền cơ khí với các trục con lăn xuất hiện"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.4, "description": "Các kiện hàng trôi tuần tự, qua cánh tay scanner kiểm định tự động"},
            {"name": "impact", "start_sec": 2.4, "end_sec": 4.0, "description": "Kiện hàng đạt chuẩn được đóng dấu PASS xanh ngọc và xuất xưởng"}
        ],
        idle_motion="Trục con lăn quay tuần hoàn đều đặn, vệt laser quét nhịp nhàng",
        default_bbox=[100, 480, 880, 600],
        params_schema={"steps": "list", "output_label": "str", "label": "str"}
    ),
    "domino_chain": RecipeMetadata(
        name="domino_chain",
        category="process_flow",
        meaning="Dùng khi giải thích phản ứng dây chuyền, một nguyên nhân dẫn đến hàng loạt hệ quả liên tiếp",
        metaphor="Chuỗi quân cờ domino đổ liên hoàn kỳ thú",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Hàng quân cờ domino 3D xếp thẳng hàng vững chãi"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.3, "description": "Quân đầu tiên bị kích hoạt ngã xuống, kéo theo chuỗi domino đổ rạp tuần tự"},
            {"name": "impact", "start_sec": 2.3, "end_sec": 4.0, "description": "Quân cờ cuối cùng va đập làm bật mở đích đến / kết quả khổng lồ"}
        ],
        idle_motion="Hạt năng lượng tỏa ra từ điểm va chạm cuối cùng",
        default_bbox=[120, 480, 840, 600],
        params_schema={"steps": "list", "final_impact": "str", "label": "str"}
    ),
    "funnel_filter": RecipeMetadata(
        name="funnel_filter",
        category="process_flow",
        meaning="Dùng khi mô tả quá trình chọn lọc, phễu chuyển đổi khách hàng hoặc sàng lọc dữ liệu tinh hoa",
        metaphor="Chiếc phễu lọc đa tầng chắt lọc tinh hoa",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Chiếc phễu thủy tinh 3 tầng trong suốt xuất hiện"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.4, "description": "Nhiều hạt dữ liệu thô rơi vào miệng phễu, lọc qua từng màng lọc thu hẹp dần"},
            {"name": "impact", "start_sec": 2.4, "end_sec": 4.0, "description": "Giọt tinh hoa rơi xuống đáy bừng sáng giá trị vàng cốt lõi"}
        ],
        idle_motion="Màng lọc phát xung năng lượng tuần hoàn, giọt tinh chất phát sáng",
        default_bbox=[160, 420, 760, 720],
        params_schema={"input_count": "int", "output_count": "int", "stages": "list", "label": "str"}
    ),
    "pipeline_pipes": RecipeMetadata(
        name="pipeline_pipes",
        category="process_flow",
        meaning="Dùng khi mô tả đường ống dữ liệu, luồng vận chuyển tài nguyên hoặc hạ tầng kết nối liên thông",
        metaphor="Hệ thống đường ống dẫn công nghiệp phát sáng năng lượng",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Mạng lưới đường ống 3D zic-zac cùng các van khóa xuất hiện"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.3, "description": "Các van tự động mở, luồng năng lượng xanh neon phóng vù vù qua các co nối"},
            {"name": "impact", "start_sec": 2.3, "end_sec": 4.0, "description": "Toàn bộ mạng lưới thông suốt, đồng hồ áp suất tại đích báo trạng thái tối ưu"}
        ],
        idle_motion="Dòng xung năng lượng chạy liên tục trong thân ống trong suốt",
        default_bbox=[120, 460, 840, 640],
        params_schema={"nodes": "list", "throughput": "str", "label": "str"}
    ),
    "dice_roll": RecipeMetadata(
        name="dice_roll",
        category="risk_prob",
        meaning="Dùng khi đề cập đến yếu tố may rủi, xác suất thống kê, canh bạc thị trường hoặc quyết định mạo hiểm",
        metaphor="Viên xúc xắc 3D lăn lông lốc trong không gian",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.5, "description": "Viên xúc xắc 3D xoay tít bay lơ lửng giữa không gian"},
            {"name": "action", "start_sec": 0.5, "end_sec": 2.2, "description": "Xúc xắc rơi xuống bàn nảy tưng bừng, các mặt điểm xoay chuyển kịch tính"},
            {"name": "impact", "start_sec": 2.2, "end_sec": 4.0, "description": "Dừng lại dứt khoát ở mặt điểm chiến thắng, phát xung hào quang vàng chói"}
        ],
        idle_motion="Viên xúc xắc bồng bềnh nhẹ trên đệm không khí, bóng đổ co giãn",
        default_bbox=[160, 460, 760, 640],
        params_schema={"result_number": "int", "probability": "str", "label": "str"}
    ),
    "lock_unlock": RecipeMetadata(
        name="lock_unlock",
        category="risk_prob",
        meaning="Dùng khi nói về bảo mật thông tin, giải mã rào cản, phá vỡ hạn chế hoặc mở khóa cơ hội mới",
        metaphor="Ổ khóa bảo mật công nghệ cao bật mở then chốt",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Ổ khóa kiên cố màu đỏ khóa chặt với biểu tượng bảo mật xuất hiện"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.1, "description": "Khóa mã số tự động xoay khớp mã hoặc chìa khóa số cắm vào xoay 90°"},
            {"name": "impact", "start_sec": 2.1, "end_sec": 4.0, "description": "Còng khóa bật nảy lên 'tách' (spring snap), toàn thân chuyển màu xanh neon mở lối"}
        ],
        idle_motion="Còng khóa đung đưa nhẹ, vòng hào quang bảo vệ lan tỏa",
        default_bbox=[180, 440, 720, 680],
        params_schema={"status": "str", "key_type": "str", "label": "str"}
    ),
    "shield_hit": RecipeMetadata(
        name="shield_hit",
        category="risk_prob",
        meaning="Dùng khi nhấn mạnh khả năng chống chịu rủi ro, bảo vệ tài sản, phòng thủ an ninh mạng vững vàng",
        metaphor="Tấm khiên năng lượng đẩy lùi mọi đòn tấn công hiểm hóc",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Tấm khiên năng lượng lục giác viền phát quang xuất hiện bảo vệ trung tâm"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.2, "description": "Các tia đạn/sét hiểm hóc bắn tới va chạm cực mạnh vào mặt khiên"},
            {"name": "impact", "start_sec": 2.2, "end_sec": 4.0, "description": "Mặt khiên phát sóng xung kích phản hồi đẩy lùi đòn đánh, khiên nguyên vẹn tỏa sáng"}
        ],
        idle_motion="Màng lưới lục giác trên thân khiên sáng nhấp nháy tuần hoàn",
        default_bbox=[160, 440, 760, 680],
        params_schema={"threat_name": "str", "defense_score": "str", "label": "str"}
    ),
    "traffic_light": RecipeMetadata(
        name="traffic_light",
        category="risk_prob",
        meaning="Dùng khi thể hiện tín hiệu đèn xanh/đỏ cho thị trường, cảnh báo dừng lại hay cho phép tăng tốc",
        metaphor="Cột đèn giao thông chuyển trạng thái dứt khoát",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Cột đèn tín hiệu công nghệ cao xuất hiện với đèn đỏ cảnh báo sáng rực"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.2, "description": "Đèn đỏ tắt, đèn vàng chớp chuyển tiếp rồi đèn xanh bừng sáng rực rỡ"},
            {"name": "impact", "start_sec": 2.2, "end_sec": 4.0, "description": "Đèn xanh phát chùm sáng thông suốt, biểu tượng bứt phá lao vút về phía trước"}
        ],
        idle_motion="Chùm tia sáng xanh quét dải sáng nhẹ nhàng về phía camera",
        default_bbox=[200, 420, 680, 720],
        params_schema={"active_signal": "str", "action_text": "str", "label": "str"}
    )
}


# 8 Recipes for Step (c): Concept & Relations + Mock UI Interfaces
RECIPES_PHASE_C: Dict[str, RecipeMetadata] = {
    "orbit_system": RecipeMetadata(
        name="orbit_system",
        category="concept_relation",
        meaning="Dùng khi mô tả hệ sinh thái xoay quanh một hạt nhân trung tâm, mạng lưới vệ tinh hoặc cấu trúc phân tán",
        metaphor="Hệ mặt trời thu nhỏ với các vệ tinh quay quanh quỹ đạo elip",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Hạt nhân trung tâm phát sáng và 3 vòng quỹ đạo elip nghiêng mở rộng"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.4, "description": "Các vệ tinh quay đều trên quỹ đạo, phát tia năng lượng kết nối về tâm"},
            {"name": "impact", "start_sec": 2.4, "end_sec": 4.0, "description": "Xung beacon quét tỏa tròn từ tâm, toàn hệ thống đồng bộ bừng sáng"}
        ],
        idle_motion="Các vệ tinh trôi mượt mà trên quỹ đạo elip, tia nối co giãn nhẹ",
        default_bbox=[120, 420, 840, 720],
        params_schema={"center_node": "str", "satellites": "list", "label": "str"}
    ),
    "layered_onion": RecipeMetadata(
        name="layered_onion",
        category="concept_relation",
        meaning="Dùng khi bóc tách các tầng bản chất, giải mã cấu trúc đa tầng hoặc đi sâu vào nguyên nhân gốc rễ",
        metaphor="Bóc tách từng lớp củ hành hé lộ hạt nhân cốt lõi",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Khối cầu đa tầng đồng tâm xuất hiện với lớp vỏ bảo vệ ngoài cùng"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.3, "description": "Lớp vỏ ngoài mở tách ra, lớp giữa xoay lệch hé lộ hạt nhân vàng rực"},
            {"name": "impact", "start_sec": 2.3, "end_sec": 4.0, "description": "Hạt nhân trung tâm trồi lên phát sáng rực rỡ, hiển thị từ khóa cốt lõi"}
        ],
        idle_motion="Các vòng tròn đồng tâm xoay ngược chiều nhau nhẹ nhàng",
        default_bbox=[160, 440, 760, 680],
        params_schema={"layers": "list", "core_text": "str", "label": "str"}
    ),
    "stack_pile": RecipeMetadata(
        name="stack_pile",
        category="concept_relation",
        meaning="Dùng khi giải thích sự tích lũy tài nguyên, xếp chồng công nghệ (tech stack) hoặc tháp năng lực",
        metaphor="Các tấm thẻ 3D xếp chồng lên nhau thành tháp vững chắc",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Tấm đế nền vững chãi xuất hiện tại trung tâm"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.3, "description": "Từng tấm thẻ tầng tiếp theo rơi từ trên xuống xếp chồng nảy nhẹ"},
            {"name": "impact", "start_sec": 2.3, "end_sec": 4.0, "description": "Tấm đỉnh trên cùng bung viền neon sáng rực, tháp vững chãi hoàn thiện"}
        ],
        idle_motion="Tháp thẻ bồng bềnh 3D nhấp nhô nhẹ theo nhịp thở",
        default_bbox=[140, 440, 800, 680],
        params_schema={"layers": "list", "top_highlight": "str", "label": "str"}
    ),
    "puzzle_snap": RecipeMetadata(
        name="puzzle_snap",
        category="concept_relation",
        meaning="Dùng khi các yếu tố tìm thấy mảnh ghép còn thiếu, hợp tác hoàn hảo hoặc hoàn thành bức tranh tổng thể",
        metaphor="Mảnh ghép jigsaw trượt vào khớp nối 'khấc' hoàn hảo",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Bức tranh ghép có một vị trí khuyết trung tâm xuất hiện"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.1, "description": "Mảnh ghép chìa khóa vàng từ ngoài biên trượt vào xoay đúng góc"},
            {"name": "impact", "start_sec": 2.1, "end_sec": 4.0, "description": "Khớp nối đóng sập 'khấc' hoàn mỹ, toàn bộ bức tranh bừng sáng neon"}
        ],
        idle_motion="Đường viền các khớp nối phát quang xung ánh sáng chạy vòng",
        default_bbox=[140, 440, 800, 660],
        params_schema={"key_piece": "str", "solution_text": "str", "label": "str"}
    ),
    "chat_thread": RecipeMetadata(
        name="chat_thread",
        category="mock_ui",
        meaning="Dùng khi mô tả tương tác người dùng, phản hồi chatbot AI, tin nhắn thông báo hoặc tranh luận",
        metaphor="Giao diện tin nhắn thông minh hội thoại real-time",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Khung ứng dụng chat bo tròn xuất hiện với bong bóng câu hỏi"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.3, "description": "Ba chấm nhảy biểu thị 'đang trả lời' rồi bong bóng kết quả bung ra"},
            {"name": "impact", "start_sec": 2.3, "end_sec": 4.0, "description": "Dấu tick đôi xanh dương hiện ra, tin nhắn câu trả lời bừng sáng"}
        ],
        idle_motion="Con trỏ gõ phím nhấp nháy tuần hoàn ở thanh nhập liệu",
        default_bbox=[120, 440, 840, 680],
        params_schema={"user_msg": "str", "bot_reply": "str", "label": "str"}
    ),
    "mock_card_swipe": RecipeMetadata(
        name="mock_card_swipe",
        category="mock_ui",
        meaning="Dùng khi đưa ra quyết định chọn lựa nhanh, phê duyệt cơ hội hoặc loại bỏ giải pháp không phù hợp",
        metaphor="Thao tác quẹt thẻ sang phải chấp thuận",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Thẻ hồ sơ / giải pháp 3D nằm ở trung tâm màn hình"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.2, "description": "Thẻ nghiêng góc và bị quẹt lướt sang phải với gia tốc mượt mà"},
            {"name": "impact", "start_sec": 2.2, "end_sec": 4.0, "description": "Con dấu 'APPROVED' màu xanh ngọc đóng sập xuống, thẻ sau trồi lên"}
        ],
        idle_motion="Thẻ mới đung đưa góc 3D đón chờ hành động tiếp theo",
        default_bbox=[140, 460, 800, 640],
        params_schema={"decision": "str", "card_title": "str", "label": "str"}
    ),
    "form_fill_submit": RecipeMetadata(
        name="form_fill_submit",
        category="mock_ui",
        meaning="Dùng khi minh họa quy trình đăng ký, xử lý hồ sơ tự động hoặc nhập liệu tốc độ cao",
        metaphor="Biểu mẫu trực tuyến tự động điền và bấm nút gửi",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Cửa sổ form biểu mẫu với các trường nhập liệu xuất hiện"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.2, "description": "Dòng chữ tự động điền vào các ô kèm con trỏ gõ nhanh, thanh tiến độ đạt 100%"},
            {"name": "impact", "start_sec": 2.2, "end_sec": 4.0, "description": "Nút 'SUBMIT' bị bấm nảy xuống, huy hiệu SUCCESS xanh ngọc bật mở"}
        ],
        idle_motion="Huy hiệu thành công co giãn nhịp thở nhẹ nhàng",
        default_bbox=[120, 440, 840, 680],
        params_schema={"fields": "list", "status": "str", "label": "str"}
    ),
    "terminal_command_run": RecipeMetadata(
        name="terminal_command_run",
        category="mock_ui",
        meaning="Dùng khi thực thi câu lệnh kỹ thuật, triển khai hệ thống (deploy) hoặc chạy thuật toán",
        metaphor="Cửa sổ dòng lệnh Terminal công nghệ cao thực thi thần tốc",
        max_words=3,
        stages=[
            {"name": "enter", "start_sec": 0.0, "end_sec": 0.6, "description": "Cửa sổ Terminal đen bóng với 3 nút điều khiển xuất hiện"},
            {"name": "action", "start_sec": 0.6, "end_sec": 2.2, "description": "Dòng lệnh được gõ nhanh sau dấu nhắc $, thanh loading chạy đầy 100%"},
            {"name": "impact", "start_sec": 2.2, "end_sec": 4.0, "description": "Dòng thông báo '✓ SUCCESS: DEPLOYED' bừng sáng xanh neon rực rỡ"}
        ],
        idle_motion="Con trỏ hình khối nhấp nháy tuần hoàn sau dòng output",
        default_bbox=[120, 460, 840, 640],
        params_schema={"command": "str", "output": "str", "label": "str"}
    )
}

ALL_RECIPES = {**RECIPES_PHASE_A, **RECIPES_PHASE_B, **RECIPES_PHASE_C}


def dump_all_descriptors(target_dir: Path) -> None:
    """Save all recipe descriptor JSON files."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for name, meta in ALL_RECIPES.items():
        meta.save_json(target_dir / f"{name}.json")

