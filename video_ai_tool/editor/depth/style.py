"""Depth Style & Shader definitions for 3D Isometric / Perspective engine."""
import math
from typing import Dict, Any, Tuple

# Safe area bounds (Post-transform)
SAFE_X_MIN = 70
SAFE_X_MAX = 1010
SAFE_Y_MIN = 240
SAFE_Y_MAX = 1330
CAPTION_Y_MIN = 1380
CAPTION_Y_MAX = 1700
CONTENT_CENTER_Y = 785

# Theme-based color ramps for 3-face rule
THEME_PALETTES = {
    "neon_dark": {
        "bg_dark": "#09041a",
        "bg_deep": "#030108",
        "grid_color": "rgba(157, 78, 221, 0.18)",
        "grid_near": "rgba(0, 245, 212, 0.24)",
        "accent_primary": "#9d4edd",
        "accent_cyan": "#00f5d4",
        "accent_magenta": "#f72585",
        "accent_gold": "#ffd166",
        "top_highlight": "rgba(255, 255, 255, 0.25)",
        "shadow_dark": "rgba(0, 0, 0, 0.40)",
        "contact_shadow": "rgba(3, 1, 8, 0.75)"
    },
    "paper_brand": {
        "bg_dark": "#1a1e24",
        "bg_deep": "#0f1216",
        "grid_color": "rgba(200, 210, 225, 0.12)",
        "grid_near": "rgba(59, 130, 246, 0.20)",
        "accent_primary": "#3b82f6",
        "accent_cyan": "#06b6d4",
        "accent_magenta": "#ec4899",
        "accent_gold": "#f59e0b",
        "top_highlight": "rgba(255, 255, 255, 0.20)",
        "shadow_dark": "rgba(0, 0, 0, 0.45)",
        "contact_shadow": "rgba(0, 0, 0, 0.80)"
    },
    "whiteboard_sketch": {
        "bg_dark": "#14171c",
        "bg_deep": "#0a0c0e",
        "grid_color": "rgba(148, 163, 184, 0.15)",
        "grid_near": "rgba(16, 185, 129, 0.20)",
        "accent_primary": "#10b981",
        "accent_cyan": "#14b8a6",
        "accent_magenta": "#f43f5e",
        "accent_gold": "#eab308",
        "top_highlight": "rgba(255, 255, 255, 0.22)",
        "shadow_dark": "rgba(0, 0, 0, 0.50)",
        "contact_shadow": "rgba(0, 0, 0, 0.85)"
    }
}


def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Convert hex string to (r, g, b) tuple."""
    hex_code = hex_code.lstrip("#")
    if len(hex_code) == 3:
        hex_code = "".join(2 * c for c in hex_code)
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))


def adjust_color_lightness(hex_code: str, factor: float) -> str:
    """Adjust color brightness: factor > 0 for highlight (top face), factor < 0 for shadow (right face)."""
    r, g, b = hex_to_rgb(hex_code)
    if factor > 0:
        # Interpolate towards white
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
    else:
        # Interpolate towards black
        factor = abs(factor)
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
    return f"#{min(255, max(0, r)):02x}{min(255, max(0, g)):02x}{min(255, max(0, b)):02x}"


def compute_3face_shading(base_color: str) -> Dict[str, str]:
    """Generate 3-face colors under top-left light: top (+15%), left (0% to -10%), right (-28%)."""
    return {
        "top": adjust_color_lightness(base_color, 0.18),
        "left": adjust_color_lightness(base_color, -0.06),
        "right": adjust_color_lightness(base_color, -0.28),
        "specular_edge": adjust_color_lightness(base_color, 0.40)
    }


def validate_3d_bbox(bbox: Dict[str, float]) -> Dict[str, Any]:
    """Audit bounding box after 3D transform against safe zones."""
    x_min = bbox.get("x", 0)
    y_min = bbox.get("y", 0)
    w = bbox.get("width", 0)
    h = bbox.get("height", 0)
    x_max = x_min + w
    y_max = y_min + h

    errors = []
    if x_min < SAFE_X_MIN:
        errors.append(f"Vật thể tràn lề trái ({x_min:.1f} < {SAFE_X_MIN})")
    if x_max > SAFE_X_MAX:
        errors.append(f"Vật thể tràn lề phải ({x_max:.1f} > {SAFE_X_MAX})")
    if y_min < SAFE_Y_MIN:
        errors.append(f"Vật thể tràn đỉnh nội dung ({y_min:.1f} < {SAFE_Y_MIN})")
    if y_max > SAFE_Y_MAX:
        errors.append(f"Vật thể chạm/lấn vùng phụ đề ({y_max:.1f} > {SAFE_Y_MAX}, phụ đề tại {CAPTION_Y_MIN})")

    center_y = y_min + h / 2
    drift_y = abs(center_y - CONTENT_CENTER_Y)
    
    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "bbox": [x_min, y_min, x_max, y_max],
        "center_y": center_y,
        "center_y_drift": drift_y
    }


# Supported 3D recipes in Phase 6 Step (b)
DEPTH_SUPPORTED_RECIPES = [
    "bar_compare",
    "gauge_ring",
    "versus_split",
    "hub_spoke",
    "checklist",
    "stat_number",
    "flow_chain",
    "terminal_typing",
    "road_tracker",
]

# 3D Camera boundaries to guarantee safe area compliance
DEPTH_CAMERA_LIMITS = {
    "max_scale": 1.10,
    "max_dolly_z": 45.0,
    "max_pan_x": 35.0,
    "max_pan_y": 25.0,
    "max_rot_x": 6.0,
    "max_rot_y": 6.0,
    "max_orbit": 6.0,
    "max_impact_bump": 6.0,
}


def validate_depth_camera(camera_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that 3D camera motion parameters do not exceed safe boundary constraints."""
    errors = []
    amount = float(camera_spec.get("amount", 0.05))
    if amount > 0.12:
        errors.append(f"Camera amount too large: {amount} > 0.12")

    move = camera_spec.get("move", "dolly_in")
    allowed_moves = {"dolly_in", "push_in", "zoom_in", "dolly_out", "pull_out", "zoom_out", "pan_left", "pan_right", "orbit"}
    if move not in allowed_moves:
        errors.append(f"Unknown camera move: {move}")

    bump = camera_spec.get("impact_bump")
    if bump is not None and not (0.0 <= float(bump) <= 60.0):
        errors.append(f"Invalid impact bump timestamp: {bump}")

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "move": move,
        "amount": amount
    }

