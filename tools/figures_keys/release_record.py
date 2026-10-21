"""Ticket 32 (release-suite-run.md D4, B16): the release's own test-suite record in figures.json, read from
the run file's meta.test_suite, which `gascf.release.cut` writes from the same block as the releases.yaml row.
No paper text carries a typed test count. A run without the record (v4-s35 and earlier) gives None."""
from __future__ import annotations


def _m(label, field, units):
    return {"label": label, "basis": "measured", "provisional": False, "ticket": "32",
            "run_field": f"meta.test_suite.{field}", "units": units, "period": "release", "status": "SOURCED",
            "print": True}


DECLARED = {
    "test_suite_pass_count": dict(_m("Tests passed at the release commit", "passed", "tests"),
                                  mapped_name="release.test_suite.passed"),
    "test_suite_total": dict(_m("Tests collected at the release commit (passed + failed + skipped + errors)",
                                "passed+failed+skipped+errors", "tests")),
    "release.test_suite.commit": _m("Commit at which the release suite ran", "commit", "git commit"),
    "release.test_suite.started_utc": _m("Release suite start time (UTC)", "started_utc", "ISO 8601, UTC"),
}


def values(run: dict) -> dict:
    t = run["meta"].get("test_suite")
    if not t:
        return {k: None for k in DECLARED}
    return {"test_suite_pass_count": t["passed"],
            "test_suite_total": t["passed"] + t["failed"] + t["skipped"] + t["errors"],
            "release.test_suite.commit": t["commit"], "release.test_suite.started_utc": t["started_utc"]}
