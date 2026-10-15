from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0013_booking_assignment_metrics"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookingchatmessage",
            name="seen_by_staff",
            field=models.BooleanField(default=False),
        ),
    ]
