from django.db import migrations, models

TO_INT = {"image": 1, "video": 2}
TO_STR = {v: k for k, v in TO_INT.items()}


def forwards(apps, schema_editor):
    M = apps.get_model("talent", "ShortlistMedia")
    for m in M.objects.all():
        m.media_type_new = TO_INT.get(m.media_type, 1)
        m.save(update_fields=["media_type_new"])


def backwards(apps, schema_editor):
    M = apps.get_model("talent", "ShortlistMedia")
    for m in M.objects.all():
        m.media_type = TO_STR.get(m.media_type_new, "image")
        m.save(update_fields=["media_type"])


class Migration(migrations.Migration):

    dependencies = [
        ('talent', '0016_shortlistmedia_media_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='shortlistmedia',
            name='media_type_new',
            field=models.PositiveSmallIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(model_name='shortlistmedia', name='media_type'),
        migrations.RenameField(model_name='shortlistmedia', old_name='media_type_new', new_name='media_type'),
        migrations.AlterField(
            model_name='shortlistmedia',
            name='media_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'image'), (2, 'video')]),
        ),
    ]
