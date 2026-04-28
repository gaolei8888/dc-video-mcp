"""Lazy-loaded model singletons.

All heavy imports happen on first call so the MCP server starts fast.
Replace functions here to swap captioner / ASR / embedder.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from .config import CONFIG


def _resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    import torch  # local import

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


# --- Captioner ---------------------------------------------------------------

class Captioner(Protocol):
    def caption(self, image_path: Path) -> str: ...


class _Moondream2:
    """Default captioner. Swap by writing a class with .caption(path) -> str."""

    def __init__(self, model_id: str, device: str) -> None:
        from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa

        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, trust_remote_code=True
        ).to(device)
        self.model.eval()

    def caption(self, image_path: Path) -> str:
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        enc = self.model.encode_image(image)
        return self.model.answer_question(enc, "Describe this image.", self.tokenizer).strip()


@lru_cache(maxsize=1)
def get_captioner() -> Captioner:
    return _Moondream2(CONFIG.caption_model, _resolve_device(CONFIG.device))


# --- ASR ---------------------------------------------------------------------

@lru_cache(maxsize=4)
def _load_asr(model_size: str):
    from faster_whisper import WhisperModel

    device = _resolve_device(CONFIG.device)
    # faster-whisper supports cpu/cuda; mps falls back to cpu.
    fw_device = "cuda" if device == "cuda" else "cpu"
    compute = "float16" if fw_device == "cuda" else "int8"
    return WhisperModel(model_size, device=fw_device, compute_type=compute)


def get_asr(model_size: str | None = None):
    """Return a faster-whisper model. Cached per model_size string.

    None -> use config default. Same size key returns the cached instance.
    """
    return _load_asr(model_size or CONFIG.asr_model)


# --- Embedder ----------------------------------------------------------------

@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer

    device = _resolve_device(CONFIG.device)
    return SentenceTransformer(CONFIG.embed_model, device=device)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedder()
    out = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return out.tolist()


def embedding_dim() -> int:
    """Dimension of the configured embedder. CLIP ViT-B/32 = 512."""
    return int(get_embedder().get_sentence_embedding_dimension())
