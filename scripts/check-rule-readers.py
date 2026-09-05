#!/usr/bin/env python3
"""Refuse a hand-rolled copy of a rule that one of this repository's scripts owns.

AGENTS.md and several script docstrings each declare that some reading -- the
liveness comparison, the `## Repos` parse, the settlement verdict, the
local-only-work reading -- lives in exactly one script, and that a second reader
written by hand somewhere else is what drifts. This is the authoring-side second
reader that enforces it: one check over every rule rather than one guard per
script, because the rules share a single failure mode and a single fix.

WHAT IT DOES NOT CATCH

A re-implementation carrying no marker of the rule it copies. A Python loop that
reads a README line by line and keeps the ones with a slash in them is a `##
Repos` parse, and nothing in it names the list; catching that needs judgement
about what a block of code means, which is the thing a grep-shaped guard cannot
have and should not pretend to. So the guard is a floor, not a fence: it stops
the copy somebody makes by pasting, which is how second readers actually get
written, and it does not stop one somebody sets out to write.

Stated here rather than fixed: widening the forms to match a paraphrase is how
a guard starts firing on prose instead of code.

The `campaign-session-alive` form went with the pid reading it guarded.
Liveness is `herdr agent list` now, and no script here compares a process name,
so a process-name selector in a markdown code block is somebody else's business
and this refuses nothing on account of it. The claim that form kept true no
longer exists to be kept.

WHAT IT READS

Code blocks -- fenced, or under a four-space or tab indent -- and only in
tracked files outside scripts/. That line is the whole design. A deliberate
mention of a retired form lives in prose as inline code -- a document may
explain at length why some command is the wrong one, and must go on being able
to say so. A
dangerous copy lives in a code block, because that is what makes it
copy-pasteable, and copy-pasted is the only way a second reader gets written.
Firing only inside code separates the two with no allowlist to maintain and no
judgement about what a paragraph means. Both shapes are read for the same
reason and both can be exempted the same way, so neither is the special case.

A code block that must hold a form anyway -- fenced or indented -- is exempted
by an HTML comment on the line above it:

    <!-- unguarded: <token> -- <why> -->

Invisible in rendered markdown, greppable, and it names the *form* it exempts so
a reader can check the claim. `<token>` is a FORM's token, one per form, which is
not always the name of the script that now holds it -- the finding prints both.
The exemption is per block, not per file, so it does not widen as the file grows,
and it is spent on the *next* block whichever shape that block has.

EXIT

Every run opens by saying how many files it read, from where, and whether it read
the working tree or the index -- because a clean tree and a tree nobody looked at
print the same nothing otherwise, and the second is what a wrong checkout or an
empty file list gives.

0 when nothing was found. 1 with one line per finding: the file, the line, the
script to call, the token to exempt, and the source line.

A path that is tracked but has no content to judge -- being deleted, or unmerged
in the index -- is *counted apart and named*. It is never a violation site, since
nothing holding no content can hold a copied rule. The count printed is what was
read, not what was globbed.

A path whose content the run *could not read* -- permission denied, a directory
in its place -- is a different answer and gets its own line and its own refusal.
It may hold exactly the rule this guard looks for, so folding it into either the
examined files or the harmless empty ones is the silent downgrade this guard
exists to stop. Exit is 1 whenever any file was unreadable, found or not.

That is a working-tree read, and it is the ad-hoc run it protects. Under
`--staged` -- the installed invocation -- content comes from the index by
`git show :<path>`, which never touches disk, so a permission bit or a directory
swapped in cannot make the read fail: the index copy is read and scanned like
any other. Nothing goes unexamined there; `broken` simply cannot arise. Said
here because a reader meeting the paragraph above would otherwise take the hook
to be the thing it guards.

Usage: scripts/check-rule-readers.py [<path> ...]      (default: every tracked file)
"""
import re
import subprocess
import sys
from pathlib import Path

# Each form is an *executable* shape, never a topic. `## Repos` in an error
# message is a mention; `grep '## Repos'` is a second reader. The difference is
# whether a tool is being pointed at the thing.
#
# Four fields, and the first two are deliberately not one string.
#
#   token  what an exemption names. One per FORM, always, whatever script the
#          form now lives in.
#   path   the script to call instead, printed in the finding.
#
# They were one field while every form had a script to itself. Merging three
# readers into `campaign-tracker` would have collapsed three tokens into one --
# and `EXEMPT` matches `[\w-]+` with no spaces, so a single
# `<!-- unguarded: campaign-tracker -->` would then have silenced the campaign issue
# survey, the index read and the settlement verdict together, with nothing
# reporting that two more forms had been exempted than the author named.
# Splitting the fields keeps the exemption as granular as the form, and keeps
# the finding pointing at a script that exists.
#
# The extension went on `path` and not on `token` when #105 gave every script
# one. `path` is a path -- it is printed as `scripts/<path>` and a reader runs
# it -- while `token` is the form's name, and four of them name scripts that no
# longer exist as files at all. A token also has a second reader nobody can
# grep: every `<!-- unguarded: ... -->` already written in the tree, and in a
# tree this check does not see. Changing one silently turns those exemptions
# into non-matches, and a non-matching exemption is reported, not honoured.
FORMS = [
    (
        "campaign-anchors",
        "campaign-tracker.py",
        # The open-campaign issue survey: a `gh issue list` on this tracker asking for
        # the fields the classification reads.
        re.compile(r"\bgh\b[^|;&]*\bissue\s+list\b[^|;&]*"
                   r"(-l\s+[\"']?campaign|--label\s+[\"']?campaign|--json[^|;&]*parent)"),
        "the open-campaign issue survey",
    ),
    (
        "campaign-bound",
        "campaign-tracker.py",
        # The binding reading: the campaign issue's `bound:` LABEL, and the
        # machine it names compared against this one's. #176 moved the binding
        # off a `BOUND` comment onto a label, so the comment shapes went with
        # it -- a hand-rolled comment read is no longer a second reader of
        # anything, because nothing reads comments any more.
        #
        # Both the reading AND the write, which the comment form could not
        # cover: `campaign-tracker bind` is the one writer now, so a hand-rolled
        # `gh issue edit --add-label bound:...` in a document is a second WRITER
        # of the rule, which is worse than a second reader. Under the comment
        # this was impossible to catch -- two blocks in the tree legitimately
        # posted one.
        #
        # Neither `hostname` alone NOR a bare labels read is the form, and both
        # exclusions are deliberate. A block may name this host without binding
        # anything -- the close comment names the host it is closing from -- so
        # a bare `hostname` cannot separate the two. And a labels read is
        # not the binding either: two skills read `--json labels` to classify a
        # campaign issue, which is a different question, and `campaign-tracker
        # bound`'s own request is character-for-character the same call. What
        # only the BINDING does is name the `bound:` prefix, or compare a host
        # name against something; hence the spaced `=` and `==`, which a
        # `HOST=$(hostname -s)` assignment does not carry.
        # A TOOL must be named, and `re.` and `==` are not tools: both were in
        # a first cut of this and both fired on ordinary code -- `a == b` beside
        # a comment mentioning `bound:`, and any `re.sub` on a line whose string
        # holds it. A form that matches a comparison operator matches prose that
        # happens to sit near one, and this file's whole design is that a
        # finding points at code.
        re.compile(r"(\bgrep\b|\bsed\b|\bawk\b|\bjq\b|--jq|startswith"
                   r"|\brg\b)[^|;&]*bound:"
                   r"|\bgh\b[^|;&]*\b(issue\s+edit|label)\b[^|;&]*bound:"
                   r"|(==|\s=\s)[^|;&]*\bhostname\b|\bhostname\b[^|;&]*(==|\s=\s)"
                   r"|\bgethostname\b|\bplatform\.node\b"),
        "the binding reading or write",
    ),
    (
        "campaign-subtasks",
        "campaign-tracker.py",
        # The sub-issue index read, in either pagination form.
        re.compile(r"\bgh\b[^|;&]*\bapi\b[^|;&]*sub_issues"
                   r"|sub_issues[^|;&]*--paginate"),
        "the sub-issue index read",
    ),
    (
        "campaign-repos",
        "campaign-repos.py",
        # `## Lands in` JOINED THE CLAIM in kalaluthien/campaign-base#217: it is
        # the same vocabulary read by the same file, so a hand-rolled parse of
        # it is the same defect and belongs under the same owner rather than in
        # a row of its own.
        re.compile(r"(\bgrep\b|\bsed\b|\bawk\b|\brg\b|\bjq\b|--jq|re\.|readlines|splitlines)"
                   r"[^|;&]*(##\s*Repos|##\s*Lands in|owner/repo)"
                   r"|(##\s*Repos|##\s*Lands in|owner/repo)[^|;&]*(\bgrep\b|\bawk\b|\bjq\b)"),
        "the ## Repos / ## Lands in parse",
    ),
    (
        "campaign-settlement",
        "campaign-tracker.py",
        # The API field names only, not the words "not planned" / "not-planned"
        # a disposition table writes as prose: matching those false-fires on
        # prose that merely mentions a verdict rather than computing one.
        re.compile(r"\b(mergedAt|merged_at|stateReason|state_reason)\b"),
        "the settlement verdict",
    ),
    (
        "campaign-local-work",
        "campaign-local-work.py",
        re.compile(r"\bgit\b[^|;&]*\b(status|worktree\s+list|for-each-ref|stash\s+list)\b"
                   r"|\bgit\b[^|;&]*\bdiff\b[^|;&]*--quiet"
                   r"|\bgit\b[^|;&]*\bbranch\b[^|;&]*--no-merged"),
        "the local-only-work reading",
    ),
    (
        "campaign-name-session",
        "campaign-name-session.py",
        re.compile(r"herdr\s+agent\s+rename\b|agent\s+prompt\b[^|;&]*/rename"),
        "the session-name shape",
    ),
]


# An opener is up to three spaces of indent then three or more backticks or
# tildes. A closer is the same character, at least as many of them, and nothing
# after it -- so a ``` line inside a ```` block, or a `~~~` line inside a ```
# block, is content rather than a closer. Getting this wrong ends the block
# early and everything after it stops being scanned, which is a silent miss.
OWNERS = frozenset(token for token, _, _, _ in FORMS)

FENCE = re.compile(r"^ {0,3}(?P<run>`{3,}|~{3,})(?P<info>.*)$")
EXEMPT = re.compile(r"<!--\s*unguarded:\s*(?P<owner>[\w-]+)\s*--")
# Anything that says `unguarded:` is an attempt at an exemption. Matching it
# loosely is what lets a malformed one be *reported* rather than skipped: the
# strict form above takes `[\w-]+`, so a prose owner -- `AGENTS.md § The session
# name`, which is what a person writes first -- matches nothing at all, and
# without this the line would simply not be an exemption and the fence would go
# on being flagged with no hint that anything had been read and rejected.
EXEMPT_LOOSE = re.compile(r"<!--\s*unguarded:\s*(?P<owner>.*?)\s*(?:--\s|-->)")

# A line indented four or more spaces renders as code too, so it carries the
# same copy-paste hazard as a fence. Only lines that match a FORM are reported,
# and no FORM matches prose, so scanning these costs no false positives.
INDENTED = re.compile(r"^(\t| {4,})\S")


def tracked():
    """Every tracked markdown path outside scripts/, repo-root-relative.

    `git ls-files` prints paths relative to the *cwd*, so a run from a
    subdirectory silently scans a fraction of the tree and reports clean. The
    -C root pins it.
    """
    # --show-toplevel, not --git-common-dir: in a linked worktree the guard must
    # judge *that* worktree's files and index, because that is what is being
    # committed. Resolving to the shared checkout makes a worktree's commit be
    # judged against somebody else's tree, and under --staged against an index
    # it never wrote. (Where the hook *lives* is the other question, and that
    # one is --git-common-dir; install-hooks answers it there.)
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    out = subprocess.run(
        ["git", "-C", root, "ls-files", "-z"],
        capture_output=True, text=True, check=True,
    )
    return root, [p for p in out.stdout.split("\0") if p]


def content(root, path, staged):
    """The text to judge: the index's copy under --staged, the file's otherwise.

    A pre-commit hook must read what is about to be committed. Reading the
    working tree instead lets a violation be staged, reverted on disk, and
    committed clean -- and makes an unstaged deletion of any tracked file crash
    the hook for every commit.
    """
    if staged:
        out = subprocess.run(
            ["git", "-C", root, "show", f":{path}"],
            capture_output=True, check=False,
        )
        if out.returncode != 0:
            return None          # not in the index: being deleted, or unmerged
        return out.stdout.decode("utf-8", errors="replace")
    f = Path(root) / path
    if not f.exists():
        return None
    return f.read_text(encoding="utf-8", errors="replace")


def findings(text):
    """Yield (line number, token, path, what, source line) for one document.

    `path` is empty for the malformed-exemption finding, which names no form."""
    inside = None            # the opener's run, while a fence is open
    exempted = None          # owner exempted for the open fence
    pending = None           # exemption seen, waiting for its fence
    carry, carry_n = "", None   # a shell continuation, joined before matching

    def scan(start, joined, exempted):
        # `token`, never `path`: two forms that now live in one script keep two
        # exemptions, so silencing one does not silence its neighbour.
        for token, path, form, what in FORMS:
            if form.search(joined) and token not in (exempted or frozenset()):
                yield start, token, path, what, joined.strip()[:160]

    for n, line in enumerate(text.splitlines(), 1):
        fence = FENCE.match(line)
        if inside is not None:
            run = fence.group("run") if fence else ""
            closes = (
                fence is not None
                and run[0] == inside[0]
                and len(run) >= len(inside)
                and not fence.group("info").strip()
            )
            if closes:
                # A continuation left open at the end of a run is scanned, not
                # dropped: the trailing backslash is a typo, not an exemption.
                yield from scan(carry_n, carry, exempted) if carry else ()
                carry, carry_n = "", None
                inside, exempted = None, None
                continue
            code = True
        elif fence:
            yield from scan(carry_n, carry, exempted) if carry else ()
            carry, carry_n = "", None
            inside, exempted, pending = fence.group("run"), pending, None
            continue
        elif INDENTED.match(line):
            # An indented line is code, so it is scanned and never read as an
            # exemption: CommonMark makes it literal content, and reading a
            # marker there let a block exempt itself from the inside -- the
            # mirror of `an exemption inside an open fence exempts nothing`.
            if pending is not None:
                # An exemption is spent on the next code block of either shape.
                exempted, pending = pending, None
            code = True
        else:
            marker = EXEMPT.search(line)
            loose = EXEMPT_LOOSE.search(line)
            if loose and not (marker and marker.group("owner") in OWNERS):
                # Silence here would be the guard's own failure mode: the
                # exemption is read, rejected, and the fence goes on being
                # reported with nothing saying why. `[\w-]+` does not match a
                # prose owner with dots or spaces, which is what a person writes
                # first.
                yield (n, loose.group("owner") or "(empty)", "",
                       "an exemption naming no script", line.strip())
                pending = None
                continue
            if marker:
                # Two exemptions in a row both apply: a fence may hold forms
                # belonging to more than one script.
                pending = (pending or frozenset()) | {marker.group("owner")}
                continue
            code = False
            if line.strip():
                # An exemption marks the next code block, not prose -- and the
                # same line ends an indented run, so the exemption it carried
                # dies with it rather than leaking into the next block.
                pending, exempted = None, None
        if not code:
            yield from scan(carry_n, carry, exempted) if carry else ()
            carry, carry_n = "", None
            continue
        # A shell continuation is one command, so it is matched as one; scanning
        # line-at-a-time would miss a form split across a trailing backslash.
        joined = (carry + " " + line.strip()) if carry else line
        start = carry_n or n
        if line.rstrip().endswith("\\"):
            carry, carry_n = joined.rstrip()[:-1].rstrip(), start
            continue
        carry, carry_n = "", None
        yield from scan(start, joined, exempted)
    yield from scan(carry_n, carry, exempted) if carry else ()


def main(argv):
    staged = "--staged" in argv[1:]
    given = [a for a in argv[1:] if a != "--staged"]
    root, all_tracked = tracked()
    if given:
        paths, root = given, "."
    else:
        paths = all_tracked
    paths = [
        p for p in paths
        if p.endswith((".md", ".markdown")) and not p.startswith("scripts/")
    ]
    # Said before any verdict and on every run, as the sibling guards do.
    where = "the index" if (staged and not given) else "the working tree"

    # Read every file first, so the announcement precedes any finding: a
    # finding above the count reads as the whole of what the run did.
    texts, unread, broken = [], [], []
    for p in sorted(paths):
        try:
            text = content(root, p, staged and not given)
        except OSError as exc:
            # Distinct from `unread`: this path has content and the run failed
            # to see it, so it cannot be reported as holding nothing.
            broken.append((p, exc.strerror or exc))
            continue
        if text is None:
            # Tracked, but nothing to judge: staged for deletion, or unmerged.
            # Not a violation, and not an examined file either.
            unread.append(p)
        else:
            texts.append((p, text))

    print(f"check-rule-readers: {len(texts)} markdown file(s) under {root}, "
          f"read from {where}")
    for p in unread:
        print(f"  unread: {p} (no content in {where})")
    for p, why in broken:
        print(f"  unreadable: {p} ({why})")

    found = 0
    for p, text in texts:
        for n, token, path, what, src in findings(text):
            found += 1
            if what == "an exemption naming no script":
                print(f"{p}:{n}: {what}: `{token}` is not one of "
                      + ", ".join(sorted(OWNERS)) + f": {src}")
            else:
                # The path is what to call; the token is what to exempt. Both,
                # because a finding naming only one sends half the readers to
                # the wrong edit.
                print(f"{p}:{n}: {what} belongs to scripts/{path} "
                      f"(exempt with `{token}`): {src}")
    if found:
        print(
            f"\ncheck-rule-readers: {found} hand-rolled reading(s) of a rule a "
            f"script owns.\nCall the script, or exempt the fence with a "
            f"`<!-- unguarded: <owner> -- <why> -->` line above it.",
            file=sys.stderr,
        )
    if broken:
        print(
            f"\ncheck-rule-readers: {len(broken)} file(s) could not be read, so "
            f"this run cannot say they hold no hand-rolled reading. Fix the read "
            f"-- see `unreadable` above -- and re-run.",
            file=sys.stderr,
        )
    if found or broken:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
