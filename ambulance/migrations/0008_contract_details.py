from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ambulance", "0007_suggestedroute_dest_lat_suggestedroute_dest_lng_and_more")]
    operations = [
        migrations.AddField("ambulance", "ambulance_contract_id", models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField("ambulance", "registration_number", models.CharField(blank=True, default="", max_length=80)),
    ]
