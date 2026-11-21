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

- AUDIO opcode 48 / viewer Hear playback  
- Apollo monitor  
- HRTmon  
- Live MMIO / SAGA / ALLOWPOKE (even though SYSINFO reported `poke=0`)  
- Native Apollo probe **execution**  
- First-install automatic daemon selection  
- Upgrade / fallback / Amigent-Update  
- Fork-specific AMMX / live PIP picture paths  

**F-DAE** protocol-6 smoke is now separately documented in `docs/APOLLO_V4_STAGE2B_FDAE_RESULTS.md` (same narrow scope as U-DAE; AUDIO/MMIO/probe still NOT RUN).

Software unit tests and host harnesses are **not** substitutes for the untested rows above.

## Mapping to contributions (do not over-claim)

| Contribution | What this HW session supports | What it does **not** prove |
|--------------|-------------------------------|----------------------------|
| Upstream **#31** ApolloOS identify | Board/OS context consistent with ApolloOS on V4-SA; AFF_FPGA present in daemon SYSINFO | Probe binary stdout/exit not run this session |
| Fork review **#4** daemon foundation | U-DAE launches; protocol 6; SYSINFO OS/CPU/board | Not a substitute for #5–#8 feature tests |
| Fork **#5** MMIO | `poke=0` observed only | No live PEEK/POKE refusal trial |
| Fork **#6** / **#8** AUDIO | Capability `audio=1` only | No opcode 48 / Hear |
| Fork **#7** packaging | Exact U-DAE hash exercised | Installer/update paths not run |
| Fork **#10** probe AFF_FPGA | FPGA bit in daemon `attn_flags` | Probe executable not launched |
| Fork **F-DAE** | Proto-6 exclusive smoke PASSED ON HW | AUDIO/MMIO/probe/PIP still NOT RUN |

Draft PR comment text: `docs/APOLLO_V4_DRAFT_UPSTREAM_HW_COMMENT.md` (**not posted**).
