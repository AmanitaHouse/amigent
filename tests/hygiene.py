"""Before-and-after inventory of a checkout.

A created, removed, resized, or same-size-modified file outside ``build/`` and
``dist/`` is a failure. ``build/`` holds generated build and test output.
``dist/`` holds a deliberately built distribution. Files that were already
present, including legitimate uncommitted work, are the baseline and are not
reported.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


def _fingerprint(path: Path) -> tuple[int, str]:
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


# Generated output. A file anywhere else, including one named ``2``, is drift.
APPROVED_OUTPUT = ("build", "dist")


def _approved(rel: str) -> bool:
    return rel in APPROVED_OUTPUT or any(rel.startswith(name + "/") for name in APPROVED_OUTPUT)


def inventory(root: Path) -> dict[str, tuple[int, str]]:
    """Relative path to ``(size, sha256)``, skipping git metadata and approved output."""
    found: dict[str, tuple[int, str]] = {}
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        if here == root:
            dirnames[:] = [name for name in dirnames if name not in {".git", *APPROVED_OUTPUT}]
        else:
            dirnames[:] = [name for name in dirnames if name != ".git"]
        for name in filenames:
            path = here / name
            rel = path.relative_to(root).as_posix()
            if rel == ".git" or rel.startswith(".git/") or _approved(rel):
                continue
            try:
                found[rel] = _fingerprint(path)
            except OSError:
                continue
    return found


def unexpected(before: dict[str, tuple[int, str]], after: dict[str, tuple[int, str]]) -> list[str]:
    """Paths created, removed, resized, or modified outside approved output."""
    problems = []
    for rel in sorted(set(before) | set(after)):
        if _approved(rel):
            continue
        if rel not in before:
            problems.append(f"created {rel}")
        elif rel not in after:
            problems.append(f"removed {rel}")
        elif before[rel][0] != after[rel][0]:
            problems.append(f"resized {rel}")
        elif before[rel][1] != after[rel][1]:
            problems.append(f"modified {rel}")
    return problems


SESSION: dict[Path, dict[str, tuple[int, str]]] = {}


def remember(roots: list[Path]) -> None:
    SESSION.clear()
    for root in roots:
        SESSION[root.resolve()] = inventory(root)


def drift() -> list[str]:
    problems = []
    for root, before in SESSION.items():
        for item in unexpected(before, inventory(root)):
            problems.append(f"{root.name}: {item}")
    return problems


def combine_exit(exitstatus: int, problems: list[str]) -> int:
    """A dirty tree fails the run even when the command already failed.

    The decision does not look at test names or at which test ran last.
    """
    if problems and exitstatus == 0:
        return 1
    return exitstatus


def main_worktree(root: Path) -> Path | None:
    """The primary checkout when ``root`` is a linked git worktree."""
    pointer = root / ".git"
    if not pointer.is_file():
        return None
    text = pointer.read_text(encoding="utf-8", errors="replace").strip()
    if not text.startswith("gitdir:"):
        return None
    gitdir = Path(text.split(":", 1)[1].strip())
    common = gitdir
    while common.name != ".git" and common.parent != common:
        common = common.parent
    main = common.parent
    if main.resolve() == root.resolve():
        return None
    return main if (main / ".git").exists() else None


def modes_survive(directory: Path) -> bool:
    """Private Unix modes stick. A drvfs mount reports 0777 for every file.

    Windows has no Unix mode bits. The tests that check them do not run there,
    and pytest's temporary files work on a native NTFS directory.
    """
    if os.name == "nt":
        return True
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / f".mode-{os.getpid()}"
    try:
        probe.write_bytes(b"x")
        os.chmod(probe, 0o600)
        return (probe.stat().st_mode & 0o777) == 0o600
    except OSError:
        return False
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


def os_temporary_root() -> Path:
    """A temporary directory on the operating system's own filesystem.

    ``TMPDIR`` is ignored. The canonical runner may already have pointed it at
    the repository, and on WSL that repository directory can be a drvfs mount.
    """
    if os.name == "nt":
        for name in ("TEMP", "TMP"):
            value = os.environ.get(name)
            if value:
                return Path(value)
        return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Temp"
    return Path("/tmp")


def temporary_directory(root: Path) -> Path:
    """Where the test run keeps private files.

    ``build/tmp`` is used when that directory keeps the file modes the suite
    checks. When it does not, an isolated directory under the operating
    system's temporary storage is used instead. That directory is outside the
    repository, one per checkout, and is still not a maintained source folder.
    """
    root = root.resolve()
    local = (root / "build" / "tmp").resolve()
    local.mkdir(parents=True, exist_ok=True)
    if modes_survive(local):
        return local
    digest = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    isolated = (os_temporary_root() / f"amigent-{digest}").resolve()
    isolated.mkdir(parents=True, exist_ok=True)
    if root == isolated or root in isolated.parents:
        raise RuntimeError(f"temporary directory {isolated} is inside {root}")
    if not modes_survive(isolated):
        raise RuntimeError(f"no temporary directory keeps private file modes: {isolated}")
    return isolated


def sh_quote(text: str) -> str:
    """Single-quote text for bash, including empty strings and quotes."""
    return "'" + text.replace("'", "'\"'\"'") + "'"


def wsl_path(path: Path) -> str:
    """A Windows or POSIX path as bash inside WSL can ``cd`` to it."""
    text = str(path.resolve())
    if len(text) >= 2 and text[1] == ":":
        return "/mnt/" + text[0].lower() + text[2:].replace("\\", "/")
    return text.replace("\\", "/")


def wsl_bash(directory: Path, args: list[str]) -> list[str]:
    """``wsl.exe`` argv that cds to ``directory`` and runs ``args`` without a login shell.

    Every argument is one quoted word. Characters such as ``>``, ``<``, ``&``,
    and spaces stay inside that word, so bash does not open a redirection.

    The whole script is one argv element. It is not a PowerShell command line.
    Windows PowerShell parses ``2>&1`` inside a double-quoted native argument
    and, next to ``>``, creates a file named `` 2`` (a leading space) in the
    current directory. Do not append ``2>&1`` outside this argument.
    """
    if not args:
        raise ValueError("wsl command is empty")
    script = "cd " + sh_quote(wsl_path(directory)) + " && exec " + " ".join(sh_quote(a) for a in args)
    return ["wsl.exe", "--exec", "/bin/bash", "-c", script]


def _report(problems: list[str]) -> None:
    if not problems:
        return
    print("unexpected repository artifacts:", file=sys.stderr)
    for item in problems:
        print(item, file=sys.stderr)


def guarded(roots: list[Path], command: list[str], *, cwd: Path | None = None) -> int:
    """Run a command and always compare the tree, including after a non-zero exit.

    A failure to start the command still inventories. The return code stays
    the command's code when that code is already non-zero.
    """
    watched = [path.resolve() for path in roots]
    before = {path: inventory(path) for path in watched}
    code = 1
    try:
        code = subprocess.run(command, cwd=cwd or (watched[0] if watched else None)).returncode
    finally:
        problems = []
        for path in watched:
            label = path.name
            for item in unexpected(before[path], inventory(path)):
                problems.append(f"{label}: {item}")
        _report(problems)
        if problems and code == 0:
            code = 1
    return code


def run_checked(root: Path, command: list[str], *, cwd: Path | None = None) -> int:
    """Run a command and return 0 only when it succeeds and the tree is unchanged."""
    root = root.resolve()
    watched = [root]
    other = main_worktree(root)
    if other is not None:
        watched.append(other.resolve())
    return guarded(watched, command, cwd=cwd or root)
