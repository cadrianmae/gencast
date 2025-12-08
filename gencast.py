#!/usr/bin/env python3
"""
gencast - Generate conversational podcasts from documents
Author: Mae Capacite
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional

from litellm import model_cost
from src.utils import extract_text
from src.dialogue import generate_dialogue
from src.planning import generate_plan
from src.audio import generate_podcast_audio, DEFAULT_VOICES
from src.logger import setup_logger, get_logger, color_metric, color_cost


def get_model_pricing(model: str) -> Optional[Dict]:
    """
    Get pricing for a specific model from LiteLLM's built-in model cost data.

    Args:
        model: Model name (e.g., 'gpt-5-mini', 'anthropic/claude-sonnet-4-5')

    Returns:
        Dict with pricing info (input_cost_per_token, output_cost_per_token, etc.),
        or None if model not found
    """
    try:
        return model_cost.get(model)
    except Exception:
        return None


def log_usage_and_cost(usage_dict: Dict[str, int], model: str, verbosity: int) -> None:
    """
    Calculate and log token usage and costs with color formatting.

    Uses LiteLLM's built-in model cost data. Falls back to token-only display
    if model pricing is unknown.
    """
    if verbosity < 1 or not usage_dict:
        return

    logger = get_logger()
    input_tokens = usage_dict.get('prompt_tokens', 0)
    output_tokens = usage_dict.get('completion_tokens', 0)
    total_tokens = usage_dict.get('total_tokens', 0)

    # Format tokens display
    tokens_text = f"Tokens: {color_metric(f'{input_tokens:,}')} in, {color_metric(f'{output_tokens:,}')} out, {color_metric(f'{total_tokens:,}')} total"

    # Try to get pricing from LiteLLM and calculate cost
    model_pricing = get_model_pricing(model)

    if model_pricing and 'input_cost_per_token' in model_pricing:
        # Calculate cost using LiteLLM's pricing (cost per token)
        input_cost_per_token = model_pricing.get('input_cost_per_token', 0)
        output_cost_per_token = model_pricing.get('output_cost_per_token', 0)
        input_cost = input_tokens * input_cost_per_token
        output_cost = output_tokens * output_cost_per_token
        total_cost = input_cost + output_cost

        cost_text = f"Cost: {color_cost(f'${total_cost:.4f}')} (est.)"
        logger.milestone(f"   {tokens_text} | {cost_text}")
    else:
        # Unknown model - show tokens only
        logger.milestone(f"   {tokens_text}")


def check_api_keys() -> None:
    """Check if required API keys are set in environment."""
    logger = get_logger()
    missing_keys = []

    if not os.environ.get('OPENAI_API_KEY'):
        missing_keys.append('OPENAI_API_KEY')

    # Mistral is optional (only needed for PDFs)
    mistral_status = "[OK]" if os.environ.get('MISTRAL_API_KEY') else "[WARN] Not set (optional, needed for PDFs)"

    if missing_keys:
        logger.error("Required API keys not found in environment")
        logger.error(f"\nMissing: {', '.join(missing_keys)}")
        logger.error("\nPlease set them:")
        logger.error("  export OPENAI_API_KEY='sk-...'")
        logger.error("  export MISTRAL_API_KEY='...'  # Optional, for PDF processing")
        sys.exit(1)

    logger.info(f"API Keys: OPENAI_API_KEY [OK] | MISTRAL_API_KEY {mistral_status}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate conversational podcasts from documents using AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s lecture.md
  %(prog)s chapter1.md chapter2.md chapter3.md
  %(prog)s lecture.md -o my_podcast.mp3
  %(prog)s lecture.md --host1-voice nova --host2-voice echo

Supported formats: .md (markdown), .txt (text), .pdf (requires MISTRAL_API_KEY)
Default voices: HOST1=nova, HOST2=echo
        """
    )

    parser.add_argument(
        'inputs',
        nargs='+',
        help='Input document(s) to convert to podcast'
    )

    parser.add_argument(
        '-o', '--output',
        default='podcast.mp3',
        help='Output podcast file path (default: podcast.mp3)'
    )

    parser.add_argument(
        '--host1-voice',
        default=DEFAULT_VOICES['HOST1'],
        choices=['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'],
        help=f"Voice for HOST1 (default: {DEFAULT_VOICES['HOST1']})"
    )

    parser.add_argument(
        '--host2-voice',
        default=DEFAULT_VOICES['HOST2'],
        choices=['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'],
        help=f"Voice for HOST2 (default: {DEFAULT_VOICES['HOST2']})"
    )

    parser.add_argument(
        '--model',
        default='anthropic/claude-sonnet-4-5',
        help='AI model for dialogue generation (default: anthropic/claude-sonnet-4-5)'
    )

    parser.add_argument(
        '--save-dialogue',
        action='store_true',
        help='Save generated dialogue to text file'
    )

    parser.add_argument(
        '--spatial-separation',
        type=float,
        default=0.4,
        help='Spatial separation 0.0-1.0 for panning and ITD (default: 0.4)'
    )

    parser.add_argument(
        '--style',
        default='educational',
        choices=['educational', 'interview', 'casual', 'debate'],
        help='Podcast style (default: educational)'
    )

    parser.add_argument(
        '--audience',
        default='general',
        choices=['general', 'technical', 'academic', 'beginner'],
        help='Target audience (default: general)'
    )

    parser.add_argument(
        '--instructions',
        type=str,
        help='Additional instructions for the podcast generation (e.g., "focus on practical examples", "emphasize challenges", "keep it light and humorous")'
    )

    parser.add_argument(
        '--with-planning',
        action='store_true',
        help='Generate podcast plan before dialogue for comprehensive coverage'
    )

    parser.add_argument(
        '--save-plan',
        action='store_true',
        help='Save generated plan to text file'
    )

    parser.add_argument(
        '--unlock-token-limit',
        action='store_true',
        help='Remove token limit cap (allows model to use maximum context)'
    )

    parser.add_argument(
        '--minimal',
        action='store_true',
        help='Minimal output: only milestones and final path (no spinners/progress)'
    )

    parser.add_argument(
        '--silent',
        action='store_true',
        help='Silent mode: suppress all output except errors'
    )

    args = parser.parse_args()

    # Setup logging based on verbosity flags
    verbosity = 0 if args.silent else (1 if args.minimal else 2)
    setup_logger(verbosity)
    logger = get_logger()

    # Header
    logger.info("=" * 60)
    logger.info("gencast - Document to Podcast Converter")
    logger.info("=" * 60)

    # Check API keys
    check_api_keys()

    # Verify input files exist
    for filepath in args.inputs:
        if not Path(filepath).exists():
            logger.error(f"File not found: {filepath}")
            sys.exit(1)

    try:
        # Determine total steps based on planning flag
        total_steps = 4 if args.with_planning else 3
        current_step = 0

        # Step 1: Extract text from documents
        current_step += 1
        logger.milestone(f"\nStep {current_step}/{total_steps}: Reading {len(args.inputs)} document(s)...")
        text = extract_text(args.inputs, verbosity=verbosity)
        logger.info(f"Extracted {len(text)} characters")

        # Step 2 (optional): Generate podcast plan
        plan = None
        if args.with_planning:
            current_step += 1
            try:
                logger.milestone(f"\nStep {current_step}/{total_steps}: Generating podcast plan...")
                plan, plan_usage = generate_plan(
                    text,
                    model=args.model,
                    audience=args.audience,
                    custom_instructions=args.instructions,
                    unlock_token_limit=args.unlock_token_limit,
                    verbosity=verbosity
                )

                # Log usage and cost
                log_usage_and_cost(plan_usage, args.model, verbosity)

                # Display plan to user
                logger.info(f"\n{'=' * 60}")
                logger.info("Generated Plan:")
                logger.info(f"{'=' * 60}")
                logger.info(plan)
                logger.info(f"{'=' * 60}\n")

                # Optionally save plan
                if args.save_plan:
                    plan_path = Path(args.output).with_suffix('.plan.txt')
                    plan_path.write_text(plan, encoding='utf-8')
                    logger.milestone(f"Saved plan to: {plan_path}")

            except Exception as e:
                logger.warning(f"Plan generation failed: {e}")
                logger.warning("Proceeding without plan...")
                plan = None

        # Step 3: Generate dialogue
        current_step += 1
        logger.milestone(f"\nStep {current_step}/{total_steps}: Generating dialogue...")
        dialogue, dialogue_usage = generate_dialogue(
            text,
            model=args.model,
            style=args.style,
            audience=args.audience,
            custom_instructions=args.instructions,
            plan=plan,
            unlock_token_limit=args.unlock_token_limit,
            verbosity=verbosity
        )

        # Log usage and cost
        log_usage_and_cost(dialogue_usage, args.model, verbosity)

        # Optionally save dialogue
        if args.save_dialogue:
            dialogue_path = Path(args.output).with_suffix('.txt')
            dialogue_path.write_text(dialogue, encoding='utf-8')
            logger.milestone(f"Saved dialogue to: {dialogue_path}")

        # Step 4: Generate audio
        current_step += 1
        logger.milestone(f"\nStep {current_step}/{total_steps}: Generating podcast audio...")
        logger.info(f"   Voices: HOST1={args.host1_voice}, HOST2={args.host2_voice}")
        output_file = generate_podcast_audio(
            dialogue,
            args.output,
            host1_voice=args.host1_voice,
            host2_voice=args.host2_voice,
            spatial_separation=args.spatial_separation,
            verbosity=verbosity
        )

        # Success!
        logger.milestone("\n" + "=" * 60)
        logger.milestone(f"Podcast created successfully!")
        logger.milestone(f"Output: {output_file}")
        logger.milestone("=" * 60)

    except KeyboardInterrupt:
        logger.error("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
