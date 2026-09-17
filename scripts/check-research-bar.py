#!/usr/bin/env python3
"""Log how a research NOTE reads against each condition of the kind's bar, and refuse nothing.

THE READING `research-bar` in scripts/jev/readings.json, asked through
scripts/campaign-jev.py. The entry holds the conditions, the question, its
criteria, the state's fields, the thresholds and the tier; this reads them and
writes none of them. How to ask Jev well in general is the `asking-jev`
skill's `references/`, not this file's.

WHO RUNS IT: scripts/check-campaign-claim.py, the comment guard, once a
`gh issue comment` whose first line holds opens `NOTE`. The guard starts this
in the background and does not wait, so a post is never slowed by the model.
The guard runs BEFORE the post, so a comment it then refuses for its claim was
read too; the log line carries the note, and a later join finds no such
comment.

WHAT IT READS: the NOTE on stdin, and the issue's work kind from
`campaign-tracker.py kind`, the one reader of that label.

  asked      a NOTE on a `kind:research` issue: one state `{condition, note}`
             per entry of the entry's `conditions`, one `choice` each, all at
             once; a note reads as the highest P(contradicts) over them, which
             is what the corpus and a reader of the log take
  skipped    anything else -- another comment kind, another work kind, a kind
             the tracker could not read -- asks nothing

THE TIER is `shadow`: every call is logged by the caller and nothing is
printed, since the guard does not read this process's output. A tier above
`shadow` needs a place a reader sees, which this hook has not got.
THE EXIT STATUS IS 0 on every path.

THE CASES are scripts/jev/corpus/research-bar.jsonl. Where this reading is
known to be wrong, as seen at jev-1.13.0 over three runs on 2026-09-17
(kalaluthien/campaign-base#458 NOTE issuecomment-5714880301), the accepted
NOTEs flagged at the threshold that flags every negative, of 127:

  baseline   14-33, the one condition that filters
  negative   113-120: 5712582059's "2 random foreign names per suite" reads
             as a negative made well, 0.04-0.08
  scope      52-59, method 90-97, raw 75-94, on two or three one-edit
             negatives each
  all five   68-72 at the highest P(contradicts)

Usage: scripts/check-research-bar.py <issue> [<repo>] < note
"""
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
READING = "research-bar"
REGISTRY = HERE / "jev" / "readings.json"
READER = "check-research-bar.py"
KIND_TIMEOUT = 20


def load_sibling(name):
    """A sibling script as a module, by path: these are scripts, not a package."""
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(HERE / name)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def work_kind(issue, repo):
    """The issue's work kind as `campaign-tracker.py kind` prints it, or ''."""
    args = [sys.executable, str(HERE / "campaign-tracker.py"), "kind", issue]
    p = subprocess.run(args + ([repo] if repo else []), capture_output=True,
                       text=True, timeout=KIND_TIMEOUT)
    return p.stdout.strip()


def questions(entry):
    q = entry["question"]
    spec = {k: v for k, v in q.items() if k in ("type", "criteria")}
    spec.update(entry["thresholds"], instructions=q["instructions"])
    return {"c": spec}


def ask_all(entry, note, subject, jev, env=None):
    """[(condition, Answer)] for every condition of the entry, asked at once."""
    def one(name):
        state = {"condition": entry["conditions"][name], "note": note}
        reading = jev.ask(READER, f"{subject} NOTE {name}", state,
                          questions(entry), env=env)
        return name, reading.answers["c"]
    with ThreadPoolExecutor(len(entry["conditions"])) as pool:
        return list(pool.map(one, entry["conditions"]))


def main(argv, stdin=sys.stdin, env=None):
    if not 1 <= len(argv) <= 2 or not argv[0].isdigit():
        print("Usage: scripts/check-research-bar.py <issue> [<repo>] < note",
              file=sys.stderr)
        return 2
    try:
        note = stdin.read()
        if not note.lstrip().startswith("NOTE "):
            return 0
        issue, repo = argv[0], (argv[1] if len(argv) > 1 else "")
        if work_kind(issue, repo) != "research":
            return 0
        entry = json.loads(REGISTRY.read_text(encoding="utf-8"))[READING]
        ask_all(entry, note, f"{repo or 'tracker'}#{issue}",
                load_sibling("campaign-jev.py"), env)
    except Exception:  # noqa: BLE001 -- a reading never refuses, and nobody reads this
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
