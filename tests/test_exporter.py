"""Smoke test against the already-indexed video in the user's cache."""
from __future__ import annotations

from pathlib import Path

import pytest

from dc_video_mcp.config import CONFIG

VIDEO_ID = "abd44648ac6eb27b"


@pytest.mark.skipif(
    not (CONFIG.db_path.exists() and (CONFIG.frames_dir / VIDEO_ID).exists()),
    reason="requires pre-indexed video in user cache",
)
def test_export_smoke():
    from dc_video_mcp.exporter import export_video
    from dc_video_mcp.storage import Storage

    # Match existing DB's embedding dim (512 = CLIP ViT-B/32 default).
    storage = Storage(CONFIG.db_path, embedding_dim=512)
    out = export_video(VIDEO_ID, storage)

    md = Path(out["export_md"])
    pdf = Path(out["export_pdf"])
    assert md.exists() and md.stat().st_size > 0
    assert pdf.exists() and pdf.stat().st_size > 10_000
