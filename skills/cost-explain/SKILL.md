---
name: gencast-cost-explain
description: This skill should be used when the user asks to "explain my gencast cost.json", "why did that podcast cost so much", "what made my gencast run expensive", or wants a plain-language breakdown of a gencast cost.json file with optimisation suggestions. Cross-references against `gencast estimate` predictions when the original notebook is available.
---

# gencast cost-explain

Read a gencast `cost.json` and translate it into a plain-language breakdown of where the money went, plus concrete optimisations. Compares predicted vs actual cost when the original notebook is also provided.

## Rate table for the bundled-default models

The rate table below is injected at skill-load time:

```!
gencast estimate --rates-only --json 2>/dev/null | jq -r 'to_entries[] | "- **\(.key)**: $\(.value.input_per_1k * 1)/1k in, $\(.value.output_per_1k * 1)/1k out"' || echo "(gencast not installed or --rates-only failed)"
```

Version check: !`gencast --version 2>/dev/null || echo "MISSING"`

## Prerequisites

- A `cost.json` file produced by `gencast generate`. Located at `<output_dir>/<notebook_name>.cost.json`.
- Optionally, the original `notebook.yaml` (lets the skill compare predicted vs actual via `gencast estimate`).

## Workflow

1. **Read cost.json.** Validate it has the expected schema:
   - Top-level `total_usd: float` and `stages: [...]` or `stages: {name: {...}}`
   - Each stage: `{name|kind: str, model: str, usd: float, ...}` (or compatible)
   If the schema does not match, stop and tell the user this does not look like a gencast cost.json.

2. **Compute proportions.** For each stage, calculate `(stage_usd / total_usd) * 100`. Order stages by descending USD.

3. **If the original notebook is available, predict vs actual.**

   ```bash
   gencast estimate <NB.yaml> --json
   ```

   Parse `total_usd` from the prediction. Compute delta % against actual. Print: "Predicted $X, actual $Y (delta Z%)."

4. **Plain-language breakdown.** Walk top-3 most-expensive stages:
   - "Transcript was 60% of cost ($0.18) because Sonnet 4.5 ran on 6 segments. Switching to Haiku 4.5 would save ~$0.13 (-72%)."
   - "TTS was 30% ($0.10) because tts-1-hd at $0.030/1k chars × 4,500 chars."
   - "Whisper was 10% ($0.04) — 6 minutes of audio × $0.006/min."

5. **Suggest optimisations.** From the rate table above + the cost breakdown:
   - **Cheaper outline/transcript model.** If using Sonnet → suggest Haiku. If using Opus → Sonnet.
   - **Fewer segments.** If `num_segments` was high in the notebook (visible in cost.json's per-segment count) → suggest 4–6 instead.
   - **Standard TTS.** If `tts-1-hd` was used → suggest `tts-1` for 50% TTS savings.
   - **`--cache-llm` flag.** If multiple runs of the same notebook are likely → enable LLM cache.
   - **Local LLM.** When v1.3 ships local-Ollama profiles → mention as a future option (not yet shipped — flag as future-work).

6. **Output format.** 5–8 lines of prose, optionally followed by a 3-bullet "what to try next" list.

## What to NOT do

- Do not modify cost.json. It's a record of what already happened.
- Do not invent rates. Use only the rates from the injected table above (they are sourced from `litellm.model_cost`, the same source gencast uses at runtime).
- Do not promise specific savings — predicted savings are heuristic. Always say "approximately" or "around".
- Do not run `gencast generate` automatically. This skill is post-mortem only.
