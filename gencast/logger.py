"""Reporter facade — Plain (Plan A) + Rich (Plan C). Plan A ships only Plain."""

from __future__ import annotations

import sys
import time
from abc import ABC, abstractmethod
from typing import Optional

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class Reporter(ABC):
    """Abstract reporter interface — same surface for Rich and Plain implementations."""

    @abstractmethod
    def stage_start(self, n: int, total: int, name: str, total_items: int | None = None) -> None: ...

    @abstractmethod
    def stage_activity(self, line: str) -> None: ...

    @abstractmethod
    def stage_advance(self, items: int = 1) -> None: ...

    @abstractmethod
    def stage_done(self) -> None: ...

    @abstractmethod
    def info(self, msg: str) -> None: ...

    @abstractmethod
    def debug(self, msg: str) -> None: ...

    @abstractmethod
    def warn(self, msg: str) -> None: ...

    @abstractmethod
    def error(self, msg: str) -> None: ...


class PlainReporter(Reporter):
    """Stderr text reporter for non-interactive contexts (CI, pipes, redirects).

    Verbosity ladder:
      -1  -- errors only (--silent)
       0  -- warnings + errors (-q/--quiet)
       1  -- INFO + WARN + ERROR (default)
       2  -- adds stage_activity / VERBOSE lines (-v/--verbose)
       3  -- full DEBUG (-vv/--debug)
    """

    def __init__(self, verbosity: int = 1):
        self.verbosity = verbosity

    def _ts(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _emit(self, level: str, msg: str) -> None:
        sys.stderr.write(f"{self._ts()} [{level}] {msg}\n")
        sys.stderr.flush()

    def stage_start(self, n: int, total: int, name: str, total_items: int | None = None) -> None:
        if self.verbosity >= 1:
            self._emit("INFO", f"Stage {n}/{total} {name}")

    def stage_activity(self, line: str) -> None:
        # stage_activity emits at verbose (2) and above
        if self.verbosity >= 2:
            self._emit("VERBOSE", line)

    def stage_advance(self, items: int = 1) -> None:
        pass  # Plain reporter doesn't track inner progress

    def stage_done(self) -> None:
        pass

    def info(self, msg: str) -> None:
        if self.verbosity >= 1:
            self._emit("INFO", msg)

    def debug(self, msg: str) -> None:
        # debug() only emits at full debug level (3)
        if self.verbosity >= 3:
            self._emit("DEBUG", msg)

    def warn(self, msg: str) -> None:
        if self.verbosity >= 0:
            self._emit("WARN", msg)

    def error(self, msg: str) -> None:
        # Errors always emit regardless of verbosity
        self._emit("ERROR", msg)


class RichReporter(Reporter):
    """Two-band Live display: progress bar on top, current activity below."""

    def __init__(self, verbosity: int = 1):
        if not RICH_AVAILABLE:
            raise RuntimeError("Rich is not installed; install gencast[all] or use PlainReporter")
        self.verbosity = verbosity
        self._console = Console(force_terminal=True)
        self._current_stage_index = 0
        self._current_stage_total = 0
        self._current_stage_name = ""
        self._items_total: Optional[int] = None
        self._items_done = 0
        self._latest_activity = ""
        self._info_buffer: list[str] = []
        self._progress: Optional[Progress] = None
        self._task_id = None
        self._live: Optional[Live] = None

    def _ensure_live(self) -> None:
        if self._live is not None:
            return
        self._progress = Progress(
            TextColumn("  [{task.fields[stage]}] {task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=self._console,
        )
        self._live = Live(self._render(), console=self._console, refresh_per_second=4)
        self._live.start()

    def _render(self) -> Panel:
        if self._progress is None:
            return Panel("starting...", border_style="cyan")
        return Panel(
            f"{self._progress}\n\n  {self._latest_activity}",
            title=f"gencast",
            border_style="cyan",
        )

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render())

    def stage_start(self, n: int, total: int, name: str, total_items: Optional[int] = None) -> None:
        self._ensure_live()
        self._current_stage_index = n
        self._current_stage_total = total
        self._current_stage_name = name
        self._items_total = total_items
        self._items_done = 0
        self._latest_activity = ""
        if self._progress is not None:
            if self._task_id is not None:
                self._progress.remove_task(self._task_id)
            self._task_id = self._progress.add_task(
                description=name,
                total=total_items if total_items is not None else 1,
                stage=f"{n}/{total}",
            )
        self._refresh()

    def stage_activity(self, line: str) -> None:
        self._latest_activity = line
        self._refresh()

    def stage_advance(self, items: int = 1) -> None:
        self._items_done += items
        if self._progress is not None and self._task_id is not None and self._items_total is not None:
            self._progress.advance(self._task_id, items)
        self._refresh()

    def stage_done(self) -> None:
        if self._progress is not None and self._task_id is not None and self._items_total is not None:
            self._progress.update(self._task_id, completed=self._items_total)
        self._refresh()

    def info(self, msg: str) -> None:
        if self.verbosity >= 1:
            self._info_buffer.append(f"[INFO] {msg}")

    def debug(self, msg: str) -> None:
        # debug() only emits at full debug level (3)
        if self.verbosity >= 3:
            self._info_buffer.append(f"[DEBUG] {msg}")

    def warn(self, msg: str) -> None:
        if self.verbosity >= 0:
            self._info_buffer.append(f"[WARN] {msg}")

    def error(self, msg: str) -> None:
        # Errors always emit regardless of verbosity
        self._info_buffer.append(f"[ERROR] {msg}")

    def close(self) -> None:
        """Tear down the Live display. Call at end of pipeline run."""
        if self._live is not None:
            self._live.stop()
            self._live = None


def make_reporter(verbosity: int = 1) -> Reporter:
    """Pick a Reporter implementation. Rich on TTY, Plain otherwise."""
    if RICH_AVAILABLE and sys.stdout.isatty():
        return RichReporter(verbosity=verbosity)
    return PlainReporter(verbosity=verbosity)
