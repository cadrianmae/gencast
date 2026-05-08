# gencast v1.0 — full rewrite design

**Status:** Approved by Mae 2026-05-07
**Branch:** `rewrite/v1.0` (off `main` after `v0.6.2`)
**Author:** Mae Capacite (with Claude Opus 4.7 as design partner)

## Summary

gencast is being fully rewritten for v1.0. The current single-shot dialogue
architecture caps podcasts at ~20 minutes and degrades sharply with long
sources. v1.0 replaces it with a per-segment pipeline, a three-axis profile
system (speakers / episodes / rooms), pluggable TTS backends, Anthropic prompt
caching, map-reduce summarization for oversize sources, sentence-level subtitle
generation embedded into M4A output, an HRTF-free spatial audio chain, and a
notebook-driven CLI + library API.

The full pipeline becomes 10 stages. Most expensive operations are cached on
disk so re-running an interrupted run resumes effectively for free.

## Non-goals (out of scope for v1.0)

- LangChain / LangGraph adoption (researched and rejected — see Section 7)
- HRTF-based spatial audio (researched, prototyped, rejected — voices sound
  thin or "phone-call-like" on consumer headphones; pan + ITD with reverb
  achieves better perceptual results)
- NotebookLM-style critique-and-revise polish passes (deferred to v1.x)
- Multilingual generation (schema reserved; English-only validation in v1)
- N>2 speakers (schema supports 1-4; only 1 and 2 tested in v1)
- Animated speaker avatars (schema reserved; future release per Section 3.7)
- Personalized HRTF, head tracking, video output, real-time generation

## 1 Pipeline architecture

The current single-shot dialogue stage is replaced by an outline + per-segment
transcript loop, with a token-aware preflight + map-reduce compression layer
in front and a packaging stage after.

| # | Stage | LLM/TTS calls | Optional? |
|---|---|---|---|
| 1 | `load_notebook` | — | no |
| 2 | `extract_sources` | — | no |
| 3 | `preflight` (token count) | — | no |
| 4 | `map_reduce_summarize` | ~K + log K summarize-model calls (K = chunks) | conditional (only if oversize) |
| 5 | `generate_outline` | 1 outline-model call | no |
| 6 | `generate_transcript_segments` | N transcript-model calls (with prompt caching) | no |
| 7 | `generate_audio` | M TTS calls (one per sentence, asyncio.gather batches of 5) | no |
| 8 | `combine_audio` | — | no |
| 9 | `package` (ffmpeg M4A mux) | — | conditional on output formats |
| 10 | `cost_report` | — | no |

### What unlocks the long-podcast capability

- **Stage 6 per-segment loop**: each segment gets its own ~5K-token output
  budget. 10 segments × 10-turn long-size = ~100 turns of dialogue, ~30-60min
  audio. The current ~20-min ceiling was a single-call output limit, not an
  economic limit.
- **Stage 4 map-reduce compression**: for sources >model context, recursive
  chunk → summarize → merge frees output budget for the per-segment dialogue
  calls. Hierarchical, not RAG (gencast podcasts must cover the whole source,
  not retrieve from it).
- **Anthropic prompt caching**: per-segment shape lets the constant prefix
  (briefing + content + outline) cache across segments 2..N. ~70% input-token
  savings, validated independently in Mae's Open Notebook stack.
- **Stage 9 native timing**: audio combination knows each clip's start/end ms,
  so SRT is emitted directly without a Whisper post-pass. Whisper STT remains
  available via `gencast subtitle <existing.mp3>` for re-subtitling external
  audio.

## 2 Components & module map

Package layout follows "package by feature" (vertical slices). Each subpackage
has one reason to change. Library API is a single `from gencast import
generate_podcast` entrypoint; CLI is a thin wrapper.

```
gencast/
├── __init__.py                      # Public API: from gencast import generate_podcast
├── cli/
│   ├── __init__.py
│   └── main.py                      # gencast notebook.yaml | gencast file.md ...
│
├── notebook.py                      # Notebook YAML schema + loader
│
├── profiles/
│   ├── __init__.py
│   ├── schemas.py                   # Speaker, SpeakerProfile, EpisodeProfile, RoomProfile
│   ├── loader.py                    # 3-level cascade: project > XDG > bundled
│   └── bundled/
│       ├── speakers/                # who is speaking (voices, personas)
│       ├── episodes/                # what kind of podcast (briefing, num_segments, models)
│       └── rooms/                   # how it sounds (spatial preset)
│
├── pipeline/
│   ├── __init__.py                  # generate_podcast() orchestration + PodcastState
│   ├── extract.py                   # md/pdf/url/stdin → str
│   ├── preflight.py                 # token count + map-reduce summarization
│   ├── outline.py                   # 1 LLM call → segment list
│   ├── transcript.py                # per-segment loop with prompt caching
│   ├── audio.py                     # sentence-split → TTS → spatial → reverb → concat
│   └── subtitles.py                 # native sentence SRT (default) + Whisper STT path
│
├── tts/
│   ├── __init__.py
│   ├── base.py                      # TTSBackend protocol + sentence splitter
│   ├── openai.py                    # OpenAI tts-1-hd
│   └── speaches.py                  # OpenAI-compat layer pointing at Speaches/Kokoro
│
├── llm/
│   ├── __init__.py                  # litellm wrapper
│   └── caching.py                   # Anthropic ephemeral cache_control helper
│
├── audio_fx/
│   ├── __init__.py
│   ├── pan_itd.py                   # amplitude pan + ITD spatial cue
│   ├── reverb.py                    # SchroederReverb (T60, LPF, damping)
│   ├── ambience.py                  # NC 20 noise bed (pink + LPF + fan rumble)
│   ├── distance.py                  # inverse-square attenuation
│   └── normalize.py                 # peak/RMS normalization
│
├── prompts/
│   ├── outline.jinja
│   └── transcript.jinja
│
├── cost.py                          # per-stage token + audio-second meter
└── logger.py                        # Reporter facade (Rich Live or plain text)
```

### Three-axis profile composition

```
notebook.yaml
  speaker_profile: revision-duo     # WHO  → 1-N Speaker objects, voices, personas
  episode_profile: exam-revision    # WHAT → briefing, num_segments, outline+transcript models
  room_profile:    small-room       # HOW IT SOUNDS → spatial pipeline params
```

Each axis swappable independently.

### Bundled rooms (locked from v1 listening tests)

- `small-room.yaml` — gencast default (T60=0.30s, wet 5%, LPF 2kHz)
- `dry.yaml` — no reverb, no ambience
- `large-room.yaml` — T60=0.50s, wet 8%, LPF 2.5kHz
- `vocal-booth.yaml` — T60=0.20s, wet 3%, LPF 1.5kHz, damping 0.65
- `wide.yaml` — arc=160°
- `narrow.yaml` — arc=80°
- `ambient.yaml` — ambience bed at -50 dBFS (loud presence)
- `silent.yaml` — ambience disabled

### Bundled speakers (initial set)

- `educational-duo` — general teaching duo
- `revision-duo` — exam-prep tone (Sophie + Ben)
- `solo-tutor` — single host, walkthrough
- `interview-duo` — interviewer + expert

### Bundled episodes (initial set)

- `concept-explainer` — define-then-deepen
- `exam-revision` — revision-style with worked Q&A
- `interview` — Q&A flow
- `casual-discussion` — conversational

### What survives from current gencast (lift, don't rewrite)

- `logger.py` — verbatim (with Reporter facade extensions)
- v0.6.2 chunked Whisper STT — moves into `pipeline/subtitles.py` for the
  re-subtitle path
- Doc extraction (md/pdf via Mistral → pypdf fallback) — into
  `pipeline/extract.py`
- pydub-based audio concat patterns

### What gets deleted

- `dialogue.py` (single-shot) → replaced by `pipeline/outline.py` +
  `pipeline/transcript.py`
- Existing spatial code (`apply_spatial_audio`, ITD/pan in `audio.py`) →
  replaced by `audio_fx/pan_itd.py` + `audio_fx/reverb.py` etc., parameterized
  by RoomProfile
- `prompts/{educational,interview,casual,debate}.txt` → replaced by jinja
  templates parameterized via episode profile
- Hardcoded HOST1/HOST2 dialogue parsing → speakers come from SpeakerProfile

## 3 Data flow + state

### 3.1 Pipeline state object

A single `PodcastState` is threaded through stages. Stages mutate state in
place and may attach to `state.cost` without threading cost through every
signature.

```python
@dataclass
class PodcastState:
    notebook: Notebook                    # input + resolved profiles
    source_text: str                      # current (possibly compressed)
    source_tokens_original: int
    source_tokens_final: int
    outline: Outline | None = None
    transcript: Transcript | None = None
    clips: list[AudioClip] = field(default_factory=list)
    combined_audio: AudioSegment | None = None
    srt_entries: list[SrtEntry] = field(default_factory=list)
    cost: CostMeter = field(default_factory=CostMeter)
```

Memory ceiling: ~20 MB peak for a 25-min podcast (clip arrays + final combined
audio). No streaming/chunked write paths needed in v1.

### 3.2 Output artifacts

Default output: `<basename>.m4a` only — single file with embedded subtitles.
Other outputs are opt-in via `output.formats`:

```
out/
├── <basename>.m4a                     # default (audio + embedded subs via mov_text)
│
├── <basename>.mp3                     # if 'mp3' in formats
├── <basename>.srt                     # if 'mp3' in formats (sidecar)
│
├── <basename>.transcript.json         # if 'transcript' in formats
├── <basename>.outline.json            # if 'outline' in formats
└── <basename>.cost.json               # if 'cost' in formats
```

`transcript.json` schema:

```json
{
  "title": "...",
  "speakers": ["Sophie", "Ben"],
  "duration_ms": 1247000,
  "turns": [
    {"speaker": "Sophie", "text": "Hi everyone...", "start_ms": 0, "end_ms": 2340}
  ]
}
```

`cost.json`:

```json
{
  "stages": {
    "outline":    {"model": "anthropic/claude-haiku-4.5", "tokens_in": 5200,  "tokens_out": 600,  "usd": 0.005},
    "transcript": {"model": "anthropic/claude-sonnet-4",  "tokens_in": 35400, "tokens_out": 4200, "usd": 0.114,
                   "cache_reads_in": 28800, "cache_writes_in": 4800, "usd_saved": 0.057},
    "tts":        {"backend": "openai", "model": "tts-1-hd", "audio_seconds": 720, "usd": 0.058}
  },
  "total_usd": 0.206,
  "total_runtime_seconds": 142
}
```

### 3.3 CLI surface

```
gencast NB.yaml                    # primary: generate from notebook
gencast file.md [file2.md ...]     # ad-hoc with default profiles
gencast init [--copy NB] [--minimal]
gencast preview NB.yaml            # outline-only dry run, prints to stdout
gencast list-profiles [--type speakers|episodes|rooms]
gencast subtitle EXISTING.mp3      # re-subtitle externally-provided audio (Whisper STT path)
gencast cache clear [tts|llm|extract|all]
```

### 3.4 Output styling & verbosity

#### Default output (interactive TTY)

Rich Live display, two-band layout — progress on top, current activity below
(modeled on convert-pdf):

```
┌─ gencast: photosynthesis-revision ──────────────────────────────┐
│                                                                  │
│  [4/10] Transcript                ██████████░░░░░░░░░░  4/6     │
│                                                                  │
│  ▎🦊 sonnet-4 — segment 4 — cache read 92% (28.8K of 31.2K tok) │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

Per-speaker emoji (from `Speaker.avatar.emoji`) appears in the activity line
for all stages where a single speaker is the focus.

#### Non-interactive (piped, CI, redirected)

Auto-detected via `Console.is_terminal`. Default: errors only on stderr; no
progress; exit code carries success/failure. With `-v`/`-vv`: plain log lines
on stderr.

#### Verbosity flags

| Flag | Interactive | Non-interactive |
|---|---|---|
| (default) | Rich Live window | errors only |
| `-v` / `--verbose` | Live + INFO log panel | plain INFO log lines |
| `-vv` / `--debug` | Live + DEBUG log panel | plain DEBUG log lines |
| `-q` / `--quiet` | spinner only | silent (errors still on stderr) |
| `--silent` | nothing visible | silent |
| `--log-file PATH` | (any verbosity) — always write full DEBUG log to file |

#### Implementation

Single `Reporter` facade in `gencast/logger.py`. Two implementations
(`RichReporter`, `PlainReporter`) selected at startup. Pipeline modules call
`reporter.stage_start(...)`, `stage_activity(...)`, `stage_advance(...)`,
`stage_done(...)` and remain unaware of the rendering implementation.

### 3.5 Future work — animated speaker avatars

Tracked in `docs/future-work.md`. v1 reserves three hooks:

1. `SpeakerProfile.avatar` field with `emoji`, `ascii` (path), `image` (path),
   `color` (hex) — all optional
2. `transcript.json` schema preserves per-sentence speaker + start/end ms (the
   substrate a future viewer will animate from)
3. `RichReporter` includes per-speaker emoji in the activity line so a
   primitive form ships in v1

vNext: `gencast view` web subcommand reading `transcript.json` + audio,
animating ASCII portraits or SVG/PNG avatars synced to per-sentence timings.

## 4 Profile schemas

### 4.1 SpeakerProfile

```python
class Avatar(BaseModel):
    emoji: str | None = None
    ascii: str | None = None     # path relative to profile dir
    image: str | None = None     # path relative to profile dir
    color: str | None = None     # hex


class Speaker(BaseModel):
    name: str
    voice_id: str
    backstory: str
    personality: str
    avatar: Avatar | None = None
    tts_provider: str | None = None    # per-speaker override (rare)
    tts_model: str | None = None
    tts_config: dict | None = None


class SpeakerProfile(BaseModel):
    name: str
    description: str | None = None
    tts_provider: str
    tts_model: str
    tts_config: dict | None = None
    speakers: list[Speaker]            # 1-4; unique names + voice IDs validated
```

### 4.2 EpisodeProfile

```python
class EpisodeProfile(BaseModel):
    name: str
    description: str | None = None
    speaker_profile: str | None = None
    default_briefing: str
    num_segments: int = 6                                  # 3-10
    segment_size_default: Literal["short", "medium", "long"] = "medium"
    outline_provider: str = "anthropic"
    outline_model: str = "claude-haiku-4.5"
    transcript_provider: str = "anthropic"
    transcript_model: str = "claude-sonnet-4"
    outline_config: dict | None = None
    transcript_config: dict | None = None
    summarize_provider: str | None = None                  # falls back to outline_provider
    summarize_model: str | None = None                     # falls back to outline_model
    language: str | None = None                            # ISO; English-only validation in v1
```

### 4.3 RoomProfile

```python
class RoomProfile(BaseModel):
    name: str
    description: str | None = None
    arc_deg: float = 120.0
    itd_max_ms: float = 0.6
    jitter_deg: float = 1.5
    reverb_t60_s: float = 0.30
    reverb_wet: float = 0.05
    reverb_lpf_hz: float = 2000.0
    reverb_damping: float = 0.55
    predelay_ms: float = 20.0
    table_radius_m: float = 0.85
    ambience_db: float | None = -70.0    # None to disable
    ambience_lpf_hz: float = 1500.0
    ambience_fan_rumble_db: float = 4.0
    target_dbfs: float = -1.0
```

### 4.4 Notebook

```python
class NotebookOutput(BaseModel):
    dir: Path = Path("./out")
    basename: str | None = None                # default: slugify(title)
    formats: list[Literal["m4a", "mp3", "transcript", "outline", "cost"]] = ["m4a"]


class NotebookOverrides(BaseModel):
    outline_provider: str | None = None
    outline_model: str | None = None
    transcript_provider: str | None = None
    transcript_model: str | None = None
    num_segments: int | None = None
    briefing_suffix: str | None = None         # appended to default_briefing
    briefing: str | None = None                # complete replacement (rare)


class Notebook(BaseModel):
    title: str
    output: NotebookOutput = Field(default_factory=NotebookOutput)
    sources: list[str]
    speaker_profile: str = "educational-duo"
    episode_profile: str = "concept-explainer"
    room_profile: str = "small-room"
    overrides: NotebookOverrides = Field(default_factory=NotebookOverrides)
    description: str | None = None
    tags: list[str] | None = None
```

### 4.5 Cascade resolution

```
1. ./gencast/profiles/{kind}/{name}.yaml              (project, highest priority)
2. ~/.config/gencast/profiles/{kind}/{name}.yaml      (XDG user)
3. <gencast install>/profiles/bundled/{kind}/{name}.yaml  (bundled defaults)
```

First match wins. `gencast list-profiles` walks all three and prints with
origin markers.

### 4.6 Override precedence

```
Final value =
  Notebook.overrides.{field}     (highest)
  ↑
  EpisodeProfile.{field}
  ↑
  Hardcoded defaults             (lowest)
```

For briefing: `Notebook.overrides.briefing` (full replacement) >
`EpisodeProfile.default_briefing + Notebook.overrides.briefing_suffix` >
`EpisodeProfile.default_briefing`.

## 5 Error handling + resumability

### 5.1 Two principles

1. **Caches make resumability free.** Re-running an interrupted gencast hits
   LLM + TTS caches for everything that completed. No explicit checkpoint
   files.
2. **Fail fast with actionable messages.** Every error names the stage, what
   it was doing, the underlying cause, and the suggested next step.

### 5.2 Per-stage error matrix

| Stage | Common failures | Response |
|---|---|---|
| `load_notebook` | YAML parse, schema violation | Fail with file:line + field path |
| | Profile not found | Fail with all 3 cascade paths searched + suggestion |
| `extract` | File not found | Fail per-source after listing all missing |
| | PDF (Mistral 4xx) | Fall back to pypdf with warning |
| | URL fetch | Retry 3x w/ backoff → fail with URL + status |
| `preflight` | Source still oversize after map-reduce | Fail with token count + budget; suggest split |
| `map_reduce` | LLM API error mid-recursion | LiteLLM retry → fail with chunk index |
| `outline` | LLM API error | LiteLLM retry → fail |
| | Invalid JSON | Re-prompt once with schema reminder; then fail (raw saved) |
| `transcript` | LLM API error per segment | Per-segment retry → fail (other segments cached) |
| | Invalid speaker name | Re-prompt with valid names list; then fail |
| `audio` | TTS API error per clip | Per-clip retry 3x → fail (cached clips persist) |
| | TTS rate limit (429) | Honor `Retry-After`; reduce concurrency |
| | Voice ID invalid | Catch at notebook load (validate against backend catalog) |
| `combine` | Pure pydub/numpy | Should not fail; if it does, file as bug |
| `package` | ffmpeg not installed | Detect at startup; clear install hint per OS |
| | ffmpeg mux failure | Save mp3 + srt sidecars even if m4a fails; warn |
| `cost_report` | Pure math | No failures |

### 5.3 Cache layout (XDG)

```
~/.cache/gencast/
├── llm/                          # opt-in via --cache-llm
│   └── <hash>.json
├── tts/                          # always on; the big cost saver
│   └── <provider>/<model>/<voice>/<text-hash>.mp3
└── extract/                      # always on (Mistral PDFs)
    └── <file-hash>.json
```

Cache keys:
- LLM: SHA256 of (provider, model, messages, params, response_format) — opt-in
  because dialogue is non-deterministic and you usually want a fresh take
- TTS: SHA256 of (provider, model, voice, text) — always on (deterministic +
  expensive)
- Mistral PDF: SHA256 of file content — always on

### 5.4 Resumability contract

Re-running after a stage 7 failure replays cached LLM + TTS work, retries the
failed clip, and continues. No explicit checkpoint files. Anthropic prompt
caching covers LLM cost on resume even with `--cache-llm` off.

### 5.5 Error message template

```
✗ Stage <N>/<total> (<stage_name>) failed

  <what was being done>
  <error class>: <error message>

  <suggested fix or next step>
  <where to look for partial state, if any>
```

### 5.6 Retry policy

- LLM: 3 retries, exponential backoff start=2s, factor=2, jitter=0.5
- TTS: 3 retries, start=1s, factor=2, jitter=0.3
- Honors server `Retry-After` headers via LiteLLM / OpenAI SDK
- User overrides: `--retries N`, `--no-retry`

### 5.7 Validation strictness

- Notebook YAML → Pydantic strict (unknown fields raise)
- Profile YAML → Pydantic `extra="ignore"` (forward-compat for older installs)
- Voice IDs → validated against backend catalog at notebook load
- Source paths → resolved + existence-checked at load time

## 6 Testing strategy

### 6.1 Test pyramid

```
                 ┌─────────────────────┐
                 │  E2E smoke (1)      │   real APIs, opt-in
                 ├─────────────────────┤
                 │  Integration (~10)  │   real APIs per backend, gated
                 ├─────────────────────┤
                 │  Component (~20)    │   stages w/ recorded fixtures
                 ├─────────────────────┤
                 │  Unit (~100+)       │   pure functions, fast, no I/O
                 └─────────────────────┘
```

### 6.2 Per-tier coverage

**Unit (`tests/unit/`)** — fast, no I/O, every commit:
audio_fx math, sentence splitter edge cases, profile schema validation,
cascade resolution, override precedence, Anthropic cache_control placement,
cost calculations, preflight decision boundaries.

**Component (`tests/component/`)** — recorded LLM responses (`vcrpy`), cached
TTS outputs (checked into `tests/fixtures/tts_cache/`):
each pipeline stage tested end-to-end with deterministic fixtures.

**Integration (`tests/integration/`)** — real API calls, gated per backend:

```bash
GENCAST_TEST_OPENAI=1 GENCAST_TEST_ANTHROPIC=1 GENCAST_TEST_SPEACHES=1 \
  pytest tests/integration
```

**E2E smoke (`tests/e2e/test_smoke.py`)** — single tiny notebook → real m4a,
gated by `GENCAST_TEST_E2E=1`. Cost ~$0.02 per run.

### 6.3 Harness fixtures

The `scratch/` harnesses produced during design land in `tests/fixtures/`:

```
tests/fixtures/
├── audio_reference/                 # known-good outputs from harness work
├── cassettes/                       # vcrpy LLM recordings
├── tts_cache/                       # pre-cached TTS for component tests
└── notebooks/                       # minimal notebooks for tests
```

### 6.4 What's NOT tested (YAGNI)

- TTS audio quality (subjective)
- LLM dialogue quality (subjective; covered by manual review when editing prompts)
- Specific provider response shapes (LiteLLM normalizes)
- ffmpeg internals (trusted dep)

### 6.5 CI

- Unit + component: every PR (free, fast)
- Integration + E2E: only on push to main, behind secrets gate (~$0.25/run)

### 6.6 Test deps

```toml
test = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "vcrpy>=5.0.0",
    "ffmpeg-python>=0.2.0",         # ffprobe wrapper for M4A verification
]
```

## 7 Decisions & rationale

### 7.1 Rejected: depending on `lfnovo/podcast-creator`

`lfnovo/podcast-creator` (the LangGraph-based library Open Notebook delegates
to) implements the same outline + per-segment shape we want. We initially
considered wrapping it. Rejected because:

- Pulls in `langgraph`, `langchain-core`, `esperanto` (LangChain adapter)
- Provides no hook to inject Anthropic `cache_control` blocks before the
  prompt hits the model — the single biggest cost win for gencast
- JSON-only profile config (vs YAML, which is friendlier for hand-editing)
- Forces async API on all callers
- Owning the prompt boundary is non-negotiable

### 7.2 Rejected: HRTF-based spatial audio

Prototyped with MIT KEMAR + diffuse-field equalization + the Xie 2009
low-frequency corrected dataset (`spatialaudio/lf-corrected-kemar-hrtfs`).
Both made voices sound thin or "phone-call-like" on consumer headphones —
non-individualized HRTF is a known issue. Pan + ITD with a parameterized
Schroeder reverb produces a more pleasant result and is simpler.

The rejected HRTF code path is gone. v1 spatial audio is:

```
mono TTS → pan + ITD → Schroeder reverb (T60/wet/LPF/damping)
        → predelay (20ms) → inverse-square distance attenuation
        → ambience bed (NC 20) → ±jitter_deg azimuth jitter per sentence
        → peak normalize -1 dBFS
```

### 7.3 Rejected: LangChain

Researched. Provides nothing gencast needs that LiteLLM doesn't, and pulls in
significant transitive dependencies. LiteLLM remains the chat-completion
layer; the OpenAI SDK and a lightweight `httpx`-based Speaches adapter handle
TTS.

### 7.4 Decided: M4A as default output

MP3 doesn't support a subtitle track. M4A with `mov_text` does and plays in
VLC, Apple Music, browsers, and ffplay natively. Podcast apps that don't
render subtitle tracks ignore them and play audio fine. Single-file UX.

`mp3` + sidecar `.srt` remains available via `output.formats: [mp3]`.

### 7.5 Decided: per-stage Haiku/Sonnet model mix

Outline is a structural task (Haiku is sufficient and 5x cheaper). Transcript
is a quality task where Sonnet pays for itself in dialogue character and is
the cache-control beneficiary. Defaults reflect this; users can override per
notebook.

### 7.6 Decided: Sync API + async TTS only

Public API is sync (`generate_podcast(notebook=...)`). Only the audio stage
uses asyncio internally for concurrent TTS calls. Users don't see async
ceremony. If gencast ever grows into a service, an async wrapper can be added
without breaking the sync API.

### 7.7 Decided: 3-level profile cascade

Project (`./gencast/profiles/`) > XDG (`~/.config/gencast/profiles/`) >
bundled. Mirrors podcast-creator's cascade because it's good. Lets users
override per-project without forking bundled defaults.

### 7.8 Decided: pip-only install, single source of truth in `pyproject.toml`

`requirements.txt` is removed. All dependencies (runtime + optional + dev/test)
live in `pyproject.toml`. Install:

```bash
# Development
python -m venv venv && source venv/bin/activate
pip install -e .[test]

# End user
pip install gencast
```

`pipx install gencast` continues to work without any extra effort on our side
(pipx reads `pyproject.toml`), but it is no longer the recommended path. The
README install section will show `pip install gencast` only.

Reasons:

- gencast is a small library (no large CLI footprint that benefits from
  isolated install)
- Single source of truth avoids drift between `pyproject.toml` and
  `requirements.txt`
- `pip install -e .[test]` already gives full dev parity in a venv
- One fewer thing in the install docs reduces decision fatigue for new users

Optional-dependency groups in `pyproject.toml`:

```toml
[project.optional-dependencies]
test = ["pytest>=7.0.0", "pytest-asyncio>=0.21.0", "vcrpy>=5.0.0", "ffmpeg-python>=0.2.0"]
dev  = ["basedpyright>=1.21.0", "ruff>=0.1.0"]
all  = ["gencast[test,dev]"]
```

## 8 Worked example

`./photosynthesis/notebook.yaml`:

```yaml
title: "CMPU 4010 — Photosynthesis revision"
description: "Light reactions vs Calvin cycle, with a worked example each."
tags: [cmpu-4010, biology-i-took-as-an-elective, exam-prep]

output:
  dir: ./out
  basename: photosynthesis-revision
  formats: [m4a]

sources:
  - lectures/photosynthesis.md
  - lectures/calvin-cycle.md

speaker_profile: revision-duo
episode_profile: exam-revision
room_profile: small-room

overrides:
  briefing_suffix: |
    Pay specific attention to the distinction between the light-dependent
    reactions and the Calvin cycle. Students consistently confuse the two
    on the exam. Include one worked Q&A on this distinction.
```

Pipeline run (5K-token source, 2 speakers, 6 segments):

```
[1/10] Resolving profiles                  revision-duo / exam-revision / small-room
[2/10] Extract                              5,012 tokens
[3/10] Preflight                            fits Sonnet 4 (5K << 195K)
[4/10] Map-reduce                           skipped
[5/10] Outline                              haiku-4.5: 6 segments
[6/10] Transcript (1/6)                    sonnet-4: cache write
[6/10] Transcript (2/6)                    sonnet-4: cache read 92%
[6/10] Transcript (3-6/6)                  sonnet-4: cache read 92%
[7/10] Audio                                openai/tts-1-hd: 28 sentences
[8/10] Combine                              12:24 podcast
[9/10] Package                              ffmpeg → m4a w/ embedded subs
[10/10] Cost                                $0.21 (cache saved $0.06)

✓ Wrote out/photosynthesis-revision.m4a
  Runtime: 2:24
```

## 9 Migration from v0.6.x

v1.0 is not backward-compatible with v0.6.x CLI flags. Old flags
(`--style`, `--audience`, `--host1-voice`, etc.) become profile fields:

| v0.6.x flag | v1.0 equivalent |
|---|---|
| `--style educational` | `episode_profile: educational-duo` (or similar) |
| `--audience technical` | bake into the episode profile's briefing |
| `--host1-voice nova` | `speaker_profile: <one with Sophie/nova>` |
| `--host2-voice echo` | same |
| `--spatial-separation 0.4` | `room_profile: <one with arc_deg=...>` |
| `--with-planning` | always on (it's the outline stage now) |
| `--save-dialogue` | `output.formats: [transcript]` |
| `--model X` | `overrides.transcript_model: X` |

Migration tool (out of scope for v1.0; could be `gencast init --from-v0`
later) would translate a v0.6.x command into a notebook.yaml.

## 10 Implementation order

Phases as discrete shippable slices on `rewrite/v1.0`. Each phase produces a
running pipeline (slimmer than the next), so we never have a 4-week build
without a testable midpoint.

| Phase | Scope | Approximate output |
|---|---|---|
| Phase 0 | Delete `requirements.txt`; consolidate deps into `pyproject.toml`; `notebook.py`, `profiles/` (schemas + loader + bundled YAML) | `gencast list-profiles` works |
| Phase 1 | `pipeline/extract.py`, `pipeline/preflight.py`, `llm/`, prompts | `gencast preview NB.yaml` (outline-only) |
| Phase 2 | `pipeline/transcript.py`, transcript JSON output | `--formats=transcript` produces dialogue |
| Phase 3 | `tts/`, `pipeline/audio.py` (without spatial yet) | first audible podcast |
| Phase 4 | `audio_fx/`, room profile applied, ambience | matches v1 listening-test quality |
| Phase 5 | `pipeline/subtitles.py`, ffmpeg M4A mux | default `.m4a` output works |
| Phase 6 | `cli/`, `gencast init` wizard, Reporter (Rich + Plain), `cost.py` | full UX shipped |
| Phase 7 | `pipeline/preflight.py` map-reduce path, `--cache-llm` flag, `gencast subtitle` | edge cases + extras |
| Phase 8 | Tests (unit, component, fixtures from harnesses) + CI | merge to main → v1.0.0 |

Each phase is mergeable independently if needed. After Phase 6, the rewrite
branch has feature parity for normal use; phases 7-8 harden it.

## Appendix A — References

- LangChain map-reduce: https://python.langchain.com/docs/how_to/summarize_map_reduce/
- Schroeder reverb math (Stanford CCRMA): https://ccrma.stanford.edu/~jos/pasp/Schroeder_Reverberators.html
- KEMAR HRTF (rejected, but referenced for Section 7.2): http://sound.media.mit.edu/resources/KEMAR.html
- Xie 2009 LF-corrected KEMAR (also rejected): https://github.com/spatialaudio/lf-corrected-kemar-hrtfs
- LiteLLM cache_control passthrough: https://docs.litellm.ai/docs/completion/prompt_caching
- ElevenLabs alignment endpoint (deferred): https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps
- NotebookLM pipeline (informational): https://simonwillison.net/2024/Sep/29/notebooklm-audio-overview/
- OpenAI no-TTS-timestamps (community thread): https://community.openai.com/t/text-to-speech-word-timings/532875
- ID3 chapters / SYLT (informational): https://id3.org/id3v2.4.0-frames

## Appendix B — Future work index

Tracked separately in `docs/future-work.md`:

- Animated speaker avatars (ASCII art → SVG/PNG → video output)
- `gencast view` web subcommand
- N>2 speakers (validated)
- Multilingual generation (validated against non-English TTS voices)
- Critique-and-revise polish passes (NotebookLM-style)
- ElevenLabs TTS backend with native alignment
- LLMLingua prompt compression as an alternative to map-reduce
- Per-speaker mood states (sentiment-driven avatar swaps)
