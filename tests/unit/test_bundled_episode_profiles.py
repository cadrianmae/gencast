import pytest
from gencast.profiles.loader import load_profile

EXPECTED = ["concept-explainer", "exam-revision", "interview", "casual-discussion"]


@pytest.mark.parametrize("name", EXPECTED)
def test_bundled_episode_profile_loads(name):
    ep = load_profile("episodes", name)
    assert ep.name == name
    assert len(ep.default_briefing) > 50
    assert 3 <= ep.num_segments <= 10
