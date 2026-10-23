"""SQLite repository with short transactions, WAL and parameterized statements."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, path, user_id=1):
        self.path = Path(path)
        self.user_id = int(user_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS scan_sources (
                    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL DEFAULT 1,
                    category_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('channel','keyword')),
                    value TEXT NOT NULL, label TEXT NOT NULL, source_url TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1, last_scanned_at TEXT, created_at TEXT NOT NULL,
                    thumbnail_url TEXT NOT NULL DEFAULT '',
                    UNIQUE(user_id, category_id, kind, value));
                CREATE TABLE IF NOT EXISTS learned_videos (
                    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL DEFAULT 1,
                    category_id TEXT NOT NULL, platform TEXT NOT NULL, video_id TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '', channel_id TEXT NOT NULL DEFAULT '',
                    published_at TEXT, duration_sec REAL NOT NULL DEFAULT 0, analyzed_at TEXT,
                    analysis_path TEXT, status TEXT NOT NULL CHECK(status IN ('done','failed','skipped')),
                    error TEXT, permanent_skip INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(platform, video_id, category_id));
                CREATE TABLE IF NOT EXISTS learned_video_sources (
                    video_pk INTEGER NOT NULL REFERENCES learned_videos(id) ON DELETE CASCADE,
                    source_id INTEGER NOT NULL REFERENCES scan_sources(id) ON DELETE CASCADE,
                    PRIMARY KEY(video_pk, source_id));
                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL DEFAULT 1,
                    provider TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS learned_category ON learned_videos(user_id, category_id, status);
                PRAGMA user_version=1;
            """)

    @classmethod
    def for_settings(cls, settings, user_id=1):
        path = settings.root_dir / "data/app.db"
        if not path.resolve().is_relative_to(settings.root_dir.resolve()) or path.is_symlink():
            raise ValueError("SQLite phải nằm trong data/app.db của dự án.")
        return cls(path, user_id)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_source(self, category_id, kind, value, label, source_url="", thumbnail_url=""):
        with self.connection() as db:
            db.execute("""INSERT INTO scan_sources(user_id,category_id,kind,value,label,source_url,thumbnail_url,created_at)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(user_id,category_id,kind,value) DO UPDATE SET
                label=excluded.label,source_url=excluded.source_url,thumbnail_url=excluded.thumbnail_url""",
                (self.user_id,category_id,kind,value,label,source_url,thumbnail_url,utcnow()))
            return dict(db.execute("SELECT * FROM scan_sources WHERE user_id=? AND category_id=? AND kind=? AND value=?",
                (self.user_id,category_id,kind,value)).fetchone())

    def sources(self, category_id, active_only=False):
        with self.connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM scan_sources WHERE user_id=? AND category_id=?"+
                (" AND active=1" if active_only else "")+" ORDER BY id",(self.user_id,category_id))]

    def source(self, source_id):
        with self.connection() as db:
            row=db.execute("SELECT * FROM scan_sources WHERE user_id=? AND id=?",(self.user_id,source_id)).fetchone()
            if row is None:
                raise ValueError("Nguồn quét không tồn tại.")
            return dict(row)

    def activate(self, source_id, active):
        with self.connection() as db:
            db.execute("UPDATE scan_sources SET active=? WHERE id=? AND user_id=?",(int(active),source_id,self.user_id))

    def scanned(self, source_id):
        with self.connection() as db:
            db.execute("UPDATE scan_sources SET last_scanned_at=? WHERE id=? AND user_id=?",(utcnow(),source_id,self.user_id))

    def video(self, category_id, platform, video_id):
        with self.connection() as db:
            row=db.execute("SELECT * FROM learned_videos WHERE user_id=? AND category_id=? AND platform=? AND video_id=?",
                (self.user_id,category_id,platform,video_id)).fetchone()
            return dict(row) if row else None

    def videos(self, category_id, source_id=None):
        with self.connection() as db:
            query="SELECT v.* FROM learned_videos v WHERE v.user_id=? AND v.category_id=?"
            args=[self.user_id,category_id]
            if source_id is not None:
                query+=" AND EXISTS(SELECT 1 FROM learned_video_sources s WHERE s.video_pk=v.id AND s.source_id=?)"
                args.append(source_id)
            return [dict(r) for r in db.execute(query+" ORDER BY v.id DESC",args)]

    def save_video(self, category_id, platform, video_id, *, status, source_ids=(), force=False, **data):
        columns=("url","title","channel_id","published_at","duration_sec","analyzed_at","analysis_path","error","permanent_skip")
        unknown=set(data)-set(columns)
        if unknown:
            raise ValueError("Cột video không được hỗ trợ.")
        with self.connection() as db:
            # Serialize the read+insert decision, including across processes.
            # UNIQUE alone prevents duplicates but would raise in a racing writer.
            db.execute("BEGIN IMMEDIATE")
            existing=db.execute("SELECT * FROM learned_videos WHERE user_id=? AND platform=? AND video_id=? AND category_id=?",
                (self.user_id,platform,video_id,category_id)).fetchone()
            if existing and not force and (existing["status"]=="done" or existing["permanent_skip"]):
                pk=existing["id"]
            elif existing:
                fields={**data,"status":status}
                db.execute("UPDATE learned_videos SET "+",".join(k+"=?" for k in fields)+" WHERE id=?",
                    (*fields.values(),existing["id"]))
                pk=existing["id"]
            else:
                fields={"user_id":self.user_id,"category_id":category_id,"platform":platform,"video_id":video_id,"status":status,**data}
                cursor=db.execute("INSERT INTO learned_videos("+",".join(fields)+") VALUES("+",".join("?" for _ in fields)+")",tuple(fields.values()))
                pk=cursor.lastrowid
            for source_id in source_ids:
                # A source from another user/category must never be linked.
                source=db.execute("SELECT id FROM scan_sources WHERE id=? AND user_id=? AND category_id=?",(source_id,self.user_id,category_id)).fetchone()
                if source:
                    db.execute("INSERT OR IGNORE INTO learned_video_sources VALUES(?,?)",(pk,source_id))
            return dict(db.execute("SELECT * FROM learned_videos WHERE id=?",(pk,)).fetchone())

    def skip_forever(self, category_id, platform, video_id):
        return self.save_video(category_id,platform,video_id,status="skipped",force=True,
            permanent_skip=1,error="Người dùng chọn bỏ qua mãi mãi.")

    def count_call(self, provider):
        with self.connection() as db:
            db.execute("INSERT INTO api_usage(user_id,provider,created_at) VALUES(?,?,?)",(self.user_id,provider,utcnow()))

    def daily_calls(self, provider):
        with self.connection() as db:
            return db.execute("SELECT COUNT(*) FROM api_usage WHERE user_id=? AND provider=? AND created_at>=?",
                (self.user_id,provider,utcnow()[:10])).fetchone()[0]
