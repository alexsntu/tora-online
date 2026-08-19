from django.db import migrations


def backfill_lower_fields(apps, schema_editor):
    Material = apps.get_model("library", "Material")
    for m in Material.objects.all():
        Material.objects.filter(pk=m.pk).update(
            title_lower=m.title.lower(), body_lower=m.body.lower()
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0013_material_body_lower_material_title_lower'),
    ]

    operations = [
        migrations.RunPython(backfill_lower_fields, noop),
    ]
