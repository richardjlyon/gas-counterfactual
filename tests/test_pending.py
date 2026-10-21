"""Ticket 02: the source-status guard (PendingSourceError, require_sourced, release_stops)."""
from __future__ import annotations

import pytest

from gascf import pending as P

SOURCED = [{"year": 2021, "value": 1.0, "status": "SOURCED", "source_id": "X-1"},
           {"year": 2022, "value": 2.0, "status": "SOURCED", "source_id": "X-1"}]


def test_require_sourced_raises_on_pending_status():
    rows = [dict(SOURCED[0]), dict(SOURCED[1], status="PENDING")]
    with pytest.raises(P.PendingSourceError, match="toy"):
        P.require_sourced(rows, "toy")


def test_require_sourced_raises_on_a_null_value():
    rows = [dict(SOURCED[0]), dict(SOURCED[1], value=None)]
    with pytest.raises(P.PendingSourceError, match="value"):
        P.require_sourced(rows, "toy")


def test_require_sourced_raises_on_a_null_source_id():
    rows = [dict(SOURCED[0]), dict(SOURCED[1], source_id="")]
    with pytest.raises(P.PendingSourceError, match="source id"):
        P.require_sourced(rows, "toy")


def test_require_sourced_passes_on_sourced_rows():
    assert P.require_sourced(SOURCED, "toy") == SOURCED


def test_release_stops_lists_each_placeholder_file_and_row_count(tmp_path):
    (tmp_path / "a.csv").write_text("year,value,status,source_id\n2021,1,SOURCED,X\n2022,,PLACEHOLDER,\n2023,,PENDING,\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.csv").write_text("year,value,status,source_id\n2021,,PLACEHOLDER,\n")
    (tmp_path / "c.csv").write_text("year,value,status,source_id\n2021,1,SOURCED,X\n")
    (tmp_path / "d.csv").write_text("year,value\n2021,1\n")
    assert P.release_stops(tmp_path) == {"a.csv": 2, "sub/b.csv": 1}
