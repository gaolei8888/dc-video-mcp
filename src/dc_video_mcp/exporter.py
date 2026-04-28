"""Auto-generated per-video exports: markdown + interleaved PDF.

Frame-to-caption mapping: frames sit at
``<frames_dir>/<video_id>/frame_NNNNN.jpg`` (1-based, sorted lexicographically)
and caption segments sorted by ``t_start`` align 1:1 with that order.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image

from .config import CONFIG
from .storage import Segment, Storage


def _mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def _split(segs: Sequence[Segment]) -> tuple[list[Segment], list[Segment]]:
    caps = sorted([s for s in segs if s.kind == "caption"], key=lambda s: s.t_start)
    trans = sorted([s for s in segs if s.kind == "transcript"], key=lambda s: s.t_start)
    return caps, trans


def _frames_for(video_id: str) -> list[Path]:
    return sorted((CONFIG.frames_dir / video_id).glob("*.jpg"))


def _video_meta(storage: Storage, video_id: str) -> dict:
    for v in storage.list_videos():
        if v["video_id"] == video_id:
            return v
    return {}


def _write_md(out: Path, video_id: str, video: dict, caps, trans, frame_count: int) -> None:
    lines = [
        f"# Video {video_id}",
        "",
        "## Metadata",
        f"- video_id: {video_id}",
        f"- duration: {video.get('duration', 0):.2f}s",
        f"- frame_count: {frame_count}",
        f"- transcript_segments: {len(trans)}",
        "",
    ]
    if trans:
        lines += ["## Transcript", ""]
        lines += [f"[{_mmss(s.t_start)}] {s.text}" for s in trans]
        lines.append("")
    lines += ["## Keyframe Captions", ""]
    lines += [f"- [{_mmss(s.t_start)}] {s.text}" for s in caps]
    out.write_text("\n".join(lines), encoding="utf-8")


def _write_pdf(out: Path, video_id: str, video: dict, caps, frames: list[Path]) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable,
        Image as RLImage,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(out), pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )
    flow = [
        Paragraph(f"Video {video_id}", styles["Title"]),
        Paragraph(
            f"duration {video.get('duration', 0):.2f}s &middot; "
            f"{len(frames)} keyframes",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]
    max_w = 500
    for i, cap in enumerate(caps):
        flow.append(Paragraph(f"<b>[{_mmss(cap.t_start)}]</b> {cap.text}", styles["Normal"]))
        flow.append(Spacer(1, 6))
        if i < len(frames):
            try:
                with Image.open(frames[i]) as im:
                    iw, ih = im.size
                w = min(max_w, iw)
                h = w * ih / iw
                flow.append(RLImage(str(frames[i]), width=w, height=h))
            except Exception as exc:  # noqa: BLE001
                flow.append(Paragraph(f"<i>[image load failed: {exc}]</i>", styles["Normal"]))
        flow.append(Spacer(1, 8))
        flow.append(HRFlowable(width="100%", thickness=0.5, color="#cccccc"))
        flow.append(Spacer(1, 8))
    doc.build(flow)


def export_video(video_id: str, storage: Storage) -> dict:
    """Write markdown + PDF for a video. Returns paths."""
    out_dir = CONFIG.cache_dir / "exports" / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{video_id}.md"
    pdf_path = out_dir / f"{video_id}.pdf"

    video = _video_meta(storage, video_id)
    caps, trans = _split(storage.all_segments(video_id))
    frames = _frames_for(video_id)

    _write_md(md_path, video_id, video, caps, trans, len(frames))
    _write_pdf(pdf_path, video_id, video, caps, frames)
    return {"export_md": str(md_path), "export_pdf": str(pdf_path)}
