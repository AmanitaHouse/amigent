"""What kind of Amiga this is: the OS from Version, the CPU from CPU, the FPU from
exec's AttnFlags, and PowerPC software."""

from __future__ import annotations

import re
from dataclasses import dataclass

OS_NAMES = {47: "AmigaOS 3.2", 46: "AmigaOS 3.1.4", 45: "AmigaOS 3.9", 44: "AmigaOS 3.5",
            40: "AmigaOS 3.1", 39: "AmigaOS 3.0", 37: "AmigaOS 2.04", 36: "AmigaOS 2.0", 34: "AmigaOS 1.3"}
# Kickstart 3.0 is exec 39. C:Reboot shipped with that Workbench.
OS3_EXEC = 39
# ColdReboot() arrived with Kickstart 2.0. Exec 34 and 35 do not have it.
COLDREBOOT_EXEC = 36

# PowerPC boards on a 68k Amiga bring one of these; Version FILE reads the version string
# without opening the library, which without a board could stop at a requester.
PPC_LIBRARIES = (("LIBS:powerpc.library", "WarpOS"), ("LIBS:ppc.library", "PowerUP"))

EMULATED_NOTE = ("amigentd is a 68k program and runs here under the system's 68k emulation. "
                 "Commands, files, mouse and keys should work; screen text and other parts that "
                 "hook into the system may not. Not tested on this system.")


def describe_system(version: str, cpu: str) -> dict:
    """Turn the output of the Version and CPU commands into a few named facts."""
    kick = re.search(r"Kickstart (\d+)\.(\d+)", version)
    bench = re.search(r"Workbench (\d+\.\d+)", version)
    major = int(kick.group(1)) if kick else 0
    morphos = re.search(r"MorphOS(?: version)? ?(\d+\.\d+)?", version)
    os4 = re.search(r"AmigaOS 4(?:\.\d+)*", version)
    chips = re.findall(r"\b(68(?:EC|LC)?0[0-9]0|6888[12])\b", cpu)
    ppc = re.search(r"\b(?:PowerPC|PPC)[ \w./-]*", cpu)
    if morphos:
        os_name = "MorphOS" + (f" {morphos.group(1)}" if morphos.group(1) else "")
    elif os4:
        os_name = os4.group(0)
    elif re.search(r"\bApolloOS\b", version):
        os_name = "ApolloOS"
    elif re.search(r"\bAROS\b", version):
        os_name = "AROS"
    elif major >= 50 and not ppc and any(c.endswith("68080") for c in chips):
        os_name = "ApolloOS"  # exec 51 on a 68080; AmigaOS 4 runs on PowerPC
    elif major >= 50 and not ppc and chips:
        os_name = "AROS"  # exec 50 or later on a 68k CPU is not AmigaOS 4
    elif major >= 50:  # 50 and later are AmigaOS 4 (MorphOS says its name)
        os_name = "AmigaOS 4"
    else:
        os_name = OS_NAMES.get(major, f"Kickstart {major}" if major else "")
    return {
        "os": os_name,
        "kickstart": f"{kick.group(1)}.{kick.group(2)}" if kick else "",
        "workbench": bench.group(1) if bench else "",
        "cpu": ppc.group(0).strip() if ppc else next((c for c in chips if not c.startswith("688")), ""),
        "fpu": next((c for c in chips if c.startswith("688")), ""),
    }


def _exec_major(version: str) -> int | None:
    major = str(version).split(".", 1)[0]
    return int(major) if major.isdigit() else None


def exec_before_os3(version: str) -> bool:
    """True for an exec version older than 3.0, such as '37.175' (2.04).

    A blank or unreadable version is not treated as old.
    """
    major = _exec_major(version)
    return major is not None and major < OS3_EXEC


def exec_coldreboot(version: str) -> bool:
    """True when this exec has ColdReboot(), from 36 up, such as '36.16'.

    A blank or unreadable version is not treated as having it. Exec 34 and
    35 can still be handed the reset chord's key-downs; they do not reset,
    and that chord never sends the key-ups.
    """
    major = _exec_major(version)
    return major is not None and major >= COLDREBOOT_EXEC


def native_ppc(facts: dict) -> bool:
    """AmigaOS 4 and MorphOS run on PowerPC; amigentd is emulated there."""
    return facts.get("os", "").startswith(("AmigaOS 4", "MorphOS"))


def reconcile_system(facts: dict, info: dict | None) -> dict:
    """Correct Version/CPU fallthroughs using daemon SYSINFO when it is clearer.

    Kickstart 50+ with an empty or unparseable C:CPU line is labelled AmigaOS 4
    by describe_system (AmigaOS 4 is PPC). ApolloOS on a V4 often prints the
    same Kickstart line without the word ApolloOS, while SYSINFO already has
    os=ApolloOS, cpu=68080 and AttnFlags bit 10. Prefer that evidence so the
    host does not skip FPU reporting under the 68k-emulation note.
    """
    if not info:
        return facts
    flags = attn_flags(info) or 0
    sys_os = str(info.get("os") or "")
    sys_cpu = str(info.get("cpu") or "")
    apollo = (
        sys_os == "ApolloOS"
        or bool(flags & AFF_68080)
        or sys_cpu.endswith("68080")
    )
    if not apollo:
        return facts
    out = dict(facts)
    if out.get("os", "").startswith("AmigaOS 4") or not out.get("os"):
        out["os"] = "ApolloOS"
    if not out.get("cpu") and sys_cpu:
        out["cpu"] = sys_cpu
    return out


def ppc_software(run) -> str:
    """'WarpOS powerpc.library 17.10' or the like on a 68k Amiga with a PowerPC board, else ''.

    run(command) gives (rc, output). Only reads files; nothing is opened or started.
    """
    found = []
    for path, name in PPC_LIBRARIES:
        rc, out = run(f"Version FILE {path}")
        line = out.strip().splitlines()[-1] if out.strip() else ""
        if rc == 0 and line:
            found.append(f"{name} {line}")
    return ", ".join(found)


# exec's AttnFlags, after exec/execbase.h of the NDK and ApolloOS's cpu_m68k.h.
AFF_68010, AFF_68020, AFF_68030, AFF_68040 = 1 << 0, 1 << 1, 1 << 2, 1 << 3
AFF_68881, AFF_68882, AFF_FPU40, AFF_68060 = 1 << 4, 1 << 5, 1 << 6, 1 << 7
AFF_68080 = 1 << 10
# Emu68 (PiStorm) puts this resource in from its own ROM board; nothing else has it.
EMU68_RESOURCE = "devicetree.resource"


def attn_flags(info: dict) -> int | None:
    """AttnFlags from SYSINFO ('0x8f' or '143'), or None when amigentd did not send them."""
    raw = str(info.get("attn_flags", "") or "").strip()
    if not raw:
        return None
    try:
        return int(raw, 0)
    except ValueError:
        return None


@dataclass
class Fpu:
    """What the Amiga has for floating point, and on a 68040/060 whether its support library is there.

    present: True, False, or None when not known (no AttnFlags and C:CPU named no FPU).
    kind: '68881', '68882', 'internal' (040/060/080) or ''.
    library: '68040.library' or '68060.library' on a 68040/060, else ''.
    emulation: on a 68040/060 with its FPU, whether exec's flags say the
    support code for the FPU instructions the chip lacks is in (the library
    then sets the 68881/68882 bits too, see execbase.h); None when unknown.
    loaded: whether the library is in exec's library list (amiga_loaded), None when not asked.
    emulator: 'Emu68' on a PiStorm: its JIT runs every FPU instruction itself
    (FSIN, FETOX included), so no support library is missing there; with
    Emu68's nofpu the FPU bits stay clear and it is no FPU as anywhere else.
    """
    cpu: str = ""
    present: bool | None = None
    kind: str = ""
    library: str = ""
    emulation: bool | None = None
    loaded: bool | None = None
    from_flags: bool = False
    emulator: str = ""

    @property
    def support_missing(self) -> bool:
        """A 68040/060 FPU without the library that emulates what the chip does not do."""
        if not (self.present and self.library) or self.emulator:
            return False
        if self.loaded is not None:
            return not self.loaded and not self.emulation
        return self.emulation is False

    def short(self) -> str:
        """For the 'fpu' field next to the CPU: '68882', 'FPU', 'FPU, 68040.library missing', 'no FPU'."""
        if self.present is None:
            return ""
        if not self.present:
            return "no FPU"
        if self.kind in ("68881", "68882"):
            return self.kind
        if self.support_missing:
            return f"FPU, {self.library} missing"
        return "FPU"

    def state(self) -> str:
        """For the remote desktop, which words it in the page's language: '' (unknown),
        none, chip (68881/68882), emu68, missing (the library), loaded, or fpu."""
        if self.present is None:
            return ""
        if not self.present:
            return "none"
        if self.kind in ("68881", "68882"):
            return "chip"
        if self.emulator:
            return "emu68"
        if self.support_missing:
            return "missing"
        return "loaded" if self.loaded else "fpu"

    def line(self) -> str:
        """'68040 with FPU (68040.library loaded)', '68LC040, no FPU' and the like."""
        cpu = self.cpu or "the CPU"
        if self.present is None:
            return f"{cpu}, FPU unknown (this amigentd does not report exec's AttnFlags)"
        if not self.present:
            return f"{cpu}, no FPU" + (f" ({self.emulator}, started with nofpu?)" if self.emulator else "")
        if self.kind in ("68881", "68882"):
            return f"{cpu} with {self.kind} FPU"
        if self.emulator:
            return f"{cpu} with FPU ({self.emulator})"
        if not self.library:
            return f"{cpu} with FPU"
        if self.support_missing:
            return (f"{cpu} with FPU, but {self.library} is not loaded: the FPU instructions "
                    "the chip does not have (FSIN, FETOX and the like) have no emulation")
        if self.loaded:
            return f"{cpu} with FPU ({self.library} loaded)"
        if self.emulation:
            return f"{cpu} with FPU (FPU emulation active)"
        return f"{cpu} with FPU ({self.library} not checked)"


def describe_fpu(flags: int | None, cpu: str = "", fpu_text: str = "") -> Fpu:
    """The FPU from AttnFlags when amigentd sent them, else from C:CPU's text.

    cpu is the CPU as C:CPU named it ('68040', '68LC040', '68EC020'); a name
    with EC or LC alone already says there is no FPU on a 68040/060. On a
    68040 or 68060 the FPU40 bit says the FPU works; the 68881/68882 bits
    beside it say its support library put the emulation in.
    """
    text_cpu = cpu
    if flags is None:
        if fpu_text:
            return Fpu(cpu, True, fpu_text)
        if re.search(r"68(?:EC|LC)0[46]0", cpu):
            return Fpu(cpu, False)
        return Fpu(cpu)
    if flags & AFF_68080:
        name = "68080"
    elif flags & AFF_68060 or "68060" in text_cpu:
        name = "68060"
    elif flags & AFF_68040:
        name = "68040"
    elif flags & AFF_68030:
        name = "68030"
    elif flags & AFF_68020:
        name = "68020"
    elif flags & AFF_68010:
        name = "68010"
    else:
        name = "68000"
    shown = text_cpu if text_cpu and text_cpu.endswith(name[2:]) else name
    if name == "68080":
        present = bool(flags & (AFF_FPU40 | AFF_68881 | AFF_68882))
        return Fpu(shown, present, "internal" if present else "", from_flags=True)
    if name in ("68040", "68060"):
        library = f"{name}.library"
        if flags & AFF_FPU40:
            return Fpu(shown, True, "internal", library,
                       emulation=bool(flags & (AFF_68881 | AFF_68882)), from_flags=True)
        if flags & (AFF_68881 | AFF_68882):  # some emulators set only these
            return Fpu(shown, True, "internal", library, emulation=True, from_flags=True)
        return Fpu(shown, False, from_flags=True)
    if flags & AFF_68882:
        return Fpu(shown, True, "68882", from_flags=True)
    if flags & AFF_68881:
        return Fpu(shown, True, "68881", from_flags=True)
    return Fpu(shown, False, from_flags=True)


def wants_loaded(fpu: Fpu) -> bool:
    """Only a 68040/060 needs the library list: for its support library, and to tell Emu68."""
    return bool(fpu.library) or fpu.cpu.endswith(("040", "060"))


def apply_loaded(fpu: Fpu, libraries) -> Fpu:
    """Fill in from LOADED (memory.Library entries): the support library, and Emu68 by its resource."""
    names = {lib.name.lower() for lib in libraries if lib.kind == "L"}
    if fpu.library:
        fpu.loaded = fpu.library in names
    if any(lib.kind == "R" and lib.name.lower() == EMU68_RESOURCE for lib in libraries):
        fpu.emulator = "Emu68"
    return fpu
