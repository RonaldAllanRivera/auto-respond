from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BillingPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="Monthly", max_length=64)),
                ("currency", models.CharField(default="usd", max_length=8)),
                ("monthly_price_cents", models.PositiveIntegerField(default=0)),
                (
                    "monthly_discount_percent",
                    models.PositiveIntegerField(
                        default=20,
                        validators=[MinValueValidator(0), MaxValueValidator(90)],
                    ),
                ),
                ("stripe_monthly_price_id", models.CharField(blank=True, default="", max_length=255)),
                ("active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="CouponCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("stripe_promotion_code_id", models.CharField(blank=True, default="", max_length=255)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
