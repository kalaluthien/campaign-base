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
import importlib.machinery
import importlib.util
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
READING = "finding-sort"
REGISTRY = HERE / "jev" / "readings.json"
READER = "check-finding-sort.py"
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
    """[(the reviewer's word, the finding masked)] in order, as measured."""
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
        out.append((word, masked))
    return out[:MAX_FINDINGS]


def load_sibling(name):
    """A sibling script as a module, by path: these are scripts, not a package."""
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(HERE / name)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def questions(entry):
    q = entry["question"]
    spec = {k: v for k, v in q.items() if k in ("type", "criteria")}
    spec.update(entry["thresholds"], instructions=q["instructions"])
    return {"c": spec}


def ask_all(entry, cut, subject, jev, env=None):
    """[Answer] for every finding, asked at once."""
    def one(item):
        n, (word, masked) = item
        reading = jev.ask(READER, f"{subject} f{n} {word}", {"finding": masked},
                          questions(entry), env=env)
        return reading.answers["c"]
    with ThreadPoolExecutor(min(8, len(cut))) as pool:
        return list(pool.map(one, enumerate(cut, 1)))


def main(argv, stdin=sys.stdin, env=None):
    if not 1 <= len(argv) <= 2 or not argv[0].isdigit():
        print("Usage: scripts/check-finding-sort.py <pr> [<repo>] < review",
              file=sys.stderr)
        return 2
    pr, repo = argv[0], (argv[1] if len(argv) > 1 else "")
    subject = f"{repo or 'tracker'}#{pr} REVIEW"
    try:
        review = stdin.read()
        if not review.lstrip().startswith("REVIEW "):
            return 0
        cut = findings(review)
        if not cut:
            return 0
        entry = json.loads(REGISTRY.read_text(encoding="utf-8"))[READING]
        ask_all(entry, cut, subject, load_sibling("campaign-jev.py"), env)
    except Exception as e:  # noqa: BLE001 -- a reading never refuses, and nobody reads this
        try:
            load_sibling("campaign-jev.py").skip(
                READER, subject, f"the reading raised {e.__class__.__name__}", env)
        except Exception:  # noqa: BLE001 -- campaign-jev itself would not load
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
