#!/usr/bin/env python3
"""Refuse a commit whose scenario, test and code path stop tying by name.

The reader of `tieDiscipline` in spec/sdlc/scenarios.als: after a commit that
writes or renames an artifact the tree is tied (`treeTied` in
spec/sdlc/system.als), which is to say every code path walks back to a
scenario through the test that drives it. The model says what a tie is; this
says how one is read off this tree, and judges the commit by what it CHANGES
about the reading rather than by the tree's whole debt.

THE THREE NAMES, as the tree carries them today

  scenario   the name of a `run` or `check` command declared in any .als
             under spec/. The declaration is read with alloy-check.py's
             `DECL`, imported, so this is not a second reader of what a
             command is.
  test       a suite: a `<stem>-test.<ext>` sitting directly in a scripts/
             directory -- the top-level one, or a skill's. Its TEXT carries a
             scenario's name as a whole word, and its NAME carries the code
             path's stem. That is the model's `names` read twice from one
             file: `t -> s` and `t -> k`, so `tie` holds `s -> t -> k` and
             `tied[k]` asks whether some suite named after k names some
             scenario that exists.
  code path  a script by check-tree-shape.py's R6 -- `.py` or `.sh`, sitting
             directly in one of those scripts/ directories -- whose stem does
             not end in `-test`. What R6 refuses or skips (no extension, a
             nested path, scripts/fixtures/) is not a code path here either.

The suite may sit in a different scripts/ directory from its code path --
scripts/acquire-repo-test.py drives a skill's acquire-repo.sh -- so the pair is
made on the stem alone, tree-wide. The stem pairs on the name and not the
extension, since a Python suite drives a shell script.

WHAT IT JUDGES

The commit's change, read as the model's events. Each code path in the tree
after the commit is either tied or not, and the same is asked of the tree
before it; a code path the commit renamed keeps its identity across the two
readings where git pairs the rename (`-M`), and a rewrite git cannot pair is a
new path, judged as one. A path that was in the tree before but not a code
path -- nested, extensionless, under fixtures/ -- ENTERS the code set when it
is moved into a scripts/ slot, and is judged as new. Three shapes are refused,
one per cause:

  T1  a code path the commit ADDS is untied: no suite carries its stem, or
      the suite names no scenario. The write that `TreeStaysTied_Bites`
      exhibits.
  T2  a code path that was tied has no suite after the commit: the suite was
      deleted or renamed, or the code path was renamed and the suite was not.
      `S4_RenameBreaksTheTie`; the rename that passes is
      `S4a_RenameKeepsItsNamers`, whose suite is rewritten in the same commit.
  T3  a code path that was tied still has its suite, and the suite names no
      scenario any more: the scenario was renamed or deleted, or the line
      naming it was dropped. The same rename read at the scenario's end.

A code path that was untied BEFORE the commit and is untied after it is
reported and not refused. The model wants the whole tree tied; this tree is
not, and a check that refused every edit to alloy-check.py until it had a
suite naming a scenario would be a wall across the repair. So the debt is
printed by name on every run, and the commit that first ties one of them is
the commit that puts it under T2 and T3 from then on.

THE SKIP, and why nothing declares one here

`maySkip[c, s]` in spec/sdlc/system.als licenses a skip when the kind's
profile allows the stage AND the stage's `criterion` holds: for Test and for
Code that is "the change has written no test and no code path". A change
that writes a code path therefore has no skip to declare to this check --
the criterion is false by the fact this check reads -- and a change that
writes none is judged on nothing here, which IS its skip of Test and Code,
declared by the absence and by no syntax. Whether that absence was licensed
is `landDiscipline`'s, read where the merge is gated, and not the commit's.

WHAT IT DOES NOT CATCH

A suite naming a scenario it does not exercise is a tie by name and passes:
the check reads names, never verdicts, and the solver stays the one reader of
a verdict. A code path whose suite names any scenario at all is tied; which
scenario is the author's. And a scenario with no test is not refused: the tie
is read from the code path up, as the model says, because reading it down
would refuse every scenario spec/campaign holds.

READING VERSUS VERDICT

Every run prints what it read -- how many scenarios, suites and code paths,
from which tree, under which root, and how many paths the change renamed -- so
a clean run and a run that examined nothing do not read the same. Every
listing and read is under the repository root, so a run from a subdirectory
reads the same tree as one from the root. Whether a code path is new is
read from the tree before the commit and never from the diff: an intent-to-add
entry sits in the index and in no `diff --cached`. A finding is one line on
stderr: the code, the path, and what was found; the exit status is 1. A
failure of the reading itself -- git absent, a tree it cannot list, an
exception nothing here foresaw -- PERMITS, exits 0, and says so on stderr with
the exception's name: a guard that could not run has judged nothing, and a
wall across every commit costs more than one unjudged one that names itself.

Usage: scripts/check-sdlc-tie.py [--staged]
  --staged   read the index and judge it against HEAD (the pre-commit form)
  otherwise  read the working tree and judge it against HEAD
"""
import importlib.machinery
import importlib.util
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

CODE_SUFFIXES = (".py", ".sh")
SKILL_SCRIPTS = re.compile(r"^\.claude/skills/[^/]+/scripts/[^/]+$")
TOP_SCRIPTS = re.compile(r"^scripts/[^/]+$")


def load_decl():
    """alloy-check.py's `DECL`: the one reader of what a command declaration
    looks like. Imported by path because these are scripts, not a package."""
    src = Path(__file__).resolve().parent / "alloy-check.py"
    spec = importlib.util.spec_from_loader(
        "alloycheck", importlib.machinery.SourceFileLoader("alloycheck", str(src)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DECL


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=True).stdout


ROOT = None          # set once by judge(); every listing and read is root-relative


def git_root(*args):
    return git("-C", ROOT, *args)


def in_scripts_dir(path):
    return bool(TOP_SCRIPTS.match(path) or SKILL_SCRIPTS.match(path))


def stem(path):
    return PurePosixPath(path).stem


class Tree:
    """One reading of one tree: HEAD, the index, or the working tree."""

    def __init__(self, label, paths, reader, decl):
        self.label = label
        self.paths = paths
        self.read = reader
        self.decl = decl
        scripts = [p for p in paths if in_scripts_dir(p)]
        self.suites = [p for p in scripts if stem(p).endswith("-test")]
        self.code = [p for p in scripts if not stem(p).endswith("-test")
                     and p.endswith(CODE_SUFFIXES)]
        self.scenarios = set()
        for p in paths:
            if p.startswith("spec/") and p.endswith(".als"):
                for line in self.read(p).splitlines():
                    m = decl.match(line)
                    if m:
                        self.scenarios.add(m.group(2))
        self.named = (re.compile(r"\b(?:" + "|".join(
            re.escape(s) for s in sorted(self.scenarios)) + r")\b")
            if self.scenarios else None)
        self._names = {}

    def suites_of(self, code_path):
        want = stem(code_path) + "-test"
        return [s for s in self.suites if stem(s) == want]

    def names_a_scenario(self, suite):
        if suite not in self._names:
            self._names[suite] = bool(self.named and self.named.search(self.read(suite)))
        return self._names[suite]

    def tied(self, code_path):
        return any(self.names_a_scenario(s) for s in self.suites_of(code_path))


def head_tree(decl):
    try:
        paths = git_root("ls-tree", "-r", "--name-only", "HEAD").splitlines()
    except subprocess.CalledProcessError:
        return Tree("HEAD (no commit yet)", [], lambda p: "", decl)
    return Tree("HEAD", paths, lambda p: git_root("show", f"HEAD:{p}"), decl)


def after_tree(staged, decl):
    paths = git_root("ls-files").splitlines()
    if staged:
        return Tree("the index", paths, lambda p: git_root("show", f":{p}"), decl)
    # The working tree is what is ON DISK: a tracked file deleted there and
    # not yet staged is gone from this reading, so a suite removed with `rm`
    # is T2 and not a FileNotFoundError the last resort permits.
    paths = [p for p in paths if (Path(ROOT) / p).is_file()]
    return Tree("the working tree", paths,
                lambda p: (Path(ROOT) / p).read_text(errors="replace"), decl)


def renames(staged):
    """{after-path: before-path} for every rename in the change, so a code
    path keeps its identity across the two readings. Whether a path is NEW
    is not read from here but from the tree before: an intent-to-add entry
    is in the index and absent from `diff --cached`, and a guard that asked
    the diff would have read it as an old path."""
    args = ["diff", "--cached", "--name-status", "-M"] if staged \
        else ["diff", "HEAD", "--name-status", "-M"]
    try:
        out = git_root(*args)
    except subprocess.CalledProcessError:
        return {}                                # no HEAD: nothing to rename from
    moved = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if parts[0].startswith("R"):
            moved[parts[2]] = parts[1]
    return moved


def judge(staged):
    global ROOT
    # Root first, and every git call and disk read under it: run from a
    # subdirectory, a bare `git ls-files` lists that directory alone, which
    # reads as a tree with no scripts/ and passes.
    ROOT = root = git("rev-parse", "--show-toplevel").strip()
    decl = load_decl()
    before = head_tree(decl)
    after = after_tree(staged, decl)
    moved = renames(staged)
    print(f"check-sdlc-tie: read {len(after.scenarios)} scenario name(s), "
          f"{len(after.suites)} suite(s), {len(after.code)} code path(s) from "
          f"{after.label} under {root}; each judged against {before.label}, "
          f"{len(moved)} path(s) renamed in between")
    findings, legacy = [], []
    for k in after.code:
        if after.tied(k):
            continue
        was = moved.get(k, k)                    # its name in the tree before
        if was not in before.code:
            why = ("no suite carries its stem" if not after.suites_of(k)
                   else "its suite names no scenario declared under spec/")
            findings.append(("T1", k, f"added untied: {why}. A code path is "
                                      f"tied by a `{stem(k)}-test` suite whose "
                                      f"text names a `run` or `check` under spec/"))
            continue
        if was in before.code and before.tied(was):
            if not after.suites_of(k):
                gone = ", ".join(before.suites_of(was))
                findings.append(("T2", k, f"was tied through {gone}; after this "
                                          f"commit no suite carries its stem. "
                                          f"Rename or restore the suite with it"))
            else:
                findings.append(("T3", k, f"was tied; its suite "
                                          f"{', '.join(after.suites_of(k))} "
                                          f"names no scenario after this commit. "
                                          f"Rewrite the name it carries"))
            continue
        legacy.append(k)
    for code, path, what in findings:
        print(f"{code}\t{path}\t{what}", file=sys.stderr)
    print(f"check-sdlc-tie: {len(findings)} finding(s); {len(legacy)} code path(s) "
          f"untied before this commit and left so"
          + (f": {', '.join(legacy)}" if legacy else ""))
    return 1 if findings else 0


def main():
    try:
        return judge("--staged" in sys.argv)
    except Exception as e:                       # noqa: BLE001 -- the last resort
        print(f"check-sdlc-tie: PERMITTING -- the reading itself failed "
              f"({e.__class__.__name__}: {e}); nothing was judged", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
