"""
Question and calculation detector for OCR-extracted text.

Scans text for:
  1. Sentences ending with '?'
  2. Sentences starting with interrogative words (what, why, where, etc.)
  3. Math expressions (e.g. "1 + 1", "what is 5 x 3")
"""

import re

INTERROGATIVE_WORDS = {
    "what", "when", "where", "who", "why", "how",
    "is", "are", "do", "does", "did",
    "can", "could", "will", "would", "should",
    "which", "whom", "whose",
}

# Pattern for math expressions: digits with operators
MATH_PATTERN = re.compile(
    r"\b\d+\s*[+\-*/×÷xX]\s*\d+",
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on '.', '!', '?', or newlines."""
    parts = re.split(r"[.!?\n]+", text)
    return [s.strip() for s in parts if s.strip()]


def detect_questions(text: str) -> list[str]:
    """
    Extract all questions from OCR text.

    Returns a list of question strings found in the text.
    """
    if not text or len(text) < 3:
        return []

    questions = []
    seen = set()

    # Strategy 1: Lines/sentences ending with '?'
    for match in re.finditer(r"[^.!?\n]*\?", text):
        q = match.group(0).strip()
        if q and len(q) > 3 and q.lower() not in seen:
            seen.add(q.lower())
            questions.append(q)

    # Strategy 2: Sentences starting with interrogative words
    sentences = _split_sentences(text)
    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        first_word = words[0].lower().rstrip(".,;:")
        if first_word in INTERROGATIVE_WORDS:
            # Add '?' if not already present
            q = sentence if sentence.endswith("?") else sentence + "?"
            if q.lower() not in seen and len(q) > 3:
                seen.add(q.lower())
                questions.append(q)

    # Strategy 3: Math expressions
    for match in MATH_PATTERN.finditer(text):
        expr = match.group(0).strip()
        q = f"What is {expr}?"
        if q.lower() not in seen:
            seen.add(q.lower())
            questions.append(q)

    return questions


def has_questions(text: str) -> bool:
    """Quick check: does the text contain any questions?"""
    return len(detect_questions(text)) > 0
