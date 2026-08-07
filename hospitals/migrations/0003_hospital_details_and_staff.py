# Generated manually to extend the operational hospital profile safely.

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0002_hospital_icu_beds_hospital_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="hospital",
            name="ambulance_bays",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="hospital",
            name="available_icu_beds",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="hospital",
            name="city",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="hospital",
            name="contact_person_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="hospital",
            name="contact_person_role",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="hospital",
            name="created_at",
            field=models.DateTimeField(default=django.utils.timezone.now, editable=False),
        ),
        migrations.AddField(
            model_name="hospital",
            name="emergency_beds",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="hospital",
            name="emergency_contact",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="hospital",
            name="facilities",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="hospital",
            name="has_blood_bank",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="hospital",
            name="hospital_contract_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="hospital",
            name="insurance_partners",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="hospital",
            name="is_24x7",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="hospital",
            name="last_capacity_updated",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="hospital",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="hospital",
            name="oxygen_beds",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="hospital",
            name="pincode",
            field=models.CharField(blank=True, default="", max_length=12),
        ),
        migrations.AddField(
            model_name="hospital",
            name="registration_number",
            field=models.CharField(blank=True, db_index=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="hospital",
            name="state",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="hospital",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="hospital",
            name="ventilators_available",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="hospital",
            name="ventilators_total",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="hospital",
            name="website",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.CreateModel(
            name="HospitalStaff",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=150)),
                ("role", models.CharField(choices=[("doctor", "Doctor"), ("nurse", "Nurse"), ("technician", "Technician"), ("coordinator", "Emergency Coordinator"), ("administrator", "Administrator"), ("other", "Other")], default="doctor", max_length=20)),
                ("specialization", models.CharField(blank=True, default="", max_length=150)),
                ("registration_number", models.CharField(blank=True, default="", max_length=100)),
                ("contact_number", models.CharField(blank=True, default="", max_length=20)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("shift", models.CharField(choices=[("day", "Day"), ("night", "Night"), ("rotational", "Rotational"), ("on_call", "On call")], default="day", max_length=20)),
                ("is_on_call", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("joined_on", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staff", to="hospitals.hospital")),
            ],
            options={"ordering": ["hospital__name", "role", "full_name"]},
        ),
    ]
