# Apollo V4 Stage 2B exclusive runbook — U-DAE first session

**Prepared:** 2026-11-21  
**Status:** Offline runbook only — **Stage 2B execution not authorised**  
**Parent docs tip:** `d449e2d`  
**Based on:** Stage 1 inventory, Stage 2A backup (`docs/APOLLO_V4_STAGE2A_RESULTS.md`), `docs/PROTOCOL.md`, `src/amigent/tls.py`, `src/amigent/amiga/amigent-update.rexx`, `src/native/amiga/daemon/amigentd.c`

This runbook tests **only U-DAE** (protected upstream contribution). Do not substitute F-DAE. Do not overwrite `C:amigentd`.

---

## Independent command control (hard gate)

| Requirement | Detail |
|-------------|--------|
| **Preferred / required method** | Direct AmigaOS **Shell on the V4 physical keyboard and display** |
| Why | After production `QUIT`, AmiGent cannot restart itself. Staging, stop, launch, and restore must not depend on the daemon under test. |
| Not accepted alone | Unverified second daemon, watchdog, remote recovery script, or “hope AmiGent recovers” |
| Other remote channels | **None independently verified** in Stage 1/2A evidence |

**Stage 2B remains blocked until the operator confirms**, as part of execution authorisation, that physical keyboard + display Shell access is available for the exclusive window and that they can type ARexx / Shell commands without AmiGent.

No automatic reboot is authorised. A controlled reboot is documented only as a last-resort recovery option under operator decision.

---

## Production baseline (Stage 2A)

| Item | Value |
|------|-------|
| Board / OS | V4-SA / ApolloOS / 68080 |
| Path | `C:amigentd` |
| Version | `amigentd 1.3` |
| Size / SHA-256 | 113324 / `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` |
| Startup | `RUN >NIL: C:amigentd TLSONLY` |
| PC backup | `~/amigent-evidence/stage2a-production-backup/20261121T010816Z/v4-production-C-amigentd.bin` |
| Drawer | `SYS:amigent/amigentd` matches `C:` |
| Protocol | **5** + TLS |

---

## Candidate (first exclusive session — U-DAE only)

| Item | Value |
|------|-------|
| ID | **U-DAE** |
| Size | **129844** |
| SHA-256 | `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` |
| Offline PC copy (preflight) | `/tmp/amigent-candidate-offline/amigentd.apollo.udae` (re-hash before use) |
| Staging path (proposed) | `Programs:AmiGent-Stage2B/amigentd.udae` |
| Must not use | `C:amigentd`, `C:amigentd.new`, Amigent-Update / `amigent-setup --update` |

`Programs:` had ≈678 MB free at Stage 1 — re-check free space before transfer.

---

## TLS and port model (source-verified)

From `docs/PROTOCOL.md` and `src/amigent/tls.py`:

| Role | Port when base `PORT` = **6801** (production default; no `PORT` on User-Startup) |
|------|----------------------------------------------------------------------------------|
| Plain protocol listener | **6801** (`DEFAULT_PORT`) |
| TLS listener | **6802** = **PORT+1** (`S:amigent-tls.pem` + AmiSSL) |
| PC client with pinned cert | Dials **port + 1** (TLS), never cleartext fallback when pin present |
| `TLSONLY` | Remote plain connections get hello flag `4` and close; localhost plain still used by TLS pump |

Production Stage 1/2A succeeded with pinned `~/.config/amigent/tls-*.pem` → PC traffic was on **TLS / 6802**, not “TLS on 6801”.

TLS material (existence confirmed Stage 2A; do not dump keys):

- Amiga: `S:amigent-tls.pem`, default auth key `S:amigent.key`
- PC: pinned cert under `~/.config/amigent/`

Candidate launch must include **`TLSONLY`** to match production locking behaviour. Default key file path applies when `KEY` is omitted (same as production User-Startup).

---

## Supported start / stop commands

### Stop (production or candidate owning ARexx `AMIGENT`)

Source: `PROTOCOL.md` ARexx `QUIT` → reply `bye`, then exit as Ctrl-C; used by `amigent-update.rexx`:

```rexx
ADDRESS AMIGENT 'QUIT'
```

At the **independent Shell**, run that via ARexx (same mechanism as the update script). Do not invent alternate CLI flags.

Poll until the ARexx port is gone (update script waits up to 15 s):

```rexx
/* conceptual: same check as amigent-update.rexx */
SHOW('P', 'AMIGENT')  /* must become false */
```

Also confirm from the PC: TLS connect to configured host:**6802** fails (and plain remote 6801 does not yield a usable AmiGent channel under `TLSONLY`).

If `AMIGENT` remains after the wait → treat as **`busy`** (update script changes nothing). **Stop Stage 2B.** Do not launch the candidate. Report. Optional operator-controlled reboot only if restoring a usable state requires it — not automatic.

### Launch candidate (after staging + hash OK + production stopped)

Match update-script launch style and production args. Prefer current directory `SYS:` (update.rexx sets this so the daemon does not hold a lock on the staging drawer):

```text
Protect Programs:AmiGent-Stage2B/amigentd.udae +e
Run <NIL: >NIL: Programs:AmiGent-Stage2B/amigentd.udae TLSONLY
```

(Equivalent background form used at boot: `RUN >NIL: … TLSONLY`.)

Do **not** pass `PORT` unless intentionally avoiding 6801; first session uses default **6801** / TLS **6802** once production has quit.

### Restore production (after candidate stop)

```text
Run <NIL: >NIL: C:amigentd TLSONLY
```

`C:amigentd` bytes must still be the Stage 2A image (never overwritten). Verify from PC: protocol **5**, TLS, `sysinfo()` spot-check.

### Stop candidate

Same ARexx `ADDRESS AMIGENT 'QUIT'` once the candidate owns `AMIGENT`.

---

## Shared hooks and reboot risk

| Topic | Finding |
|-------|---------|
| Hooks semaphore | `"amigent hooks 1"` — single owner |
| On clean exit | `hooks_stop()` → `unhook_all()`; traces cleared |
| Residual | LVO stubs may remain with cleared function pointers after owned unhook |
| Second PORT | Not isolation for hooks / AUDIO / monitor — not used in this session |
| Reboot | **Not required** on happy path. Consider **operator-controlled** reboot only if: QUIT stuck/`busy`, ports remain occupied, unexpected hook/resource behaviour, or production will not restart cleanly. Do not loop recovery experiments. |

---

## Corrected Stage 2B sequence (U-DAE)

Any candidate staging write and any production interruption require **Stage 2B authorisation**. Until then, do not run steps that write to the V4 or stop `AMIGENT`.

1. **Confirm independent Shell** (physical keyboard + display).  
2. Confirm production AmiGent responds (protocol 5 + TLS) — read-only.  
3. Re-verify PC production backup SHA-256 = `b00fef0e…`.  
4. Record startup: `RUN >NIL: C:amigentd TLSONLY`.  
5. Check staging free space (`Programs:` or chosen volume).  
6. **Transfer U-DAE** to `Programs:AmiGent-Stage2B/amigentd.udae` (AmiGent `put` / write API while production still up).  
7. **Read back** staged bytes to PC; verify size 129844 and SHA-256 `456fce26…`. Mismatch → **stop**, delete staging only if already authorised cleanup; do not QUIT production.  
8. Confirm recovery command ready at the console: `Run <NIL: >NIL: C:amigentd TLSONLY`.  
9. **Request / confirm final execution authorisation** for interruption (if not already covered).  
10. Stop production: ARexx `ADDRESS AMIGENT 'QUIT'`; wait until `AMIGENT` gone.  
11. Confirm ports released (ARexx gone; PC TLS **6802** dead).  
12. Launch staged candidate with `TLSONLY` (commands above).  
13. PC connect (pinned TLS → **6802**); expect protocol **6**.  
14. Approved read-only tests only (below).  
15. Stop candidate: `ADDRESS AMIGENT 'QUIT'`; confirm ports free.  
16. Relaunch `C:amigentd TLSONLY`.  
17. Verify protocol **5** + TLS.  
18. Final `sysinfo()`; record results; close PC client only.

**Order rule:** steps 6–7 **before** step 10. Never stage after production is down unless independent console + alternate transfer is already proven (not assumed).

---

## In-scope tests (narrow)

- Candidate launch and ARexx port acquisition  
- Protocol-6 handshake  
- TLS-only connectivity (pinned cert)  
- `sysinfo()`: ApolloOS, CPU 68080, AFF_FPGA / `attn_flags` if reported  
- Basic read-only volumes / `Version` as in Stage 1  
- Clean candidate shutdown  
- Production protocol-5 restoration  

## Out of scope

AUDIO, monitor, HRTmon, file writes (beyond staging already done), setup/update, PIP, PEEK/POKE, benchmarks, MMIO, F-DAE, overwrite of `C:amigentd`.

---

## Stop conditions

Halt candidate testing (and restore production when possible) if:

- Staged hash ≠ `456fce26…`  
- Production will not shut down cleanly (`busy` / port stuck)  
- Unexpected hook or resource behaviour  
- Candidate fails TLS or protocol negotiation (≠ 6)  
- Production restart command cannot be executed  
- V4 becomes unstable  

If restore fails: **halt**. Report observed state. Do not repeatedly experiment with recovery commands. Operator may choose a controlled reboot; this runbook does not authorise automatic reboot.

---

## Recovery procedure (console)

| Situation | Action |
|-----------|--------|
| Before production QUIT | Nothing to restore; optional delete of staging file only |
| Candidate running | `ADDRESS AMIGENT 'QUIT'` → `Run <NIL: >NIL: C:amigentd TLSONLY` |
| Candidate failed to start; ports free | `Run <NIL: >NIL: C:amigentd TLSONLY` |
| QUIT busy / port stuck | Do not launch candidate; report; optional operator reboot |
| Production file damaged (should not happen) | Restore bytes from PC backup via a **separately authorised** write — not part of happy-path 2B |

Never use Amigent-Update to load U-DAE (it overwrites `C:amigentd`).

---

## Evidence (outside Git)

Session directory example:

`~/amigent-evidence/stage2b-udae-exclusive/<session-UTC>/`

Record: binary id + SHA-256, timestamps, start/stop commands used, negotiated protocol, TLS status, SYSINFO, errors, whether reboot was needed, whether protocol-5 restore succeeded. Keep raw logs and binaries out of Git.

---

## Approval conditions still required

1. Operator confirms **physical Shell** access for the exclusive window.  
2. Explicit authorisation for **V4 writes** (staging U-DAE) and **temporary production interruption**.  
3. Confirmation that **only U-DAE** is in scope (not F-DAE).  
4. Acceptance of stop/recovery rules above (no Update swap; no automatic reboot).

---

## Checklist before dialling Stage 2B

- [ ] Stage 2A backup hash re-verified on PC  
- [ ] U-DAE offline hash re-verified  
- [ ] Physical console confirmed  
- [ ] Exclusive window scheduled (no competing input agents)  
- [ ] Staging path chosen; free space checked once live  
- [ ] Recovery command written at the console for immediate use  
- [ ] PC TLS pin present; expect connect on **6802**  
- [ ] Evidence directory prepared outside Git  
