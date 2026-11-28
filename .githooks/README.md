# Repository identity guard

Commits in this clone must use this identity for both the author and the committer:

```
AmanitaHouse <226066545+AmanitaHouse@users.noreply.github.com>
```

That address is the GitHub noreply address for the AmanitaHouse account. The same pair is stored in `.githooks/identity`. The guard reads the effective identity. A correct `git config user.name` is not enough when an environment variable or `--author` overrides it.

`pre-commit` rejects a commit whose effective author or committer does not match. `pre-push` reads the raw author and committer stored in each newly introduced commit. Commits already reachable from `origin` are not treated as new fork commits. Upstream history is exempt only when the annotated tag `upstream-v1.4.0` is exactly the verified tag object `3c7cec6ac6c9bacf5bc2c4d4dc70606289c2f971` (tagger Andreas Wendorf, commit `4fea38f602f84ddad2d5215fbc9d2742605d892c`) and every reviewed upstream boundary listed below exists as that exact commit and descends from the one before it. The ids are pinned twice, in `.githooks/upstream-baseline` (lines 4 and on) and in `trusted_boundaries` in `.githooks/lib.sh`, and the hook refuses to run unless the two agree exactly, with nothing extra in the file. A tag or branch whose name begins with `upstream-` or `upstream/` is not an exemption, and neither is an author name. The hooks do not rewrite identities and do not contact the network. If the identity cannot be determined, or `origin/main`, the verified upstream tag or any pinned boundary object is missing or does not match, the hook fails closed.

## Reviewed upstream boundaries

| Boundary | What it covers |
| --- | --- |
| `f6aab1d4953c1d83be2f71e73faef6fa5dc236ff` | tracked boundary after upstream 1.4.0 |
| `8e576ad94d8c936a662dfd7375c31456341f49fd` | the boundary the installed hook trusted before PR #22 (a descendant of the one above) |
| `dfd086194c918cd91f91626072d20ec6e605d1bf` | upstream PRs #46 and #52, merged into the fork by PR #22 |
| `5a85d63c5aa8cb3ccacd716d806e81c8a7366543` | upstream PR #50 (Apollo AUDIO/Hear), integrated atomically into the fork |

Everything reachable from a boundary is exempt from the author and committer check; nothing else is. A commit made later, including one that claims Andreas Wendorf or `GitHub` as author or committer, is a new fork commit and must carry the identity above. Later upstream branches and PRs (such as `feature/1.6.0` at `49fd7539`, PR #53 or PR #54) are not a boundary. A boundary is added only by a deliberate reconciliation decision, as one exact id in both places, with the regression tests updated in the same change.

GitHub's merge commits have `GitHub <noreply@github.com>` as committer. They are accepted only because they are already reachable from `origin`, so run `git fetch origin` after a pull request is merged on GitHub before pushing work that contains the merge commit. There is no exemption for the name `GitHub`.

## Tests

`tests/test_githooks.py` drives the real hook files through `git push` and `git commit` in temporary repositories with a local bare remote. It needs `git` and `sh` and no network. `SyntheticGuard` runs anywhere. `RealHistoryGuard` uses the hook files unmodified against a `git clone --shared` of a repository that holds the pinned history, and is skipped when that history is missing (a shallow clone). Set `AMIGENT_HOOK_TEST_SOURCE` to such a repository when this checkout is a linked worktree that the running Git cannot open. From WSL: `AMIGENT_HOOK_TEST_SOURCE=/mnt/d/path/to/primary python3 tests/test_githooks.py`.

## Where the active hooks live

The tracked files in `.githooks` are the source. They are not the active hook path. `core.hooksPath` is left unset, because a path inside the working tree disappears on a branch that does not contain `.githooks`.

`sh .githooks/activate` copies `pre-commit`, `pre-push`, `lib.sh`, `identity`, and `upstream-baseline` into the private hooks directory of this repository and of every existing linked worktree. Git then runs those copies from `$GIT_DIR/hooks` on every branch. Run `sh .githooks/activate` again after `git worktree add`, and again after changing the tracked hook files. The copy does not remove sample hooks or any other hook file.

The tracked files and the installed copies can drift apart, and the installed copy is what runs. Compare them after a change: `cmp .githooks/lib.sh "$(git rev-parse --path-format=absolute --git-common-dir)/hooks/lib.sh"`, and the same for `pre-push` and `upstream-baseline`. Git reads hooks from the shared `hooks` directory of the common Git directory for every linked worktree, so the copies that `activate` also writes under `worktrees/<name>/hooks` are not the ones that run.

## Reactivate after a clone

`user.name`, `user.email`, and `user.useConfigOnly` are stored in this clone's `.git/config`. They are not copied by `git clone`. From the repository root, in either Windows Git or WSL Git:

```sh
sh .githooks/activate
```

That command writes only repository-local configuration and the private hooks directory. It does not change global or system Git configuration. Linked worktrees share the main `.git/config`. Each linked worktree has its own private hooks directory; activate fills all of them.

## Verify the effective identity

From the repository root, with Windows Git or WSL Git:

```sh
git config --show-origin --get-regexp '^user\.'
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

The local `user.name` and `user.email` lines, and both `git var` results, must be `AmanitaHouse <226066545+AmanitaHouse@users.noreply.github.com>`. A global identity may still exist for other repositories. It must not be the identity these commands resolve inside this clone.

## Verify that the guards are operational

These commands must be rejected, and `git rev-parse HEAD` must be unchanged afterwards. The same rejection must happen on a branch whose tree does not contain `.githooks`:

```sh
GIT_AUTHOR_NAME=wrong GIT_AUTHOR_EMAIL=wrong@example.com git commit --allow-empty -m "identity probe"
GIT_COMMITTER_NAME=wrong GIT_COMMITTER_EMAIL=wrong@example.com git commit --allow-empty -m "identity probe"
git -c user.email=wrong@example.com commit --allow-empty -m "identity probe"
git commit --allow-empty --author="Wrong <wrong@example.com>" -m "identity probe"
```

`pre-push` reads the author and committer stored in the commit object. It rejects a newly introduced fork commit whose stored author or committer is not the identity above. It does not reject a commit already reachable from `origin`, or a commit reachable from the verified `upstream-v1.4.0` tag or from any of the reviewed upstream boundaries listed above.

## What can still bypass it

`git commit --no-verify` and `git push --no-verify` skip these hooks. Deleting the private hook files, or setting `core.hooksPath` in this clone, also skips them. A server-side GitHub ruleset or required status check on `AmanitaHouse/amigent` is the control that a local hook cannot replace. This repository's GitHub rulesets were not changed when the guard was added.
