#!/usr/bin/env python3
# witnesses: S1_FullChain, TreeStaysTied_Bites, S4_CodeRenameBreak
# witnesses: S4a_TiedCodeRename, S4b_ScenarioRenameBreak
# witnesses: S4c_TestRenameBreak, WitnessesResolve_Bites
# witnesses: S4e_ScenarioRenameWithItsTests
"""Cases for check-sdlc-tie.py: one named refusal per branch, and the allows
beside each -- the ordinary shapes a tie check could catch by mistake.

Each fixture is two trees: one committed, one staged on top, and the guard is
run `--staged` over the second against the first, which is what the pre-commit
does. The scenarios these fixtures play out are spec/sdlc's:
`S1_FullChain` is the allow every refusal is a step away from,
`S4_CodeRenameBreak` is T2 at the code path's end,
`S4c_TestRenameBreak` is T2 at the suite's,
`S4b_ScenarioRenameBreak` is T3, `S4a_TiedCodeRename` is the
allow beside them, `S4e_ScenarioRenameWithItsTests` is the allow beside T3,
`TreeStaysTied_Bites` is T1, and `WitnessesResolve_Bites`
in checks.als is T6. The `# witnesses:` lines
above are what tie this suite to them, and are themselves the form under test.

EVERY CASE PASSES `--legacy`, with an empty list unless it is about the
allow-list. The built-in `LEGACY` names this repository's own untied paths, and
a fixture tree holds none of them, so a case that let the default stand would
be judging 22 spent lines rather than the shape it means to. The one case that
DOES let it stand is named for exactly that reading.

A mutation that deletes one branch of the guard fails the case named for it;
the PR that added this suite ran that sweep and its REPORT quotes the result.
"""
import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "check-sdlc-tie.py"


def guard_module():
    """The guard as a module, for `LEGACY` alone. A case about the built-in
    list must not pin its LENGTH: the list shrinks by one line per repair, and a
    literal count here would make every such commit edit a case named for
    something else."""
    spec = importlib.util.spec_from_loader(
        "tie", importlib.machinery.SourceFileLoader("tie", str(GUARD)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LEGACY = guard_module().LEGACY

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
    ("allow a declaration written with slack whitespace around every part",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "#   witnesses:   S1_FullChain  \n"}, None),
    ("allow a declaration split over two `# witnesses:` lines, both live",
     {SPEC: DECL + "run S1_Other for 3 expect 1\n"},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "# witnesses: S1_FullChain\n# witnesses: S1_Other\n"}, None),
    ("allow a suite holding a byte that is not UTF-8 beside its declaration",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": b"# witnesses: S1_FullChain\n# \xff\n"}, None),
    ("allow a spec module holding a byte that is not UTF-8",
     {}, {SPEC: b"run S1_FullChain for 3 expect 1\n-- \xff\n",
          "scripts/a.py": CODE, "scripts/a-test.py": SUITE}, None),
]

# ---- T6: a declared name that resolves to no scenario. Each of these must
# come back with T6 AND NOTHING ELSE, because the gap it closes is one live name
# covering the rest: the code path is tied throughout, so a T1 or a T3 beside
# the T6 would mean the reading lost the live name -- a reader keeping one
# `# witnesses:` line of two, say -- and not that it found the dead one.
TWO = DECL + "run S1_Other for 3 expect 1\n"
BOTH = "# witnesses: S1_FullChain, S1_Other\n"
DEBT = {SPEC: DECL, "scripts/a.py": CODE,
        "scripts/a-test.py": "# witnesses: S1_FullChain, S9_Nowhere\n"}
T6_CASES = [
    ("T6 WitnessesResolve_Bites: a scenario renamed while the suite's other "
     "name still ties it, bd2143d's shape",
     {SPEC: TWO, "scripts/a.py": CODE, "scripts/a-test.py": BOTH},
     {SPEC: DECL + "run S1_Renamed for 3 expect 1\n"}),
    ("T6 a scenario's module deleted while another module still declares the "
     "suite's other name",
     {SPEC: DECL, "spec/y/checks.als": "check S1_Other for 3 expect 0\n",
      "scripts/a.py": CODE, "scripts/a-test.py": BOTH},
     {"spec/y/checks.als": None}),
    ("T6 a declaration naming two, only one of which spec/ declares",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "# witnesses: S9_Nowhere, S1_FullChain\n"}),
    ("T6 a dead name on the second `# witnesses:` line, the live one first",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "# witnesses: S1_FullChain\n# witnesses: S9_Nowhere\n"}),
    ("T6 a dead name on the first `# witnesses:` line, the live one second",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "# witnesses: S9_Nowhere\n# witnesses: S1_FullChain\n"}),
    ("T6 a suite written before its code path, declaring a dead name",
     {SPEC: DECL},
     {"scripts/a-test.py": "# witnesses: S1_FullChain, S9_Nowhere\n"}),
    ("T6 an indented `# witnesses:` line inside a multi-line string is a declaration too",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": SUITE + 'F = """\n    # witnesses: S9_Nowhere\n"""\n'}),
    ("T6 a dead name already there, in a suite this change edits",
     DEBT, {"scripts/a-test.py": DEBT["scripts/a-test.py"] + "x = 1\n"}),
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
             legacy=(), config=(), commits=(), branch_at_head=None,
             back_to=None):
    """One fixture repository, and the guard run over it.

    `legacy` is the allow-list, written to a file OUTSIDE the repository -- a
    file inside it would be a tracked path the guard then has to have an
    opinion about. `None` withholds the flag entirely, which is the only way
    the built-in `LEGACY` is reached. `commits` are further commits made after
    `before`, for the cases that need two commits to judge between;
    `branch_at_head` names the last of them and `back_to` then checks an earlier
    one out, which is how a HEAD that does not CONTAIN the ref is built."""
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
        if branch_at_head:
            subprocess.run(["git", "branch", branch_at_head], cwd=root, check=True)
        if back_to:
            subprocess.run(["git", "checkout", "-q", "--detach", back_to],
                           cwd=root, check=True)
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

    for name, before, after in T6_CASES:
        r = run_case(before, after)
        ok, want = judge(r, "T6")
        codes = {line.split("\t", 1)[0] for line in r.stderr.splitlines() if "\t" in line}
        check(name, ok and codes == {"T6"}, want + ", and no other code", r)

    # T6 names the file, the name and the tree it searched, and only the dead one.
    r = run_case({SPEC: DECL},
                 {"scripts/a-test.py": "# witnesses: S1_FullChain, S9_Nowhere\n"})
    line = next((ln for ln in r.stderr.splitlines() if ln.startswith("T6\t")), "")
    check("T6's line names the suite, the dead name and the tree it searched, "
          "and not the live name",
          line.startswith("T6\tscripts/a-test.py\t") and "`S9_Nowhere`" in line
          and "the index" in line and "S1_FullChain" not in line,
          "one T6 line naming scripts/a-test.py, `S9_Nowhere` and the index", r)
    # One line PER dead name: bd2143d left three of four, and a reader that
    # reported the first would read the same verdict with two names unlisted.
    r = run_case({SPEC: DECL},
                 {"scripts/a.py": CODE,
                  "scripts/a-test.py": "# witnesses: S9_A, S1_FullChain, S9_B, S9_C\n"})
    got = sorted(ln.split(" line declares `")[1].split("`")[0]
                 for ln in r.stderr.splitlines()
                 if ln.startswith("T6\t"))
    check("T6 names every dead name on its own line, three of four as bd2143d left",
          got == ["S9_A", "S9_B", "S9_C"], "T6 lines for S9_A, S9_B and S9_C", r)
    r = run_case(DEBT, {"README.md": "r\n"})
    ok, want = judge(r, None)
    check("a dead name already there, in a suite the change never opened, is not "
          "this change's debt, and the reading counts it",
          ok and "1 dead witness name(s) left where the change never opened"
          in r.stdout, "0 finding(s) and the count of what was left", r)

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
    r = run_case({SPEC: DECL}, {"scripts/a.py": CODE, "scripts/a-test.py": SUITE},
                 args=(), on_disk={"scripts/a-test.py":
                                   b"# witnesses: S1_FullChain\n# \xff\n"})
    ok, want = judge(r, None)
    check("without --staged, a byte that is not UTF-8 on disk is replaced, not "
          "raised", ok, want, r)
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
    rename = ({SPEC: DECL, "scripts/a.py": CODE},
              {"scripts/a.py": None, "scripts/b.py": CODE})
    r = run_case(*rename, legacy=["scripts/b.py"])
    ok, want = judge(r, None)
    check("a rename is licensed by the line's NEW name, so file and line move "
          "in one commit", ok, want, r)
    r = run_case(*rename, legacy=["scripts/a.py"])
    ok, want = judge(r, None)
    check("a rename is licensed by the line's OLD name too, so the line may "
          "move in the commit after", ok, want, r)
    r = run_case(TIED, {"README.md": "r\n"}, legacy=["scripts/a.py"])
    ok, want = judge(r, "T5")
    check("T5 an allow-list line whose code path is tied now", ok, want, r)
    r = run_case({SPEC: DECL, "scripts/a.py": CODE}, {"scripts/a.py": None},
                 legacy=["scripts/a.py"])
    ok, want = judge(r, None)
    check("an allow-list line naming no code path here is counted, not refused: "
          "a deleted path and a tree the list is not about read the same",
          ok and "1 naming no code path here" in r.stdout,
          "0 finding(s) and the absent count", r)
    r = run_case({SPEC: DECL, "scripts/a.py": CODE, "scripts/a-test.py": SUITE},
                 {"README.md": "r\n"},
                 legacy=["scripts/a.py", "scripts/gone.py"])
    ok, want = judge(r, "T5")
    check("T5 fires on the tied line while a line naming nothing here does not",
          ok and r.stderr.count("T5\t") == 1
          and "1 naming no code path here" in r.stdout,
          "exactly one T5, for the tied path", r)
    r = run_case({SPEC: DECL, "scripts/a.py": CODE}, {"README.md": "r\n"})
    ok, want = judge(r, None)
    check("a code path untied on both sides that the change never touched is "
          "not this change's debt: an unlisted path is refused only when the "
          "change opens it",
          ok, want, r)
    r = run_case(TIED, {"README.md": "r\n"}, legacy=None)
    ok, want = judge(r, None)
    check("with no --legacy the built-in list is read, and a tree that never "
          "held its paths is not judged to have spent every line",
          ok and f"(LEGACY, {len(LEGACY)} entr(ies), {len(LEGACY)} naming no "
          f"code path here)" in r.stdout,
          "0 finding(s) and a reading naming LEGACY, its size and its absences", r)

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
    # The phrase is the GATE's, not the last-resort handler's: with the
    # could-not-read branch deleted the 128 falls through to `ls-tree`, whose
    # raise the handler reports as "the reading itself failed" too -- so a case
    # asserting that much passes on the wrong reader.
    check("--against a ref that does not resolve says the READING failed, not "
          "that HEAD does not contain it",
          r.returncode == 0 and "does not contain" not in r.stderr
          and "git could not say whether HEAD contains" in r.stderr,
          "exit 0 and the gate's own could-not-read line", r)
    check("...and git's own message is quoted inside the guard's line rather "
          "than printed beside it",
          r.stderr.count("check-sdlc-tie:") == 1
          and "Not a valid object name" in r.stderr.split("check-sdlc-tie:")[1],
          "one guard line, carrying git's message", r)
    # A HEAD that does not CONTAIN the ref is not a change: every commit the ref
    # has and HEAD has not reads backwards, so a branch that committed nothing
    # of its own was refused with a T3 naming a file it never opened.
    r = run_case({SPEC: DECL, "scripts/a.py": CODE,
                  "scripts/a-test.py": "#!/usr/bin/env python3\n"},
                 {}, args=("--against", "ahead"), legacy=["scripts/a.py"],
                 commits=[{"scripts/a-test.py": SUITE}], branch_at_head="ahead",
                 back_to="HEAD~1")
    check("--against a ref HEAD does not contain permits loudly, rather than "
          "refusing a branch for a commit it never made",
          r.returncode == 0 and "does not contain" in r.stderr
          and "T3\t" not in r.stderr, "exit 0 and PERMITTING, no T3", r)

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

    r = run_case({SPEC: DECL}, {}, args=("--staged", "--against", "HEAD"))
    check("--staged and --against are exclusive, and saying both is refused "
          "rather than one being dropped",
          r.returncode != 0 and "not allowed with" in r.stderr,
          "a non-zero exit naming the conflict", r)

    # A SHALLOW clone answers every ancestry question no, because HEAD's parents
    # are grafted away. Collapsed with a real "does not contain" this made the
    # guard permit on every CI run while its log read like a verdict, so the two
    # are told apart by name. `file://` is what forces a true shallow clone: a
    # plain path copies the whole object store and the depth marker means
    # nothing.
    with tempfile.TemporaryDirectory() as d:
        up = Path(d) / "up"
        up.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(up)], check=True)
        commit(up, {SPEC: DECL})
        subprocess.run(["git", "-C", str(up), "checkout", "-qb", "pr"], check=True)
        commit(up, {"scripts/a.py": CODE})
        for depth, name, want in ((["--depth=1"], "shallow", "SHALLOW"),
                                  ([], "full", "T1")):
            wd = Path(d) / name
            subprocess.run(["git", "clone", "-q", *depth, "--branch", "pr",
                            f"file://{up}", str(wd)], check=True)
            subprocess.run(["git", "-C", str(wd), "fetch", "-q", "--no-tags", *depth,
                            "origin", "+refs/heads/main:refs/remotes/origin/main"],
                           check=True)
            allow = Path(d) / f"legacy-{name}.txt"
            allow.write_text("")
            r = subprocess.run([sys.executable, str(GUARD), "--against",
                                "origin/main", "--legacy", str(allow)],
                               cwd=wd, capture_output=True, text=True)
            if want == "SHALLOW":
                check("--against in a shallow clone names the clone, not a "
                      "verdict about the branch",
                      r.returncode == 0 and "SHALLOW" in r.stderr
                      and "does not contain" not in r.stderr,
                      "exit 0 and PERMITTING naming the shallow clone", r)
            else:
                check("--against in the same clone at full depth judges the "
                      "change, which is what makes the shallow case a defect",
                      r.returncode == 1 and "T1\t" in r.stderr,
                      "T1 on stderr, exit 1", r)

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
