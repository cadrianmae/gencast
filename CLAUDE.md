# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**gencast** is a Python CLI tool that generates conversational podcasts from documents using AI. It's a cost-effective, customizable alternative to NotebookLM, featuring multiple podcast styles, audience levels, spatial audio, and automatic subtitle generation.

**User Context**: Created for Mae Capacite, Year 4 Computer Science student at TU Dublin, for generating podcasts from lecture materials with neurodivergent-friendly features.

## Installation & Setup

```bash
# Environment setup
python3 -m venv venv
source venv/bin/activate
pip install -e .  # Editable install

# Required API keys
export OPENAI_API_KEY="sk-..."  # Required (for TTS and Whisper)
export ANTHROPIC_API_KEY="sk-ant-..."  # Optional (for Claude models)
export MISTRAL_API_KEY="..."  # Optional (for PDF processing)

# Command now available system-wide (when venv active)
gencast --help
```

**System-wide installation** (recommended for production use):
```bash
pipx install -e .  # Makes gencast available globally
```

## Common Commands

```bash
# Basic usage
gencast lecture.md

# Multiple files
gencast chapter1.md chapter2.md chapter3.md -o combined.mp3

# Podcast styles (educational, interview, casual, debate)
gencast doc.md --style interview --audience technical

# Voice customization (alloy, echo, fable, onyx, nova, shimmer)
gencast doc.md --host1-voice nova --host2-voice echo

# Spatial audio adjustment (0.0-1.0, default 0.4)
gencast doc.md --spatial-separation 0.6

# Save dialogue for review before audio generation
gencast doc.md --save-dialogue

# Multi-provider support (OpenAI, Anthropic, 100+ others)
gencast doc.md --model gpt-5-mini  # Default
gencast doc.md --model gpt-4o-mini
gencast doc.md --model anthropic/claude-sonnet-4.5

# Planning feature (comprehensive coverage)
gencast doc.md --with-planning --save-plan

# All options combined
gencast input.md -o output.mp3 \
  --model anthropic/claude-sonnet-4.5 \
  --style casual \
  --audience beginner \
  --host1-voice nova \
  --host2-voice echo \
  --spatial-separation 0.4 \
  --with-planning \
  --save-plan \
  --save-dialogue

# Verbosity control
gencast doc.md --minimal  # Minimal output
gencast doc.md --silent   # Silent mode (errors only)
```

## Architecture

```
gencast/
├── gencast.py             # Main CLI orchestration
├── __init__.py            # Package entry point
├── src/
│   ├── utils.py           # Document reading (MD, TXT, PDF)
│   ├── models.py          # Pydantic models for structured outputs
│   ├── dialogue.py        # Multi-provider dialogue (LiteLLM + Instructor)
│   ├── planning.py        # Podcast planning (LiteLLM + Instructor)
│   ├── audio.py           # TTS + spatial audio + Whisper (OpenAI)
│   └── logger.py          # Logging with verbosity levels
├── prompts/               # Podcast style and planning templates
│   ├── educational.txt    # Friendly hosts explaining concepts
│   ├── interview.txt      # HOST1=interviewer, HOST2=expert
│   ├── casual.txt         # Informal friends chatting
│   ├── debate.txt         # Two perspectives, contrasting views
│   └── planning.txt       # Podcast structure planning prompt
├── audiences/             # 4 audience modifier templates
│   ├── general.txt        # Clear, accessible language
│   ├── technical.txt      # Deep-dive with technical terms
│   ├── academic.txt       # Scholarly tone, theoretical depth
│   └── beginner.txt       # ELI5 style, lots of analogies
├── pyproject.toml         # Package config + CLI entry point + basedpyright
└── requirements.txt       # Dependencies
```

### Layer Separation (Critical Design Pattern)

**Data Layer** (`src/utils.py`):
- Pure I/O operations, returns raw text strings
- `extract_text(filepaths) -> str`: Concatenates multiple files
- PDF: Mistral AI for intelligent extraction → pypdf fallback

**Business Logic** (`src/dialogue.py`, `src/planning.py`, `src/audio.py`):
- Never prints (except progress indicators)
- Returns data structures, not side effects
- `generate_plan(text, model, audience, ...) -> Tuple[str, Dict]`
- `generate_dialogue(text, model, style, audience, plan, ...) -> Tuple[str, Dict]`
- `generate_podcast_audio(dialogue, output_path, ...) -> str`

**Interface** (`gencast.py`):
- CLI argument parsing, orchestration only
- User-facing messages and error handling
- Pipeline: extract → [planning] → dialogue → audio → subtitles

### Structured Output Models (`src/models.py`)

All AI-generated content uses Pydantic models for type-safe, validated outputs:

**Dialogue Models:**
- `DialogueSegment`: Single host utterance with speaker validation (HOST1/HOST2) and non-empty text
- `PodcastDialogue`: Complete dialogue with automatic validation (both hosts required)
  - `to_text_format() -> str`: Converts to HOST1:/HOST2: format for audio.py
  - `count_segments() -> Dict[str, int]`: Returns segment counts per speaker

**Planning Models:**
- `PlanTopic`: Single topic with title, key points, and estimated duration
- `PodcastPlan`: Complete plan with overview, topics, target audience, and duration
  - `to_markdown() -> str`: Converts to formatted markdown for display

**Why Instructor + Pydantic?**
- **Validation during generation**: Models validate as the AI generates, with automatic retries (max 3) on validation failures
- **No regex cleanup**: Replaced `validate_and_clean_dialogue()` (57 lines) - Pydantic handles format enforcement
- **Type safety**: IDE autocomplete and type checking throughout codebase
- **Streaming support**: `Partial[Model]` for incremental updates in live previews

**Token Usage Tracking:**
- Streaming mode: Token usage not available (instructor limitation)
- Non-streaming mode: `create_with_completion()` returns tuple of (response, raw_completion) with full usage data

**Token Allocation:**
- Planning: 1500-3000 tokens (50% of dialogue tokens, increased for JSON structure overhead)
- Dialogue: 2000-5000 tokens (based on input length, targets 17-20 min podcasts)

## Key Technical Details

### Prompt System (Composable Two-Layer Design)

**Style prompts** define conversation structure:
- Loaded from `prompts/{style}.txt`
- Controls how hosts interact (educational, interview, casual, debate)

**Audience modifiers** adjust complexity:
- Loaded from `audiences/{audience}.txt`
- Appended to style prompt: `full_prompt = style + audience_modifier`

**Loading strategy**:
```python
# Relative to dialogue.py location
prompt_path = Path(__file__).parent.parent / "prompts" / f"{style}.txt"
```

**Fallback**: Hardcoded educational prompt if file not found

### Dialogue Generation with Streaming

```python
# Multi-provider streaming via LiteLLM
from litellm import completion

request_params = {
    "model": "gpt-5-mini",  # Or "anthropic/claude-sonnet-4.5", etc.
    "messages": [{"role": "system", "content": full_prompt}, ...],
    "stream": True,  # Enables live preview
    "api_key": api_key
}
# Only add max_tokens if limited (None = unlimited)
if max_tokens is not None:
    request_params["max_tokens"] = max_tokens

stream = completion(**request_params)
```

**Multi-Provider Support**:
- Supports 100+ AI providers via LiteLLM
- OpenAI: `gpt-5-mini`, `gpt-4o`, `gpt-4o-mini`
- Anthropic: `anthropic/claude-sonnet-4.5`, `anthropic/claude-opus-4.5`
- See [LiteLLM providers](https://docs.litellm.ai/docs/providers) for full list

**Output format**:
```
HOST1: [dialogue text]
HOST2: [dialogue text]
HOST1: [continuing...]
```

### Spatial Audio Implementation

**Two-technique approach** for realistic positioning:

1. **Panning** (volume-based):
   ```python
   audio.pan(position)  # -1 (left) to +1 (right)
   ```

2. **ITD - Interaural Time Difference** (timing-based):
   ```python
   # Add 0-0.6ms delay to ear opposite sound source
   max_itd_ms = 0.6
   itd_delay_ms = abs(position) * max_itd_ms
   ```

**Default positioning**:
- HOST1: -0.4 (slightly left)
- HOST2: +0.4 (slightly right)
- Recommended range: 0.3-0.6

**Audio pipeline**:
1. Parse dialogue → `(speaker, text)` tuples
2. Generate TTS for each segment (OpenAI `tts-1-hd`)
3. Convert mono → stereo (fixes single-ear playback)
4. Apply spatial audio (panning + ITD)
5. Concatenate with 300ms pauses
6. Export MP3 (192kbps)

### Subtitle Generation (Whisper)

```python
# After audio export, transcribe with Whisper
transcript = client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_file,
    response_format="srt"  # Returns properly formatted SRT
)
```

**Result**: Readable chunks (1-3 seconds), not walls of text

**VLC viewing**: Enable Audio → Visualizations → Spectrometer to see subtitles

### Rich Progress Indicators (Optional Dependency)

**Pattern throughout codebase**:
```python
try:
    from rich import ...
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Later in code
if RICH_AVAILABLE:
    # Rich progress bars, live displays
else:
    # Simple print() fallback
```

**Features when available**:
- Live streaming preview of dialogue generation
- Progress bar with segment preview during audio synthesis
- Time estimates (elapsed + remaining)
- Professional UX without breaking when absent

**Terminal Width Handling**:
- Dynamically truncates text to fit terminal width (prevents line wrapping)
- Audio generation: `max_preview = max(20, terminal_width - 74)`
- Dialogue streaming: `max_line_length = max(20, console.width - len(prefix) - 5)`
- Uses `Console(force_terminal=True)` for consistent display
- No emojis in progress displays to avoid width calculation issues

## API Usage & Costs

### Hybrid Architecture

**LiteLLM** (chat completions):
- `dialogue.py` and `planning.py` use LiteLLM for multi-provider support
- Supports OpenAI, Anthropic, and 100+ other providers
- Preserves streaming UX for neurodivergent-friendly progress feedback

**OpenAI SDK** (audio processing):
- `audio.py` uses OpenAI SDK for TTS and Whisper
- These APIs are not yet supported by LiteLLM

### Cost Estimates (3-minute podcast, ~1500 words)

| API | Purpose | Model | Cost |
|-----|---------|-------|------|
| **Dialogue/Planning** (flexible) | Chat completions | `gpt-5-mini` (default) | ~$0.02-0.05 |
| | | `gpt-4o-mini` | ~$0.02-0.05 |
| | | `anthropic/claude-sonnet-4.5` | ~$0.15-0.30 |
| **Audio** (OpenAI only) | TTS | `tts-1-hd` | ~$0.06-0.10 |
| | Subtitles | `whisper-1` | ~$0.01 |
| **PDF** (optional) | Extraction | `mistral-large-latest` | ~$0.01 |

**Total**: ~$0.10-0.17 per podcast (with GPT-5-mini/GPT-4o-mini)
**Total**: ~$0.23-0.41 per podcast (with Claude Sonnet 4.5)

## Testing Strategy

**Current approach** (cost-effective manual testing):
1. Use `test_input.md` with 1-2 paragraphs
2. Test each component: document → dialogue → audio
3. Then test with full materials

**Test document creation tip**:
```bash
gencast test_input.md --save-dialogue  # Review dialogue before audio
```

## Error Handling Patterns

**API Key Validation**:
- Checks on startup with clear setup instructions
- Mistral key optional (only for PDFs)

**Graceful Degradation**:
- PDF processing: Mistral AI → pypdf fallback
- Progress display: Rich → simple print fallback
- SRT generation: Continues if Whisper fails

**File Validation**:
- Checks existence before processing
- Clear error messages per file
- Continues processing remaining files in multi-file mode

## Non-Obvious Implementation Details

### 1. Mono to Stereo Conversion
```python
# Fixes single-ear playback on some devices
if audio.channels == 1:
    audio = audio.set_channels(2)
```

### 2. ITD Implementation
- Delays the ear *opposite* to the sound source
- Pads both channels to same length to avoid drift
- Mimics natural head-related transfer function (HRTF)

### 3. Dialogue Parsing Edge Cases
- Multi-line speaker segments (continuation lines without labels)
- Joins continuation lines with spaces
- Skips empty lines
- Captures final segment after loop ends
- Handles markdown-formatted labels: GPT-4 sometimes outputs `**HOST1:**` instead of plain `HOST1:`
  - Parser strips markdown bold (`**`) before matching speaker labels
  - Prevents "0 dialogue segments" parsing failures

### 4. Temporary File Cleanup
```python
# OpenAI TTS streams to temp file
with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
    temp_path = temp_file.name
    response.stream_to_file(temp_path)
audio = AudioSegment.from_mp3(temp_path)
os.unlink(temp_path)  # Clean up
```

### 5. Package Entry Point Chain
1. `pyproject.toml`: `gencast = gencast:main`
2. `__init__.py`: Imports `main` from `gencast.py` module
3. `gencast.py`: Defines `main()` function

Requires `[tool.setuptools] py-modules = ["gencast"]` in pyproject.toml

## Dependencies

**Required**:
- `openai>=1.0.0` - TTS and Whisper APIs (audio processing)
- `litellm>=1.30.0` - Multi-provider AI chat completions
- `pydub>=0.25.1` - Audio manipulation (requires ffmpeg system dependency)
- `audioop-lts>=0.2.0` - Python 3.13+ compatibility fix
- `rich>=13.0.0` - Progress bars (graceful degradation if missing)

**Optional**:
- `mistralai>=1.0.0` - PDF processing (falls back to pypdf)
- `pypdf>=3.0.0` - Basic PDF extraction

**Development**:
- `basedpyright>=1.21.0` - Type checking (strict mode, warn-only)
- `pytest>=7.0.0` - Testing framework
- `ruff>=0.1.0` - Linting and formatting

**System Dependencies**:
- `ffmpeg` - Required by pydub for audio processing

## Code Style

- Clean, readable Python 3.8+
- **Full type hints** using stdlib `typing` and `typing_extensions`
  - All function parameters and returns typed
  - `Optional`, `Dict`, `Tuple`, `List`, `Any` used throughout
  - Type checked with basedpyright (strict mode, warn-only)
- Docstrings for public functions
- Single responsibility per function
- Layer separation: data → business logic → interface
- Graceful degradation for optional features

### Type Checking

```bash
# Full project (0 errors, ~360 warnings expected)
basedpyright

# Single file
basedpyright src/dialogue.py

# Configuration in pyproject.toml
# - Strict mode with warn-only enforcement
# - Errors only for critical issues (optional access, subscript)
```

## Critical Reminders

1. **Always activate venv**: `source venv/bin/activate`
2. **Cost awareness**: Test with small documents first (~$0.10-0.17 per run)
3. **Prompt file paths**: Loaded relative to `dialogue.py` location
4. **Spatial audio range**: 0.3-0.6 recommended (0.4 default, max 1.0)
5. **VLC subtitles**: Requires visualizations enabled
6. **Python 3.13+**: Requires `audioop-lts` package

## Package Management

```bash
# Development (editable mode)
pip install -e .

# System-wide (isolated environment)
pipx install -e .
pipx upgrade gencast
pipx uninstall gencast

# List installed
pipx list
```

## User Experience (Neurodivergent-Friendly Design)

- Clear step-by-step progress (Step 1/3, 2/3, 3/3)
- Immediate feedback on each operation
- Live streaming preview of dialogue generation
- Progress bars with time estimates
- Explicit success confirmations with emojis
- SRT subtitles for accessibility
- Minimal decision points in CLI
