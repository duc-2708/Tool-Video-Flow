"""Category-aware reference paths; moving requires an explicit user action."""
import os
from pathlib import Path
from config.categories import categories_for, resolve_category
from schemas.style import AnalysisRecord
from utils.atomic_io import write_json_atomic, read_json_atomic
from utils.file_lock import file_lock


def root(settings):
    from pipeline.style_learner import reference_dir
    return reference_dir(settings)


def resolve_video(settings, filename):
    base=root(settings)
    relative=Path(filename)
    parts=relative.parts
    if relative.is_absolute() or len(parts) not in (1,2) or any(p in {".",".."} or ":" in p for p in parts):
        raise ValueError("Chọn file .mp4 trong assets/reference_videos/ hoặc thư mục danh mục hợp lệ.")
    if len(parts)==2 and parts[0]!="_unsorted":
        resolve_category(settings,parts[0])
    path=base/relative
    if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(base) or path.suffix.lower()!=".mp4" or not path.is_file():
        raise ValueError("Chọn file .mp4 thực trong thư viện; không dùng URL/liên kết/đường dẫn ngoài.")
    return path.resolve()


def relative_name(settings, path):
    return Path(path).resolve().relative_to(root(settings)).as_posix()


def category_of(settings, filename):
    relative=resolve_video(settings,filename).relative_to(root(settings))
    return resolve_category(settings,relative.parts[0]).category_id if len(relative.parts)==2 and relative.parts[0]!="_unsorted" else None


def list_videos(settings, category=None):
    base=root(settings)
    target=resolve_category(settings,category).category_id if category and category!="_unsorted" else category
    found=[]
    for path in sorted(base.glob("*.mp4"))+sorted(base.glob("*/*.mp4")):
        if path.parent.name=="analysis":
            continue
        try:
            name=relative_name(settings,resolve_video(settings,relative_name(settings,path)))
            actual=category_of(settings,name)
            if target is None or target==actual or target=="_unsorted" and actual is None:
                found.append(name)
        except ValueError:
            continue
    return list(dict.fromkeys(found))


def record_path(settings, filename, *, status=False):
    from pipeline.style_learner import storage
    path=resolve_video(settings,filename)
    relative=path.relative_to(root(settings))
    destination=storage(settings)/relative.with_suffix(".status.json" if status else ".json")
    if not destination.resolve().is_relative_to(storage(settings)) or destination.parent.is_symlink():
        raise ValueError("Đường dẫn phân tích nằm ngoài thư viện.")
    return destination


def read_record(settings, filename):
    return AnalysisRecord.model_validate(read_json_atomic(record_path(settings,filename)))


def confirm_category(settings, filename, category):
    """Never overwrite another video. Notes and analysis move with the video."""
    from pipeline.style_learner import digest_file,storage
    source=resolve_video(settings,filename)
    category=resolve_category(settings,category)
    destination=root(settings)/category.category_id/source.name
    destination.parent.mkdir(exist_ok=True)
    if destination.parent.is_symlink() or destination.resolve().parent!=destination.parent.resolve() or not destination.resolve().is_relative_to(root(settings)):
        raise ValueError("Thư mục đích không hợp lệ.")
    with file_lock(storage(settings)/"library.lock",timeout=1):
        record=read_record(settings,filename)
        if digest_file(source)!=record.file_hash:
            raise ValueError("Video đã đổi sau phân tích; phân tích lại trước khi xác nhận.")
        old_record=record_path(settings,filename)
        old_status=record_path(settings,filename,status=True)
        notes=source.with_suffix(".txt")
        if notes.is_symlink():
            raise ValueError("File ghi chú không được là liên kết.")
        if source!=destination and (destination.exists() or destination.with_suffix(".txt").exists()):
            raise FileExistsError("Đích đã có video/ghi chú cùng tên; đổi tên hoặc chọn danh mục khác.")
        # Validate the exact resolved source and destination before the move.
        if source!=destination:
            source.rename(destination)
            try:
                if notes.exists():
                    notes.rename(destination.with_suffix(".txt"))
            except OSError:
                destination.rename(source)
                raise
        new_name=relative_name(settings,destination)
        record=record.model_copy(update={"filename":new_name,"category_id":category.category_id,"category_confirmed":True})
        write_json_atomic(record_path(settings,new_name),record.model_dump(mode="json"))
        if old_status.exists():
            write_json_atomic(record_path(settings,new_name,status=True),read_json_atomic(old_status))
        if old_record!=record_path(settings,new_name):
            old_record.unlink(missing_ok=True)
            old_status.unlink(missing_ok=True)
        return new_name


def save_upload(settings, filename, data, category="_unsorted"):
    """Persist browser uploads without allowing paths or replacing existing files."""
    from utils.atomic_io import write_bytes_atomic
    from pipeline.style_learner import inspect_video
    if filename!=Path(filename).name or Path(filename).suffix.lower()!=".mp4" or not data or len(data)>settings.style_max_file_mb*1024**2:
        raise ValueError("Upload phải là MP4 có tên hợp lệ, nằm trong giới hạn kích thước.")
    folder=root(settings)/(resolve_category(settings,category).category_id if category!="_unsorted" else "_unsorted")
    folder.mkdir(exist_ok=True)
    path=folder/filename
    if folder.is_symlink() or not path.resolve().is_relative_to(root(settings)):
        raise ValueError("Đường dẫn upload không hợp lệ.")
    with file_lock(root(settings)/"analysis/library.lock",timeout=1):
        if path.exists():
            raise FileExistsError("Đã có video cùng tên; đổi tên trước khi upload.")
        write_bytes_atomic(path,data)
        try:
            inspect_video(path,settings)
        except Exception:
            path.unlink(missing_ok=True)
            raise
    return relative_name(settings,path)
