from collections import Counter
from rdflib import Graph

g = Graph()
g.parse("data/raw/gs/full.ttl", format="turtle")

query = """
PREFIX org:   <http://www.w3.org/ns/org#>
PREFIX part:  <http://purl.org/vocab/participation/schema#>
PREFIX foaf:  <http://xmlns.com/foaf/0.1/>

SELECT DISTINCT ?name
WHERE {
  {
    ?person org:memberOf ?org .
  }
  UNION
  {
    ?person part:holder_of ?amt .
    ?amt part:role_at ?org .
  }
  ?org foaf:name ?name .
}
"""

first_token = Counter()
first_two_tokens = Counter()

for row in g.query(query):
    name = str(row.name).strip()
    tokens = name.split()
    if not tokens:
        continue

    first_token[tokens[0]] += 1
    if len(tokens) >= 2:
        first_two_tokens[" ".join(tokens[:2])] += 1

print("Top first tokens:")
for token, count in first_token.most_common(50):
    print(f"{count:>5}  {token}")

print("\nTop first two tokens:")
for token, count in first_two_tokens.most_common(50):
    print(f"{count:>5}  {token}")