"""
Management command to seed the Django Sites framework.

Usage:
    python manage.py seed_site
    python manage.py seed_site --domain=myapp.onrender.com --name="Production"
"""

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed the Sites framework (Site id=SITE_ID) with the correct domain and display name."

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            default="localhost:8000",
            help="Domain name for the site (default: localhost:8000)",
        )
        parser.add_argument(
            "--name",
            default="Meet Lessons",
            help="Display name for the site (default: Meet Lessons)",
        )

    def handle(self, *args, **options):
        domain = options["domain"]
        name = options["name"]
        site_id = getattr(settings, "SITE_ID", 1)

        site, created = Site.objects.update_or_create(
            id=site_id,
            defaults={"domain": domain, "name": name},
        )

        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{verb} Site(id={site.id}): domain={site.domain}, name={site.name}")
        )
