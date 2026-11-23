"""The Raspberry Pi's own network for an Amiga with Emu68 (#20).

Many PiStorm Amigas reach the network through a slow adapter at the parallel
or serial port, while the Pi behind them has Ethernet (Pi 4, CM4) or Wi-Fi
(Pi 3, Pi 4, Zero 2 W) that Emu68 drivers hand to AmigaOS. This module

- tells what is there: Emu68 or not, the drivers in DEVS:Networks, the
  TCP/IP stack, the interfaces Roadshow has, and what the link runs at;
- sets up the Pi's Ethernet or Wi-Fi as a second Roadshow interface next to
  the existing one, on probation: the interface file first lives in
  Amigent's own folder, AddNetInterface brings it up from there, and a script
  started with Run takes it down again after a while unless the PC has
  confirmed through the new address. A restart forgets it as well, since
  nothing in DEVS:NetInterfaces changed yet. The way back needs no network.
- keeps it after the confirmation: only then is the file copied into
  DEVS:NetInterfaces, so Roadshow brings it up at every start.

Nothing here deletes or edits an existing interface, and nothing touches the
Pi's boot partition. Wi-Fi names and passwords are never handled: the user
enters them on the Amiga, where wifipi.device expects them.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import secret, roster
from .errors import AmigaError

NETINTERFACES = "DEVS:NetInterfaces"
NETWORKS = "DEVS:Networks"
PROBATION = 90  # seconds before the probation script takes the new interface down again
CONFIRM_FLAG = "ENV:amigent-net-ok"  # written by the PC through the new address
TEST_FILE = "RAM:amigent-net-speed"
TEST_BYTES = 32 * 1024


@dataclass(frozen=True)
class Kind:
    key: str
    device: str
    interface: str  # Roadshow names the interface after its file
    what: str
    source: str


KINDS = {
    "ethernet": Kind("ethernet", "genet.device", "pieth", "the Ethernet port of a Pi 4 or CM4",
                     "the emu68-genet project on GitHub (Pi 4 and CM4 only, it needs a recent "
                     "Emu68; the Pi 3's Ethernet sits on its USB hub and has no Amiga driver)"),
    "wifi": Kind("wifi", "wifipi.device", "piwifi", "the Wi-Fi of a Pi 3, Pi 4 or Zero 2 W",
                 "Emu68-tools (github.com/michalsc/Emu68-tools); AmiKit and other "
                 "PiStorm distributions often have it already"),
}
_IPV4 = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")


def kind(name: str) -> Kind:
    try:
        return KINDS[name.strip().lower()]
    except KeyError:
        raise AmigaError(f"interface is 'ethernet' or 'wifi', not {name!r}") from None


def join(folder: str, name: str) -> str:
    return folder + name if folder.endswith((":", "/")) else f"{folder}/{name}"


# ---------------------------------------------------------------- reading

def parse_interface(text: str) -> dict:
    """A Roadshow interface file: key=value lines, # starts a comment."""
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            key, value = line.split("=", 1)
            out[key.strip().lower()] = value.strip()
    return out


def addresses(text: str) -> list[str]:
    """IPv4 addresses in ShowNetStatus output, without masks, loopback or 0.0.0.0."""
    found = []
    for m in _IPV4.finditer(text):
        parts = [int(p) for p in m.groups()]
        if any(p > 255 for p in parts) or parts[0] in (0, 127, 255):
            continue
        address = ".".join(map(str, parts))
        if address not in found:
            found.append(address)
    return found


def interface_file(k: Kind) -> str:
    """What the setup writes: DHCP on the Pi's device, unit 0."""
    return (f"# {k.interface}: {k.what}, set up by Amigent\n"
            f"device={k.device}\nunit=0\nconfigure=dhcp\n")


def exists(ctl, path: str) -> bool:
    try:
        ctl.stat(path)
        return True
    except AmigaError:
        return False


def names(ctl, folder: str) -> list[dict]:
    try:
        return ctl.list_dir(folder)
    except AmigaError:
        return []


def stack(ctl) -> dict:
    """Which TCP/IP stack: Roadshow (DEVS:NetInterfaces), AmiTCP, Miami."""
    if exists(ctl, NETINTERFACES) or exists(ctl, "C:AddNetInterface"):
        return {"name": "Roadshow", "interfaces": NETINTERFACES, "can_set_up": True}
    for name, marks in (("Miami", ("Miami:", "C:MiamiDx")), ("AmiTCP", ("AmiTCP:", "AmiTCP:db/interfaces"))):
        if any(exists(ctl, m) for m in marks):
            return {"name": name, "can_set_up": False,
                    "note": f"{name} keeps its interfaces in its own settings; Amigent sets up "
                            "only Roadshow. Add the device there by hand"}
    return {"name": "unknown", "can_set_up": False,
            "note": "no Roadshow, AmiTCP or Miami found"}


def report(ctl, emu68: bool, link: dict | None = None) -> dict:
    """What is possible, read only. ctl: exec, stat, list_dir, read_file."""
    out: dict = {"emu68": emu68}
    if not emu68:
        out["note"] = ("this Amiga does not run Emu68 (no devicetree.resource): the Pi's "
                       "network is only for PiStorm Amigas with Emu68")
    out["pi"] = ("Emu68 does not tell AmigaOS the Pi model; the drivers decide: Ethernet "
                 "needs a Pi 4 or CM4, Wi-Fi a Pi 3, Pi 4 or Zero 2 W")
    drivers = {e["name"].lower(): e for e in names(ctl, NETWORKS) if str(e.get("type", "")).lower() != "dir"}
    out["drivers"] = sorted(e["name"] for e in drivers.values())
    for k in KINDS.values():
        entry: dict = {"device": k.device, "installed": k.device in drivers, "for": k.what}
        if entry["installed"]:
            result = ctl.exec(f'Version "{join(NETWORKS, k.device)}" FULL')
            if not result.rc and result.output.strip():
                entry["version"] = result.output.strip().splitlines()[0]
        else:
            entry["missing"] = f"{k.device} is not in {NETWORKS}; it comes from {k.source}"
        out[k.key] = entry
    out["stack"] = stack(ctl)
    interfaces = []
    for e in names(ctl, NETINTERFACES):
        if str(e.get("type", "")).lower() == "dir" or e["name"].lower().endswith(".info"):
            continue
        try:
            settings = parse_interface(ctl.read_file(join(NETINTERFACES, e["name"])).decode("iso-8859-1"))
        except AmigaError:
            settings = {}
        interfaces.append({"name": e["name"], **{k: settings[k] for k in ("device", "unit", "configure",
                                                                           "address") if k in settings}})
    out["interfaces"] = interfaces
    if out["stack"]["name"] == "Roadshow":
        status = ctl.exec("ShowNetStatus")
        if not status.rc:
            out["addresses_now"] = addresses(status.output)
    if link:
        out["link"] = link
    return out


# ---------------------------------------------------------------- the change

@dataclass
class Record:
    """What the setup did, on the PC (JSON per Amiga) and next to it on the Amiga."""
    kind: str
    interface: str
    home: str
    old_address: str
    new_address: str = ""
    state: str = "probation"  # probation, kept, restored, undone
    started: str = ""
    probation: int = PROBATION
    before: list = field(default_factory=list)  # DEVS:NetInterfaces before, names only
    before_addresses: list = field(default_factory=list)  # what ShowNetStatus listed before
    speed_before: float = 0.0  # KB/s
    speed_after: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1)

    @property
    def folder(self) -> str:
        return join(self.home, "net")

    @property
    def staged(self) -> str:
        """The interface file while on probation, outside DEVS:NetInterfaces."""
        return join(self.folder, self.interface)

    @property
    def target(self) -> str:
        return join(NETINTERFACES, self.interface)

    @property
    def script(self) -> str:
        return join(self.folder, "probation")

    @property
    def log(self) -> str:
        return join(self.folder, "probation.log")


def record_file(amiga: str) -> Path:
    return secret.FOLDER / "pinet" / f"{secret.safe(roster.identity(amiga) or 'Amiga')}.json"


def save(amiga: str, record: Record) -> Path:
    path = record_file(amiga)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.to_json(), encoding="utf-8")
    return path


def load(amiga: str) -> Record | None:
    path = record_file(amiga)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    known = Record.__dataclass_fields__
    return Record(**{k: v for k, v in data.items() if k in known})


def probation_script(record: Record) -> str:
    """Run in the background on the Amiga: unless the PC confirmed in time, the
    new interface goes down. It needs no network and changes no file of the
    system; a restart forgets the interface anyway, since it is not in
    DEVS:NetInterfaces yet."""
    return "\n".join([
        f"; Amigent: probation for {record.interface}, written {record.started}",
        "FailAt 21",
        f"Wait {record.probation} SECS",
        f'If EXISTS "{CONFIRM_FLAG}"',
        f'  Delete >NIL: "{CONFIRM_FLAG}" QUIET',
        f'  Echo >"{record.log}" "kept: the PC confirmed {record.interface} in time"',
        "  Quit",
        "EndIf",
        f"ConfigureNetInterface >NIL: {record.interface} STATE=DOWN",
        f'Echo >"{record.log}" "restored: no confirmation within {record.probation} s, '
        f'{record.interface} is down again"',
        "",
    ])


def undo_script(record: Record) -> str:
    """Takes the interface down and removes only what the setup added."""
    return "\n".join([
        "FailAt 21",
        f"ConfigureNetInterface >NIL: {record.interface} STATE=DOWN",
        f'If EXISTS "{record.target}"',
        f'  Delete >NIL: "{record.target}" QUIET',
        "EndIf",
        f'Delete >NIL: "{record.target}.info" QUIET',
        f'Delete >NIL: "{CONFIRM_FLAG}" QUIET',
        f'Echo >"{record.log}" "undone: {record.interface} removed"',
        "",
    ])


def repair_module(record: Record) -> str:
    """After a system reinstall the kept interface file comes back from the Amigent folder."""
    return "\n".join([
        f"; pi-network: written by Amigent on {time.strftime('%Y-%m-%d')}: the Pi's "
        f"{record.kind} as Roadshow interface {record.interface}",
        "",
        f'If NOT EXISTS "{record.target}"',
        f'  Copy "{record.staged}" "{record.target}" CLONE QUIET',
        "EndIf",
        "",
    ])


def new_address(before: list[str], after: list[str], old: str, local=None) -> str:
    """The address that came with the new interface: in after, not before, not the
    old one; one on the PC's own networks first."""
    fresh = [a for a in after if a not in before and a != old]
    if local:
        import ipaddress
        mine = [a for a in fresh if any(ipaddress.ip_address(a) in net for net in local)]
        if mine:
            return mine[0]
    return fresh[0] if fresh else ""


def speed(ctl, data: bytes | None = None) -> float:
    """KB/s of a read of TEST_BYTES of random data (packing doesn't help) through ctl."""
    import os
    data = data if data is not None else os.urandom(TEST_BYTES)
    ctl.write_file(TEST_FILE, data)
    began = time.perf_counter()
    got = ctl.read_file(TEST_FILE)
    took = max(time.perf_counter() - began, 1e-6)
    try:
        ctl.delete(TEST_FILE)
    except AmigaError:
        pass
    return round(len(got) / 1024 / took, 1)
