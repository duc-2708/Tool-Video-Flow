"""Central element registry for motion graphics elements and annotations."""
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ElementDefinition:
    type_name: str
    description: str
    supported_themes: list[str] = field(default_factory=lambda: ["neon_dark", "paper_brand", "whiteboard_sketch"])
    fallback_type: str = "text_focus"
    render_module: str = ""
    params_schema: dict[str, Any] = field(default_factory=dict)


class ElementRegistry:
    def __init__(self):
        self._registry: dict[str, ElementDefinition] = {}
        self._annotations: set[str] = {
            "strike",
            "check",
            "cross",
            "underline",
            "circle_highlight",
            "stamp",
            "question",
            "arrow",
            "tag",
            "pencil",
        }

    def register(self, element: ElementDefinition) -> None:
        self._registry[element.type_name] = element

    def get(self, type_name: str) -> ElementDefinition | None:
        return self._registry.get(type_name)

    def is_registered(self, type_name: str) -> bool:
        return type_name in self._registry

    def is_annotation_supported(self, annot_type: str) -> bool:
        return annot_type in self._annotations

    def find_fallback(self, type_name: str) -> str:
        elem = self._registry.get(type_name)
        if elem and elem.fallback_type and elem.fallback_type in self._registry:
            return elem.fallback_type
        # Semantic fallbacks
        fallbacks = {
            "title_chip": "section_title",
            "line_chart_draw": "bar_compare",
            "versus_split": "bar_compare",
            "mock_ui_window": "container_fill",
            "checklist": "steps_ladder",
            "terminal_typing": "stat_number",
            "hub_spoke": "flow_chain",
            "magnifier_check": "stat_number",
            "progress_tracker": "steps_ladder",
            "chat_bubble_poll": "steps_ladder",
            "quote_card": "stat_number",
            "source_badge": "stat_number",
            "icon_tile": "stat_number",
            "funnel": "container_fill",
            "letter_tiles": "steps_ladder",
            "prompt_card": "terminal_typing",
            "search_bar_typing": "terminal_typing",
            "code_card": "terminal_typing",
        }
        return fallbacks.get(type_name, "text_focus")

    def catalog_prompt_string(self) -> str:
        """Generate formatted element catalog string for Prompt B."""
        elements_str = ", ".join(f"{k} ({v.description})" for k, v in self._registry.items())
        annots_str = ", ".join(sorted(self._annotations))
        return f"DANH MỤC PHẦN TỬ (chỉ dùng các type đã hỗ trợ): {elements_str}. CHÚ THÍCH (annotations): {annots_str}."

    def list_registered_types(self) -> list[str]:
        return list(self._registry.keys())

    def list_supported_annotations(self) -> list[str]:
        return sorted(self._annotations)


# Singleton registry instance
REGISTRY = ElementRegistry()

# 1. 6 Priority elements (Core Phase 1)
REGISTRY.register(
    ElementDefinition(
        type_name="container_fill",
        description="chai/bình/cốc đổ đầy chất lỏng theo %, thể hiện giới hạn/dung lượng",
        fallback_type="gauge_ring",
        render_module="editor.motion.scenes.container_fill",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="bar_compare",
        description="biểu đồ cột so sánh tối thiểu 2 đối tượng có số liệu/nhãn",
        fallback_type="stat_number",
        render_module="editor.motion.scenes.bar_grow",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="stat_number",
        description="con số thống kê lớn kèm nhãn: count_up (đếm lên) hoặc strike_replace (gạch số cũ hiện số mới)",
        fallback_type="text_focus",
        render_module="editor.motion.scenes.stat_number",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="flow_chain",
        description="chuỗi quy trình 3-4 bước nối nhau bằng mũi tên hoặc đường dẫn",
        fallback_type="steps_ladder",
        render_module="editor.motion.scenes.flow_chain",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="steps_ladder",
        description="thang bậc các tầng/cấp độ theo chiều dọc hoặc bậc thang",
        fallback_type="flow_chain",
        render_module="editor.motion.scenes.stack_cards",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="gauge_ring",
        description="đồng hồ đo hoặc vòng tròn tiến độ % bán nguyệt/toàn phần",
        fallback_type="bar_compare",
        render_module="editor.motion.scenes.gauge",
    )
)

# 2. Remaining registered elements (Phase 2)
REGISTRY.register(
    ElementDefinition(
        type_name="versus_split",
        description="so sánh hai bên đối lập chia đôi màn hình trái vs phải",
        fallback_type="bar_compare",
        render_module="editor.motion.scenes.versus_scale",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="mock_ui_window",
        description="cửa sổ ứng dụng giả lập chung chung có thanh tab/nút điều khiển",
        fallback_type="container_fill",
        render_module="editor.motion.scenes.terminal_type",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="checklist",
        description="danh sách tiêu chí kèm dấu tích xanh hoặc gạch chéo đỏ",
        fallback_type="steps_ladder",
        render_module="editor.motion.scenes.checklist",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="terminal_typing",
        description="cửa sổ dòng lệnh CLI gõ từng ký tự mã hoặc lệnh",
        fallback_type="stat_number",
        render_module="editor.motion.scenes.terminal_type",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="line_chart_draw",
        description="biểu đồ đường vẽ dần qua các mốc thời gian",
        fallback_type="bar_compare",
        render_module="editor.motion.scenes.line_draw",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="hub_spoke",
        description="mô hình trung tâm kết nối tỏa tròn ra các vệ tinh/nút mạng",
        fallback_type="flow_chain",
        render_module="editor.motion.scenes.network_nodes",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="magnifier_check",
        description="kính lúp soi cận cảnh kiểm tra tính xác thực hoặc lỗ hổng",
        fallback_type="stat_number",
        render_module="editor.motion.scenes.magnifier_check",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="progress_tracker",
        description="thanh tiến trình ngang đánh dấu các chặng của video",
        fallback_type="steps_ladder",
        render_module="editor.motion.scenes.timeline_march",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="chat_bubble_poll",
        description="khung câu hỏi bình chọn tương tác hoặc bong bóng chat đối thoại",
        fallback_type="steps_ladder",
        render_module="editor.motion.scenes.stack_cards",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="source_badge",
        description="huy hiệu chứng thực nguồn uy tín trích dẫn từ tài liệu",
        fallback_type="stat_number",
        render_module="editor.motion.scenes.stat_number",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="icon_tile",
        description="ô thẻ biểu tượng minh họa khái niệm trực quan",
        fallback_type="stat_number",
        render_module="editor.motion.scenes.stack_cards",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="funnel",
        description="hình phễu lọc thu hẹp tỷ lệ chuyển đổi qua các giai đoạn",
        fallback_type="container_fill",
        render_module="editor.motion.scenes.funnel_filter",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="timeline",
        description="trục thời gian chạy dọc hoặc ngang qua các mốc lịch sử",
        fallback_type="steps_ladder",
        render_module="editor.motion.scenes.timeline_march",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="prompt_card",
        description="thẻ câu lệnh prompt AI giả lập với nhãn tham số",
        fallback_type="terminal_typing",
        render_module="editor.motion.scenes.terminal_type",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="search_bar_typing",
        description="thanh tìm kiếm gõ từ khóa và gợi ý kết quả",
        fallback_type="terminal_typing",
        render_module="editor.motion.scenes.terminal_type",
    )
)

REGISTRY.register(
    ElementDefinition(
        type_name="code_card",
        description="thẻ khối mã lập trình với cú pháp nổi bật",
        fallback_type="terminal_typing",
        render_module="editor.motion.scenes.terminal_type",
    )
)


# ============================================================================
# Dynamic Illustrations Loader & Topic Matcher
# ============================================================================

_ILLUSTRATIONS_CACHE: dict[str, Any] | None = None


def load_illustrations_config() -> dict[str, Any]:
    """Load configuration for the 15 original dynamic illustrations."""
    global _ILLUSTRATIONS_CACHE
    if _ILLUSTRATIONS_CACHE is not None:
        return _ILLUSTRATIONS_CACHE

    from pathlib import Path
    import yaml

    config_path = Path(__file__).resolve().parents[2] / "config" / "illustrations.yaml"
    if not config_path.is_file():
        # Fallback to local config relative to current working dir
        config_path = Path("config/illustrations.yaml")

    if config_path.is_file():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                _ILLUSTRATIONS_CACHE = yaml.safe_load(f) or {}
                return _ILLUSTRATIONS_CACHE
        except Exception:
            _ILLUSTRATIONS_CACHE = {}
    else:
        _ILLUSTRATIONS_CACHE = {}
    return _ILLUSTRATIONS_CACHE


def list_available_illustrations() -> list[str]:
    """Return the list of 15 available dynamic vector illustration IDs."""
    cfg = load_illustrations_config()
    illustrations = cfg.get("illustrations", {})
    return list(illustrations.keys())


def get_illustration_info(name: str) -> dict[str, Any] | None:
    """Get metadata for a specific illustration."""
    cfg = load_illustrations_config()
    return cfg.get("illustrations", {}).get(name)


def match_illustration_for_topic(text: str) -> str | None:
    """
    Match topic, prompt, or narration keywords to the best dynamic illustration ID.
    Returns matched illustration key or default ('drone').
    """
    if not text:
        return None

    import unicodedata

    def _normalize(s: str) -> str:
        norm = unicodedata.normalize("NFD", str(s).casefold()).replace("đ", "d")
        return "".join(c for c in norm if c.isalnum() or c.isspace())

    norm_text = _normalize(text)
    cfg = load_illustrations_config()
    illustrations = cfg.get("illustrations", {})

    best_match = None
    best_score = 0

    for ill_id, meta in illustrations.items():
        keywords = meta.get("keywords", [])
        score = 0
        for kw in keywords:
            norm_kw = _normalize(kw)
            if norm_kw and norm_kw in norm_text:
                score += len(norm_kw.split()) * 2 + 1
        if score > best_score:
            best_score = score
            best_match = ill_id

    if best_match:
        return best_match
    return cfg.get("default", "drone")

