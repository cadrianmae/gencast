# gencast — future work

Items deliberately out of scope for v1.0. Captured here so the v1 design
keeps the small hooks each one needs without bloating v1 with the work
itself.

## Animated speaker avatars

**v1 hooks reserved:**

- `SpeakerProfile.avatar` field with `emoji`, `ascii`, `image`, `color`
- `transcript.json` carries per-sentence `speaker` + `start_ms` + `end_ms`
- `RichReporter` shows per-speaker emoji in the activity line

**vNext directions** (in rough order of effort):

1. ASCII portrait avatars in the Rich Live panel — switch the active
   speaker's portrait based on which segment the LLM is generating, which
   clip is being TTS'd. Bundled ASCII art pack for the four bundled
   speaker profiles.
2. `gencast view <transcript.json> <audio.m4a>` web subcommand — opens a
   browser tab with a tiny static viewer that animates SVG/PNG avatars in
   sync with `audio.timeupdate`. Reads `transcript.json` directly.
3. Optional video-output format `mp4-video` — generates an MP4 with audio
   + subtitle track + a video track of animated avatars (SVG → frames via
   cairosvg, then ffmpeg muxed). Heaviest dep but most self-contained.
4. Mood states from sentiment analysis — swap avatars between
   neutral / excited / puzzled / amused based on per-turn sentiment.

## N>2 speaker support (validated)

Schema supports 1-4 speakers; v1 only tests 1 and 2. vNext: validate 3 and 4
end-to-end:

- Outline + transcript prompts handle "which speaker speaks when" with a
  larger cast (current prompts already generalize)
- TTS + spatial pipeline handle 3-4 voices at distinct azimuths (audio_fx
  arc-spreader handles arbitrary N)
- Add 3-4 speaker bundled profiles (`panel-discussion`, `interview-trio`)

## Multilingual generation (validated)

`EpisodeProfile.language` field exists; not exercised in v1. vNext:

- Test prompt rendering with non-English `language` directive (jinja
  template already includes the LANGUAGE INSTRUCTION block)
- Validate against non-English TTS voices (Speaches/Kokoro has limited
  multilingual; OpenAI TTS supports many languages)
- Bundled non-English profiles (Irish, Portuguese as candidates)

## Critique-and-revise polish passes (NotebookLM-style)

NotebookLM's pipeline has 5 stages vs gencast v1's 6. The two missing:

- **Outline-revision pass** — after outline, a critique-and-revise call
  tightens segment ordering and balance. One extra LLM call. Cheap with
  prompt caching.
- **Per-segment critique pass** — after transcript, a per-segment critique
  call rewrites for naturalness. N extra LLM calls. Quality bump.
- **Disfluency injection** — after transcript, a stylistic pass adds
  banter, pauses, and "uh"s for naturalness.

Each is +1 LLM call per affected stage. Defer until v1's per-segment
output proves itself; layer these in if quality plateaus.

## ElevenLabs TTS backend

Adds character-level alignment via the `/with-timestamps` endpoint, which
gives word-by-word highlighting for free. Implementation:

1. New `gencast/tts/elevenlabs.py` implementing `TTSBackend`
2. ElevenLabs response includes `normalized_alignment` — convert to
   per-sentence timing for `transcript.json`
3. Surface ElevenLabs voices in the bundled speaker profiles
4. `audio_fx/jitter.py` could use word-level boundaries for sub-sentence
   variation in spatial position

Cost note: ElevenLabs is significantly more expensive than OpenAI TTS or
local Speaches. Won't be the default.

## LLMLingua prompt compression

Alternative to map-reduce summarization for oversize sources. Compresses
prompts 2-5× while preserving meaning, using a small LM (BERT-class).
Adds a heavy dep (BERT-class model + weights). Considered for v1 and
rejected — map-reduce is simpler and the dep cost is real. Revisit if
map-reduce proves too lossy for specific source types.

## Whisper-X / aeneas forced alignment

For users who want word-level timing on top of native sentence-level
timing. WhisperX's wav2vec2 forced alignment can be constrained with the
known script. Adds `whisperx` + wav2vec2 model weights. Defer until
demand surfaces (likely tied to the avatar viewer wanting word-level
animation triggers).

## Live-highlighted transcript in `gencast view`

Once the `gencast view` web subcommand exists, add the live-highlighted
transcript pattern from Open Notebook (Mae's local stack already has
this). Reads `transcript.json` `start_ms`/`end_ms`, binary-searches the
current line on `audio.timeupdate`, smooth-scrolls into view. Click a
line to seek.

## Migration tool from v0.6.x

`gencast init --from-v0 "<old command>"` translates a v0.6.x command-line
invocation into a v1 `notebook.yaml`. Handles `--style`, `--audience`,
`--host1-voice`, `--host2-voice`, `--spatial-separation`, etc. Probably
~100 LOC; punted from v1 to keep the v1 surface focused.

## Speaches voice catalog auto-discovery

v1 validates voice IDs against a hardcoded backend voice catalog at
notebook load. vNext: query Speaches' OpenAI-compat `/v1/audio/voices`
endpoint at startup to learn which voices are actually available on the
running instance (supports per-instance Kokoro voice packs).

## Cost estimation before generation

`gencast estimate <notebook.yaml>` prints expected USD cost without
running anything — token-counts the source, multiplies by per-stage
model rates from LiteLLM's pricing data, plus TTS character pricing.
Useful for "is this notebook worth $0.20 or $5?" decisions before
committing to generation.

## SurrealDB cost-history backend (heavy)

Optional: persist cost.json from each run into a SurrealDB instance for
trend analysis. Mirrors what Open Notebook's tier-B cost tracking would
have done. Probably never built — `cost.json` files in a directory are
greppable enough.
