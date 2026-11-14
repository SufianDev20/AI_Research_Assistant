"""
Prompt builder for the LLM instructions and metadata from the user query

Converts a list of structured paper metadata from the ExtractionService into system prompt (instructions for LLM to output the response) and user message

The models is instructed to:
   - Write a synthesized summary of the papers.
   - Use inline[N] citations markers tied to the numbered reference list.
   - Format each reference in Harvard style.
   - Use ONLY the metadata provided. No fabrication.

Harvard citation format reference:
  Author(s) (Year) Title. Source. DOI.
"""

import re
from typing import List, Dict

system_prompt = """You are an academic research assistant. Summarise each paper individually using only the provided metadata. No fabrication.

For each paper, output exactly this structure with no deviations:

Paper [N]: Title
Authors: [authors from metadata]
Year: [year from metadata]
Source: [source from metadata]
DOI: [doi from metadata]
Summary: [100-120 words describing the problem, method, and findings using only the metadata]
Repeat this block for every paper. Do not combine papers. Omit a field only if it is absent from the metadata.
After all paper blocks, output:
References:
Harvard style: [N] Surname, I. (Year) 'Title'. Source. doi: DOI.
Use up to three authors, then et al. Omit fields not in metadata. Plain text only. No markdown. No abstract available state: Abstract not available - summary based on title and metadata only"""
# ---------------------------------------------------------------------------
# User message builder — assembles the numbered paper block for each request.
# ---------------------------------------------------------------------------


def build_user_message(papers: List[Dict], query: str) -> str:
    """
    Build the user-turn message from extracted paper metadata.

    Args:
        papers: List of dicts produced by ExtractionService.extract_metadata().
                Expected keys: title, authors, abstract, publication_year,
                doi, source, cited_by_count, concepts.
        query:  The original search query. Provides context for the synthesis.

    Returns:
        A formatted string listing all papers with their metadata, ready
        to be sent as the user message to the LLM.
    """
    if not papers:
        return "No papers were found for this query."

    lines = [
        f'Query: "{query}"',
        "Summarize each paper individually:",
        "",
    ]

    for id, paper in enumerate(papers, start=1):
        lines.append(f"Paper {id}: {paper.get('title') or 'N/A'}")

        authors = paper.get("authors", [])
        if authors:
            author_strings = _format_author_list(authors)
            lines.append(f"Authors: {author_strings}")

        year = paper.get("publication_year")
        if year:
            lines.append(f"Year: {year}")

        source = paper.get("source")
        if source and source != "N/A":
            lines.append(f"Source: {source}")

        doi = paper.get("doi")
        if doi and doi != "N/A":
            lines.append(f"DOI: {doi}")

        # Only include abstract if it's substantial (reduce tokens)
        abstract = paper.get("abstract", "").strip()
        if abstract:
            lines.append(
                f"Abstract: {abstract[:500]}..."
            )  # Truncate long abstract lines
        else:
            lines.append(
                "Abstract: Abstract not available - summary based on title and metadata only"
            )

        lines.append("")

    return "\n".join(lines)


# Matches the start of the first real paper block, per the structure
# required above ("Paper [N]: Title"). Free OpenRouter models occasionally
# narrate their own reasoning ("We need to output each paper block...")
# ahead of the actual answer even with reasoning tokens excluded from the
# API response (see OpenRouterService.complete()) -- some providers just
# don't separate the two. Since every valid answer is required to begin
# with this marker, anything before its first occurrence is not part of
# the intended output.
_PAPER_BLOCK_RE = re.compile(r"(?im)^\s*Paper\s*\[?\d+\]?\s*:")


class InvalidSummaryFormat(ValueError):
    """The model did not provide the requested paper summary format."""


def extract_final_summary(raw_content: str) -> str:
    """
    Strip any reasoning/narration preamble a model prepended ahead of the
    first "Paper N:" block, returning only the intended final summary.

    A response without a paper block must not reach the UI: some models
    place their reasoning in message.content instead of a separate field.
    """
    if not raw_content:
        raise InvalidSummaryFormat("No paper summary was returned.")
    match = _PAPER_BLOCK_RE.search(raw_content)
    if not match:
        raise InvalidSummaryFormat("No formatted paper summary was returned.")
    return raw_content[match.start():].strip()


# Output budget for a summary. The old fixed 4000 cap cut long answers off
# before their References list (the answer still came back as "success").
SUMMARY_MAX_TOKENS = 8000
_SUMMARY_TOKENS_BASE = 1500
_SUMMARY_TOKENS_PER_PAPER = 600


def summary_max_tokens(paper_count: int) -> int:
    """Token budget for a summary of ``paper_count`` papers, capped."""
    return min(
        SUMMARY_MAX_TOKENS,
        _SUMMARY_TOKENS_BASE + _SUMMARY_TOKENS_PER_PAPER * max(1, paper_count),
    )


_REFERENCES_RE = re.compile(r"(?im)^\s*References\s*:")


def require_all_papers(paper_count: int):
    """
    Build a response validator for complete(): the reply must contain a
    "Paper N:" block for every paper. A reply cut off by max_tokens misses
    the later blocks, so the call falls through to the next model instead of
    showing the user half a summary. A missing References list is not
    rejected; ensure_references() rebuilds it.
    """

    def validate(raw_content: str) -> None:
        summary = extract_final_summary(raw_content)
        found = len(_PAPER_BLOCK_RE.findall(summary))
        if found < paper_count:
            raise InvalidSummaryFormat(
                f"Summary covers {found} of {paper_count} papers (cut off?)."
            )

    return validate


def _harvard_author(name: str) -> str:
    """"Fabian Pedregosa" -> "Pedregosa, F." (names are "Given Family")."""
    parts = name.replace(",", " ").split()
    if len(parts) < 2:
        return name.strip()
    return f"{parts[-1]}, " + " ".join(f"{p[0]}." for p in parts[:-1])


def build_references(papers: List[Dict]) -> str:
    """Harvard-style References list built from paper metadata alone."""
    lines = ["References:"]
    for n, paper in enumerate(papers, start=1):
        names = [a.get("name", "").strip() for a in paper.get("authors") or [] if a.get("name")]
        authors = "; ".join(_harvard_author(x) for x in names[:3])
        if len(names) > 3:
            authors += " et al."
        parts = [authors] if authors else []
        if paper.get("publication_year"):
            parts.append(f"({paper['publication_year']})")
        parts.append(f"'{paper.get('title') or 'N/A'}'.")
        source = paper.get("source")
        if source and source != "N/A":
            parts.append(f"{source}.")
        doi = paper.get("doi")
        if doi and doi != "N/A":
            parts.append(f"doi: {doi}.")
        lines.append(f"[{n}] " + " ".join(parts))
    return "\n".join(lines)


def ensure_references(summary: str, papers: List[Dict]) -> str:
    """Append a References list built from metadata when the model left it out."""
    if _REFERENCES_RE.search(summary):
        return summary
    return f"{summary}\n\n{build_references(papers)}"


def _format_author_list(authors: List[Dict]) -> str:
    """
    Convert author dicts to a comma-separated display string.

    Each author dict has keys: name, orcid, institutions.
    Only the name field is used here; the LLM handles Harvard formatting.
    """
    names = [a.get("name", "").strip() for a in authors if a.get("name")]
    if not names:
        return ""
    if len(names) > 3:
        return "; ".join(names[:3]) + " et al."
    return "; ".join(names)
