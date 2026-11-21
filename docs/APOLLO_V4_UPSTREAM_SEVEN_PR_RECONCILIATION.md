# AmiGent — Seven fork PRs + upstream #31 reconciliation

**Date:** 2026-11-21  
**Fork:** `AmanitaHouse/amigent` · tip `main` `fad6693…`  
**Upstream:** `akustikrausch/amigent` · public `main` `f6aab1d…` · latest public tag `v1.4.0`  
**Authorisation for this document:** inspection + drafting only — **no** hardware sessions, merges, releases, PR closes, or GitHub posts

## 0. Open-count verification

| Repo | Open PRs inspected | Count |
|---|---|---|
| Fork `AmanitaHouse/amigent` | **#4–#10** | **Exactly seven** |
| Upstream `akustikrausch/amigent` (AmanitaHouse Apollo sequence) | **#27–#38** still **OPEN** against public `main` | **Twelve** (not seven) |

The seven open **fork** PRs are **not** the same set as the twelve open **upstream** contributions.  
Fork #4–#10 are stacked Apollo review vehicles. Upstream #27–#38 are independent small contributions plus Apollo identify (#31) and daemon fallback (#38).

`feature/1.5.0` on `akustikrausch/amigent`: **HTTP 404** (branch not publicly visible). Maintainer comments on #27–#38 stating “merged into `feature/1.5.0`” are therefore **reported private integration**, not independently verifiable in public source.

Public upstream `main` contains **no** `amiga/apollo/`, no `daemons.py`, no `connect_audio`, no Apollo detect/probe/MMIO/AUDIO sources (verified by tree/grep against `upstream/main`).

---

## 1. Exact seven open fork PRs

| Fork PR | Title | Base → Head | Tip commit | URL |
|---|---|---|---|---|
| **#4** | Add the ApolloOS native daemon foundation | `contrib/apollo-identify` → `contrib/apollo-daemon` | `1134d9c` | https://github.com/AmanitaHouse/amigent/pull/4 |
| **#5** | Protect Apollo MMIO ranges from generic PEEK and POKE | `contrib/apollo-daemon` → `contrib/apollo-mmio-safety` | `00857e5` | https://github.com/AmanitaHouse/amigent/pull/5 |
| **#6** | Add Apollo AUDIO opcode 48 on the MMIO-protected daemon | `contrib/apollo-mmio-safety` → `review/apollo-protected-audio` | `b918ce9` | https://github.com/AmanitaHouse/amigent/pull/6 |
| **#7** | Package the protected Apollo daemon, probe and monitor | `review/apollo-protected-audio` → `integrate/apollo-safe-upstream-stack` | `685309d` | https://github.com/AmanitaHouse/amigent/pull/7 |
| **#8** | Add on-demand Apollo AUDIO playback to the viewer | `integrate/apollo-safe-upstream-stack` → `contrib/apollo-audio-review` | `5b1ff4c` | https://github.com/AmanitaHouse/amigent/pull/8 |
| **#9** | Report connected daemon identity and capabilities in the viewer | `contrib/daemon-compatible-fallback` → `contrib/daemon-identity` | `739aa4c` | https://github.com/AmanitaHouse/amigent/pull/9 |
| **#10** | Expose Apollo 68080 core evidence during initial setup probing | `integrate/apollo-safe-upstream-stack` → `review/apollo-probe-core-evidence` | `4924da4` | https://github.com/AmanitaHouse/amigent/pull/10 |

Protected packaging hashes on #7 tip (`685309d`):

- `amigentd.apollo` `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` (129844 B)  
- Probe (pre-#10) `ab454b39988bd7b88c24058d0398507456ff12ff180b638d626beac821e1aff4`  
- Monitor `e06222ce73f62a1ec6cab7a370e3e6154f1c396160a4813d29ad7fd7cdb9626e`

Fork `main` currently ships a **different** Apollo daemon: `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` (128744 B).

None of the seven tip commits is a git ancestor of fork `main` (parallel history / `src/native` layout). Equivalent **behaviour** is present on fork `main` under `src/native/…` and host Python, but the protected flat-`amiga/` contribution tips remain the upstream-facing patch vehicles.

---

## 2. Seven-row upstream reconciliation

| Fork PR | What it contributes | On fork `main`? | Corresponding upstream PR | In public upstream `main`? | Integrated differently? | Evidence | Private 1.5.0 only reported? | Disposition |
|---|---|---|---|---|---|---|---|---|
| **#4** | 68080 ApolloCrossDev daemon foundation; SYSINFO ApolloOS/board; no AUDIO/PIP | **Functional yes** (`src/native/…`); tip commit **not** in main ancestry | None opened yet (depends on #31) | **No** | Maintainer adapted **#31** detect only; daemon foundation not visible publicly | Tree/grep `upstream/main`; fork PR files vs `origin/main` | Unknown whether private 1.5.0 contains foundation | **SHOULD CONTRIBUTE UPSTREAM** (after public #31/1.5.0 base) |
| **#5** | Eight-window MMIO PEEK/POKE refuse + harness | Functional yes (`apollo_mmio.c`) | None yet | **No** | N/A publicly | Same | Unknown | **SHOULD CONTRIBUTE UPSTREAM** |
| **#6** | AUDIO opcode 48 + channel host support on MMIO-protected daemon | Functional yes (fork also evolved further) | None yet | **No** | N/A publicly | Same | Unknown | **SHOULD CONTRIBUTE UPSTREAM** |
| **#7** | Package protected `456fce26…` daemon + probe + monitor | **Partial** — main packages **`63db83ff…`**, not `456fce26…` | None yet | **No** | Fork distribution deliberately differs | Hash compare main vs `685309d` | Unknown | **SHOULD CONTRIBUTE UPSTREAM** (keep protected hashes; do not export fork daemon) |
| **#8** | Viewer / `amiga_listen` on-demand Hear | Functional yes; main also has later Hear UI safety (fork PRs #12/#13 merged) | None yet | **No** | Fork main is ahead of #8 tip | Diff presence of `connect_audio` / Hear | Unknown | **SHOULD CONTRIBUTE UPSTREAM** (rebase onto public base; include later safety only if reviewable) |
| **#9** | Viewer About: connected daemon identity | Functional yes (`describe_connected`) | Depends on upstream **#38** (not a duplicate of #38) | **No** | N/A publicly | `upstream/main` lacks `daemons.py` | #38 reported merged into private 1.5.0 | **SHOULD CONTRIBUTE UPSTREAM** after public #38 |
| **#10** | Probe prints `68080` on AttnFlags bit 10; exit 0 only if ApolloOS ∧ bit | Functional yes (probe `96ca1b38…` on main) | Touches #31 detect semantics | **No** | Maintainer #31 reply: detect by **exec 51 + bit 10 (`AFB_68080`)**; **remove `$DFF3FC` fallback**; probe only if `amigentd.apollo` packaged | Stage 3A HW on our probes; #31 comment vs our `apollo_detect.c` still has IdString + `$DFF3FC` | **Yes** — private detect not verifiable | **NEEDS MAINTAINER CONFIRMATION** before opening upstream |

Disposition legend used above matches the requested categories. None of #4–#10 is **ALREADY UPSTREAM** in public `main`. None is **SUPERSEDED** by a public merge. Several are **EQUIVALENT** only as *fork-main functionality*, not as public-upstream code.

---

## 3. Upstream PR #31 — state and discussion

**URL:** https://github.com/akustikrausch/amigent/pull/31  
**State:** **OPEN** against `akustikrausch/amigent:main` (not merged/closed on GitHub)  
**Head:** `contrib/apollo-identify` @ `dcb1f8f`  
**Files:** `amiga/Makefile.apollo`, `amiga/apollo/apollo_detect.c`, `apollo_probe.c`, `src/amigent/setup.py`, `tests/test_apollo_foundation.py`

### What #31 originally proposed

Identify ApolloOS without requiring a packaged Apollo daemon; copy `amigentd.apollo` only when ApolloOS is identified **and** the file is present; otherwise keep 1.4.0 classic selection. Probe source included; no 68080 daemon build; protocol 6 still ends at opcode 47; AUDIO/PIP reserved.

### Discussion timeline

1. **AmanitaHouse** — listed protected follow-up branches (`685309d` stack); stated native HW behaviour **not** established for the new daemon.  
2. **akustikrausch** — “merged into `feature/1.5.0`” **with changes**:  
   - Detect by exec 51 + AttnFlags bit 10 (`AFB_68080`); **no** `$DFF3FC` fallback for OS detect; `apollo_board()` reporting-only.  
   - Probe/questions only when `amigentd.apollo` is packaged.  
   - Selection folded into #38’s daemon catalogue.  
   - `system.py` separates ApolloOS/AROS from AmigaOS 4.  
   - Cannot test on Vampire; HW feedback after release welcome.  
3. **AmanitaHouse HW comment** — exclusive sessions for `456fce26…` and `1e0e3f65…`: proto-6 TLS, ApolloOS/68080, SYSINFO/read-only, clean QUIT + production restore. Explicitly **did not** claim AUDIO, MMIO, probe, monitor, HRTmon, install/update, or any 1.5.0 executable. Asked to review public 1.5.0 before adapting remaining stack.

### What the maintainer requested

Not a specific additional lab checklist. Requested posture: HW feedback welcome (esp. Vampire); private adaptation already applied. Outstanding for us: factual update of what we have since tested, without claiming the private detect rewrite.

### #31 disposition

**UPSTREAM PR PENDING** publicly + **NEEDS MAINTAINER CONFIRMATION** that private 1.5.0 still matches the adapted detect described in the comment (branch not visible). Do **not** treat as **ALREADY UPSTREAM**.

---

## 4. Hardware evidence mapped to claims (executable identity required)

| Claim usable in a #31 follow-up | Supporting test | Executable / artifact | OK to state? |
|---|---|---|---|
| V4-SA runs ApolloOS / Kickstart 51.51 / 68080 / AFF_FPGA (`attn_flags` includes bit 10) | Stage 2–4 SYSINFO | Production proto-5 `b00fef0e…`; candidates below | **Yes** (board context) |
| Protected contribution daemon proto-6 smoke | Stage 2B U-DAE | `456fce26…` (129844) | **Yes** (already posted) |
| Earlier fork daemon proto-6 smoke | Stage 2B F-DAE | `1e0e3f65…` (131292) | **Yes** (already posted) |
| Packaged identify probe stdout `ApolloOS` / rc 0 | Stage 3A U-PRB | `ab454b39…` (3112) | **Yes — new vs posted comment** |
| Core-evidence probe stdout `ApolloOS`+`68080` / rc 0 (OS∧bit10) | Stage 3A F-PRB | `96ca1b38…` (3224) | **Yes — new vs posted comment** |
| Three protected MMIO PEEK refuses | Stage 4 D2 | `00443719…` (129944) | **Yes for #5 lineage — not a #31 detect claim**; do not extrapolate other windows |
| Non-MMIO D2 controls | Stage 4 D2 | same | Preserve limitation: ROM/`$4` were **out of authorised control class** |
| AUDIO oneshot / stream / stock Hear (corrected fork) | Stage 3B | `00443719…` | Useful for **#6/#8**, not #31 identify |
| Hardened daemon proto-6 + AUDIO + Hear | Stage 4 D4–D5B | `63db83ff…` (128744) | Fork distribution; **not** protected #7 hash; choppy Hear + connection-loss = findings only |
| U-DAE AUDIO oneshot nonempty | Stage 3B Phase 2A | `456fce26…` | #6 support |
| Live POKE write / TRACE set / full MMIO map / install `--update` / private 1.5.0 detect | — | — | **Do not claim** |

Bit note: our `AFF_FPGA` is `#define AFF_FPGA (1L << 10)` — same bit index the maintainer names `AFB_68080`. That **does not** prove the private detect rewrite (IdString/`$DFF3FC` removal / packaged-only probe gating).

---

## 5. What should actually go upstream

| Fork PR | Generally useful upstream? | Apollo- vs fork-specific | Upstream already equivalent? | Conflicts with stated 1.5.0 direction? | Small independent change? | Keep out of upstream PR |
|---|---|---|---|---|---|---|
| #4 | Yes | Apollo | No (public) | Unknown until public 1.5.0 | Yes as stacked PR after identify | `.githooks`, `src/native` rewrite, PIP/AMMX |
| #5 | Yes (safety) | Apollo | No | Unlikely | Yes after #4 | Evidence dumps |
| #6 | Yes | Apollo | No | Unlikely (opcode 48 reserved in #31 text) | Yes after #5 | Fork-only stream dumps; fidelity campaigns |
| #7 | Yes | Apollo packaging | No | Must align with #38 catalogue + packaged-only probe rule | Yes after #6 | Fork `63db83ff…` binary; experimental `.080` |
| #8 | Yes | Host/viewer | No | Unlikely | Yes after packaging | Soak evidence; private paths |
| #9 | Yes | Host/viewer | No | Wait for #38 | Yes after #38 | Duplicate Russian catalog (#35) |
| #10 | Yes, but shape TBD | Apollo probe contract | No | **Possible** — private detect uses AFB_68080 naming + stricter OS detect + packaged-only probing | Yes once confirmed | `$DFF3FC` OS-detect fallback if maintainer rejected it |

**Fork-only (do not export):** `.githooks/**`, `.gitattributes`, identity-guard tooling, `src/native` directory restructuring as a patch, fork daemon `63db83ff…` as the “upstream” binary, private evidence trees, credentials.

**Protected contribution branches:** preserve; do not rewrite tips.

---

## 6. Actionable upstream sequence (authorisation-gated)

### First — resolve #31 evidence loop

Post **one** factual follow-up on upstream #31 (draft in `docs/APOLLO_V4_DRAFT_UPSTREAM_HW_COMMENT.md` section A2). Content:

- Update that Stage 3A probe HW now exists for `ab454b39…` and `96ca1b38…`.  
- Confirm bit-10 core evidence on V4-SA without claiming private 1.5.0 detect.  
- Reaffirm we still cannot verify unpublished `feature/1.5.0` adaptations.  
- Do **not** re-post the earlier daemon smoke paragraph as if new.  
- Do **not** broaden to POKE/TRACE/full MMIO/install.

### Second — fork PRs already represented upstream?

| Item | Action when authorised |
|---|---|
| Fork #4–#10 | **Do not close** as superseded yet — they are the protected review stack, not duplicates of public merges |
| Upstream #27–#38 | Remain OPEN on public `main` despite “merged into 1.5.0” comments — **NEEDS MAINTAINER CONFIRMATION** / leave until public 1.5.0 lands; closing would erase the public review record without a visible merge |

### Third — genuinely missing from public upstream (priority)

1. Apollo daemon foundation (#4 → upstream PR after public identify base)  
2. MMIO refuse (#5)  
3. AUDIO 48 (#6)  
4. Protected packaging + monitor (#7) using `456fce26…` lineage  
5. Viewer Hear (#8), optionally folding later Hear safety from fork #12/#13  
6. Daemon identity (#9) after public #38  
7. Probe core-evidence (#10) **only after** confirm against public 1.5.0 detect  

Also still missing as a prepared upstream unit: Apollo-aware first-install Python selection (fork `integrate/apollo-complete` / `4ea1ef9` reference) — depends on #38+#7+#10.

### Fourth — remain fork-only

Layout restore, hooks, fork-hardened `63db83ff…` distribution policy, AMMX, PIP empty surface, Stage 4 D3 TRACE disable packaging, private evidence.

### Blocked solely by unpublished 1.5.0

- Independent verification of adapted #31 detect / #38 catalogue fold-in / #37 HRTmon rewrite / other “merged into 1.5.0” deltas  
- Safe rebase of protected Apollo stack onto maintainer tip  
- Claiming behavioural equivalence to private 1.5.0 AUDIO/detect commentary  

**Not** blocked by 1.5.0: posting the #31 HW follow-up; keeping fork review PRs open; preparing patch series offline against public `main` for later retarget.

---

## 7. Ready-to-review #31 follow-up

See **section A2** in `docs/APOLLO_V4_DRAFT_UPSTREAM_HW_COMMENT.md`. **Not posted.**

---

## 8. Confirmation

- No hardware session was run for this reconciliation.  
- No merge, release, upstream PR creation, PR close, or GitHub comment was published.  
- Existing evidence and protected contribution tips are preserved.
