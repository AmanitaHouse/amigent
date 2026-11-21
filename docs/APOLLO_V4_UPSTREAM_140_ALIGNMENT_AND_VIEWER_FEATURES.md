# AmiGent — Upstream 1.4.0 alignment and Viewer-feature completion audit

**Date:** 2026-11-21  
**Method:** Live `git fetch` + Windows `gh` against `AmanitaHouse/amigent` and `akustikrausch/amigent`  
**Docs branch:** `validation/apollo-v4-evidence-prep`  
**Authorisation:** read-only Git/GitHub + docs only — **no** hardware, merges, upstream posts, or `main` changes  
**Private `feature/1.5.0`:** still **HTTP 404** — not inspected; maintainer “merged into 1.5.0” comments are **not** treated as verified public code

---

## Deliverable A — Fork aligned with upstream v1.4.0?

### Exact refs (verified)

| Ref | SHA |
|---|---|
| Annotated tag object `v1.4.0` | `3c7cec6ac6c9bacf5bc2c4d4dc70606289c2f971` |
| Dereferenced release commit | **`4fea38f602f84ddad2d5215fbc9d2742605d892c`** (`1.4.0: release date`) |
| Upstream public `main` | **`f6aab1d4953c1d83be2f71e73faef6fa5dc236ff`** (sole commit after 1.4.0: Windows deflate harness) |
| Fork `main` | **`fad6693a1678c5ae65c60d29a9a6a6b74feb42f3`** |
| `merge-base(origin/main, upstream/main)` | **`f6aab1d…`** (= current upstream tip) |

### Ancestry

- `git merge-base --is-ancestor 4fea38f origin/main` → **yes**  
- `git merge-base --is-ancestor f6aab1d origin/main` → **yes**  
- Fork `main` therefore contains **all** of public upstream `main`, including v1.4.0 and the one post-release commit.

### Missing upstream release changes?

**None.** Diff `4fea38f..upstream/main` is only `tests/c/zharness_main.c` (+9), and that commit is already an ancestor of fork `main`.

### Intentional fork divergences (not omissions)

- Native tree under `src/native/amiga/…` / `tests/native/amiga/…` (fork PR [#2](https://github.com/AmanitaHouse/amigent/pull/2))  
- Apollo detect/daemon/AUDIO/MMIO/packaging/selection (`amigentd.apollo` = `63db83ff…`)  
- Viewer Hear + Apollo eligibility + daemon About identity  
- POKE resource gates + Apollo TRACE fail-closed (fork PR [#14](https://github.com/AmanitaHouse/amigent/pull/14))  
- `.githooks/**`, `.gitattributes` (local tooling)

### Retained functionality markers on fork `main`

| Capability | Evidence on `origin/main` |
|---|---|
| ApolloOS/68080 detection | `src/native/amiga/platform/apollo/apollo_detect.c`, `apollo_probe.c` |
| Native Apollo packaging/selection | `src/amigent/amiga/bin/amigentd.apollo`, `src/amigent/daemons.py`, `setup.py` |
| AUDIO one-shot/stream + Hear | `apollo` AUDIO sources, `channel.connect_audio`, `viewer` Hear path |
| Hear lifecycle + eligibility | `hear_eligible` / `apollo_machine` in `viewer.py`; `infoHearEligible` in `viewer.js`; tests `test_viewer_hear_visibility.py`, `test_viewer_hear_lifecycle.py` |
| MMIO protections | `apollo_mmio.c` + daemon call sites |
| POKE resource limits | `c_poke` / `PEEK_MAX` ordering; `tests/test_stage4_d3_poke_resource.py` |
| Apollo TRACE fail-closed | `trace=0` advertise; `c_trace` refuses set under `AMIGENT_APOLLO`; `tests/test_stage4_d3_trace_integration.py` |
| Non-Apollo compatibility | Packaged `amigentd`, `amigentd.000`, classic monitor/status still in `src/amigent/amiga/bin/` |

### Verdict A

**ALIGNED**

Smallest corrective action: **none** for 1.4.0 / public-`main` ancestry. (Promotion of fork-only features upstream is separate — see B–D.)

---

## Deliverable B — Repository restructure promoted upstream?

### What changed in the fork

| Before (upstream / pre-restore) | After (fork `main`) |
|---|---|
| Flat `amiga/*.c`, `amiga/build-amigentd`, tests beside `amiga/` | `src/native/amiga/{daemon,tools,platform/apollo,examples}/` |
| Mixed on-Amiga tests under `amiga/` | `tests/native/amiga/` |
| — | `benchmarks/` for offline harnesses |
| Packaged binaries | Unchanged location: `src/amigent/amiga/bin/` |
| Sdist | `MANIFEST.in` → `graft src/native`; wheel finder keeps `amigent*` only |

**Fork integration:** [PR #2](https://github.com/AmanitaHouse/amigent/pull/2) merged 2026-11-20 — commits include `7113006` (“Move the native sources into src/native and tests/native”), `5c90e94`, …, merge `14ec6ed`.

**Documented rationale (PR #2 body):** restore the November-15 native layout lost at reconciliation; keep protocol-6 sources; update Makefiles/scripts/`MANIFEST.in`/docs/tests; keep packaged binaries stable; leave upstream flat-`amiga/` contribution branches untouched.

### Upstream proposal status

| Question | Answer |
|---|---|
| Proposed to `akustikrausch/amigent`? | **No.** No open/closed/merged upstream PR by AmanitaHouse (or title/head search) covers `src/native` / layout restore |
| Equivalent structure on public upstream `main`? | **No** — still flat `amiga/` (`amigentd.c`, tools, tests beside it) |
| Accepted / modified / rejected? | **N/A — never submitted** |

Earlier coverage docs labelled the layout “fork-only”; that was an integration-plan choice, **not** evidence of an upstream decision. This audit treats promotion as **still required** if the original objective stands.

### Verdict B

**NOT PROMOTED**

#### Ready-to-review upstream proposal (do **not** publish yet)

**Title:** `Move Amiga daemon sources under src/native and tests/native`

**Proposed base:** `akustikrausch/amigent:main` @ `f6aab1d` (public 1.4.0 + harness)

**Description (draft):**

> ## Summary
> Relocate Amiga native sources from the flat `amiga/` tree into `src/native/amiga/` (daemon, tools, platform hooks, examples, build scripts) and on-Amiga C tests into `tests/native/amiga/`, matching a clearer host-vs-target split already used by the Python package under `src/amigent/`.
>
> ## Why
> - Separates **shipped host package** (`src/amigent/`) from **rebuildable Amiga sources** (`src/native/`).
> - Keeps packaged binaries in `src/amigent/amiga/bin/` so installers and wheels do not change.
> - Makes Apollo platform files a deliberate subdirectory instead of mixing them into a single flat folder as the tree grows.
> - Lets sdist `graft src/native` while the wheel continues to ship only `amigent*` + staged binaries.
>
> ## Compatibility
> - No protocol or runtime behaviour change intended.
> - Update `Makefile` / `build-amigentd` paths, docs (`GUIDE.md` / `PROTOCOL.md` links), and CI/scripts that invoke the classic build.
> - Existing flat-`amiga/` contribution PRs can keep their layout until rebased; this PR should be a pure path move + reference updates.
>
> ## Migration cost
> Mostly `git mv` + path string updates. Contributors rebuilding on the Amiga need the new script paths once.
>
> ## Tests
> Packaging/layout tests that assert sdist contains `src/native`, wheel excludes native Makefiles/sources, and classic/Apollo build scripts resolve.
>
> ## Out of scope
> `.githooks`, identity guards, hardware evidence, Apollo feature code, binary content changes.

**Exact proposed patch scope (path moves + reference updates only):**

- `amiga/amigentd.c` → `src/native/amiga/daemon/amigentd.c` (+ stubs)  
- `amiga/amigent-monitor.c`, `amigent-status.c` → `src/native/amiga/tools/`  
- `amiga/build-amigentd`, Makefile variants → `src/native/amiga/`  
- `amiga/*-test.c` → `tests/native/amiga/`  
- `amiga/repair.d` → `src/native/amiga/examples/`  
- `MANIFEST.in`, docs, scripts, packaging tests  
- **Exclude:** `.githooks/**`, Apollo-only new sources unless already upstream, binary blobs

**Preferred source for the move:** replay fork commits `7113006` + `5c90e94` (and packaging-test follow-ups) onto public `main`, **without** Apollo feature commits.

---

## Deliverable C — Apollo-only Hear visibility

### Fork

| Item | Evidence |
|---|---|
| Integration PR | [AmanitaHouse #13](https://github.com/AmanitaHouse/amigent/pull/13) **MERGED** 2026-11-21 |
| Implementation commit | **`0ad41f0b0e3475e763fb6ec6554bfe0fbcc3ce98`** |
| In fork `main`? | **Yes** (`merge-base --is-ancestor 0ad41f0 origin/main`) |
| Eligibility | `hear_eligible`: connected + `apollo_machine` (`os==ApolloOS` or `cpu` contains `68080`) + protocol ≥ 6 + `audio=1`; JS `infoHearEligible` / `hearEligible`; server rejects ineligible ON |
| Tests | `tests/test_viewer_hear_visibility.py`, updates in `test_viewer_hear_lifecycle.py`, `test_apollo_playback.py` |
| Files | `src/amigent/viewer.py`, `web/viewer.js`, `web/viewer.css`, `web/index.html` |

### Upstream public `main`

| Item | Evidence |
|---|---|
| `hear_eligible` / `apollo_machine` / `infoHearEligible` | **Absent** (`git grep` on `upstream/main` empty) |
| `connect_audio` / stock Hear Apollo gating | **Absent** |
| Dedicated upstream PR for this rule | **None** found among AmanitaHouse upstream PRs or Hear/audio searches |

Note: public upstream also lacks the broader Apollo AUDIO / Hear stack (fork review [#8](https://github.com/AmanitaHouse/amigent/pull/8) / upstream not opened). Apollo-only visibility is therefore **not** present even as a partial Viewer patch.

### Verdict C

| Layer | Status |
|---|---|
| Fork implementation | **COMPLETE** on `main` @ `0ad41f0` via [#13](https://github.com/AmanitaHouse/amigent/pull/13) |
| Upstream implementation | **ABSENT** |
| Upstream PR | **NOT OPENED** |

**Smallest independent upstream contribution:** Viewer/JS/CSS/HTML + `test_viewer_hear_visibility.py` extracting the eligibility helpers — **but** it is only useful once upstream has Apollo AUDIO advertising/`connect_audio` (depends on protected stack / fork [#6](https://github.com/AmanitaHouse/amigent/pull/6)–[#8](https://github.com/AmanitaHouse/amigent/pull/8) landing, or a combined Viewer AUDIO PR). Opening Hear-visibility alone against stock 1.4.0 would be dead code.

**Recommended next action:** keep [#13](https://github.com/AmanitaHouse/amigent/pull/13) as the canonical fork patch; when opening upstream Viewer AUDIO, include Apollo-only Hear eligibility in the same or immediately following PR. Do **not** open a standalone upstream Hear-visibility PR against current public `main`.

---

## Deliverable D — Viewer daemon identity (fork PR #9)

### Feature identity

Yes — this is the second Viewer improvement: **About dialog shows connected daemon identity/capabilities separately from host CPU/OS.**

| Item | Evidence |
|---|---|
| Fork review PR | [AmanitaHouse #9](https://github.com/AmanitaHouse/amigent/pull/9) **OPEN** — base `contrib/daemon-compatible-fallback` (= upstream [#38](https://github.com/akustikrausch/amigent/pull/38)), tip `739aa4c` |
| Tip commit message | “Show the connected daemon separately from the computer and this PC.” |
| API | `describe_connected()` in `src/amigent/daemons.py`; Viewer About fields `daemon_family` / `daemon_target` / `daemon_identity` / `daemon_capabilities` |

### Is it on current fork `main`?

**Yes, functionally.**  
`describe_connected`, About JS bindings, and `tests/test_daemon_identity.py` are present on `origin/main`.

`739aa4c` is **not** a git ancestor of `main` (parallel integrate history), but the same feature was merged via the functional integrate path (e.g. history includes `c2c20dd` / `1b2d2e6` “show the connected daemon…”). Fork `main`’s `daemons.py` has since grown Apollo selection / `SUPERSEDED_APOLLO_SHA256` beyond the pure #9 tip.

### Upstream?

| Question | Answer |
|---|---|
| Implemented on public upstream `main`? | **No** (`describe_connected` / About daemon fields absent) |
| Proposed as upstream PR? | **No** — only fork review [#9](https://github.com/AmanitaHouse/amigent/pull/9); no `akustikrausch` PR |
| Equivalent in upstream [#38](https://github.com/akustikrausch/amigent/pull/38)? | **No** — #38 is daemon **selection/fallback** (`daemons.py` catalogue); `gh pr diff 38` has no `describe_connected` / `daemon_identity` |
| Conflict with #38? | **No** — #9 **depends on** #38’s `daemons.py` module; contributing identity after #38 would extend it, not duplicate it |

### Is original PR #9 still needed?

- As a **fork `main` gap-filler:** **No** — behaviour already shipped.  
- As the **upstream-facing isolated patch** (against #38 base): **Yes** — still the right vehicle to open upstream **after** public #38 (or public 1.5.0 catalogue) lands. Prefer rebasing the #9 delta (`739aa4c` identity-only hunks + locales + `test_daemon_identity.py`) rather than exporting the whole fork `daemons.py`.

### Verdict D

| Layer | Status |
|---|---|
| Feature identity | **Confirmed** — daemon About identity = fork [#9](https://github.com/AmanitaHouse/amigent/pull/9) |
| Fork `main` | **IMPLEMENTED** (via integrate; tip `739aa4c` not required as ancestor) |
| Upstream | **ABSENT** / **NOT PROPOSED** to `akustikrausch` |
| Next action | Open upstream PR from #9’s identity delta **after** public #38; do not duplicate #38 |

---

## Decision table

| Objective | Verdict | Git/PR evidence | Missing work | Recommended action |
|---|---|---|---|---|
| Fork aligned with upstream v1.4.0, functionality retained | **ALIGNED** | Tag `v1.4.0` → `4fea38f`; fork `main` `fad6693`; `merge-base` with upstream = `f6aab1d`; ancestry checks exit 0 | None for 1.4.0 | No ancestry fix |
| Repository restructure promoted upstream with rationale | **NOT PROMOTED** | Fork [#2](https://github.com/AmanitaHouse/amigent/pull/2) `7113006` on fork only; upstream still flat `amiga/`; no upstream layout PR | Upstream layout PR with rationale | Authorise opening draft in §B against public `main` |
| Apollo-only Hear visibility upstream | **ABSENT UPSTREAM** (fork complete) | Fork [#13](https://github.com/AmanitaHouse/amigent/pull/13) `0ad41f0` on fork `main`; upstream grep empty | Upstream Viewer AUDIO + eligibility | Bundle with Apollo Hear/#8 upstream; do not solo-PR vs 1.4.0 |
| Viewer daemon identity feature upstream | **ABSENT UPSTREAM** (fork complete) | Fork [#9](https://github.com/AmanitaHouse/amigent/pull/9) `739aa4c`; `describe_connected` on fork `main`; not in upstream/#38 | Upstream identity PR after #38 | Reuse [#9](https://github.com/AmanitaHouse/amigent/pull/9) delta; wait for public #38 |

---

## Minimal close-out actions

1. **Immediate (public upstream, no 1.5.0 required):**  
   - Authorise opening the **native layout** PR (§B draft) against `akustikrausch/amigent:main`.  
2. **Immediate (docs/process only):**  
   - Treat fork objectives for Hear + identity as **done on fork `main`**; track upstream as separate promotions.  
3. **Depends on maintainer / public #38 or 1.5.0:**  
   - Upstream daemon-identity PR (reuse fork [#9](https://github.com/AmanitaHouse/amigent/pull/9)).  
   - Upstream Apollo Hear stack + Apollo-only visibility (reuse [#8](https://github.com/AmanitaHouse/amigent/pull/8)+[#13](https://github.com/AmanitaHouse/amigent/pull/13) intent).  
   - Rebase protected Apollo stack (#4–#7/#10) once public identify/catalogue base exists.  
4. **Reuse, do not duplicate:**  
   - Layout: fork [#2](https://github.com/AmanitaHouse/amigent/pull/2) commits.  
   - Identity: fork [#9](https://github.com/AmanitaHouse/amigent/pull/9).  
   - Hear eligibility: fork [#13](https://github.com/AmanitaHouse/amigent/pull/13) (with AUDIO [#8](https://github.com/AmanitaHouse/amigent/pull/8)).  
   - Fallback catalogue: upstream [#38](https://github.com/akustikrausch/amigent/pull/38) (already open).  
5. **Single batch for user authorisation (suggested):**  
   1. Open upstream **layout** PR from §B (only immediate public-baseline contribution among these four objectives).  
   2. Do **not** open Hear-visibility or identity upstream PRs in the same batch until #38 / Apollo AUDIO base is public.  
   3. Do **not** repost #31 HW comment.  
   4. Leave fork #4–#10 open as protected review stack.

---

## Confirmation

- No hardware session, merge, release, upstream comment, or PR open/close was performed for this audit.  
- Private `feature/1.5.0` remains unpublished and was not inspected.
