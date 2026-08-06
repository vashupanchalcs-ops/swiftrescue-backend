from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("hospitals", "0002_hospital_icu_beds_hospital_status")]

    operations = [
        migrations.CreateModel(
            name="HospitalStaff",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=120)),
                ("role", models.CharField(choices=[("doctor", "Doctor"), ("nurse", "Nurse"), ("technician", "Technician"), ("support", "Support")], default="doctor", max_length=20)),
                ("specialization", models.CharField(blank=True, default="", max_length=120)),
                ("contact_number", models.CharField(blank=True, default="", max_length=20)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("is_on_call", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("years_experience", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staff", to="hospitals.hospital")),
            ],
        ),
    ]
