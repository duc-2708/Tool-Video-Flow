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
    ids=[c.category_id.casefold() for c in data.categories]
    if len(ids)!=len(set(ids)): raise ValueError("ID danh mục bị trùng.")
    return data


def save_categories(data,path=None):
    source = Path(path) if path else DEFAULT_CATEGORIES
    parsed = CategoryFile.model_validate(data)
    names = [c.name.casefold() for c in parsed.categories]
    if len(names)!=len(set(names)): raise ValueError("Tên danh mục bị trùng.")
    ids=[c.category_id.casefold() for c in parsed.categories]
    if len(ids)!=len(set(ids)): raise ValueError("ID danh mục bị trùng.")
    with file_lock(source.with_suffix(".lock")):
        write_text_atomic(source,yaml.safe_dump(parsed.model_dump(mode="json"),allow_unicode=True,sort_keys=False))
    return parsed


def categories_for(settings):
    path=settings.root_dir/"config/categories.yaml"
    return load_categories(path if path.is_file() else None)


def resolve_category(settings, value):
    from utils.text import slugify
    for category in categories_for(settings).categories:
        if value in {category.category_id,category.name} or slugify(value)==slugify(category.category_id):
            return category
    raise ValueError(f"Danh mục không có trong categories.yaml: {value}")
