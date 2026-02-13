from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0002_lesson_meeting_id_lesson_meeting_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="transcriptchunk",
            name="content_hash",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddConstraint(
            model_name="transcriptchunk",
            constraint=models.UniqueConstraint(
                condition=models.Q(("content_hash__gt", "")),
                fields=("lesson", "content_hash"),
                name="unique_chunk_per_lesson",
            ),
        ),
    ]
