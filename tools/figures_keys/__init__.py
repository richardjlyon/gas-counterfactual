"""Figures key modules (ticket 02). One module per item; each declares

    DECLARED = {placeholder_name: {"label", "basis", "provisional", "ticket", "run_field"}}
    def values(run: dict) -> {placeholder_name: value}

Keys are the Report writer's placeholder names (figures-keys.md; placeholder names win over rb.s4.*).
Add the module's name to MODULES. Starts empty."""
MODULES: list[str] = ["core", "ucl_period", "range", "eii_shift", "lost_value", "release_record", "fleet", "worked_hh", "closures", "ranking", "grid", "carbon_split", "moe_crisis", "household", "household_share", "ccl", "on_the_road", "volume", "pricing", "balancing_factors", "calibration", "pos_cm", "params", "case_b", "non_power_gas", "s36_reads", "recut_0122", "sens_0144", "sourced"]
