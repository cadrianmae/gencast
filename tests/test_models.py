import pytest
from src.models import DialogueSegment, PodcastDialogue, PlanTopic, PodcastPlan

def test_dialogue_segment_valid():
    seg = DialogueSegment(speaker="HOST1", text="Hello")
    assert seg.speaker == "HOST1"
    assert seg.text == "Hello"

def test_dialogue_segment_empty_text_fails():
    with pytest.raises(ValueError):
        DialogueSegment(speaker="HOST1", text="   ")

def test_podcast_dialogue_both_hosts():
    dialogue = PodcastDialogue(segments=[
        DialogueSegment(speaker="HOST1", text="Hi"),
        DialogueSegment(speaker="HOST2", text="Hello")
    ])
    counts = dialogue.count_segments()
    assert counts["HOST1"] == 1
    assert counts["HOST2"] == 1

def test_podcast_dialogue_single_host_fails():
    with pytest.raises(ValueError):
        PodcastDialogue(segments=[
            DialogueSegment(speaker="HOST1", text="Hi"),
            DialogueSegment(speaker="HOST1", text="Again")
        ])

def test_dialogue_to_text_format():
    dialogue = PodcastDialogue(segments=[
        DialogueSegment(speaker="HOST1", text="First"),
        DialogueSegment(speaker="HOST2", text="Second")
    ])
    text = dialogue.to_text_format()
    assert text == "HOST1: First\nHOST2: Second"

def test_plan_topic_valid():
    topic = PlanTopic(
        title="Introduction",
        key_points=["Point 1", "Point 2"],
        estimated_minutes=2.5
    )
    assert topic.title == "Introduction"
    assert len(topic.key_points) == 2

def test_podcast_plan_to_markdown():
    plan = PodcastPlan(
        overview="Test overview",
        target_audience="general",
        topics=[
            PlanTopic(
                title="Topic 1",
                key_points=["Point A"],
                estimated_minutes=3.0
            )
        ]
    )
    markdown = plan.to_markdown()
    assert "# Podcast Plan" in markdown
    assert "Topic 1" in markdown
    assert "Point A" in markdown
