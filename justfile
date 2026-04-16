# Default: list available recipes
default:
    @just --list

# Versions of Apache Jena to download.
# Check https://jena.apache.org/download/ for the latest release.
JENA_VERSION   := "6.0.0"
FUSEKI_VERSION := "6.0.0"

# Set up dependencies, build reduced example inputs, run harmonization,
# export person-focused examples, and start query services.
go: sync test fetch reduce use-cohort clean harmonize examples-export fuseki
setup: go

# Install project and dev dependencies
sync:
    uv sync --extra dev

# Run all tests
test *args:
    uv run pytest tests/ {{ args }}

# Run a single test file
test-file file *args:
    uv run pytest {{ file }} {{ args }}

# Fetch latest GND ontology HTML documentation to docs/gndo.html
gndo-doc-fetch:
    ./scripts/fetch_gndo_html.sh

fetch: gndo-doc-fetch gs-fetch rgo-fetch dnb-fetch

clean: gs-clean

# Normalize fuzzy GS date literals in data/raw/gs/clean.ttl to xsd:gYear.
gs-fix-dates *args:
    UV_CACHE_DIR=/tmp/uv-cache uv run python src/gs/fix_gs_clean_dates.py {{ args }}

# Build cohort.ttl for all three sources using year-based filtering.
reduce: gs-reduce dnb-reduce rgo-reduce
alias cohort := reduce

# Build example.ttl for all three sources using the four cross-source example persons.
extract-examples: gs-extract-examples dnb-extract-examples rgo-extract-examples

# Reduce GS raw data to the cohort time window (birth 1361–1447, fallback death 1431–1497).
gs-reduce:
    @mkdir -p data/raw/gs
    just robot query \
        --input data/raw/gs/full.ttl \
        --tdb true \
        --query mappings/gs/reduce.rq data/raw/gs/cohort.ttl

# Extract four cross-source example persons from GS full data.
gs-extract-examples:
    @mkdir -p data/raw/gs
    just robot query \
        --input data/raw/gs/full.ttl \
        --tdb true \
        --query mappings/gs/create_min_examples.rq data/raw/gs/example.ttl

# Reduce DNB raw data to the cohort time window.
dnb-reduce:
	UV_CACHE_DIR=/tmp/uv-cache uv run python mappings/dnb/reduce_persons.py \
		--input data/raw/dnb/persons_full.ttl \
		--output data/raw/dnb/persons_cohort.ttl
	UV_CACHE_DIR=/tmp/uv-cache uv run python mappings/dnb/reduce_places.py \
		--persons data/raw/dnb/persons_cohort.ttl \
		--places-input data/raw/dnb/places_full.ttl \
		--output data/raw/dnb/places_cohort.ttl
	cat data/raw/dnb/persons_cohort.ttl data/raw/dnb/places_cohort.ttl > data/raw/dnb/cohort.ttl

# Extract four cross-source example persons from DNB full data.
dnb-extract-examples:
	UV_CACHE_DIR=/tmp/uv-cache uv run python mappings/dnb/create_min_examples.py \
		--input data/raw/dnb/persons_full.ttl \
		--output data/raw/dnb/persons_example.ttl
	UV_CACHE_DIR=/tmp/uv-cache uv run python mappings/dnb/reduce_places.py \
		--persons data/raw/dnb/persons_example.ttl \
		--places-input data/raw/dnb/places_full.ttl \
		--output data/raw/dnb/places_example.ttl
	cat data/raw/dnb/persons_example.ttl data/raw/dnb/places_example.ttl > data/raw/dnb/example.ttl

# Reduce RGO source data to cohort scope (RG5 is already fully within the cohort time range).
rgo-reduce:
    @mkdir -p data/raw/rgo
    cp data/raw/rgo/full.ttl data/raw/rgo/cohort.ttl

# Extract four cross-source example persons from RGO full data.
rgo-extract-examples:
    @mkdir -p data/raw/rgo
    just robot query \
        --input data/raw/rgo/full.ttl \
        --tdb true \
        --query mappings/rgo/create_min_examples.rq data/raw/rgo/example.ttl

# Activate full variants as pipeline inputs.
use-full:
    cp data/raw/gs/full.ttl data/raw/gs/statements.ttl
    cp data/raw/dnb/full.ttl data/raw/dnb/statements.ttl
    cp data/raw/rgo/full.ttl data/raw/rgo/statements.ttl

# Activate cohort-filtered variants as pipeline inputs.
use-cohort:
    cp data/raw/gs/cohort.ttl data/raw/gs/statements.ttl
    cp data/raw/dnb/cohort.ttl data/raw/dnb/statements.ttl
    cp data/raw/rgo/cohort.ttl data/raw/rgo/statements.ttl

# Activate four-person example variants as pipeline inputs.
use-example:
    cp data/raw/gs/example.ttl data/raw/gs/statements.ttl
    cp data/raw/dnb/example.ttl data/raw/dnb/statements.ttl
    cp data/raw/rgo/example.ttl data/raw/rgo/statements.ttl

# Harmonize GS and RGO source graphs to GNDO-oriented projections using ROBOT.
# Merges all sources and the TBox directly into data/harmonized/statements.ttl.
# OWL reasoning is deferred to Apache Jena Fuseki at query time.
harmonize:
    @mkdir -p data/harmonized
    just robot query \
        --input data/raw/gs/clean.ttl \
        --tdb true \
        --query mappings/gs/harmonize.rq data/harmonized/gs.ttl
    just robot query \
        --input data/raw/rgo/statements.ttl \
        --tdb true \
        --query mappings/rgo/harmonize.rq data/harmonized/rgo.ttl
    just robot merge \
        --input data/harmonized/gs.ttl \
        --input data/harmonized/rgo.ttl \
        --input data/raw/dnb/statements.ttl \
        --input mappings/harmonize.ttl \
        --output data/harmonized/statements.ttl

# Export per-person harmonized examples from data/harmonized/statements.ttl.
# Default mode is focused (one person per file). To reproduce the previous
# broad traversal behavior, pass: --mode neighborhood
examples-export *args:
    UV_CACHE_DIR=/tmp/uv-cache uv run python src/export_harmonized_examples.py {{ args }}
    for file in data/examples/harmonized/*.ttl; do \
        case "$file" in \
            *.reasoned.ttl) ;; \
            *) tmp="${file%.ttl}.with-ontology.ttl"; \
               just robot merge --input mappings/harmonize.ttl --input "$file" --output "$tmp"; \
               just robot reason --input "$tmp" --reasoner HermiT --output "${file%.ttl}.reasoned.ttl"; \
               rm -f "$tmp" ;; \
        esac; \
    done

# Fetch Germania Sacra persons active in the RG5 timeframe (1361–1447).
# Downloads all ~2775 pages, caches under data/raw/gs/pages/, filters by date,
# and writes merged output to data/raw/gs/full.ttl.
# Use --start-page N to resume from a specific page.
gs-fetch *args:
    uv run python src/gs/fetch.py {{ args }}
    cp data/raw/gs/full.ttl data/raw/gs/statements.ttl

# Fetch RG5 XML from the configured GitHub repository ref.
# Requires GITHUB_TOKEN in the environment.
rgo-fetch *args:
    uv run python src/rgo/fetch.py {{ args }}
    uv run python src/rgo/materialize.py {{ args }}
    uv run python src/rgo/allign.py {{ args }}
    cp data/raw/rgo/full.ttl data/raw/rgo/statements.ttl

# Apply the three GS cleaning CONSTRUCT queries locally via ROBOT + Jena TDB,
# then normalize fuzzy date literals in the cleaned output.
# --tdb true bypasses the OWL API so that blank-node persons and their
# owl:sameAs links are preserved.
gs-clean:
    @mkdir -p data/raw/gs
    just robot query \
        --input data/raw/gs/statements.ttl \
        --tdb true \
        --query mappings/gs/clean-persons.rq data/raw/gs/clean-persons.ttl \
        --query mappings/gs/clean-orgs.rq    data/raw/gs/clean-orgs.ttl \
        --query mappings/gs/clean-amts.rq    data/raw/gs/clean-amts.ttl
    just robot merge \
        --input data/raw/gs/clean-persons.ttl \
        --input data/raw/gs/clean-orgs.ttl \
        --input data/raw/gs/clean-amts.ttl \
        --output data/raw/gs/clean.ttl
    just gs-fix-dates

# Download the GND person and place authority dumps.
# Produces persons_full.ttl and places_full.ttl as internal files,
# then merges them into full.ttl for use with use-full / QLever.
dnb-fetch:
	@mkdir -p data/raw/dnb
	curl -L -o data/raw/dnb/persons_full.ttl.gz \
		https://data.dnb.de/opendata/authorities-gnd-person_lds.ttl.gz
	gunzip -c data/raw/dnb/persons_full.ttl.gz \
		> data/raw/dnb/persons_full.ttl

	curl -L -o data/raw/dnb/places_full.ttl.gz \
		https://data.dnb.de/opendata/authorities-gnd-geografikum_lds.ttl.gz
	gunzip -c data/raw/dnb/places_full.ttl.gz \
		> data/raw/dnb/places_full.ttl

	cat data/raw/dnb/persons_full.ttl data/raw/dnb/places_full.ttl > data/raw/dnb/full.ttl

qlever-restart: qlever-stop qlever-start

qlever: qlever-stop qlever-index qlever-up

# ── Apache Jena ────────────────────────────────────────────────────────────

# Download and extract the Apache Jena command-line tools into ./jena/.
# Creates ./rsparql symlink in the project root (used by cq, scq, sparql).
jena-fetch:
    mkdir -p jena
    curl -L -o jena/apache-jena-{{JENA_VERSION}}.tar.gz \
        https://downloads.apache.org/jena/binaries/apache-jena-{{JENA_VERSION}}.tar.gz
    tar -xzf jena/apache-jena-{{JENA_VERSION}}.tar.gz -C jena/
    ln -sf jena/apache-jena-{{JENA_VERSION}}/bin/rsparql rsparql
    @echo "Apache Jena {{JENA_VERSION}} extracted; ./rsparql symlink created."

# ── Apache Jena Fuseki ─────────────────────────────────────────────────────

# Download and extract Apache Jena Fuseki into the fuseki/ directory.
# Update FUSEKI_VERSION at the top of this file if a newer release is available.
fuseki-fetch:
    mkdir -p fuseki
    curl -L -o fuseki/apache-jena-fuseki-{{FUSEKI_VERSION}}.tar.gz \
        https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-{{FUSEKI_VERSION}}.tar.gz
    tar -xzf fuseki/apache-jena-fuseki-{{FUSEKI_VERSION}}.tar.gz -C fuseki/
    @echo "Fuseki {{FUSEKI_VERSION}} extracted to fuseki/apache-jena-fuseki-{{FUSEKI_VERSION}}/"

# Start Fuseki SPARQL endpoint on port 3030 with OWL inference (e.g. fuseki-config.ttl).
# SPARQL endpoint: http://localhost:3030/integration/sparql
# JVM_ARGS sets the heap; increase if the reasoner runs out of memory.
fuseki-start:
    bash -c 'JVM_ARGS="-Xmx8g" nohup fuseki/apache-jena-fuseki-{{FUSEKI_VERSION}}/fuseki-server --config=fuseki-config-lightweight.ttl --port=3030 > fuseki/fuseki.log 2>&1 & PID=$!; echo $PID > fuseki/fuseki.pid; echo "Fuseki started (PID $PID) — http://localhost:3030/integration/sparql"'

# Stop the Fuseki SPARQL endpoint.
fuseki-stop:
    -bash -c '[ -f fuseki/fuseki.pid ] && kill "$(cat fuseki/fuseki.pid)" 2>/dev/null && rm -f fuseki/fuseki.pid && echo "Fuseki stopped." || rm -f fuseki/fuseki.pid'

# Stop any running Fuseki instance and start a fresh one.
fuseki: fuseki-stop fuseki-start

# Run all competency-question SPARQL queries against the Fuseki integration
# endpoint (http://localhost:3030/integration/sparql) and save CSV outputs.
# Requires: just fuseki-start (or just fuseki) to be running first.
# Requires: ./rsparql symlink created by just jena-fetch.
# Output files are written to queries/cq/results/.
cq:
    @mkdir -p queries/cq/results
    @set -e; \
    for query in queries/cq/*.rq; do \
        out="queries/cq/results/$(basename "${query%.rq}").csv"; \
        ./rsparql --service=http://localhost:3030/integration/sparql \
            --results=CSV --query="$query" > "$out"; \
    done

# Run one/single competency-question query by number (e.g. `just scq 5`).
# Requires: just fuseki-start and ./rsparql (see just jena-fetch).
# Output file is written to queries/cq/results/.
scq number:
    @mkdir -p queries/cq/results
    @set -e; \
    num_padded="$(printf "%02d" "{{number}}")"; \
    set -- queries/cq/"${num_padded}"-*.rq; \
    if [ "$1" = "queries/cq/${num_padded}-*.rq" ]; then \
        echo "No CQ file found for number {{number}} (expected queries/cq/${num_padded}-*.rq)"; \
        exit 1; \
    fi; \
    if [ "$#" -ne 1 ]; then \
        echo "Expected exactly one CQ file for number {{number}}, found $#"; \
        exit 1; \
    fi; \
    query="$1"; \
    out="queries/cq/results/$(basename "${query%.rq}").csv"; \
    ./rsparql --service=http://localhost:3030/integration/sparql \
        --results=CSV --query="$query" > "$out"

# Run an ad-hoc SPARQL query against the Fuseki integration endpoint.
# Requires: just fuseki-start and ./rsparql (see just jena-fetch).
# Example: just sparql --query queries/cq/01-cross-source-identity-disagreement.rq
sparql *args:
    ./rsparql --service=http://localhost:3030/integration/sparql --results=CSV {{ args }}

# Build the QLever index from all available source files
qlever-index:
    @if [ ! -f data/raw/dnb/statements.ttl ] && [ -f data/raw/dnb/full.ttl ]; then cp data/raw/dnb/full.ttl data/raw/dnb/statements.ttl; fi
    qlever index --overwrite-existing \
        --multi-input-json '[{"cmd":"cat {}","format":"ttl","graph":"https://data.hisqu.de/graph/harmonized","for-each":"data/harmonized/statements.ttl"}]'

# Start the QLever SPARQL endpoint (port 7001)
qlever-start:
    qlever start

# Stop the QLever SPARQL endpoint
qlever-stop:
    qlever stop

# Build index and start server in one step
qlever-up: qlever-index qlever-start

# Build the common matching input table from source RDF snapshots.
# Writes data/tabular/common_profiles.csv and data/tabular/common_profiles.pkl.
match-context:
    PYTHONPATH=src uv run python -m matching.fetch_context

# Run Splink-based matching using the prepared common profile table.
# Writes pairwise predictions to data/matching_outputs/predictions_pairs.csv.
match-run:
    PYTHONPATH=src uv run python -m matching.main_match

# Full matching workflow: first build context table, then run matching.
match: match-context match-run

ui: ui-stop ui-fetch ui-build ui-setup ui-start

# Clone or pull the QLever UI source from GitHub
ui-fetch:
    if [ -d qlever-ui/.git ]; then git -C qlever-ui pull --ff-only; else git clone https://github.com/ad-freiburg/qlever-ui qlever-ui; fi

# Build the QLever UI Docker image
ui-build:
    docker build -t qleverui -f Dockerfile.qleverui qlever-ui/

# Configure the database and backend (run once after ui-build; safe to re-run)
ui-setup:
    chmod 777 qlever-ui/db && touch qlever-ui/db/qleverui.sqlite3 && chmod 666 qlever-ui/db/qleverui.sqlite3
    docker run --rm \
        -e PYTHONPATH=/app \
        -v "$(pwd)/qlever-ui/db:/app/db" \
        -v "$(pwd)/scripts/setup_qlever_ui.py:/setup.py:ro" \
        -v "$(pwd)/queries/examples:/queries/examples:ro" \
        -v "$(pwd)/queries/cq:/queries/cq:ro" \
        qleverui python /setup.py

# Start the QLever UI container on port 7000
ui-start:
    docker run -d \
        -p 7000:7000 \
        --add-host=host.docker.internal:host-gateway \
        -v "$(pwd)/qlever-ui/db:/app/db" \
        --name qleverui \
        qleverui

# Stop and remove the QLever UI container
ui-stop:
    -docker stop qleverui
    -docker rm qleverui

# ── ROBOT ──────────────────────────────────────────────────────────────────

# Run ROBOT via Docker; pass any ROBOT command and flags as arguments
# Example: just robot convert --input mappings/gs/ontology.owl --output out.ttl
robot *args:
    docker compose run --rm robot robot {{ args }}

# ── RDF4J ──────────────────────────────────────────────────────────────────

# Start RDF4J, then configure repositories and load source data
rdf4j: rdf4j-stop rdf4j-start rdf4j-setup

# Start the RDF4J server + Workbench container (port 8080)
rdf4j-start:
    docker run -d \
        --name rdf4j \
        -p 8080:8080 \
        --user "$(id -u):$(id -g)" \
        -e JAVA_OPTS="-Xms1g -Xmx4g" \
        -v "$(pwd)/rdf4j/data:/var/rdf4j" \
        -v "$(pwd)/rdf4j/logs:/usr/local/tomcat/logs" \
        eclipse/rdf4j-workbench:latest

# Stop and remove the RDF4J container (data persists in rdf4j/data/)
rdf4j-stop:
    -docker stop rdf4j
    -docker rm rdf4j

# Create repositories (gs, rgo, integration/FedX) and load available source data
rdf4j-setup:
    uv run python scripts/setup_rdf4j.py
