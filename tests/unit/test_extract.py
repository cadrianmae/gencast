from pathlib import Path
import pytest
from gencast.pipeline.extract import extract_sources, count_tokens


def test_extract_single_markdown(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("# Title\n\nSome content.")
    text, tokens = extract_sources([str(p)], model="gpt-4o-mini")
    assert "Title" in text
    assert "Some content" in text
    assert tokens > 0


def test_extract_multiple_files_concatenated(tmp_path):
    p1 = tmp_path / "a.md"
    p2 = tmp_path / "b.md"
    p1.write_text("First file content.")
    p2.write_text("Second file content.")
    text, _ = extract_sources([str(p1), str(p2)], model="gpt-4o-mini")
    assert "First file content" in text
    assert "Second file content" in text
    assert "---" in text


def test_extract_text_file(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("Plain text notes.")
    text, _ = extract_sources([str(p)], model="gpt-4o-mini")
    assert "Plain text notes" in text


def test_extract_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_sources([str(tmp_path / "nonexistent.md")], model="gpt-4o-mini")


def test_extract_unsupported_format_raises(tmp_path):
    p = tmp_path / "audio.mp3"
    p.write_bytes(b"\x00\x00\x00")
    with pytest.raises(ValueError, match="unsupported"):
        extract_sources([str(p)], model="gpt-4o-mini")


def test_count_tokens():
    n = count_tokens("hello world", model="gpt-4o-mini")
    assert n >= 2


def test_extract_token_count_matches_text():
    text = "The quick brown fox jumps over the lazy dog."
    n = count_tokens(text, model="gpt-4o-mini")
    assert n > 5
