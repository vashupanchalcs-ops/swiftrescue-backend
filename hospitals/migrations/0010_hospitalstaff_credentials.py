from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0009_hospitalbed"),
    ]

    operations = [
        migrations.AddField(
            model_name="hospitalstaff",
            name="staff_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="hospitalstaff",
            name="password_hash",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
