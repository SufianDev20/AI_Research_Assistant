from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    # Creates the table behind settings.CACHES["throttle"]. Done here rather
    # than as a separate `createcachetable` deploy step, because a missing
    # table would make every throttled API request fail. The command skips
    # tables that already exist.
    call_command(
        "createcachetable", database=schema_editor.connection.alias, verbosity=0
    )


class Migration(migrations.Migration):

    dependencies = [
        ("Research_AI_Assistant", "0011_querylog_owner_rls"),
    ]

    operations = [
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]
