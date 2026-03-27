# Default: list available recipes
default:
    @just --list

# Install project and dev dependencies
sync:
    uv sync --dev

# Run all tests
test *args:
    uv run pytest tests/ {{ args }}

# Run a single test file
test-file file *args:
    uv run pytest {{ file }} {{ args }}

# Count ecclesiastical persons on the DNB endpoint (no data fetched)
dnb-count:
    uv run python src/dnb/acquisition/fetch_source_dnb.py --dry-run

# Fetch and materialize DNB source data
dnb-fetch *args:
    uv run python src/dnb/acquisition/fetch_source_dnb.py {{ args }}

# Fetch DNB data with verbose logging
dnb-fetch-verbose:
    uv run python src/dnb/acquisition/fetch_source_dnb.py -v

# Build the QLever index from all available source files
qlever-index:
    qlever index

# Start the QLever SPARQL endpoint (port 7001)
qlever-start:
    qlever start

# Stop the QLever SPARQL endpoint
qlever-stop:
    qlever stop

# Build index and start server in one step
qlever-up: qlever-index qlever-start

# Build the QLever UI Docker image
ui-build:
    docker build -t qleverui qlever-ui/

# Configure the database and backend (run once after ui-build; safe to re-run)
ui-setup:
    docker run --rm \
        -v "$(pwd)/qlever-ui/db:/app/db" \
        -v "$(pwd)/scripts/setup_qlever_ui.py:/setup.py:ro" \
        qleverui python /setup.py

# Start the QLever UI container on port 7000
ui-start:
    docker run -d \
        --network host \
        -v "$(pwd)/qlever-ui/db:/app/db" \
        --name qleverui \
        qleverui

# Stop and remove the QLever UI container
ui-stop:
    docker stop qleverui
    docker rm qleverui
