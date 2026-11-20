"""Fork safeguards that stay on the upstream 1.4.0 tree."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_TAG = "4fea38f602f84ddad2d5215fbc9d2742605d892c"
UPSTREAM_MAIN = "f6aab1d4953c1d83be2f71e73faef6fa5dc236ff"


def test_identity_guard_trusts_verified_upstream_main_only():
    baseline = (ROOT / ".githooks" / "upstream-baseline").read_text(encoding="utf-8").splitlines()
    assert baseline == [
        "refs/tags/upstream-v1.4.0",
        "3c7cec6ac6c9bacf5bc2c4d4dc70606289c2f971",
        UPSTREAM_TAG,
        UPSTREAM_MAIN,
    ]
    lib = (ROOT / ".githooks" / "lib.sh").read_text(encoding="utf-8")
    push = (ROOT / ".githooks" / "pre-push").read_text(encoding="utf-8")
    assert UPSTREAM_MAIN in lib
    assert "merge-base --is-ancestor" in lib
    assert "--not \"$verified_upstream\" \"$verified_upstream_main\"" in push


def test_russian_catalog_has_one_string_per_key():
    text = (ROOT / "src" / "amigent" / "web" / "locales" / "ru.json").read_text(encoding="utf-8")
    keys = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('"') and '":' in stripped:
            keys.append(stripped.split('":', 1)[0] + '"')
    assert len(keys) == len(set(keys))
    catalog = json.loads(text)
    english = json.loads((ROOT / "src" / "amigent" / "web" / "locales" / "en.json").read_text(encoding="utf-8"))
    for key in ("mem_graphics", "mem_fast_only", "status_chip", "status_graphics", "status_fast"):
        assert key in catalog
        assert key in english


def test_sdist_includes_the_amiga_sources_and_the_protocol6_apollo_daemon():
    lines = (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    assert "graft amiga" in lines
    assert "graft src/native" not in lines
    assert "exclude src/amigent/amiga/bin/amigentd.080" in lines
    assert (ROOT / "amiga" / "amigentd.c").is_file()
    binary = ROOT / "src" / "amigent" / "amiga" / "bin"
    assert (binary / "amigentd.apollo").is_file()
    assert (binary / "amigent-apollo-probe").is_file()
    assert not (binary / "amigent-monitor.apollo").exists()
