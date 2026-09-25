from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hospitals", "0010_hospitalstaff_credentials"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="hospital",
            index=models.Index(fields=["is_active", "status", "city"], name="hospital_active_status_idx"),
        ),
        migrations.AddIndex(
            model_name="hospital",
            index=models.Index(fields=["is_active", "available_beds", "available_icu_beds"], name="hospital_capacity_idx"),
        ),
        migrations.AddIndex(
            model_name="hospitalstaff",
            index=models.Index(fields=["hospital", "is_active", "is_busy"], name="staff_availability_idx"),
        ),
        migrations.AddIndex(
            model_name="hospitalstaff",
            index=models.Index(fields=["assigned_booking_id"], name="staff_booking_idx"),
        ),
    ]
