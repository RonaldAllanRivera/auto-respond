"""
OCR module — extracts text from screenshot images using Tesseract.

Tesseract must be installed on the system:
  Ubuntu/Debian: sudo apt install tesseract-ocr
  macOS:         brew install tesseract
  Windows:       Download from https://github.com/UB-Mannheim/tesseract/wiki

Optimizations:
  - Resize images to optimal size (~1920px width) for faster processing
  - Convert to grayscale to reduce processing time
  - Enhance contrast for better accuracy
  - Use PSM 6 (uniform block of text) for faster recognition
  - Expected: 30-50% faster than default settings
"""

import pytesseract
from PIL import Image, ImageEnhance


def extract_text(image: Image.Image) -> str:
    """
    Run Tesseract OCR on a PIL Image with optimized preprocessing.

    Preprocessing steps:
    1. Resize to optimal size if too large (Tesseract works best at ~1920px width)
    2. Convert to grayscale (faster processing)
    3. Enhance contrast (better accuracy)
    4. Use PSM 6 config (assume uniform block of text, faster than default)

    Args:
        image: PIL Image (e.g. from clipboard or file).

    Returns:
        Extracted text string, stripped of leading/trailing whitespace.
    """
    # Step 1: Resize to optimal size if too large
    # Tesseract is fastest at around 1920px width
    if image.width > 1920:
        ratio = 1920 / image.width
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Step 2: Convert to grayscale (faster OCR processing)
    # Skip if already grayscale
    if image.mode != 'L':
        image = image.convert('L')
    
    # Step 3: Enhance contrast (improves accuracy for Google Meet captions)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)
    
    # Step 4: Run Tesseract with optimized config
    # --psm 6: Assume a single uniform block of text (Google Meet captions)
    # --oem 3: Default OCR Engine Mode (best balance of speed/accuracy)
    text = pytesseract.image_to_string(
        image, 
        lang="eng",
        config='--psm 6 --oem 3'
    )
    
    return text.strip()
