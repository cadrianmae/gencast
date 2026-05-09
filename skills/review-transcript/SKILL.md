---
name: gencast-review-transcript
description: This skill should be used when the user asks to "review this gencast transcript", "is this transcript good", "check the dialogue in transcript.json", or wants a per-segment quality review of a gencast-generated transcript. Advisory only — flags awkward phrasings, factual contradictions against source material, and flow problems. Does not auto-regenerate audio in v1.2.
---

# gencast review-transcript

Review a gencast `transcript.json` for quality issues — awkward phrasings, factual claims that contradict source material, and flow problems between segments. Advisory only: surfaces what needs manual fixing or which segments to regenerate by hand. Auto-regeneration is deferred to a future gencast version that adds `--segments X,Y` to the generate command.

## Prerequisites

- A `transcript.json` file produced by `gencast generate`. Located at `<output_dir>/<notebook_name>.transcript.json`.
- Optionally, the original source files the notebook was built from (for fact-checking).
- `gencast>=1.2.0` available — version check: !`gencast --version 2>/dev/null || echo "MISSING"`

## Workflow

1. **Locate transcript.** Read the user-named `transcript.json`. Validate it has the expected schema:
   - Top-level `segments: [...]`
   - Each segment: `{speaker: str, text: str, start_ms: int, end_ms: int}` (or compatible)
   If the schema does not match, stop and tell the user this does not look like a gencast transcript.

2. **For each segment, scan for these issues:**

   **Awkward phrasings (severity: low):**
   - Repeated openers across segments ("So, let's talk about...", "Right, so...")
   - "As an AI..." or other meta-disclosures
   - Filler words clustered ("um, uh, well, you know")
   - Sentence fragments mid-segment

   **Factual contradictions (severity: high):**
   Only if user provides source paths. Quote a claim, then check whether it appears (or is contradicted) in any source file. Flag mismatches; do not flag novel paraphrasing.

   **Flow problems (severity: medium):**
   - Jarring topic shifts between segments (segment N ends on Topic A, segment N+1 opens on unrelated Topic B with no transition)
   - Missing transitions ("And speaking of X..." would help)
   - Same speaker for >3 consecutive segments (gencast usually alternates)

3. **For long transcripts (>30 segments), chunk the review** into groups of 10 segments. Report each chunk separately so the user can act on partial results without waiting for the whole review.

4. **Output format.**

   ```
   Segment N (HOST1, 23s): [text snippet]
     - [low] repeated opener "So, let's talk about" — appears in segments N-2, N-4
     - [high] factual: claim "X happened in 1992" but source 2 says 1989
     - [medium] flow: jarring shift from photosynthesis (seg N-1) to mitochondria
   ```

   At the end, summary block:
   ```
   Summary: 12 segments, 4 issues (1 high, 2 medium, 1 low)
   Suggested manual edits: segments 3, 7, 8
   Suggested regeneration candidates: segment 7 (factual)
   ```

5. **What to recommend at the end:**
   - For low-severity issues: "you can fix these by editing the transcript and re-running TTS only — see future-work in gencast docs"
   - For high/medium issues: "consider re-running `gencast generate` with adjusted briefing or a different episode profile, OR wait for `gencast generate --segments X,Y` (planned)"

## What to NOT do

- **Do not auto-regenerate.** v1.2 of gencast does not have `--segments X,Y`. Suggesting it would mislead the user. Be explicit that this is advisory.
- Do not modify the transcript file in place. Output suggestions; let the user edit.
- Do not flag every "uh" — clusters only.
- Do not invent factual claims to check. Only check claims actually present in the transcript text.
