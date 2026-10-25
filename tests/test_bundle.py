"""Release bundle in the layout the fact-checker's review-report script reads (research-director, 19 Oct 2026; checked
against the reviewer's review-report script): <releases>/<model>/<version>/ holding source/ (git
archive of the release ref), uv-cache/, figures.json, the run file, RERUN.md, an executable rerun.sh, and
SHA256SUMS (every file but itself, paths relative to the bundle, made last; review-report runs `sha256sum --quiet -c`
in the bundle). Light: a throwaway git repo."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from gascf import bundle as BU


def _git(root, *a):
    return subprocess.run(["git", *a], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """Code committed first (the cut commit), then the release files on top with the row naming the cut commit, as
    `gascf.release.cut` and the release-files commit do (0122 item 5)."""
    root = tmp_path / "eng"
    (root / "out/v4").mkdir(parents=True)
    (root / "out/figures").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src/x.py").write_text("x = 1\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c0 code")
    cut = _git(root, "rev-parse", "HEAD")
    (root / "out/v4/2026-10-19-s99.json").write_text('{"meta": {}}')
    (root / "out/figures/v4-s99.json").write_text('{"keys": {}}')
    (root / "releases.yaml").write_text(json.dumps({"releases": [
        {"version": "v4-s99", "commit": cut, "run_file": "out/v4/2026-10-19-s99.json",
         "figures_file": "out/figures/v4-s99.json"}]}))
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c1 release files")
    cache = tmp_path / "cache"
    (cache / "wheels").mkdir(parents=True)
    (cache / "wheels/a.whl").write_bytes(b"wheel")
    return root, cache


def test_rerun_md_names_the_cut_commit_and_the_source_commit_and_what_lies_between(repo, tmp_path):
    root, cache = repo
    cut = json.loads((root / "releases.yaml").read_text())["releases"][0]["commit"]
    head = _git(root, "rev-parse", "HEAD")
    out = BU.build("v4-s99", "HEAD", releases_root=tmp_path / "releases", uv_cache=cache, root=root)
    md = (out / "RERUN.md").read_text()
    assert f"cut at commit {cut}" in md and f"source/ is commit {head}" in md
    assert "releases.yaml" in md and "out/figures/v4-s99.json" in md


def test_refuses_a_source_commit_that_changes_code_after_the_cut(repo, tmp_path):
    root, cache = repo
    (root / "src/x.py").write_text("x = 2\n")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "code after the cut")
    with pytest.raises(SystemExit, match="src/x.py"):
        BU.build("v4-s99", "HEAD", releases_root=tmp_path / "releases", uv_cache=cache, root=root)


def test_refuses_a_source_commit_that_does_not_contain_the_cut(repo, tmp_path):
    root, cache = repo
    reg = json.loads((root / "releases.yaml").read_text())
    reg["releases"][0]["commit"] = "0" * 40
    (root / "releases.yaml").write_text(json.dumps(reg))
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "row names another commit")
    with pytest.raises(SystemExit, match="cut commit"):
        BU.build("v4-s99", "HEAD", releases_root=tmp_path / "releases", uv_cache=cache, root=root)


def test_bundle_carries_the_gates_suite_output(repo, tmp_path):
    """Card [internal ticket] (sweep 5.1): the suite output files the row pins (row.suite_output) go into the bundle under
    tests/, and committing them after the cut is a release-files-only change."""
    root, cache = repo
    reg = json.loads((root / "releases.yaml").read_text())
    (root / "out/tests").mkdir()
    (root / "out/tests/v4-s99-suite.log").write_text("3 passed in 1.0s\n")
    (root / "out/tests/v4-s99-suite-junit.xml").write_text("<testsuites/>")
    import hashlib
    reg["releases"][0]["suite_output"] = {
        f: hashlib.sha256((root / f).read_bytes()).hexdigest()
        for f in ("out/tests/v4-s99-suite.log", "out/tests/v4-s99-suite-junit.xml")}
    (root / "releases.yaml").write_text(json.dumps(reg))
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c2 suite output")
    out = BU.build("v4-s99", "HEAD", releases_root=tmp_path / "releases", uv_cache=cache, root=root)
    assert (out / "tests/v4-s99-suite.log").read_text() == "3 passed in 1.0s\n"
    assert (out / "tests/v4-s99-suite-junit.xml").is_file()
    assert BU.check_layout(out) == []


def test_bundle_layout_matches_review_report(repo, tmp_path):
    root, cache = repo
    out = BU.build("v4-s99", "HEAD", releases_root=tmp_path / "releases", uv_cache=cache, root=root)
    assert out == tmp_path / "releases/gas-counterfactual/v4-s99"
    for p in ("source/src/x.py", "source/releases.yaml", "uv-cache/wheels/a.whl", "figures.json",
              "2026-10-19-s99.json", "RERUN.md", "rerun.sh", "SHA256SUMS"):
        assert (out / p).is_file(), p
    assert os.access(out / "rerun.sh", os.X_OK)
    assert not (out / "source/.git").exists()
    sh = (out / "rerun.sh").read_text()
    assert "python -m gascf.rerun v4-s99" in sh and "--bundle \"$BUNDLE\"" in sh and "uv sync --frozen --offline" in sh
    assert "RERUN PASS v4-s99" in (out / "RERUN.md").read_text()
    sums = (out / "SHA256SUMS").read_text().splitlines()
    names = {line.split("  ", 1)[1] for line in sums}
    every = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS"}
    assert names == {f"./{n}" for n in every}
    subprocess.run(["sha256sum", "--quiet", "-c", "SHA256SUMS"], cwd=out, check=True)
    assert BU.check_layout(out) == []


def test_check_layout_names_each_fault(repo, tmp_path):
    root, cache = repo
    out = BU.build("v4-s99", "HEAD", releases_root=tmp_path / "releases", uv_cache=cache, root=root)
    (out / "rerun.sh").chmod(0o644)
    (out / "figures.json").write_text("{}")
    faults = BU.check_layout(out)
    assert "rerun.sh is not executable" in faults
    assert any(f.startswith("SHA256SUMS does not verify") for f in faults)


def test_refuses_an_existing_bundle(repo, tmp_path):
    root, cache = repo
    BU.build("v4-s99", "HEAD", releases_root=tmp_path / "releases", uv_cache=cache, root=root)
    with pytest.raises(SystemExit, match="exists"):
        BU.build("v4-s99", "HEAD", releases_root=tmp_path / "releases", uv_cache=cache, root=root)
