"""Ticket 44 (key half): §4.3 worked half-hour keys and the §8.4 Shao-method 2022 uplift.

Names: the placeholder names are the figures.json keys; the ruled `rb.s4.*` names are the engine-side
fields, carried as `engine_field` (Q-KEYS-1 and R-A3, 17 Oct 2026: placeholder names win). Values come from
`fleet[2024].worked_hh`, which the export half of 44 (serial tail) adds; until then every value is None.
"""
from __future__ import annotations


BLOCKS = ("coal", "ccgt", "other_gas", "oil", "new_ccgt", "new_ocgt")   # the stack's block names (R-A3)


def _m(label, run_field, units, engine_field=None, **extra):
    m = {"label": label, "basis": "modelled", "provisional": True, "ticket": "44", "run_field": run_field,
         "units": units, "period": "2024", "status": "PENDING", "print": True, **extra}
    if engine_field:
        m["engine_field"] = engine_field
    return m


def _wh(p):
    P = p.capitalize()
    f = f"fleet[2024].worked_hh.{p}"
    return {
        f"wh_{p}_halfhour": _m(f"Date and half-hour (span on the UK clock, e.g. 12:00-12:30) of the worked {p} half-hour: the 2024 half-hour "
                               f"with the {'highest' if p == 'peak' else 'median'} residual demand",
                               f"{f}.date + clock span of {f}.sp", "datetime",
                               f"rb.s4.worked_hh_{p}_date"),
        f"wh_{p}_settlement_period": _m(f"Settlement period of the worked {p} half-hour (number only; the date is "
                                        f"wh_{p}_halfhour)", f"{f}.sp", "number", f"rb.s4.worked_hh_{p}_sp"),
        f"wh_{p}_residual_gw": _m(f"Residual demand in the worked {p} half-hour", f"{f}.residual_mw / 1000", "GW"),
        f"wh_{p}_uplift_gbp_mwh": _m(f"Shao-scaled renewables uplift to the price in the worked {p} half-hour "
                                     "(raw step × the year's mult + flat; the value that feeds the headline)",
                                     f"{f}.scaled_step_gbp_mwh", "£/MWh, cash",
                                     f"rb.s4.merit_order_uplift_{p}_gbp_mwh"),
        f"annex.s4.merit_order_uplift_raw_{p}_gbp_mwh": _m(
            f"Raw merit-order step in the worked {p} half-hour, max(0, p1 − p0), for the methods annex",
            f"{f}.raw_step_gbp_mwh", "£/MWh, cash", print=False),
        # R-A3: which of p0, p1 is "RB's marginal cost" is the export half's to state (serial tail); the key
        # reads the export's own rb_cost_gbp_mwh and carries p0/p1 nowhere else.
        f"wh_{p}_rb_cost_gbp_mwh": _m(f"Reliable Britain's marginal cost in the worked {p} half-hour (R-A3)",
                                      f"{f}.rb_cost_gbp_mwh (export: p0, p1, top running block)", "£/MWh, cash"),
        f"wh_{p}_marginal_plant": _m(f"Marginal plant type on the road in the worked {p} half-hour (the top "
                                     "running block)", f"{f}.top_block", "text", allowed=list(BLOCKS)),
        # RB v1.1 F7 (decision 0163, R25 (a), Richard Lyon 21 Oct 2026): Elexon's market index price beside the
        # worked half-hour, named as what it is (a short-term market index, not the day-ahead auction price).
        f"wh_{p}_market_index_price_gbp_mwh": _m(
            f"Elexon market index price (MID, APX) in the worked {p} half-hour: the actual short-term market "
            "price, shown beside the worked example (Elexon BMRS MID, free)",
            f"{f}.market_index_price_gbp_mwh (data/raw/elexon/MID_APX_2024.csv, Elexon BMRS MID, APXMIDP rows)",
            "£/MWh, cash", basis="measured", status="SOURCED", provisional=False,
            source_id="elexon-mid-apx", decisions=["0163 R25 (a)"]),
    }


def _sp_clock(date: str, sp: int) -> str:
    import datetime as dt
    d = dt.date.fromisoformat(date)
    last_sun = lambda m: max(dt.date(d.year, m, x) for x in range(25, 32) if dt.date(d.year, m, x).weekday() == 6)
    if d in (last_sun(3), last_sun(10)):
        raise NotImplementedError(f"{date} is a clock-change day (46 or 50 periods): SP {sp} needs the Editor")
    a, b = (sp - 1) * 30, sp * 30 % (24 * 60)          # option (b), EIC 17 Oct 2026: the span, UK clock
    return f"{date} {a // 60:02d}:{a % 60:02d}-{b // 60:02d}:{b % 60:02d}"


DECLARED = {
    **_wh("peak"), **_wh("median"),
    # E2 (Editor-in-chief, 17 Oct 2026): MODELLED, never sourced.yaml.
    "shao_uplift_2022_gbp_mwh": _m(
        "Merit-order uplift in 2022, time-mean, modelled: this paper's estimate using the method of Shao and "
        "others (2022) (their coefficients, wind and solar), applied by the engine; not a figure published by "
        "Shao and others; not the v4-s39 central uplift, which from May 2021 to Dec 2023 is re-estimated on "
        "outturn (decision 0164, M9 B)", "fleet[2022].moe.shao_mean_gbp_mwh (time mean; read only where moe.rule is 'shao')",
        "£/MWh, cash",
        period="2022", estimate_label="modelled (engine value), not sourced (E2)"),
    # R26 / R123 (research-director, card [internal ticket]): the same for 2021 and 2023, beside the 2022 key, same basis.
    **{f"shao_uplift_{y}_gbp_mwh": _m(
        f"Merit-order uplift in {y}, time-mean, modelled: this paper's estimate using the method of Shao and "
        "others (2022) (their coefficients, wind and solar), applied by the engine; not a figure published by "
        f"Shao and others; not the v4-s39 central uplift, which from May 2021 to Dec 2023 is re-estimated on "
        f"outturn (decision 0164, M9 B)", f"fleet[{y}].moe.shao_mean_gbp_mwh (time mean; read only where moe.rule is 'shao')",
        "£/MWh, cash", period=y, estimate_label="modelled (engine value), not sourced (E2)") for y in ("2021", "2023")},
}


def values(run: dict) -> dict:
    out = {k: None for k in DECLARED}
    m22 = run["fleet"].get("2022", {}).get("moe")
    if m22:
        if m22.get("rule") != "shao":
            raise ValueError(f"fleet[2022].moe.rule is {m22.get('rule')!r}, not 'shao': shao_uplift_2022 has no source")
        out["shao_uplift_2022_gbp_mwh"] = m22["shao_mean_gbp_mwh"]
    for y in ("2021", "2023"):
        m = run["fleet"].get(y, {}).get("moe")
        if m:
            if m.get("rule") != "shao":
                raise ValueError(f"fleet[{y}].moe.rule is {m.get('rule')!r}, not 'shao': shao_uplift_{y} has no source")
            out[f"shao_uplift_{y}_gbp_mwh"] = m["shao_mean_gbp_mwh"]
    wh = run["fleet"]["2024"].get("worked_hh")
    if not wh:
        return out
    for p in ("peak", "median"):
        h = wh[p]
        out.update({f"wh_{p}_halfhour": _sp_clock(h["date"], h["sp"]), f"wh_{p}_settlement_period": int(h["sp"]),
                    f"wh_{p}_residual_gw": h["residual_mw"] / 1000,
                    f"wh_{p}_uplift_gbp_mwh": h["scaled_step_gbp_mwh"],
                    f"annex.s4.merit_order_uplift_raw_{p}_gbp_mwh": h["raw_step_gbp_mwh"],
                    f"wh_{p}_rb_cost_gbp_mwh": h["rb_cost_gbp_mwh"], f"wh_{p}_marginal_plant": h["top_block"],
                    f"wh_{p}_market_index_price_gbp_mwh": h.get("market_index_price_gbp_mwh")})
        if h["top_block"] not in BLOCKS:
            raise ValueError(f"worked_hh.{p}.top_block {h['top_block']!r} is not a stack block name {BLOCKS}")
    return out
