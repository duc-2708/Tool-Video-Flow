with open("tools/audit_video.py", "r", encoding="utf-8") as f:
    c = f.read()

pos = c.find("# Check numeric hallucinations and % unit validity")
assert pos != -1
end_pos = c.find("# Check empty gap", pos)
assert end_pos != -1

new_code = '''# Check numeric hallucinations and % unit validity
        narration_text = str(scene.get("narration", ""))
        has_percent_evidence = ("%" in narration_text) or ("phần trăm" in narration_text.lower())
        numeric_hallucinations = 0

        # Facts context from brief if available
        brief_text = ""
        if brief:
            facts = getattr(brief, "facts", [])
            brief_text = " ".join((getattr(f, "fact_vi", None) or getattr(f, "claim", "")) + " " + (getattr(f, "evidence_quote", None) or "") for f in facts)

        from agents.visual_diversity import values_in
        allowed_nums = values_in(narration_text + " " + brief_text)

        # 1. Check raw digits > 6 digits (e.g. 65000000000 or 65.000.000.00)
        scene_visual_texts = [str(data.get("number_text", "")), str(data.get("text", "")), str(data.get("label", "")), str(data.get("unit", "")), str(data.get("title", ""))]
        scene_visual_texts.extend([str(it) for it in items])
        for vt in scene_visual_texts:
            if not vt:
                continue
            if re.search(r'\\b\\d{7,}\\b', vt):
                numeric_hallucinations += 1
            cleaned_num = re.sub(r'[,.]', '', vt)
            if re.search(r'\\b\\d{7,}\\b', cleaned_num) and not any(w in vt.lower() for w in ["tỷ", "triệu", "nghìn", "ngàn", "usd", "$"]):
                numeric_hallucinations += 1
            if "%" in vt and not has_percent_evidence:
                numeric_hallucinations += 1
        if data.get("unit") == "%" and not has_percent_evidence:
            numeric_hallucinations += 1

        # 2. Check fabricated "Ước tính" bars without evidence
        bars = data.get("bars", [])
        if bars:
            has_estimate_word = ("ước tính" in narration_text.lower()) or ("ước tính" in brief_text.lower()) or ("dự báo" in narration_text.lower())
            for b in bars:
                blbl = str(b.get("label", "")).lower()
                if "ước tính" in blbl and not has_estimate_word:
                    numeric_hallucinations += 1

        # 3. Check fake versus 40/85 default bars
        if len(bars) >= 2:
            b_vals = [b.get("value") for b in bars]
            if 40 in b_vals and 85 in b_vals and ("40" not in allowed_nums or "85" not in allowed_nums):
                numeric_hallucinations += 1

        # 4. Check all visual numbers against allowed evidence
        if data.get("value") is not None and not data.get("no_numbers", False):
            val_str = f"{data['value']:.10f}".rstrip("0").rstrip(".")
            if not values_in(val_str) <= allowed_nums:
                numeric_hallucinations += 1

        for b in bars:
            if b.get("value") is not None:
                bval_str = f"{b['value']:.10f}".rstrip("0").rstrip(".")
                if not values_in(bval_str) <= allowed_nums:
                    numeric_hallucinations += 1

        '''

c = c[:pos] + new_code + c[end_pos:]
with open("tools/audit_video.py", "w", encoding="utf-8") as f:
    f.write(c)

print("Successfully updated tools/audit_video.py!")
