# dc-video-mcp

Lightweight MCP server for video analysis. Extracts keyframes with ffmpeg,
captions them with a small VLM (Moondream2 by default), transcribes audio with
faster-whisper, embeds everything with CLIP, and stores it in a single SQLite
file (sqlite-vec). Designed for laptop / Apple Silicon use; no docker, no
local LLM. The calling assistant (e.g. Claude) synthesizes summaries from
the structured output.

## Install

Requires Python 3.11+ and a working `ffmpeg` / `ffprobe` on PATH.

```sh
uv sync
```

Heavy ML dependencies (torch, transformers, faster-whisper,
sentence-transformers) are declared in `pyproject.toml` but lazy-imported at
tool-call time so the server starts fast. Models are downloaded on first use
and cached under `~/.cache/dc-video-mcp` (override with
`DC_VIDEO_MCP_CACHE`).

## Run

```sh
uv run dc-video-mcp
```

The server speaks MCP over stdio.

## Claude Desktop config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dc-video-mcp": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/dc-video-mcp", "run", "dc-video-mcp"]
    }
  }
}
```

## Tools

- `index_video(path, fps=0.5, asr_language=None, asr_model=None)` - extract
  keyframes (scene change, fallback to fps sampling), caption + transcribe
  + embed, persist. `asr_language` is an ISO 639-1 code (`en`, `zh`, `ja`,
  ...) or `None` to auto-detect. `asr_model` overrides the configured
  Whisper size (`tiny`, `base`, `small`, `medium`, `large-v3`); models are
  cached per size so swapping does not reload an already-loaded model. The
  result includes `asr_model`, `asr_language` (used or detected), and
  `asr_language_detected`.
- `list_supported_languages()` - curated top-30 ISO 639-1 codes accepted by
  `asr_language`. Whisper supports ~99 total; pass any code it accepts.
- `search_video(query, video_id?, top_k=10)` - semantic search over captions
  and transcript segments.
- `get_clip_context(video_id, start, end)` - captions and transcript inside a
  time window.
- `list_videos()` - all indexed videos with metadata.
- `summarize_video(video_id, style="default")` - returns full captions +
  transcript plus a `style_instruction` the caller LLM should follow when
  formatting the summary. See "Styles" below.
- `list_styles()` - enumerate available output style presets.

## Auto-export

After every `index_video` call, the server writes two files into
`~/.cache/dc-video-mcp/exports/<video_id>/`:

- `<video_id>.md` — keyframe captions + transcript (markdown)
- `<video_id>.pdf` — same content as PDF, with each keyframe screenshot
  embedded inline next to its `[mm:ss] caption` line (rendered with reportlab)

Paths are returned in the `index_video` response as `export_md` / `export_pdf`.
Export failures are logged and non-fatal — indexing always succeeds first.

## Slash command: `/video-blog` (Claude Code)

A Claude Code slash command at `~/.claude/commands/video-blog.md` runs the
full pipeline in one shot: index → generate tech-style blog (md) → render
to PDF with embedded keyframes → open.

```
/video-blog /abs/path/to/video.mov [style=...] [tone=...] [audience=...] [frames=N] [lang=...] [length=...]
```

Flags (all optional):

| Flag | Values | Default |
| --- | --- | --- |
| `style` | `influencer`, `tutorial`, `changelog`, `exec-summary`, `thread` | `influencer` |
| `tone` | freeform (e.g. `dry-witty`, `academic`, `hype`) | preset default |
| `audience` | freeform (e.g. `CFOs`, `junior-devs`) | unset |
| `frames` | int 3–20, target keyframes embedded | `8` |
| `lang` | ISO 639-1 (`en`, `zh`, ...) | `en` |
| `length` | `short` (~300w), `medium` (~700w), `long` (~1500w) | `medium` |

Examples:

```
/video-blog /v/demo.mov
/video-blog /v/demo.mov style=tutorial audience=junior-devs frames=12
/video-blog /v/demo.mov style=exec-summary tone=dry length=short
/video-blog /v/demo.mov style=thread lang=zh
```

Output lands at `~/.cache/dc-video-mcp/exports/<video_id>/blog.md` +
`blog.pdf`. After generation, ask the assistant for edits in plain language
("swap the frame in section 3", "make it shorter", "translate to Chinese") —
it edits the md and re-renders the PDF.

The renderer is a small reportlab script at
`scripts/blog_md_to_pdf.py`; it parses headings, paragraphs, lists, quotes,
inline `**bold**`/`*italic*`/`` `code` ``, and image references with
relative paths.

## Styles

`summarize_video` returns raw structured data; the caller LLM does the
writing. The `style` argument selects a prompt fragment (returned as
`style_instruction`) telling the LLM exactly how to format its output. The
server itself never calls an LLM.

Presets:

| Style | Description |
| --- | --- |
| `default` | Neutral 3-5 paragraph summary. |
| `blog` | Engaging blog post (500-800 words) with title, intro, sections, conclusion. |
| `release_notes` | Terse bullet changelog grouped into New / Changed / Fixed. |
| `tutorial` | Step-by-step guide with prerequisites and expected outcome. |
| `tweet_thread` | 5-8 tweet thread, hook first, each <280 chars, ends with CTA. |
| `transcript_clean` | Cleaned transcript only (grammar fixed, fillers removed). No summary. |
| `key_moments` | Timestamped highlight list with short descriptions. |

Two ways to use a style:

1. **Tool argument** - call `summarize_video(video_id, style="blog")`
   directly. Unknown style raises a `ValueError` listing valid names.
2. **Slash-command prompt** - the server registers one MCP prompt per
   non-default style, so Claude Desktop surfaces them as slash commands:
   `blog-from-video`, `release-notes-from-video`, `tutorial-from-video`,
   `tweet-thread-from-video`, `clean-transcript`, `key-moments`. Each takes
   a `video_id` argument and instructs the assistant to invoke
   `summarize_video` with the matching style.

## Supported formats

Anything `ffmpeg` decodes: mp4, mov, mkv, webm, avi, m4v, etc.

## Models (env-overridable)

| Variable | Default | Notes |
| --- | --- | --- |
| `DC_VIDEO_MCP_CAPTION_MODEL` | `vikhyatk/moondream2` | Swap to SmolVLM, Florence-2, etc. by editing `models.py`. |
| `DC_VIDEO_MCP_ASR_MODEL` | `base` | Whisper size: `tiny`, `base`, `small`, `medium`, `large-v3`. |
| `DC_VIDEO_MCP_WHISPER_MODEL` | (unset) | Legacy alias for `DC_VIDEO_MCP_ASR_MODEL`; used only if the new var is unset. |
| `DC_VIDEO_MCP_ASR_LANGUAGE` | (unset) | ISO 639-1 code; unset = auto-detect per video. |
| `DC_VIDEO_MCP_EMBED_MODEL` | `clip-ViT-B-32` | Any sentence-transformers model. Changing this requires a fresh DB. |
| `DC_VIDEO_MCP_DEVICE` | `auto` | `auto` picks `mps` / `cuda` / `cpu`. |
| `DC_VIDEO_MCP_SCENE_THRESHOLD` | `0.4` | ffmpeg scene-change sensitivity. |
| `DC_VIDEO_MCP_CACHE` | `~/.cache/dc-video-mcp` | Frames + DB + model cache root. |
| `DC_VIDEO_MCP_DB` | `<cache>/index.db` | SQLite path. |

## ASR model sizes

faster-whisper sizes trade RAM and speed for transcription quality. Pick
per-call via `asr_model` or set `DC_VIDEO_MCP_ASR_MODEL`.

| Size | Approx RAM (int8 CPU) | Relative speed | Quality |
| --- | --- | --- | --- |
| `tiny` | ~0.5 GB | ~10x realtime | Lowest; OK for clean English |
| `base` | ~0.8 GB | ~7x realtime | Default; good general use |
| `small` | ~1.5 GB | ~4x realtime | Notably better, esp. non-English |
| `medium` | ~3 GB | ~1.5x realtime | High quality; slow on CPU |
| `large-v3` | ~5 GB | <1x realtime CPU | Best; recommend GPU |

Examples:

```jsonc
// English
{ "name": "index_video", "arguments": { "path": "/v/talk.mp4", "asr_language": "en" } }
// Mandarin Chinese
{ "name": "index_video", "arguments": { "path": "/v/jiang.mp4", "asr_language": "zh", "asr_model": "small" } }
// Japanese, large model
{ "name": "index_video", "arguments": { "path": "/v/jp.mp4", "asr_language": "ja", "asr_model": "large-v3" } }
```

## Multilingual note

ASR (Whisper) is multilingual out of the box. Embeddings (`clip-ViT-B-32`)
are English-tuned, so semantic search quality drops for non-English queries
even when transcripts are correctly transcribed. For heavy non-English use,
swap the embed model to a multilingual one and rebuild the DB:

```sh
DC_VIDEO_MCP_EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2 \
  uv run dc-video-mcp
```

The default is unchanged; this is a recommendation only.

## Swapping the captioner

`models.py` exposes a `Captioner` Protocol with a single `.caption(path) -> str`
method. Drop in a class implementing it and return it from `get_captioner()`.

## Tests

```sh
uv run pytest
```

`tests/test_storage.py` exercises the SQLite + sqlite-vec layer end-to-end
without loading any ML model.
