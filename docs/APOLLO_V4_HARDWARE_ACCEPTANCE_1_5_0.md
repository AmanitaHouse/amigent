# Hardware acceptance — AmiGent 1.5.0 + Apollo candidate

**Documentation and operator procedure only.**  
This file does **not** authorise hardware execution. A separate, explicit
authorisation is required before any step labelled **HW-AUTH**.

**Maintainer prohibition (always in force for this gate):** do **not** run
live `amigent-setup --update` or `amigent-setup --force` (or any Amiga-side
`Amigent-Update` / `amigent-update.rexx` that replaces the daemon over the
network). Recovery and install steps below are **manual** and must work with
Workbench / AmigaShell / removable media if the network daemon is dead.

---

## 0. Immutable identities (do not conflate)

### 0.1 Revision metadata

| Field | Value | Notes |
|---|---|---|
| Integration / source baseline | `953f7d5` | Apollo+1.5.0 integration with parseable Viewer Hear JS; packages **C**. |
| Prior packaging baseline | `fa91b07` | Packaged Apollo rebuild / probe / monitor / identity (still valid for binaries). |
| Candidate package tree | worktree `integrate-150-apollo-rehearsal` on branch `rehearse/integrate-150-apollo` | Binaries under `src/amigent/amiga/bin/` |
| This procedure revision | `procedure-rev-2026-11-23-hear-pass` | Records completed RAM Hear PASS; no permanent install of **C**. |
| Live production digest | **A** verified on V4-SA 2026-11-23 | Pre-flight and post-restore: `b00fef0e…` |

### 0.2 Daemon identities

| Role | Meaning | Size | Full SHA-256 |
|---|---|---|---|
| **A** | Documented production protocol-5 / TLS daemon (recovery *target* if pre-flight matches) | (record at capture) | `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` |
| **B** | Historical 1.4.0 Apollo AUDIO smoke package; superseded in code; **not** production recovery | 128744 | `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` |
| **C** | New 1.5.0 Apollo candidate packaged as `amigentd.apollo` | 132140 | `0f1405a1d3494e1bebf6185030139c7858d5636a22cd565a8b432143c90c735d` |

Supporting package artifacts (same candidate tree):

| File | Size | Full SHA-256 |
|---|---|---|
| `amigent-apollo-probe` | 3108 | `ea78c8c508e2e3c12b719ac20ebf175a4805d34a3458e6a4882118ad417d2bb7` |
| `amigent-monitor.apollo` | 22804 | `e80c0456d63d435a57febd722caabdf7f1017c99985efa2e016d7f3c9a97bc96` |
| Classic `amigentd` (unchanged upstream 1.5.0) | 118268 | `6d5f6d0e9e91b37eeb75c1d5fd379781826e587d82bd93fbf414656bd5d8466a` |
| Classic `amigent-monitor` | 18376 | `78b49713d9529bbe5804f02525f50bfc3e6431011ed9be0ae39c28643759b80e` |

Candidate `$VER` string expected inside **C**: `amigentd 1.5.0 (21.11.2026)`.

### 0.3 Paths used by this product (from repository)

Verified against `src/amigent/setup.py`, `src/amigent/amiga/amigent-repair`, and daemon sources:

| Item | Typical path |
|---|---|
| Daemon executable | `C:amigentd` |
| Staging name used by setup (do **not** use setup) | `C:amigentd.new` (mentioned only for awareness) |
| Home folder | `ENVARC:amigent-home` or default `SYS:amigent` |
| Spare folder | `ENVARC:amigent-spare` (optional) |
| Key | `S:amigent.key` and `{home}/amigent.key` |
| TLS certificate | `S:amigent-tls.pem` and/or `{home}/amigent-tls.pem` |
| TLS-only marker | `{home}/amigent.tlsonly` (if present → User-Startup uses `C:amigentd TLSONLY`) |
| Windows | `{home}/amigent-monitor`, `{home}/amigent-status` (+ `.info`) |
| Scripts | `{home}/amigent-repair`, `amigent-scan`, `menu-add.rexx` |
| Launch line | `S:User-Startup` contains `RUN >NIL: C:amigentd` or `… TLSONLY` |

**Sensitive:** never print key/certificate contents in logs, chat, or git commits.

---

## 1. Command inventory (by environment)

Legend: **OFFLINE-OK** = verifiable without V4 · **HW-AUTH** = needs explicit hardware authorisation · **OPERATOR VERIFICATION REQUIRED** = syntax known from repo/docs but behaviour on this V4 must be confirmed before GO

### 1.1 Windows (PowerShell) — OFFLINE-OK

```powershell
# Length + SHA-256 of a file (candidate package or recovery copy)
Get-Item -LiteralPath 'PATH\TO\FILE' | Select-Object FullName, Length
(Get-FileHash -LiteralPath 'PATH\TO\FILE' -Algorithm SHA256).Hash.ToLower()

# Copy without replacing an existing recovery file
if (Test-Path -LiteralPath 'DEST') { throw 'DEST exists; refuse overwrite' }
Copy-Item -LiteralPath 'SRC' -Destination 'DEST'

# Dual recovery media (never overwrite)
Copy-Item -LiteralPath 'CAPTURE.bin' -Destination 'E:\amigent-recovery\C-amigentd.bin'
Copy-Item -LiteralPath 'CAPTURE.bin' -Destination 'F:\amigent-recovery\C-amigentd.bin'
```

### 1.2 WSL — OFFLINE-OK

```bash
sha256sum /mnt/.../FILE
wc -c /mnt/.../FILE
cmp /mnt/.../FILE1 /mnt/.../FILE2 && echo identical
```

### 1.3 AmigaShell / ApolloOS — OPERATOR VERIFICATION REQUIRED unless noted

Commands below appear in repository scripts (`amigent-repair`, `legacy.py`, setup install script). Confirm each returns the documented result on **this** V4 before installation of **C**.

```text
; Is amigentd running? (WARN ≈ not running — same pattern as amigent-repair)
Status >NIL: COMMAND=C:amigentd

; Process list line for Break (capture CLI number) — OPERATOR VERIFICATION REQUIRED
Status COMMAND=C:amigentd

; Version string of the installed file (does not replace SHA-256)
Version C:amigentd
Version FILE C:amigentd

; List home / keys existence (no content dump)
List C:amigentd
List S:amigent.key
List S:amigent-tls.pem
List ENVARC:amigent-home
List SYS:amigent

; Copy with protection bits (CLONE) — used by amigent-repair
Copy C:amigentd DF0:recovery/amigentd CLONE
Protect C:amigentd rwed

; Graceful quit via ARexx port AMIGENT (PROTOCOL.md / GUIDE) — needs running daemon
; From ARexx: address AMIGENT 'QUIT'
; From Shell if rx available: rx "address AMIGENT; QUIT"

; Force end if QUIT fails — OPERATOR VERIFICATION REQUIRED (legacy pattern)
; Break <cli-number> C
; where <cli-number> comes from: Status COMMAND=C:amigentd

; Start daemon (same as User-Startup / repair)
Run >NIL: C:amigentd
; or if amigent.tlsonly exists in home:
Run >NIL: C:amigentd TLSONLY

; Probe (after copying probe to a volume; writes only that path)
Protect T:amigent-apollo-probe +e
T:amigent-apollo-probe
; Expect exit 0 and stdout containing ApolloOS and 68080 on this FPGA V4
```

**Not available on AmigaOS (do not invent):** `sha256sum`, `md5`, Unix `cp`, bash.

### 1.4 PC AmiGent tools — HW-AUTH for live host; OFFLINE-OK for package checks

```text
; Forbidden for this gate:
amigent-setup --update …
amigent-setup --force …

; Allowed for read-only pre-flight IF already authorised later:
; Viewer/server connect to existing protocol-5 daemon (no package update)
```

SHA-256 of the live `C:amigentd` **cannot** be computed on the Amiga. Obtain bytes then hash on Windows/WSL (§2).

---

## 2. Pre-flight: measure the live V4 (HW-AUTH for access; no install)

**STOP** if any step fails. Do not proceed to §4.

### 2.1 Identify running daemon and launch path — HW-AUTH

**Environment:** AmigaShell on the V4 (physical keyboard / local display).

1. `Status >NIL: COMMAND=C:amigentd`  
   - No WARN → a process named `C:amigentd` is running.  
   - WARN → not running; record that and continue with file identity only.
2. `Type S:User-Startup` (or view in editor) and record the `C:amigentd` launch line (`TLSONLY` or not).
3. `List ENVARC:amigent-home` / `Type ENVARC:amigent-home` → record home path (default `SYS:amigent` if unset).
4. `Version C:amigentd` → record version text (informational only).

### 2.2 Capture installed daemon bytes without modifying production — HW-AUTH

Prefer **removable media** (CF / USB volume mounted as e.g. `DF0:` / `USB0:`) so recovery does not depend on AmiGent networking.

**Environment:** AmigaShell

```text
; Create a dated drawer on removable media (name as you prefer)
MakeDir DF0:amigent-capture-YYYYMMDD
Copy C:amigentd DF0:amigent-capture-YYYYMMDD/C-amigentd.bin CLONE
List DF0:amigent-capture-YYYYMMDD/C-amigentd.bin
```

**Integrity on Amiga (weak):** compare sizes with `List` of `C:amigentd` and the copy.  
**Strong integrity:** only after PC hash (§2.4).

**Alternative if a working AmiGent channel already exists (protocol-5 **A**):**  
OPERATOR VERIFICATION REQUIRED — use the existing Viewer/server **download** of `C:amigentd` to the PC **without** running setup/update. Confirm the tool performs a read-only GET. If unsure, use removable media only.

### 2.3 Preserve configuration inventory — HW-AUTH

Copy to the **same** capture drawer (CLONE). Do **not** open or log secrets.

```text
Copy S:amigent.key DF0:amigent-capture-YYYYMMDD/S-amigent.key CLONE
; if present:
Copy S:amigent-tls.pem DF0:amigent-capture-YYYYMMDD/S-amigent-tls.pem CLONE
Copy ENVARC:amigent-home DF0:amigent-capture-YYYYMMDD/ENVARC-amigent-home CLONE
; if spare set:
Copy ENVARC:amigent-spare DF0:amigent-capture-YYYYMMDD/ENVARC-amigent-spare CLONE
; home tree pieces actually present (adjust HOME from §2.1):
Copy HOME:amigent.key DF0:amigent-capture-YYYYMMDD/home-amigent.key CLONE
Copy HOME:amigent-tls.pem DF0:amigent-capture-YYYYMMDD/home-amigent-tls.pem CLONE
Copy HOME:amigent.tlsonly DF0:amigent-capture-YYYYMMDD/home-amigent.tlsonly CLONE
Copy HOME:amigent-monitor DF0:amigent-capture-YYYYMMDD/home-amigent-monitor CLONE
Copy HOME:amigent-status DF0:amigent-capture-YYYYMMDD/home-amigent-status CLONE
Copy HOME:amigent-repair DF0:amigent-capture-YYYYMMDD/home-amigent-repair CLONE
Copy S:User-Startup DF0:amigent-capture-YYYYMMDD/S-User-Startup CLONE
```

Record a written inventory: path on Amiga → filename on media → present/absent.

**STOP** if `S:amigent.key` is missing and the install uses a key (normal production).  
**STOP** if TLS-only install (`amigent.tlsonly` or User-Startup `TLSONLY`) but `amigent-tls.pem` is missing.

### 2.4 Transfer to Windows/WSL and hash — OFFLINE-OK after media is off the V4

**Environment:** Windows PowerShell (paths illustrative)

```powershell
$cap = 'E:\amigent-capture-YYYYMMDD\C-amigentd.bin'   # from the CF/USB
Get-Item -LiteralPath $cap | Format-List FullName, Length
$hash = (Get-FileHash -LiteralPath $cap -Algorithm SHA256).Hash.ToLower()
$hash
```

Optional WSL cross-check:

```bash
sha256sum /mnt/e/amigent-capture-YYYYMMDD/C-amigentd.bin
```

### 2.5 Reconcile identity — OFFLINE-OK

Compare `$hash` to §0.2:

| Result | Action |
|---|---|
| Equals **A** (`b00fef0e…`) | Production baseline confirmed. Continue to §3. |
| Equals **B** (`63db83ff…`) | **STOP.** Live machine is AUDIO smoke, not documented production. Reconcile/restore **A** before any candidate test. |
| Equals **C** (`0f1405a1…`) | **STOP.** Candidate already installed; unexpected. |
| Other | **STOP.** Record digest; do not deploy until written re-baseline. |

The **rollback target** is always the §2 capture bytes + config inventory, not an assumption that **B** is recovery.

### 2.6 Package hash check (candidate media) — OFFLINE-OK

On Windows, from the integration worktree (or a copied package folder):

```powershell
$bin = 'D:\Development\per\amigent-worktrees\integrate-150-apollo-rehearsal\src\amigent\amiga\bin'
@(
  'amigentd.apollo',
  'amigent-apollo-probe',
  'amigent-monitor.apollo'
) | ForEach-Object {
  $p = Join-Path $bin $_
  $h = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower()
  "{0} {1} {2}" -f $_, (Get-Item $p).Length, $h
}
```

**STOP** if any hash/size differs from §0.2.

---

## 3. Independent recovery prerequisites (mandatory before §4)

**STOP** before any replacement of `C:amigentd` unless **all** of the following hold.

### 3.1 Two verified recovery copies — OFFLINE-OK

```powershell
$src = 'E:\amigent-capture-YYYYMMDD\C-amigentd.bin'
$h = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLower()
# Must equal live capture from §2.4 / §2.5
foreach ($dest in @(
  'E:\amigent-recovery-1\C-amigentd.bin',
  'F:\amigent-recovery-2\C-amigentd.bin'   # second physical medium or independent volume
)) {
  if (Test-Path -LiteralPath $dest) { throw "Refuse overwrite: $dest" }
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  Copy-Item -LiteralPath $src -Destination $dest
  $h2 = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLower()
  if ($h2 -ne $h) { throw "Recovery copy mismatch: $dest" }
}
```

Also copy the **entire** capture drawer (keys/config) to both recovery locations without logging secrets.

### 3.2 Match to installed file

Already required in §2.4–2.5: recovery hash == installed capture hash == reconciled **A** (or written re-baseline).

### 3.3 Daemon-independent restore path — OPERATOR VERIFICATION REQUIRED

Cold restore must work with **no** AmiGent network daemon:

1. Boot Workbench / ApolloOS to a Shell (local display).  
2. Insert recovery medium.  
3. AmigaShell:

```text
; Example: restore daemon from DF0: recovery copy
Copy DF0:amigent-recovery-1/C-amigentd.bin C:amigentd CLONE
Protect C:amigentd rwed
; restore key/TLS if they were damaged (CLONE); do not Type them
Copy DF0:amigent-recovery-1/S-amigent.key S:amigent.key CLONE
Copy DF0:amigent-recovery-1/S-amigent-tls.pem S:amigent-tls.pem CLONE
; start
Run >NIL: C:amigentd
; or TLSONLY if that was the captured launch mode
```

4. Confirm with `Status >NIL: COMMAND=C:amigentd` (no WARN) and PC reconnect.

**Offline rehearsal (limitations documented):** Windows dual-copy + hash (§3.1) was rehearsed on disposable files without touching the V4. That proves PC-side copy/hash discipline only — **not** AmigaShell restore on this machine. AmigaShell restore remains **OPERATOR VERIFICATION REQUIRED** before GO.

### 3.4 Local recovery access

**STOP** if the operator cannot reach a local Shell/Workbench without the network daemon (no keyboard/display plan, sealed remote-only box, etc.).

---

## 4. Installation and restart (HW-AUTH only — do not execute in this documentation task)

Still **without** `amigent-setup --update` / `--force`.

### 4.1 Stage candidate on removable media — OFFLINE-OK then HW-AUTH to insert

```powershell
$bin = 'D:\Development\per\amigent-worktrees\integrate-150-apollo-rehearsal\src\amigent\amiga\bin'
$stage = 'E:\amigent-stage-C'
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item "$bin\amigentd.apollo" "$stage\amigentd.apollo"
Copy-Item "$bin\amigent-apollo-probe" "$stage\amigent-apollo-probe"
Copy-Item "$bin\amigent-monitor.apollo" "$stage\amigent-monitor.apollo"
# Re-hash staged copies; must match §0.2
```

### 4.2 Graceful shutdown — HW-AUTH · Amiga / PC

1. On PC: stop Viewer Hear / disconnect Viewer sessions.  
2. On Amiga (prefer ARexx while daemon still up):

```text
rx "address AMIGENT; QUIT"
```

OPERATOR VERIFICATION REQUIRED: confirm `rx` / ARexx port `AMIGENT` works on this install.

3. If still running:

```text
Status COMMAND=C:amigentd
; note CLI number N, then:
Break N C
```

4. Confirm: `Status >NIL: COMMAND=C:amigentd` → WARN.

### 4.3 Replace executable without touching recovery media — HW-AUTH

```text
; From staged volume, e.g. DF0:amigent-stage-C/
; Do NOT delete recovery copies on other media
Copy DF0:amigent-stage-C/amigentd.apollo C:amigentd CLONE
Protect C:amigentd rwed
List C:amigentd
```

Optional monitor:

```text
Copy DF0:amigent-stage-C/amigent-monitor.apollo SYS:amigent/amigent-monitor CLONE
Protect SYS:amigent/amigent-monitor rwed
```

(Adjust `SYS:amigent` to recorded home.)

### 4.4 Start candidate **C** — HW-AUTH

```text
Run >NIL: C:amigentd
; or TLSONLY if §2 recorded that mode
Status >NIL: COMMAND=C:amigentd
Version C:amigentd
```

Expect `$VER` / Version text mentioning `1.5.0`.

### 4.5 Confirm identity after install — HW-AUTH + OFFLINE hash if pulled again

Preferred strong check: copy `C:amigentd` out again to PC and hash → must be **C**  
`0f1405a1d3494e1bebf6185030139c7858d5636a22cd565a8b432143c90c735d`.

### 4.6 Restore production **A** (rollback) — HW-AUTH · no network daemon required

```text
; From recovery medium (example DF1:)
Copy DF1:amigent-recovery-1/C-amigentd.bin C:amigentd CLONE
Protect C:amigentd rwed
Copy DF1:amigent-recovery-1/S-amigent.key S:amigent.key CLONE
Copy DF1:amigent-recovery-1/S-amigent-tls.pem S:amigent-tls.pem CLONE
; restore home monitor/scripts if replaced
Run >NIL: C:amigentd
; or TLSONLY per capture
```

Then re-hash on PC; must match §2 capture.

---

## 5. Acceptance tests

### 5.1 Classification

| Test | When | Class |
|---|---|---|
| Package hashes §2.6 | Before any HW | **Mandatory · OFFLINE-OK** |
| Pre-flight identity §2 | Before install | **Mandatory · HW-AUTH** |
| Dual recovery §3 | Before install | **Mandatory · OFFLINE-OK + Amiga restore OPERATOR VERIFICATION REQUIRED** |
| Protocol-5 baseline connect | Before install, on **A** | **Mandatory · HW-AUTH · read-mostly** |
| Probe ApolloOS+FPGA (§5.2) | Before or after install | **Mandatory · HW-AUTH** (writes probe file to a volume) |
| Probe non-FPGA negative | — | **Offline/synthetic only** (do **not** require on this FPGA V4) |
| Protocol 6 + `audio=1` | After **C** | **Mandatory · HW-AUTH** |
| TLS reconnect | After **C** | **Mandatory · HW-AUTH** |
| Session identity (#51) | After **C** | **Mandatory if two sessions available · else note N/A** |
| Hear start/stop / disconnect | After **C** | **Mandatory · HW-AUTH** |
| Monitor selection | After **C** if monitor installed | **Optional · HW-AUTH** |
| MMIO/TRACE refuse via daemon | After **C** | **Mandatory · HW-AUTH · tightly bounded** |
| POKE deadline / hang | — | **Offline-only** (do not hang production) |
| Unbounded POKE / ALLOWPOKE to custom regs | — | **Forbidden** |

### 5.2 Probe (FPGA V4) — HW-AUTH

```text
Copy DF0:amigent-stage-C/amigent-apollo-probe T:amigent-apollo-probe CLONE
Protect T:amigent-apollo-probe +e
T:amigent-apollo-probe
```

**Expect:** exit code 0; stdout contains `ApolloOS` and `68080`.  
**STOP/ROLLBACK** if exit ≠ 0 on this known ApolloOS+FPGA machine after **C** is selected for install (mis-built probe).  
Delete `T:amigent-apollo-probe` when finished.

Non-FPGA negative case: covered by offline unit/source tests (`tests/test_apollo_probe_policy.py`); **not** required on this V4.

### 5.3 Protocol / TLS / sessions

**Before install (on A):** connect Viewer/server; confirm protocol **5** (or whatever §2 records), TLS as per `TLSONLY`/certificate presence; no update.

**After C:** connect; confirm protocol **6**; SYSINFO includes `audio=1`; opcode 48 meaning taken from SYSINFO only.  
Client baseline `fa91b07` uses `LOADED_PROTOCOL = 6`.

### 5.4 AUDIO / Hear — HW-AUTH after C

1. Start playback through `arne.audio`.  
2. Enable Viewer Hear; confirm PCM frames.  
3. Hear OFF; confirm stop.  
4. Disconnect Viewer; reconnect; Hear must not stay armed.  
**ROLLBACK** if Hear cannot stop or the machine hard-locks.

#### 5.4.1 Result — Viewer Hear end-to-end: **PASS — 23 November 2026**

Physical Vampire V4-SA (ApolloOS / 68080). Candidate **C** from RAM
(`0f1405a1…`, protocol 6 / TLS, SYSINFO `audio=1`). AmigaAMP looping an MP3
through the established ARNE/AHI path. AmiGent **1.5.0** Viewer (`953f7d5`
parseable `viewer.js`) with live video and visible Hear.

| Check | Result |
|---|---|
| Hear ON | Operator heard the MP3 on the PC; ~1.7 MB PCM in ~20 s |
| Hear OFF | PCM stopped (0 bytes) |
| Reconnect | Hear not left armed |
| Stop **C** / restore **A** | Protocol 5 / TLS; disk still **A** (`b00fef0e…`); User-Startup unchanged |

**Not** a permanent install of **C**. Protocol-only `audio_start`/`audio_stop` from
an earlier RAM run remains historical evidence only and is **not** this PASS
(see correction record under `D:\scratch\temp\amigent-ram-acceptance\`).

### 5.5 MMIO / TRACE — bounded hardware checks after C

These exercise the **daemon guard**. If the daemon is correct, the request is refused **before** custom-register access (see `apollo_mmio.c` comments on why unguarded reads are dangerous).

**Mandatory:**

1. **PEEK refuse:** request PEEK of Apollo-guarded address `0x00DFF1F4` length `2` (GFXMODE window).  
   **Expect:** error / refusal text containing  
   `that range includes Apollo registers that a read can change`  
   (or equivalent Apollo refuse path).  
   **STOP/ROLLBACK immediately** if the call succeeds or the machine glitches.

2. **TRACE refuse:** attempt TRACE set.  
   **Expect:** `tracepoints are not supported on this Apollo build yet`.

**POKE:**  
- **Offline-only:** deadline / oversized POKE behaviour (`POKE_DEADLINE_MS`, `PEEK_MAX`).  
- **Forbidden on production:** POKE into any `0x00DFF…` window, POKE with `ALLOWPOKE` toward custom regs, or intentional long-block tests.

### 5.6 Monitor — optional after C

Open `{home}/amigent-monitor`; confirm agent-link updates without taking input focus.

---

## 6. STOP / ROLLBACK conditions

### 6.1 STOP before installation

- Installed hash unexpected / cannot reconcile to **A** (or written re-baseline).  
- Running daemon path/launch line cannot be recorded.  
- Fewer than two verified recovery copies; hash mismatch; overwrite attempted.  
- No daemon-independent local Shell/Workbench recovery access.  
- Missing `S:amigent.key` / TLS material required by this install.  
- Candidate package hashes ≠ §0.2.  
- Any **OPERATOR VERIFICATION REQUIRED** AmigaShell command not confirmed on this V4.  
- Machine state differs from documented baseline.

### 6.2 ROLLBACK after installation

Restore §3 recovery image + config (§4.6) if:

- Daemon fails to start, crashes, or Status never clears WARN.  
- Connection or TLS fails vs preserved config.  
- Hear cannot stop safely / hard-lock.  
- Session identity wrong.  
- MMIO/TRACE refuse missing or unexpected hardware side effect.  
- Configuration drifts (User-Startup/key paths changed unintentionally).  
- Machine unstable.

### 6.3 Updater ban

No live `amigent-setup --update`, `--force`, or Amiga `Amigent-Update` / `amigent-update.rexx` during this gate.

---

## 7. Offline verification performed while authoring this revision

| Check | Result |
|---|---|
| Packaged **C** hash/size | `132140` / `0f1405a1d3494e1bebf6185030139c7858d5636a22cd565a8b432143c90c735d` |
| Probe / monitor package hashes | Match §0.2 |
| Windows dual-copy + `Get-FileHash` rehearsal | PASS on disposable files under `D:\scratch\temp\amigent-recovery-rehearsal\` (does **not** prove Amiga restore) |
| WSL `sha256sum` cross-check of same bytes | PASS |
| AmigaShell `Copy`/`Protect`/`Status`/`Run` patterns | Present in `amigent-repair` / `legacy.py` |
| ARexx `QUIT` | Documented in PROTOCOL.md / `amigent-update.rexx` |
| MMIO window `0xDFF1F4` | In `apollo_mmio.c` |
| Refusal strings in **C** binary | Present |
| Live V4 contact | **Performed 2026-11-23** under explicit operator GO (RAM **C** + Viewer Hear) |
| Viewer Hear end-to-end | **PASS** (§5.4.1); production left on **A** |

---

## 8. Remaining limitations

1. Candidate **C** was accepted from **RAM only**; it is **not** permanently installed.  
2. Permanent install of **C** (if ever authorised) still needs a separate GO and dual recovery.  
3. macOS app-bundle testing remains out of scope on Windows.  
4. Upstream PR **#46** (native layout) and **#50** (AUDIO draft) remain open on upstream; this tree carries native layout + validated Hear independently of merging those PRs blindly.

---

## 9. Hardware acceptance status (after 2026-11-23)

**RAM-based candidate + Viewer Hear:** **PASS** (§5.4.1).  
**Production:** restored to **A** (protocol 5 / TLS).  
**Permanent install of C:** **not authorised / not performed**.
