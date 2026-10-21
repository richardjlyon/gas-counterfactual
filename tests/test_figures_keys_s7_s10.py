"""Ticket 44 (key half): §7.2 new-build keys and §10.3 RPI-X keys.

Seam: `tools.figures.generate(run, modules=[...])` on the v4-s35 run file (s35 values are references, not
quotable) with fixture edits; the §10 rows come from the one-at-a-time block (28) once ticket 25 merges."""
import copy
import json
from pathlib import Path

import pytest

from tools import figures as F

ROOT = Path(__file__).resolve().parents[1]
RUN = json.loads((ROOT / "out/v4/2026-10-14-s35.json").read_text())


def test_new_ccgt_built_by_2024_reads_fleet_ccgt_gw():
    from tools.figures_keys import fleet
    k = F.generate(RUN, modules=[fleet])["keys"]["rb.s7.new_ccgt_built_by_2024"]
    assert k["value"] is False                        # s35 reference: ccgt_gw = 0 every year
    assert k["meta"]["years_with_new_ccgt"] == [] or "years_with_new_ccgt" not in k["meta"]
    r = copy.deepcopy(RUN)
    r["fleet"]["2011"]["ccgt_gw"] = 0.5
    r["fleet"]["2025"]["ccgt_gw"] = 9.0
    assert F.generate(r, modules=[fleet])["keys"]["rb.s7.new_ccgt_built_by_2024"]["value"] is True
    r2 = copy.deepcopy(RUN)
    r2["fleet"]["2025"]["ccgt_gw"] = 9.0               # 2025 is never read
    assert F.generate(r2, modules=[fleet])["keys"]["rb.s7.new_ccgt_built_by_2024"]["value"] is False


def test_new_build_mix_2024_sums_and_reads_fleet():
    """Q-KEYS-5: printed at the new-build-sized total without the margin spare; spare in its own annex key."""
    from tools.figures_keys import fleet
    k = F.generate(RUN, modules=[fleet])["keys"]
    t = k["rb.s7.new_build_mix_gw_2024"]["value"]
    f = RUN["fleet"]["2024"]
    rows = {"ccgt": f["ccgt_gw"], "ocgt": f["ocgt_gw"], "coal": f["new_coal_gw"],
            "ocgt_block_spare": f["spare_gw"] - f["firm_extra_gw"], "ocgt_firm_spare": f["firm_extra_gw"]}
    for n, v in rows.items():
        assert t[n] == pytest.approx(v, abs=1e-9) and t[n] >= 0
    assert t["total"] == pytest.approx(sum(rows.values()), abs=1e-9)
    assert t["total_ex_firm_spare"] == pytest.approx(f["new_gw"], abs=1e-9)
    assert t["printed_total"] == "total_ex_firm_spare"
    assert k["annex.s7.margin_spare_ocgt_gw_2024"]["value"] == pytest.approx(f["firm_extra_gw"], abs=1e-9)
    # s35 reference only: OCGT 6.266, block spare 0.474, firm spare 0.188; 6.740 printed, 6.928 with the spare
    assert (round(t["ocgt"], 3), round(t["total_ex_firm_spare"], 3), round(t["total"], 3)) == (6.266, 6.740, 6.928)
    assert "afresh" in k["rb.s7.new_build_mix_gw_2024"]["meta"]["label"]
