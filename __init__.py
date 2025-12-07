"""
gencast - Generate conversational podcasts from documents using AI
A cost-effective NotebookLM alternative
"""

__version__ = "0.5.1"
__author__ = "Mae Capacite"

# Import main function from the script module
import sys
import os

# Add current directory to path to import gencast script
sys.path.insert(0, os.path.dirname(__file__))

# Now import main from the gencast module
import gencast as _gencast_module
main = _gencast_module.main

__all__ = ["main", "__version__", "__author__"]
