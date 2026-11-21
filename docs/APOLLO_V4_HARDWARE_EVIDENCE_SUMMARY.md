# Apollo V4 hardware evidence summary (maintainer-facing)

**Public-safe.** No hosts, keys, credentials, or raw logs.  
**Session:** Stage 2B exclusive U-DAE — 2026-11-21  
**Detail report:** `docs/APOLLO_V4_STAGE2B_UDAE_RESULTS.md`  
**Docs branch:** `validation/apollo-v4-evidence-prep`

## What was tested on hardware

| Item | Result |
|------|--------|
| Board | Apollo **V4-SA** |
| OS / Kickstart | **ApolloOS**, Kickstart **51.51**, exec 51.3 |
| CPU | **68080**; `attn_flags` includes AFF_FPGA (42111 decimal) |
| Binary | Protected upstream Apollo daemon (**U-DAE**), 129844 bytes |
| SHA-256 | `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` |
| Transport | TLS with existing pin; base PORT 6801, TLS on **PORT+1** |
| Handshake | **Protocol 6** negotiated |
| Read-only ops | SYSINFO, volumes, Shell `Version` |
| Shutdown | ARexx `QUIT` — clean |
| Restore | Original `C:amigentd` / protocol **5** / `TLSONLY` restored; no reboot |

Production executable was **not** overwritten. Staging used a non-`C:` path.

## SYSINFO `self` path note

Staged file: `…/amigentd.udae`  
SYSINFO `self`: `…/amigentd` (extension omitted)

**Cause (source):** `find_self()` builds `self` from `GetProgramDir()` + `FilePart(GetProgramName())`, not from the staging pathname string. See `docs/APOLLO_V4_SELF_PATH_NOTE.md`. Not treated as a validated truncation defect; not a change to protected contribution history.

## Explicitly **not** hardware-validated by this session

- F-DAE AUDIO / long-duration Hear soak — still **NOT RUN ON HW**  
- Viewer Hear (stream-safe U-HEAR `983fd853…`): **PASSED ON HW** (bounded supervised session) — `docs/APOLLO_V4_STAGE3B_HEAR_RESULTS.md`  
- Apollo monitor  
- HRTmon  
- Live MMIO / SAGA / ALLOWPOKE (even though SYSINFO reported `poke=0`)  
- First-install automatic daemon selection  
- Upgrade / fallback / Amigent-Update  
- Fork-specific AMMX / live PIP picture paths  
- `$DFF3FC` fallback path / non-Apollo negative detection / unpublished 1.5.0 detect  

**F-DAE** protocol-6 smoke: `docs/APOLLO_V4_STAGE2B_FDAE_RESULTS.md`.  
**Stage 3A probes:** U-PRB + F-PRB executed on V4 while production stayed up — `docs/APOLLO_V4_STAGE3A_PROBE_RESULTS.md` (PASSED ON HW; does not validate install selection).

**Stage 3B AUDIO (U-DAE exclusive):**

| Phase | Result | Doc |
|-------|--------|-----|
| Phase 1 one-shot quiet | **PASSED ON HW (valid empty)** | `docs/APOLLO_V4_STAGE3B_AUDIO_PHASE1_RESULTS.md` |
| Phase 2A one-shot + AHI source | **PASSED ON HW (nonempty PCM + nonzero signal)** | `docs/APOLLO_V4_STAGE3B_AUDIO_PHASE2A_RESULTS.md` |

Software unit tests and host harnesses are **not** substitutes for the untested rows above.

## Mapping to contributions (do not over-claim)

| Contribution | What this HW session supports | What it does **not** prove |
|--------------|-------------------------------|----------------------------|
| Upstream **#31** ApolloOS identify | Board/OS context; **U-PRB** HW stdout `ApolloOS` / rc 0 | Negative detection / 1.5.0 private detect not proven |
| Fork review **#4** daemon foundation | U-DAE launches; protocol 6; SYSINFO OS/CPU/board | Not a substitute for #5–#8 feature tests |
| Fork **#5** MMIO | `poke=0` observed only | No live PEEK/POKE refusal trial |
| Fork **#6** AUDIO | Opcode 48 one-shot nonempty capture on U-DAE (Phase 2A) | Fidelity; stream; F-DAE AUDIO |
| Fork **#8** Viewer Hear | Supervised Hear HW on U-HEAR `983fd853…` | Stock Viewer UI soak / F-DAE / fidelity not proven |
| Fork **#7** packaging | Exact U-DAE hash exercised | Installer/update paths not run |
| Fork **#10** probe AFF_FPGA | **F-PRB** HW: `ApolloOS`+`68080` / rc 0 (OS∧AFF_FPGA) | Installer consumption of exit code; `$DFF3FC` fallback |
| Fork **F-DAE** | Proto-6 exclusive smoke PASSED ON HW | AUDIO/MMIO/probe/PIP still NOT RUN |

Draft PR comment text: `docs/APOLLO_V4_DRAFT_UPSTREAM_HW_COMMENT.md` (**not posted**).
