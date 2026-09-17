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
logs, its reviewer's word already masked. The reviewed sha is the first hex
word of 7-40 characters on the REVIEW's first line. A finding's site is the
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
             path or line does not resolve at the sha; one for the whole
             REVIEW when its first line names no sha this checkout holds, or
             the reading raised

THE TIER is `shadow`: every call is logged by the caller and nothing is
printed, since the guard does not read this process's output.
THE EXIT STATUS IS 0 on every path.

THE CASES are scripts/jev/corpus/finding-site.jsonl. Where this reading is
known to be wrong, as seen at jev-1.13.0 over three runs on 2026-09-17
(kalaluthien/campaign-base#458 R4): over 122 findings whose fix commit
changed their site, the same finding against the slice at the fix read
P(contradicts) above its own reviewed slice 95-102 times, where token overlap
did 28; but at the threshold that flags every fixed slice (0.02-0.03), 115-121
of the 122 reviewed slices are flagged too. Of 30 of those fixes checked by
hand, 26 removed what the finding named, and they read P(contradicts) 0.05 to
at most 7 over 0.5, so the overlap is the reading's and not the history's.
A finding whose evidence is a probe -- a mutation that stayed green, a command
no verdict moved -- reads `supports` from a slice that cannot show it. The
enclosing function as the slice did no better.

Usage: scripts/check-finding-site.py <pr> [<repo>] < review
"""
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
READING = "finding-site"
REGISTRY = HERE / "jev" / "readings.json"
READER = "check-finding-site.py"
SLICE_HALF = 40
GIT_TIMEOUT = 20

SITE = re.compile(r"`?((?:[\w.-]+/)*[\w.-]+\.(?:py|sh|als|md|json|jsonl|yml|yaml|html|toml))`?:(\d+)")
SHA = re.compile(r"\b([0-9a-f]{7,40})\b")


def load_sibling(name):
    """A sibling script as a module, by path: these are scripts, not a package."""
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(HERE / name)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
    lines = (git("show", f"{sha}:{path}") or "").split("\n")
    if not 1 <= line <= len(lines):
        return None, f"{path} has no line {line} at {sha[:12]}"
    lo, hi = max(1, line - SLICE_HALF), min(len(lines), line + SLICE_HALF)
    return (path, line), "\n".join(f"{i}: {lines[i - 1]}" for i in range(lo, hi + 1))


def questions(entry):
    q = entry["question"]
    spec = {k: v for k, v in q.items() if k in ("type", "criteria")}
    spec.update(entry["thresholds"], instructions=q["instructions"])
    return {"c": spec}


def ask_all(entry, cut, sha, subject, jev, env=None):
    """Ask every finding with a site at once; log a skip for every other."""
    asks = []
    for n, (_, masked) in enumerate(cut, 1):
        site, got = site_slice(sha, masked)
        if site is None:
            jev.skip(READER, f"{subject} f{n}", got, env)
        else:
            asks.append((f"{subject} f{n} {site[0]}:{site[1]}",
                         {"finding": masked, "slice": got}))
    if not asks:
        return []

    def one(item):
        label, state = item
        return jev.ask(READER, label, state, questions(entry), env=env).answers["c"]
    with ThreadPoolExecutor(min(8, len(asks))) as pool:
        return list(pool.map(one, asks))


def main(argv, stdin=sys.stdin, env=None):
    if not 1 <= len(argv) <= 2 or not argv[0].isdigit():
        print("Usage: scripts/check-finding-site.py <pr> [<repo>] < review",
              file=sys.stderr)
        return 2
    pr, repo = argv[0], (argv[1] if len(argv) > 1 else "")
    subject = f"{repo or 'tracker'}#{pr} REVIEW"
    try:
        review = stdin.read()
        if not review.lstrip().startswith("REVIEW "):
            return 0
        cut = load_sibling("check-finding-sort.py").findings(review)
        if not cut:
            return 0
        jev = load_sibling("campaign-jev.py")
        named = SHA.search(review.lstrip().split("\n", 1)[0])
        sha = named and (git("rev-parse", "--verify", "-q", named.group(1) + "^{commit}") or "").strip()
        if not sha:
            jev.skip(READER, subject, "the first line names no sha this checkout holds", env)
            return 0
        entry = json.loads(REGISTRY.read_text(encoding="utf-8"))[READING]
        ask_all(entry, cut, sha, subject, jev, env)
    except Exception as e:  # noqa: BLE001 -- a reading never refuses, and nobody reads this
        try:
            load_sibling("campaign-jev.py").skip(
                READER, subject, f"the reading raised {e.__class__.__name__}", env)
        except Exception:  # noqa: BLE001 -- campaign-jev itself would not load
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
