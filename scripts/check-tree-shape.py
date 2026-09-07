#!/usr/bin/env python3
"""Refuse a commit whose tree holds a shape this repository's design forbids.

Sibling of check-rule-readers, and split from it by question rather than by
rule: that guard asks whether a rule got a second reader, this one asks whether
the tree still has the shape AGENTS.md describes. Four rules share that failure
mode -- each is a sentence of prose today, each is decidable from the file list
alone, and each has already been broken once or is one careless commit from it.

WHAT IT CHECKS

  R1  spec/ and docs/ hold no markdown.
      spec/ is Alloy whose comments are the spec, and an HTML diagram may sit
      beside a model; docs/ is HTML drawn for a reader. What this refuses is
      markdown under either, which is what "temporary" always turns out to be.
      Nothing here counts the diagrams or checks where one sits: that would be
      a rule with no reader, and this is the reader.

  R2  every tracked top-level entry is named in .gitignore's allowlist.
      The root is `/*` plus `!` lines. A directory that gets tracked without
      one is tracked by accident, and the accident is invisible: git says
      nothing, and the next `git add` in it silently commits scratch.

  R3  what code names is what the tree holds. THREE ALLOW-LISTS, each derived
      from the tree rather than listed by hand (#237 replaced a deny list of
      retired names, which grew one entry per retirement and caught nothing
      nobody had thought of):

        R3a  a `scripts/<name>` a code line calls resolves to a file.
             The resolver is `check-cross-references.py`'s `Tree`, imported.
        R3b  a `runtime/<name>` is derived state or a process artifact.
             A record of the work belongs on its issue, not here.
        R3c  a `campaign-claim.py <verb>` is one its argparse defines.

      Same split check-rule-readers makes, and for the same reason: prose must
      go on being able to say `runtime/holder` is retired, while a path
      spelling it is a reintroduction. R3 stands down over `RECORDED` -- a
      corpus of calls that were really made -- and R3a over the suites, whose
      fixtures name absent paths on purpose. Both are counted on every run.

  R4  no member-repository file is committed here.
      Three planes, and the base is one of them. R2 catches the ordinary
      route in (repos/ has no allowlist line); this catches the deliberate one.

WHAT IT DOES NOT CATCH

R3 is a path check, not a concept check: reintroducing the holder role under a
different word, or in a file that exists, passes. R1 does not read a file's contents, so HTML named .md is
caught and markdown named .html is not. Both are floors -- they stop the commit
somebody makes without noticing, which is how every one of these got broken.

EXEMPTING A BLOCK FROM R3

Code that must spell a retired name anyway -- this guard's own suite, whose
fixtures have to -- carries a marker in whatever comment its language has:

    unguarded: <owner> -- <why>

`<owner>` is `check-tree-shape` and nothing else. A marker naming a sibling
guard's token belongs to that guard and silences nothing here, and prose that
merely spells the word (this paragraph) names no owner and exempts nothing --
which is the point, since the unowned form let this header exempt this body.

It reaches the code beneath the comment it is the last thing to say, up to the
next blank line. Prose after it on a later line spends it; the comment's own
closing delimiter does not.

READING VERSUS VERDICT

A file it cannot read is reported as R0 and refuses the commit. It is never
skipped: a guard that skips what it cannot read reports nothing and reads
exactly like a pass, which is the failure mode this whole family of checks
exists to refuse. R0 is counted apart from R1-R4 because "I looked and found
nothing" and "I could not look" want different repairs.

EXIT

Every run prints how many paths it read and from where -- the index under
`--staged`, the working tree otherwise -- because a silent clean run and a run
that examined nothing read the same, and "examined nothing" is what a wrong
checkout or an empty file list looks like. 1 adds one line per finding on
stderr: the rule, the path, and what was found. The status is about the verdict;
an unreadable tree crashes.

Usage: scripts/check-tree-shape.py [--staged]
"""
import importlib.machinery
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

def extensionless_call():
    """A call to a script beside this one that omits its language extension.

    #105 gave every script here `.py` or `.sh`, so `scripts/campaign-claim`
    names no file. The names are read from the directory this guard was loaded
    out of, never listed: the other bans below are literals because they name
    things that will never come back, and this one names things that arrive --
    a script added tomorrow is covered with no edit here. The directory exists
    by construction, the interpreter having just read this file out of it.

    `(?![\\w.-])` is what lets the correct spellings through:
    `scripts/campaign-claim` is refused, while `scripts/campaign-claim.py` and
    `scripts/campaign-claim-test.py` both pass.
    """
    names = sorted((p.stem for p in Path(__file__).resolve().parent.iterdir()
                    if p.suffix in (".py", ".sh")), key=len, reverse=True)
    return re.compile(r"\bscripts/(" + "|".join(re.escape(n) for n in names)
                      + r")(?![\w.-])")


# R3 IS THREE ALLOW-LISTS, NOT A DENY LIST (#237). It was a list of retired
# names, and a deny list has the failure mode every deny list has: it grows one
# entry per retirement, it says nothing about a name nobody thought to add, and
# every entry is a second reader of a rule some other file already owns. Each
# list below is derived from what the tree actually holds, so a retirement
# lands in it by deleting the file, and a name nobody anticipated is caught the
# same day it is written.
#
# What the deny list held, and where each entry went:
#
#   scripts/campaign-{anchors,bound,...}   R3a -- the file is not there
#   scripts/acquire-repo, campaign-name-session (old paths)   R3a, likewise
#   scripts/<name> with no extension       R3a
#   runtime/{holder,executors,claims,handover}   R3b -- not in the set
#   campaign-claim.py {status,list,alive,stood-down}   R3c -- argparse says
#   CLAIMED, STOOD DOWN                    dropped. They are words, not paths,
#                                          and the concepts behind them are
#                                          gone from the model; a word check
#                                          could only catch the spelling.

# R3a. Every `scripts/<name>` a code line calls, skill-scoped or not. THE
# RESOLUTION IS `check-cross-references.py`'s: its `Tree` is the one reader of
# whether a path exists in this tree, and this asks it rather than restating
# it. That file reads `.md`, `.markdown` and `.als`; this reads code, so the
# two cover different files with one rule between them.
#
# THE TOKEN MAY NOT END IN PUNCTUATION. `see scripts/install-hooks.sh.` ends a
# sentence, and a trailing dot swallowed into the token made every such line a
# finding about a file that is plainly there.
SCRIPT_CALL = re.compile(
    r"(?<![\w./-])((?:\.claude/skills/[a-z][a-z0-9-]*/)?"
    r"scripts/[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9])")

# R3b. What `runtime/` may hold, named by what it is FOR: a derived file that
# can be rebuilt from GitHub, or a process artifact no issue can carry. A
# record of the work is not in the list, and that is the rule -- AGENTS.md
# § The three planes says no record of the work lives only in `runtime/`, and
# this is the machine behind that sentence rather than a second statement of
# it.
RUNTIME_ALLOWED = ("repos", "repos.tmp", "campaign-issue-body-derived.md",
                   "guard.log", "briefed")
RUNTIME_SUFFIXES = (".pid", ".lock", ".log")
RUNTIME_CALL = re.compile(r"(?<![\w./-])runtime/([A-Za-z0-9][A-Za-z0-9._-]*)")

# R3c. A `campaign-claim.py <subcommand>` is one argparse defines. Read from
# the file, so retiring a subcommand is deleting its `add_parser` and nothing
# else -- the deny list needed an entry per retired verb, and had four.
# THE LOOKAHEAD IS WHAT KEEPS PROSE OUT. `scripts/campaign-claim.py in a
# checkout` is a sentence, not a call, and `in` is not a subcommand -- so
# a real call is recognised by what FOLLOWS the verb: an argument, a
# placeholder, a flag, or the end of the command.
CLAIM_CALL = re.compile(
    r"campaign-claim\.py[\"\']?\s+(?!--)([a-z][a-z-]*)"
    r"(?=[\"\']?\s*(?:$|[<$0-9]|--))")


def load_tree(staged):
    """(Tree or None, why) -- `check-cross-references.py`'s path resolver.

    Imported by path because these are scripts and not a package. It owns
    whether a path resolves in this tree; asking it is what keeps R3a from
    becoming a second reader of that."""
    src = Path(__file__).resolve().parent / "check-cross-references.py"
    try:
        spec = importlib.util.spec_from_loader(
            "xref", importlib.machinery.SourceFileLoader("xref", str(src)))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.Tree(Path(mod.repo_root()), staged), None
    except Exception as e:                      # noqa: BLE001 -- any of them
        return None, f"{e.__class__.__name__}: {e}"


def claim_subcommands():
    """Every subcommand `campaign-claim.py` defines.

    Three outcomes, and the caller acts on each differently:

      a set      these are the verbs; R3c judges against them
      None       the file is not in this tree, so there is no `campaign-claim`
                 here to call -- R3c does not apply, and R3a already refuses a
                 call naming a file that is not there
      raises     never: an unreadable file comes back as `False`, which R3c
                 reports as `could not look` rather than judging"""
    src = Path(__file__).resolve().parent / "campaign-claim.py"
    if not src.is_file():
        return None
    try:
        text = src.read_text()
    except OSError:
        return False
    return set(re.findall(r"add_parser\(\"([a-z][a-z-]*)\"", text))


# A RECORDED CORPUS IS EVIDENCE, NOT CODE, and R3 does not run over one.
# `scripts/fixtures/` holds calls this machine's sessions really made, extracted
# by scripts/guard-corpus.py and replayed by the guard suite. Some of them spell
# a name that has since been retired, because they were typed before it was --
# and that is the record being correct, not a reintroduction. Editing the entry
# to please R3 would falsify the measurement, and dropping it would delete the
# one allow case that pins how the guard reads that shape.
#
# NARROW BY PATH AND BY NOTHING ELSE. Not by suffix, which would exempt every
# `.jsonl` anywhere, and not by a marker, which a data format has nowhere to
# put. R1, R2 and R4 still run over these paths: a member repository's file
# under `scripts/fixtures/` is as wrong as anywhere else, and only the
# retired-name reading has a reason to stand down. Every run says how many
# paths it skipped and why, because an exemption that prints nothing is a rule
# silently gone.
RECORDED = ("scripts/fixtures/",)

FENCE = re.compile(r"^\s*(```|~~~)")

# An exemption names the guard it exempts, the way check-rule-readers' does, and
# `check-tree-shape` is the only owner this one answers to. Two things turn on
# that. A marker naming another guard -- `campaign-repos`, one of
# check-rule-readers' tokens -- is that guard's business and silences nothing
# here. And a docstring *explaining* the syntax names no owner at all, so this
# guard's own header no longer exempts this guard's body: the failure that
# taught it, since an unowned marker had exempted every line under the
# explanation up to the next blank one.
OWNER = "check-tree-shape"
EXEMPT = re.compile(r"<!--\s*unguarded:\s*(?P<owner>[\w-]+)\s*--")
EXEMPT_ANY = re.compile(r"\bunguarded:\s*(?P<owner>[\w-]+)\s*--")

# A prose line carrying nothing but the comment's own punctuation -- ` */`, a
# docstring's closing `"""`, `-->`. Such a line says nothing, so it neither
# grants an exemption nor spends one; every other prose line spends it.
DELIMITER_ONLY = re.compile(r"^[\s*/#<>!'\"-]*$")


def exempts(text, pattern=EXEMPT_ANY):
    m = pattern.search(text)
    return bool(m and m.group("owner") == OWNER)


def prose_exempt(text, current, pattern=EXEMPT_ANY):
    """Whether the code beneath this prose line is exempt.

    A marker naming this guard sets it. Any other prose line clears it, so a
    marker buried in the middle of a docstring cannot reach the code the
    docstring precedes -- only a marker the code is actually written under can.
    A delimiter-only line is not prose and leaves the reading where it was, so
    a marker on a block comment's last content line still reaches past ` */`.
    """
    if exempts(text, pattern):
        return True
    return current if DELIMITER_ONLY.match(text.strip()) else False

# Where the prose lives differs by language, and a sweep that knows only one of
# them is the sweep that comes up a copy short. ~/.claude/CLAUDE.md states the
# rule; this table is what makes a machine able to run it. Each entry says how
# a file's *prose* is delimited, and every line that is not prose is code.
#
#   block  -- (open, close) pairs; the delimiters' own lines are prose too
#   line   -- a marker that makes the rest of the line prose
#
# A name in prose is a mention this repository must go on being able to make.
# A name in code is a reintroduction.
PROSE = {
    ".als":  {"block": [("/*", "*/")], "line": ["//", "--"]},
    ".yml":  {"block": [], "line": ["#"]},
    ".py":   {"block": [('"""', '"""'), ("'''", "'''")], "line": ["#"]},
    ".sh":   {"block": [], "line": ["#"]},      # no block comment in POSIX sh
    ".html": {"block": [("<!--", "-->")], "line": []},
    ".json": {"block": [], "line": []},        # no comment syntax; all code
    ".jsonl": {"block": [], "line": []},       # ditto, one object per line
    "":      {"block": [('"""', '"""'), ("'''", "'''")], "line": ["#"]},
}


def code_lines_by_comment(text, spec):
    """Lines that are not inside a comment. A block delimiter's own line counts
    as prose, so a docstring naming a retired term does not fire on its first
    line either.

    The same per-block exemption markdown gets, spelled in whichever comment the
    language has: a marker naming this guard exempts the run of code beneath it,
    up to the next blank line. One syntax across both guards and every language,
    and it names its owner so a reader can check the claim. Its first user is
    this guard's own test, whose fixtures have to spell the names it bans."""
    out, closing, exempt = [], None, False
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            exempt = False
            continue
        if closing:
            exempt = prose_exempt(line, exempt)
            if closing in line:
                closing = None
            continue
        before = None
        for o, c in spec["block"]:
            if o in line:
                # A one-line block opens and closes on the same line.
                before, rest = line.split(o, 1)
                if c not in rest:
                    closing = c
                break
        if before is not None:
            # Same split the line-comment cut makes below, for the same reason:
            # an opener with code in front of it is a string literal as often as
            # it is a docstring, so it may grant an exemption and never spends
            # one. An opener at the head of its line is prose and does both.
            if before.strip():
                exempt = exempt or exempts(line)
            else:
                exempt = prose_exempt(line, exempt)
            continue
        # A line comment makes the rest of the line prose, so the earliest
        # marker wins -- taking the first marker in table order instead lets a
        # name sitting between two markers read as code. A whole-line comment
        # needs no case of its own: it is this cut at column zero.
        cut = min((line.index(m) for m in spec["line"] if m in line), default=None)
        if cut is not None:
            # A whole-line comment is prose and spends the exemption. A comment
            # trailing code annotates that code, so it may grant one and never
            # spends one: this cut cannot tell a comment from a `#` inside a
            # string literal, and letting one end an exemption granted several
            # lines above would make the marker unusable over a run of code.
            if line[:cut].strip():
                exempt = exempt or exempts(line[cut:])
            else:
                exempt = prose_exempt(line[cut:], exempt)
            line = line[:cut]
        if line.strip() and not exempt:
            out.append((n, line))
    return out


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=True).stdout


def tracked(staged):
    src = ["diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged \
        else ["ls-files"]
    return [p for p in git(*src).splitlines() if p]


def read(path, staged):
    """Contents as they will be committed. A path that cannot be read is a
    crash: see READING VERSUS VERDICT."""
    if staged:
        return git("show", f":{path}")
    return Path(path).read_text()


def code_lines(text):
    """Line numbers whose text renders as code -- fenced or indented -- with
    check-rule-readers' per-block exemption honoured. The exemption sits on the
    line *above* the block, so the fence that opens the block must carry it in
    rather than clear it."""
    out, fenced, exempt_block, exempt_next = [], False, False, False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced, exempt_block = (not fenced), (exempt_next if not fenced else False)
            exempt_next = False
            continue
        if fenced:
            if not exempt_block:
                out.append((n, line))
            continue
        if exempts(line, EXEMPT):
            exempt_next = True
            continue
        if line.startswith(("    ", "\t")) and line.strip():
            if not exempt_next:
                out.append((n, line))
            continue
        if line.strip():
            exempt_next = False
    return out


def main():
    staged = "--staged" in sys.argv
    paths = tracked(staged)
    # Said before any verdict, and on every run: a clean tree and a tree nobody
    # looked at both print nothing otherwise, and the second is what a wrong
    # checkout or an empty file list gives.
    root = git("rev-parse", "--show-toplevel").strip()
    print(f"check-tree-shape: {len(paths)} tracked path(s) under {root}, "
          f"read from {'the index' if staged else 'the working tree'}")
    findings = []

    def note(rule, path, what):
        findings.append(f"{rule}\t{path}\t{what}")

    # R1
    misfiled = [p for p in paths
                if p.endswith(".md") and p.split("/")[0] in ("spec", "docs")]
    for p in misfiled:
        note("R1", p, "markdown under spec/ or docs/ -- spec/ is Alloy, docs/ is HTML")

    # R2
    ignore = Path(".gitignore")
    tops = sorted({p.split("/")[0] for p in paths})
    if not ignore.exists():
        # Reported, not raised: raising here would discard R1's findings and
        # skip R3 and R4 too.
        note("R0", ".gitignore", "absent, so the allowlist could not be read "
                                 "and R2 did not run")
        allowed = None
    else:
        allowed = {l[2:].rstrip("/") for l in ignore.read_text().splitlines()
                   if l.startswith("!/")}
        for t in tops:
            if t not in allowed:
                note("R2", t, "tracked but not in .gitignore's allowlist")

    # R3
    # ONE READER OF "DOES THIS PATH EXIST HERE", imported rather than restated:
    # `check-cross-references.py`'s `Tree`. When it will not load, R3a stands
    # down and says so -- `could not look` is not `every call resolves`.
    tree, tree_why = load_tree(staged)
    if tree_why:
        note("R0", "scripts/check-cross-references.py",
             f"R3a did not run: the path resolver would not load ({tree_why})")
    # R3a STANDS DOWN OVER SUITES, for the reason it stands down over the
    # recorded corpus: a suite's fixtures name paths that deliberately do not
    # exist -- `scripts/gone.py` is the point of the case it sits in, and a
    # rule that refused it would refuse every guard's own coverage. R3b and
    # R3c still run there, because neither depends on a path existing.
    fixtures = {q for q in paths if q.endswith("-test.py")}
    subs = claim_subcommands()
    if subs is False:
        note("R0", "scripts/campaign-claim.py",
             "R3c did not run: the file is here but its subcommands could "
             "not be read")
        subs = None
    recorded = [p for p in paths if p.startswith(RECORDED)]
    for p in paths:
        if p in recorded:
            continue
        # The kind is decided before the file is opened, so a binary file with
        # no prose rule for its suffix is reported as R0 rather than crashing
        # the decode.
        spec = None if p.endswith(".md") else PROSE.get(Path(p).suffix)
        if not p.endswith(".md") and spec is None:
            # A file this sweep cannot read. Counted apart from what it found,
            # because "I looked and found nothing" and "I could not look" are
            # the two outcomes a guard must never merge -- and reported rather
            # than raised, so the rules that already ran still print what they
            # saw.
            note("R0", p, "no prose rule for this suffix; the sweep could not "
                          "read it. Add the suffix to PROSE.")
            continue
        try:
            text = read(p, staged)
        except (UnicodeDecodeError, OSError) as e:
            note("R0", p, f"could not be read as text ({e.__class__.__name__}); "
                          f"the sweep did not run over it")
            continue
        lines = code_lines(text) if spec is None else code_lines_by_comment(text, spec)
        for n, line in lines:
            for tok in (SCRIPT_CALL.findall(line)
                        if tree and p not in fixtures else []):
                if tree.exists(tok):
                    continue                  # a file or a directory that is there
                if not tok.endswith((".py", ".sh")):
                    note("R3a", f"{p}:{n}", f"`{tok}` names no file: a script "
                                            f"carries the extension of its "
                                            f"language; add .py or .sh")
                else:
                    note("R3a", f"{p}:{n}", f"`{tok}` names no file in this "
                                            f"tree -- it was renamed, merged "
                                            f"or moved, and this call was not")
            for tok in RUNTIME_CALL.findall(line):
                if tok in RUNTIME_ALLOWED or tok.endswith(RUNTIME_SUFFIXES):
                    continue
                note("R3b", f"{p}:{n}", f"`runtime/{tok}` is not what runtime/ "
                                        f"holds: {', '.join(RUNTIME_ALLOWED)}, "
                                        f"or a pid, lock or log. A record of "
                                        f"the work goes on its issue")
            if subs is not None:
                for tok in CLAIM_CALL.findall(line):
                    if tok not in subs:
                        note("R3c", f"{p}:{n}", f"`campaign-claim.py {tok}` is "
                                                f"not a subcommand it defines: "
                                                f"{' | '.join(sorted(subs))}")

    # R4
    for p in paths:
        if p == "repos" or p.startswith("repos/") or "/repos/" in p:
            note("R4", p, "a member repository's file in the base plane")

    if fixtures:
        print(f"  R3a stood down for {len(fixtures)} suite(s): a case's "
              f"fixture names a path on purpose that is not there")
    if recorded:
        print(f"  R3 stood down for {len(recorded)} recorded path(s) under "
              f"{', '.join(RECORDED)}: a corpus of calls that were really made "
              f"is evidence, and a retired name in one records when it was "
              f"typed")
    unread = sum(1 for f in findings if f.startswith("R0\t"))
    print(f"  {len(findings)} finding(s)"
          + (f", {unread} of them a path the sweep could not read" if unread else ""))
    if findings:
        print("check-tree-shape: refusing", file=sys.stderr)
        for f in findings:
            print("  " + f, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
