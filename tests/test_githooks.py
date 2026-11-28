"""Offline regression tests for the identity guard in .githooks.

They drive the real hook scripts through real ``git push`` and ``git commit`` in
temporary repositories with a local bare remote. Nothing here talks to a network,
to GitHub or to this checkout's own hooks, configuration or remotes.

Two worlds run the same cases:

* ``SyntheticGuard`` builds a small history shaped like the real one (a verified
  upstream tag, four reviewed upstream boundaries, upstream commits after them) and
  substitutes only the pinned object ids. It runs everywhere, including a shallow CI
  checkout. Every substitution is asserted, so a refactor cannot make it silently stop
  testing the pins.
* ``RealHistoryGuard`` runs the hook files unmodified, with their real pins, against a
  ``git clone --shared`` of a repository that holds the reviewed history. It is skipped
  when the pinned objects are not available (a shallow clone, for example). Set
  ``AMIGENT_HOOK_TEST_SOURCE`` to a repository that has them when this checkout is a
  linked worktree that the running Git cannot open (a Windows worktree seen from WSL).

The guard code is never replaced by a stub.
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".githooks"
ZERO = "0" * 40
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

IDENT = (HOOKS / "identity").read_text().splitlines()
APPROVED = (IDENT[0].strip(), IDENT[1].strip())
ANDREAS = ("Andreas Wendorf", "akustikrausch@gmail.com")
ANDREAS_NOREPLY = ("Andreas Wendorf", "95188773+akustikrausch@users.noreply.github.com")
GITHUB = ("GitHub", "noreply@github.com")
MALLORY = ("Mallory", "mallory@example.invalid")

# The reviewed objects the hooks pin. The real world uses them as they are.
REAL = {
    "tag_object": "3c7cec6ac6c9bacf5bc2c4d4dc70606289c2f971",
    "tag_commit": "4fea38f602f84ddad2d5215fbc9d2742605d892c",
    "boundary_a": "f6aab1d4953c1d83be2f71e73faef6fa5dc236ff",
    "boundary_b": "8e576ad94d8c936a662dfd7375c31456341f49fd",
    "boundary_dfd": "dfd086194c918cd91f91626072d20ec6e605d1bf",
    "boundary_pr50": "5a85d63c5aa8cb3ccacd716d806e81c8a7366543",
    "pre_main": "fbbecc78e4ae7135fa6b0e29eaff56dd77646642",
    "integration": "9d2d31750ca75ebe2b359886f277fc14e51d94bc",
    "merged_main": "ed701f327ff7df0063ec6010e651a0394278d44f",
}
PINNED = ("tag_object", "tag_commit", "boundary_a", "boundary_b", "boundary_dfd", "boundary_pr50")
# Unreviewed upstream branch head after PR #50 (not pinned and not required in fresh fork clones).
FEATURE_160 = "49fd75393087055453705a07b50c3361ef0dc9c4"


def _find_sh():
    found = shutil.which("sh")
    if found:
        return found
    try:
        out = subprocess.run(["git", "--exec-path"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    for parent in list(Path(out).parents)[:4]:  # Git for Windows: <root>/mingw64/libexec/git-core
        candidate = parent / "bin" / "sh.exe"
        if candidate.is_file():
            return str(candidate)
    return None


SH = _find_sh()
GIT = shutil.which("git")


def _rmtree(path):
    def fix(func, p, *_):
        os.chmod(p, stat.S_IWRITE)  # Git's object files are read-only on Windows
        func(p)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=fix)
    else:
        shutil.rmtree(path, onerror=fix)


class Sandbox:
    """A scratch directory with a Git environment that sees nothing of the user's."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="amigent-hooktest-"))
        home = self.root / "home"
        home.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(
            HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(home),
            GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
            GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory", GIT_CONFIG_VALUE_0="*",
        )
        self.env = env
        self.clock = 1_700_000_000

    def close(self):
        _rmtree(self.root)

    def git(self, *args, cwd=None, check=True, input=None, extra_env=None):
        env = dict(self.env)
        env.update(extra_env or {})
        proc = subprocess.run([GIT, *args], cwd=cwd, env=env, input=input, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        if check and proc.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
        return proc

    def out(self, *args, **kw):
        return self.git(*args, **kw).stdout.strip()

    def commit(self, cwd, parents, message, author, committer=None):
        committer = committer or author
        self.clock += 60
        stamp = f"{self.clock} +0000"
        env = {
            "GIT_AUTHOR_NAME": author[0], "GIT_AUTHOR_EMAIL": author[1], "GIT_AUTHOR_DATE": stamp,
            "GIT_COMMITTER_NAME": committer[0], "GIT_COMMITTER_EMAIL": committer[1], "GIT_COMMITTER_DATE": stamp,
        }
        args = ["commit-tree", EMPTY_TREE]
        for parent in parents:
            args += ["-p", parent]
        args += ["-m", message]
        return self.out(*args, cwd=cwd, extra_env=env)

    def snapshot(self, bare):
        refs = self.out("for-each-ref", "--format=%(refname) %(objectname)", cwd=bare)
        objs = self.out("cat-file", "--batch-all-objects", "--batch-check", cwd=bare)
        return refs, sorted(objs.splitlines())


def _transform_synthetic(text, mapping):
    for real, fake in mapping.items():
        assert real in text, f"pin {real} not found; the synthetic world no longer tests the hook"
        text = text.replace(real, fake)
    return text


class World:
    """A work repository with the hooks activated, and a bare remote."""

    def __init__(self, sandbox, work, bare, ids):
        self.sb, self.work, self.bare, self.ids = sandbox, work, bare, ids
        self.initial_origin = self.sb.snapshot(bare)
        self.initial_tracking = self.tracking()

    def tracking(self):
        return self.sb.out("for-each-ref", "--format=%(refname) %(objectname)", "refs/remotes/origin", cwd=self.work)

    def git(self, *a, **kw):
        kw.setdefault("cwd", self.work)
        return self.sb.git(*a, **kw)

    def forged(self, parent, author, committer=None, message="forged"):
        return self.sb.commit(self.work, [parent], message, author, committer)

    def push(self, sha, name, cwd=None):
        return self.sb.git("push", "origin", f"{sha}:refs/{name}", cwd=cwd or self.work, check=False)

    def run_hook(self, stdin, cwd=None, relative=False):
        """Run the installed pre-push the way Git does, but with ref updates we choose."""
        hook = Path(self.work) / ".git" / "hooks" / "pre-push"
        cwd = cwd or self.work
        path = os.path.relpath(hook, cwd).replace("\\", "/") if relative else hook.as_posix()
        proc = subprocess.run(
            [SH, path, "origin", self.bare.as_posix()], cwd=cwd, env=self.sb.env,
            input=stdin, capture_output=True,
        )
        return proc.returncode, proc.stdout.decode(errors="replace"), proc.stderr.decode(errors="replace")

    def reset(self):
        """Put the remote and the remote-tracking refs back after a test that published."""
        for line in self.tracking().splitlines():
            ref = line.split()[0]
            if ref != "refs/remotes/origin/main":
                self.git("update-ref", "-d", ref)
        for line in self.sb.out("for-each-ref", "--format=%(refname)", "refs/heads", cwd=self.bare).splitlines():
            if line != "refs/heads/main":
                self.sb.git("update-ref", "-d", line, cwd=self.bare)
        assert self.tracking() == self.initial_tracking, "the shared world's origin refs changed"


def _install(sandbox, work, transform=None, custom=None):
    target = Path(work) / ".githooks"
    target.mkdir(exist_ok=True)
    for src in HOOKS.iterdir():
        if src.is_file():
            data = src.read_bytes()
            if transform and src.name in ("lib.sh", "upstream-baseline"):
                data = transform(src.name, data.decode()).encode()
            (target / src.name).write_bytes(data)
    if custom:
        hooks = Path(work) / ".git" / "hooks"
        hooks.mkdir(exist_ok=True)
        for name, body in custom.items():
            (hooks / name).write_text(body, newline="\n")
    proc = subprocess.run([SH, ".githooks/activate"], cwd=work, env=sandbox.env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _seed(sandbox, work, bare, sha):
    sandbox.git("init", "--bare", "-q", str(bare))
    sandbox.git("push", "-q", str(bare), f"{sha}:refs/heads/main", cwd=work)
    if sandbox.git("remote", "get-url", "origin", cwd=work, check=False).returncode == 0:
        sandbox.git("remote", "set-url", "origin", str(bare), cwd=work)
    else:
        sandbox.git("remote", "add", "origin", str(bare), cwd=work)
    # A clone brings its source's branches and a symbolic origin/HEAD. Drop them without following
    # the symref, so that origin holds exactly what was seeded.
    for line in sandbox.out("for-each-ref", "--format=%(refname)", "refs/remotes/origin", cwd=work).splitlines():
        sandbox.git("update-ref", "--no-deref", "-d", line, cwd=work)
    sandbox.git("symbolic-ref", "--delete", "refs/remotes/origin/HEAD", cwd=work, check=False)
    sandbox.git("fetch", "-q", "origin", cwd=work)
    assert sandbox.out("for-each-ref", "--format=%(refname)", "refs/remotes/origin", cwd=work) == "refs/remotes/origin/main"


def synthetic_chain(sb, work):
    """A deterministic upstream-shaped history. The ids repeat in every repository."""
    sb.clock = 1_650_000_000
    ids = {}
    ids["tag_commit"] = sb.commit(work, [], "upstream: 1.4.0", ANDREAS)
    sb.git("tag", "-a", "-m", "upstream v1.4.0", "upstream-v1.4.0", ids["tag_commit"], cwd=work, extra_env={
        "GIT_COMMITTER_NAME": ANDREAS[0], "GIT_COMMITTER_EMAIL": ANDREAS[1], "GIT_COMMITTER_DATE": "1650000001 +0000"})
    ids["tag_object"] = sb.out("rev-parse", "refs/tags/upstream-v1.4.0", cwd=work)
    ids["boundary_a"] = sb.commit(work, [ids["tag_commit"]], "upstream: tests on Windows", ANDREAS)
    ids["boundary_b"] = sb.commit(work, [ids["boundary_a"]], "upstream: screenshots", ANDREAS)
    mid = sb.commit(work, [ids["boundary_b"]], "upstream: PR 46 refactor", ANDREAS_NOREPLY)
    ids["boundary_dfd"] = sb.commit(work, [mid], "Merge #52: TLS-only and read-only", ANDREAS_NOREPLY, GITHUB)
    p1 = sb.commit(work, [ids["boundary_dfd"]], "upstream: AUDIO opcode 49", APPROVED)
    ids["boundary_pr50"] = sb.commit(work, [ids["boundary_dfd"], p1], "Merge #50: source-only Apollo", ANDREAS)
    ids["future_upstream"] = sb.commit(work, [ids["boundary_pr50"]], "upstream: feature/1.6.0 capture work", ANDREAS)
    return ids


def build_synthetic(sb, name, origin_state, trim_dfd=False, trim_pr50=False):
    work, bare = sb.root / name / "work", sb.root / name / "remote.git"
    work.mkdir(parents=True)
    sb.git("init", "-q", "-b", "main", str(work))
    ids = synthetic_chain(sb, work)
    sb.clock += 1_000
    pre = sb.commit(work, [ids["boundary_b"]], "fork: tests for the guard", APPROVED)
    # The previous fork main, then an integration merge of upstream into it (9d2d317's shape),
    # then the merge commit GitHub made for the pull request (ed701f32's shape).
    integration = sb.commit(work, [pre, ids["boundary_dfd"]], "Merge upstream PR 46 and 52", APPROVED)
    merged = sb.commit(work, [pre, integration], "Merge pull request #22", APPROVED, GITHUB)
    ids.update(pre_main=pre, integration=integration, merged_main=merged)
    origin_tip = {"pre": pre, "post": merged}.get(origin_state)
    if origin_state == "orphan":
        origin_tip = sb.commit(work, [], "fork: unrelated root", APPROVED)
    ids["origin_tip"] = origin_tip

    def transform(fname, text):
        mapping = {REAL[k]: ids[k] for k in PINNED}
        sep = " " if fname == "lib.sh" else "\n"
        if trim_dfd or trim_pr50:
            assert sep + REAL["boundary_pr50"] in text
            text = text.replace(sep + REAL["boundary_pr50"], "")
            assert REAL["boundary_pr50"] not in text
            del mapping[REAL["boundary_pr50"]]
        if trim_dfd:  # the boundaries as they stood before PR #22
            assert sep + REAL["boundary_dfd"] in text
            text = text.replace(sep + REAL["boundary_dfd"], "")
            assert REAL["boundary_dfd"] not in text
            del mapping[REAL["boundary_dfd"]]
        return _transform_synthetic(text, mapping)

    _seed(sb, work, bare, origin_tip)
    _install(sb, work, transform)
    return World(sb, work, bare, ids)


def _source_repo():
    return Path(os.environ.get("AMIGENT_HOOK_TEST_SOURCE") or ROOT)


def real_history_missing():
    if GIT is None or SH is None:
        return "git or sh is not available"
    src = _source_repo()
    probe = subprocess.run([GIT, "-c", "safe.directory=*", "-C", str(src), "rev-parse", "--git-dir"], capture_output=True, text=True)
    if probe.returncode != 0:
        return f"{src} is not a repository this Git can open"
    missing = []
    for key, sha in REAL.items():
        kind = "tag" if key == "tag_object" else "commit"
        r = subprocess.run([GIT, "-c", "safe.directory=*", "-C", str(src), "cat-file", "-t", sha], capture_output=True, text=True)
        if r.stdout.strip() != kind:
            missing.append(f"{key} {sha[:8]}")
    return ("pinned history is not in this repository: " + ", ".join(missing)) if missing else None


def build_real(sb, name, origin_state, old_hooks_from=None, lib_edit=None):
    work, bare = sb.root / name / "work", sb.root / name / "remote.git"
    work.parent.mkdir(parents=True)
    sb.git("clone", "--shared", "--no-checkout", "-q", str(_source_repo()), str(work))
    ids = dict(REAL)
    # Unreviewed post-PR-#50 commit descending from 5a85d63c (uses real feature/1.6.0 if present).
    has_160 = sb.git("cat-file", "-t", FEATURE_160, cwd=work, check=False)
    if has_160.returncode == 0 and has_160.stdout.strip() == "commit":
        ids["future_upstream"] = FEATURE_160
    else:
        ids["future_upstream"] = sb.commit(work, [REAL["boundary_pr50"]],
                                           "upstream: unreviewed post-PR-#50 work", ANDREAS)
    if origin_state == "orphan":
        ids["origin_tip"] = sb.commit(work, [], "fork: unrelated root", APPROVED)
    else:
        ids["origin_tip"] = {"pre": REAL["pre_main"], "post": REAL["merged_main"]}[origin_state]
    _seed(sb, work, bare, ids["origin_tip"])
    # lib_edit applies to the hooks under test; with old_hooks_from it applies to the old files below.
    _install(sb, work, None if old_hooks_from else lib_edit)
    if old_hooks_from:
        for fname in ("lib.sh", "pre-push", "upstream-baseline", "identity", "pre-commit"):
            data = sb.git("show", f"{old_hooks_from}:.githooks/{fname}", cwd=work).stdout
            if fname in ("lib.sh", "upstream-baseline") and lib_edit:
                data = lib_edit(fname, data)
            (work / ".git" / "hooks" / fname).write_bytes(data.encode())
    return World(sb, work, bare, ids)


class _GuardCases:
    """Cases shared by both worlds. Subclasses supply ``build(name, state)``."""

    worlds = None
    sandbox = None

    @classmethod
    def setUpClass(cls):
        cls.sandbox = Sandbox()
        cls.worlds = {}

    @classmethod
    def tearDownClass(cls):
        if cls.sandbox:
            cls.sandbox.close()

    def world(self, state):
        if state not in self.worlds:
            self.worlds[state] = self.build(f"w-{state}", state)
        w = self.worlds[state]
        self.addCleanup(w.reset)
        return w

    def own_world(self, name, state, **kw):
        return self.build(name, state, **kw)

    # ---- helpers

    def assertPushes(self, w, sha, name):
        proc = w.push(sha, f"heads/{name}")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(w.sb.out("rev-parse", f"refs/heads/{name}", cwd=w.bare), sha)
        return proc

    def assertRejected(self, w, sha, name, mention=None, refname=None):
        before = w.sb.snapshot(w.bare)
        proc = w.push(sha, refname or f"heads/{name}")
        self.assertNotEqual(proc.returncode, 0, "the guard accepted a push it must reject\n" + proc.stdout + proc.stderr)
        self.assertIn("amigent identity guard", proc.stderr)
        if mention:
            self.assertIn(mention, proc.stderr)
        self.assertEqual(w.sb.snapshot(w.bare), before, "a rejected push changed the remote")
        return proc

    def head_of(self, w, tip):
        return w.sb.out("rev-parse", tip, cwd=w.work)

    # ---- positive cases

    def test_p1_historical_upstream_history_stays_exempt(self):
        w = self.world("orphan")  # origin holds none of it, so only the pinned boundaries exempt it
        for i, key in enumerate(("tag_commit", "boundary_a", "boundary_b")):
            self.assertPushes(w, w.ids[key], f"hist-{i}")
            w.reset()

    def test_p2_pr_46_52_ancestry_through_dfd08619_passes(self):
        w = self.world("orphan")
        self.assertPushes(w, w.ids["boundary_dfd"], "dfd")

    def test_p2c_pr_50_ancestry_through_5a85d63c_passes(self):
        w = self.world("orphan")
        self.assertPushes(w, w.ids["boundary_pr50"], "pr50")
        w.reset()
        # A normal two-parent fork merge of PR #50 authored by APPROVED passes too.
        w_post = self.world("post")
        merge = w_post.sb.commit(
            w_post.work, [w_post.ids["merged_main"], w_post.ids["boundary_pr50"]],
            "Merge upstream PR #50 ancestry", APPROVED,
        )
        self.assertPushes(w_post, merge, "pr50-merge")

    def test_p2b_integration_commit_passes_against_the_pre_merge_origin(self):
        w = self.world("pre")  # origin main is the previous fork main
        self.assertPushes(w, w.ids["integration"], "integration")

    def test_p3_merged_fork_main_history_passes(self):
        w = self.world("post")  # origin main is the GitHub merge commit
        self.assertPushes(w, w.ids["merged_main"], "main-copy")
        w.reset()
        self.assertPushes(w, w.ids["integration"], "integration-copy")

    def test_p4_new_approved_commit_through_the_real_commit_hook(self):
        w = self.world("post")
        w.git("symbolic-ref", "HEAD", "refs/heads/p4")
        w.git("update-ref", "refs/heads/p4", w.ids["merged_main"])
        w.git("read-tree", w.ids["merged_main"])
        w.git("commit", "-q", "--allow-empty", "-m", "approved change")
        tip = self.head_of(w, "HEAD")
        raw = w.git("cat-file", "commit", tip).stdout
        self.assertIn(f"author {APPROVED[0]} <{APPROVED[1]}>", raw)
        self.assertIn(f"committer {APPROVED[0]} <{APPROVED[1]}>", raw)
        self.assertPushes(w, tip, "p4")

    def test_p5_branch_based_on_current_fork_main_with_several_commits(self):
        w = self.world("post")
        a = w.forged(w.ids["merged_main"], APPROVED, message="one")
        b = w.forged(a, APPROVED, message="two")
        self.assertPushes(w, b, "p5")

    def test_p6_push_from_a_linked_worktree_uses_the_shared_hooks(self):
        w = self.world("post")
        wt = w.sb.root / f"wt-{type(self).__name__}"
        w.git("worktree", "add", "--no-checkout", "-q", "-b", "p6", str(wt), w.ids["merged_main"])
        self.addCleanup(lambda: w.git("worktree", "remove", "--force", str(wt), check=False))
        hooks = w.sb.out("rev-parse", "--path-format=absolute", "--git-path", "hooks", cwd=wt)
        self.assertEqual(Path(hooks).resolve(), (Path(w.work) / ".git" / "hooks").resolve())
        tip = w.forged(w.ids["merged_main"], APPROVED, message="from a worktree")
        proc = w.sb.git("push", "origin", f"{tip}:refs/heads/p6", cwd=wt, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        bad = w.forged(w.ids["merged_main"], ANDREAS, message="from a worktree, forged")
        before = w.sb.snapshot(w.bare)
        proc = w.sb.git("push", "origin", f"{bad}:refs/heads/p6bad", cwd=wt, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(w.sb.snapshot(w.bare), before)

    def test_p7_hook_reads_crlf_ref_updates_and_runs_from_a_subdirectory(self):
        w = self.world("post")
        tip = w.forged(w.ids["merged_main"], APPROVED, message="crlf")
        line = f"refs/heads/crlf {tip} refs/heads/crlf {ZERO}\r\n".encode()
        sub = Path(w.work) / "sub" / "dir"
        sub.mkdir(parents=True, exist_ok=True)
        code, out, err = w.run_hook(line, cwd=sub)  # not the repository root
        self.assertEqual(code, 0, out + err)
        code, out, err = w.run_hook(line, cwd=sub, relative=True)  # the hook named by a relative path
        self.assertEqual(code, 0, out + err)
        bad = w.forged(w.ids["merged_main"], ANDREAS, message="crlf forged")
        code, out, err = w.run_hook(f"refs/heads/x {bad} refs/heads/x {ZERO}\r\n".encode(), cwd=w.work)
        self.assertEqual(code, 1, out + err)
        self.assertIn(bad, err)

    def test_p8_deleting_a_remote_ref_is_not_a_commit_check(self):
        w = self.world("post")
        code, out, err = w.run_hook(f"(delete) {ZERO} refs/heads/gone {w.ids['merged_main']}\n".encode())
        self.assertEqual(code, 0, out + err)

    def test_p9_activate_installs_the_guard_and_keeps_unrelated_hooks(self):
        w = self.world("post")
        hooks = Path(w.work) / ".git" / "hooks"
        for name in ("pre-commit", "pre-push", "lib.sh", "identity", "upstream-baseline"):
            self.assertTrue((hooks / name).is_file(), name)
        sb = Sandbox()
        try:
            repo = sb.root / "r"
            sb.git("init", "-q", str(repo))
            _install(sb, repo, custom={"commit-msg": "#!/bin/sh\nexit 0\n", "post-checkout": "#!/bin/sh\nexit 0\n"})
            self.assertEqual((repo / ".git" / "hooks" / "commit-msg").read_text(), "#!/bin/sh\nexit 0\n")
            self.assertTrue((repo / ".git" / "hooks" / "post-checkout").is_file())
            self.assertEqual(sb.out("config", "--local", "user.name", cwd=repo), APPROVED[0])
            self.assertEqual(sb.out("config", "--local", "user.useConfigOnly", cwd=repo), "true")
            self.assertEqual(sb.git("config", "--local", "core.hooksPath", cwd=repo, check=False).returncode, 1)
        finally:
            sb.close()

    def test_p10_pre_commit_rejects_an_overridden_identity(self):
        w = self.world("post")
        w.git("symbolic-ref", "HEAD", "refs/heads/p10")
        w.git("update-ref", "refs/heads/p10", w.ids["merged_main"])
        before = self.head_of(w, "HEAD")
        for env in ({"GIT_AUTHOR_NAME": "wrong", "GIT_AUTHOR_EMAIL": "wrong@example.com"},
                    {"GIT_COMMITTER_NAME": "wrong", "GIT_COMMITTER_EMAIL": "wrong@example.com"}):
            proc = w.git("commit", "-q", "--allow-empty", "-m", "probe", check=False, extra_env=env)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(self.head_of(w, "HEAD"), before)

    # ---- negative cases

    def test_n1_new_commit_claiming_andreas_as_author(self):
        w = self.world("post")
        sha = w.forged(w.ids["merged_main"], ANDREAS, APPROVED)
        self.assertRejected(w, sha, "n1", mention=sha)

    def test_n2_new_commit_claiming_andreas_as_committer(self):
        w = self.world("post")
        sha = w.forged(w.ids["merged_main"], APPROVED, ANDREAS)
        self.assertRejected(w, sha, "n2", mention=sha)

    def test_n2b_new_commit_claiming_andreas_as_both(self):
        w = self.world("post")
        for who in (ANDREAS, ANDREAS_NOREPLY):
            self.assertRejected(w, w.forged(w.ids["merged_main"], who), "n2b")

    def test_n3_unapproved_author_with_approved_committer(self):
        w = self.world("post")
        self.assertRejected(w, w.forged(w.ids["merged_main"], MALLORY, APPROVED), "n3")

    def test_n4_approved_author_with_unapproved_committer(self):
        w = self.world("post")
        self.assertRejected(w, w.forged(w.ids["merged_main"], APPROVED, MALLORY), "n4")

    def test_n4b_no_blanket_github_committer_exemption(self):
        w = self.world("post")
        sha = w.forged(w.ids["merged_main"], APPROVED, GITHUB, message="Merge pull request #99 from someone/else")
        self.assertRejected(w, sha, "n4b", mention="GitHub")
        sha = w.forged(w.ids["merged_main"], ANDREAS_NOREPLY, GITHUB, message="Merge #53")
        self.assertRejected(w, sha, "n4b2")

    def test_n4c_a_github_merge_is_trusted_only_once_origin_has_it(self):
        w = self.world("pre")  # origin does not have the merge commit yet
        self.assertRejected(w, w.ids["merged_main"], "n4c", mention=w.ids["merged_main"])

    def test_n5_branch_named_upstream_main_is_not_an_exemption(self):
        w = self.world("post")
        sha = w.forged(w.ids["merged_main"], ANDREAS, message="upstream main")
        for ref in ("refs/heads/upstream/main", "refs/remotes/upstream/main"):
            w.git("update-ref", ref, sha)
            self.addCleanup(lambda r=ref: w.git("update-ref", "-d", r, check=False))
        self.assertRejected(w, sha, "upstream/main")
        self.assertRejected(w, "refs/remotes/upstream/main", "n5b")

    def test_n6_misleading_tag_is_not_an_exemption(self):
        w = self.world("post")
        sha = w.forged(w.ids["merged_main"], ANDREAS, message="release")
        light = "upstream-v1.5.0"
        w.git("tag", light, sha)
        self.addCleanup(lambda: w.git("tag", "-d", light, check=False))
        ann = "upstream-v1.6.0"
        w.git("tag", "-a", "-m", "verified, honest", ann, sha, extra_env={
            "GIT_COMMITTER_NAME": ANDREAS[0], "GIT_COMMITTER_EMAIL": ANDREAS[1]})
        self.addCleanup(lambda: w.git("tag", "-d", ann, check=False))
        self.assertRejected(w, sha, "n6")
        self.assertRejected(w, sha, "n6t1", refname=f"tags/{light}")
        self.assertRejected(w, w.sb.out("rev-parse", ann, cwd=w.work), "n6t2", refname=f"tags/{ann}")

    def test_n7_forged_commit_with_an_upstream_looking_message_and_parents(self):
        w = self.world("post")
        msg = "Merge #52: optional TLS-only and server-enforced read-only modes"
        self.assertRejected(w, w.forged(w.ids["merged_main"], ANDREAS_NOREPLY, GITHUB, msg), "n7")
        # Parenting on a verified boundary does not make the new commit verified.
        sha = w.sb.commit(w.work, [w.ids["boundary_dfd"]], msg, ANDREAS_NOREPLY, GITHUB)
        self.assertRejected(w, sha, "n7b", mention=sha)
        # The commit message of a sibling that really is exempt does not travel.
        copy = w.sb.commit(w.work, [w.ids["merged_main"]], w.git("log", "-1", "--format=%B", w.ids["boundary_dfd"]).stdout, ANDREAS)
        self.assertRejected(w, copy, "n7c")

    def test_n8_post_pr_50_upstream_history_outside_the_pinned_ancestry(self):
        w = self.world("post")
        tip = w.ids["future_upstream"]
        self.assertRejected(w, tip, "n8", mention=tip)
        # Merging unreviewed post-PR-#50 history under the approved identity does not launder it.
        merge = w.sb.commit(w.work, [w.ids["merged_main"], tip], "Merge upstream feature/1.6.0", APPROVED)
        proc = self.assertRejected(w, merge, "n8b")
        self.assertNotIn(f"push rejected for {merge}", proc.stderr)  # the merge itself is approved
        self.assertIn(tip, proc.stderr)
        self.assertRejected(self.world("pre"), tip, "n8d")  # and against the pre-merge origin

    def test_n9_unverifiable_pins_or_objects_fail_closed(self):
        w = self.world("post")
        # An unknown commit named on the hook's input.
        code, out, err = w.run_hook(f"refs/heads/x {'1' * 40} refs/heads/x {ZERO}\n".encode())
        self.assertEqual(code, 1, out + err)
        self.assertIn("Fail closed", err)
        # A repository that does not hold the pinned upstream objects at all.
        sb = self.sandbox
        bare_world = _unpinned_world(sb, f"unpinned-{type(self).__name__}")
        proc = bare_world.push(bare_world.ids["origin_tip"], "heads/ok")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Fail closed", proc.stderr)
        child = bare_world.forged(bare_world.ids["origin_tip"], APPROVED)
        before = sb.snapshot(bare_world.bare)
        self.assertNotEqual(bare_world.push(child, "heads/child").returncode, 0)
        self.assertEqual(sb.snapshot(bare_world.bare), before)

    def test_n9b_missing_boundary_object_fails_closed(self):
        w = self.own_world(f"own-missing-{type(self).__name__}", "orphan")
        git_dir = Path(w.work) / ".git"
        lib = git_dir / "hooks" / "lib.sh"
        text = lib.read_text()
        # The hook pins an id this repository cannot supply. Nothing else changes.
        absent = "e" * 40
        self.assertIn(w.ids["boundary_pr50"], text)
        lib.write_text(text.replace(w.ids["boundary_pr50"], absent), newline="\n")
        base = (git_dir / "hooks" / "upstream-baseline")
        base.write_text(base.read_text().replace(w.ids["boundary_pr50"], absent), newline="\n")
        child = w.forged(w.ids["origin_tip"], APPROVED)
        before = w.sb.snapshot(w.bare)
        proc = w.push(child, "heads/x")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(absent, proc.stderr)
        self.assertEqual(w.sb.snapshot(w.bare), before)

    def test_n10_missing_origin_main_fails_closed(self):
        w = self.own_world(f"own-noorigin-{type(self).__name__}", "orphan")
        w.git("update-ref", "-d", "refs/remotes/origin/main")
        child = w.forged(w.ids["origin_tip"], APPROVED)
        proc = w.push(child, "heads/x")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Fail closed", proc.stderr)

    def test_n11_the_verified_tag_cannot_be_moved_or_replaced(self):
        w = self.own_world(f"own-tag-{type(self).__name__}", "orphan")
        forged_tip = w.forged(w.ids["origin_tip"], ANDREAS, message="moved tag")
        w.git("tag", "-f", "-a", "-m", "same name", "upstream-v1.4.0", forged_tip, extra_env={
            "GIT_COMMITTER_NAME": ANDREAS[0], "GIT_COMMITTER_EMAIL": ANDREAS[1]})
        child = w.forged(w.ids["origin_tip"], APPROVED)
        proc = w.push(child, "heads/x")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Fail closed", proc.stderr)
        w.git("tag", "-f", "upstream-v1.4.0", w.ids["tag_commit"])  # lightweight, not the verified object
        self.assertNotEqual(w.push(child, "heads/y").returncode, 0)

    def test_n12_the_baseline_file_cannot_add_a_boundary(self):
        w = self.own_world(f"own-extra-{type(self).__name__}", "orphan")
        hooks = Path(w.work) / ".git" / "hooks"
        base = hooks / "upstream-baseline"
        original = base.read_text()
        future = w.ids["future_upstream"]
        child = w.forged(w.ids["origin_tip"], APPROVED)
        for text, label in ((original.rstrip("\n") + "\n" + future + "\n", "added boundary"),
                            (original.rstrip("\n") + "\n\n  \nsomething\n", "trailing junk")):
            base.write_text(text, newline="\n")
            proc = w.push(child, "heads/x")
            self.assertNotEqual(proc.returncode, 0, label)
            self.assertIn("Fail closed", proc.stderr, label)
        # A boundary in the file that the hook does not pin is refused, even if the file omits others.
        lines = original.splitlines()
        base.write_text("\n".join(lines[:3] + [future]) + "\n", newline="\n")
        self.assertNotEqual(w.push(child, "heads/y").returncode, 0)
        # And the unreviewed future upstream tip is rejected as new history under the unmodified file.
        base.write_text(original, newline="\n")
        self.assertRejected(w, future, "n12", mention=future)

    def test_n13_without_the_new_boundary_the_integration_push_is_rejected(self):
        """The root cause, reproduced: boundaries that stop short of dfd08619 reject PR #22's integration commit."""
        w = self.build_old(f"own-old-{type(self).__name__}")
        proc = self.assertRejected(w, w.ids["integration"], "n13")
        self.assertIn("Andreas Wendorf", proc.stderr)

    def test_n13c_without_the_pr50_boundary_pr50_merge_is_rejected(self):
        """Boundaries that stop at dfd08619 reject upstream PR #50 (5a85d63c) and its fork merge."""
        w = self.build_pre_pr50(f"own-pre-pr50-{type(self).__name__}")
        tip = w.ids["boundary_pr50"]
        self.assertRejected(w, tip, "n13c", mention=tip)
        merge = w.sb.commit(w.work, [w.ids["merged_main"], tip], "Merge upstream PR #50", APPROVED)
        proc = self.assertRejected(w, merge, "n13c-merge", mention=tip)
        self.assertNotIn(f"push rejected for {merge}", proc.stderr)

    def test_n14_tracked_pins_are_exact_and_future_upstream_is_not_trusted(self):
        lib = (HOOKS / "lib.sh").read_text()
        base = (HOOKS / "upstream-baseline").read_text().splitlines()
        self.assertEqual(base, ["refs/tags/upstream-v1.4.0", REAL["tag_object"], REAL["tag_commit"],
                                REAL["boundary_a"], REAL["boundary_b"], REAL["boundary_dfd"],
                                REAL["boundary_pr50"]])
        self.assertIn(
            f'trusted_boundaries="{REAL["boundary_a"]} {REAL["boundary_b"]} '
            f'{REAL["boundary_dfd"]} {REAL["boundary_pr50"]}"',
            lib,
        )
        for name in ("lib.sh", "pre-push", "pre-commit", "upstream-baseline", "activate"):
            text = (HOOKS / name).read_text()
            self.assertNotIn(FEATURE_160, text, name)
            self.assertNotIn(FEATURE_160[:8], text, name)
        # No wildcard, name or author rule has crept in.
        for word in ("Andreas", "akustikrausch", "refs/remotes/upstream", "refs/heads/upstream", "--no-verify", "BYPASS"):
            self.assertNotIn(word, lib + (HOOKS / "pre-push").read_text())


def _unpinned_world(sb, name):
    """The real pins in a repository that has none of the upstream objects."""
    work, bare = sb.root / name / "work", sb.root / name / "remote.git"
    work.mkdir(parents=True)
    sb.git("init", "-q", "-b", "main", str(work))
    root = sb.commit(work, [], "fork: root", APPROVED)
    _seed(sb, work, bare, root)
    _install(sb, work)
    return World(sb, work, bare, {"origin_tip": root})


class SyntheticGuard(_GuardCases, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if GIT is None or SH is None:
            raise unittest.SkipTest("git or sh is not available")
        super().setUpClass()

    def build(self, name, state, **kw):
        return build_synthetic(self.sandbox, name, state, **kw)

    def build_old(self, name):
        return build_synthetic(self.sandbox, name, "pre", trim_dfd=True)

    def build_pre_pr50(self, name):
        return build_synthetic(self.sandbox, name, "post", trim_pr50=True)


class RealHistoryGuard(_GuardCases, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        why = real_history_missing()
        if why:
            raise unittest.SkipTest(why)
        super().setUpClass()

    def build(self, name, state, **kw):
        return build_real(self.sandbox, name, state, **kw)

    def build_old(self, name):
        """The hooks tracked at the PR #22 merge, whose boundary stops at f6aab1d4, and the stale installed variant."""
        return build_real(self.sandbox, name, "pre", old_hooks_from=REAL["merged_main"])

    def build_pre_pr50(self, name):
        """The hooks as they stood before PR #50 integration (stopping at dfd08619)."""
        def drop_pr50(fname, text):
            sep = " " if fname == "lib.sh" else "\n"
            assert sep + REAL["boundary_pr50"] in text
            return text.replace(sep + REAL["boundary_pr50"], "")
        return build_real(self.sandbox, name, "post", lib_edit=drop_pr50)

    def test_n13b_the_stale_installed_8e576ad9_variant_also_rejects(self):
        def edit(fname, text):
            return text.replace(REAL["boundary_a"], REAL["boundary_b"])
        w = build_real(self.sandbox, f"own-stale-{id(self)}", "pre", old_hooks_from=REAL["merged_main"], lib_edit=edit)
        text = (Path(w.work) / ".git" / "hooks" / "lib.sh").read_text()
        self.assertIn(REAL["boundary_b"], text)
        self.assertNotIn(REAL["boundary_dfd"], text)
        self.assertRejected(w, w.ids["integration"], "n13b")

    def test_n15_the_real_pr_50_history_is_trusted_and_feature_160_is_rejected(self):
        w = self.world("post")
        gone = w.sb.out("rev-list", "--count", REAL["boundary_pr50"], "--not", REAL["boundary_dfd"], REAL["merged_main"], cwd=w.work)
        self.assertEqual(gone, "10")  # the ten upstream PR #50 commits now covered by the 4th boundary
        self.assertPushes(w, REAL["boundary_pr50"], "n15-pr50")
        w.reset()
        # Unreviewed post-PR-#50 upstream history (real feature/1.6.0 when present, or descendant) stays rejected.
        has_160 = w.sb.git("cat-file", "-t", FEATURE_160, cwd=w.work, check=False)
        if has_160.returncode == 0 and has_160.stdout.strip() == "commit":
            ahead = w.sb.out("rev-list", "--count", FEATURE_160, "--not", REAL["boundary_pr50"], REAL["merged_main"], cwd=w.work)
            self.assertEqual(ahead, "8")
            self.assertRejected(w, FEATURE_160, "n15-160", mention=FEATURE_160)
        else:
            self.assertRejected(w, w.ids["future_upstream"], "n15-post", mention=w.ids["future_upstream"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
