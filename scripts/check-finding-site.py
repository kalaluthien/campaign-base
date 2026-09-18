#!/usr/bin/env python3
"""Log whether each finding of a REVIEW holds at the `path:line` it names, and refuse nothing.

THE READING `finding-site` in scripts/jev/readings.json, asked through
scripts/campaign-jev.py. The entry holds the question, its criteria, the
state's fields, the thresholds and the tier; this reads them and writes none
of them. How to ask Jev well in general is the `asking-jev` skill's
`references/`, not this file's.

WHO RUNS IT: scripts/check-campaign-claim.py, the comment guard, beside
check-finding-sort.py on every `gh pr comment` whose first line opens `REVIEW`,
in the background, from the checkout the post runs in. The guard does not
wait, and runs BEFORE the post, so a REVIEW it then refuses was read too.

WHAT IT READS: the REVIEW on stdin, cut into findings by
check-finding-sort.py's `findings()`, so finding `f<n>` is one finding in both
logs, its reviewer's word already masked. The reviewed sha is the LAST word on
the REVIEW's first line that check-merge-review.py's `SHA` reads as one and
this checkout holds, since a narrowed round names its range before its head
(`narrowed to a73fc57..031cd03, at 031cd03`). A finding's site is the
first `path:line` it names; the path is taken as written when the reviewed sha
holds it, else the one file there ending in it, else the one of several the
sha changed since `origin/main`. The slice is that file at the reviewed sha,
`SLICE_HALF` lines each side of the line, each line numbered, read with `git
show` in this process's checkout.

  asked      one state `{finding, slice}` per finding with a site, one
             `choice` supports / contradicts / says_nothing each, all at once
  logged     each call's label is `<repo>#<pr> REVIEW f<n> <path>:<line>`
             (`tracker#<pr>` with no repo)
  passed     another comment kind, or a REVIEW with no finding, asks nothing
  skipped    one `skipped` row per finding naming no `path:line`, or whose
             path or line does not resolve at the sha, or of a REVIEW whose
             first line names no sha this checkout holds; one for the whole
             REVIEW when the reading raised

THE TIER is `shadow`: every call is logged by the caller and nothing is
printed, since the guard does not read this process's output.
THE EXIT STATUS IS 0 on every path.

THE CASES are scripts/jev/corpus/finding-site.jsonl. Where this reading is
known to be wrong, as seen at jev-1.13.0 on 2026-09-17
(kalaluthien/campaign-base#458 R4), over 122 findings whose fix commit changed
their site, each asked against the slice at the reviewed sha and at the fix,
three runs:

  order      the fix read P(contradicts) above the reviewed slice in 95-102
             of 122 pairs; token overlap did in 28
  filter     none: the threshold that flags every fix (0.02-0.03) flags
             115-121 of the 122 reviewed slices too
  truth      of 30 fixes checked by hand, 26 removed what the finding named;
             those read P(contradicts) from 0.05, and 7 of 26 over 0.5
  probes     a finding whose evidence is a probe -- a mutation that stayed
             green, a command no verdict moved -- reads `supports` from a
             slice that cannot show it
  slices     the enclosing function instead did no better (77-87 of 122 in
             order), and neither did a `choice` of the block first, with
             `none` and a confidence floor, then the claim against the block
             picked (one run, across the floors tried: 57-68 of 80-101 pairs
             in order)

Usage: scripts/check-finding-site.py <pr> [<repo>] < review
"""
import importlib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
READER = "check-finding-site.py"
INPUT = "comment REVIEW"
USAGE = "scripts/check-finding-site.py <pr> [<repo>] < review"
READING = "finding-site"
SLICE_HALF = 40
GIT_TIMEOUT = 20

SITE = re.compile(r"`?((?:[\w.-]+/)*[\w.-]+\.(?:py|sh|als|md|json|jsonl|yml|yaml|html|toml))`?:(\d+)")


def git(*args):
    """stdout, or None when git refused."""
    p = subprocess.run(["git", *args], capture_output=True, text=True,
                       timeout=GIT_TIMEOUT)
    return p.stdout if p.returncode == 0 else None


def resolve(sha, name):
    """The path at `sha` a finding's `name` means, or None."""
    paths = (git("ls-tree", "-r", "--name-only", sha) or "").split("\n")
    if name in paths:
        return name
    hits = [p for p in paths if p.endswith("/" + name)]
    if len(hits) > 1:
        base = (git("merge-base", sha, "origin/main") or "").strip()
        changed = set((git("diff", "--name-only", base, sha) or "").split("\n")) if base else set()
        hits = [p for p in hits if p in changed]
    return hits[0] if len(hits) == 1 else None


def site_slice(sha, masked):
    """((path, line), the numbered slice) or (None, why the finding has none)."""
    site = SITE.search(masked)
    if not site:
        return None, "the finding names no path:line"
    path, line = resolve(sha, site.group(1)), int(site.group(2))
    if path is None:
        return None, f"{site.group(1)} is no one file at {sha[:12]}"
    text = git("show", f"{sha}:{path}") or ""
    # `git show` ends in a newline, which is no line of the file.
    lines = text.removesuffix("\n").split("\n") if text else []
    if not 1 <= line <= len(lines):
        return None, f"{path} has no line {line} at {sha[:12]}"
    lo, hi = max(1, line - SLICE_HALF), min(len(lines), line + SLICE_HALF)
    return (path, line), "\n".join(f"{i}: {lines[i - 1]}" for i in range(lo, hi + 1))


def reviewed_sha(first_line, jev):
    """The last sha the first line names that this checkout holds, or None."""
    review = jev.load_sibling("check-merge-review.py")
    for named in reversed(review.SHA.findall(first_line)):
        sha = (git("rev-parse", "--verify", "-q", named + "^{commit}") or "").strip()
        if sha:
            return sha
    return None


def steps(inp, reg, jev):
    """ONE `judge` CALL A FINDING WITH A SITE, which is what this entry's
    `compose` says by `call`: the finding and its slice ARE the state. The
    ROW carries the reading's name, the wording and the KEY -- the repository,
    the pull request and which finding of the review it was -- so the thread's
    next REVIEW can be joined to the answer (sdlc-alloy#458 DECISION
    5722176509)."""
    cut = jev.load_sibling("check-finding-sort.py").findings(inp.body)
    if not cut:
        return
    sha = reviewed_sha(inp.body.lstrip().split("\n", 1)[0], jev)
    if not sha:
        for n in range(1, len(cut) + 1):
            yield jev.Skip(f"{inp.subject} f{n}",
                           "the first line names no sha this checkout holds")
        return
    group = reg[READING]["group"]
    # A KEY ONLY WHERE THE REPOSITORY IS KNOWN: a number with no repository
    # names no pull request when a member repository's numbers collide with
    # this tracker's.
    key = {"repo": inp.repo, "pull_request": int(inp.number)} if inp.repo else {}
    asks = []
    for n, (_word, masked, _ident) in enumerate(cut, 1):
        site, got = site_slice(sha, masked)
        if site is None:
            yield jev.Skip(f"{inp.subject} f{n}", got)
        else:
            asks.append({"state": {"finding": masked, "slice": got},
                         "read": f"{inp.subject} f{n} {site[0]}:{site[1]}",
                         "key": dict(key, finding=n)})
    yield jev.Ask(asks, {"group": group})


def main(argv, stdin=None, env=None):
    return importlib.import_module("campaign-jev").run_reader(
        globals(), argv, stdin, env=env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
