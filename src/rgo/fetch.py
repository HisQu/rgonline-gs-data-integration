import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx


DATASET = "rgo"
SOURCE_FILE = "rg5.xml"
REPO_OWNER = "HisQu"
REPO_NAME = "RG_data"
REPO_PATH = "rg_xml/rg5.xml"
GIT_REF = "792fcd6"

# Required for private repository access. Can be exported in a shell or set it an environment before running the script.
# Example:
#   export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"

CONTENTS_API_URL = (
    f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{REPO_PATH}"
)

BASE_DIR = Path("data/raw/rgo")
LATEST_DIR = BASE_DIR / "latest"
SNAPSHOT_DIR = BASE_DIR / "snapshots"


def sha256_of_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def fetch() -> None:
    token = os.getenv(GITHUB_TOKEN_ENV)
    if not token:
        raise RuntimeError(
            f"Missing GitHub token. Please set the environment variable "
            f"{GITHUB_TOKEN_ENV}."
        )

    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).replace(microsecond=0)
    ts_str = ts.isoformat().replace("+00:00", "Z")

    snapshot_xml = SNAPSHOT_DIR / f"{ts_str}_{SOURCE_FILE}"
    snapshot_meta = SNAPSHOT_DIR / f"{ts_str}_{SOURCE_FILE}.metadata.json"

    latest_xml = LATEST_DIR / SOURCE_FILE
    latest_meta = LATEST_DIR / f"{SOURCE_FILE}.metadata.json"

    headers_json = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "hisqu-rg-fetch-script",
        }
    headers_raw = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "hisqu-rg-fetch-script",
    }

    params = {"ref": GIT_REF}

    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        meta_response = client.get(CONTENTS_API_URL, params=params, headers=headers_json)
        meta_response.raise_for_status()
        payload = meta_response.json()

        if payload.get("type") != "file":
            raise RuntimeError(
                f"Expected a file at {REPO_PATH}, but got type={payload.get('type')!r}"
            )

        raw_response = client.get(CONTENTS_API_URL, params=params, headers=headers_raw)
        raw_response.raise_for_status()
        xml_bytes = raw_response.content

    if not xml_bytes:
        raise RuntimeError("GitHub raw response did not contain file bytes.")

    snapshot_xml.write_bytes(xml_bytes)
    latest_xml.write_bytes(xml_bytes)

    checksum = sha256_of_file(snapshot_xml)
    size_bytes = snapshot_xml.stat().st_size

    metadata = {
        "dataset": DATASET,
        "source_system": "RG Online / private GitHub repository",
        "logical_source_file": REPO_PATH,
        "repo_owner": REPO_OWNER,
        "repo_name": REPO_NAME,
        "git_ref_requested": GIT_REF,
        "github_token_env_var": GITHUB_TOKEN_ENV,
        "contents_api_url": CONTENTS_API_URL,
        "html_url": payload.get("html_url"),
        "download_url": payload.get("download_url"),
        "resolved_path": payload.get("path"),
        "git_blob_sha": payload.get("sha"),
        "file_size_reported_by_github": payload.get("size"),
        "fetched_at_utc": ts_str, 
        "http_status": meta_response.status_code,
        "etag": meta_response.headers.get("etag"),
        "last_modified": meta_response.headers.get("last-modified"),
        "x_github_request_id": meta_response.headers.get("x-github-request-id"),
        "snapshot_path": str(snapshot_xml),
        "latest_path": str(latest_xml),
        "sha256": checksum,
        "size_bytes": size_bytes,
    }

    snapshot_meta.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    latest_meta.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Saved snapshot to {snapshot_xml}")
    print(f"Saved latest copy to {latest_xml}")

if __name__ == "__main__":
    fetch()