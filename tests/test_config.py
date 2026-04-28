"""Env-var resolution for Config.from_env. No model loads."""
from __future__ import annotations

from pathlib import Path

import pytest

from dc_video_mcp.config import Config
from dc_video_mcp.languages import list_supported_languages


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    for var in (
        "DC_VIDEO_MCP_CACHE",
        "DC_VIDEO_MCP_DB",
        "DC_VIDEO_MCP_FRAMES",
        "DC_VIDEO_MCP_CAPTION_MODEL",
        "DC_VIDEO_MCP_WHISPER_MODEL",
        "DC_VIDEO_MCP_ASR_MODEL",
        "DC_VIDEO_MCP_ASR_LANGUAGE",
        "DC_VIDEO_MCP_EMBED_MODEL",
        "DC_VIDEO_MCP_DEVICE",
        "DC_VIDEO_MCP_SCENE_THRESHOLD",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DC_VIDEO_MCP_CACHE", str(tmp_path))


def test_defaults() -> None:
    cfg = Config.from_env()
    assert cfg.asr_model == "base"
    assert cfg.asr_language is None
    assert cfg.whisper_model == "base"  # alias
    assert cfg.embed_model == "clip-ViT-B-32"
    assert cfg.device == "auto"


def test_asr_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DC_VIDEO_MCP_ASR_MODEL", "small")
    cfg = Config.from_env()
    assert cfg.asr_model == "small"
    assert cfg.whisper_model == "small"


def test_asr_model_falls_back_to_legacy_whisper_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DC_VIDEO_MCP_WHISPER_MODEL", "medium")
    cfg = Config.from_env()
    assert cfg.asr_model == "medium"


def test_asr_model_takes_precedence_over_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DC_VIDEO_MCP_WHISPER_MODEL", "tiny")
    monkeypatch.setenv("DC_VIDEO_MCP_ASR_MODEL", "large-v3")
    cfg = Config.from_env()
    assert cfg.asr_model == "large-v3"


def test_asr_language_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DC_VIDEO_MCP_ASR_LANGUAGE", "zh")
    cfg = Config.from_env()
    assert cfg.asr_language == "zh"


def test_embed_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DC_VIDEO_MCP_EMBED_MODEL",
        "paraphrase-multilingual-MiniLM-L12-v2",
    )
    cfg = Config.from_env()
    assert cfg.embed_model == "paraphrase-multilingual-MiniLM-L12-v2"


def test_supported_languages_shape() -> None:
    langs = list_supported_languages()
    assert len(langs) == 30
    codes = {entry["code"] for entry in langs}
    assert {"en", "zh", "ja", "es", "fr"} <= codes
    for entry in langs:
        assert set(entry) == {"code", "name"}
        assert entry["code"] and entry["name"]


# ---------------------------------------------------------------------------
# _default_cache_dir: OS-specific defaults
# ---------------------------------------------------------------------------


def test_default_cache_dir_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    from dc_video_mcp.config import _default_cache_dir

    monkeypatch.setattr("dc_video_mcp.config.platform.system", lambda: "Darwin")
    result = _default_cache_dir()
    assert result == Path.home() / "Documents" / "dc-video-mcp"


def test_default_cache_dir_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    from dc_video_mcp.config import _default_cache_dir

    monkeypatch.setattr("dc_video_mcp.config.platform.system", lambda: "Windows")
    result = _default_cache_dir()
    assert result == Path.home() / "Documents" / "dc-video-mcp"


def test_default_cache_dir_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    from dc_video_mcp.config import _default_cache_dir

    monkeypatch.setattr("dc_video_mcp.config.platform.system", lambda: "Linux")
    result = _default_cache_dir()
    assert result == Path.home() / "dc-video-mcp"


# ---------------------------------------------------------------------------
# reconfigure(): rebuild CONFIG with overrides
# ---------------------------------------------------------------------------


def test_reconfigure_updates_cache_dir(tmp_path: Path) -> None:
    from dc_video_mcp.config import reconfigure

    new_cache = tmp_path / "test-cache"
    cfg = reconfigure(cache_dir=str(new_cache))
    assert cfg.cache_dir == new_cache


def test_reconfigure_derives_db_and_frames(tmp_path: Path) -> None:
    from dc_video_mcp.config import reconfigure

    new_cache = tmp_path / "test-cache-derived"
    cfg = reconfigure(cache_dir=str(new_cache))
    assert cfg.db_path == new_cache / "index.db"
    assert cfg.frames_dir == new_cache / "frames"


def test_reconfigure_propagates_to_module_config(tmp_path: Path) -> None:
    import dc_video_mcp.config as config_mod
    from dc_video_mcp.config import reconfigure

    new_cache = tmp_path / "test-cache-module"
    reconfigure(cache_dir=str(new_cache))
    assert config_mod.CONFIG.cache_dir == new_cache


# ---------------------------------------------------------------------------
# --cache-dir CLI argument
# ---------------------------------------------------------------------------


def test_cli_accepts_cache_dir_argument() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="dc-video-mcp")
    parser.add_argument("--cache-dir", help="Override cache directory")
    args = parser.parse_args(["--cache-dir", "/tmp/cli-test"])
    assert args.cache_dir == "/tmp/cli-test"


def test_cli_cache_dir_defaults_to_none() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="dc-video-mcp")
    parser.add_argument("--cache-dir", help="Override cache directory")
    args = parser.parse_args([])
    assert args.cache_dir is None
