---
name: gencast-source-check
description: This skill should be used when the user asks to "check these sources for a podcast", "are these sources good for gencast", "preflight my notebook before generating", or wants a quality + cost review of source material before running `gencast generate`. Reports token counts, predicted USD cost via `gencast estimate`, and topical coherence read.
---

# gencast source-check

Preflight a gencast notebook (or candidate source files) before spending money. Reports source-token counts, predicted cost, fits-in-budget verdict, and a subjective topical-coherence read. Identifies opportunities to split the notebook, summarise first, or pick a cheaper model.

## Available episode profiles

```!
gencast list-profiles --type episodes --json 2>/dev/null | jq -r '.[] | "- **\(.name)**: \(.description // "(no description)")"' || echo "(gencast not installed)"
```

Version check (need `gencast>=1.2.0`): !`gencast --version 2>/dev/null | python3 -c "import sys,re; v=sys.stdin.read().strip(); m=re.search(r'(\d+)\.(\d+)', v); sys.exit(1) if not v else print(v if m and (int(m[1]),int(m[2]))>=(1,2) else f'TOO OLD: need gencast>=1.2.0, found {v} — run: pipx upgrade gencast')" 2>/dev/null || echo "MISSING — install with: pipx install gencast"`

## Prerequisites

- `gencast>=1.2.0` on `PATH`
- Either an existing `notebook.yaml`, OR a list of candidate source files the user wants to evaluate.

## Workflow

1. **Identify the input.** If the user gave a `notebook.yaml`, use it directly. If the user only named source files, scaffold a minimal notebook in a temp file (using bundled defaults) so `gencast estimate` has something to operate on. Do not prompt the user for profiles in this case — defaults are fine for a preflight.

2. **Run `gencast estimate`.**

   ```bash
   gencast estimate <NB.yaml> --json
   ```

   Parse the JSON output: `total_usd`, per-stage breakdown, `source_tokens`, `suggestions`.

3. **Read the source content.** For each source file, read the actual text (~first 2,000 chars is enough for a coherence read). Do not load entire large PDFs.

4. **Report findings in this order:**

   - **Cost verdict.** "$X estimated (±25%). Fits within typical $0.10–$0.50 range." OR "expensive — $Y; consider cheaper outline model."
   - **Token verdict.** "Source is N tokens; well within budget." OR "Source exceeds budget — gencast will run map-reduce summarisation first (adds cost)."
   - **Coherence.** Subjective read — "all three sources are about Topic X" or "source 2 is off-topic, consider splitting".
   - **Suggestions.** Surface any `suggestions` from the estimate JSON (cheaper-model swaps), and add the user's own based on coherence (split into multiple notebooks, summarise first, etc.).

5. **Output format.** Plain-language summary in 5–8 lines. No tables unless the user asks.

## What to NOT do

- Do not run `gencast generate`. This skill is preflight only.
- Do not edit the user's notebook. Suggestions are advisory.
- Do not load entire PDF binaries — use the first ~2,000 chars per source for the coherence read.
- Do not re-run `gencast estimate` multiple times. One call per notebook.
