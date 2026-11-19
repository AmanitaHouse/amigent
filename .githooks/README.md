# Repository identity guard

Commits in this clone must use the identity in `.githooks/identity` for both the author and the committer. The guard reads the effective identity. A correct `git config user.name` is not enough when an environment variable overrides it.

`pre-commit` rejects a commit whose effective author or committer does not match. `pre-push` reads the raw author and committer stored in each newly introduced commit. Commits already on `origin` and commits reachable from the `upstream-v1.4.0` tag, any `upstream-*` tag, or `refs/remotes/upstream`, are not treated as new fork commits. The hooks do not rewrite identities and do not contact the network. If the identity cannot be determined, or `origin/main` or the upstream baseline tag is missing, the hook fails closed.

## Reactivate after a clone

`user.name`, `user.email`, `user.useConfigOnly`, and `core.hooksPath` are stored in this clone's `.git/config`. They are not copied by `git clone`. From the repository root, in either Windows Git or WSL Git:

```sh
sh .githooks/activate
```

That command writes only repository-local configuration. It does not change global or system Git configuration. Run it in every new clone and in every linked worktree's repository configuration (linked worktrees share the main `.git/config`).

The hook files must be present in the working tree. `core.hooksPath` is `.githooks`, so a checkout that does not contain this directory will not have the scripts until this commit is merged into that branch.

## What can still bypass it

`git commit --no-verify` and `git push --no-verify` skip these hooks. Unsetting `core.hooksPath` in this clone also skips them. A server-side GitHub ruleset or required status check on `AmanitaHouse/amigent` is the control that a local hook cannot replace. This repository's GitHub rulesets were not changed when the guard was added.
