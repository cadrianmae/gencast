# gencast

Generate conversational podcasts from documents using AI.

> **v1.0 — currently in active rewrite. The `rewrite/v1.0` branch is the
> source of truth. The published `gencast` 0.6.x on PyPI predates this
> design and is being replaced.**

## What works (Plan A — current branch state)

- `gencast list-profiles` — list all bundled + user-installed profiles
- `gencast preview NB.yaml` — render outline only (no transcript, no audio)

## What's coming

- Plan B: per-segment transcript, TTS, spatial audio, M4A output with embedded subtitles
- Plan C: full CLI UX (init wizard, Rich progress UI), edge cases (map-reduce, re-subtitling), tests + CI

See `docs/superpowers/specs/2026-05-07-gencast-v1-rewrite-design.md` for the full design.

## Install (development)

```bash
python -m venv venv
source venv/bin/activate
pip install -e .[test,dev]
```

## Try it

```bash
# List bundled profiles
gencast list-profiles

# Outline a tiny notebook
echo "Some content." > lecture.md
cat > nb.yaml <<EOF
title: My first podcast
sources: [lecture.md]
EOF
gencast preview nb.yaml
```

## Tests

```bash
pytest tests/unit                    # fast, no API calls
pytest tests/component               # vcrpy cassettes — no API keys needed once recorded
GENCAST_TEST_E2E=1 pytest tests/e2e  # real API calls, costs a few cents
```

## License

MIT
