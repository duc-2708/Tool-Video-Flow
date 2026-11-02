from pathlib import Path

p = Path("video_ai_tool/editor/render.py")
text = p.read_text(encoding="utf-8")

target = "            # Đảm bảo mọi shot trong timeline đều có visual_plan được lập lịch riêng"
assert target in text, "target not found in render.py"

insert_code = """            # Tự động kích hoạt Slide Script khi theme là light_glass
            if settings.motion_theme == "light_glass" and (timeline.project / "brief.json").is_file():
                try:
                    from schemas.slide_script import SlideScript
                    from editor.motion.light_glass_slots import create_heuristic_slide_script
                    from editor.motion.slide_grounding import verify_and_ground_slides
                    from utils.atomic_io import read_json_atomic, write_json_atomic
                    from utils.word_timing import read_words

                    slide_script_file = timeline.project / "slide_script.json"
                    slide_script_obj = None
                    if slide_script_file.is_file():
                        try:
                            slide_script_obj = SlideScript.model_validate(read_json_atomic(slide_script_file))
                        except Exception:
                            slide_script_obj = None

                    if slide_script_obj is None:
                        sentences = []
                        cur_t = 0.0
                        for sc in timeline.scenes:
                            w_file = timeline.project / "audio" / f"scene_{sc.spec.id}.words.json"
                            sc_words = read_words(w_file) if w_file.is_file() else []
                            sentences.append({
                                "id": sc.spec.id,
                                "text": sc.spec.narration,
                                "start": cur_t,
                                "end": cur_t + sc.duration,
                                "words": sc_words,
                            })
                            cur_t += sc.duration
                        brief_data = read_json_atomic(timeline.project / "brief.json")
                        slide_script_obj = create_heuristic_slide_script(
                            sentences=sentences,
                            brief=brief_data,
                            total_duration=cur_t,
                            brand_name=getattr(settings, "brand_name", "TIN CÔNG NGHỆ"),
                        )
                        slide_script_obj = verify_and_ground_slides(slide_script_obj, {s["id"]: s for s in sentences}, brief_data)
                        write_json_atomic(slide_script_file, slide_script_obj.model_dump(mode="json"))

                    scene_to_slide = {}
                    for sl in slide_script_obj.slides:
                        for sid in sl.sentence_ids:
                            scene_to_slide[sid] = sl

                    for sc in timeline.scenes:
                        matching_slide = scene_to_slide.get(sc.spec.id)
                        if matching_slide:
                            from schemas.motion_scene import MotionScenePlan
                            from schemas.visual import VisualBeat, VisualData
                            s_data_dict = dict(matching_slide.slots)
                            s_data_dict["emphasis"] = [e.model_dump(mode="json") for e in matching_slide.emphasis]
                            valid_vkeys = set(VisualData.model_fields.keys())
                            clean_vdata = {k: v for k, v in s_data_dict.items() if k in valid_vkeys}
                            shot_spec_data = VisualData(**clean_vdata) if clean_vdata else VisualData()
                            vp_obj = MotionScenePlan(
                                scene_type=matching_slide.layout,
                                layout=matching_slide.layout,
                                theme="light_glass",
                                data=shot_spec_data,
                                beats=[
                                    VisualBeat(at_sec=0.35, action=f"enter_{matching_slide.layout}"),
                                    VisualBeat(at_sec=1.2, action=f"action_{matching_slide.layout}_step"),
                                ],
                                transition="directional_wipe",
                            )
                            setattr(vp_obj, "slot_data", s_data_dict)
                            for sh in sc.shots:
                                sh.spec.visual_plan = vp_obj
                                sh.visual_plan = vp_obj
                except Exception as lg_err:
                    diagnostics.record_exception(lg_err, "Tự động áp dụng Slide Script khi render theme light_glass lỗi")

"""

text = text.replace(target, insert_code + target, 1)
p.write_text(text, encoding="utf-8")
print("Updated editor/render.py successfully!")
