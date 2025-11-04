"""
File utilities for reading and processing various document formats.
Uses Mistral AI for intelligent PDF understanding.
"""

import os
from pathlib import Path
from typing import List
from mistralai import Mistral
from pypdf import PdfReader


def read_markdown(filepath: str) -> str:
    """
    Read a markdown file and return its contents.

    Args:
        filepath: Path to the markdown file

    Returns:
        String containing the file contents
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def read_text(filepath: str) -> str:
    """
    Read a plain text file and return its contents.

    Args:
        filepath: Path to the text file

    Returns:
        String containing the file contents
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def read_pdf_with_mistral(filepath: str) -> str:
    """
    Read a PDF file and use Mistral AI to extract and understand its content.
    Falls back to basic pypdf extraction if Mistral AI is not available.

    Args:
        filepath: Path to the PDF file

    Returns:
        String containing the extracted and processed content
    """
    # First extract raw text from PDF
    reader = PdfReader(filepath)
    raw_text = ""
    for page in reader.pages:
        raw_text += page.extract_text() + "\n\n"

    # Try to use Mistral AI for intelligent processing
    api_key = os.environ.get('MISTRAL_API_KEY')
    if not api_key:
        print("⚠️  MISTRAL_API_KEY not found. Using basic PDF extraction.")
        return raw_text

    try:
        client = Mistral(api_key=api_key)

        # Use Mistral to clean and structure the extracted text
        response = client.chat.complete(
            model="mistral-large-latest",
            messages=[
                {
                    "role": "system",
                    "content": "You are a document processing assistant. Extract and clean the following PDF text, preserving key information, structure, and meaning. Remove formatting artifacts and make the text clear and readable."
                },
                {
                    "role": "user",
                    "content": f"Please clean and structure this PDF text:\n\n{raw_text}"
                }
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"⚠️  Mistral AI processing failed: {e}")
        print("Falling back to basic PDF extraction.")
        return raw_text


def read_file(filepath: str) -> str:
    """
    Read a file and return its contents, routing to appropriate reader.

    Args:
        filepath: Path to the file

    Returns:
        String containing the file contents

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file type is not supported
    """
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    extension = path.suffix.lower()

    if extension == '.md':
        return read_markdown(filepath)
    elif extension == '.txt':
        return read_text(filepath)
    elif extension == '.pdf':
        return read_pdf_with_mistral(filepath)
    else:
        raise ValueError(f"Unsupported file type: {extension}")


def extract_text(filepaths: List[str]) -> str:
    """
    Extract and concatenate text from multiple files.

    Args:
        filepaths: List of file paths to process

    Returns:
        Concatenated string of all file contents
    """
    texts = []

    for filepath in filepaths:
        print(f"📄 Reading: {filepath}")
        try:
            content = read_file(filepath)
            texts.append(f"=== {Path(filepath).name} ===\n\n{content}\n\n")
        except Exception as e:
            print(f"❌ Error reading {filepath}: {e}")
            continue

    if not texts:
        raise ValueError("No files were successfully processed")

    return "\n".join(texts)
