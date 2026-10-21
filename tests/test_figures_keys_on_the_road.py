"""Ticket 26 (0097): figures keys for the pre-2002 netting of NZ2 (Fossil Fuel Levy, to 2019) and NZ10 (EESoP,
every year), each incl. VAT (figures-keys.md rows pre2002_netting_nz2/nz10/total). Read from the run file's
on_the_road block, which carries the netted-off part AND the VAT the engine removed (option a), in 2024 prices.
Toy run, no build."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import figures as F  # noqa: E402

Y = [str(y) for y in range(2002, 2026)]
RUN = {"meta": {"engine_version": "toy", "price_base": 2025, "deflator": "ONS CPIH L522"},
       "bills": {y: {"netzero": [], "gasonly": []} for y in Y},
       "on_the_road": {"decision": "0097, 0044", "years": {
           y: {"nz2_on_the_road_gbp_m_2024": 10.0, "nz2_on_the_road_vat_gbp_m_2024": 1.0,
               "nz10_on_the_road_gbp_m_2024": 20.0, "nz10_on_the_road_vat_gbp_m_2024": 2.0} for y in Y}}}


def test_pre2002_netting_keys_from_the_run_file():
    from tools.figures_keys import on_the_road as K
    from tools import figures_keys
    assert "on_the_road" in figures_keys.MODULES
    v = F.generate(RUN, modules=[K])["keys"]
    nz2 = -(10.0 + 1.0) * 18 / 1e3                       # 2002-2019 inclusive, incl VAT
    nz10 = -(20.0 + 2.0) * 23 / 1e3                      # 2002-2024 inclusive, incl VAT
    assert v["pre2002_netting_nz2_2002_19_gbp_bn"]["value"] == pytest.approx(nz2)
    assert v["pre2002_netting_nz10_2002_24_gbp_bn"]["value"] == pytest.approx(nz10)
    assert v["pre2002_netting_total_2002_24_gbp_bn"]["value"] == pytest.approx(nz2 + nz10)
    for meta in (x["meta"] for x in v.values()):
        assert meta["ticket"] == "26" and meta["basis"] == "modelled"


def test_pre2002_netting_keys_none_without_the_block():
    from tools.figures_keys import on_the_road as K
    v = F.generate({"meta": {"engine_version": "toy", "price_base": 2025}, "bills": {}}, modules=[K])["keys"]
    assert all(v[k]["value"] is None for k in K.DECLARED)


def test_10_flags_nz10_keys_interim_approved_and_nz2_sourced():
    """Spec test 10: every figures.json key that depends on NZ10 netting carries both INTERIM_APPROVED notes
    (EESoP spend indicative, split by energy saved); the NZ2 (FFL) key is SOURCED. The interim keys show up in
    the release record's non-SOURCED list."""
    from tools.figures_keys import on_the_road as K
    fig = F.generate(RUN, modules=[K])
    v = fig["keys"]
    assert v["pre2002_netting_nz2_2002_19_gbp_bn"]["meta"]["status"] == "SOURCED"
    for k in ("pre2002_netting_nz10_2002_24_gbp_bn", "pre2002_netting_total_2002_24_gbp_bn"):
        meta = v[k]["meta"]
        assert meta["status"] == "INTERIM_APPROVED", k
        assert len(meta["notes"]) == 2 and all("INTERIM_APPROVED" in n for n in meta["notes"]), k
    nonsourced = dict(F.not_sourced(fig))
    assert nonsourced.get("pre2002_netting_nz10_2002_24_gbp_bn") == "INTERIM_APPROVED"
    assert nonsourced.get("pre2002_netting_total_2002_24_gbp_bn") == "INTERIM_APPROVED"
    assert "pre2002_netting_nz2_2002_19_gbp_bn" not in nonsourced


def test_nz2_value_follows_settings_and_refuses_a_mislabelled_end_year(monkeypatch):
    """Review ST5 + R2-ST5a: the NZ2 netting end year is the engine's own Settings.otr_nz2_end_year (not a 2019
    literal in the filter), and because the key name/label/period are fixed at 2002-19 the build refuses if the
    engine's end year is anything else, so a 2002-10 value can never sit under a 2002-19 label."""
    from gascf import bills
    from tools.figures_keys import on_the_road as K
    v = F.generate(RUN, modules=[K])["keys"]
    assert v["pre2002_netting_nz2_2002_19_gbp_bn"]["value"] == pytest.approx(-(10.0 + 1.0) * 18 / 1e3)  # 2002-2019
    monkeypatch.setattr(bills.Settings, "otr_nz2_end_year", 2010)
    with pytest.raises(ValueError, match="2002-19"):
        F.generate(RUN, modules=[K])


def test_interim_notes_derive_the_eesop_numbers_from_the_engine_inputs():
    """Review ST5: the EESoP spend and electricity share in the INTERIM notes are derived from otr_blocks.INPUTS,
    not re-typed, so a change to the inputs flows through to the printed note."""
    from gascf.otr_blocks import INPUTS
    from tools.figures_keys import on_the_road as K
    spend = next(i["value"] for i in INPUTS if i["name"] == "eesop_spend_gbp_m")
    share = next(i["value"] for i in INPUTS if i["name"] == "eesop_electricity_share")
    notes = " ".join(K._INTERIM)
    assert f"£{spend:g}m" in notes and f"{share * 100:.1f}%" in notes
    assert "£110m" in notes and "44.8%" in notes


def test_pre2002_netting_2002_04_in_2025_prices_0111():
    """Research-director's request (19 Oct 2026) for the figure decision 0111 quotes (about £647.2m, 2025 prices):
    0097's netting over 2002-04, NZ2 + NZ10 incl. their VAT, as the positive amount removed, £m in 2025 prices."""
    from gascf import deflator_cpih
    from tools.figures_keys import on_the_road as K
    c = deflator_cpih.cpih()
    v = F.generate(RUN, modules=[K])["keys"]["pre2002_netting_2002_04_gbp_m"]
    assert v["value"] == pytest.approx(3 * (10.0 + 1.0 + 20.0 + 2.0) * c[2025] / c[2024], rel=1e-12)
    assert v["meta"]["units"] == "£m, 2025 prices" and v["meta"]["period"] == "2002-2004"
