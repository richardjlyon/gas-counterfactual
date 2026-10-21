"""ECR 2026 security parameters and their effect on fleet B."""
from pathlib import Path

import pytest

from gascf.capacity import MARGIN_QUOTE, ECR_PDF, margin_fraction, read_derating, read_peak_base_case
from gascf.fleetb import cost_fleet_b
from gascf.official import read_desnz_plants


def test_derating_read_at_source():
    d = read_derating()
    assert round(d["ocgt"] * 100, 2) == 92.97     # Auction Guidelines 2026 Table 3
    assert round(d["ccgt"] * 100, 2) == 90.48


def test_peak_and_margin():
    pk = read_peak_base_case()
    assert pk["2030/31"] == 64.2 and pk["2025/26"] == 60.2 and pk["2027/28"] == 61.0
    assert margin_fraction("central") == pytest.approx(4.5 / 61.0)      # decision 0133: the 2027/28 peak
    assert margin_fraction("low") < margin_fraction("central") < margin_fraction("high")


def test_margin_quote_is_in_the_report():
    import re
    import pymupdf
    text = re.sub(r"\s+", " ", " ".join(p.get_text() for p in pymupdf.open(ECR_PDF)))
    assert MARGIN_QUOTE in text


RAW = Path(__file__).parents[1] / "data/raw"


@pytest.fixture(scope="module")
def plants():
    p = read_desnz_plants(RAW / "DESNZ_EGC2025_AnnexA.xlsx")
    return p[("Gas CCGT 93% Load Factor", 2030)], p[("Gas OCGT 760MW 30% Load Factor", 2030)]


def test_breakdowns_add_spare_capacity(plants):
    P, Q = plants
    ldc = sorted([10_000.0] * 100 + [5_000.0] * 900, reverse=True)
    perfect = cost_fleet_b(ldc, 30, P, Q, 0.07)
    real = cost_fleet_b(ldc, 30, P, Q, 0.07, derating={"ccgt": 0.9048, "ocgt": 0.9297})
    assert perfect.reserve_gw == pytest.approx(0.7, abs=0.01)
    running = real.ccgt_gw + real.ocgt_gw
    derated = real.ccgt_gw * 0.9048 + real.ocgt_gw * 0.9297 + real.reserve_gw * 0.9297
    assert derated == pytest.approx(10.0 * 1.07, rel=1e-6)    # rule met exactly
    assert real.reserve_gw > perfect.reserve_gw
    assert real.fixed_gbp_m > perfect.fixed_gbp_m and real.variable_gbp_m == perfect.variable_gbp_m
    assert running == pytest.approx(10.0, abs=0.05)
