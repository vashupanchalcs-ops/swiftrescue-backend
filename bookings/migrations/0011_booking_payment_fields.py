from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0010_videocallrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="payment_amount_due",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="payment_note",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="booking",
            name="payment_status",
            field=models.CharField(choices=[("draft", "Draft"), ("due", "Due"), ("paid", "Paid"), ("overdue", "Overdue"), ("cancelled", "Cancelled")], default="due", max_length=20),
        ),
        migrations.AddField(
            model_name="booking",
            name="payment_total",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="payment_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
