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
