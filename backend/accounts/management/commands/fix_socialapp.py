"""
Management command to fix django-allauth SocialApp configuration issues.
Ensures only one Google OAuth app exists and is properly configured.
"""

from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = "Fix SocialApp configuration - ensure only one Google OAuth app exists"

    def handle(self, *args, **options):
        # Get the current site
        site = Site.objects.get_current()
        self.stdout.write(f"Current site: {site.domain} (ID: {site.id})")

        # Find all Google apps
        google_apps = SocialApp.objects.filter(provider="google")
        count = google_apps.count()

        self.stdout.write(f"Found {count} Google OAuth app(s)")

        if count == 0:
            self.stdout.write(self.style.ERROR("No Google OAuth app found. Create one in Django Admin."))
            return

        if count == 1:
            app = google_apps.first()
            self.stdout.write(self.style.SUCCESS(f"✓ Only 1 Google app exists (ID: {app.id}, Name: {app.name})"))
            
            # Ensure it's linked to the current site
            if site not in app.sites.all():
                app.sites.add(site)
                self.stdout.write(self.style.WARNING(f"Added site '{site.domain}' to app"))
            else:
                self.stdout.write(f"  App is already linked to site '{site.domain}'")
            
            # Check for extra sites
            app_sites = app.sites.all()
            if app_sites.count() > 1:
                self.stdout.write(self.style.WARNING(f"  App is linked to {app_sites.count()} sites:"))
                for s in app_sites:
                    self.stdout.write(f"    - {s.domain} (ID: {s.id})")
                self.stdout.write(self.style.WARNING("  Consider removing extra sites if only one is needed."))
            
            return

        # Multiple Google apps found - delete all except the first one
        self.stdout.write(self.style.WARNING(f"Found {count} Google apps - will keep the first one and delete the rest"))
        
        keep_app = google_apps.first()
        delete_apps = google_apps.exclude(id=keep_app.id)
        
        self.stdout.write(f"Keeping: {keep_app.name} (ID: {keep_app.id})")
        for app in delete_apps:
            self.stdout.write(f"Deleting: {app.name} (ID: {app.id})")
            app.delete()
        
        # Ensure the kept app is linked to the current site
        if site not in keep_app.sites.all():
            keep_app.sites.add(site)
            self.stdout.write(f"Added site '{site.domain}' to the kept app")
        
        self.stdout.write(self.style.SUCCESS("✓ Fixed: Only 1 Google OAuth app remains"))
