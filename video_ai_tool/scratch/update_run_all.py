from pathlib import Path

target_file = Path("pipeline/run_all.py")
code = target_file.read_text(encoding="utf-8")

old_str = """                                        manifest_data["resolved_plan_hash"] = cache_key(resolved_obj.model_dump(mode="json"))
                                        write_json_atomic(project / "assets.json", manifest_data)
                                except Exception:
                                    pass
                        files,warnings = asset_files(project,project/"edit_plan.json")
                        if (project / "director_state.visual_v3.json").is_file():
                            files.append(project / "director_state.visual_v3.json")"""

new_str = """                                        manifest_data["resolved_plan_hash"] = cache_key(resolved_obj.model_dump(mode="json"))
                                        write_json_atomic(project / "assets.json", manifest_data)
                                except Exception:
                                    pass

                            # Giai đoạn 8-W2a: Visual Bible cho video
                            try:
                                emit(step, "Khởi tạo Visual Bible kế hoạch hình ảnh tổng thể...")
                                from agents.visual_bible import create_visual_bible, save_visual_bible
                                v_bible, v_status = create_visual_bible(
                                    current_plan,
                                    brief=brief_obj,
                                    words_by_scene=words_map,
                                    settings=settings,
                                    diagnostics=diagnostics,
                                )
                                save_visual_bible(project, v_bible, v_status)
                            except Exception as exc:
                                diagnostics.record_exception(exc, "Khởi tạo Visual Bible thất bại")
                        files,warnings = asset_files(project,project/"edit_plan.json")
                        if (project / "director_state.visual_v3.json").is_file():
                            files.append(project / "director_state.visual_v3.json")
                        if (project / "visual_bible.json").is_file():
                            files.append(project / "visual_bible.json")
                        if (project / "visual_bible_status.json").is_file():
                            files.append(project / "visual_bible_status.json")"""

assert old_str in code, "old_str not found in run_all.py"
code = code.replace(old_str, new_str)
target_file.write_text(code, encoding="utf-8")
print("run_all.py updated with visual bible integration!")
