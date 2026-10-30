import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.visual_diversity import values_in
import re

projects = [
    ("iphone-18e", "auto-cong-nghe-724a258d"),
    ("artemis", "auto-cong-nghe-3deb20b3"),
    ("co-hoi-ty-usd", "auto-cong-nghe-e0a81f1e"),
    ("viet-nam-dat-giai-thuong", "auto-cong-nghe-efa8eac5"),
    ("luat-cam-chatbot", "auto-cong-nghe-64e6b569"),
    ("macbook-pro-oled", "auto-cong-nghe-d56d3ebe")
]

results = []

for tag, p_name in projects:
    p_dir = ROOT / "output" / p_name
    if not p_dir.is_dir():
        results.append({"tag": tag, "project": p_name, "found": False})
        continue

    plan_path = p_dir / "edit_plan.json"
    if not plan_path.is_file():
        results.append({"tag": tag, "project": p_name, "found": False})
        continue

    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    brief_path = p_dir / "brief.json"
    brief_text = ""
    if brief_path.is_file():
        try:
            bd = json.loads(brief_path.read_text(encoding="utf-8"))
            facts = bd.get("facts", [])
            brief_text = " ".join((f.get("fact_vi") or f.get("claim", "")) + " " + (f.get("evidence_quote") or "") for f in facts)
        except Exception:
            pass

    project_violations = []

    for sc in plan_data.get("scenes", []):
        sid = sc.get("id")
        narr = sc.get("narration", "")
        vp = sc.get("visual_plan") or {}
        data = vp.get("data") or {}
        items = data.get("items") or []

        has_percent_evidence = ("%" in narr) or ("phần trăm" in narr.lower()) or ("%" in brief_text) or ("phần trăm" in brief_text.lower())
        allowed_nums = values_in(narr + " " + brief_text)

        # 1. Check raw digits > 6 digits
        check_texts = [str(data.get("number_text", "")), str(data.get("text", "")), str(data.get("label", "")), str(data.get("unit", "")), str(data.get("title", ""))]
        check_texts.extend([str(it) for it in items])
        for vt in check_texts:
            if not vt:
                continue
            if re.search(r'\b\d{7,}\b', vt):
                project_violations.append(f"Cảnh {sid}: chuỗi số thô > 6 chữ số: '{vt}'")
            cleaned_num = re.sub(r'[,.]', '', vt)
            if re.search(r'\b\d{7,}\b', cleaned_num) and not any(w in vt.lower() for w in ["tỷ", "triệu", "nghìn", "ngàn", "usd", "$"]):
                project_violations.append(f"Cảnh {sid}: chuỗi số thô > 6 chữ số sau làm sạch: '{vt}'")
            if "%" in vt and not has_percent_evidence:
                project_violations.append(f"Cảnh {sid}: dấu % không có căn cứ trong text: '{vt}'")

        if data.get("unit") == "%" and not has_percent_evidence:
            project_violations.append(f"Cảnh {sid}: đơn vị % không có căn cứ")

        # 2. Check fabricated "Ước tính" bars
        bars = data.get("bars", [])
        if bars:
            has_estimate_word = ("ước tính" in narr.lower()) or ("ước tính" in brief_text.lower()) or ("dự báo" in narr.lower())
            for b in bars:
                blbl = str(b.get("label", "")).lower()
                if "ước tính" in blbl and not has_estimate_word:
                    project_violations.append(f"Cảnh {sid}: cột 'Ước tính' tự sinh: '{b}'")

        # 3. Check fake versus 40/85
        if len(bars) >= 2:
            b_vals = [b.get("value") for b in bars]
            if 40 in b_vals and 85 in b_vals and ("40" not in allowed_nums or "85" not in allowed_nums):
                project_violations.append(f"Cảnh {sid}: thanh versus giả 40/85")

        # 4. Check numbers grounded
        if data.get("value") is not None and not data.get("no_numbers", False):
            val_str = f"{data['value']:.10f}".rstrip("0").rstrip(".")
            if not values_in(val_str) <= allowed_nums:
                project_violations.append(f"Cảnh {sid}: số {data['value']} không có trong căn cứ")

    results.append({
        "tag": tag,
        "project": p_name,
        "found": True,
        "violations_count": len(project_violations),
        "violations": project_violations
    })

print(json.dumps(results, indent=2, ensure_ascii=False))
