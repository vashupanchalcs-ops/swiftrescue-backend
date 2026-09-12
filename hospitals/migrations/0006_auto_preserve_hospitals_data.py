# Generated manually to permanently preserve operational hospital and fleet data across container restarts.

from django.db import migrations

def preserve_hospital_and_ambulance_data(apps, schema_editor):
    Hospital = apps.get_model("hospitals", "Hospital")
    Ambulance = apps.get_model("ambulance", "Ambulance")

    # Preserve Saharda Hospital
    Hospital.objects.update_or_create(
        id=1,
        defaults={
            "name": "Saharda Hospital",
            "hospital_contract_id": "ShardaUP0001H",
            "contact_number": "8882128534",
            "available_beds": 10,
            "icu_beds": 0,
            "status": "active",
            "is_active": True,
            "city": "Ghaziabad",
            "email": "ivashu.07@gmail.com",
            "total_beds": 40,
        }
    )

    # Preserve Ambulances
    fleet_data = [
        (1, "AMB-0001", "ankit", "ap9860988@gmail.com", "available", "bopuhra"),
        (2, "AMB-0000", "ganga", "", "offline", "bophal"),
        (3, "111222333", "ankit", "factmania98@gmail.com", "en_route", "Loni"),
        (4, "AMB-0000", "ankit", "ap9860988@gmail.com", "available", "Ghaziabad"),
        (5, "AMB-0000", "Vikram", "", "offline", "Gurgao"),
        (6, "AMB-0000", "driver", "forumdocx@gmail.com", "en_route", "noida"),
        (7, "AMB-0007", "Rahul", "", "en_route", "delhi"),
    ]

    for item in fleet_data:
        Ambulance.objects.update_or_create(
            id=item[0],
            defaults={
                "ambulance_number": item[1],
                "driver": item[2],
                "driver_email": item[3],
                "status": item[4],
                "location": item[5],
            }
        )

def reverse_func(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0005_persist_staff_profile_cards"),
        ("ambulance", "0008_ambulance_ambulance_contract_id_and_more"),
    ]

    operations = [
        migrations.RunPython(preserve_hospital_and_ambulance_data, reverse_func),
    ]
