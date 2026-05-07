# gencast v1.0 — Plan A: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1.0 foundation — a fresh `gencast/` package replacing the old `src/` + `gencast.py` module, providing profile schemas (speakers/episodes/rooms), notebook YAML loading, the 3-level cascade resolver, the LLM wrapper, and the outline pipeline stage. End state: `gencast list-profiles` and `gencast preview NB.yaml` both work.

**Architecture:** Package-by-feature layout. Pydantic for schemas (strict for notebook, `extra="ignore"` for profiles for forward-compat). LiteLLM wraps multi-provider chat completions. Jinja for prompt rendering. Click for CLI.

**Tech Stack:** Python 3.10+, pydantic v2, pyyaml, litellm, jinja2, click, rich, pytest.

**Branch:** `rewrite/v1.0` (already cut). Old `src/` and `gencast.py` are removed in Task 1; the rest of this plan builds the new `gencast/` package from scratch.

**Spec reference:** `docs/superpowers/specs/2026-05-07-gencast-v1-rewrite-design.md` — sections 1, 2, 4, 7.8 are most relevant to this plan.

---

## File Structure (Plan A)

| Path | Created/Modified | Responsibility |
|---|---|---|
| `pyproject.toml` | Modified | Single source of truth for deps; remove `py-modules`, switch to package config |
| `requirements.txt` | Deleted | Consolidated into pyproject.toml |
| `src/` | Deleted | Replaced by `gencast/` package |
| `gencast.py` | Deleted | Replaced by `gencast/__init__.py` + `gencast/cli/main.py` |
| `prompts/` (top level) | Deleted | Replaced by `gencast/prompts/` |
| `audiences/` | Deleted | Folded into bundled episode profiles |
| `gencast/__init__.py` | Created | Package marker + `__version__`. The public `generate_podcast()` lands in Plan B. |
| `gencast/cli/__init__.py` | Created | Empty package marker |
| `gencast/cli/main.py` | Created | Click root + `list-profiles` + `preview` commands |
| `gencast/profiles/__init__.py` | Created | Re-exports loader + schemas |
| `gencast/profiles/schemas.py` | Created | Pydantic: Avatar, Speaker, SpeakerProfile, EpisodeProfile, RoomProfile |
| `gencast/profiles/loader.py` | Created | 3-level cascade resolver |
| `gencast/profiles/bundled/speakers/*.yaml` | Created | 4 starter speaker profiles |
| `gencast/profiles/bundled/episodes/*.yaml` | Created | 4 starter episode profiles |
| `gencast/profiles/bundled/rooms/*.yaml` | Created | 8 room profiles (locked from harness work) |
| `gencast/notebook.py` | Created | Pydantic Notebook + NotebookOutput + NotebookOverrides schemas + YAML loader |
| `gencast/llm/__init__.py` | Created | LiteLLM wrapper with retry policy + cost tracking |
| `gencast/cost.py` | Created | CostMeter dataclass (per-stage accumulator) |
| `gencast/logger.py` | Created | Reporter facade (Rich + Plain) — minimal version for Phase 0/1 |
| `gencast/prompts/outline.jinja` | Created | Outline pass prompt template |
| `gencast/pipeline/__init__.py` | Created | PodcastState dataclass |
| `gencast/pipeline/extract.py` | Created | md/text extraction with token counting |
| `gencast/pipeline/preflight.py` | Created | Token-budget check (preflight only; map-reduce in Plan C Phase 7) |
| `gencast/pipeline/outline.py` | Created | Outline stage |
| `tests/conftest.py` | Created | Shared fixtures (tmp_xdg_dir, sample_speaker_profile, etc.) |
| `tests/unit/test_*.py` | Created | Unit tests for each module |
| `tests/component/test_*.py` | Created | Component tests with vcrpy cassettes |
| `tests/fixtures/cassettes/` | Created | vcrpy LLM recording dir |
| `tests/fixtures/notebooks/minimal.yaml` | Created | Test fixture |

---

## Phase 0 Tasks (1-13): Foundation — schemas, profiles, cascade, CLI skeleton

### Task 1: Wipe legacy code and rebuild pyproject.toml

**Files:**
- Delete: `src/`
- Delete: `gencast.py`
- Delete: `requirements.txt`
- Delete: `prompts/` (top-level)
- Delete: `audiences/`
- Modify: `pyproject.toml` (lines 5-95 — full replacement of project + setuptools sections)

- [ ] **Step 1: Verify branch and clean state**

```bash
git status
git branch --show-current
```

Expected: `rewrite/v1.0`, working tree clean (only docs/ committed previously).

- [ ] **Step 2: Delete legacy code**

```bash
git rm -r src/ gencast.py requirements.txt prompts/ audiences/
```

Expected: `git status` shows the deletions staged.

- [ ] **Step 3: Replace `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gencast"
version = "1.0.0a1"
description = "Generate conversational podcasts from documents using AI"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Mae Capacite", email = "cadrianmae@users.noreply.github.com"}
]
keywords = ["podcast", "ai", "tts", "openai", "anthropic", "notebooklm", "education"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Education",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Multimedia :: Sound/Audio :: Speech",
]

dependencies = [
    "click>=8.1.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "jinja2>=3.1.0",
    "litellm>=1.30.0",
    "openai>=1.0.0",
    "pydub>=0.25.1",
    "mistralai>=1.0.0",
    "pypdf>=3.0.0",
    "audioop-lts>=0.2.0; python_version >= '3.13'",
    "rich>=13.0.0",
    "srt>=3.5.0",
    "tiktoken>=0.7.0",
]

[project.optional-dependencies]
test = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "vcrpy>=5.0.0",
    "ffmpeg-python>=0.2.0",
]
dev = [
    "basedpyright>=1.21.0",
    "ruff>=0.1.0",
]
all = ["gencast[test,dev]"]

[project.scripts]
gencast = "gencast.cli.main:cli"

[project.urls]
Homepage = "https://github.com/cadrianmae/podcast-ai"
Repository = "https://github.com/cadrianmae/podcast-ai"
Issues = "https://github.com/cadrianmae/podcast-ai/issues"

[tool.setuptools.packages.find]
where = ["."]
include = ["gencast*"]

[tool.setuptools.package-data]
"gencast.profiles.bundled" = ["**/*.yaml"]
"gencast.prompts" = ["*.jinja"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
extend-select = ["I", "N", "W"]

[tool.basedpyright]
pythonVersion = "3.10"
pythonPlatform = "Linux"
typeCheckingMode = "standard"
include = ["gencast", "tests"]
exclude = ["venv", "build", "**/__pycache__", "scratch"]
```

- [ ] **Step 4: Verify package install fails (no source yet)**

```bash
./venv/bin/pip install -e . 2>&1 | tail -3
```

Expected: error like "package directory 'gencast' does not exist". Good — confirms the legacy code is fully removed.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Plan A Task 1: wipe legacy code, rewrite pyproject.toml for package layout"
```

---

### Task 2: Create empty package skeleton

**Files:**
- Create: `gencast/__init__.py`
- Create: `gencast/cli/__init__.py`
- Create: `gencast/profiles/__init__.py`
- Create: `gencast/profiles/bundled/speakers/.gitkeep`
- Create: `gencast/profiles/bundled/episodes/.gitkeep`
- Create: `gencast/profiles/bundled/rooms/.gitkeep`
- Create: `gencast/llm/__init__.py`
- Create: `gencast/pipeline/__init__.py`
- Create: `gencast/prompts/.gitkeep`
- Test: (no test yet — sanity check via import)

- [ ] **Step 1: Create top-level package**

```python
# gencast/__init__.py
"""gencast — generate conversational podcasts from documents."""

__version__ = "1.0.0a1"

# Public API populated as later phases land
__all__ = ["__version__"]
```

- [ ] **Step 2: Create empty subpackage __init__ files**

```bash
mkdir -p gencast/cli gencast/profiles/bundled/speakers gencast/profiles/bundled/episodes gencast/profiles/bundled/rooms gencast/llm gencast/pipeline gencast/prompts
touch gencast/cli/__init__.py gencast/profiles/__init__.py gencast/llm/__init__.py gencast/pipeline/__init__.py
touch gencast/profiles/bundled/speakers/.gitkeep gencast/profiles/bundled/episodes/.gitkeep gencast/profiles/bundled/rooms/.gitkeep gencast/prompts/.gitkeep
```

- [ ] **Step 3: Install package**

Run: `./venv/bin/pip install -e .[test,dev]`
Expected: install succeeds; `gencast` console script registers but errors on invocation (no main yet).

- [ ] **Step 4: Verify import works**

```bash
./venv/bin/python -c "import gencast; print(gencast.__version__)"
```

Expected: `1.0.0a1`

- [ ] **Step 5: Commit**

```bash
git add gencast/
git commit -m "Plan A Task 2: empty gencast/ package skeleton"
```

---

### Task 3: Implement Avatar + Speaker pydantic schemas

**Files:**
- Create: `gencast/profiles/schemas.py` (lines 1-50)
- Test: `tests/unit/test_schemas_speaker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_schemas_speaker.py
import pytest
from pydantic import ValidationError
from gencast.profiles.schemas import Avatar, Speaker


def test_avatar_all_fields_optional():
    a = Avatar()
    assert a.emoji is None
    assert a.ascii is None
    assert a.image is None
    assert a.color is None


def test_avatar_with_fields():
    a = Avatar(emoji="🦊", color="#ff7847")
    assert a.emoji == "🦊"
    assert a.color == "#ff7847"


def test_speaker_required_fields():
    s = Speaker(name="Sophie", voice_id="nova", backstory="bg", personality="p")
    assert s.name == "Sophie"
    assert s.voice_id == "nova"
    assert s.avatar is None


def test_speaker_with_avatar():
    s = Speaker(
        name="Sophie", voice_id="nova", backstory="bg", personality="p",
        avatar={"emoji": "🦊"},
    )
    assert s.avatar.emoji == "🦊"


def test_speaker_missing_field_raises():
    with pytest.raises(ValidationError):
        Speaker(name="Sophie", voice_id="nova", backstory="bg")  # personality missing


def test_speaker_per_speaker_tts_override():
    s = Speaker(
        name="Sophie", voice_id="nova", backstory="bg", personality="p",
        tts_provider="speaches", tts_model="kokoro",
        tts_config={"base_url": "http://localhost:8969"},
    )
    assert s.tts_provider == "speaches"
    assert s.tts_config["base_url"] == "http://localhost:8969"
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_schemas_speaker.py -v`
Expected: FAIL with `ImportError: cannot import name 'Avatar'`

- [ ] **Step 3: Implement schemas**

```python
# gencast/profiles/schemas.py
"""Pydantic schemas for speakers, episodes, rooms, profiles."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Avatar(BaseModel):
    """Speaker avatar — emoji for terminals, ASCII or image for richer renderers."""
    model_config = ConfigDict(extra="ignore")

    emoji: str | None = None
    ascii: str | None = None     # path relative to profile dir
    image: str | None = None     # path relative to profile dir
    color: str | None = None     # hex like "#ff7847"


class Speaker(BaseModel):
    """A single host/voice."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    voice_id: str = Field(..., min_length=1)
    backstory: str = Field(..., min_length=1)
    personality: str = Field(..., min_length=1)
    avatar: Avatar | None = None
    tts_provider: str | None = None
    tts_model: str | None = None
    tts_config: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty after stripping")
        return v
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_schemas_speaker.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/profiles/schemas.py tests/unit/test_schemas_speaker.py
git commit -m "Plan A Task 3: Avatar + Speaker pydantic schemas"
```

---

### Task 4: Implement SpeakerProfile schema with validators

**Files:**
- Modify: `gencast/profiles/schemas.py` (append SpeakerProfile)
- Test: `tests/unit/test_schemas_speaker_profile.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_schemas_speaker_profile.py
import pytest
from pydantic import ValidationError
from gencast.profiles.schemas import SpeakerProfile, Speaker


def make_speaker(name: str, voice_id: str) -> dict:
    return {
        "name": name,
        "voice_id": voice_id,
        "backstory": "background",
        "personality": "personality",
    }


def test_speaker_profile_minimum():
    sp = SpeakerProfile(
        name="solo",
        tts_provider="openai",
        tts_model="tts-1-hd",
        speakers=[make_speaker("Sophie", "nova")],
    )
    assert len(sp.speakers) == 1


def test_speaker_profile_two_speakers():
    sp = SpeakerProfile(
        name="duo",
        tts_provider="openai",
        tts_model="tts-1-hd",
        speakers=[
            make_speaker("Sophie", "nova"),
            make_speaker("Ben", "echo"),
        ],
    )
    assert len(sp.speakers) == 2


def test_speaker_profile_zero_speakers_rejected():
    with pytest.raises(ValidationError, match="1-4"):
        SpeakerProfile(name="empty", tts_provider="openai", tts_model="tts-1-hd", speakers=[])


def test_speaker_profile_five_speakers_rejected():
    with pytest.raises(ValidationError, match="1-4"):
        SpeakerProfile(
            name="big",
            tts_provider="openai",
            tts_model="tts-1-hd",
            speakers=[make_speaker(f"S{i}", f"v{i}") for i in range(5)],
        )


def test_speaker_profile_duplicate_names_rejected():
    with pytest.raises(ValidationError, match="unique"):
        SpeakerProfile(
            name="dup",
            tts_provider="openai",
            tts_model="tts-1-hd",
            speakers=[make_speaker("Same", "nova"), make_speaker("Same", "echo")],
        )


def test_speaker_profile_duplicate_voices_rejected():
    with pytest.raises(ValidationError, match="unique"):
        SpeakerProfile(
            name="dup",
            tts_provider="openai",
            tts_model="tts-1-hd",
            speakers=[make_speaker("A", "nova"), make_speaker("B", "nova")],
        )
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_schemas_speaker_profile.py -v`
Expected: FAIL with `ImportError: cannot import name 'SpeakerProfile'`

- [ ] **Step 3: Implement SpeakerProfile**

Append to `gencast/profiles/schemas.py`:

```python
class SpeakerProfile(BaseModel):
    """A named collection of 1-4 speakers sharing a TTS provider."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    description: str | None = None
    tts_provider: str = Field(..., min_length=1)
    tts_model: str = Field(..., min_length=1)
    tts_config: dict[str, Any] | None = None
    speakers: list[Speaker]

    @field_validator("speakers")
    @classmethod
    def validate_speakers(cls, v: list[Speaker]) -> list[Speaker]:
        if not 1 <= len(v) <= 4:
            raise ValueError(f"Must have 1-4 speakers, got {len(v)}")
        names = [s.name for s in v]
        if len(names) != len(set(names)):
            raise ValueError("Speaker names must be unique within a profile")
        voices = [s.voice_id for s in v]
        if len(voices) != len(set(voices)):
            raise ValueError("Voice IDs must be unique within a profile")
        return v
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_schemas_speaker_profile.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/profiles/schemas.py tests/unit/test_schemas_speaker_profile.py
git commit -m "Plan A Task 4: SpeakerProfile schema with uniqueness validators"
```

---

### Task 5: Implement EpisodeProfile schema

**Files:**
- Modify: `gencast/profiles/schemas.py` (append EpisodeProfile)
- Test: `tests/unit/test_schemas_episode_profile.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_schemas_episode_profile.py
import pytest
from pydantic import ValidationError
from gencast.profiles.schemas import EpisodeProfile


def test_episode_profile_minimum():
    ep = EpisodeProfile(name="basic", default_briefing="A briefing.")
    assert ep.num_segments == 6
    assert ep.outline_provider == "anthropic"
    assert ep.transcript_model == "claude-sonnet-4"
    assert ep.segment_size_default == "medium"
    assert ep.language is None


def test_episode_profile_full():
    ep = EpisodeProfile(
        name="custom",
        description="A custom episode",
        speaker_profile="revision-duo",
        default_briefing="Revise everything.",
        num_segments=8,
        segment_size_default="long",
        outline_provider="openai",
        outline_model="gpt-4o-mini",
        transcript_provider="anthropic",
        transcript_model="claude-sonnet-4",
        language="en",
    )
    assert ep.num_segments == 8
    assert ep.speaker_profile == "revision-duo"


def test_episode_profile_segments_too_few():
    with pytest.raises(ValidationError, match="3-10"):
        EpisodeProfile(name="x", default_briefing="b", num_segments=2)


def test_episode_profile_segments_too_many():
    with pytest.raises(ValidationError, match="3-10"):
        EpisodeProfile(name="x", default_briefing="b", num_segments=11)


def test_episode_profile_segment_size_invalid():
    with pytest.raises(ValidationError):
        EpisodeProfile(name="x", default_briefing="b", segment_size_default="xl")


def test_episode_profile_summarize_falls_back():
    """summarize_provider/model are None → callers fall back to outline_*. Schema just allows it."""
    ep = EpisodeProfile(name="x", default_briefing="b")
    assert ep.summarize_provider is None
    assert ep.summarize_model is None
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_schemas_episode_profile.py -v`
Expected: FAIL with `ImportError: cannot import name 'EpisodeProfile'`

- [ ] **Step 3: Implement EpisodeProfile**

Append to `gencast/profiles/schemas.py`:

```python
SegmentSize = Literal["short", "medium", "long"]


class EpisodeProfile(BaseModel):
    """How the podcast is structured — briefing, segment count, models per stage."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    description: str | None = None
    speaker_profile: str | None = None
    default_briefing: str = Field(..., min_length=1)
    num_segments: int = 6
    segment_size_default: SegmentSize = "medium"
    outline_provider: str = "anthropic"
    outline_model: str = "claude-haiku-4.5"
    transcript_provider: str = "anthropic"
    transcript_model: str = "claude-sonnet-4"
    outline_config: dict[str, Any] | None = None
    transcript_config: dict[str, Any] | None = None
    summarize_provider: str | None = None
    summarize_model: str | None = None
    language: str | None = None

    @field_validator("num_segments")
    @classmethod
    def validate_num_segments(cls, v: int) -> int:
        if not 3 <= v <= 10:
            raise ValueError(f"num_segments must be 3-10, got {v}")
        return v
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_schemas_episode_profile.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/profiles/schemas.py tests/unit/test_schemas_episode_profile.py
git commit -m "Plan A Task 5: EpisodeProfile schema with num_segments validator"
```

---

### Task 6: Implement RoomProfile schema

**Files:**
- Modify: `gencast/profiles/schemas.py` (append RoomProfile)
- Test: `tests/unit/test_schemas_room_profile.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_schemas_room_profile.py
import pytest
from pydantic import ValidationError
from gencast.profiles.schemas import RoomProfile


def test_room_profile_defaults_match_v1_small_room():
    rp = RoomProfile(name="small-room")
    assert rp.arc_deg == 120.0
    assert rp.reverb_t60_s == 0.30
    assert rp.reverb_wet == 0.05
    assert rp.reverb_lpf_hz == 2000.0
    assert rp.reverb_damping == 0.55
    assert rp.predelay_ms == 20.0
    assert rp.ambience_db == -70.0
    assert rp.target_dbfs == -1.0


def test_room_profile_disable_ambience():
    rp = RoomProfile(name="silent", ambience_db=None)
    assert rp.ambience_db is None


def test_room_profile_extreme_t60():
    """Schema allows wide T60 range; sensibility is the user's call."""
    rp = RoomProfile(name="hall", reverb_t60_s=2.5, reverb_wet=0.20)
    assert rp.reverb_t60_s == 2.5


def test_room_profile_negative_arc_rejected():
    with pytest.raises(ValidationError):
        RoomProfile(name="bad", arc_deg=-10.0)


def test_room_profile_arc_over_180_rejected():
    with pytest.raises(ValidationError):
        RoomProfile(name="bad", arc_deg=200.0)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_schemas_room_profile.py -v`
Expected: FAIL with `ImportError: cannot import name 'RoomProfile'`

- [ ] **Step 3: Implement RoomProfile**

Append to `gencast/profiles/schemas.py`:

```python
class RoomProfile(BaseModel):
    """Spatial audio + ambience configuration."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    description: str | None = None
    # Speaker arc spread
    arc_deg: float = Field(120.0, ge=0.0, le=180.0)
    itd_max_ms: float = Field(0.6, ge=0.0)
    jitter_deg: float = Field(1.5, ge=0.0)
    # Reverb (Schroeder)
    reverb_t60_s: float = Field(0.30, ge=0.0)
    reverb_wet: float = Field(0.05, ge=0.0, le=1.0)
    reverb_lpf_hz: float = Field(2000.0, gt=0.0)
    reverb_damping: float = Field(0.55, ge=0.0, le=1.0)
    predelay_ms: float = Field(20.0, ge=0.0)
    # Distance attenuation
    table_radius_m: float = Field(0.85, gt=0.0)
    # Ambience bed (NC 20)
    ambience_db: float | None = -70.0
    ambience_lpf_hz: float = Field(1500.0, gt=0.0)
    ambience_fan_rumble_db: float = 4.0
    # Output
    target_dbfs: float = Field(-1.0, le=0.0)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_schemas_room_profile.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/profiles/schemas.py tests/unit/test_schemas_room_profile.py
git commit -m "Plan A Task 6: RoomProfile schema with v1 locked defaults"
```

---

### Task 7: Implement profile cascade loader

**Files:**
- Create: `gencast/profiles/loader.py`
- Test: `tests/unit/test_profile_loader.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_profile_loader.py
from pathlib import Path
import pytest
from gencast.profiles.loader import (
    resolve_profile_path,
    load_profile,
    list_profile_names,
    ProfileNotFoundError,
)
from gencast.profiles.schemas import SpeakerProfile


@pytest.fixture
def tmp_layout(tmp_path, monkeypatch):
    """Set up project + XDG dirs and chdir into project root."""
    proj = tmp_path / "proj"
    xdg = tmp_path / "xdg"
    bundled = tmp_path / "bundled_root"
    (proj / "gencast" / "profiles" / "speakers").mkdir(parents=True)
    (xdg / "gencast" / "profiles" / "speakers").mkdir(parents=True)
    (bundled / "speakers").mkdir(parents=True)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    return {"proj": proj, "xdg": xdg, "bundled": bundled}


def test_resolve_uses_project_first(tmp_layout, monkeypatch):
    proj_yaml = tmp_layout["proj"] / "gencast/profiles/speakers/duo.yaml"
    xdg_yaml = tmp_layout["xdg"] / "gencast/profiles/speakers/duo.yaml"
    bundled_yaml = tmp_layout["bundled"] / "speakers/duo.yaml"
    proj_yaml.write_text("name: proj")
    xdg_yaml.write_text("name: xdg")
    bundled_yaml.write_text("name: bundled")
    monkeypatch.setattr("gencast.profiles.loader._BUNDLED_ROOT", tmp_layout["bundled"])
    found = resolve_profile_path("speakers", "duo")
    assert found == proj_yaml


def test_resolve_falls_back_to_xdg(tmp_layout, monkeypatch):
    xdg_yaml = tmp_layout["xdg"] / "gencast/profiles/speakers/duo.yaml"
    bundled_yaml = tmp_layout["bundled"] / "speakers/duo.yaml"
    xdg_yaml.write_text("name: xdg")
    bundled_yaml.write_text("name: bundled")
    monkeypatch.setattr("gencast.profiles.loader._BUNDLED_ROOT", tmp_layout["bundled"])
    found = resolve_profile_path("speakers", "duo")
    assert found == xdg_yaml


def test_resolve_falls_back_to_bundled(tmp_layout, monkeypatch):
    bundled_yaml = tmp_layout["bundled"] / "speakers/duo.yaml"
    bundled_yaml.write_text("name: bundled")
    monkeypatch.setattr("gencast.profiles.loader._BUNDLED_ROOT", tmp_layout["bundled"])
    found = resolve_profile_path("speakers", "duo")
    assert found == bundled_yaml


def test_resolve_raises_with_paths(tmp_layout, monkeypatch):
    monkeypatch.setattr("gencast.profiles.loader._BUNDLED_ROOT", tmp_layout["bundled"])
    with pytest.raises(ProfileNotFoundError) as ei:
        resolve_profile_path("speakers", "missing")
    msg = str(ei.value)
    assert "missing" in msg
    assert str(tmp_layout["proj"]) in msg
    assert str(tmp_layout["xdg"]) in msg
    assert str(tmp_layout["bundled"]) in msg


def test_load_profile_speaker(tmp_layout, monkeypatch):
    bundled_yaml = tmp_layout["bundled"] / "speakers/solo.yaml"
    bundled_yaml.write_text(
        "name: solo\n"
        "tts_provider: openai\n"
        "tts_model: tts-1-hd\n"
        "speakers:\n"
        "  - name: Sophie\n"
        "    voice_id: nova\n"
        "    backstory: bg\n"
        "    personality: p\n"
    )
    monkeypatch.setattr("gencast.profiles.loader._BUNDLED_ROOT", tmp_layout["bundled"])
    sp = load_profile("speakers", "solo")
    assert isinstance(sp, SpeakerProfile)
    assert sp.speakers[0].name == "Sophie"


def test_list_profile_names_aggregates_all_levels(tmp_layout, monkeypatch):
    (tmp_layout["proj"] / "gencast/profiles/speakers/proj-only.yaml").write_text("name: proj-only")
    (tmp_layout["xdg"] / "gencast/profiles/speakers/xdg-only.yaml").write_text("name: xdg-only")
    (tmp_layout["bundled"] / "speakers/bundled-only.yaml").write_text("name: bundled-only")
    (tmp_layout["proj"] / "gencast/profiles/speakers/shared.yaml").write_text("name: shared")
    (tmp_layout["bundled"] / "speakers/shared.yaml").write_text("name: shared")
    monkeypatch.setattr("gencast.profiles.loader._BUNDLED_ROOT", tmp_layout["bundled"])
    names = list_profile_names("speakers")
    assert "proj-only" in names
    assert "xdg-only" in names
    assert "bundled-only" in names
    # Shared shows once (project wins) but no duplicates
    assert names.count("shared") == 1
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_profile_loader.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_profile_path'`

- [ ] **Step 3: Implement loader**

```python
# gencast/profiles/loader.py
"""3-level profile cascade resolver: project > XDG > bundled."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Type, TypeVar

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


T = TypeVar("T", bound=BaseModel)


def load_profile(kind: ProfileKind, name: str) -> SpeakerProfile | EpisodeProfile | RoomProfile:
    """Load and validate a profile by name through the cascade."""
    path = resolve_profile_path(kind, name)
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    model = _KIND_TO_MODEL[kind]
    return model(**data)


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
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_profile_loader.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/profiles/loader.py tests/unit/test_profile_loader.py
git commit -m "Plan A Task 7: 3-level profile cascade loader"
```

---

### Task 8: Write 4 bundled speaker profiles

**Files:**
- Create: `gencast/profiles/bundled/speakers/educational-duo.yaml`
- Create: `gencast/profiles/bundled/speakers/revision-duo.yaml`
- Create: `gencast/profiles/bundled/speakers/solo-tutor.yaml`
- Create: `gencast/profiles/bundled/speakers/interview-duo.yaml`
- Test: `tests/unit/test_bundled_speaker_profiles.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_bundled_speaker_profiles.py
import pytest
from gencast.profiles.loader import load_profile

EXPECTED = ["educational-duo", "revision-duo", "solo-tutor", "interview-duo"]


@pytest.mark.parametrize("name", EXPECTED)
def test_bundled_speaker_profile_loads(name):
    sp = load_profile("speakers", name)
    assert sp.name == name
    assert sp.tts_provider in {"openai", "speaches"}
    assert 1 <= len(sp.speakers) <= 4


def test_solo_tutor_has_one_speaker():
    sp = load_profile("speakers", "solo-tutor")
    assert len(sp.speakers) == 1


def test_duos_have_two_speakers():
    for name in ["educational-duo", "revision-duo", "interview-duo"]:
        sp = load_profile("speakers", name)
        assert len(sp.speakers) == 2, f"{name} should have 2 speakers"
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_bundled_speaker_profiles.py -v`
Expected: FAIL with `ProfileNotFoundError`.

- [ ] **Step 3: Create the YAML files**

```yaml
# gencast/profiles/bundled/speakers/educational-duo.yaml
name: educational-duo
description: Two friendly hosts walking through a topic together — general teaching duo.

tts_provider: openai
tts_model: tts-1-hd

speakers:
  - name: Alex
    voice_id: nova
    backstory: |
      A friendly explainer who's good at breaking concepts down into clear,
      bite-sized pieces. Spends a lot of time tutoring.
    personality: |
      Warm, patient, leans on analogies. Happy to slow down or rewind.
    avatar:
      emoji: "🦊"
      color: "#ff7847"

  - name: Sam
    voice_id: echo
    backstory: |
      A curious learner who asks the questions students actually have.
      Sometimes jumps ahead, but is good at admitting confusion.
    personality: |
      Curious, slightly self-deprecating, occasionally pushes back on jargon.
    avatar:
      emoji: "🐻"
      color: "#4a90e2"
```

```yaml
# gencast/profiles/bundled/speakers/revision-duo.yaml
name: revision-duo
description: Two-host revision/teaching duo with exam-prep tone.

tts_provider: openai
tts_model: tts-1-hd

speakers:
  - name: Sophie
    voice_id: nova
    backstory: |
      A graduate teaching assistant who's spent the last few years walking
      students through the same exam material every spring. Patient,
      structured, leans on analogies from everyday life.
    personality: |
      Warm, methodical, asks the questions her audience would ask. Uses
      "let me show you" framings. Gentle when correcting.
    avatar:
      emoji: "🦊"
      color: "#ff7847"

  - name: Ben
    voice_id: echo
    backstory: |
      Final-year student preparing for the same exam. Smart, sometimes
      gets ahead of himself, occasionally needs the abstraction grounded
      back in concrete examples.
    personality: |
      Curious, slightly self-deprecating, asks the questions students
      actually have. Will push back when something doesn't quite click.
    avatar:
      emoji: "🐻"
      color: "#4a90e2"
```

```yaml
# gencast/profiles/bundled/speakers/solo-tutor.yaml
name: solo-tutor
description: A single host walking through a topic — best for narrating articles or solo concept explainers.

tts_provider: openai
tts_model: tts-1-hd

speakers:
  - name: Professor Vale
    voice_id: nova
    backstory: |
      An experienced teacher who has a knack for making complex topics
      accessible. Loves to explain things from first principles.
    personality: |
      Approachable, structured, uses "let's think through this together"
      framings even when speaking solo.
    avatar:
      emoji: "🦉"
      color: "#7b6ca8"
```

```yaml
# gencast/profiles/bundled/speakers/interview-duo.yaml
name: interview-duo
description: An interviewer + a domain expert — Q&A flow with curiosity from the host and depth from the expert.

tts_provider: openai
tts_model: tts-1-hd

speakers:
  - name: Riley
    voice_id: shimmer
    backstory: |
      A tech journalist whose strength is making technical interviewees
      explain things to a general audience. Asks the questions the audience
      would, not the ones an expert would.
    personality: |
      Engaging, slightly skeptical, excellent at follow-up questions that
      push for clarity.
    avatar:
      emoji: "🎙️"
      color: "#e8765a"

  - name: Dr. Chen
    voice_id: onyx
    backstory: |
      A subject-matter expert who has spent 15 years in their field.
      Excellent at giving technical context but sometimes needs to be
      pushed to translate jargon for a general audience.
    personality: |
      Analytical, thorough, occasionally drifts into technical depth.
      Responds well to "explain that for someone who doesn't know X" prompts.
    avatar:
      emoji: "👨‍🔬"
      color: "#4a90e2"
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_bundled_speaker_profiles.py -v`
Expected: 6 tests pass (4 parametrized + 2 explicit).

- [ ] **Step 5: Commit**

```bash
git add gencast/profiles/bundled/speakers/ tests/unit/test_bundled_speaker_profiles.py
git commit -m "Plan A Task 8: 4 bundled speaker profiles (educational/revision/solo/interview)"
```

---

### Task 9: Write 4 bundled episode profiles

**Files:**
- Create: `gencast/profiles/bundled/episodes/concept-explainer.yaml`
- Create: `gencast/profiles/bundled/episodes/exam-revision.yaml`
- Create: `gencast/profiles/bundled/episodes/interview.yaml`
- Create: `gencast/profiles/bundled/episodes/casual-discussion.yaml`
- Test: `tests/unit/test_bundled_episode_profiles.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_bundled_episode_profiles.py
import pytest
from gencast.profiles.loader import load_profile

EXPECTED = ["concept-explainer", "exam-revision", "interview", "casual-discussion"]


@pytest.mark.parametrize("name", EXPECTED)
def test_bundled_episode_profile_loads(name):
    ep = load_profile("episodes", name)
    assert ep.name == name
    assert len(ep.default_briefing) > 50  # non-trivial briefing
    assert 3 <= ep.num_segments <= 10
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_bundled_episode_profiles.py -v`
Expected: FAIL with `ProfileNotFoundError`.

- [ ] **Step 3: Create the YAML files**

```yaml
# gencast/profiles/bundled/episodes/concept-explainer.yaml
name: concept-explainer
description: Define-then-deepen format. Hosts work through one or more concepts, building up from definitions to nuanced cases.

speaker_profile: educational-duo

default_briefing: |
  This is a concept-explainer podcast. The hosts are working through the
  source material in a define-then-deepen pattern. They should:
    - Define each new term clearly the first time it's introduced
    - Build up from simple cases to more complex ones
    - Use concrete analogies for abstract ideas
    - Periodically check in: "did that land?" / "let's try another way"
  Tone: friendly, structured, conversational. Avoid lecture-mode. The
  audience is curious but not necessarily expert.

num_segments: 5
segment_size_default: medium
```

```yaml
# gencast/profiles/bundled/episodes/exam-revision.yaml
name: exam-revision
description: Revision podcast for exam prep — concept walkthroughs with worked examples.

speaker_profile: revision-duo

default_briefing: |
  This is an exam-revision podcast. The hosts are walking through the
  source material as if preparing for a written exam. They should:
    - Define each major term clearly when first introduced
    - Work through at least one concrete example or worked problem per segment
    - Distinguish things that are commonly confused
    - Periodically tie concepts back to "what could be on the exam"
  Tone: friendly, structured, slightly informal. Avoid jargon unless
  defining it. No introductions for new segments — flow naturally.

num_segments: 6
segment_size_default: medium
```

```yaml
# gencast/profiles/bundled/episodes/interview.yaml
name: interview
description: Q&A format — interviewer asks, expert answers, with follow-ups for depth.

speaker_profile: interview-duo

default_briefing: |
  This is an interview-format podcast. The interviewer's role is to ask
  the audience's questions and push for clarity; the expert's role is to
  provide depth and concrete examples. They should:
    - Open with an introduction to the topic and why it matters
    - Cover key questions the audience would actually have
    - Push back when answers are too jargon-heavy: "what does that mean for someone outside the field?"
    - Close with a takeaway or "what should the listener remember"
  Tone: engaged, curious, occasionally challenging in a friendly way.

num_segments: 5
segment_size_default: medium
```

```yaml
# gencast/profiles/bundled/episodes/casual-discussion.yaml
name: casual-discussion
description: Two friends chatting about a topic — informal, exploratory, not lecture-shaped.

speaker_profile: educational-duo

default_briefing: |
  This is a casual-discussion podcast. The hosts are chatting about the
  source material as if they just read it and want to talk it through.
  They should:
    - Sound like friends having coffee, not a structured lecture
    - Be willing to riff, react, share what surprised them
    - Use natural disagreements as a way to explore the topic
    - Avoid feeling like a script — let them be a bit messy
  Tone: relaxed, conversational, occasionally playful. Definitions emerge
  through discussion rather than being announced.

num_segments: 5
segment_size_default: medium
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_bundled_episode_profiles.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/profiles/bundled/episodes/ tests/unit/test_bundled_episode_profiles.py
git commit -m "Plan A Task 9: 4 bundled episode profiles"
```

---

### Task 10: Write 8 bundled room profiles (locked from harness work)

**Files:**
- Create: `gencast/profiles/bundled/rooms/small-room.yaml`
- Create: `gencast/profiles/bundled/rooms/dry.yaml`
- Create: `gencast/profiles/bundled/rooms/large-room.yaml`
- Create: `gencast/profiles/bundled/rooms/vocal-booth.yaml`
- Create: `gencast/profiles/bundled/rooms/wide.yaml`
- Create: `gencast/profiles/bundled/rooms/narrow.yaml`
- Create: `gencast/profiles/bundled/rooms/ambient.yaml`
- Create: `gencast/profiles/bundled/rooms/silent.yaml`
- Test: `tests/unit/test_bundled_room_profiles.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_bundled_room_profiles.py
import pytest
from gencast.profiles.loader import load_profile

EXPECTED = [
    "small-room", "dry", "large-room", "vocal-booth",
    "wide", "narrow", "ambient", "silent",
]


@pytest.mark.parametrize("name", EXPECTED)
def test_bundled_room_profile_loads(name):
    rp = load_profile("rooms", name)
    assert rp.name == name


def test_dry_disables_reverb():
    rp = load_profile("rooms", "dry")
    assert rp.reverb_wet == 0.0
    assert rp.ambience_db is None


def test_silent_disables_ambience():
    rp = load_profile("rooms", "silent")
    assert rp.ambience_db is None


def test_small_room_matches_v1_defaults():
    rp = load_profile("rooms", "small-room")
    assert rp.reverb_t60_s == 0.30
    assert rp.reverb_wet == 0.05
    assert rp.reverb_lpf_hz == 2000.0


def test_vocal_booth_short_decay():
    rp = load_profile("rooms", "vocal-booth")
    assert rp.reverb_t60_s == 0.20
    assert rp.reverb_lpf_hz == 1500.0


def test_large_room_longer_decay():
    rp = load_profile("rooms", "large-room")
    assert rp.reverb_t60_s == 0.50


def test_wide_arc():
    rp = load_profile("rooms", "wide")
    assert rp.arc_deg == 160.0


def test_narrow_arc():
    rp = load_profile("rooms", "narrow")
    assert rp.arc_deg == 80.0


def test_ambient_audible_bed():
    rp = load_profile("rooms", "ambient")
    assert rp.ambience_db == -50.0
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_bundled_room_profiles.py -v`
Expected: FAIL with `ProfileNotFoundError`.

- [ ] **Step 3: Create the YAML files**

```yaml
# gencast/profiles/bundled/rooms/small-room.yaml
name: small-room
description: gencast default — subtle small-room sense.
arc_deg: 120.0
itd_max_ms: 0.6
jitter_deg: 1.5
reverb_t60_s: 0.30
reverb_wet: 0.05
reverb_lpf_hz: 2000.0
reverb_damping: 0.55
predelay_ms: 20.0
table_radius_m: 0.85
ambience_db: -70.0
ambience_lpf_hz: 1500.0
ambience_fan_rumble_db: 4.0
target_dbfs: -1.0
```

```yaml
# gencast/profiles/bundled/rooms/dry.yaml
name: dry
description: No reverb, no ambience. Cold but very clean.
reverb_wet: 0.0
ambience_db: null
```

```yaml
# gencast/profiles/bundled/rooms/large-room.yaml
name: large-room
description: More open-feeling room — longer decay, brighter reflections.
reverb_t60_s: 0.50
reverb_wet: 0.08
reverb_lpf_hz: 2500.0
```

```yaml
# gencast/profiles/bundled/rooms/vocal-booth.yaml
name: vocal-booth
description: Tight, intimate booth — short decay, heavier absorption.
reverb_t60_s: 0.20
reverb_wet: 0.03
reverb_lpf_hz: 1500.0
reverb_damping: 0.65
predelay_ms: 15.0
```

```yaml
# gencast/profiles/bundled/rooms/wide.yaml
name: wide
description: Speakers spread wider (160° arc).
arc_deg: 160.0
```

```yaml
# gencast/profiles/bundled/rooms/narrow.yaml
name: narrow
description: Speakers closer together (80° arc).
arc_deg: 80.0
```

```yaml
# gencast/profiles/bundled/rooms/ambient.yaml
name: ambient
description: Audible studio ambience preset (-50 dBFS).
ambience_db: -50.0
```

```yaml
# gencast/profiles/bundled/rooms/silent.yaml
name: silent
description: No ambience bed, otherwise default room.
ambience_db: null
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_bundled_room_profiles.py -v`
Expected: 15 tests pass (8 parametrized + 7 explicit).

- [ ] **Step 5: Commit**

```bash
git add gencast/profiles/bundled/rooms/ tests/unit/test_bundled_room_profiles.py
git commit -m "Plan A Task 10: 8 bundled room profiles (locked from harness)"
```

---

### Task 11: Implement Notebook schema with overrides

**Files:**
- Create: `gencast/notebook.py`
- Test: `tests/unit/test_notebook_schema.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_notebook_schema.py
import pytest
from pathlib import Path
from pydantic import ValidationError
from gencast.notebook import Notebook, NotebookOutput, NotebookOverrides


def test_notebook_minimum():
    nb = Notebook(title="t", sources=["a.md"])
    assert nb.speaker_profile == "educational-duo"
    assert nb.episode_profile == "concept-explainer"
    assert nb.room_profile == "small-room"
    assert nb.output.formats == ["m4a"]
    assert nb.output.dir == Path("./out")


def test_notebook_full():
    nb = Notebook(
        title="t",
        description="desc",
        tags=["a", "b"],
        sources=["x.md", "y.md"],
        speaker_profile="revision-duo",
        episode_profile="exam-revision",
        room_profile="vocal-booth",
        output={"dir": "/tmp/out", "basename": "ep1", "formats": ["m4a", "mp3"]},
        overrides={
            "outline_model": "claude-haiku-4.5",
            "transcript_model": "claude-sonnet-4",
            "briefing_suffix": "Focus on X.",
        },
    )
    assert nb.output.formats == ["m4a", "mp3"]
    assert nb.overrides.briefing_suffix == "Focus on X."


def test_notebook_no_sources_rejected():
    with pytest.raises(ValidationError, match="sources"):
        Notebook(title="t", sources=[])


def test_notebook_invalid_format_rejected():
    with pytest.raises(ValidationError):
        Notebook(title="t", sources=["a.md"], output={"formats": ["wav"]})


def test_notebook_overrides_default_empty():
    nb = Notebook(title="t", sources=["a.md"])
    assert nb.overrides.outline_model is None
    assert nb.overrides.briefing_suffix is None


def test_notebook_strict_unknown_field_rejected():
    """Notebook YAML is strict: unknown top-level fields raise."""
    with pytest.raises(ValidationError):
        Notebook(title="t", sources=["a.md"], unknown_field=123)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_notebook_schema.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement Notebook schema**

```python
# gencast/notebook.py
"""Notebook YAML schema + loader."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

OutputFormat = Literal["m4a", "mp3", "transcript", "outline", "cost"]


class NotebookOutput(BaseModel):
    """Where + which formats to write."""
    model_config = ConfigDict(extra="forbid")

    dir: Path = Path("./out")
    basename: str | None = None
    formats: list[OutputFormat] = Field(default_factory=lambda: ["m4a"])


class NotebookOverrides(BaseModel):
    """Optional per-notebook overrides on top of episode-profile defaults."""
    model_config = ConfigDict(extra="forbid")

    outline_provider: str | None = None
    outline_model: str | None = None
    transcript_provider: str | None = None
    transcript_model: str | None = None
    num_segments: int | None = None
    briefing_suffix: str | None = None
    briefing: str | None = None  # full replacement


class Notebook(BaseModel):
    """Top-level notebook YAML — composes speaker + episode + room profiles."""
    model_config = ConfigDict(extra="forbid")  # strict for notebook YAML

    title: str = Field(..., min_length=1)
    description: str | None = None
    tags: list[str] | None = None

    output: NotebookOutput = Field(default_factory=NotebookOutput)
    sources: list[str]
    speaker_profile: str = "educational-duo"
    episode_profile: str = "concept-explainer"
    room_profile: str = "small-room"
    overrides: NotebookOverrides = Field(default_factory=NotebookOverrides)

    @field_validator("sources")
    @classmethod
    def at_least_one_source(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Notebook needs at least one source")
        return v


def load_notebook(path: str | Path) -> Notebook:
    """Load + validate a notebook YAML file."""
    path = Path(path)
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return Notebook(**data)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_notebook_schema.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/notebook.py tests/unit/test_notebook_schema.py
git commit -m "Plan A Task 11: Notebook + Output + Overrides schemas with strict validation"
```

---

### Task 12: Implement notebook loader + override resolution

**Files:**
- Modify: `gencast/notebook.py` (append `ResolvedNotebook` dataclass + resolver)
- Test: `tests/unit/test_notebook_resolver.py`
- Test: `tests/fixtures/notebooks/minimal.yaml`

- [ ] **Step 1: Create test fixture**

```yaml
# tests/fixtures/notebooks/minimal.yaml
title: Minimal test notebook
sources:
  - dummy.md
```

- [ ] **Step 2: Write failing tests**

```python
# tests/unit/test_notebook_resolver.py
from pathlib import Path
import pytest
from gencast.notebook import load_notebook, resolve_notebook


def test_load_notebook_from_file(tmp_path):
    p = tmp_path / "nb.yaml"
    p.write_text(
        "title: t\n"
        "sources: [a.md]\n"
        "speaker_profile: revision-duo\n"
        "episode_profile: exam-revision\n"
        "overrides:\n"
        "  briefing_suffix: extra\n"
    )
    nb = load_notebook(p)
    assert nb.speaker_profile == "revision-duo"
    assert nb.overrides.briefing_suffix == "extra"


def test_resolve_notebook_returns_concrete_profiles(tmp_path):
    p = tmp_path / "nb.yaml"
    p.write_text("title: t\nsources: [a.md]\n")
    nb = load_notebook(p)
    resolved = resolve_notebook(nb)
    # Each profile is a loaded model, not just a name
    from gencast.profiles.schemas import SpeakerProfile, EpisodeProfile, RoomProfile
    assert isinstance(resolved.speaker, SpeakerProfile)
    assert isinstance(resolved.episode, EpisodeProfile)
    assert isinstance(resolved.room, RoomProfile)


def test_resolve_briefing_suffix_appends(tmp_path):
    p = tmp_path / "nb.yaml"
    p.write_text(
        "title: t\nsources: [a.md]\n"
        "overrides: {briefing_suffix: 'Focus on X.'}\n"
    )
    nb = load_notebook(p)
    resolved = resolve_notebook(nb)
    assert "Focus on X." in resolved.briefing
    # Default briefing still present
    assert len(resolved.briefing) > len("Focus on X.")


def test_resolve_briefing_full_replacement(tmp_path):
    p = tmp_path / "nb.yaml"
    p.write_text(
        "title: t\nsources: [a.md]\n"
        "overrides: {briefing: 'Custom briefing'}\n"
    )
    nb = load_notebook(p)
    resolved = resolve_notebook(nb)
    assert resolved.briefing == "Custom briefing"


def test_resolve_model_override(tmp_path):
    p = tmp_path / "nb.yaml"
    p.write_text(
        "title: t\nsources: [a.md]\n"
        "overrides: {outline_model: gpt-4o-mini, transcript_model: gpt-5-mini}\n"
    )
    nb = load_notebook(p)
    resolved = resolve_notebook(nb)
    assert resolved.outline_model == "gpt-4o-mini"
    assert resolved.transcript_model == "gpt-5-mini"


def test_resolve_default_basename_from_title(tmp_path):
    p = tmp_path / "nb.yaml"
    p.write_text("title: 'My Cool Podcast!'\nsources: [a.md]\n")
    nb = load_notebook(p)
    resolved = resolve_notebook(nb)
    assert resolved.basename == "my-cool-podcast"
```

- [ ] **Step 3: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_notebook_resolver.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_notebook'`

- [ ] **Step 4: Implement resolver**

Append to `gencast/notebook.py`:

```python
import re
from dataclasses import dataclass

from .profiles.loader import load_profile
from .profiles.schemas import EpisodeProfile, RoomProfile, SpeakerProfile


@dataclass
class ResolvedNotebook:
    """Notebook with all profiles loaded and overrides applied — what the pipeline reads."""
    notebook: Notebook
    speaker: SpeakerProfile
    episode: EpisodeProfile
    room: RoomProfile

    # Resolved fields
    briefing: str
    outline_provider: str
    outline_model: str
    transcript_provider: str
    transcript_model: str
    num_segments: int
    basename: str


def _slugify(s: str) -> str:
    """Convert a title to a filesystem-friendly basename."""
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")


def resolve_notebook(nb: Notebook) -> ResolvedNotebook:
    """Load profiles, apply overrides, return a fully-resolved view of the notebook."""
    speaker = load_profile("speakers", nb.speaker_profile)
    episode = load_profile("episodes", nb.episode_profile)
    room = load_profile("rooms", nb.room_profile)

    # Briefing resolution: full replacement > base + suffix > base
    if nb.overrides.briefing is not None:
        briefing = nb.overrides.briefing
    elif nb.overrides.briefing_suffix is not None:
        briefing = f"{episode.default_briefing}\n\nAdditional focus: {nb.overrides.briefing_suffix}"
    else:
        briefing = episode.default_briefing

    return ResolvedNotebook(
        notebook=nb,
        speaker=speaker,
        episode=episode,
        room=room,
        briefing=briefing,
        outline_provider=nb.overrides.outline_provider or episode.outline_provider,
        outline_model=nb.overrides.outline_model or episode.outline_model,
        transcript_provider=nb.overrides.transcript_provider or episode.transcript_provider,
        transcript_model=nb.overrides.transcript_model or episode.transcript_model,
        num_segments=nb.overrides.num_segments or episode.num_segments,
        basename=nb.output.basename or _slugify(nb.title),
    )
```

- [ ] **Step 5: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_notebook_resolver.py -v`
Expected: 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add gencast/notebook.py tests/unit/test_notebook_resolver.py tests/fixtures/notebooks/minimal.yaml
git commit -m "Plan A Task 12: ResolvedNotebook + override resolution + slugify basename"
```

---

### Task 13: Implement `gencast list-profiles` CLI command

**Files:**
- Create: `gencast/cli/main.py`
- Test: `tests/unit/test_cli_list_profiles.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_cli_list_profiles.py
from click.testing import CliRunner
from gencast.cli.main import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "list-profiles" in result.output


def test_list_profiles_default_lists_all_kinds():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-profiles"])
    assert result.exit_code == 0
    # bundled profiles should appear
    assert "small-room" in result.output
    assert "revision-duo" in result.output
    assert "exam-revision" in result.output


def test_list_profiles_filtered_by_type():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-profiles", "--type", "rooms"])
    assert result.exit_code == 0
    assert "small-room" in result.output
    # non-room profiles should not appear
    assert "revision-duo" not in result.output


def test_list_profiles_invalid_type():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-profiles", "--type", "invalid"])
    assert result.exit_code != 0


def test_list_profiles_shows_origin_marker():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-profiles", "--type", "rooms"])
    # bundled profiles should be marked as such
    assert "(bundled)" in result.output
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_cli_list_profiles.py -v`
Expected: FAIL with `ImportError: cannot import name 'cli'`

- [ ] **Step 3: Implement CLI**

```python
# gencast/cli/main.py
"""gencast CLI entry point."""

from __future__ import annotations

import click

from gencast import __version__
from gencast.profiles.loader import (
    ProfileNotFoundError,
    list_profile_names,
    origin_marker,
)


@click.group(invoke_without_command=False)
@click.version_option(__version__, prog_name="gencast")
def cli() -> None:
    """gencast — generate conversational podcasts from documents."""


@cli.command("list-profiles")
@click.option(
    "--type",
    "kind",
    type=click.Choice(["speakers", "episodes", "rooms", "all"], case_sensitive=False),
    default="all",
    help="Which profile kind to list.",
)
def list_profiles(kind: str) -> None:
    """List available profiles from the 3-level cascade (project, user, bundled)."""
    kinds = ["speakers", "episodes", "rooms"] if kind == "all" else [kind]
    for k in kinds:
        click.secho(f"\n{k}:", fg="cyan", bold=True)
        names = list_profile_names(k)  # type: ignore[arg-type]
        if not names:
            click.echo("  (none found)")
            continue
        for name in names:
            try:
                origin = origin_marker(k, name)  # type: ignore[arg-type]
            except ProfileNotFoundError:
                origin = "?"
            click.echo(f"  {name:30s} ({origin})")
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_cli_list_profiles.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Manual smoke test**

Run: `./venv/bin/gencast list-profiles`
Expected: lists all 16 bundled profiles (4 speakers, 4 episodes, 8 rooms) each marked `(bundled)`.

Run: `./venv/bin/gencast list-profiles --type rooms`
Expected: lists only the 8 rooms.

- [ ] **Step 6: Commit**

```bash
git add gencast/cli/main.py tests/unit/test_cli_list_profiles.py
git commit -m "Plan A Task 13: gencast list-profiles command with cascade origin markers"
```

---

## Phase 1 Tasks (14-22): Outline pipeline

### Task 14: CostMeter (per-stage accumulator)

**Files:**
- Create: `gencast/cost.py`
- Test: `tests/unit/test_cost.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_cost.py
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
    """Per-segment transcript: 6 calls land in 'transcript' stage and accumulate."""
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
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_cost.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement CostMeter**

```python
# gencast/cost.py
"""Per-stage cost tracking — tokens, audio seconds, USD."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageCost:
    kind: str  # "llm" | "tts"
    model: str | None = None
    backend: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cache_reads_in: int = 0
    cache_writes_in: int = 0
    audio_seconds: float = 0.0
    usd: float = 0.0


@dataclass
class CostMeter:
    """Accumulates per-stage costs across a pipeline run."""
    stages: dict[str, StageCost] = field(default_factory=dict)

    def _stage(self, name: str, kind: str) -> StageCost:
        if name not in self.stages:
            self.stages[name] = StageCost(kind=kind)
        return self.stages[name]

    def record_llm(
        self, stage: str, *, model: str,
        tokens_in: int, tokens_out: int,
        cache_reads_in: int = 0, cache_writes_in: int = 0,
        usd: float,
    ) -> None:
        s = self._stage(stage, "llm")
        s.model = model
        s.tokens_in += tokens_in
        s.tokens_out += tokens_out
        s.cache_reads_in += cache_reads_in
        s.cache_writes_in += cache_writes_in
        s.usd += usd

    def record_tts(
        self, stage: str, *, backend: str, model: str,
        audio_seconds: float, usd: float,
    ) -> None:
        s = self._stage(stage, "tts")
        s.backend = backend
        s.model = model
        s.audio_seconds += audio_seconds
        s.usd += usd

    @property
    def total_usd(self) -> float:
        return sum(s.usd for s in self.stages.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages": {
                name: {
                    "kind": s.kind,
                    "model": s.model,
                    "backend": s.backend,
                    "tokens_in": s.tokens_in,
                    "tokens_out": s.tokens_out,
                    "cache_reads_in": s.cache_reads_in,
                    "cache_writes_in": s.cache_writes_in,
                    "audio_seconds": s.audio_seconds,
                    "usd": s.usd,
                }
                for name, s in self.stages.items()
            },
            "total_usd": self.total_usd,
        }
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_cost.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/cost.py tests/unit/test_cost.py
git commit -m "Plan A Task 14: CostMeter with per-stage LLM + TTS accumulators"
```

---

### Task 15: Minimal Reporter facade (Plan A version)

**Files:**
- Create: `gencast/logger.py`
- Test: `tests/unit/test_logger.py`

(Plan C will extend this with the full Rich Live UI; Plan A only needs a basic
plain reporter sufficient for `list-profiles` and `preview` commands.)

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_logger.py
import sys
from gencast.logger import Reporter, PlainReporter, make_reporter


def test_make_reporter_returns_plain_when_not_tty(capsys, monkeypatch):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
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
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_logger.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement Reporter**

```python
# gencast/logger.py
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
    # For Plan A: always Plain. Plan C swaps in RichReporter when stdout.isatty().
    return PlainReporter(verbosity=verbosity)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_logger.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/logger.py tests/unit/test_logger.py
git commit -m "Plan A Task 15: PlainReporter + Reporter ABC (Rich variant in Plan C)"
```

---

### Task 16: LiteLLM wrapper with cost tracking

**Files:**
- Modify: `gencast/llm/__init__.py` (full content)
- Test: `tests/unit/test_llm_wrapper.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_llm_wrapper.py
from unittest.mock import patch, MagicMock
import pytest
from gencast.llm import chat_completion, LLMResponse
from gencast.cost import CostMeter


def _mock_litellm_response(content: str = "ok", tokens_in: int = 100, tokens_out: int = 50):
    """Build a mock litellm response shape."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = tokens_in
    resp.usage.completion_tokens = tokens_out
    resp.usage.cache_read_input_tokens = 0
    resp.usage.cache_creation_input_tokens = 0
    resp._hidden_params = {"response_cost": 0.001}
    return resp


def test_chat_completion_returns_text_and_usage():
    with patch("gencast.llm.completion") as mock:
        mock.return_value = _mock_litellm_response("hello world")
        result = chat_completion(
            provider="anthropic", model="claude-haiku-4.5",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert isinstance(result, LLMResponse)
        assert result.content == "hello world"
        assert result.tokens_in == 100
        assert result.tokens_out == 50
        assert result.usd == pytest.approx(0.001)


def test_chat_completion_records_cost(monkeypatch):
    cm = CostMeter()
    with patch("gencast.llm.completion") as mock:
        mock.return_value = _mock_litellm_response()
        chat_completion(
            provider="anthropic", model="claude-haiku-4.5",
            messages=[{"role": "user", "content": "hi"}],
            cost_meter=cm, stage="outline",
        )
    assert "outline" in cm.stages
    assert cm.stages["outline"].tokens_in == 100


def test_chat_completion_passes_response_format():
    with patch("gencast.llm.completion") as mock:
        mock.return_value = _mock_litellm_response('{"k":"v"}')
        chat_completion(
            provider="anthropic", model="claude-haiku-4.5",
            messages=[{"role": "user", "content": "hi"}],
            response_format={"type": "json_object"},
        )
        kwargs = mock.call_args.kwargs
        assert kwargs["response_format"] == {"type": "json_object"}


def test_chat_completion_combines_provider_model():
    """litellm wants 'anthropic/claude-haiku-4.5', not separate provider+model."""
    with patch("gencast.llm.completion") as mock:
        mock.return_value = _mock_litellm_response()
        chat_completion(
            provider="anthropic", model="claude-haiku-4.5",
            messages=[{"role": "user", "content": "hi"}],
        )
        kwargs = mock.call_args.kwargs
        assert kwargs["model"] == "anthropic/claude-haiku-4.5"


def test_chat_completion_openai_no_provider_prefix():
    """OpenAI models don't take a provider prefix in litellm."""
    with patch("gencast.llm.completion") as mock:
        mock.return_value = _mock_litellm_response()
        chat_completion(
            provider="openai", model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
        )
        kwargs = mock.call_args.kwargs
        assert kwargs["model"] == "gpt-4o-mini"
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_llm_wrapper.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement LLM wrapper**

```python
# gencast/llm/__init__.py
"""LiteLLM wrapper — chat completion + usage extraction + cost tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from litellm import completion

from gencast.cost import CostMeter


@dataclass
class LLMResponse:
    content: str
    tokens_in: int
    tokens_out: int
    cache_reads_in: int
    cache_writes_in: int
    usd: float
    raw: Any  # full litellm response, for callers that need extra fields


def _format_model(provider: str, model: str) -> str:
    """litellm uses 'provider/model' for non-OpenAI; 'model' alone for OpenAI."""
    if provider == "openai":
        return model
    return f"{provider}/{model}"


def chat_completion(
    *,
    provider: str,
    model: str,
    messages: list[dict[str, Any]],
    response_format: dict[str, Any] | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    extra: dict[str, Any] | None = None,
    cost_meter: CostMeter | None = None,
    stage: str | None = None,
) -> LLMResponse:
    """One LLM call. Records cost into cost_meter[stage] if provided."""
    kwargs: dict[str, Any] = {
        "model": _format_model(provider, model),
        "messages": messages,
        "num_retries": 3,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    if extra:
        kwargs.update(extra)

    resp = completion(**kwargs)

    content = resp.choices[0].message.content or ""
    usage = resp.usage
    tokens_in = getattr(usage, "prompt_tokens", 0)
    tokens_out = getattr(usage, "completion_tokens", 0)
    cache_reads_in = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_writes_in = getattr(usage, "cache_creation_input_tokens", 0) or 0
    usd = (resp._hidden_params or {}).get("response_cost", 0.0) or 0.0

    if cost_meter is not None and stage is not None:
        cost_meter.record_llm(
            stage,
            model=_format_model(provider, model),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cache_reads_in=cache_reads_in,
            cache_writes_in=cache_writes_in,
            usd=usd,
        )

    return LLMResponse(
        content=content,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_reads_in=cache_reads_in,
        cache_writes_in=cache_writes_in,
        usd=usd,
        raw=resp,
    )
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_llm_wrapper.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/llm/__init__.py tests/unit/test_llm_wrapper.py
git commit -m "Plan A Task 16: LiteLLM wrapper with cost tracking + provider/model formatting"
```

---

### Task 17: Source extraction (markdown + plain text)

**Files:**
- Create: `gencast/pipeline/extract.py`
- Test: `tests/unit/test_extract.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_extract.py
from pathlib import Path
import pytest
from gencast.pipeline.extract import extract_sources, count_tokens


def test_extract_single_markdown(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("# Title\n\nSome content.")
    text, tokens = extract_sources([str(p)], model="gpt-4o-mini")
    assert "Title" in text
    assert "Some content" in text
    assert tokens > 0


def test_extract_multiple_files_concatenated(tmp_path):
    p1 = tmp_path / "a.md"
    p2 = tmp_path / "b.md"
    p1.write_text("First file content.")
    p2.write_text("Second file content.")
    text, _ = extract_sources([str(p1), str(p2)], model="gpt-4o-mini")
    assert "First file content" in text
    assert "Second file content" in text
    # Files separated by a separator line
    assert "---" in text


def test_extract_text_file(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("Plain text notes.")
    text, _ = extract_sources([str(p)], model="gpt-4o-mini")
    assert "Plain text notes" in text


def test_extract_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_sources([str(tmp_path / "nonexistent.md")], model="gpt-4o-mini")


def test_extract_unsupported_format_raises(tmp_path):
    p = tmp_path / "audio.mp3"
    p.write_bytes(b"\x00\x00\x00")
    with pytest.raises(ValueError, match="unsupported"):
        extract_sources([str(p)], model="gpt-4o-mini")


def test_count_tokens():
    n = count_tokens("hello world", model="gpt-4o-mini")
    assert n >= 2  # very rough lower bound


def test_extract_token_count_matches_text():
    """Returned token count agrees with count_tokens(returned_text)."""
    text = "The quick brown fox jumps over the lazy dog."
    n = count_tokens(text, model="gpt-4o-mini")
    assert n > 5
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_extract.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement extract**

```python
# gencast/pipeline/extract.py
"""Source extraction — markdown / plain text. PDF + URL deferred to Plan C."""

from __future__ import annotations

from pathlib import Path

import tiktoken

SOURCE_SEPARATOR = "\n\n---\n\n"
SUPPORTED_EXT = {".md", ".markdown", ".txt"}


def count_tokens(text: str, *, model: str) -> int:
    """Best-effort token count via tiktoken (falls back to cl100k_base)."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _read_one(path: Path) -> str:
    if path.suffix.lower() not in SUPPORTED_EXT:
        raise ValueError(
            f"Source format unsupported in Plan A: {path.suffix} "
            f"(supported: {sorted(SUPPORTED_EXT)}). PDF and URL extraction "
            f"land in Plan C."
        )
    return path.read_text(encoding="utf-8")


def extract_sources(paths: list[str], *, model: str) -> tuple[str, int]:
    """
    Read sources, concatenate, return (text, token_count).
    Files are separated by `\\n\\n---\\n\\n` so the LLM knows they're distinct.
    """
    parts: list[str] = []
    for path_str in paths:
        path = Path(path_str)
        if not path.is_file():
            raise FileNotFoundError(f"Source not found: {path}")
        parts.append(_read_one(path))
    text = SOURCE_SEPARATOR.join(parts)
    tokens = count_tokens(text, model=model)
    return text, tokens
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_extract.py -v`
Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/pipeline/extract.py tests/unit/test_extract.py
git commit -m "Plan A Task 17: source extraction (md/txt) with tiktoken token counting"
```

---

### Task 18: Token preflight (no map-reduce in Plan A)

**Files:**
- Create: `gencast/pipeline/preflight.py`
- Test: `tests/unit/test_preflight.py`

(Map-reduce summarization for oversize sources lands in Plan C Phase 7. Plan A
ships preflight that fails clearly when the source exceeds budget.)

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_preflight.py
import pytest
from gencast.pipeline.preflight import preflight, SourceTooLargeError, model_input_budget


def test_model_input_budget_known_models():
    assert model_input_budget("anthropic/claude-sonnet-4") == 200_000 - 5_000
    assert model_input_budget("openai/gpt-5-mini") > 0
    assert model_input_budget("anthropic/claude-haiku-4.5") == 200_000 - 5_000


def test_model_input_budget_unknown_returns_default():
    """Unknown models get a conservative default."""
    n = model_input_budget("unknown/model")
    assert n == 100_000  # documented conservative default


def test_preflight_passes_when_fits():
    # Should not raise
    preflight(source_tokens=5_000, model="anthropic/claude-sonnet-4")


def test_preflight_raises_when_oversize():
    with pytest.raises(SourceTooLargeError) as ei:
        preflight(source_tokens=300_000, model="anthropic/claude-sonnet-4")
    assert "300000" in str(ei.value) or "300,000" in str(ei.value)
    assert "claude-sonnet-4" in str(ei.value)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_preflight.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement preflight**

```python
# gencast/pipeline/preflight.py
"""Token-budget preflight. Map-reduce path lives in Plan C."""

from __future__ import annotations

# Conservative budgets per model — context window minus headroom for prompt
# scaffolding, system messages, and response. Numbers reflect 2026 model
# context windows.
_MODEL_BUDGETS: dict[str, int] = {
    "anthropic/claude-sonnet-4":  200_000 - 5_000,
    "anthropic/claude-haiku-4.5": 200_000 - 5_000,
    "anthropic/claude-opus-4-7":  200_000 - 5_000,
    "openai/gpt-5-mini":           400_000 - 5_000,
    "openai/gpt-4o-mini":          128_000 - 5_000,
    "openai/gpt-4o":               128_000 - 5_000,
}

_DEFAULT_BUDGET = 100_000


class SourceTooLargeError(ValueError):
    def __init__(self, source_tokens: int, budget: int, model: str):
        self.source_tokens = source_tokens
        self.budget = budget
        self.model = model
        super().__init__(
            f"Source is {source_tokens:,} tokens, exceeds {model} input budget of "
            f"{budget:,} tokens. Plan C will add map-reduce compression. "
            f"For now: split the notebook, trim sources, or pick a model with a larger context."
        )


def model_input_budget(model: str) -> int:
    """Return conservative input-token budget for the given litellm model string."""
    return _MODEL_BUDGETS.get(model, _DEFAULT_BUDGET)


def preflight(*, source_tokens: int, model: str) -> None:
    """Raise SourceTooLargeError if the source exceeds the model's input budget."""
    budget = model_input_budget(model)
    if source_tokens > budget:
        raise SourceTooLargeError(source_tokens, budget, model)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_preflight.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/pipeline/preflight.py tests/unit/test_preflight.py
git commit -m "Plan A Task 18: token-budget preflight (no compression yet — Plan C)"
```

---

### Task 19: Outline jinja prompt + Outline pydantic model

**Files:**
- Create: `gencast/prompts/outline.jinja`
- Create: `gencast/pipeline/outline.py` (model + prompt rendering)
- Test: `tests/unit/test_outline_prompt.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_outline_prompt.py
import pytest
from gencast.profiles.schemas import Speaker, SpeakerProfile
from gencast.pipeline.outline import (
    Outline, OutlineSegment,
    render_outline_prompt,
)


def test_outline_segment_validation():
    s = OutlineSegment(name="Intro", description="welcome", size="short")
    assert s.size == "short"


def test_outline_segment_invalid_size_rejected():
    with pytest.raises(Exception):
        OutlineSegment(name="x", description="x", size="huge")


def test_outline_holds_segments():
    o = Outline(segments=[
        OutlineSegment(name="A", description="a", size="short"),
        OutlineSegment(name="B", description="b", size="medium"),
    ])
    assert len(o.segments) == 2


def _sample_speakers():
    return SpeakerProfile(
        name="duo", tts_provider="openai", tts_model="tts-1-hd",
        speakers=[
            Speaker(name="Sophie", voice_id="nova", backstory="bg1", personality="p1"),
            Speaker(name="Ben", voice_id="echo", backstory="bg2", personality="p2"),
        ],
    )


def test_render_outline_prompt_basic():
    text = render_outline_prompt(
        briefing="A cool podcast",
        content="Source content here.",
        speakers=_sample_speakers().speakers,
        num_segments=5,
        language=None,
    )
    assert "A cool podcast" in text
    assert "Source content here" in text
    assert "Sophie" in text
    assert "Ben" in text
    assert "5" in text


def test_render_outline_prompt_with_language():
    text = render_outline_prompt(
        briefing="b", content="c",
        speakers=_sample_speakers().speakers,
        num_segments=3, language="Portuguese",
    )
    assert "Portuguese" in text


def test_render_outline_prompt_no_language_excludes_clause():
    text = render_outline_prompt(
        briefing="b", content="c",
        speakers=_sample_speakers().speakers,
        num_segments=3, language=None,
    )
    assert "LANGUAGE INSTRUCTION" not in text.upper()
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/unit/test_outline_prompt.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Create the jinja template**

```jinja
{# gencast/prompts/outline.jinja #}
You are an AI podcast producer. Your task is to create a detailed outline for a podcast episode based on the provided briefing and source content.

<briefing>
{{ briefing }}
</briefing>

<content>
{{ content }}
</content>

The podcast features the following speakers:
<speakers>
{%- for speaker in speakers %}
- **{{ speaker.name }}**: {{ speaker.backstory }}
  Personality: {{ speaker.personality }}
{%- endfor %}
</speakers>

{% if language -%}
LANGUAGE INSTRUCTION: Generate ALL output in {{ language }}.
{% endif -%}

Create an outline with exactly {{ num_segments }} segments. Each segment has:
- a clear, informative name (catchy but accurate)
- a description (2-4 sentences) covering what will be discussed and how
- a size: "short" (about 3 turns), "medium" (about 6 turns), or "long" (about 10 turns)

Guidelines:
- The first segment is an introduction; the last is a conclusion
- Segments should flow logically — the listener gets progressively deeper into the material
- Match segment sizes to importance: trivia gets "short", core concepts get "medium" or "long"
- Don't repeat introductions or topic-restatements between segments — they're internal markers, not chapters
- Consider speaker personalities when planning who would naturally lead each segment

Return ONLY valid JSON in this exact shape, with no surrounding prose, no code fences:
{
  "segments": [
    {"name": "...", "description": "...", "size": "short" | "medium" | "long"}
  ]
}
```

- [ ] **Step 4: Implement Outline + render**

```python
# gencast/pipeline/outline.py
"""Outline pass — Pydantic model + jinja rendering. Stage executor in Task 20."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict, Field

from gencast.profiles.schemas import Speaker

SegmentSize = Literal["short", "medium", "long"]

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    autoescape=select_autoescape(default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


class OutlineSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    size: SegmentSize = "medium"


class Outline(BaseModel):
    model_config = ConfigDict(extra="ignore")
    segments: list[OutlineSegment]


def render_outline_prompt(
    *,
    briefing: str,
    content: str,
    speakers: list[Speaker],
    num_segments: int,
    language: str | None,
) -> str:
    template = _jinja_env.get_template("outline.jinja")
    return template.render(
        briefing=briefing,
        content=content,
        speakers=speakers,
        num_segments=num_segments,
        language=language,
    )
```

- [ ] **Step 5: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/unit/test_outline_prompt.py -v`
Expected: 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add gencast/prompts/outline.jinja gencast/pipeline/outline.py tests/unit/test_outline_prompt.py
git commit -m "Plan A Task 19: outline jinja template + Outline pydantic model + render fn"
```

---

### Task 20: Outline stage executor (calls LLM, parses JSON)

**Files:**
- Modify: `gencast/pipeline/outline.py` (append `run_outline_stage`)
- Test: `tests/component/test_outline_stage.py`
- Test: `tests/conftest.py` (shared fixtures)

- [ ] **Step 1: Create shared conftest**

```python
# tests/conftest.py
"""Shared pytest fixtures."""

from unittest.mock import MagicMock

import pytest

from gencast.cost import CostMeter


@pytest.fixture
def cost_meter():
    return CostMeter()


@pytest.fixture
def mock_llm_outline_response():
    """Build a mock LLMResponse-like object that returns a valid Outline JSON."""
    def _make(json_str: str = '{"segments":[{"name":"A","description":"d","size":"short"},{"name":"B","description":"d","size":"medium"},{"name":"C","description":"d","size":"long"},{"name":"D","description":"d","size":"medium"},{"name":"E","description":"d","size":"short"}]}'):
        resp = MagicMock()
        resp.content = json_str
        resp.tokens_in = 5000
        resp.tokens_out = 600
        resp.cache_reads_in = 0
        resp.cache_writes_in = 0
        resp.usd = 0.005
        return resp
    return _make
```

- [ ] **Step 2: Write failing tests**

```python
# tests/component/test_outline_stage.py
from unittest.mock import patch
import pytest
from gencast.pipeline.outline import run_outline_stage, Outline
from gencast.profiles.schemas import Speaker, SpeakerProfile


@pytest.fixture
def speakers():
    return [
        Speaker(name="Sophie", voice_id="nova", backstory="bg", personality="p"),
        Speaker(name="Ben", voice_id="echo", backstory="bg", personality="p"),
    ]


def test_run_outline_stage_happy_path(speakers, cost_meter, mock_llm_outline_response):
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        outline = run_outline_stage(
            briefing="b", content="c",
            speakers=speakers, num_segments=5, language=None,
            outline_provider="anthropic", outline_model="claude-haiku-4.5",
            cost_meter=cost_meter,
        )
    assert isinstance(outline, Outline)
    assert len(outline.segments) == 5


def test_run_outline_stage_records_cost(speakers, cost_meter, mock_llm_outline_response):
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        run_outline_stage(
            briefing="b", content="c",
            speakers=speakers, num_segments=5, language=None,
            outline_provider="anthropic", outline_model="claude-haiku-4.5",
            cost_meter=cost_meter,
        )
    # chat_completion was given the cost_meter; we can't introspect it without
    # the real wrapper, but we can verify it was passed.
    call_kwargs = mock.call_args.kwargs
    assert call_kwargs["cost_meter"] is cost_meter
    assert call_kwargs["stage"] == "outline"


def test_run_outline_stage_handles_json_with_code_fence(speakers, cost_meter, mock_llm_outline_response):
    """Some models emit ```json ... ``` even when asked not to. Strip it."""
    fenced = '```json\n{"segments":[{"name":"X","description":"d","size":"short"}]}\n```'
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response(fenced)
        outline = run_outline_stage(
            briefing="b", content="c",
            speakers=speakers, num_segments=1, language=None,
            outline_provider="anthropic", outline_model="claude-haiku-4.5",
            cost_meter=cost_meter,
        )
    assert outline.segments[0].name == "X"


def test_run_outline_stage_invalid_json_raises(speakers, cost_meter, mock_llm_outline_response):
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response("not json")
        with pytest.raises(ValueError, match="JSON"):
            run_outline_stage(
                briefing="b", content="c",
                speakers=speakers, num_segments=1, language=None,
                outline_provider="anthropic", outline_model="claude-haiku-4.5",
                cost_meter=cost_meter,
            )
```

- [ ] **Step 3: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/component/test_outline_stage.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement run_outline_stage**

Append to `gencast/pipeline/outline.py`:

```python
import json
import re

from gencast.cost import CostMeter
from gencast.llm import chat_completion

# Strip optional ```json ... ``` code fences from LLM output.
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_code_fence(s: str) -> str:
    m = _FENCE_RE.match(s)
    return m.group(1) if m else s


def run_outline_stage(
    *,
    briefing: str,
    content: str,
    speakers: list[Speaker],
    num_segments: int,
    language: str | None,
    outline_provider: str,
    outline_model: str,
    cost_meter: CostMeter,
) -> Outline:
    """Generate the podcast outline. One LLM call, JSON-structured output."""
    prompt = render_outline_prompt(
        briefing=briefing, content=content, speakers=speakers,
        num_segments=num_segments, language=language,
    )
    response = chat_completion(
        provider=outline_provider,
        model=outline_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=3000,
        cost_meter=cost_meter,
        stage="outline",
    )

    raw = _strip_code_fence(response.content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Outline LLM response was not valid JSON: {e}. Raw response: {raw[:300]!r}"
        ) from e

    return Outline(**data)
```

- [ ] **Step 5: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/component/test_outline_stage.py -v`
Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add gencast/pipeline/outline.py tests/component/test_outline_stage.py tests/conftest.py
git commit -m "Plan A Task 20: run_outline_stage executor with JSON parsing + code-fence strip"
```

---

### Task 21: PodcastState dataclass + pipeline orchestration up to outline

**Files:**
- Modify: `gencast/pipeline/__init__.py` (PodcastState + run_through_outline)
- Test: `tests/component/test_pipeline_through_outline.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/component/test_pipeline_through_outline.py
from unittest.mock import patch
import pytest
from pathlib import Path
from gencast.notebook import Notebook, load_notebook
from gencast.pipeline import PodcastState, run_through_outline


@pytest.fixture
def sample_notebook(tmp_path):
    src = tmp_path / "lecture.md"
    src.write_text("Photosynthesis is the process by which plants make food from sunlight.")
    nb_path = tmp_path / "nb.yaml"
    nb_path.write_text(
        f"title: Test\n"
        f"sources: [{src}]\n"
    )
    return load_notebook(nb_path)


def test_run_through_outline_full_path(sample_notebook, mock_llm_outline_response):
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        state = run_through_outline(sample_notebook)

    assert isinstance(state, PodcastState)
    assert state.source_text != ""
    assert "Photosynthesis" in state.source_text
    assert state.source_tokens_original > 0
    assert state.outline is not None
    assert len(state.outline.segments) >= 3


def test_run_through_outline_tokens_recorded(sample_notebook, mock_llm_outline_response):
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        state = run_through_outline(sample_notebook)
    assert state.cost.total_usd > 0
    assert "outline" in state.cost.stages
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/component/test_pipeline_through_outline.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement PodcastState + orchestration**

```python
# gencast/pipeline/__init__.py
"""Pipeline state + orchestrator. Plan A only goes through the outline stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gencast.cost import CostMeter
from gencast.notebook import Notebook, ResolvedNotebook, resolve_notebook
from gencast.pipeline.extract import extract_sources
from gencast.pipeline.outline import Outline, run_outline_stage
from gencast.pipeline.preflight import preflight

if TYPE_CHECKING:
    pass


@dataclass
class PodcastState:
    notebook: Notebook
    resolved: ResolvedNotebook
    source_text: str = ""
    source_tokens_original: int = 0
    source_tokens_final: int = 0
    outline: Outline | None = None
    cost: CostMeter = field(default_factory=CostMeter)


def run_through_outline(notebook: Notebook) -> PodcastState:
    """Plan A pipeline: load → extract → preflight → outline. Returns the state."""
    resolved = resolve_notebook(notebook)
    state = PodcastState(notebook=notebook, resolved=resolved)

    # Stage 2: extract
    text, tokens = extract_sources(
        notebook.sources, model=f"{resolved.outline_provider}/{resolved.outline_model}"
    )
    state.source_text = text
    state.source_tokens_original = tokens
    state.source_tokens_final = tokens  # no map-reduce in Plan A

    # Stage 3: preflight
    preflight(
        source_tokens=tokens,
        model=f"{resolved.outline_provider}/{resolved.outline_model}",
    )

    # Stage 5: outline (no map-reduce stage 4 in Plan A)
    state.outline = run_outline_stage(
        briefing=resolved.briefing,
        content=text,
        speakers=resolved.speaker.speakers,
        num_segments=resolved.num_segments,
        language=resolved.episode.language,
        outline_provider=resolved.outline_provider,
        outline_model=resolved.outline_model,
        cost_meter=state.cost,
    )

    return state
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/component/test_pipeline_through_outline.py -v`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gencast/pipeline/__init__.py tests/component/test_pipeline_through_outline.py
git commit -m "Plan A Task 21: PodcastState + run_through_outline (extract + preflight + outline)"
```

---

### Task 22: `gencast preview` CLI command

**Files:**
- Modify: `gencast/cli/main.py` (add `preview` command)
- Test: `tests/component/test_cli_preview.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/component/test_cli_preview.py
from unittest.mock import patch
from pathlib import Path
import pytest
from click.testing import CliRunner
from gencast.cli.main import cli


@pytest.fixture
def sample_notebook_file(tmp_path):
    src = tmp_path / "lecture.md"
    src.write_text("Some interesting content about a topic.")
    nb = tmp_path / "nb.yaml"
    nb.write_text(
        f"title: Test podcast\n"
        f"sources: [{src}]\n"
    )
    return nb


def test_preview_smoke(sample_notebook_file, mock_llm_outline_response):
    runner = CliRunner()
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        mock.return_value = mock_llm_outline_response()
        result = runner.invoke(cli, ["preview", str(sample_notebook_file)])
    assert result.exit_code == 0, result.output
    assert "segments" in result.output.lower() or "outline" in result.output.lower()


def test_preview_shows_segment_names(sample_notebook_file, mock_llm_outline_response):
    runner = CliRunner()
    with patch("gencast.pipeline.outline.chat_completion") as mock:
        # mock returns segments named A-E
        mock.return_value = mock_llm_outline_response()
        result = runner.invoke(cli, ["preview", str(sample_notebook_file)])
    assert "A" in result.output
    assert "E" in result.output


def test_preview_missing_notebook(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["preview", str(tmp_path / "nonexistent.yaml")])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `./venv/bin/pytest tests/component/test_cli_preview.py -v`
Expected: FAIL with `Error: No such command 'preview'`.

- [ ] **Step 3: Implement preview**

Append to `gencast/cli/main.py`:

```python
import sys
from pathlib import Path

from gencast.notebook import load_notebook
from gencast.pipeline import run_through_outline


@cli.command("preview")
@click.argument("notebook_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def preview(notebook_path: Path) -> None:
    """Render outline only — fast dry-run before paying for full transcript + audio generation."""
    nb = load_notebook(notebook_path)
    state = run_through_outline(nb)

    click.secho(f"\n{state.notebook.title}", fg="cyan", bold=True)
    click.echo(f"  speakers:  {state.resolved.speaker.name}")
    click.echo(f"  episode:   {state.resolved.episode.name}")
    click.echo(f"  room:      {state.resolved.room.name}")
    click.echo(f"  source:    {state.source_tokens_original:,} tokens")
    click.echo(f"  cost so far: ${state.cost.total_usd:.4f}")

    click.secho(f"\nOutline ({len(state.outline.segments)} segments):", fg="green")
    for i, seg in enumerate(state.outline.segments, 1):
        click.echo(f"  {i}. [{seg.size}] {seg.name}")
        # Indent description
        for line in seg.description.split("\n"):
            click.echo(f"       {line}")
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `./venv/bin/pytest tests/component/test_cli_preview.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Manual smoke test (real API call — costs ~$0.005)**

```bash
# Create a tiny test notebook
mkdir -p /tmp/gencast-smoke
cat > /tmp/gencast-smoke/lecture.md <<EOF
Photosynthesis is the process plants use to make food from sunlight.
It involves two stages: the light reactions and the Calvin cycle.
EOF
cat > /tmp/gencast-smoke/nb.yaml <<EOF
title: Photosynthesis smoke test
sources: [lecture.md]
EOF
cd /tmp/gencast-smoke
OPENAI_API_KEY=$(pass api/openai) ANTHROPIC_API_KEY=$(pass api/anthropic) gencast preview nb.yaml
cd -
```

Expected: real outline with ~5 segments printed, cost ~$0.005.

- [ ] **Step 6: Commit**

```bash
git add gencast/cli/main.py tests/component/test_cli_preview.py
git commit -m "Plan A Task 22: gencast preview command — outline-only dry run"
```

---

## Phase 1 wrap-up

### Task 23: README + run summary for end of Plan A

**Files:**
- Create: `README.md` (replace any old one)
- Test: manual

- [ ] **Step 1: Write the README**

```markdown
# gencast

Generate conversational podcasts from documents using AI.

> **v1.0 — currently in active rewrite. The `rewrite/v1.0` branch is the
> source of truth. The published `gencast` 0.6.x on PyPI predates this
> design and is being replaced.**

## What works (Plan A — current branch state)

- `gencast list-profiles` — list all bundled + user-installed profiles
- `gencast preview NB.yaml` — render outline only (no transcript, no audio)

## What's coming

- Plan B: per-segment transcript, TTS, spatial audio, M4A output with embedded subtitles
- Plan C: full CLI UX (init wizard, Rich progress UI), edge cases (map-reduce, re-subtitling), tests + CI

See `docs/superpowers/specs/2026-05-07-gencast-v1-rewrite-design.md` for the full design.

## Install (development)

```bash
python -m venv venv
source venv/bin/activate
pip install -e .[test,dev]
```

## Try it

```bash
# List bundled profiles
gencast list-profiles

# Outline a tiny notebook
echo "Some content." > lecture.md
cat > nb.yaml <<EOF
title: My first podcast
sources: [lecture.md]
EOF
gencast preview nb.yaml
```

## Tests

```bash
pytest tests/unit                    # fast, no API calls
pytest tests/component               # vcrpy cassettes — no API keys needed once recorded
GENCAST_TEST_E2E=1 pytest tests/e2e  # real API calls, costs a few cents
```

## License

MIT
```

- [ ] **Step 2: Run the full test suite**

```bash
./venv/bin/pytest tests/ -v
```

Expected: all unit + component tests pass. No e2e tests yet.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Plan A Task 23: replace README with v1.0 status + Plan A try-it instructions"
```

---

## Plan A — done

After Task 23 the branch state is:

- `gencast list-profiles` works (16 bundled profiles)
- `gencast preview NB.yaml` works (outline pass with real LLM call)
- All schemas (Speaker / Episode / Room / Notebook) validated
- 3-level cascade resolver with project / XDG / bundled
- LiteLLM wrapper with cost tracking
- PlainReporter (Rich variant deferred to Plan C)
- ~30 unit tests + ~6 component tests, all green

**Plan B** picks up from here: transcript pass, TTS backends, audio FX, M4A
mux. The contracts are stable: `PodcastState`, `ResolvedNotebook`,
`CostMeter`, `LLMResponse`, the prompt template loader.
