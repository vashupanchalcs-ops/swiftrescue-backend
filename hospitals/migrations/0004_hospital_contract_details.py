from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hospitals", "0003_hospitalstaff")]

    operations = [
        migrations.AddField("hospital", "hospital_contract_id", models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField("hospital", "registration_number", models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField("hospital", "total_ventilators", models.IntegerField(default=0)),
        migrations.AddField("hospital", "available_ventilators", models.IntegerField(default=0)),
    ]
