"""Pack the Amiga side of a release as an .lha archive, using LhA on an Amiga.

Usage: make_release.py HOST

Needs a running amigentd or amigactld on HOST and LhA in its C: (AmiKit has it).
Writes dist/amigent.lha with an Amigent drawer: amigentd (68020),
amigentd.000 (68000) if built, the icon, Amigent-Update, ReadMe, Amigent.guide
and the licence,
and next to it amigent.readme for Aminet. Aminet wants the version in the
readme, not in the file name: uploading amigent.lha again replaces the last one.
The same archive goes to the GitHub release as amigent-<version>.lha.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "src" / "amigent" / "amiga" / "bin"
sys.path.insert(0, str(ROOT / "src"))

from amigent import __version__  # noqa: E402
from amigent.channel import Commands  # noqa: E402

README = f"""Amigent {__version__}

A remote desktop for your real Amiga, like TeamViewer or VNC, and an AI agent
that can work on it, both from a PC or Mac over the home network.
https://github.com/akustikrausch/amigent

This drawer is the Amiga half. The PC or Mac half comes from the internet.

On the Amiga

1. Copy this drawer to the Amiga, for example to RAM:.
2. Double-click amigentd, or run "amigentd SETUP" in a Shell.
   On a plain 68000 take amigentd.000 instead.

On the PC or Mac

3. Paste this into your AI agent (Claude, Codex or any other MCP client):

     Install Amigent from https://github.com/akustikrausch/amigent for me.

   The agent installs the Python package with "pipx install amigent", runs
   amigent-setup, which finds the Amiga on the network, copies amigentd to
   C:, adds it to S:User-Startup and gives it a key, and sets up the
   remote desktop as a program.

   Without an AI agent, in a terminal:

     pipx install amigent
     amigent-setup
     amigent-viewer --install

   The full guide is on the project page above.

Updating from an earlier Amigent: Amigent has two halves, amigentd on the
Amiga and the program on the PC or Mac. Update both. Easiest: paste this
into your AI agent:

     Update Amigent for me, both halves: run "pipx upgrade amigent" on this
     computer, then "amigent-setup --update" for the amigentd on my Amiga.
     Then tell me to restart you, so you get the new tools.

Or by hand:

- From the PC or Mac, both at once: "pipx upgrade amigent", then
  "amigent-setup --update", which puts the new amigentd on the Amiga.
- Or on the Amiga: copy this drawer over, double-click Amigent-Update.
  Then on the PC or Mac: "pipx upgrade amigent".

Afterwards restart the AI app and the remote desktop. Key, certificate and
the start line in S:User-Startup stay; should the new amigentd not start,
the old one starts again. One side alone keeps working as before, the new
features need both. From 1.5.0 on Amigent tells you when a new release is
out and offers the update.

Requirements: AmigaOS 2.04 or newer (encryption needs OS 3.0 and AmiSSL),
any CPU from the 68000 on (a Vampire's 68080 runs the plain amigentd), a
TCP/IP stack with bsdsocket.library. On the PC or Mac: Python 3.10 or newer.

Tool types of the icon: SETUP (accept the first install from the PC),
KEY=<file> (default S:amigent.key), PORT=<n> (default 6801), QUIET, TLSONLY,
ALLOWPOKE (let the agent write memory; off unless given).

amigent-monitor opens a window that shows, line by line, what the agent
does on this Amiga: the tools it calls, commands, files, clicks and keys,
next to the data rates and totals. Tool types: NAME=<your name> for the
greeting, WIDTH, HEIGHT, LEFT, TOP, FONT, SIZE. The window can be sized
and zoomed. Esc or the close gadget ends it, C clears the log.

amigent-status shows a small window with amigentd's state and its
connections, refreshed every 2 seconds. amigentd also answers ARexx on the
port AMIGENT: STATUS, CLIENTS, VERSION, PAUSE, RESUME, ACTIVATEWINDOW,
TYPE, KEY, BUSY, HELP, QUIT. PAUSE <seconds> stops all screen reading for that
long, so a test or a benchmark has the CPU to itself; RESUME ends it.
ACTIVATEWINDOW <pattern> brings a window to the front, TYPE <text> types
into it through your keymap (keys in angle brackets: <return>, <ctrl c>),
KEY <name> presses one key, BUSY says whether a menu or a popup holds
Intuition up.

Licence: MIT, see LICENSE.
"""


# Aminet files from before the archive lost its version number; they go away with
# the next upload. Empty this once Aminet shows only amigent.lha.
REPLACES = ""

AMINET_HEAD = f"""Short:        Remote desktop and AI agent for Amigas
Author:       Andreas Wendorf (Akustikrausch)
Uploader:     akustikrausch@gmail.com (Andreas Wendorf)
Type:         comm/net
Version:      {__version__}
""" + (f"Replaces:     {REPLACES}\n" if REPLACES else "") + """\
Architecture: m68k-amigaos >= 2.0.4
Distribution: Aminet
Requires:     a TCP/IP stack with bsdsocket.library, such as Roadshow
"""

AMINET_BODY = """
A REMOTE DESKTOP FOR YOUR REAL AMIGA, LIKE TEAMVIEWER OR VNC

Sit at your PC or Mac and use your Amiga as if it were in front of you: its
screen live in a window, your own mouse and keyboard on it, Amiga keys and
shortcuts on a side panel, files in either direction (drop them on the
window to send them) and one shared clipboard. No VNC server and no extra
software on the Amiga beyond this archive, and it stays quick even on a
7 MHz 68000 behind a plipbox.


AN AI AGENT THAT WORKS ON YOUR AMIGA, THROUGH MCP

An AI agent (Claude, Codex or any other MCP client) takes over the same
way: it runs commands, copies files, installs software and clicks through
programs, while you watch every click in that window and can take over at
any moment. It reads the screen as text where a picture isn't needed, can
take an installation back, explains a guru, sees which drivers really run,
and helps you develop: it builds C programs on the Amiga, reads their debug
output and sets tracepoints in them.

This archive is the Amiga half: amigentd, the small service that does the
work on the Amiga, amigent-status, a window that shows who is connected,
amigent-monitor, a window that shows what the agent is doing,
Amigent-Update for updating an earlier installation, and Amigent.guide, the
help for all of it. The PC or Mac half is a Python package:

    pipx install amigent

or just tell your AI agent: "Install Amigent from
https://github.com/akustikrausch/amigent for me." It then finds the Amiga on
the network and sets everything up from the PC.


NEW IN THIS VERSION

- Amigent notices a new release by itself, at most once a day, and offers
  it in the remote desktop and to the AI agent. Once you agree, one step
  updates both halves: the PC and every saved Amiga.
- Several Amigas: one AI agent drives every saved Amiga by its name, and
  the remote desktop switches between them from its Amiga menu.
- PiStorm and other Emu68 boards: what runs on the Raspberry Pi (Emu68
  version, temperature, under-voltage, JIT counters); JIT settings tried
  while the Amiga runs and kept per program; boot options and the Kickstart
  on the SD card changed with a backup; Emu68 updated from a release, with
  a way back and a rescue from the PC.
- The Pi's own Ethernet or Wi-Fi as a second network interface, on
  probation, and Emu68's serial debug output recorded on the PC.
- Graphics boards: card, driver, Warp3D and MiniGL, and the Picasso96
  screen modes with their colour depths, switched on and off with undo.
- PowerPC boards (CyberStorm PPC, Blizzard PPC): card, kernel and ROM,
  PowerPC crash windows in words, WarpOS programs built with vbcc. The
  classic PiStorm emulator under Linux, managed over SSH.
- The FPU is told from exec's own flags, and a program that needs an FPU
  is not started on an Amiga without one.
- The remote desktop has a new layout: an Amiga menu, a keyboard panel with
  tabs, a game mode that captures the mouse, a dark appearance, and an
  About page with the connection and the daemon. New languages: Russian,
  Greek and Turkish.
- amigentd turns graphics card screens into tiles faster and never packs
  on a 68000; with TLSONLY it stays closed to plain connections even when
  TLS fails. amigent-monitor runs on a 68000 again.
- amigent-setup --update renews the repair scripts as well and can keep a
  second Amigent folder on another disk.
- Thanks to reinauer, midwan and AmanitaHouse for their pull requests.


TUNED FOR SLOW AMIGAS AND SLOW NETWORKS

Chipset screens go out as the bitplanes the Amiga keeps anyway, graphics card
screens as tiles with their own small palette, and only what changed. Mouse
and keys are carried out at once, even while a picture is still on its way.

  68000 at 7 MHz, 640x256:  whole screen 0.6-1.0 s, unchanged 80 ms,
                            under 10% of the CPU while the PC watches
  68020 at 14 MHz:          whole screen 0.1 s, 2-3% of the CPU
  1920x1080 RTG on a plipbox (about 50 KB/s): whole screen about 3 s


INSTALLATION

1. Unpack the archive, e.g.  LhA x amigent.lha RAM:
2. Double-click amigentd (amigentd.000 on a plain 68000), or in a Shell:
       RAM:Amigent/amigentd SETUP
3. On the PC or Mac: pipx install amigent, then amigent-setup.
   It copies amigentd to C:, adds it to S:User-Startup and gives it a key.
4. For the remote desktop alone, no AI agent needed: amigent-viewer --install
   puts Amigent into the Start menu (Windows) or Applications (macOS).

A Vampire's 68080 runs the plain amigentd. Tool types and Shell arguments:
SETUP, KEY=<file>, PORT=<n>, QUIET, TLSONLY, ALLOWPOKE. amigentd answers
ARexx on the port AMIGENT (STATUS, CLIENTS, VERSION, PAUSE, RESUME,
ACTIVATEWINDOW, TYPE, KEY, BUSY, HELP, QUIT).


UPDATING FROM AN EARLIER AMIGENT

Amigent has two halves, amigentd on the Amiga and the program on the PC or
Mac. Update both. Easiest: paste this into your AI agent:

  Update Amigent for me, both halves: run "pipx upgrade amigent" on this
  computer, then "amigent-setup --update" for the amigentd on my Amiga.
  Then tell me to restart you, so you get the new tools.

By hand, from the PC or Mac, both at once: pipx upgrade amigent, then
amigent-setup --update. Or on the Amiga: unpack the archive, double-click
Amigent-Update in its drawer, then run pipx upgrade amigent on the PC.

Afterwards restart the AI app and the remote desktop. Key, certificate and
the start line in S:User-Startup stay. Should the new amigentd not start, the
old one starts again. One side alone keeps working as before; the new
features need both. From 1.5.0 on Amigent tells you when a new release is
out and offers the update.


REQUIREMENTS

AmigaOS 2.04 or newer, any CPU from the 68000 on, a network connection (a
plipbox on the parallel port is enough). Encrypted connections need OS 3.0
and AmiSSL 5.1 or newer. Updating on the Amiga needs ARexx (RexxMast). On
the PC: Windows, macOS or Linux with Python 3.10 or newer.


SECURITY

amigentd asks every connection for a key that amigent-setup creates, and with
AmiSSL it encrypts the connection with TLS, pinned to the certificate made for
this Amiga. Keep it in your home network; do not open its port to the
internet.


Source, documentation and the wire protocol:
https://github.com/akustikrausch/amigent

Licence: MIT.
"""


# The same help as an AmigaGuide document, for MultiView. Lines stay short: the
# guide is also read on a 640 pixel Workbench.
GUIDE_NODES = [
    ("MAIN", f"Amigent {__version__}", """
@{b}Amigent@{ub}: a remote desktop for your real Amiga, and an AI agent that
can work on it, both from a PC or Mac over the home network.

This drawer is the Amiga half. The PC or Mac half is a Python package
that comes from the internet.

  @{" Installation       " link INSTALL}  the first time
  @{" Updating           " link UPDATE}  from an earlier Amigent
  @{" amigentd           " link AMIGENTD}  tool types and Shell arguments
  @{" ARexx              " link AREXX}  the port AMIGENT
  @{" amigent-monitor    " link MONITOR}  watch what the agent does
  @{" amigent-status     " link STATUS}  who is connected
  @{" What the agent does" link AGENT}  and what is new
  @{" If it doesn't work " link TROUBLE}  the usual causes
  @{" Requirements       " link NEEDS}
  @{" Security           " link SECURITY}
  @{" Licence            " link LICENCE}

Source, the full guide and the wire protocol:
https://github.com/akustikrausch/amigent
"""),
    ("INSTALL", "Installation", """
@{b}On the Amiga@{ub}

1. Copy this drawer to the Amiga, for example to RAM:.
2. Double-click amigentd, or run "amigentd SETUP" in a Shell.
   On a plain 68000 take amigentd.000 instead.

It now waits for the PC. Nothing is installed yet.

@{b}On the PC or Mac@{ub}

3. Paste this into your AI agent (Claude, Codex or any other MCP
   client):

     Install Amigent from https://github.com/akustikrausch/amigent
     for me.

   The agent installs the Python package, finds the Amiga on the
   network, copies amigentd to C:, adds it to S:User-Startup, gives it
   a key and sets up the remote desktop as a program.

   Without an AI agent, in a terminal:

     pipx install amigent
     amigent-setup
     amigent-viewer --install

After that amigentd starts with the Amiga, and this drawer is no longer
needed, except for @{"amigent-monitor" link MONITOR} and @{"amigent-status" link STATUS}.
"""),
    ("UPDATE", "Updating from an earlier Amigent", """
Amigent has two halves, amigentd on the Amiga and the program on the PC
or Mac. Update both. Easiest: paste this into your AI agent:

  Update Amigent for me, both halves: run "pipx upgrade amigent" on
  this computer, then "amigent-setup --update" for the amigentd on my
  Amiga. Then tell me to restart you, so you get the new tools.

@{b}By hand, from the PC or Mac@{ub}

  pipx upgrade amigent
  amigent-setup --update

@{b}By hand, on the Amiga@{ub}

Double-click Amigent-Update in this drawer (it needs ARexx, RexxMast).
Then run "pipx upgrade amigent" on the PC or Mac.

Afterwards restart the AI app and the remote desktop. Key, certificate
and the start line in S:User-Startup stay. Should the new amigentd not
start, the old one starts again; the update waits up to a minute and a
half for the network port to become free.

One side alone keeps working as before; the new features need both.
From 1.5.0 on Amigent tells you when a new release is out and offers
the update.
"""),
    ("AMIGENTD", "amigentd", """
amigentd is the small service that does the work on the Amiga. Setup
copies it to C: and starts it from S:User-Startup.

Tool types of the icon, and the same words as Shell arguments:

  @{b}SETUP@{ub}        accept the first installation from the PC
  @{b}KEY=<file>@{ub}   the key file, default S:amigent.key
  @{b}PORT=<n>@{ub}     the TCP port, default 6801 (TLS on the next one)
  @{b}QUIET@{ub}        no output
  @{b}TLSONLY@{ub}      only encrypted connections from other computers
  @{b}ALLOWPOKE@{ub}    let the agent write memory (off unless given)

Ctrl-C ends it, and so does QUIT on its @{"ARexx port" link AREXX}.

amigentd.000 is the build for a plain 68000. A Vampire's 68080 runs the
plain amigentd.
"""),
    ("AREXX", "ARexx", """
amigentd answers on the port @{b}AMIGENT@{ub}:

  STATUS                   one line on its state
  CLIENTS                  who is connected
  VERSION                  name, version and date
  PAUSE <seconds>          stop all screen reading for that long, so a
                           test or a benchmark has the CPU to itself
  RESUME                   end the pause
  ACTIVATEWINDOW <pattern> bring a window to the front
  TYPE <text>              type into it through your keymap; keys in
                           angle brackets: <return>, <ctrl c>
  KEY <name>               press one key
  BUSY                     whether a menu or a popup holds Intuition up
  HELP                     this list
  QUIT                     end amigentd

From a Shell:  rx "address AMIGENT; 'STATUS'; say result"
"""),
    ("MONITOR", "amigent-monitor", """
A window that shows, line by line, what the agent does on this Amiga:
the tools it calls, commands, files, clicks and keys, next to the data
rates, totals and free memory.

Tool types: NAME=<your name> for the greeting, WIDTH, HEIGHT, LEFT, TOP,
FONT, SIZE. The window can be sized and zoomed. Esc or the close gadget
ends it, C clears the log.

While the agent measures how windows move, the monitor stays still, so
it doesn't spoil the measurement.
"""),
    ("STATUS", "amigent-status", """
A small window with amigentd's state and its connections, refreshed
every 2 seconds. Tool type: PORT=<name> of the ARexx port to watch,
default AMIGENT.
"""),
    ("AGENT", "What the agent does", """
Through the remote desktop you use the Amiga yourself from the PC or
Mac: live screen, mouse, keyboard, files in both directions, one
clipboard.

An AI agent (Claude, Codex or any other MCP client) works the same way,
while you watch: it runs commands, copies files, installs software and
can take an installation back, clicks through programs, reads the
screen as text, fetches programs from Aminet, and builds and tests C
programs on the Amiga.

@{b}New in this version@{ub}

- Amigent notices a new release and offers to update both halves.
- One AI agent drives several saved Amigas, each by its name.
- PiStorm and other Emu68 boards: what runs on the Pi, JIT settings
  while the Amiga runs, boot options and Kickstart on the SD card with a
  backup, and Emu68 updates with a way back.
- Graphics boards and their screen modes; PowerPC boards.
- The FPU is told from exec's own flags.
- The remote desktop has a new layout, a game mode, a dark appearance,
  and Russian, Greek and Turkish.
- amigent-monitor runs on a 68000 again.

All tools are listed in the guide on the project page.
"""),
    ("TROUBLE", "If it doesn't work", """
@{b}The PC doesn't find the Amiga@{ub}
Is the TCP/IP stack running, and does the Amiga have an address? Ping
it from the PC. Then give the address: amigent-setup <address>.

@{b}"refused the key"@{ub}
The key on the PC and S:amigent.key on the Amiga differ. Run
"amigentd SETUP" on the Amiga and amigent-setup on the PC again.

@{b}The remote desktop keeps trying@{ub}
From 1.4.0 the page and the terminal say why. Small things work but a
whole screen never arrives: a network driver that drops large packets.

@{b}A new window doesn't open@{ub}
A menu or a popup is open and holds Intuition up. Press Esc.

@{b}After an update the new tools are missing@{ub}
Restart the AI app; it reads the list of tools when it starts.

More in the FAQ on the project page.
"""),
    ("NEEDS", "Requirements", """
AmigaOS 2.04 or newer, any CPU from the 68000 on, a network connection
with a TCP/IP stack that has bsdsocket.library (a plipbox on the
parallel port is enough). Encrypted connections need OS 3.0 and AmiSSL
5.1 or newer. Amigent-Update needs ARexx (RexxMast).

On the PC or Mac: Windows, macOS or Linux with Python 3.10 or newer.
"""),
    ("SECURITY", "Security", """
amigentd asks every connection for a key that amigent-setup creates,
and with AmiSSL it encrypts the connection with TLS, pinned to the
certificate made for this Amiga. With TLSONLY it takes nothing else
from other computers.

Keep it in your home network; do not open its port to the internet.
"""),
    ("LICENCE", "Licence", """
MIT, see the file LICENSE in this drawer.

Andreas Wendorf (Akustikrausch)
https://github.com/akustikrausch/amigent
"""),
]


def amiga_guide(date: str) -> str:
    """The AmigaGuide document; date as in a version string, 18.11.2026."""
    out = ["@database Amigent.guide", f"@$VER: Amigent.guide {__version__} ({date})",
           "@author Andreas Wendorf", "@remark made by scripts/make_release.py", ""]
    for name, title, body in GUIDE_NODES:
        out += [f'@node {name} "{title}"', *([] if name == "MAIN" else ['@toc MAIN']), body.strip("\n"), "@endnode", ""]
    text = "\n".join(out)
    assert all(len(line) <= 100 for line in text.splitlines()), "keep guide lines short"
    return text


def aminet_readme() -> str:
    text = AMINET_HEAD + AMINET_BODY
    short = text.splitlines()[0].split(":", 1)[1].strip()
    assert len(short) <= 40, "Aminet allows 40 characters in Short:"
    assert all(len(line) <= 78 for line in text.splitlines()), "keep readme lines short"
    return text


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    host = sys.argv[1]
    ctl = Commands(host, timeout=120)
    stage = "RAM:amigent-release"
    folder = f"{stage}/Amigent"
    ctl.exec(f"Delete >NIL: {stage} ALL QUIET")
    ctl.makedir(stage)
    ctl.makedir(folder)
    files = {"amigentd": BIN / "amigentd", "amigentd.info": BIN / "amigentd.info",
             "LICENSE": ROOT / "LICENSE"}
    if (BIN / "amigent-status").exists():
        files["amigent-status"] = BIN / "amigent-status"
        files["amigent-status.info"] = BIN / "amigent-status.info"
    if (BIN / "amigent-monitor").exists():
        files["amigent-monitor"] = BIN / "amigent-monitor"
        files["amigent-monitor.info"] = BIN / "amigent-monitor.info"
    if (BIN / "amigentd.000").exists():
        files["amigentd.000"] = BIN / "amigentd.000"
        files["amigentd.000.info"] = BIN / "amigentd.info"
    amiga = ROOT / "src" / "amigent" / "amiga"
    for name in ("Amigent-Update", "Amigent-Update.info", "amigent-update.rexx"):
        files[name] = amiga / name
    for name, source in files.items():
        ctl.write_file(f"{folder}/{name}", source.read_bytes())
    ctl.write_file(f"{folder}/ReadMe", README.encode("iso-8859-1"))
    ctl.write_file(f"{folder}/Amigent.guide", amiga_guide(time.strftime("%d.%m.%Y")).encode("iso-8859-1"))
    ctl.write_file(f"{folder}/Amigent.guide.info", (amiga / "Amigent.guide.info").read_bytes())
    ctl.write_file(f"{stage}/Amigent.info", (BIN / "Amigent.info").read_bytes())
    for name in ("amigentd", "amigentd.000", "amigent-status", "amigent-monitor"):
        if name in files:
            ctl.exec(f"Protect {folder}/{name} +rwed")
    archive = "amigent.lha"
    result = ctl.exec(f"LhA -r -x -q a {stage}/{archive} Amigent Amigent.info", cd=stage, timeout=120)
    if result.rc > 5:
        raise SystemExit(f"LhA said {result.rc}:\n{result.output}")
    data = ctl.read_file(f"{stage}/{archive}")
    ctl.exec(f"Delete >NIL: {stage} ALL QUIET")
    out = ROOT / "dist" / archive
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(data)
    (out.parent / f"amigent-{__version__}.lha").write_bytes(data)
    (out.parent / "amigent.readme").write_text(aminet_readme(), encoding="iso-8859-1")
    print(f"{out} ({len(data)} bytes), amigent-{__version__}.lha for GitHub, amigent.readme")


if __name__ == "__main__":
    main()
