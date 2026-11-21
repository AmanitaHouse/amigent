# Apollo V4 — release readiness and upstream 1.5.0 reconciliation

**Date:** 2026-11-21  
**Fork `main` tip (at audit):** `fad6693a1678c5ae65c60d29a9a6a6b74feb42f3`  
**Hardened Apollo packaged identity:** `63db83ff…` / 128744 B  
**Docs branch:** `validation/apollo-v4-evidence-prep`  
**Authorisation:** documentation / planning only — **no** new hardware tests, merges, releases, or upstream submissions

## 1. Basic AUDIO regression — CLOSED for `63db83ff…`

| Layer | Evidence | Status |
|---|---|---|
| D4 startup / proto-6 TLS / SYSINFO | `docs/APOLLO_V4_STAGE4_D4_NEW_DAEMON_SMOKE_RESULTS.md` | PASSED ON HARDWARE |
| D5 nonempty one-shot `audio(0)` | `docs/APOLLO_V4_STAGE4_D5_AUDIO_RESULTS.md` (remake) | PASSED ON HARDWARE |
| D5B bounded stock Viewer Hear | `docs/APOLLO_V4_STAGE4_D5B_VIEWER_HEAR_RESULTS.md` | PASSED ON HARDWARE |
| Human-audible PC playback | D5B operator | **YES (choppy)** |

**Basic AUDIO regression coverage for hardened executable `63db83ff…` is CLOSED.**

Do **not** open another AUDIO quality, scheduling, soak, or fidelity campaign on the basis of D5B observations alone.

### Documented findings (not release blockers by themselves)

| Finding | Treatment |
|---|---|
| Choppy PC playback during D5B Hear | Documented limitation of that session; not escalated to a reproducible product regression without a separate authorised investigation |
| Operator-reported Viewer connection loss after Hear | Documented observation; instrumentation still recorded one complete start/stop/end-marker stream. Not treated as a blocker unless reproduced under an authorised session |
| Earlier same-day D5 valid-empty oneshot | Procedural miss (no post-launch play confirmation); preserved separately; remake succeeded |

Prior Stage 3B identities (`00443719…`, `456fce26…`, `983fd853…`, etc.) remain historical evidence and are **not** re-opened here.

## 2. Features that should remain disabled / unclaimed in a stable fork release

Ship with clear “not supported / fail-closed” posture unless a future authorised session changes status:

| Feature | Release posture | Basis |
|---|---|---|
| POKE / ALLOWPOKE | **Disabled by default**; do not enable on V4 production | Offline harden PASS; HW POKE **NOT_TESTED** |
| TRACE set on Apollo/68080 | **Fail-closed** (`trace=0`; set refused) | Source + D4 capability advertise; TRACE HW **NOT_TESTED** |
| PIP | Advertise / keep `pip=0`; do not claim picture path | Protected stack / fork daemon posture |
| Monitor (D6) | **Not a release claim**; do not market as validated | Offline review only; HW **NOT_TESTED** |
| HRTmon (D7) | **Not a release claim**; ROM path blocked in software | Offline review; HW **NOT_TESTED** |
| Full MMIO map | Only three D2 PEEK refuses HW-proven on older `00443719…` identity | Do not claim full MMIO safety for `63db83ff…` |
| Long-duration AUDIO soak / fidelity | **Out of basic regression** | Explicitly not pursued after D5B |
| Experimental `amigentd.080` | Keep excluded from packages / never auto-select | Existing packaging policy |

## 3. Installation / update safety (reuse existing evidence)

| Topic | Status | Notes |
|---|---|---|
| Packaged Apollo on `main` | `63db83ff…` | Wheel/sdist verified at Stage 4 merge |
| Classic daemons | Preserved | Unchanged vs pre-Stage-4 packaging |
| `SUPERSEDED_APOLLO_SHA256` | `1e0e3f65…`, `00443719…` only | Allows same-`$VER` replacement of known old Apollo bytes; unknown hashes stay blocked |
| Fresh ApolloOS+68080 selection | Offline-tested | Selects `amigentd.apollo` |
| Compatible-daemon fallback | Fork + upstream PR **#38** | Offline / design reviewed; keep fail-safe behaviour |
| Probe-assisted selection | Offline + Stage 3A HW for probes | Do not fail-closed if probe absent |
| Live `amigent-setup --update` on production V4 | **NOT_RUN** as a dedicated HW gate | Offline distribution/update tests PASS; treat live update as **approval-gated** |
| Production install today | Proto-5 `C:amigentd` `b00fef0e…` | Must not be overwritten by unauthorised sessions; release process must preserve restore story |

**Release implication:** offline installer/update protection is in good shape for a fork package that ships `63db83ff…`. A live production `--update` remains a separate, authorised operation — not a missing AUDIO task.

## 4. Upstream 1.5.0 reconciliation (still private)

Re-checked remote heads/tags on `akustikrausch/amigent` (2026-11-21):

| Check | Result |
|---|---|
| `feature/1.5.0` | **Absent** |
| Latest public tag | **v1.4.0** (`4fea38f…`) |
| Upstream `main` | `f6aab1d…` (post-1.4.0 Windows deflate harness) |

**Do not wait on unpublished 1.5.0 to:**

- Close basic AUDIO regression for `63db83ff…` (done).  
- Document fork release blockers and disabled-feature posture (this file).  
- Keep submitting / reviewing independent upstream PRs already opened against 1.4.0-era trees (`#31`, `#38`, `#27`–`#37`, etc.).  
- Maintain the protected contribution stack plan in `docs/UPSTREAM_CONTRIBUTION_COVERAGE.md`.  
- Run offline packaging/CI and documentation hygiene on the fork.

**Do wait on a public 1.5.0 branch/tag before:**

- Claiming behavioural equivalence to private 1.5.0 AUDIO/detect commentary.  
- Auto-rebasing the protected Apollo contribution stack onto an unpublished tip.  
- Treating issue “before 1.5.0” language as an implemented public API.

When 1.5.0 appears publicly: fresh compare plan only — no automatic rebase.

## 5. Remaining blockers to a **stable fork release** (priority order)

These are planning blockers, not an authorisation to release:

1. **Release packaging decision** — confirm shipping identity remains `63db83ff…` with SUPERSEDED list as above; write release notes that state choppy-Hear limitation and disabled POKE/TRACE/monitor claims.  
2. **Approval-gated live update policy** — decide whether first production cutover uses staged exclusive session (proven) vs `amigent-setup --update` (offline-tested, HW update path NOT_RUN).  
3. **Feature matrix in release notes** — AUDIO basic OK; POKE/TRACE/monitor/HRTmon/PIP unclaimed; D2 MMIO refuses are for prior identity, not transferred wholesale to `63db83ff…`.  
4. **Documentation consolidation onto the release branch** — Stage 4 evidence currently lives on `validation/apollo-v4-evidence-prep`; a release needs an explicit docs promotion step (separate authorisation).  
5. **Upstream contribution queue** — fork release can proceed **without** 1.5.0, but upstream Apollo stack still depends on `#31` → `#4`…`#8` ordering; do not block fork release on that queue.  
6. **No further AUDIO investigation** — choppy/connection-loss stay documented; not a reason to delay release engineering unless a new authorised session proves a hard regression.

## 6. What “done enough” looks like without upstream 1.5.0

| Track | Without 1.5.0 |
|---|---|
| Hardened daemon basic AUDIO | **Closed** |
| Fork stable release engineering | **Can proceed** once release/update/docs decisions above are authorised |
| Upstream Apollo stack merge | Continues on 1.4.0 baseline; re-diff later |
| Stage 4 POKE/TRACE/monitor HW | Remains deferred / disabled in claims |

## 7. Explicit non-actions (this instruction)

- No new hardware tests  
- No AUDIO quality redesign or new investigation branch  
- No merges to fork `main`  
- No releases or package publication  
- No upstream PR creation or comments  

## Confirmation

Existing Stage 3B/D2/D4/D5/D5B evidence and hashes are preserved. D5B choppy playback and Viewer connection-loss remain **documented findings**. Basic AUDIO regression for `63db83ff…` is **closed**.
