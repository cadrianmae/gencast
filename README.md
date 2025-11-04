# Podcast AI (gencast)

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

### Advanced

```bash
# Use different GPT model
gencast doc.md --model gpt-4

# All options
gencast input.md \
  -o output.mp3 \
  --style interview \
  --audience technical \
  --host1-voice nova \
  --host2-voice echo \
  --spatial-separation 0.4 \
  --save-dialogue
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
podcast-ai/
├── podcast_ai.py          # Main CLI entry point
├── src/
│   ├── dialogue.py        # GPT-4 dialogue generation with streaming
│   ├── audio.py           # TTS + spatial audio + Whisper SRT
│   └── utils.py           # Document reading (MD, TXT, PDF)
├── prompts/               # Podcast style prompts
│   ├── educational.txt
│   ├── interview.txt
│   ├── casual.txt
│   └── debate.txt
├── audiences/             # Audience modifiers
│   ├── general.txt
│   ├── technical.txt
│   ├── academic.txt
│   └── beginner.txt
├── pyproject.toml        # Package configuration
├── requirements.txt
└── README.md
```

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

# Format code
black .

# Lint
ruff check .
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

Created by Mae Capacite (C21348423) as a more affordable, customisable alternative to NotebookLM for generating educational podcasts from lecture materials.

## License

MIT
