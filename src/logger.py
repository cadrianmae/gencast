"""Logging configuration for gencast CLI.

Provides verbosity control with three levels:
- silent (0): Errors only
- minimal (1): Milestones + warnings + errors
- normal (2): All output including progress indicators
"""

import logging
import sys

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
    """Configure logger based on verbosity level.

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

    # Simple formatter (no timestamps, just message)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    """Get the gencast logger instance."""
    return logging.getLogger("gencast")
