"""Tests for the DNB acquisition and materialization pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dnb.fetch import (
    ENDPOINT,
    main,
    run_count_query,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_ntriples() -> str:
    return (FIXTURES_DIR / "source-dnb-sample.nt").read_text(encoding="utf-8")


@pytest.fixture
def mock_count_response() -> dict:
    return {
        "results": {
            "bindings": [{"total": {"type": "literal", "value": "25"}}]
        }
    }


class TestRunCountQuery:
    def test_parses_count_from_json(self, mock_count_response: dict) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_count_response
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        total = run_count_query(mock_client)
        assert total == 25

    def test_sends_correct_accept_header(self, mock_count_response: dict) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_count_response
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        run_count_query(mock_client)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["headers"]["Accept"] == "application/sparql-results+json"


class TestMainDryRun:
    @patch("dnb.fetch.httpx.Client")
    def test_dry_run_prints_count(
        self, mock_client_cls: MagicMock, mock_count_response: dict, capsys: pytest.CaptureFixture
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_count_response
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        main(["--dry-run"])

        captured = capsys.readouterr()
        assert "25" in captured.out


class TestFetchAndMaterialize:
    @patch("dnb.fetch.httpx.Client")
    def test_creates_pages_metadata_and_turtle(
        self,
        mock_client_cls: MagicMock,
        sample_ntriples: str,
        mock_count_response: dict,
        tmp_path: Path,
    ) -> None:
        raw_dir = tmp_path / "raw"
        output_dir = tmp_path / "interim"

        mock_count_resp = MagicMock()
        mock_count_resp.json.return_value = mock_count_response
        mock_count_resp.raise_for_status = MagicMock()

        mock_construct_resp = MagicMock()
        mock_construct_resp.text = sample_ntriples
        mock_construct_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.side_effect = [mock_count_resp, mock_construct_resp]
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        main([
            "--raw-dir", str(raw_dir),
            "--output-dir", str(output_dir),
            "--page-size", "100",
        ])

        # Raw page cached
        page_files = list(raw_dir.glob("persons-page-*.nt"))
        assert len(page_files) == 1
        assert page_files[0].stat().st_size > 0

        # Metadata written
        meta_path = raw_dir / "fetch-metadata.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["total_persons"] == 25
        assert meta["endpoint"] == ENDPOINT
        assert meta["num_triples_deduped"] > 0

        # Materialized Turtle written
        ttl_path = output_dir / "source-dnb.ttl"
        assert ttl_path.exists()
        assert ttl_path.stat().st_size > 0

    @patch("dnb.fetch.httpx.Client")
    def test_skips_existing_pages(
        self,
        mock_client_cls: MagicMock,
        sample_ntriples: str,
        mock_count_response: dict,
        tmp_path: Path,
    ) -> None:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        output_dir = tmp_path / "interim"

        # Pre-create page file with valid N-Triples
        existing_page = raw_dir / "persons-page-0000.nt"
        existing_page.write_text(sample_ntriples)

        mock_count_resp = MagicMock()
        mock_count_resp.json.return_value = mock_count_response
        mock_count_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_count_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        main([
            "--raw-dir", str(raw_dir),
            "--output-dir", str(output_dir),
            "--page-size", "100",
        ])

        # Only the count query should have been called (no construct fetch)
        assert mock_client.get.call_count == 1
