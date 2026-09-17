#!/usr/bin/env python3
# witnesses: JV1_ARepliedConfidentFittingJudgmentAdvises, JV1b_AFailedLowOrNoMatchAnswerNeverAdvises
"""Prove campaign-jev.py branches where its thresholds say and answers `unknown` everywhere else.

THE DEFAULT RUN IS OFFLINE and needs no key: a stub HTTP server on 127.0.0.1
stands in for the endpoint, and `CAMPAIGN_JEV_URL` points the module at it. CI
runs every `scripts/*-test.*` with no key at all, so a suite that reached the
real endpoint would be red on the machine that has no key and green on the one
that has -- the two states a measurement must never share.

The table asserts what the module decides: the request shape (the model pinned,
every question in ONE call), each branch of `noul` and `choice`, the confidence
floor beside the no-match option, and every failure path answering `unknown` --
a closed port, HTTP 500, a body that is not JSON, a response naming another
model, an answer of the wrong type, a missing answer, and a missing key. Each is
then broken in turn by a mutation of the script's own text and must go red by
its own assertion, because a case that cannot fail is a case that proves
nothing.

`--live` is the other half and is opt-in: it runs
`scripts/fixtures/jev-cases.json` -- cases of this tracker's own history, one of
which is not a unit of work at all -- against the real endpoint and asserts a
BAND per group, never a float, since the same request comes back a few
hundredths apart. It reads `campaign-tracker.py`'s thresholds and asserts each
sits in the GAP between the two bands and on neither: that is what makes the
thresholds measured rather than chosen. `--record` writes the observed bands,
the date and the answering model back into the fixture.

Usage: scripts/campaign-jev-test.py [--live [--record]]
"""
import contextlib
import datetime
import http.server
import importlib
import json
import socket
import sys
import tempfile
import threading
import types
from pathlib import Path

harness = importlib.import_module("suite-harness-test")
check = harness.check

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "campaign-jev.py"
SOURCE = SCRIPT.read_text()
FIXTURE = HERE / "fixtures" / "jev-cases.json"
MODEL = "jev-1.13.0"

ROOT = Path(tempfile.mkdtemp(prefix="campaign-jev-"))
HOME = ROOT / "home"
HOME.mkdir()
LOG = ROOT / "jev.log"

# What the stub answers next, and what it last received. One dict each: the
# cases run in one thread, one call at a time.
NEXT = {"status": 200, "body": {}}
SEEN = {"count": 0, "body": "", "auth": ""}


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        SEEN["count"] += 1
        SEEN["body"] = self.rfile.read(
            int(self.headers.get("Content-Length") or 0)).decode()
        SEEN["auth"] = self.headers.get("Authorization", "")
        payload = NEXT["body"]
        data = (payload if isinstance(payload, str)
                else json.dumps(payload)).encode()
        self.send_response(NEXT["status"])
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


SERVER = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{SERVER.server_address[1]}/v1/systemone"


def closed_port():
    """A port nothing listens on: bound, read, and let go."""
    with contextlib.closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


CLOSED = f"http://127.0.0.1:{closed_port()}/v1/systemone"

NOUL_Q = {"type": "noul", "instructions": "Is the title verb-first?",
          "yes_over": 0.85, "no_under": 0.70}
CHOICE_Q = {"type": "choice", "instructions": "What kind of work is this?",
            "criteria": {"research": "ask", "development": "build",
                         "maintenance": "tidy", "none": "not work at all"},
            "floor": 0.60, "no_match": "none"}
BOTH = {"verb_first": NOUL_Q, "work_kind": CHOICE_Q}
STATE = {"title": "Put Jev judgments into orchestration", "body": "- a body"}


def env(url=None, key="stub-key", log=None, home=None):
    """A case's whole environment: never `os.environ`, so no key, no log and no
    endpoint of this machine's ever reaches a case."""
    out = {"HOME": str(home or HOME), "CAMPAIGN_JEV_URL": url or URL,
           "CAMPAIGN_JEV_LOG": str(log or LOG)}
    if key is not None:
        out["TYPESAFE_API_KEY"] = key
    return out


def answered(noul=0.95, choice="maintenance", confidence=0.90, model=MODEL):
    return {"model": model,
            "answers": {"verb_first": {"type": "noul", "noul": noul},
                        "work_kind": {"type": "choice", "choice": choice,
                                      "confidence": confidence}}}


def serving(status=200, body=None, **kw):
    NEXT["status"], NEXT["body"] = status, answered(**kw) if body is None else body
    SEEN["count"] = 0


def read(m, questions=None, **kw):
    """One call against the stub, with the log truncated first so each case
    reads its own line and never the run before it."""
    LOG.write_text("")
    serving(**{k: v for k, v in kw.items() if k not in ("url", "key", "home")})
    return m.ask("a suite", "a label", STATE, questions or BOTH,
                 env=env(url=kw.get("url"), key=kw.get("key", "stub-key"),
                         home=kw.get("home")), timeout=5)


def word(name, want, **kw):
    """The branch one question fell in, over a stub answering `kw`."""
    def case(m):
        r = read(m, **kw)
        got = r.answers[name]
        return got.word == want, (got.word, got.why, r.model)
    return case


def unknown_because(name, fragment, **kw):
    def case(m):
        r = read(m, **kw)
        got = r.answers[name]
        return got.word == "unknown" and fragment in got.why, (got.word, got.why)
    return case


def pure_branches(m):
    """`branch` alone: the whole decision, with no request spent."""
    noul = lambda v: {"type": "noul", "noul": v}  # noqa: E731
    pick = lambda o, c: {"type": "choice", "choice": o, "confidence": c}  # noqa: E731
    check("branch: a noul over the cut is yes",
          m.branch(NOUL_Q, noul(0.92))[0] == "yes")
    check("branch: a noul under the cut is no",
          m.branch(NOUL_Q, noul(0.61))[0] == "no")
    check("branch: a noul in the gap is unknown",
          m.branch(NOUL_Q, noul(0.78))[0] == "unknown")
    check("branch: the cuts are inclusive at both ends",
          m.branch(NOUL_Q, noul(0.85))[0] == "yes"
          and m.branch(NOUL_Q, noul(0.70))[0] == "no")
    check("branch: a confident fitting option is the option",
          m.branch(CHOICE_Q, pick("research", 0.71))[0] == "research")
    check("branch: under the floor is unknown",
          m.branch(CHOICE_Q, pick("research", 0.59))[0] == "unknown")
    check("branch: the no-match option is unknown at any confidence",
          m.branch(CHOICE_Q, pick("none", 0.99))[0] == "unknown")
    check("branch: no answer at all is unknown",
          m.branch(NOUL_Q, None)[0] == "unknown")
    # AN UNSUPPORTED TYPE IS THE CALLER'S BUG, and it raises rather than
    # wearing the word every failure of the model's already wears.
    try:
        m.branch({"type": "score"}, {"type": "score", "score": 1.0})
        check("branch: an unsupported type raises", False, "it returned")
    except ValueError as e:
        check("branch: an unsupported type raises", "score" in str(e), str(e))


CASES = {
    # --- the request shape ---
    "the request pins the model": lambda m: (
        read(m) and json.loads(SEEN["body"])["model"] == MODEL,
        SEEN["body"][:120]),
    "every question goes in one call": lambda m: (
        read(m) and SEEN["count"] == 1
        and set(json.loads(SEEN["body"])["questions"]) == set(BOTH),
        (SEEN["count"], sorted(json.loads(SEEN["body"] or "{}").get("questions", {})))),
    "the thresholds are never sent to the model": lambda m: (
        read(m) and not any(k in json.loads(SEEN["body"])["questions"]["verb_first"]
                            for k in ("yes_over", "no_under")),
        SEEN["body"][:200]),
    "the key travels in the header and nowhere else": lambda m: (
        read(m) and SEEN["auth"] == "Bearer stub-key"
        and "stub-key" not in SEEN["body"], (SEEN["auth"], "stub-key" in SEEN["body"])),
    # --- the branches, through a whole call ---
    "a noul over the cut is yes": word("verb_first", "yes", noul=0.94),
    "a noul under the cut is no": word("verb_first", "no", noul=0.46),
    "a noul in the gap is unknown": unknown_because(
        "verb_first", "in the gap", noul=0.78),
    "a confident fitting option is the option": word(
        "work_kind", "maintenance", confidence=0.95),
    "a choice under the floor is unknown": unknown_because(
        "work_kind", "under the floor", confidence=0.51),
    "the no-match option is unknown": unknown_because(
        "work_kind", "no-match option", choice="none", confidence=0.95),
    # --- every failure path ---
    "a closed port answers unknown": unknown_because(
        "verb_first", "did not answer", url=CLOSED),
    "...and the other question too": unknown_because(
        "work_kind", "did not answer", url=CLOSED),
    "an HTTP error answers unknown": unknown_because(
        "verb_first", "HTTP 500", status=500),
    "a body that is not JSON answers unknown": unknown_because(
        "verb_first", "not JSON", body="<html>gateway</html>"),
    "a response naming another model is unknown": unknown_because(
        "verb_first", "is pinned", model="jev-latest"),
    "an answer of another type is unknown": unknown_because(
        "verb_first", "answered a `choice`",
        body={"model": MODEL, "answers": {
            "verb_first": {"type": "choice", "choice": "x", "confidence": 1.0}}}),
    "a missing answer is unknown": unknown_because(
        "verb_first", "carried no answer",
        body={"model": MODEL, "answers": {}}),
    "a missing key is unknown and spends no request": lambda m: (
        read(m, key=None).answers["verb_first"].word == "unknown"
        and SEEN["count"] == 0, SEEN["count"]),
}


def key_from_dotenv(m):
    home = ROOT / "withenv"
    home.mkdir(exist_ok=True)
    (home / ".env").write_text('export TYPESAFE_API_KEY="from-the-file"\n')
    r = read(m, key=None, home=home)
    return (r.answers["verb_first"].word == "yes"
            and SEEN["auth"] == "Bearer from-the-file"), (r.answers, SEEN["auth"])


def logged_line(m):
    r = read(m, noul=0.94, choice="research", confidence=0.95)
    rows = [json.loads(x) for x in LOG.read_text().splitlines() if x]
    if len(rows) != 1:
        return False, f"{len(rows)} lines"
    row = rows[0]
    ok = (row["reader"] == "a suite" and row["read"] == "a label"
          and row["asked"] == MODEL and row["answered"] == MODEL
          and isinstance(row["latency"], float)
          and row["answers"]["verb_first"]["branch"] == "yes"
          and row["answers"]["verb_first"]["raw"]["noul"] == 0.94
          and row["answers"]["work_kind"]["branch"] == "research"
          # THE STATE IS NOT IN THE LINE: a label says what was read, and an
          # issue body in a scratch log is a copy nobody sweeps.
          and STATE["title"] not in json.dumps(row)
          and row["at"].endswith("+00:00")
          and r.logged.startswith("logged to"))
    return ok, (row, r.logged)


def log_refused(m):
    blocker = ROOT / "not-a-dir"
    blocker.write_text("")
    serving()
    r = m.ask("a suite", "a label", STATE, BOTH,
              env=env(log=blocker / "jev.log"), timeout=5)
    return ("answer not logged to" in r.logged
            and r.answers["verb_first"].word == "yes"), r.logged


CASES["the key is read from ~/.env when the environment has none"] = key_from_dotenv
CASES["the call is logged as one JSON line"] = logged_line
CASES["a log that would not write is reported, not raised"] = log_refused

MUTATIONS = [
    ("the confidence floor dropped", 'if confidence < spec["floor"]:', "if False:",
     "a choice under the floor is unknown"),
    ("the no-match option ignored", 'if option == spec["no_match"]:', "if False:",
     "the no-match option is unknown"),
    ("the noul gap closed", 'if value <= spec["no_under"]:', "if True:",
     "a noul in the gap is unknown"),
    ("a failure answered instead of unknown",
     "return {qid: Answer(UNKNOWN, None, why) for qid in questions}",
     'return {qid: Answer("yes", None, why) for qid in questions}',
     "a closed port answers unknown"),
    ("the pinned model unread in the response", 'elif out.get("model") != MODEL:',
     "elif False:", "a response naming another model is unknown"),
    ("the answer's own type unread", 'if raw.get("type") != kind:', "if False:",
     "an answer of another type is unknown"),
    ("a missing answer read as an answer",
     '        return UNKNOWN, "the response carried no answer for this question"',
     '        return "yes", ""', "a missing answer is unknown"),
    ("the model unpinned in the request", 'return {"model": MODEL, "state": state,',
     'return {"model": "jev-latest", "state": state,', "the request pins the model"),
    ("the thresholds sent to the model",
     'if k in ("type", "instructions", "criteria")}',
     "if k not in ()}", "the thresholds are never sent to the model"),
    ("the ~/.env fallback dropped",
     'path = Path(env.get("HOME", "~")).expanduser() / ".env"',
     'path = Path("/nonexistent") / ".env"',
     "the key is read from ~/.env when the environment has none"),
    ("the log line not written",
     'fh.write(json.dumps(row, sort_keys=True) + "\\n")', "pass",
     "the call is logged as one JSON line"),
    ("the log path never resolved", "    path, how = log_path(env, cwd)",
     '    path, how = None, "nowhere"',
     "a log that would not write is reported, not raised"),
]


def load(source):
    m = types.ModuleType("campaignjev")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return m


# ------------------------------------------------------------------- the live half


def band(values):
    return (min(values), max(values)) if values else None


def live(record):
    """The fixture against the real endpoint: one band per group, and each of
    `campaign-tracker.py`'s thresholds asserted into the gap between two."""
    jev = load(SOURCE)
    tracker = harness.load(HERE / "campaign-tracker.py", "campaign_tracker")
    cases = json.loads(FIXTURE.read_text())
    groups = cases["groups"]
    model = ""

    yes, no = [], []
    q = {"verb_first": {"type": "noul",
                        "instructions": tracker.VERB_FIRST_QUESTION,
                        "yes_over": tracker.VERB_FIRST_YES_OVER,
                        "no_under": tracker.VERB_FIRST_NO_UNDER}}
    for c in groups["verb-first"]["cases"]:
        # THE STATE IS PRODUCTION'S, title and body together: the body moves
        # the title's answer, so a band measured on the title alone is a band
        # for a call this tree never makes.
        r = jev.ask("campaign-jev-test.py --live", c["id"],
                    {"title": c["title"], "body": c["body"]}, q)
        model = r.model or model
        raw = r.answers["verb_first"].raw
        if raw is None:
            check(f"live verb-first {c['id']} answered", False, r.answers)
            continue
        (yes if c["truth"] == "yes" else no).append(raw["noul"])
        print(f"  {c['id']:<8} noul {raw['noul']:.2f}  truth {c['truth']}")
    check("live: every verb-first case answered", len(yes) + len(no)
          == len(groups["verb-first"]["cases"]), (len(yes), len(no)))
    print(f"  verb-first bands: yes {band(yes)}  no {band(no)}")

    cleared, suppressed, wrong, nomatch = [], [], [], []
    q = {"work_kind": {"type": "choice",
                       "instructions": tracker.WORK_KIND_QUESTION,
                       "criteria": tracker.WORK_KIND_CRITERIA,
                       "floor": tracker.WORK_KIND_FLOOR,
                       "no_match": tracker.WORK_KIND_NO_MATCH}}
    for c in groups["work-kind"]["cases"]:
        r = jev.ask("campaign-jev-test.py --live", c["id"],
                    {"title": c["title"], "body": c["body"]}, q)
        model = r.model or model
        raw = r.answers["work_kind"].raw
        if raw is None:
            check(f"live work-kind {c['id']} answered", False, r.answers)
            continue
        print(f"  {c['id']:<10} {raw['choice']:<12} conf {raw['confidence']:.2f}"
              f"  truth {c['truth']}  -> {r.answers['work_kind'].word}")
        if c["truth"] == "unknown":
            nomatch.append((raw["choice"], raw["confidence"],
                            r.answers["work_kind"].word))
        elif r.answers["work_kind"].word == "unknown":
            suppressed.append(raw["confidence"])
        else:
            cleared.append(raw["confidence"])
            if raw["choice"] != c["truth"]:
                wrong.append((c["id"], raw["choice"], raw["confidence"],
                              c["truth"]))
    print(f"  work-kind bands: over the floor {band(cleared)}  "
          f"under it {band(suppressed)}  wrong over it {wrong}")

    # THE ASSERTIONS ARE BANDS AND GAPS, never floats: the same request comes
    # back a few hundredths apart, so a case pinned to a value is a case that
    # goes red on nothing having changed.
    check("live: the verb-first yes band clears its cut",
          bool(yes) and min(yes) > tracker.VERB_FIRST_YES_OVER,
          (band(yes), tracker.VERB_FIRST_YES_OVER))
    check("live: the verb-first no band clears its cut",
          bool(no) and max(no) < tracker.VERB_FIRST_NO_UNDER,
          (band(no), tracker.VERB_FIRST_NO_UNDER))
    check("live: the two verb-first bands do not meet",
          bool(yes) and bool(no) and max(no) < min(yes), (band(no), band(yes)))
    # THE FLOOR SEPARATES TWO BANDS OF CONFIDENCE, not right answers from wrong
    # ones: a run may hold no wrong answer at all, and a threshold measured
    # against a band that does not exist would be a number chosen and called
    # measured. What must hold is that the floor sits in the gap between what it
    # clears and what it suppresses, and that nothing it clears is wrong.
    check("live: the floor sits above everything it suppresses",
          not suppressed or max(suppressed) < tracker.WORK_KIND_FLOOR,
          (band(suppressed), tracker.WORK_KIND_FLOOR))
    check("live: the floor sits below everything it clears",
          bool(cleared) and min(cleared) > tracker.WORK_KIND_FLOOR,
          (band(cleared), tracker.WORK_KIND_FLOOR))
    check("live: every kind over the floor names the label the owner set",
          not wrong, wrong)
    check("live: the case that fits no option comes back unknown",
          bool(nomatch) and all(w == "unknown" for _o, _c, w in nomatch), nomatch)
    check("live: the pinned model is the one that answered",
          model == jev.MODEL, model)

    if record:
        groups["verb-first"]["observed"] = {"yes": band(yes), "no": band(no)}
        groups["work-kind"]["observed"] = {"over the floor": band(cleared),
                                           "under the floor": band(suppressed),
                                           "wrong over the floor": wrong,
                                           "no-match": nomatch}
        cases["measured"] = datetime.date.today().isoformat()
        cases["model"] = model
        FIXTURE.write_text(json.dumps(cases, indent=1, ensure_ascii=False) + "\n")
        print(f"recorded into {FIXTURE}")


def main(argv):
    if "--live" in argv:
        live("--record" in argv)
        return harness.report()
    pure_branches(load(SOURCE))
    harness.mutate(SOURCE, load, CASES, MUTATIONS)
    return harness.report()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
