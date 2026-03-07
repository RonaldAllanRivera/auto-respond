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


def _build_prompt(question: str, context: str, max_sentences: int,
                  persona: str = "", description: str = "", source_type: str = "recitation") -> list[dict]:
    """Build the chat messages for the OpenAI API call.
    
    Args:
        question: The question to answer
        context: Lesson context or recent captions
        max_sentences: Max sentences in answer
        persona: AI persona for recitation mode
        description: AI description for recitation mode
        source_type: 'recitation' (live capture) or 'lesson' (uploaded document)
    """
    # Different AI roles based on source type
    if source_type == "lesson":
        # Lesson mode: Act as tutor explaining uploaded document content
        system_msg = (
            f"You are a helpful tutor. Explain concepts from the lesson clearly and concisely "
            f"in {max_sentences} sentence(s) or fewer. Base your answer on the lesson content provided. "
            f"If the question involves a calculation, show the steps briefly."
        )
    else:
        # Recitation mode: Use persona/description for homework help
        if persona:
            system_msg = f"{persona}. "
        else:
            system_msg = "You are a helpful tutor. "
        
        # Add description if provided
        if description:
            system_msg += f"{description}. "
        
        # Add standard instructions
        system_msg += (
            f"Answer the question clearly and concisely in {max_sentences} sentence(s) or fewer. "
            f"If the question involves a calculation, show the steps briefly."
        )

    # Build user message with context
    user_msg = question
    if context:
        if source_type == "lesson":
            # Lesson mode: Provide full lesson content as context
            user_msg = (
                f"Lesson content:\n{context}\n\n"
                f"Question: {question}"
            )
        else:
            # Recitation mode: Provide recent captions as context
            user_msg = (
                f"Recent captions:\n{context}\n\n"
                f"Question: {question}"
            )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def answer_question(question: str, context: str = "",
                    max_sentences: int = 2,
                    persona: str = "", description: str = "",
                    source_type: str = "recitation") -> dict:
    """
    Call OpenAI to answer a question synchronously.

    Args:
        question: The question or prompt to answer
        context: Lesson context or previous captions
        max_sentences: Max sentences in answer
        persona: AI persona/role for recitation mode (e.g., "You are a grade 3 student")
        description: Additional AI instructions for recitation mode (e.g., "Help me impress my teacher")
        source_type: 'recitation' (uses persona) or 'lesson' (uses tutor mode)

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
    messages = _build_prompt(question, context, max_sentences, persona, description, source_type)
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
                              max_sentences: int = 2,
                              persona: str = "", description: str = "",
                              source_type: str = "recitation"):
    """
    Call OpenAI to answer a question with streaming.
    
    Args:
        question: The question to answer
        context: Lesson context or recent captions
        max_sentences: Max sentences in answer
        persona: AI persona for recitation mode
        description: AI description for recitation mode
        source_type: 'recitation' (uses persona) or 'lesson' (uses tutor mode)

    Yields answer tokens as strings. The caller can use these for SSE.
    """
    if not settings.OPENAI_API_KEY:
        yield "(AI answering not configured — set OPENAI_API_KEY)"
        return

    client = _get_client()
    messages = _build_prompt(question, context, max_sentences, persona, description, source_type)
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
