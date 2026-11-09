from django.conf import settings
from django.db import migrations, models


def enable_query_log_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    table = schema_editor.quote_name(
        apps.get_model("Research_AI_Assistant", "QueryLog")._meta.db_table
    )
    policy = schema_editor.quote_name("querylog_owner_isolation")
    schema_editor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    schema_editor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    schema_editor.execute(
        f"""
        CREATE POLICY {policy} ON {table}
        USING (
            owner_id = NULLIF(current_setting('app.user_id', true), '')::bigint
            OR current_setting('app.is_staff', true) = 'true'
        )
        WITH CHECK (
            owner_id = NULLIF(current_setting('app.user_id', true), '')::bigint
            OR current_setting('app.is_staff', true) = 'true'
        )
        """
    )


def disable_query_log_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    table = schema_editor.quote_name(
        apps.get_model("Research_AI_Assistant", "QueryLog")._meta.db_table
    )
    policy = schema_editor.quote_name("querylog_owner_isolation")
    schema_editor.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
    schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


class Migration(migrations.Migration):
    dependencies = [
        ("Research_AI_Assistant", "0010_alter_responselog_request_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="querylog",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="query_logs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(enable_query_log_rls, disable_query_log_rls),
    ]
