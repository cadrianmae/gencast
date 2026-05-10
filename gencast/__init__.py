"""gencast — generate conversational podcasts from documents."""
from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("gencast")
except PackageNotFoundError:
    # Source checkout without an editable install — fall back to a sentinel so
    # `gencast --version` still returns *something* parseable.
    __version__ = "0.0.0+source"

__all__ = ["__version__"]
