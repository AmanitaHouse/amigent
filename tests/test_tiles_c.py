"""amigentd's tile helpers (RGB332, PackBits, colour index), built for the PC
with gcc, against the PC's decoder in planar.py."""

import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from amigent.planar import Chunky, unpackbits

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "amiga" / "amigentd.c"

PRELUDE = """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
typedef int32_t LONG;
typedef uint32_t ULONG;
typedef uint8_t UBYTE;
"""
PARTS = ["to332", "to332_at", "islot", "tables_init", "rgb_to_332", "packbits",
         "idx_row1", "idx_row2", "idx_row4", "IDX_PIXEL", "idx_colours", "index_tile"]


def cut(code: str, name: str) -> str:
    """A static variable, a #define or a whole static function of amigentd.c."""
    m = re.search(r"^#define " + name + r"\b(?:.*\\\n)*.*$", code, re.M)
    if m:
        return m.group(0)
    m = re.search(r"^static [^\n(]*\b" + name + r"\b[^\n(]*;.*$", code, re.M)
    if m:
        return m.group(0)
    m = re.search(r"^static [^\n;]*\b" + name + r"\(", code, re.M)
    assert m, name
    at, depth = code.index("{", m.start()), 0
    for end in range(at, len(code)):
        depth += {"{": 1, "}": -1}.get(code[end], 0)
        if not depth:
            return code[m.start():end + 1]
    raise AssertionError(name)


@pytest.fixture(scope="module")
def tiles(tmp_path_factory):
    if not shutil.which("gcc"):
        pytest.skip("no gcc")
    code = SOURCE.read_text(encoding="latin-1")
    folder = tmp_path_factory.mktemp("tiles")
    src = folder / "tiles.c"
    src.write_text(PRELUDE + "\n\n".join(cut(code, name) for name in PARTS) + "\n" +
                   (ROOT / "tests/c/tiles_main.c").read_text(), encoding="latin-1")
    exe = folder / "tiles"
    done = subprocess.run(["gcc", "-O1", "-w", "-o", str(exe), str(src)], capture_output=True, text=True)
    if done.returncode:
        pytest.fail(done.stderr[-3000:])
    return exe


def run(exe, *args, data: bytes) -> bytes:
    done = subprocess.run([str(exe), *args], input=data, capture_output=True)
    assert done.returncode == 0, (args, done.returncode)
    return done.stdout


def rows_of(rnd, w, h, colours, run):
    """w*h pixels of the given colours, changing about every run pixels."""
    out, c = bytearray(), colours[0]
    for _ in range(w * h):
        if rnd.randrange(run) == 0:
            c = rnd.choice(colours)
        out.append(c)
    return bytes(out)


def test_rgb332_matches_the_formula(tiles):
    rgb = bytes(range(256)) * 3 + bytes(random.Random(1).getrandbits(8) for _ in range(30000))
    rgb = rgb[:len(rgb) // 3 * 3]
    want = bytes((r >> 5) | (g >> 5 << 3) | (b & 0xC0) for r, g, b in zip(rgb[0::3], rgb[1::3], rgb[2::3]))
    assert run(tiles, "conv", data=rgb) == want


def test_packbits_unpacks_and_stays_in_its_bounds(tiles):
    rnd = random.Random(7)
    samples = [b"", b"a", b"ab", b"aaa", b"abb", b"\0" * 4096, bytes(rnd.getrandbits(8) for _ in range(4096)),
               b"\0" * 129 + b"xy" + b"\1" * 3, bytes(range(256)) * 16]
    for _ in range(300):
        samples.append(rows_of(rnd, rnd.randrange(1, 200), rnd.randrange(1, 30), [0, 1, 2, 0xFF], rnd.choice([1, 2, 3, 8, 200])))
    for data in samples:
        packed = run(tiles, "pack", data=data)
        assert unpackbits(packed, len(data)) == data
        # no shorter than two bytes a 128, no longer than one in 128 over: amigentd's buffers count on it
        assert 2 * -(-len(data) // 128) <= len(packed) <= len(data) + -(-len(data) // 128)


@pytest.mark.parametrize("colours", [1, 2, 3, 4, 5, 16])
def test_indexed_tiles_decode_to_their_pixels(tiles, colours):
    rnd = random.Random(colours)
    for w, h in [(64, 64), (1, 1), (7, 3), (41, 61), (64, 17), (3, 64)]:
        palette = rnd.sample(range(256), colours)
        pixels = rows_of(rnd, w, h, palette, rnd.choice([1, 3, 40]))
        data = run(tiles, "index", str(w), str(h), data=pixels)
        k = data[0]
        assert k == len(set(pixels))
        assert list(data[1:1 + k]) == list(dict.fromkeys(pixels))  # in the order they come
        assert Chunky(w, h)._indexed(w, h, 0, 0, data) == pixels


def test_seventeen_colours_are_not_indexed(tiles):
    pixels = bytes(range(17)) * 200
    assert run(tiles, "index", "40", "85", data=pixels) == b""
