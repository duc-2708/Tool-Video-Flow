"""Công cụ kiểm thử UI review trực quan bằng Playwright Chromium ở 1440x900.

Kiểm tra DOM thực tế:
(a) Mở app mặc định thấy tiêu đề "Hôm nay làm video gì?" và khối "SỐ LƯỢNG VIDEO"
(b) Selectbox thời lượng nằm BÊN TRONG phần tử class st-key-opt_dur
(c) Font tính toán của body có chứa "Inter"
(d) Không còn phần tử stAlert nền xanh dương mặc định
(e) Mỗi trang trong PAGES có đúng 1 thẻ h1
Chụp ảnh 14 trang vào output/ui_review/<tên trang>.png
"""
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PAGE_KEYS = [
    "Tạo video",
    "Tạo video theo danh mục",
    "Khám phá chủ đề",
    "Trend Scout",
    "Research",
    "Edit Plan",
    "Assets",
    "AI Video",
    "Render",
    "Kho video đã làm",
    "Phong cách mẫu",
    "Xem trước mẫu",
    "Phòng thử hiệu ứng",
    "Cài đặt Token & AI",
]

PAGE_SLUGS = {
    "Tạo video": "tao_video",
    "Tạo video theo danh mục": "tu_dong_danh_muc",
    "Khám phá chủ đề": "kham_pha_chu_de",
    "Trend Scout": "trend_scout",
    "Research": "research",
    "Edit Plan": "edit_plan",
    "Assets": "assets",
    "AI Video": "ai_video",
    "Render": "render",
    "Kho video đã làm": "kho_video",
    "Phong cách mẫu": "phong_cach_mau",
    "Xem trước mẫu": "xem_truoc_mau",
    "Phòng thử hiệu ứng": "phong_thu_hieu_ung",
    "Cài đặt Token & AI": "cai_dat_token_ai",
}


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 30.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.5)
    return False


def run_review():
    root = Path(__file__).resolve().parents[1]
    repo_root = root.parent
    output_dir = repo_root / "output/ui_review"
    output_dir.mkdir(parents=True, exist_ok=True)

    port = 8599
    cmd = [
        str(root / ".venv/Scripts/python.exe"),
        "-m",
        "streamlit",
        "run",
        str(root / "app/streamlit_app.py"),
        f"--server.port={port}",
        "--server.headless=true",
        "--server.enableStaticServing=true",
    ]

    env = os.environ.copy()
    # Fake keys để không chạm mạng
    env["GEMINI_API_KEY"] = "fake-gemini-key-for-ui-review"
    env["OPENAI_API_KEY"] = "fake-openai-key-for-ui-review"
    env["PIXABAY_API_KEY"] = "fake-pixabay-key-for-ui-review"

    print(f"Khởi động Streamlit trên cổng {port}...", flush=True)
    server = subprocess.Popen(cmd, cwd=str(root), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        if not wait_for_port(port, timeout=35.0):
            print(f"LỖI: Không kết nối được tới Streamlit port {port}", flush=True)
            return False

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            url = f"http://127.0.0.1:{port}"
            page.goto(url, wait_until="networkidle", timeout=35000)
            
            # Đợi cho tới khi sidebar radio và thẻ h1 đầu tiên xuất hiện
            page.wait_for_selector('[data-testid="stSidebar"] [role="radiogroup"] label', timeout=35000)
            page.wait_for_selector('h1', timeout=35000)
            time.sleep(2.5)

            results = {}

            # (a) Mở app mặc định thấy tiêu đề "Hôm nay làm video gì?" và khối "SỐ LƯỢNG VIDEO"
            body_text = page.inner_text("body")
            has_title_default = "Hôm nay làm video" in body_text and "gì?" in body_text
            has_qty_card = page.locator(".st-key-qty_card").count() > 0 or "SỐ LƯỢNG VIDEO" in body_text
            results["(a) Mặc định mở Hub Tạo video & khối Số lượng video"] = has_title_default and has_qty_card

            # (b) selectbox thời lượng nằm BÊN TRONG phần tử class st-key-opt_dur
            opt_dur_select = page.locator(".st-key-opt_dur [data-testid='stSelectbox'], .st-key-opt_dur [data-baseweb='select']")
            results["(b) Selectbox thời lượng nằm BÊN TRONG .st-key-opt_dur"] = opt_dur_select.count() > 0

            # (c) Font tính toán của body có chứa "Inter"
            computed_font = page.evaluate("() => window.getComputedStyle(document.body).fontFamily")
            results["(c) Font tính toán của body chứa 'Inter'"] = "Inter" in computed_font

            # (d) Không còn phần tử stAlert nền xanh dương mặc định
            alert_count = page.locator('[data-testid="stAlert"]').count()
            blue_alerts = 0
            for i in range(alert_count):
                alert_bg = page.locator('[data-testid="stAlert"]').nth(i).evaluate("el => window.getComputedStyle(el).backgroundColor")
                # Nền xanh dương mặc định của Streamlit thường là rgb(28, 131, 225) hoặc rgb(240, 242, 246)
                if "28, 131, 225" in alert_bg or "240, 242, 246" in alert_bg or "230, 240, 250" in alert_bg:
                    blue_alerts += 1
            results["(d) Không còn stAlert nền xanh dương mặc định"] = (blue_alerts == 0)

            # (e) Mỗi trang có đúng 1 h1 & Chụp ảnh từng trang
            h1_results = {}
            for idx, page_key in enumerate(PAGE_KEYS):
                slug = PAGE_SLUGS[page_key]
                # Chọn radio item theo index
                radio_labels = page.locator('[data-testid="stSidebar"] [role="radiogroup"] label')
                if idx < radio_labels.count():
                    radio_labels.nth(idx).click()

                time.sleep(2.0)
                try:
                    page.wait_for_selector('h1', timeout=10000)
                except Exception:
                    pass

                h1_count = page.locator("h1").count()
                h1_results[page_key] = (h1_count == 1)

                # Chụp ảnh 1440x900
                img_path = output_dir / f"{slug}.png"
                page.screenshot(path=str(img_path), full_page=False)
                print(f"  [Chụp ảnh] {page_key} -> {img_path.name} (H1 count: {h1_count})", flush=True)

            results["(e) Mỗi trang có đúng 1 h1"] = all(h1_results.values())

            browser.close()

            print("\n" + "=" * 65, flush=True)
            print("KẾT QUẢ KIỂM THỬ THẬT PLAYWRIGHT (DOM & GIAO DIỆN)", flush=True)
            print("=" * 65, flush=True)
            all_passed = True
            for k, passed in results.items():
                status_str = "ĐẠT" if passed else "CHƯA ĐẠT"
                print(f"{k}: {status_str}", flush=True)
                if not passed:
                    all_passed = False

            print("\nChi tiết thẻ H1 từng trang:", flush=True)
            for p_k, p_pass in h1_results.items():
                print(f"  • {p_k}: {'1 thẻ H1 (Đạt)' if p_pass else 'Sai số lượng H1'}", flush=True)

            return all_passed

    finally:
        print("\nDừng máy chủ Streamlit...", flush=True)
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    success = run_review()
    sys.exit(0 if success else 1)
