"""Reporter facade — Plain (Plan A) + Rich (Plan C). Plan A ships only Plain."""

from __future__ import annotations

import sys
import time
from abc import ABC, abstractmethod


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
    """Stderr text reporter for non-interactive contexts (CI, pipes, redirects)."""

    def __init__(self, verbosity: int = 1):
        self.verbosity = verbosity  # 0=silent, 1=info, 2=debug

    def _ts(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _emit(self, level: str, msg: str) -> None:
        sys.stderr.write(f"{self._ts()} [{level}] {msg}\n")
        sys.stderr.flush()

    def stage_start(self, n: int, total: int, name: str, total_items: int | None = None) -> None:
        if self.verbosity >= 1:
            self._emit("INFO", f"Stage {n}/{total} {name}")

    def stage_activity(self, line: str) -> None:
        if self.verbosity >= 2:
            self._emit("DEBUG", line)

    def stage_advance(self, items: int = 1) -> None:
        pass  # Plain reporter doesn't track inner progress

    def stage_done(self) -> None:
        pass

    def info(self, msg: str) -> None:
        if self.verbosity >= 1:
            self._emit("INFO", msg)

    def debug(self, msg: str) -> None:
        if self.verbosity >= 2:
            self._emit("DEBUG", msg)

    def warn(self, msg: str) -> None:
        if self.verbosity >= 0:
            self._emit("WARN", msg)

    def error(self, msg: str) -> None:
        # Errors always emit
        self._emit("ERROR", msg)


def make_reporter(verbosity: int = 1) -> Reporter:
    """Pick a Reporter implementation. Plan C will expand this for RichReporter."""
    return PlainReporter(verbosity=verbosity)
