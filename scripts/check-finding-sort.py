#!/usr/bin/env python3
"""Log whether each finding of a REVIEW reads as a defect or a refinement, and refuse nothing.

THE READING `finding-sort` in scripts/jev/readings.json, asked through
scripts/campaign-jev.py. The entry holds the question, its criteria, the
state's fields, the thresholds and the tier; this reads them and writes none
of them. How to ask Jev well in general is the `asking-jev` skill's
`references/`, not this file's.

WHO RUNS IT: scripts/check-campaign-claim.py, the comment guard, once a
`gh pr comment` whose first line holds opens `REVIEW` -- the same background
hand-off that starts check-research-bar.py on a NOTE. The guard does not wait,
and runs BEFORE the post, so a REVIEW it then refuses was read too.

WHAT IT READS: the REVIEW on stdin, cut into findings as the measurement cut
them (sdlc-alloy#458 NOTE issuecomment-5715409487): an item line after the
first -- a bullet, a numbered item, a table row; a bold `**F1**` lead reads
as a `*` bullet, as it did when measured -- of at least `MIN_CHARS`, and not a verification note. The reviewer's own word
is read first -- a label in the finding's first 60 characters, else the
section heading it sits under, a plain line such as `Defects:` (a bold
`**Defects**` reads as an item, as it did when measured) -- and then MASKED to
`[label]`, so the model reads the finding and not the verdict written on it.

  asked      one state `{finding}` per finding, up to `MAX_FINDINGS`, one
             `choice` defect / refinement / unclear each, all at once
  logged     each call's label is `<repo>#<pr> REVIEW f<n> <word>`
             (`tracker#<pr>` with no repo), `<word>` the reviewer's own --
             `defect`, `refinement` or `none` -- so shadow agreement with the
             reviewer is counted from the log alone
  passed     another comment kind, or a REVIEW with no finding, asks nothing
  skipped    a reading that raised logs one `skipped` row naming why

THE TIER is `shadow`: every call is logged by the caller and nothing is
printed, since the guard does not read this process's output.
THE EXIT STATUS IS 0 on every path.

THE CASES are scripts/jev/corpus/finding-sort.jsonl. Where this reading is
known to be wrong, as seen at jev-1.13.0 over three runs on 2026-09-17: over
333 labelled findings of 55 pull requests it agreed with the reviewer's word
188-190 times, where a keyword rule agreed 206; on 32 findings hand-labelled
by reviewing.md's written definition it agreed 20-21, the reviewer's own word
21 and the keyword rule 14. Those counts take P(defect) at 0.5; at the entry's
own two edges, as `--live` scores the corpus, 10-11 of the 32 read `uncertain`
and 14-16 meet their truth, so `--live` without `--record` prints about 18
off. The reviewer's word is weak truth -- "a test half
that cannot fail" called a refinement, a false docstring a defect -- which is
why the log keeps it beside the answer rather than scoring against it.

Usage: scripts/check-finding-sort.py <pr> [<repo>] < review
"""
import importlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
READER = "check-finding-sort.py"
INPUT = "comment REVIEW"
USAGE = "scripts/check-finding-sort.py <pr> [<repo>] < review"
READING = "finding-sort"
MIN_CHARS = 25
MAX_FINDINGS = 40

ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*]|\|\s*(?:\*\*)?([FDR]?\d+)(?:\*\*)?\s*\|)\s*(.*)$")
SEPARATOR = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
SAYS_DEFECT = re.compile(r"(?i)\b(defects?|behaviou?ral|blocking)\b|^\W*D\s*[,:|]|^\W*D\d+\b")
SAYS_REFINEMENT = re.compile(r"(?i)\b(refinements?|nit|wording)\b|^\W*R\s*[,:|]|^\W*R\d+\b")
SAYS_NONE = re.compile(r"(?i)\b(no|not a|none|non-?)\s*(behaviou?ral\s*)?(defects?|blocking)\b")
SECTION_DEFECT = re.compile(r"(?i)^\W*(defects?|behaviou?ral( findings)?|blocking)\b")
SECTION_REFINEMENT = re.compile(r"(?i)^\W*(refinements?|nits?|wording)\b")
SECTION_OTHER = re.compile(r"(?i)^\W*(verified|what holds|holds|checks?|ran|tests|clean|notes?|findings)\b")
LEAD = re.compile(r"(?i)^\W*[DR](?:\s*[,:]|\d+\b)\s*")
LABEL = re.compile(r"(?i)\[?\b(non-?blocking|defects?|refinements?|behaviou?ral|blocking|nits?|wording)\b\]?|\b[DR]\d+\b")
SEVERITY = re.compile(r"(?i)(\[label\]\W{0,3})\s*(low|medium|high)\b\W*")
NOT_A_FINDING = re.compile(r"(?i)^\W*not \[label\]|^\W*(resolved|closed|verified)\b|\b(none found|none\.|: none\b|reworded as asked|is applied)")


def findings(review):
    """[(the reviewer's word, the finding masked, the reviewer's own id for it
    or "")] in order, as measured.

    THE ID IS THE REVIEW'S OWN -- `F3`, `D2`, `4` -- where the REVIEW numbers
    its findings in a table, and empty where it does not. This reading does not
    use it; `check-merge-review.py`'s does, to ask whether the REPORT disposed
    of THAT finding and to let its prefilter look the id up in the REPORT's own
    rows. It is returned here rather than cut a second time there, because two
    readers of how a REVIEW splits into findings would drift."""
    out, section = [], None
    for line in review.split("\n")[1:]:
        if not line.strip() or SEPARATOR.match(line):
            continue
        m = ITEM.match(line)
        if not m:
            if SECTION_DEFECT.match(line):
                section = "defect"
            elif SECTION_REFINEMENT.match(line):
                section = "refinement"
            elif SECTION_OTHER.match(line) or line.startswith(("#", "**")):
                section = None
            continue
        text = m.group(2).strip()
        head = (m.group(1) or "") + " " + text[:60]
        if SAYS_NONE.search(head):
            word = "none"
        elif SAYS_DEFECT.search(head) and not SAYS_REFINEMENT.search(head):
            word = "defect"
        elif SAYS_REFINEMENT.search(head) and not SAYS_DEFECT.search(head):
            word = "refinement"
        else:
            word = section or "none"
        masked = SEVERITY.sub(r"\1 ", LABEL.sub("[label]", LEAD.sub("", text)))
        if len(text) < MIN_CHARS or NOT_A_FINDING.search(masked):
            continue
        out.append((word, masked, (m.group(1) or "").strip()))
    return out[:MAX_FINDINGS]


def steps(inp, reg, jev):
    """ONE `judge` CALL A FINDING, which is what this entry's `compose` says by
    `call`: the finding IS the state. The ROW carries the reading's name, the
    wording and the KEY -- the repository, the pull request and which finding
    of the review it was -- so the same thread's next REVIEW can be joined to
    the answer (sdlc-alloy#458 DECISION 5722176509)."""
    # A KEY ONLY WHERE THE REPOSITORY IS KNOWN: a number with no repository
    # names no pull request when a member repository's numbers collide with
    # this tracker's.
    key = {"repo": inp.repo, "pull_request": int(inp.number)} if inp.repo else {}
    yield jev.Ask([{"state": {"finding": masked},
                    "read": f"{inp.subject} f{n} {word}",
                    "key": dict(key, finding=n)}
                   for n, (word, masked, _ident) in enumerate(findings(inp.body), 1)],
                  {"group": reg[READING]["group"]})


def main(argv, stdin=None, env=None):
    return importlib.import_module("campaign-jev").run_reader(
        globals(), argv, stdin, env=env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
