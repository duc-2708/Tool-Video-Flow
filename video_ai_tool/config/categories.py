"""Safe, editable RSS category settings; no access to credentials."""
from pathlib import Path
import yaml
from config.settings import ROOT_DIR
from schemas.topic_discovery import CategoryFile
from utils.atomic_io import write_text_atomic
from utils.file_lock import file_lock

DEFAULT_CATEGORIES = ROOT_DIR/"config/categories.yaml"

def load_categories(path=None):
    source = Path(path) if path else DEFAULT_CATEGORIES
    data = CategoryFile.model_validate(yaml.safe_load(source.read_text(encoding="utf-8")))
    names = [c.name.casefold() for c in data.categories]
    if len(names)!=len(set(names)): raise ValueError("Tên danh mục bị trùng.")
    return data


def save_categories(data,path=None):
    source = Path(path) if path else DEFAULT_CATEGORIES
    parsed = CategoryFile.model_validate(data)
    names = [c.name.casefold() for c in parsed.categories]
    if len(names)!=len(set(names)): raise ValueError("Tên danh mục bị trùng.")
    with file_lock(source.with_suffix(".lock")):
        write_text_atomic(source,yaml.safe_dump(parsed.model_dump(mode="json"),allow_unicode=True,sort_keys=False))
    return parsed
