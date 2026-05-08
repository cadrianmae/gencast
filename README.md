# gencast

Generate conversational podcasts from documents using AI. A cost-effective, customisable, local-first alternative to NotebookLM.

```text
gencast notebook.yaml  ->  podcast.m4a (with embedded subtitles)
```

## Install

```bash
pip install gencast
```

System dependency: `ffmpeg` (for audio combining and M4A muxing).

API keys (export or use `gencast init` to be prompted):

```bash
export OPENAI_API_KEY="sk-..."          # required (TTS + Whisper)
export ANTHROPIC_API_KEY="sk-ant-..."   # required (default outline + transcript)
export MISTRAL_API_KEY="..."            # optional (better PDF extraction)
```

## Quickstart

```bash
gencast init                        # interactive notebook wizard
gencast preview notebook.yaml       # outline-only dry run (free)
gencast generate notebook.yaml      # full pipeline -> out/<basename>.m4a
```

Or one-shot from a markdown file (uses default profiles):

```bash
gencast generate path/to/lecture.md
```

## Three-axis profile system

Each notebook composes three orthogonal profiles:

```yaml
speaker_profile: revision-duo       # WHO speaks (1-4 voices, personas)
episode_profile: exam-revision      # WHAT kind of podcast (briefing, segments, models)
room_profile:    small-room         # HOW it sounds (spatial pipeline)
```

List bundled profiles:

```bash
gencast list-profiles --type speakers
gencast list-profiles --type episodes
gencast list-profiles --type rooms
```

Profiles cascade: `./gencast/profiles/<kind>/<name>.yaml` (project)
> `~/.config/gencast/profiles/<kind>/<name>.yaml` (XDG)
> bundled defaults. Override per-notebook via `overrides:` block in the
notebook YAML.

## Worked example

`./photosynthesis/notebook.yaml`:

```yaml
title: Photosynthesis revision
sources:
  - lectures/photosynthesis.md
  - lectures/calvin-cycle.md
speaker_profile: revision-duo
episode_profile: exam-revision
room_profile: small-room
output:
  basename: photosynthesis-revision
  formats: [m4a]
overrides:
  briefing_suffix: |
    Pay specific attention to the distinction between the light-dependent
    reactions and the Calvin cycle. Include one worked Q&A on this distinction.
```

```bash
gencast generate photosynthesis/notebook.yaml
# -> photosynthesis/out/photosynthesis-revision.m4a
```

## Cost

Typical 10-min podcast (~5K-token source, 6 segments, 2 speakers):

| Component | Default model | Cost |
|---|---|---|
| Outline | `claude-haiku-4-5` | ~$0.005 |
| Transcript (with prompt cache) | `claude-sonnet-4-5` | ~$0.10 |
| TTS | `openai/tts-1-hd` | ~$0.06 |
| Subtitles | native (no Whisper) | $0.00 |
| **Total** | | **~$0.17** |

Use `--model` overrides or different episode profiles to trade quality for cost.

## Caches

- **TTS cache** -- `~/.cache/gencast/tts/` -- always on. Re-runs cost only changed sentences.
- **LLM cache** -- `~/.cache/gencast/llm/` -- opt-in via `--cache-llm`. Off by default since dialogue is non-deterministic.
- **PDF extract cache** -- `~/.cache/gencast/extract/` -- always on for Mistral PDF extraction.

Manage:

```bash
gencast cache status
gencast cache clear --type tts --yes
```

## CLI reference

```text
gencast NB.yaml                       generate (alias for `gencast generate NB.yaml`)
gencast init [--copy NB] [--minimal]  interactive notebook wizard
gencast preview NB.yaml               outline-only dry run
gencast generate NB.yaml              full pipeline -> m4a + sidecars
gencast list-profiles [--type X]      enumerate profiles in cascade
gencast subtitle audio.mp3            re-subtitle external audio (Whisper)
gencast cache status [--type X]       inspect cache sizes
gencast cache clear [--type X] [--yes]
```

Verbosity: `-v`, `-vv`, `-q`, `--silent`, `--log-file PATH`.

## Tests

```bash
pytest tests/unit                          # fast, no API calls
pytest tests/component                     # vcrpy cassettes, no keys needed once recorded
GENCAST_TEST_E2E=1 pytest tests/e2e        # real API calls, costs a few cents
GENCAST_TEST_AUDIO=1 pytest tests/audio    # TTS + spatial audio (requires OPENAI_API_KEY)
```

## Specs and design

- [v1.0 design](docs/superpowers/specs/2026-05-07-gencast-v1-rewrite-design.md)
- [Plan A -- foundation](docs/superpowers/plans/2026-05-07-gencast-v1-plan-a-foundation.md)
- [Plan B -- pipeline](docs/superpowers/plans/2026-05-07-gencast-v1-plan-b-pipeline.md)
- [Plan C -- finishing](docs/superpowers/plans/2026-05-08-gencast-v1-plan-c-finishing.md)
- [Future work](docs/future-work.md)

## License

MIT.
