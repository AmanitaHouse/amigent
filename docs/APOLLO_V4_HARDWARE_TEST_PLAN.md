# Apollo V4 hardware validation plan

**Plan date:** 2026-11-21  
**Audit commit (fork `main`):** `79880b8f018ae735715de4f1d0e943acf4462dcd`  
**Status:** Preparation only — **no V4 contact authorised by this document**

Source of truth for ports, tool types and second-instance behaviour: `docs/PROTOCOL.md`, `docs/GUIDE.md`, `src/amigent/setup.py`, `src/amigent/viewer.py`, `src/amigent/server.py`, `src/amigent/doctor.py`, `src/amigent/hrtmon.py`.

## Binary matrix (must record per result)

| ID | Artifact | Size (bytes) | SHA-256 | Role |
|----|----------|-------------:|---------|------|
| F-DAE | Fork `amigentd.apollo` | 131292 | `1e0e3f65d46b62c93f7986d8137120ef5e2dec2515a9b63f6aa5909d2e75e9ca` | Current fork package (AUDIO+PIP stub+AMMX lineage) |
| U-DAE | Contribution `amigentd.apollo` | 129844 | `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` | Protected upstream stack tip `685309d` |
| F-PRB | Fork `amigent-apollo-probe` | 3224 | `96ca1b389980b5a94ce0fc94c67c8eeafa7dd2455df497f52532e15409ba0265` | AFF_FPGA exit contract |
| U-PRB | Contribution probe | 3112 | `ab454b39988bd7b88c24058d0398507456ff12ff180b638d626beac821e1aff4` | Packaging tip probe (OS-only exit 0 historically) |
| MON | `amigent-monitor.apollo` | 22816 | `e06222ce73f62a1ec6cab7a370e3e6154f1c396160a4813d29ad7fd7cdb9626e` | Same hash on fork and contribution |
| CLI | Host client from commit under test | — | record `git rev-parse HEAD` + `__version__` | Must match the Python tree used |

**Rule:** Results from F-DAE do **not** validate U-DAE. Run separate rows for each candidate.

## Staging principles (non-destructive)

Documented facts (not assumptions):

- Default screen/control port is **6801**; TLS listens on **PORT+1** (`docs/PROTOCOL.md`).
- `PORT <n>` selects another port; PROTOCOL states this is “handy for running a second copy next to the first.” ARexx becomes `AMIGENT.<port>` when the primary name is taken.
- Client env defaults: `AMIGENT_CTL_PORT`/`AMIGENT_SCREEN_PORT` default **6800**/**6801** in `server.py` (control may be amigactld on older installs); viewer HTTP `AMIGENT_VIEWER_PORT` default **6810** on localhost.
- `amigent-setup --update` **replaces** the running daemon with the packaged build — treat as **approval-gated** on a known-good V4.
- This plan’s preferred mode: stage candidates under a **separate drawer** (e.g. `T:amigent-candidate/` or `SYS:amigent-test/`), launch with an **unused PORT**, point the PC client at that host:port via documented env vars — **only after** inventory confirms the port is free and the known-good instance remains untouched.

If concurrent operation cannot be confirmed safe on the live machine (port conflict, RAM, TLS cert path), stop and request an **exclusive session** with tested rollback.

### Offline procedure checklist (before any connection)

1. Read-only inventory: board, Kickstart/ApolloOS strings, installed `C:amigentd` size/hash if obtainable without replacing it, User-Startup line, ports in use.  
2. Backup: copy installed daemon, key/cert paths referenced by startup, User-Startup snippet, and package version notes to the PC.  
3. Record hashes for every candidate binary and the PC git SHA.  
4. Stage candidates to a **non-startup** path; do not overwrite `C:amigentd` in preparation.  
5. Confirm candidate launch command uses an explicit unused `PORT` and does not rewrite User-Startup.  
6. Prevent conflicts: choose PORT not equal to the production listener; do not start two SETUP instances that share the same key file unexpectedly.  
7. Concurrent support: PROTOCOL documents second-copy via PORT; still verify on the V4 that production continues answering on its port before declaring concurrency safe.  
8. Define start (launch candidate) and stop (quit candidate only; leave production running).  
9. Failure handling: if production port stops answering, restore from backup only under approval.  
10. Post-test: re-hash production binary path, confirm production SYSINFO/hello, confirm User-Startup unchanged.

## Risk legend

| Level | Meaning |
|-------|---------|
| L0 | PC-only / already-captured software evidence |
| L1 | Read-only or additive on V4; production daemon untouched |
| L2 | Temporary second instance on unused PORT |
| L3 | Touches production install / `--update` / exclusive session |
| L4 | Potentially hazardous (POKE, HRTmon, live MMIO write) — approval required |

---

## Test matrix

### A — System and identification

| ID | Purpose | Preconditions | Implementation / command | Binary | Expected | Evidence | Risk | Approval? | Pass/fail |
|----|---------|---------------|--------------------------|--------|----------|----------|------|-----------|-----------|
| A1 | Record board/OS | Inventory access | Manual + `amiga_sysinfo` / doctor once connected | CLI | Apollo model/OS strings logged | Screenshot/log | L1–L3 | If connect | Strings recorded |
| A2 | AFF_FPGA / probe contract | Candidate probe staged | Run `amigent-apollo-probe` from Shell; note stdout + exit | F-PRB and U-PRB separately | F-PRB: `ApolloOS` then `68080`, exit 0 only if both; AmigaOS → non-zero; U-PRB behaviour per its contract | Shell transcript | L1 | No if already on path copy | Matches contract for **that** probe hash |
| A3 | SYSINFO fields | Connected daemon | Client SYSINFO / About | F-DAE / U-DAE | `os`, `cpu`, `audio`, `pip` (fork may show `pip=0`; U-DAE must not advertise pip=1) | Redacted SYSINFO | L2 | Port staging | Fields match build |
| A4 | First-install selection | Disposable or exclusive | `amigent-setup` against staged package | CLI+F-PRB+F-DAE or U-* | Selects Apollo daemon only with sufficient evidence | Setup log | L3 | **Yes** | Correct binary chosen |
| A5 | Update path non-destructive | Known installed specialised daemon | `amigent-setup --update` against package that must not downgrade | CLI+#38 logic | Leaves specialised install when policy says so | Before/after hashes | L3 | **Yes** | Policy respected |

### B — Connectivity and protocol

| ID | Purpose | Preconditions | Implementation | Binary | Expected | Evidence | Risk | Approval? | Pass/fail |
|----|---------|---------------|----------------|--------|----------|----------|------|-----------|-----------|
| B1 | Protocol-6 hello | Candidate listening | Connect with matching key/TLS policy | F/U-DAE | Protocol 6; capabilities consistent | Hello/SYSINFO | L2 | Staging | Handshake OK |
| B2 | Reconnect | Stable link | Disconnect/reconnect viewer | same | Recovers without corrupting production | Log | L2 | | Reconnect OK |
| B3 | Classic fallback | Missing optional `.apollo` in package under test | Install/update with Apollo binary removed from package | CLI | Falls back to general `amigentd`; no fail-closed | Log | L3 | **Yes** | Fallback |
| B4 | TLSONLY remote plaintext | TLS up, TLSONLY set | Plain remote connect | daemon with TLSONLY | Closed after hello (`flags` bit per PROTOCOL) | Log | L2 | | Fail-closed |
| B5 | Client/daemon mismatch | Older client or proto | Documented mismatch case | — | Clear error; no crash | Log | L2 | | Error clear |

### C — Native daemon (general)

| ID | Purpose | Preconditions | Implementation | Binary | Expected | Evidence | Risk | Approval? | Pass/fail |
|----|---------|---------------|----------------|--------|----------|----------|------|-----------|-----------|
| C1 | Launch / quit | Unused PORT | `amigentd PORT <n> KEY <file>` (or tool types) | F/U-DAE | Starts; quits cleanly; production still up | Process/port check | L2 | Staging OK | Clean lifecycle |
| C2 | Commands / files | SETUP only if required | PUT/RUN only under SETUP on candidate | same | Documented SETUP behaviour | Log | L2–L3 | If SETUP | Success |
| C3 | Screen + viewer | Candidate screen port | `amigent-viewer` with env ports | same | Picture; mouse/keys | Screenshot | L2 | | Viewer works |
| C4 | Memory reporting | Connected | Chip/Fast displays | same | Missing chip ≠ zero (#33) | Screenshot | L2 | | Semantics OK |
| C5 | Daemon identity About | Identity-capable client | Open About | F-DAE + identity UI | Host CPU vs daemon family vs protocol vs capabilities distinct; unnamed → Not reported | Screenshot | L2 | | Distinguishes 1–4 |

### D — Apollo-specific

| ID | Purpose | Preconditions | Implementation | Binary | Expected | Evidence | Risk | Approval? | Pass/fail |
|----|---------|---------------|----------------|--------|----------|----------|------|-----------|-----------|
| D1 | MMIO refuse (software) | Host tests | `tests/test_apollo_mmio.py` / harness | — | All eight windows refuse | CI/local log | L0 | No | Pass |
| D2 | MMIO refuse (live read) | Candidate + ALLOWPOKE **off** | Protocol PEEK into a protected window | F/U-DAE | Refused; no register side effects claimed without proof | Log | L2 | Explicit | Refuse |
| D3 | MMIO write attempt | ALLOWPOKE on **candidate only** | POKE into protected window | same | Refused even with ALLOWPOKE | Log | L4 | **Yes** | Refuse |
| D4 | AUDIO opcode 48 | `audio=1` | Viewer Hear / `amiga_listen` | F/U-DAE separately | Stream starts/stops; WAV/PCM path | Audio note + log | L2 | Staging | Audible/logged |
| D5 | PIP remains unsupported as claimed | SYSINFO | Check `pip` and opcode 49 | U-DAE: no PIP cmd; F-DAE: `pip=0` empty | No overlay claim | SYSINFO | L2 | | Matches build |
| D6 | Apollo monitor | Packaged monitor present | Launch monitor path used by setup | MON | Runs or documented fallback | Log | L2–L3 | If replaces | OK / fallback |
| D7 | HRTmon program | ApolloOS, HRTmon on path | `amiga_hrtmon` / server tool | CLI | Starts **program** HRTmon only; never ROM | Log | L4 | **Yes** | Plan() rules |
| D8 | Graphics reporting | Connected | SYSINFO / About graphics fields | same | Consistent with machine | Screenshot | L2 | | Consistent |

### E — Compatibility and recovery

| ID | Purpose | Preconditions | Implementation | Binary | Expected | Evidence | Risk | Approval? | Pass/fail |
|----|---------|---------------|----------------|--------|----------|----------|------|-----------|-----------|
| E1 | Missing Apollo executable | Package without `.apollo` | Setup/update | CLI | Compatible general daemon | Log | L3 | **Yes** | Fallback |
| E2 | Preserve specialised install | #38 policy | Update that would downgrade | CLI | Refuses replace | Before/after hash | L3 | **Yes** | Preserved |
| E3 | Interrupt recovery | Mid-transfer | Unplug/reconnect network | L2 | Recovers or clear error | Log | L2 | | Recovered |
| E4 | Rollback | After exclusive test | Restore backed-up `C:amigentd` + startup | L3 | Production hash matches pre-test | Hashes | L3 | **Yes** | Restored |

---

## What can run without disturbing production

**Without V4:** A1 prep notes, D1, packaging/hash verification, client unit tests, report template dry-run.

**With V4, production untouched (after staging approval):** A2 using a **copied** probe binary not on the startup path; A3/B1/B2/B4/C1/C3/C4/C5/D2/D4/D5/D8 on a **second** `PORT` instance if concurrency is verified; evidence capture only.

**Requires explicit authorisation / exclusive session:** A4, A5, B3, C2 with SETUP writing system paths, D3, D6 if it replaces monitor, D7, E1–E2, E4, any `amigent-setup --update`, any overwrite of `C:amigentd`, any ALLOWPOKE experiment, any live SAGA register write.

## Maintainer-facing explanation (draft — do not post yet)

> We can run reproducible checks on a physical Apollo V4 and attach evidence (binary SHA-256, client commit, SYSINFO excerpts, and procedure IDs from our hardware test plan) to the relevant upstream PRs. Software CI and host harnesses already cover MMIO window refusal and packaging hashes; hardware runs will be labelled separately and will name the exact daemon/probe builds under test. The packaged contribution daemon (`456fce26…`) and our fork’s distributed daemon (`1e0e3f65…`) are different binaries and will not be conflated in results.

## Untested until authorised

All L1–L4 rows that require V4 contact. No hardware result may be marked passed in the report template until executed.
