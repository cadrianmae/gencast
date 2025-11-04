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

CRITICAL FORMATTING RULES:
- Output ONLY dialogue lines in the format: HOST1: text or HOST2: text
- Each line MUST start with either "HOST1: " or "HOST2: " (with a space after the colon)
- NO markdown formatting (no **, __, *, #, etc.)
- NO section headers or titles
- NO stage directions or [bracketed actions]
- NO quotes around dialogue
- NO numbered lists or bullet points
- NO blank lines between dialogue lines
- Plain text ONLY

Example of CORRECT format:
HOST1: Welcome to today's episode! I'm your host.
HOST2: And I'm here to dive into this fascinating topic with you.
HOST1: So let's start with the basics. What exactly are we talking about today?

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


def validate_and_clean_dialogue(dialogue: str) -> str:
    """
    Validate and clean generated dialogue to ensure strict format compliance.
    Removes any non-dialogue lines and enforces HOST1:/HOST2: format.

    Args:
        dialogue: Raw generated dialogue text

    Returns:
        Cleaned dialogue with only valid HOST1:/HOST2: lines
    """
    import re

    lines = dialogue.strip().split('\n')
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Strip markdown formatting
        # Remove bold: **text** -> text
        line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
        # Remove italic: *text* or _text_ -> text
        line = re.sub(r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)', r'\1', line)
        line = re.sub(r'_([^_]+)_', r'\1', line)
        # Remove markdown headers: ## text -> text
        line = re.sub(r'^#+\s*', '', line)

        # Check if line starts with HOST1: or HOST2:
        if line.startswith('HOST1:') or line.startswith('HOST2:'):
            # Remove quotes around dialogue if present
            line = re.sub(r'^(HOST[12]:)\s*["\'](.+)["\']$', r'\1 \2', line)
            cleaned_lines.append(line)
        elif line.startswith('**HOST1:**') or line.startswith('**HOST2:**'):
            # Handle markdown bold formatting on labels
            line = line.replace('**HOST1:**', 'HOST1:').replace('**HOST2:**', 'HOST2:')
            line = re.sub(r'^(HOST[12]:)\s*["\'](.+)["\']$', r'\1 \2', line)
            cleaned_lines.append(line)
        # Skip any other lines (headers, stage directions, etc.)

    cleaned_dialogue = '\n'.join(cleaned_lines)

    # Count valid segments
    host1_count = cleaned_dialogue.count('HOST1:')
    host2_count = cleaned_dialogue.count('HOST2:')

    if host1_count == 0 or host2_count == 0:
        raise ValueError(
            f"Generated dialogue has invalid format. "
            f"Found {host1_count} HOST1 lines and {host2_count} HOST2 lines. "
            f"Both hosts must have at least one line."
        )

    return cleaned_dialogue


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


def calculate_max_tokens(input_length: int, scale_factor: float = 2.0) -> int:
    """
    Calculate appropriate max_tokens based on input content length.

    Uses a configurable scaling factor to generate proportional dialogue output.
    Default scale_factor=2.0 means roughly 2 tokens output per 1 char input.

    Example ranges with default scale_factor=2.0:
    - Small docs (< 1000 chars): 2000-4000 tokens
    - Medium docs (1000-5000 chars): 4000-10000 tokens
    - Large docs (5000-8000 chars): 10000-16000 tokens
    - Very large docs (> 8000 chars): 16000 tokens (capped)

    Args:
        input_length: Character count of input text
        scale_factor: Tokens per character multiplier (default: 2.0)
                     Higher = longer dialogue output

    Returns:
        Appropriate max_tokens value
    """
    # Base minimum for very short inputs
    min_tokens = 2000

    # Scale factor: adjustable tokens output per char input
    # (accounts for dialogue expansion from source material)
    scaled_tokens = int(input_length * scale_factor)

    # Apply floor and ceiling
    max_tokens = max(min_tokens, scaled_tokens)
    max_tokens = min(max_tokens, 16000)  # Cap at model limits

    return max_tokens


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

    # Calculate appropriate max_tokens based on input length
    max_tokens = calculate_max_tokens(len(text))

    try:
        client = OpenAI(api_key=api_key)

        print(f"🎭 Generating dialogue with {model}...")
        print(f"   Style: {style} | Audience: {audience}")
        print(f"   Input: {len(text)} chars → Max tokens: {max_tokens}")

        # Stream the dialogue generation with live preview
        dialogue_chunks = []
        current_preview = ""

        if RICH_AVAILABLE:
            console = Console(force_terminal=True)
            with Live("", console=console) as live:
                stream = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": full_prompt},
                        {"role": "user", "content": f"Convert this content into a podcast dialogue:\n\n{text}"}
                    ],
                    temperature=0.8,
                    max_tokens=max_tokens,
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
                max_tokens=max_tokens,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    dialogue_chunks.append(chunk.choices[0].delta.content)

        dialogue = "".join(dialogue_chunks)
        print(f"✅ Generated {len(dialogue)} characters of dialogue")

        # Validate and clean the dialogue format
        try:
            cleaned_dialogue = validate_and_clean_dialogue(dialogue)
            removed_lines = len(dialogue.split('\n')) - len(cleaned_dialogue.split('\n'))
            if removed_lines > 0:
                print(f"🧹 Cleaned format: removed {removed_lines} non-dialogue lines")
            return cleaned_dialogue
        except ValueError as e:
            print(f"⚠️  Warning: {e}")
            print("Raw dialogue (first 500 chars):")
            print(dialogue[:500])
            raise

    except Exception as e:
        raise Exception(f"Failed to generate dialogue: {e}")
