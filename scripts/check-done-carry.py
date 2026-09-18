#!/usr/bin/env python3
"""Log whether a test in a pull request's diff carries each Definition of done condition, and refuse nothing.

THE READINGS `done-test-select` and `done-test-claim` in
scripts/jev/readings.json, asked through scripts/campaign-jev.py. The entries
hold the questions, their criteria, the state's fields, the prefilter's
patterns, the thresholds and the tier; this reads them and writes none of
them. How to ask Jev well in general is the `asking-jev` skill's
`references/`, not this file's.

WHO RUNS IT: scripts/check-campaign-claim.py, the comment guard, on every
`gh pr comment` whose first line opens `REPORT`, in the background, from the
checkout the post runs in. The guard does not wait, and runs BEFORE the post,
so a REPORT it then refuses was read too.

WHAT IT READS: the REPORT on stdin; through `gh`, the pull request's closing
issues (`closingIssuesReferences`), each one's body, and `gh pr diff`, which
is GitHub's patch and not this machine's git config. A condition is one item
of the body's `## Definition of done`: a list item with the lines under it, or
a table's body row. A candidate is one hunk of a test file, a path check-diff-screen.py's
`TEST` names, keyed `h1..hN` in diff order.

  passed     another comment kind, or a REPORT that does not ask for the merge
             (the select entry's `asks_merge`), asks nothing and logs nothing
  settled    a condition every clause of which is an event no test could carry
             -- a comment posted, a label set, a merge, an install reached --
             logs one `skipped` row and is asked nothing
  select     ONE call a sub-issue, state `{candidateHunks}`, one `choice` a
             condition over the hunks and `noMatch`, the condition in the
             instructions; `noMatch` is itself the flag that no test carries it
  claim      ONE call a hunk some condition picked, state `{hunk}`, one
             `choice` supports / contradicts / says_nothing a condition that
             picked it; nothing is asked for a condition that picked no hunk.
             A pick under the select entry's floor is asked too, on purpose:
             the carry score below reads every pick, and the floor is the
             verdict's to apply, from the logged confidence
  logged     `<repo>#<pr> REPORT <issue> select` and
             `<repo>#<pr> REPORT <issue> claim <hunk> <path>`
             (`tracker#<pr>` with no repo)
  skipped    one row for a pull request read that failed, for one closing no
             sub-issue with a Definition of done, for a diff changing no test
             file, for a select state over the budget, and for a reading that
             raised

So a sub-issue costs at most one call plus one a distinct hunk picked, and a
condition at most two.

THE TIER is `shadow`: every call is logged by the caller and nothing is
printed, since the guard does not read this process's output.
THE EXIT STATUS IS 0 on every path the guard can reach; a usage error, a
first argument that is not a number, exits 2.

THE CASES are scripts/jev/corpus/done-test-select.jsonl, the conditions no
hunk carries, since a hunk id is an option built per state and no word of
the entry, and done-test-claim.jsonl, each pick with its truth. Where this reading is known to be wrong, as seen at
jev-1.13.0 on 2026-09-18 (kalaluthien/campaign-base#458 T2), over 48 merged
pull requests, one a sub-issue, 192 conditions hand-labelled against their own
words (51 carried, 39 partly, 78 not, 24 events), each carried or partly
carried condition asked again with its labelled hunks removed:

  carry      (1 - P(noMatch)) x P(supports), 0 where no hunk was picked; AUC
             0.96 against the removed-hunk negatives, 0.98 against the
             conditions no hunk carries
  verdict    a hunk picked at confidence 0.5 and P(supports) >= 0.5 reads
             carried for 42 of 51 carried conditions, 5 of 51 negatives and
             1 of 77 conditions no hunk carries
  every neg  the cut that flags every negative (0.90) flags 28 of 51 carried;
             two of the negatives read carried are carried by a hunk of
             another suite the label left out
  baseline   token overlap, same cut: 48 of 51; yet it ranks as well, AUC
             0.95 against the removed-hunk negatives and 0.91 against the
             conditions no hunk carries: it orders, and cannot filter
  selection  the labelled hunk was picked for 76 of 90 carried or partly
             carried conditions, `noMatch` for 11
  prefilter  8 of 192 settled: 7 events, 1 a condition no hunk carries
  noise      a repeat of 42 states moved 1 verdict of 163 conditions and 0
             of 84 negatives

Usage: scripts/check-done-carry.py <pr> [<repo>] < report
"""
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
READER = "check-done-carry.py"
INPUT = "comment REPORT"
USAGE = "scripts/check-done-carry.py <pr> [<repo>] < report"
CWD = HERE
SELECT, CLAIM = "done-test-select", "done-test-claim"
TRACKER = "kalaluthien/campaign-base"
GH_TIMEOUT = 30
DOD = "## Definition of done"


def gh(*args):
    """(stdout, why it failed or '')."""
    p = subprocess.run(["gh", *args], capture_output=True, text=True,
                       timeout=GH_TIMEOUT)
    if p.returncode:
        return "", (p.stderr.strip().splitlines() or [f"exit {p.returncode}"])[-1]
    return p.stdout, ""


def conditions(body):
    """The Definition of done items of an issue body: a list item with every
    line under it, or a table's body row -- not its header, the row above the
    rule, and not the rule."""
    dod = body.split(DOD, 1)[1].split("\n## ", 1)[0]
    lines = dod.splitlines()
    rule = re.compile(r"^\|[\s:|-]+\|?$")
    out = []
    for i, line in enumerate(lines):
        if re.match(r"^([-*]|\d+\.)\s", line):
            out.append(re.sub(r"^([-*]|\d+\.)\s+", "", line).strip())
        elif line.startswith("|"):
            header = i + 1 < len(lines) and rule.match(lines[i + 1])
            if not rule.match(line) and not header:
                out.append(line.strip())
        elif line.strip() and out:
            out[-1] += " " + re.sub(r"^\s+([-*]|\d+\.)\s+", "", line).strip()
    return out


def hunks(diff, test):
    """{h1: {path, text}, ...}: every hunk of a file `test` names, in diff order."""
    found = []
    for part in re.split(r"^diff --git ", diff, flags=re.M)[1:]:
        path = part.split("\n", 1)[0].split(" b/", 1)[-1]
        body = part.split("\n@@", 1)
        if not test.search(path) or len(body) < 2:
            continue
        for chunk in re.split(r"\n(?=@@ )", "@@" + body[1]):
            found.append({"path": path, "text": chunk.rstrip("\n")})
    return {f"h{k}": h for k, h in enumerate(found, 1)}


def settled(prefilter, text):
    """True when every clause of the condition is an event no test could carry.
    A merge named in a long clause is not settled: it is the condition's
    subject there ("one merged pull request in which ..."), not its event."""
    event, ceiling = re.compile(prefilter["event"]), prefilter["merge_clause_ceiling"]
    parts = [c for c in re.split(prefilter["clause"], text) if c.strip()]
    return bool(parts) and all(
        any(not ("merged" in m.group(0).lower() and len(c) > ceiling)
            for m in event.finditer(c))
        for c in parts)


def ask_issue(reg, subject, conds, cands, jev, key=None):
    """The two calls for one sub-issue, as steps: a skip, or one chain.

    ONE `judge` CALL EACH, where it used to be one `ask`. `done-test-select`'s
    options are one per candidate hunk, built from the template the entry holds
    under `{hunk}`, and both readings splice the condition's text at
    `{condition}` -- the shapes this file composed by hand until now, held to
    the byte by campaign-jev-test's "a built-criteria question and a
    two-placeholder one are what their readers sent". What the ROWS gained is
    each reading's name, its wording and the KEY -- the repository, the
    sub-issue and the pull request -- so a later REVIEW or reopen naming that
    Definition-of-done line can be joined to the answer (sdlc-alloy#458
    DECISION 5722176509)."""
    text = {h: c["path"] + "\n" + c["text"] for h, c in cands.items()}
    if jev.over_budget({"candidateHunks": text}):
        yield jev.Skip(f"{subject} select", f"the {len(cands)} test hunks are "
                       f"over the {jev.STATE_BUDGET}-byte budget")
        return
    yield jev.Ask([{
        "select": SELECT,
        "state": {"candidateHunks": text, "condition": conds},
        "then": lambda h, asked: {
            "group": reg[CLAIM]["group"],
            "state": {"hunk": text[h], "condition": asked},
            "read": f"{subject} claim {h} {cands[h]['path']}"}
        if h in cands else None,
        "read": f"{subject} select", "reg": reg, "key": key}], {})


def closing(jev, subject, pr, repo):
    """Steps; then ([(repository, number, body)] of every issue the pull
    request closes whose body holds a Definition of done, the pull request's
    diff), or None after a skip naming what did not read or what is missing.
    Used as `got = yield from closing(...)`."""
    target = ["-R", repo or TRACKER]
    view, why = gh("pr", "view", pr, *target, "--json", "closingIssuesReferences")
    if why:
        yield jev.Skip(subject, f"the pull request read failed: {why}")
        return None
    bodies = []
    for ref in json.loads(view)["closingIssuesReferences"]:
        name = f"{ref['repository']['owner']['login']}/{ref['repository']['name']}"
        body, why = gh("issue", "view", str(ref["number"]), "-R", name,
                       "--json", "body", "--jq", ".body")
        if why:
            yield jev.Skip(f"{subject} {ref['number']}",
                           f"the issue read failed: {why}")
        elif DOD in body:
            bodies.append((name, ref["number"], body))
    if not bodies:
        yield jev.Skip(subject, "the pull request closes no issue with a "
                       "Definition of done")
        return None
    diff, why = gh("pr", "diff", pr, *target)
    if why:
        yield jev.Skip(subject, f"the diff read failed: {why}")
        return None
    return bodies, diff


def steps(inp, reg, jev):
    pr, repo, subject, report = inp.number, inp.repo, inp.subject, inp.body
    prefilter = reg[SELECT]["prefilter"]
    if not re.search(prefilter["asks_merge"], report):
        return
    got = yield from closing(jev, subject, pr, repo)
    if got is None:
        return
    bodies, diff = got
    cands = hunks(diff, jev.load_sibling("check-diff-screen.py").TEST)
    if not cands:
        yield jev.Skip(subject, "the diff changes no test file, so no "
                       "condition is carried by one")
        return
    for _name, number, body in bodies:
        conds = {}
        for k, text in enumerate(conditions(body), 1):
            if settled(prefilter, text):
                yield jev.Skip(f"{subject} {number} c{k}", "an event no "
                               "test could carry")
            else:
                conds[f"c{k}"] = text
        if conds:
            # A KEY ONLY WHERE THE REPOSITORY IS KNOWN: a number with no
            # repository names no issue when a member repository's numbers
            # collide with this tracker's.
            yield from ask_issue(reg, f"{subject} {number}", conds, cands, jev,
                                 {"repo": repo, "issue": int(number),
                                  "pull_request": int(pr)} if repo else None)


def main(argv, stdin=None, env=None):
    return importlib.import_module("campaign-jev").run_reader(
        globals(), argv, stdin, env=env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
