"""
Dialogue generation using OpenAI GPT-4o-mini.
Converts document text into natural conversational podcast dialogue.
"""

import os
from pathlib import Path
from openai import OpenAI

try:
    from rich.live import Live
    from rich.text import Text
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# Fallback system prompt (educational style, general audience)
FALLBACK_SYSTEM_PROMPT = """You are a podcast dialogue writer. Convert the provided educational content into a natural, engaging conversation between two podcast hosts.

Guidelines:
- Create a friendly, conversational tone suitable for learning
- Have the hosts build on each other's points naturally
- Include clarifying questions and explanations
- Break down complex topics into digestible segments
- Use transitions between topics smoothly
- Keep the conversation informative but accessible

Format your output as:
HOST1: [their dialogue]
HOST2: [their dialogue]
HOST1: [continuing the conversation]

The hosts should introduce themselves briefly at the start and wrap up the discussion at the end."""


def load_prompt(style: str = "educational") -> str:
    """
    Load podcast style prompt from prompts/ directory.

    Args:
        style: Podcast style (educational, interview, casual, debate)

    Returns:
        System prompt text, or fallback if file not found
    """
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{style}.txt"

    try:
        if prompt_path.exists():
            return prompt_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"⚠️  Could not load prompt '{style}': {e}")

    # Fallback to hardcoded prompt
    print(f"⚠️  Using fallback prompt (educational)")
    return FALLBACK_SYSTEM_PROMPT


def load_audience_modifier(audience: str = "general") -> str:
    """
    Load audience modifier from audiences/ directory.

    Args:
        audience: Target audience (general, technical, academic, beginner)

    Returns:
        Audience modifier text, or empty string if not found
    """
    if audience == "general":
        # General is default, no modifier needed
        audience_path = Path(__file__).parent.parent / "audiences" / "general.txt"
    else:
        audience_path = Path(__file__).parent.parent / "audiences" / f"{audience}.txt"

    try:
        if audience_path.exists():
            return "\n\n" + audience_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"⚠️  Could not load audience modifier '{audience}': {e}")

    return ""


def generate_dialogue(
    text: str,
    model: str = "gpt-4o-mini",
    style: str = "educational",
    audience: str = "general"
) -> str:
    """
    Generate conversational dialogue from document text using OpenAI.

    Args:
        text: The extracted document text to convert
        model: OpenAI model to use (default: gpt-4o-mini)
        style: Podcast style (educational, interview, casual, debate)
        audience: Target audience (general, technical, academic, beginner)

    Returns:
        Formatted dialogue string with HOST1:/HOST2: labels

    Raises:
        ValueError: If OPENAI_API_KEY is not set
        Exception: If API call fails
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable not set.\n"
            "Please set it with: export OPENAI_API_KEY='sk-...'"
        )

    # Load style prompt and audience modifier
    system_prompt = load_prompt(style)
    audience_modifier = load_audience_modifier(audience)
    full_prompt = system_prompt + audience_modifier

    try:
        client = OpenAI(api_key=api_key)

        print(f"🎭 Generating dialogue with {model}...")
        print(f"   Style: {style} | Audience: {audience}")

        # Stream the dialogue generation with live preview
        dialogue_chunks = []
        current_preview = ""

        if RICH_AVAILABLE:
            console = Console(force_terminal=True)
            with Live("", refresh_per_second=4, console=console) as live:
                stream = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": full_prompt},
                        {"role": "user", "content": f"Convert this content into a podcast dialogue:\n\n{text}"}
                    ],
                    temperature=0.8,
                    max_tokens=4000,
                    stream=True
                )

                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        dialogue_chunks.append(content)
                        current_preview += content

                        # Extract last line for preview (update in place)
                        lines = current_preview.strip().split('\n')
                        last_line = lines[-1] if lines else ""

                        # Truncate to fit terminal width
                        prefix = "Generating: "
                        max_line_length = max(20, console.width - len(prefix) - 5)
                        if len(last_line) > max_line_length:
                            last_line = last_line[:max_line_length] + "..."

                        preview_text = Text()
                        preview_text.append(prefix, style="bold cyan")
                        preview_text.append(last_line, style="white")
                        live.update(preview_text)
        else:
            # Fallback without rich
            stream = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": full_prompt},
                    {"role": "user", "content": f"Convert this content into a podcast dialogue:\n\n{text}"}
                ],
                temperature=0.8,
                max_tokens=4000,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    dialogue_chunks.append(chunk.choices[0].delta.content)

        dialogue = "".join(dialogue_chunks)
        print(f"✅ Generated {len(dialogue)} characters of dialogue")

        return dialogue

    except Exception as e:
        raise Exception(f"Failed to generate dialogue: {e}")
