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
    "which", "whom", "whose",
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
    Extract all questions from OCR text.

    Returns a list of question strings found in the text.
    """
    if not text or len(text) < 3:
        return []

    questions: list[str] = []
    seen: set[str] = set()

    cleaned = clean_transcript_text(text) or text
    sentences = _split_sentences(cleaned)

    for sentence in sentences:
        if _is_urlish(sentence):
            continue
        words = sentence.split()
        if not words:
            continue

        first_word = re.sub(r"[^a-zA-Z]", "", words[0].lower())
        if first_word in INTERROGATIVE_WORDS:
            q = sentence.strip()
            if not q.endswith("?"):
                q += "?"
            qk = q.lower()
            if len(q) > 3 and qk not in seen:
                seen.add(qk)
                questions.append(q)

    for match in MATH_PATTERN.finditer(cleaned):
        expr = " ".join(match.group(0).strip().split())
        q = f"What is {expr}?"
        qk = q.lower()
        if qk not in seen:
            seen.add(qk)
            questions.append(q)

    return questions


def has_questions(text: str) -> bool:
    """Quick check: does the text contain any questions?"""
    return len(detect_questions(text)) > 0
