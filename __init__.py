"""
Podcast AI - Generate conversational podcasts from documents using AI
A cost-effective NotebookLM alternative
"""

__version__ = "0.1.0"
__author__ = "Mae Capacite"

# Import main function from the script module
import sys
import os

# Add current directory to path to import podcast_ai script
sys.path.insert(0, os.path.dirname(__file__))

# Now import main from the podcast_ai module
import podcast_ai as _podcast_ai_module
main = _podcast_ai_module.main

__all__ = ["main", "__version__", "__author__"]
