from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [("ambulance", "0011_ambulance_battery_percentage")]
    operations = [
        migrations.CreateModel(
            name="BookingTrackingState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("booking_id", models.IntegerField(db_index=True, unique=True)),
                ("phase", models.CharField(choices=[("to_patient", "To patient"), ("to_hospital", "To hospital"), ("completed", "Completed")], default="to_patient", max_length=20)),
                ("patient_lat", models.FloatField(blank=True, null=True)), ("patient_lng", models.FloatField(blank=True, null=True)),
                ("hospital_lat", models.FloatField(blank=True, null=True)), ("hospital_lng", models.FloatField(blank=True, null=True)),
                ("ambulance_id", models.IntegerField(blank=True, null=True)), ("ambulance_lat", models.FloatField(blank=True, null=True)),
                ("ambulance_lng", models.FloatField(blank=True, null=True)), ("ambulance_heading", models.FloatField(blank=True, null=True)),
                ("last_location_at", models.DateTimeField(blank=True, null=True)), ("last_checkpoint_at", models.DateTimeField(blank=True, null=True)),
                ("sequence", models.PositiveIntegerField(default=0)), ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"indexes": [models.Index(fields=["phase", "updated_at"], name="ambulance_b_phase_8d5e0e_idx")]},
        ),
        migrations.CreateModel(
            name="TrackingRoute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("route_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("booking_id", models.IntegerField(db_index=True)),
                ("version", models.PositiveIntegerField(default=1)), ("phase", models.CharField(choices=[("to_patient", "To patient"), ("to_hospital", "To hospital"), ("completed", "Completed")], max_length=20)),
                ("origin_lat", models.FloatField()), ("origin_lng", models.FloatField()), ("destination_lat", models.FloatField()), ("destination_lng", models.FloatField()),
                ("distance_m", models.PositiveIntegerField(default=0)), ("duration_s", models.PositiveIntegerField(default=0)), ("traffic_duration_s", models.PositiveIntegerField(blank=True, null=True)),
                ("encoded_polyline", models.TextField(blank=True)), ("provider", models.CharField(default="google_routes", max_length=40)), ("is_active", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-version", "-created_at"], "indexes": [models.Index(fields=["booking_id", "phase", "version"], name="ambulance_t_booking_2ddf2f_idx")]},
        ),
    ]
