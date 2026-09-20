"""Create the configured deployment administrator once."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from ambulance.sequence_repair import repair_postgres_sequences


class Command(BaseCommand):
    help = "Create the configured Django administrator when it does not exist."

    def handle(self, *args, **options):
        repaired = repair_postgres_sequences()
        if repaired:
            self.stdout.write(f"Repaired {repaired} PostgreSQL sequence(s) before admin setup.")

        email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
        password = os.getenv("ADMIN_PASSWORD") or ""
        username = (os.getenv("ADMIN_USERNAME") or email.split("@", 1)[0]).strip()
        if not email or not password or not username:
            self.stdout.write("Admin secrets are not configured; skipping administrator setup.")
            return

        user_model = get_user_model()
        if user_model.objects.filter(username=username).exists():
            self.stdout.write("Administrator already exists; no account changes made.")
            return

        # Preserve the existing deployment administrator when the configured
        # username is changed to match the legacy admin account name.
        existing = user_model.objects.filter(email__iexact=email).first()
        if existing:
            existing.username = username
            existing.is_staff = True
            existing.is_superuser = True
            existing.save(update_fields=["username", "is_staff", "is_superuser"])
            self.stdout.write(self.style.SUCCESS(f"Administrator renamed: {existing.username}"))
            return

        user = user_model.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Administrator created: {user.username}"))
