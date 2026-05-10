"""Validate the .claude-plugin/plugin.json manifest + skills layout."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).parent.parent.parent
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
SKILLS_DIR = REPO_ROOT / "skills"


class PluginRequires(BaseModel):
    system: list[str] = Field(default_factory=list)


class PluginManifest(BaseModel):
    name: str
    version: str
    description: str
    author: str | dict
    homepage: str | None = None
    repository: str | None = None
    skills: list[str] = Field(default_factory=list)
    requires: PluginRequires | None = None


def test_plugin_manifest_exists_and_parses():
    assert PLUGIN_MANIFEST.exists(), f"missing {PLUGIN_MANIFEST}"
    data = json.loads(PLUGIN_MANIFEST.read_text())
    manifest = PluginManifest(**data)
    assert manifest.name == "gencast"
    assert manifest.version.startswith("1.2.")


def test_plugin_manifest_lists_four_skills():
    data = json.loads(PLUGIN_MANIFEST.read_text())
    skills = data.get("skills", [])
    assert len(skills) == 6
    expected = {
        "./skills/notebook-init",
        "./skills/source-check",
        "./skills/review-transcript",
        "./skills/cost-explain",
        "./skills/bug",
        "./skills/feature",
    }
    assert set(skills) == expected


def test_each_declared_skill_has_skill_md():
    data = json.loads(PLUGIN_MANIFEST.read_text())
    for skill_path in data.get("skills", []):
        skill_dir = REPO_ROOT / skill_path.lstrip("./")
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.exists(), f"missing SKILL.md at {skill_md}"


def test_each_skill_md_has_required_frontmatter():
    for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
        text = skill_md.read_text()
        assert text.startswith("---\n"), f"{skill_md} missing YAML frontmatter"
        # Parse the front matter manually — keep tests dep-light
        end = text.index("\n---\n", 4)
        frontmatter = text[4:end]
        assert "name:" in frontmatter, f"{skill_md} missing name"
        assert "description:" in frontmatter, f"{skill_md} missing description"
        # Description must be third person per plugin-dev:skill-development
        desc_line = next(
            line for line in frontmatter.splitlines() if line.startswith("description:")
        )
        assert "should be used when" in desc_line.lower(), (
            f"{skill_md} description must be third person and start with "
            f"'This skill should be used when...' (got: {desc_line!r})"
        )
