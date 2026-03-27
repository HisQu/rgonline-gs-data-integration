# Default: list available recipes
default:
    @just --list

# Set up the entire project environment and starts all services
go: sync test gs-fetch gs-clean dnb-fetch qlever ui

# Install project and dev dependencies
sync:
    uv sync --dev

# Run all tests
test *args:
    uv run pytest tests/ {{ args }}

# Run a single test file
test-file file *args:
    uv run pytest {{ file }} {{ args }}

fetch: gs-fetch dnb-fetch

clean: gs-clean

# Fetch Germania Sacra source data
gs-fetch:
    uv run python src/gs/fetch.py

# Run the GS cleaning SPARQL UPDATE against the QLever endpoint
gs-clean:
    curl -s -X POST "http://localhost:7001" \
        --data-urlencode "update@mappings/gs/clean.rq" \
        --data-urlencode "access-token=ecclesiastical-persons-token" \
    | uv run python scripts/report_update.py Persons Organisations Offices

# Count ecclesiastical persons on the DNB endpoint (no data fetched)
dnb-count:
    uv run python src/dnb/fetch.py --dry-run

# Fetch and materialize DNB source data
dnb-fetch *args:
    uv run python src/dnb/fetch.py {{ args }}

# Fetch DNB data with verbose logging
dnb-fetch-verbose:
    uv run python src/dnb/fetch.py -v

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
