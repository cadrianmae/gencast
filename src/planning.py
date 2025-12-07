"""
Podcast planning using OpenAI GPT-4o-mini.
Generates structured outline before dialogue generation for comprehensive coverage.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Tuple
from litellm import completion

from .logger import get_logger
from .dialogue import calculate_max_tokens

try:
    from rich.live import Live
    from rich.text import Text
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def load_planning_prompt() -> str:
    """
    Load planning prompt from prompts/planning.txt.

    Returns:
        Planning prompt text
    """
    logger = get_logger()
    prompt_path = Path(__file__).parent.parent / "prompts" / "planning.txt"

    try:
        if prompt_path.exists():
            return prompt_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.warning(f"Could not load planning prompt: {e}")

    # Minimal fallback if file not found
    return """Analyze the content and create a comprehensive podcast structure plan.

Include:
- List of key topics to cover
- Coverage goals
- Conversation flow structure
- Key points for each topic
- Estimated duration

Output as structured markdown."""


def calculate_plan_max_tokens(input_length: int, unlock_limit: bool = False) -> Optional[int]:
    """
    Calculate appropriate max_tokens for plan generation.

    Plans are outlines (less verbose than dialogue), so use ~30% of
    what dialogue generation would use.

    Args:
        input_length: Character count of input text
        unlock_limit: If True, returns None (no token limit)

    Returns:
        Appropriate max_tokens value for planning (600-2000 range), or None if unlocked
    """
    if unlock_limit:
        return None  # No limit - let model use its maximum

    dialogue_tokens = calculate_max_tokens(input_length, unlock_limit=False)
    if dialogue_tokens is None:
        return None
    plan_tokens = int(dialogue_tokens * 0.3)

    # Plan should typically be 600-2000 tokens
    plan_tokens = max(600, plan_tokens)
    plan_tokens = min(plan_tokens, 2000)

    return plan_tokens


def generate_plan(
    text: str,
    model: str = "anthropic/claude-sonnet-4-5",
    audience: str = "general",
    custom_instructions: Optional[str] = None,
    unlock_token_limit: bool = False,
    verbosity: int = 2
) -> Tuple[str, Dict[str, int]]:
    """
    Generate podcast structure plan from document text using LiteLLM.

    Creates a comprehensive outline that will be used to guide dialogue
    generation, ensuring thorough coverage of all source material.

    Args:
        text: The extracted document text to analyze
        model: OpenAI model to use (default: gpt-5-mini)
        audience: Target audience (general, technical, academic, beginner)
        custom_instructions: Additional instructions for planning focus
        unlock_token_limit: Remove token cap (default: False)
        verbosity: Logging verbosity level (0=silent, 1=minimal, 2=normal)

    Returns:
        Tuple of (plan_text, usage_dict) where usage_dict contains:
            - prompt_tokens: Input token count
            - completion_tokens: Output token count
            - total_tokens: Total token count

    Raises:
        ValueError: If OPENAI_API_KEY is not set
        Exception: If API call fails
    """
    logger = get_logger()

    # LiteLLM automatically reads API keys from environment based on provider
    # OpenAI: OPENAI_API_KEY
    # Anthropic: ANTHROPIC_API_KEY
    # etc.

    # Load planning prompt
    planning_prompt = load_planning_prompt()

    # Add audience context if not general
    if audience != "general":
        planning_prompt += f"\n\nTarget audience: {audience}"
        planning_prompt += f"\nAdjust technical depth and terminology accordingly."

    # Add custom instructions if provided
    if custom_instructions:
        planning_prompt += f"\n\nAdditional focus: {custom_instructions}"

    # Calculate appropriate max_tokens for planning
    max_tokens = calculate_plan_max_tokens(len(text), unlock_limit=unlock_token_limit)

    try:
        logger.info(f"Generating plan with {model}...")
        logger.info(f"   Audience: {audience}")
        if custom_instructions:
            logger.info(f"   Focus: {custom_instructions[:60]}{'...' if len(custom_instructions) > 60 else ''}")
        logger.info(f"   Input: {len(text)} chars -> Max tokens: {max_tokens if max_tokens else 'unlimited'}")

        # Stream the plan generation with live preview
        plan_chunks = []
        current_preview = ""
        usage_data = None

        if RICH_AVAILABLE and verbosity >= 2:
            # Use Rich Live preview for visual feedback
            console = Console(force_terminal=True)
            with Live("", console=console) as live:
                # Build request parameters
                request_params = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": planning_prompt},
                        {"role": "user", "content": f"Analyze this content and create a comprehensive podcast plan:\n\n{text}"}
                    ],
                    "stream": True,
                    "stream_options": {"include_usage": True}
                }
                # Only add max_tokens if limited
                if max_tokens is not None:
                    request_params["max_tokens"] = max_tokens

                stream = completion(**request_params)

                for chunk in stream:
                    # Capture usage data from final chunk
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage_data = chunk.usage

                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        plan_chunks.append(content)
                        current_preview += content

                        # Extract last line for preview
                        lines = current_preview.strip().split('\n')
                        last_line = lines[-1] if lines else ""

                        # Truncate to fit terminal width
                        prefix = "Planning: "
                        max_line_length = max(20, console.width - len(prefix) - 5)
                        if len(last_line) > max_line_length:
                            last_line = last_line[:max_line_length] + "..."

                        preview_text = Text()
                        preview_text.append(prefix, style="bold cyan")
                        preview_text.append(last_line, style="white")
                        live.update(preview_text)
        else:
            # Silent generation (no live preview)
            # Build request parameters
            request_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": planning_prompt},
                    {"role": "user", "content": f"Analyze this content and create a comprehensive podcast plan:\n\n{text}"}
                ],
                "stream": True,
                "stream_options": {"include_usage": True}
            }
            # Only add max_tokens if limited
            if max_tokens is not None:
                request_params["max_tokens"] = max_tokens

            stream = completion(**request_params)

            for chunk in stream:
                # Capture usage data from final chunk
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage_data = chunk.usage

                if chunk.choices[0].delta.content:
                    plan_chunks.append(chunk.choices[0].delta.content)

        plan = "".join(plan_chunks)
        logger.info(f"Generated plan: {len(plan)} characters")

        # Prepare usage dict
        usage_dict = {
            'prompt_tokens': usage_data.prompt_tokens if usage_data else 0,
            'completion_tokens': usage_data.completion_tokens if usage_data else 0,
            'total_tokens': usage_data.total_tokens if usage_data else 0
        }

        return plan.strip(), usage_dict

    except Exception as e:
        raise Exception(f"Failed to generate plan: {e}")
