"""Output style presets for summarize_video.

Each preset is an instruction string returned to the caller LLM (e.g. Claude)
so it formats the captions + transcript however the user asked. No LLM calls
happen server-side; we just hand back the prompt fragment.
"""
from __future__ import annotations

STYLES: dict[str, dict[str, str]] = {
    "default": {
        "description": "Neutral 3-5 paragraph summary.",
        "instruction": (
            "Write a neutral, factual summary of the video using the captions "
            "and transcript provided. Aim for 3-5 short paragraphs. Cover the "
            "main subject, what happens, and any notable details. Do not "
            "invent content that is not supported by the captions or "
            "transcript."
        ),
    },
    "blog": {
        "description": "Engaging blog post (500-800 words) with title, intro, sections, conclusion.",
        "instruction": (
            "Write an engaging blog post (500-800 words) based on the video. "
            "Structure:\n"
            "  # <Compelling title>\n"
            "  <1-2 paragraph intro that hooks the reader>\n"
            "  ## <Section header>\n"
            "  <Body paragraphs>\n"
            "  ## <Section header>\n"
            "  <Body paragraphs>\n"
            "  ## Conclusion\n"
            "  <Wrap-up + takeaway>\n"
            "Use Markdown. Tone: knowledgeable but conversational. Anchor "
            "claims in the captions/transcript; do not fabricate."
        ),
    },
    "release_notes": {
        "description": "Terse bullet changelog grouped into New / Changed / Fixed.",
        "instruction": (
            "Produce release notes as a Markdown bullet changelog. Group "
            "items under exactly these headers:\n"
            "  ## New\n"
            "  ## Changed\n"
            "  ## Fixed\n"
            "Each bullet is one short sentence in imperative mood (e.g. "
            "'Add support for X'). Omit a section if it has no items. Do not "
            "include marketing fluff or preamble."
        ),
    },
    "tutorial": {
        "description": "Step-by-step guide with prerequisites and expected outcome.",
        "instruction": (
            "Rewrite the video as a step-by-step tutorial. Structure:\n"
            "  # <Task title>\n"
            "  ## Prerequisites\n"
            "  - <bullet list of what the reader needs first>\n"
            "  ## Steps\n"
            "  1. <First action, with any commands or code in fenced blocks>\n"
            "  2. <Next action>\n"
            "  ...\n"
            "  ## Expected outcome\n"
            "  <What the reader should see when done>\n"
            "Keep steps small and verifiable. Use Markdown."
        ),
    },
    "tweet_thread": {
        "description": "5-8 tweet thread, hook first, each <280 chars, ends with CTA.",
        "instruction": (
            "Write a thread of 5-8 tweets summarizing the video. Rules:\n"
            "  - Tweet 1 is a hook that makes people want to read on.\n"
            "  - Each tweet is strictly under 280 characters.\n"
            "  - Number them as '1/', '2/', etc.\n"
            "  - Last tweet ends with a clear call to action (watch, share, "
            "subscribe, try, etc.).\n"
            "Output one tweet per line, blank line between tweets. No "
            "surrounding commentary."
        ),
    },
    "transcript_clean": {
        "description": "Cleaned transcript only (grammar fixed, fillers removed). No summary.",
        "instruction": (
            "Return ONLY a cleaned version of the transcript. Fix grammar "
            "and punctuation, remove filler words (um, uh, you know, like as "
            "filler), and merge fragmented sentences, but preserve the "
            "speaker's meaning and order. Do not summarize, do not add "
            "headers, do not include captions. Output the cleaned prose as "
            "plain paragraphs."
        ),
    },
    "key_moments": {
        "description": "Timestamped highlight list with short descriptions.",
        "instruction": (
            "List the key moments of the video as a timestamped highlight "
            "list. Format:\n"
            "  - [MM:SS] <one-line description of what happens>\n"
            "Use the timestamps from the captions/transcript, sorted "
            "ascending. Include 5-15 entries depending on video length. No "
            "preamble, no summary paragraph."
        ),
    },
}


def list_styles() -> list[dict]:
    """Available presets as [{name, description}]."""
    return [{"name": n, "description": s["description"]} for n, s in STYLES.items()]


def get_instruction(style: str) -> str:
    """Return instruction string for the named style. Raises ValueError on unknown."""
    if style not in STYLES:
        available = ", ".join(sorted(STYLES))
        raise ValueError(f"unknown style {style!r}; available: {available}")
    return STYLES[style]["instruction"]
