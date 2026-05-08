"""Chunked Whisper STT for re-subtitling externally provided audio.

Lifted from v0.6.x src/audio.py (commit 3934c69 on main).
Whisper API has a 25 MB upload cap; we split large inputs into 10-minute chunks
then merge the resulting SRTs with adjusted timestamps.
"""

from __future__ import annotations

import os
import tempfile
from datetime import timedelta
from pathlib import Path

import srt
from openai import OpenAI
from pydub import AudioSegment

WHISPER_MAX_BYTES = 24 * 1024 * 1024  # 24 MB safety margin under 25 MB API limit
CHUNK_DURATION_MS = 10 * 60 * 1000     # 10 minutes


def chunk_audio_for_whisper(audio_path: Path) -> tuple[list[Path], list[int]]:
    """Split mp3 into ≤25 MB chunks. Returns (chunk_paths, durations_ms)."""
    file_size = audio_path.stat().st_size
    if file_size <= WHISPER_MAX_BYTES:
        audio = AudioSegment.from_mp3(str(audio_path))
        return [audio_path], [len(audio)]

    audio = AudioSegment.from_mp3(str(audio_path))
    chunk_paths: list[Path] = []
    chunk_durations: list[int] = []
    for i in range(0, len(audio), CHUNK_DURATION_MS):
        chunk = audio[i : i + CHUNK_DURATION_MS]
        chunk_durations.append(len(chunk))
        with tempfile.NamedTemporaryFile(
            suffix=f"_chunk{len(chunk_paths)}.mp3", delete=False,
        ) as f:
            tmp = Path(f.name)
        chunk.export(str(tmp), format="mp3", bitrate="192k")
        chunk_paths.append(tmp)
    return chunk_paths, chunk_durations


def combine_srt_chunks(srt_contents: list[str], chunk_durations_ms: list[int]) -> str:
    """Merge SRT chunks with re-offset timestamps. Re-indexes globally."""
    all_subs = []
    time_offset_ms = 0
    for chunk_idx, content in enumerate(srt_contents):
        subs = list(srt.parse(content))
        offset = timedelta(milliseconds=time_offset_ms)
        for sub in subs:
            sub.start += offset
            sub.end += offset
            all_subs.append(sub)
        time_offset_ms += chunk_durations_ms[chunk_idx]
    for i, sub in enumerate(all_subs, start=1):
        sub.index = i
    return srt.compose(all_subs)


def transcribe_to_srt(audio_path: Path, *, openai_api_key: str | None = None) -> str:
    """End-to-end: chunk if needed, transcribe each chunk, merge into one SRT."""
    client = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
    chunk_paths, durations = chunk_audio_for_whisper(audio_path)

    srts: list[str] = []
    try:
        for cp in chunk_paths:
            with cp.open("rb") as f:
                content = client.audio.transcriptions.create(
                    model="whisper-1", file=f, response_format="srt",
                )
            srts.append(content if isinstance(content, str) else str(content))
    finally:
        # Cleanup chunk temp files (but not the original audio path)
        for cp in chunk_paths:
            if cp != audio_path:
                cp.unlink(missing_ok=True)

    if len(srts) == 1:
        return srts[0]
    return combine_srt_chunks(srts, durations)
