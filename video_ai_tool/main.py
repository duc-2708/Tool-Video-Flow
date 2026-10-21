# file: main.py
"""Kiểm tra khung offline; Researcher chạy qua python -m agents.researcher."""
import argparse
from pydantic import ValidationError
from config.settings import get_settings
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from utils.console import configure_console


def main() -> int:
    configure_console()
    parser = argparse.ArgumentParser(description="video_ai_tool — kiểm tra khung dự án offline")
    parser.add_argument("--check", action="store_true", help="Kiểm tra cấu hình và schema offline, không gọi API")
    args = parser.parse_args()
    if not args.check:
        parser.print_help()
        print("Researcher: python -m agents.researcher <chủ đề>. Dùng --check để kiểm tra khung offline.")
        return 0
    try:
        settings = get_settings()
        settings.ensure_directories()
        ResearchBrief.model_json_schema()
        EditPlan.model_json_schema()
    except (ValidationError, OSError, ValueError) as error:
        # Không in ValidationError vì input lỗi có thể chứa secret.
        print(f"Kiểm tra thất bại ({type(error).__name__}). Kiểm tra kiểu và khoảng giá trị trong .env cùng quyền ghi thư mục.")
        return 1
    print("OK: cấu hình hợp lệ; schema ResearchBrief và EditPlan sẵn sàng.")
    print(f"Output: {settings.output_dir}")
    print("Kiểm tra offline hoàn tất. Chưa gọi API, chưa tạo video.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
