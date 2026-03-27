"""Read a QLever SPARQL UPDATE JSON response from stdin and print a summary."""
import sys
import json

data = json.load(sys.stdin)
ops = data["operations"]

labels = sys.argv[1:] if len(sys.argv) > 1 else [f"Operation {i+1}" for i in range(len(ops))]

col = 16
print(f"  {'Entity':<{col}} {'inserted':>10} {'deleted':>10} {'total':>10}")
print("  " + "-" * (col + 34))
grand_inserted = 0
for i, op in enumerate(ops):
    dt = op["delta-triples"]["operation"]
    label = labels[i] if i < len(labels) else f"Operation {i+1}"
    print(f"  {label:<{col}} {dt['inserted']:>10,} {dt['deleted']:>10,} {dt['total']:>10,}")
    grand_inserted += dt["inserted"]
print("  " + "-" * (col + 34))
print(f"  {'Total':<{col}} {grand_inserted:>10,}")
