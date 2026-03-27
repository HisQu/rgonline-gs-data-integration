"""
Configure QLever UI for the ecclesiastical-persons dataset.
Runs inside the qlever-ui Docker container — Django is already on the path.

Creates the backend if missing, makes it the default, deletes all
pre-installed demo backends, configures prefix auto-completion,
and loads two example queries.
Idempotent: safe to re-run.
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qlever.settings")

import django
django.setup()

from django.core.management import call_command
from backend.models import Backend, Example

SLUG = "ecclesiastical-persons"
NAME = "Ecclesiastical Persons"
URL  = "http://localhost:7001"

# Prefixes declared in the GS source data plus common SPARQL vocabulary.
# With fillPrefixes=True, the UI will automatically insert the relevant
# PREFIX declaration at the top of the query when a prefixed name is used.
PREFIXES = """\
@prefix ns0: <http://purl.org/vocab/participation/schema#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <http://schema.org/> .
@prefix org: <http://www.w3.org/ns/org#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix gs: <https://personendatenbank.germania-sacra.de/index/gsn/> .
"""

EXAMPLES = [
    {
        "name": "Offices at institutions with dates",
        "sortKey": 1,
        "query": """\
PREFIX ns0: <http://purl.org/vocab/participation/schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT ?officeName ?institutionName ?start ?end WHERE {
  ?office foaf:name ?officeName ;
          ns0:role_at ?orgRef .
  BIND(IRI(CONCAT("https://personendatenbank.germania-sacra.de/index/gsn/",
    REPLACE(STR(?orgRef), "^person:", ""))) AS ?institution)
  ?institution foaf:name ?institutionName .
  OPTIONAL { ?office ns0:startDate ?start }
  OPTIONAL { ?office ns0:endDate ?end }
}
ORDER BY ?institutionName ?start
LIMIT 20""",
    },
    {
        "name": "Most frequent office types",
        "sortKey": 2,
        "query": """\
PREFIX ns0: <http://purl.org/vocab/participation/schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT ?officeName (COUNT(?office) AS ?count) WHERE {
  ?office foaf:name ?officeName ;
          ns0:role_at ?orgRef .
}
GROUP BY ?officeName
ORDER BY DESC(?count)
LIMIT 20""",
    },
]

# ── migrate ────────────────────────────────────────────────────────────────
call_command("migrate", verbosity=1)

# ── backend ────────────────────────────────────────────────────────────────
_, created = Backend.objects.get_or_create(
    slug=SLUG,
    defaults={"name": NAME, "baseUrl": URL},
)
print(f"{'Created' if created else 'Found existing'} backend '{NAME}'")

deleted, _ = Backend.objects.exclude(slug=SLUG).delete()
print(f"Deleted {deleted} other backend(s)")

backend = Backend.objects.get(slug=SLUG)
backend.isDefault     = True
backend.baseUrl       = URL
backend.sortKey       = 1
backend.suggestedPrefixes = PREFIXES
backend.fillPrefixes  = True
backend.save()
print(f"Set '{NAME}' as default at {URL} with {len(PREFIXES.splitlines())} prefixes")

# ── examples ───────────────────────────────────────────────────────────────
Example.objects.filter(backend=backend).delete()
for ex in EXAMPLES:
    Example.objects.create(backend=backend, **ex)
print(f"Created {len(EXAMPLES)} example(s)")

print("Done — QLever UI ready at http://localhost:7000")
