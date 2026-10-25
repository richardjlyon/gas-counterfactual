#!/usr/bin/env python3
"""Download the input files this repository cannot republish, from their publishers, and check each one's sha256.

    python3 fetch_data.py            # fetch every file with a public download address
    python3 fetch_data.py --check    # only check files already in place

The list is data/FETCH.tsv: path, sha256, url (or "-" where the publisher gives no stable download address).
A file whose sha256 differs from the release's is kept as <path>.fetched and reported: the publisher has changed it
since the release was cut, and the rerun will not match until the release's own copy is obtained.
Python 3 standard library only. Exit 0 only if every listed file is in place with the release's sha256.
"""
import hashlib
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (compatible; gas-counterfactual-fetch/1.0)"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rows():
    for ln in (ROOT / "data" / "FETCH.tsv").read_text(encoding="utf-8").splitlines():
        if ln.strip() and not ln.startswith("#"):
            path, digest, url = ln.split("\t")[:3]
            yield path, digest, url


def fetch(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    ok = changed = failed = manual = 0
    for path, digest, url in rows():
        dest = ROOT / path
        if dest.is_file() and sha256(dest) == digest:
            ok += 1
            print(f"OK       {path}")
            continue
        if check_only or url == "-":
            manual += 1
            print(f"MISSING  {path}  (no public download address; see data/raw/SOURCES.md)" if url == "-" else f"MISSING  {path}")
            continue
        tmp = dest.with_name(dest.name + ".fetched")
        try:
            fetch(url, tmp)
        except Exception as e:  # report and carry on with the rest
            failed += 1
            print(f"FAILED   {path}  {type(e).__name__}: {e}")
            continue
        got = sha256(tmp)
        if got == digest:
            tmp.replace(dest)
            ok += 1
            print(f"FETCHED  {path}")
        else:
            changed += 1
            print(f"CHANGED  {path}  sha256 {got}, release {digest}; kept as {tmp.name}")
        time.sleep(1)
    print(f"\n{ok} in place, {changed} changed at source, {failed} failed to download, {manual} without a download address")
    return 0 if changed == failed == manual == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
