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
    # `url` IS PASSED THROUGH WHEN IT IS EMPTY, not swallowed by an `or`: the
    # set-but-empty value is a case, and a helper that read it as "unset" would
    # be the very confusion the module was fixed for.
    out = {"HOME": str(home or HOME),
           "CAMPAIGN_JEV_URL": URL if url is None else url,
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
    serving(**{k: v for k, v in kw.items()
               if k not in ("url", "key", "home", "state")})
    return m.ask("a suite", "a label", kw.get("state", STATE), questions or BOTH,
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
    # --- the paths that used to raise instead of answering ---
    "a URL with no scheme is unknown, not a traceback": unknown_because(
        "verb_first", "did not answer (ValueError)", url="garbage"),
    "an endpoint set to nothing never reaches the network": lambda m: (
        "set to nothing" in read(m, url="").answers["verb_first"].why
        and SEEN["count"] == 0, (read(m, url="").answers["verb_first"].why,
                                 SEEN["count"])),
    # --- the size budget ---
    "a state over the budget is never posted": None,
    "the endpoint's own max_tokens_exceeded reads as too large": unknown_because(
        "verb_first", "the state was too large", status=400,
        body='{"error": {"type": "max_tokens_exceeded", "message": "too big"}}'),
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


def over_budget(m):
    """A state past `STATE_BUDGET`: not sent, not cut down, and still logged.

    THE STUB'S COUNTER IS THE ASSERTION. "It answered unknown" is satisfied by
    every other failure path too; "no request arrived" is what says the budget
    was read BEFORE the post rather than after a 400 came back."""
    big = {"title": "t", "body": "x" * (m.STATE_BUDGET + 1)}
    r = read(m, state=big)
    got = r.answers["verb_first"]
    rows = [json.loads(x) for x in LOG.read_text().splitlines() if x]
    return (got.word == "unknown" and SEEN["count"] == 0
            and str(m.STATE_BUDGET) in got.why and "not sent" in got.why
            and "never truncates" in got.why
            and r.logged.startswith("logged to") and len(rows) == 1
            and rows[0]["answers"]["verb_first"]["branch"] == "unknown"
            ), (got.why, SEEN["count"], r.logged, len(rows))


def env_not_text(m):
    """A `~/.env` that is not UTF-8: `read_text` raised past `ask` and out
    through `campaign-tracker check` as a traceback."""
    home = ROOT / "badenv"
    home.mkdir(exist_ok=True)
    (home / ".env").write_bytes(b"TYPESAFE_API_KEY=\xff\xfe\x00nonsense\n")
    r = read(m, key=None, home=home)
    got = r.answers["verb_first"]
    return (got.word == "unknown"
            and "did not read (UnicodeDecodeError)" in got.why), got


def raised_where_nothing_should(m):
    """A question spec missing a threshold: `branch` raises KeyError inside the
    call, and `ask`'s own boundary is the only thing between that and the
    caller's traceback.

    IT CATCHES RATHER THAN LETTING THE CRASH BE THE RESULT: a case that dies of
    the very exception it is asserting against reports "crashed", which the
    mutation runner reads as neither red nor green. Named here, it is red."""
    serving()
    try:
        r = m.ask("a suite", "a label", STATE,
                  {"verb_first": {"type": "noul", "instructions": "x"}},
                  env=env(), timeout=5)
    except Exception as e:  # noqa: BLE001 -- the thing under assertion
        return False, f"it raised {e.__class__.__name__} instead of answering"
    got = r.answers["verb_first"]
    return (got.word == "unknown"
            and "raised where nothing is meant to (KeyError)" in got.why), got


def log_refused(m):
    blocker = ROOT / "not-a-dir"
    blocker.write_text("")
    serving()
    r = m.ask("a suite", "a label", STATE, BOTH,
              env=env(log=blocker / "jev.log"), timeout=5)
    return ("answer not logged to" in r.logged
            and r.answers["verb_first"].word == "yes"), r.logged


CASES["a state over the budget is never posted"] = over_budget
CASES["the key is read from ~/.env when the environment has none"] = key_from_dotenv
CASES["a ~/.env that is not text is unknown, not a traceback"] = env_not_text
CASES["a call that raises where nothing should is unknown"] = raised_where_nothing_should
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
    ("the pinned model unread in the response", '    if out.get("model") != MODEL:',
     "    if False:", "a response naming another model is unknown"),
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
    ("the budget never measured", '    if size > STATE_BUDGET:', "    if False:",
     "a state over the budget is never posted"),
    ("the endpoint's max_tokens_exceeded unread",
     '        if e.code == 400 and "max_tokens_exceeded" in detail:',
     "        if False:",
     "the endpoint's own max_tokens_exceeded reads as too large"),
    # THE FOUR PATHS THAT USED TO RAISE. Each mutation puts the code back the
    # way it was, so the case that found it must go red on exactly that.
    ("the request built outside the try again",
     "    try:\n        # BUILDING THE REQUEST IS INSIDE THE TRY.",
     "    urllib.request.Request(url)\n    try:\n        #",
     "a URL with no scheme is unknown, not a traceback"),
    ("the ~/.env decode error let out", "    except (OSError, UnicodeDecodeError) as e:",
     "    except OSError as e:", "a ~/.env that is not text is unknown, not a traceback"),
    ("ask's boundary removed",
     "    except Exception as e:  # noqa: BLE001 -- the boundary; the promise is here",
     "    except ZeroDivisionError as e:", "a call that raises where nothing should is unknown"),
    ("a set-but-empty endpoint read as unset", "    if not url:",
     "    if False:", "an endpoint set to nothing never reaches the network"),
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
    return [min(values), max(values)] if values else None


def widened(was, seen, pad=0.02):
    """The declared band: the union of what was declared and THIS RUN PADDED.

    THE PADDING GOES ON THE OBSERVATION, NOT ON THE UNION. Padding the union
    widens the band by `pad` on every record whether or not anything moved, so
    a band that nothing had drifted still crept outward until it swallowed a
    threshold -- growth that reads exactly like drift and is not. This way a
    run inside the band changes nothing, and only a real excursion widens it."""
    if seen is None:
        return was
    lo = round(max(0.0, seen[0] - pad), 3)
    hi = round(min(1.0, seen[1] + pad), 3)
    if was:
        lo, hi = min(lo, was[0]), max(hi, was[1])
    return [lo, hi]


def inside(value, declared):
    return declared is not None and declared[0] <= value <= declared[1]


def live(record):
    """The fixture against the real endpoint.

    THE FIXTURE DECLARES THE BANDS AND THIS ASSERTS THEM. Every case must land
    inside its group's declared band, and each of `campaign-tracker.py`'s
    thresholds must sit STRICTLY between the two declared bands it separates.
    A recorded band no assertion reads is a number that drifts in silence,
    which is what these were before: the declared band is the contract, the
    observed one is the last run and says nothing on its own.

    `--record` widens the declared bands to hold this run. Widening past a
    threshold turns the assertion below red, which is the drift alarm: nothing
    here quietly moves a cut to fit new data."""
    jev = load(SOURCE)
    tracker = harness.load(HERE / "campaign-tracker.py", "campaign_tracker")
    cases = json.loads(FIXTURE.read_text())
    groups = cases["groups"]
    model = ""

    # ---------------------------------------------------------- verb-first
    seen = {"yes": [], "no": []}
    outside = []
    declared = groups["verb-first"].get("declared") or {}
    q = {"verb_first": {"type": "noul",
                        "instructions": tracker.VERB_FIRST_QUESTION,
                        "yes_over": tracker.VERB_FIRST_YES_OVER,
                        "no_under": tracker.VERB_FIRST_NO_UNDER}}
    for c in groups["verb-first"]["cases"]:
        # THE STATE IS PRODUCTION'S, title and body together and untruncated:
        # the body moves the title's answer, so a band measured on the title
        # alone, or on a body cut mid-word, is a band for a call never made.
        r = jev.ask("campaign-jev-test.py --live", c["id"],
                    {"title": c["title"], "body": c["body"]}, q)
        model = r.model or model
        raw = r.answers["verb_first"].raw
        if raw is None:
            check(f"live verb-first {c['id']} answered", False, r.answers)
            continue
        seen[c["truth"]].append(raw["noul"])
        if not record and not inside(raw["noul"], declared.get(c["truth"])):
            outside.append((c["id"], raw["noul"], c["truth"],
                            declared.get(c["truth"])))
        print(f"  {c['id']:<8} noul {raw['noul']:.2f}  truth {c['truth']}")
    check("live: every verb-first case answered",
          len(seen["yes"]) + len(seen["no"])
          == len(groups["verb-first"]["cases"]),
          (len(seen["yes"]), len(seen["no"])))
    print(f"  verb-first seen: yes {band(seen['yes'])}  no {band(seen['no'])}"
          f"  declared {declared}")

    # ----------------------------------------------------------- work-kind
    conf = {"confident": [], "unsure": []}
    kout, wrong, nomatch, floor_only = [], [], [], []
    kdeclared = groups["work-kind"].get("declared") or {}
    q = {"work_kind": {"type": "choice",
                       "instructions": tracker.WORK_KIND_QUESTION,
                       "criteria": tracker.WORK_KIND_CRITERIA,
                       "floor": tracker.WORK_KIND_FLOOR,
                       "no_match": tracker.WORK_KIND_NO_MATCH}}
    for c in groups["work-kind"]["cases"]:
        r = jev.ask("campaign-jev-test.py --live", c["id"],
                    {"title": c["title"], "body": c["body"]}, q)
        model = r.model or model
        got = r.answers["work_kind"]
        raw = got.raw
        if raw is None:
            check(f"live work-kind {c['id']} answered", False, r.answers)
            continue
        print(f"  {c['id']:<10} {raw['choice']:<12} conf {raw['confidence']:.2f}"
              f"  truth {c['truth']}  -> {got.word}")
        if c["truth"] == "unknown":
            nomatch.append((c["id"], raw["choice"], raw["confidence"], got.word))
            continue
        conf[c["band"]].append(raw["confidence"])
        if not record and not inside(raw["confidence"], kdeclared.get(c["band"])):
            kout.append((c["id"], raw["confidence"], c["band"],
                         kdeclared.get(c["band"])))
        if c["band"] == "confident" and raw["choice"] != c["truth"]:
            wrong.append((c["id"], raw["choice"], raw["confidence"], c["truth"]))
        if c["band"] == "unsure":
            floor_only.append((c["id"], raw["choice"], got.word))
    print(f"  work-kind seen: confident {band(conf['confident'])}  "
          f"unsure {band(conf['unsure'])}  declared {kdeclared}")

    # ------------------------------------------------------- the assertions
    # EACH DECLARED BAND HAS ONE EDGE THAT CARRIES THE CLAIM, the one facing
    # its threshold, and the fixture declares the other at the extreme: a `no`
    # answered lower, or a `confident` answered higher, moves away from the cut
    # and says nothing it is about. Asserting both edges cost a false alarm
    # the first time an `unsure` case answered 0.14 against a 0.15 declared.
    check("live: every verb-first case landed in its declared band",
          not outside, outside)
    check("live: every work-kind case landed in its declared band",
          not kout, kout)
    # THE THRESHOLDS AGAINST THE DECLARED BANDS, not against this run: a cut
    # measured against the run that just happened moves with it.
    check("live: the no-verb cut sits above the whole declared `no` band",
          bool(declared.get("no"))
          and declared["no"][1] < tracker.VERB_FIRST_NO_UNDER,
          (declared.get("no"), tracker.VERB_FIRST_NO_UNDER))
    check("live: the verb-first cut sits below the whole declared `yes` band",
          bool(declared.get("yes"))
          and tracker.VERB_FIRST_YES_OVER < declared["yes"][0],
          (tracker.VERB_FIRST_YES_OVER, declared.get("yes")))
    check("live: the two verb-first cuts do not cross",
          tracker.VERB_FIRST_NO_UNDER <= tracker.VERB_FIRST_YES_OVER,
          (tracker.VERB_FIRST_NO_UNDER, tracker.VERB_FIRST_YES_OVER))
    check("live: the floor sits above the whole declared `unsure` band",
          bool(kdeclared.get("unsure"))
          and kdeclared["unsure"][1] < tracker.WORK_KIND_FLOOR,
          (kdeclared.get("unsure"), tracker.WORK_KIND_FLOOR))
    check("live: the floor sits below the whole declared `confident` band",
          bool(kdeclared.get("confident"))
          and tracker.WORK_KIND_FLOOR < kdeclared["confident"][0],
          (tracker.WORK_KIND_FLOOR, kdeclared.get("confident")))
    check("live: every confident kind names the label the owner set",
          not wrong, wrong)
    # THE TWO WAYS A `choice` COMES BACK UNKNOWN, TOLD APART. Both branches
    # print the same word, so a case that asserted only the word would pass
    # with either one dead.
    check("live: the case fitting no option is unknown BY the no-match option",
          bool(nomatch) and all(o == tracker.WORK_KIND_NO_MATCH and w == "unknown"
                                for _i, o, _c, w in nomatch), nomatch)
    check("live: an unsure case is unknown by the FLOOR, naming a real option",
          bool(floor_only)
          and all(o != tracker.WORK_KIND_NO_MATCH and o in tracker.WORK_KINDS
                  and w == "unknown" for _i, o, w in floor_only), floor_only)
    check("live: the pinned model is the one that answered",
          model == jev.MODEL, model)

    if record:
        groups["verb-first"]["declared"] = {
            k: widened(declared.get(k), band(seen[k])) for k in ("yes", "no")}
        groups["verb-first"]["observed"] = {k: band(seen[k])
                                            for k in ("yes", "no")}
        groups["work-kind"]["declared"] = {
            k: widened(kdeclared.get(k), band(conf[k]))
            for k in ("confident", "unsure")}
        groups["work-kind"]["observed"] = {k: band(conf[k])
                                           for k in ("confident", "unsure")}
        groups["work-kind"]["observed"]["no-match"] = nomatch
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
