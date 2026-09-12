#!/usr/bin/env python3
# witnesses: S1_FullChain, TreeStaysTied_Bites, S4_CodeRenameBreak
# witnesses: S4a_TiedCodeRename, S4b_ScenarioRenameBreak
# witnesses: S4c_TestRenameBreak, WitnessesResolve_Bites
# witnesses: S4e_ScenarioRenameWithItsTests
# witnesses: FeaturelessKeeps_Bites, DebtNeverGrows_Bites
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
`TreeStaysTied_Bites` is T1, `WitnessesResolve_Bites`
in checks.als is T6, `FeaturelessKeeps_Bites` is T8, and
`DebtNeverGrows_Bites` is T4 over a list the commit grows. The `# witnesses:` lines
above are what tie this suite to them, and are themselves the form under test.

EVERY CASE PASSES `--legacy`, with an empty list unless it is about the
allow-list. The built-in `LEGACY` names this repository's own untied paths, and
a fixture tree holds none of them, so a case that let the default stand would
be judging 22 spent lines rather than the shape it means to. The one case that
DOES let it stand is named for exactly that reading; the cases about the list
growing carry their own copy of the guard, whose `LEGACY` is theirs.

A mutation that deletes one branch of the guard fails the case named for it;
the PR that added this suite ran that sweep and its REPORT quotes the result.
"""
import importlib.machinery
import importlib.util
import json
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

SPEC = "spec/commands.snapshot.json"


def snap(*rows):
    """A command snapshot, the one place the guard reads a scenario name. A
    row is a name (a `run` in one module), a (kind, name) pair, or a whole
    [module, kind, name] row."""
    full = [["x/checks.als", "run", r] if isinstance(r, str)
            else ["x/checks.als", *r] if len(r) == 2 else list(r) for r in rows]
    return json.dumps({"commands": full}) + "\n"


DECL = snap("S1_FullChain")
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
     TIED, {SPEC: snap("S1_Other")}, "T3"),
    ("T3 the `# witnesses:` line dropped from the suite",
     TIED, {"scripts/a-test.py": "#!/usr/bin/env python3\n"}, "T3"),
    ("T3 the `# witnesses:` line left with a name spec/ no longer declares",
     TIED, {"scripts/a-test.py": "# witnesses: S1_Other\n"}, "T3"),
    ("T3 the snapshot deleted, so no scenario is listed",
     TIED, {SPEC: None}, "T3"),
    ("T3 a command a model still declares, dropped from the snapshot: the "
     "snapshot is what is read, not the model",
     {**TIED, "spec/x/checks.als": "run S1_FullChain for 3 expect 1\n"},
     {SPEC: snap("S1_Other")}, "T3"),
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
     TIED, {SPEC: snap("S1_FullChain", ("check", "Z"))}, None),
    ("allow a command the snapshot lists though no model under spec/ declares "
     "it: the snapshot is what is read, and CI compares it to the models",
     {"README.md": "r\n"}, TIED, None),
    ("allow a commit touching neither spec, suite nor code path",
     TIED, {"README.md": "r\n"}, None),
    ("allow a suite in scripts/ tying a code path in a skill's scripts/",
     {SPEC: DECL},
     {".claude/skills/s/scripts/a.sh": "#!/bin/sh\n", "scripts/a-test.py": SUITE}, None),
    ("allow a code path tied through a `check`, not only a `run`",
     {SPEC: snap(("check", "Held"))},
     {"scripts/a.py": CODE, "scripts/a-test.py": "# witnesses: Held\n"}, None),
    ("allow a file under scripts/fixtures/, which is data",
     {SPEC: DECL}, {"scripts/fixtures/a.py": CODE}, None),
    ("allow a file nested below scripts/, which is not a code path",
     {SPEC: DECL}, {"scripts/sub/a.py": CODE}, None),
    ("allow a scripts/ file with no language extension, which R6 refuses instead",
     {SPEC: DECL}, {"scripts/a": CODE}, None),
    ("allow a scenario renamed with its suite rewritten",
     TIED, {SPEC: snap("S1_Other"),
            "scripts/a-test.py": "# witnesses: S1_Other\n"}, None),
    ("allow a declaration written with slack whitespace around every part",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "#   witnesses:   S1_FullChain  \n"}, None),
    ("allow a declaration split over two `# witnesses:` lines, both live",
     {SPEC: snap("S1_FullChain", "S1_Other")},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": "# witnesses: S1_FullChain\n# witnesses: S1_Other\n"}, None),
    ("allow a suite holding a byte that is not UTF-8 beside its declaration",
     {SPEC: DECL},
     {"scripts/a.py": CODE,
      "scripts/a-test.py": b"# witnesses: S1_FullChain\n# \xff\n"}, None),
    ("allow a snapshot holding a byte that is not UTF-8",
     {}, {SPEC: b'{"why": "\xff", "commands": [["x/checks.als", "run", "S1_FullChain"]]}\n',
          "scripts/a.py": CODE, "scripts/a-test.py": SUITE}, None),
]

# ---- T6: a declared name that resolves to no scenario. Each of these must
# come back with T6 AND NOTHING ELSE, because the gap it closes is one live name
# covering the rest: the code path is tied throughout, so a T1 or a T3 beside
# the T6 would mean the reading lost the live name -- a reader keeping one
# `# witnesses:` line of two, say -- and not that it found the dead one.
TWO = snap("S1_FullChain", "S1_Other")
BOTH = "# witnesses: S1_FullChain, S1_Other\n"
DEBT = {SPEC: DECL, "scripts/a.py": CODE,
        "scripts/a-test.py": "# witnesses: S1_FullChain, S9_Nowhere\n"}
T6_CASES = [
    ("T6 WitnessesResolve_Bites: a scenario renamed while the suite's other "
     "name still ties it, bd2143d's shape",
     {SPEC: TWO, "scripts/a.py": CODE, "scripts/a-test.py": BOTH},
     {SPEC: snap("S1_FullChain", "S1_Renamed")}),
    ("T6 a module's rows dropped from the snapshot while another module's row "
     "still lists the suite's other name",
     {SPEC: snap("S1_FullChain", ("y/checks.als", "check", "S1_Other")),
      "scripts/a.py": CODE, "scripts/a-test.py": BOTH},
     {SPEC: DECL}),
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

# ---- T6 and T7 over an html form under spec/, the model's `Html`: its
# `data-refines` names are read as a suite's `# witnesses:` names are, against
# the commands of the form's own entity -- `x`, the module `snap` gives a row.
FORM = "spec/x/view.html"


def form(names, attrs="data-scenario"):
    return f'<section {attrs} data-refines="{names}">\n<p>drawn</p>\n</section>\n'


HTML_CASES = [
    ("allow an html form refining a witnessed scenario of its own entity",
     TIED, {FORM: form("S1_FullChain")}, None),
    ("allow data-refines in single quotes",
     TIED, {FORM: "<section data-scenario data-refines='S1_FullChain'></section>\n"}, None),
    ("T7 an html form with no data-scenario section",
     TIED, {FORM: "<section><p>S1_FullChain</p></section>\n"}, "T7"),
    ("T7 a data-refines on a section without data-scenario declares nothing",
     TIED, {FORM: form("S1_FullChain", attrs="class=x")}, "T7"),
    ("T7 data-scenario-id is not data-scenario",
     TIED, {FORM: form("S1_FullChain", attrs="data-scenario-id=k")}, "T7"),
    ("T7 a data-refines inside another attribute's value is text",
     TIED, {FORM: "<section data-scenario title=\"see data-refines='S1_FullChain'\">"
                  "</section>\n"}, "T7"),
    ("allow data-scenario after data-refines, and in capitals",
     TIED, {FORM: '<SECTION DATA-REFINES="S1_FullChain" DATA-SCENARIO></SECTION>\n'},
     None),
    ("T7 an html form refining a scenario no suite witnesses",
     dict(TIED, **{SPEC: TWO}), {FORM: form("S1_Other")}, "T7"),
    ("T6 an html form refining a name the snapshot does not list",
     TIED, {FORM: form("S1_FullChain, S9_Nowhere")}, "T6"),
    ("T6 an html form refining a command of another entity",
     {SPEC: snap("S1_FullChain", ("y/checks.als", "run", "S2_Y")),
      "scripts/a.py": CODE,
      "scripts/a-test.py": "# witnesses: S1_FullChain, S2_Y\n"},
     {FORM: form("S1_FullChain, S2_Y")}, "T6"),
    # The change adds a command, so it is a feature change and T8 stands down:
    # what is left to refuse is the form's.
    ("T7 an html form this change never opened, untied by the change",
     {SPEC: DECL, "scripts/b-test.py": SUITE, FORM: form("S1_FullChain")},
     {SPEC: snap("S1_FullChain", "S2_New"), "scripts/b-test.py": "# nothing\n"},
     "T7"),
    ("allow an html form this change never opened, with a fault it already had",
     {SPEC: DECL, FORM: "<p>nothing declared</p>\n"},
     {"spec/x/checks.als": "open x/system\n"}, None),
]

# ---- T8: a change that adds no feature -- the command list as it was --
# shrinks what the suites witness. `FeaturelessKeeps_Bites` in checks.als.
T8_CASES = [
    ("T8 FeaturelessKeeps_Bites: one live name of two dropped, the command list "
     "as it was, the code path still tied through the other",
     {SPEC: TWO, "scripts/a.py": CODE, "scripts/a-test.py": BOTH},
     {"scripts/a-test.py": SUITE}, "T8"),
    ("T8 a script deleted with its suite, the scenario it alone witnessed left",
     TIED, {"scripts/a.py": None, "scripts/a-test.py": None}, "T8"),
    ("allow a name dropped from one suite while another still declares it",
     {SPEC: TWO, "scripts/a.py": CODE, "scripts/a-test.py": BOTH,
      "scripts/b.py": CODE, "scripts/b-test.py": "# witnesses: S1_Other\n"},
     {"scripts/a-test.py": SUITE}, None),
    ("allow a name dropped in a commit that adds a command: a feature change, "
     "which T8 does not read",
     {SPEC: TWO, "scripts/a.py": CODE, "scripts/a-test.py": BOTH},
     {SPEC: snap("S1_FullChain", "S1_Other", "S2_New"), "scripts/a-test.py": SUITE},
     None),
    ("allow a suite renamed with its code path, declaring what it declared",
     TIED, {"scripts/a.py": None, "scripts/b.py": CODE,
            "scripts/a-test.py": None, "scripts/b-test.py": SUITE}, None),
    ("allow T6's remedy: a dead name dropped, the command list as it was -- a "
     "name no command carries was never witnessed",
     DEBT, {"scripts/a-test.py": SUITE}, None),
    ("T8 reads the command NAMES: a snapshot rewritten with the same names is "
     "no feature, and the name dropped beside it is refused",
     {SPEC: TWO, "scripts/a.py": CODE, "scripts/a-test.py": BOTH},
     {SPEC: snap(("check", "S1_FullChain"), "S1_Other"), "scripts/a-test.py": SUITE},
     "T8"),
]


def own_guard(entries):
    """This guard's text with `LEGACY` set to `entries`: a fixture tree that
    carries its own copy, as this repository does, so the list BEFORE the commit
    is a blob in the committed tree and the list after it is the copy the hook
    runs."""
    text = GUARD.read_text()
    head, _, rest = text.partition("LEGACY = (\n")
    _, _, tail = rest.partition("\n)\n")
    body = "".join(f'    "{e}",\n' for e in entries)
    return f"{head}LEGACY = (\n{body})\n{tail}"


def own_list_case(listed_before, listed_after, change=None, copy_before=None,
                  on_disk=None, copy_after=None):
    """An untied code path under a list the fixture tree carries itself, run
    the way the pre-commit runs it: the tree's own copy. The commit edits the
    path unless `change` says what it does instead; `copy_before` replaces the
    committed copy's whole text and `copy_after` the staged one's; `on_disk` is
    written after staging, unstaged."""
    sibling = GUARD.parent / "check-tree-shape.py"
    base = {SPEC: DECL, "scripts/a.py": CODE,
            "scripts/check-tree-shape.py": sibling.read_text(),
            "scripts/check-sdlc-tie-test.py": SUITE,
            "scripts/check-sdlc-tie.py": copy_before or own_guard(listed_before)}
    staged = {"scripts/a.py": CODE + "y\n"} if change is None else dict(change)
    staged["scripts/check-sdlc-tie.py"] = copy_after or own_guard(listed_after)
    return run_case(base, staged, on_disk=on_disk, legacy=None,
                    guard="scripts/check-sdlc-tie.py")


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
             back_to=None, guard=None):
    """One fixture repository, and the guard run over it.

    `legacy` is the allow-list, written to a file OUTSIDE the repository -- a
    file inside it would be a tracked path the guard then has to have an
    opinion about. `None` withholds the flag entirely, which is the only way
    the built-in `LEGACY` is reached. `commits` are further commits made after
    `before`, for the cases that need two commits to judge between;
    `branch_at_head` names the last of them and `back_to` then checks an earlier
    one out, which is how a HEAD that does not CONTAIN the ref is built.
    `guard` runs the fixture's own copy at that path instead of this one."""
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
        script = root / guard if guard else GUARD
        return subprocess.run([sys.executable, str(script), *args], cwd=root / cwd,
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

    for name, before, after, code in HTML_CASES:
        r = run_case(before, after)
        ok, want = judge(r, code)
        codes = {line.split("\t", 1)[0] for line in r.stderr.splitlines() if "\t" in line}
        check(name, ok and codes <= {code}, want + ", and no other code", r)

    for name, before, after, code in T8_CASES:
        r = run_case(before, after)
        ok, want = judge(r, code)
        codes = {line.split("\t", 1)[0] for line in r.stderr.splitlines() if "\t" in line}
        check(name, ok and codes <= {code}, want + ", and no other code", r)
    r = run_case(*T8_CASES[0][1:3])
    line = next((ln for ln in r.stderr.splitlines() if ln.startswith("T8\t")), "")
    check("T8's line names the suite that declared it and the name it lost",
          line.startswith("T8\tscripts/a-test.py\t") and "`S1_Other`" in line,
          "one T8 line naming scripts/a-test.py and `S1_Other`", r)
    r = run_case(TIED, {"README.md": "r\n"})
    check("the reading says T8 read the witnessed scenarios",
          "T8 read 1 witnessed scenario(s) before and 1 after" in r.stdout,
          "the T8 clause with both counts", r)
    r = run_case(TIED, {SPEC: snap("S1_FullChain", "S2_New")})
    check("the reading says T8 stood down when the command names changed",
          "T8 stood down" in r.stdout, "the T8 stand-down clause", r)

    # ---- the list before the commit, read from the tree that holds it.
    r = own_list_case([], ["scripts/a.py"])
    ok, want = judge(r, "T4")
    check("T4 DebtNeverGrows_Bites: a code path the commit touches untied, "
          "licensed by a line the same commit adds: the list does not grow",
          ok, want, r)
    r = own_list_case(["scripts/a.py"], ["scripts/a.py"])
    ok, want = judge(r, None)
    check("allow a code path licensed by a line the list held before the commit",
          ok, want, r)
    r = own_list_case(["scripts/a.py"], [])
    ok, want = judge(r, "T4")
    check("T4 a line dropped while the path it licensed is touched and untied",
          ok, want, r)
    r = own_list_case([], ["scripts/a.py"], change={"README.md": "r\n"})
    ok, want = judge(r, "T4")
    check("T4 a line added for an untied path the commit never touches: the "
          "list does not grow anywhere", ok and "gains this line" in r.stderr,
          want + ", naming the line gained", r)
    r = own_list_case(["scripts/a.py"], ["scripts/b.py"],
                      change={"scripts/a.py": None, "scripts/b.py": CODE})
    ok, want = judge(r, None)
    check("allow a line moved with the file it names, in the same commit",
          ok, want, r)
    r = own_list_case(["scripts/a.py"], ["scripts/a.py"],
                      change={"scripts/a.py": None, "scripts/b.py": CODE})
    ok, want = judge(r, "T4")
    check("T4 a listed file renamed with its line left at the old name: no "
          "later commit could move the line", ok and "names only the old path"
          in r.stderr, want + ", naming the line left behind", r)
    # The list after is the judged tree's, not the copy on disk.
    r = own_list_case([], [], change={"README.md": "r\n"},
                      on_disk={"scripts/check-sdlc-tie.py": own_guard(["scripts/a.py"])})
    ok, want = judge(r, None)
    check("allow a commit while a line sits unstaged in the copy on disk: the "
          "index does not carry it", ok and "read from the index's" in r.stdout,
          want + ", the list after read from the index", r)
    r = own_list_case([], ["scripts/a.py"], change={"README.md": "r\n"},
                      on_disk={"scripts/check-sdlc-tie.py": own_guard([])})
    ok, want = judge(r, "T4")
    check("T4 a line the index gains, reverted on disk only", ok, want, r)
    # A list before that cannot be read is not a licence to skip the commit:
    # the running list stands for it, the reading says why, and T1 still bites.
    added = {"scripts/b.py": CODE}
    DEEP = own_guard([]) + "\nX = " + "-" * 200000 + "1\n"   # MemoryError at the parse
    LONG = own_guard([]) + "\nX = a" + ".b" * 300000 + "\n"  # RecursionError at the parse
    for name, copy, why in (
            ("does not parse", "#!/bin/sh\necho not python\n", "does not parse"),
            ("is no literal", own_guard([]).replace("LEGACY = (\n", "LEGACY = tuple((\n")
             .replace("\n)\n", "\n))\n", 1), "is no literal"),
            *((f"assigns {v}", own_guard([]) + f"\nLEGACY = {v}\n",
               "is no sequence of paths")
              for v in ("None", "0", '(["x"],)', '"scripts/a.py"')),
            ("assigns an unhashable set", own_guard([]) + '\nLEGACY = {["x"]}\n',
             "is no literal (TypeError"),
            ("nests too deep to parse", DEEP, "does not parse"),
            ("chains too long to parse", LONG, "does not parse")):
        r = own_list_case([], [], change=added, copy_before=copy)
        ok, want = judge(r, "T1")
        check(f"a list before that {name} is named in the reading, and the "
              f"commit is still judged", ok and why in r.stdout
              and "PERMITTING" not in r.stderr, want + f", `{why}` in the reading", r)
    for name, copy in (("nests too deep", DEEP), ("chains too long", LONG)):
        r = own_list_case([], [], change=added, copy_after=copy,
                          on_disk={"scripts/check-sdlc-tie.py": own_guard([])})
        ok, want = judge(r, "T1")
        check(f"a list after that {name} to parse is named in the reading, "
              f"and the commit is still judged", ok and "does not parse" in
              r.stdout and "PERMITTING" not in r.stderr, want + ", `does not "
              "parse` in the reading", r)
    twice = own_guard([]) + '\nLEGACY = ("scripts/a.py",)\n'
    r = own_list_case(None, ["scripts/a.py"], copy_before=twice)
    ok, want = judge(r, None)
    check("a list before assigned twice is read at its last assignment, as "
          "Python keeps it", ok, want, r)
    annotated = own_guard(["scripts/a.py"]).replace("LEGACY = (", "LEGACY: tuple = (", 1)
    r = own_list_case(None, ["scripts/a.py"], copy_before=annotated)
    check("an annotated list before is read, not taken for no list",
          judge(r, None)[0] and "the list before read from HEAD's" in r.stdout,
          "0 finding(s) and the list-before clause naming HEAD", r)

    # An unopened form's old fault is counted in the reading, not dropped.
    r = run_case({SPEC: DECL, FORM: "<p>nothing declared</p>\n"}, {"README.md": "x\n"})
    check("an unopened form's old fault is counted in the reading",
          judge(r, None)[0] and "1 fault(s) left in html forms" in r.stdout,
          "0 finding(s) and `1 fault(s) left in html forms` in the reading", r)

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
    check("without --staged, the snapshot deleted on disk and not staged is T3",
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
    ok, want = judge(r, "T4")
    check("T4 a rename the line's OLD name alone names: the line moves in the "
          "same commit, since the commit after would be a line the list gains",
          ok, want, r)
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
          ok and f"(LEGACY, the running copy's: the index holds no "
          f"scripts/check-sdlc-tie.py; {len(LEGACY)} entr(ies), {len(LEGACY)} "
          f"naming no code path here; LEGACY stands for the list before too"
          in r.stdout,
          "0 finding(s) and a reading naming LEGACY, its size, its absences "
          "and which list stood for the tree before", r)
    r = own_list_case(["scripts/a.py"], ["scripts/a.py"])
    check("the reading names the tree the list before was read from",
          "the list before read from HEAD's scripts/check-sdlc-tie.py, 1 entr(ies)"
          in r.stdout, "the list-before clause naming HEAD and its size", r)

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
    want = ("read 1 scenario name(s), 1 suite(s), 0 html form(s), 1 code path(s) "
            "from the index under")
    check("the reading names what it counted and where", want in r.stdout, want, r)

    print(f"{ran} case(s) ran, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
