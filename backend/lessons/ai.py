"""
AI answering module — calls OpenAI to answer detected questions.

Uses the student's grade level and max_sentences preferences from their
SubscriberProfile to tailor the response.
"""

import logging
import time

from django.conf import settings

from openai import OpenAI

logger = logging.getLogger(__name__)


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
    )


def _build_prompt(question: str, context: str, grade_level: int, max_sentences: int) -> list[dict]:
    """Build the chat messages for the OpenAI API call."""
    system_msg = (
        f"You are a helpful teaching assistant for a Grade {grade_level} student. "
        f"Answer the question clearly and concisely in {max_sentences} sentence(s) or fewer. "
        f"Use simple language appropriate for the student's grade level. "
        f"If the question involves a calculation, show the steps briefly."
    )

    user_msg = question
    if context:
        user_msg = (
            f"Context from the lesson:\n{context}\n\n"
            f"Question: {question}"
        )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def answer_question(question: str, context: str = "",
                    grade_level: int = 3, max_sentences: int = 2) -> dict:
    """
    Call OpenAI to answer a question synchronously.

    Returns:
        {
            "answer": "The answer text...",
            "model": "gpt-4o-mini",
            "latency_ms": 1234,
        }
    """
    if not settings.OPENAI_API_KEY:
        return {
            "answer": "(AI answering not configured — set OPENAI_API_KEY)",
            "model": "",
            "latency_ms": 0,
        }

    client = _get_client()
    messages = _build_prompt(question, context, grade_level, max_sentences)
    model = settings.OPENAI_MODEL

    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=300,
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()
        latency_ms = int((time.time() - start) * 1000)

        return {
            "answer": answer,
            "model": model,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error("OpenAI API error: %s", e)
        return {
            "answer": f"(AI error: {e})",
            "model": model,
            "latency_ms": latency_ms,
        }


def answer_question_streaming(question: str, context: str = "",
                              grade_level: int = 3, max_sentences: int = 2):
    """
    Call OpenAI to answer a question with streaming.

    Yields answer tokens as strings. The caller can use these for SSE.
    """
    if not settings.OPENAI_API_KEY:
        yield "(AI answering not configured — set OPENAI_API_KEY)"
        return

    client = _get_client()
    messages = _build_prompt(question, context, grade_level, max_sentences)
    model = settings.OPENAI_MODEL

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=300,
            temperature=0.3,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
    except Exception as e:
        logger.error("OpenAI streaming error: %s", e)
        yield f"(AI error: {e})"
