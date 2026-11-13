"""
Postgres row-level-security session variables, shared by authentication.py
(sets them once a request is authenticated) and middleware.py (clears them
before a pooled connection is reused). Both must set/clear the same two keys
the same way, so that logic lives here instead of twice.
"""

from django.db import connection


def set_rls_context(user) -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.user_id', %s, false)", [str(user.pk)])
        cursor.execute(
            "SELECT set_config('app.is_staff', %s, false)",
            ["true" if user.is_staff else "false"],
        )


def clear_rls_context() -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.user_id', '', false)")
        cursor.execute("SELECT set_config('app.is_staff', '', false)")
