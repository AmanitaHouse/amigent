# Apollo V4 Stage 3A — Apollo probe hardware-test runbook

**Status:** **EXECUTED** — see `docs/APOLLO_V4_STAGE3A_PROBE_RESULTS.md` (session `20261121T021031Z`)  
**Docs parent tip:** `dd81a39` (validation/apollo-v4-evidence-prep)  
**Fork `main`:** `79880b8` (unchanged)  
**Production:** leave `C:amigentd` / protocol 5 / `TLSONLY` running

This runbook covers **U-PRB** and **F-PRB** only. No daemon swap, AUDIO, monitor, HRTmon, MMIO poke, PIP, or setup/update.

---

## Binary provenance (verified offline)

| ID | Size | SHA-256 | Packaged path | Source tip | Probe source | Linked detect |
|----|-----:|---------|---------------|------------|--------------|---------------|
| **U-PRB** | 3112 | `ab454b39988bd7b88c24058d0398507456ff12ff180b638d626beac821e1aff4` | `integrate/apollo-safe-upstream-stack@685309d` → `src/amigent/amiga/bin/amigent-apollo-probe` | `amiga/apollo/apollo_probe.c` (exit 0 on ApolloOS alone) | `amiga/apollo/apollo_detect.c` |
| **F-PRB** | 3224 | `96ca1b389980b5a94ce0fc94c67c8eeafa7dd2455df497f52532e15409ba0265` | fork `main` / `review/apollo-probe-core-evidence@4924da4` → `src/amigent/amiga/bin/amigent-apollo-probe` | `src/native/amiga/platform/apollo/apollo_probe.c` | same detect (board fallback) |

Both are AmigaOS loadseg executables, built `-m68000` (`PROBE_CFLAGS`), linked with `apollo_probe.c` + `apollo_detect.c` + libgcc. **Do not rebuild** for Stage 3A; use these hashes.

PC offline copies (private):

- `/tmp/amigent-candidate-offline/amigent-apollo-probe.uprb`
- `/tmp/amigent-candidate-offline/amigent-apollo-probe.fprb` (or packaged F-PRB path)

---

## Output / exit contracts

`RETURN_OK` = 0, `RETURN_WARN` = 5 (AmigaDOS).

### U-PRB (original protected)

| Condition | stdout | exit |
|-----------|--------|-----:|
| `apollo_os_here()` true | `ApolloOS\n` | **0** |
| else | `AmigaOS\n` | **5** |

Does **not** print `68080`. Exit 0 on ApolloOS **without** requiring AFF_FPGA.

### F-PRB (fork / review #10)

| Condition | stdout | exit |
|-----------|--------|-----:|
| ApolloOS + AFF_FPGA | `ApolloOS\n` then `68080\n` | **0** |
| ApolloOS, no AFF_FPGA | `ApolloOS\n` only | **5** |
| not ApolloOS, AFF_FPGA set | `AmigaOS\n` then `68080\n` | **5** |
| not ApolloOS, no AFF_FPGA | `AmigaOS\n` | **5** |

**Contract:** exit 0 ⇒ ApolloOS **and** FPGA core bit. ApolloOS alone must not select 68080 via SETUP exit code (`setup._apollo_by_probe` / `amigentd_build`).

### `apollo_os_here()` (both binaries)

Order in `apollo_detect.c`:

1. `SysBase->LibNode.lib_IdString` contains `"ApolloOS"` → true (**no board read**)  
2. `lib_Version < 51` → false  
3. `AttnFlags & AFF_FPGA` (bit 10) → true (**no board read**)  
4. else **read** `*(UWORD *)0xDFF3FC` (`VREG_BOARD`); model byte 1…9 → true  

On the Stage 1/2 V4 (ApolloOS + `attn_flags` 42111 incl. AFF_FPGA), steps 1 or 3 succeed → **`$DFF3FC` not read** on the expected path.

### Expected on this V4 (HW-confirmed in Stage 3A results)

| Probe | Expected stdout | Expected exit |
|-------|-----------------|--------------:|
| U-PRB | `ApolloOS\n` | 0 |
| F-PRB | `ApolloOS\n68080\n` | 0 |

---

## Safety assessment

| Topic | Finding |
|-------|---------|
| APIs | `PutStr` (dos); read `SysBase` IdString / Version / `AttnFlags`; optional volatile word read at `$DFF3FC` |
| Memory writes | **None** in probe/detect |
| Hooks / ports / resident | **None** |
| Graphics / AUDIO / monitor / HRTmon | **Not touched** |
| Coexist with production `amigentd` | **Yes** for this V4 profile — short CLI process; no ARexx/`AMIGENT` conflict |
| `$DFF3FC` | Linked detect **can** read it on fallback path; daemon PEEK refuses that window. On AFF_FPGA / ApolloOS IdString path, read skipped. Residual risk if detect falls through — low on this board |
| Stack / cwd | Standard CLI; no special stack in source. Working dir irrelevant (no file I/O beyond stdout) |
| Protect | Needs execute bit: `Protect "…path…" +e` (FAQ / Stage 2B verified form) |

**Verdict:** Stage 3A may run **while production protocol-5 remains up** (non-exclusive), with post-exec `sysinfo()` check. If `$DFF3FC` path is ever forced or the V4 misbehaves, stop and escalate to exclusive review — do not invent recovery.

Does **not** validate unpublished upstream 1.5.0 detect (bit-10-only, no board fallback, probe gated on packaged `.apollo`).

---

## Offline verification (done at preparation)

- Hashes re-verified: U-PRB `ab454b39…` / 3112; F-PRB `96ca1b38…` / 3224  
- `pytest` `test_daemon_selection.py` + `test_apollo_distribution.py` + `test_protocol6_align.py`: **29 passed**  
- Software mocks ≠ hardware probe execution  

---

## Proposed Stage 3A procedure (execute only when authorised)

Staging volume: `Programs:` (separate from Stage 2B daemons).

| Path | Role |
|------|------|
| `Programs:AmiGent-Stage3A/amigent-apollo-probe.uprb` | U-PRB |
| `Programs:AmiGent-Stage3A/amigent-apollo-probe.fprb` | F-PRB |

### While production stays up

1. Connect TLS protocol 5; `sysinfo()` spot-check.  
2. Re-hash PC U-PRB / F-PRB.  
3. `makedirs` `Programs:AmiGent-Stage3A`.  
4. Put each file; **read-back** SHA-256 must match.  
5. `Protect "Programs:AmiGent-Stage3A/amigent-apollo-probe.uprb" +e`  
   `Protect "Programs:AmiGent-Stage3A/amigent-apollo-probe.fprb" +e`  
6. Execute via AmiGent `exec` (capture rc + output), **one at a time**:

```text
Programs:AmiGent-Stage3A/amigent-apollo-probe.uprb
Programs:AmiGent-Stage3A/amigent-apollo-probe.fprb
```

   (Quoted if the channel requires it; same pattern as setup’s `T:amigent-apollo-probe`.)  
7. Record stdout, rc; compare to contracts and SYSINFO.  
8. Final `sysinfo()` — production still protocol 5 + TLS.  
9. Close PC client only — **no** QUIT, no User-Startup change.

Evidence dir (private): `~/amigent-evidence/stage3a-probe/<UTC>/`

### Out of scope

setup/update, daemon launch, AUDIO, monitor, HRTmon, PEEK/POKE, PIP, overwriting Stage 2B staged daemons.

---

## 1.5.0 comparison notes (when public)

| Our probes | Private 1.5.0 comment (#31) |
|------------|------------------------------|
| Board `$DFF3FC` fallback in detect | Removed |
| AFF_FPGA / IdString / exec 51 | Bit-10 + exec 51 emphasised |
| Probe always runnable if packaged | Probe questions only when `.apollo` packaged |
| F-PRB exit needs OS+FPGA | Aligns in spirit with “OS alone ≠ 68080” |

Stage 3A results apply to **these** binaries only.

---

## Authorisation gate

Stage 3A execution was authorised and completed. Re-runs still require separate approval.
