"""
Management command to seed the Django Sites framework.

Usage:
    python manage.py seed_site
    python manage.py seed_site --domain=myapp.onrender.com --name="Production"
"""

import os

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed the Sites framework (Site id=SITE_ID) with the correct domain and display name."

    def add_arguments(self, parser):
        default_domain = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        if not default_domain:
            allowed = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
            default_domain = allowed.split(",")[0].strip() if allowed.strip() else "localhost:8000"

        parser.add_argument(
            "--domain",
            default=default_domain,
            help="Domain name for the site (default: derived from env, else localhost:8000)",
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
