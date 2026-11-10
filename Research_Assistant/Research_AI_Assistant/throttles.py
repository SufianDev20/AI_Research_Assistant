"""
Rate limits for the API.

Every API view except api_root requires sign-in, so these key on the user
(UserRateThrottle). AnonRateThrottle is skipped by DRF for any authenticated
request and would leave signed-in users unlimited.

Counters are stored in the "throttle" cache (a database table, see
settings.CACHES) so that all gunicorn workers share one count. With a
per-process cache each limit would be multiplied by the number of workers.

Each class needs its own `scope`: it is part of the cache key, so two classes
with the same scope would share one counter.
"""

from django.core.cache import caches
from rest_framework.throttling import UserRateThrottle


class SharedUserRateThrottle(UserRateThrottle):
    cache = caches["throttle"]


class SearchRateThrottle(SharedUserRateThrottle):
    """Paper and author search."""

    scope = "search"
    rate = "60/m"


class GenerateTitle(SharedUserRateThrottle):
    """LLM calls: shared by generate_title and summarise."""

    scope = "llm"
    rate = "20/m"


class MultiPaperQAThrottle(SharedUserRateThrottle):
    """PDF fetch + OCR + LLM call makes this the most expensive endpoint."""

    scope = "multi_paper_qa"
    rate = "10/m"


class PerformanceRateThrottle(SharedUserRateThrottle):
    """Staff-only performance API."""

    scope = "performance"
    rate = "60/m"
