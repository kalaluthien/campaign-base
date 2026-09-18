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
label `<repo>#<issue> NOTE` (`tracker#<issue>` with no repo), an answer per
condition, and the time, not the note: a join matches on the issue and the time. A kind read
that failed, or a reading that raised, logs a `skipped` row naming why, so a
count of what the reading covered sees what it missed.

WHAT IT READS: the NOTE on stdin, and the issue's work kind from
`campaign-tracker.py kind`, the one reader of that label.

  asked      a NOTE on a `kind:research` issue: ONE call, state `{note}`, one
             `choice` question per entry of the entry's `conditions`, each its
             condition put into the entry's instructions; a note reads as the
             highest P(contradicts) over them, which is what the corpus and a
             reader of the log take
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
import importlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
READER = "check-research-bar.py"
INPUT = "comment NOTE"
USAGE = "scripts/check-research-bar.py <issue> [<repo>] < note"
READING = "research-bar"
KIND_TIMEOUT = 20


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


def steps(inp, reg, jev):
    """ONE CALL A NOTE, not one a condition (sdlc-alloy#458 DECISION
    issuecomment-5716072632): questions in one call cannot see each other, so
    each still asks one narrow judgment, and the state the endpoint is sent is
    the note alone. The conditions are handed to `judge` as the state's
    `condition` field and its `compose` splices each one's text at
    `{condition}`, so what is sent did not move. The ROW carries the reading's
    name, the wording and the KEY, without which no later DECISION could ever
    be joined to the answer (sdlc-alloy#458 DECISION 5722176509)."""
    kind, why = work_kind(inp.number, inp.repo)
    if why:
        yield jev.Skip(inp.subject, f"the kind read failed: {why}")
        return
    if kind != "research":
        return
    entry = reg[READING]
    # A KEY ONLY WHERE THE REPOSITORY IS KNOWN: the guard passes it, and a
    # number with no repository names no issue when a member repository's
    # numbers collide with this tracker's.
    key = {"repo": inp.repo, "issue": int(inp.number)} if inp.repo else {}
    yield jev.Ask([{"state": {"note": inp.body, "condition": entry["conditions"]},
                    "read": inp.subject, "key": key}],
                  {"group": entry["group"]})


def main(argv, stdin=None, env=None):
    return importlib.import_module("campaign-jev").run_reader(
        globals(), argv, stdin, env=env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
