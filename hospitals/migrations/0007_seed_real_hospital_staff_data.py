from django.db import migrations

def seed_staff_data(apps, schema_editor):
    Hospital = apps.get_model("hospitals", "Hospital")
    HospitalStaff = apps.get_model("hospitals", "HospitalStaff")

    for h in Hospital.objects.all():
        if HospitalStaff.objects.filter(hospital=h).count() == 0:
            staff_members = [
                ("Dr. Rajesh Sharma", "doctor", "Cardiology", "REG-8821", "9876543210", "dr.rajesh@saharda.org", 15, "day", True, True, "Senior Cardiologist"),
                ("Dr. Ananya Verma", "doctor", "Emergency Medicine", "REG-8822", "9876543211", "dr.ananya@saharda.org", 10, "rotational", True, True, "Emergency Specialist"),
                ("Dr. Vikram Malhotra", "doctor", "Neurology", "REG-8823", "9876543212", "dr.vikram@saharda.org", 12, "on_call", True, True, "On-call Neurologist"),
                ("Dr. Meera Kapoor", "doctor", "Pediatrics", "REG-8824", "9876543213", "dr.meera@saharda.org", 8, "day", False, False, "Off-duty Specialist"),
                ("Nurse Priya Singh", "nurse", "ICU Intensive Care", "NUR-4401", "9876543214", "priya@saharda.org", 6, "day", False, True, "Senior ICU Nurse"),
                ("Nurse Amit Patel", "nurse", "Emergency Trauma", "NUR-4402", "9876543215", "amit@saharda.org", 5, "night", False, True, "Trauma Care Nurse"),
                ("Nurse Sunita Rao", "nurse", "Triage Care", "NUR-4403", "9876543216", "sunita@saharda.org", 7, "day", False, True, "Triage Coordinator"),
                ("Nurse Kavita Sharma", "nurse", "General Ward", "NUR-4404", "9876543217", "kavita@saharda.org", 4, "day", False, False, "Off-duty Nurse"),
                ("Rohan Gupta", "technician", "Ventilator Technician", "TECH-101", "9876543218", "rohan@saharda.org", 6, "rotational", True, True, "Active ICU Tech"),
                ("Suresh Kumar", "coordinator", "Intake Coordinator", "COORD-201", "9876543219", "suresh@saharda.org", 9, "day", True, True, "Emergency Desk"),
            ]
            for s in staff_members:
                HospitalStaff.objects.create(
                    hospital=h,
                    full_name=s[0],
                    role=s[1],
                    specialization=s[2],
                    registration_number=s[3],
                    contact_number=s[4],
                    email=s[5],
                    years_experience=s[6],
                    shift=s[7],
                    is_on_call=s[8],
                    is_active=s[9],
                    notes=s[10],
                )

def reverse_func(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0006_auto_preserve_hospitals_data"),
    ]

    operations = [
        migrations.RunPython(seed_staff_data, reverse_func),
    ]
