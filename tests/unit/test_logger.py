import sys
from gencast.logger import Reporter, PlainReporter, make_reporter


def test_make_reporter_returns_plain():
    r = make_reporter(verbosity=1)
    assert isinstance(r, PlainReporter)


def test_plain_reporter_info_writes_to_stderr(capsys):
    r = PlainReporter(verbosity=1)
    r.info("hello")
    out = capsys.readouterr()
    assert "hello" in out.err


def test_plain_reporter_silent_suppresses_info(capsys):
    r = PlainReporter(verbosity=0)
    r.info("hello")
    out = capsys.readouterr()
    assert "hello" not in out.err


def test_plain_reporter_error_always_emits(capsys):
    r = PlainReporter(verbosity=0)
    r.error("boom")
    out = capsys.readouterr()
    assert "boom" in out.err


def test_plain_reporter_stage_lines(capsys):
    r = PlainReporter(verbosity=1)
    r.stage_start(1, 10, "extract")
    r.stage_activity("Reading a.md")
    r.stage_done()
    out = capsys.readouterr()
    assert "1/10" in out.err
    assert "extract" in out.err


def test_plain_reporter_silent_suppresses_warn(capsys):
    """Silent verbosity (-1) suppresses warnings; only errors emit."""
    r = PlainReporter(verbosity=-1)
    r.warn("important warning")
    out = capsys.readouterr()
    assert "important warning" not in out.err
