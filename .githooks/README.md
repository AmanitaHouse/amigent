# Repository identity guard

Commits in this clone must use this identity for both the author and the committer:

```
AmanitaHouse <226066545+AmanitaHouse@users.noreply.github.com>
```

That address is the GitHub noreply address for the AmanitaHouse account. The same pair is stored in `.githooks/identity`. The guard reads the effective identity. A correct `git config user.name` is not enough when an environment variable or `--author` overrides it.

`pre-commit` rejects a commit whose effective author or committer does not match. `pre-push` reads the raw author and committer stored in each newly introduced commit. Commits already reachable from `origin` are not treated as new fork commits. Upstream history is exempt only when the annotated tag `upstream-v1.4.0` is exactly the verified tag object `3c7cec6ac6c9bacf5bc2c4d4dc70606289c2f971` (tagger Andreas Wendorf, commit `4fea38f602f84ddad2d5215fbc9d2742605d892c`). Those ids are pinned in `.githooks/upstream-baseline` and checked again by the hook. A tag whose name begins with `upstream-` is not an exemption. The hooks do not rewrite identities and do not contact the network. If the identity cannot be determined, or `origin/main` or the verified upstream tag is missing or does not match, the hook fails closed.

## Where the active hooks live

The tracked files in `.githooks` are the source. They are not the active hook path. `core.hooksPath` is left unset, because a path inside the working tree disappears on a branch that does not contain `.githooks`.

`sh .githooks/activate` copies `pre-commit`, `pre-push`, `lib.sh`, `identity`, and `upstream-baseline` into the private hooks directory of this repository and of every existing linked worktree. Git then runs those copies from `$GIT_DIR/hooks` on every branch. Run `sh .githooks/activate` again after `git worktree add`, and again after changing the tracked hook files. The copy does not remove sample hooks or any other hook file.

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

`pre-push` reads the author and committer stored in the commit object. It rejects a newly introduced fork commit whose stored author or committer is not the identity above. It does not reject a commit already reachable from `origin`, or a commit reachable from the verified `upstream-v1.4.0` tag object named above.

## What can still bypass it

`git commit --no-verify` and `git push --no-verify` skip these hooks. Deleting the private hook files, or setting `core.hooksPath` in this clone, also skips them. A server-side GitHub ruleset or required status check on `AmanitaHouse/amigent` is the control that a local hook cannot replace. This repository's GitHub rulesets were not changed when the guard was added.
