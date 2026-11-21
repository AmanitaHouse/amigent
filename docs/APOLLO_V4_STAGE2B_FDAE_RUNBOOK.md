# Apollo V4 Stage 2B — F-DAE exclusive runbook

**Status:** Prepared offline — **not authorised for execution**  
**Basis:** Proven U-DAE exclusive session (`docs/APOLLO_V4_STAGE2B_UDAE_RESULTS.md`)  
**Do not** treat U-DAE success as F-DAE validation.

## Candidate

| Item | Value |
|------|-------|
| ID | **F-DAE** (fork Apollo daemon only) |
| Size | **131292** |
| SHA-256 | `1e0e3f65d46b62c93f7986d8137120ef5e2dec2515a9b63f6aa5909d2e75e9ca` |
| Staging path (proposed) | `Programs:AmiGent-Stage2B/amigentd.fdae` |
| Must not use | U-DAE path `…/amigentd.udae`, `C:amigentd`, Amigent-Update |

## Production baseline (unchanged)

- Path: `C:amigentd` — do not overwrite  
- Startup: `RUN >NIL: C:amigentd TLSONLY`  
- Backup: `~/amigent-evidence/stage2a-production-backup/20261121T010816Z/v4-production-C-amigentd.bin`  
  SHA-256 `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3`  
- Ports: plain **6801**, TLS **6802** (PORT+1)

## Hard requirements

1. Physical AmigaOS Shell (keyboard + display) confirmed before QUIT.  
2. Stage + PC read-back hash **before** stopping production.  
3. Same limited tests as U-DAE: protocol-6 TLS, SYSINFO, volumes, Version — read-only.  
4. Restore `Run <NIL: >NIL: C:amigentd TLSONLY`; verify protocol 5 + TLS.  
5. Out of scope: AUDIO, monitor, HRTmon, PIP, MMIO, update/fallback, U-DAE retest as fallback.

## Sequence (mirrors U-DAE)

1. Confirm physical Shell.  
2. Confirm production protocol 5 + TLS.  
3. Re-verify PC production backup hash.  
4. Re-verify F-DAE offline hash.  
5. Check `Programs:` free space; ensure `…/amigentd.fdae` is absent or already exact F-DAE.  
6. `makedirs` `Programs:AmiGent-Stage2B`; put F-DAE; read-back SHA-256.  
7. `Protect "Programs:AmiGent-Stage2B/amigentd.fdae" +e`  
8. Console handover: launch + recovery commands ready.  
9. Authorised interrupt → ARexx `ADDRESS AMIGENT 'QUIT'` → confirm TLS 6802 down.  
10. Console: `Run <NIL: >NIL: Programs:AmiGent-Stage2B/amigentd.fdae TLSONLY`  
11. PC: expect protocol **6** + TLS; SYSINFO / volumes / Version only.  
12. ARexx `QUIT` candidate → confirm ports free.  
13. Console: `Run <NIL: >NIL: C:amigentd TLSONLY`  
14. PC: verify protocol **5** + TLS + SYSINFO spot-check.  
15. Record evidence under `~/amigent-evidence/stage2b-fdae-exclusive/<UTC>/` (outside Git).

## Rollback

| Situation | Action |
|-----------|--------|
| Hash mismatch before QUIT | Abort; leave production running |
| QUIT busy | Do not launch F-DAE; report |
| Candidate up | `QUIT` then restore `C:amigentd TLSONLY` |
| Restore fails | Halt; no automatic reboot; operator decides |

## Lesson from U-DAE for staging names

Prefer a staging leaf name that matches normal Amiga program naming if SYSINFO `self` fidelity matters (`amigentd.fdae` may show as `…/amigentd` in `self`, same mechanism as U-DAE). Hash of the staged file remains authoritative.
