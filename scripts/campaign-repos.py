#!/usr/bin/env python3
"""Read the `## Repos` list of a campaign README or campaign issue body.

    scripts/campaign-repos.py <path>

The one reader of that list, and the one statement of what it refuses. AGENTS.md
used to enumerate these and no longer does, which left the enumeration alive only
as exit strings in the code below.

  no `## Repos` heading       the list is not there at all, and a missing list is
                              not an empty one.
  a malformed line under it   anything that is not `- owner/repo`, `- none`, or
                              `- owner/repo (installed: <path>, apply: <cmd>)`,
                              which is also what a surviving `<owner/repo>`
                              placeholder is. Skipping it silently made a list
                              written `* owner/repo` read as empty.
  a malformed marker          the bracket after a repository names a key that
                              is not `installed` or `apply`, names one twice,
                              carries `apply` with no `installed`, or an
                              `installed` path that is not absolute or
                              `~`-rooted -- a relative one resolves against
                              whatever the reader's cwd is.
  an empty list               indistinguishable from a list a bad write dropped,
                              and this list is the only copy of the repository
                              index the close does not delete.
  a mixed list                `- none` beside a repository. Nothing in it says
                              whether `none` is a sentinel somebody forgot or a
                              repository the list means to name, and neither
                              reading can be acted on.
  colliding checkouts         two entries whose checkout directory `repos/<name>/`
                              is the same, so the second acquire overwrites the
                              first without a word.
  the base                    `## Repos` lists the MEMBER repositories a campaign
                              clones; the base reaches its campaign directory by
                              its own route, so a list naming it would acquire a
                              second checkout. Prose said so in three files and
                              no reader enforced it (#205).

THE INSTALLED MARKER (kalaluthien/campaign-base#239). A repository that is
INSTALLED on this machine -- checked out where it is used, `~/.claude` for
dotclaude, the base root for the base -- has two checkouts once a campaign
clones it, and a merge is not finished until the install shows it. The
`## Repos` entry says so with one bracket, `- owner/repo (installed: <path>,
apply: <command>)`, `apply:` optional: the path is where the install is, and
the command is what the install runs after it is fast-forwarded. This file
parses the bracket and nothing else; `scripts/campaign-installed.py` is what
reads the install off disk and reaches it. The base is never listed here, so
its row is a constant in that script and not a line in any list. Every reader
of the LIST still gets `owner/repo` per line: the marker rides on the entry
and changes nothing about what is cloned.

`slug`, `key`, `WRAPPERS`, `BASE_REPO`, `lands_in` and `read_repos` are
exported: the first five for `scripts/campaign-claim.py`, which compares a
sub-issue's `## Lands in` entry to this list -- one reader of what makes two
spellings the same repository, rather than two that agree by both being exact
-- and `read_repos` for `scripts/campaign-installed.py`, which needs the
marker and not only the slug and would otherwise be the second parser.

`lands_in` IS THE SECOND SECTION THIS FILE READS (kalaluthien/campaign-base#217),
and its docstring says why it is not `## Repos` with a count of one. The command
line still reads `## Repos` alone: a sub-issue's destination is read on the claim
path, in process, and never as a subprocess whose refusals a caller re-reads.

scripts/check-rule-readers.py is the second reader that keeps this claim true: it
refuses a commit that stages a `grep`, `sed`, `awk`, `rg`, `jq` or Python
line-reading parse naming `## Repos` or `owner/repo` -- as code in any tracked
markdown outside scripts/, inside a fence or a four-space indent, reading the
index rather than the working tree. A parse naming no tool, a bare `while read`
with a `case`, is outside the claim. It
catches a pasted copy, not a re-implementation that names nothing; see its
header. Removing the guard returns this line to being a hope.

The contract callers hold it to:

  exit 0, one `owner/repo` per line   the list names repositories
  exit 0, no output                   the list is exactly `- none`, so the
                                      campaign has no member repository and a
                                      caller loops zero times without a special
                                      case
  exit 1, one line on stderr          the list is wrong, and the line says how

opening-campaign step 4 runs it and writes `runtime/repos`; step 5 reads that
file. Its passage on adding a repository runs it again before the sync, and
closing-campaign step 4 runs it over the README and over the body GitHub stored.
"""
import re
import sys

REPOS_HEADING = "Repos"
LANDS_HEADING = "Lands in"
NEXT_SECTION = re.compile(r"^## ")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
ITEM = re.compile(r"^- (\S.*)$")
# An entry is `owner/repo` or the sentinel, and the sentinel is spelled exactly.
ENTRY = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
NONE = "none"
# THE INSTALLED MARKER: `owner/repo (installed: <path>, apply: <command>)`. The
# bracket is one, at the end, and its fields are `key: value` split on the
# next ` key:` so a command may hold a comma. `apply` without `installed` is
# refused: a command with nowhere to run is a marker half written.
# One bracket, holding no bracket: a second `(...)` after the first leaves the
# line matching nothing here and refused as a malformed line, where a greedy
# body read `(installed: /a) (apply: b)` as a path and dropped the command.
MARKED = re.compile(r"^(?P<slug>\S+)\s+\((?P<marker>[^()]*)\)$")
MARKER_KEYS = ("installed", "apply")
MARKER_FIELD = re.compile(r"(?:^|,\s*)(installed|apply):\s*")

# THE BASE'S OWN SLUG LIVES HERE because this is the reader that has to refuse
# it, and `scripts/campaign-claim.py` imports it from here rather than keeping a
# second spelling: that file is the only other reader that compares a slug to
# the base, and two copies of a name would drift on the first rename. It cannot
# go the other way -- campaign-claim.py already reads this file, and the pair
# would import in a circle.
BASE_REPO = "kalaluthien/campaign-base"

# WHAT A SLUG IS ALLOWED TO ARRIVE WRAPPED IN. `## Repos` is authored from a
# template and stays strict: `ENTRY` above admits `owner/repo` and nothing else,
# and a list written any other way is refused where it is written. A
# `## Lands in` entry on a sub-issue is prose a person types, and the same
# repository arrives there as `owner/repo`, in backticks, in angle brackets,
# with a trailing slash, with a `.git`, or in another case. Those are one
# repository, and comparing them raw made a scope refusal say "this campaign is
# not for that repository" when the truth was "that line was not read as a slug"
# (kalaluthien/campaign-base#205). `slug` and `key` are the ONE reader of that,
# used by the base check here and by `lands_in` below and its caller. The
# section replaced a `Repository:` keyword line in #217; the leniency did not
# move with it, because what a person types is what it was always about.
#
# ANGLE BRACKETS ARE NOT A WRAPPER, and this is the one entry that has to be
# argued rather than listed: `<owner/repo>` is the sub-issue template's
# PLACEHOLDER, so stripping the brackets would read an unfilled template as a
# repository literally named `owner/repo` and cut a ref for it. A placeholder is
# an absent answer, and it stays one.
WRAPPERS = "`'\" \t"
DOT_GIT = ".git"


def slug(text):
    """The repository this text names, wrappers and a `.git` removed and the
    CASE LEFT ALONE, or None when it names none.

    None is a REFUSAL and never a pass-through: a caller that fell back to the
    raw text on None would restore exactly the raw comparison this replaces.
    Case is left alone because this is what gets printed and passed to `gh` --
    `key` below is the thing to compare with, and the two are separate so that
    a case-folded slug never reaches a reader as the repository's name."""
    s = (text or "").strip().strip(WRAPPERS).rstrip("/")
    if s.lower().endswith(DOT_GIT):
        s = s[:-len(DOT_GIT)]
    s = s.strip("/")
    return s if ENTRY.match(s) else None


def key(text):
    """The comparison key: `slug` case-folded, because GitHub does not tell
    `Web` from `web` and two readers that disagree about that refuse each
    other's repositories. None when the text names no repository."""
    s = slug(text)
    return None if s is None else s.casefold()


def is_base(text):
    """Whether this text names the base, however it was spelled."""
    return key(text) is not None and key(text) == key(BASE_REPO)


def section(text, heading=REPOS_HEADING):
    """The non-blank lines under `## <heading>`, or None when there is none.

    Parameterised by #217, when `## Lands in` joined `## Repos` as the second
    section written in this vocabulary. One walker, because the two sections
    differ in what their entries MEAN and not in how a section is found, and a
    second copy of the walk would be the one that stopped honouring `<!-- -->`
    or the next `## `."""
    want = re.compile(rf"^## {re.escape(heading)}\s*$")
    out, inside = [], False
    for line in COMMENT.sub("", text).splitlines():
        if want.match(line):
            inside = True
            continue
        if inside:
            if NEXT_SECTION.match(line):
                break
            if line.strip():
                out.append(line.rstrip())
    return out if inside else None


def lands_in(text):
    """(entry, why) -- the ONE repository a sub-issue's `## Lands in` names.

    `entry` is the raw entry as written, and `why` is a refusal naming what was
    read; exactly one of the two is None. The caller decides what the entry
    MEANS -- `campaign-claim.py`'s `issue_repo` maps `none` and the base's own
    slug to the base and everything else to a member repository -- because that
    mapping is the claim's question and not this reader's.

    WHY IT IS NOT `## Repos` WITH A COUNT OF ONE (kalaluthien/campaign-base#217).
    The two sections ask different questions of one vocabulary: `## Repos` says
    which repositories a campaign CLONES, a set, and refuses the base, because
    the base reaches its campaign directory by another route; `## Lands in` says
    where ONE sub-issue's work lands, a single value, and the base is its
    commonest answer. A `--one` mode over the first would have to unlearn its
    own base refusal, which is the collision this heading avoids by existing.

    THE ENTRY IS NOT NORMALISED HERE. `slug` is the one reader of what makes two
    spellings the same repository and the caller calls it, so this returns what
    was written and a refusal quotes it verbatim -- a reader that had already
    de-wrapped could not say which of the two diagnoses applied, "that is not a
    repository" or "this campaign is not for it"."""
    lines = section(text, LANDS_HEADING)
    if lines is None:
        return None, (f"no `## {LANDS_HEADING}` heading, so where the work "
                      f"lands is unstated")
    items = []
    for line in lines:
        m = ITEM.match(line)
        if not m:
            return None, (f"malformed line under ## {LANDS_HEADING}: {line}")
        items.append(m.group(1).strip())
    if not items:
        return None, f"the ## {LANDS_HEADING} section is empty"
    if len(items) != 1:
        # A SUB-ISSUE LANDS IN ONE REPOSITORY, and two entries is not a wider
        # sub-issue but an unanswered question: the claim cuts ONE ref, and
        # picking the first would cut it wherever the list happened to be
        # ordered. Work moving two repositories together is two sub-issues, or
        # one whose second repository is named in `## Plan` and claimed there.
        return None, (f"## {LANDS_HEADING} holds {len(items)} entries "
                      f"({', '.join(items)}); a sub-issue lands in one "
                      f"repository, because its claim is one ref")
    entry = items[0]
    # THE SENTINEL IS AS LENIENT AS A SLUG HERE, and exactly here. `## Repos`
    # spells `- none` and nothing else, because that list is authored from a
    # template and refused where it is written; this entry is a person's answer
    # to "where does it land", and `` `none` `` and `None` are that answer. The
    # caller re-tests the sentinel the same way, so a spelling this admits is
    # one it can act on.
    if entry.strip(WRAPPERS).lower() != NONE and slug(entry) is None:
        return None, (f"## {LANDS_HEADING} reads {entry!r}, which is not an "
                      f"owner/repo and not `{NONE}`. It is not a scope "
                      f"question: nothing was compared, because that line does "
                      f"not name a repository")
    return entry, None


def marker(entry):
    """(slug, installed, apply, why) for one entry as written. `installed` and
    `apply` are None on a bare entry; `why` is the refusal and the other three
    are None when the bracket does not read."""
    m = MARKED.match(entry)
    if not m:
        return entry, None, None, None
    slug_, text = m.group("slug"), m.group("marker")
    if slug_ == NONE:
        return None, None, None, (f"malformed marker on {NONE}: the sentinel "
                                  f"names no repository, so nothing is installed")
    fields = {}
    hits = list(MARKER_FIELD.finditer(text))
    if not hits or hits[0].start() != 0:
        return None, None, None, (f"malformed marker on {slug_}: `({text})` "
                                  f"does not open with one of {', '.join(MARKER_KEYS)}")
    for n, h in enumerate(hits):
        end = hits[n + 1].start() if n + 1 < len(hits) else len(text)
        value = text[h.end():end].strip()
        if h.group(1) in fields:
            return None, None, None, (f"malformed marker on {slug_}: "
                                      f"`{h.group(1)}` is given twice")
        if not value:
            return None, None, None, (f"malformed marker on {slug_}: "
                                      f"`{h.group(1)}` has no value")
        fields[h.group(1)] = value
    installed, apply = fields.get("installed"), fields.get("apply")
    if installed is None:
        return None, None, None, (f"malformed marker on {slug_}: `apply` with "
                                  f"no `installed`, so there is nowhere to run it")
    if not (installed.startswith("/") or installed == "~"
            or installed.startswith("~/")):
        return None, None, None, (f"malformed marker on {slug_}: installed path "
                                  f"`{installed}` is not absolute or `~`-rooted, "
                                  f"so it would resolve against the reader's cwd")
    return slug_, installed, apply, None


def read_repos(text):
    """(rows, why) -- the `## Repos` list of one body, each row
    `(owner/repo, installed, apply)` with the last two None on a bare entry.
    `rows` is `[]` for `- none` alone; `why` is the refusal, verbatim what the
    command line prints, and `rows` is None beside it. Pure, so the command
    line and `campaign-installed.py` read one parser and cannot disagree."""
    lines = section(text)
    if lines is None:
        return None, "no `## Repos` heading"

    items = []
    for line in lines:
        m = ITEM.match(line)
        if not m:
            return None, f"malformed line under ## Repos: {line}"
        entry = m.group(1).strip()
        slug_, installed, apply, why = marker(entry)
        if why:
            return None, why
        if slug_ != NONE and not ENTRY.match(slug_):
            # `<owner/repo>` from the template lands here too, and reads as what
            # it is: a line that is neither a repository nor the sentinel.
            return None, f"malformed line under ## Repos: - {entry}"
        entry = slug_
        # THE BASE IS NEVER A MEMBER OF THIS LIST, and until #205 that was
        # prose in three files with no reader. `## Repos` says which
        # repositories to CLONE when a campaign opens; the base reaches
        # `<campaign>/repos/campaign-base/` by its own route, so a list naming
        # it would have step 5 acquire it a second time. The claim path is
        # unaffected either way -- `campaign-claim.py` exempts the base before
        # it reads the list -- so this refusal is the structural gap being
        # closed, not a live break being fixed.
        if is_base(entry):
            return None, (f"`## Repos` names the base ({entry}); it "
                          f"lists the MEMBER repositories a campaign clones, and the"
                          f" base is a member of its own campaign by another route")
        items.append((entry, installed, apply))

    if not items:
        return None, "the ## Repos list is empty"

    repos = [i for i in items if i[0] != NONE]
    if len(repos) != len(items):
        if repos:
            plural = "y" if len(repos) == 1 else "ies"
            return None, (f"`- none` is mixed with {len(repos)} repository"
                          f" entr{plural}; the list is `- none` alone or repositories,"
                          " never both")
        return [], None            # `- none` alone: no repositories, and that is fine

    # Every entry becomes a checkout at repos/<name>/, so two entries ending in
    # the same name are one directory and the second acquire overwrites the
    # first. Case-folded: the filesystem here does not tell `Web` from `web`.
    # `where` and not `key`: `key` is this module's exported reader, and a local
    # of that name shadowed it inside the one function that might come to need
    # it. Latent when a review found it, and a rename is cheaper than the day it
    # is not.
    seen = {}
    for i, _installed, _apply in repos:
        where = i.rsplit("/", 1)[-1].casefold()
        if where in seen:
            if seen[where] == i:
                return None, f"duplicate entry under ## Repos: {i}"
            return None, ("two entries share the checkout directory"
                          f" repos/{i.rsplit('/', 1)[-1]}/: {seen[where]} and {i}")
        seen[where] = i
    return repos, None


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    path = sys.argv[1]
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        sys.exit(f"campaign-repos: cannot read {path}: {e.strerror}")

    rows, why = read_repos(text)
    if why:
        # The two refusals that name the file keep naming it: a heading that is
        # not there and a list that is empty are about the file, where every
        # other refusal quotes the line.
        if why.startswith("no `## Repos` heading") or why.startswith("the ## Repos list is empty"):
            why = f"{why} in {path}"
        sys.exit(f"campaign-repos: {why}")
    if rows:
        print("\n".join(r[0] for r in rows))


# GUARDED, so campaign-claim.py can import `slug`, `key` and `BASE_REPO` without
# running the reader. It used to call `main()` at import time, which is why that
# file ran this one as a subprocess; it still does for the LIST, because the
# refusals above are exit strings and reading them back as a verdict is what
# keeps one reader rather than two.
if __name__ == "__main__":
    main()
