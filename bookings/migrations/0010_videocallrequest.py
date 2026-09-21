from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0009_alter_booking_options_and_more"),
        ("hospitals", "0007_seed_real_hospital_staff_data"),
    ]

    operations = [
        migrations.CreateModel(
            name="VideoCallRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("driver_email", models.EmailField(blank=True, default="", max_length=254)),
                ("driver_name", models.CharField(blank=True, default="", max_length=120)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("cancelled", "Cancelled")], db_index=True, default="pending", max_length=20)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("joined_at", models.DateTimeField(blank=True, null=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="video_call_requests", to="bookings.booking")),
                ("staff", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="video_call_requests", to="hospitals.hospitalstaff")),
            ],
            options={
                "ordering": ["-requested_at", "-id"],
                "indexes": [
                    models.Index(fields=["booking", "status"], name="bookings_vi_booking_2f14c7_idx"),
                    models.Index(fields=["staff", "status"], name="bookings_vi_staff_i_6e7bc1_idx"),
                ],
            },
        ),
    ]
