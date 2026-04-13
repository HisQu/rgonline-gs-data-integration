"""
Configure QLever UI for the ecclesiastical-persons dataset.
Runs inside the qlever-ui Docker container — Django is already on the path.

Creates the backend if missing, makes it the default, deletes all
pre-installed demo backends, configures prefix auto-completion,
and loads example queries from /queries/examples/*.rq and /queries/cq/*.rq.
Idempotent: safe to re-run.
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qlever.settings")

import django
django.setup()

from pathlib import Path
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

def _load_examples(examples_dir: Path) -> list[dict]:
    """Load example queries from *.rq files.

    Each file may begin with header comment lines of the form:
        # Name: <display name>
        # SortKey: <integer>
    The remainder (or full file if no headers) is used as the query body.
    """
    examples = []
    for path in sorted(examples_dir.glob("*.rq")):
        lines = path.read_text().splitlines()
        meta: dict = {}
        query_start = len(lines)
        for i, line in enumerate(lines):
            if line.startswith("# ") and ":" in line:
                key, _, val = line[2:].partition(":")
                meta[key.strip().lower()] = val.strip()
            else:
                query_start = i
                break
        query = "\n".join(lines[query_start:]).strip()
        examples.append({
            "name": meta.get("name", path.stem),
            "sortKey": int(meta.get("sortkey", 99)),
            "query": query,
        })
    return examples

EXAMPLES = _load_examples(Path("/queries/examples")) + _load_examples(Path("/queries/cq"))

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
