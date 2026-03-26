```
/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── Makefile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
│
├── docs/
│   ├── architecture.md
│   ├── ontology.md
│   └── decisions/
│       ├── 0001-data-sources.md
│       ├── 0002-uri-policy.md
│       └── 0003-er-thresholds.md
│
├── configs/
│   ├── morph-kgc/
│   │   ├── source-a.ini
│   │   ├── source-b.ini
│   │   ├── source-c.ini
│   │   └── shared-prefixes.ttl
│   ├── qlever/
│   │   ├── dataset.settings.json
│   │   └── qleverfile.example
│   └── splink/
│       ├── blocking_rules.py
│       ├── comparisons.py
│       └── thresholds.yaml
│
├── mappings/
│   ├── source-a/
│   │   └── mapping.rml.ttl
│   ├── source-b/
│   │   └── mapping.rml.ttl
│   ├── source-c/
│   │   └── mapping.rml.ttl
│   └── unified/
│       ├── ontology.ttl
│       ├── harmonize.ru
│       └── canonicalize.ru
│
├── data/
│   ├── raw/
│   │   ├── source-a/
│   │   ├── source-b/
│   │   └── source-c/
│   ├── interim/
│   │   ├── rdf/
│   │   │   ├── source-a.ttl
│   │   │   ├── source-b.ttl
│   │   │   ├── source-c.ttl
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
│   └── project_name/
│       ├── __init__.py
│       ├── acquisition/
│       │   ├── fetch_source_a.py
│       │   ├── fetch_source_b.py
│       │   └── fetch_source_c.py
│       ├── materialize/
│       │   ├── run_morph_kgc.py
│       │   └── validate_rdf.py
│       ├── transform/
│       │   ├── export_er_table.py
│       │   ├── run_harmonization.py
│       │   └── write_links_back.py
│       ├── er/
│       │   ├── train_splink.py
│       │   ├── predict_matches.py
│       │   └── cluster_entities.py
│       └── qlever/
│           ├── build_index.py
│           └── load_queries.py
│
├── queries/
│   ├── validation/
│   ├── analysis/
│   └── reports/
│
├── tests/
│   ├── test_mappings.py
│   ├── test_harmonization.py
│   ├── test_er_pipeline.py
│   └── fixtures/
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