"""Where amigentd spends its time per screen picture, measured against a real Amiga.

    AMIGENT_KEY=... python3 scripts/bench_amiga.py --host 192.168.1.20
    python3 scripts/bench_amiga.py --host 127.0.0.1 --port 6811 --ctl-port 6810 --seconds 8
    python3 scripts/bench_amiga.py --host ... --no-change      # skip the changing screen
    python3 scripts/bench_amiga.py --host ... --json out.json  # keep the numbers

Asks for pictures the way the viewer does (FRAME with the planar/chunky bits,
deflate off, fast or best) and times them from the PC, then derives the stages:

    ping        one command there and back: the floor of every frame
    still       nothing changed, the Amiga only compares (on a graphics card it
                answers from what its background reader has already read)
    still+read  the same right after a MOVE of the pointer onto itself, which
                makes amigentd read every tile fresh: read + compare
    full        every tile, read fresh, packed and sent (arg 1)
    stream      frames back to back for --seconds while a Shell lists a
                directory in a loop: frames per second, bytes and ms per frame
    cpu         amiga_cpu's sampler while streaming: amigentd's share

read = still+read - ping, pack+send = full - still+read, deflate = full(fast or
best) - full(off). Over a slow link the send dominates; on localhost to an
emulator it shows what the Amiga side costs. An emulator's CPU is not a real
one: compare the stages with each other, not the milliseconds with hardware.

Harmless: it only reads the screen, moves the pointer onto the spot where it
already is, and for the changing screen writes two small scripts to RAM:, opens
one Shell window that lists SYS:C in a loop, and stops and deletes it all at
the end. Needs amigentd 1.4.0 for the CPU sampler (skipped on older ones).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from amigent.amigentd import CMD_FRAME, CMD_MOVE, CMD_PING, FRAME_DEFLATE, FRAME_PLANAR  # noqa: E402

LEVELS = {"off": 0, "fast": FRAME_DEFLATE[1], "best": FRAME_DEFLATE[2]}
STOP = "RAM:amigent-bench.stop"
LOOP = "RAM:amigent-bench.loop"
START = "RAM:amigent-bench.start"


def med(values):
    return statistics.median(values) if values else 0.0


class Bench:
    def __init__(self, args):
        from amigent.amigentd import Amigentd
        from amigent.channel import Commands

        self.args = args
        self.screen = Amigentd(args.host, args.port, timeout=60, key=args.key)
        self.screen.connect()
        self.ctl = Commands(args.host, args.ctl_port, args.port, timeout=60)
        self.ctl.connect()
        self.results: dict = {}
        self._daemon: dict | None = None

    # ---- one request, timed from the PC --------------------------------

    def frame(self, arg: int) -> dict:
        """One FRAME of the whole screen: ms to the first byte and to the last, bytes, tiles."""
        s = self.screen
        if arg & 1:
            s.drop_picture()
        tiles: list = []
        t0 = time.perf_counter()
        s._send(CMD_FRAME, arg, 0, 0, s.width, s.height)
        kind = s._exact(1)[0] if s.planar else 0
        t1 = time.perf_counter()
        count, size, _ = s._drive(s._format_reply(kind, tiles.append))
        t2 = time.perf_counter()
        s._take_tiles(tiles)
        return {"ms": (t2 - t0) * 1000, "first_ms": (t1 - t0) * 1000, "bytes": size + 1, "tiles": count}

    def ping(self) -> float:
        s = self.screen
        t0 = time.perf_counter()
        s._send(CMD_PING)
        s._exact(1)
        return (time.perf_counter() - t0) * 1000

    def touch(self) -> None:
        """A MOVE onto the pointer's own spot: amigentd then reads every tile fresh."""
        s = self.screen
        at = s.pointer() or (s.width // 2, s.height // 2)
        s._send(CMD_MOVE, 0, *at)
        s._exact(1)

    def base_arg(self, level: str) -> int:
        arg = FRAME_PLANAR if self.screen.planar else 0
        if self.screen.protocol >= 5:
            arg |= LEVELS[level]
        elif level != "off":
            return -1
        return arg

    # ---- the stages ----------------------------------------------------

    def still(self, n: int) -> None:
        arg = self.base_arg("off")
        self.frame(arg | 1)  # a picture to compare against
        pings = [self.ping() for _ in range(n)]
        quiet = [self.frame(arg) for _ in range(n)]
        fresh = []
        for _ in range(n):
            self.touch()
            fresh.append(self.frame(arg))
        self.results["ping_ms"] = med(pings)
        self.results["still"] = summary(quiet)
        self.results["still_read"] = summary(fresh)

    def full(self, n: int) -> None:
        for level in LEVELS:
            arg = self.base_arg(level)
            if arg < 0:
                continue
            self.results[f"full_{level}"] = summary([self.frame(arg | 1) for _ in range(n)])

    def stream(self, level: str, seconds: float, sample_cpu: bool, gap: float = 0.0) -> dict:
        arg = self.base_arg(level)
        if arg < 0:
            return {}
        self.frame(arg | 1)
        cpu: dict = {}
        sampler = None
        if sample_cpu:
            sampler = threading.Thread(target=self._cpu, args=(max(1, int(seconds) - 1), cpu), daemon=True)
            sampler.start()
        frames, end = [], time.perf_counter() + seconds
        start = time.perf_counter()
        while time.perf_counter() < end:
            frames.append(self.frame(arg))
            if gap:
                time.sleep(gap)
        took = time.perf_counter() - start
        if sampler:
            sampler.join(seconds + 30)
        row = summary(frames)
        busy = [f for f in frames if f["tiles"]]
        row["ms_mean"] = sum(f["ms"] for f in frames) / max(1, len(frames))
        row["bytes_mean"] = sum(f["bytes"] for f in frames) / max(1, len(frames))
        row["ms_changed"] = med([f["ms"] for f in busy])
        row["bytes_changed"] = med([f["bytes"] for f in busy])
        row["tiles_changed"] = med([f["tiles"] for f in busy])
        row["fps"] = len(frames) / took
        row["kb_s"] = sum(f["bytes"] for f in frames) / took / 1000
        row["changed"] = sum(1 for f in frames if f["tiles"]) / max(1, len(frames))
        if cpu:
            row["cpu"] = cpu
        return row

    def daemon_tasks(self) -> dict:
        """address -> label of amigentd's own tasks (its process may be a "Background CLI")."""
        from amigent import memory

        if self._daemon is None:
            try:
                tasks = memory.parse_tasks(self.ctl.tasks())
            except Exception:
                tasks = []
            self._daemon = {t.address: t.label for t in tasks
                            if "amigent" in f"{t.name} {t.command}".lower() and "monitor" not in t.label.lower()}
        return self._daemon

    def _cpu(self, seconds: int, into: dict) -> None:
        daemon = self.daemon_tasks()
        try:
            lines = self.ctl.cpu(seconds, 10)
        except Exception as e:  # an older amigentd: no sampler
            into["error"] = str(e)
            return
        head = next((ln.split("\t") for ln in lines if ln.startswith("N\t")), None)
        if not head:
            return
        samples, idle = int(head[1]), int(head[3])
        tasks: dict = {}
        mine = 0
        for ln in lines:
            p = ln.split("\t")
            if p[0] == "C" and len(p) >= 4:
                at = int(p[1], 16)
                name = "amigentd" if at in daemon else p[3]
                tasks[name] = tasks.get(name, 0) + int(p[2])
                mine += int(p[2]) if at in daemon else 0
        pct = lambda n: round(100.0 * n / samples, 1) if samples else 0.0  # noqa: E731
        into["idle"] = pct(idle)
        into["amigentd"] = pct(mine)
        into["top"] = sorted(((pct(n), name) for name, n in tasks.items()), reverse=True)[:5]

    # ---- something that redraws ----------------------------------------

    def start_change(self) -> None:
        loop = (f"Lab top\nList SYS:C\nIf EXISTS {STOP}\n  Skip done\nEndIf\nSkip top BACK\n"
                f"Lab done\nDelete {STOP} QUIET\nEndCLI >NIL:\n")
        self.ctl.write_file(LOOP, loop.encode())
        self.ctl.write_file(START, f"Execute {LOOP}\nEndCLI\n".encode())
        self.ctl.exec(f'Run >NIL: NewShell "CON:0/40/{min(self.screen.width, 640)}/180/amigent-bench" FROM {START}')
        time.sleep(3)

    def stop_change(self) -> None:
        """The loop deletes the stop file when it sees it and ends; wait for that."""
        try:
            self.ctl.write_file(STOP, b"stop\n")
            end = time.monotonic() + 180
            while time.monotonic() < end:
                try:
                    self.ctl.stat(STOP)
                except Exception:
                    break  # gone: the loop has ended
                time.sleep(1)
            else:
                print(f"the Shell loop did not end; delete {STOP} by hand when it has", file=sys.stderr)
                return
            time.sleep(2)  # EndCLI closes its window
        finally:
            for path in (STOP, LOOP, START):
                try:
                    self.ctl.delete(path)
                except Exception:
                    pass


def summary(frames: list[dict]) -> dict:
    return {"n": len(frames), "ms": med([f["ms"] for f in frames]),
            "first_ms": med([f["first_ms"] for f in frames]),
            "bytes": med([f["bytes"] for f in frames]), "tiles": med([f["tiles"] for f in frames])}


def report(r: dict) -> str:
    out = [f"{r['machine']}", f"{'stage':14} {'ms':>9} {'first':>9} {'bytes':>9} {'tiles':>6}"]
    out.append(f"{'ping':14} {r['ping_ms']:9.1f}")
    for key in ("still", "still_read", "full_off", "full_fast", "full_best"):
        if key in r:
            v = r[key]
            out.append(f"{key:14} {v['ms']:9.1f} {v['first_ms']:9.1f} {v['bytes']:9.0f} {v['tiles']:6.0f}")
    p, sr, fo = r["ping_ms"], r["still_read"]["ms"], r["full_off"]["ms"]
    out.append("")
    out.append(f"derived: read+compare {sr - p:.1f} ms, compare only {r['still']['ms'] - p:.1f} ms, "
               f"pack(PackBits)+send {fo - sr:.1f} ms")
    for level in ("fast", "best"):
        if f"full_{level}" in r:
            v = r[f"full_{level}"]
            out.append(f"         deflate {level}: +{v['ms'] - fo:.1f} ms, {v['bytes'] / max(1, r['full_off']['bytes']):.0%}"
                       " of the bytes")
    for key, v in r.items():
        if key.startswith("stream_") and v:
            line = (f"{key:18} {v['fps']:6.2f} fps {v['ms_mean']:7.1f} ms/frame {v['bytes_mean']:7.0f} B/frame"
                    f" {v['kb_s']:6.1f} KB/s; {v['changed']:.0%} changed: median {v['ms_changed']:.1f} ms,"
                    f" {v['bytes_changed']:.0f} B, {v['tiles_changed']:.0f} tiles")
            out.append(line)
            if "cpu" in v and "idle" in v["cpu"]:
                c = v["cpu"]
                out.append(f"{'':18} cpu: amigentd {c['amigentd']} %, idle {c['idle']} %, top "
                           + ", ".join(f"{name} {pct}" for pct, name in c["top"]))
            elif "cpu" in v:
                out.append(f"{'':18} cpu: {v['cpu'].get('error')}")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default=os.environ.get("AMIGENT_HOST", ""))
    ap.add_argument("--port", type=int, default=int(os.environ.get("AMIGENT_SCREEN_PORT", 6801)))
    ap.add_argument("--ctl-port", type=int, default=0, help="old amigactld port; amigentd's own channel by default")
    ap.add_argument("--key", default=os.environ.get("AMIGENT_KEY"))
    ap.add_argument("-n", type=int, default=5, help="repeats of each single frame")
    ap.add_argument("--seconds", type=float, default=8.0, help="length of each stream")
    ap.add_argument("--gap", type=float, default=0.25,
                    help="seconds between frames on the changing screen, so the Shell loop gets the CPU too")
    ap.add_argument("--no-change", action="store_true", help="no Shell loop, still streams only")
    ap.add_argument("--json", help="write the numbers here as well")
    args = ap.parse_args()
    if not args.host:
        ap.error("--host or AMIGENT_HOST")
    args.ctl_port = args.ctl_port or args.port - 1
    if args.key:
        os.environ["AMIGENT_KEY"] = args.key  # the command channel reads it from there

    b = Bench(args)
    si = b.ctl.sysinfo()
    s = b.screen
    front = next((x for x in s.screens() if x["front"]), {})
    r = b.results
    r["machine"] = (f"{si.get('cpu')} Kickstart {si.get('kickstart')}, front screen {s.width}x{s.height}"
                    f" depth {front.get('depth')} {'RTG' if front.get('rtg') else 'chipset'},"
                    f" protocol {s.protocol}, {'planar' if s.planar and not front.get('rtg') else 'chunky'};"
                    f" deflate KB/s fast {si.get('deflate_fast')} best {si.get('deflate_best')}")
    r["sysinfo"] = {k: v for k, v in si.items() if k not in ("ports", "tasks")}
    print("measuring:", r["machine"], file=sys.stderr, flush=True)
    b.still(args.n)
    b.full(args.n)
    sampler = si.get("probe") == "1"
    r["stream_still_off"] = b.stream("off", args.seconds, sampler)
    if not args.no_change:
        b.start_change()
        try:
            for level in LEVELS:
                r[f"stream_change_{level}"] = b.stream(level, args.seconds, sampler, args.gap)
        finally:
            b.stop_change()
    print(report(r))
    if args.json:
        Path(args.json).write_text(json.dumps(r, indent=1))
    b.screen.close()


if __name__ == "__main__":
    main()
