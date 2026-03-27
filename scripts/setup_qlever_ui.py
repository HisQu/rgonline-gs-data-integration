"""
Configure QLever UI for the ecclesiastical-persons dataset.
Runs inside the qlever-ui Docker container — Django is already on the path.

Creates the backend if missing, makes it the default, and hides all
pre-installed demo backends (Wikidata, Freebase, etc.).
Idempotent: safe to re-run.
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qlever.settings")

import django
django.setup()

from django.core.management import call_command
from backend.models import Backend

SLUG = "ecclesiastical-persons"
NAME = "Ecclesiastical Persons"
URL  = "http://localhost:7001"

call_command("migrate", verbosity=1)

_, created = Backend.objects.get_or_create(
    slug=SLUG,
    defaults={"name": NAME, "baseUrl": URL},
)
print(f"{'Created' if created else 'Found existing'} backend '{NAME}'")

deleted, _ = Backend.objects.exclude(slug=SLUG).delete()
print(f"Deleted {deleted} other backend(s)")

backend = Backend.objects.get(slug=SLUG)
backend.isDefault = True
backend.baseUrl = URL
backend.sortKey = 1
backend.save()
print(f"Set '{NAME}' as default at {URL}")
print("Done — QLever UI ready at http://localhost:7000")
