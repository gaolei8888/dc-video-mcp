# dc-video-mcp 🎬⚡

> **Drop a video in. Get back a searchable, summarizable, blog-ready knowledge base.** Local. Fast. No cloud. No API keys.

You hand it an `.mov`. It hands you keyframes, captions, transcripts, vector embeddings, and — with one slash command — a **publishable tech-influencer blog post with screenshots inlined.**

All on your laptop. 🚀

---

## TL;DR

- 🔥 **Single MCP server.** Plugs into Claude Desktop / Claude Code / any MCP client.
- ⚡ **Local everything.** Moondream2 for captions, faster-whisper for ASR, CLIP for embeddings, sqlite-vec for storage. No external APIs.
- 🎯 **Apple Silicon native.** No Docker. No GPU required (but it'll use one if you have it).
- 📝 **One-shot blog generation.** `/video-blog video.mov` → indexed + blog.md + blog.pdf with screenshots embedded inline.
- 🔍 **Semantic search across every video you've ever indexed.** "Find the moment someone clicked the orange Pay button" — and it does.

---

## The Hook

You record a 4-minute screen demo. Now what? Re-watch it 12 times to write the blog? Manually screenshot every frame? Pay an LLM to ingest the entire video?

**Stop.** Let your laptop do it.

`dc-video-mcp` extracts every meaningful frame, captions it with a tiny VLM, transcribes the audio, embeds it all into a vector index, and writes the result to disk — captions, transcript, **and** a PDF with each frame embedded next to its timestamped caption.

Then point Claude at it. Ask for a blog. Get a blog. With your screenshots already embedded. No clipboard gymnastics.

---

## What you get out of one `index_video` call

```
~/.cache/dc-video-mcp/exports/<video_id>/
├── <video_id>.md          # full caption dump
├── <video_id>.pdf         # text + every keyframe inline (mm:ss + caption + screenshot)
frames/<video_id>/
├── frame_00001.jpg        # extracted keyframes (scene-cut detected)
├── frame_00002.jpg
└── ...
index.db                   # sqlite-vec: search across ALL your videos
```

> **Pull quote:** *Indexing isn't a step. It's a side effect. The thing you want — the blog, the search, the summary — is one tool call away.*

---

## Install (60 seconds)

Python 3.11+ and `ffmpeg` on PATH.

```sh
git clone <this repo> && cd dc-video-mcp
uv sync
```

Heavy ML deps (torch, transformers, faster-whisper, sentence-transformers) are **lazy-imported on first tool call** — server boots instantly. Models download once, cache to `~/.cache/dc-video-mcp`.

```sh
uv run dc-video-mcp        # speaks MCP over stdio
```

### Wire it to Claude Desktop

```jsonc
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "dc-video-mcp": {
      "command": "uv",
      "args": ["--directory", "/abs/path/to/dc-video-mcp", "run", "dc-video-mcp"]
    }
  }
}
```

---

## ⚡ The killer feature: `/video-blog`

A Claude Code slash command that runs the **entire** pipeline in one shot.

```
/video-blog /Users/you/Desktop/demo.mov
```

That's it. You get:

1. Video indexed (keyframes + captions + transcript + embeddings persisted)
2. Tech-influencer blog written (`blog.md`) with **6–10 hand-picked screenshots embedded inline**
3. Rendered to PDF (`blog.pdf`) — formatted, paginated, ready to send
4. PDF opens automatically

### Customize on the fly

```
/video-blog demo.mov style=tutorial audience=junior-devs frames=12
/video-blog demo.mov style=exec-summary tone=dry length=short
/video-blog demo.mov style=thread lang=zh
/video-blog demo.mov style=changelog
```

| Flag | Values |
| --- | --- |
| `style` | `influencer` (default) · `tutorial` · `changelog` · `exec-summary` · `thread` |
| `tone` | freeform (`dry-witty`, `academic`, `hype`, ...) |
| `audience` | freeform (`CFOs`, `junior-devs`, ...) |
| `frames` | int 3–20 (default `8`) |
| `lang` | ISO 639-1 (`en`, `zh`, `ja`, ...) |
| `length` | `short` (~300w) · `medium` (~700w, default) · `long` (~1500w) |

### Edit loop (no API keys, no friction)

After it generates, just **talk to it**:

> *"swap the frame in section 3 — that one's blank"*
> *"make section 5 shorter and snarkier"*
> *"translate the whole thing to Chinese"*
> *"re-render the pdf"*

Claude edits the md and re-renders. Done.

> **Bold takeaway:** *Most "AI blog generators" lock you into their UI. This one is just files. Markdown in, PDF out, you own all of it.*

---

## 🛠 Tools (the MCP surface)

| Tool | What it does |
| --- | --- |
| `index_video(path, fps=0.5, asr_language=None, asr_model=None)` | Extract keyframes + caption + transcribe + embed + persist + auto-export md/pdf. Returns `video_id`, frame/segment counts, `export_md`, `export_pdf`. |
| `search_video(query, video_id?, top_k=10)` | Semantic search across captions + transcripts. Filterable per video. |
| `get_clip_context(video_id, start, end)` | All captions/transcript inside `[start, end]` seconds. |
| `summarize_video(video_id, style="default")` | Returns full structured data + a `style_instruction` your caller LLM follows. **Server itself never calls an LLM.** |
| `list_videos()` | Every indexed video with metadata. |
| `list_styles()` | Available `summarize_video` style presets. |
| `list_supported_languages()` | Top-30 ISO 639-1 codes for `asr_language` (Whisper supports ~99). |

### Built-in summarize styles

| Style | What you get |
| --- | --- |
| `default` | Neutral 3–5 paragraph summary |
| `blog` | 500–800 word blog post |
| `release_notes` | New / Changed / Fixed bullets |
| `tutorial` | Step-by-step with prereqs |
| `tweet_thread` | 5–8 tweet thread, hook-first |
| `transcript_clean` | Cleaned transcript, no summary |
| `key_moments` | Timestamped highlight reel |

Each non-default style is also exposed as an MCP slash command (`blog-from-video`, `tutorial-from-video`, ...) — appears natively in Claude Desktop.

---

## 🎛 Configuration (env vars)

| Variable | Default | Why you'd touch it |
| --- | --- | --- |
| `DC_VIDEO_MCP_CAPTION_MODEL` | `vikhyatk/moondream2` | Swap to SmolVLM, Florence-2, etc. via `models.py` |
| `DC_VIDEO_MCP_ASR_MODEL` | `base` | `tiny` · `base` · `small` · `medium` · `large-v3` |
| `DC_VIDEO_MCP_ASR_LANGUAGE` | (auto) | Force a language — skip detection cost |
| `DC_VIDEO_MCP_EMBED_MODEL` | `clip-ViT-B-32` | Multilingual? `paraphrase-multilingual-MiniLM-L12-v2` (rebuild DB) |
| `DC_VIDEO_MCP_DEVICE` | `auto` | `mps` / `cuda` / `cpu` |
| `DC_VIDEO_MCP_SCENE_THRESHOLD` | `0.4` | Higher = fewer keyframes |
| `DC_VIDEO_MCP_CACHE` | `~/.cache/dc-video-mcp` | Move it to an SSD with space |
| `DC_VIDEO_MCP_DB` | `<cache>/index.db` | Override SQLite path |

### Whisper sizes — pick your tradeoff

| Size | RAM (int8 CPU) | Speed | Quality |
| --- | --- | --- | --- |
| `tiny` | ~0.5 GB | ~10× realtime | Lowest, fine for clean English |
| `base` | ~0.8 GB | ~7× realtime | **Default — good general use** |
| `small` | ~1.5 GB | ~4× realtime | Notably better, esp. non-English |
| `medium` | ~3 GB | ~1.5× realtime | High quality, slow on CPU |
| `large-v3` | ~5 GB | <1× realtime CPU | Best — recommend GPU |

### Examples

```jsonc
// English screen demo, default everything
{ "name": "index_video", "arguments": { "path": "/v/demo.mp4", "asr_language": "en" } }
// Mandarin lecture, bigger model
{ "name": "index_video", "arguments": { "path": "/v/jiang.mp4", "asr_language": "zh", "asr_model": "small" } }
// Japanese, max quality
{ "name": "index_video", "arguments": { "path": "/v/jp.mp4", "asr_language": "ja", "asr_model": "large-v3" } }
```

---

## 🌐 Multilingual note

Whisper handles ~99 languages out of the box. The default embed model
(`clip-ViT-B-32`) is English-tuned, so **semantic search quality drops for
non-English queries** even when transcripts are accurate. For heavy
non-English use:

```sh
DC_VIDEO_MCP_EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2 uv run dc-video-mcp
```

(This requires a fresh DB — embeddings aren't cross-compatible.)

---

## 🧩 Extending

### Swap the captioner

`models.py` exposes a `Captioner` Protocol with `.caption(path) -> str`. Drop in a class, return it from `get_captioner()`. Done.

### Swap the PDF renderer

`scripts/blog_md_to_pdf.py` is ~120 lines of reportlab. Edit fonts, margins, page size, callouts — whatever. The slash command picks up changes immediately.

---

## 🧪 Tests

```sh
uv run pytest
```

`tests/test_storage.py` exercises the SQLite + sqlite-vec layer end-to-end **without loading any ML model.** Fast feedback, no GPU needed.

---

## Supported formats

Anything `ffmpeg` decodes: `mp4`, `mov`, `mkv`, `webm`, `avi`, `m4v`, ...

---

## Why this exists

Every "AI video summarizer" wants you to upload your video, give them an API key, and trust their pricing. **None of that.**

This thing is a single MCP server. It runs on your laptop. It writes files to your disk. You can read them, edit them, version them, share them. The AI part is whatever client you point at it — Claude Desktop, Claude Code, your own.

If you ship demos, record talks, take screen recordings of bug reproductions, or just have a folder full of `.mov` files you can't search — **this is the missing layer.** 🔥

---

## CTA

```
git clone <repo> && cd dc-video-mcp && uv sync && uv run dc-video-mcp
```

Then drop your first video in. Run `/video-blog`. Watch it write itself.

Drop a 🔥 in the issues if you want me to add a `karaoke` style next.
