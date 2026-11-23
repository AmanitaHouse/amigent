# Hardware acceptance — AmiGent 1.5.0 + Apollo candidate

**Procedure only.** Do not run this until separately authorised.
**Forbidden without new authorisation:** `amigent-setup --update`, daemon restart,
file transfer to the production Vampire V4, or any change to the live install.

| Field | Value |
|---|---|
| Candidate | `rehearse/integrate-150-apollo` @ `fa91b07` |
| Worktree | `D:\Development\per\amigent-worktrees\integrate-150-apollo-rehearsal` |
| Toolchain | ApolloCrossDev GCC-6.50-Stable (`Makefile.apollo`) |

## 1. Identities under test

| Artifact | Size | SHA-256 |
|---|---|---|
| `amigentd.apollo` (candidate) | 132140 | `0f1405a1d3494e1bebf6185030139c7858d5636a22cd565a8b432143c90c735d` |
| `amigent-apollo-probe` | 3108 | `ea78c8c508e2e3c12b719ac20ebf175a4805d34a3458e6a4882118ad417d2bb7` |
| `amigent-monitor.apollo` | 22804 | `e80c0456d63d435a57febd722caabdf7f1017c99985efa2e016d7f3c9a97bc96` |
| Classic `amigentd` (unchanged) | 118268 | `6d5f6d0e9e91b37eeb75c1d5fd379781826e587d82bd93fbf414656bd5d8466a` |
| Classic `amigent-monitor` | 18376 | `78b49713d9529bbe5804f02525f50bfc3e6431011ed9be0ae39c28643759b80e` |

Historical production / HW-smoke daemon (keep as rollback reference; superseded in code):

| Artifact | Size | SHA-256 |
|---|---|---|
| Known-good / prior smoke `amigentd.apollo` | 128744 | `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` |

Embedded version expected in the candidate daemon: `$VER: amigentd 1.5.0 (21.11.2026)`.

## 2. Preservation and recovery (before any change)

1. On the PC, copy the **currently installed** Amiga `C:amigentd` bytes (and
   `SYS:amigent/amigent-monitor` if present) to a dated offline folder. Record
   size and SHA-256.
2. Confirm the offline copy matches either `63db83ff…` (prior smoke) or another
   documented production digest. If it matches neither, **stop** and reassess.
3. Keep a bootable way to restore that exact file to `C:amigentd` without
   depending on the candidate package (Workbench / CF card / known-good spare).
4. Do **not** delete the spare restore path until acceptance is complete.

## 3. Authorised install path (when execution is later approved)

Prefer a **manual, reversible** install over `amigent-setup --update` until the
maintainer lifts that restriction:

1. Stop Hear / Viewer sessions on the PC.
2. On the Amiga, quit the running amigentd (or use a maintenance boot) so
   `C:amigentd` can be replaced offline.
3. Copy candidate `amigentd.apollo` → `C:amigentd` only after the SHA-256 check
   on the transfer media matches `0f1405a1…`.
4. Optionally copy `amigent-monitor.apollo` → `SYS:amigent/amigent-monitor`.
5. Start amigentd; do not run package `--update` against production in this gate.

## 4. Probe behaviour

1. Run packaged `amigent-apollo-probe` on ApolloOS with the 68080/`AFF_FPGA` bit set:
   - stdout contains `ApolloOS` and `68080`
   - exit code **0**
2. On AmigaOS (or ApolloOS without the FPGA bit):
   - exit code **5** (non-zero)
   - must **not** be treated as Apollo daemon selection for SETUP

## 5. Connection, protocol, TLS, sessions

1. From the candidate Viewer/server, connect to the Amiga.
2. Confirm protocol negotiation reaches protocol 6.
3. SYSINFO on the Apollo daemon: `audio=1`, `emu68` not advertising as the
   meaning of opcode 48 (client must use SYSINFO, never the opcode alone).
4. Confirm TLS / key behaviour matches the existing 1.5.0 install (same key
   folder; no forced re-key unless already required).
5. Open two Viewer sessions if available; confirm #51 session-aware identity
   (each session keeps its own daemon facts; disconnect clears that session’s
   cache only).

## 6. AUDIO / Hear

1. With `arne.audio` playing on ApolloOS, enable Viewer Hear.
2. Confirm framed PCM arrives; Hear OFF stops cleanly.
3. Disconnect / reconnect: Hear must not stay armed across a dead session.
4. Before any later update test, Hear must stop before daemon replacement
   (`stop_hear` ordering).

Failure: machine lockup, dump files under `T:audio-mem` / `T:audio-ptrs`, or
Hear that cannot be stopped from the Viewer.

## 7. Safety: MMIO, POKE deadline, TRACE

Offline-proven in source/tests; on hardware confirm:

1. PEEK/POKE of Apollo register windows is refused with the packaged refusal text.
2. Oversized / slow POKE payload does not hang the daemon beyond the wall-clock
   POKE deadline.
3. TRACE set is refused on this Apollo build (`tracepoints are not supported…`).

## 8. Apollo monitor selection

1. With `amigent-monitor.apollo` installed as `amigent-monitor`, open it on
   ApolloOS; confirm the agent-link window updates without taking input focus.
2. On a non-Apollo install path, classic `amigent-monitor` remains the file used.

## 9. Failure criteria → rollback

Rollback immediately (restore the preserved `C:amigentd` from §2) if any of:

- Boot failure, guru, or repeated daemon crash after install
- Loss of command channel / Viewer cannot reconnect
- AUDIO/Hear hard-locks the machine
- Probe exit 0 on a non-68080 ApolloOS-named system and selects Apollo daemon
- Any need to run emergency `--force` classic downgrade without a recorded plan

After rollback, re-verify connection with the restored digest before further tests.

## 10. Pass criteria (for a later GO to sync)

- Candidate daemon digest on Amiga is `0f1405a1…`
- Probe policy §4 observed
- Hear §6 observed without lockup
- Safety §7 observed
- Monitor §8 observed
- Rollback path §2 still available and tested once

## 11. Explicit non-goals of this document

- No authorisation to execute the steps above
- No fork `main` sync, PR publish, or upstream #46/#50 changes
- No claim that `0f1405a1…` has already been HW-validated (it has not)
