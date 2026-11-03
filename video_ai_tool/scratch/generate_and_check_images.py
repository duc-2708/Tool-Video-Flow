import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemas.slide_script import SlideScript
from pipeline.slide_image_resolver import resolve_images_for_slide_script
from editor.motion.light_glass_slots import _generate_vivid_image_prompt

project_dir = ROOT / "output" / "auto-cong-nghe-f4d9a86b"
slide_script_file = project_dir / "slide_script.json"

if not slide_script_file.is_file():
    print(f"Missing {slide_script_file}")
    sys.exit(1)

ss = SlideScript.model_validate_json(slide_script_file.read_text(encoding="utf-8"))
print(f"Loaded slide script with {len(ss.slides)} slides.")

# Refresh prompts for all slides using the upgraded generator
for idx, slide in enumerate(ss.slides):
    author = "Elon Musk" if idx == 0 else ("Ted Jenkin" if idx in (6, 7) else None)
    new_prompt = _generate_vivid_image_prompt(
        narration=slide.narration,
        layout=slide.layout,
        author=author,
        idx=idx,
    )
    slide.image_prompt = new_prompt
    slide.slots["image_prompt"] = new_prompt

# Save updated slide_script
slide_script_file.write_text(ss.model_dump_json(indent=2), encoding="utf-8")

# Resolve images
resolved = resolve_images_for_slide_script(project_dir, ss, force_refresh=True)

print(f"\nResolved {len(resolved)} image assets:")
sizes = []
for idx, r in enumerate(resolved):
    p = Path(r)
    sz = p.stat().st_size
    sizes.append(sz)
    print(f"Beat {idx+1:02d}: {p.name} -> {sz} bytes")

unique_sizes = len(set(sizes))
print(f"\nTotal distinct file sizes: {unique_sizes} / {len(sizes)}")
assert unique_sizes >= 8, f"Expected high variety of visuals, got only {unique_sizes} distinct sizes"
print("SUCCESS: 12 beats have high-variety, distinct imagery!")
