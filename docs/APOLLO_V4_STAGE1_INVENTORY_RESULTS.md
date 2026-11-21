# Apollo V4 Stage 1 inventory results

**Session UTC:** 2026-11-21T00:59:10Z  
**Authorisation:** Stage 1 read-only inventory only  
**Plan / docs commit:** `feeb427085345c5d1b167b3dcfb1ade15a380e6e`  
**Fork `main` (unchanged):** `79880b8f018ae735715de4f1d0e943acf4462dcd`  
**Client:** Amigent `1.4.0` from docs checkout `feeb427` (same Python tree as `main`)  
**Machine entry:** `V4SA` (existing default)  
**Transport:** TLS to configured production host/port (address redacted)  
**PC evidence (private):** `~/amigent-evidence/stage1-inventory/20261121T005910Z/`

No Stage 2/3 tests were run. No installation, update, restart, second daemon, AUDIO, monitor, HRTmon launch, doctor, or V4 file write occurred.

## Results summary

| ID | Operation | Result | Notes |
|----|-----------|--------|-------|
| C1 | Connect + handshake | **PASS** | Banner `amigentd protocol 5`, TLS |
| C2 | `sysinfo()` | **PASS** | See fields below |
| C2 | `volumes()` | **PASS** | RAM Disk, Programs, ApolloOS |
| C2 | `exec("Version")` | **PASS** | Kickstart 51.51, Workbench 40.0 |
| C2 | `exec("CPU")` | **PASS** (empty utility) | Output: `CPU: object not found` — CPU taken from SYSINFO only |
| C3 | `Which HRTmon` | **PASS** (absent) | `rc=5`, empty output — not on command path |
| C4 | Daemon `self` path / disk hash | **SKIPPED** | SYSINFO has no `self` (expected on this protocol-5 build) |
| G | Recheck `sysinfo()` after inventory | **PASS** | Production still responsive |

## Observed identification

| Field | Value |
|-------|-------|
| Negotiated protocol | **5** |
| TLS | yes |
| `os` | ApolloOS |
| `board_name` | V4-SA |
| `board` | 0000050e |
| `cpu` (SYSINFO) | 68080 |
| `exec_version` | 51.3 |
| `kickstart` | 51.51 |
| `attn_flags` | 42111 (decimal; includes AFF_FPGA bit 0x400) |
| Shell `Version` | Kickstart 51.51, Workbench 40.0 |

## Reported capabilities (SYSINFO)

| Key | Value |
|-----|-------|
| audio | 1 |
| pip | 0 |
| note | 1 |
| text | 1 |
| debug | 1 |
| readfrom | 1 |
| poke / loaded / probe / self | **not reported** |

Public ports list includes `AMIGENT`. Task list includes `amigentd`, `amigentd reader`, `amigentd tls`, `amigentd tls listener`.

## Memory / volumes (as reported)

| Volume | Free (bytes) | Capacity (bytes) |
|--------|-------------:|-----------------:|
| RAM Disk: | 973897592 | 974442776 |
| Programs: | 678789120 | 7574999040 |
| ApolloOS: | 152369664 | 263191040 |

| Memory | Free | Total |
|--------|-----:|------:|
| Chip | 12036376 | 12050432 |
| Fast | 961861328 | 1050148864 |

## Daemon disk identity

**Not obtained.** Protocol 5 SYSINFO did not provide `self=`, so no Version-of-path or PC-side SHA-256 of an installed executable was collected. Running process identity is therefore known only by connection behaviour (protocol 5, TLS, capabilities above), not by disk hash.

## Confirmations

- No `amigent-doctor`, SETUP, `--update`, candidate daemon, probe execution, AUDIO, monitor, HRTmon launch, PEEK/POKE, or V4 writes.
- PC client connection closed after inventory; no remote shutdown.
- Production daemon answered a second read-only `sysinfo()` before disconnect.

## Recommended Stage 2 arrangement (not authorised yet)

1. Treat production as a **known-good protocol-5** ApolloOS install with `audio=1` / `pip=0`.
2. Prefer an **exclusive session** for any candidate protocol-6 daemon (F-DAE / U-DAE), or a second `PORT` only for TCP/SYSINFO with hook caveats — do not run concurrent AUDIO.
3. Before exclusive replacement: obtain a PC-side copy/hash of `C:amigentd` (or the path used at boot) via an **approved** read of a known path, since `self=` is unavailable on this build.
4. Keep F-DAE and U-DAE results in separate report rows.
5. Re-approve before any Stage 2 contact.
