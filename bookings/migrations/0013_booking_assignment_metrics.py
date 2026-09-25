from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0012_patientconditionphoto_image_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="assignment_distance_km",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="assignment_eta_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="assignment_route_provider",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="booking",
            name="assignment_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
