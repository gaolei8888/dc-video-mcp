"""SQLite + sqlite-vec storage. Single-file DB.

Schema:
    videos(id TEXT PK, path TEXT, duration REAL, fps REAL, indexed_at TEXT, meta JSON)
    segments(id INTEGER PK, video_id, kind TEXT, t_start REAL, t_end REAL, text TEXT)
        kind in ('caption', 'transcript')
    vec_segments(rowid INTEGER PK, embedding FLOAT[DIM]) -- sqlite-vec virtual table

Embedding dim defaults to 512 (CLIP ViT-B/32). Override with embedding_dim arg.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence


@dataclass
class Segment:
    video_id: str
    kind: str  # 'caption' | 'transcript'
    t_start: float
    t_end: float
    text: str


@dataclass
class SearchHit:
    video_id: str
    kind: str
    t_start: float
    t_end: float
    text: str
    score: float


class Storage:
    def __init__(self, db_path: Path, embedding_dim: int = 512) -> None:
        self.db_path = Path(db_path)
        self.embedding_dim = embedding_dim
        self._ensure_schema()

    # --- connection ---

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            self._load_vec(conn)
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _load_vec(conn: sqlite3.Connection) -> None:
        """Load sqlite-vec extension. Lazy import keeps cold start fast."""
        try:
            import sqlite_vec  # noqa: WPS433 - intentional lazy import
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("sqlite-vec not installed") from exc
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

    # --- schema ---

    def _ensure_schema(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    duration REAL,
                    fps REAL,
                    indexed_at TEXT NOT NULL,
                    meta TEXT
                );
                CREATE TABLE IF NOT EXISTS segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    t_start REAL NOT NULL,
                    t_end REAL NOT NULL,
                    text TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_segments_video
                    ON segments(video_id, t_start);
                """
            )
            c.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_segments "
                f"USING vec0(embedding FLOAT[{self.embedding_dim}])"
            )

    # --- writes ---

    def upsert_video(
        self,
        video_id: str,
        path: str,
        duration: float,
        fps: float,
        indexed_at: str,
        meta: dict | None = None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO videos(id, path, duration, fps, indexed_at, meta) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (video_id, path, duration, fps, indexed_at, json.dumps(meta or {})),
            )
            c.execute("DELETE FROM segments WHERE video_id = ?", (video_id,))
            # Note: orphaned vec_segments rows are tolerated; rebuilt on next add.

    def add_segments(
        self,
        items: Sequence[tuple[Segment, Sequence[float]]],
    ) -> None:
        """Insert segments + their embeddings transactionally."""
        if not items:
            return
        import struct

        with self._conn() as c:
            for seg, emb in items:
                cur = c.execute(
                    "INSERT INTO segments(video_id, kind, t_start, t_end, text) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (seg.video_id, seg.kind, seg.t_start, seg.t_end, seg.text),
                )
                rowid = cur.lastrowid
                blob = struct.pack(f"{len(emb)}f", *emb)
                c.execute(
                    "INSERT INTO vec_segments(rowid, embedding) VALUES (?, ?)",
                    (rowid, blob),
                )

    # --- reads ---

    def list_videos(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, path, duration, fps, indexed_at, meta FROM videos "
                "ORDER BY indexed_at DESC"
            ).fetchall()
        out: list[dict] = []
        for r in rows:
            out.append(
                {
                    "video_id": r["id"],
                    "path": r["path"],
                    "duration": r["duration"],
                    "fps": r["fps"],
                    "indexed_at": r["indexed_at"],
                    "meta": json.loads(r["meta"] or "{}"),
                }
            )
        return out

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int = 10,
        video_id: str | None = None,
    ) -> list[SearchHit]:
        import struct

        blob = struct.pack(f"{len(query_embedding)}f", *query_embedding)
        sql = (
            "SELECT s.video_id, s.kind, s.t_start, s.t_end, s.text, v.distance "
            "FROM vec_segments v JOIN segments s ON s.id = v.rowid "
            "WHERE v.embedding MATCH ? AND k = ? "
        )
        params: list = [blob, top_k]
        if video_id:
            sql += "AND s.video_id = ? "
            params.append(video_id)
        sql += "ORDER BY v.distance"
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        return [
            SearchHit(
                video_id=r["video_id"],
                kind=r["kind"],
                t_start=r["t_start"],
                t_end=r["t_end"],
                text=r["text"],
                score=1.0 - float(r["distance"]),
            )
            for r in rows
        ]

    def segments_in_window(
        self, video_id: str, start: float, end: float
    ) -> list[Segment]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT video_id, kind, t_start, t_end, text FROM segments "
                "WHERE video_id = ? AND t_end >= ? AND t_start <= ? "
                "ORDER BY t_start",
                (video_id, start, end),
            ).fetchall()
        return [
            Segment(
                video_id=r["video_id"],
                kind=r["kind"],
                t_start=r["t_start"],
                t_end=r["t_end"],
                text=r["text"],
            )
            for r in rows
        ]

    def all_segments(self, video_id: str) -> list[Segment]:
        return self.segments_in_window(video_id, 0.0, float("inf"))

    def has_video(self, video_id: str) -> bool:
        with self._conn() as c:
            r = c.execute("SELECT 1 FROM videos WHERE id = ?", (video_id,)).fetchone()
        return r is not None
