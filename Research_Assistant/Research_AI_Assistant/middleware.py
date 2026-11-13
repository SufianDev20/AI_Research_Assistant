from django.db import connection

from .rls_context import clear_rls_context, set_rls_context


class ClearPostgresRLSContextMiddleware:
    """Clear per-request RLS settings before a pooled connection is reused."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if connection.vendor == "postgresql":
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                set_rls_context(user)
        try:
            return self.get_response(request)
        finally:
            clear_rls_context()
