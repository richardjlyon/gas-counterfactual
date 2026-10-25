"""Input audit v4-s41, part A find 5 (A5): the cost edition in force for 2011 (card [internal ticket]; v4-s42, decision 0195).

Under fossil_fleet.edition's stated rule ('the latest official cost set published by the end of `year`') 2011 takes
the PB 2011 update (Parsons Brinckerhoff for DECC, August 2011), not Mott MacDonald 2010. The spec §4.3 table gives
2002-11 to MM2010; decision 0195 rules that the stated rule governs and the table is corrected. PB 2011 has CCGT and OCGT tables (Appendix B, printed pp.18 and 26) and an
unabated coal table without NOx abatement; coal for 2011 stays on MM2010 (FGD + SCR reference plant) in this
candidate, because pairing PB 2011 coal with a retrofit would be a method choice. PB 2011 prints no price base; the
release takes 2011 (2010 measured as a variant, no printed difference): stated in decision 0195, not ruled.
Expected values: the Nth-of-a-kind medium column printed in the PDF.
"""
import pytest

from gascf import fossil_fleet as ff


def test_2011_gas_plant_is_pb2011():
    ed = ff.edition(2011)
    assert ed.source_id["ccgt"] == "pb2011-ccgt" and ed.source_id["ocgt"] == "pb2011-ocgt"
    assert ed.ccgt.construction_gbp_kw["medium"] == pytest.approx(640.0)      # EPC cost £/kW, p.18
    assert ed.ccgt.fixed_om_gbp_mw_yr == pytest.approx(23182.0)
    assert ed.ocgt.construction_gbp_kw["medium"] == pytest.approx(525.0)      # p.26
    assert ed.ocgt.connection_uos_gbp_mw_yr == pytest.approx(-2359.0)
    assert ed.basis["ocgt"] == "measured"


def test_2011_coal_stays_mm2010():
    assert ff.edition(2011).source_id["coal"] == "mm2010-tableA3"


@pytest.mark.parametrize("year,src", [(2010, "mm2010-tableA1"), (2012, "pb2012-ccgt")])
def test_neighbours_unchanged(year, src):
    assert ff.edition(year).source_id["ccgt"] == src
