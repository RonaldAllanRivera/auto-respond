"""
Management command to forcefully clean up django-allauth configuration.
Deletes ALL Social Apps and Sites, then recreates a single clean configuration.
"""

from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = "Nuclear option: delete all Sites and SocialApps, recreate clean config"

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Actually execute the cleanup (default is dry-run)',
        )

    def handle(self, *args, **options):
        execute = options['execute']
        
        if not execute:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - use --execute to actually run"))
        
        # Count existing objects
        site_count = Site.objects.count()
        socialapp_count = SocialApp.objects.count()
        
        self.stdout.write(f"Found {site_count} Site(s)")
        self.stdout.write(f"Found {socialapp_count} SocialApp(s)")
        
        if execute:
            # Delete all SocialApps first (to avoid FK constraints)
            deleted_apps = SocialApp.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_apps[0]} SocialApp(s)"))
            
            # Delete all Sites
            deleted_sites = Site.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_sites[0]} Site(s)"))
            
            # Create a single clean Site
            site = Site.objects.create(
                id=1,
                domain='auto-respond-tdp7.onrender.com',
                name='Meet Lessons'
            )
            self.stdout.write(self.style.SUCCESS(f"Created Site: {site.domain} (ID: {site.id})"))
            
            self.stdout.write(self.style.WARNING("\n⚠️  You must now manually create the Google OAuth Social Application in Django Admin:"))
            self.stdout.write("1. Go to /admin/socialaccount/socialapp/add/")
            self.stdout.write("2. Provider: Google")
            self.stdout.write("3. Name: Google OAuth")
            self.stdout.write("4. Client ID: (from Google Cloud Console)")
            self.stdout.write("5. Secret key: (from Google Cloud Console)")
            self.stdout.write("6. Sites: Select 'auto-respond-tdp7.onrender.com'")
            self.stdout.write("7. Save")
        else:
            self.stdout.write(self.style.WARNING("\nTo execute cleanup, run:"))
            self.stdout.write("  python manage.py cleanup_oauth --execute")
