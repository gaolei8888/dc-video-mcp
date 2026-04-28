"""Configuration: paths and model identifiers, all env-overridable.

Heavy imports stay out of this module so MCP startup is fast.
"""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path


def _env_path(var: str, default: Path) -> Path:
    raw = os.environ.get(var)
    return Path(raw).expanduser() if raw else default


def _default_cache_dir() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Documents" / "dc-video-mcp"
    if system == "Windows":
        return Path.home() / "Documents" / "dc-video-mcp"
    return Path.home() / "dc-video-mcp"


DEFAULT_CACHE = _default_cache_dir()


@dataclass(frozen=True)
class Config:
    cache_dir: Path
    db_path: Path
    frames_dir: Path
    caption_model: str
    whisper_model: str  # alias of asr_model, kept for back-compat
    asr_model: str
    asr_language: str | None
    embed_model: str
    device: str  # "auto" | "cpu" | "mps" | "cuda"
    scene_threshold: float  # ffmpeg select=gt(scene\,X)

    @classmethod
    def from_env(cls) -> "Config":
        cache = _env_path("DC_VIDEO_MCP_CACHE", DEFAULT_CACHE)
        cache.mkdir(parents=True, exist_ok=True)
        db = _env_path("DC_VIDEO_MCP_DB", cache / "index.db")
        frames = _env_path("DC_VIDEO_MCP_FRAMES", cache / "frames")
        frames.mkdir(parents=True, exist_ok=True)
        # ASR_MODEL takes precedence; fall back to legacy WHISPER_MODEL; default "base".
        asr_model = (
            os.environ.get("DC_VIDEO_MCP_ASR_MODEL")
            or os.environ.get("DC_VIDEO_MCP_WHISPER_MODEL")
            or "base"
        )
        asr_language = os.environ.get("DC_VIDEO_MCP_ASR_LANGUAGE") or None
        return cls(
            cache_dir=cache,
            db_path=db,
            frames_dir=frames,
            caption_model=os.environ.get("DC_VIDEO_MCP_CAPTION_MODEL", "vikhyatk/moondream2"),
            whisper_model=asr_model,
            asr_model=asr_model,
            asr_language=asr_language,
            embed_model=os.environ.get("DC_VIDEO_MCP_EMBED_MODEL", "clip-ViT-B-32"),
            device=os.environ.get("DC_VIDEO_MCP_DEVICE", "auto"),
            scene_threshold=float(os.environ.get("DC_VIDEO_MCP_SCENE_THRESHOLD", "0.4")),
        )


CONFIG = Config.from_env()


def reconfigure(*, cache_dir: str | Path | None = None) -> Config:
    """Rebuild CONFIG with overrides and propagate to all importing modules."""
    import sys

    if cache_dir is not None:
        os.environ["DC_VIDEO_MCP_CACHE"] = str(cache_dir)

    new = Config.from_env()

    # Update module-level CONFIG in this module and all importers.
    global CONFIG  # noqa: PLW0603
    CONFIG = new
    this = sys.modules[__name__]
    for mod in sys.modules.values():
        if mod is this or mod is None:
            continue
        try:
            if getattr(mod, "CONFIG", None) is not None and mod.__name__.startswith("dc_video_mcp"):
                mod.CONFIG = new  # type: ignore[attr-defined]
        except Exception:
            pass
    return new
