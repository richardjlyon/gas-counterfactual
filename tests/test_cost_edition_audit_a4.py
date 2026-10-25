"""Input audit v4-s41, part A find 4 (A4): the cost edition in force for 2025 (card [internal ticket]; v4-s42, decision 0195).

fossil_fleet.edition states the rule 'the latest official cost set published by the end of `year`'. DESNZ Electricity
Generation Costs 2025 was first published on 14 January 2026 (GOV.UK content API, first_published_at 2026-01-14;
release copy's cover 'first published January 2026'), so the set in force at the end of 2025 is EGC 2023. The spec
§4.3 table gives '2025 ->' to EGC 2025; the two disagree, and decision 0195 (Richard Lyon, 24 Oct 2026, "yes to all three") rules that the stated rule governs (part A
option 4(b)); the spec table is corrected to match.
"""
from gascf import fossil_fleet as ff


def test_2025_takes_egc2023():
    ed = ff.edition(2025)
    assert ed.source_id["ccgt"] == ed.source_id["ocgt"] == "desnz-egc2023-annexA"


def test_2025_plants_equal_2024s():
    a, b = ff.edition(2024), ff.edition(2025)
    assert (a.ccgt, a.ocgt, a.coal, a.coal_nox) == (b.ccgt, b.ocgt, b.coal, b.coal_nox)
    assert a.price_base == b.price_base


def test_2024_unchanged():
    assert ff.edition(2024).source_id["ccgt"] == "desnz-egc2023-annexA"
