# Maintainer three Apollo V4 requests — evidence status

**Date:** 2026-11-21  
**Hardware session:** authorised Session A (requests 1–2). Request 3 not run.  
**1.5.0 tip tested:** `651a357b6aae8800c314799347b257e9884e2773`  
**Daemon under test:** `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` (128744 B) staged as `Programs:AmiGent-Stage4/amigentd.d4`  
**Evidence:** `~/amigent-evidence/stage4-maintainer-150-regress-cpu/20261121T113257Z`  
**Production restored:** `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` · protocol 5 · SYSINFO ×2 PASS  

**Distinction:** 1.5.0 host tools / safe `regress.py` against our Apollo-packaged daemon ≠ hardware pass of packaged classic 1.5.0 `amigentd`.

---

## Summary table

| Maintainer request | Status | Actual evidence | Remaining |
|---|---|---|---|
| Native build + `regress.py` | **PARTIAL** | Safe `--only` **14 PASS / 3 FAIL / 0 SKIP**; unrestricted script not run | Optional follow-up on job/FOLLOW/`self` path; no full regress |
| `amiga_status` / `amiga_cpu` / FPU | **PARTIAL** | CPU **68080** via SYSINFO PASS; load sampler PASS; live FPU field absent (root cause offline) | Apply/review SYSINFO reconcile patch; **do not** claim live FPU verified |
| `amigent-setup --update` | **NOT HARDWARE TESTED — APOLLO PACKAGING/SELECTION BLOCKER** | 1.5.0 package has no `amigentd.apollo` | Separate auth + packaging/policy |

---

## Offline root causes (post-session)

### 1. AmigaOS 4 misclassification

**Exact path:** `amiga_status` → `_system_facts()` → `describe_system(Version, CPU)` → `native_ppc` → skip `_read_fpu`.

Captured live `system` block: `os=AmigaOS 4`, `kickstart=51.51`, `workbench=40.0`, no `cpu`/`fpu`/`processor`, plus the 68k-emulation note.

Offline reproduction (pinned 1.5.0):

```text
describe_system("Kickstart 51.51, Workbench 40.0\n", "")
  → os=AmigaOS 4, cpu='', native_ppc=True
```

When `C:CPU` yields a `68080` token, the same Kickstart line becomes ApolloOS. Foundation tests already document Kickstart ≥50 + empty CPU → AmigaOS 4.

**Meanwhile SYSINFO** (same session) correctly had `os=ApolloOS`, `cpu=68080`, `attn_flags=42111`. `describe_system` never consults SYSINFO. This is **detection precedence / host-tool vs daemon SYSINFO mismatch**, not a cached stale value and not a daemon protocol error.

Aligns with PR #31 intent (ApolloOS ≠ AmigaOS 4; 68080 / exec 51 evidence) but the host Version/CPU path lagged SYSINFO.

### 2. Missing live FPU field

Because `native_ppc(AmigaOS 4)` was true, `_system_facts` took the emulation branch and **never called** `_read_fpu` / `describe_fpu`. Offline `describe_fpu(42111)` → `68080 with FPU` (FPU AttnFlags bits, **not** bit 10 alone). Correcting OS classification restores the FPU code path (proven with FakeAmiga + reconcile).

| Layer | Result |
|---|---|
| Raw AttnFlags `42111` | Observed on HW |
| Software-inferred FPU | Offline OK; **live field not emitted** |
| FPU instruction execution | **Not tested** |

### 3. Prepared fix (not published as PR)

Branch `review/apolloos-sysinfo-reconcile` @ `7a45c57` (from `651a357…`):

- `system.reconcile_system(facts, sysinfo)` — if SYSINFO shows ApolloOS / 68080 / `AFF_68080`, override false AmigaOS 4 and fill `cpu`
- `_system_facts` applies reconcile before `native_ppc` / FPU
- Tests: Session A shape + end-to-end FakeAmiga status; **47 passed** (`test_apollo_foundation` + `test_fpu`)

No upstream PR opened.

### 4. Regression failures (preserve **14 / 3 / 0**)

| Check | Expected | Actual | Verdict |
|---|---|---|---|
| `version` | `Version "{self}"` rc=0 | `self=Programs:AmiGent-Stage4/amigentd`; Version rc=20 object not found; file on disk is `amigentd.d4` (SHA verified) | **Test / Amiga `self` path-form quirk** — known since D4; not wrong binary |
| `job` | Echo/Search/break job pipeline | `AssertionError` with empty detail (failed assert message was empty output) | **Likely follow-on of bad `self` path** — job scripts `Run "{self}" FOLLOW …`; unresolved without re-run |
| `live_output` | Early output contains `rwed` while still running | `[job 2 still running]` only (no listing yet / empty out) | **Same FOLLOW/`self` compatibility** — PIPE live path needs runnable `self`; timing secondary |

Not assertion rewrites; product/compat issue when `GetProgramName`/`self` omits `.d4`.

### 5. Reboot / network chronology (UTC)

| Time | Event |
|---|---|
| ~11:36 | Offline GO |
| ~11:39 | First post-TLS-pin connect reached channel; preflight **read timed out** |
| 11:41:40 | `network-outage.json` — ARP present, ICMP/TLS dead (errno 113) |
| *(operator)* | **Operator-initiated reboot** (stated in chat) during recovery — **not** mid-candidate-session |
| 11:42 | Preflight PASS after reboot; shell check PASS |
| 11:43:40 | Physical handover MessageBox Yes (“after reboot”) |
| 11:44 | Production QUIT → candidate proto-6 |
| 11:45 | Safe regress + status/cpu on candidate |
| 11:46–11:52 | Candidate QUIT; production restore (second prompt); verify PASS |

Session was **not** reboot-free: reboot occurred **before** candidate launch, after preflight network loss.

### 6. Updater

**Not run.** Public 1.5.0 package still has **no** `amigentd.apollo`; ApolloOS selection falls back to classic `amigentd` — live-update **NO-GO**.

---

## Draft GitHub comment (**NOT POSTED**)

> We completed an authorised exclusive V4 session against public `feature/1.5.0` @ `651a357…` using our previously validated Apollo daemon `63db83ff…` (not the packaged classic 1.5.0 binary). Production was restored afterward.
>
> **1. `regress.py`** — Safe `--only` subset (17 checks; no TRACE/UI/monitor/clipboard/installer/MMIO): **14 passed, 3 failed** (`version`, `job`, `live_output`). Full unrestricted regression was not run. The `version` failure matches a known `SYSINFO self=` path form (`…/amigentd` vs staged `amigentd.d4`); SHA-256 of the staged file was verified independently. `job` / `live_output` look like follow-ons when job FOLLOW uses that `self` path. This is not a hardware pass of packaged 1.5.0 `amigentd`.
>
> **2. `amiga_status` / `amiga_cpu` / FPU** — Daemon SYSINFO: ApolloOS, **68080**, `attn_flags=42111`. `amiga_cpu` (2 s load sample) OK. Live `amiga_status` `system` incorrectly said **AmigaOS 4** (and omitted FPU) because `describe_system(Version, CPU)` with Kickstart 51.51 and an empty/unparsed CPU line falls through to AmigaOS 4 and then skips AttnFlags FPU reporting — even though SYSINFO was already correct. Offline, `describe_fpu(42111)` yields `68080 with FPU` from FPU bits (not bit 10 alone). We prepared a small local reconcile of SYSINFO→`system` facts on `review/apolloos-sysinfo-reconcile` (tests green); no PR opened yet. We do **not** claim live FPU reporting was verified on hardware.
>
> **3. `amigent-setup --update`** — Not run on production. Public 1.5.0 still ships no `amigentd.apollo`, so an ApolloOS update would select classic `amigentd` — packaging/policy blocker before any live update test.
>
> Chronology note: PC lost the V4 briefly during preflight; the operator rebooted **before** candidate launch; the candidate session itself then completed and production was restored.

---

## Confirmations

- Fork `main`, upstream PRs, production bytes: **unchanged** by the offline investigation.  
- No hardware contact for this follow-up.  
- No `--update`. No upstream comment posted.  
- Review branch local (+ optional fork push): `review/apolloos-sysinfo-reconcile` @ `7a45c57`.
