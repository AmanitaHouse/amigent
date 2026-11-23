"""The classic PiStorm emulator under Linux, managed on its Raspberry Pi over SSH.

The original PiStorm software (the "emulator" program with .cfg files such as
default.cfg) runs as a Linux program on the Pi. This module logs in to the Pi
with the system's ssh command and the user's own key (BatchMode=yes: no
password prompts, the user's known_hosts), and

- finds out how the emulator runs: a systemd unit, or a process started by
  hand or by a run script, and which .cfg it reads;
- shows the configuration and changes it, with a copy on the Pi first and a
  record on this PC, so undo() puts the old file back in one call;
- restarts the emulator the way it was started;
- reads its log and the Pi's temperature and under-voltage state.

Amigent stores no passwords.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import posixpath
import re
import shlex
import subprocess
import time

from . import paths, roster
from .errors import AmigaError

TIMEOUT = 30
UNIT_SEPARATOR = "\x1f"  # /proc/<pid>/cmdline arrives with this in place of NUL bytes


class PiError(AmigaError):
    pass


# ---------------------------------------------------------------- where the Pi is

_USER = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,31}")


def validate_pi(value: str) -> str:
    """'[user@]host', the host an IP address or hostname. Anything else for ssh
    (port, key file, jump host) belongs into ~/.ssh/config under that name."""
    value = value.strip()
    user, at, host = value.rpartition("@")
    if at and not _USER.fullmatch(user):
        raise roster.RegistryError("Give the Pi as [user@]address, for example pi@raspberrypi.local.")
    try:
        host = roster.validate_address(host)
    except roster.RegistryError:
        raise roster.RegistryError("Give the Pi as [user@]address, for example pi@raspberrypi.local.") from None
    return f"{user}@{host}" if at else host


def set_pi(machine: str, pi: str) -> dict:
    """Keep the Pi's SSH address with the Amiga's entry; '' removes it."""
    with roster.transaction():
        amigas = roster.load()
        entry = roster._find(machine, amigas)
        if not entry:
            raise roster.RegistryError("No such saved Amiga.")
        if pi.strip():
            entry["pi"] = validate_pi(pi)
        else:
            entry.pop("pi", None)
        roster.save(amigas)
        return entry


def pi_of(machine: str) -> str:
    entry = roster.find(machine)
    if not entry or not entry.get("pi"):
        raise PiError("No Pi is set for this Amiga. Set it with amigent-fleet --pi NAME [user@]address "
                      "or amiga_pistorm('set_pi', pi='[user@]address', confirm=True); the login "
                      "uses your own SSH key.")
    return validate_pi(entry["pi"])


# ---------------------------------------------------------------- ssh

def ssh_runner(target: str, command: str, stdin: bytes | None = None,
               timeout: float = TIMEOUT) -> tuple[int, str, str]:
    """One remote command through the system's ssh: the user's key and known_hosts,
    never a password prompt."""
    ssh = os.environ.get("AMIGENT_SSH", "ssh")
    argv = [ssh, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "--", target, command]
    try:
        done = subprocess.run(argv, input=stdin if stdin is not None else b"",
                              capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise PiError(f"no ssh command found ({ssh}); install OpenSSH or set AMIGENT_SSH") from None
    except subprocess.TimeoutExpired:
        raise PiError(f"the Pi {target} did not finish within {timeout:.0f} s") from None
    return done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace")


def _q(value: str) -> str:
    return shlex.quote(value)


# The remote side is POSIX sh. pgrep -x matches the process name "emulator".
PROBE = r"""
pid=$(pgrep -x emulator | head -n 1)
echo "pid=$pid"
if [ -n "$pid" ]; then
  echo "cwd=$(readlink /proc/$pid/cwd 2>/dev/null || sudo -n readlink /proc/$pid/cwd 2>/dev/null)"
  echo "cmd=$(tr '\000' '\037' < /proc/$pid/cmdline)"
  echo "user=$(ps -o user= -p $pid | tr -d ' ')"
  echo "out=$(readlink /proc/$pid/fd/1 2>/dev/null || sudo -n readlink /proc/$pid/fd/1 2>/dev/null)"
  echo "unit=$(grep -o 'system.slice/[^/]*[.]service' /proc/$pid/cgroup 2>/dev/null | tail -n 1 | cut -d/ -f2)"
  p=$(ps -o ppid= -p $pid | tr -d ' ')
  if [ -n "$p" ] && [ "$(ps -o comm= -p $p)" = sudo ]; then p=$(ps -o ppid= -p $p | tr -d ' '); fi
  if [ -n "$p" ] && [ "$p" != 1 ]; then echo "parent=$(tr '\000' '\037' < /proc/$p/cmdline)"; fi
fi
for f in $(grep -lsE 'pistorm|/emulator( |$)' /etc/systemd/system/*.service 2>/dev/null); do
  u=$(basename "$f")
  echo "unitfile=$u"
  systemctl show -p ExecStart -p WorkingDirectory -p ActiveState -p UnitFileState "$u" 2>/dev/null | sed "s/^/show:$u:/"
done
echo "temp=$(vcgencmd measure_temp 2>/dev/null)"
echo "throttled=$(vcgencmd get_throttled 2>/dev/null)"
echo "zone=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)"
"""

THROTTLED = {
    0: "under-voltage now",
    1: "ARM frequency capped now",
    2: "throttled now",
    3: "soft temperature limit now",
    16: "under-voltage has occurred since boot",
    17: "ARM frequency capping has occurred",
    18: "throttling has occurred",
    19: "soft temperature limit has occurred",
}


def decode_throttled(text: str) -> tuple[int | None, list[str]]:
    """'throttled=0x50005' -> (0x50005, ['under-voltage now', ...])."""
    match = re.search(r"0x([0-9a-fA-F]+)", text or "")
    if not match:
        return None, []
    value = int(match.group(1), 16)
    return value, [why for bit, why in sorted(THROTTLED.items()) if value >> bit & 1]


def _exec_start_argv(text: str) -> list[str]:
    """systemctl show's 'ExecStart={ path=... ; argv[]=/x/emulator --config a.cfg ; ... }'."""
    match = re.search(r"argv\[\]=(.*?) ;", text or "")
    if not match:
        return []
    try:
        return shlex.split(match.group(1))
    except ValueError:
        return match.group(1).split()


def config_from_argv(argv: list[str], cwd: str) -> str:
    """The .cfg this emulator command line reads; emulator.c falls back to default.cfg."""
    if not argv or posixpath.basename(argv[0]) != "emulator":
        return ""
    name = "default.cfg"
    for i, arg in enumerate(argv[1:], 1):
        if arg in ("--config-file", "--config") and i + 1 < len(argv):
            name = argv[i + 1]
    if posixpath.isabs(name):
        return posixpath.normpath(name)
    return posixpath.normpath(posixpath.join(cwd, name)) if cwd else ""


class Pi:
    """One Pi with the classic PiStorm emulator. run is ssh_runner or a stand-in."""

    def __init__(self, machine: str, target: str | None = None, run=None):
        self.machine = machine
        self.target = target or pi_of(machine)
        self.run = run or ssh_runner

    # -------------------------------------------------- plumbing

    def sh(self, script: str, stdin: bytes | None = None, timeout: float = TIMEOUT,
           check: bool = True) -> str:
        rc, out, err = self.run(self.target, "sh -c " + _q(script), stdin, timeout)
        if rc == 255:
            raise PiError(f"no SSH login to {self.target}: {err.strip() or 'connection failed'}. "
                          "Amigent logs in with your own key and never asks for a password: "
                          f"run 'ssh {self.target}' once yourself (host key, key file in ~/.ssh/config).")
        if check and rc != 0:
            raise PiError(f"on {self.target}: {(err or out).strip() or f'exit code {rc}'}")
        return out

    def probe(self) -> dict:
        info = {"units": {}, "unitfiles": []}
        for line in self.sh(PROBE).splitlines():
            key, eq, value = line.partition("=")
            if not eq:
                continue
            if key.startswith("show:"):
                _, unit, prop = key.split(":", 2)
                info["units"].setdefault(unit, {})[prop] = value
            elif key == "unitfile":
                info["unitfiles"].append(value)
            else:
                info[key] = value
        info["argv"] = [a for a in info.get("cmd", "").split(UNIT_SEPARATOR) if a]
        info["parent_argv"] = [a for a in info.get("parent", "").split(UNIT_SEPARATOR) if a]
        return info

    def how(self, info: dict) -> dict:
        """How this emulator runs: unit, config file, working folder. Detected, never guessed."""
        unit = info.get("unit") or ""
        if not unit and not info.get("pid") and len(info["unitfiles"]) == 1:
            unit = info["unitfiles"][0]
        cwd, argv = info.get("cwd", ""), info["argv"]
        if not argv and unit:
            shown = info["units"].get(unit, {})
            argv = _exec_start_argv(shown.get("ExecStart", ""))
            cwd = shown.get("WorkingDirectory", "") or (posixpath.dirname(argv[0]) if argv else "")
        return {"unit": unit, "cwd": cwd, "argv": argv, "config": config_from_argv(argv, cwd)}

    def _config_path(self, file: str, how: dict) -> str:
        if file:
            path = file if posixpath.isabs(file) else posixpath.join(how["cwd"], file) if how["cwd"] else ""
            if not path:
                raise PiError("give file as an absolute path; the emulator's folder is not known")
            path = posixpath.normpath(path)
        else:
            path = how["config"]
            if not path:
                raise PiError("which .cfg the emulator reads could not be found out (it is not running, "
                              "and no unit starts it directly); pass file='/path/to/your.cfg'")
        if not path.endswith(".cfg"):
            raise PiError("only PiStorm .cfg files are shown and changed here")
        return path

    # -------------------------------------------------- reading

    def status(self) -> str:
        info = self.probe()
        how = self.how(info)
        lines = [f"Pi: {self.target}  (classic PiStorm emulator)"]
        if info.get("pid"):
            lines.append(f"emulator: running, pid {info['pid']} as {info.get('user') or '?'}, "
                         f"in {info.get('cwd') or '?'}: {' '.join(info['argv'])}")
        else:
            lines.append("emulator: not running")
        if how["unit"]:
            shown = info["units"].get(how["unit"], {})
            state = ", ".join(v for v in (shown.get("ActiveState"), shown.get("UnitFileState")) if v)
            lines.append(f"started by: systemd unit {how['unit']}" + (f" ({state})" if state else ""))
        elif info.get("pid"):
            parent = " ".join(info["parent_argv"])
            lines.append(f"started by: {parent}" if parent else "started by: hand or rc.local (no parent left)")
        if len(info["unitfiles"]) > 1 and not info.get("unit"):
            lines.append("units that mention the emulator: " + ", ".join(info["unitfiles"]))
        lines.append(f"config: {how['config'] or 'unknown'}")
        if info.get("out"):
            lines.append(f"output goes to: {info['out']}")
        lines.append("temperature: " + self._temperature(info))
        value, flags = decode_throttled(info.get("throttled", ""))
        if value is None:
            lines.append("power: unknown (vcgencmd get_throttled gave no answer)")
        elif not flags:
            lines.append("power: fine, no under-voltage or throttling since boot")
        else:
            lines.append(f"power: 0x{value:x}: " + "; ".join(flags))
        return "\n".join(lines)

    @staticmethod
    def _temperature(info: dict) -> str:
        match = re.search(r"([0-9.]+)'?C", info.get("temp", ""))
        if match:
            return f"{float(match.group(1)):.1f} °C"
        if info.get("zone", "").strip().isdigit():
            return f"{int(info['zone']) / 1000:.1f} °C"
        return "unknown"

    def health(self) -> dict:
        info = self.probe()
        value, flags = decode_throttled(info.get("throttled", ""))
        return {"temperature": self._temperature(info), "throttled": value, "flags": flags}

    def read_config(self, file: str = "") -> tuple[str, str]:
        path = self._config_path(file, self.how(self.probe()))
        text = self.sh(f"cat -- {_q(path)} 2>/dev/null || sudo -n cat -- {_q(path)}")
        return path, text

    def log(self, lines: int = 100) -> str:
        lines = max(1, min(int(lines), 2000))
        info = self.probe()
        how = self.how(info)
        if how["unit"]:
            u = _q(how["unit"])
            # sudo first: without it a user outside the adm group sees no system unit's lines
            return self.sh(f"sudo -n journalctl -u {u} -n {lines} --no-pager 2>/dev/null || "
                           f"journalctl -u {u} -n {lines} --no-pager")
        out = info.get("out", "")
        if not info.get("pid"):
            raise PiError("the emulator is not running and no systemd unit starts it: no log to read")
        if not out.startswith("/") or out.startswith(("/dev/", "/proc/")) or "(deleted)" in out or "pipe:" in out:
            raise PiError(f"the emulator writes to {out or 'nowhere known'}, not into a file: "
                          "it prints its log only there")
        return self.sh(f"tail -n {lines} -- {_q(out)} 2>/dev/null || sudo -n tail -n {lines} -- {_q(out)}")

    # -------------------------------------------------- changing

    def records(self) -> list[dict]:
        try:
            return json.loads(_record_file(self.machine).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _save_records(self, records: list[dict]) -> None:
        path = _record_file(self.machine)
        path.parent.mkdir(parents=True, exist_ok=True)
        roster._atomic_json(path, records)

    def write_config(self, text: str, file: str = "", confirm: bool = False) -> str:
        """Without confirm: the difference only. With confirm: copy on the Pi, then the new text."""
        path, old = self.read_config(file)
        if not text.endswith("\n"):
            text += "\n"
        diff = "".join(difflib.unified_diff(old.splitlines(True), text.splitlines(True),
                                            path, path + " (new)"))
        if not diff:
            return f"{path} already says exactly this; nothing to change"
        if not confirm:
            return diff + "\nNothing changed yet; confirm=True writes it (a copy is kept on the Pi)."
        backup = f"{path}.amigent-{time.strftime('%Y%m%d-%H%M%S')}"
        p, b = _q(path), _q(backup)
        self.sh(f'if [ -w {p} ]; then S=; else S="sudo -n"; fi; '
                f'$S cp -p -- {p} {b} && $S tee -- {p} >/dev/null', stdin=text.encode())
        records = self.records()
        records.append({"file": path, "backup": backup, "at": time.time(),
                        "before": _sha(old), "after": _sha(text)})
        self._save_records(records)
        return (diff + f"\nWritten. The old file is in {backup}; amiga_pistorm('undo', confirm=True) "
                "puts it back. The emulator reads it at its next start (restart).")

    def undo(self, confirm: bool = False) -> str:
        records = self.records()
        if not records:
            raise PiError("no change to the emulator's configuration to take back")
        last = records[-1]
        path, backup = last["file"], last["backup"]
        current = self.sh(f"cat -- {_q(path)} 2>/dev/null || sudo -n cat -- {_q(path)}")
        if _sha(current) != last["after"]:
            raise PiError(f"{path} was changed again since Amigent wrote it; the old file is still in "
                          f"{backup}, copy it back yourself if you want it")
        if not confirm:
            return f"undo would copy {backup} back to {path}; confirm=True does it"
        p, b = _q(path), _q(backup)
        self.sh(f'if [ -w {p} ]; then S=; else S="sudo -n"; fi; $S cp -p -- {b} {p}')
        self._save_records(records[:-1])
        return f"{path} is back as it was before {time.strftime('%Y-%m-%d %H:%M', time.localtime(last['at']))}; restart the emulator to use it"

    def restart(self, confirm: bool = False) -> str:
        info = self.probe()
        how = self.how(info)
        if how["unit"]:
            plan = f"sudo systemctl restart {how['unit']}"
        elif info.get("pid"):
            plan = (f"stop pid {info['pid']} and start '{' '.join(info['argv'])}' again in "
                    f"{info.get('cwd')} (unless its run script starts it again by itself)")
        else:
            raise PiError("the emulator is not running and no systemd unit starts it, so how it is "
                          "started is not known; start it once yourself, then restart works")
        if not confirm:
            return f"restart would: {plan}; confirm=True does it"
        if how["unit"]:
            self.sh(f"sudo -n systemctl restart {_q(how['unit'])}", timeout=60)
            state = self.sh(f"systemctl is-active {_q(how['unit'])}", check=False).strip()
            return f"restarted {how['unit']}: {state or 'unknown state'}"
        pid, cwd, argv = info["pid"], info.get("cwd", ""), info["argv"]
        if not pid.isdigit() or not cwd or not argv:
            raise PiError("the running emulator's folder or command line could not be read; restart it yourself")
        out = info.get("out", "")
        if not out.startswith("/") or out.startswith(("/dev/", "/proc/")) or "(deleted)" in out:
            out = posixpath.join(cwd, "amigent-emulator.log")
        user = info.get("user", "")
        script = (f'if [ "$(id -un)" = {_q(user)} ]; then S=; else S="sudo -n"; fi; '
                  f"$S kill {pid} || exit 1; "
                  f"i=0; while kill -0 {pid} 2>/dev/null && [ $i -lt 10 ]; do sleep 1; i=$((i+1)); done; "
                  "sleep 3; n=$(pgrep -x emulator | head -n 1); "
                  'if [ -n "$n" ]; then echo "again=$n"; exit 0; fi; '
                  f"cd {_q(cwd)} && $S setsid nohup {' '.join(_q(a) for a in argv)} "
                  f">> {_q(out)} 2>&1 < /dev/null & "
                  'sleep 2; echo "started=$(pgrep -x emulator | head -n 1)"')
        result = self.sh(script, timeout=60)
        for line in result.splitlines():
            key, _, value = line.partition("=")
            if key == "again":
                return f"stopped pid {pid}; its run script started it again (pid {value})"
            if key == "started":
                if not value:
                    raise PiError(f"stopped pid {pid}, but it did not come back; see {out}")
                return f"restarted: pid {value}, output in {out}"
        raise PiError(f"no answer from the restart on {self.target}")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _record_file(machine: str):
    return paths.FOLDER / "pistorm" / (paths.safe(roster.identity(machine)) + ".json")
