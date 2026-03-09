"""
Question and prompt detector for OCR-extracted text.

Scans text for:
  1. Interrogative questions (what, why, where, who, when, how, etc.)
  2. Imperative prompts (explain, describe, define, compare, etc.)
  3. Math expressions (e.g. "1 + 1", "what is 5 x 3")
  
All detected prompts are sent to the AI for answering.
"""

import re

INTERROGATIVE_WORDS = {
    "what", "when", "where", "who", "why", "how",
    "which", "whom", "whose",
}

# Imperative/command words that indicate questions or prompts
IMPERATIVE_WORDS = {
    "explain", "describe", "define", "compare", "contrast",
    "summarize", "discuss", "analyze", "evaluate", "identify",
    "list", "name", "state", "give", "provide", "show",
    "tell", "calculate", "solve", "find", "determine",
}

_URL_RE = re.compile(
    r"(?i)\b(?:https?://|www\.)\S+|\b\S+\.(?:com|net|org|io|gov|edu)\b\S*|\bdocs\.google\.com\b\S*"
)

_UI_TRASH_SUBSTRINGS = (
    "file edit view insert format tools extensions help",
    "saved to drive",
    "askgoogle",
)

# Pattern for math expressions including fractions (e.g. "1/4 x 1/5", "2 × 3", "10 ÷ 2")
_NUM_TOKEN = r"\d+(?:\s*/\s*\d+)?"
MATH_PATTERN = re.compile(
    rf"\b{_NUM_TOKEN}(?:\s*[+\-*×÷xX]\s*{_NUM_TOKEN})+\b",
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on '.', '!', '?', or newlines."""
    if not text:
        return []
    normalized = re.sub(r"\s+", " ", text.replace("\n", " ").replace("\r", " "))
    parts = re.split(r"[.!?]+", normalized)
    return [s.strip() for s in parts if s.strip()]


def _is_urlish(text: str) -> bool:
    if not text:
        return False
    if _URL_RE.search(text):
        return True
    t = text.strip().lower()
    if t.startswith("com/") or t.startswith("www/"):
        return True
    if t.count("/") >= 2 and any(x in t for x in (".com", ".net", ".org", "docs.google")):
        return True
    return False


def clean_transcript_text(text: str) -> str:
    if not text:
        return ""

    lines = []
    for raw_line in re.split(r"\r?\n+", text):
        line = raw_line.strip()
        if len(line) < 3:
            continue
        if _is_urlish(line):
            continue
        low = " ".join(line.lower().split())
        if any(s in low for s in _UI_TRASH_SUBSTRINGS):
            continue
        lines.append(line)

    return "\n".join(lines).strip()


def looks_like_noise(text: str) -> bool:
    if not text:
        return True
    low = " ".join(text.lower().split())
    if _URL_RE.search(text):
        return True
    if any(s in low for s in _UI_TRASH_SUBSTRINGS):
        return True
    return False


def detect_questions(text: str) -> list[str]:
    """
    Return the full OCR text as a single question for AI processing.
    
    NEW BEHAVIOR: Sends the ENTIRE screenshot text as ONE question.
    The AI is smart enough to understand:
    - Multiple-choice questions (with a., b., c. options)
    - Questions without '?' (Google Meet often omits punctuation)
    - Statements that need explanation
    - Any meaningful text from the screenshot
    
    Examples:
    - "What is Python?" → ["What is Python?"]
    - "What is X?\na. Option A\nb. Option B" → ["What is X?\na. Option A\nb. Option B"]
    - "Explain photosynthesis" → ["Explain photosynthesis"]
    - "photosynthesis" → ["photosynthesis"]

    Returns a list with ONE item: the full cleaned text from the screenshot.
    """
    if not text or len(text) < 3:
        return []

    # Clean the text (remove URLs, UI noise, etc.)
    cleaned = clean_transcript_text(text)
    
    # If cleaning removed everything, check if original was noise
    if not cleaned or len(cleaned) < 3:
        if looks_like_noise(text):
            return []
        # Use original text if cleaning was too aggressive
        cleaned = text.strip()
    
    # Return the FULL text as a single question
    # The AI will understand the context and answer appropriately
    return [cleaned]


def has_questions(text: str) -> bool:
    """Quick check: does the text contain any questions?"""
    return len(detect_questions(text)) > 0
