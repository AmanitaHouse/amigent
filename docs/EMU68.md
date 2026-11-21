# Emu68

[Emu68](https://github.com/michalsc/Emu68) runs the 68k code of an Amiga on a
Raspberry Pi: on a PiStorm, a PiStorm32 lite and similar boards. Much of what
matters when such an Amiga misbehaves sits on the Pi and is invisible from
AmigaOS. Amigent reads it through what Emu68 offers the Amiga side, and needs
amigentd 1.5.0 for it.

## What runs, and how the Pi is

`amiga_emu68` shows:

- Emu68's version, variant (such as `pistorm32lite`) and git hash,
- the Pi's model and memory,
- the boot options from `cmdline.txt`, with a word on those Emu68 documents,
- temperature, ARM clock and core voltage,
- whether the Pi reported under-voltage or throttling, now and since power on,
- the JIT cache (size, use, units, misses) and the 68k instructions so far,
- the JIT settings now,
- PiStormBoot and Emu68PWM, when they are there.

It changes nothing. A value the firmware does not give is left out.

`amiga_status` mentions under-voltage and throttling by itself: a weak power
supply is a common cause of freezes. `amiga_cpu` adds how many million 68k
instructions a second ran meanwhile and how often the JIT had to translate.

On an Amiga without Emu68 both tools say "not Emu68" and do nothing else.

### Where it comes from

- `devicetree.resource`, which Emu68 provides: `/emu68` (idstring, version,
  git-hash, variant), `/` (model), `/chosen` (bootargs).
- The Pi firmware's mailbox (through `mailbox.resource` when it is there, as
  EmuControl does): board revision, temperature, clocks, voltage, and the
  firmware's throttling flags.
- Emu68's control registers, read with MOVEC (see
  `docs/internals/ControlRegisters.md` in the Emu68 sources).

amigentd touches the control registers only after it found `/emu68` with an
idstring in the device tree. On any other 68k they would be illegal
instructions.

## JIT settings while the Amiga runs

Some games and demos run too fast or glitch under Emu68 until a JIT setting
is changed. `amiga_emu68_jit` changes them at once, with no restart:

| setting | short | what it does |
|---|---|---|
| `chip_slowdown` | `sc` | slow down code running from Chip RAM |
| `chip_slowdown_spacing` | `scs` | with it, only every n-th instruction (1-8) |
| `dbf_slowdown` | `dbf` | DBF busy loops in Chip RAM take real time (old MOD replayers) |
| `blitter_wait` | `bw` | wait for the blitter before the CPU writes to it |
| `ccr_depth` | `ccrd` | look-ahead of the CCR optimiser, 0 switches it off |
| `insn_depth` | `icnt` | most 68k instructions in one JIT unit (1-256) |
| `inline_range` | `irng` | branch inlining distance, 0 switches it off |
| `loop_count` | `lcnt` | loop unrolling (1-16) |
| `soft_flush` | `sf` | keep JIT units over a cache flush and check them |
| `soft_flush_limit` | `sfl` | above this many units a flush drops them all |

These are the fields Emu68 documents as changeable; other bits stay as they
are. The debug registers and the cache switch in CACR are not offered.
`insn_depth=1` is only taken together with `ccr_depth=0`, as Emu68's author
advises (Emu68 issues 144 and 232).

    amiga_emu68_jit()                                  what is set now
    amiga_emu68_jit("sc=1 dbf=1")                      change it
    amiga_emu68_jit(restore=True)                      back to before the first change
    amiga_emu68_jit("bw=1", program="Games:Foo/Foo", remember=True)

The values from before the first change are kept on the PC, next to the
notes. Nothing is written to the SD card: after a restart Emu68 starts with
what `cmdline.txt` says, and the saved values are dropped. PiStormBoot applies
its own JIT settings again at every start, so after a restart those are what
you see.

With `program=` the program runs as a job between two lines that set and put
back the settings:

    FailAt 2147483647
    "<amigentd>" EMU68JIT 1e0:3:3
    Games:Foo/Foo
    "<amigentd>" EMU68JIT ea:1f4:ffffffff,eb:1fff81:fffffff1,1e0:a0:ffb

so the Amiga restores them itself when the program ends, whatever it returns,
also when the PC is gone meanwhile. Should the job be broken off with
`amiga_break`, `restore=True` still puts the old values back. `remember=True` keeps the settings as an `amiga_note` for the
program, and the next `amiga_emu68_jit(program=...)` without settings uses them.
