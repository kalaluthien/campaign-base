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
read too, and a later join finds no such comment. The log line carries the
label `<repo>#<issue> NOTE <condition>` (`tracker#<issue>` with no repo) and
the time, not the note: a join matches on the issue and the time. A kind read
that failed, or a reading that raised, logs a `skipped` row naming why, so a
count of what the reading covered sees what it missed.

WHAT IT READS: the NOTE on stdin, and the issue's work kind from
`campaign-tracker.py kind`, the one reader of that label.

  asked      a NOTE on a `kind:research` issue: one state `{condition, note}`
             per entry of the entry's `conditions`, one `choice` each, all at
             once; a note reads as the highest P(contradicts) over them, which
             is what the corpus and a reader of the log take
  passed     another comment kind or another work kind asks nothing and logs
             nothing
  skipped    a kind the tracker could not read, or a reading that raised,
             asks nothing and logs one `skipped` row

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
    """(the issue's work kind as `campaign-tracker.py kind` prints it, why it
    could not be read or ''). Exit 1 is a kind read only when it printed `none`:
    a tracker that raised exits 1 too, with nothing on stdout."""
    args = [sys.executable, str(HERE / "campaign-tracker.py"), "kind", issue]
    p = subprocess.run(args + ([repo] if repo else []), capture_output=True,
                       text=True, timeout=KIND_TIMEOUT)
    kind = p.stdout.strip()
    if p.returncode == 0 or (p.returncode == 1 and kind == "none"):
        return kind, ""
    return "", (p.stderr.strip().splitlines() or [f"exit {p.returncode}"])[-1]


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
    issue, repo = argv[0], (argv[1] if len(argv) > 1 else "")
    subject = f"{repo or 'tracker'}#{issue} NOTE"
    try:
        note = stdin.read()
        if not note.lstrip().startswith("NOTE "):
            return 0
        jev = load_sibling("campaign-jev.py")
        kind, why = work_kind(issue, repo)
        if why:
            jev.skip(READER, subject, f"the kind read failed: {why}", env)
            return 0
        if kind != "research":
            return 0
        entry = json.loads(REGISTRY.read_text(encoding="utf-8"))[READING]
        ask_all(entry, note, f"{repo or 'tracker'}#{issue}", jev, env)
    except Exception as e:  # noqa: BLE001 -- a reading never refuses, and nobody reads this
        skipped(subject, e, env)
    return 0


def skipped(subject, e, env):
    """The skip row for a reading that raised, written if the log can be."""
    try:
        load_sibling("campaign-jev.py").skip(
            READER, subject, f"the reading raised {e.__class__.__name__}", env)
    except Exception:  # noqa: BLE001 -- campaign-jev itself would not load
        pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
