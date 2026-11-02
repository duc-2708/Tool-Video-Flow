"""Motion Vocabulary Recipes package."""
from pathlib import Path
import hashlib
from .recipe_meta import RecipeMetadata, RecipeStage, RECIPES_PHASE_A, RECIPES_PHASE_B, RECIPES_PHASE_C, ALL_RECIPES, dump_all_descriptors

# Export descriptors automatically on import
DESCRIPTORS_DIR = Path(__file__).parent / "descriptors"
dump_all_descriptors(DESCRIPTORS_DIR)

VOCABULARY_JS = Path(__file__).parent / "vocabulary.js"
LIGHT_GLASS_JS = Path(__file__).parent / "light_glass.js"


def bundle_vocabulary() -> tuple[str, str, str]:
    """Return (css_str, js_str, sha256_digest) for Motion Vocabulary Recipes."""
    js_parts = []
    hasher = hashlib.sha256()
    if VOCABULARY_JS.is_file():
        js_parts.append(VOCABULARY_JS.read_text(encoding="utf-8"))
        hasher.update(VOCABULARY_JS.read_bytes())
    if LIGHT_GLASS_JS.is_file():
        js_parts.append(LIGHT_GLASS_JS.read_text(encoding="utf-8"))
        hasher.update(LIGHT_GLASS_JS.read_bytes())
    return "", "\n".join(js_parts), hasher.hexdigest()


__all__ = [
    "RecipeMetadata",
    "RecipeStage",
    "RECIPES_PHASE_A",
    "RECIPES_PHASE_B",
    "RECIPES_PHASE_C",
    "ALL_RECIPES",
    "dump_all_descriptors",
    "bundle_vocabulary",
]
