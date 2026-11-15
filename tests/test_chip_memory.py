"""Available Chip RAM on the viewer status bar.

The daemon already reports it as chip_free from AvailMem(MEMF_CHIP). The page
shows that reading as "graphics mem" and leaves the existing status total
alone. That total is Chip plus Fast, not Fast RAM by itself.
"""

import hashlib
import json
import shutil
import socket
import struct
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "src" / "native" / "amiga" / "daemon" / "amigentd.c"
WEB = ROOT / "src" / "amigent" / "web"
VIEWER_JS = WEB / "viewer.js"
APOLLO_BIN = ROOT / "src" / "amigent" / "amiga" / "bin" / "amigentd.apollo"


def extract_function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    i = source.index("{", start)
    depth = 0
    j = i
    while j < len(source):
        c = source[j]
        if c in ("'", '"', "`"):
            j += 1
            while j < len(source) and source[j] != c:
                j += 2 if source[j] == "\\" else 1
            j += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return source[start:j + 1]
        j += 1
    raise AssertionError(name)


def test_chip_free_is_available_chip_ram_on_both_builds():
    text = DAEMON.read_text(encoding="utf-8")
    body = text[text.index("static BOOL c_sysinfo"):text.index("static void t_bytes")]
    chip = 't_pair(&t, "chip_free", AvailMem(MEMF_CHIP));'
    fast = 't_pair(&t, "fast_free", AvailMem(MEMF_FAST));'
    assert chip in body
    assert fast in body
    assert body.index(chip) < body.index("#ifdef AMIGENT_APOLLO")
    line = next(ln.strip() for ln in body.splitlines() if '"chip_free"' in ln)
    assert line == chip
    assert "MEMF_FAST" not in line and "SAGA" not in line and "VREG" not in line
    # dec() writes a digit before dividing, so a real zero is still sent.
    dec = text[text.index("static void dec(char *p, ULONG v)"):text.index("static void t_pad")]
    assert "do" in dec and "d[n++] = '0' + v % 10;" in dec
    classic = (ROOT / "src" / "native" / "amiga" / "build-amigentd").read_text(encoding="latin-1")
    apollo = (ROOT / "src" / "native" / "amiga" / "Makefile.apollo").read_text(encoding="utf-8")
    assert "daemon/amigentd.c" in classic
    assert "$(DAEMON)/amigentd.c" in apollo
    assert "AvailMem" not in (ROOT / "src" / "native" / "amiga" / "platform" / "apollo" / "apollo.c").read_text(encoding="utf-8")


def test_sysinfo_parses_chip_and_fast_and_an_older_reply(monkeypatch):
    from amigent.channel import NEWEST_PROTOCOL, PACK_PROTOCOL, SYSINFO, AmigaChannel

    assert SYSINFO == 30 and NEWEST_PROTOCOL == PACK_PROTOCOL
    monkeypatch.setenv("AMIGENT_TLS", "off")

    def ask(body: str) -> dict:
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        raw = body.encode("iso-8859-1")
        packet = b"\0" + struct.pack(">I", len(raw)) + raw

        def serve():
            conn, _ = listener.accept()
            try:
                conn.sendall(b"AMGT" + struct.pack(">HH", 3, 0))
                rd = conn.makefile("rb")
                while len(head := rd.read(10)) == 10:
                    cmd = head[0]
                    if cmd == 20:
                        conn.sendall(b"\0")
                    elif cmd == 30:
                        conn.sendall(packet)
                    else:
                        conn.sendall(b"\1")
            finally:
                conn.close()

        threading.Thread(target=serve, daemon=True).start()
        port = listener.getsockname()[1]
        try:
            return AmigaChannel("127.0.0.1", port, timeout=5, key="").sysinfo()
        finally:
            listener.close()

    both = ask("chip_free=1887436\nfast_free=970981376\nnote=1\n")
    assert both["chip_free"] == "1887436"
    assert both["fast_free"] == "970981376"
    assert both["note"] == "1"
    older = ask("fast_free=970981376\nkickstart=47.115\n")
    assert "chip_free" not in older
    assert older["fast_free"] == "970981376"
    zero = ask("chip_free=0\nfast_free=4096\n")
    assert zero["chip_free"] == "0"
    assert zero["fast_free"] == "4096"


def _viewer():
    from amigent.viewer import Viewer

    viewer = Viewer.__new__(Viewer)
    viewer._system = {"os": "AmigaOS 3.2", "cpu": "68030"}
    return viewer


def _read(info: dict, volumes=None):
    viewer = _viewer()

    class Ctl:
        backend = type("B", (), {"protocol": 5})()

        def sysinfo(self):
            return info

        def volumes(self):
            return volumes if volumes is not None else [{"name": "RAM:", "free": 1, "capacity": 2}]

    viewer.ctl = Ctl()
    viewer._ctl = lambda fn: fn()
    return viewer.read_amiga()


def test_read_amiga_keeps_fast_ram_and_distinguishes_a_missing_chip_count():
    from amigent.viewer import counted_bytes, reported_bytes, status_free_bytes

    full = _read({
        "chip_free": "1887436", "chip_total": "2097152",
        "fast_free": "970981376", "fast_total": "1073741824",
        "bsdsocket": "4.307", "os": "AmigaOS",
    })
    assert full["chip_free"] == 1887436
    assert full["fast_free"] == 970981376
    assert full["chip_total"] == 2097152
    assert full["fast_total"] == 1073741824
    assert status_free_bytes(full["chip_free"], full["fast_free"]) == 1887436 + 970981376

    older = _read({"fast_free": "4096", "bsdsocket": "4.1"})
    assert older["chip_free"] is None
    assert older["fast_free"] == 4096
    assert older["chip_total"] == 0 and older["fast_total"] == 0
    assert status_free_bytes(older["chip_free"], older["fast_free"]) == 4096
    assert '"chip_free": null' in json.dumps({"chip_free": older["chip_free"]})

    zero = _read({"chip_free": "0", "fast_free": "0"})
    assert zero["chip_free"] == 0 and zero["fast_free"] == 0
    assert reported_bytes({"chip_free": ""}, "chip_free") is None
    assert reported_bytes({}, "chip_free") is None
    assert counted_bytes({}, "fast_free") == 0


def test_fleet_total_ignores_unreported_chip_and_keeps_fast(monkeypatch):
    from amigent.fleet import Fleet

    fleet = Fleet.__new__(Fleet)
    fleet.entries = [{
        "info": {"os": "ApolloOS", "cpu": "68080", "chip_free": None, "fast_free": 4096},
        "name": "V4", "online": True, "seen": 1,
        "viewer": type("V", (), {"clients": set()})(),
    }]
    monkeypatch.setattr("amigent.fleet.machines.address", lambda host: host)
    row = fleet.status()[0]
    assert row["free"] == 4096
    assert row["info"]["fast_free"] == 4096
    assert row["info"]["chip_free"] is None
    fleet.entries[0]["info"] = {"os": "AmigaOS", "cpu": "68030", "chip_free": 0, "fast_free": 4096}
    assert fleet.status()[0]["free"] == 4096


def test_memory_refresh_stays_on_the_existing_sysinfo_tick():
    text = (ROOT / "src" / "amigent" / "viewer.py").read_text(encoding="utf-8")
    stats = text.split("def _stats", 1)[1].split("def _media", 1)[0]
    assert "seconds % 30 == 0" in stats
    assert "read_amiga" in stats
    assert "chip_free" not in stats
    feed = (ROOT / "src" / "amigent" / "screenfeed.py").read_text(encoding="utf-8")
    assert "chip_free" not in feed and "AvailMem" not in feed
    script = VIEWER_JS.read_text(encoding="utf-8")
    binary = script.split("function onBinary", 1)[1].split("function ", 1)[0]
    assert "chip_free" not in binary and "st-graphics" not in binary and "memoryIndicators" not in binary


def test_status_bar_puts_graphics_mem_before_the_existing_total():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    status = html.split('id="status"', 1)[1].split("</footer>", 1)[0]
    assert status.index('id="st-graphics"') < status.index('id="st-mem"')
    graphics = status.split('id="st-graphics"', 1)[1].split(">", 1)[0]
    assert "hidden" in graphics
    english = json.loads((WEB / "locales" / "en.json").read_text(encoding="utf-8"))
    assert english["status_graphics"] == "graphics mem {size}"
    assert english["status_free"] == "{size} free"
    css = (WEB / "viewer.css").read_text(encoding="utf-8")
    assert "font: 11.5px/1" in css.split("#status {", 1)[1].split("}", 1)[0]
    assert "font" not in css.split("#st-graphics", 1)[1].split("}", 1)[0]


def test_graphics_mem_formatting_order_and_absence(tmp_path):
    source = VIEWER_JS.read_text(encoding="utf-8")
    program = "\n".join(extract_function(source, name) for name in (
        "bytes", "memoryIndicators", "applyMemoryStatus"))
    program += r"""
const label = {
  graphics: (size) => `graphics mem ${size}`,
  free: (size) => `${size} free`,
};
function watch(hidden, text) {
  const el = { hidden, textContent: text, writes: 0 };
  const orig = el;
  return new Proxy(el, {
    set(target, key, value) {
      if (key === "textContent" && target.textContent !== value) target.writes += 1;
      if (key === "hidden" && target.hidden !== value) target.writes += 1;
      target[key] = value;
      return true;
    },
  });
}
function paint(info, g, m) {
  return applyMemoryStatus(info, g, m, label);
}
const chip = 1887436;
const fast = 970981376;
const g = watch(true, "");
const m = watch(false, "");
paint({ chip_free: chip, fast_free: fast }, g, m);
const first = { graphics: g.textContent, free: m.textContent, hidden: g.hidden, writes: g.writes + m.writes };
paint({ chip_free: chip, fast_free: fast }, g, m);
const same = g.writes + m.writes;
paint({ chip_free: 524288, fast_free: fast }, g, m);
const replaced = { graphics: g.textContent, free: m.textContent, writes: g.writes + m.writes };
const g2 = watch(false, first.graphics);
const m2 = watch(false, first.free);
paint({ chip_free: chip, fast_free: fast + 1048576 }, g2, m2);
const gone = watch(false, first.graphics);
const goneMem = watch(false, first.free);
paint({ chip_free: null, fast_free: fast }, gone, goneMem);
const absent = watch(false, "stale");
const absentMem = watch(false, "stale");
paint({ fast_free: fast }, absent, absentMem);
const zero = watch(true, "");
const zeroMem = watch(false, "");
paint({ chip_free: 0, fast_free: fast }, zero, zeroMem);
const blank = watch(false, "stale");
const blankMem = watch(false, "");
paint({ chip_free: "", fast_free: fast }, blank, blankMem);
console.log(JSON.stringify({
  first, same, replaced,
  fastChangedGraphics: g2.textContent,
  fastChangedFree: m2.textContent,
  missing: { hidden: gone.hidden, graphics: gone.textContent, free: goneMem.textContent },
  absent: { hidden: absent.hidden, graphics: absent.textContent, free: absentMem.textContent },
  zero: { hidden: zero.hidden, graphics: zero.textContent, free: zeroMem.textContent },
  blank: { hidden: blank.hidden, graphics: blank.textContent, free: blankMem.textContent },
  units: {
    kb: bytes(1024),
    mb: bytes(99 * 1024 ** 2),
    mbRound: bytes(100 * 1024 ** 2),
    gb: bytes(1024 ** 3),
    chip: bytes(chip),
    total: bytes(chip + fast),
    fastOnly: bytes(fast),
    zero: bytes(0),
  },
}));
"""
    node = next((found for found in (
        shutil.which("node"), shutil.which("node.exe"),
        "/mnt/c/Program Files/nodejs/node.exe") if found and Path(found).exists()), None)
    assert node, "node is required for the viewer status checks"
    script = tmp_path / "status.js"
    if node.lower().endswith(".exe"):
        out = ROOT / "build"
        out.mkdir(parents=True, exist_ok=True)
        script = out / "status-memory-check.js"
    script.write_text(program, encoding="utf-8")
    target = str(script.resolve())
    if node.lower().endswith(".exe"):
        raw = script.resolve().as_posix()
        if raw.startswith("/mnt/") and len(raw) > 6 and raw[6] == "/":
            target = raw[5].upper() + ":" + raw[6:].replace("/", "\\")
    done = subprocess.run([node, target], check=True, capture_output=True, text=True)
    got = json.loads(done.stdout)
    units = got["units"]
    assert units["kb"] == "1 KB"
    assert units["mb"] == "99.0 MB" and units["mbRound"] == "100 MB"
    assert units["gb"] == "1.0 GB" and units["zero"] == "0 KB"
    assert units["chip"] == "1.8 MB" and units["fastOnly"] == "926 MB"
    assert units["total"] != units["fastOnly"]
    assert got["first"]["graphics"] == "graphics mem 1.8 MB"
    assert got["first"]["free"] == units["total"] + " free"
    assert got["first"]["free"] != units["fastOnly"] + " free"
    assert got["first"]["hidden"] is False
    assert got["same"] == got["first"]["writes"]
    assert got["replaced"]["graphics"] == "graphics mem 512 KB"
    assert got["replaced"]["free"] != got["first"]["free"]
    assert got["fastChangedGraphics"] == got["first"]["graphics"]
    assert got["fastChangedFree"] != got["first"]["free"]
    fast_free = units["fastOnly"] + " free"
    assert got["missing"] == {"hidden": True, "graphics": "", "free": fast_free}
    assert got["absent"] == {"hidden": True, "graphics": "", "free": fast_free}
    assert got["zero"]["hidden"] is False
    assert got["zero"]["graphics"] == "graphics mem 0 KB"
    assert got["zero"]["free"] == fast_free
    assert got["blank"] == {"hidden": True, "graphics": "", "free": fast_free}


def test_packaged_apollo_executable_is_the_secured_one():
    data = APOLLO_BIN.read_bytes()
    assert len(data) == 108112
    assert hashlib.sha256(data).hexdigest() == "158435c2fa757febe6a0c09403ad3983e34f520c78c2b328d82f2b5b712d14d6"


def test_viewer_assets_are_package_data():
    package = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'amigent = ["web/*", "web/locales/*", "macos/*", "amiga/*", "amiga/bin/*"]' in package
    for name in ("index.html", "viewer.js", "viewer.css", "locales/en.json"):
        assert (WEB / name).is_file()
