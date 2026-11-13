"""
Cross-cutting constants shared by more than one layer. A value here is one
both the Python views/services and the frontend JS need to agree on.
"""

# The workspace search UI's year-range slider defaults to this full span, so
# the frontend always sends it even when the user applied no year filter.
# views.search treats exactly this range as "no filter" (so the local corpus,
# which can't honour a year filter, still gets tried first); OpenAlexService
# treats it as "no filter" too (so it skips an unnecessary filter clause).
# Keep in sync with the frontend's default range (templates/static/js).
DEFAULT_MIN_YEAR = 1900
DEFAULT_MAX_YEAR = 2026
