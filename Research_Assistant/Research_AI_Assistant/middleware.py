from django.db import connection


class ClearPostgresRLSContextMiddleware:
    """Clear per-request RLS settings before a pooled connection is reused."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if connection.vendor == "postgresql":
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.user_id', %s, false)",
                        [str(user.pk)],
                    )
                    cursor.execute(
                        "SELECT set_config('app.is_staff', %s, false)",
                        ["true" if user.is_staff else "false"],
                    )
        try:
            return self.get_response(request)
        finally:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.user_id', '', false)"
                    )
                    cursor.execute("SELECT set_config('app.is_staff', '', false)")
