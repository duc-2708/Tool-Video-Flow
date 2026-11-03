"""Helper script to update light_glass.js to Hero Full-Stage Visual Motion."""
from pathlib import Path

file_path = Path("editor/motion/recipes/light_glass.js")
content = file_path.read_text(encoding="utf-8")

# Let's inspect where renderLgSourceHeadline starts
start_tag = "// 1. lg_source_headline"
end_tag = "// Export light glass recipes"

idx_start = content.find(start_tag)
idx_end = content.find(end_tag)

if idx_start == -1 or idx_end == -1:
    print(f"Error: tags not found. start={idx_start}, end={idx_end}")
else:
    print(f"Found region: {idx_start} to {idx_end} (length: {idx_end - idx_start})")
