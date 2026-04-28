"""MCP entry point. Tool registration only; heavy work delegated to indexer/storage."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
)

from .config import CONFIG
from .styles import STYLES, get_instruction, list_styles


server: Server = Server("dc-video-mcp")


def _storage():
    """Lazy storage. Embedding dim resolved from the embedder on first use."""
    from .models import embedding_dim
    from .storage import Storage

    return Storage(CONFIG.db_path, embedding_dim=embedding_dim())


# --- tool schemas ------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="index_video",
        description="Extract keyframes, caption them, transcribe audio, embed, and store in the index.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to a video file."},
                "fps": {"type": "number", "default": 0.5, "description": "Fallback sampling rate when scene detection finds no cuts."},
                "asr_language": {
                    "type": ["string", "null"],
                    "default": None,
                    "description": "ISO 639-1 code (e.g. 'en','zh','ja'). None = auto-detect.",
                },
                "asr_model": {
                    "type": ["string", "null"],
                    "default": None,
                    "description": "Whisper size: tiny|base|small|medium|large-v3. None = config default.",
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="list_supported_languages",
        description="List the curated top-30 ASR language codes accepted by index_video's asr_language.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="search_video",
        description="Semantic search over indexed frame captions and transcript segments.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "video_id": {"type": ["string", "null"], "default": None},
                "top_k": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_clip_context",
        description="Captions and transcript segments inside [start, end] for one video.",
        inputSchema={
            "type": "object",
            "properties": {
                "video_id": {"type": "string"},
                "start": {"type": "number"},
                "end": {"type": "number"},
            },
            "required": ["video_id", "start", "end"],
        },
    ),
    Tool(
        name="list_videos",
        description="List all indexed videos with metadata.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="summarize_video",
        description=(
            "Return all captions + the full transcript for a video, plus a "
            "style instruction the caller LLM should follow when summarizing. "
            "Use list_styles to discover available presets."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "video_id": {"type": "string"},
                "style": {
                    "type": "string",
                    "default": "default",
                    "description": "Output style preset name (see list_styles).",
                },
            },
            "required": ["video_id"],
        },
    ),
    Tool(
        name="list_styles",
        description="List available output style presets for summarize_video.",
        inputSchema={"type": "object", "properties": {}},
    ),
]


# --- prompts -----------------------------------------------------------------
# One MCP prompt per non-default style; surfaced as slash-commands in clients.

_PROMPT_STYLES = {
    "blog-from-video": "blog",
    "release-notes-from-video": "release_notes",
    "tutorial-from-video": "tutorial",
    "tweet-thread-from-video": "tweet_thread",
    "clean-transcript": "transcript_clean",
    "key-moments": "key_moments",
}


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    return [
        Prompt(
            name=name,
            description=f"{STYLES[style]['description']} Calls summarize_video with style={style!r}.",
            arguments=[
                PromptArgument(
                    name="video_id",
                    description="ID of an indexed video (see list_videos).",
                    required=True,
                ),
            ],
        )
        for name, style in _PROMPT_STYLES.items()
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
    if name not in _PROMPT_STYLES:
        raise ValueError(f"unknown prompt: {name}")
    args = arguments or {}
    video_id = args.get("video_id")
    if not video_id:
        raise ValueError("missing required argument: video_id")
    style = _PROMPT_STYLES[name]
    text = (
        f"Call the `summarize_video` tool with video_id={video_id!r} and "
        f"style={style!r}. Then format the response strictly per the "
        f"`style_instruction` field returned by the tool. Do not deviate "
        f"from that format."
    )
    return GetPromptResult(
        description=STYLES[style]["description"],
        messages=[
            PromptMessage(role="user", content=TextContent(type="text", text=text)),
        ],
    )


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


def _text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


# --- tool handlers (lazy heavy imports) --------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "index_video":
        from .indexer import index_video

        result = await index_video(
            path=arguments["path"],
            fps=float(arguments.get("fps", 0.5)),
            storage=_storage(),
            asr_language=arguments.get("asr_language"),
            asr_model=arguments.get("asr_model"),
        )
        return _text(result)

    if name == "list_supported_languages":
        from .languages import list_supported_languages

        return _text(list_supported_languages())

    if name == "search_video":
        from .models import embed_texts

        query = arguments["query"]
        emb = embed_texts([query])[0]
        hits = await asyncio.to_thread(
            _storage().search,
            emb,
            int(arguments.get("top_k", 10)),
            arguments.get("video_id"),
        )
        return _text([
            {
                "video_id": h.video_id,
                "timestamp": h.t_start,
                "kind": h.kind,
                "text": h.text,
                "score": h.score,
            }
            for h in hits
        ])

    if name == "get_clip_context":
        segs = await asyncio.to_thread(
            _storage().segments_in_window,
            arguments["video_id"],
            float(arguments["start"]),
            float(arguments["end"]),
        )
        return _text([
            {"kind": s.kind, "t_start": s.t_start, "t_end": s.t_end, "text": s.text}
            for s in segs
        ])

    if name == "list_videos":
        videos = await asyncio.to_thread(_storage().list_videos)
        return _text(videos)

    if name == "summarize_video":
        video_id = arguments["video_id"]
        style = arguments.get("style", "default")
        instruction = get_instruction(style)  # raises ValueError on unknown
        storage = _storage()
        segs = await asyncio.to_thread(storage.all_segments, video_id)
        captions = [
            {"timestamp": s.t_start, "caption": s.text}
            for s in segs if s.kind == "caption"
        ]
        transcript_text = " ".join(
            s.text for s in segs if s.kind == "transcript"
        ).strip()
        duration = next(
            (v["duration"] for v in storage.list_videos() if v["video_id"] == video_id),
            None,
        )
        return _text({
            "video_id": video_id,
            "duration": duration,
            "captions": captions,
            "transcript": transcript_text,
            "style": style,
            "style_instruction": instruction,
        })

    if name == "list_styles":
        return _text(list_styles())

    raise ValueError(f"unknown tool: {name}")


async def _run() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
