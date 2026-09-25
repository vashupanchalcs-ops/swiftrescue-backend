from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ambulance", "0011_ambulance_battery_percentage"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="driverlocation",
            index=models.Index(fields=["ambulance", "-timestamp"], name="driver_loc_amb_time_idx"),
        ),
        migrations.AddIndex(
            model_name="driverlocation",
            index=models.Index(fields=["driver_email", "-timestamp"], name="driver_loc_email_time_idx"),
        ),
        migrations.AddIndex(
            model_name="ambulance",
            index=models.Index(fields=["status", "latitude", "longitude"], name="ambulance_dispatch_geo_idx"),
        ),
    ]
