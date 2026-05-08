"""Packaging stage — write requested formats. M4A via ffmpeg with mov_text subs."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from gencast.pipeline.io import (
    write_cost_json,
    write_outline_json,
    write_transcript_json,
)
from gencast.pipeline.subtitles import build_native_srt, srt_format

if TYPE_CHECKING:
    from gencast.pipeline import PodcastState


_FFMPEG = shutil.which("ffmpeg")


def write_outputs(state: "PodcastState") -> dict[str, Path]:
    """Write every format listed in state.notebook.output.formats. Returns paths by format key."""
    out_dir = state.notebook.output.dir
    out_dir.mkdir(parents=True, exist_ok=True)
    base = state.resolved.basename
    formats = set(state.notebook.output.formats)
    written: dict[str, Path] = {}

    needs_mp3 = "m4a" in formats or "mp3" in formats
    needs_srt = "m4a" in formats or "mp3" in formats

    mp3_path = out_dir / f"{base}.mp3"
    srt_path = out_dir / f"{base}.srt"

    if needs_mp3:
        assert state.combined_audio is not None, "combined_audio must be populated"
        state.combined_audio.export(str(mp3_path), format="mp3", bitrate="192k")

    if needs_srt:
        entries = build_native_srt(state.clips, include_speaker=True)
        srt_path.write_text(srt_format(entries))

    if "m4a" in formats:
        m4a_path = out_dir / f"{base}.m4a"
        try:
            _mux_m4a(mp3_path, srt_path, m4a_path)
            written["m4a"] = m4a_path
        except RuntimeError as e:
            print(
                f"[warn] m4a mux failed ({e}); kept mp3+srt sidecars at {mp3_path}.",
                file=sys.stderr,
            )

    if "mp3" in formats:
        written["mp3"] = mp3_path
        written["srt"] = srt_path
    elif "m4a" in formats and "m4a" in written:
        # M4A succeeded; mp3+srt were intermediates → remove unless explicitly requested
        mp3_path.unlink(missing_ok=True)
        srt_path.unlink(missing_ok=True)

    if "transcript" in formats:
        p = out_dir / f"{base}.transcript.json"
        write_transcript_json(state, p)
        written["transcript"] = p

    if "outline" in formats:
        p = out_dir / f"{base}.outline.json"
        write_outline_json(state, p)
        written["outline"] = p

    if "cost" in formats:
        p = out_dir / f"{base}.cost.json"
        write_cost_json(state, p)
        written["cost"] = p

    return written


def _mux_m4a(mp3_path: Path, srt_path: Path, out_path: Path) -> None:
    """Use ffmpeg to mux mp3 + srt → m4a with mov_text embedded subs."""
    if _FFMPEG is None:
        raise RuntimeError("ffmpeg not found on PATH")
    cmd = [
        _FFMPEG, "-y",
        "-i", str(mp3_path),
        "-i", str(srt_path),
        "-map", "0:a", "-map", "1:s",
        "-c:a", "aac", "-b:a", "192k",
        "-c:s", "mov_text",
        "-metadata:s:s:0", "language=eng",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {proc.returncode}): {proc.stderr.decode()[-400:]}"
        )
