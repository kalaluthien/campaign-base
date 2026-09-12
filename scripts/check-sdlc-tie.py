#!/usr/bin/env python3
"""Refuse a commit whose scenario, test and code path stop tying by name.

The reader of `tieDiscipline` in spec/sdlc/checks.als: after a commit that
writes or renames an artifact the tree is tied (`everyCodeHasScenario` in
spec/sdlc/system.als), which is to say every code path the allow-list does not
exempt walks back to a scenario through the test that drives it, and every
name a test declares is a scenario (`everyWitnessExists`); and of what
`keepDiscipline` makes true, that a change adding no feature leaves every
witnessed scenario witnessed (`FeaturelessKeeps`, T8). The model says what a tie is; this
says how one is read off this tree, and judges the commit by what it CHANGES
about the reading rather than by the tree's whole debt.

THE THREE NAMES, as the tree carries them today

  scenario   the name of a `run` or `check` command, as
             spec/commands.snapshot.json lists it. The snapshot is
             alloy-check.py's statement of every command under spec/, and CI
             compares it to the models (`--commands spec`), so this reads
             that statement and parses no model: it is not a second reader of
             what a command is. A tree with no snapshot lists no scenario, and
             a command added to a model is a scenario here once the snapshot
             is regenerated in the same commit.
  test       a suite: a `<stem>-test.<ext>` sitting directly in a scripts/
             directory -- the top-level one, or a skill's. It DECLARES the
             scenarios it witnesses on a `# witnesses: <Name>[, <Name>...]`
             line, and its NAME carries the code path's stem. That is the
             model's two relations read off one file: `t -> s` from
             `witnesses`, `t -> k` from `drives`, so `tie` holds `s -> t -> k`
             and `tied[k]` asks whether some suite named after k declares some
             scenario that exists.
  html form  an `.html` under spec/, which check-tree-shape.py's R8 admits
             only beside an entity's `system.als` and `checks.als`: a
             scenario drawn for a reader, the model's `Html`. It DECLARES the
             commands it draws on a `<section data-scenario
             data-refines="<Name>[, <Name>...]">` tag -- `h -> s` in the
             model's `refines`, read the way a suite's `# witnesses:` line is
             -- and a name counts only as a command of the form's own entity,
             a snapshot row whose module sits in the `.html`'s directory.
  code path  a script by check-tree-shape.py's R6 -- `.py` or `.sh`, sitting
             directly in a scripts/ directory -- whose stem does not end in
             `-test`. R6's membership is IMPORTED (`in_scripts_dir`), so what
             R6 skips (a nested path, scripts/fixtures/, an assets/ template)
             is not a code path here either, and what it refuses (no
             extension) is not one until it has one.

The suite may sit in a different scripts/ directory from its code path, so
the pair is made on the stem alone, tree-wide. The stem pairs on the name and not the
extension, since a Python suite drives a shell script.

A DECLARATION, NOT A MENTION. Until #268 the tie was any whole-word occurrence
of a declared command name in the suite's text, which is forgeable -- a comment
ties a code path it never exercises -- and accidental, since a short name
(`Sanity`, `NoOrphan`) ties whatever prose happens to spell it. The
`# witnesses:` line is a form that has to be written on purpose, matched
EXACTLY against the declared names, so what ties is something the author
declared and not something the text happens to contain. AGENTS.md's "prefer
parsing formal syntax over prose"; the model's half is `witnesses` being its
own relation from Test to Spec.

WHAT IT JUDGES

The commit's change, read as the model's events. Each code path in the tree
after the commit is either tied or not, and the same is asked of the tree
before it; a code path the commit renamed keeps its identity across the two
readings where git pairs the rename (`-M`), and a rewrite git cannot pair is a
new path, judged as one. A path that was in the tree before but not a code
path -- nested, extensionless, under fixtures/ -- ENTERS the code set when it
is moved into a scripts/ slot, and is judged as new. Eight shapes are refused,
one per cause; a suite whose only declared name is dead reads T1 or T3 and T6
together, the first saying what the code path lost and T6 which name did it,
and a suite dropping a scenario nothing else witnesses reads T8 beside them:

  T1  a code path the commit ADDS is untied: no suite carries its stem, or
      the suite declares no scenario. The write that `TreeStaysTied_Bites`
      exhibits.
  T2  a code path that was tied has no suite after the commit: the suite was
      deleted or renamed, or the code path was renamed and the suite was not.
      `S4_CodeRenameBreak` at the code path's end and
      `S4c_TestRenameBreak` at the suite's -- one relation,
      `drives`, broken by renaming either end; the rename that passes is
      `S4a_TiedCodeRename`, whose suite moves in the same commit.
  T3  a code path that was tied still has its suite, and the suite declares no
      scenario any more: the scenario was renamed or deleted, or the
      `# witnesses:` line was dropped. The same rename read at the scenario's
      end (`S4b_ScenarioRenameBreak`).
  T4  a code path THIS CHANGE TOUCHED that is untied both before and after it
      and that the allow-list below does not name: the debt grew where nothing
      here could see it, by a bypassed hook or a merge this never ran over. The
      touched scope is what separates this tree's debt from a tree the list is
      not about -- every fixture repository under scripts/*-test.py is a tree of
      copied guards with no suites, and unscoped this refused every commit any
      of them made. The same code refuses a LINE THE COMMIT ADDS to the list,
      wherever its path is, save a line moved with the file it names: the list
      only shrinks (`licenceNeverGrows`, `DebtNeverGrows_Bites`), so a line
      licenses only a path the list held before the commit as well as after.
      And it refuses a line the commit DROPS whose path is untied after it,
      touched or not: the line leaves with the tie, since a path off the list
      must be tied after every commit (`everyCodeHasScenario`), and unscoped
      this is no wall -- a fixture's list is a copy nothing edits.
  T5  an allow-list entry whose code path is TIED now. The licence is spent and
      the line comes out in the same commit. An entry naming no code path here
      is counted in the reading instead of refused: the path may have been
      deleted, or this may be a tree the list is not about -- which is what
      every fixture repository under scripts/*-test.py is, since each copies the
      guards by their real names, so refusing on it walled off every commit any
      of them made. A rename is licensed by the NEW name, the line moving with
      its file in the same commit; a rename that leaves the line at the old
      name is a T4, since no later commit could move it -- it would be a line
      the list gains.
  T6  a suite's `# witnesses:` line declares a name the snapshot does not
      list. One live name ties the code path, so T1 and T3 read the
      rest of the line not at all, and a scenario renamed away from a suite that
      declared two left the second name dead with nothing refusing it (bd2143d,
      `WitnessesResolve_Bites`). Scoped the way T4 is: in a suite this change
      touched every dead name is refused, and in one it never opened only a
      name that resolved before the change and does not after it; the dead
      names left in unopened suites are counted in the reading. An html
      form's `data-refines` names are read the same way, against the
      commands of its own entity.
  T7  an html form that refines no scenario, or refines one no suite's
      `# witnesses:` line declares. The form is a Spec artifact tied by
      name, so a view of nothing, or of a scenario nothing tests, is refused
      rather than kept as a second statement no check reads. Scoped as T6:
      in a form this change touched every such fault, in one it never opened
      only a fault the change introduced.
  T8  a scenario some suite's `# witnesses:` line declared before the commit
      and none declares after it, where the commit leaves the snapshot's
      command list as it was. That commit adds no feature, and a change that
      adds none keeps what is witnessed (`FeaturelessKeeps_Bites`): the model
      proves it from `keepDiscipline` and `rename`, and this reads it over the
      edit the model has no step for, a declaration rewritten or a suite
      deleted in place. A commit that changes the command list is a feature
      change and is not read here, where the model reads a rename by a change
      with no scenario of its own as that change's; deleting a script with its
      suite retires its scenario in the same commit.

THE ALLOW-LIST, AND WHY IT IS NOT A REPORT

`LEGACY` is what the model's `Licensed` names (spec/sdlc/system.als), and
`licenceNeverGrows` is the rule it is kept to: T1, T2 and T3 are judged before
the list is read, so a line licenses only a path that was untied before the
commit, and T4 reads the list twice -- the copies the tree before and the
tree judged hold, at `LEGACY_HOME` -- so a line licenses only what both name. Every other code path is to be tied, and a check that refused every
edit to alloy-check.py until it had a suite would be a wall across the
repair. So the debt is licensed by name in `LEGACY` -- derived from the tree
when #268 wrote it, the shape #237 gave R3 -- and the licence bites both ways:
T4 refuses a path the change touches that is untied and unlisted, T5 refuses a
line whose path is tied now. A list that only prints, which is what this printed
before #268, never shrinks and never refuses anything; one the tree is checked
against shrinks by one line per repair, and a path the change opens cannot slip
past it.

WHAT THE LIST CANNOT SAY is whether this is the tree it is about. A fixture
repository under scripts/*-test.py copies these guards by their real names with
no suites beside them, so every entry matches a path there and none is tied --
which is indistinguishable, from inside, from this repository having let its
whole debt rot. That is why neither refusal reads the tree at large: T4 reads
what the change touched, and an entry naming no code path here is a count in the
reading rather than a finding.

`--legacy <file>` substitutes a list, one path per line, `#` starting a
comment, on both sides of the change. It is how check-sdlc-tie-test.py
exercises T4 and T5 over a fixture tree, whose paths no built-in list could
name; the cases about the list growing carry their own copy of this guard
instead. A tree judged that holds no readable copy has the running list
stand for it, and a tree before that holds none -- a first commit, a
fixture -- has the list after; the reading says which was read.

THE SKIP, and why nothing declares one here

`maySkip[c, s]` in spec/sdlc/system.als licenses a skip when the kind's
profile allows the stage AND the stage's `criterion` holds: for Test and for
Code that is "the change has written no test and no code path". A change
that writes a code path therefore has no skip to declare to this check --
the criterion is false by the fact this check reads -- and a change that
writes none is judged on nothing here, which IS its skip of Test and Code,
declared by the absence and by no syntax. Whether that absence was licensed
is `landDiscipline`'s, which check-merge-review.py --land reads where the
merge is gated, and not the commit's.

WHAT IT DOES NOT CATCH

A suite declaring a scenario it does not exercise is a tie by name and passes:
the check reads names, never verdicts, and the solver stays the one reader of
a verdict. What the declaration buys is that the name was written on purpose,
not that it was earned. A code path whose suite declares any scenario at all is
tied; which scenario is the author's, though every name it declares must
resolve (T6). And a scenario with no test is not
refused: the tie is read from the code path up, as the model says, because
reading it down would refuse every scenario spec/campaign holds.

The line is read wherever it stands in a suite's text, a multi-line string
included, so a fixture that holds one is a declaration here: it can tie a code
path, and T6 refuses it when its name is dead, indented or not. Keep a
fixture's `# witnesses:` off any line whose first non-blank character is `#`,
as check-sdlc-tie-test.py does by writing it inside a quoted string.

READING VERSUS VERDICT

Every run prints what it read -- how many scenarios, suites and code paths,
from which tree, under which root, how many paths the change renamed, and how
long each tree took -- so a clean run and a run that examined nothing do not
read the same. Every listing and read is under the repository root, so a run
from a subdirectory reads the same tree as one from the root. Whether a code
path is new is read from the tree before the commit and never from the diff: an
intent-to-add entry sits in the index and in no `diff --cached`. A finding is
one line on stderr: the code, the path, and what was found; the exit status is
1. A failure of the reading itself -- git absent, a tree it cannot list, an
exception nothing here foresaw -- PERMITS, exits 0, and says so on stderr with
the exception's name: a guard that could not run has judged nothing, and a
wall across every commit costs more than one unjudged one that names itself.

BYTES AND PATHS. Every blob is decoded with `errors="replace"`, so one
non-UTF-8 byte in the snapshot or a suite is a replacement character in the text
this reads and not an exception the last resort turns into a permit. Every
listing is `-z`, so a non-ASCII path arrives raw rather than quoted by
`core.quotePath`, which git and CI both default on -- a quoted path matches no
suite and no code path, and would have left every set silently.

ONE READ PER TREE. A tree's blobs come back in one `git cat-file --batch` over
the oids its listing already gave, rather than one `git show` per file: at 20
suites and 40 modules across two trees that was 120 processes and 0.69 s on a
README-only commit, against 8 ms for the next tree guard.

Usage: scripts/check-sdlc-tie.py [--staged | --against <ref>] [--legacy <file>]
  --staged         read the index and judge it against HEAD (the pre-commit form)
  --against <ref>  read HEAD and judge it against <ref> (the CI form: the whole
                   of a pull request's change, which judging against HEAD on a
                   merge commit cannot see)
  otherwise        read the working tree and judge it against HEAD
  --legacy <file>  take the allow-list from <file> instead of `LEGACY`, before
                   and after the change alike
"""
import argparse
import ast
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

CODE_SUFFIXES = (".py", ".sh")

# WHERE THE SCENARIO NAMES ARE READ: the committed command snapshot, whose
# rows are [module, kind, name]. See the docstring's `scenario`.
SNAPSHOT = "spec/commands.snapshot.json"

# WHAT A SUITE DECLARES IT WITNESSES. One line, `#` because every suite this
# tree holds is Python or shell and both comment that way; the names after the
# colon are split on commas and matched EXACTLY against the listed commands,
# so `S1_FullChainX` is not `S1_FullChain` and no prose spelling either name
# ties anything. A suite may carry the line more than once and the names union.
WITNESSES = re.compile(r"^[ \t]*#[ \t]*witnesses:[ \t]*(.*)$")

# WHAT AN HTML FORM DECLARES IT REFINES: a `<section>` tag carrying
# `data-scenario` and `data-refines="<Name>[, <Name>...]"`, the names split on
# commas and matched exactly, as WITNESSES's are. A tag without `data-scenario`
# declares nothing, so a section that only mentions a name is prose. The tag's
# attributes are read one by one, name then value, so `data-scenario-id` is not
# `data-scenario` and a `data-refines` inside another attribute's value is text.
SECTION = re.compile(r"<section\b([^>]*)>", re.IGNORECASE)
ATTR = re.compile(r"""([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?""")


def attributes(text):
    """{lowercased name: value, or None for a bare attribute} of one tag."""
    found = {}
    for m in ATTR.finditer(text):
        value = next((v for v in m.groups()[1:] if v is not None), None)
        found.setdefault(m.group(1).lower(), value)
    return found


def html_form(path):
    return path.startswith("spec/") and path.endswith(".html")


# WHERE A TREE HOLDS ITS OWN ALLOW-LIST: this guard's `LEGACY`, read from the
# tree before the commit as well as from the tree judged. See the docstring's T4.
LEGACY_HOME = "scripts/check-sdlc-tie.py"


def listed(text):
    """(the `LEGACY` a copy of this guard assigns, "") -- or (None, why) where
    no list can be read off it. The LAST assignment is the one, as Python
    keeps it, and an annotated one counts. A copy that does not parse, or
    whose list is no literal sequence of paths, is a reading that could not be
    made: the caller lets another list stand for it and says so, rather than
    letting the raise permit the whole commit."""
    try:
        body = ast.parse(text).body
    except SyntaxError as e:
        return None, f"it does not parse (SyntaxError: {e.msg}, line {e.lineno})"
    except (MemoryError, RecursionError) as e:   # nesting past the parser's depth
        return None, f"it does not parse ({type(e).__name__}: {e})"
    value = None
    for node in body:
        targets = (node.targets if isinstance(node, ast.Assign) else
                   [node.target] if isinstance(node, ast.AnnAssign) and node.value
                   else [])
        if any(isinstance(t, ast.Name) and t.id == "LEGACY" for t in targets):
            value = node.value
    if value is None:
        return None, "it assigns no LEGACY"
    try:
        entries = ast.literal_eval(value)
    except (ValueError, TypeError, MemoryError, RecursionError) as e:
        return None, f"its LEGACY is no literal ({type(e).__name__}: {e})"
    if not (isinstance(entries, (tuple, list, set, frozenset))
            and all(isinstance(e, str) for e in entries)):
        return None, (f"its LEGACY is no sequence of paths (a "
                      f"{type(entries).__name__})")
    return set(entries), ""


def own_list(tree):
    """(the `LEGACY` a tree's own copy of this guard holds, "") -- or (None,
    why) where it holds none that can be read."""
    if LEGACY_HOME not in tree.texts:
        return None, f"{tree.label} holds no {LEGACY_HOME}"
    held, why = listed(tree.texts[LEGACY_HOME])
    return held, "" if held is not None else \
        f"{tree.label}'s {LEGACY_HOME} was not read, {why}"


# THE LEGACY ALLOW-LIST, the model's `Licensed`. Every code path this tree held
# untied when #268 wrote it, derived from the tree by running the guard over it
# -- the shape #237 gave
# R3, and for the same reason: a list the tree is CHECKED AGAINST shrinks by one
# line per repair, where a list that only printed never shrank. What each
# refusal actually reads is in the docstring's T4 and T5, and the two are
# narrower than a tree-wide reading on purpose: T4 refuses only a path THIS
# CHANGE TOUCHED that is untied and unlisted, and T5 refuses only a line whose
# path is TIED now -- a line naming no code path here is a count in the reading,
# because from inside a fixture tree that is indistinguishable from the list
# being about another repository.
#
# Each line left says why its path does not tie (sdlc-alloy#250): the model
# holds no scenario its suite drives, or no suite carries its stem. Neither is
# a declaration's to fix -- a `# witnesses:` line naming a scenario the suite
# does not drive is the forgery the declaration exists to prevent -- so a line
# goes when the model gains the scenario or the path gains a suite.
LEGACY = (
    # The model leaves the session name unmodelled on purpose
    # (spec/campaign/session/system.als), so there is no scenario to drive.
    ".claude/skills/assuming-role/scripts/campaign-name-session.py",
    # Its suite checks the table's shape, which the model does not state;
    # check-campaign-claim-test.py drives the verdicts the table decides.
    ".claude/skills/assuming-role/scripts/campaign-roles.py",
    # Its suite reads a directory's leftovers and drives no scenario over
    # `LocalOnly`, the set this script reads (R5b needs an agent's push).
    "scripts/campaign-local-work.py",
    # No model rule: what is installed and declared on this machine.
    "scripts/campaign-primitives.py",
    # Test tooling: a mutation runner over campaign-token-tally-test.py.
    "scripts/campaign-token-tally-mutations.py",
    # No model rule: token accounting over transcripts.
    "scripts/campaign-token-tally.py",
    # No model rule: a document's pointer at another resolving.
    "scripts/check-cross-references.py",
    # No model rule: one reader per rule a script owns.
    "scripts/check-rule-readers.py",
    # No model rule: R1-R9 are tree-layout rules the model does not state.
    "scripts/check-tree-shape.py",
    # No model rule: which recorded calls a replay corpus keeps.
    "scripts/guard-corpus.py",
    # The model states the verdict log, not the pairing read off it.
    "scripts/guard-precision.py",
    # No suite of its stem; install-hooks-test.py section 6 drives it
    # (`Cov_PushBase`).
    "scripts/push-campaign-branch.sh",
)


def load_sibling(name):
    """A sibling script as a module, by path, because these are scripts and
    not a package. One rule is read this way rather than restated:
    check-tree-shape.py's `in_scripts_dir`, R6's reading of a script's own
    directory."""
    src = Path(__file__).resolve().parent / name
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(src)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ROOT = None          # set once by judge(); every listing and read is root-relative


def git_bytes(*args, stdin=b""):
    """git's stdout as BYTES, so nothing is decoded before the caller knows
    what it is holding: a listing is paths, which are bytes on this platform,
    and a blob may hold one byte that is not UTF-8."""
    return subprocess.run(["git", *args], input=stdin,
                          capture_output=True, check=True).stdout


def git_root_bytes(*args, stdin=b""):
    return git_bytes("-C", ROOT, *args, stdin=stdin)


def stem(path):
    return PurePosixPath(path).stem


def read_blobs(oids):
    """{oid: text} for every oid, in ONE `git cat-file --batch`.

    The batch protocol is `<oid> <type> <size>\\n<content>\\n` per request. A
    header of fewer than three fields is skipped and the reader advances one
    line, which serves two ends: `<oid> missing` for an oid it cannot resolve --
    not reachable from here, since every oid came from this repository's own
    listing, but a path with no text rather than a raise if it ever were -- and
    RE-SYNCHRONISATION, since a size that does not land on the next header
    leaves the reader mid-stream and this is what walks it back to one. Every
    blob is decoded with `errors="replace"`: a
    non-UTF-8 byte in the snapshot or a suite becomes a replacement character in the
    text, where a strict decode raised and the last resort turned the raise
    into a permit."""
    oids = sorted(set(oids))
    if not oids:
        return {}
    out = git_root_bytes("cat-file", "--batch",
                         stdin=("\n".join(oids) + "\n").encode())
    blobs, i = {}, 0
    while i < len(out):
        end = out.find(b"\n", i)
        if end < 0:
            break
        head = out[i:end].split()
        if len(head) < 3:
            i = end + 1                      # `<oid> missing`
            continue
        oid, size = head[0].decode(), int(head[2])
        blobs[oid] = out[end + 1:end + 1 + size].decode("utf-8", "replace")
        i = end + 1 + size + 1
    return blobs


def wanted(paths, in_scripts_dir):
    """The paths whose TEXT is read: the snapshot, for the command names,
    every suite, for the `# witnesses:` lines, every html form, for its
    `data-refines`, and this guard's own copy, for the list it held. Nothing else's bytes are fetched, which is what keeps a
    tree to one listing and one batch."""
    return [p for p in paths
            if p in (SNAPSHOT, LEGACY_HOME) or html_form(p)
            or (in_scripts_dir(p) and stem(p).endswith("-test"))]


class Tree:
    """One reading of one tree: a commit, the index, or the working tree.

    `texts` covers `wanted(paths)` and nothing else; a path outside it reads as
    empty, which is correct because nothing asks for one."""

    def __init__(self, label, paths, texts, in_scripts_dir):
        self.label = label
        self.paths = paths
        self.texts = texts
        scripts = [p for p in paths if in_scripts_dir(p)]
        self.suites = [p for p in scripts if stem(p).endswith("-test")]
        self.code = [p for p in scripts if not stem(p).endswith("-test")
                     and p.endswith(CODE_SUFFIXES)]
        rows = json.loads(texts[SNAPSHOT])["commands"] if SNAPSHOT in texts else []
        self.scenarios = {row[2] for row in rows}
        self._by_entity = {}
        for module, _, name in rows:
            self._by_entity.setdefault(str(PurePosixPath(module).parent), set()).add(name)
        self.htmls = [p for p in paths if html_form(p)]
        self._declared = {}

    def suites_of(self, code_path):
        want = stem(code_path) + "-test"
        return [s for s in self.suites if stem(s) == want]

    def declared(self, suite):
        """The names a suite's `# witnesses:` lines declare, whatever the tree
        holds -- so a declaration naming nothing that exists can be told from
        no declaration at all."""
        if suite not in self._declared:
            names = set()
            for line in self.texts.get(suite, "").splitlines():
                m = WITNESSES.match(line)
                if m:
                    names |= {n.strip() for n in m.group(1).split(",") if n.strip()}
            self._declared[suite] = names
        return self._declared[suite]

    def declared_by_suites(self):
        return set().union(*(self.declared(s) for s in self.suites))

    def witnessed(self):
        """The listed scenarios some suite declares: the model's `witnessed`."""
        return self.declared_by_suites() & self.scenarios

    def witnesses_a_scenario(self, suite):
        return bool(self.declared(suite) & self.scenarios)

    def tied(self, code_path):
        return any(self.witnesses_a_scenario(s) for s in self.suites_of(code_path))

    def refines(self, html):
        """The names an html form's `data-scenario` sections declare."""
        names = set()
        for m in SECTION.finditer(self.texts.get(html, "")):
            attrs = attributes(m.group(1))
            if "data-scenario" in attrs and attrs.get("data-refines"):
                names |= {n.strip() for n in attrs["data-refines"].split(",")
                          if n.strip()}
        return names

    def html_faults(self, html):
        """(T6, T7) for one html form: the names that are no command of its
        entity, and what it lacks as a tie -- each a sorted list of strings."""
        entity = str(PurePosixPath(html).parent.relative_to("spec"))
        own = self._by_entity.get(entity, set())
        names = self.refines(html)
        witnessed = self.declared_by_suites()
        t7 = ([] if names else ['refines no scenario: it carries no `<section '
                                'data-scenario data-refines="<Name>">`'])
        t7 += [f"refines `{n}`, which no suite's `# witnesses:` line declares"
               for n in sorted(names & own - witnessed)]
        return sorted(names - own), t7


def entries(out, oid_field):
    """{path: oid} from a `-z` listing whose record is `<info>\\t<path>`.

    `-z` and `os.fsdecode`, never the default listing: under `core.quotePath`,
    which git and CI both default on, a non-ASCII path comes back quoted and
    matches no suite, no code path and no spec module, so it leaves every set
    without a word. `-z` emits the bytes, and fsdecode round-trips them."""
    found = {}
    for rec in out.split(b"\0"):
        if not rec:
            continue
        info, _, raw = rec.partition(b"\t")
        fields = info.split()
        oid = oid_field(fields)
        if oid is not None:
            found[os.fsdecode(raw)] = oid.decode()
    return found


def committed(label, ref, rules):
    """A tree named by a commit or a ref."""
    oid_of = entries(git_root_bytes("ls-tree", "-r", "-z", ref),
                     lambda f: f[2] if f[1] == b"blob" else None)
    want = wanted(list(oid_of), rules[0])
    blobs = read_blobs(oid_of[p] for p in want)
    return Tree(label, list(oid_of),
                {p: blobs.get(oid_of[p], "") for p in want}, *rules)


def head_tree(rules):
    try:
        return committed("HEAD", "HEAD", rules)
    except subprocess.CalledProcessError:
        return Tree("HEAD (no commit yet)", [], {}, *rules)


def index_tree(rules):
    oid_of = entries(git_root_bytes("ls-files", "-s", "-z"), lambda f: f[1])
    want = wanted(list(oid_of), rules[0])
    blobs = read_blobs(oid_of[p] for p in want)
    return Tree("the index", list(oid_of),
                {p: blobs.get(oid_of[p], "") for p in want}, *rules)


def worktree(rules):
    """The working tree is what is ON DISK: a tracked file deleted there and
    not yet staged is gone from this reading, so a suite removed with `rm` is
    T2 and not a FileNotFoundError the last resort permits."""
    paths = [os.fsdecode(r) for r in git_root_bytes("ls-files", "-z").split(b"\0") if r]
    paths = [p for p in paths if (Path(ROOT) / p).is_file()]
    texts = {p: (Path(ROOT) / p).read_text(errors="replace")
             for p in wanted(paths, rules[0])}
    return Tree("the working tree", paths, texts, *rules)


def changed(before_ref, after_kind):
    """({after-path: before-path} for every rename, {every path the change
    touched}).

    The renames are what lets a code path keep its identity across the two
    readings. Whether a path is NEW is not read from here but from the tree
    before: an intent-to-add entry is in the index and absent from
    `diff --cached`, and a guard that asked the diff would have read it as an
    old path. The touched set is read from here on purpose, and only T4 and T6
    use it -- see the T4 note in judge().

    `-z` for the same reason the listings use it, and its records come in
    threes for a rename or a copy -- status, source, destination -- against
    twos for everything else."""
    args = ["diff", before_ref, "--name-status", "-M", "-z"]
    if after_kind == "index":
        args = ["diff", "--cached", before_ref, "--name-status", "-M", "-z"]
    elif after_kind == "commit":
        args = ["diff", before_ref, "HEAD", "--name-status", "-M", "-z"]
    try:
        fields = [f for f in git_root_bytes(*args).split(b"\0")]
    except subprocess.CalledProcessError:
        return {}, set()                         # no HEAD: nothing to diff from
    moved, touched, i = {}, set(), 0
    while i < len(fields) and fields[i]:
        status = fields[i].decode()
        if status[:1] in ("R", "C"):
            if i + 2 >= len(fields):
                break
            src, dst = os.fsdecode(fields[i + 1]), os.fsdecode(fields[i + 2])
            if status[:1] == "R":
                moved[dst] = src
            touched |= {src, dst}
            i += 3
        else:
            touched.add(os.fsdecode(fields[i + 1]))
            i += 2
    return moved, touched


def read_legacy(path):
    """An allow-list from a file, one path per line, `#` starting a comment.

    A file that is not there RAISES rather than reading as an empty list: an
    absent list and a list of nothing license opposite things, and the caller
    that named a file is owed the difference."""
    lines = Path(path).read_text(errors="replace").splitlines()
    return {t for t in (line.split("#", 1)[0].strip() for line in lines) if t}


def judge(after_kind, against, legacy_path):
    global ROOT
    # Root first, and every git call and disk read under it: run from a
    # subdirectory, a bare `git ls-files` lists that directory alone, which
    # reads as a tree with no scripts/ and passes.
    ROOT = root = git_bytes("rev-parse", "--show-toplevel").decode(
        "utf-8", "replace").strip()
    rules = (load_sibling("check-tree-shape.py").in_scripts_dir,)
    source = "LEGACY" if legacy_path is None else legacy_path

    if after_kind == "commit":
        # HEAD MUST CONTAIN THE REF, or the two trees are not a change: every
        # commit the ref has and HEAD has not reads backwards -- a path the ref
        # tied reads as one HEAD untied, and a branch that committed nothing at
        # all is refused with a T3 naming a file it never opened. The reading
        # cannot be made, so it is not made: this permits and says so, the way
        # every other unreadable input here does. On a pull request GitHub's
        # merge commit contains the base by construction, and merge condition 3
        # keeps it so; what this catches is the window where `origin/main` moved
        # between that merge commit and the fetch.
        #
        # THREE OUTCOMES, NOT TWO, and collapsing them is what made this guard
        # inert in CI for four commits. `--is-ancestor` exits 0 for yes, 1 for
        # no, and 128 for a question it could not read -- a ref that does not
        # resolve, or a SHALLOW clone, where HEAD's parents are grafted away and
        # every ancestry answer is no. `check.yml` cloned shallow, so the gate
        # fired on every run and the log read like a verdict. A shallow tree is
        # named as such here, because the remedy is the clone's and not the
        # branch's.
        probe = subprocess.run(["git", "-C", ROOT, "merge-base", "--is-ancestor",
                                against, "HEAD"], capture_output=True, text=True)
        if probe.returncode not in (0, 1):
            print(f"check-sdlc-tie: PERMITTING -- the reading itself failed: git "
                  f"could not say whether HEAD contains {against} "
                  f"({probe.stderr.strip() or f'exit {probe.returncode}'}); "
                  f"nothing was judged", file=sys.stderr)
            return 0
        if probe.returncode == 1:
            shallow = git_root_bytes("rev-parse", "--is-shallow-repository"
                                     ).strip() == b"true"
            why = ("this clone is SHALLOW, so HEAD's parents are grafted away "
                   "and no ancestry can be read here -- deepen the clone rather "
                   "than reading this as a verdict about the branch"
                   if shallow else
                   f"HEAD does not contain {against}, so the two trees are not "
                   f"a change and every commit {against} has and HEAD has not "
                   f"would read backwards")
            print(f"check-sdlc-tie: PERMITTING -- {why}. Nothing was judged",
                  file=sys.stderr)
            return 0
    t0 = time.perf_counter()
    before = committed(against, against, rules) if after_kind == "commit" \
        else head_tree(rules)
    t1 = time.perf_counter()
    after = {"index": index_tree, "worktree": worktree}.get(
        after_kind, lambda r: committed("HEAD", "HEAD", r))(rules)
    t2 = time.perf_counter()
    moved, touched = changed(against if after_kind == "commit" else "HEAD",
                             after_kind)
    # THE LIST AFTER IS THE ONE THE JUDGED TREE HOLDS, not the copy running:
    # under `--staged` the running copy is the worktree's, and a line on disk
    # only would license or refuse a commit that does not carry it. A tree with
    # no readable copy of its own is judged by the running one, and says so.
    if legacy_path is not None:
        allowed, after_read = read_legacy(legacy_path), ""
        held, unread = None, ""
    else:
        held, why = own_list(after)
        allowed = set(LEGACY) if held is None else held
        after_read = (f"read from {after.label}'s {LEGACY_HOME}; "
                      if held is not None else f"the running copy's: {why}; ")
        held, unread = own_list(before)
        unread = f": {unread}"
    allowed_before = allowed if held is None else held
    list_read = (f"the list before read from {before.label}'s {LEGACY_HOME}, "
                 f"{len(held)} entr(ies)" if held is not None else
                 f"{source} stands for the list before too{unread}")

    print(f"check-sdlc-tie: read {len(after.scenarios)} scenario name(s), "
          f"{len(after.suites)} suite(s), {len(after.htmls)} html form(s), "
          f"{len(after.code)} code path(s) from "
          f"{after.label} under {root}; each judged against {before.label}, "
          f"{len(moved)} path(s) renamed in between; two trees read in "
          f"{(t1 - t0) * 1000:.0f} + {(t2 - t1) * 1000:.0f} ms")

    findings, licensed = [], []
    for k in after.code:
        if after.tied(k):
            continue
        was = moved.get(k, k)                    # its name in the tree before
        if was not in before.code:
            why = ("no suite carries its stem" if not after.suites_of(k)
                   else f"its suite declares no scenario {SNAPSHOT} lists")
            findings.append(("T1", k, f"added untied: {why}. A code path is "
                                      f"tied by a `{stem(k)}-test` suite carrying "
                                      f"a `# witnesses: <Name>` line that names a "
                                      f"command {SNAPSHOT} lists"))
            continue
        if before.tied(was):                     # `was` is in before.code here
            if not after.suites_of(k):
                gone = ", ".join(before.suites_of(was))
                findings.append(("T2", k, f"was tied through {gone}; after this "
                                          f"commit no suite carries its stem. "
                                          f"Rename or restore the suite with it"))
            else:
                findings.append(("T3", k, f"was tied; its suite "
                                          f"{', '.join(after.suites_of(k))} "
                                          f"declares no scenario after this "
                                          f"commit. Rewrite its `# witnesses:` "
                                          f"line"))
            continue
        if k in allowed and {was, k} & allowed_before:  # the line moved with it
            licensed.append(k)
        elif k in allowed:
            pass                                 # a line this commit added: below
        elif was in allowed:                     # renamed, its line left behind
            findings.append(("T4", k, f"renamed from {was}, and the allow-list "
                                      f"({source}) names only the old path: a "
                                      f"line moves with its file, in the same "
                                      f"commit, since a later one would be a "
                                      f"line the list gains. Move it to {k}, or "
                                      f"tie it"))
        elif was in allowed_before:              # its line dropped, still untied
            findings.append(("T4", k, f"untied, and the allow-list ({source}) "
                                      f"loses its line in this commit: a line "
                                      f"leaves with the tie, in the same commit. "
                                      f"Tie it, or keep the line"))
        elif k not in touched:               # a rename puts both ends in it
            # ONLY WHERE THIS COMMIT TOUCHED IT. A path untied on both sides
            # that the change never opened is not this change's debt, and every
            # fixture repository under scripts/*-test.py is a tree of copied
            # guards with no suites -- so an unscoped T4 refused every commit
            # any of them makes. Scoped, the bite that is left is real: a path a
            # bypassed hook landed untied is refused the next time anything
            # opens it, and CI's `--against origin/main` reads the whole pull
            # request, where the same path is new and T1 has it already.
            licensed.append(k)
        else:
            findings.append(("T4", k, f"untied before this commit and untied "
                                      f"after it, and the allow-list ({source}) "
                                      f"does not name it: the debt grew where "
                                      f"nothing read it. Tie it"))
    for e in sorted(allowed - allowed_before):
        if moved.get(e) in allowed_before:       # the line moved with its file
            continue
        findings.append(("T4", e, f"the allow-list ({source}) gains this line in "
                                  f"this commit, and the list only shrinks: a line "
                                  f"licenses nothing {before.label}'s list did not "
                                  f"hold. Tie the path instead"))
    absent = 0
    for e in sorted(allowed):
        if e not in after.code:
            # NOT A FINDING, A COUNT. An entry naming no code path here says
            # nothing on its own: the path may have been deleted, or this may be
            # a tree the list is not about -- which is what every fixture
            # repository under scripts/*-test.py is, since each copies the
            # guards by their real names. Refusing on it walled off every commit
            # any of them made, including the one that deletes a guard on
            # purpose. The count goes in the reading and the reader decides.
            absent += 1
        elif after.tied(e):
            findings.append(("T5", e, f"the allow-list ({source}) names it and it "
                                      f"is tied now: the licence is spent. Drop "
                                      f"it"))
    left = 0
    for s in after.suites:
        dead = after.declared(s) - after.scenarios
        if s not in touched:                     # a rename puts both ends in it
            # ONLY WHAT THIS CHANGE KILLED, in a suite it never opened: a name
            # already dead before is not this change's debt, the scope T4 has.
            # The ones left are counted in the reading, so a tree carrying
            # that debt does not read like a clean one.
            old = dead & (before.declared(s) - before.scenarios)
            left += len(old)
            dead -= old
        for n in sorted(dead):
            findings.append(("T6", s, f"its `# witnesses:` line declares `{n}`, "
                                      f"and {SNAPSHOT} in {after.label} lists "
                                      f"no such command. Rename it to the "
                                      f"scenario it witnesses, or drop it, or "
                                      f"regenerate the snapshot"))
    kept = 0
    for h in after.htmls:
        dead, lacks = after.html_faults(h)
        if h not in touched:                     # T6's scope, for a form
            # Untouched is unrenamed too: a rename puts both ends in `touched`.
            old_dead, old_lacks = (before.html_faults(h) if h in before.htmls
                                   else ([], []))
            kept += (sum(n in old_dead for n in dead)
                     + sum(w in old_lacks for w in lacks))
            dead = [n for n in dead if n not in old_dead]
            lacks = [w for w in lacks if w not in old_lacks]
        for n in dead:
            findings.append(("T6", h, f"its `data-refines` declares `{n}`, and "
                                      f"{SNAPSHOT} in {after.label} lists no such "
                                      f"command in its entity"))
        for w in lacks:
            findings.append(("T7", h, f"an html form is a scenario tied by name, "
                                      f"and this one {w}"))
    t8_read = (f"T8 read {len(before.witnessed())} witnessed scenario(s) "
               f"before and {len(after.witnessed())} after"
               if after.scenarios == before.scenarios else
               f"T8 stood down, the command names in {SNAPSHOT} having changed")
    if after.scenarios == before.scenarios:
        # NO FEATURE, READ BY NAMES: the command list is what it was. Every
        # scenario a suite declared must still be declared by some suite.
        for n in sorted(before.witnessed() - after.witnessed()):
            for s in before.suites:
                if n in before.declared(s):
                    findings.append(("T8", s, f"declared `{n}` before this commit "
                                              f"and no suite declares it after, "
                                              f"while {SNAPSHOT} lists the "
                                              f"commands it did: a change that "
                                              f"adds no feature keeps what is "
                                              f"witnessed. Keep the declaration, "
                                              f"or retire the scenario in the "
                                              f"same commit"))
    for code, path, what in sorted(findings):
        print(f"{code}\t{path}\t{what}", file=sys.stderr)
    print(f"check-sdlc-tie: {len(findings)} finding(s); {len(licensed)} code "
          f"path(s) untied and licensed by the allow-list ({source}, "
          f"{after_read}"
          f"{len(allowed)} entr(ies), {absent} naming no code path here; "
          f"{list_read}); "
          f"{left} dead witness name(s) left where the change never opened "
          f"the suite, {kept} fault(s) left in html forms it never opened; "
          f"{t8_read}")
    return 1 if findings else 0


def main():
    p = argparse.ArgumentParser(add_help=False)
    # EXCLUSIVE, because each names a different pair of trees and passing both
    # silently dropped `--against`: the reading line said "judged against HEAD"
    # and the caller who asked for a ref was told nothing.
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--against", metavar="REF")
    p.add_argument("--legacy", metavar="FILE")
    args = p.parse_args()
    kind = "index" if args.staged else ("commit" if args.against else "worktree")
    try:
        return judge(kind, args.against or "HEAD", args.legacy)
    except Exception as e:                       # noqa: BLE001 -- the last resort
        print(f"check-sdlc-tie: PERMITTING -- the reading itself failed "
              f"({e.__class__.__name__}: {e}); nothing was judged", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
