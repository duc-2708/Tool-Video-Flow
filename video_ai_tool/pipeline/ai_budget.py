"""Conservative atomic daily POST budget; errors/ambiguous submits still count."""
from datetime import datetime,timezone,timedelta
from utils.atomic_io import read_json_atomic,write_json_atomic
from utils.file_lock import file_lock


def reserve(settings,identity):
    day=datetime.now(timezone(timedelta(hours=7))).date().isoformat()
    folder=settings.cache_dir;folder.mkdir(parents=True,exist_ok=True)
    path=folder/'ai_clip_budget.json'
    with file_lock(folder/'ai_clip_budget.lock'):
        data=read_json_atomic(path) if path.exists() else {}
        requests=data.setdefault(day,[])
        if identity in requests: return
        if len(requests)>=settings.ai_clip_budget_per_day:
            raise ValueError('Đã hết AI_CLIP_BUDGET_PER_DAY (lượt POST, gồm thử lại/lỗi). Dùng nền gradient; không gửi thêm job.')
        requests.append(identity)
        # Reserve is durable before any paid POST, including retries. Fail closed.
        write_json_atomic(path,{k:v for k,v in data.items() if k>=day})


def remaining(settings):
    day=datetime.now(timezone(timedelta(hours=7))).date().isoformat()
    path=settings.cache_dir/'ai_clip_budget.json'
    data=read_json_atomic(path) if path.exists() else {}
    return max(0,settings.ai_clip_budget_per_day-len(data.get(day,[])))
