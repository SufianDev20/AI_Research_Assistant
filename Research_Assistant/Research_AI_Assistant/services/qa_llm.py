"""
Q&A-specific LLM services for Multi-Paper Q&A.

This module contains everything that communicates with the LLM:

    - Q&A system prompt
    - User-message construction
    - LLM completion
    - JSON parsing and structural validation

The paper/data processing pipeline itself is kept in qa_pipeline.py.
"""

import json, logging
from typing import Dict, List

# Configuration/Constants

QA_MAX_TOKENS = 800
QA_TEMPERATURE = 0.1

# Logging

logger = logging.getLogger(__name__)

# Q&A System Prompt
QA_SYSTEM_PROMPT = """You are an academic research assistant answering questions about a specific set of papers.

Rules:
1. Use ONLY the page-tagged excerpts provided in the user message. Do not use outside knowledge.
2. If the answer is not supported by the provided excerpts, respond exactly with: "not found in provided papers" as the "answer" field, and return an empty citations list.
3. Keep "answer" to 3-5 sentences maximum. Do not pad or restate the question.
4. Every claim in "answer" must be traceable to at least one citation in "citations".
5. Each citation must reference a paper_id and page number that actually appear in the provided excerpts. Do not invent page numbers.
6. "quoted_snippet" must be a short excerpt (under 15 words) copied verbatim from the cited page's text, so it can be verified against the source.
7. Output ONLY valid JSON matching this exact schema, no markdown code fences, no extra commentary:

{
  "answer": "string",
  "citations": [
    {"paper_id": "string", "page": 0, "quoted_snippet": "string"}
  ]
}
"""


# Prompt Builder
def build_qa_user_message(
    context_chunks: List[Dict],
    question: str,
) -> str:
    """
    Build the user-turn message for a Multi-Paper Q&A request.

    Args:
        context_chunks: List of dicts from qa_context_service.py, each with
            keys "paper_id", "page", "text". Expected to already be filtered
            to fit the model's context window before this is called.
        question: The user's natural-language question.

    Returns:
        A formatted string listing every chunk as
        "[Paper ID, Page N]: text", followed by the question, ready to send
        as the user message.

    Raises:
        ValueError: If context_chunks is empty, since answering a question
            with zero source material would force the model to fabricate.
    """
    if not context_chunks:
        raise ValueError(
            "context_chunks is empty; refusing to build a Q&A prompt with no "
            "source material to cite."
        )

    if not question or not question.strip():
        raise ValueError("question must be a non-empty string.")

    lines = [
        "Excerpts from the selected papers:",
        "",
    ]

    for chunk in context_chunks:
        paper_id = chunk.get(
            "paper_id",
            "UNKNOWN",
        )

        page = chunk.get(
            "page",
            "UNKNOWN",
        )

        text = chunk.get(
            "text",
            "",
        ).strip()

        if not text:
            continue

        lines.append(f"[{paper_id}, Page {page}]: {text}")

        lines.append("")

    lines.append(f'Question: "{question.strip()}"')

    lines.append(
        "Answer using only the excerpts above. " "Output valid JSON per the schema."
    )

    return "\n".join(lines)


# LLM Completion
class QACompletionError(Exception):
    """Raised when the LLM call fails or returns unparseable JSON."""

    pass


class QACompletionService:
    """Call the LLM for a Q&A turn and parse its JSON response."""

    @staticmethod
    def ask(
        openrouter_service,
        context_chunks: List[Dict],
        question: str,
    ) -> Dict:
        """
        Send a Q&A request to the LLM and parse the structured response.

        Args:
            openrouter_service: An instance of OpenRouterService. Passed in rather than instantiated here so the view controls the request lifecycle and so tests can inject a fake.
            context_chunks: Ordered chunk list from
            qa_context_service.build_context().question: The user's question.

        Returns:
            dict with keys "answer" (str) and "citations" (list of dicts,
            each with "paper_id", "page", "quoted_snippet"), exactly as
            returned by the model, before validation.

        Raises:
            QACompletionError: If the LLM call fails after all fallbacks,
            or if the model's response is not valid JSON matching the
            expected top-level shape. Callers must not let this crash
            the whole request; catch it and return a structured error.
        """
        user_message = build_qa_user_message(
            context_chunks,
            question,
        )

        try:
            raw_content = openrouter_service.complete(
                system_prompt=QA_SYSTEM_PROMPT,
                user_message=user_message,
                temperature=QA_TEMPERATURE,
                max_tokens=QA_MAX_TOKENS,
                request_type="qa",
            )

        except Exception as exc:
            raise QACompletionError(f"LLM completion failed: {exc}") from exc

        return QACompletionService._parse_response(raw_content)

    @staticmethod
    def _parse_response(
        raw_content: str,
    ) -> Dict:
        """
        Parse and structurally validate the model's JSON output.

        Strips markdown code fences defensively (some free-tier models wrap
        JSON in ```json blocks despite instructions not to), then validates
        the top-level "answer"/"citations" shape before returning.
        """
        cleaned = raw_content.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")

            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]

            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)

        except (ValueError, TypeError) as exc:
            raise QACompletionError(f"Model did not return valid JSON: {exc}") from exc

        if not isinstance(parsed, dict) or "answer" not in parsed:
            raise QACompletionError(
                "Model response is missing the required 'answer' field."
            )

        citations = parsed.get(
            "citations",
            [],
        )

        if not isinstance(citations, list):
            raise QACompletionError("Model response's 'citations' is not a list.")

        clean_citations = []

        for item in citations:
            if not isinstance(item, dict):
                continue

            clean_citations.append(
                {
                    "paper_id": item.get("paper_id"),
                    "page": item.get("page"),
                    "quoted_snippet": item.get(
                        "quoted_snippet",
                        "",
                    ),
                }
            )

        return {
            "answer": str(
                parsed.get(
                    "answer",
                    "",
                )
            ),
            "citations": clean_citations,
        }
