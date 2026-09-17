#!/usr/bin/env python3
"""Log whether the evidence beside a settlement REPORT meets each Definition of done condition, and refuse nothing.

THE READINGS `done-report-select` and `done-report-claim` in
scripts/jev/readings.json, asked through scripts/campaign-jev.py. The entries
hold the questions, their criteria, the state's fields, the prefilter's
patterns, the thresholds and the tier; this reads them and writes none of
them. How to ask Jev well in general is the `asking-jev` skill's
`references/`, not this file's.

WHAT IT ADDS TO check-done-carry.py, WHOSE HOP IT REUSES: that reading asks
whether a TEST in the diff carries a condition. This one asks whether the
condition is MET, over a wider candidate set -- every hunk, code and test,
plus the REPORT's own result lines -- and shows the model what the REPORT
CLAIMS beside the evidence, which is what the earlier rounds of this reading
lacked: a REPORT alone says nothing of what a reviewer read in code. The
cutter, the selection and the claim builder are imported from that script and
not written twice. ONE COUPLING RIDES ON THAT: `select_questions` reads the
literal criteria key `{hunk}`, so this reading's entry spells it that way too,
though its state field is `candidates` and `r1..rM` are REPORT lines and no
hunk at all. The key is the placeholder's name, not a claim about what a
candidate is; `entry_reaches_model` in the suite goes red if either side
renames it.

WHO RUNS IT: scripts/check-campaign-claim.py, the comment guard, on every
`gh pr comment` whose first line opens `REPORT`, in the background, from the
checkout the post runs in, beside check-done-carry.py. The guard does not
wait, and runs BEFORE the post, so a REPORT it then refuses was read too.

WHAT IT READS: the REPORT on stdin; through `gh`, the pull request's closing
issues (`closingIssuesReferences`), each one's body, labels and state, its
comment kinds where a condition names one, and `gh pr diff`, which is GitHub's
patch and not this machine's git config.

  passed     another comment kind, or a REPORT that does not ask for the merge
             (the select entry's `reads_from` entry's `asks_merge`), asks
             nothing and logs nothing
  settled    a condition every clause of which is an event: the FACT is read
             from `gh` -- the pull request merged, the sub-issue closed, a
             label set, a comment of that kind posted -- and one `skipped` row
             carries the fact's name and what was read, so the share settled by
             code is counted off the log
  select     ONE call a sub-issue, state `{candidates}`, one `choice` a
             condition over the candidates and `noMatch`, the condition in the
             instructions; `noMatch` is itself the flag that nothing here is
             evidence
  claim      ONE call a candidate some condition picked, state `{evidence}`,
             one `choice` supports / contradicts / says_nothing a condition
             that picked it, the condition AND ITS REPORT LINE in the
             instructions -- the REPORT's line of highest token overlap with
             the condition, at or above the entry's `report_line_floor`, else
             the question's `no_report_line`. Nothing is asked for a condition
             that picked no candidate. A pick under the select entry's floor is
             asked too, on purpose: the met score below reads every pick, and
             the floor is the verdict's to apply, from the logged confidence
  logged     `<repo>#<pr> REPORT <issue> select` and
             `<repo>#<pr> REPORT <issue> claim <cand> <path>`
             (`tracker#<pr>` with no repo)
  skipped    one row for a pull request read that failed, for one closing no
             sub-issue with a Definition of done, for a diff and a REPORT
             yielding no candidate, for a select state over the budget, for
             each condition an event settles, and for a reading that raised

So a sub-issue costs at most one call plus one a distinct candidate picked,
and a condition at most two.

THE TIER is `shadow`: every call is logged by the caller and nothing is
printed, since the guard does not read this process's output.
THE EXIT STATUS IS 0 on every path the guard can reach; a usage error, a
first argument that is not a number, exits 2.

THE CASES are scripts/jev/corpus/done-report-select.jsonl, the conditions no
candidate is evidence for, since a candidate id is an option built per state
and no word of the entry, and done-report-claim.jsonl, each pick with its
truth. Where this reading is known to be wrong, as seen at jev-1.13.0 on
2026-09-18 (kalaluthien/campaign-base#458 Cl1), over 54 merged pull requests,
one a sub-issue, 204 conditions asked and 200 of them labelled against their
own words (114 met, 41 partly, 32 met by nothing here, 13 events) -- 51 of them T2's labels carried
over by (path, text) -- each met condition asked again with its evidence
removed:

  met        (1 - P(noMatch)) x P(supports), 0 where no candidate was picked;
             AUC 0.79 against the removed-evidence negatives and 0.93 against
             the conditions nothing here meets
  the line   THE REPORT LINE IS WHAT MAKES IT WORK: the same picks and the
             same evidence with the line withheld read 0.64 and 0.88. It does
             not raise a met condition's score -- that mean FALLS, 0.51
             with the line to 0.47 -- it pushes the negatives down harder,
             which is what a
             reading that separates does and what a mean cannot show
  baselines  token overlap 0.71 and 0.82; T2's carry over the same conditions
             0.58 and 0.82, its candidates being the test hunks alone
  no cut     the cut that flags EVERY negative is 0.99 and flags all 107 met
             lines -- so does every baseline's. This reading ORDERS and does
             not filter, and that is why it stays at `shadow`
  one cut    0.05 catches 30 of the 32 conditions nothing here meets and 82 of
             140 removed-evidence negatives, flagging 17 of 107 met lines
  selection  the labelled candidate was picked for 78 of 107 met conditions,
             `noMatch` for 4; 11 of the 107 picks were a REPORT result line
  prefilter  15 of 341 conditions settled by a fact (4%): 8 a comment posted,
             7 the merge; `label` and `closed` matched none in this sample
  reach      4 of 54 states (7%) were over the budget and asked nothing; 120
             of 326 conditions (37%) got no REPORT line at all
  noise      a repeat of 25 states WITH campaign-jev's store off moved 8
             verdicts of 93 -- 7 selects and 6 claims. With the store on it
             reads 0, because that key is the state and not the label

Usage: scripts/check-done-report.py <pr> [<repo>] < report
"""
import importlib.machinery
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELECT, CLAIM = "done-report-select", "done-report-claim"
REGISTRY = HERE / "jev" / "readings.json"
READER = "check-done-report.py"
CARRY = "check-done-carry.py"
TRACKER = "kalaluthien/campaign-base"
DOD = "## Definition of done"
# EVERY PATH IS A CANDIDATE'S PATH: this reading's candidates are the whole
# diff, where check-done-carry.py's are the test files alone. The cutter is
# that script's, given the screen that lets everything through.
ANY = re.compile("")
REPORT_PATH = "the REPORT"
CUT = "\n... cut"


def load_sibling(name):
    """A sibling script as a module, by path: these are scripts, not a package."""
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(HERE / name)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def result_lines(pattern, report):
    """{r1: {path, text}, ...}: the REPORT's lines quoting a suite result, in
    REPORT order. They are candidates beside the diff's hunks because a
    condition about a suite passing is met by a number and by no hunk."""
    hit = re.compile(pattern)
    found = [line.strip() for line in report.splitlines()
             if line.strip() and hit.search(line)]
    return {f"r{k}": {"path": REPORT_PATH, "text": t}
            for k, t in enumerate(found, 1)}


def report_line(overlap, floor, report, condition):
    """The REPORT's line carrying most of the condition's words, at or above
    `floor`; '' when none does. BY CODE AND NOT BY A CALL: which line a REPORT
    devotes to a condition is a match, and a second question would cost a call
    a condition where the whole design is one call a sub-issue."""
    best, score = "", floor
    for line in report.splitlines():
        line = line.strip()
        if not line:
            continue
        got = overlap(line, condition)
        if got >= score:
            best, score = line, got
    return best


def capped(text, ceiling):
    """The candidate's text, cut at `ceiling` BYTES of utf-8 and said to be cut.

    BYTES AND NOT CHARACTERS, because the state budget this ceiling exists to
    keep under is bytes: a character cut let 96 of 2733 candidates end past the
    declared 1200, the longest at 2042 (the REVIEW at 8b6f35a, D1). A cut
    landing inside a character drops that character rather than emitting half
    of it.

    WHY A CEILING AT ALL: over the 87 merged pull requests this reading builds
    a state for, the whole diff's hunks run a median of 36 KB and a maximum of
    204 KB against a 60 KB state budget, so without one 23 of them (26%) would
    be skipped unasked; with it, 9. The cut is measured with the rest: a hunk
    whose evidence sat past it is a miss this reading owns."""
    raw = text.encode("utf-8")
    if len(raw) <= ceiling:
        return text
    return raw[:ceiling].decode("utf-8", "ignore") + CUT


def fact_of(facts, text):
    """The name of the GitHub fact a settled condition turns on, or ''.

    The first pattern that matches wins, so the entry's order is the order they
    are tried in. Case is passed here and not spelled in the patterns, since
    `fact.closed` is also appended to a cut that already sets the flag, and an
    inline flag anywhere but the head of a joined pattern is a PatternError."""
    for name, pattern in facts.items():
        if re.search(pattern, text, re.I):
            return name
    return ""


def read_fact(gh, name, repo, pr, issue, seen):
    """What `gh` says about that fact, one line, read once per (fact, issue).

    A settled condition is not judged -- it is READ. At a settlement REPORT the
    pull request is not merged yet, so `merged` reads the state it is in and
    says so; that is the fact, not a failure."""
    # `label` and `closed` are one `gh issue view`, so they share a key: two
    # names reading one call must not cost two.
    key = (name if name in ("merged", "comment") else "issue", issue)
    if key in seen:
        return seen[key]
    if name == "merged":
        out, why = gh("pr", "view", str(pr), "-R", repo, "--json", "state",
                      "--jq", ".state")
        got = f"the pull request is {out.strip()}" if not why else f"unread: {why}"
    elif name == "comment":
        out, why = gh("api", f"repos/{repo}/issues/{issue}/comments",
                      "--jq", "[.[].body|split(\"\\n\")[0]|split(\" \")[0]]"
                      "|unique|join(\",\")")
        got = f"the comment kinds on it are {out.strip() or 'none'}" \
            if not why else f"unread: {why}"
    else:
        out, why = gh("issue", "view", str(issue), "-R", repo, "--json",
                      "state,labels", "--jq",
                      '.state + " / " + ([.labels[].name]|join(","))')
        got = f"the sub-issue is {out.strip()}" if not why else f"unread: {why}"
    seen[key] = got
    return got


def ask_issue(reg, subject, conds, cands, lines, jev, carry, env=None):
    """The two calls for one sub-issue; {condition id: candidate picked or None}."""
    ceiling = reg[SELECT]["prefilter"]["candidate_ceiling"]
    text = {k: capped(c["path"] + "\n" + c["text"], ceiling)
            for k, c in cands.items()}
    state = {"candidates": text}
    if len(json.dumps(state).encode("utf-8")) > jev.STATE_BUDGET:
        jev.skip(READER, f"{subject} select", f"the {len(cands)} candidates are "
                 f"over the {jev.STATE_BUDGET}-byte budget", env, cwd=HERE)
        return {}
    got = jev.ask(READER, f"{subject} select", state,
                  carry.select_questions(reg[SELECT], conds, cands),
                  env=env, cwd=HERE)
    picked = {cid: (a.raw or {}).get("choice") for cid, a in got.answers.items()}
    by_cand = {}
    for cid, h in picked.items():
        if h in cands:
            by_cand.setdefault(h, {})[cid] = conds[cid]
    none = reg[CLAIM]["question"]["no_report_line"]
    for h, asked in sorted(by_cand.items()):
        questions = carry.claim_questions(reg[CLAIM], asked)
        for cid, q in questions.items():
            q["instructions"] = q["instructions"].replace(
                "{reportLine}", lines.get(cid) or none)
        jev.ask(READER, f"{subject} claim {h} {cands[h]['path']}",
                {"evidence": text[h]}, questions, env=env, cwd=HERE)
    return picked


def main(argv, stdin=sys.stdin, env=None):
    if not 1 <= len(argv) <= 2 or not argv[0].isdigit():
        print("Usage: scripts/check-done-report.py <pr> [<repo>] < report",
              file=sys.stderr)
        return 2
    pr, repo = argv[0], (argv[1] if len(argv) > 1 else "")
    subject = f"{repo or 'tracker'}#{pr} REPORT"
    try:
        report = stdin.read()
        if not report.lstrip().startswith("REPORT "):
            return 0
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        pre = reg[SELECT]["prefilter"]
        # THE MOMENT AND THE EVENT CUT ARE READ FROM THE ENTRY THAT OWNS THEM,
        # never copied: this reading and done-test-select run on the same
        # comment, and two copies of one regex are two that drift. What this
        # reading adds it declares ONCE, in the one place it is also used: a
        # closed sub-issue is a fact this reading reads and an event that one
        # has no use for, so `fact.closed` is both.
        shared = dict(reg[pre["reads_from"]]["prefilter"])
        shared["event"] = shared["event"] + "|" + pre["fact"]["closed"]
        if not re.search(shared["asks_merge"], report):
            return 0
        jev = load_sibling("campaign-jev.py")
        carry = load_sibling(CARRY)
        target = ["-R", repo or TRACKER]
        view, why = carry.gh("pr", "view", pr, *target, "--json",
                             "closingIssuesReferences")
        if why:
            jev.skip(READER, subject, f"the pull request read failed: {why}",
                     env, cwd=HERE)
            return 0
        bodies = []
        for ref in json.loads(view)["closingIssuesReferences"]:
            name = f"{ref['repository']['owner']['login']}/{ref['repository']['name']}"
            body, why = carry.gh("issue", "view", str(ref["number"]), "-R", name,
                                 "--json", "body", "--jq", ".body")
            if why:
                jev.skip(READER, f"{subject} {ref['number']}",
                         f"the issue read failed: {why}", env, cwd=HERE)
            elif DOD in body:
                bodies.append((name, ref["number"], body))
        if not bodies:
            jev.skip(READER, subject, "the pull request closes no issue with a "
                     "Definition of done", env, cwd=HERE)
            return 0
        diff, why = carry.gh("pr", "diff", pr, *target)
        if why:
            jev.skip(READER, subject, f"the diff read failed: {why}", env, cwd=HERE)
            return 0
        cands = carry.hunks(diff, ANY)
        cands.update(result_lines(pre["result_line"], report))
        if not cands:
            jev.skip(READER, subject, "the diff has no hunk and the REPORT "
                     "quotes no result, so there is no evidence to weigh",
                     env, cwd=HERE)
            return 0
        seen = {}
        for name, number, body in bodies:
            conds, lines = {}, {}
            for k, text in enumerate(carry.conditions(body), 1):
                cid = f"c{k}"
                if carry.settled(shared, text):
                    fact = fact_of(pre["fact"], text) or "event"
                    read = read_fact(carry.gh, fact, name, pr, number, seen) \
                        if fact != "event" else "no fact here reads it"
                    jev.skip(READER, f"{subject} {number} {cid}",
                             f"an event, settled by the GitHub fact `{fact}`: "
                             f"{read}", env, cwd=HERE)
                else:
                    conds[cid] = text
                    lines[cid] = report_line(jev.overlap,
                                             pre["report_line_floor"],
                                             report, text)
            if conds:
                ask_issue(reg, f"{subject} {number}", conds, cands, lines,
                          jev, carry, env)
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
