"""Is a newer Amigent out? And if the user says yes: update this PC, then every Amiga.

The check asks PyPI for the release list, nothing else: no name, no Amiga, no
identifier goes out (the request carries the PC's address, as any download
does). At most once a day, in the background, with a short timeout; offline
or behind a proxy it stays silent. PyPI, not GitHub: pipx installs from PyPI,
so a version is only offered once it can be installed.

Switched off with AMIGENT_NO_UPDATE_CHECK=1 or `"check": false` in
~/.config/amigent/update.json (`python -m amigent.update off`).

The update itself runs `pipx upgrade amigent`, then `amigent-setup --update`
for each saved Amiga in a fresh process: the new amigentd comes with the new
package, and this process still has the old files loaded.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from . import __version__
from .paths import FOLDER

PYPI = "https://pypi.org/pypi/amigent/json"
RELEASE = "https://api.github.com/repos/akustikrausch/amigent/releases/tags/v{version}"
RELEASE_PAGE = "https://github.com/akustikrausch/amigent/releases/tag/v{version}"
CHECK_EVERY = 24 * 3600  # seconds between two questions to PyPI
TIMEOUT = 3.0
NOTES_LINES = 8  # lines of "what is new" at most
_lock = threading.Lock()
_running = threading.Event()  # a check is on its way


def _file() -> Path:
    return FOLDER / "update.json"


def _load() -> dict:
    try:
        value = json.loads(_file().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(state: dict) -> None:
    try:
        FOLDER.mkdir(parents=True, exist_ok=True)
        part = _file().with_name(f"update.json.{os.getpid()}.part")
        part.write_text(json.dumps(state, indent=1), encoding="utf-8")
        os.replace(part, _file())
    except OSError:
        pass  # only the next check comes sooner


def _change(**values) -> dict:
    with _lock:
        state = _load()
        for key, value in values.items():
            if value is None:
                state.pop(key, None)
            else:
                state[key] = value
        _save(state)
        return state


def enabled() -> bool:
    if os.environ.get("AMIGENT_NO_UPDATE_CHECK", "").strip() not in ("", "0"):
        return False
    return _load().get("check", True) is not False


def set_enabled(on: bool) -> None:
    _change(check=None if on else False)


def skip(version: str) -> None:
    """The user does not want this version offered again."""
    _change(skip=version)


def version_key(version: str) -> tuple[int, ...] | None:
    """(1, 4, 0) for '1.4.0'; None for anything else, such as '1.5.0rc1' or '1.5.0.dev1'."""
    if not re.fullmatch(r"\d+(\.\d+){0,3}", version or ""):
        return None
    numbers = [int(p) for p in version.split(".")]
    return tuple(numbers + [0] * (4 - len(numbers)))


def newer(version: str, than: str | None = None) -> bool:
    a, b = version_key(version), version_key(__version__ if than is None else than)
    return a is not None and b is not None and a > b


def latest_from_pypi(answer: dict) -> str:
    """The newest release that can be installed: not a pre-release, not yanked, with files."""
    best, key = "", None
    for version, files in (answer.get("releases") or {}).items():
        k = version_key(version)
        if k is None or not files or all(f.get("yanked") for f in files):
            continue
        if key is None or k > key:
            best, key = version, k
    return best


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": f"amigent/{__version__}",
                                                   "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # nosec: fixed sites
        return answer.read(4 << 20)


def release_notes(version: str) -> str:
    """The first lines of the GitHub release text, bullets only; '' if it can't be had."""
    try:
        body = json.loads(_get(RELEASE.format(version=version))).get("body") or ""
    except (OSError, ValueError):
        return ""
    lines = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ")):
            text = re.sub(r"\*\*|`", "", line[2:])
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
            lines.append("- " + (text if len(text) <= 160 else text[:157].rstrip() + "..."))
            if len(lines) == NOTES_LINES:
                break
    return "\n".join(lines)


def refresh(force: bool = False) -> dict:
    """Ask PyPI if the last answer is older than a day (or force). Never raises."""
    state = _load()
    if not force and time.time() - float(state.get("checked", 0) or 0) < CHECK_EVERY:
        return state
    try:
        latest = latest_from_pypi(json.loads(_get(PYPI)))
    except (OSError, ValueError, AttributeError):
        return _change(checked=time.time())  # offline: ask again tomorrow, quietly
    notes = state.get("notes", "") if state.get("latest") == latest else None
    if notes is None:
        notes = release_notes(latest) if latest and newer(latest) else ""
    return _change(checked=time.time(), latest=latest or None, notes=notes or None)


def refresh_in_background(then=None) -> None:
    """refresh() on a thread of its own, once at a time; then(offer()) afterwards."""
    if not enabled() or _running.is_set():
        return
    _running.set()

    def run():
        try:
            refresh()
            if then:
                then(offer())
        finally:
            _running.clear()

    threading.Thread(target=run, daemon=True, name="amigent update check").start()


def offer(state: dict | None = None) -> dict | None:
    """What to tell the user, from the last answer: {'version', 'current', 'notes', 'page'}, or None."""
    if not enabled():
        return None
    state = _load() if state is None else state
    latest = state.get("latest") or ""
    if not latest or not newer(latest) or state.get("skip") == latest:
        return None
    return {"version": latest, "current": __version__, "notes": state.get("notes") or "",
            "page": RELEASE_PAGE.format(version=latest)}


# how this Amigent was installed, and what updates it

def how_installed() -> str:
    """'pipx', 'source' (a checkout, editable or on PYTHONPATH) or 'pip'."""
    package = Path(__file__).resolve().parent
    if not any(part == "site-packages" for part in package.parts):
        return "source"
    try:
        from importlib.metadata import distribution
        direct = json.loads(distribution("amigent").read_text("direct_url.json") or "{}")
        if (direct.get("dir_info") or {}).get("editable"):
            return "source"
    except Exception:  # noqa: BLE001 - metadata missing or odd: judge by the path alone
        pass
    if (Path(sys.prefix) / "pipx_metadata.json").exists():  # pipx leaves it in each of its venvs
        return "pipx"
    return "pip"


def command(kind: str | None = None) -> list[str]:
    """What updates this PC's Amigent; [] for a checkout, which updates with git."""
    kind = kind or how_installed()
    if kind == "pipx":
        return ["pipx", "upgrade", "amigent"]
    if kind == "pip":
        return [sys.executable, "-m", "pip", "install", "--upgrade", "amigent"]
    return []


def installed_version(python: str = sys.executable) -> str:
    """The version a fresh Python from this environment imports: the new one after an upgrade."""
    done = subprocess.run([python, "-c", "import amigent; print(amigent.__version__)"],
                          capture_output=True, text=True, timeout=60)
    return done.stdout.strip()


def apply(amigas: list[str], say=print, run=subprocess.run) -> bool:
    """Update this PC, then each Amiga. say() gets every step; True when the PC got newer.

    Only for pipx and pip installs. Each Amiga gets `amigent-setup --update` from
    the new package, in a process of its own; one that does not answer is skipped.
    """
    kind = how_installed()
    upgrade = command(kind)
    if not upgrade:
        say("This Amigent runs from a source checkout: update it with git pull, "
            "then run amigent-setup --update.")
        return False
    if kind == "pipx":
        from shutil import which
        if not which("pipx"):
            say("pipx is not on the PATH: run pipx upgrade amigent by hand.")
            return False
        upgrade[0] = which("pipx")
    say(f"Updating Amigent {__version__} on this computer: {' '.join(command(kind)[-3:])}")
    done = run(upgrade, capture_output=True, text=True, timeout=600)
    if done.returncode:
        say(f"That failed ({done.returncode}):\n{(done.stderr or done.stdout).strip()[-1500:]}")
        return False
    now = installed_version()
    if not now or now == __version__:
        hint = (" pipx updates from where Amigent was installed from; to take it from PyPI: "
                "pipx install --force amigent") if kind == "pipx" else ""
        say(f"Amigent on this computer is still {now or __version__}; nothing changed.{hint}")
        return False
    say(f"This computer now has Amigent {now}.")
    _change(skip=None, done=now)
    for host in amigas:
        say(f"Updating amigentd on {host} ...")
        step = run([sys.executable, "-m", "amigent.setup", host, "--update"],
                   capture_output=True, text=True, timeout=900)
        last = [line for line in (step.stdout or "").splitlines() if line.strip()]
        text = last[-1] if last else (step.stderr or "").strip()[-300:]
        say(f"{host}: {text or 'no answer'}" + ("" if step.returncode == 0 else " (skipped)"))
    return True


def _log() -> Path:
    return FOLDER / "update.log"


def start_for_viewer(host: str) -> None:
    """The remote desktop's Update button: a helper of its own does the work once this
    viewer has quit (Windows does not replace the files of a running program)."""
    FOLDER.mkdir(parents=True, exist_ok=True)
    log = open(_log(), "w", encoding="utf-8")  # noqa: SIM115 - the helper owns it from here
    flags = {}
    if sys.platform == "win32":
        flags["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        flags["start_new_session"] = True
    subprocess.Popen([sys.executable, "-m", "amigent.update", "viewer", host, str(os.getpid())],
                     stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **flags)


def _gone(pid: int) -> bool:
    if sys.platform == "win32":
        done = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) not in done.stdout
    try:
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        return True
    except PermissionError:
        return False


def _for_viewer(host: str, pid: int) -> None:
    """Wait for the viewer to go, update, refresh the Start menu entry, open the viewer again."""
    deadline = time.monotonic() + 30
    while not _gone(pid) and time.monotonic() < deadline:
        time.sleep(0.5)
    lines: list[str] = []

    def say(text: str) -> None:
        print(text, flush=True)
        lines.append(text)

    from . import machines
    ok = apply([a["name"] for a in machines.load()] or [host], say=say)
    if ok:
        done = subprocess.run([sys.executable, "-c",
                               "from amigent import desktop, machines\n"
                               f"if desktop.installed(): desktop.install(machines.name_of({host!r}))"],
                              capture_output=True, text=True, timeout=300)
        if done.returncode:
            say("The Start menu entry keeps its old number: run amigent-viewer --install.")
    _change(last_run="\n".join(lines), last_ok=ok)
    subprocess.Popen([sys.executable, "-m", "amigent.viewer", host, "--exit-when-closed"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     **({"start_new_session": True} if sys.platform != "win32" else {}))


def last_run() -> dict | None:
    """What the last update from the remote desktop said, once: {'ok', 'text'}."""
    state = _load()
    if "last_run" not in state:
        return None
    _change(last_run=None, last_ok=None)
    return {"ok": bool(state.get("last_ok")), "text": state["last_run"]}


def main() -> None:
    """python -m amigent.update [check|on|off|apply]"""
    what = sys.argv[1] if len(sys.argv) > 1 else "check"
    if what == "off":
        set_enabled(False)
        print("The update check is off.")
    elif what == "on":
        set_enabled(True)
        print("The update check is on.")
    elif what == "check":
        found = offer(refresh(force=True)) if enabled() else None
        if not enabled():
            print("The update check is off (python -m amigent.update on).")
        elif found:
            print(f"Amigent {found['version']} is out (this is {found['current']}).\n{found['notes']}\n{found['page']}")
        else:
            print(f"Amigent {__version__} is the newest.")
    elif what == "viewer" and len(sys.argv) == 4:
        _for_viewer(sys.argv[2], int(sys.argv[3]))
    elif what == "apply":
        from . import machines
        hosts = [a["name"] for a in machines.load()]
        sys.exit(0 if apply(hosts) else 1)
    else:
        raise SystemExit(main.__doc__)


if __name__ == "__main__":
    main()
