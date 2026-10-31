from pathlib import Path

target_file = Path("pipeline/assets.py")
code = target_file.read_text(encoding="utf-8")

old_str = """            scene_audio_hashes=scene_audio_hashes,
            scene_clip_hashes=scene_clip_hashes
        )
        return persist(project, resolved, manifest, diagnostics,motion_enabled=settings.motion_enabled)"""

new_str = """            scene_audio_hashes=scene_audio_hashes,
            scene_clip_hashes=scene_clip_hashes
        )
        # Giai đoạn 8-W2a: Visual Bible
        try:
            from agents.visual_bible import create_visual_bible, save_visual_bible
            brief_f = project / "brief.json"
            brief_obj = None
            if brief_f.is_file():
                try:
                    from schemas.research import ResearchBrief
                    brief_obj = ResearchBrief.model_validate(read_json(brief_f))
                except Exception:
                    brief_obj = read_json(brief_f)
            v_bible, v_status = create_visual_bible(resolved, brief=brief_obj, settings=settings, diagnostics=diagnostics)
            save_visual_bible(project, v_bible, v_status)
        except Exception as exc:
            diagnostics.record_exception(exc, "Tạo Visual Bible trong assets thất bại")

        return persist(project, resolved, manifest, diagnostics,motion_enabled=settings.motion_enabled)"""

assert old_str in code, "old_str not found in assets.py"
code = code.replace(old_str, new_str)
target_file.write_text(code, encoding="utf-8")
print("assets.py updated with visual bible integration!")
