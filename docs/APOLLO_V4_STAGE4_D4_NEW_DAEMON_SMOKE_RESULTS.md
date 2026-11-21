# Apollo V4 — Stage 4 D4 new-daemon smoke results

**Session:** Stage 4 D4 — security-hardened Apollo daemon read-only compatibility smoke  
**Evidence (private):** `~/amigent-evidence/stage4-d4-new-daemon-smoke/20261121T075758Z`  
**Mode:** Exclusive candidate launch; production restored  
**Conclusion:** **APOLLO V4 STAGE 4 D4 NEW DAEMON SMOKE VALIDATED — PRODUCTION RESTORED**

## Candidate identity

| Field | Value |
|---|---|
| Staged path | `Programs:AmiGent-Stage4/amigentd.d4` |
| Size | 128744 |
| SHA-256 | `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` |
| Lineage | PR [#14](https://github.com/AmanitaHouse/amigent/pull/14) / `review/stage4-d3-trace-integration` tip `f927b86…` |
| Fork `main` at freeze | `fad6693a1678c5ae65c60d29a9a6a6b74feb42f3` |
| Toolchain | GCC-6.50-Stable `-m68080 -DAMIGENT_APOLLO` |
| Launch | `Run <NIL: >NIL: Programs:AmiGent-Stage4/amigentd.d4 TLSONLY` |
| ALLOWPOKE | **not** enabled |

Staged read-back matched the frozen SHA-256 before production QUIT.

## Production baseline (unchanged)

| Field | Value |
|---|---|
| Path | `C:amigentd` |
| Protocol | 5 |
| TLS | certificate-verified on PORT+1 (6802) |
| Size / SHA-256 | 113324 / `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` |
| Backup | `~/amigent-evidence/stage2a-production-backup/20261121T010816Z/v4-production-C-amigentd.bin` |
| Restore | `Run <NIL: >NIL: C:amigentd TLSONLY` |

## Session sequence

1. Offline GO (provenance, native D3/TRACE safety, TLS client, backup).  
2. Production preflight: proto 5 TLS, ApolloOS / 68080, SYSINFO ×2.  
3. Stage `amigentd.d4` while production remained up; read-back hash PASS.  
4. Physical-console handover (`operator_ready`, signal: `awaiting quit`).  
5. ARexx `ADDRESS AMIGENT 'QUIT'` — TLS 6802 released.  
6. Operator launched D4 candidate with `TLSONLY`.  
7. One read-only smoke: proto 6 TLS + SYSINFO.  
8. Candidate QUIT — TLS released.  
9. Operator restored classic production.  
10. Production verify: proto 5 TLS + SYSINFO ×2.

No reboot. No production file replacement. No install/update.

## Smoke results (candidate)

| Check | Result |
|---|---|
| TLS certificate verified | PASS |
| Protocol | **6** |
| OS / CPU | ApolloOS / **68080** |
| Board | V4-SA |
| Kickstart | 51.51 |
| SYSINFO | PASS |
| `audio` | `1` (reported only; **not** exercised) |
| `poke` | `0` |
| `trace` | `0` |
| `pip` | `0` |
| Candidate QUIT | PASS |

Note: SYSINFO `self` reported `Programs:AmiGent-Stage4/amigentd` (Amiga path form); staged file name remained `amigentd.d4`. Hash was verified by PC read-back before launch.

## What this validates

The exact `63db83ff…` executable can:

- Start on Apollo V4-SA under ApolloOS.  
- Negotiate protocol 6 over certificate-verified TLS.  
- Identify ApolloOS / 68080 and return read-only SYSINFO.  
- Advertise `poke=0` and `trace=0` (and `pip=0`).  
- Shut down via ARexx QUIT.  
- Allow restoration of protocol-5 production without reboot.

## What this does **not** validate

- Hardware-tested POKE refusal or the 30-second POKE deadline.  
- Hardware-tested TRACE refusal / set/list/clear.  
- AUDIO capture, streaming, or Viewer Hear on this executable.  
- MMIO protection on this executable.  
- Monitor / HRTmon.  
- Long-duration stability or production deployment readiness.

Historical hardware identity `00443719…` / 129944 B (Stage 3B / D2) is **not** transferred to `63db83ff…`.

## Coverage vs prior Stage 4 work

| Item | Status after D4 |
|---|---|
| D2 protected-window PEEK refuse (on `00443719…`) | unchanged historical PASS |
| D3 POKE hardware | still **not** authorised / not tested |
| TRACE 68080 hardware | still **not** authorised / not tested |
| D6 / D7 | still **not** authorised |
| New combined daemon start/SYSINFO (`63db83ff…`) | **D4 PASS** |
