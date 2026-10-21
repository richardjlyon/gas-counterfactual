"""The waterfall from fossil Britain's bill to net-zero Britain's (spec v4 §9.1-§9.2).

Plain words: start at fossil Britain's total bill (step 0), then add, one at a time, what
net-zero Britain pays that fossil Britain does not, or pays less of: power before carbon
(negative: in the like-for-like central case, s22, fossil Britain has to replace
renewables' output with extra fossil running and new gas, and pays a higher wholesale
price without them; under the `fleet="all_new"` switch it is the actual price less carbon
against a whole fossil fleet built new), carbon in the power price, renewables subsidies,
extra backup, running the grid, the high-voltage grid, the Climate Change Levy, and the
energy-saving schemes on bills (s24). Taxes count as a cost to whoever pays them; no Treasury
receipt is netted off (s30, Richard 12 Oct 2026: the Electricity Generator Levy line is deleted). The steps land exactly on net-zero Britain's
total (the identity, tested every year and every switch). Same-in-both costs (S1) sit in
step 0 and in the end bar and cancel.
"""
from __future__ import annotations

from gascf import bills as B

def _opt(b: dict, lid: str) -> float:
    """A line that exists only under some settings (NZ4b with the biomass CfD split): 0 if absent."""
    try:
        return B.val(b, lid)
    except KeyError:
        return 0.0


# Decision 0108 item 1.16 (B7, ruled a defect by Richard on 16 Oct 2026): each step is a list of signed terms; its value
# and its printed formula are both generated from them (step 1 is a difference, not a sum). Lines that exist only
# under some settings (OPTIONAL) count as 0 when absent and drop out of that year's formula.
OPTIONAL = ("NZ4b", "NZ11", "GO7")
STEP_TERMS = (
    (1, "Power, before carbon", ((1, "NZ1"), (-1, "NZ1c"), (-1, "GO1"), (-1, "GO1k"))),
    (2, "Carbon in the power price", ((1, "NZ1c"),)),
    (3, "Renewables subsidies", ((1, "NZ2"), (1, "NZ3"), (1, "NZ4"), (1, "NZ4b"))),
    (4, "Backup (Capacity Market extra)", ((1, "NZ5"),)),
    (5, "Running the grid", ((1, "NZ6"), (-1, "GO4"))),
    (6, "High-voltage grid", ((1, "NZ7"), (-1, "GO5"))),
    (7, "Climate Change Levy", ((1, "NZ8"),)),
    (8, "Energy-saving schemes (EEC, CERT, CESP, ECO, GBIS)", ((1, "NZ10"),)),
    (9, "VAT on households' share of the extra", ((1, "NZ11"), (-1, "GO7"))),
)


def _term_value(b: dict, lid: str) -> float:
    return _opt(b, lid) if lid in OPTIONAL else B.val(b, lid)


def _step_fn(terms):
    return lambda b: sum(sg * _term_value(b, lid) for sg, lid in terms)


def formula(terms: list[dict]) -> str:
    """'NZ1 - NZ1c - GO1 - GO1k' from [{"line", "sign"}, ...]."""
    out = ""
    for i, t in enumerate(terms):
        op = ("-" if t["sign"] < 0 else "") if i == 0 else (" - " if t["sign"] < 0 else " + ")
        out += op + t["line"]
    return out


STEPS = tuple((n, label, _step_fn(terms), tuple(lid for _, lid in terms)) for n, label, terms in STEP_TERMS)
_TERMS = {n: terms for n, _, terms in STEP_TERMS}
# lines that are zero by rule and sit in no step (GO2 is inside GO1; GO3, GO6 are zero)
ZERO_BY_RULE = ("GO2", "GO3", "GO6")
# Spec §15.3 item 3: each step's reader group (layout only; the steps and totals are unchanged).
STEP_GROUP = {1: "power", 2: "carbon", 3: "subsidies", 4: "backup", 5: "backup", 6: "wires",
              7: "ccl", 8: "schemes", 9: "vat"}
GROUP_ORDER = ("power", "subsidies", "backup", "wires", "carbon", "ccl", "schemes", "vat")
# s27b/s27c (spec §15.5 item 3): with the carbon split (central) step 2 is shown in two groups,
# carbon tax collected and carbon in the price (their sum is NZ1c, so step 2 and every total are
# unchanged), and step 7 (CCL, a tax collected) joins carbon tax collected.
GROUP_ORDER_SPLIT = ("power", "subsidies", "backup", "wires", "carbon_price_receipts", "ccl",
                     "carbon_in_price", "schemes", "vat")


def steps_for(b: dict, y: int) -> list[dict]:
    """One year's waterfall: step 0 (fossil total), steps 1-8, and the end bar, each in £m
    nominal, £m 2025 money and £ per household 2025 money, with the weakest basis of its lines."""
    H = b["households"]

    split = "carbon_split" in b

    def row(step, label, v, ids):
        ids = tuple(i for i in ids if _has(b, i))
        basis = B.weakest(*(B.line(b, i)["basis"] for i in ids)) if ids else "modelled"
        r = B.real(v, y)
        return {"step": step, "group": STEP_GROUP.get(step), "label": label, "value_gbp_m_nominal": v,
                "value_gbp_m_real": r,
                "per_household_real": r * 1e6 / H, "basis": basis, "lines": list(ids)}

    t = b["totals"]
    out = [row(0, "Fossil Britain", t["go_gbp_m"], ())]
    out[0]["basis"] = B.weakest(*(l["basis"] for l in b["fossil"]))
    out += [row(n, label, f(b), ids) for n, label, f, ids in STEPS]
    for r in out[1:]:
        r["terms"] = [{"line": lid, "sign": sg} for sg, lid in _TERMS[r["step"]] if _has(b, lid)]
        r["formula"] = formula(r["terms"])
    if split:
        cs = b["carbon_split"]
        st2 = next(r for r in out if r["step"] == 2)
        parts = {g: cs[g]["national_gbp_m_nominal"] for g in ("carbon_price_receipts", "carbon_in_price")}
        if abs(sum(parts.values()) - st2["value_gbp_m_nominal"]) > 1e-6:
            raise AssertionError(f"{y}: carbon split {parts} does not add to NZ1c {st2['value_gbp_m_nominal']}")
        st2["group"] = "carbon_split"
        st2["parts"] = {g: {"value_gbp_m_nominal": v, "value_gbp_m_real": B.real(v, y),
                            "per_household_real": B.real(v, y) * 1e6 / H, "basis": cs[g]["basis"],
                            "line": cs[g]["id"]} for g, v in parts.items()}
    out.append(row("=", "Net-zero Britain", t["nz_gbp_m"], ()))
    out[-1]["basis"] = B.weakest(*(l["basis"] for l in b["netzero"]))
    return out


def _has(b: dict, lid: str) -> bool:
    try:
        B.line(b, lid)
        return True
    except KeyError:
        return False


def waterfall(s: B.Settings = B.CENTRAL) -> dict[int, list[dict]]:
    built = B.build(s)
    return {y: steps_for(built[y], y) for y in B.YEARS}


def identity_error(steps: list[dict]) -> float:
    """GO_total + Σ steps 1-8 − NZ_total, £m nominal (spec §9.2: must be within £0.01m)."""
    mid = sum(s["value_gbp_m_nominal"] for s in steps if s["step"] not in (0, "="))
    return steps[0]["value_gbp_m_nominal"] + mid - steps[-1]["value_gbp_m_nominal"]


def lines_in_steps() -> list[str]:
    """Every line id named by a step (NZ1c appears in steps 1 and 2 as carve-out and step)."""
    return [i for _, _, _, ids in STEPS for i in ids]


def grouped(steps: list[dict]) -> list[dict]:
    """The same waterfall in reader groups (§15.3 item 3): fossil Britain, power before carbon,
    then wind and solar subsidies, backup, long power lines, carbon tax, energy-saving schemes, VAT, and the end bar.
    Sums of the steps it groups; the identity still lands on net-zero Britain's total."""
    from gascf.bills import GROUP_LABELS, weakest
    out = [dict(steps[0], group="fossil")]
    split = any(s.get("parts") for s in steps)
    # each step as one or more (group, part-row) pieces: step 2 split in two when the carbon is split
    pieces = []
    for s in steps:
        if s["step"] in (0, "="):
            continue
        if s.get("parts"):
            pieces += [(g, dict(p, step=s["step"], lines=[p["line"]])) for g, p in s["parts"].items()]
        else:
            pieces.append((s["group"], s))
    for g in (GROUP_ORDER_SPLIT if split else GROUP_ORDER):
        mine = [p for gg, p in pieces if gg == g]
        out.append({"step": g, "group": g, "label": GROUP_LABELS[g],
                    "value_gbp_m_nominal": sum(s["value_gbp_m_nominal"] for s in mine),
                    "value_gbp_m_real": sum(s["value_gbp_m_real"] for s in mine),
                    "per_household_real": sum(s["per_household_real"] for s in mine),
                    "basis": weakest(*(s["basis"] for s in mine)) if mine else "modelled",
                    "steps": [s["step"] for s in mine], "lines": [i for s in mine for i in s["lines"]]})
    out.append(dict(steps[-1], group="netzero"))
    return out
