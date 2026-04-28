"""Style preset registry tests."""
from __future__ import annotations

import pytest

from dc_video_mcp.styles import STYLES, get_instruction, list_styles

EXPECTED = {
    "default",
    "blog",
    "release_notes",
    "tutorial",
    "tweet_thread",
    "transcript_clean",
    "key_moments",
}


def test_list_styles_returns_expected_names():
    names = {s["name"] for s in list_styles()}
    assert names == EXPECTED


def test_list_styles_entries_have_descriptions():
    for entry in list_styles():
        assert entry["description"], f"{entry['name']} missing description"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_each_preset_has_non_empty_instruction(name):
    instr = get_instruction(name)
    assert isinstance(instr, str)
    assert len(instr.strip()) > 50, f"{name} instruction too short"


def test_unknown_style_raises_value_error():
    with pytest.raises(ValueError) as exc:
        get_instruction("does_not_exist")
    msg = str(exc.value)
    # Error message should list available styles for discoverability.
    for name in EXPECTED:
        assert name in msg


def test_styles_dict_keys_match_list_styles():
    assert set(STYLES.keys()) == EXPECTED
