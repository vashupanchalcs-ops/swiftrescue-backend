from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0011_booking_payment_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="patientconditionphoto",
            name="image_data",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="patientconditionphoto",
            name="image",
            field=models.FileField(blank=True, default="", upload_to="condition_photos/%Y/%m/%d/"),
        ),
    ]
