#!/usr/bin/env python3
"""
Podcast AI - Generate conversational podcasts from documents
Author: Mae Capacite
"""

import argparse
import os
import sys
from pathlib import Path

from src.utils import extract_text
from src.dialogue import generate_dialogue
from src.audio import generate_podcast_audio, DEFAULT_VOICES
from src.logger import setup_logger, get_logger


def check_api_keys():
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


def main():
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
        default='gpt-4o-mini',
        help='OpenAI model for dialogue generation (default: gpt-4o-mini)'
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
    logger.info("Podcast AI - Document to Podcast Converter")
    logger.info("=" * 60)

    # Check API keys
    check_api_keys()

    # Verify input files exist
    for filepath in args.inputs:
        if not Path(filepath).exists():
            logger.error(f"File not found: {filepath}")
            sys.exit(1)

    try:
        # Step 1: Extract text from documents
        logger.milestone(f"\nStep 1/3: Reading {len(args.inputs)} document(s)...")
        text = extract_text(args.inputs, verbosity=verbosity)
        logger.info(f"Extracted {len(text)} characters")

        # Step 2: Generate dialogue
        logger.milestone(f"\nStep 2/3: Generating dialogue...")
        dialogue = generate_dialogue(
            text,
            model=args.model,
            style=args.style,
            audience=args.audience,
            custom_instructions=args.instructions,
            verbosity=verbosity
        )

        # Optionally save dialogue
        if args.save_dialogue:
            dialogue_path = Path(args.output).with_suffix('.txt')
            dialogue_path.write_text(dialogue, encoding='utf-8')
            logger.milestone(f"Saved dialogue to: {dialogue_path}")

        # Step 3: Generate audio
        logger.milestone(f"\nStep 3/3: Generating podcast audio...")
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
