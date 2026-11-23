# Hardware acceptance — AmiGent 1.5.0 + Apollo candidate

**Procedure only.** Do not run this until separately authorised.

**Maintainer prohibition (in force for this gate):** do **not** run live
`amigent-setup --update` (or `--force`) against the production Vampire V4.
Do not restart the production daemon, transfer candidate files, or change the
live install until a later, explicit hardware-test authorisation says so.

| Field | Value |
|---|---|
| Candidate | `rehearse/integrate-150-apollo` @ `829831d` |
| Worktree | `D:\Development\per\amigent-worktrees\integrate-150-apollo-rehearsal` |
| Toolchain | ApolloCrossDev GCC-6.50-Stable (`Makefile.apollo`) |

## 1. Three daemon identities (do not conflate)

These are **different** artifacts. Rollback, smoke history, and the candidate
under test must be named separately.

| Role | What it is | Size (if known) | Full SHA-256 |
|---|---|---|---|
| **A. Production baseline** | Previously restored **production** protocol-5 / TLS daemon on the V4. This is the live recovery target unless §2 records a different *currently installed* digest. | (record on capture) | `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` |
| **B. Historical Apollo AUDIO smoke** | 1.4.0-era packaged `amigentd.apollo` used for earlier AUDIO hardware smoke. Superseded in candidate code (`SUPERSEDED_APOLLO_SHA256`). **Not** the production recovery baseline. | 128744 | `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` |
| **C. Candidate under test** | Rebuilt 1.5.0 Apollo daemon from this tree (`src/native` + `Makefile.apollo`). Packaged as `amigentd.apollo`. **Not** HW-validated yet. | 132140 | `0f1405a1d3494e1bebf6185030139c7858d5636a22cd565a8b432143c90c735d` |

Supporting candidate package artifacts (same build):

| Artifact | Size | Full SHA-256 |
|---|---|---|
| `amigent-apollo-probe` | 3108 | `ea78c8c508e2e3c12b719ac20ebf175a4805d34a3458e6a4882118ad417d2bb7` |
| `amigent-monitor.apollo` | 22804 | `e80c0456d63d435a57febd722caabdf7f1017c99985efa2e016d7f3c9a97bc96` |
| Classic `amigentd` (upstream 1.5.0, unchanged) | 118268 | `6d5f6d0e9e91b37eeb75c1d5fd379781826e587d82bd93fbf414656bd5d8466a` |
| Classic `amigent-monitor` | 18376 | `78b49713d9529bbe5804f02525f50bfc3e6431011ed9be0ae39c28643759b80e` |

Candidate embedded version: `$VER: amigentd 1.5.0 (21.11.2026)`.

## 2. Pre-flight: verify the V4’s *actual* installed daemon

**Mandatory before any authorised test.** Do not deploy identity **C** until this
section is completed and reconciled.

1. Read the bytes currently installed as the running daemon path (normally
   `C:amigentd`). Record size and **full** SHA-256 offline.
2. Also preserve, offline, the production configuration and backups that make
   that install work: at least `S:amigent.key` / `SYS:amigent` key copy,
   `ENVARC:amigent-home` (and spare if set), `SYS:amigent/` scripts and windows
   as present, TLS material the install uses, and any dated spare/`repair`
   copies already on the machine. Record paths and digests.
3. Compare the installed daemon digest to the table in §1:
   - If it equals **A** (`b00fef0e…`): production baseline confirmed; proceed
     only after separate hardware-test authorisation.
   - If it equals **B** (`63db83ff…`): the V4 is on the historical AUDIO smoke
     binary, **not** the documented production protocol-5/TLS baseline.
     **Stop.** Reconcile with the operator (restore **A**, or explicitly
     re-baseline production documentation) before any candidate deploy.
   - If it equals **C** (`0f1405a1…`): candidate already installed; **stop** and
     treat as an unexpected state until authorised.
   - If it matches **none** of A/B/C: **stop.** Capture the digest, reconcile
     the historical record, and do not deploy until the live identity and the
     rollback target agree in writing.
4. The rollback target for an authorised test is always the **bytes and config
   captured in this section** (expected to be **A**), never an assumption that
   **B** is “the” recovery image.

## 3. Preservation and recovery plan

1. Keep the §2 offline copies on non-V4 media until acceptance is finished.
2. Keep a restore path that does **not** use `amigent-setup --update`: e.g.
   Workbench / CF / known-good spare folder that can put the preserved
   `C:amigentd` bytes and keys back by hand.
3. On failure after an authorised install of **C**, restore the §2 daemon
   **and** the preserved keys/home/scripts/windows as captured—not a generic
   package default, and not identity **B** unless §2 proved **B** was what was
   actually installed.
4. After rollback, re-hash `C:amigentd` and confirm it matches the §2 capture
   before further work.

## 4. Authorised install path (only after hardware-test authorisation)

Still **without** live `amigent-setup --update`:

1. Stop Hear / Viewer sessions on the PC.
2. Quit the running amigentd on the Amiga (or use a maintenance boot) so
   `C:amigentd` can be replaced offline.
3. Copy candidate **C** → `C:amigentd` only after the transfer media hashes to
   the full digest  
   `0f1405a1d3494e1bebf6185030139c7858d5636a22cd565a8b432143c90c735d`.
4. Optionally copy `amigent-monitor.apollo` → `SYS:amigent/amigent-monitor`
   (hash `e80c0456d63d435a57febd722caabdf7f1017c99985efa2e016d7f3c9a97bc96`).
5. Start amigentd manually. Do **not** run `amigent-setup --update` or
   `--force` against production in this gate.

## 5. Probe behaviour

1. Run packaged `amigent-apollo-probe` on ApolloOS with the 68080/`AFF_FPGA` bit set:
   - stdout contains `ApolloOS` and `68080`
   - exit code **0**
2. On AmigaOS (or ApolloOS without the FPGA bit):
   - exit code **5** (non-zero)
   - must **not** select the Apollo daemon for SETUP

## 6. Connection, protocol, TLS, sessions

1. Connect with the candidate Viewer/server.
2. After **C** is installed: confirm protocol 6 and SYSINFO `audio=1` (opcode 48
   meaning comes from SYSINFO, never from the opcode alone).
3. While still on production **A** (pre-deploy checks only): confirm the existing
   protocol-5 / TLS behaviour still matches the preserved install—do not “fix”
   by updating.
4. Confirm keys/TLS still match the §2 preserved configuration (no forced
   re-key unless already required by that install).
5. If two Viewer sessions are available: #51 session-aware identity (per-session
   daemon facts; disconnect clears that session’s cache only).

## 7. AUDIO / Hear (after **C** is authorised and installed)

1. With `arne.audio` playing, enable Viewer Hear; confirm framed PCM; Hear OFF
   stops cleanly.
2. Disconnect / reconnect: Hear must not stay armed across a dead session.
3. Failure: machine lockup, `T:audio-mem` / `T:audio-ptrs` dumps, or Hear that
   cannot be stopped from the Viewer.

## 8. Safety: MMIO, POKE deadline, TRACE (after **C**)

1. PEEK/POKE of Apollo register windows refused with packaged refusal text.
2. Oversized / slow POKE does not hang past the wall-clock POKE deadline.
3. TRACE set refused (`tracepoints are not supported…`).

## 9. Apollo monitor selection (after **C**, if monitor copied)

1. `amigent-monitor.apollo` installed as `amigent-monitor` updates without
   taking input focus.
2. Non-Apollo path continues to use classic `amigent-monitor`.

## 10. Failure criteria → rollback

Restore §2 preserved daemon + configuration immediately if any of:

- Boot failure, guru, or repeated daemon crash after install of **C**
- Loss of command channel / Viewer cannot reconnect
- AUDIO/Hear hard-lock
- Probe exit 0 on a non-68080 ApolloOS-named system selecting Apollo daemon
- Installed digest after “rollback” does not match the §2 capture

Do **not** roll back by installing identity **B** unless §2 recorded **B** as
what was actually running.

## 11. Pass criteria (for a later sync decision)

- Pre-flight §2 completed; live identity reconciled to **A** (or a written
  re-baseline) before deploy
- After test: Amiga daemon digest is full `0f1405a1d3494e1bebf6185030139c7858d5636a22cd565a8b432143c90c735d`
- §§5–9 observed
- §2 rollback path still available and proven once
- No use of live `amigent-setup --update` during the gate

## 12. Explicit non-goals

- No authorisation, by this document alone, to execute §§4–9
- No fork `main` sync, PR publish, or upstream #46/#50 changes
- No claim that identity **C** is HW-validated
- No claim that identity **B** is the production recovery image
