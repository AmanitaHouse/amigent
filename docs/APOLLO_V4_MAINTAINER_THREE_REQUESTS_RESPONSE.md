# Maintainer three Apollo V4 requests — evidence status

**Date:** 2026-11-21  
**Scope:** Offline review + **authorised Session A hardware** for requests 1–2. Request 3 (`--update`) **not** run.  
**1.5.0 public tip:** `upstream/feature/1.5.0` @ `651a357b6aae8800c314799347b257e9884e2773`  
**Evidence:** `~/amigent-evidence/stage4-maintainer-150-regress-cpu/20261121T113257Z`  
**HW candidate:** `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` (128744 B) — staged `Programs:AmiGent-Stage4/amigentd.d4`  
**Production restored:** `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` · protocol 5 TLS · SYSINFO ×2 PASS  

**Distinction:** 1.5.0 `regress.py` / host tools against our Apollo-packaged daemon `63db83ff…` does **not** validate the maintainer’s packaged classic 1.5.0 native daemon.

---

## Summary table

| Maintainer request | Status | Actual evidence | Remaining requirement |
|---|---|---|---|
| Native build + `regress.py` | **PARTIAL** — safe subset run | Exact command below; **14 PASS / 3 FAIL / 0 SKIP** on 17 allowlisted checks; full unrestricted script **not** run | Optional follow-up on `version`/`job`/`live_output` only; still no full `regress.py` |
| `amiga_status` / `amiga_cpu` / FPU | **PARTIAL** | Verbatim 1.5.0 outputs captured; SYSINFO CPU **68080** PASS; load sampler PASS; live FPU line **missing** (host mistook ApolloOS Version as AmigaOS 4) | Host `describe_system` ApolloOS path fix; re-capture FPU line after that |
| `amigent-setup --update` | **NOT HARDWARE TESTED — APOLLO PACKAGING/SELECTION BLOCKER** | Offline only; 1.5.0 package has no `amigentd.apollo` | Separate auth + packaging/policy |

---

## Session A results (2026-11-21T113257Z)

### Offline GO
- Source pinned `651a357…`; `regress.py` SHA-256 `faad890aa4ee6dc229c1dd2209fe0048f6188d6f57cb7e862e431577a26ed988`
- Allowlist 17 names; no prohibited intersection; **OFFLINE GO**

### Preflight (after operator reboot)
- Protocol 5 TLS verified; plaintext rejected; ApolloOS / 68080 / Kickstart 51.51; SYSINFO ×2 stable
- Production live hash `b00fef0e…`; staged `.d4` hash `63db83ff…` (128744)
- Backup `…/20261121T010816Z/v4-production-C-amigentd.bin` OK

### Handover / launch / restore
- Physical MessageBox confirmation: operator_ready → awaiting quit
- Production QUIT → candidate `…/amigentd.d4 TLSONLY` → protocol **6**, `audio=1` `poke=0` `trace=0` `pip=0`
- Candidate QUIT → production restore → protocol **5** TLS, ApolloOS/68080, SYSINFO ×2 PASS
- Mid-session network outage after hung read required reboot (recorded); session continued after recovery

### Request 1 — exact regression command

```text
/home/ami/amigent-test/bin/python scripts/regress.py V4SA --only \
  status,version,exec,missing_volume,job,live_output,loaded,journal,gurus,screen,state,files,tree,packing,notes,screen_diff,close_shell \
  --report <evidence>/private/regress-report.md
```

(from worktree `/mnt/d/Development/per/amigent-worktrees/inspect-150` @ `651a357…`)

| Verdict | Checks |
|---|---|
| PASS (14) | status, exec, missing_volume, loaded, journal, state, gurus, screen_diff, files, screen, packing, tree, notes, close_shell |
| FAIL (3) | **version** (`Version` on `Programs:AmiGent-Stage4/amigentd` → rc=20 object not found; staged file is `amigentd.d4`), **job**, **live_output** (job still running) |
| SKIP (0) | — |
| Not run | All excluded RISK/UI/INST/TRACE/monitor/clipboard/takeover/… |

Daemon remained responsive after the subset. Full unrestricted `regress.py` remains untested.

### Request 2 — CPU / FPU / load

**SYSINFO (daemon):** `os=ApolloOS`, `cpu=68080`, `attn_flags=42111`, board V4-SA.

**`amiga_status` anomaly:** `system.os` reported **AmigaOS 4** with 68k-emulation note; **no** `fpu` / `processor` fields. Cause: 1.5.0 `describe_system`/`native_ppc` path on `Version`/`CPU` text skipped `_read_fpu`. Offline reinterpret of the same flags: `describe_fpu(42111)` → `68080 with FPU` (FPU bits present; **not** inferred from bit 10 alone).

| Classification | Result |
|---|---|
| CPU model identification | **PASS** (SYSINFO `cpu=68080` + bit 10) |
| FPU reporting (live host field) | **INCONCLUSIVE** (field absent due to AmigaOS 4 mis-ID) |
| CPU-load sampling (`amiga_cpu` 2 s) | **PASS** (idle 97.5 %; task breakdown returned) |

`amiga_cpu` is a load sampler, not a CPU-model tool.

### Request 3
**Not run.** Public 1.5.0 package lacks `amigentd.apollo`; live update remains NO-GO.

---

## A. PR #10 relevance verdict

**NO NEW UPSTREAM PR for #10.** Unchanged from prior review. Bit 10 ≠ FPU.

---

## Draft maintainer response (**NOT POSTED**)

> Thanks — we ran an authorised exclusive V4 session against public `feature/1.5.0` @ `651a357…` using our previously validated Apollo daemon `63db83ff…` (not the packaged classic 1.5.0 binary).
>
> **1. `regress.py`**  
> Safe `--only` subset (17 checks; no TRACE/UI/monitor/clipboard/installer/MMIO): **14 passed, 3 failed**. Failures: `version` (SYSINFO `self` path `Programs:AmiGent-Stage4/amigentd` vs staged `amigentd.d4`), plus `job` and `live_output`. Full unrestricted regression was not run. This does not claim a hardware pass of the maintainer’s packaged 1.5.0 daemon.
>
> **2. `amiga_status` / `amiga_cpu` / FPU**  
> Daemon SYSINFO: ApolloOS, **68080**, `attn_flags=42111`. `amiga_cpu` (2 s load sample) OK. Live `amiga_status` `system` block incorrectly labelled the machine **AmigaOS 4** (68k-emulation note) and therefore omitted the FPU line; offline `describe_fpu(42111)` yields `68080 with FPU` from FPU AttnFlags bits (not from bit 10 alone). Happy to re-test after an ApolloOS Version-parsing fix.
>
> **3. `amigent-setup --update`**  
> Still not run on production. Public 1.5.0 ships no `amigentd.apollo`, so selection would favour classic `amigentd` — blocker until packaging/policy is agreed.
>
> Production was restored to protocol 5 / `b00fef0e…` with SYSINFO ×2 after the session.

---

## Confirmations

- Fork `main`, upstream PRs, and production `C:amigentd` bytes **unchanged** (exclusive staged candidate only).  
- No upstream comment posted.  
- No `--update`. No native rebuild.
