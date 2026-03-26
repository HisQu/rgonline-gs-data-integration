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
