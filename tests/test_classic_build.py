"""The classic Amiga build names an output directory. It is not compiled here."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "native" / "amiga" / "build-amigentd"


def defaults() -> dict[str, str]:
    found = {}
    for line in SCRIPT.read_text(encoding="latin-1").splitlines():
        if line.startswith(".DEF "):
            key, value = line[5:].split(" ", 1)
            found[key] = value
    return found


def test_classic_build_writes_under_build_classic():
    text = SCRIPT.read_text(encoding="latin-1")
    values = defaults()
    assert values["SOURCE"] == "daemon/amigentd.c"
    assert values["TO"] == "///build/classic/amigentd"
    assert values["OBJ"] == "///build/classic/amigentd.o"
    assert "MakeDir ///build/classic" in text
    compile_line = next(line for line in text.splitlines() if line.startswith("VBCC:bin/vc") and " -c " in line)
    link_line = next(line for line in text.splitlines() if line.startswith("VBCC:bin/vc") and " -c " not in line)
    assert "-o <OBJ> <SOURCE>" in compile_line
    assert "-o <TO> <OBJ>" in link_line
    assert "-lamiga" in link_line
    assert not any(line == ".DEF TO amigentd" for line in text.splitlines())
    assert not any(line == ".DEF SOURCE amigentd.c" for line in text.splitlines())
