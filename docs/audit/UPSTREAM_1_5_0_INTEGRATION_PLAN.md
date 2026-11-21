# Fork integration plan — after public upstream 1.5.0

Depends on: `docs/audit/UPSTREAM_1_5_0_RECONCILIATION.md`  
**Do not execute** until `upstream/feature/1.5.0` (or equivalent) is fetchable.

## Preconditions

- [ ] Public tip SHA recorded  
- [ ] Comparison worktree created (not merged to `main`)  
- [ ] Full diff `v1.4.0…1.5.0-tip` inventoried  
- [ ] Confirm presence/absence of Apollo native daemon sources vs comments  

## Workstreams

| # | Workstream | Preserve | Import / adapt |
|---|------------|----------|----------------|
| 1 | Multi-Amiga sessions / roster / keys-by-ID | Fork MCP tools behaviour where still valid | Upstream session model from 1.5.0 |
| 2 | TLSONLY client + viewer reason keys | Production TLSONLY ops knowledge | Maintainer #27/#36 messaging |
| 3 | Daemon selection / update | No silent downgrade; no auto `.080` | #38 script renewal + `$VER` date |
| 4 | Apollo identify | HW evidence feedback | Bit-10 detect; probe gated on packaged `.apollo` |
| 5 | Apollo stack #4–#10 | Protected tips immutable | **New** branches from 1.5.0 tip |
| 6 | Layout | `src/native/**`, hooks, gitattributes | Path mapping only for upstream PRs |
| 7 | Binaries | F-DAE/U-DAE hashes until rebuild | Rebuild + HW revalidation if sources change |

## Checks before touching `main`

- pytest full suite  
- packaging / setuptools≥77  
- No V4 contact without authorisation  
- No version bump / PyPI  

## Explicit non-goals of first integrate

- Publishing a release  
- Force-pushing protected Apollo history  
- Overwriting production V4 `C:amigentd`  
- Claiming HW validation for untested 1.5.0 natives  
