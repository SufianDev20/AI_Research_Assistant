"""
Vocabulary of LLM request types, shared by models.py (ResponseLog choices),
performance_tracker.py (format-compliance checks) and the backends that pick
a JSON vs. plain-text prompt (ollama_service.py, openrouter_service.py).

Adding a new request type means adding it to REQUEST_TYPE_LABELS below (and
to JSON_REQUEST_TYPES if its prompt demands JSON) — nowhere else.

SUMMARY_REQUIRED_FIELDS mirrors the field labels the "summary" system prompt
(services/prompt_builder.py) instructs the model to output. That prompt is
natural-language text for the LLM, not a list, so it cannot import this
constant directly — if the required fields change, update both.
"""

REQUEST_TYPE_LABELS = {
    "summary": "Paper Summary",
    "title": "Title Generation",
    "qa": "Multi-Paper Q&A",
    "other": "Other",
}

REQUEST_TYPE_CHOICES = list(REQUEST_TYPE_LABELS.items())

# Request types whose prompt demands a JSON reply (qa_llm.QA_SYSTEM_PROMPT).
JSON_REQUEST_TYPES = frozenset({"qa"})

# Mirrors services/prompt_builder.py's "summary" system_prompt field labels.
SUMMARY_REQUIRED_FIELDS = (
    "Authors:",
    "Year:",
    "Source:",
    "DOI:",
    "Summary:",
    "References:",
)
