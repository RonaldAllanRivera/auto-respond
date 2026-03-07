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
    Extract all meaningful text from OCR for AI processing.
    
    NEW BEHAVIOR: Sends ALL non-noise text to backend, not just questions.
    The backend AI will decide what to answer based on persona/description.
    
    Examples that will be sent:
    - Questions: "What is Python?", "How does this work?"
    - Prompts: "Explain Python", "Describe photosynthesis"
    - Single words: "photosynthesis", "mitosis"
    - Math: "5 + 3", "1/4 x 1/5"
    - Statements: Any meaningful text

    Returns a list of text segments to send to AI.
    """
    if not text or len(text) < 3:
        return []

    prompts: list[str] = []
    seen: set[str] = set()

    cleaned = clean_transcript_text(text) or text
    
    # If cleaned text is short (single word or phrase), send it as-is
    if len(cleaned.split()) <= 5:
        if not looks_like_noise(cleaned):
            return [cleaned.strip()]
    
    # For longer text, split into sentences and send each
    sentences = _split_sentences(cleaned)

    for sentence in sentences:
        if _is_urlish(sentence):
            continue
        if not sentence or len(sentence) < 3:
            continue
            
        # Send ALL sentences (no keyword filtering)
        prompt = sentence.strip()
        prompt_key = prompt.lower()
        
        if prompt_key not in seen:
            seen.add(prompt_key)
            prompts.append(prompt)

    # Also detect math expressions and send them
    for match in MATH_PATTERN.finditer(cleaned):
        expr = " ".join(match.group(0).strip().split())
        prompt = f"What is {expr}?"
        prompt_key = prompt.lower()
        if prompt_key not in seen:
            seen.add(prompt_key)
            prompts.append(prompt)

    return prompts


def has_questions(text: str) -> bool:
    """Quick check: does the text contain any questions?"""
    return len(detect_questions(text)) > 0
