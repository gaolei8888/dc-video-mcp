"""Storage roundtrip: insert + window query + vector search.

Uses a tiny embedding dim so we don't need real models.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dc_video_mcp.storage import Segment, Storage


@pytest.fixture()
def storage(tmp_path: Path) -> Storage:
    return Storage(tmp_path / "test.db", embedding_dim=4)


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def test_upsert_and_window(storage: Storage) -> None:
    storage.upsert_video(
        video_id="v1", path="/tmp/a.mp4", duration=30.0, fps=0.5,
        indexed_at=datetime.now(timezone.utc).isoformat(),
    )
    items = [
        (Segment("v1", "caption", 1.0, 1.0, "a dog runs"), _unit([1, 0, 0, 0])),
        (Segment("v1", "transcript", 2.0, 4.0, "hello world"), _unit([0, 1, 0, 0])),
        (Segment("v1", "caption", 10.0, 10.0, "a cat sits"), _unit([0, 0, 1, 0])),
    ]
    storage.add_segments(items)

    in_window = storage.segments_in_window("v1", 0.0, 5.0)
    assert len(in_window) == 2
    assert {s.kind for s in in_window} == {"caption", "transcript"}

    videos = storage.list_videos()
    assert len(videos) == 1 and videos[0]["video_id"] == "v1"
    assert storage.has_video("v1")


def test_vector_search_orders_by_similarity(storage: Storage) -> None:
    storage.upsert_video(
        video_id="v1", path="/tmp/a.mp4", duration=30.0, fps=0.5,
        indexed_at=datetime.now(timezone.utc).isoformat(),
    )
    storage.add_segments([
        (Segment("v1", "caption", 1.0, 1.0, "dog"), _unit([1, 0, 0, 0])),
        (Segment("v1", "caption", 2.0, 2.0, "cat"), _unit([0, 1, 0, 0])),
        (Segment("v1", "caption", 3.0, 3.0, "tree"), _unit([0, 0, 1, 0])),
    ])
    hits = storage.search(_unit([0.9, 0.1, 0, 0]), top_k=3)
    assert hits[0].text == "dog"
    assert len(hits) == 3


def test_upsert_replaces_segments(storage: Storage) -> None:
    iso = datetime.now(timezone.utc).isoformat()
    storage.upsert_video("v1", "/tmp/a.mp4", 10.0, 0.5, iso)
    storage.add_segments([(Segment("v1", "caption", 0.0, 0.0, "old"), _unit([1, 0, 0, 0]))])
    # Re-upsert: segments wiped.
    storage.upsert_video("v1", "/tmp/a.mp4", 10.0, 0.5, iso)
    assert storage.all_segments("v1") == []
