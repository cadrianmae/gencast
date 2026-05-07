"""Audio stage — TTS dispatch, sentence-level clips, concat with timing.

Plan B Task 10 ships without spatial FX. Plan B Task 15 wires audio_fx/ in.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydub import AudioSegment

from gencast.tts import TTSBackend, get_backend, split_sentences
from gencast.tts.cache import TTSDiskCache, default_cache_dir

if TYPE_CHECKING:
    from gencast.pipeline import PodcastState

INTER_TURN_PAUSE_MS = 300


@dataclass
class AudioClip:
    """One sentence of TTS output, positioned in the final timeline."""
    start_ms: int
    end_ms: int
    speaker_index: int
    speaker_name: str
    sentence_text: str
    segment_index: int
    audio: AudioSegment


async def _synthesize_one(
    *, backend: TTSBackend, voice: str, text: str, cache: TTSDiskCache,
    semaphore: asyncio.Semaphore,
) -> tuple[AudioSegment, float, bool]:
    """Returns (audio_seg, audio_seconds, was_cache_hit)."""
    cached = cache.get(
        provider=backend.backend_name, model=backend.model, voice=voice, text=text,
    )
    if cached is not None:
        seg = AudioSegment.from_file(io.BytesIO(cached), format="mp3")
        return seg, len(seg) / 1000.0, True

    async with semaphore:
        audio_bytes, seconds = await backend.synthesize(voice=voice, text=text)
    cache.put(
        provider=backend.backend_name, model=backend.model, voice=voice, text=text,
        audio_bytes=audio_bytes,
    )
    seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    return seg, seconds, False


async def run_audio_stage(
    state: "PodcastState",
    *,
    backend: TTSBackend | None = None,
    cache_dir: Path | None = None,
    concurrency: int = 5,
) -> None:
    """Populate state.clips and state.combined_audio. No spatial FX in Plan B Task 10."""
    assert state.transcript is not None, "transcript must be populated"
    sp = state.resolved.speaker
    if backend is None:
        backend = get_backend(sp.tts_provider, sp.tts_model, **(sp.tts_config or {}))
    cache = TTSDiskCache(cache_dir or default_cache_dir())

    # Map speaker name -> (index, voice)
    speaker_lookup = {s.name: (i, s.voice_id) for i, s in enumerate(sp.speakers)}

    # Build the synthesis job list (one per sentence)
    jobs: list[tuple[int, int, str, str, int, str, str]] = []
    # tuple = (turn_index, sentence_index_within_turn, speaker_name, sentence_text, segment_index, voice, _)
    for turn_index, turn in enumerate(state.transcript.turns):
        if turn.speaker not in speaker_lookup:
            raise ValueError(
                f"Turn {turn_index}: unknown speaker {turn.speaker!r}; "
                f"valid: {list(speaker_lookup)}"
            )
        spk_idx, voice = speaker_lookup[turn.speaker]
        seg_idx = turn.segment_index if turn.segment_index is not None else 0
        for s_idx, sentence in enumerate(split_sentences(turn.text)):
            jobs.append((turn_index, s_idx, turn.speaker, sentence, seg_idx, voice, ""))

    # Synthesize concurrently
    semaphore = asyncio.Semaphore(concurrency)

    async def _do(j):
        _, _, _, sentence, _, voice, _ = j
        return await _synthesize_one(
            backend=backend, voice=voice, text=sentence,
            cache=cache, semaphore=semaphore,
        )

    results = await asyncio.gather(*(_do(j) for j in jobs))

    # Stitch clips with timing + record cost for non-cached
    clips: list[AudioClip] = []
    cursor_ms = 0
    last_turn_index = -1
    combined = AudioSegment.empty()

    for j, (audio, seconds, hit) in zip(jobs, results):
        turn_index, s_idx, speaker_name, sentence_text, seg_idx, voice, _ = j
        spk_idx = speaker_lookup[speaker_name][0]

        if last_turn_index != -1 and turn_index != last_turn_index:
            cursor_ms += INTER_TURN_PAUSE_MS
            combined += AudioSegment.silent(
                duration=INTER_TURN_PAUSE_MS, frame_rate=audio.frame_rate
            ).set_channels(audio.channels)

        start = cursor_ms
        end = cursor_ms + len(audio)
        clips.append(AudioClip(
            start_ms=start, end_ms=end,
            speaker_index=spk_idx, speaker_name=speaker_name,
            sentence_text=sentence_text, segment_index=seg_idx,
            audio=audio,
        ))
        combined += audio
        cursor_ms = end
        last_turn_index = turn_index

        if not hit:
            usd = seconds * backend.usd_per_audio_second
            state.cost.record_tts(
                "tts",
                backend=backend.backend_name,
                model=backend.model,
                audio_seconds=seconds,
                usd=usd,
            )

    state.clips = clips
    state.combined_audio = combined
