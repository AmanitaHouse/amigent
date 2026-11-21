# Upstream contribution coverage audit

**Audit date:** 2026-11-21  
**Fork `main`:** `79880b8f018ae735715de4f1d0e943acf4462dcd`  
**Upstream 1.4.0 release:** tag `v1.4.0` → commit `4fea38f602f84ddad2d5215fbc9d2742605d892c` (`1.4.0: release date`)  
**Upstream `main` tip at audit:** `f6aab1d` (one Windows deflate-harness commit after 1.4.0)

This document inventories fork-specific work relative to upstream 1.4.0 and the open contribution PRs. Having a fork-local review PR does **not** mean the change has been submitted upstream.

## Categories

| Code | Meaning |
|------|---------|
| AU | Already upstream (in 1.4.0 or merged) |
| SU | Submitted upstream, awaiting review |
| FL | Prepared in fork-local PR, not submitted upstream |
| IM | Implemented in fork, submission not yet prepared |
| FO | Intentionally fork-only |
| EX | Experimental or not suitable for upstream |
| UN | Uncertain — needs further investigation |

## Baseline notes

- Fork `main` contains upstream 1.4.0 (`4fea38f` is an ancestor) plus fork improvements.
- Native sources live under `src/native/…` on the fork; upstream contribution branches keep the flat `amiga/` layout.
- Packaged binaries differ by design: fork Apollo daemon `1e0e3f65…` (131292 bytes) ≠ protected contribution daemon `456fce26…` (129844 bytes).
- Fork-only: `.githooks/**`, `.gitattributes`, `src/native` restructuring, identity-guard tooling.

## Coverage table

| Feature / change | Sources / commits (indicative) | On fork `main` | In upstream 1.4.0 | Upstream PR | Fork review PR | Need upstream? | Depends on | Category | HW validation | Limitations |
|------------------|--------------------------------|----------------|-------------------|-------------|---------------|----------------|------------|----------|---------------|-------------|
| ApolloOS identification (probe/detect, no packaged Apollo daemon required) | `amiga/apollo/apollo_detect.c`, `apollo_probe.c`, `setup.py` | Yes (restored paths) | No | **#31** | (base of #4) | Yes — awaiting review | — | SU | Probe stdout/exit on V4 | ApolloOS ≠ 68080 alone |
| Apollo daemon foundation (68080 runtime, SYSINFO OS) | `amiga/amigentd.c`, `apollo_runtime.c`, … | Yes | No | — | **#4** | Yes after #31 | #31 | FL | **U-DAE proto-6 smoke PASSED ON HW** (exclusive); see `docs/APOLLO_V4_HARDWARE_EVIDENCE_SUMMARY.md` | AUDIO/MMIO/probe/install still NOT RUN; F-DAE NOT RUN |
| Native MMIO protection (PEEK/POKE refuse) | `apollo_mmio.c`, harness tests | Yes | No | — | **#5** | Yes after #4 | #31→#4 | FL | Prefer harness; live poke only if approved | Eight windows; software ≠ HW proof |
| AUDIO opcode 48 (protected stack) | `apollo_audio.c`, PROTOCOL, channel | Yes (fork also has richer build) | No | — | **#6** | Yes after #5 | MMIO | FL | Hear / `amiga_listen` | **U-DAE oneshot nonempty+signal PASSED ON HW** (Phase 2A); stream/Hear/F-DAE still NOT RUN |
| Protected packaging + monitor | `amigentd.apollo` `456fce26…`, probe `ab454b39…`, monitor `e06222ce…` | Partial — fork ships different daemon/probe | No | — | **#7** | Yes after #6 | AUDIO | FL | Install/update paths | CI needs setuptools≥77 (`86c1342`) |
| Viewer on-demand AUDIO playback | `channel.py`, `viewer.py`, web Hear | Yes | No | — | **#8** | Yes after #7 | packaging | FL | Hear controls | Fallback if Apollo binary missing |
| Probe AFF_FPGA core evidence | `apollo_probe.c`, probe `96ca1b38…` | Yes (newer probe) | No | — | **#10** | Yes after #7 | packaging | FL | Probe exit 0 = OS∧FPGA | #10 CI packaging flake until CI pin |
| Universal compatible-daemon fallback | `daemons.py`, `setup.py` | Yes | No | **#38** | — | Yes — awaiting review | — | SU | Install/update without V4 risk if staged | Win3.10 pause noise notes |
| Daemon identity in viewer About | `daemons.describe_connected`, locales | Yes | No | — | **#9** | Yes after #38 | #38 | FL | About dialog | Named file ≠ running image |
| Apollo-aware first-install selection (probe exit → 68080) | `setup.py` / `4ea1ef9` selection | Yes on main | No | — | — | Yes after #38+#7+#10 | #38, packaging, probe | IM | Fresh install selection | Do not fail-closed if `.apollo` missing; never auto `.080` |
| TLSONLY fail-closed remote plaintext | `amigentd.c`, `test_tlsonly.py` | Yes | No | **#27** | — | Awaiting review | — | SU | TLS/plain probe | |
| Reset chord only from Exec 36+ | `system.py`, `viewer.py` | Yes | No | **#28** | — | Awaiting review | — | SU | Soft reset path | |
| Screen handover keeps picture | `amigentd.c`, handover tests | Yes | No | **#29** | — | Awaiting review | — | SU | Viewer replace | |
| Fast-CPU packing waits for raw sample | `pack.py` | Yes (content) | No | **#30** | — | Awaiting review | — | SU | Packing mode | Pause CI noise unrelated |
| Pause-rounding (whole seconds) | `amigentd.py`, `viewer.py`, `test_pause.py` | Yes (fork #3) | No | **#32** | merged fork #3 | Awaiting review | — | SU | Pause countdown | |
| Chip RAM missing ≠ zero | viewer/fleet/locales | Yes | No | **#33** | — | Awaiting review | — | SU | About/memory | |
| Doctor `--help` exit 0 | `doctor.py` | Yes | No | **#34** | — | Awaiting review | — | SU | CLI only | No V4 needed |
| Russian locale | `locales/ru.json` | Yes | No | **#35** | — | Awaiting review | — | SU | Viewer strings | Identity About keys already on fork `ru.json`; upstream #35 still separate |
| Viewer fixed error reasons | `viewer.py` / JS | Yes | No | **#36** | — | Awaiting review | — | SU | Disconnect UX | |
| ApolloOS HRTmon program launch | `hrtmon.py`, `amiga_hrtmon` | Yes | No | **#37** | — | Awaiting review | ApolloOS | SU | **Approval-gated** | Never enter ROM HRTMon |
| PIP opcode 49 empty surface (`pip=0`) | fork `amigentd.c` / `apollo.c` | Yes (fork daemon) | No | — | — | **Decide** — not in protected stack | MMIO/safety | EX / UN | Only if picture path proven safe | Protected stack reserves 49 unimplemented |
| AMMX screen helpers | `ammx.s`, linked in fork daemon | Yes | No | — | — | **Not prepared** — fork-specific acceleration | ApolloCrossDev | EX / UN | Perf only; not required for protected contrib | Absent from `685309d` Makefile |
| Protocol-6 host/viewer/installer alignment | channel/server/tests | Yes | Partial (1.4.0 has proto 6) | — | embedded in Apollo PRs | Covered by Apollo stack + tests | — | FL/IM | Handshake | |
| Graphics mem / Fast RAM display | viewer/fleet | Yes | Partial | #33 related | — | Covered by #33 | — | SU | | |
| Native layout restore `src/native` | refactor commits | Yes | N/A | — | — | **No** | — | FO | — | Keep out of upstream diffs |
| `.githooks` / `.gitattributes` / identity guard | hooks | Yes | N/A | — | — | **No** | — | FO | — | |
| CI `setuptools>=77` for SPDX packaging tests | `.github/workflows/tests.yml` | Yes on main; validate `86c1342` | No on upstream tip | — | validate branch only | Yes with packaging PRs | packaging tests | IM | CI only | Upstream still missing pin |
| Experimental `amigentd.080` | excluded from package | Artifact only | N/A | — | — | **No** — never auto-select | — | EX | — | |
| Packaging CI validation | `validate/apollo-packaging-ci-setuptools` @ `86c1342` | Branch only | — | — | — | Cherry-pick onto submission heads | — | IM | — | Do not rewrite protected tips |

## Definitive dependency map

```
Upstream #31 ApolloOS identify
  └─ Fork #4 daemon foundation
      └─ Fork #5 MMIO
          └─ Fork #6 AUDIO 48
              └─ Fork #7 protected packaging + monitor
                  ├─ Fork #8 viewer playback
                  └─ Fork #10 probe AFF_FPGA evidence

Upstream #38 universal daemon fallback
  ├─ Fork #9 daemon identity
  └─ (not yet prepared) Apollo-aware first-install selection
         needs #38 + #7 + #10; reference integrate/apollo-complete @ 4ea1ef9

Independent / parallel (already upstream PRs):
  #27 TLSONLY  #28 reset Exec36  #29 handover  #30 packing
  #32 pause  #33 chip RAM  #34 doctor help  #35 Russian
  #36 viewer errors  #37 HRTmon

CI packaging pin (setuptools≥77): include when submitting packaging-related PRs
  (validated at 86c1342; already on fork main).
```

## Gaps still needing isolated upstream preparation

1. **Apollo-aware first-install Python selection** — on fork `main`, not a fork-local review PR yet; wait for #38 + packaging + probe evidence.
2. **PIP empty-handler / AMMX** — present on fork daemon only; **not** in protected contribution stack. Treat as experimental until a safe, reviewable unit exists. Do not bundle into the protected AUDIO/MMIO stack.
3. **CI setuptools pin for upstream** — needed wherever in-process wheel/sdist tests meet SPDX `license = "MIT"`.
4. **Russian About keys after #35** — fork already has them; when submitting identity upstream after #38, ensure keys land without duplicating #35’s catalog work.

## Intentionally fork-only

- `.githooks/**`, `.gitattributes`, commit/push identity guard  
- `src/native` / `tests/native` directory restructuring  
- Fork packaging of the larger Apollo daemon (`1e0e3f65…`) as the default distributed Apollo binary  

## Audit uncertainties

- Exact behavioural delta between fork daemon `1e0e3f65…` and contribution daemon `456fce26…` beyond known PIP/AMMX/AUDIO packaging differences has not been instruction-level diffed here; treat them as **distinct** validation targets.
- Whether a future PIP contribution is appropriate remains open until a safe picture path is established (current fork advertises `pip=0`).
- Physical Apollo register behaviour is software-reviewed and harness-tested only until authorised V4 tests run.
