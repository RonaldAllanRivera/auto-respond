from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0002_stripe_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="couponcode",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="couponcode",
            name="max_redemptions",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="couponcode",
            name="redeemed_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
