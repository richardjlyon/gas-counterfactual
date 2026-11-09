#!/usr/bin/env python3
"""Download the input files this repository cannot republish, from their publishers, and check each one's sha256.

    python3 fetch_data.py            # fetch every file with a public download address
    python3 fetch_data.py --check    # only check files already in place

The list is data/FETCH.tsv: path, sha256, url (or "-" where the publisher gives no stable download address), and,
for a text copy the release made from a publisher's document, a fourth column naming how to remake it:
"pdftotext -layout <url or path>". That needs pdftotext (poppler-utils); the release's text copies were made with
poppler 25.03.0, and another version may lay the text out differently. Some addresses are Internet Archive copies
(web.archive.org/web/<time>id_/...), where the publisher has since changed or removed the file.
A file whose sha256 differs from the release's is kept as <path>.fetched and reported: the publisher has changed it
since the release was cut, and the rerun will not match until the release's own copy is obtained.
Python 3 standard library only. Exit 0 only if every listed file is in place with the release's sha256.
"""
import hashlib
import subprocess
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
            cols = ln.split("\t")
            path, digest, url = cols[:3]
            made_from = cols[3] if len(cols) > 3 else ""
            yield path, digest, url, made_from


def fetch(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def make(made_from: str, dest: Path) -> None:
    """Remake a text copy the release made from a publisher's document, e.g. "pdftotext -layout <pdf>"."""
    *cmd, src = made_from.split()
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = ROOT / src
    if "://" in src:  # the publisher's document, downloaded first and not kept
        source = dest.with_name(dest.name + ".source")
        fetch(src, source)
    try:
        out = subprocess.run([*cmd, str(source), "-"], capture_output=True, check=True).stdout
    finally:
        if "://" in src:
            source.unlink(missing_ok=True)
    dest.write_bytes(out)


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    ok = changed = failed = manual = 0
    for path, digest, url, made_from in rows():
        dest = ROOT / path
        if dest.is_file() and sha256(dest) == digest:
            ok += 1
            print(f"OK       {path}")
            continue
        if not check_only and made_from:
            src = made_from.split()[-1]
            if "://" not in src and not (ROOT / src).is_file():
                manual += 1
                print(f"MISSING  {path}  (made from {src}, not yet in place)")
                continue
            url = made_from
        if check_only or url == "-":
            manual += 1
            print(f"MISSING  {path}  (no public download address; see data/raw/SOURCES.md)" if url == "-" else f"MISSING  {path}")
            continue
        tmp = dest.with_name(dest.name + ".fetched")
        try:
            make(made_from, tmp) if made_from else fetch(url, tmp)
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
