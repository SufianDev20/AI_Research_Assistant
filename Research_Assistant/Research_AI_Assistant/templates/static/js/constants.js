// Cross-module constants that must stay in sync with each other (and, for
// the year range, with the backend's DEFAULT_MIN_YEAR/DEFAULT_MAX_YEAR in
// Research_AI_Assistant/constants.py).

export const YEAR_MIN = 1900;
export const YEAR_MAX = 2026;

// Matches QARequestSerializer's paper_ids cap (serializers.py).
export const MAX_ANALYZABLE_PAPERS = 10;
