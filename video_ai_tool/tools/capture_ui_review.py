"""Script to start a temporary Streamlit instance and capture 1440x900 screenshots with Playwright."""
import os
import sys
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import urllib.request

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT_DIR.parent / "output" / "ui_review"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8599
URL = f"http://localhost:{PORT}"


def wait_for_server(url: str, timeout: float = 30.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    python_exe = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)

    print(f"Starting Streamlit on port {PORT}...")
    server_log = open(ROOT_DIR / "logs" / "streamlit_server.log", "w", encoding="utf-8")
    server_process = subprocess.Popen(
        [
            str(python_exe),
            "-m",
            "streamlit",
            "run",
            str(ROOT_DIR / "app" / "streamlit_app.py"),
            f"--server.port={PORT}",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--server.enableCORS=false",
            "--server.enableXsrfProtection=false",
        ],
        cwd=str(ROOT_DIR),
        env=env,
        stdout=server_log,
        stderr=server_log,
    )

    try:
        ready = wait_for_server(URL, timeout=30.0)
        if not ready:
            print("Failed to connect to Streamlit server!")
            return

        print("Streamlit server ready. Launching Playwright browser at 1440x900...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(URL)

            print("Waiting for Streamlit app to mount...")
            page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=40000)
            page.wait_for_selector('[data-testid="stSidebar"] [data-testid="stRadio"]', timeout=40000)
            time.sleep(3.0)

            print("Page title:", page.title())

            # Target pages to capture
            pages_to_capture = [
                ("Tạo video theo danh mục", "tao_video.png"),
                ("Kho video đã làm", "kho_video.png"),
                ("Cài đặt Token & AI", "cai_dat.png"),
                ("Edit Plan", "edit_plan.png"),
                ("Render", "render.png"),
            ]

            for label, filename in pages_to_capture:
                print(f"Selecting {label} -> {filename}...")
                try:
                    radio = page.locator('[data-testid="stSidebar"] [data-testid="stRadio"]')
                    loc = radio.locator("label").filter(has_text=label).first
                    if loc.count() > 0:
                        loc.click()
                        time.sleep(3.0)
                    else:
                        print(f"Not found: {label}")
                    out_path = OUT_DIR / filename
                    page.screenshot(path=str(out_path), full_page=False)
                    print(f"Saved: {out_path.name}")
                except Exception as ex:
                    print(f"Error {label}: {ex}")

            browser.close()
            print("All screenshots captured successfully.")
    finally:
        print("Terminating Streamlit server process...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except Exception:
            server_process.kill()


if __name__ == "__main__":
    main()
