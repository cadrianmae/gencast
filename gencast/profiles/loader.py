"""3-level profile cascade resolver: project > XDG > bundled."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Type, cast

import yaml
from pydantic import BaseModel

from .schemas import EpisodeProfile, RoomProfile, SpeakerProfile

ProfileKind = Literal["speakers", "episodes", "rooms"]

_KIND_TO_MODEL: dict[str, Type[BaseModel]] = {
    "speakers": SpeakerProfile,
    "episodes": EpisodeProfile,
    "rooms": RoomProfile,
}

# The bundled directory ships with the package.
_BUNDLED_ROOT = Path(__file__).parent / "bundled"


class ProfileNotFoundError(LookupError):
    def __init__(self, kind: str, name: str, paths_searched: list[Path]):
        self.kind = kind
        self.name = name
        self.paths_searched = paths_searched
        joined = "\n  ".join(str(p) for p in paths_searched)
        super().__init__(
            f"Profile '{name}' (kind: {kind}) not found. Searched:\n  {joined}"
        )


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))


def _candidate_paths(kind: ProfileKind, name: str) -> list[Path]:
    return [
        Path.cwd() / "gencast" / "profiles" / kind / f"{name}.yaml",
        _xdg_config_home() / "gencast" / "profiles" / kind / f"{name}.yaml",
        _BUNDLED_ROOT / kind / f"{name}.yaml",
    ]


def resolve_profile_path(kind: ProfileKind, name: str) -> Path:
    """Return first existing path for the named profile, or raise."""
    candidates = _candidate_paths(kind, name)
    for p in candidates:
        if p.is_file():
            return p
    raise ProfileNotFoundError(kind, name, candidates)


def load_profile(kind: ProfileKind, name: str) -> SpeakerProfile | EpisodeProfile | RoomProfile:
    """Load and validate a profile by name through the cascade."""
    path = resolve_profile_path(kind, name)
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    model = _KIND_TO_MODEL[kind]
    # Cast: _KIND_TO_MODEL maps each kind to exactly one of the union members.
    return cast("SpeakerProfile | EpisodeProfile | RoomProfile", model(**data))


def _scan_dir(d: Path) -> set[str]:
    """Return profile names (file stems) that look like .yaml files in d."""
    if not d.is_dir():
        return set()
    return {p.stem for p in d.glob("*.yaml")}


def list_profile_names(kind: ProfileKind) -> list[str]:
    """Names from all 3 levels, deduplicated, sorted."""
    proj = Path.cwd() / "gencast" / "profiles" / kind
    xdg = _xdg_config_home() / "gencast" / "profiles" / kind
    bundled = _BUNDLED_ROOT / kind
    return sorted(_scan_dir(proj) | _scan_dir(xdg) | _scan_dir(bundled))


def origin_marker(kind: ProfileKind, name: str) -> str:
    """Return 'project' / 'user' / 'bundled' for where the named profile is loaded from."""
    proj, xdg, bundled = _candidate_paths(kind, name)
    if proj.is_file():
        return "project"
    if xdg.is_file():
        return "user"
    if bundled.is_file():
        return "bundled"
    raise ProfileNotFoundError(kind, name, [proj, xdg, bundled])
