import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the Django admin user from environment variables."

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_ADMIN_USERNAME", "").strip()
        email = os.getenv("DJANGO_ADMIN_EMAIL", "").strip()
        password = os.getenv("DJANGO_ADMIN_PASSWORD", "")

        if not username or not email or not password:
            raise CommandError(
                "Set DJANGO_ADMIN_USERNAME, DJANGO_ADMIN_EMAIL and DJANGO_ADMIN_PASSWORD."
            )

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Admin user {'created' if created else 'updated'}: {username}"))
