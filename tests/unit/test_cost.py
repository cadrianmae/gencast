import pytest
from gencast.cost import CostMeter, StageCost


def test_cost_meter_starts_empty():
    cm = CostMeter()
    assert cm.total_usd == 0.0
    assert cm.stages == {}


def test_record_llm_stage():
    cm = CostMeter()
    cm.record_llm("outline", model="claude-haiku-4.5",
                  tokens_in=5000, tokens_out=600,
                  cache_reads_in=0, cache_writes_in=0,
                  usd=0.005)
    assert cm.total_usd == pytest.approx(0.005)
    assert "outline" in cm.stages
    assert cm.stages["outline"].tokens_in == 5000


def test_record_tts_stage():
    cm = CostMeter()
    cm.record_tts("tts", backend="openai", model="tts-1-hd",
                  audio_seconds=720, usd=0.058)
    assert cm.stages["tts"].audio_seconds == 720
    assert cm.total_usd == pytest.approx(0.058)


def test_record_multiple_calls_same_stage_accumulates():
    cm = CostMeter()
    for _ in range(6):
        cm.record_llm("transcript", model="claude-sonnet-4",
                      tokens_in=5000, tokens_out=700,
                      cache_reads_in=4500, cache_writes_in=0,
                      usd=0.019)
    assert cm.stages["transcript"].tokens_in == 30000
    assert cm.stages["transcript"].cache_reads_in == 27000
    assert cm.total_usd == pytest.approx(0.114)


def test_to_dict_format():
    cm = CostMeter()
    cm.record_llm("outline", model="m", tokens_in=1, tokens_out=1,
                  cache_reads_in=0, cache_writes_in=0, usd=0.01)
    d = cm.to_dict()
    assert d["total_usd"] == pytest.approx(0.01)
    assert d["stages"]["outline"]["tokens_in"] == 1


def test_stage_kind_mismatch_raises():
    """Reusing a stage name with a different kind raises ValueError."""
    cm = CostMeter()
    cm.record_llm("foo", model="m", tokens_in=1, tokens_out=1, usd=0.01)
    with pytest.raises(ValueError, match="kind"):
        cm.record_tts("foo", backend="b", model="m", audio_seconds=1.0, usd=0.01)
