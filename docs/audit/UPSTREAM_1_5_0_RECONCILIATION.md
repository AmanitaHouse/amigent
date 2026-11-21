# Upstream 1.5.0 reconciliation audit

**Audit date (UTC):** 2026-11-21  
**Auditor branch:** `audit/upstream-1.5.0-reconciliation`  
**Fork `main` (untouched):** `79880b8f018ae735715de4f1d0e943acf4462dcd`  
**Upstream remote:** `https://github.com/akustikrausch/amigent.git`  
**Upstream `v1.4.0`:** `4fea38f602f84ddad2d5215fbc9d2742605d892c`  
**Upstream `main` tip at audit:** `f6aab1d4953c1d83be2f71e73faef6fa5dc236ff`  
**Hardware evidence tip:** `dd81a39` on `validation/apollo-v4-evidence-prep`

This is an **audit**, not a merge. No fork `main` changes, no V4 contact, no PR close/rewrite, no release.

---

## Part A — Where is “1.5.0”?

| Question | Finding |
|----------|---------|
| Public branch named `feature/1.5.0` / `1.5.0`? | **Not present** on `akustikrausch/amigent` (`git ls-remote`: only `main`, `feature/1.3.0`, `feature/screen-pause`) |
| Tag / GitHub Release / PyPI `1.5.0`? | **None** (latest release and PyPI: **1.4.0**) |
| Upstream `main` version metadata | `__version__ = "1.4.0"`; CHANGELOG top section remains **1.4.0** |
| Relation of `main` to `v1.4.0` | `main` = `v1.4.0` **+ 1 commit** (`f6aab1d` Windows deflate harness binary mode) |
| Maintainer statements | On **2026-11-21**, akustikrausch commented on PRs **#27–#38** that each was **“merged into `feature/1.5.0` for 1.5.0”** (sometimes with modifications) |
| Issue #40 | Open: *Document what changes with several Amigas before 1.5.0* — confirms 1.5.0 is **planned**, not released |

### Audit verdict on the tip

**There is no publicly fetchable 1.5.0 implementation SHA at audit time.**

The active public baseline remains:

- **Released:** `v1.4.0` @ `4fea38f`  
- **Development tip (public):** `upstream/main` @ `f6aab1d` (still labelled 1.4.0)

**Private / unpublished:** maintainer’s `feature/1.5.0` (referenced only in PR comments). Diffs against that branch **cannot** be verified until it is pushed or otherwise shared.

GitHub PR state for #27–#38: all still **open**, **not** GitHub-merged into `main`. “Merged into `feature/1.5.0`” means **maintainer-side cherry-pick / private branch**, not a GitHub merge event.

---

## Part B — Upstream PRs #27–38

Evidence sources: GitHub PR metadata; `git merge-base --is-ancestor` vs `upstream/main` (all tips **not** in `main`); akustikrausch PR comments (2026-11-21); PR file lists from API/Web.

Legend for **1.5.0 status**:

- **Private-applied** = maintainer says applied to unpublished `feature/1.5.0`
- **Public-absent** = not in `upstream/main` / not released
- **Unchanged / Modified** = per maintainer comment

| PR | GitHub | Original intent | In `upstream/main`? | Private 1.5.0 (comment) | Maintainer changes | Behaviour / tests / docs | Regression risk (from comment only) | Status vs fork | Action (do not execute yet) |
|----|--------|-----------------|---------------------|-------------------------|--------------------|---------------------------|--------------------------------------|----------------|------------------------------|
| **#27** TLSONLY fail-closed | open | Remote plaintext closed whenever TLSONLY requested (even if TLS listener failed) | no | Private-applied, **modified** | Client distinguishes AmiSSL-open vs not; pinned cert reads plain hello without sending; PROTOCOL/GUIDE/FAQ lockout recovery | Intent preserved; client UX + docs expanded | Lockout is intentional; recovery docs added — **not** a silent weaken | Still required on public main; private tip likely supersedes our tip once published | When `feature/1.5.0` is public, compare daemon + client messages; close or retarget only after verification |
| **#28** Reset chord Exec 36+ | open | No reset chord before Exec 36 | no | Private-applied, **unchanged** | none claimed | Expected identical | Low | Redundant once 1.5.0 public | Leave open until public merge |
| **#29** Screen handover | open | Keep picture when replacement viewer waiting | no | Private-applied, **unchanged** | Maintainer will still HW-check before release | Expected identical | Low; pending maintainer HW check | Same | Leave open |
| **#30** Fast-CPU packing | open | No pack before raw sample on fast CPU | no | Private-applied, **unchanged** | none claimed | Expected identical | Low | Same | Leave open |
| **#31** ApolloOS identify | open | Identify ApolloOS; optional `.apollo` selection without requiring packaged Apollo daemon | no | Private-applied, **modified** | Detect by **exec 51 + AttnFlags bit 10 (`AFB_68080`)** only; **no `$DFF3FC` board fallback**; probe only if `amigentd.apollo` packaged; folded into #38 catalogue; `system.py` splits ApolloOS/AROS from AmigaOS 4 | Our AFF_FPGA / board-fallback path may differ; probe gating stricter | Detection narrowing may miss edge cases; board register removal is likely a **safety improvement** on non-Apollo | **Partially incorporated** privately; fork HW evidence (SYSINFO AFF_FPGA / 68080) still relevant for feedback | Adapt identify + packaging story to bit-10 model when 1.5.0 lands; do not force-push old tip |
| **#32** Pause rounding | open | Whole-second pause reporting / coarse clock | no | Private-applied, **adapted** | Adapted to **per-machine sessions**; ends flaky Windows check | Behavioural core kept; session model differs | Low | Partially superseded by session adaptation | Rebase/adapt only if public 1.5.0 differs from fork #3 |
| **#33** Chip RAM ≠ zero | open | Missing Chip RAM ≠ zero | no | Private-applied, **modified** | `fleet.py` for reworked overview; unknown Chip shown as **dash** | Intent preserved; UI differs | Low | Same | Align fleet overview when integrating |
| **#34** Doctor `--help` exit 0 | open | Help exits 0 | no | Private-applied, **unchanged** | none | Expected identical | Low | Same | Leave open |
| **#35** Russian locale | open | `ru.json` + language lists | no | Private-applied, **extended** | Russian for new 1.5.0 strings (update notice, Amiga manager, connection reasons, redesigned desktop); `type_hint` wording | Our catalog incomplete vs private 1.5.0 UI | Low | Partially superseded | Refresh `ru.json` from published 1.5.0 |
| **#36** Viewer error reasons | open | Fixed viewer sentences; no address/greeting on page | no | Private-applied, **modified** | Reason **keys** + i18n; more cases (TLS mismatch, ambiguous pin, TLSONLY without AmiSSL, changed machine); terminal keeps raw | Stronger than our PR; aligned with #27 client messaging | Low / improvement | Superseded when 1.5.0 public | Prefer upstream implementation |
| **#37** HRTmon | open | ApolloOS-gated `Run >NIL: HRTmon`; never enter ROM | no | Private-applied, **changed** | Works on **any** Amiga; `Which HRTmon` + Aminet pointer; load only; **agent told never to enter**; uses 1.5.0 per-machine session | Safer operational model; broader OS scope | Entering monitor still dangerous — upstream comment addresses this | Superseded in spirit; fork `hrtmon.py` must not fight new rules | Re-validate against published code; keep “never enter” |
| **#38** Compatible-daemon fallback | open | Catalogue + no downgrade; no auto `.080` | no | Private-applied, **modified** | Scripts renewed even if daemon kept; `--force`; equal `$VER` uses date; dead connection ≠ “not installed”; one CPU check; notice when 68000 chosen | Richer update path; selection folded with #31 Apollo | Low if downgrade guards preserved — **must verify in source when public** | Partially incorporated; fork identity (#9) / install selection depend on this | Diff against published 1.5.0 before adapting #9/#10 |

### Important classification rule

**Do not claim a GitHub merge** of #27–#38. Commits are **not** ancestors of `upstream/main`. Private application is **comment evidence only**.

---

## Part C — New upstream 1.5.0 functionality (from comments / #40, not in public tree)

Cannot inventory source diffs of unpublished `feature/1.5.0`. From maintainer text and issue #40, expected **new** themes include:

| Theme | Evidence | Conflict risk with fork |
|-------|----------|-------------------------|
| Multi-Amiga / per-machine sessions | #32, #37, #40 | High — fork session/host assumptions |
| Amiga manager / overview rework | #33, #35, #40 | Medium — fleet/viewer |
| Connection reason keys + i18n | #27, #36, #35 | Medium — viewer error paths |
| Redesigned remote desktop | #35 | Medium — viewer UI |
| Update notice | #35 | Low |
| Strict `amigas.json` / ID-named key/cert files | #40 | Medium — roster/tls paths; `.githooks` unaffected |
| Viewer follow paths `follow/ /` | #40 | Low–medium |
| Default Amiga required for some tools | #40 | Medium — MCP/fleet |
| Apollo detect: bit 10 only; probe gated on packaged `.apollo` | #31 | High vs fork probe/install |
| HRTmon any-OS + never-enter policy | #37 | Medium vs ApolloOS-only tool |
| Daemon update: renew scripts independently; `$VER` date | #38 | Medium vs fork update/identity |

Public `main` since `v1.4.0` adds only the Windows deflate harness fix (`f6aab1d`) — **not** the 1.5.0 feature set.

---

## Part D — Upstream public tip vs completed fork

| Area | Fork `main` `79880b8` | Upstream `main` `f6aab1d` | Notes |
|------|------------------------|---------------------------|-------|
| Layout | `src/native/amiga/`, `tests/native/`, `benchmarks/` | Flat `amiga/` | Keep fork layout; map paths on contrib |
| Apollo daemon / monitor / probe binaries | Packaged (F-DAE `1e0e3f65…`, etc.) | **Absent** | Fork-ahead |
| MMIO / AUDIO 48 / Hear / identity / AFF_FPGA probe | Present | **Absent** | Fork-ahead / review #4–#10 |
| HRTmon helper | Present (ApolloOS-oriented) | **Absent** on public main | Private 1.5.0 has different design |
| TLSONLY fail-closed (#27) | On contrib tips / coverage | **Absent** on public main | Private-applied |
| Compatible fallback (#38) | On fork / contrib | **Absent** on public main | Private-applied |
| Russian locale | Present | **Absent** | Private-applied + extended |
| Protocol 6 base | Yes | Yes (1.4.0) | Shared |
| `.githooks` / `.gitattributes` | Fork-only | N/A | Never upstream |

**Lost / weakened on public upstream?** No — public upstream simply has not yet published the private 1.5.0 applications. Fork remains **ahead** on Apollo stack.

**Safer / more complete on private 1.5.0 (claimed):** TLSONLY client messaging (#27+#36), Apollo detect without `$DFF3FC` (#31), HRTmon never-enter (#37), update script renewal (#38), multi-Amiga session model.

---

## Part E — Protected Apollo review stack (#4–#10)

| Unit | Upstream 1.5.0 (comment evidence) | Classification | Dependency impact |
|------|-----------------------------------|----------------|-------------------|
| **#4** Daemon foundation | Not claimed merged | **Still required** (adapt to published identify/#38) | Base after public #31-equivalent |
| **#5** MMIO | Not claimed | **Still required unchanged** in intent | After #4 |
| **#6** AUDIO 48 | Not claimed | **Still required** | After #5 |
| **#7** Packaging + monitor | Not claimed | **Still required**; selection must match #31/#38 private rules | After #6 |
| **#8** Viewer Hear | Not claimed | **Still required** | After #7 |
| **#9** Daemon identity | Not claimed; depends on #38 | **Still required with adaptation** to 1.5.0 update/session | After public #38-equivalent |
| **#10** Probe AFF_FPGA | Partially affected by #31 (probe only if `.apollo` packaged; bit-10 detect) | **Still required with adaptation** | Align with published #31 |

**Do not** submit old stacked branches blindly onto unpublished history. When `feature/1.5.0` is public, create **new** adaptation branches from that tip; **do not force-push** protected historical tips (`685309d`, review SHAs).

U-DAE binary `456fce26…` is the protected stack artifact — still the HW-validated contribution daemon; any **new** upstream Apollo native build is a **different** binary.

---

## Part F — Hardware evidence applicability

| Binary | SHA-256 | HW result | Applies to unpublished 1.5.0 Apollo code? |
|--------|---------|-----------|-------------------------------------------|
| U-DAE | `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` | Proto-6 TLS smoke PASS | **Only that exact image** |
| F-DAE | `1e0e3f65d46b62c93f7986d8137120ef5e2dec2515a9b63f6aa5909d2e75e9ca` | Proto-6 TLS smoke PASS | **Only that exact image** |

Docs: `docs/APOLLO_V4_STAGE2B_UDAE_RESULTS.md`, `docs/APOLLO_V4_STAGE2B_FDAE_RESULTS.md` (`dd81a39`).

**Renewed HW validation required when:**

- Upstream publishes a different `amigentd.apollo` (or equivalent) build  
- Native Apollo detect / MMIO / AUDIO / probe code changes vs tested images  
- Install/update paths that write `C:amigentd` are exercised (not done in Stage 2B)

**Still useful without new contact:** V4-SA / ApolloOS / 68080 / AFF_FPGA context for maintainer feedback on #31 (Vampire/ApolloOS testing welcome per comment).

Production V4 stays on protocol-5 `C:amigentd` — unchanged by this audit.

---

## Part G — Safe fork reconciliation strategy (plan only)

1. **Blocker:** Obtain public `feature/1.5.0` (or ask maintainer to push). Until then, **no** integration merge.  
2. **Comparison worktree** (when available): `git fetch upstream feature/1.5.0 && git worktree add … upstream/feature/1.5.0` — read-only analysis first.  
3. **Preserve on fork:** `src/native/**`, Apollo stack, F-DAE/U-DAE hashes in package until consciously rebuilt, `.githooks/**`, `.gitattributes`, TLSONLY/production recovery docs.  
4. **Import from 1.5.0:** multi-Amiga sessions, client TLSONLY messaging, viewer reason keys, HRTmon policy, update/`$VER` date logic, locale extensions — via dedicated integrate branch, **not** force onto `main` in one shot.  
5. **Directory map:** upstream `amiga/` ↔ fork `src/native/amiga/`; never submit `.githooks` upstream.  
6. **Regression checks:** full pytest; packaging CI (`setuptools≥77`); identity/About; daemon selection; TLSONLY tests; **no** V4 until authorised.  
7. **Native binaries:** do not overwrite verified F-DAE/U-DAE bytes without rebuild + hash update + HW revalidation plan.  
8. **Version bump / publish:** not in this audit.

Comparison-only stub branch name reserved: `compare/upstream-1.5.0-tip` — create only when the tip is fetchable.

---

## Part H — Recommended sequences

### Upstream contribution hygiene (recommendations only)

1. Leave #27–#38 **open** until `feature/1.5.0` is public **or** maintainer GitHub-merges/closes them.  
2. Optionally (with authorisation) thank and note private application — **do not post without approval**.  
3. After public 1.5.0: open **follow-up** PRs only for gaps (e.g. fork Apollo stack units not taken).  
4. Do **not** rewrite protected Apollo historical branches.

### Fork integration sequence (after public 1.5.0)

1. Fetch + comparison worktree  
2. Port session/multi-Amiga + TLSONLY client + viewer reasons  
3. Reconcile identify/#38 selection with fork packaging  
4. Re-stack or adapt review #4–#10 as **new** branches from 1.5.0 tip  
5. Packaging CI + software tests  
6. Authorised HW only for **new** native hashes  

### Contribution order (conceptual)

Public 1.5.0 base → remaining Apollo foundation/MMIO/AUDIO/packaging/Hear/identity/probe (adapted) → Stage 3 HW as authorised.

---

## Unresolved questions

1. Will `feature/1.5.0` be pushed to `akustikrausch/amigent`, and under what exact SHA?  
2. Exact source diff of maintainer modifications (comment summaries only today).  
3. Whether private 1.5.0 already contains any of review #4–#10 beyond #31/#38 identify/selection.  
4. Release timing vs issue #40 documentation milestone.

---

## Conclusion

Upstream **1.5.0 development is real in maintainer workflow** (PR comments + issue #40) but **not published** as a fetchable ref. Public baseline remains **1.4.0** (`f6aab1d`). PRs #27–#38 are **privately applied** (per comments), still **GitHub-open**, and **absent from `main`**. Apollo review stack #4–#10 largely **still required**. Hardware evidence remains valid **only** for the tested U-DAE/F-DAE hashes.
