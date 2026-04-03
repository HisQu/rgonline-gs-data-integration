# Default: list available recipes
default:
    @just --list

# Set up dependencies, build reduced example inputs, run harmonization,
# export person-focused examples, and start query services.
go: sync test fetch reduce use-example clean harmonize examples-export qlever ui
setup: go

# Install project and dev dependencies
sync:
    uv sync --dev

# Run all tests
test *args:
    uv run pytest tests/ {{ args }}

# Run a single test file
test-file file *args:
    uv run pytest {{ file }} {{ args }}

# Fetch latest GND ontology HTML documentation to docs/gndo.html
gndo-doc-fetch:
    ./scripts/fetch_gndo_html.sh

fetch: gndo-doc-fetch gs-fetch dnb-fetch

clean: gs-clean

# Normalize fuzzy GS date literals in data/raw/gs/clean.ttl to xsd:gYear.
gs-fix-dates *args:
    UV_CACHE_DIR=/tmp/uv-cache uv run python src/gs/fix_gs_clean_dates.py {{ args }}

# Reduce all raw sources to example subsets.
reduce: gs-reduce dnb-reduce rgo-reduce

# Reduce GS raw data to four example persons.
gs-reduce:
    @mkdir -p data/raw/gs
    just robot query \
        --input data/raw/gs/full.ttl \
        --tdb true \
        --query mappings/gs/reduce.rq data/raw/gs/example.ttl

# Reduce DNB raw data to four example persons.
dnb-reduce:
    UV_CACHE_DIR=/tmp/uv-cache uv run python mappings/dnb/reduce.py

# Reduce RGO source data to four example persons.
rgo-reduce:
    @mkdir -p data/raw/rgo
    just robot query \
        --input data/raw/rgo/full.ttl \
        --tdb true \
        --query mappings/rgo/reduce.rq data/raw/rgo/example.ttl

# Activate full variants as pipeline inputs.
use-full:
    cp data/raw/gs/full.ttl data/raw/gs/statements.ttl
    cp data/raw/dnb/full.ttl data/raw/dnb/statements.ttl
    cp data/raw/rgo/full.ttl data/raw/rgo/statements.ttl

# Activate reduced example variants as pipeline inputs.
use-example:
    cp data/raw/gs/example.ttl data/raw/gs/statements.ttl
    cp data/raw/dnb/example.ttl data/raw/dnb/statements.ttl
    cp data/raw/rgo/example.ttl data/raw/rgo/statements.ttl

# Harmonize GS and RGO source graphs to GNDO-oriented projections using ROBOT.
# Writes outputs to data/harmonized/.
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
        --output data/harmonized/full.ttl

# Export per-person harmonized examples from data/harmonized/full.ttl.
# Default mode is focused (one person per file). To reproduce the previous
# broad traversal behavior, pass: --mode neighborhood
examples-export *args:
    UV_CACHE_DIR=/tmp/uv-cache uv run python src/export_harmonized_examples.py {{ args }}

# Fetch Germania Sacra persons active in the RG5 timeframe (1361–1447).
# Downloads all ~2775 pages, caches under data/raw/gs/pages/, filters by date,
# and writes merged output to data/raw/gs/full.ttl.
# Use --start-page N to resume from a specific page.
gs-fetch *args:
    uv run python src/gs/fetch.py {{ args }}
    cp data/raw/gs/full.ttl data/raw/gs/statements.ttl

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

# Download the GND person authority dump and extract to data/raw/dnb/full.ttl
dnb-fetch:
    @mkdir -p data/raw/dnb
    curl -L -o data/raw/dnb/authorities-gnd-person_lds.ttl.gz \
        https://data.dnb.de/opendata/authorities-gnd-person_lds.ttl.gz
    gunzip -c data/raw/dnb/authorities-gnd-person_lds.ttl.gz \
        > data/raw/dnb/full.ttl
    cp data/raw/dnb/full.ttl data/raw/dnb/statements.ttl

qlever-restart: qlever-stop qlever-start

qlever: qlever-index qlever-up

# Build the QLever index from all available source files
qlever-index:
    qlever index --overwrite-existing

# Start the QLever SPARQL endpoint (port 7001)
qlever-start:
    qlever start

# Stop the QLever SPARQL endpoint
qlever-stop:
    qlever stop

# Build index and start server in one step
qlever-up: qlever-index qlever-start

ui: ui-stop ui-build ui-setup ui-start

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
