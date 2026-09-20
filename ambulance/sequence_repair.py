"""Helpers for keeping PostgreSQL auto-increment sequences in sync."""

from django.apps import apps
from django.db import connection
from django.db.models import AutoField, BigAutoField, SmallAutoField


def repair_postgres_sequences():
    """Advance every integer primary-key sequence past the current max id.

    This is intentionally a non-destructive repair: it never deletes or
    changes existing rows.  It is useful after importing rows with explicit
    primary keys, which can leave PostgreSQL sequences behind the data.
    """
    if connection.vendor != "postgresql":
        return 0

    repaired = 0
    with connection.cursor() as cursor:
        for model in apps.get_models():
            primary_key = model._meta.pk
            if not isinstance(primary_key, (AutoField, BigAutoField, SmallAutoField)):
                continue

            table_name = model._meta.db_table
            column_name = primary_key.column
            quoted_table = connection.ops.quote_name(table_name)
            quoted_column = connection.ops.quote_name(column_name)

            cursor.execute(f"SELECT MAX({quoted_column}) FROM {quoted_table}")
            max_id = cursor.fetchone()[0]
            if max_id is None:
                continue

            cursor.execute(
                "SELECT pg_get_serial_sequence(%s, %s)",
                [table_name, column_name],
            )
            sequence_name = cursor.fetchone()[0]
            if not sequence_name:
                continue

            # is_called=true makes the next generated id max_id + 1.
            cursor.execute("SELECT setval(%s, %s, true)", [sequence_name, max_id])
            repaired += 1

    return repaired
