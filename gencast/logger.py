"""Reporter facade — Plain (Plan A) + Rich (Plan C). Plan A ships only Plain."""

from __future__ import annotations

import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
    from rich.text import Text
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

    # Optional log sink — when set, every reporter event is also appended to
    # this path. Used for session log persistence.
    def set_log_sink(self, path: Path) -> None:
        self._log_sink_path: Path | None = path

    def _sink(self, line: str) -> None:
        path = getattr(self, "_log_sink_path", None)
        if path is None:
            return
        try:
            with open(path, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass  # logging shouldn't crash the pipeline

    # Streaming preview API — no-ops in non-TTY contexts.
    def stream_open(self, title: str, mode: str = "rolling", max_lines: int = 5) -> None:
        """Open a streaming preview window. mode='full' shows everything (for outline);
        mode='rolling' shows the last N lines (for per-segment transcript)."""
        pass

    def stream_chunk(self, text: str) -> None:
        """Append a chunk of streamed text to the open preview window."""
        pass

    def stream_close(self) -> None:
        """Close the streaming preview window."""
        pass


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
        line = f"{self._ts()} [{level}] {msg}"
        sys.stderr.write(line + "\n")
        sys.stderr.flush()
        self._sink(line)

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
    """Borderless Live display: progress bar, activity line, optional stream preview."""

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
        # Stream preview state
        self._stream_title: str = ""
        self._stream_mode: str = "rolling"  # "full" | "rolling"
        self._stream_max_lines: int = 5
        self._stream_buffer: str = ""  # full-mode accumulator
        self._stream_lines: list[str] = []  # rolling-mode buffer
        self._stream_active: bool = False

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
        self._live = Live(self._render(), console=self._console, refresh_per_second=10)
        self._live.start()

    def _render(self):
        # Borderless: just a Group of renderables, no Panel wrapping.
        if self._progress is None:
            return Text("starting...", style="dim")
        parts: list = [self._progress]
        if self._latest_activity:
            parts.append(Text(f"  {self._latest_activity}", style="dim"))
        if self._stream_active:
            parts.append(Text(f"  {self._stream_title}", style="bold dim"))
            parts.append(Text(self._stream_render(), style="dim"))
        return Group(*parts)

    def _stream_render(self) -> str:
        """Format the stream preview content per current mode."""
        if self._stream_mode == "full":
            return "  " + self._stream_buffer.replace("\n", "\n  ")
        # rolling
        display = self._stream_lines[-self._stream_max_lines:]
        if not display:
            return ""
        return "  " + "\n  ".join(display)

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
        self._sink(f"[stage_start] {n}/{total} {name}"
                   + (f" ({total_items} items)" if total_items else ""))

    def stage_activity(self, line: str) -> None:
        self._latest_activity = line
        self._refresh()
        self._sink(f"[stage_activity] {line}")

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
        self._sink(f"[INFO] {msg}")

    def debug(self, msg: str) -> None:
        # debug() only emits at full debug level (3)
        if self.verbosity >= 3:
            self._info_buffer.append(f"[DEBUG] {msg}")
        self._sink(f"[DEBUG] {msg}")

    def warn(self, msg: str) -> None:
        if self.verbosity >= 0:
            self._info_buffer.append(f"[WARN] {msg}")
        self._sink(f"[WARN] {msg}")

    def error(self, msg: str) -> None:
        # Errors always emit regardless of verbosity
        self._info_buffer.append(f"[ERROR] {msg}")
        self._sink(f"[ERROR] {msg}")

    def close(self) -> None:
        """Tear down the Live display. Call at end of pipeline run."""
        if self._live is not None:
            self._live.stop()
            self._live = None

    # Streaming preview implementation
    def stream_open(self, title: str, mode: str = "rolling", max_lines: int = 5) -> None:
        self._stream_title = title
        self._stream_mode = mode
        self._stream_max_lines = max_lines
        self._stream_buffer = ""
        self._stream_lines = []
        self._stream_active = True
        self._refresh()

    def stream_chunk(self, text: str) -> None:
        if not self._stream_active:
            return
        if self._stream_mode == "full":
            self._stream_buffer += text
        else:
            # rolling — split incoming text on newlines, append to line buffer
            pending = (self._stream_lines.pop() if self._stream_lines else "") + text
            *complete, partial = pending.split("\n")
            self._stream_lines.extend(complete)
            self._stream_lines.append(partial)
        self._refresh()

    def stream_close(self) -> None:
        self._stream_active = False
        self._stream_buffer = ""
        self._stream_lines = []
        self._refresh()


def make_reporter(verbosity: int = 1) -> Reporter:
    """Pick a Reporter implementation. Rich on TTY, Plain otherwise."""
    if RICH_AVAILABLE and sys.stdout.isatty():
        return RichReporter(verbosity=verbosity)
    return PlainReporter(verbosity=verbosity)
