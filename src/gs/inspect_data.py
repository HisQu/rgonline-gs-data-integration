"""Inspect the raw GS data to understand its structure and predicates."""
import collections
from rdflib import Graph
from rdflib.term import BNode

g = Graph()
g.parse("data/raw/gs/statements.ttl", format="turtle")

print(f"Total triples: {len(g)}")

all_subjects = set(g.subjects(unique=True))
print(f"Unique subjects: {len(all_subjects)}")

# Persons are blank nodes; organisations and offices are fragment URIs.
persons, amts, orgs = [], [], []
for s in all_subjects:
    uri = str(s)
    if "#amt-" in uri:
        amts.append(s)
    elif "#organisation-" in uri:
        orgs.append(s)
    elif isinstance(s, BNode):
        persons.append(s)

print(f"Persons (blank nodes): {len(persons)}, Amts: {len(amts)}, Orgs: {len(orgs)}")

# Predicates on blank-node persons
pred_counts: collections.Counter = collections.Counter()
samples: dict = collections.defaultdict(list)
for p in persons:
    for pred, obj in g.predicate_objects(p):
        pred_counts[pred] += 1
        if len(samples[pred]) < 3:
            samples[pred].append(repr(obj))

print("\nPredicates on person records:")
for pred, count in sorted(pred_counts.items(), key=lambda x: -x[1]):
    print(f"  [{count:6d}] {pred}")
    for v in samples[pred]:
        print(f"             {v}")

# Predicates on amt records
print("\nPredicates on amt (#amt-) records:")
amt_pred_counts: collections.Counter = collections.Counter()
amt_samples: dict = collections.defaultdict(list)
for a in amts:
    for pred, obj in g.predicate_objects(a):
        amt_pred_counts[pred] += 1
        if len(amt_samples[pred]) < 2:
            amt_samples[pred].append(repr(obj))
for pred, count in sorted(amt_pred_counts.items(), key=lambda x: -x[1]):
    print(f"  [{count:6d}] {pred}")
    for v in amt_samples[pred]:
        print(f"             {v}")

# Sample person
if persons:
    p = persons[0]
    print(f"\nSample person (blank node):")
    for pred, obj in g.predicate_objects(p):
        print(f"  {pred} -> {obj!r}")
