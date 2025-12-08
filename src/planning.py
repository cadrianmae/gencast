"""
Podcast planning using LiteLLM with Instructor for structured outputs.
Generates structured outline before dialogue generation for comprehensive coverage.
"""

from pathlib import Path
from typing import Optional, Dict, Tuple
import instructor
from litellm import completion as litellm_completion

from .logger import get_logger
from .dialogue import calculate_max_tokens as calculate_dialogue_max_tokens
from .models import PodcastPlan

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

    With structured outputs (Pydantic models), plans need ~50% of dialogue tokens
    due to JSON structure overhead. Minimum 1500 tokens for basic plans.

    Args:
        input_length: Character count of input text
        unlock_limit: If True, returns None (no token limit)

    Returns:
        Appropriate max_tokens value for planning (1500-3000 range), or None if unlocked
    """
    if unlock_limit:
        return None  # No limit - let model use its maximum

    dialogue_tokens = calculate_dialogue_max_tokens(input_length, unlock_limit=False)
    if dialogue_tokens is None:
        return None
    plan_tokens = int(dialogue_tokens * 0.5)  # Increased from 0.3 for structured outputs

    # Plan should typically be 1500-3000 tokens (increased for JSON structure)
    plan_tokens = max(1500, plan_tokens)
    plan_tokens = min(plan_tokens, 3000)

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
    Generate podcast structure plan from document text using LiteLLM + Instructor.

    Creates a comprehensive outline that will be used to guide dialogue
    generation, ensuring thorough coverage of all source material.

    Args:
        text: The extracted document text to analyze
        model: Model to use (default: anthropic/claude-sonnet-4-5)
        audience: Target audience (general, technical, academic, beginner)
        custom_instructions: Additional instructions for planning focus
        unlock_token_limit: Remove token cap (default: False)
        verbosity: Logging verbosity level (0=silent, 1=minimal, 2=normal)

    Returns:
        Tuple of (plan_markdown, usage_dict) where usage_dict contains:
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

    # Load planning prompt
    planning_prompt = load_planning_prompt()

    # Add audience context if not general
    if audience != "general":
        planning_prompt += f"\n\nTarget audience: {audience}"
        planning_prompt += f"\nAdjust technical depth and terminology accordingly."

    # Add custom instructions if provided
    if custom_instructions:
        planning_prompt += f"\n\nAdditional focus: {custom_instructions}"

    # Calculate dialogue token limit to inform planning
    dialogue_max_tokens = calculate_dialogue_max_tokens(len(text), unlock_limit=unlock_token_limit)
    if dialogue_max_tokens:
        dialogue_minutes = int((dialogue_max_tokens * 4) / 1000)
        planning_prompt += f"\n\nIMPORTANT: The dialogue generation is limited to approximately {dialogue_minutes} minutes (~{dialogue_max_tokens} tokens). Plan for comprehensive coverage of all topics, but note at the end that the actual podcast will be condensed to this duration. For full coverage of longer content, recommend splitting the material or using --unlock-token-limit."

    # Calculate appropriate max_tokens for planning
    max_tokens = calculate_plan_max_tokens(len(text), unlock_limit=unlock_token_limit)

    try:
        logger.info(f"Generating plan with {model}...")
        logger.info(f"   Audience: {audience}")
        if custom_instructions:
            logger.info(f"   Focus: {custom_instructions[:60]}{'...' if len(custom_instructions) > 60 else ''}")
        logger.info(f"   Input: {len(text)} chars -> Max tokens: {max_tokens if max_tokens else 'unlimited'}")

        # Create instructor client
        client = instructor.from_litellm(litellm_completion)

        # Build request parameters
        request_params = {
            "model": model,
            "messages": [
                {"role": "system", "content": planning_prompt},
                {"role": "user", "content": f"Analyze this content and create a comprehensive podcast plan:\n\n{text}"}
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
                request_params["response_model"] = Partial[PodcastPlan]

                stream = client.chat.completions.create(**request_params)

                partial_plan = None
                for partial_plan in stream:
                    if partial_plan.topics:
                        topic_count = len(partial_plan.topics)
                        last_title = partial_plan.topics[-1].title if partial_plan.topics else "..."

                        # Truncate title to fit terminal width
                        prefix = f"Planning ({topic_count} topics): "
                        max_title_length = max(20, console.width - len(prefix) - 5)
                        if len(last_title) > max_title_length:
                            last_title = last_title[:max_title_length] + "..."

                        preview_text = Text()
                        preview_text.append(prefix, style="bold cyan")
                        preview_text.append(last_title, style="white")
                        live.update(preview_text)

                # Final plan is the last partial received
                if partial_plan is None:
                    raise Exception("No plan generated from streaming")
                final_plan = partial_plan

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
            request_params["response_model"] = PodcastPlan

            final_plan, raw_completion = client.chat.completions.create_with_completion(**request_params)

            # Extract usage from raw completion
            usage_dict = {
                'prompt_tokens': raw_completion.usage.prompt_tokens if hasattr(raw_completion, 'usage') else 0,
                'completion_tokens': raw_completion.usage.completion_tokens if hasattr(raw_completion, 'usage') else 0,
                'total_tokens': raw_completion.usage.total_tokens if hasattr(raw_completion, 'usage') else 0
            }

        # Convert structured plan to markdown
        plan_markdown = final_plan.to_markdown()
        logger.info(f"Generated plan: {len(final_plan.topics)} topics, {len(plan_markdown)} characters")

        return plan_markdown, usage_dict

    except Exception as e:
        raise Exception(f"Failed to generate plan: {e}")
