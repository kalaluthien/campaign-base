#!/usr/bin/env python3
"""Refuse a commit in which one document's pointer at another does not resolve.

Sibling of check-rule-readers and check-tree-shape, and split from both by
question. That one asks whether a rule got a second reader; the shape guard asks
whether the tree still has the shape AGENTS.md describes; this one asks whether
the names documents call each other by still land on something.

Nothing read those names before. The #112 restructure renamed every AGENTS.md
section, and all sixteen `§` citations in the two skills dangled until a person
fixed them by hand -- a whole class of pointer with no reader at all.

WHAT IT CHECKS

Four shapes, and each resolves against a different thing. A guard covering two
leaves the others live and unflagged, so all four are here.

  S1  `§ <Name>` -- a section citation.
      Target file: the markdown path written immediately before the `§`, or
      AGENTS.md when none is. Resolves against that file's ATX headings.

  S2  a literal `.claude/skills/...` path, against the filesystem.

  S3  a literal `spec/campaign/...` path, against the filesystem.

  S5  a literal `scripts/<name>.py` or `.sh` path. TWO ROOTS, and it resolves
      if EITHER holds the file: this repository keeps scripts at its root and
      each skill may keep its own, and prose in a skill cites both -- 17 of the
      references in the tree today name the repository's from inside a skill.
      Asking one root would flag those; asking both still catches the only
      failure that matters, a path naming no file anywhere. A leading `$BASE/`,
      which is how every skill spells a command a session runs, is stripped
      before any shape is asked. Added by #227,
      after that sub-issue moved a script under a skill and left six prose
      citations of the old path standing -- `check-tree-shape`'s RETIRED row
      reads code lines only, so a path grep found them and no guard did.

  S4  a relative `references/...` or `assets/...` path.
      Ambiguous on its own: it resolves against the *citing* file's skill root
      -- the nearest ancestor holding a SKILL.md -- not against a fixed root.
      So the guard must know which file it is reading, not only what that file
      names. Written outside a skill the shape names no root, and that is U2
      below rather than a dangling reference.

WHERE THE NAME ENDS (S1)

A citation is followed by ordinary prose with no delimiter, so `§ The binding),
so this step` and `§ Sub-issues says` and `§ ID, directory, branch` all run
straight into their sentences. A throwaway version of this check that stopped at
punctuation reported five false danglings on exactly those.

The name is found by LONGEST-PREFIX MATCH against the target's heading set,
constrained to end on a word boundary. The heading set is the only thing that
knows where a name ends, so it is what terminates the scan rather than any
guessed delimiter -- and the boundary is what stops the heading `The binding`
from swallowing a citation of a hypothetical `The bindings`, where a bare
`startswith` would resolve a broken name to the wrong section. Longest wins so
that a heading and a longer heading beginning with it both stay citable.

The text scanned runs to the end of the paragraph with newlines joined to
spaces, because these files are hard-wrapped and a name can wrap.

THE THREE VERDICTS, AND WHY THE THIRD EXISTS

  resolved    the target was read and holds the thing named.
  dangling    the target was read and does not hold it.        -> exit 2
  undecided   the guard has no rule for this token, or could
              not open the file it would have to read.         -> exit 3

The third is the whole point. `closing-campaign/references/rationale.md` once
cited `§ Compare then write the campaign issue body`, which named BOLD INLINE
PROSE in AGENTS.md rather than a heading. A guard that scans `^#` lines, fails
to find it, and calls it dangling has folded together two different facts --
*this citation is broken* and *I do not have a rule for this shape* -- and a
guard that folds them reports the tree clean while a class of pointer goes
unchecked. That is this repository's signature defect and building a fresh one
here would be worse than the gap it closes. So:

  U1  a `§` name that no heading prefixes, but that a **bold span** in the
      target file does. The citation points at prose; the guard has no rule for
      citing prose. Named, never counted as dangling and never as resolved.
  U2  an S4 relative path in a file that is inside no skill: no root to
      resolve against.
  U3  a file that cannot be opened or decoded -- the citing file, or the target
      of an S1 citation.

WHAT IS DELIBERATELY NOT A REFERENCE

Printed as counts, and listed by --list, so the boundary is visible rather than
implied:

  template  a path-like run holding `<...>` or a `*` glob. `<campaign>/repos/`
            and `spec/campaign/*/*.als` name a form, not a file.
  external  an S1 citation qualified by a path outside this repository --
            `~/.claude/CLAUDE.md § Git`. The guard cannot check it without
            making its verdict depend on the machine it runs on, and CI has no
            such file. Reported per token, never silently dropped.
  unshaped  every other path-like run. This is the scope boundary, and
            `scripts/<name>` is deliberately on the far side of it: a survey
            found eleven mentions that all resolve, but a twelfth --
            `scripts/repos-helper.sh` in closing-campaign's rationale -- names a
            hypothetical file under a *campaign* directory to explain what a
            `*/runtime*` prune pattern would hide. It is backticked exactly like
            the other eleven, so no lexical rule separates them, and an
            existence check over this shape reports a false dangling. Renaming a
            base script is also self-correcting in a way these four shapes
            are not: campaign-primitives derives its inventory from the
            filesystem, so a rename shows up there without anyone editing prose.

WHAT IT DOES NOT CATCH

A pointer written as prose rather than as a path -- "the launching reference",
"the section on merge conditions". Catching that needs judgement about what a
sentence means. This is a floor, not a fence: it stops the pointer that breaks
because something it names was renamed, which is how every one of these broke.

EXIT

0 clean, and a two-line summary of what was read either way. 2 with one line
per dangling reference. 3 when any token or file was undecided, whether or not
something also dangled, because a reading that did not complete is not a
verdict. Under the installed pre-commit hook every non-zero status blocks, so
an undecided token stops the commit without being called a finding.

Usage: scripts/check-cross-references.py [--staged] [--list] [<path> ...]
"""
import re
import subprocess
import sys
from pathlib import Path

# A path-like run: at least one slash, and the class carries `<`, `>` and `*` on
# purpose so a template is *seen and classified* rather than silently truncated
# to the real-looking prefix in front of its placeholder. Without them
# `assets/agents/<kind>.md` would tokenize as `assets/agents/`, which exists,
# and the guard would report a resolved reference nobody wrote.
RUN = re.compile(r"[A-Za-z0-9._<>*-]*/[A-Za-z0-9._/<>*-]*")

# Trailing sentence punctuation is not part of a path. `/` is kept: it is how a
# reference says "directory".
TRAILING = ".,;:!?)]}\"'`"

SECTION = re.compile("§")

# The qualifier of a `§`: a markdown path written just before it, backticked or
# bare, with punctuation and whitespace allowed between. `~/.claude/CLAUDE.md §
# Git` has no backticks; ``AGENTS.md`, § Review` has a comma.
QUALIFIER = re.compile(r"(?P<path>[~A-Za-z0-9._/-]+\.md)`?[\s,;:]*$")

ATX = re.compile(r"^ {0,3}(?P<hashes>#{1,6})\s+(?P<text>.*?)\s*#*\s*$")
FENCE = re.compile(r"^ {0,3}(?P<run>`{3,}|~{3,})(?P<info>.*)$")
BOLD = re.compile(r"\*\*(?P<text>.+?)\*\*", re.S)

DEFAULT_TARGET = "AGENTS.md"

# Which shape a run belongs to, by prefix. Order matters only in that the two
# absolute prefixes are tested before the two relative ones.
ABSOLUTE_PREFIXES = (".claude/skills/", "spec/campaign/")
RELATIVE_PREFIXES = ("references/", "assets/")
SCRIPT_PREFIX = "scripts/"
SCRIPT_SUFFIXES = (".py", ".sh")


def repo_root():
    """The worktree being committed, never the shared checkout.

    --show-toplevel, not --git-common-dir: the guard judges the files and index
    of the checkout making the commit. Resolving to the main checkout would
    judge a worktree's commit against somebody else's tree. (Where the hook
    *lives* is the other question, and install-hooks answers it the other way.)
    """
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def tracked(root):
    """Every tracked path, repo-root-relative.

    `git ls-files` prints paths relative to the cwd, so a run from a
    subdirectory would silently scan a fraction of the tree and report clean.
    The -C root pins it.
    """
    out = subprocess.run(
        ["git", "-C", root, "ls-files", "-z"],
        capture_output=True, text=True, check=True,
    )
    return [p for p in out.stdout.split("\0") if p]


class Tree:
    """The tree under judgement: the index under --staged, the worktree else.

    Both readings go through here so that a target file is read from the same
    place as the file citing it. Reading a citation from the index and its
    target from disk would let a rename be staged and pass against the old tree.
    """

    def __init__(self, root, staged):
        self.root = Path(root)
        self.staged = staged
        self._names = None

    def names(self):
        """The set of paths that exist, for the filesystem-resolved shapes."""
        if self._names is None:
            self._names = set(tracked(str(self.root)))
        return self._names

    def exists(self, rel):
        """Does `rel` name a file or a directory in the tree under judgement?

        Under --staged the index is the tree, so existence is membership in the
        tracked set; a directory is any prefix of a tracked path. On the
        worktree it is the filesystem, which also sees untracked files -- and
        that is right, because a reference to a file added in this same commit
        must resolve.
        """
        rel = rel.rstrip("/")
        if not rel:
            return False
        if self.staged:
            names = self.names()
            return rel in names or any(n.startswith(rel + "/") for n in names)
        p = self.root / rel
        return p.exists()

    def read(self, rel):
        """The text of `rel`, or None when it cannot be read.

        None is "I could not look" and every caller must treat it as such. It is
        never an empty document.
        """
        if self.staged:
            out = subprocess.run(
                ["git", "-C", str(self.root), "show", f":{rel}"],
                capture_output=True, check=False,
            )
            if out.returncode != 0:
                return None
            return out.stdout.decode("utf-8", errors="replace")
        p = self.root / rel
        if not p.is_file():
            return None
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None


def headings(text):
    """Every ATX heading's text, fences skipped.

    A `# comment` inside a ```sh fence is not a heading, and AGENTS.md is full
    of them. Counting one would make a citation of it resolve.

    Each heading is offered in two spellings, with its inline backticks and
    without: `## The `## Repos` list` is cited either way, and neither spelling
    is more correct than the other.
    """
    out = set()
    inside = None
    for line in text.splitlines():
        fence = FENCE.match(line)
        if inside is not None:
            if (fence and fence.group("run")[0] == inside[0]
                    and len(fence.group("run")) >= len(inside)
                    and not fence.group("info").strip()):
                inside = None
            continue
        if fence:
            inside = fence.group("run")
            continue
        m = ATX.match(line)
        if m:
            t = m.group("text").strip()
            if t:
                out.add(t)
                out.add(t.replace("`", ""))
    return out


def paragraphs(text):
    """(offset, joined text) per paragraph, newlines collapsed to spaces.

    These files are hard-wrapped, so a citation's name and a bold span both wrap
    mid-phrase. Matching line by line would miss the second half of either. A
    blank line ends the join: a paragraph break is the one boundary a wrapped
    phrase never crosses.
    """
    out, buf, start, pos = [], [], 0, 0
    for line in text.splitlines(keepends=True):
        if line.strip():
            if not buf:
                start = pos
            buf.append(line.rstrip("\n"))
        elif buf:
            out.append((start, " ".join(buf)))
            buf = []
        pos += len(line)
    if buf:
        out.append((start, " ".join(buf)))
    return out


def bold_spans(text):
    """Every `**...**` span, per paragraph so a span cannot swallow a document.

    Only read to answer U1 -- *is this citation pointing at prose rather than a
    heading* -- and never to resolve anything.
    """
    out = set()
    for _, para in paragraphs(text):
        for m in BOLD.finditer(para):
            t = m.group("text").strip()
            if t:
                out.add(t)
                out.add(t.replace("`", ""))
    return out


def longest_prefix(after, candidates):
    """The longest candidate that prefixes `after` and ends on a word boundary.

    The boundary is the load-bearing half. `The binding` prefixes the string
    `The bindings say`, so a bare startswith resolves a broken citation onto a
    section it does not name; requiring the next character to be a non-word
    character rejects that while still accepting `The binding), so this step`
    and `The campaign issue body.` and `ID, directory, branch`.
    """
    best = None
    for c in candidates:
        if not after.startswith(c):
            continue
        rest = after[len(c):]
        if rest and (rest[0].isalnum() or rest[0] == "_"):
            continue
        if best is None or len(c) > len(best):
            best = c
    return best


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def skill_root(rel):
    """The skill directory a path lives under, as `a/b/c`, or None.

    `.claude/skills/<skill>/` is the root a relative `references/x.md` resolves
    against -- not the citing file's own directory, which is why
    `references/launching.md` may correctly name `assets/sub-issue.md`.
    """
    # Exactly `.claude/skills/<skill>`: three segments, so two slashes. A
    # deeper ancestor is a subdirectory of the skill, and resolving against it
    # makes `references/launching.md` look for `references/assets/sub-issue.md`.
    parts = rel.split("/")
    for i in range(len(parts) - 1, 0, -1):
        d = "/".join(parts[:i])
        if d.startswith(".claude/skills/") and d.count("/") == 2:
            return d
    return None


class Report:
    """Every token lands in exactly one bucket, and every bucket is printed."""

    def __init__(self):
        self.resolved = []
        self.dangling = []
        self.undecided = []
        self.external = []
        self.template = []
        self.unshaped = []

    def counts(self):
        return {
            "resolved": len(self.resolved),
            "dangling": len(self.dangling),
            "undecided": len(self.undecided),
            "external": len(self.external),
            "template": len(self.template),
            "unshaped": len(self.unshaped),
        }


def check_sections(rel, text, tree, report):
    """S1: every `§` in one document."""
    for m in SECTION.finditer(text):
        n = line_of(text, m.start())
        before = text[:m.start()]
        # Back to the paragraph start, joined, so a qualifier on the previous
        # line is seen: `(`AGENTS.md`\n§ The binding)` is one sentence.
        cut = before.rfind("\n\n")
        before_para = " ".join(before[cut + 2 if cut >= 0 else 0:].split())
        after = text[m.end():]
        cut = after.find("\n\n")
        after_para = " ".join(after[:cut if cut >= 0 else len(after)].split())

        q = QUALIFIER.search(before_para)
        target = q.group("path") if q else DEFAULT_TARGET
        if target.startswith("~") or target.startswith("/"):
            report.external.append(
                (rel, n, f"§ {after_para[:60]}",
                 f"qualified by {target}, which is outside this repository"))
            continue

        # A `./` prefix, and only that. `lstrip("./")` strips a character SET,
        # so it eats the leading dot of `.claude/skills/...` and sends the read
        # to a path that has never existed.
        if target.startswith("./"):
            target = target[2:]
        target_text = tree.read(target)
        if target_text is None:
            report.undecided.append(
                (rel, n, f"§ {after_para[:60]}", "U3",
                 f"cannot read the target {target}"))
            continue

        name = longest_prefix(after_para, headings(target_text))
        if name is not None:
            report.resolved.append((rel, n, f"§ {name}", f"{target} heading"))
            continue

        prose = longest_prefix(after_para, bold_spans(target_text))
        if prose is not None:
            report.undecided.append(
                (rel, n, f"§ {prose}", "U1",
                 f"names bold prose in {target}, not a heading -- the guard "
                 f"has no rule for citing prose"))
            continue

        report.dangling.append(
            (rel, n, f"§ {after_para[:60]}",
             f"{target} has no heading this name prefixes"))


def check_paths(rel, text, tree, report):
    """S2, S3, S4 and S5: every path-like run in one document."""
    root = skill_root(rel)
    for m in RUN.finditer(text):
        raw = m.group(0)
        tok = raw.rstrip(TRAILING)
        if not tok or "/" not in tok:
            continue
        n = line_of(text, m.start())

        # `$BASE/` IS THE ONE VARIABLE THIS TREE PRESCRIBES for the base root
        # (AGENTS.md § The three planes), and every skill spells its commands
        # with it -- 17 citations do. `RUN` cannot hold a `$`, so what arrives
        # here is `BASE/...`, which matched no prefix and fell into `unshaped`:
        # the shapes below were checking 121 references while 17 script paths a
        # session is told to RUN went unchecked, including the one #227's own
        # sweep had just repaired. Stripped before shaping, so the same rules
        # decide it.
        if tok.startswith("BASE/"):
            tok = tok[len("BASE/"):]

        if "<" in tok or ">" in tok or "*" in tok:
            report.template.append((rel, n, tok, "names a form, not a file"))
            continue

        if tok.startswith(ABSOLUTE_PREFIXES):
            shape = "S2" if tok.startswith(".claude/") else "S3"
            if tree.exists(tok):
                report.resolved.append((rel, n, tok, f"{shape}, tree root"))
            else:
                report.dangling.append(
                    (rel, n, tok, f"{shape}: nothing at this path in the tree"))
            continue

        if tok.startswith(SCRIPT_PREFIX) and tok.endswith(SCRIPT_SUFFIXES):
            roots = [""] + ([root] if root else [])
            where = [r for r in roots
                     if tree.exists(f"{r}/{tok}" if r else tok)]
            if where:
                report.resolved.append(
                    (rel, n, tok, f"S5, under {where[0] or 'tree root'}"))
            else:
                report.dangling.append(
                    (rel, n, tok,
                     "S5: nothing at this path under the tree root"
                     + (f" or under {root}" if root else "")))
            continue

        if tok.startswith(RELATIVE_PREFIXES):
            if root is None:
                report.undecided.append(
                    (rel, n, tok, "U2",
                     "a relative skill path in a file inside no skill: it "
                     "names no root to resolve against"))
                continue
            if tree.exists(f"{root}/{tok}"):
                report.resolved.append((rel, n, tok, f"S4, under {root}"))
            else:
                report.dangling.append(
                    (rel, n, tok, f"S4: nothing at {root}/{tok}"))
            continue

        report.unshaped.append((rel, n, tok, "no shape rule claims it"))


def main(argv):
    args = argv[1:]
    staged = "--staged" in args
    show = "--list" in args
    given = [a for a in args if not a.startswith("--")]

    root = repo_root()
    tree = Tree(root, staged and not given)
    if given:
        # Given paths are taken as-is so a fixture can be checked in place; they
        # are still resolved against the repository root, which is what every
        # shape resolves against.
        paths = []
        for a in given:
            p = Path(a).resolve()
            try:
                paths.append(str(p.relative_to(Path(root).resolve())))
            except ValueError:
                print(f"check-cross-references: {a} is outside {root}",
                      file=sys.stderr)
                return 3
    else:
        # `.als` IS A SOURCE, not only a target. In this repository the model
        # files ARE the spec and their comments are its prose, so a citation
        # there is as load-bearing as one in a document -- and #227 left a
        # retired script path standing in `github/system.als` that a
        # markdown-only sweep could not see. Three of these files cite a
        # heading with `§` as well, and those resolve too.
        paths = [p for p in tracked(root)
                 if p.endswith((".md", ".markdown", ".als"))]

    report = Report()
    unreadable = []
    for rel in sorted(paths):
        text = tree.read(rel)
        if text is None:
            # Under --staged a path absent from the index is being deleted, and
            # that is not an absence to refuse over. A path given by hand, or a
            # tracked file the worktree cannot open, is U3.
            if staged and not given:
                continue
            unreadable.append(rel)
            report.undecided.append(
                (rel, 0, "(the file itself)", "U3", "cannot read this file"))
            continue
        check_sections(rel, text, tree, report)
        check_paths(rel, text, tree, report)

    c = report.counts()
    source = "index (--staged)" if tree.staged else "working tree"
    checked = c["resolved"] + c["dangling"] + c["undecided"]
    print(f"check-cross-references: {len(paths)} file(s) under "
          f"{root}, read from the {source}")
    print(f"  {checked} reference(s): {c['resolved']} resolved, "
          f"{c['dangling']} dangling, {c['undecided']} undecided "
          f"| {c['external']} external, {c['template']} template, "
          f"{c['unshaped']} unshaped")

    for rel, n, tok, why in report.dangling:
        print(f"DANGLING\t{rel}:{n}\t{tok}\t{why}")
    for rel, n, tok, code, why in report.undecided:
        print(f"UNDECIDED\t{rel}:{n}\t{tok}\t{code}: {why}")
    if show:
        for rel, n, tok, why in report.external:
            print(f"external\t{rel}:{n}\t{tok}\t{why}")
        for rel, n, tok, why in report.template:
            print(f"template\t{rel}:{n}\t{tok}\t{why}")
        for rel, n, tok, why in report.unshaped:
            print(f"unshaped\t{rel}:{n}\t{tok}\t{why}")
        for rel, n, tok, why in report.resolved:
            print(f"resolved\t{rel}:{n}\t{tok}\t{why}")

    if report.undecided:
        print(
            f"\ncheck-cross-references: {len(report.undecided)} token(s) or "
            f"file(s) this guard has no rule for, listed above as UNDECIDED.\n"
            f"That is the guard's own failure, not a verdict: it did not decide "
            f"they resolve\nand it did not decide they dangle. Give the shape a "
            f"rule, or write the pointer\nin one of the four shapes the header "
            f"lists. Exit 3, which the pre-commit hook\ntreats as a refusal.",
            file=sys.stderr,
        )
        if report.dangling:
            print(f"({len(report.dangling)} reference(s) also dangle; both "
                  f"lists are above.)", file=sys.stderr)
        return 3
    if report.dangling:
        print(
            f"\ncheck-cross-references: {len(report.dangling)} reference(s) "
            f"name something this tree does not hold.\nFix the name, or move "
            f"the thing back. Each line above says which file cites it,\nwhich "
            f"line, and what was searched.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
