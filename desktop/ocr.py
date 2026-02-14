"""
OCR module — extracts text from screenshot images using Tesseract.

Tesseract must be installed on the system:
  Ubuntu/Debian: sudo apt install tesseract-ocr
  macOS:         brew install tesseract
  Windows:       Download from https://github.com/UB-Mannheim/tesseract/wiki
"""

import pytesseract
from PIL import Image


def extract_text(image: Image.Image) -> str:
    """
    Run Tesseract OCR on a PIL Image and return the extracted text.

    Args:
        image: PIL Image (e.g. from clipboard or file).

    Returns:
        Extracted text string, stripped of leading/trailing whitespace.
    """
    text = pytesseract.image_to_string(image, lang="eng")
    return text.strip()
