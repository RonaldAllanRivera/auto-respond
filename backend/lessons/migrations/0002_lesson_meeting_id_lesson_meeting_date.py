from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="meeting_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="lesson",
            name="meeting_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.UniqueConstraint(
                condition=models.Q(("meeting_id__gt", "")),
                fields=("user", "meeting_id", "meeting_date"),
                name="unique_lesson_per_meeting_per_day",
            ),
        ),
    ]
