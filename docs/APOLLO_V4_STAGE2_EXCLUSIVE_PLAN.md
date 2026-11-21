# Apollo V4 Stage 2 exclusive validation plan

**Prepared:** 2026-11-21  
**Based on Stage 1:** `docs/APOLLO_V4_STAGE1_INVENTORY_RESULTS.md` (session `20261121T005910Z`)  
**Docs branch tip at preparation parent:** `6c87c22`  
**Stage 2A results:** `docs/APOLLO_V4_STAGE2A_RESULTS.md` (session `20261121T010816Z`)  
**Status:** Stage 2A executed under separate authorisation. **Stage 2B not authorised by this document.**

Stage 1 established: V4-SA, ApolloOS, SYSINFO CPU 68080, AFF_FPGA bit present, Kickstart 51.51, **production protocol 5 + TLS**, `AMIGENT` public, production remained responsive, **no `self=` path**.

Stage 2A established (disk-file): `C:amigentd` = `amigentd 1.3`, 113324 bytes, SHA-256 `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3`; User-Startup `RUN >NIL: C:amigentd TLSONLY`; drawer `SYS:amigent/amigentd` matches; production still responsive after backup.

## Offline findings: startup and shutdown

Sources: `docs/PROTOCOL.md`, `docs/FAQ.md`, `docs/GUIDE.md`, `src/amigent/setup.py`, `src/amigent/amiga/Amigent-Update`, `src/amigent/amiga/amigent-update.rexx`, `src/native/amiga/daemon/amigentd.c`.

| Topic | Finding |
|-------|---------|
| Normal launch | FAQ: only `amigentd` from **`S:User-Startup`**. Setup appends `RUN >NIL: C:amigentd` (optional args later). |
| Executable path | Installed as **`C:amigentd`**. Setup also copies into `{home}/` (`ENVARC:amigent-home` or `SYS:amigent`). |
| Startup args | Read by `amigent-update.rexx` from the User-Startup line containing `C:amigentd` (e.g. `TLSONLY`, `KEY=…`). Tool types on Workbench icons: `PORT`, `SETUP`, `KEY`, `QUIET`, `TLSONLY`, … |
| Default port / TLS | Default listen **6801**; TLS on **PORT+1**. Key file default **`S:amigent.key`**. PC pins cert under `~/.config/amigent/`. |
| Supported stop | ARexx **`ADDRESS AMIGENT 'QUIT'`** → reply `bye`, then exit as on Ctrl-C (`PROTOCOL.md`). Used by `amigent-update.rexx` before swap. |
| After QUIT | `hooks_stop()` runs; owner releases `"amigent hooks 1"`. Tracepoints cleared. Stubs may remain in LVO chain but hook function pointers cleared when owned. |
| If QUIT fails | Update script reports **`busy`** and changes nothing. Older builds without ARexx port need **reboot** after file swap (`reboot` outcome). Stage 1 saw `AMIGENT` → QUIT is the expected path. |
| Restore without new software | Keep original **`C:amigentd` bytes untouched** on PC; after candidate exits, `Run <NIL: >NIL: C:amigentd` + **same User-Startup args**. No package install required. |
| Candidate handshake failure | Leave production file in place; do not run Update swap. Re-launch `C:amigentd` with recorded args; if port stuck, wait (daemon retries ~1 minute on busy port) or reboot as last resort. |

**Second PORT is not process isolation** for hooks, ARNE/AUDIO, or `Amigent.monitor`. Exclusive session is the Stage 2B default.

## Feasibility: exclusive candidate without overwriting production

**Yes, if Stage 2A succeeds.** Preferred pattern:

1. PC holds backup of production `C:amigentd` bytes + User-Startup amigent line + knowledge of `KEY`/`TLSONLY`.  
2. Stage candidate to a **non-`C:amigentd`** path (e.g. under `Programs:` or Amigent home test drawer) via V4←PC transfer only when Stage 2B is approved.  
3. `ADDRESS AMIGENT 'QUIT'`; wait until `AMIGENT` is gone.  
4. Launch candidate: `Run <NIL: >NIL: <candidate-path> KEY S:amigent.key` (+ same TLSONLY/PORT as production if required). Prefer **PORT 6801** for client compatibility once production has quit.  
5. Test; `QUIT` candidate; `Run` production `C:amigentd` with original args.  

**Reboot:** not required for the happy path. Document reboot if QUIT fails, port remains occupied, or hooks/resources behave unexpectedly after stop.

**Do not** use `amigent-setup --update` / Amigent-Update for Stage 2B candidate tests — those **overwrite `C:amigentd`**.

---

## Stage 2A — Production executable identification (read-only)

**Requires separate approval for another V4 connection.** No stop, no candidate, no writes to Amiga volumes except none — transfers are **V4 → PC only**.

### Proposed operations (not executed in this preparation)

Use existing TLS production connection (`V4SA`). Prefer AmiGent `Commands` / `exec` / `read_file` / `stat` as implemented.

| # | Purpose | Proposed call / command | Notes |
|---|---------|-------------------------|-------|
| 2A.1 | Startup line | `exec` reading User-Startup safely, e.g. search/list lines containing amigentd | Record full amigent line; redact secrets if any appear |
| 2A.2 | Home drawer | `read_file("ENVARC:amigent-home")` or treat missing as `SYS:amigent` | Path only |
| 2A.3 | Installed Version | `Version "C:amigentd"` | Quote path |
| 2A.4 | File metadata | `stat("C:amigentd")` / List as supported by API | Size/date if available |
| 2A.5 | **PC-side backup** | `read_file("C:amigentd")` → save under `~/amigent-evidence/…` | SHA-256 on PC; **never** write copy back to V4 |
| 2A.6 | Drawer copy Version | If home has `amigentd`, Version that path; optional read if differs | Distinguish copies |
| 2A.7 | Key/cert paths (existence) | Confirm `S:amigent.key` via `stat` only — **do not** dump key material into Git | Redact |
| 2A.8 | Monitor presence | `stat` / List home `amigent-monitor` — do not launch | |
| 2A.9 | Responsiveness | Final `sysinfo()` | Confirm still protocol 5 |

**Caveat:** Disk bytes at `C:amigentd` are **not** proof the running image matches after an incomplete update; Stage 1 had no `self=`. After 2A.5, treat PC hash as **installed-file** identity.

### Still requiring live V4 / Stage 2B

- Whether QUIT is answered promptly (smoke only in 2B).  
- Free space on staging volume at the moment of candidate upload (Stage 1 had Programs: free ≈ 678 MB).  
- Running-image ≡ disk-file proof (protocol 5 has no `self=`).

---

## Stage 2B — Exclusive protocol-6 candidate tests

**Requires approval for temporary production interruption and candidate execution.**

### Binaries (test separately)

| ID | Role | Size | SHA-256 |
|----|------|-----:|---------|
| U-DAE | Protected contribution | 129844 | `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` |
| F-DAE | Fork package | 131292 | `1e0e3f65d46b62c93f7986d8137120ef5e2dec2515a9b63f6aa5909d2e75e9ca` |

Offline PC copies for U-DAE may already exist under `/tmp/amigent-candidate-offline/` from preflight; re-verify hashes before upload.

### Sequence (per binary, after 2A backup verified)

1. Confirm PC backup hash of production `C:amigentd` and recorded startup args.  
2. Confirm restore command rehearsed on paper: `Run <NIL: >NIL: C:amigentd` + args.  
3. Exclusive window: no other agents driving mouse/keyboard.  
4. `ADDRESS AMIGENT 'QUIT'`; wait until ARexx port `AMIGENT` gone (poll via Amiga Shell/`show` or lost TCP).  
5. Confirm production TCP 6801 no longer answers AmiGent hello.  
6. Upload **one** candidate to a non-production path; `Protect … +e`; launch with `KEY S:amigent.key` and production-equivalent TLSONLY/PORT.  
7. From PC: connect, record protocol (expect **6**), SYSINFO, volumes, Version; **read-only** only.  
8. `QUIT` candidate; confirm port free.  
9. Restore: launch `C:amigentd` with original args.  
10. Verify PC: protocol **5**, TLS, SYSINFO spot-check vs Stage 1.  

Repeat steps 4–10 for the other binary in a **separate** session or clearly separated report rows. Never conflate U-DAE and F-DAE results.

### In scope for 2B (once approved)

Handshake, SYSINFO, basic read-only commands/files as already used in Stage 1, TLS behaviour observation.

### Out of scope for 2B (Stage 3)

AUDIO / Hear, monitor start, HRTmon, update/fallback, ALLOWPOKE, MMIO writes, PIP experiments, `amigent-setup --update`.

---

## Stage 3 — Apollo-specific (later)

Separate authorisations for AUDIO, monitor, HRTmon, update/fallback. Host harness remains preferred for MMIO window refusal.

---

## Preflight checklist (before any Stage 2A/2B contact)

- [ ] Stage 1 evidence retained under `~/amigent-evidence/stage1-inventory/20261121T005910Z/`  
- [ ] PC evidence directory created for 2A/2B (outside Git)  
- [ ] U-DAE / F-DAE / probe hashes re-verified offline  
- [ ] Client git SHA recorded  
- [ ] User-Startup amigent line captured (2A)  
- [ ] Production `C:amigentd` PC SHA-256 captured (2A)  
- [ ] Restore command documented with exact args (2A→2B)  
- [ ] QUIT / busy / reboot failure branches understood  
- [ ] No Update/setup scripts in the candidate path  
- [ ] Immediate stop if: QUIT fails, restore fails, unexpected protocol, TLS break, or production will not return  

### Rollback (supported mechanisms)

| Situation | Action |
|-----------|--------|
| Candidate not started | Nothing to roll back |
| Candidate running | ARexx `QUIT` on its port name; then `Run` `C:amigentd` + original args |
| Candidate left `C:` untouched but port stuck | Wait; retry production launch; reboot if still busy |
| Mistaken use of Update swap | `C:amigentd.old` may exist — copy back only if that file was created and matches PC backup; prefer restoring from **PC backup** via approved write of known-good bytes |

### Immediate termination conditions

QUIT does not clear `AMIGENT` within documented wait; restore launch fails; production returns protocol ≠ 5 or TLS fails; any unapproved write path invoked; unexplained OS/hardware error.

---

## Approval gates

| Stage | Approves |
|-------|----------|
| **2A** | Another V4 connection; read-only inventory + V4→PC file read of `C:amigentd` (and listed config reads). No stop, no candidate. |
| **2B** | Exclusive interruption; QUIT production; launch **one** named candidate (U-DAE or F-DAE); restore; verify protocol 5. |
| **3** | AUDIO / monitor / HRTmon / update tests — separately. |
