#!/usr/bin/env python3
# witnesses: S1_FullChain, TreeStaysTied_Bites, S4_RenameBreaksTheTie
# witnesses: S4a_RenameKeepsItsNamers, S4b_RenameOfTheScenarioBreaksTheTie
# witnesses: S4c_RenameOfTheTestBreaksTheTie
"""Cases for check-sdlc-tie.py: one named refusal per branch, and the allows
beside each -- the ordinary shapes a tie check could catch by mistake.

Each fixture is two trees: one committed, one staged on top, and the guard is
run `--staged` over the second against the first, which is what the pre-commit
does. The scenarios these fixtures play out are spec/sdlc/scenarios.als's:
`S1_FullChain` is the allow every refusal is a step away from,
`S4_RenameBreaksTheTie` is T2 at the code path's end,
`S4c_RenameOfTheTestBreaksTheTie` is T2 at the suite's,
`S4b_RenameOfTheScenarioBreaksTheTie` is T3, `S4a_RenameKeepsItsNamers` is the
allow beside them, and `TreeStaysTied_Bites` is T1. The `# witnesses:` line
above is what ties this suite to them, and is itself the form under test.

EVERY CASE PASSES `--legacy`, with an empty list unless it is about the
allow-list. The built-in `LEGACY` names this repository's own untied paths, and
a fixture tree holds none of them, so a case that let the default stand would
be judging 22 spent lines rather than the shape it means to. The one case that
DOES let it stand is named for exactly that reading.

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
SUITE = "#!/usr/bin/env python3\n# witnesses: S1_FullChain\n"
CODE = "#!/usr/bin/env python3\nprint('x')\n"
TIED = {SPEC: DECL, "scripts/a.py": CODE, "scripts/a-test.py": SUITE}

# (name, committed tree, staged tree -- None deletes, code wanted or None)
CASES = [
    # ---- T1: a code path added untied.
    ("T1 a code path added with no suite",
     {SPEC: DECL}, {"scripts/a.py": CODE}, "T1"),
    ("T1 a code path added whose suite names no scenario",
     {SPEC: DECL}, {"scripts/a.py": CODE, "scripts/a-test.py": "# nothing\n"}, "T1"),
    ("T1 a suite that only mentions the scenario in prose, declaring nothing",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "# S1_FullChain is the allow every refusal steps from\n"}, "T1"),
    ("T1 a declaration whose name is the scenario's with a suffix",
     {SPEC: DECL},
     {"scripts/a.py": CODE, "scripts/a-test.py": "# witnesses: S1_FullChainX\n"}, "T1"),
    ("T1 a declaration naming a prefix of the scenario's name",
     {SPEC: DECL},
     {"scripts/a.py": CODE, "scripts/a-test.py": "# witnesses: S1_Full\n"}, "T1"),
    ("T1 a declaration whose name is the scenario's with a prefix",
     {SPEC: DECL},
     {"scripts/a.py": CODE, "scripts/a-test.py": "# witnesses: XS1_FullChain\n"}, "T1"),
    ("T1 a declaration naming only a scenario nothing under spec/ declares",
     {SPEC: DECL},
     {"scripts/a.py": CODE, "scripts/a-test.py": "# witnesses: S9_Nowhere\n"}, "T1"),
    ("T1 the word witnesses in prose, with no colon and no declaration",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "# witnesses S1_FullChain\n"}, "T1"),
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
    ("T3 the `# witnesses:` line dropped from the suite",
     TIED, {"scripts/a-test.py": "#!/usr/bin/env python3\n"}, "T3"),
    ("T3 the `# witnesses:` line left with a name spec/ no longer declares",
     TIED, {"scripts/a-test.py": "# witnesses: S1_Other\n"}, "T3"),
    ("T3 the scenario's module deleted",
     TIED, {SPEC: None}, "T3"),
    # ---- allows.
    ("allow a full chain added in one commit",
     {"README.md": "r\n"}, TIED, None),
    ("allow the rename that rewrites its suite in the same commit",
     TIED, {"scripts/a.py": None, "scripts/b.py": CODE,
            "scripts/a-test.py": None, "scripts/b-test.py": SUITE}, None),
    # ---- T4: untied on both sides, and no allow-list line licenses it.
    ("T4 a code path untied before the commit and after it, edited, unlisted",
     {SPEC: DECL, "scripts/a.py": CODE}, {"scripts/a.py": CODE + "y = 2\n"}, "T4"),
    ("T4 a code path untied before the commit and after it, renamed, unlisted",
     {SPEC: DECL, "scripts/a.py": CODE},
     {"scripts/a.py": None, "scripts/b.py": CODE}, "T4"),
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
     {"scripts/a.py": CODE, "scripts/a-test.py": "# witnesses: Held\n"}, None),
    ("allow a file under scripts/fixtures/, which is data",
     {SPEC: DECL}, {"scripts/fixtures/a.py": CODE}, None),
    ("allow a file nested below scripts/, which is not a code path",
     {SPEC: DECL}, {"scripts/sub/a.py": CODE}, None),
    ("allow a scripts/ file with no language extension, which R6 refuses instead",
     {SPEC: DECL}, {"scripts/a": CODE}, None),
    ("allow a scenario renamed with its suite rewritten",
     TIED, {SPEC: "run S1_Other for 3 expect 1\n",
            "scripts/a-test.py": "# witnesses: S1_Other\n"}, None),
    ("allow a declaration naming two, only one of which spec/ declares",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "# witnesses: S9_Nowhere, S1_FullChain\n"}, None),
    ("allow a declaration written with slack whitespace around every part",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "#   witnesses:   S1_FullChain  \n"}, None),
    ("allow a declaration split over two `# witnesses:` lines",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "# witnesses: S9_Nowhere\n# witnesses: S1_FullChain\n"}, None),
    ("allow a suite holding a byte that is not UTF-8 beside its declaration",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": b"# witnesses: S1_FullChain\n# \xff\n"}, None),
    ("allow a spec module holding a byte that is not UTF-8",
     {}, {SPEC: b"run S1_FullChain for 3 expect 1\n-- \xff\n",
          "scripts/a.py": CODE, "scripts/a-test.py": SUITE}, None),
]


def put(root, rel, body):
    """A fixture file. `bytes` goes down as bytes, which is how the cases that
    are about a byte git will not decode say so; `None` deletes."""
    p = root / rel
    if body is None:
        p.unlink()
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, bytes):
        p.write_bytes(body)
    else:
        p.write_text(body)


def commit(root, files):
    for rel, body in files.items():
        put(root, rel, body)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "before", "--no-verify", "--allow-empty"],
                   cwd=root, check=True)


def stage(root, files):
    for rel, body in files.items():
        put(root, rel, body)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)


def run_case(before, after, args=("--staged",), on_disk=None, cwd="",
             legacy=(), config=(), commits=()):
    """One fixture repository, and the guard run over it.

    `legacy` is the allow-list, written to a file OUTSIDE the repository -- a
    file inside it would be a tracked path the guard then has to have an
    opinion about. `None` withholds the flag entirely, which is the only way
    the built-in `LEGACY` is reached. `commits` are further commits made after
    `before`, for the cases that need two commits to judge between."""
    with tempfile.TemporaryDirectory() as d:
        root = (Path(d) / "repo").resolve()
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        for k, v in config:
            subprocess.run(["git", "config", k, v], cwd=root, check=True)
        if before:
            commit(root, before)
        for files in commits:
            commit(root, files)
        stage(root, after)
        for rel, body in (on_disk or {}).items():
            put(root, rel, body)
        if legacy is not None:
            allow = Path(d) / "legacy.txt"
            allow.write_text("".join(f"{e}\n" for e in legacy))
            args = (*args, "--legacy", str(allow))
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

    # ---- the allow-list: what it licenses, and what spends a line.
    edit = ({SPEC: DECL, "scripts/a.py": CODE}, {"scripts/a.py": CODE + "y\n"})
    r = run_case(*edit, legacy=["scripts/a.py"])
    ok, want = judge(r, None)
    check("an allow-list line licenses the code path it names, left untied",
          ok and "1 code path(s) untied and licensed" in r.stdout,
          "0 finding(s) and the licensed count", r)
    r = run_case(*edit, legacy=["scripts/a.py  # why it is still untied"])
    ok, want = judge(r, None)
    check("an allow-list line's trailing `#` comment is not part of the path",
          ok, want, r)
    r = run_case({SPEC: DECL, "scripts/a.py": CODE},
                 {"scripts/a.py": None, "scripts/b.py": CODE},
                 legacy=["scripts/b.py"])
    ok, want = judge(r, None)
    check("a rename carries the licence, so file and line move in one commit",
          ok, want, r)
    r = run_case(TIED, {"README.md": "r\n"}, legacy=["scripts/a.py"])
    ok, want = judge(r, "T5")
    check("T5 an allow-list line whose code path is tied now", ok, want, r)
    r = run_case({SPEC: DECL, "scripts/a.py": CODE}, {"scripts/a.py": None},
                 legacy=["scripts/a.py"])
    ok, want = judge(r, "T5")
    check("T5 an allow-list line whose code path the tree no longer holds", ok, want, r)
    r = run_case(TIED, {"README.md": "r\n"}, legacy=None)
    check("with no --legacy the built-in list is read, and a tree holding none "
          "of its paths reports every line spent",
          r.returncode == 1 and "T5\t" in r.stderr and "(LEGACY," in r.stdout,
          "T5 findings and a reading naming LEGACY", r)

    # ---- --against <ref>: the whole change between two commits, which is what
    # CI has to judge and what judging against HEAD on a merge commit cannot see.
    # The allow-list is the same on both sides, so the flag is the only thing
    # that varies between the two readings.
    two = dict(before={SPEC: DECL}, after={}, commits=[{"scripts/a.py": CODE}],
               legacy=["scripts/a.py"])
    r = run_case(two["before"], two["after"], args=(), commits=two["commits"],
                 legacy=two["legacy"])
    ok, want = judge(r, None)
    check("against HEAD, a change already committed is nothing left to judge",
          ok, want, r)
    r = run_case(two["before"], two["after"], args=("--against", "HEAD~1"),
                 commits=two["commits"], legacy=two["legacy"])
    ok, want = judge(r, "T1")
    check("--against a ref, the same change is judged as the commit that made it",
          ok, want, r)
    r = run_case(TIED, {}, args=("--against", "HEAD~1"),
                 commits=[{"scripts/a-test.py": None}])
    ok, want = judge(r, "T2")
    check("--against a ref reads a suite deleted in a later commit", ok, want, r)
    r = run_case({SPEC: DECL}, {}, args=("--against", "no-such-ref"))
    check("--against a ref that does not resolve permits loudly",
          r.returncode == 0 and "PERMITTING" in r.stderr, "exit 0 and PERMITTING", r)

    # ---- a non-ASCII path. `core.quotePath` is git's default and CI's, and a
    # quoted path matches no stem and no suffix, so it leaves every set without
    # a word. The listings are `-z`, which emits the bytes instead.
    quote = (("core.quotePath", "true"),)
    r = run_case({SPEC: DECL}, {"scripts/캠페인.py": CODE}, config=quote)
    ok, want = judge(r, "T1")
    check("a code path at a non-ASCII path is in the code set under quotePath",
          ok, want, r)
    r = run_case({SPEC: DECL},
                 {"scripts/캠페인.py": CODE, "scripts/캠페인-test.py": SUITE},
                 config=quote)
    ok, want = judge(r, None)
    check("a suite at a non-ASCII path ties the code path beside it", ok, want, r)
    # The committed tree is listed by a different command from the index, so it
    # needs a case of its own: quoted, this reads as T1 -- a path that was never
    # there before -- rather than as the T2 it is.
    r = run_case({SPEC: DECL, "scripts/캠페인.py": CODE,
                  "scripts/캠페인-test.py": SUITE},
                 {"scripts/캠페인-test.py": None}, config=quote)
    ok, want = judge(r, "T2")
    check("a code path tied at a non-ASCII path is read from the tree before",
          ok, want, r)
    # And the working tree is a third listing.
    r = run_case({SPEC: DECL, "scripts/캠페인.py": CODE,
                  "scripts/캠페인-test.py": SUITE},
                 {}, args=(), on_disk={"scripts/캠페인-test.py": None}, config=quote)
    ok, want = judge(r, "T2")
    check("without --staged, a non-ASCII path on disk is read the same way",
          ok, want, r)

    # ---- an allow-list file that is not there is a reading that could not be
    # made, and permitting on it would license a debt nobody listed.
    r = run_case({SPEC: DECL, "scripts/a.py": CODE},
                 {"scripts/a.py": CODE + "y\n"},
                 args=("--staged", "--legacy", "/nonexistent/legacy.txt"),
                 legacy=None)
    check("an allow-list file that is not there permits loudly, and does not "
          "read as a list of nothing",
          r.returncode == 0 and "PERMITTING" in r.stderr
          and "FileNotFoundError" in r.stderr,
          "exit 0 and PERMITTING naming the exception", r)

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
