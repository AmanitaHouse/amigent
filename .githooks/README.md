# Repository identity guard

Commits in this clone must use this identity for both the author and the committer:

```
AmanitaHouse <226066545+AmanitaHouse@users.noreply.github.com>
```

That address is the GitHub noreply address for the AmanitaHouse account. The same pair is stored in `.githooks/identity`. The guard reads the effective identity. A correct `git config user.name` is not enough when an environment variable or `--author` overrides it.

`pre-commit` rejects a commit whose effective author or committer does not match. `pre-push` reads the raw author and committer stored in each newly introduced commit. Commits already on `origin` and commits reachable from the `upstream-v1.4.0` tag, any `upstream-*` tag, or `refs/remotes/upstream`, are not treated as new fork commits. The hooks do not rewrite identities and do not contact the network. If the identity cannot be determined, or `origin/main` or the upstream baseline tag is missing, the hook fails closed.

## Reactivate after a clone

`user.name`, `user.email`, `user.useConfigOnly`, and `core.hooksPath` are stored in this clone's `.git/config`. They are not copied by `git clone`. From the repository root, in either Windows Git or WSL Git:

```sh
sh .githooks/activate
```

That command writes only repository-local configuration. It does not change global or system Git configuration. Run it in every new clone and in every linked worktree's repository configuration (linked worktrees share the main `.git/config`).

The hook files must be present in the working tree. `core.hooksPath` is `.githooks`, so a checkout that does not contain this directory will not have the scripts until this commit is merged into that branch.

## Verify the effective identity

From the repository root, with Windows Git or WSL Git:

```sh
git config --show-origin --get-regexp '^user\.'
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

The local `user.name` and `user.email` lines, and both `git var` results, must be `AmanitaHouse <226066545+AmanitaHouse@users.noreply.github.com>`. A global identity may still exist for other repositories. It must not be the identity these commands resolve inside this clone.

## Verify that the guards are operational

These commands must be rejected, and `git rev-parse HEAD` must be unchanged afterwards:

```sh
GIT_AUTHOR_NAME=wrong GIT_AUTHOR_EMAIL=wrong@example.com git commit --allow-empty -m "identity probe"
GIT_COMMITTER_NAME=wrong GIT_COMMITTER_EMAIL=wrong@example.com git commit --allow-empty -m "identity probe"
git -c user.email=wrong@example.com commit --allow-empty -m "identity probe"
git commit --allow-empty --author="Wrong <wrong@example.com>" -m "identity probe"
```

`pre-push` reads the author and committer stored in the commit object. It rejects a newly introduced fork commit whose stored author or committer is not the identity above. It does not reject a commit already reachable from `origin`, or a commit reachable from `upstream-v1.4.0`, another `upstream-*` tag, or `refs/remotes/upstream`.

## What can still bypass it

`git commit --no-verify` and `git push --no-verify` skip these hooks. Unsetting `core.hooksPath` in this clone also skips them. A server-side GitHub ruleset or required status check on `AmanitaHouse/amigent` is the control that a local hook cannot replace. This repository's GitHub rulesets were not changed when the guard was added.
