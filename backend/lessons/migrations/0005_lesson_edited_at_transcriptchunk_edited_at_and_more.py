# Generated manually for document ingestion feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lessons', '0004_lesson_source_type_transcriptchunk_page_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='edited_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transcriptchunk',
            name='edited_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='lesson',
            index=models.Index(fields=['user', 'source_type', '-created_at'], name='lessons_les_user_id_source_created_idx'),
        ),
    ]
