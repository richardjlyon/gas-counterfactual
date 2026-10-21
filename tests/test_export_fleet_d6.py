"""Found at the s36 release run (19 Oct 2026): bills._ic_fields puts the D6 interconnector fields on fleet[y]
(ticket 15: ic_basis, sizing peak, margin on gross, imports at peak; 0066: ic_peak_dy), but export_v4._fleet's
field list never named them, so the run file lacked them and the figures keys that read them (ic_peak_dy_2019,
ic_peak_dy_contracted_mw_2019 and others) were None, which the release gate refuses. Light: a stand-in build."""
from __future__ import annotations

import inspect

from gascf import bills as B
from gascf import export_v4 as X


def _d6_names() -> set[str]:
    sp = {"gross_peak_mw": 1.0, "residual_mw": 1.0, "day": __import__("datetime").date(2019, 1, 15), "period": 30,
          "contracted": True, "nuclear_gw": 1.0, "ps_gw": 1.0, "imports_metered_gw": 1.0,
          "imports_contracted_gw": 1.0, "imports_counted_gw": 1.0}
    fr = {"firm_requirement_gw": 1.0, "margin_on_gross_extra_gw": 1.0}
    called = {"ic_called_twh": 0.0, "ic_called_halfhours": 0, "ic_called_gbp_m": 0.0}
    return set(B._ic_fields(2019, sp, 0.1, fr, "contracted", called))


def test_every_d6_fleet_field_reaches_the_run_file():
    names = _d6_names()
    assert {"ic_peak_dy", "ic_peak_dy_contracted_mw", "margin_on_gross_extra_gw", "sizing_peak_halfhour"} <= names
    built = {y: {"fleet": {n: 1.0 for n in names} | {"coal_gw": 1.0}} for y in B.YEARS}
    out = X._fleet(built)
    missing = sorted(names - set(out["2019"]))
    assert not missing, f"fleet[y] D6 fields not exported: {missing}"


def test_ic_fields_signature_unchanged():
    assert list(inspect.signature(B._ic_fields).parameters) == ["year", "sp", "mfrac", "fr", "ic_basis", "called"]
