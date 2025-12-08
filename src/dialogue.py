"""
Dialogue generation using LiteLLM with Instructor for structured outputs.
Converts document text into natural conversational podcast dialogue.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Tuple, Any
import instructor
from litellm import completion as litellm_completion

from .logger import get_logger
from .models import PodcastDialogue

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
- Cover ALL major points from the source material thoroughly
- Explore each concept in detail with examples and explanations
- Create a comprehensive discussion that does justice to the content
- Aim for depth over brevity - take time to fully explain ideas

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
    logger = get_logger()
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{style}.txt"

    try:
        if prompt_path.exists():
            return prompt_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.warning(f"Could not load prompt '{style}': {e}")

    # Fallback to hardcoded prompt
    logger.warning(f"Using fallback prompt (educational)")
    return FALLBACK_SYSTEM_PROMPT


# validate_and_clean_dialogue() removed - Pydantic models handle validation automatically


def load_audience_modifier(audience: str = "general") -> str:
    """
    Load audience modifier from audiences/ directory.

    Args:
        audience: Target audience (general, technical, academic, beginner)

    Returns:
        Audience modifier text, or empty string if not found
    """
    logger = get_logger()

    if audience == "general":
        # General is default, no modifier needed
        audience_path = Path(__file__).parent.parent / "audiences" / "general.txt"
    else:
        audience_path = Path(__file__).parent.parent / "audiences" / f"{audience}.txt"

    try:
        if audience_path.exists():
            return "\n\n" + audience_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.warning(f"Could not load audience modifier '{audience}': {e}")

    return ""


def calculate_max_tokens(input_length: int, scale_factor: float = 2.0, unlock_limit: bool = False) -> Optional[int]:
    """
    Calculate appropriate max_tokens based on input content length.

    Uses a configurable scaling factor to generate proportional dialogue output.
    Default scale_factor=2.0 means roughly 2 tokens output per 1 char input.

    Hard limit of 5,000 tokens targets ~20 minutes of podcast duration
    to prevent model output limits from truncating content. The model is
    instructed via prompt to naturally conclude within this timeframe.

    Example ranges with default scale_factor=2.0:
    - Small docs (< 1000 chars): 2000-4000 tokens (~8-16 mins)
    - Medium docs (1000-2500 chars): 4000-5000 tokens (~16-20 mins)
    - Large docs (> 2500 chars): 5000 tokens (~20 mins, capped)

    For longer podcasts, use --unlock-token-limit or plan-based chunking (see issue #2).

    Args:
        input_length: Character count of input text
        scale_factor: Tokens per character multiplier (default: 2.0)
                     Higher = longer dialogue output
        unlock_limit: If True, returns None (no token limit)

    Returns:
        Appropriate max_tokens value, or None if unlocked
    """
    if unlock_limit:
        return None  # No limit - let model use its maximum

    # Base minimum for very short inputs
    min_tokens = 2000

    # Scale factor: adjustable tokens output per char input
    # (accounts for dialogue expansion from source material)
    scaled_tokens = int(input_length * scale_factor)

    # Apply floor and ceiling
    max_tokens = max(min_tokens, scaled_tokens)
    # Cap at 5000 tokens (~17-20 mins podcast) to prevent model output limit truncation
    # For longer content, use plan-based chunking (see issue #2)
    max_tokens = min(max_tokens, 5000)

    return max_tokens


def generate_dialogue(
    text: str,
    model: str = "anthropic/claude-sonnet-4-5",
    style: str = "educational",
    audience: str = "general",
    custom_instructions: Optional[str] = None,
    plan: Optional[str] = None,
    unlock_token_limit: bool = False,
    verbosity: int = 2
) -> Tuple[str, Dict[str, int]]:
    """
    Generate conversational dialogue from document text using LiteLLM + Instructor.

    Args:
        text: The extracted document text to convert
        model: Model to use (default: anthropic/claude-sonnet-4-5)
        style: Podcast style (educational, interview, casual, debate)
        audience: Target audience (general, technical, academic, beginner)
        custom_instructions: Additional custom instructions to append to the prompt
        plan: Optional podcast plan outline to guide dialogue generation
        unlock_token_limit: Remove 16k token cap (default: False)
        verbosity: Logging verbosity level (0=silent, 1=minimal, 2=normal)

    Returns:
        Tuple of (dialogue_text, usage_dict) where usage_dict contains:
            - prompt_tokens: Input token count
            - completion_tokens: Output token count
            - total_tokens: Total token count

    Raises:
        ValueError: If required API key is not set
        Exception: If API call fails
    """
    logger = get_logger()

    # LiteLLM automatically reads API keys from environment based on provider
    # OpenAI: OPENAI_API_KEY
    # Anthropic: ANTHROPIC_API_KEY
    # etc.

    # Load style prompt and audience modifier
    system_prompt = load_prompt(style)
    audience_modifier = load_audience_modifier(audience)
    full_prompt = system_prompt + audience_modifier

    # Add custom instructions if provided
    if custom_instructions:
        full_prompt += f"\n\nAdditional instructions: {custom_instructions}"

    # Add plan context if provided
    if plan:
        full_prompt += f"\n\nPodcast Plan to Follow:\n{plan}"
        full_prompt += "\n\nGenerate dialogue that comprehensively covers all topics in the plan."

    # Calculate appropriate max_tokens based on input length
    max_tokens = calculate_max_tokens(len(text), unlock_limit=unlock_token_limit)

    # Add duration guidance to prompt (targets ~17-20 mins by default)
    if max_tokens:
        # Estimate podcast duration: ~1000 chars/min, ~4 chars/token
        estimated_minutes = int((max_tokens * 4) / 1000)
        full_prompt += f"\n\nIMPORTANT: Target podcast duration is approximately {estimated_minutes} minutes. Structure the conversation to naturally conclude within this timeframe while covering the key points comprehensively."

    try:
        logger.info(f"Generating dialogue with {model}...")
        logger.info(f"   Style: {style} | Audience: {audience}")
        if custom_instructions:
            logger.info(f"   Custom: {custom_instructions[:60]}{'...' if len(custom_instructions) > 60 else ''}")
        logger.info(f"   Input: {len(text)} chars -> Max tokens: {max_tokens if max_tokens else 'unlimited'}")

        # Create instructor client
        client = instructor.from_litellm(litellm_completion)

        # Build request parameters
        request_params = {
            "model": model,
            "messages": [
                {"role": "system", "content": full_prompt},
                {"role": "user", "content": f"Convert this content into a podcast dialogue:\n\n{text}"}
            ],
        }
        # Only add max_tokens if limited
        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens

        if RICH_AVAILABLE and verbosity >= 2:
            # Use Rich Live preview for visual feedback with streaming
            from instructor import Partial

            console = Console(force_terminal=True)
            with Live("", console=console) as live:
                request_params["stream"] = True
                request_params["response_model"] = Partial[PodcastDialogue]

                stream = client.chat.completions.create(**request_params)

                partial_dialogue = None
                for partial_dialogue in stream:
                    if partial_dialogue.segments:
                        seg_count = len(partial_dialogue.segments)
                        last_seg = partial_dialogue.segments[-1]

                        # Show segment count + last segment
                        last_text = last_seg.text if last_seg.text else ""
                        prefix = f"Generating ({seg_count} segments): {last_seg.speaker}: "
                        max_text_length = max(20, console.width - len(prefix) - 5)
                        if len(last_text) > max_text_length:
                            last_text = last_text[:max_text_length] + "..."

                        preview_text = Text()
                        preview_text.append(f"Generating ({seg_count} segments): ", style="bold cyan")
                        preview_text.append(f"{last_seg.speaker}: ", style="yellow")
                        preview_text.append(last_text, style="white")
                        live.update(preview_text)

                # Final dialogue is the last partial received
                if partial_dialogue is None:
                    raise Exception("No dialogue generated from streaming")
                final_dialogue = partial_dialogue

            # Extract usage from streaming (may not be available)
            usage_dict = {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0
            }
            logger.warning("Token usage tracking not available with instructor streaming mode")

        else:
            # Non-streaming mode with token usage tracking
            request_params["stream"] = False
            request_params["response_model"] = PodcastDialogue

            final_dialogue, raw_completion = client.chat.completions.create_with_completion(**request_params)

            # Extract usage from raw completion
            usage_dict = {
                'prompt_tokens': raw_completion.usage.prompt_tokens if hasattr(raw_completion, 'usage') else 0,
                'completion_tokens': raw_completion.usage.completion_tokens if hasattr(raw_completion, 'usage') else 0,
                'total_tokens': raw_completion.usage.total_tokens if hasattr(raw_completion, 'usage') else 0
            }

        # Convert structured dialogue to text format for audio.py compatibility
        dialogue_text = final_dialogue.to_text_format()
        segment_counts = final_dialogue.count_segments()
        logger.info(f"Generated dialogue: {segment_counts['HOST1']} HOST1 segments, {segment_counts['HOST2']} HOST2 segments")

        return dialogue_text, usage_dict

    except Exception as e:
        raise Exception(f"Failed to generate dialogue: {e}")
