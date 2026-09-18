#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-done-carry.py asks one select call a sub-issue and one claim call a hunk picked, asks nothing else, and never refuses.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers each
select question with the hunk a case names for its condition, and each claim
question `supports`; a stub `gh` on PATH answers the pull request's closing
issues, each issue's body and the diff from a case's own JSON. The reader runs
from a fixture directory holding the real scripts/campaign-jev.py, the real
check-diff-screen.py whose `TEST` it reads, and both registry entries. Each
case is then broken by a mutation of the reader's text and must go red by its
own assertion.

`--live` asks every line of scripts/jev/corpus/done-test-select.jsonl and
done-test-claim.jsonl against the real endpoint and prints each answer beside
its truth; `--record` appends the reading to `seen`.

Usage: scripts/check-done-carry-test.py [--live [--record]]
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
SCRIPT = HERE / "check-done-carry.py"
SOURCE = SCRIPT.read_text()
ENTRIES = json.loads((HERE / "jev" / "readings.json").read_text())
SELECT, CLAIM = ENTRIES["done-test-select"], ENTRIES["done-test-claim"]
CORPUS = HERE / "jev" / "corpus"
BUDGET = importlib.import_module("campaign-jev").STATE_BUDGET
ROOT = Path(tempfile.mkdtemp(prefix="done-test-"))
REPORT = "REPORT demo-worker-1: pr#9 at abcdef1, asking for the merge\n"

BODY = """## Intent

- x

## Definition of done

- `tool` refuses an empty name, with a named case.
- `tool --list` prints every name
  sorted by date.
- The pull request is merged and the install shows it.

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
PICKS = {"refuses an empty name": "h1", "prints every name": "noMatch"}

SEEN = []
LOGGED = []


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        answers = {}
        for q, spec in body["questions"].items():
            if "candidateHunks" in body["state"]:
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
    m = types.ModuleType("donetest")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return types.SimpleNamespace(source=source, m=m)


def closing(*numbers, owner="kalaluthien", name="campaign-base"):
    return {"closingIssuesReferences": [
        {"number": n, "repository": {"name": name, "owner": {"login": owner}}}
        for n in numbers]}


def run(t, report=REPORT, argv=("9",), view=None, bodies=None, diff=DIFF,
        fail=()):
    """The finished process; `gh-argv.jsonl` in its directory holds each gh call.
    `fail` names the gh verbs (`pr view`, `issue view`, `pr diff`) that exit 1.
    Every run NAMES a log, because since pr#474 a stubbed endpoint that names
    none writes nothing at all -- campaign-jev-test.py owns that rule."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    (d / "jev").mkdir()
    (d / "bin").mkdir()
    (d / "check-done-carry.py").write_text(t.source)
    shutil.copy(HERE / "campaign-jev.py", d / "campaign-jev.py")
    shutil.copy(HERE / "check-diff-screen.py", d / "check-diff-screen.py")
    (d / "jev" / "readings.json").write_text(json.dumps(
        {"done-test-select": SELECT, "done-test-claim": CLAIM}))
    answers = {"pr view": json.dumps(closing(5) if view is None else view),
               "pr diff": diff}
    for n, body in (bodies if bodies is not None else {5: BODY}).items():
        answers[f"issue view {n}"] = body
    (d / "answers.json").write_text(json.dumps(answers))
    (d / "bin" / "gh").write_text(
        "#!/usr/bin/env python3\nimport json, sys\n"
        f"open({str(d / 'gh-argv.jsonl')!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        f"a = json.load(open({str(d / 'answers.json')!r}))\n"
        "verb = ' '.join(sys.argv[1:3])\n"
        f"if verb in {list(fail)!r}:\n    sys.exit('gh stub: refused')\n"
        "key = verb + (' ' + sys.argv[3] if verb == 'issue view' else '')\n"
        "sys.stdout.write(a[key])\n")
    (d / "bin" / "gh").chmod(0o755)
    SEEN.clear()
    env = dict(os.environ, CAMPAIGN_JEV_URL=URL, TYPESAFE_API_KEY="stub",
               CAMPAIGN_JEV_LOG=str(d / "jev.log"), HOME=str(d),
               PATH=f"{d / 'bin'}:{os.environ['PATH']}")
    r = subprocess.run([sys.executable, str(d / "check-done-carry.py"), *argv],
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


def two_calls(t):
    r = run(t)
    kinds = ["select" if "candidateHunks" in b["state"] else "claim" for b in SEEN]
    asked = [sorted(q.split("#", 1)[-1] for q in b["questions"]) for b in SEEN]
    return (r.returncode == 0 and r.stdout == "" and kinds == ["select", "claim"]
            and asked == [["c1", "c2"], ["c1"]]
            and SEEN[1]["state"] == {"hunk": "scripts/tool-test.py\n@@ -10,2 +10,4 @@ "
                                     "def cases():\n+def refuses_empty():\n"
                                     "+    assert run(\"\").code == 2"}
            and reads() == [("tracker#9 REPORT 5 c3", "an event no test could carry"),
                            ("tracker#9 REPORT 5 select", None),
                            ("tracker#9 REPORT 5 claim h1 scripts/tool-test.py", None)]
            ), (r.stderr[-300:], SEEN, reads())


def candidates_are_test_hunks(t):
    run(t)
    cands = SEEN[0]["state"]["candidateHunks"] if SEEN else {}
    return (sorted(cands) == ["h1", "h2"]
            and cands["h1"].startswith("scripts/tool-test.py\n@@ -10,2")
            and cands["h2"].startswith("scripts/tool-test.py\n@@ -40,1")), cands


def entry_reaches_model(t):
    run(t)
    q = SEEN[0]["questions"].get("done-test-select#c2", {}) if SEEN else {}
    c = SEEN[1]["questions"].get("done-test-claim#c1", {}) if len(SEEN) > 1 else {}
    want = SELECT["question"]["instructions"].replace(
        "{condition}", "`tool --list` prints every name sorted by date.")
    return (q.get("instructions") == want
            and sorted(q.get("criteria", {})) == ["h1", "h2", "noMatch"]
            and q["criteria"]["h2"] == SELECT["question"]["criteria"]["{hunk}"]
            .replace("{hunk}", "h2").replace("{path}", "scripts/tool-test.py")
            and c.get("criteria") == CLAIM["question"]["criteria"]
            and "floor" not in q and "yes_over" not in c), (q, c)


def one_claim_a_hunk(t):
    PICKS["prints every name"] = "h1"
    try:
        run(t)
    finally:
        PICKS["prints every name"] = "noMatch"
    claims = [b for b in SEEN if "hunk" in b["state"]]
    asked = sorted(q.split("#", 1)[-1] for q in claims[0]["questions"]) \
        if claims else []
    return len(claims) == 1 and asked == ["c1", "c2"], SEEN


def no_merge_ask_asks_nothing(t):
    r = run(t, report="REPORT demo-worker-1: pr#9 merged at abcdef1\n")
    return r.returncode == 0 and not SEEN and not LOGGED and not r.gh, (SEEN, LOGGED)


def other_comment_asks_nothing(t):
    r = run(t, report="NOTE demo-worker-1: asking for the merge\n")
    return r.returncode == 0 and not SEEN and not LOGGED, (SEEN, LOGGED)


def no_done_issue_skips(t):
    r = run(t, bodies={5: "## Intent\n\n- x\n"})
    return (r.returncode == 0 and not SEEN and reads() == [
        ("tracker#9 REPORT", "the pull request closes no issue with a Definition of done")]), reads()


def no_test_hunk_skips(t):
    r = run(t, diff=DIFF.split("diff --git a/scripts/tool-test.py")[0])
    return (r.returncode == 0 and not SEEN and reads() == [
        ("tracker#9 REPORT", "the diff changes no test file, so no condition is carried by one")]), reads()


def over_budget_skips(t):
    big = DIFF + "".join(f"@@ -{i},1 +{i},1 @@\n+{'x' * 999}\n" for i in range(100, 170))
    r = run(t, diff=big)
    return (r.returncode == 0 and not SEEN and len(LOGGED) == 2
            and LOGGED[1]["read"] == "tracker#9 REPORT 5 select"
            and f"over the {BUDGET}-byte budget" in LOGGED[1].get("skipped", "")), reads()


def failed_pr_read_skips(t):
    r = run(t, fail=("pr view",))
    return (r.returncode == 0 and not SEEN and len(LOGGED) == 1
            and LOGGED[0]["skipped"] == "the pull request read failed: gh stub: refused"), reads()


def failed_issue_read_skips(t):
    r = run(t, fail=("issue view",))
    return (r.returncode == 0 and not SEEN and reads() == [
        ("tracker#9 REPORT 5", "the issue read failed: gh stub: refused"),
        ("tracker#9 REPORT", "the pull request closes no issue with a Definition of done")]), reads()


def failed_diff_read_skips(t):
    r = run(t, fail=("pr diff",))
    return (r.returncode == 0 and not SEEN and reads() == [
        ("tracker#9 REPORT", "the diff read failed: gh stub: refused")]), reads()


def repository_reaches_gh(t):
    """A member repository's pull request closing a tracker sub-issue: the pull
    request is read in its repository, the issue in the tracker."""
    r = run(t, argv=("9", "o/r"))
    return ([c[:4] for c in r.gh] == [["pr", "view", "9", "-R"], ["issue", "view", "5", "-R"],
                                       ["pr", "diff", "9", "-R"]]
            and [c[4] for c in r.gh] == ["o/r", "kalaluthien/campaign-base", "o/r"]
            and LOGGED[-1]["read"].startswith("o/r#9 REPORT 5")), (r.gh, reads())


def issue_in_its_own_repository(t):
    r = run(t, view=closing(5, owner="o", name="r"))
    return [c[4] for c in r.gh] == ["kalaluthien/campaign-base", "o/r",
                                    "kalaluthien/campaign-base"], r.gh


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
NO_TEST_DIFF = ("diff --git a/scripts/tool.py b/scripts/tool.py\n"
                "--- a/scripts/tool.py\n+++ b/scripts/tool.py\n@@ -1,2 +1,3 @@\n a\n+b\n")


def drive(t, jev, answers, diff=DIFF, body=BODY):
    """`main()` once with `jev` in place of the real one, over a gh double.

    `answers` names the gh verbs that fail. The real `load_sibling` still
    answers for check-diff-screen.py, whose TEST names a test path."""
    real, real_gh = t.m.load_sibling, t.m.gh
    t.m.load_sibling = lambda n: jev if n == "campaign-jev.py" else real(n)
    t.m.gh = lambda *a: (
        ("", "gh double: refused") if " ".join(a[:2]) in answers else
        (json.dumps(closing(5)), "") if a[:2] == ("pr", "view") else
        (diff, "") if a[:2] == ("pr", "diff") else (body, ""))
    try:
        return t.m.main(["9"], io.StringIO(REPORT))
    finally:
        t.m.load_sibling, t.m.gh = real, real_gh


def every_jev_call_names_the_readers_base(t):
    """Every one of the reader's ten call sites, and each must name HERE.

    ask_issue's three are driven directly; main()'s seven are driven through
    main() itself, because a case that calls the inner function supplies the
    argument the call site was supposed to be pinned for -- that is how this
    case lost main()'s skips once (the REVIEW at 318a053, D1)."""
    conds = {"c1": "a condition one test could carry"}
    cands = {"h1": {"path": "scripts/tool-test.py", "text": "@@ -1 +1 @@\n+x"}}
    inner, over = RecordingJev(), RecordingJev()
    t.m.ask_issue({"done-test-select": SELECT, "done-test-claim": CLAIM},
                  "tracker#9 REPORT 5", conds, cands, inner)
    t.m.ask_issue({"done-test-select": SELECT, "done-test-claim": CLAIM},
                  "tracker#9 REPORT 5", conds,
                  {"h1": {"path": "scripts/tool-test.py",
                          "text": "x" * (BUDGET + 1)}}, over)
    seen, counts = [], []
    for kw in ({"answers": {"pr view"}},          # the pull request read failed
               {"answers": {"issue view"}},       # the issue read failed
               {"answers": (), "body": NO_DOD},   # closes no issue with a DoD
               {"answers": {"pr diff"}},          # the diff read failed
               {"answers": (), "diff": NO_TEST_DIFF},   # no test hunk
               {"answers": ()}):                  # the settled condition, then both asks
        one = RecordingJev()
        drive(t, one, **{"answers": kw.pop("answers"), **kw})
        seen += one.cwds
        counts.append(len(one.cwds))
    raised = RecordingJev()
    raised.judge = raised.skip        # a skip signature for a judge call: TypeError
    drive(t, raised, answers=())
    seen += raised.cwds
    named = inner.cwds + over.cwds + seen
    # `== 2` and not `>= 1`: the settled skip lands first, so only the count
    # says skipped() itself ran -- with its call cut the case stayed green.
    return (set(named) == {t.m.HERE} and counts == [1, 2, 1, 1, 1, 3]
            and len(raised.cwds) == 2), (counts, len(raised.cwds),
                                         sorted(set(map(str, named))))


def tracker_is_the_default(t):
    r = run(t)
    return [c[4:5] for c in r.gh] == [["kalaluthien/campaign-base"]] * 3, r.gh


def failure_exits_zero(t):
    r = run(t, view={"closing": []})
    return (r.returncode == 0 and r.stdout == "" and r.stderr == "" and not SEEN
            and reads() == [("tracker#9 REPORT", "the reading raised KeyError")]), (r.stderr[-300:], reads())


def conditions_cut(t):
    body = ("## Definition of done\n\n- one\n  - sub\n  more\n1. two\n"
            "| a | b |\n| --- | --- |\n| c | d |\n\n## Plan\n\n- not a condition\n")
    got = t.m.conditions(body)
    return got == ["one sub more", "two", "| c | d |"], got


def settled_by_events_only(t):
    pre = SELECT["prefilter"]
    cases = {
        "The pull request is merged and the install shows it.": True,
        "The pull request merged; install reached (`reach` line quoted).": True,
        "The REPORT lists the three counts before and after.": True,
        "Merged PR on the base: `x/` holds the vendored skill.": False,
        "One merged pull request in which `spec/sdlc` names the change with a check.": False,
        "`tool` refuses an empty name; the pull request merged.": False,
    }
    got = {c: t.m.settled(pre, c) for c in cases}
    return got == cases, got


CASES = {
    "a REPORT asking for the merge asks one select call and one claim call a hunk picked, printing nothing": two_calls,
    "the candidates are the test file's hunks, each its path and hunk": candidates_are_test_hunks,
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "two conditions picking one hunk share one claim call": one_claim_a_hunk,
    "a REPORT not asking for the merge asks and logs nothing": no_merge_ask_asks_nothing,
    "a comment of another kind asks nothing": other_comment_asks_nothing,
    "a pull request closing no Definition of done logs one skip": no_done_issue_skips,
    "a diff changing no test file logs one skip": no_test_hunk_skips,
    "a select state over the budget is not sent and logs a skip": over_budget_skips,
    "a failed pull request read logs one skip": failed_pr_read_skips,
    "a failed issue read logs a skip for that issue": failed_issue_read_skips,
    "a failed diff read logs one skip": failed_diff_read_skips,
    "a member pull request is read in its repository, its tracker issue in the tracker": repository_reaches_gh,
    "an issue is read in its own repository": issue_in_its_own_repository,
    "every jev call names the reader's own base, not the process cwd": every_jev_call_names_the_readers_base,
    "with no repository gh is told the tracker": tracker_is_the_default,
    "a reader that raised exits 0, says nothing and logs a skip": failure_exits_zero,
    "a condition is a list item with its lines, or a table row": conditions_cut,
    "only a condition of events alone is settled": settled_by_events_only,
}

MUTATIONS = [
    ("a call a condition",
     '                    {"candidateHunks": text, "condition": conds},',
     '                    {"candidateHunks": text,\n'
     '                     "condition": dict(list(conds.items())[:1])},',
     "a REPORT asking for the merge asks one select call and one claim call a hunk picked, printing nothing"),
    ("a claim call for noMatch", "        if h in cands:", "        if h:",
     "a REPORT asking for the merge asks one select call and one claim call a hunk picked, printing nothing"),
    ("a claim call a condition",
     "            by_hunk.setdefault(h, {})[cid] = conds[cid]",
     "            by_hunk[h + cid] = {cid: conds[cid]}; cands[h + cid] = cands[h]",
     "two conditions picking one hunk share one claim call"),
    ("the prefilter not read", "                if settled(prefilter, text):", "                if False:",
     "a REPORT asking for the merge asks one select call and one claim call a hunk picked, printing nothing"),
    ("every file a candidate", "if not test.search(path) or len(body) < 2:", "if len(body) < 2:",
     "the candidates are the test file's hunks, each its path and hunk"),
    ("the path dropped from a candidate",
     'text = {h: c["path"] + "\\n" + c["text"] for h, c in cands.items()}',
     'text = {h: c["text"] for h, c in cands.items()}',
     "the candidates are the test file's hunks, each its path and hunk"),
    ("the conditions never handed to the select call",
     '                    {"candidateHunks": text, "condition": conds},',
     '                    {"candidateHunks": text,\n'
     '                     "condition": {c: "" for c in conds}},',
     "the entry's instructions and criteria reach the model, thresholds do not"),
    ("the candidates never handed to the select call",
     '                    {"candidateHunks": text, "condition": conds},',
     '                    {"candidateHunks": {}, "condition": conds},',
     "the entry's instructions and criteria reach the model, thresholds do not"),
    ("the merge ask not read", 'if not re.search(prefilter["asks_merge"], report):', "if False:",
     "a REPORT not asking for the merge asks and logs nothing"),
    ("the comment kind not read", 'if not report.lstrip().startswith("REPORT "):', "if False:",
     "a comment of another kind asks nothing"),
    ("an issue with no DoD asked", "            elif DOD in body:", "            elif True:",
     "a pull request closing no Definition of done logs one skip"),
    ("no test hunk not skipped", "        if not cands:", "        if False:",
     "a diff changing no test file logs one skip"),
    ("the budget not read",
     '    if len(json.dumps({"candidateHunks": text}).encode("utf-8")) > jev.STATE_BUDGET:',
     "    if False:",
     "a select state over the budget is not sent and logs a skip"),
    ("a failed pr read taken for one",
     '        view, why = gh("pr", "view", pr, *target, "--json", "closingIssuesReferences")\n        if why:',
     '        view, why = gh("pr", "view", pr, *target, "--json", "closingIssuesReferences")\n        if False:',
     "a failed pull request read logs one skip"),
    ("a failed issue read unlogged",
     '                jev.skip(READER, f"{subject} {ref[\'number\']}",\n                         f"the issue read failed: {why}", env, cwd=HERE)',
     "                pass",
     "a failed issue read logs a skip for that issue"),
    ("a failed diff read taken for one",
     '        diff, why = gh("pr", "diff", pr, *target)\n        if why:',
     '        diff, why = gh("pr", "diff", pr, *target)\n        if False:',
     "a failed diff read logs one skip"),
    ("the repository dropped", 'target = ["-R", repo or TRACKER]', 'target = ["-R", TRACKER]',
     "a member pull request is read in its repository, its tracker issue in the tracker"),
    ("the issue read in the pull request's repository", '"-R", name,', '*target,',
     "a member pull request is read in its repository, its tracker issue in the tracker"),
    ("the issue read in the tracker always", '"-R", name,', '"-R", TRACKER,',
     "an issue is read in its own repository"),
    ("the log resolved from the process's cwd, at a main() skip",
     '                             "test could carry", env, cwd=HERE)',
     '                             "test could carry", env)',
     "every jev call names the reader's own base, not the process cwd"),
    ("the log resolved from the process's cwd",
     "                    read=f\"{subject} select\", reader=READER, key=key,\n"
     "                    env=env, cwd=HERE)",
     "                    read=f\"{subject} select\", reader=READER, key=key,\n"
     "                    env=env)",
     "every jev call names the reader's own base, not the process cwd"),
    ("the table header kept", "            if not rule.match(line) and not header:", "            if not rule.match(line):",
     "a condition is a list item with its lines, or a table row"),
    ("no tracker default", 'target = ["-R", repo or TRACKER]', 'target = ["-R", repo] if repo else []',
     "with no repository gh is told the tracker"),
    ("the failure boundary removed",
     "except Exception as e:  # noqa: BLE001 -- a reading never refuses, and nobody reads this",
     "except ZeroDivisionError as e:",
     "a reader that raised exits 0, says nothing and logs a skip"),
    ("a continuation line dropped", '            out[-1] += " " + re.sub(', "            out[-1] += \"\" and re.sub(",
     "a condition is a list item with its lines, or a table row"),
    ("the table rule kept", "            if not rule.match(line) and not header:", "            if not header:",
     "a condition is a list item with its lines, or a table row"),
    ("a long merge clause settled", 'not ("merged" in m.group(0).lower() and len(c) > ceiling)', "True",
     "only a condition of events alone is settled"),
    ("any event clause settles", "    return bool(parts) and all(", "    return bool(parts) and any(",
     "only a condition of events alone is settled"),
]


def live(record):
    """Every corpus case of both readings against the real endpoint, once,
    asked as the reader asks it: one condition's question over the case's own
    state. Prints each answer beside its truth; `--record` appends it."""
    m = load(SOURCE).m
    jev = m.load_sibling("campaign-jev.py")
    today = datetime.date.today().isoformat()
    for name, entry in (("done-test-select", SELECT), ("done-test-claim", CLAIM)):
        path = CORPUS / f"{name}.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines() if x]
        wording = hashlib.sha256(json.dumps(entry["question"], sort_keys=True)
                                 .encode()).hexdigest()[:12]
        off = 0
        for row in rows:
            cond = {"c": row["state"]["condition"]}
            if name == "done-test-select":
                cands = {h: {"path": t.split("\n", 1)[0], "text": t.split("\n", 1)[1]}
                         for h, t in row["state"]["candidateHunks"].items()}
                reading = jev.ask(m.READER, row["id"],
                                  {"candidateHunks": row["state"]["candidateHunks"]},
                                  m.select_questions(entry, cond, cands))
                a = reading.answers["c"]
                word = (a.raw or {}).get("choice")
                raw = (a.raw or {}).get("confidence")
                hit = word in row["truth"] if isinstance(row["truth"], list) else word == row["truth"]
            else:
                reading = jev.ask(m.READER, row["id"], {"hunk": row["state"]["hunk"]},
                                  m.claim_questions(entry, cond))
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
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


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
