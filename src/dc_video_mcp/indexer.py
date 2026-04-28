"""Indexing pipeline: ffmpeg keyframes -> caption + ASR -> embed -> store."""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import CONFIG
from .storage import Segment, Storage


def _video_id(path: Path) -> str:
    stat = path.stat()
    seed = f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"
    return hashlib.sha1(seed.encode()).hexdigest()[:16]


def _has_audio_stream(path: Path) -> bool:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=index",
                "-of", "json", str(path),
            ]
        )
        return bool(json.loads(out).get("streams"))
    except (subprocess.CalledProcessError, ValueError, KeyError) as exc:
        print(f"[indexer] ffprobe audio probe failed: {exc}", file=sys.stderr)
        return False


def _ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ]
    )
    return float(json.loads(out)["format"]["duration"])


def _extract_keyframes(video: Path, out_dir: Path, fps: float, scene_thr: float) -> list[tuple[float, Path]]:
    """Extract keyframes via scene-change filter; fallback to fps sampling.

    Returns list of (timestamp_seconds, image_path).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jpg"):
        old.unlink()

    # Try scene-change first.
    pattern = str(out_dir / "scene_%05d.jpg")
    proc = subprocess.run(
        [
            "ffmpeg", "-loglevel", "error", "-y", "-i", str(video),
            "-vf", f"select='gt(scene,{scene_thr})',showinfo",
            "-vsync", "vfr", "-frame_pts", "1", pattern,
        ],
        capture_output=True, text=True,
    )
    timestamps = _parse_showinfo(proc.stderr)
    frames = sorted(out_dir.glob("scene_*.jpg"))

    if frames and len(frames) == len(timestamps):
        return list(zip(timestamps, frames))

    # Fallback: sample at fps.
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    pattern = str(out_dir / "frame_%05d.jpg")
    subprocess.run(
        [
            "ffmpeg", "-loglevel", "error", "-y", "-i", str(video),
            "-vf", f"fps={fps}", pattern,
        ],
        check=True,
    )
    frames = sorted(out_dir.glob("frame_*.jpg"))
    interval = 1.0 / fps if fps > 0 else 2.0
    return [((i + 0.5) * interval, f) for i, f in enumerate(frames)]


def _parse_showinfo(stderr: str) -> list[float]:
    """Parse showinfo lines to extract pts_time per emitted frame."""
    times: list[float] = []
    for line in stderr.splitlines():
        if "pts_time:" not in line:
            continue
        try:
            t = line.split("pts_time:")[1].split()[0]
            times.append(float(t))
        except (IndexError, ValueError):
            continue
    return times


def _transcribe(
    video: Path,
    language: str | None,
    model_size: str | None,
) -> tuple[list[Segment], str | None]:
    from .models import get_asr

    if not _has_audio_stream(video):
        print(f"[indexer] no audio stream in {video}; skipping transcription", file=sys.stderr)
        return [], None

    asr = get_asr(model_size)
    kwargs: dict = {"vad_filter": True}
    if language:
        kwargs["language"] = language
    try:
        segments, info = asr.transcribe(str(video), **kwargs)
    except Exception as exc:  # noqa: BLE001
        print(f"[indexer] asr.transcribe failed: {exc}", file=sys.stderr)
        return [], None
    out: list[Segment] = []
    for s in segments:
        text = (s.text or "").strip()
        if not text:
            continue
        out.append(Segment(
            video_id="",  # filled by caller
            kind="transcript",
            t_start=float(s.start),
            t_end=float(s.end),
            text=text,
        ))
    detected = getattr(info, "language", None)
    return out, detected


def _caption_frames(frames: list[tuple[float, Path]]) -> list[Segment]:
    from .models import get_captioner

    cap = get_captioner()
    out: list[Segment] = []
    for ts, path in frames:
        try:
            text = cap.caption(path)
        except Exception as exc:  # noqa: BLE001
            text = f"[caption failed: {exc}]"
        if text:
            out.append(Segment(
                video_id="",
                kind="caption",
                t_start=float(ts),
                t_end=float(ts),
                text=text,
            ))
    return out


def _index_sync(
    path: Path,
    fps: float,
    storage: Storage,
    asr_language: str | None,
    asr_model: str | None,
) -> dict:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg/ffprobe not found in PATH")

    video_id = _video_id(path)
    duration = _ffprobe_duration(path)

    frame_dir = CONFIG.frames_dir / video_id
    frames = _extract_keyframes(path, frame_dir, fps=fps, scene_thr=CONFIG.scene_threshold)

    captions = _caption_frames(frames)
    language = asr_language if asr_language is not None else CONFIG.asr_language
    model_used = asr_model or CONFIG.asr_model
    transcripts, detected_language = _transcribe(path, language, model_used)
    for seg in (*captions, *transcripts):
        seg.video_id = video_id

    from .models import embed_texts, embedding_dim

    if storage.embedding_dim != embedding_dim():
        # Mismatch indicates DB built with a different embed model. Surface clearly.
        raise RuntimeError(
            f"Embedding dim mismatch: storage={storage.embedding_dim} "
            f"model={embedding_dim()}. Delete the DB or set DC_VIDEO_MCP_EMBED_MODEL."
        )

    all_segs = [*captions, *transcripts]
    storage.upsert_video(
        video_id=video_id,
        path=str(path.resolve()),
        duration=duration,
        fps=fps,
        indexed_at=datetime.now(timezone.utc).isoformat(),
        meta={"frame_count": len(frames)},
    )
    if all_segs:
        embeddings = embed_texts([s.text for s in all_segs])
        storage.add_segments(list(zip(all_segs, embeddings)))

    result = {
        "video_id": video_id,
        "duration": duration,
        "frames": len(frames),
        "captions": len(captions),
        "transcript_segments": len(transcripts),
        "asr_model": model_used,
        "asr_language": language or detected_language,
        "asr_language_detected": detected_language,
    }
    try:
        from .exporter import export_video

        result.update(export_video(video_id, storage))
    except Exception as exc:  # noqa: BLE001
        print(f"[indexer] export failed: {exc}", file=sys.stderr)
    return result


async def index_video(
    path: str,
    fps: float,
    storage: Storage,
    asr_language: str | None = None,
    asr_model: str | None = None,
) -> dict:
    """Async wrapper: runs the blocking pipeline in a thread."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(p)
    return await asyncio.to_thread(
        _index_sync, p, fps, storage, asr_language, asr_model
    )
