---
name: gencast-release-prep
description: This skill should be used when the user asks to "prep a gencast release", "check before tagging", "verify version parity", or "preflight v1.X.Y". Runs a release-readiness checklist that catches the version-drift, schema-mismatch, and stale-test traps that bit prior cutovers.
disable-model-invocation: true
---

# gencast-release-prep

Pre-tag checklist for a gencast release. Catches the failure modes that have surfaced in prior cutovers (v1.0, v1.1, v1.2, v1.2.1):

- **Version drift** — pyproject.toml, .claude-plugin/plugin.json, .claude-plugin/marketplace.json must all agree.
- **Manifest schema mismatch** — plugin.json `author` must be the object form `{name, email}`, not a string. Missed-on-load = silent failure inside Claude Code.
- **Stale CI** — full test suite must pass on the integration branch before tagging.
- **PyPI-side rate-only flag** — v1.2 cost-explain skill depends on `gencast estimate --rates-only --json`. Verify it still works against the smoke fixture.
- **Skill smoke contract** — the gencast CLI commands each SKILL.md depends on must still produce the documented JSON shapes.

## Prerequisites

- Working from the gencast repo root.
- An integration branch checked out (e.g. `v1.3/local-llm` or `main`) with the version bump committed.
- Venv activated.

## Workflow

1. **Run the parity script.**
   ```bash
   bash ${CLAUDE_SKILL_DIR}/scripts/check-version-parity.sh
   ```
   Exits non-zero on any drift between the three version sources. Print the exact diffs to the user.

2. **Run the full test suite.**
   ```bash
   PYTHONPATH=. ./venv/bin/pytest --tb=no -q --no-header 2>&1 | grep -E "^[0-9]+ (passed|failed|error)"
   ```
   Demand all tests passing (5 skipped is expected — they are env-gated). Refuse to proceed if any fail.

3. **Validate the plugin manifest schema.**
   ```bash
   PYTHONPATH=. ./venv/bin/pytest tests/skills/test_plugin_manifest.py -v
   ```
   All 4 tests must pass. The `author` schema check lives in this file — that catches the "string instead of object" trap.

4. **Smoke-check skill-dependent CLI commands.**
   ```bash
   PYTHONPATH=. ./venv/bin/pytest tests/skills/test_skill_smoke.py -v
   ```
   All 5 tests must pass (gencast --version + the per-skill CLI dependency contracts).

5. **Spot-check `gencast estimate --rates-only --json`.**
   ```bash
   ./venv/bin/gencast estimate --rates-only --json | python3 -m json.tool | head -10
   ```
   Should print a JSON dict keyed by `provider/model` with `input_per_1k` + `output_per_1k`. If empty or errored, the v1.2 cost-explain skill is broken.

6. **Show the release checklist.** If everything above passed, print the cutover ceremony for the user to run:
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z — <short-description>

   <release notes>
   "
   git push origin <branch>
   git push origin vX.Y.Z
   # release.yml fires → wait for PyPI propagation → gh release create
   ```

   Do NOT execute the cutover commands automatically — the user opts in by running them manually.

## What to NOT do

- Do not modify any files. This is read-only verification.
- Do not push, tag, or create releases automatically. The user runs those after seeing the green checks.
- Do not skip a check because "it usually passes". The whole point of this skill is the previous cutover bugs that "usually passed" too.
