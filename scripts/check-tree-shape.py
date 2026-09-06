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

  R3  a retired name does not come back as code.
      Same split check-rule-readers makes, for the same reason: prose must go
      on being able to say `runtime/holder` is retired, while a path or an
      identifier spelling it is a reintroduction. Retirement notes exist to
      stop reintroduction; with a machine behind the ban they can be deleted.
      It stands down over `RECORDED` -- a corpus of calls that were really
      made -- and says so on every run; the comment there is why.

  R4  no member-repository file is committed here.
      Three planes, and the base is one of them. R2 catches the ordinary
      route in (repos/ has no allowlist line); this catches the deliberate one.

WHAT IT DOES NOT CATCH

R3 is a name check, not a concept check: reintroducing the holder role under a
different word passes. R1 does not read a file's contents, so HTML named .md is
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


# A retired name and the issue that retired it, so a finding says why.
# Prose may name any of these; code may not.
RETIRED = [
    (re.compile(r"\bruntime/holder\b"), "#100 -- the holding session is retired"),
    (re.compile(r"\bruntime/executors\b"), "#59 -- renamed to runtime/claims/, itself retired by #176"),
    # The bare word, not quoted: a quote immediately after it would miss
    # `CLAIMED:`, `send(CLAIMED)`, and `CLAIMED <issue>`. R3 only ever reads
    # code, so prose may still name the message.
    (re.compile(r"\bCLAIMED\b"), "#59 -- the claim is a record, not an announcement"),
    # #105 folded eighteen scripts into twelve. These bans are on the *path*,
    # not the bare word, and deliberately: check-rule-readers keeps
    # `campaign-anchors`, `campaign-subtasks`, `campaign-settlement` and
    # `campaign-session-alive` as exemption tokens, one per form, and its suite
    # writes them into fixtures. Banning the bare word would refuse the table
    # that is the authoritative record of those tokens. What a reintroduction
    # actually looks like is a call, and a call names the path.
    (re.compile(r"\bscripts/campaign-(anchors|bound|subtasks|settlement)\b"),
     "#105 -- merged into scripts/campaign-tracker.py <subcommand>"),
    (re.compile(r"\bscripts/campaign-(live|session-alive)\b"),
     "#105 -- merged into scripts/campaign-claim.py live"),
    # #176 deleted the record, the brief, the canary and the two prose
    # comments.
    #
    # NO `(?!/)` LOOKAHEAD, and the first cut of these had one. It was meant to
    # let prose say `runtime/claims/` while banning the bare noun, and it
    # inverted the intent exactly: a reintroduced READER writes
    # `runtime/claims/<issue>` or `d / "runtime" / "claims"`, both of which the
    # lookahead exempted, while the only thing it caught was prose. These match
    # the path however it is spelled, and a document that must name the retired
    # shape exempts the block, which is what the exemption is for.
    (re.compile(r"\bruntime/claims\b|[\"']runtime[\"']\s*[/,]\s*[\"']claims[\"']"),
     "#176 -- the claim is the branch ref; there is no record"),
    (re.compile(r"\bruntime/handover\b|[\"']runtime[\"']\s*[/,]\s*[\"']handover[\"']"),
     "#176 -- the brief is the sub-issue body"),
    # The comment used to announce a STOOD DOWN ban that no pattern implemented.
    (re.compile(r"\bSTOOD DOWN\b"),
     "#176 -- a peer leaves by stopping its pane, not by saying so"),
    # `\b` before the subcommand and not after `.py`: the skills write
    # `"$BASE/scripts/campaign-claim.py" stood-down`, where a quote stands
    # between the path and the space, so a pattern anchored on `.py ` misses
    # every real call site.
    (re.compile(r"campaign-claim\.py[\"']?\s+(status|list|alive|stood-down)\b"),
     "#176 -- retired with the record; take | release | live are what is left"),
    (re.compile(r"\bscripts/alloy-trace-digest\b"),
     "#105 -- merged into scripts/alloy-check.py --digest"),
    # The lookbehind is load-bearing: the destination path *ends* in
    # `scripts/acquire-repo.sh`, so a bare pattern would refuse every correct call
    # as well as every stale one.
    # Same shape as acquire-repo below: the lookbehind lets the NEW path
    # through, since `.claude/skills/assuming-role/scripts/campaign-name-session.py`
    # spells the old substring inside the correct one.
    (re.compile(r"(?<!assuming-role/)\bscripts/campaign-name-session\b"),
     "#227 -- moved to "
     ".claude/skills/assuming-role/scripts/campaign-name-session.py"),
    (re.compile(r"(?<!opening-campaign/)\bscripts/acquire-repo\b"),
     "#105 -- moved to .claude/skills/opening-campaign/scripts/acquire-repo.sh"),
    (extensionless_call(),
     "#105 -- a script carries the extension of its language; add .py or .sh"),
]

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
            for pat, why in RETIRED:
                if pat.search(line):
                    note("R3", f"{p}:{n}", f"retired name as code ({why}): {line.strip()[:60]}")

    # R4
    for p in paths:
        if p == "repos" or p.startswith("repos/") or "/repos/" in p:
            note("R4", p, "a member repository's file in the base plane")

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
