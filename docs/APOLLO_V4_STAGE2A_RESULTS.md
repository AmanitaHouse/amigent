# Apollo V4 Stage 2A results — production identification and PC backup

**Session UTC:** 2026-11-21T01:08:16Z  
**Authorisation:** Stage 2A read-only V4 contact + V4→PC backup of `C:amigentd` only  
**Plan / docs parent:** `ef4f4801c68e16a80b68cf389976d7c858927854`  
**Fork `main` (unchanged):** `79880b8f018ae735715de4f1d0e943acf4462dcd`  
**Client:** Amigent `1.4.0` from docs checkout `ef4f480`  
**Machine entry:** `V4SA` (existing default)  
**Transport:** TLS to configured production host/port (address redacted)  
**PC evidence (private):** `~/amigent-evidence/stage2a-production-backup/20261121T010816Z/`

No Stage 2B candidate launch, QUIT, restart, update, AUDIO, monitor, HRTmon, PEEK/POKE, doctor, or V4 write occurred.

## Results summary

| ID | Operation | Result | Notes |
|----|-----------|--------|-------|
| B | Connect + handshake | **PASS** | Banner `amigentd protocol 5`, TLS |
| B | Initial `sysinfo()` | **PASS** | Board/OS match Stage 1 |
| C | Read `S:User-Startup` (PC inspect) | **PASS** | One amigent line; raw kept private |
| D | `stat("C:amigentd")` | **PASS** | file, 113324 bytes, datestamp 2026-08-19 01:42:33 |
| D | `Version "C:amigentd"` | **PASS** | `amigentd 1.3` |
| E | `read_file("C:amigentd")` → PC | **PASS** | length matches stat; SHA-256 verified on PC |
| F | Home + drawer copy | **PASS** | Home `SYS:amigent`; drawer matches `C:` byte-for-byte |
| G | TLS path existence | **PASS** | `S:amigent.key` and `S:amigent-tls.pem` exist (contents not transferred) |
| H | Final `sysinfo()` | **PASS** | Production still responsive; protocol 5 / TLS |

## Observed facts (hardware / connection)

| Field | Value |
|-------|-------|
| Negotiated protocol | **5** |
| TLS | yes |
| `os` | ApolloOS |
| `board_name` | V4-SA |
| `cpu` (SYSINFO) | 68080 |
| `kickstart` | 51.51 |
| `exec_version` | 51.3 |
| `attn_flags` | 42111 (AFF_FPGA bit present) |

## Disk-file evidence (installed executable)

| Field | Value |
|-------|-------|
| Installed path | **`C:amigentd`** |
| Version string | `amigentd 1.3` |
| Size | **113324** bytes |
| Datestamp (stat) | 2026-08-19 01:42:33 |
| SHA-256 (PC of V4→PC read) | `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` |
| Size matches V4 stat | **yes** |
| Backup complete | **yes** |

**Running-image caveat:** Protocol 5 SYSINFO still has no `self=` path. The hash above identifies the **installed file** at `C:amigentd`, not a proven match to the in-memory process image.

### Drawer copy

| Field | Value |
|-------|-------|
| Home source | `ENVARC:amigent-home` → `SYS:amigent` |
| Drawer path | `SYS:amigent/amigentd` |
| Present | yes |
| Version | `amigentd 1.3` |
| Size / SHA-256 | identical to `C:amigentd` |
| Match | **yes** (disk files match; still not running-image proof) |

## Startup configuration (redacted)

Exact AmiGent line observed (credentials: none present as values):

```text
RUN >NIL: C:amigentd TLSONLY
```

| Topic | Finding |
|-------|---------|
| Launch method | `RUN >NIL:` from `S:User-Startup` |
| Executable | `C:amigentd` |
| PORT | **not set** on the line → default **6801** (TLS on PORT+1 per docs) |
| TLS | **`TLSONLY`** present |
| KEY path on line | **absent** → daemon default key file (`S:amigent.key` exists) |
| Other args | none observed |

### TLS path existence (no secret material)

| Path | Exists | Type | Size (bytes) |
|------|--------|------|-------------:|
| `S:amigent.key` | yes | file | 33 |
| `S:amigent-tls.pem` | yes | file | 848 |
| `SYS:amigent/amigent-monitor` | yes | file | _(not launched)_ |

## Recovery readiness (assessment only — not drilled)

| Prerequisite | Status |
|--------------|--------|
| Production path known | `C:amigentd` |
| PC backup of production bytes | verified SHA-256 above |
| Startup args reproducible | `RUN >NIL: C:amigentd TLSONLY` |
| Key/cert files present on V4 | existence confirmed; contents not copied |
| Restore without package install | yes, if `C:amigentd` left untouched and PC backup retained |
| QUIT latency / busy behaviour | **not tested** (Stage 2B) |
| Running image ≡ disk file | **unverified** (no `self=`) |

Production backup hash **differs** from U-DAE (`456fce26…`, 129844) and F-DAE (`1e0e3f65…`, 131292) — expected for a separate exclusive candidate session.

## Confirmations

- PC client connection closed after inventory; **no** ARexx `QUIT`, restart, candidate upload/launch, Update, or V4 write.
- Raw `User-Startup`, private session JSON, and executable backups remain **outside Git**.

## Next step

Stage 2B U-DAE results: **`docs/APOLLO_V4_STAGE2B_UDAE_RESULTS.md`**.  
F-DAE and Stage 3 await separate authorisation.
