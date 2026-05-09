# gencast — Claude Code plugin

Conversational interface to [gencast](https://github.com/cadrianmae/gencast).
Lets you build notebooks, check sources, review transcripts, and explain
costs through natural-language prompts inside Claude Code.

## Install

```bash
pip install "gencast>=1.2.0"      # or: pipx install gencast
```

In Claude Code:

```
/plugin install gencast
```

## Skills

| Skill | Trigger phrases | What it does |
|---|---|---|
| `notebook-init` | "draft a gencast notebook from these notes" | Builds `notebook.yaml` conversationally from candidate sources. |
| `source-check` | "are these sources good for a podcast?" | Token-counts sources and predicts USD cost via `gencast estimate`. |
| `review-transcript` | "review this gencast transcript" | Reads `transcript.json` and flags awkward phrasings + flow problems. Advisory only — does not auto-regenerate. |
| `cost-explain` | "explain my gencast cost.json" | Plain-language cost-by-stage breakdown with optimisation suggestions. |

## Requirements

- `gencast>=1.2.0` on `PATH`
- `ffmpeg` (system dep — required by gencast for audio)
- `jq` (used by some skills for inline JSON parsing in dynamic-context blocks)

## Source

https://github.com/cadrianmae/gencast — skills live in `skills/`.
