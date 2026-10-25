"""Reader for the shared cost register (decision 0168: one number, one source).

One file, the same bytes in every model that reads it (the engine, the Subsidy Clock, the Report No. 2 data
build). Standard library only. A model pins the register it reads by sha256; load() refuses any other bytes.

    reg = load(path, sha256)
    reg.series("RO")                  # {year: GBP m cash}: the line's one yearly series
    reg.line("RO", "clock_live")      # the series plus every input adjustment that applies to that product
    reg.row("RO", 2020)               # the series row (basis, source, source_id, ...)

Products: 'clock_live' (the Subsidy Clock as live), 'no2' (Report No. 2's data build), 'rb' (the engine behind
Reliable Britain), and 'rb_sensitivity_*' names for engine sensitivity rows. An input adjustment applies to the
products named in its applies_to column (';'-separated).

Version 2: rows are indexed once at load and every answer is memoised per register object, so a model may call
the reader in an inner loop. Answers are returned as fresh dicts, so a caller cannot change what the next caller
reads. The rows themselves are read-only: never edit reg.rows.
"""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path

READER_VERSION = 2


class RegisterError(ValueError):
    pass


@dataclass
class Register:
    path: Path
    sha256: str
    rows: list[dict] = field(repr=False)

    def __post_init__(self) -> None:
        self._index: dict[tuple[str, str], list[dict]] = {}
        for r in self.rows:
            self._index.setdefault((r["line_id"], r["row_type"]), []).append(r)
        self._memo: dict[tuple, object] = {}

    def _rows(self, line: str, row_type: str) -> list[dict]:
        return self._index.get((line, row_type), [])

    def lines(self) -> list[str]:
        return sorted({line for (line, rt) in self._index if rt == "series"})

    def _series(self, line: str, column: str) -> dict[int, float]:
        key = ("series", line, column)
        if key not in self._memo:
            rs = self._rows(line, "series") or self._rows(line, "memo")
            if not rs:
                raise RegisterError(f"register {self.sha256[:12]} has no line {line!r}")
            self._memo[key] = {int(r["year"]): float(r[column]) for r in rs if r[column] != ""}
        return self._memo[key]

    def series(self, line: str, column: str = "cash_gbp_m") -> dict[int, float]:
        return dict(self._series(line, column))

    def row(self, line: str, year: int) -> dict:
        key = ("rows", line)
        if key not in self._memo:
            self._memo[key] = {int(r["year"]): r for r in self._rows(line, "series") or self._rows(line, "memo")}
        try:
            return self._memo[key][year]
        except KeyError:
            raise RegisterError(f"register has no {line} row for {year}") from None

    def _adjustments(self, line: str, product: str) -> dict[str, dict[int, float]]:
        key = ("adj", line, product)
        if key not in self._memo:
            out: dict[str, dict[int, float]] = {}
            for r in self._rows(line, "input_adjustment"):
                if product in r["applies_to"].split(";"):
                    out.setdefault(r["item_id"], {})[int(r["year"])] = float(r["cash_gbp_m"])
            self._memo[key] = out
        return self._memo[key]

    def adjustments(self, line: str, product: str) -> dict[str, dict[int, float]]:
        return {k: dict(v) for k, v in self._adjustments(line, product).items()}

    def line(self, line: str, product: str) -> dict[int, float]:
        """The series plus every input adjustment applying to `product`, by the series' own year key."""
        key = ("line", line, product)
        if key not in self._memo:
            out = dict(self._series(line, "cash_gbp_m"))
            for item, vals in self._adjustments(line, product).items():
                for y, v in vals.items():
                    if y not in out:
                        raise RegisterError(f"{item}: {y} has no {line} series row")
                    out[y] += v
            self._memo[key] = out
        return dict(self._memo[key])


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load(path: Path | str, sha256: str) -> Register:
    p = Path(path)
    b = p.read_bytes()
    h = sha256_bytes(b)
    if h != sha256:
        raise RegisterError(f"{p}: sha256 {h} is not the pinned register {sha256}; re-pin on purpose, never "
                            f"edit the file")
    rows = list(csv.DictReader(io.StringIO(b.decode("utf-8"))))
    if not rows or "line_id" not in rows[0]:
        raise RegisterError(f"{p}: not a shared cost register")
    return Register(path=p, sha256=h, rows=rows)
