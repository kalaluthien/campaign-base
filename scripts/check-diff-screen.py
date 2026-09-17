#!/usr/bin/env python3
"""Log how each file a commit touched reads against the diff screen's five questions, and refuse nothing.

THE READING `diff-screen` in scripts/jev/readings.json, asked through
scripts/campaign-jev.py. The entry holds the five `nouls`, the question they
are composed into, the state's fields, the thresholds and the tier; this reads
them and writes none of them.

WHO RUNS IT: scripts/push-campaign-branch.sh, the post-commit hook, in the
background once it pushed a claim to a GitHub remote. WHY THEN: it is the
cheapest moment that has seen the diff before a reviewer does. Every change a
reviewer reads came through a commit, so the last call on each file before
the review launch holds the screen of the head it reviews. Counted over the 77
fix-round pull requests (sdlc-alloy#458 R2), a file of a commit is 17.2 calls
a pull request. Screening the whole branch at each push is 92.5, and at each
review round 30.4. A `REVIEW` post is after the reading it would steer. The
review launch is an `Agent` call no field of which says it is one.

The log line carries the label `<branch> <sha12> <path>`, an answer per noul
and the time, never the patch. A join finds the pull request by the branch,
and a `REVIEW` defect naming the path by `path:line` as its later fact.

WHAT IT READS: the commit's own files (`git diff-tree`), each file's patch from
`git merge-base <commit> origin/main` to the commit, and the paths of the test
files that branch diff changes.

  asked      one call a file the commit touched: state `{file: {path, patch},
             changedTests}`, one `noul` question a noul, all five in the call
  passed     a merge commit asks nothing: `git diff-tree` lists no file for
             one, since its files are main's, not the branch's work
  skipped    a binary file, a file whose branch patch is empty, a patch over
             PATCH_CEILING, a commit with no merge-base, or a reading that
             raised, asks nothing and logs one `skipped` row naming why

THE TIER is `shadow`: every call is logged and nothing is printed, since the
hook's background start discards this process's output.
THE EXIT STATUS IS 0 on every path.

WHERE THIS READING IS KNOWN TO BE WRONG, as seen at jev-1.13.0 on 2026-09-17,
one run and repeats for 147 rows, over 399 files of 77 pull requests (39 a
`REVIEW` defect named, 360 no finding named): at the cut that keeps every
defect file, the highest of the five lets a reviewer skip 44-57 of 399
(11-14%), AUC 0.73; "most added lines" skips 30 (8%), AUC 0.78; "tests changed
or not" skips none. Its lowest defect files are prose: AGENTS.md at 0.12.

Usage: scripts/check-diff-screen.py [<commit>]
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
READING = "diff-screen"
REGISTRY = HERE / "jev" / "readings.json"
READER = "check-diff-screen.py"
GIT_TIMEOUT = 30
# 55 KB was the largest patch answered in the measurement; 127 KB came back
# `max_tokens_exceeded` (topic-jev).
PATCH_CEILING = 100_000
# THE PATCH'S FORM IS PINNED, not left to the machine's git config: the
# measurement ran under `diff.noprefix` and `diff.algorithm=histogram`, and a
# config without them sends a patch the band was not measured on.
PATCH_FORM = ("--no-prefix", "--diff-algorithm=histogram", "--no-color",
              "--no-ext-diff", "--no-textconv", "--no-renames")
TEST = re.compile(r"(-test\.\w+$|_test\.\w+$|(^|/)checks\.als$|(^|/)tests?/)")
WORKERS = 8


def load_sibling(name):
    """A sibling script as a module, by path: these are scripts, not a package."""
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(HERE / name)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(*args):
    """stdout, or None when git exited non-zero."""
    p = subprocess.run(["git", *args], capture_output=True, text=True,
                       timeout=GIT_TIMEOUT)
    return p.stdout if p.returncode == 0 else None


def questions(entry):
    """A `noul` question a noul, each the entry's question with that noul's
    words put in its placeholders."""
    q, cuts = entry["question"], entry["thresholds"]
    text = json.dumps({k: q[k] for k in ("type", "instructions", "criteria")})
    out = {}
    for name, words in entry["nouls"].items():
        filled = text
        for key, value in words.items():
            filled = filled.replace("{" + key + "}", json.dumps(value)[1:-1])
        out[name] = dict(json.loads(filled), **cuts)
    return out


def files(commit, base):
    """[(path, why it is skipped or "")] for every file the commit touched."""
    touched = (git("diff-tree", "--no-commit-id", "--name-only", "-r",
                   "--no-renames", commit) or "").split("\n")
    stat = {}
    for line in (git("diff", "--numstat", "--no-renames", base, commit)
                 or "").split("\n"):
        if line:
            added, _removed, path = line.split("\t", 2)
            stat[path] = added
    out = []
    for path in filter(None, touched):
        if path not in stat:
            out.append((path, "the branch's patch of it is empty"))
        elif stat[path] == "-":
            out.append((path, "a binary file"))
        else:
            out.append((path, ""))
    return out, sorted(p for p in stat if TEST.search(p))


def main(argv, env=None):
    if len(argv) > 1:
        print("Usage: scripts/check-diff-screen.py [<commit>]", file=sys.stderr)
        return 2
    subject = argv[0] if argv else "HEAD"
    try:
        jev = load_sibling("campaign-jev.py")
        commit = (git("rev-parse", "--verify", "-q", subject + "^{commit}")
                  or "").strip()
        branch = (git("symbolic-ref", "--quiet", "--short", "HEAD")
                  or "detached").strip()
        label = f"{branch} {commit[:12] or subject}"
        if not commit:
            jev.skip(READER, label, "the commit does not resolve", env)
            return 0
        base = (git("merge-base", commit, "origin/main") or "").strip()
        if not base:
            jev.skip(READER, label, "no merge-base with origin/main", env)
            return 0
        entry = json.loads(REGISTRY.read_text(encoding="utf-8"))[READING]
        asked = questions(entry)
        found, tests = files(commit, base)

        def one(item):
            path, why = item
            patch = "" if why else git("diff", *PATCH_FORM, base, commit,
                                       "--", path) or ""
            if not why and len(patch) > PATCH_CEILING:
                why = f"a patch of {len(patch)} chars, over {PATCH_CEILING}"
            if why:
                jev.skip(READER, f"{label} {path}", why, env)
                return
            jev.ask(READER, f"{label} {path}",
                    {"file": {"path": path, "patch": patch},
                     "changedTests": tests}, asked, env=env)
        with ThreadPoolExecutor(WORKERS) as pool:
            list(pool.map(one, found))
    except Exception as e:  # noqa: BLE001 -- a reading never refuses, and nobody reads this
        skipped(f"{subject}", e, env)
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
