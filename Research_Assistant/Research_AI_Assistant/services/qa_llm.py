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
from typing import Dict, List, Optional, Tuple

from .qa_pipeline import resolve_paper_id

# Configuration/Constants

QA_MAX_TOKENS = 800
QA_TEMPERATURE = 0.1

# Logging

logger = logging.getLogger(__name__)

# Q&A System Prompt
QA_SYSTEM_PROMPT = """You are an academic research assistant answering questions about a specific set of papers.

Rules:
1. Use ONLY the page-tagged excerpts provided in the user message. Do not use outside knowledge.
2. If the answer is not supported by the provided excerpts, respond exactly with: "not found in provided papers" as the "answer" field, and return an empty citations list. Only refuse this way when the excerpts truly do not address the question — for broad or overview questions (e.g. "what does this paper cover", "summarize this paper"), synthesize an answer from whatever excerpts are relevant, even if no single excerpt states the summary outright.
3. Keep "answer" to 3-5 sentences maximum. Do not pad or restate the question.
4. Every claim in "answer" must be traceable to at least one citation in "citations". For a broad/overview question, cite the excerpts that best support the overall summary (e.g. the abstract or introduction) rather than refusing because no excerpt is itself a full summary.
5. Each citation must reference a paper_id and page number that actually appear in the provided excerpts. The paper_id is the short alias printed in the excerpt tag (e.g. "P1" from "[P1, Page 3]"); copy it exactly. Do not invent page numbers, and do not cite a page from your general knowledge of how the paper is likely structured (e.g. "the abstract is usually page 1") — only a page you can see printed as "[P1, Page N]" in the excerpts below is valid. Not every page of a paper is shown to you; a page missing from the excerpts is being enforced as absent, not omitted by accident, and citing it will cause the citation to be rejected and shown to the user as unverified.
6. "quoted_snippet" must be a short excerpt (under 15 words) copied verbatim from the cited page's text, so it can be verified against the source.
7. Never write aliases (P1, P2), IDs or URLs in "answer". Refer to a paper only by the label given in the paper list, copied exactly. Start every statement drawn from a paper with "The paper <label> says" (or "The paper <label> reports/finds/argues"), e.g. "The paper Smith and Jones says the model improved recall. The paper Lee et al. says ...". Use one such sentence per paper when several papers are relevant. This does not apply to the exact refusal answer from rule 2.
8. Output ONLY valid JSON matching this exact schema, no markdown code fences, no extra commentary:

{
  "answer": "string",
  "citations": [
    {"paper_id": "P1", "page": 0, "quoted_snippet": "string"}
  ]
}
"""


# Paper legend (aliases + display labels)
def _surname(name: str) -> str:
    parts = (name or "").replace(",", " ").split()
    return parts[-1] if parts else ""


def paper_label(meta: Dict, fallback: str) -> str:
    """
    Short author label for a paper: "Smith", "Smith and Jones", or
    "Smith, Jones et al." (3+ authors). Falls back to the title, then to
    ``fallback`` when the paper has no usable metadata.
    """
    meta = meta or {}
    surnames = [s for s in (_surname(a) for a in (meta.get("authors") or []) if isinstance(a, str)) if s]
    if len(surnames) == 1:
        return surnames[0]
    if len(surnames) == 2:
        return f"{surnames[0]} and {surnames[1]}"
    if surnames:
        return f"{surnames[0]}, {surnames[1]} et al."
    title = (meta.get("title") or "").strip()
    return title or fallback


def build_paper_legend(paper_meta: Optional[Dict], paper_ids) -> Tuple[Dict, Dict]:
    """
    Assign each paper a short alias so the LLM never has to echo an OpenAlex URL.

    Aliases follow sorted paper_id order, matching how build_context orders
    excerpts. Returns (alias_map, papers) where alias_map is {"P1": paper_id}
    and papers is {paper_id: {"alias", "label", "title", "year"}}.
    """
    paper_meta = paper_meta or {}
    alias_map: Dict[str, str] = {}
    papers: Dict[str, Dict] = {}
    for i, paper_id in enumerate(sorted(set(paper_ids)), start=1):
        alias = f"P{i}"
        meta = paper_meta.get(paper_id) or {}
        alias_map[alias] = paper_id
        papers[paper_id] = {
            "alias": alias,
            "label": paper_label(meta, f"Paper {i}"),
            "title": (meta.get("title") or "").strip(),
            "year": meta.get("year"),
        }
    return alias_map, papers


# Prompt Builder
def build_qa_user_message(
    context_chunks: List[Dict],
    question: str,
    papers: Optional[Dict[str, Dict]] = None,
) -> str:
    """
    Build the user-turn message for a Multi-Paper Q&A request.

    Args:
        context_chunks: List of dicts from qa_context_service.py, each with
            keys "paper_id", "page", "text". Expected to already be filtered
            to fit the model's context window before this is called.
        question: The user's natural-language question.
        papers: Optional {paper_id: {"alias", "label", "title", "year"}} from
            build_paper_legend. When given, excerpts are tagged with the short
            alias and a paper list is prepended; otherwise tags use the raw id.

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

    lines = []

    if papers:
        lines.append("Papers (cite by alias; name them in the answer by label):")
        for info in sorted(papers.values(), key=lambda p: int(p["alias"][1:])):
            title = f' "{info["title"]}"' if info.get("title") else ""
            year = f' ({info["year"]})' if info.get("year") else ""
            lines.append(f'{info["alias"]} ={title}{year} — label: {info["label"]}')
        lines.append("")

    lines.extend(["Excerpts from the selected papers:", ""])

    for chunk in context_chunks:
        paper_id = chunk.get(
            "paper_id",
            "UNKNOWN",
        )
        if papers and paper_id in papers:
            paper_id = papers[paper_id]["alias"]

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
        papers: Optional[Dict[str, Dict]] = None,
    ) -> Dict:
        """
        Send a Q&A request to the LLM and parse the structured response.

        When ``papers`` (from build_paper_legend) is given, the model sees
        short aliases and each returned citation's paper_id is mapped back to
        the real paper id before returning.

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
            papers,
        )

        try:
            raw_content = openrouter_service.complete(
                system_prompt=QA_SYSTEM_PROMPT,
                user_message=user_message,
                temperature=QA_TEMPERATURE,
                max_tokens=QA_MAX_TOKENS,
                request_type="qa",
                response_validator=QACompletionService._parse_response,
            )

        except Exception as exc:
            raise QACompletionError(f"LLM completion failed: {exc}") from exc

        result = QACompletionService._parse_response(raw_content)

        if papers:
            alias_map = {info["alias"]: pid for pid, info in papers.items()}
            for citation in result["citations"]:
                citation["paper_id"] = resolve_paper_id(
                    citation["paper_id"], alias_map, papers.keys()
                )

        return result

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
