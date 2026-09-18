#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-done-report.py asks one select call a sub-issue and one claim call a candidate picked, reads each settled condition's fact from gh, and never refuses.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers each
select question with the candidate a case names for its condition, and each
claim question `supports`; a stub `gh` on PATH answers the pull request's
closing issues, each issue's body, its state and labels, and the diff, from a
case's own JSON. The reader runs from a fixture directory holding the real
scripts/campaign-jev.py, the real check-done-carry.py whose cutter, selection
and claim builder it imports, and three registry entries -- its own two, and
the `done-test-select` its prefilter reads the moment and the event cut from.
Each case is then broken by a mutation of the reader's text and must go red by
its own assertion.

`--live` asks every line of scripts/jev/corpus/done-report-select.jsonl and
done-report-claim.jsonl against the real endpoint and prints each answer
beside its truth; `--record` appends the reading to `seen`.

Usage: scripts/check-done-report-test.py [--live [--record]]
"""
import datetime
import hashlib
import http.server
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import types
from pathlib import Path

harness = importlib.import_module("suite-harness-test")
check = harness.check

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-done-report.py"
SOURCE = SCRIPT.read_text()
ENTRIES = json.loads((HERE / "jev" / "readings.json").read_text())
SELECT, CLAIM = ENTRIES["done-report-select"], ENTRIES["done-report-claim"]
SHARED = ENTRIES["done-test-select"]
CEILING = SELECT["prefilter"]["candidate_ceiling"]
CORPUS = HERE / "jev" / "corpus"
BUDGET = importlib.import_module("campaign-jev").STATE_BUDGET
ROOT = Path(tempfile.mkdtemp(prefix="done-report-"))

REPORT = ("REPORT demo-worker-1: pr#9 at abcdef1, asking for the merge\n"
          "\n"
          "The suite refuses an empty name, with a named case at line 12.\n"
          "Suites here: 12/12, 0 findings.\n")
# A REPORT WHOSE EVERY LINE IS BELOW THE FLOOR for both conditions: the claim
# then carries the entry's `no_report_line` and not a line that matched nothing.
BARE = ("REPORT demo-worker-1: pr#9 at abcdef1, asking for the merge\n"
        "\n"
        "12/12, 0 findings.\n")
# AND ONE QUOTING NO RESULT AT ALL, so a diff with no hunk leaves no candidate.
QUIET = "REPORT demo-worker-1: pr#9, asking for the merge\n"

BODY = """## Intent

- x

## Definition of done

- `tool` refuses an empty name, with a named case.
- `tool --list` prints every name
  sorted by date.
- The pull request is merged and the install shows it.
- The `backlog` label is removed.
- The sub-issue is closed as completed.

## Plan

- y
"""
DIFF = """diff --git a/scripts/tool.py b/scripts/tool.py
--- a/scripts/tool.py
+++ b/scripts/tool.py
@@ -1,2 +1,3 @@
 a
+b
diff --git a/scripts/tool-test.py b/scripts/tool-test.py
--- a/scripts/tool-test.py
+++ b/scripts/tool-test.py
@@ -10,2 +10,4 @@ def cases():
+def refuses_empty():
+    assert run("").code == 2
@@ -40,1 +42,2 @@ def more():
+def lists_sorted(): pass
"""
H2 = ("scripts/tool-test.py\n@@ -10,2 +10,4 @@ def cases():\n"
      "+def refuses_empty():\n+    assert run(\"\").code == 2")
R1 = "the REPORT\nSuites here: 12/12, 0 findings."
PICKS = {"refuses an empty name": "h2", "prints every name": "r1"}

SEEN = []
LOGGED = []


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        answers = {}
        for q, spec in body["questions"].items():
            if "candidates" in body["state"]:
                pick = next((h for k, h in PICKS.items()
                             if k in spec["instructions"]), "noMatch")
                answers[q] = {"type": "choice", "choice": pick, "confidence": 0.9,
                              "probabilities": {pick: 0.9}}
            else:
                answers[q] = {"type": "choice", "choice": "supports",
                              "confidence": 0.9,
                              "probabilities": {"supports": 0.9,
                                                "contradicts": 0.05,
                                                "says_nothing": 0.05}}
        data = json.dumps({"model": "jev-1.13.0", "answers": answers}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


SERVER = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{SERVER.server_address[1]}/v1/systemone"


def load(source):
    m = types.ModuleType("donereport")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return types.SimpleNamespace(source=source, m=m)


def closing(*numbers, owner="kalaluthien", name="campaign-base"):
    return {"closingIssuesReferences": [
        {"number": n, "repository": {"name": name, "owner": {"login": owner}}}
        for n in numbers]}


def registry(shared=None):
    return {"done-report-select": SELECT, "done-report-claim": CLAIM,
            "done-test-select": shared or SHARED}


def run(t, report=REPORT, argv=("9",), view=None, bodies=None, diff=DIFF,
        fail=(), reg=None):
    """The finished process; `gh-argv.jsonl` in its directory holds each gh call.
    `fail` names the gh verbs (`pr view`, `pr view state`, `issue view`,
    `pr diff`) that exit 1. Every run NAMES a log, because since pr#474 a
    stubbed endpoint that names none writes nothing at all -- campaign-jev-test.py
    owns that rule."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    (d / "jev").mkdir()
    (d / "bin").mkdir()
    (d / "check-done-report.py").write_text(t.source)
    shutil.copy(HERE / "campaign-jev.py", d / "campaign-jev.py")
    shutil.copy(HERE / "check-done-carry.py", d / "check-done-carry.py")
    (d / "jev" / "readings.json").write_text(json.dumps(reg or registry()))
    answers = {"pr view": json.dumps(closing(5) if view is None else view),
               "pr view state": "MERGED\n", "pr diff": diff}
    for n, body in (bodies if bodies is not None else {5: BODY}).items():
        answers[f"issue view {n}"] = body
        answers[f"issue view {n} state"] = "OPEN / kind:dev\n"
    (d / "answers.json").write_text(json.dumps(answers))
    (d / "bin" / "gh").write_text(
        "#!/usr/bin/env python3\nimport json, sys\n"
        f"open({str(d / 'gh-argv.jsonl')!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        f"a = json.load(open({str(d / 'answers.json')!r}))\n"
        "v = sys.argv[1:]\n"
        "verb = v[0] if v[0] == 'api' else ' '.join(v[:2])\n"
        "j = v[v.index('--json') + 1] if '--json' in v else ''\n"
        "key = verb + (' ' + v[2] if verb == 'issue view' else '')\n"
        "if 'state' in j:\n    key += ' state'\n"
        f"if key in {list(fail)!r} or verb in {list(fail)!r}:\n"
        "    sys.exit('gh stub: refused')\n"
        "sys.stdout.write(a[key])\n")
    (d / "bin" / "gh").chmod(0o755)
    SEEN.clear()
    env = dict(os.environ, CAMPAIGN_JEV_URL=URL, TYPESAFE_API_KEY="stub",
               CAMPAIGN_JEV_LOG=str(d / "jev.log"), HOME=str(d),
               PATH=f"{d / 'bin'}:{os.environ['PATH']}")
    r = subprocess.run([sys.executable, str(d / "check-done-report.py"), *argv],
                       input=report, capture_output=True, text=True, env=env)
    log = d / "jev.log"
    LOGGED[:] = ([json.loads(x) for x in log.read_text().splitlines() if x]
                 if log.exists() else [])
    calls = d / "gh-argv.jsonl"
    r.gh = ([json.loads(x) for x in calls.read_text().splitlines()]
            if calls.exists() else [])
    return r


def reads():
    return [(x["read"], x.get("skipped")) for x in LOGGED]


FACT = "an event, settled by the GitHub fact `{}`: {}"
MERGED = ("tracker#9 REPORT 5 c3", FACT.format("merged", "the pull request is MERGED"))
LABEL = ("tracker#9 REPORT 5 c4", FACT.format("label", "the sub-issue is OPEN / kind:dev"))
CLOSED = ("tracker#9 REPORT 5 c5", FACT.format("closed", "the sub-issue is OPEN / kind:dev"))


def one_select_and_one_claim_a_candidate(t):
    r = run(t)
    kinds = ["select" if "candidates" in b["state"] else "claim" for b in SEEN]
    return (r.returncode == 0 and r.stdout == ""
            and kinds == ["select", "claim", "claim"]
            and [sorted(q.split("#", 1)[-1] for q in b["questions"])
                 for b in SEEN] == [["c1", "c2"], ["c1"], ["c2"]]
            and SEEN[1]["state"] == {"evidence": H2}
            and SEEN[2]["state"] == {"evidence": R1}
            and reads() == [MERGED, LABEL, CLOSED,
                            ("tracker#9 REPORT 5 select", None),
                            ("tracker#9 REPORT 5 claim h2 scripts/tool-test.py", None),
                            ("tracker#9 REPORT 5 claim r1 the REPORT", None)]
            ), (r.stderr[-300:], kinds, reads())


def candidates_are_every_hunk_and_the_result_lines(t):
    run(t)
    cands = SEEN[0]["state"]["candidates"] if SEEN else {}
    return (sorted(cands) == ["h1", "h2", "h3", "r1"]
            and cands["h1"].startswith("scripts/tool.py\n@@ -1,2")
            and cands["h2"].startswith("scripts/tool-test.py\n@@ -10,2")
            and cands["h3"].startswith("scripts/tool-test.py\n@@ -40,1")
            and cands["r1"] == R1), cands


def entry_reaches_model(t):
    run(t)
    q = SEEN[0]["questions"].get("done-report-select#c2", {}) if SEEN else {}
    c = SEEN[1]["questions"].get("done-report-claim#c1", {}) if len(SEEN) > 1 else {}
    want = SELECT["question"]["instructions"].replace(
        "{condition}", "`tool --list` prints every name sorted by date.")
    crit = SELECT["question"]["criteria"]["{hunk}"]
    return (q.get("instructions") == want
            and sorted(q.get("criteria", {})) == ["h1", "h2", "h3", "noMatch", "r1"]
            and q["criteria"]["h1"] == crit.replace("{hunk}", "h1")
            .replace("{path}", "scripts/tool.py")
            and q["criteria"]["r1"] == crit.replace("{hunk}", "r1")
            .replace("{path}", "the REPORT")
            and c.get("criteria") == CLAIM["question"]["criteria"]
            and "floor" not in q and "yes_over" not in c), (q, c)


def the_report_line_reaches_the_claim(t):
    run(t)
    c = SEEN[1]["questions"].get("done-report-claim#c1", {}) if len(SEEN) > 1 else {}
    line = "The suite refuses an empty name, with a named case at line 12."
    want = (CLAIM["question"]["instructions"].replace("{reportLine}", line)
            .replace("{condition}", "`tool` refuses an empty name, with a named case."))
    return c.get("instructions") == want, c.get("instructions")


def no_report_line_says_so(t):
    run(t, report=BARE)
    c = SEEN[1]["questions"].get("done-report-claim#c1", {}) if len(SEEN) > 1 else {}
    return (CLAIM["question"]["no_report_line"] in c.get("instructions", "")
            and "12/12" not in c.get("instructions", "")), c.get("instructions")


def no_pick_asks_no_claim(t):
    """`noMatch` is the flag that nothing here is evidence, and it is never a
    candidate: a claim call over it would read a state that does not exist."""
    saved = dict(PICKS)
    PICKS.clear()
    try:
        r = run(t)
    finally:
        PICKS.update(saved)
    kinds = ["select" if "candidates" in b["state"] else "claim" for b in SEEN]
    return (r.returncode == 0 and kinds == ["select"]
            and reads()[-1] == ("tracker#9 REPORT 5 select", None)), (kinds, reads())


def two_conditions_one_candidate_one_call(t):
    PICKS["prints every name"] = "h2"
    try:
        run(t)
    finally:
        PICKS["prints every name"] = "r1"
    claims = [b for b in SEEN if "evidence" in b["state"]]
    asked = sorted(q.split("#", 1)[-1] for q in claims[0]["questions"]) \
        if claims else []
    return len(claims) == 1 and asked == ["c1", "c2"], SEEN


def a_long_candidate_is_cut(t):
    """THE CUT IS BYTES, and the fixture is multi-byte so a character cut fails
    it: `'x' * n` passes either rule and pinned nothing (the REVIEW at 8b6f35a,
    D1). An em dash is 3 bytes, so a character cut would send 3x the ceiling."""
    big = (DIFF + "diff --git a/scripts/big.py b/scripts/big.py\n"
           f"@@ -1 +1 @@\n+{'\u2014' * CEILING}\n")
    run(t, diff=big)
    cands = SEEN[0]["state"]["candidates"] if SEEN else {}
    got = cands.get("h4", "")
    body = got[:-len("\n... cut")] if got.endswith("\n... cut") else got
    return (got.endswith("\n... cut")
            and len(body.encode("utf-8")) <= CEILING
            and len(body.encode("utf-8")) > CEILING - 4
            and len(cands["h1"].encode("utf-8")) < CEILING
            ), (len(got), len(got.encode("utf-8")))


def a_cut_never_splits_a_character(t):
    """A ceiling landing mid-character: the character goes, and what comes back
    is still text -- never a lone half of one."""
    got = [t.m.capped("a" * n + "\u2014" * 10, CEILING) for n in
           (CEILING - 2, CEILING - 1, CEILING)]
    return all(g.endswith(t.m.CUT) and len(g[:-len(t.m.CUT)].encode()) <= CEILING
               and "\ufffd" not in g for g in got), got


def a_settled_condition_reads_its_fact(t):
    r = run(t)
    state = [c for c in r.gh if c[:2] == ["pr", "view"] and "state" in c]
    issue = [c for c in r.gh if c[:2] == ["issue", "view"] and "state,labels" in c]
    return ([x for x in reads() if x[0][-2:] in ("c3", "c4", "c5")]
            == [MERGED, LABEL, CLOSED]
            and len(state) == 1 and len(issue) == 1), (reads(), r.gh)


def one_gh_read_a_fact(t):
    """`label` and `closed` are one `gh issue view`: two settled conditions
    turning on it read it once, so two names never cost two calls."""
    r = run(t)
    issue = [c for c in r.gh if c[:2] == ["issue", "view"] and "state,labels" in c]
    return len(issue) == 1 and [x[0] for x in reads()][:3] == [
        MERGED[0], LABEL[0], CLOSED[0]], r.gh


def an_unread_fact_says_so(t):
    """A fact `gh` refused is still one skip row, saying it went unread: a
    settled condition is never asked, and never silently dropped."""
    r = run(t, fail=("pr view state",))
    got = dict(reads())
    return (r.returncode == 0
            and got.get(MERGED[0], "").endswith("unread: gh stub: refused")
            and got.get(LABEL[0]) == LABEL[1]), reads()


def no_merge_ask_asks_nothing(t):
    r = run(t, report="REPORT demo-worker-1: pr#9 merged at abcdef1\n")
    return r.returncode == 0 and not SEEN and not LOGGED and not r.gh, (SEEN, LOGGED)


def other_comment_asks_nothing(t):
    r = run(t, report="NOTE demo-worker-1: asking for the merge\n")
    return r.returncode == 0 and not SEEN and not LOGGED, (SEEN, LOGGED)


def no_done_issue_skips(t):
    r = run(t, bodies={5: "## Intent\n\n- x\n"})
    return (r.returncode == 0 and not SEEN and reads() == [
        ("tracker#9 REPORT", "the pull request closes no issue with a "
                             "Definition of done")]), reads()


def no_candidate_skips(t):
    r = run(t, diff="", report=QUIET)
    return (r.returncode == 0 and not SEEN and reads() == [
        ("tracker#9 REPORT", "the diff has no hunk and the REPORT quotes no "
                             "result, so there is no evidence to weigh")]), reads()


def over_budget_skips(t):
    n = BUDGET // CEILING + 2
    big = DIFF + "".join(f"diff --git a/scripts/b{i}.py b/scripts/b{i}.py\n"
                         f"@@ -1 +1 @@\n+{'x' * CEILING}\n" for i in range(n))
    r = run(t, diff=big)
    return (r.returncode == 0 and not SEEN
            and reads()[-1][0] == "tracker#9 REPORT 5 select"
            and f"over the {BUDGET}-byte budget" in (reads()[-1][1] or "")), reads()


def failed_pr_read_skips(t):
    r = run(t, fail=("pr view",))
    return (r.returncode == 0 and not SEEN and len(LOGGED) == 1
            and LOGGED[0]["skipped"] == "the pull request read failed: "
                                        "gh stub: refused"), reads()


def failed_issue_read_skips(t):
    r = run(t, fail=("issue view",))
    return (r.returncode == 0 and not SEEN and reads() == [
        ("tracker#9 REPORT 5", "the issue read failed: gh stub: refused"),
        ("tracker#9 REPORT", "the pull request closes no issue with a "
                             "Definition of done")]), reads()


def failed_diff_read_skips(t):
    r = run(t, fail=("pr diff",))
    return (r.returncode == 0 and not SEEN and reads() == [
        ("tracker#9 REPORT", "the diff read failed: gh stub: refused")]), reads()


def repository_reaches_gh(t):
    r = run(t, argv=("9", "o/r"))
    named = [(c[0], c[1], c[4]) for c in r.gh if len(c) > 4 and c[3] == "-R"]
    return (("pr", "view", "o/r") in named
            and ("issue", "view", "kalaluthien/campaign-base") in named
            and ("pr", "diff", "o/r") in named
            and LOGGED[-1]["read"].startswith("o/r#9 REPORT 5")), (named, reads())


def tracker_is_the_default(t):
    """EVERY gh call names a repository, and with no argument it is the
    tracker: a call that named none would read whatever checkout it ran in."""
    r = run(t)
    named = [c[c.index("-R") + 1] if "-R" in c else None for c in r.gh]
    return (len(r.gh) >= 3
            and named == ["kalaluthien/campaign-base"] * len(r.gh)), r.gh


def failure_exits_zero(t):
    r = run(t, view={"closing": []})
    return (r.returncode == 0 and r.stdout == "" and r.stderr == "" and not SEEN
            and reads() == [("tracker#9 REPORT", "the reading raised KeyError")]
            ), (r.stderr[-300:], reads())


def result_lines_cut(t):
    pattern = SELECT["prefilter"]["result_line"]
    report = ("REPORT x: asking for the merge\n"
              "\n"
              "Prose about the design that quotes nothing.\n"
              "47/47, 649/649, 0 findings.\n"
              "45 suites here, none failed.\n"
              "  1 defect, 3 refinements.  \n")
    got = t.m.result_lines(pattern, report)
    return (sorted(got) == ["r1", "r2", "r3"]
            and [got[k]["text"] for k in ("r1", "r2", "r3")] == [
                "47/47, 649/649, 0 findings.", "45 suites here, none failed.",
                "1 defect, 3 refinements."]
            and {v["path"] for v in got.values()} == {"the REPORT"}), got


def the_report_line_is_the_best_over_the_floor(t):
    jev = t.m.load_sibling("campaign-jev.py")
    report = ("REPORT x: asking for the merge\n"
              "It names an empty case.\n"
              "The suite refuses an empty name with a named case.\n")
    cond = "`tool` refuses an empty name, with a named case."
    best = t.m.report_line(jev.overlap, 0.15, report, cond)
    far = t.m.report_line(jev.overlap, 0.99, report, cond)
    none = t.m.report_line(jev.overlap, 0.15, report,
                           "Alloy scopes exhaust cleanly")
    return (best == "The suite refuses an empty name with a named case."
            and far == "" and none == ""), (best, far, none)


def facts_are_read_in_order(t):
    pre = SELECT["prefilter"]["fact"]
    cases = {
        "The `backlog` label is removed.": "label",
        "The `backlog` label is removed and the sub-issue closed.": "label",
        "The sub-issue is closed as completed.": "closed",
        "The closing NOTE quotes the counts.": "comment",
        "The pull request is merged and the install shows it.": "merged",
        "The suite passes.": "",
    }
    got = {c: t.m.fact_of(pre, c) for c in cases}
    return got == cases, got


def a_closed_sub_issue_is_an_event_here(t):
    """`fact.closed` widens the shared cut AND names the fact, one string doing
    both: with it dropped, a closed sub-issue is no event and is asked."""
    pre = dict(SELECT["prefilter"])
    shared = dict(SHARED["prefilter"])
    both = dict(shared, event=shared["event"] + "|" + pre["fact"]["closed"])
    carry = t.m.load_sibling(t.m.CARRY)
    text = "The sub-issue is closed as completed."
    return (carry.settled(both, text) and not carry.settled(shared, text)
            ), (carry.settled(both, text), carry.settled(shared, text))


def the_moment_is_read_from_the_other_entry(t):
    """The prefilter's `reads_from` is followed, not copied: with the shared
    entry's `asks_merge` cut to something this REPORT cannot match, nothing is
    asked -- so this reader really reads that entry and holds no copy."""
    shared = dict(SHARED, prefilter=dict(SHARED["prefilter"],
                                         asks_merge="NEVER MATCHES THIS"))
    r = run(t, reg=registry(shared))
    return (r.returncode == 0 and not SEEN and not LOGGED and not r.gh
            ), (SEEN, reads())


class RecordingJev:
    """A jev double that answers nothing and keeps the `cwd` of every call.

    The shared log is where `cwd` used to be observable, and since pr#474 a
    stubbed endpoint that names no log writes nothing at all -- on purpose, so
    a suite's answers can never reach the log the corpus grows from. So the
    reader's side of the rule is asserted where the reader makes it: every
    call names the reader's OWN base, never the process's cwd, which is what
    puts a production row in that reader's `runtime/jev.log` when a session
    runs it from some other checkout. Its budget is `BUDGET`, this file's one
    reading of the real one, since a copy of its own passes a moved budget."""

    STATE_BUDGET = BUDGET    # the real one, read once at the top of this file

    def __init__(self):
        self.cwds = []

    @staticmethod
    def overlap(text, against):
        return 1.0

    def judge(self, group, state, read="", reader="", key=None, env=None,
              cwd=None):
        self.cwds.append(cwd)
        return types.SimpleNamespace(verdicts={group: types.SimpleNamespace(
            raw={cid: {"choice": "h1"} for cid in state.get("condition") or {}},
            why={})})

    def words_of(self, entry, verdict):
        return {cid: types.SimpleNamespace(raw=raw)
                for cid, raw in (verdict.raw or {}).items()}

    def skip(self, reader, label, why, env=None, cwd=None):
        self.cwds.append(cwd)


NO_DOD = "## Intent\n\n- x\n"
EVENTS_ONLY = ("## Definition of done\n\n- The pull request is merged and the "
               "install shows it.\n\n## Plan\n\n- y\n")


def drive(t, jev, answers, diff=DIFF, body=BODY, report=REPORT):
    """`main()` once with `jev` in place of the real one, over a gh double.

    `answers` names the gh verbs that fail. check-done-carry.py is loaded for
    real and its `gh` replaced, since that is the one this reader calls."""
    real = t.m.load_sibling
    carry = real(t.m.CARRY)
    carry.gh = lambda *a: (
        ("", "gh double: refused") if " ".join(a[:2]) in answers else
        (json.dumps(closing(5)), "") if a[:2] == ("pr", "view")
        and "closingIssuesReferences" in a else
        ("MERGED", "") if a[:2] == ("pr", "view") else
        (diff, "") if a[:2] == ("pr", "diff") else
        ("OPEN / kind:dev", "") if "state,labels" in a else (body, ""))
    t.m.load_sibling = lambda n: (jev if n == "campaign-jev.py" else
                                  carry if n == t.m.CARRY else real(n))
    try:
        return t.m.main(["9"], io.StringIO(report))
    finally:
        t.m.load_sibling = real


def every_jev_call_names_the_readers_base(t):
    """Every one of the reader's call sites, and each must name HERE.

    ask_issue's three are driven directly; main()'s are driven through main()
    itself, because a case that calls the inner function supplies the argument
    the call site was supposed to be pinned for -- that is how the same case
    lost main()'s skips once in T2 (the REVIEW at 318a053, D1)."""
    reg = registry()
    conds = {"c1": "a condition one hunk could show"}
    cands = {"h1": {"path": "scripts/tool.py", "text": "@@ -1 +1 @@\n+x"}}
    inner, over = RecordingJev(), RecordingJev()
    t.m.ask_issue(reg, "tracker#9 REPORT 5", conds, cands, {"c1": "a line"},
                  inner)
    t.m.ask_issue(reg, "tracker#9 REPORT 5", conds,
                  {f"h{i}": {"path": "p", "text": "x" * CEILING}
                   for i in range(BUDGET // CEILING + 2)},
                  {"c1": "a line"}, over)
    seen, counts = [], []
    for kw in ({"answers": {"pr view"}},              # the pull request read failed
               {"answers": {"issue view"}},           # the issue read failed
               {"answers": (), "body": NO_DOD},       # closes no issue with a DoD
               {"answers": {"pr diff"}},              # the diff read failed
               {"answers": (), "diff": "", "report": QUIET},   # no candidate
               {"answers": (), "body": EVENTS_ONLY},  # one settled condition
               {"answers": ()}):                      # three skips, then both asks
        one = RecordingJev()
        drive(t, one, **{"answers": kw.pop("answers"), **kw})
        seen += one.cwds
        counts.append(len(one.cwds))
    raised = RecordingJev()
    raised.judge = raised.skip        # a skip signature for a judge call: TypeError
    drive(t, raised, answers=())
    seen += raised.cwds
    named = inner.cwds + over.cwds + seen
    # `== 4` and not `>= 1`: the three settled skips land first, so only the
    # count says skipped() itself ran.
    return (set(named) == {t.m.HERE} and counts == [1, 2, 1, 1, 1, 1, 5]
            and len(raised.cwds) == 4), (counts, len(raised.cwds),
                                         sorted(set(map(str, named))))


CASES = {
    "a settlement REPORT asks one select call a sub-issue and one claim call a candidate picked": one_select_and_one_claim_a_candidate,
    "the candidates are every hunk, code and test, and the REPORT's result lines": candidates_are_every_hunk_and_the_result_lines,
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "the condition's REPORT line reaches the claim's instructions": the_report_line_reaches_the_claim,
    "a condition no REPORT line matches carries the entry's words for that": no_report_line_says_so,
    "a select answering noMatch throughout asks no claim call": no_pick_asks_no_claim,
    "two conditions picking one candidate share one claim call": two_conditions_one_candidate_one_call,
    "a candidate over the ceiling is cut at bytes and says it was": a_long_candidate_is_cut,
    "a cut landing inside a character drops it, never halves it": a_cut_never_splits_a_character,
    "a settled condition's GitHub fact is read and named in its skip": a_settled_condition_reads_its_fact,
    "a label and a closed fact are one issue read, not two": one_gh_read_a_fact,
    "a fact gh refused is still one skip row, saying it went unread": an_unread_fact_says_so,
    "a REPORT not asking for the merge asks and logs nothing": no_merge_ask_asks_nothing,
    "a comment of another kind asks nothing": other_comment_asks_nothing,
    "a pull request closing no Definition of done logs one skip": no_done_issue_skips,
    "a diff and a REPORT yielding no candidate log one skip": no_candidate_skips,
    "a select state over the budget is not sent and logs a skip": over_budget_skips,
    "a failed pull request read logs one skip": failed_pr_read_skips,
    "a failed issue read logs a skip for that issue": failed_issue_read_skips,
    "a failed diff read logs one skip": failed_diff_read_skips,
    "a member pull request is read in its repository, its tracker issue in the tracker": repository_reaches_gh,
    "with no repository gh is told the tracker": tracker_is_the_default,
    "a reader that raised exits 0, says nothing and logs a skip": failure_exits_zero,
    "the REPORT's result lines are cut, and its prose is not one": result_lines_cut,
    "the REPORT line is the best line at or over the floor, else none": the_report_line_is_the_best_over_the_floor,
    "each settled condition names the first fact its words match": facts_are_read_in_order,
    "a closed sub-issue is an event here and not in the entry read from": a_closed_sub_issue_is_an_event_here,
    "the merge ask is read from the entry `reads_from` names, not a copy": the_moment_is_read_from_the_other_entry,
    "every jev call names the reader's own base, not the process cwd": every_jev_call_names_the_readers_base,
}

MUTATIONS = [
    ("a call a condition",
     '                    {"candidates": text, "condition": conds},',
     '                    {"candidates": text,\n'
     '                     "condition": dict(list(conds.items())[:1])},',
     "a settlement REPORT asks one select call a sub-issue and one claim call a candidate picked"),
    ("a claim call for noMatch", "        if h in cands:", "        if h:",
     "a select answering noMatch throughout asks no claim call"),
    ("a claim call a condition",
     "            by_cand.setdefault(h, {})[cid] = conds[cid]",
     "            by_cand[h + cid] = {cid: conds[cid]}; cands[h + cid] = cands[h]; text[h + cid] = text[h]",
     "two conditions picking one candidate share one claim call"),
    ("the test screen kept, so a code hunk is no candidate",
     "        cands = carry.hunks(diff, ANY)",
     '        cands = carry.hunks(diff, carry.load_sibling("check-diff-screen.py").TEST)',
     "the candidates are every hunk, code and test, and the REPORT's result lines"),
    ("the REPORT's result lines not candidates",
     '        cands.update(result_lines(pre["result_line"], report))', "        pass",
     "the candidates are every hunk, code and test, and the REPORT's result lines"),
    ("the path dropped from a candidate",
     '    text = {k: capped(c["path"] + "\\n" + c["text"], ceiling)',
     '    text = {k: capped(c["text"], ceiling)',
     "the candidates are every hunk, code and test, and the REPORT's result lines"),
    ("a REPORT line given a file's path", 'REPORT_PATH = "the REPORT"',
     'REPORT_PATH = "scripts/tool.py"',
     "the entry's instructions and criteria reach the model, thresholds do not"),
    ("the REPORT line never handed to the claim call",
     '                   "reportLine": {cid: lines.get(cid) or none for cid in asked}},',
     '                   "reportLine": {}},',
     "the condition's REPORT line reaches the claim's instructions"),
    ("the condition handed in its REPORT line's place",
     '                   "reportLine": {cid: lines.get(cid) or none for cid in asked}},',
     '                   "reportLine": dict(asked)},',
     "the condition's REPORT line reaches the claim's instructions"),
    ("no words for a condition the REPORT misses",
     '                   "reportLine": {cid: lines.get(cid) or none for cid in asked}},',
     '                   "reportLine": {cid: lines.get(cid, "") for cid in asked}},',
     "a condition no REPORT line matches carries the entry's words for that"),
    ("the ceiling not applied",
     '    raw = text.encode("utf-8")\n    if len(raw) <= ceiling:\n        return text',
     '    raw = text.encode("utf-8")\n    if True:\n        return text',
     "a candidate over the ceiling is cut at bytes and says it was"),
    ("the cut not said", 'CUT = "\\n... cut"', 'CUT = ""',
     "a candidate over the ceiling is cut at bytes and says it was"),
    ("the ceiling read as characters, not bytes",
     '    raw = text.encode("utf-8")\n    if len(raw) <= ceiling:\n        return text\n    return raw[:ceiling].decode("utf-8", "ignore") + CUT',
     "    return text if len(text) <= ceiling else text[:ceiling] + CUT",
     "a candidate over the ceiling is cut at bytes and says it was"),
    ("a cut that halves a character",
     '    return raw[:ceiling].decode("utf-8", "ignore") + CUT',
     '    return raw[:ceiling].decode("utf-8", "replace") + CUT',
     "a cut landing inside a character drops it, never halves it"),
    ("the fact not read",
     '                    read = read_fact(carry.gh, fact, name, pr, number, seen) \\\n                        if fact != "event" else "no fact here reads it"',
     '                    read = "no fact here reads it"',
     "a settled condition's GitHub fact is read and named in its skip"),
    ("the fact's name dropped",
     '                             f"an event, settled by the GitHub fact `{fact}`: "',
     '                             f"an event, settled by the GitHub fact: "',
     "a settled condition's GitHub fact is read and named in its skip"),
    ("a fact read once a name",
     '    key = (name if name in ("merged", "comment") else "issue", issue)',
     "    key = (name, issue)",
     "a label and a closed fact are one issue read, not two"),
    ("an unread pull request state taken for a reading",
     '        got = f"the pull request is {out.strip()}" if not why else f"unread: {why}"',
     '        got = f"the pull request is {out.strip()}"',
     "a fact gh refused is still one skip row, saying it went unread"),
    ("the merge ask not read",
     '        if not re.search(shared["asks_merge"], report):', "        if False:",
     "a REPORT not asking for the merge asks and logs nothing"),
    ("the moment copied instead of read",
     '        shared = dict(reg[pre["reads_from"]]["prefilter"])',
     '        shared = dict(reg[pre["reads_from"]]["prefilter"], asks_merge="(?i)merge")',
     "the merge ask is read from the entry `reads_from` names, not a copy"),
    ("the event cut not widened",
     '        shared["event"] = shared["event"] + "|" + pre["fact"]["closed"]',
     "        pass",
     "a settlement REPORT asks one select call a sub-issue and one claim call a candidate picked"),
    ("the comment kind not read",
     'if not report.lstrip().startswith("REPORT "):', "if False:",
     "a comment of another kind asks nothing"),
    ("an issue with no DoD asked", "            elif DOD in body:", "            elif True:",
     "a pull request closing no Definition of done logs one skip"),
    ("no candidate not skipped", "        if not cands:", "        if False:",
     "a diff and a REPORT yielding no candidate log one skip"),
    ("the budget not read",
     '    if len(json.dumps({"candidates": text}).encode("utf-8")) > jev.STATE_BUDGET:',
     "    if False:",
     "a select state over the budget is not sent and logs a skip"),
    ("a failed pr read taken for one",
     '        view, why = carry.gh("pr", "view", pr, *target, "--json",\n                             "closingIssuesReferences")\n        if why:',
     '        view, why = carry.gh("pr", "view", pr, *target, "--json",\n                             "closingIssuesReferences")\n        if False:',
     "a failed pull request read logs one skip"),
    ("a failed issue read unlogged",
     '                jev.skip(READER, f"{subject} {ref[\'number\']}",\n                         f"the issue read failed: {why}", env, cwd=HERE)',
     "                pass",
     "a failed issue read logs a skip for that issue"),
    ("a failed diff read taken for one",
     '        diff, why = carry.gh("pr", "diff", pr, *target)\n        if why:',
     '        diff, why = carry.gh("pr", "diff", pr, *target)\n        if False:',
     "a failed diff read logs one skip"),
    ("the repository dropped", 'target = ["-R", repo or TRACKER]', 'target = ["-R", TRACKER]',
     "a member pull request is read in its repository, its tracker issue in the tracker"),
    ("no tracker default", 'target = ["-R", repo or TRACKER]', 'target = ["-R", repo] if repo else []',
     "with no repository gh is told the tracker"),
    ("the failure boundary removed",
     "except Exception as e:  # noqa: BLE001 -- a reading never refuses, and nobody reads this",
     "except ZeroDivisionError as e:",
     "a reader that raised exits 0, says nothing and logs a skip"),
    ("the REPORT's prose taken for a result",
     "             if line.strip() and hit.search(line)]",
     "             if line.strip()]",
     "the REPORT's result lines are cut, and its prose is not one"),
    ("a result line not stripped",
     "    found = [line.strip() for line in report.splitlines()",
     "    found = [line for line in report.splitlines()",
     "the REPORT's result lines are cut, and its prose is not one"),
    ("the floor not read", '    best, score = "", floor', '    best, score = "", 0.0',
     "the REPORT line is the best line at or over the floor, else none"),
    ("the first line over the floor, not the best",
     "        if got >= score:\n            best, score = line, got",
     "        if got >= score:\n            return line",
     "the REPORT line is the best line at or over the floor, else none"),
    ("the facts read in name order", "    for name, pattern in facts.items():",
     "    for name, pattern in sorted(facts.items()):",
     "each settled condition names the first fact its words match"),
    ("a condition of no event settled", "                if carry.settled(shared, text):",
     "                if True:",
     "a settlement REPORT asks one select call a sub-issue and one claim call a candidate picked"),
    ("the log resolved from the process's cwd, at a main() skip",
     '                             f"{read}", env, cwd=HERE)',
     '                             f"{read}", env)',
     "every jev call names the reader's own base, not the process cwd"),
    ("the log resolved from the process's cwd",
     '                    read=f"{subject} select", reader=READER, key=key,\n'
     "                    env=env, cwd=HERE)",
     '                    read=f"{subject} select", reader=READER, key=key,\n'
     "                    env=env)",
     "every jev call names the reader's own base, not the process cwd"),
]


def live(record):
    """Every corpus case of both readings against the real endpoint, once,
    asked as the reader asks it: one condition's question over the case's own
    state. Prints each answer beside its truth; `--record` appends it."""
    m = load(SOURCE).m
    jev = m.load_sibling("campaign-jev.py")
    carry = m.load_sibling(m.CARRY)
    today = datetime.date.today().isoformat()
    for name, entry in (("done-report-select", SELECT),
                        ("done-report-claim", CLAIM)):
        path = CORPUS / f"{name}.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines() if x]
        wording = hashlib.sha256(json.dumps(entry["question"], sort_keys=True)
                                 .encode()).hexdigest()[:12]
        off = 0
        for row in rows:
            cond = {"c": row["state"]["condition"]}
            if name == "done-report-select":
                cands = {h: {"path": v.split("\n", 1)[0],
                             "text": v.split("\n", 1)[1]}
                         for h, v in row["state"]["candidates"].items()}
                reading = jev.ask(m.READER, row["id"],
                                  {"candidates": row["state"]["candidates"]},
                                  carry.select_questions(entry, cond, cands))
                a = reading.answers["c"]
                word = (a.raw or {}).get("choice")
                raw = (a.raw or {}).get("confidence")
                hit = word in row["truth"] if isinstance(row["truth"], list) \
                    else word == row["truth"]
            else:
                qs = carry.claim_questions(entry, cond)
                qs["c"]["instructions"] = qs["c"]["instructions"].replace(
                    "{reportLine}", row["state"]["reportLine"])
                reading = jev.ask(m.READER, row["id"],
                                  {"evidence": row["state"]["evidence"]}, qs)
                a = reading.answers["c"]
                raw = ((a.raw or {}).get("probabilities") or {}).get("supports")
                word = a.word
                hit = word == row["truth"]
            off += not hit
            print(f"{row['id']}  truth {row['truth']}  {word} {raw}")
            row["seen"].append({"model": reading.model, "wording": wording,
                                "raw": raw, "word": word, "at": today})
        print(f"{name}: {off} of {len(rows)} case(s) off their truth")
        if record:
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                    for r in rows))


def main(argv):
    try:
        if "--live" in argv:
            live("--record" in argv)
            return 0
        harness.mutate(SOURCE, load, CASES, MUTATIONS)
        return harness.report()
    finally:
        shutil.rmtree(ROOT, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
