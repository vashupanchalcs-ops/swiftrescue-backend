import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0007_booking_assigned_bed_id_booking_assigned_bed_number_and_more")]

    operations = [
        migrations.CreateModel(
            name="PatientConditionPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("photo_type", models.CharField(choices=[("ecg", "ECG"), ("patient", "Patient condition"), ("patient_id", "Patient ID"), ("vitals", "Vitals / monitor"), ("documents", "Medical document"), ("other", "Other")], default="patient", max_length=30)),
                ("instruction", models.CharField(blank=True, default="", max_length=300)),
                ("image", models.FileField(upload_to="condition_photos/%Y/%m/%d/")),
                ("original_name", models.CharField(blank=True, default="", max_length=255)),
                ("content_type", models.CharField(blank=True, default="", max_length=100)),
                ("uploader_role", models.CharField(default="driver", max_length=30)),
                ("uploader_name", models.CharField(blank=True, default="", max_length=120)),
                ("uploader_email", models.EmailField(blank=True, default="", max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="condition_photos", to="bookings.booking")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
