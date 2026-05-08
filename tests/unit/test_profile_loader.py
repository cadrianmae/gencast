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
    assert names.count("shared") == 1
