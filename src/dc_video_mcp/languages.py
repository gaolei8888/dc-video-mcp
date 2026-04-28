"""ASR language helpers.

Whisper supports 99 languages total. We expose a curated top-30 subset by
global usage for the `list_supported_languages` MCP tool. Pass any ISO 639-1
code Whisper accepts via `asr_language` on `index_video` even if not listed
here. Full list: https://github.com/openai/whisper#available-models-and-languages
"""
from __future__ import annotations

# (code, English name). ISO 639-1 codes accepted by faster-whisper.
SUPPORTED_LANGUAGES: list[dict[str, str]] = [
    {"code": "en", "name": "English"},
    {"code": "zh", "name": "Chinese"},
    {"code": "es", "name": "Spanish"},
    {"code": "hi", "name": "Hindi"},
    {"code": "ar", "name": "Arabic"},
    {"code": "pt", "name": "Portuguese"},
    {"code": "bn", "name": "Bengali"},
    {"code": "ru", "name": "Russian"},
    {"code": "ja", "name": "Japanese"},
    {"code": "de", "name": "German"},
    {"code": "fr", "name": "French"},
    {"code": "ko", "name": "Korean"},
    {"code": "tr", "name": "Turkish"},
    {"code": "vi", "name": "Vietnamese"},
    {"code": "it", "name": "Italian"},
    {"code": "pl", "name": "Polish"},
    {"code": "uk", "name": "Ukrainian"},
    {"code": "nl", "name": "Dutch"},
    {"code": "id", "name": "Indonesian"},
    {"code": "th", "name": "Thai"},
    {"code": "fa", "name": "Persian"},
    {"code": "he", "name": "Hebrew"},
    {"code": "sv", "name": "Swedish"},
    {"code": "el", "name": "Greek"},
    {"code": "cs", "name": "Czech"},
    {"code": "ro", "name": "Romanian"},
    {"code": "hu", "name": "Hungarian"},
    {"code": "fi", "name": "Finnish"},
    {"code": "da", "name": "Danish"},
    {"code": "no", "name": "Norwegian"},
]


def list_supported_languages() -> list[dict[str, str]]:
    """Return the curated top-30 language list. Whisper supports ~99 total."""
    return list(SUPPORTED_LANGUAGES)
