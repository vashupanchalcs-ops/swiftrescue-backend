"""Keep legacy deployment commands compatible without changing accounts."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Retain compatibility with the legacy Render startup command."

    def handle(self, *args, **options):
        self.stdout.write("Administrator setup skipped during automated deployment.")
