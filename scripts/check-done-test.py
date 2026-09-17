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
a table row. A candidate is one hunk of a test file, a path check-diff-screen.py's
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
             picked it; nothing is asked for a condition that picked no hunk
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
THE EXIT STATUS IS 0 on every path.

THE CASES are scripts/jev/corpus/done-test-select.jsonl and
done-test-claim.jsonl. Where this reading is known to be wrong, as seen at
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
  baseline   token overlap, same cut: 48 of 51
  selection  the labelled hunk was picked for 76 of 90 carried or partly
             carried conditions, `noMatch` for 11
  prefilter  8 of 192 settled: 7 events, 1 a condition no hunk carries
  noise      a repeat of 42 states moved one verdict of 163, and one of 84
             negatives none

Usage: scripts/check-done-test.py <pr> [<repo>] < report
"""
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELECT, CLAIM = "done-test-select", "done-test-claim"
REGISTRY = HERE / "jev" / "readings.json"
READER = "check-done-test.py"
TRACKER = "kalaluthien/campaign-base"
GH_TIMEOUT = 30
DOD = "## Definition of done"


def load_sibling(name):
    """A sibling script as a module, by path: these are scripts, not a package."""
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(HERE / name)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def gh(*args):
    """(stdout, why it failed or '')."""
    p = subprocess.run(["gh", *args], capture_output=True, text=True,
                       timeout=GH_TIMEOUT)
    if p.returncode:
        return "", (p.stderr.strip().splitlines() or [f"exit {p.returncode}"])[-1]
    return p.stdout, ""


def conditions(body):
    """The Definition of done items of an issue body: a list item with every
    line under it, or a table row that is not the header rule."""
    dod = body.split(DOD, 1)[1].split("\n## ", 1)[0]
    out = []
    for line in dod.splitlines():
        if re.match(r"^([-*]|\d+\.)\s", line):
            out.append(re.sub(r"^([-*]|\d+\.)\s+", "", line).strip())
        elif line.startswith("|"):
            if not re.match(r"^\|[\s:|-]+\|?$", line):
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


def select_questions(entry, conds, cands):
    """One `choice` a condition over the candidate hunks and `noMatch`."""
    q = entry["question"]
    template = q["criteria"]["{hunk}"]
    criteria = {h: template.replace("{hunk}", h).replace("{path}", c["path"])
                for h, c in cands.items()}
    criteria["noMatch"] = q["criteria"]["noMatch"]
    spec = dict(entry["thresholds"], type=q["type"], criteria=criteria)
    return {cid: dict(spec, instructions=q["instructions"].replace("{condition}", t))
            for cid, t in conds.items()}


def claim_questions(entry, conds):
    """One `choice` supports / contradicts / says_nothing a condition."""
    q = entry["question"]
    spec = dict(entry["thresholds"], type=q["type"], criteria=q["criteria"])
    return {cid: dict(spec, instructions=q["instructions"].replace("{condition}", t))
            for cid, t in conds.items()}


def ask_issue(reg, subject, conds, cands, jev, env=None):
    """The two calls for one sub-issue; {condition id: hunk picked or None}."""
    state = {"candidateHunks": {h: c["path"] + "\n" + c["text"]
                                for h, c in cands.items()}}
    if len(json.dumps(state).encode("utf-8")) > jev.STATE_BUDGET:
        jev.skip(READER, f"{subject} select", f"the {len(cands)} test hunks are "
                 f"over the {jev.STATE_BUDGET}-byte budget", env, cwd=HERE)
        return {}
    got = jev.ask(READER, f"{subject} select", state,
                  select_questions(reg[SELECT], conds, cands), env=env, cwd=HERE)
    picked = {cid: (a.raw or {}).get("choice") for cid, a in got.answers.items()}
    by_hunk = {}
    for cid, h in picked.items():
        if h in cands:
            by_hunk.setdefault(h, {})[cid] = conds[cid]
    for h, asked in sorted(by_hunk.items()):
        jev.ask(READER, f"{subject} claim {h} {cands[h]['path']}",
                {"hunk": cands[h]["path"] + "\n" + cands[h]["text"]},
                claim_questions(reg[CLAIM], asked), env=env, cwd=HERE)
    return picked


def main(argv, stdin=sys.stdin, env=None):
    if not 1 <= len(argv) <= 2 or not argv[0].isdigit():
        print("Usage: scripts/check-done-test.py <pr> [<repo>] < report",
              file=sys.stderr)
        return 2
    pr, repo = argv[0], (argv[1] if len(argv) > 1 else "")
    subject = f"{repo or 'tracker'}#{pr} REPORT"
    try:
        report = stdin.read()
        if not report.lstrip().startswith("REPORT "):
            return 0
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        prefilter = reg[SELECT]["prefilter"]
        if not re.search(prefilter["asks_merge"], report):
            return 0
        jev = load_sibling("campaign-jev.py")
        target = ["-R", repo or TRACKER]
        view, why = gh("pr", "view", pr, *target, "--json", "closingIssuesReferences")
        if why:
            jev.skip(READER, subject, f"the pull request read failed: {why}", env, cwd=HERE)
            return 0
        bodies = []
        for ref in json.loads(view)["closingIssuesReferences"]:
            name = f"{ref['repository']['owner']['login']}/{ref['repository']['name']}"
            body, why = gh("issue", "view", str(ref["number"]), "-R", name,
                           "--json", "body", "--jq", ".body")
            if why:
                jev.skip(READER, f"{subject} {ref['number']}",
                         f"the issue read failed: {why}", env, cwd=HERE)
            elif DOD in body:
                bodies.append((ref["number"], body))
        if not bodies:
            jev.skip(READER, subject, "the pull request closes no issue with a "
                     "Definition of done", env, cwd=HERE)
            return 0
        diff, why = gh("pr", "diff", pr, *target)
        if why:
            jev.skip(READER, subject, f"the diff read failed: {why}", env, cwd=HERE)
            return 0
        cands = hunks(diff, load_sibling("check-diff-screen.py").TEST)
        if not cands:
            jev.skip(READER, subject, "the diff changes no test file, so no "
                     "condition is carried by one", env, cwd=HERE)
            return 0
        for number, body in bodies:
            conds = {}
            for k, text in enumerate(conditions(body), 1):
                if settled(prefilter, text):
                    jev.skip(READER, f"{subject} {number} c{k}", "an event no "
                             "test could carry", env, cwd=HERE)
                else:
                    conds[f"c{k}"] = text
            if conds:
                ask_issue(reg, f"{subject} {number}", conds, cands, jev, env)
    except Exception as e:  # noqa: BLE001 -- a reading never refuses, and nobody reads this
        skipped(subject, e, env)
    return 0


def skipped(subject, e, env):
    """The skip row for a reading that raised, written if the log can be."""
    try:
        load_sibling("campaign-jev.py").skip(
            READER, subject, f"the reading raised {e.__class__.__name__}", env,
            cwd=HERE)
    except Exception:  # noqa: BLE001 -- campaign-jev itself would not load
        pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
