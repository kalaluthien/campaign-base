#!/usr/bin/env python3
"""The one harness the suites import: the tally, its verdict, and the fixture helpers.

A suite records each case with `check` and returns `report()` from `main`;
`load` makes a script a module by its path; `run_case` and `mutate` run a
table of cases and break a script's branches in turn; `git`, `write_tree` and
`guard_in_repo` build a fixture repository, and `fake` puts a stand-in command
on a case's PATH. Each was a copy in every suite that used it, and a copy is
what drifts.

It is named as a suite and is one: run, it proves the tally and the helpers
below. Named as a code path it would owe a scenario, and it is test code that
no scenario describes. A suite in `scripts/` imports it by name,
`importlib.import_module("suite-harness-test")`, since the script's own
directory heads `sys.path`; a skill's suite appends this directory to it.

Usage: scripts/suite-harness-test.py
"""
import atexit
import contextlib
import importlib.machinery
import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAN, FAILED = [], []


def check(name, ok, detail=""):
    """Record one case; a false `ok` fails it, and `detail` says what was seen."""
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}  -- {detail}" if detail else name)


def report():
    """Print each failure and the tally; the exit status `main` returns. A run
    that recorded no case is a failure too, since an empty run prints green."""
    for name in FAILED:
        print(f"FAIL  {name}")
    if not RAN:
        print("FAIL  the suite ran no case at all")
        return 1
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


def load(path, alias):
    """The script at `path` as a module named `alias`, executed afresh on every
    call: these are scripts and not a package, and a suite that loads a copy
    or loads twice must get a module of its own each time."""
    spec = importlib.util.spec_from_loader(
        alias, importlib.machinery.SourceFileLoader(alias, str(path)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_case(case, *args):
    """(ok, detail) from one case, or (None, what crashed): a crash asserted nothing."""
    try:
        ok, detail = case(*args)
        return bool(ok), detail
    except Exception as e:  # noqa: BLE001 -- a crash is reported, not red
        return None, f"{e.__class__.__name__}: {e}"


def mutate(source, load, cases, mutations):
    """Every case green on `load(source)`, then each `(label, old, new, case
    name)` red on the source with `old` replaced, by that case's own assertion."""
    real = load(source)
    for name, case in cases.items():
        ok, detail = run_case(case, real)
        check(name, ok, str(detail)[-600:])
    for label, old, new, name in mutations:
        count = source.count(old)
        if count != 1:
            check(f"MUTATION {label}", False, f"the text to break occurs {count} times")
            continue
        ok, detail = run_case(lambda m: cases[name](m), load(source.replace(old, new)))
        check(f"MUTATION {label}", ok is False,
              f"{name!r} crashed -- {detail}" if ok is None else f"{name!r} stayed green")


def git(cwd, *args, check=False, **kw):
    """git in `cwd` under a fixed identity, so a fixture commits on a machine
    with none. `check` raises on a non-zero exit, carrying what git said."""
    r = subprocess.run(["git", "-C", str(cwd), "-c", "user.email=t@t",
                        "-c", "user.name=t", *args],
                       capture_output=True, text=True, **kw)
    if check and r.returncode:
        raise AssertionError(f"git {' '.join(args)} in {cwd}: {r.stderr.strip()}")
    return r


def write_tree(root, files):
    """Write `{relative path: text or bytes}` under `root`; None is a path left absent."""
    for rel, body in files.items():
        if body is None:
            continue
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, bytes):
            p.write_bytes(body)
        else:
            p.write_text(body, encoding="utf-8")


_FAKES = {}


def fake(bin_dir, name, body):
    """An executable `name` holding `body` in `bin_dir`, linked to one copy
    written per run. The first exec of a new file costs 160-360 ms on macOS
    and a later one about 15, measured on sdlc-alloy#364, so a fake written
    per case paid that every case. A fake that needs its case's directory
    reads it off `sys.argv[0]`, which names the link and not the copy."""
    if (name, body) not in _FAKES:
        home = Path(tempfile.mkdtemp(prefix="suite-fake-"))
        atexit.register(shutil.rmtree, home, True)
        (home / name).write_text(body)
        (home / name).chmod(0o755)
        _FAKES[name, body] = home / name
    Path(bin_dir).mkdir(parents=True, exist_ok=True)
    (Path(bin_dir) / name).symlink_to(_FAKES[name, body])


def guard_in_repo(guard, files, *args):
    """`guard` run in a fresh repository holding `files`, every one of them staged."""
    with tempfile.TemporaryDirectory() as d:
        write_tree(d, files)
        git(d, "init", "-q", check=True)
        git(d, "add", "-Af", check=True)
        return subprocess.run([sys.executable, str(guard), *args], cwd=d,
                              capture_output=True, text=True)


@contextlib.contextmanager
def apart():
    """A tally of its own for the block, the suite's restored after it."""
    saved = RAN[:], FAILED[:]
    RAN.clear()
    FAILED.clear()
    try:
        yield
    finally:
        RAN[:], FAILED[:] = saved


def main():
    """Each helper against a case whose answer is known, on a tally of its own."""
    # `check` first and by hand: a `check` that drops a failure drops its own too
    with apart():
        check("b", False, "seen")
        recorded = FAILED == ["b  -- seen"]
    if not recorded:
        print("FAIL  check does not record a failing case, so no case here can fail")
        return 1

    def verdict(*cases):
        with apart(), contextlib.redirect_stdout(io.StringIO()) as out:
            for name, ok in cases:
                check(name, ok, "seen")
            return report(), out.getvalue(), FAILED[:]

    got = [verdict(("a", True)), verdict(("a", True), ("b", False)), verdict()]
    check("a passing tally exits 0 and says so", got[0][:2] == (0, "1/1 cases pass\n"), got[0])
    check("a failing case exits 1, named with its detail",
          got[1][0] == 1 and "FAIL  b  -- seen" in got[1][1] and got[1][2] == ["b  -- seen"], got[1])
    check("a run of no case exits 1", got[2][0] == 1 and "ran no case" in got[2][1], got[2])

    def boom():
        raise ValueError("x")
    check("run_case passes a case's own verdict through, as a bool",
          run_case(lambda: ([], "d")) == (False, "d") and run_case(lambda: ([], "d"))[0] is False)
    check("run_case reports a crash as None, never red", run_case(boom) == (None, "ValueError: x"))

    with tempfile.TemporaryDirectory() as d:
        script = Path(d) / "a-b.py"
        script.write_text("N = []\nN.append(__name__)\n")
        one, two = load(script, "ab"), load(script, "ab")
        check("load executes a hyphenated script afresh on every call, under its alias",
              one is not two and one.N == ["ab"] and two.N == ["ab"]
              and one.__file__ == str(script) and "ab" not in sys.modules,
              f"{one.N} {two.N} {one.__file__}")

    # The loader's floor, rule-check#370 row 4: every suite loads through
    # `load` above, and a code file holds one loader of its own, since it
    # cannot import one it would first have to load by path.
    r = git(Path(__file__).resolve().parent.parent, "grep", "-c",
            "module_from_spec[(]", "--", "*.py", ":!*fixtures*")
    sites = dict(line.rsplit(":", 1) for line in r.stdout.split())
    suites = sorted(p for p in sites if p.endswith("-test.py"))
    check("only this harness builds a module from a path among the suites",
          r.returncode == 0 and [Path(p).name for p in suites] == [Path(__file__).name]
          and sites[suites[0]] == "1", f"{r.stderr.strip()} {suites}")
    check("a code file builds a module from a path in one place at most",
          sites and all(n == "1" for n in sites.values()),
          {p: n for p, n in sites.items() if n != "1"})

    def run_text(text):
        ns = {}
        exec(text, ns)
        return ns

    with apart():
        mutate("def f():\n    return 1\n", run_text,
               {"f is 1": lambda m: (m["f"]() == 1, ""),
                "f is 2": lambda m: (m["f"]() == 2, "f is 1")},
               [("caught", "return 1", "return 2", "f is 1"),
                ("survives", "def f", "def f", "f is 1"),
                ("absent", "return 3", "return 4", "f is 1"),
                ("crashed", "def f():", "f = 1\ndef g():", "f is 1"),
                ("unnamed", "return 1", "return 2", "no such case")])
        seen = RAN[:], FAILED[:]
    check("mutate runs every case, then each mutation", seen[0] == [
        "f is 1", "f is 2", "MUTATION caught", "MUTATION survives",
        "MUTATION absent", "MUTATION crashed", "MUTATION unnamed"], seen)
    check("a case red on the unmutated source fails", "f is 2  -- f is 1" in seen[1], seen[1])
    check("a mutation passes only when its case goes red by its own assertion",
          seen[1][1:4] == ["MUTATION survives  -- 'f is 1' stayed green",
                           "MUTATION absent  -- the text to break occurs 0 times",
                           "MUTATION crashed  -- 'f is 1' crashed -- TypeError: 'int' object is not callable"]
          and seen[1][4].startswith("MUTATION unnamed  -- 'no such case' crashed -- KeyError"),
          seen[1])

    with tempfile.TemporaryDirectory() as d:
        write_tree(d, {"a/b.txt": "t", "c.bin": b"\x00", "gone.txt": None})
        check("write_tree writes text and bytes, and leaves None absent",
              (Path(d) / "a/b.txt").read_text() == "t"
              and (Path(d) / "c.bin").read_bytes() == b"\x00"
              and not (Path(d) / "gone.txt").exists())
        git(d, "init", "-q", check=True)
        git(d, "add", "-A", check=True)
        r = git(d, "commit", "-qm", "m", env={"PATH": "/usr/bin:/bin", "HOME": d,
                                              "GIT_CONFIG_NOSYSTEM": "1"})
        check("git commits under its own identity with none configured",
              r.returncode == 0 and git(d, "log", "-1", "--format=%ae").stdout == "t@t\n",
              r.stderr)
        try:
            git(d, "rev-parse", "no-such-ref", check=True)
            raised = ""
        except AssertionError as e:
            raised = str(e)
        check("git with check raises, saying what git said",
              raised.startswith("git rev-parse no-such-ref in ") and "no-such-ref" in raised[30:],
              raised)

    with tempfile.TemporaryDirectory() as d:
        probe = Path(d) / "probe.py"
        probe.write_text("import subprocess, sys\n"
                         "print(subprocess.run(['git', 'diff', '--cached', '--name-only'],"
                         " capture_output=True, text=True).stdout.split(), sys.argv[1:])\n")
        r = guard_in_repo(probe, {"x.txt": "1", ".gitignore": "x.txt\n"}, "--flag")
        check("guard_in_repo runs the guard over every file staged, ignored ones too",
              r.stdout.strip() == "['.gitignore', 'x.txt'] ['--flag']", r.stdout + r.stderr)
    with tempfile.TemporaryDirectory() as d:
        body = "#!/bin/sh\necho \"$0\"\n"
        for case in ("a", "b"):
            fake(Path(d) / case / "bin", "said", body)
        said = [subprocess.run(["said"], capture_output=True, text=True,
                               env={"PATH": str(Path(d) / c / "bin")}).stdout.strip()
                for c in ("a", "b")]
        links = [(Path(d) / c / "bin" / "said").resolve() for c in ("a", "b")]
        check("fake links every case to one copy, and each sees its own path",
              said == [str(Path(d) / c / "bin" / "said") for c in ("a", "b")]
              and links[0] == links[1] and links[0] != Path(d) / "a" / "bin" / "said",
              f"{said} {links}")
    # read off the tally as well: a broken `report` cannot report itself
    return max(report(), 1 if FAILED else 0)


if __name__ == "__main__":
    sys.exit(main())
