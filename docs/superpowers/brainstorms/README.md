# Brainstorm visual companions — curated archive

These HTML mockups were produced by the `superpowers:brainstorming` skill's visual companion during early-design exploration. The skill treats them as ephemeral aids by default; they are preserved here when they document *why* a non-obvious design decision was made.

## What's here

### Pipeline architecture

- **`2026-05-07-pipeline-overview.html`** — early visualisation of the v1.0 pipeline stages (extract → outline → transcript → audio → subtitles). Captures the data flow before it was implemented in `gencast/pipeline/`.

### Spatial-audio room geometry

The `room` profile YAMLs (`gencast/profiles/bundled/rooms/*.yaml`) carry parameters like `arc_deg`, `itd_max_ms`, `table_radius_m`, `reverb_t60_s` whose specific values came from picking among visual iterations. These four files are the design evolution:

- **`2026-05-07-round-table-geometries-v1.html`** — initial exploration of speaker layouts (front-back, left-right, side-by-side, round-table)
- **`2026-05-07-round-table-geometries-v2.html`** — refined exploration with arc-degree variations
- **`2026-05-07-round-table-v2.html`** — round-table with adjustable spread + per-speaker positioning
- **`2026-05-07-round-table-mix.html`** — first mix combining geometry + ITD + room reverb
- **`2026-05-07-round-table-mix-v2.html`** — final iteration that informed the bundled `small-room` profile defaults

## Why these and not others?

The brainstorming skill's default is to leave visual companions in `.superpowers/` (gitignored). Two heuristics for migrating:

1. **The visual is the only record of why a numeric parameter has its specific value.** Specs document intent; mockups document the visual reasoning that picked the number.
2. **The visual would help a future reader who asks "why is the schema shaped like this?"** Code shows the *what*; brainstorm visuals show the *why*.

Future raw brainstorm sessions auto-land in `.superpowers/` and stay gitignored. Only artefacts that meet the heuristics above should be migrated here.

## Viewing

These are static HTML files — open directly in a browser:

```bash
xdg-open docs/superpowers/brainstorms/2026-05-07-round-table-mix-v2.html
```
