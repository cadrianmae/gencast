"""RichReporter state tests — does not assert on visual output."""

from __future__ import annotations

from gencast.logger import RichReporter


def test_rich_reporter_records_stage_state():
    r = RichReporter(verbosity=1)
    r.stage_start(1, 10, "Resolve", total_items=None)
    assert r._current_stage_index == 1
    assert r._current_stage_total == 10
    assert r._current_stage_name == "Resolve"
    r.stage_done()
    assert r._current_stage_index == 1  # last seen, not reset


def test_rich_reporter_advance_increments():
    r = RichReporter(verbosity=1)
    r.stage_start(1, 10, "Audio", total_items=5)
    r.stage_advance(items=2)
    assert r._items_done == 2
    r.stage_advance(items=3)
    assert r._items_done == 5


def test_rich_reporter_activity_records():
    r = RichReporter(verbosity=1)
    r.stage_start(2, 10, "Outline")
    r.stage_activity("[claude-haiku-4-5] generating outline...")
    assert "claude-haiku-4-5" in r._latest_activity


def test_rich_reporter_log_levels_respect_verbosity():
    r = RichReporter(verbosity=0)
    r.info("hidden")
    assert r._info_buffer == []  # info is suppressed at v=0

    # debug() only emits at verbosity 3 (--debug / -vv)
    r2 = RichReporter(verbosity=2)
    r2.debug("hidden at verbose")
    assert r2._info_buffer == []  # debug still hidden at -v (verbosity 2)

    r3 = RichReporter(verbosity=3)
    r3.debug("visible at debug")
    assert "visible at debug" in r3._info_buffer[-1]


def test_make_reporter_picks_rich_on_tty(monkeypatch):
    """make_reporter switches to RichReporter when stdout is a TTY."""
    import gencast.logger as L

    monkeypatch.setattr(L.sys.stdout, "isatty", lambda: True)
    r = L.make_reporter(verbosity=1)
    assert isinstance(r, RichReporter)


def test_make_reporter_picks_plain_when_not_tty(monkeypatch):
    import gencast.logger as L

    monkeypatch.setattr(L.sys.stdout, "isatty", lambda: False)
    r = L.make_reporter(verbosity=1)
    assert r.__class__.__name__ == "PlainReporter"
