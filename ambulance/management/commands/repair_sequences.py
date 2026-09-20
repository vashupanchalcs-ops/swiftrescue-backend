from django.core.management.base import BaseCommand

from ambulance.sequence_repair import repair_postgres_sequences


class Command(BaseCommand):
    help = "Align PostgreSQL auto-increment sequences with existing primary keys."

    def handle(self, *args, **options):
        if self.connection_vendor() != "postgresql":
            self.stdout.write("Sequence repair skipped; the active database is not PostgreSQL.")
            return

        repaired = repair_postgres_sequences()
        self.stdout.write(self.style.SUCCESS(f"Repaired {repaired} PostgreSQL sequence(s)."))

    @staticmethod
    def connection_vendor():
        from django.db import connection

        return connection.vendor
