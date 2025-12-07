"""
Audio synthesis using OpenAI TTS and pydub for mixing.
Generates podcast audio from dialogue text.
"""

import os
import tempfile
import time
from pathlib import Path
from typing import List, Tuple
from openai import OpenAI
from pydub import AudioSegment

from .logger import get_logger

try:
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# Default voices for hosts
DEFAULT_VOICES = {
    'HOST1': 'nova',
    'HOST2': 'echo'
}


def parse_dialogue(dialogue_text: str) -> List[Tuple[str, str]]:
    """
    Parse dialogue text into (speaker, text) segments.
    Handles both plain (HOST1:) and markdown-formatted (**HOST1:**) labels.

    Args:
        dialogue_text: Formatted dialogue with HOST1:/HOST2: labels

    Returns:
        List of (speaker, text) tuples
    """
    segments = []
    current_speaker = None
    current_text = []

    for line in dialogue_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Strip markdown bold formatting if present (GPT-4 sometimes adds this)
        # **HOST1:** -> HOST1:
        cleaned_line = line.replace('**HOST1:**', 'HOST1:').replace('**HOST2:**', 'HOST2:')

        # Check if line starts with a speaker label
        if cleaned_line.startswith('HOST1:'):
            if current_speaker and current_text:
                segments.append((current_speaker, ' '.join(current_text)))
            current_speaker = 'HOST1'
            # Extract text after label (handle both formats)
            text_start = cleaned_line.find(':') + 1
            current_text = [cleaned_line[text_start:].strip()]
        elif cleaned_line.startswith('HOST2:'):
            if current_speaker and current_text:
                segments.append((current_speaker, ' '.join(current_text)))
            current_speaker = 'HOST2'
            # Extract text after label (handle both formats)
            text_start = cleaned_line.find(':') + 1
            current_text = [cleaned_line[text_start:].strip()]
        else:
            # Continuation of previous speaker
            if current_text:
                current_text.append(line)

    # Add final segment
    if current_speaker and current_text:
        segments.append((current_speaker, ' '.join(current_text)))

    return segments


def generate_speech(text: str, voice: str, model: str = "tts-1-hd") -> AudioSegment:
    """
    Generate speech audio from text using OpenAI TTS.

    Args:
        text: The text to convert to speech
        voice: OpenAI voice name (nova, echo, alloy, fable, onyx, shimmer)
        model: TTS model to use (default: tts-1-hd for higher quality)

    Returns:
        AudioSegment containing the generated speech
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)

    # Generate speech via OpenAI TTS
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text
    )

    # Save to temporary file and load as AudioSegment
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
        temp_path = temp_file.name
        response.stream_to_file(temp_path)

    audio = AudioSegment.from_mp3(temp_path)
    os.unlink(temp_path)  # Clean up temp file

    # Convert mono to stereo if needed (fixes single-ear playback issue)
    if audio.channels == 1:
        audio = audio.set_channels(2)

    return audio


def apply_spatial_audio(audio: AudioSegment, position: float) -> AudioSegment:
    """
    Apply spatial audio effects using both panning and interaural time difference (ITD).

    Args:
        audio: Stereo AudioSegment to process
        position: Spatial position from -1 (left) to +1 (right)

    Returns:
        AudioSegment with spatial effects applied
    """
    # Apply volume-based panning first
    audio = audio.pan(position)

    # Calculate ITD delay based on position
    # Human ITD is ~0.7ms max at 90 degrees, we'll use similar values
    max_itd_ms = 0.6  # milliseconds
    itd_delay_ms = abs(position) * max_itd_ms

    if abs(itd_delay_ms) < 0.01:  # Skip if delay is negligible
        return audio

    # Split into left and right channels
    channels = audio.split_to_mono()
    if len(channels) != 2:
        return audio  # Return unchanged if not stereo

    left, right = channels

    # Apply ITD: delay the channel opposite to the position
    if position < 0:  # Sound from left, delay right ear
        delay = AudioSegment.silent(duration=int(itd_delay_ms))
        right = delay + right
        # Trim left to match length
        left = left + AudioSegment.silent(duration=int(itd_delay_ms))
    elif position > 0:  # Sound from right, delay left ear
        delay = AudioSegment.silent(duration=int(itd_delay_ms))
        left = delay + left
        # Trim right to match length
        right = right + AudioSegment.silent(duration=int(itd_delay_ms))

    # Recombine channels
    return AudioSegment.from_mono_audiosegments(left, right)


def mix_audio_segments(
    segments: List[Tuple[str, str]],
    host1_voice: str = DEFAULT_VOICES['HOST1'],
    host2_voice: str = DEFAULT_VOICES['HOST2'],
    pause_ms: int = 300,
    spatial_separation: float = 0.4,
    verbosity: int = 2
) -> Tuple[AudioSegment, List[Tuple[str, str, int, int]]]:
    """
    Generate and mix audio segments with pauses between speakers.
    Applies spatial audio with panning and interaural time difference (ITD).

    Args:
        segments: List of (speaker, text) tuples
        host1_voice: Voice for HOST1
        host2_voice: Voice for HOST2
        pause_ms: Milliseconds of silence between segments
        spatial_separation: Spatial separation amount 0.0-1.0 (default: 0.4)
                           Controls both panning and ITD for realistic spatial effect
        verbosity: Logging verbosity level (0=silent, 1=minimal, 2=normal)

    Returns:
        Tuple of (combined AudioSegment, timing data)
        Timing data is list of (speaker, text, start_ms, end_ms)
    """
    voices = {
        'HOST1': host1_voice,
        'HOST2': host2_voice
    }

    # Spatial positions: negative = left, positive = right
    positions = {
        'HOST1': -spatial_separation,  # Left
        'HOST2': spatial_separation     # Right
    }

    logger = get_logger()
    combined = AudioSegment.empty()
    pause = AudioSegment.silent(duration=pause_ms)
    timing_data = []

    total_segments = len(segments)
    current_time_ms = 0
    start_time = time.time()

    if RICH_AVAILABLE and verbosity >= 2:
        # Rich progress display with metrics (only at verbosity >= 2)
        console = Console(force_terminal=True)
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                f"Generating audio (spatial: {spatial_separation})",
                total=total_segments
            )

            for i, (speaker, text) in enumerate(segments, 1):
                # Calculate max preview length to fit terminal width
                # Account for: counter(~12) + speaker(7) + colon(2) + ellipsis(3) + progress bar(~50)
                terminal_width = console.width
                fixed_text_width = 74  # Approximate space for progress bar + fixed text
                max_preview = max(20, terminal_width - fixed_text_width)

                preview = text[:max_preview] + "..." if len(text) > max_preview else text
                progress.update(
                    task,
                    description=f"[{i}/{total_segments}] {speaker}: {preview}",
                    completed=i-1
                )

                voice = voices.get(speaker, host1_voice)
                audio = generate_speech(text, voice)

                # Apply spatial audio (panning + ITD)
                position = positions.get(speaker, 0)
                audio = apply_spatial_audio(audio, position)

                # Record timing for this segment
                start_ms = current_time_ms
                end_ms = start_ms + len(audio)
                timing_data.append((speaker, text, start_ms, end_ms))

                combined += audio
                current_time_ms = end_ms

                if i < total_segments:  # Add pause between segments
                    combined += pause
                    current_time_ms += pause_ms

                progress.update(task, completed=i)

    else:
        # Silent generation (no progress display)
        for i, (speaker, text) in enumerate(segments, 1):
            voice = voices.get(speaker, host1_voice)
            audio = generate_speech(text, voice)

            # Apply spatial audio (panning + ITD)
            position = positions.get(speaker, 0)
            audio = apply_spatial_audio(audio, position)

            # Record timing for this segment
            start_ms = current_time_ms
            end_ms = start_ms + len(audio)
            timing_data.append((speaker, text, start_ms, end_ms))

            combined += audio
            current_time_ms = end_ms

            if i < total_segments:  # Add pause between segments
                combined += pause
                current_time_ms += pause_ms

    return combined, timing_data


def generate_srt_with_whisper(audio_path: str, output_path: str, verbosity: int = 2) -> str:
    """
    Generate SRT subtitle file using OpenAI Whisper transcription.
    This produces properly timed, readable subtitles broken into natural chunks.

    Args:
        audio_path: Path to the audio file (MP3)
        output_path: Path to save the SRT file
        verbosity: Logging verbosity level (0=silent, 1=minimal, 2=normal)

    Returns:
        Path to the generated SRT file
    """
    logger = get_logger()
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.warning("OPENAI_API_KEY not found, skipping subtitle generation")
        return ""

    try:
        client = OpenAI(api_key=api_key)

        # Get file size for display
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)

        if RICH_AVAILABLE and verbosity >= 2:
            console = Console(force_terminal=True)
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}"),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task(
                    f"Transcribing with Whisper ({file_size_mb:.1f} MB)...",
                    total=None
                )

                # Open audio file for transcription
                with open(audio_path, 'rb') as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="srt"
                    )

                progress.update(task, completed=True)
        else:
            # Silent transcription (no progress)
            with open(audio_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="srt"
                )

        # Write SRT content to file
        srt_path = Path(output_path)
        srt_path.write_text(transcript, encoding='utf-8')

        return str(srt_path)

    except Exception as e:
        logger.warning(f"Failed to generate subtitles with Whisper: {e}")
        return ""


def export_podcast(audio: AudioSegment, output_path: str, verbosity: int = 2) -> str:
    """
    Export audio as MP3 file.

    Args:
        audio: AudioSegment to export
        output_path: Path to save the MP3 file
        verbosity: Logging verbosity level (0=silent, 1=minimal, 2=normal)

    Returns:
        Path to the exported file
    """
    logger = get_logger()

    # Ensure output directory exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Exporting podcast to: {output_path}")

    audio.export(
        str(output_path),
        format="mp3",
        bitrate="192k",
        tags={
            'artist': 'Podcast AI',
            'album': 'Generated Podcast',
            'genre': 'Educational'
        }
    )

    duration_seconds = len(audio) / 1000
    duration_mins = int(duration_seconds // 60)
    duration_secs = int(duration_seconds % 60)

    logger.info(f"Podcast created: {duration_mins}m {duration_secs}s")

    return str(output_path)


def generate_podcast_audio(
    dialogue_text: str,
    output_path: str,
    host1_voice: str = DEFAULT_VOICES['HOST1'],
    host2_voice: str = DEFAULT_VOICES['HOST2'],
    spatial_separation: float = 0.4,
    verbosity: int = 2
) -> str:
    """
    Main function to generate podcast audio from dialogue.
    Also generates an SRT subtitle file for accessibility.

    Args:
        dialogue_text: Formatted dialogue text
        output_path: Path to save the MP3 file
        host1_voice: Voice for HOST1
        host2_voice: Voice for HOST2
        spatial_separation: Spatial separation 0.0-1.0 (controls panning + ITD)
        verbosity: Logging verbosity level (0=silent, 1=minimal, 2=normal)

    Returns:
        Path to the generated podcast file
    """
    logger = get_logger()
    segments = parse_dialogue(dialogue_text)
    logger.info(f"Parsed {len(segments)} dialogue segments")

    # Generate audio with timing data
    audio, timing_data = mix_audio_segments(
        segments, host1_voice, host2_voice,
        spatial_separation=spatial_separation,
        verbosity=verbosity
    )

    # Export MP3
    mp3_path = export_podcast(audio, output_path, verbosity=verbosity)

    # Generate SRT subtitle file using Whisper
    srt_path = Path(output_path).with_suffix('.srt')
    generated_srt = generate_srt_with_whisper(mp3_path, str(srt_path), verbosity=verbosity)
    if generated_srt:
        logger.info(f"Generated subtitles: {srt_path}")

    return mp3_path
