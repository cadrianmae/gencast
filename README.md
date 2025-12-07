# gencast

🎙️ Generate conversational podcasts from documents using AI - A cost-effective, customisable NotebookLM alternative

## Features

✨ **Multiple Input Formats**
- Markdown (`.md`)
- Plain text (`.txt`)
- PDF (`.pdf`) with intelligent extraction via Mistral AI

🎭 **Podcast Styles**
- **Educational**: Friendly hosts explaining concepts clearly
- **Interview**: Curious host interviewing an expert
- **Casual**: Friends chatting informally about the topic
- **Debate**: Two perspectives discussing different viewpoints

👥 **Target Audiences**
- **General**: Accessible language for general audiences
- **Technical**: Deep-dive with technical terminology
- **Academic**: Scholarly tone with theoretical depth
- **Beginner**: ELI5 style with lots of analogies

🎧 **Premium Audio Features**
- HD TTS (OpenAI `tts-1-hd`)
- Spatial audio with panning and interaural time difference (ITD)
- Customisable voice selection (6 voices available)
- Professional stereo mixing

📝 **Accessibility**
- Automatic SRT subtitle generation via Whisper
- Readable subtitle chunks (not walls of text!)
- VLC-compatible with visualizations

⚡ **Developer Experience**
- Rich progress indicators with live streaming preview
- Real-time dialogue generation display
- Detailed progress bars with time estimates

## Installation

```bash
# Clone the repository
git clone https://github.com/cadrianmae/podcast-ai.git
cd podcast-ai

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in editable mode
pip install -e .

# Set up API keys
export OPENAI_API_KEY="sk-..."
export MISTRAL_API_KEY="..."  # Optional, only needed for PDFs
```

The `gencast` command is now available in your terminal (when venv is active)!

## Usage

### Basic Usage

```bash
# Generate podcast from a document
gencast lecture.md

# Multiple documents
gencast chapter1.md chapter2.md chapter3.md -o combined_podcast.mp3

# Specify output
gencast document.pdf -o my_podcast.mp3
```

### Podcast Styles & Audiences

```bash
# Educational podcast for beginners
gencast machine_learning.md --style educational --audience beginner

# Technical interview
gencast architecture.md --style interview --audience technical

# Casual conversation for academics
gencast research_paper.pdf --style casual --audience academic

# Debate format for general audience
gencast topic.md --style debate --audience general
```

### Voice & Audio Customisation

```bash
# Custom voices (alloy, echo, fable, onyx, nova, shimmer)
gencast doc.md --host1-voice nova --host2-voice echo

# Adjust spatial separation (0.0-1.0)
gencast doc.md --spatial-separation 0.6

# Save dialogue for review
gencast doc.md --save-dialogue
```

### Multi-Provider Support

```bash
# OpenAI models (default)
gencast doc.md --model gpt-4o-mini
gencast doc.md --model gpt-4o

# Anthropic Claude models
gencast doc.md --model anthropic/claude-sonnet-4.5
gencast doc.md --model anthropic/claude-opus-4.5

# Supports 100+ models via LiteLLM
# See https://docs.litellm.ai/docs/providers for full list
```

Set up API keys for your chosen provider:

```bash
# OpenAI (required for audio - TTS and Whisper)
export OPENAI_API_KEY="sk-..."

# Anthropic (optional, for Claude models)
export ANTHROPIC_API_KEY="sk-ant-..."

# Mistral (optional, for PDF processing)
export MISTRAL_API_KEY="..."
```

### Planning Feature

```bash
# Generate comprehensive podcast plan before dialogue
gencast doc.md --with-planning

# Save the plan for review
gencast doc.md --with-planning --save-plan

# Combine with other options
gencast doc.md --with-planning --save-plan --save-dialogue \
  --style interview --audience technical
```

The planning feature creates a structured outline ensuring thorough coverage of all source material before generating the dialogue.

### Advanced Options

```bash
# Combine all features
gencast input.md \
  -o output.mp3 \
  --model anthropic/claude-sonnet-4.5 \
  --style interview \
  --audience technical \
  --host1-voice nova \
  --host2-voice echo \
  --spatial-separation 0.4 \
  --with-planning \
  --save-plan \
  --save-dialogue

# Verbosity control
gencast doc.md --minimal  # Minimal output
gencast doc.md --silent   # Silent mode (errors only)
```

## Cost

Typical cost per 3-minute podcast (~1500 words):
- **Document processing** (Mistral, optional): ~$0.01
- **Dialogue generation** (GPT-4o-mini): ~$0.02-0.05
- **TTS audio** (tts-1-hd): ~$0.06-0.10
- **Whisper transcription**: ~$0.01

**Total**: ~$0.10-0.17 per podcast 💜

## Requirements

- Python 3.8+
- OpenAI API key (required)
- Mistral API key (optional, for PDF processing)

## Architecture

```
gencast/
├── gencast.py             # Main CLI entry point
├── src/
│   ├── dialogue.py        # Multi-provider dialogue (LiteLLM)
│   ├── planning.py        # Podcast planning (LiteLLM)
│   ├── audio.py           # TTS + spatial audio + Whisper (OpenAI)
│   ├── utils.py           # Document reading (MD, TXT, PDF)
│   └── logger.py          # Logging with verbosity levels
├── prompts/               # Podcast style prompts
│   ├── educational.txt
│   ├── interview.txt
│   ├── casual.txt
│   ├── debate.txt
│   └── planning.txt
├── audiences/             # Audience modifiers
│   ├── general.txt
│   ├── technical.txt
│   ├── academic.txt
│   └── beginner.txt
├── pyproject.toml        # Package configuration
├── requirements.txt
└── README.md
```

### Hybrid AI Provider Architecture

**LiteLLM** (chat completions):
- `dialogue.py` and `planning.py` use LiteLLM for multi-provider support
- Supports OpenAI, Anthropic, and 100+ other providers
- Preserves streaming UX for neurodivergent-friendly progress feedback

**OpenAI SDK** (audio processing):
- `audio.py` uses OpenAI SDK for TTS and Whisper
- These APIs are not yet supported by LiteLLM

## Playing Podcasts with Subtitles

To view SRT subtitles with audio in VLC:

1. Open the MP3 file in VLC (subtitles auto-load if same filename)
2. Enable visualizations: **Audio → Visualizations → Spectrometer**
3. Subtitles will appear over the visualization!

The Whisper-generated subtitles are broken into short, readable chunks (1-3 seconds each) for a great viewing experience.

## Development

```bash
# Run tests
pytest

# Type checking (strict mode, warn-only)
basedpyright                 # Full project
basedpyright src/dialogue.py # Single file

# Lint and format
ruff check .
ruff format .
```

## Tips

- Use `--save-dialogue` to review the generated conversation before audio synthesis
- Experiment with different `--spatial-separation` values (0.3-0.6 recommended)
- The `casual` style works great for making dry academic content more engaging
- PDFs work best when text-based (not scanned images)

## Troubleshooting

**"No module named 'audioop'"** (Python 3.13+)
- Already handled! The `audioop-lts` package is included in requirements.

**Subtitles don't show in VLC**
- Enable Audio → Visualizations → Spectrometer
- Ensure .srt file has same name as .mp3

**Poor audio quality**
- Check you're using `tts-1-hd` (default)
- Try different voice combinations

## Acknowledgements

Created by Mae Capacite as a more affordable, customisable alternative to NotebookLM for generating educational podcasts from lecture materials.

## License

MIT
