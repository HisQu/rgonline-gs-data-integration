```
/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── .envrc
├── justfile
├── pyproject.toml
├── uv.lock
│
├── docs/
│   ├── architecture.md
│   ├── ontology.md
│   └── decisions/
│       ├── 0001-data-sources.md
│       ├── 0002-uri-policy.md
│       ├── 0003-er-thresholds.md
│       └── 0004-dnb-skip-materialization.md
│
├── configs/
│   ├── morph-kgc/
│   │   ├── source-gs.ini
│   │   ├── source-rgo.ini
│   │   └── shared-prefixes.ttl
│   ├── qlever/
│   │   ├── dataset.settings.json
│   │   └── qleverfile.example
│   └── limes/
│       ├── blocking_rules.py
│       ├── comparisons.py
│       └── thresholds.yaml
│
├── mappings/
│   ├── source-gs/
│   │   └── mapping.rml.ttl
│   ├── source-rgo/
│   │   └── mapping.rml.ttl
│   └── unified/
│       ├── ontology.ttl
│       ├── harmonize.ru
│       └── canonicalize.ru
│
├── data/
│   ├── raw/
│   │   ├── source-gs/
│   │   ├── source-dnb/
│   │   └── source-rgo/
│   ├── interim/
│   │   ├── rdf/
│   │   │   ├── source-gs.ttl
│   │   │   ├── source-dnb.ttl
│   │   │   ├── source-rgo.ttl
│   │   │   └── unified.ttl
│   │   └── er/
│   │       ├── candidate-records.parquet
│   │       ├── pairwise-scores.parquet
│   │       └── clusters.parquet
│   ├── processed/
│   │   ├── canonical-graph.ttl
│   │   ├── links.ttl
│   │   └── exports/
│   └── qlever/
│       ├── input/
│       ├── index/
│       └── logs/
│
├── src/
│   ├── dnb/                    # Deutsche Nationalbibliothek — SPARQL endpoint (QLever/GND)
│   │   ├── __init__.py
│   │   └── fetch.py            # Paginated CONSTRUCT queries → cache → dedup → Turtle
│   ├── gs/                     # Germania Sacra — TTL file download
│   │   ├── __init__.py
│   │   └── fetch.py
│   ├── rgo/                    # Repertorium Germanicum Online — XML parsing + RDF conversion
│   │   ├── __init__.py
│   │   └── fetch.py
│   └── er/                     # Entity resolution — record linkage across all three sources
│       └── __init__.py
│
├── queries/
│   ├── acquisition/
│   │   ├── source-dnb-count.rq
│   │   ├── source-dnb-construct.rq
│   │   └── source-dnb-construct-literal-occ.rq
│   ├── validation/
│   ├── analysis/
│   └── reports/
│
├── tests/
│   ├── test_acquisition_source_dnb.py
│   ├── test_harmonization_source_dnb.py
│   └── fixtures/
│       └── source-dnb-sample.nt
│
├── notebooks/
│   ├── 01-exploration.ipynb
│   └── 02-er-evaluation.ipynb
│
└── scripts/
    ├── run_acquisition.sh
    ├── run_materialization.sh
    ├── run_er.sh
    └── run_qlever.sh
```
