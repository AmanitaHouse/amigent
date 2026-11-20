"""Generated files stay in build/, and a dirty checkout is not the failure."""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hygiene import (
    combine_exit,
    guarded,
    modes_survive,
    sh_quote,
    temporary_directory,
    unexpected,
    wsl_bash,
    wsl_path,
)

ROOT = Path(__file__).resolve().parents[1]
JUNK = ("a.out", "=1.2,", "=10")


def _mark(size: int, salt: bytes) -> tuple[int, str]:
    return size, hashlib.sha256(salt).hexdigest()


def test_unexpected_inventory_fails_on_a_root_artifact():
    before = {
        "README.md": _mark(10, b"readme"),
        "build/classic/amigentd.o": _mark(4, b"obj"),
    }
    after = dict(before)
    after["a.out"] = _mark(323, b"vasm")
    after["build/classic/hookstub.bin"] = _mark(8, b"bigger")
    assert unexpected(before, after) == ["created a.out"]

    grown = dict(before)
    grown["README.md"] = _mark(11, b"readme-grown")
    assert unexpected(before, grown) == ["resized README.md"]

    same_size = dict(before)
    same_size["README.md"] = _mark(10, b"readme-edited")
    assert unexpected(before, same_size) == ["modified README.md"]

    same = dict(before)
    same["build/pytest/cache"] = _mark(1, b"cache")
    assert unexpected(before, same) == []

    shipped = dict(before)
    shipped["dist/amigent-1.3.0.tar.gz"] = _mark(8, b"sdist")
    shipped["build/apollo/amigentd.apollo"] = _mark(8, b"apollo")
    assert unexpected(before, shipped) == []

    numbered = dict(before)
    numbered["2"] = _mark(0, b"")
    numbered[" 2"] = _mark(16, b"log")
    assert unexpected(before, numbered) == ["created  2", "created 2"]

    removed = dict(before)
    del removed["README.md"]
    assert unexpected(before, removed) == ["removed README.md"]


def test_exit_status_does_not_depend_on_a_named_test():
    assert combine_exit(0, ["created a.out"]) == 1
    assert combine_exit(3, ["created a.out"]) == 3
    assert combine_exit(0, []) == 0
    assert combine_exit(2, []) == 2


def test_failed_command_is_still_scanned(tmp_path, capsys):
    root = tmp_path / "tree"
    root.mkdir()
    (root / "keep").write_bytes(b"same")
    code = guarded(
        [root],
        [sys.executable, "-c",
         "from pathlib import Path\n"
         "Path('keep').write_bytes(b'xxxx')\n"
         "Path('new').write_bytes(b'z')\n"
         "raise SystemExit(3)\n"],
        cwd=root)
    assert code == 3
    err = capsys.readouterr().err
    assert "modified keep" in err
    assert "created new" in err


def test_interrupted_command_is_still_scanned(tmp_path, capsys):
    root = tmp_path / "tree"
    root.mkdir()
    code = guarded(
        [root],
        [sys.executable, "-c",
         "from pathlib import Path\n"
         "import os, signal\n"
         "Path('partial').write_bytes(b'q')\n"
         "os.kill(os.getpid(), signal.SIGTERM)\n"],
        cwd=root)
    assert code != 0
    assert "created partial" in capsys.readouterr().err


def test_runner_starts_python_with_the_cache_prefix():
    env = os.environ.copy()
    for name in ("PYTHONPYCACHEPREFIX", "TMPDIR", "TEMP", "TMP"):
        env.pop(name, None)
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "repo_hygiene.py"), "--",
         sys.executable, "-c",
         "import os, sys, tempfile\n"
         "print(os.environ.get('PYTHONPYCACHEPREFIX', ''))\n"
         "print(sys.pycache_prefix or '')\n"
         "print(os.environ.get('TMPDIR', ''))\n"
         "print(os.environ.get('TEMP', ''))\n"
         "print(os.environ.get('TMP', ''))\n"
         "print(tempfile.gettempdir())\n"],
        cwd=ROOT, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    prefix = str((ROOT / "build" / "pycache").resolve())
    temp = str(temporary_directory(ROOT))
    lines = [line.strip() for line in done.stdout.splitlines() if line.strip()]
    assert lines[-6:] == [prefix, prefix, temp, temp, temp, temp]
    assert prefix.startswith(str((ROOT / "build").resolve()))
    assert Path(temp).is_dir()
    build_tmp = (ROOT / "build" / "tmp").resolve()
    if modes_survive(build_tmp):
        assert Path(temp) == build_tmp
    else:
        assert ROOT.resolve() not in Path(temp).resolve().parents
        assert Path(temp).name.startswith("amigent-")
        assert modes_survive(Path(temp))


def test_repository_temp_is_used_when_private_modes_survive(tmp_path, monkeypatch):
    monkeypatch.setattr("hygiene.modes_survive", lambda directory: True)
    chosen = temporary_directory(tmp_path)
    assert chosen == (tmp_path / "build" / "tmp").resolve()


def test_os_temp_is_used_when_private_modes_do_not_survive(tmp_path, monkeypatch):
    monkeypatch.setattr("hygiene.modes_survive", lambda directory: directory.name != "tmp")
    chosen = temporary_directory(tmp_path)
    assert chosen.name.startswith("amigent-")
    assert tmp_path.resolve() not in chosen.parents
    assert chosen.is_dir()


def test_clean_command_stays_clean(tmp_path, capsys):
    root = tmp_path / "tree"
    root.mkdir()
    (root / "keep").write_bytes(b"same")
    code = guarded([root], [sys.executable, "-c", "raise SystemExit(0)"], cwd=root)
    assert code == 0
    assert capsys.readouterr().err == ""


def test_successful_command_that_writes_still_fails(tmp_path, capsys):
    root = tmp_path / "tree"
    root.mkdir()
    code = guarded(
        [root],
        [sys.executable, "-c", "from pathlib import Path; Path('a.out').write_bytes(b'x')"],
        cwd=root)
    assert code == 1
    assert "created a.out" in capsys.readouterr().err


def test_shell_quote_keeps_redirections_inside_one_word():
    assert sh_quote("mcp>=1.2,<2") == "'mcp>=1.2,<2'"
    assert sh_quote("pillow>=10") == "'pillow>=10'"
    assert sh_quote("") == "''"
    assert sh_quote("it's") == "'it'\"'\"'s'"
    quoted = wsl_bash(ROOT / "build" / "gate", ["printf", "%s", "mcp>=1.2,<2"])
    assert quoted[:4] == ["wsl.exe", "--exec", "/bin/bash", "-c"]
    assert "cd " in quoted[4]
    assert "'mcp>=1.2,<2'" in quoted[4]
    assert ">=" not in quoted[4].replace("'mcp>=1.2,<2'", "")


def _wsl_ready() -> bool:
    """True when this Windows process can run the reviewed WSL command shape."""
    if shutil.which("wsl.exe") is None and shutil.which("wsl") is None:
        return False
    try:
        done = subprocess.run(
            ["wsl.exe", "--exec", "/bin/bash", "-c", "printf ok"],
            capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0 and done.stdout == "ok"


@pytest.mark.skipif(not _wsl_ready(), reason="wsl.exe cannot run bash")
def test_wsl_sets_the_directory_and_does_not_redirect(tmp_path):
    gate = ROOT / "build" / "gate"
    gate.mkdir(parents=True, exist_ok=True)
    for name in JUNK:
        assert not (ROOT / name).exists(), name
        assert not (gate / name).exists(), name
    pwd = subprocess.run(wsl_bash(gate, ["pwd"]), check=True, capture_output=True, text=True)
    assert pwd.stdout.strip() == wsl_path(gate)
    shown = subprocess.run(
        wsl_bash(gate, ["printf", "%s", "mcp>=1.2,<2"]),
        check=True, capture_output=True, text=True)
    assert shown.stdout == "mcp>=1.2,<2"
    for name in JUNK:
        assert not (ROOT / name).exists(), name
        assert not (gate / name).exists(), name


def test_pycache_prefix_is_read_at_interpreter_startup(tmp_path):
    module = tmp_path / "sample_mod.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    prefix = tmp_path / "prefixed"
    env = os.environ.copy()
    env.pop("PYTHONPYCACHEPREFIX", None)
    late = subprocess.run(
        [sys.executable, "-c",
         "import os, sys\n"
         "os.environ['PYTHONPYCACHEPREFIX'] = sys.argv[1]\n"
         "sys.path.insert(0, sys.argv[2])\n"
         "import sample_mod\n",
         str(prefix), str(tmp_path)],
        env=env, check=True, capture_output=True, text=True)
    assert late.returncode == 0
    beside = list((tmp_path / "__pycache__").glob("sample_mod*.pyc"))
    assert beside, "setting the variable inside the process did not redirect bytecode"
    assert not list(prefix.rglob("sample_mod*.pyc"))
    for path in beside:
        path.unlink()
    started = env.copy()
    started["PYTHONPYCACHEPREFIX"] = str(prefix)
    subprocess.run(
        [sys.executable, "-c",
         "import sys\n"
         "sys.path.insert(0, sys.argv[1])\n"
         "import sample_mod\n",
         str(tmp_path)],
        env=started, check=True, capture_output=True, text=True)
    assert list(prefix.rglob("sample_mod*.pyc"))
    assert not list((tmp_path / "__pycache__").glob("sample_mod*.pyc"))


def git_dir(root: Path) -> Path:
    """The worktree git dir, including a Windows gitdir: pointer read from WSL."""
    pointer = root / ".git"
    if pointer.is_file() and pointer.read_text(encoding="utf-8").startswith("gitdir:"):
        raw = pointer.read_text(encoding="utf-8").split(":", 1)[1].strip()
        if len(raw) >= 3 and raw[1] == ":":
            return Path("/mnt") / raw[0].lower() / raw[2:].lstrip("\\/").replace("\\", "/")
        return Path(raw)
    return pointer


def test_known_junk_is_absent_and_untracked():
    for name in JUNK:
        assert not (ROOT / name).exists(), name
    listed = subprocess.run(
        ["git", f"--git-dir={git_dir(ROOT)}", "ls-files", "--", *JUNK],
        cwd=ROOT, check=True, capture_output=True, text=True)
    assert listed.stdout.strip() == ""


def test_suite_left_no_artifacts():
    from hygiene import drift

    assert drift() == []
