from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ambulance", "0010_userprofile_ambulance_ambulance_a_status_8cb0e8_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ambulance",
            name="battery_percentage",
            field=models.IntegerField(default=100),
        ),
    ]
