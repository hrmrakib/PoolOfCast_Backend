from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('talent', '0014_shortlistorder'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShortlistMedia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_id', models.IntegerField(db_index=True)),
                ('file', models.FileField(upload_to='shortlist_media/')),
                ('media_type', models.CharField(choices=[('image', 'Image'), ('video', 'Video')], max_length=10)),
                ('caption', models.CharField(blank=True, default='', max_length=255)),
                ('uploaded_by', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'talent_shortlist_media',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
