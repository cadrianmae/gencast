"""Logging configuration for gencast CLI.

Provides verbosity control with three levels:
- silent (0): Errors only
- minimal (1): Milestones + warnings + errors
- normal (2): All output including progress indicators

Color scheme:
- Errors: red
- Warnings: yellow
- Info: white (default)
- Milestones: blue
- Metrics: cyan (tokens), green (costs)
"""

import logging
import sys

try:
    from rich.console import Console
    from rich.logging import RichHandler
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Custom log level for milestones (between INFO=20 and WARNING=30)
MILESTONE = 25
logging.addLevelName(MILESTONE, "MILESTONE")


def milestone(self, message, *args, **kwargs):
    """Log a milestone message (Step 1/3, etc.)."""
    if self.isEnabledFor(MILESTONE):
        self._log(MILESTONE, message, args, **kwargs)


# Add milestone method to Logger class
logging.Logger.milestone = milestone


def setup_logger(verbosity: int = 2) -> logging.Logger:
    """Configure logger based on verbosity level with Rich colors.

    Args:
        verbosity: 0=silent, 1=minimal, 2=normal

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("gencast")

    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()

    # Map verbosity to log level
    if verbosity == 0:
        level = logging.ERROR
    elif verbosity == 1:
        level = MILESTONE
    else:
        level = logging.INFO

    logger.setLevel(level)

    if RICH_AVAILABLE:
        # Use Rich handler for colored output
        console = Console(stderr=False, force_terminal=True)

        # Custom formatter that adds colors based on log level
        class ColoredFormatter(logging.Formatter):
            def format(self, record):
                msg = super().format(record)
                # Apply colors based on log level
                if record.levelno >= logging.ERROR:
                    return f"[red]{msg}[/red]"
                elif record.levelno >= logging.WARNING:
                    return f"[yellow]{msg}[/yellow]"
                elif record.levelno >= MILESTONE:
                    return f"[blue]{msg}[/blue]"
                else:  # INFO and below
                    return msg  # white (default)

        handler = RichHandler(
            console=console,
            show_time=False,
            show_path=False,
            show_level=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=False
        )
        handler.setFormatter(ColoredFormatter("%(message)s"))
    else:
        # Fallback to simple handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    """Get the gencast logger instance."""
    return logging.getLogger("gencast")


# Color helper functions for inline formatting (metrics only)
# Log level colors (error=red, warning=yellow, milestone=blue, info=white)
# are handled automatically by ColoredFormatter above
def color_metric(text: str) -> str:
    """Color text cyan for metrics (token counts)."""
    return f"[cyan]{text}[/cyan]" if RICH_AVAILABLE else text


def color_cost(text: str) -> str:
    """Color text green for cost values."""
    return f"[green]{text}[/green]" if RICH_AVAILABLE else text
