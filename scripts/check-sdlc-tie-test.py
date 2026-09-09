#!/usr/bin/env python3
"""Cases for check-sdlc-tie.py: one named refusal per branch, and the allows
beside each -- the ordinary shapes a tie check could catch by mistake.

Each fixture is two trees: one committed, one staged on top, and the guard is
run `--staged` over the second against the first, which is what the pre-commit
does. The scenarios these fixtures play out are spec/sdlc/scenarios.als's:
`S1_FullChain` is the allow every refusal is a step away from,
`S4_RenameBreaksTheTie` is T2, `S4a_RenameKeepsItsNamers` its allow, and
`TreeStaysTied_Bites` is T1. Naming them here is also what ties the guard.

A mutation that deletes one branch of the guard fails the case named for it;
the PR that added this suite ran that sweep and its REPORT quotes the result.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "check-sdlc-tie.py"

SPEC = "spec/x/scenarios.als"
DECL = "run S1_FullChain for 3 expect 1\n"
SUITE = "#!/usr/bin/env python3\n# witnesses S1_FullChain\n"
CODE = "#!/usr/bin/env python3\nprint('x')\n"
TIED = {SPEC: DECL, "scripts/a.py": CODE, "scripts/a-test.py": SUITE}

# (name, committed tree, staged tree -- None deletes, code wanted or None)
CASES = [
    # ---- T1: a code path added untied.
    ("T1 a code path added with no suite",
     {SPEC: DECL}, {"scripts/a.py": CODE}, "T1"),
    ("T1 a code path added whose suite names no scenario",
     {SPEC: DECL}, {"scripts/a.py": CODE, "scripts/a-test.py": "# nothing\n"}, "T1"),
    ("T1 a suite naming the scenario only as the head of a longer word",
     {SPEC: DECL},
     {"scripts/a.py": CODE, "scripts/a-test.py": "# S1_FullChainX\n"}, "T1"),
    ("T1 a suite naming the scenario only as the tail of a longer word",
     {SPEC: DECL},
     {"scripts/a.py": CODE, "scripts/a-test.py": "# XS1_FullChain\n"}, "T1"),
    ("T1 on the first commit, with no HEAD to judge against",
     {}, {SPEC: DECL, "scripts/a.py": CODE}, "T1"),
    ("T1 a code path added in a skill's scripts/ with no suite anywhere",
     {SPEC: DECL}, {".claude/skills/s/scripts/a.sh": "#!/bin/sh\n"}, "T1"),
    ("T1 a nested script moved into a scripts/ slot enters the code set untied",
     {SPEC: DECL, "scripts/sub/a.py": CODE},
     {"scripts/sub/a.py": None, "scripts/a.py": CODE}, "T1"),
    ("T1 a fixture moved into a scripts/ slot enters the code set untied",
     {SPEC: DECL, "scripts/fixtures/a.py": CODE},
     {"scripts/fixtures/a.py": None, "scripts/a.py": CODE}, "T1"),
    ("T1 an extensionless script given its extension enters the code set untied",
     {SPEC: DECL, "scripts/a": CODE},
     {"scripts/a": None, "scripts/a.py": CODE}, "T1"),
    # ---- T2: a tied code path loses its suite.
    ("T2 the code path renamed and its suite not",
     TIED, {"scripts/a.py": None, "scripts/b.py": CODE}, "T2"),
    ("T2 the suite deleted from under a tied code path",
     TIED, {"scripts/a-test.py": None}, "T2"),
    ("T2 the suite renamed away from its code path",
     TIED, {"scripts/a-test.py": None, "scripts/c-test.py": SUITE}, "T2"),
    # ---- T3: a tied code path's suite stops naming a scenario.
    ("T3 the scenario renamed and the suite still names the old one",
     TIED, {SPEC: "run S1_Other for 3 expect 1\n"}, "T3"),
    ("T3 the line naming the scenario dropped from the suite",
     TIED, {"scripts/a-test.py": "#!/usr/bin/env python3\n"}, "T3"),
    ("T3 the scenario's module deleted",
     TIED, {SPEC: None}, "T3"),
    # ---- allows.
    ("allow a full chain added in one commit",
     {"README.md": "r\n"}, TIED, None),
    ("allow the rename that rewrites its suite in the same commit",
     TIED, {"scripts/a.py": None, "scripts/b.py": CODE,
            "scripts/a-test.py": None, "scripts/b-test.py": SUITE}, None),
    ("allow a code path untied before the commit, edited",
     {SPEC: DECL, "scripts/a.py": CODE}, {"scripts/a.py": CODE + "y = 2\n"}, None),
    ("allow a code path untied before the commit, renamed",
     {SPEC: DECL, "scripts/a.py": CODE}, {"scripts/a.py": None, "scripts/b.py": CODE}, None),
    ("allow a suite written before its code path",
     {SPEC: DECL}, {"scripts/a-test.py": SUITE}, None),
    ("allow the code path written after its suite",
     {SPEC: DECL, "scripts/a-test.py": SUITE}, {"scripts/a.py": CODE}, None),
    ("allow a scenario added on its own",
     TIED, {"spec/y/checks.als": "check Z for 3 expect 0\n"}, None),
    ("allow a commit touching neither spec, suite nor code path",
     TIED, {"README.md": "r\n"}, None),
    ("allow a suite in scripts/ tying a code path in a skill's scripts/",
     {SPEC: DECL},
     {".claude/skills/s/scripts/a.sh": "#!/bin/sh\n", "scripts/a-test.py": SUITE}, None),
    ("allow a code path tied through a `check`, not only a `run`",
     {SPEC: "check Held for 3 expect 0\n"},
     {"scripts/a.py": CODE, "scripts/a-test.py": "# Held\n"}, None),
    ("allow a file under scripts/fixtures/, which is data",
     {SPEC: DECL}, {"scripts/fixtures/a.py": CODE}, None),
    ("allow a file nested below scripts/, which is not a code path",
     {SPEC: DECL}, {"scripts/sub/a.py": CODE}, None),
    ("allow a scripts/ file with no language extension, which R6 refuses instead",
     {SPEC: DECL}, {"scripts/a": CODE}, None),
    ("allow a scenario renamed with its suite rewritten",
     TIED, {SPEC: "run S1_Other for 3 expect 1\n",
            "scripts/a-test.py": "# S1_Other\n"}, None),
]


def commit(root, files):
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "before", "--no-verify", "--allow-empty"],
                   cwd=root, check=True)


def stage(root, files):
    for rel, body in files.items():
        p = root / rel
        if body is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)


def run_case(before, after, args=("--staged",), on_disk=None, cwd=""):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d).resolve()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        if before:
            commit(root, before)
        stage(root, after)
        for rel, body in (on_disk or {}).items():
            p = root / rel
            if body is None:
                p.unlink()
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body)
        return subprocess.run([sys.executable, str(GUARD), *args], cwd=root / cwd,
                              capture_output=True, text=True)


def judge(r, code):
    out = r.stdout + r.stderr
    read = "check-sdlc-tie: read " in r.stdout
    if code:
        return (r.returncode == 1 and f"{code}\t" in r.stderr and read,
                f"a {code} finding on stderr beside the reading, exit 1")
    return (r.returncode == 0 and "0 finding(s)" in r.stdout and read
            and "PERMITTING" not in out,
            "0 finding(s) beside the reading, exit 0")


def main():
    failed = ran = 0

    def check(name, ok, want, r):
        nonlocal failed, ran
        ran += 1
        if ok:
            print(f"ok    {name}")
        else:
            failed += 1
            print(f"FAIL  {name}: wanted {want}")
            print("      " + (r.stdout + r.stderr).strip().replace("\n", "\n      ")[:900])

    for name, before, after, code in CASES:
        r = run_case(before, after)
        ok, want = judge(r, code)
        check(name, ok, want, r)

    # --staged reads the index and not the disk, both ways round.
    r = run_case({SPEC: DECL}, {"scripts/a.py": CODE}, on_disk={"scripts/a.py": None})
    ok, want = judge(r, "T1")
    check("--staged judges the untied code path staged, though it is gone from disk",
          ok, want, r)
    r = run_case({SPEC: DECL}, {"README.md": "r\n"}, on_disk={"scripts/a.py": CODE})
    ok, want = judge(r, None)
    check("--staged ignores an untied code path only the disk has", ok, want, r)
    r = run_case({SPEC: DECL}, {"scripts/a.py": CODE, "scripts/a-test.py": SUITE},
                 on_disk={"scripts/a-test.py": "# nothing\n"})
    ok, want = judge(r, None)
    check("--staged reads the suite's staged text, not the disk's emptier one", ok, want, r)
    r = run_case({SPEC: DECL}, {"scripts/a.py": CODE, "scripts/a-test.py": "# nothing\n"},
                 on_disk={"scripts/a-test.py": SUITE})
    ok, want = judge(r, "T1")
    check("--staged reads the suite's staged text, not the disk's tied one", ok, want, r)

    # Without --staged the working tree is read against HEAD.
    r = run_case({SPEC: DECL}, {}, args=(), on_disk={"scripts/a.py": CODE})
    check("without --staged, an untied code path on disk is not read: it is untracked",
          r.returncode == 0 and "0 finding(s)" in r.stdout, "exit 0", r)
    r = run_case(TIED, {}, args=(), on_disk={"scripts/a-test.py": "# gone\n"})
    check("without --staged, a suite edited on disk to name nothing is T3",
          r.returncode == 1 and "T3\t" in r.stderr, "T3 on stderr, exit 1", r)
    r = run_case(TIED, {}, args=(), on_disk={"scripts/a-test.py": None})
    check("without --staged, a suite deleted on disk and not staged is T2, not a permit",
          r.returncode == 1 and "T2\t" in r.stderr and "PERMITTING" not in r.stderr,
          "T2 on stderr, exit 1", r)
    r = run_case(TIED, {}, args=(), on_disk={SPEC: None})
    check("without --staged, a spec module deleted on disk and not staged is T3",
          r.returncode == 1 and "T3\t" in r.stderr and "PERMITTING" not in r.stderr,
          "T3 on stderr, exit 1", r)

    # From a subdirectory the same tree is read.
    r = run_case({SPEC: DECL}, {"scripts/a.py": CODE}, cwd="spec")
    ok, want = judge(r, "T1")
    check("run from a subdirectory, the guard reads the whole tree", ok, want, r)

    # The legacy debt is reported by name on the allow that leaves it.
    r = run_case({SPEC: DECL, "scripts/a.py": CODE}, {"scripts/a.py": CODE + "y\n"})
    check("an untied code path left untied is named in the reading",
          "1 code path(s) untied before this commit and left so: scripts/a.py"
          in r.stdout, "the legacy line naming scripts/a.py", r)

    # A reading that fails permits, and says so.
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([sys.executable, str(GUARD), "--staged"], cwd=d,
                           capture_output=True, text=True)
    check("outside a git repository the guard permits loudly",
          r.returncode == 0 and "PERMITTING" in r.stderr
          and "CalledProcessError" in r.stderr,
          "exit 0 and PERMITTING naming the exception", r)

    # The reading names its counts and its tree.
    r = run_case(TIED, {"README.md": "r\n"})
    want = ("read 1 scenario name(s), 1 suite(s), 1 code path(s) from the index under")
    check("the reading names what it counted and where", want in r.stdout, want, r)

    print(f"{ran} case(s) ran, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
