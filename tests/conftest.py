"""s23b: the central case reads the fossil-Britain closure register (spec §15.3 item 2). Engine
tests run against the small labelled fixture (`tests/fixtures/s23b_fossil_closures_fixture.yaml`)
so they do not depend on the register's contents (strand s23a tests the register itself, in
`tests/test_fossil_closures.py`). Set GASCF_FOSSIL_CLOSURES to test against another register."""
import os
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures/s23b_fossil_closures_fixture.yaml"
os.environ.setdefault("GASCF_FOSSIL_CLOSURES", str(FIXTURE))
