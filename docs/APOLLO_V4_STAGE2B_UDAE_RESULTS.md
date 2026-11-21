# Apollo V4 Stage 2B results — U-DAE exclusive protocol-6 validation

**Session UTC start:** 2026-11-21T01:17:56Z  
**Authorisation:** Stage 2B exclusive — physical Shell confirmed; staging + temporary production interruption approved  
**Runbook:** `docs/APOLLO_V4_STAGE2B_RUNBOOK.md`  
**Docs parent tip:** `cc2907e`  
**Fork `main` (unchanged):** `79880b8f018ae735715de4f1d0e943acf4462dcd`  
**Client:** Amigent `1.4.0` from docs checkout `cc2907e`  
**Machine:** `V4SA`  
**PC evidence (private):** `~/amigent-evidence/stage2b-udae-exclusive/20261121T011756Z/`

F-DAE was **not** tested. Stage 3 was **not** started. `C:amigentd` was **not** overwritten. No automatic reboot.

## Session metadata (template fields)

| Field | Value |
|-------|-------|
| Test date (UTC) | 2026-11-21 |
| Authorisation | Stage 2B exclusive U-DAE |
| Session stage | **2B exclusive candidate** |
| Independent console | **yes** (physical V4 Shell) |
| Candidate staged before QUIT | **yes** |
| Concurrent second PORT | **no** |
| TLS on PORT+1 (6802) | **yes** |
| Full amigent-doctor | **no** |

## Binary under test

| Role | Path | Size | SHA-256 | ID |
|------|------|-----:|---------|-----|
| Candidate | `Programs:AmiGent-Stage2B/amigentd.udae` | 129844 | `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` | **U-DAE** |
| Production (untouched) | `C:amigentd` | 113324 | `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` | prod 1.3 |

## Results summary

| Step | Result | Notes |
|------|--------|-------|
| Staging + PC read-back hash | **PASS** | Match U-DAE; `Protect "…/amigentd.udae" +e` rc=0 |
| Console handover | **PASS** | Operator confirmed Shell; recovery command available |
| Production `QUIT` | **PASS** | ARexx via `rx`; TLS 6802 refused afterward |
| U-DAE launch (console) | **PASS** | `Run <NIL: >NIL: Programs:AmiGent-Stage2B/amigentd.udae TLSONLY` |
| Protocol-6 + TLS | **PASS** | Banner `amigentd protocol 6`, TLS |
| SYSINFO / volumes / Version | **PASS** | See observations below |
| Candidate `QUIT` | **PASS** | TLS 6802 refused afterward |
| Production restore (console) | **PASS** | `Run <NIL: >NIL: C:amigentd TLSONLY` |
| Final protocol-5 + TLS | **PASS** | Second `sysinfo()` also OK |
| Reboot / recovery intervention | **none** | |

## Hardware observations (U-DAE / protocol 6)

| Field | Observed |
|-------|----------|
| Negotiated protocol | **6** |
| TLS | yes (PORT+1) |
| `os` | ApolloOS |
| `board_name` | V4-SA |
| `cpu` | 68080 |
| `kickstart` | 51.51 |
| `exec_version` | 51.3 |
| `attn_flags` | 42111 (AFF_FPGA bit present) |
| Shell `Version` | Kickstart 51.51, Workbench 40.0 |
| `self` (protocol 6) | `Programs:AmiGent-Stage2B/amigentd` — staged file was `…/amigentd.udae`; see `docs/APOLLO_V4_SELF_PATH_NOTE.md` |
| `poke` | 0 |
| `probe` | 1 |
| `loaded` | 1 |
| `audio` (capability bit) | 1 — **AUDIO not exercised** |

Volumes (read-only): RAM Disk, Programs, ApolloOS — listed successfully.

## Commands executed

| Who | Command |
|-----|---------|
| PC (AmiGent) | Stage/put/read-back; `Protect "Programs:AmiGent-Stage2B/amigentd.udae" +e` |
| PC (AmiGent→rx) | ARexx `ADDRESS AMIGENT 'QUIT'` (production) |
| Operator (V4 Shell) | `Run <NIL: >NIL: Programs:AmiGent-Stage2B/amigentd.udae TLSONLY` |
| PC | Protocol-6 connect, `sysinfo()`, `volumes()`, `exec("Version")` |
| PC (AmiGent→rx) | ARexx `ADDRESS AMIGENT 'QUIT'` (candidate) |
| Operator (V4 Shell) | `Run <NIL: >NIL: C:amigentd TLSONLY` |
| PC | Protocol-5 connect, `sysinfo()` ×2 |

## Evidence class

All protocol/SYSINFO rows above are **HW** (physical V4). No SW-only substitution.

## Confirmations

- No AUDIO/Hear, monitor, HRTmon, PIP, PEEK/POKE, MMIO, Update, file writes beyond staging, or F-DAE.
- PC client closed without remote shutdown of restored production.
- Raw logs, staged binary read-back, and private JSON remain **outside Git**.

## Upstream PR support (hardware claims now evidenced)

With this session, physical V4 evidence supports reporting that the **U-DAE** Apollo contribution daemon:

- Runs exclusively on V4-SA / ApolloOS / 68080 with AFF_FPGA present in `attn_flags`
- Negotiates **protocol 6** over TLS (`TLSONLY` / PORT+1)
- Reports ApolloOS, CPU 68080, Kickstart 51.51, and `self` path
- Advertises `probe=1`, `loaded=1`, `poke=0` (poke not enabled; poke/MMIO **not** validated live)
- Shuts down cleanly via ARexx `QUIT`; production protocol-5 restore succeeded without reboot

## Remaining hardware-validation gaps (Stage 3 / later)

- F-DAE exclusive session  
- AUDIO / Hear  
- Apollo monitor  
- HRTmon  
- Probe execution on hardware  
- MMIO / ALLOWPOKE / PIP  
- Update / fallback paths  
- Long-soak / twin-PORT behaviour  

## Next step

Do **not** begin Stage 3 from this report. Further sessions require separate authorisation.
