"""What amigentd measures on the Amiga itself: who holds the layer locks, CPU load
per task, and how a window follows when it is dragged.

amigentd 1.4.0 with "probe" in SYSINFO answers LOCKS, CPU and DRAG; this module
turns their lines into text for the agent.
"""

from __future__ import annotations

from statistics import median


def locks(lines: list[str]) -> str:
    """K lines -> one row per lock, held and waited-for ones marked."""
    out, busy = [], 0
    for line in lines:
        p = line.split("\t")
        if p[0] != "K" or len(p) < 7:
            continue
        kind, at, what, owner, nest = p[1], p[2], p[3], p[4], int(p[5])
        waiters = p[7] if len(p) > 7 else ""
        free = owner == "-" and nest <= 0
        held = "free" if free else (f"held by {owner}" if owner != "-" else f"held shared ({nest})")
        if not free and owner != "-":
            held += f", nested {nest}"
        mark = ""
        if waiters:
            mark = f"; waiting: {waiters}"
            busy += 1
        label = f"{kind} {at}" + (f" {what!r}" if what else "")
        out.append(f"{label:48} {held}{mark}")
    if not out:
        return "no locks reported"
    head = (f"{busy} lock(s) with tasks waiting\n" if busy else "nobody waits for a layer lock\n")
    return head + "\n".join(out) + (
        "\n(Intuition's own IBase locks are private and can't be read; a task that waits "
        "in LockIBase shows in amiga_task(name, stack=...))")


def cpu(lines: list[str], names: dict[int, str] | None = None) -> str:
    """N and C lines -> percent per task, busiest first."""
    head = next((line.split("\t") for line in lines if line.startswith("N\t")), None)
    if not head or len(head) < 5:
        return "no samples"
    samples, ms, idle, other = (int(x) for x in head[1:5])
    rows = []
    for line in lines:
        p = line.split("\t")
        if p[0] == "C" and len(p) >= 4:
            at = int(p[1], 16)
            rows.append((int(p[2]), at, (names or {}).get(at) or p[3]))
    rows.sort(reverse=True)
    pct = lambda n: 100.0 * n / samples if samples else 0.0  # noqa: E731
    out = [f"{samples} samples every {ms} ms ({samples * ms / 1000:.1f} s); idle {pct(idle):.1f} %"]
    if len(head) >= 7:
        out[0] += f"; exec switched tasks {head[5]} times meanwhile"
    for n, at, name in rows:
        out.append(f"{pct(n):5.1f} %  {at:08X}  {name}")
    if other:
        out.append(f"{pct(other):5.1f} %  (more tasks than amigentd counts)")
    out.append("(the task running when the sampler woke, or the next one in turn at its priority)")
    return "\n".join(out)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = min(len(s) - 1, max(0, round(p / 100 * (len(s) - 1))))
    return s[k]


def drag(lines: list[str], step: int) -> str:
    """D lines -> how long each step took and how often the window did not follow."""
    rows = []
    for line in lines:
        p = line.split("\t")
        if p[0] == "D" and len(p) >= 10:
            rows.append([int(x) for x in p[1:10]])
    if not rows:
        return "no steps measured"
    frames = [r[4] / 1000 for r in rows]
    events = [r[3] / 1000 for r in rows]
    still = 0
    lag = []
    for i, r in enumerate(rows):
        prev_left = rows[i - 1][5] if i else None
        if prev_left is not None and r[5] == prev_left:
            still += 1
        lag.append(abs((r[1] - rows[0][1]) - (r[5] - rows[0][5])))
    first, last = rows[0], rows[-1]
    out = [f"{len(rows)} steps of {step} px",
           f"per step (event to next frame): median {median(frames):.1f} ms, p95 {percentile(frames, 95):.1f} ms, "
           f"max {max(frames):.1f} ms",
           f"event into input.device: median {median(events):.2f} ms, max {max(events):.2f} ms",
           f"steps the window did not move: {still} of {len(rows) - 1}",
           f"window behind the pointer: median {median(lag):.0f} px, max {max(lag)} px",
           f"window went from {first[5]},{first[6]} to {last[5]},{last[6]}"]
    if still == len(rows) - 1:
        out.append("the window never moved while dragged: outline dragging (not opaque) in "
                   "Intuition's prefs, or something holds its layers")
    return "\n".join(out)
