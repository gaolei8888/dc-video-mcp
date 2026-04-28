# dc-video-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A local MCP server that turns video files into searchable, summarizable, blog-ready knowledge bases. Keyframe extraction, multi-lingual transcription, semantic search, and one-shot blog generation -- all on your machine, no cloud APIs required.

---

## Highlights

- **MCP-native.** Plugs into Claude Desktop, Claude Code, or any MCP client over stdio.
- **Multi-lingual transcription.** Powered by faster-whisper (Whisper), supporting ~99 languages with automatic detection or explicit language selection.
- **Fully local.** Moondream2 for frame captioning, faster-whisper for ASR, CLIP for embeddings, sqlite-vec for vector storage. No external API keys.
- **Apple Silicon friendly.** Runs natively on macOS (MPS), Linux (CUDA/CPU), and Windows. No Docker required.
- **One-shot blog generation.** Index a video and generate a polished blog post with embedded screenshots in a single command.
- **RAG-powered search.** Vector embeddings (CLIP) + sqlite-vec enable semantic retrieval across every indexed video. The MCP client (e.g. Claude) closes the RAG loop by generating answers from retrieved context.

---

## Multi-Lingual Support

dc-video-mcp uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper), a high-performance reimplementation of OpenAI Whisper, for speech recognition. It supports approximately **99 languages** out of the box.

### Automatic language detection

By default, faster-whisper auto-detects the spoken language. No configuration needed -- just index a video and the language is identified automatically.

### Explicit language selection

For faster processing or when auto-detection is unreliable (short clips, mixed-language audio), set the language explicitly:

**Per-call** via the `index_video` tool:
```json
{ "name": "index_video", "arguments": { "path": "/videos/lecture.mp4", "asr_language": "ja" } }
```

**Globally** via environment variable:
```sh
export DC_VIDEO_MCP_ASR_LANGUAGE=zh
```

This accepts any ISO 639-1 code that Whisper supports. The `list_supported_languages` tool returns a curated top-30 list, but any valid code works.

### Whisper model selection

Larger models yield better accuracy, especially for non-English languages:

| Model | RAM (int8 CPU) | Speed | Quality |
|---|---|---|---|
| `tiny` | ~0.5 GB | ~10x realtime | Lowest; fine for clean English |
| `base` | ~0.8 GB | ~7x realtime | **Default -- good general use** |
| `small` | ~1.5 GB | ~4x realtime | Notably better for non-English |
| `medium` | ~3 GB | ~1.5x realtime | High quality; slow on CPU |
| `large-v3` | ~5 GB | <1x realtime CPU | Best quality; GPU recommended |

Set via `DC_VIDEO_MCP_ASR_MODEL` or the `asr_model` parameter on `index_video`.

### Multilingual semantic search

The default embedding model (`clip-ViT-B-32`) is English-tuned. Transcripts in other languages will be accurate, but semantic search quality may degrade for non-English queries. For heavy non-English use, switch to a multilingual embedding model:

```sh
DC_VIDEO_MCP_EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2 uv run dc-video-mcp
```

This requires a fresh database (embeddings are not cross-compatible between models).

---

## Installation

### Prerequisites

| Dependency | Version | Purpose | Install |
|---|---|---|---|
| **Python** | 3.11+ | Runtime | [python.org](https://www.python.org/downloads/) or `brew install python` |
| **ffmpeg** | any recent | Video decoding & frame extraction | See below |
| **uv** | latest | Python package manager | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

#### Installing ffmpeg

| OS | Command |
|---|---|
| macOS | `brew install ffmpeg` |
| Ubuntu / Debian | `sudo apt install ffmpeg` |
| Windows | `choco install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html) |

Verify: `ffmpeg -version`

```sh
git clone https://github.com/gaolei8888/dc-video-mcp.git
cd dc-video-mcp
uv sync
```

Heavy ML dependencies (torch, transformers, faster-whisper, sentence-transformers) are lazy-imported on first tool call. The server boots instantly and models download once on first use.

### Run the server

```sh
uv run dc-video-mcp
```

With a custom storage directory:

```sh
uv run dc-video-mcp --cache-dir /path/to/storage
```

### Connect to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```jsonc
{
  "mcpServers": {
    "dc-video-mcp": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/dc-video-mcp", "run", "dc-video-mcp"]
    }
  }
}
```

### Supported video formats

Anything ffmpeg decodes: `.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`, `.m4v`, and more.

---

## MCP Tools

| Tool | Description |
|---|---|
| `index_video(path, fps?, asr_language?, asr_model?)` | Extract keyframes, caption them, transcribe audio, embed, and persist. Auto-exports Markdown and PDF. Returns `video_id`, counts, and export paths. |
| `search_video(query, video_id?, top_k?)` | Semantic search across captions and transcripts. Optionally filter by video. |
| `get_clip_context(video_id, start, end)` | Retrieve all captions and transcript segments within a time window. |
| `summarize_video(video_id, style?)` | Return structured video data with a style instruction for the caller LLM. The server itself never calls an LLM. |
| `list_videos()` | List all indexed videos with metadata. |
| `list_styles()` | List available summarization style presets. |
| `list_supported_languages()` | List the curated top-30 ASR language codes (Whisper supports ~99 total). |

### Summarization style presets

| Style | Output |
|---|---|
| `default` | Neutral 3-5 paragraph summary |
| `blog` | 500-800 word blog post |
| `release_notes` | New / Changed / Fixed bullet points |
| `tutorial` | Step-by-step guide with prerequisites |
| `tweet_thread` | 5-8 tweet thread, hook-first |
| `transcript_clean` | Cleaned transcript without summary |
| `key_moments` | Timestamped highlight reel |

Each non-default style is also exposed as an MCP prompt (slash command in Claude Desktop): `blog-from-video`, `tutorial-from-video`, `release-notes-from-video`, `tweet-thread-from-video`, `clean-transcript`, `key-moments`.

---

## The `/video-blog` Slash Command

A Claude Code slash command that runs the full pipeline in one shot:

```
/video-blog /Users/you/Desktop/demo.mov
```

This indexes the video (keyframes, captions, transcript, embeddings), writes a blog post (`blog.md`) with hand-picked screenshots embedded inline, renders it to PDF (`blog.pdf`), and opens the result.

### Customization flags

```
/video-blog demo.mov style=tutorial audience=junior-devs frames=12
/video-blog demo.mov style=exec-summary tone=dry length=short
/video-blog demo.mov style=thread lang=zh
```

| Flag | Values |
|---|---|
| `style` | `influencer` (default), `tutorial`, `changelog`, `exec-summary`, `thread` |
| `tone` | Freeform: `dry-witty`, `academic`, `hype`, etc. |
| `audience` | Freeform: `CFOs`, `junior-devs`, etc. |
| `frames` | Integer 3-20 (default `8`) |
| `lang` | ISO 639-1 code: `en`, `zh`, `ja`, etc. |
| `length` | `short` (~300 words), `medium` (~700 words, default), `long` (~1500 words) |

After generation, iterate by talking to Claude: swap frames, adjust tone, translate, or re-render the PDF.

---

## Configuration

### CLI argument

| Argument | Description |
|---|---|
| `--cache-dir` | Override the storage directory. Takes priority over env var and OS default. |

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `DC_VIDEO_MCP_CACHE` | OS-dependent (see below) | Root storage directory for frames, exports, and model cache. |
| `DC_VIDEO_MCP_DB` | `<cache>/index.db` | SQLite database path. |
| `DC_VIDEO_MCP_CAPTION_MODEL` | `vikhyatk/moondream2` | Vision-language model for frame captioning. |
| `DC_VIDEO_MCP_ASR_MODEL` | `base` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large-v3`. |
| `DC_VIDEO_MCP_ASR_LANGUAGE` | Auto-detect | ISO 639-1 language code to force for all transcriptions. |
| `DC_VIDEO_MCP_EMBED_MODEL` | `clip-ViT-B-32` | Sentence-transformer model for embeddings. |
| `DC_VIDEO_MCP_DEVICE` | `auto` | Compute device: `auto`, `cpu`, `mps`, `cuda`. |
| `DC_VIDEO_MCP_SCENE_THRESHOLD` | `0.4` | Scene-change sensitivity. Higher = fewer keyframes. |

### Default storage paths

| OS | Default path |
|---|---|
| macOS | `~/Documents/dc-video-mcp` |
| Windows | `~/Documents/dc-video-mcp` |
| Linux | `~/dc-video-mcp` |

Priority order: `--cache-dir` CLI argument > `DC_VIDEO_MCP_CACHE` env var > OS default.

### Output structure

```
<cache-dir>/
  index.db                          # sqlite-vec vector index (all videos)
  frames/<video_id>/                # extracted keyframes
    frame_00001.jpg
    frame_00002.jpg
    ...
  exports/<video_id>/
    <video_id>.md                   # full caption dump
    <video_id>.pdf                  # text + keyframes inline
```

---

## Extending

### Custom captioner

`models.py` exposes a `Captioner` protocol with a `.caption(path) -> str` method. Implement the protocol and return your class from `get_captioner()`.

### Custom PDF renderer

`scripts/blog_md_to_pdf.py` uses reportlab (~120 lines). Edit fonts, margins, page size, or callout styling as needed. The slash command picks up changes immediately.

---

## Tests

```sh
uv run pytest
```

`tests/test_storage.py` exercises the SQLite + sqlite-vec layer end-to-end without loading any ML model. Fast feedback, no GPU required.

---

## License

MIT
