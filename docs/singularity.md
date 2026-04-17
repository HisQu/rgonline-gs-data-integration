# Singularity 3.11 Development Container

This project can be run in a Singularity/Apptainer image built from:

- `singularity/Singularity.dev.def`

The definition mirrors `Dockerfile.dev` and installs:

- Python 3.12 + `uv`
- OpenJDK 21
- `just`
- `qlever`
- Docker CLI + Compose plugin

## Prerequisites

- SingularityCE `3.11.x`
- Linux host with network access during build

Check version:

```bash
singularity --version
```

## Build

From the repository root (auto-uses `fakeroot` when available):

```bash
just singularity-build
```

If your host does not support `--fakeroot` (for example: `no mapping entry found in /etc/subuid`), use one of:

Remote build:

```bash
just singularity-build-remote
```

Local root build:

```bash
just singularity-build-sudo
```

## Run an interactive shell

Bind the repository into `/workspace`:

```bash
singularity shell --bind "$(pwd):/workspace" rgonline-dev.sif
```

Inside the container:

```bash
cd /workspace
uv sync --dev --frozen
just sync
just test
```

## Run commands directly

```bash
singularity exec --bind "$(pwd):/workspace" rgonline-dev.sif just test
```

## Use GHCR instead of local build

If your cluster cannot use `fakeroot` and you do not have `sudo`, publish `Dockerfile.dev`
to GHCR from GitHub Actions, then pull it as a SIF.

Workflow file:

- `.github/workflows/ghcr-dev-image.yml`

Published tags:

- `ghcr.io/<owner>/<repo>:dev-latest`
- `ghcr.io/<owner>/<repo>:dev-<git-sha>`

Note: OCI image references must be lowercase.

Pull public image:

```bash
just singularity-pull-oci ghcr.io/<owner>/<repo>:dev-latest
```

Pull private image (requires token with `read:packages`):

```bash
export SINGULARITY_DOCKER_USERNAME=<github-username>
export SINGULARITY_DOCKER_PASSWORD=<github-token>
just singularity-pull-oci-private ghcr.io/<owner>/<repo>:dev-latest
```

Run:

```bash
just singularity-shell
```

## Notes about Docker-dependent recipes

Recipes that call `docker` (for example `just ui`, `just rdf4j`, or Docker-based ROBOT usage) still require access to a host Docker daemon and appropriate socket/container runtime setup from your environment. Python/ROBOT/Fuseki/QLever workflows can run fully inside the Singularity container.
