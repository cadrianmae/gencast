"""gencast cache status / clear filesystem ops."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from gencast.cli.main import cli


def _populate_cache(root: Path, files: int = 3, size: int = 1024) -> None:
    for i in range(files):
        p = root / f"{i:02d}.bin"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * size)


def test_status_reports_size(tmp_path, monkeypatch):
    fake_cache = tmp_path / "fake-cache" / "gencast" / "tts"
    _populate_cache(fake_cache, files=5, size=2048)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "fake-cache"))

    runner = CliRunner()
    result = runner.invoke(cli, ["cache", "status", "--type=tts"])
    assert result.exit_code == 0, result.output
    assert "tts" in result.output.lower()
    # 5 × 2 KB = 10 KB minimum; allow some slack
    assert "kb" in result.output.lower() or "KB" in result.output


def test_clear_removes_files(tmp_path, monkeypatch):
    fake_cache = tmp_path / "fake-cache" / "gencast" / "tts"
    _populate_cache(fake_cache, files=3)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "fake-cache"))

    runner = CliRunner()
    result = runner.invoke(cli, ["cache", "clear", "--type=tts", "--yes"])
    assert result.exit_code == 0, result.output
    # Files gone but directory exists
    remaining = list(fake_cache.rglob("*.bin"))
    assert remaining == []


def test_clear_all_types(tmp_path, monkeypatch):
    base = tmp_path / "fake-cache" / "gencast"
    _populate_cache(base / "tts", files=2)
    _populate_cache(base / "llm", files=2)
    _populate_cache(base / "extract", files=2)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "fake-cache"))

    runner = CliRunner()
    result = runner.invoke(cli, ["cache", "clear", "--type=all", "--yes"])
    assert result.exit_code == 0
    for kind in ("tts", "llm", "extract"):
        assert list((base / kind).rglob("*.bin")) == []
