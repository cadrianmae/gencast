"""Pure formatters for `gencast estimate` output. No I/O."""

from __future__ import annotations

import json
from pathlib import Path

from gencast.pipeline.estimate import Estimate, StageEstimate


_STAGE_LABELS = {
    "extract": "Extract",
    "outline": "Outline",
    "transcript": "Transcript",
    "tts": "TTS",
    "whisper": "Whisper",
}


def _stage_detail(s: StageEstimate) -> str:
    """Compact one-line detail string for the table's middle column."""
    if s.stage == "extract":
        return ""
    if s.stage == "outline":
        return f"{s.model:<24} · {s.input_tokens / 1000:.1f}k in"
    if s.stage == "transcript":
        n_segs = max(1, int(s.output_tokens / (150 * 1.5)))  # invert heuristic
        return f"{s.model:<24} · {n_segs} segs/~{s.output_tokens / 1000:.1f}k"
    if s.stage == "tts":
        return f"{s.provider}/{s.model:<16} · ~{s.characters:,} chars"
    if s.stage == "whisper":
        return f"{s.model:<24} · ~{s.duration_minutes:.1f} min"
    return ""


def format_table(est: Estimate) -> str:
    """Human-readable cost preview. Multi-line string ending with a newline."""
    lines: list[str] = []
    lines.append(f"gencast estimate — {est.notebook_path.name}")
    lines.append("=" * 64)
    src_label = "files" if est.source_tokens > 0 else "no sources"
    lines.append(f"Source:    {est.source_tokens:,} tokens  ({src_label})")
    lines.append("")
    lines.append(f"{'Stage breakdown':<54}{'est. USD':>10}")
    lines.append(f"{'-' * 54}  {'-' * 8}")
    for s in est.stages:
        label = _STAGE_LABELS[s.stage]
        detail = _stage_detail(s)
        usd_col = f"${s.usd:>6.2f}"
        lines.append(f"{label:<12} {detail:<41} {usd_col:>10}")
    lines.append(f"{' ' * 54}  {'-' * 8}")
    lines.append(f"{'Total:':>54}  ${est.total_usd:.2f}")
    lines.append(f"{' ' * 54}  ±{est.uncertainty_pct}%")
    if est.suggestions:
        lines.append("")
        lines.append("Cheaper alternatives")
        for sug in est.suggestions:
            short_alt = sug.alternative.split("/", 1)[1]
            lines.append(
                f"  {sug.stage:<12} {sug.current.split('/', 1)[1]:<24} "
                f"→ {short_alt:<24} saves ~${sug.saves_usd:.2f} (-{sug.saves_pct}%)"
            )
            lines.append(f"  {' ' * 12} ({sug.trade_off} trade-off — see docs)")
    lines.append("")
    return "\n".join(lines)
