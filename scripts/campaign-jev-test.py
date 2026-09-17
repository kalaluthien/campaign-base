#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
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

It also reads the COMMITTED REGISTRY, `scripts/jev/readings.json`: every entry
carries what a reader branches on, a reading with no thresholds is at `shadow`
alone, one at `act` declares what it does and how it is undone and stays inside
the four bounds on an act, a declared wording is its question's hash, and no
Jev question is written anywhere else in this tree.

`--live` is the other half and is opt-in: it runs
`scripts/jev/corpus/<reading>.jsonl` -- cases of this tracker's own history,
one of which fits no option and one of which is a flip -- against the real
endpoint, asking the REGISTRY'S OWN question rather than a copy built here, so
what is measured is what production sends. It asserts a BAND per band key and
never a float, since the same request comes back a few hundredths apart: every
case must land in its DECLARED band, and each cut must sit strictly between the
two declared bands it separates. That is what makes a threshold measured rather
than chosen. `--record` widens the declared bands to hold an excursion, writes
them with the wording hash and the date into the entry, and appends one `seen`
row per case. `--wording <hash>` asks a retired wording from
`scripts/jev/wordings.json` instead, which is how a criteria change gets its
before-and-after numbers. A reading whose `question.per` says its own reader
composes one question per claim or per condition is SKIPPED and says so: the
entry's bare `instructions` are not what production sends, and a band measured
on them would belong to a call nobody makes.

Usage: scripts/campaign-jev-test.py [--live [--record] [--wording <hash>]]
"""
import contextlib
import datetime
import http.server
import importlib
import json
import os
import re
import shutil
import socket
import subprocess
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
REGISTRY = HERE / "jev" / "readings.json"
WORDINGS = HERE / "jev" / "wordings.json"
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

NOUL_CRITERIA = {"true": {"what": "it opens with an order",
                          "examples": ["Cache the feed"]},
                 "false": {"what": "it opens with anything else",
                           "examples": ["The feed is cold"]}}
NOUL_Q = {"type": "noul", "instructions": "Is the title verb-first?",
          "criteria": NOUL_CRITERIA, "yes_over": 0.85, "no_under": 0.70}
CHOICE_Q = {"type": "choice", "instructions": "What kind of work is this?",
            "criteria": {"research": "ask", "development": "build",
                         "maintenance": "tidy", "none": "not work at all"},
            "floor": 0.60, "no_match": "none"}
OPTION_Q = {"type": "choice", "instructions": "Is the claim true of the text?",
            "criteria": {"supports": "true", "contradicts": "false",
                         "says_nothing": "neither"},
            "option": "contradicts", "yes_over": 0.50, "no_under": 0.20}
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


def clear_store():
    """The stored answers beside the log, gone. Every case below asks about a
    call that was MADE, so a case reading the answer a case before it stored
    would be measuring the store and calling it the endpoint."""
    shutil.rmtree(LOG.parent / "jev-cache", ignore_errors=True)


def read(m, questions=None, **kw):
    """One call against the stub, with the log truncated and the store cleared
    first so each case reads its own call and never the run before it."""
    LOG.write_text("")
    clear_store()
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
    check("branch: a noul between the two edges is uncertain, not unknown",
          m.branch(NOUL_Q, noul(0.78))[0] == "uncertain")
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
    probs = lambda c: {"type": "choice", "choice": "supports", "confidence": 0.9,  # noqa: E731
                       "probabilities": {"supports": 1 - c, "contradicts": c}}
    check("branch: one option's probability over the cut is yes, whoever won",
          m.branch(OPTION_Q, probs(0.55))[0] == "yes")
    check("branch: one option's probability under the cut is no",
          m.branch(OPTION_Q, probs(0.10))[0] == "no")
    check("branch: one option's probability between the edges is uncertain",
          m.branch(OPTION_Q, probs(0.35))[0] == "uncertain")
    # THE SECOND EDGE OF A `choice`'s BAND. `floor` alone was a lone cut inside
    # the measured `confident` band, which is what flips on noise; `certain_over`
    # is its upper edge and what falls between them is `uncertain`.
    banded = dict(CHOICE_Q, floor=0.45, certain_over=0.50)
    check("branch: a choice over the upper edge is the option",
          m.branch(banded, pick("research", 0.51))[0] == "research")
    check("branch: a choice between the two edges is uncertain",
          m.branch(banded, pick("research", 0.47))[0] == "uncertain")
    check("branch: a choice under the lower edge is still unknown",
          m.branch(banded, pick("research", 0.44))[0] == "unknown")
    check("branch: the no-match option is unknown inside the band too",
          m.branch(banded, pick("none", 0.47))[0] == "unknown")
    # A READING THAT DECLARES NO EDGE records and judges nothing. Legal at
    # `shadow` alone, where a reading enters to collect cases.
    bare_choice = {k: v for k, v in CHOICE_Q.items()
                   if k not in ("floor", "no_match")}
    got, why = m.branch(bare_choice, pick("research", 0.31))
    check("branch: a choice with no cut records the model's own option",
          got == "research" and "no cut is declared" in why, (got, why))
    bare_noul = {k: v for k, v in NOUL_Q.items()
                 if k not in ("yes_over", "no_under")}
    got, why = m.branch(bare_noul, noul(0.31))
    check("branch: a noul with no cut is uncertain, since it has no word",
          got == "uncertain" and "no cut is declared" in why, (got, why))
    check("branch: an answer carrying no probabilities is unknown",
          m.branch(OPTION_Q, {"type": "choice", "choice": "supports",
                              "confidence": 0.9})[0] == "unknown")
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
    # A `noul`'s CRITERIA MUST REACH THE MODEL. It is optional to the API and
    # was absent from the question this tree asks, which is what pins a subtle
    # yes/no boundary; a whitelist that dropped it would leave the question
    # asked the old way with the new bands measured for the new one.
    "a noul's criteria reaches the model whole": lambda m: (
        read(m) and json.loads(SEEN["body"])["questions"]["verb_first"]
        .get("criteria") == NOUL_CRITERIA,
        json.loads(SEEN["body"] or "{}").get("questions", {})
        .get("verb_first", {}).get("criteria")),
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
    "a noul between the two edges is uncertain": lambda m: (
        lambda a: (a.word == "uncertain" and "in the band between" in a.why,
                   (a.word, a.why)))(read(m, noul=0.78).answers["verb_first"]),
    "a confident fitting option is the option": word(
        "work_kind", "maintenance", confidence=0.95),
    "a choice cut on one option reads that option's probability": lambda m: (
        lambda r: (r.answers["claim"].word == "yes", r.answers["claim"]))(
        read(m, questions={"claim": OPTION_Q}, body={"model": MODEL, "answers": {
            "claim": {"type": "choice", "choice": "supports", "confidence": 0.3,
                      "probabilities": {"supports": 0.45, "contradicts": 0.52,
                                        "says_nothing": 0.03}}}})),
    "a choice under the floor is unknown": unknown_because(
        "work_kind", "under the floor", confidence=0.51),
    # THE SECOND EDGE, THROUGH A WHOLE CALL. `floor` alone was a lone cut inside
    # the measured `confident` band; `certain_over` is that band's lower edge
    # and what falls between the two is `uncertain` -- an answer that happened.
    "a choice between the two edges is uncertain": lambda m: (
        lambda a: (a.word == "uncertain" and "sits in the band" in a.why,
                   (a.word, a.why)))(
        read(m, questions={"work_kind": dict(CHOICE_Q, floor=0.45,
                                             certain_over=0.50)},
             confidence=0.47).answers["work_kind"]),
    # A READING THAT DECLARES NO EDGE, through a whole call: the model's own
    # option is recorded and nothing is judged. That is what `shadow` is for.
    "a reading with no cut records and judges nothing": lambda m: (
        lambda a: (a.word == "maintenance" and "no cut is declared" in a.why,
                   (a.word, a.why)))(
        read(m, questions={"work_kind": {k: v for k, v in CHOICE_Q.items()
                                         if k not in ("floor", "no_match")}},
             confidence=0.31).answers["work_kind"]),
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
    # THE REASON NAMES THE VARIABLE, not the endpoint: nothing was asked of
    # any endpoint, so "the endpoint did not answer" would send a reader
    # looking at a service that was never reached.
    "a URL with no scheme is unknown and blames the variable": unknown_because(
        "verb_first", "`CAMPAIGN_JEV_URL` names no usable endpoint",
        url="garbage"),
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
    """A question spec declaring ONE of its two edges: `branch` raises KeyError
    inside the call, and `ask`'s own boundary is the only thing between that and
    the caller's traceback. One edge and not none, because none is a reading
    that declares no cut at all, which is legal at `shadow` and judges nothing;
    a half-declared band is the caller's bug and `thresholds_or_shadow` refuses
    it in the registry.

    IT CATCHES RATHER THAN LETTING THE CRASH BE THE RESULT: a case that dies of
    the very exception it is asserting against reports "crashed", which the
    mutation runner reads as neither red nor green. Named here, it is red."""
    serving()
    try:
        r = m.ask("a suite", "a label", STATE,
                  {"verb_first": {"type": "noul", "instructions": "x",
                                  "no_under": 0.2}},
                  env=env(), timeout=5)
    except Exception as e:  # noqa: BLE001 -- the thing under assertion
        return False, f"it raised {e.__class__.__name__} instead of answering"
    got = r.answers["verb_first"]
    return (got.word == "unknown"
            and "raised where nothing is meant to (KeyError)" in got.why), got


def skip_logged(m):
    LOG.write_text("")
    note = m.skip("a suite", "a label", "the kind read failed (TimeoutExpired)",
                  env=env())
    rows = [json.loads(x) for x in LOG.read_text().splitlines() if x]
    ok = (len(rows) == 1 and rows[0]["reader"] == "a suite"
          and rows[0]["read"] == "a label" and rows[0]["asked"] == MODEL
          and rows[0]["skipped"] == "the kind read failed (TimeoutExpired)"
          and "answers" not in rows[0] and note.startswith("logged to"))
    return ok, (rows, note)


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
CASES["a skipped reading is logged as one JSON line naming why"] = skip_logged

# ------------------------------------------------- the registry, well-formed
# THE ENTRY IS THE CONTRACT, so these read the committed file and not a
# fixture: a registry that would not load, or an entry a reader cannot branch
# on, is the one failure no live run would ever reach.


def entries(m):
    return m.load_registry()


def registry_shape(m):
    """Every entry carries what a reader branches on, and nothing it cannot."""
    bad = []
    for name, e in entries(m).items():
        for field in ("owner", "tier", "group", "state", "prefilter",
                      "question", "join", "bands"):
            if field not in e:
                bad.append(f"{name}: no `{field}`")
        if e.get("tier") not in m.TIERS:
            bad.append(f"{name}: tier `{e.get('tier')}`")
        if not (e.get("state") or {}).get("fields"):
            bad.append(f"{name}: no state fields")
        q = e.get("question") or {}
        if q.get("type") not in (m.NOUL, m.CHOICE):
            bad.append(f"{name}: question type `{q.get('type')}`")
        if not q.get("instructions") or not q.get("criteria"):
            bad.append(f"{name}: a question with no instructions or criteria")
    return not bad, bad


def thresholds_or_shadow(m):
    """A reading with no thresholds is legal at `shadow` alone: there is no
    branch to take, so printing one would be a verdict nobody measured."""
    bad = []
    for name, e in entries(m).items():
        cuts, q = e.get("thresholds") or {}, e.get("question") or {}
        if not cuts:
            if e.get("tier") != m.SHADOW:
                bad.append(f"{name}: no thresholds at tier `{e['tier']}`")
            continue
        # A `choice` IS CUT ONE OF TWO WAYS, and both are whole. The ordinary
        # one is the winner's confidence against a `floor`, beside the name of
        # the no-match option; the other names ONE `option` and cuts its own
        # probability as a `noul` is cut, for a reading that flags one word --
        # `contradicts` -- where the winner would hide a strong second.
        if q.get("type") == m.NOUL or "option" in cuts:
            want = ("yes_over", "no_under")
        else:
            want = ("floor", "no_match")
        for k in want:
            if k not in cuts:
                bad.append(f"{name}: no `{k}`")
        options = q.get("criteria") or {}
        for k in ("no_match", "option"):
            if k in cuts and cuts[k] not in options:
                bad.append(f"{name}: `{k}` names no option of the set")
    return not bad, bad


def act_declares_its_undo(m):
    """A reading at `act` says what it does, how it is undone, and the two cuts
    `does` reads -- or it does not load. An irreversible thing on a typed guess
    is the one answer this module never gives, and a missing cut would reach
    `does` as a KeyError on the one call that cleared its threshold.

    MADE ENTRIES, NOT THE COMMITTED REGISTRY, which holds nothing at `act`: a
    case that reads the registry alone passes over an empty set and proves
    nothing (the REVIEW at a73fc57, note 3).
    """
    bad = []
    for missing in m.ACT_FIELDS:
        act = {"verb": "label", "label": "kind:development", "what": "x",
               "undo": "y", "act_over": 0.9, "ask_over": 0.7}
        act.pop(missing)
        ok, why = refused(m, acting(**act), f"no `{missing}`")
        if not ok:
            bad.append((missing, why))
    whole = acting(verb="label", label="kind:development", what="x", undo="y",
                   act_over=0.9, ask_over=0.7)
    ok, _why = refused(m, whole, "")
    if ok:
        bad.append(("all four", "a whole act was refused"))
    # The entries the tree actually ships, judged the same way.
    for name, e in entries(m).items():
        if e.get("tier") == m.ACTS:
            for k in m.ACT_FIELDS:
                if k not in (e.get("act") or {}):
                    bad.append(f"{name}: at `act` with no `{k}`")
    return not bad, bad


def wording_is_computed(m):
    """A declared wording is the hash of the question beside it. A rewording
    that kept the old hash would keep a band measured for another question."""
    bad = [f"{n}: declares {e['bands']['wording']}, computed {m.wording(e)}"
           for n, e in entries(m).items()
           if (e.get("bands") or {}).get("wording")
           and e["bands"]["wording"] != m.wording(e)]
    return not bad, bad


def no_question_outside_the_registry(m):
    """The one home of a question. A script that writes its own would be a
    second wording nothing measures and no `report` counts."""
    allowed = {"campaign-jev.py"}
    found = []
    for root in [HERE, *sorted((HERE.parent / ".claude" / "skills").glob(
            "*/scripts"))]:
        for path in sorted(root.glob("*.py")):
            if path.name in allowed or path.name.endswith("-test.py"):
                continue
            # A QUESTION WRITTEN, not a question READ. `"instructions":` with
            # a value after it is a question being composed; `q["instructions"]`
            # is a script reading the registry's, which is the sanctioned path
            # and is what `check-docstring-claims.py` does.
            if re.search(r'["\']instructions["\']\s*:', path.read_text(encoding="utf-8")):
                found.append(str(path))
    return not found, found


# ------------------------------------------------------ the join and the reader
# THE JOIN IS WHAT MAKES THE CORPUS GROW BY ITSELF, so it is exercised offline
# against a stubbed fetch: `fetch_issue` is the one call out, and every join
# reads what it returns. The corpus and the log are a case's own temp files --
# a suite that wrote into `scripts/jev/corpus/` would be a suite that edits the
# evidence.
ISSUES = {
    ("kalaluthien/campaign-base", 900): {
        "title": "Cache the weather feed", "state": "CLOSED", "labels": [],
        "closedByPullRequestsReferences": [
            {"number": 28, "repository": {"name": "dotclaude",
                                          "owner": {"login": "kalaluthien"}}}]},
    ("kalaluthien/campaign-base", 901): {
        "title": "A title somebody rewrote", "state": "CLOSED", "labels": [
            {"name": "kind:development"}]},
    ("kalaluthien/campaign-base", 902): {
        "title": "Still being argued about", "state": "OPEN", "labels": []},
}


# ONE PULL REQUEST THREAD PER SUBJECT, as `ISSUES` is one issue per subject:
# the thread's join asks what came AFTER the REPORT it judged.
THREADS = {
    ("kalaluthien/campaign-base", 700): {
        "state": "OPEN", "comments": [
            {"created_at": "2026-09-17T01:00:00Z",
             "body": "REVIEW r-1: F1 the ceiling is stated twice, and the "
                     "second copy is the one that drifts"},
            {"created_at": "2026-09-17T02:00:00Z", "body": "NOTE w-1: pushed"}]},
    ("kalaluthien/campaign-base", 701): {
        "state": "MERGED", "comments": [
            {"created_at": "2026-09-17T02:00:00Z", "body": "NOTE w-1: merged"}]},
}


def thread_row(call, number, findings, **kw):
    row = {"at": "2026-09-17T00:00:00+00:00", "call": call,
           "reading": "C-report-disposes-finding",
           "subject": f"kalaluthien/campaign-base#{number} thread",
           "read": f"kalaluthien/campaign-base#{number} thread",
           "repo": "kalaluthien/campaign-base", "pull_request": number,
           "state": {"findings": findings, "report": "REPORT w-1: fixed",
                     "review": "REVIEW r-1: ...", "thread": "..."},
           "wording": "0" * 12, "settled": None, "tier": "shadow",
           "does": "nothing", "asked": MODEL, "answered": MODEL, "latency": 0.5,
           "branch": None, "raw": {}, "why": "", "endpoint": "real",
           "flag": None}
    row.update(kw)
    return row


def log_row(call, reading, title, number, **kw):
    row = {"at": "2026-09-17T00:00:00+00:00", "call": call, "reading": reading,
           "subject": f"kalaluthien/campaign-base#{number}",
           "read": f"kalaluthien/campaign-base#{number}",
           "repo": "kalaluthien/campaign-base", "issue": number,
           "state": {"title": title, "body": "- a body"},
           "wording": "0" * 12, "settled": None, "tier": "advise",
           "does": "show", "asked": MODEL, "answered": MODEL, "latency": 0.5,
           "branch": "yes", "raw": {"type": "noul", "noul": 0.9}, "why": "",
           "endpoint": "real", "flag": None}
    row.update(kw)
    return row


def joined(m, rows):
    """`corpus join` over one temp log and one temp corpus, with the fetch
    stubbed. Returns (the cases by reading, the log's line count after)."""
    corpus = ROOT / f"corpus-{abs(hash(SOURCE)) % 9999}-{len(rows)}"
    if corpus.exists():
        for f in corpus.glob("*"):
            f.unlink()
    log = ROOT / "join.log"
    log.write_text("".join(json.dumps(r) + "\n" for r in rows))
    was = m.CORPUS
    m.CORPUS = corpus
    old = os.environ.get("CAMPAIGN_JEV_LOG")
    os.environ["CAMPAIGN_JEV_LOG"] = str(log)
    try:
        args = types.SimpleNamespace(
            fetch=lambda repo, number: ISSUES.get((repo, number)),
            fetch_thread=lambda repo, number: THREADS.get((repo, number)))
        m.cmd_corpus_join(args)
        out = {n: m.read_corpus(n) for n in
               ("verb-first", "work-kind", "C-report-disposes-finding")}
    finally:
        m.CORPUS = was
        if old is None:
            os.environ.pop("CAMPAIGN_JEV_LOG", None)
        else:
            os.environ["CAMPAIGN_JEV_LOG"] = old
    return out, len(log.read_text().splitlines())


def join_labels_a_closed_issue(m):
    """The title kept through the close labels the state `yes`; the title
    rewritten before it labels the state as judged `no`."""
    cases, _lines = joined(m, [
        log_row("aaaa", "verb-first", "Cache the weather feed", 900),
        log_row("bbbb", "verb-first", "The title as it was judged", 901)])
    by = {c["id"]: c for c in cases["verb-first"]}
    kept = by.get("verb-first-aaaa") or {}
    moved = by.get("verb-first-bbbb") or {}
    return (kept.get("truth") == "yes" and moved.get("truth") == "no"
            and kept.get("label", {}).get("from") == "join:issue-title-kept"
            and kept.get("source", {}).get("ref") == "aaaa:verb-first"),  \
        (kept.get("truth"), moved.get("truth"), kept.get("label"))


def join_reads_the_kind_label(m):
    """work-kind's join is the `kind:` label the issue carries now: the
    owner's word, the strongest label this tree has."""
    cases, _lines = joined(m, [
        log_row("cccc", "work-kind", "A title somebody rewrote", 901,
                branch="maintenance",
                raw={"type": "choice", "choice": "maintenance",
                     "confidence": 0.8})])
    got = (cases["work-kind"] or [{}])[0]
    return (got.get("truth") == "development"
            and got.get("label", {}).get("from") == "join:issue-kind-label"), got


def join_keeps_what_it_cannot_label(m):
    """A row it cannot label yet STAYS in the log and is counted. A row dropped
    before it is joined is a case nobody will ever have."""
    cases, lines = joined(m, [
        log_row("dddd", "verb-first", "Still being argued about", 902),
        log_row("eeee", "verb-first", "No key at all", 900, repo=None,
                issue=None)])
    return (not cases["verb-first"] and lines == 2), (cases["verb-first"], lines)


def join_reads_a_later_review_on_the_thread(m):
    """C-report-disposes-finding's join: a finding a LATER REVIEW raises again
    is one the REPORT did not dispose. The strong half of the two."""
    cases, _lines = joined(m, [thread_row("tttt", 700, {
        "F1": "the ceiling is stated twice and the second copy drifts",
        "F2": "the usage line still calls the flag --dry"})])
    got = (cases["C-report-disposes-finding"] or [{}])[0]
    return (got.get("truth") == {"F1": "undisposed", "F2": "disposed"}
            and got.get("label", {}).get("from") == "join:thread-refinding"
            and "raised again: F1" in got.get("label", {}).get("evidence", "")),\
        got


def join_waits_for_the_merge_on_an_open_thread(m):
    """The WEAK half waits: with no later REVIEW, only a MERGED pull request
    labels the disposed class. An open one is a thread nobody has looked at
    again, which is not agreement."""
    open_pr, _l = joined(m, [thread_row("uuuu", 700, {"F9": "nobody re-raised"},
                                        at="2026-09-17T09:00:00+00:00")])
    merged, _l2 = joined(m, [thread_row("vvvv", 701, {"F9": "nobody re-raised"})])
    got = (merged["C-report-disposes-finding"] or [{}])[0]
    return (not open_pr["C-report-disposes-finding"]
            and got.get("truth") == {"F9": "disposed"}
            and "merged with no REVIEW" in got.get("label", {}).get("evidence", "")),\
        (open_pr["C-report-disposes-finding"], got)


def join_writes_one_case_for_one_row(m):
    """Run twice, and the second run writes nothing: a case is keyed by the
    call and the reading, so a join that ran again would otherwise double every
    case it had already labelled."""
    rows = [log_row("ffff", "verb-first", "Cache the weather feed", 900)]
    first, _l = joined(m, rows)
    corpus = ROOT / f"corpus-{abs(hash(SOURCE)) % 9999}-1"
    # The same temp corpus is reused by `joined` for a one-row list, so the
    # second call meets the case the first wrote.
    was, out = m.CORPUS, None
    m.CORPUS = corpus
    old = os.environ.get("CAMPAIGN_JEV_LOG")
    os.environ["CAMPAIGN_JEV_LOG"] = str(ROOT / "join.log")
    try:
        m.cmd_corpus_join(types.SimpleNamespace(
            fetch=lambda repo, number: ISSUES.get((repo, number)),
            fetch_thread=lambda repo, number: THREADS.get((repo, number))))
        out = m.read_corpus("verb-first")
    finally:
        m.CORPUS = was
        if old is None:
            os.environ.pop("CAMPAIGN_JEV_LOG", None)
        else:
            os.environ["CAMPAIGN_JEV_LOG"] = old
    return len(first["verb-first"]) == 1 and len(out) == 1, \
        (len(first["verb-first"]), len(out or []))


def a_joined_case_is_held_to_a_band(m):
    """THE DEFECT THE REVIEW AT a73fc57 FOUND: `corpus join` wrote a case with
    no `band`, and the drift reader resolved the band from the TRUTH word --
    which for a `choice` is an option name and never a band name. So every case
    the join added was drift-blind for good, at any confidence, while the
    evidence row and the agreement share went on counting it.

    The case is the join's own output, not a hand-built dict: a regression test
    over a shape the join does not actually write would pass with the join
    still broken."""
    entry = m.load_registry()["work-kind"]
    cases, _lines = joined(m, [
        log_row("gggg", "work-kind", "A title somebody rewrote", 901,
                wording=m.wording(entry), branch="maintenance",
                raw={"type": "choice", "choice": "maintenance",
                     "confidence": 0.01})])
    got = (cases["work-kind"] or [{}])[0]
    drifted, unplaced = m.drift_line(entry, cases["work-kind"])
    return (got.get("band") == "confident" and "work-kind-gggg" in drifted
            and "0.01" in drifted and not unplaced), (got.get("band"), drifted,
                                                      unplaced)


def a_case_held_to_no_band_is_listed(m):
    """And the other half: a case `band_of` cannot place is RETURNED, never
    skipped. A case counted by the evidence row while no band could call it
    drifted is the shape this reader was blind in."""
    entry = m.load_registry()["work-kind"]
    nomatch = {"id": "a-no-match", "reading": "work-kind", "role": "no-match",
               "truth": "none", "state": {}, "label": {"from": "owner"},
               "source": {"kind": "fixture"},
               "seen": [{"model": MODEL, "wording": m.wording(entry),
                         "raw": {"type": "choice", "choice": "none",
                                 "confidence": 0.99}}]}
    _drifted, unplaced = m.drift_line(entry, [nomatch])
    return (len(unplaced) == 1 and "a-no-match" in unplaced[0]
            and "no-match case" in unplaced[0]), unplaced


CASES["the thread join reads a later REVIEW that raised the finding again"] = join_reads_a_later_review_on_the_thread
CASES["the thread join waits for the merge where nothing was re-raised"] = join_waits_for_the_merge_on_an_open_thread
CASES["a case the join writes is held to a band, and drift reads it"] = a_joined_case_is_held_to_a_band
CASES["a case held to no band is listed, never skipped"] = a_case_held_to_no_band_is_listed


# ------------------------------------------- one thread, one call, per finding
# A READING WHOSE `question.per` NAMES A STATE FIELD is asked once per key of
# that field, IN THE SAME CALL: every question over one pull request thread goes
# in the one call (DECISION 5716060001), and the answers come back as one
# `Verdict` carrying {key: raw} and no word.
THREAD_STATE = {"report": "REPORT w-1: F1 fixed", "findings": {"F1": "a", "F2": "b"},
                "review": "REVIEW r-1: two findings", "thread": "comment w-1: ..."}


def thread_answers(**kw):
    """The stub's reply, keyed the way `judge` fans a per-item reading out."""
    def picked(p):
        return {"type": "choice", "choice": "supports", "confidence": 0.9,
                "probabilities": {"supports": p, "contradicts": 1 - p,
                                  "says_nothing": 0.0}}
    answers = {"C-report-disposes-finding#F1": picked(kw.get("f1", 0.95)),
               "C-report-disposes-finding#F2": picked(kw.get("f2", 0.10)),
               "C-review-not-the-author": picked(0.9)}
    NEXT["status"], NEXT["body"] = 200, {"model": MODEL, "answers": answers}
    SEEN["count"] = 0


def a_per_item_reading_is_one_call(m):
    """Two findings and the other reading of the group: three questions, ONE
    request, and each question's instructions name its own item, since the id
    never reaches the model."""
    LOG.write_text("")
    clear_store()
    thread_answers()
    judged = m.judge("pull-request-thread", THREAD_STATE, read="a thread",
                     env=env(), timeout=5, log=False)
    sent = json.loads(SEEN["body"])["questions"]
    v = judged.verdicts["C-report-disposes-finding"]
    named = {qid: "findings.F1" in q["instructions"]
             for qid, q in sent.items() if qid.endswith("#F1")}
    return (SEEN["count"] == 1 and len(sent) == 3 and v.word is None
            and sorted(v.raw) == ["F1", "F2"] and all(named.values())
            and judged.verdicts["C-review-not-the-author"].word == "supports"),\
        (SEEN["count"], sorted(sent), v.word, sorted(v.raw or {}), named)


def a_cleared_finding_is_never_sent(m):
    """H5: what the prefilter settles is never sent. The settled word may be a
    {item: word} dict, and only the items it names are cleared."""
    LOG.write_text("")
    clear_store()
    thread_answers()
    judged = m.judge("pull-request-thread", THREAD_STATE, read="a thread",
                     settled={"C-report-disposes-finding": {"F1": "disposed"}},
                     env=env(), timeout=5, log=False)
    sent = sorted(json.loads(SEEN["body"])["questions"])
    return (sent == ["C-report-disposes-finding#F2", "C-review-not-the-author"]
            and sorted(judged.verdicts["C-report-disposes-finding"].raw)
            == ["F2"]), sent


def a_flag_may_be_computed_from_the_answers(m):
    """A reader cannot compute a flag from answers it has not got back yet, so
    `flag` may be a callable. The log row carries what code computed and which
    answer moved it."""
    LOG.write_text("")
    clear_store()
    thread_answers()
    m.judge("pull-request-thread", THREAD_STATE, read="a thread", env=env(),
            timeout=5, flag=lambda name, raw: {"code": len(raw or {})})
    rows = [json.loads(ln) for ln in LOG.read_text().splitlines()]
    by = {r["reading"]: r for r in rows}
    return (by["C-report-disposes-finding"]["flag"] == {"code": 2}
            and by["C-report-disposes-finding"]["branch"] is None), rows


def a_per_item_question_must_name_its_item(m):
    """Without the marker the same question would be asked once per item and
    answered once per item, identically -- the id never reaches the model."""
    reg = m.load_registry()
    entry = reg["C-report-disposes-finding"]
    entry["question"] = dict(entry["question"],
                             instructions="How does `report` relate?")
    try:
        m.judge("pull-request-thread", THREAD_STATE, reg=reg, env=env(CLOSED),
                timeout=1)
    except ValueError as e:
        return "{item}" in str(e), str(e)
    return False, "it asked the same question once per item"


CASES["every question over one thread goes in one call, one per finding"] = a_per_item_reading_is_one_call
CASES["a finding the prefilter cleared is never sent"] = a_cleared_finding_is_never_sent
CASES["a flag the reader computes from the answers reaches the log row"] = a_flag_may_be_computed_from_the_answers
CASES["a per-item question must name its item"] = a_per_item_question_must_name_its_item


def a_key_names_its_repository(m):
    """A number without its repository is refused: a member repository's pull
    request closes a sub-issue here and its number collides with this
    tracker's -- 33 of 199 closing links (rule-check#460 NOTE 5713928884)."""
    bad = []
    for key in ({"issue": 455}, {"pull_request": 28},
                {"repo": "kalaluthien/campaign-base", "comment": 5}):
        try:
            m.judge("issue-shape", {"title": "t", "body": "b"}, key=key,
                    env=env(url=CLOSED), timeout=1)
        except ValueError as e:
            if "repo" not in str(e):
                bad.append((key, str(e)))
            continue
        if "repo" not in key:
            bad.append((key, "took a number with no repository"))
    return not bad, bad


CASES["the join labels a closed issue by what happened to its title"] = join_labels_a_closed_issue
CASES["the join reads the kind label the owner set"] = join_reads_the_kind_label
CASES["a row the join cannot label stays in the log and is counted"] = join_keeps_what_it_cannot_label
CASES["joining twice writes one case"] = join_writes_one_case_for_one_row
CASES["a join key names its repository beside every number"] = a_key_names_its_repository


def refused(m, entry, fragment, name="a-reading"):
    """(whether loading a registry holding `entry` refused, naming `fragment`,
    the message). The bounds are read where the registry is LOADED, so this is
    the moment a bad entry is stopped -- not the call that happens to clear a
    threshold months later."""
    try:
        m.check_act_bounds({name: entry})
    except ValueError as e:
        return fragment in str(e), str(e)
    return False, "loaded without a word"


def acting(**act):
    """An entry at tier `act`, otherwise well-formed."""
    return {"owner": "a suite", "tier": "act", "group": "g",
            "state": {"fields": ["title"], "why": ""},
            "prefilter": {"what": ""},
            "question": {"type": "noul", "instructions": "?",
                         "criteria": {"true": {}, "false": {}}},
            "thresholds": {"yes_over": 0.9, "no_under": 0.1},
            "join": "j", "bands": {}, "act": act}


def act_never_moves_a_person_label(m):
    """BOUND a: `standing`, `backlog`, `bound:` and `campaign:` are a person's
    alone -- nothing here can observe that they changed their mind."""
    bad = []
    for label in ("standing", "backlog", "bound:mini", "campaign:rule-check"):
        ok, why = refused(m, acting(verb="label", label=label, what="", undo="",
                                    act_over=0.9, ask_over=0.7), "bound a")
        if not ok:
            bad.append((label, why))
    ok, _why = refused(m, acting(verb="label", label="kind:development",
                                 what="", undo="", act_over=0.9, ask_over=0.7),
                       "bound a")
    if ok:
        bad.append(("kind:development", "refused, and it is not a person's"))
    return not bad, bad


def act_is_never_an_event_with_an_actor(m):
    """BOUND b: a claim, a release, a merge, a close, a launch and a retire each
    have an actor in the model, and a judgment is not one."""
    bad = []
    for verb in m.NEVER_ACTED:
        ok, why = refused(m, acting(verb=verb, what="", undo="", act_over=0.9,
                                    ask_over=0.7), "bound b")
        if not ok:
            bad.append((verb, why))
    return not bad, bad


def act_carries_no_command_for_this_module(m):
    """BOUND c: the write is made by the calling reader's own session through
    the ordinary guarded path, so no entry hands this module a command."""
    bad = []
    for field in m.NEVER_IN_AN_ENTRY:
        ok, why = refused(m, acting(verb="label", label="kind:development",
                                    what="", undo="", act_over=0.9,
                                    ask_over=0.7, **{field: "gh issue edit"}),
                          "bound c")
        if not ok:
            bad.append((field, why))
    return not bad, bad


def this_module_carries_out_no_act(m):
    """BOUND c, the other half: `campaign-jev.py` writes nothing to GitHub. It
    reads an issue for a join and nothing else, so every write a judgment
    causes is the reader's session's and is judged by its role and its claim."""
    writes = ("gh issue edit", "gh issue close", "gh issue comment", "gh pr ",
              "gh label", "gh api -X", "--method POST", "--method PATCH")
    found = [w for w in writes if w in SOURCE]
    return not found, found


def act_never_opens_a_decision(m):
    """BOUND d: the answer to a `BLOCKED` is a planner's `DECISION`
    (`EscalationGoesThroughAPlanner`), so no reading writes one -- at `act`, at
    `advise` or at `shadow`."""
    bad = []
    for tier in ("shadow", "advise", "act"):
        entry = acting(verb="comment", opens="DECISION", what="", undo="",
                       act_over=0.9, ask_over=0.7)
        entry["tier"] = tier
        ok, why = refused(m, entry, "bound d")
        if not ok:
            bad.append((tier, why))
    return not bad, bad


def a_blocked_reading_may_only_route(m):
    """BOUND d: on a `BLOCKED` the ceiling is `advise` plus a route label."""
    entry = acting(verb="comment", opens="NOTE", what="", undo="",
                   act_over=0.9, ask_over=0.7)
    entry["subject"] = "blocked"
    ok, why = refused(m, entry, "bound d")
    routed = acting(verb="label", label="kind:development", what="", undo="",
                    act_over=0.9, ask_over=0.7)
    routed["subject"] = "blocked"
    also, why2 = refused(m, routed, "bound d")
    return ok and not also, (why, why2)


def relive_appends_and_never_replaces(m):
    """`report --live` re-asks a case and APPENDS what came back. A run that
    overwrote the one before it would erase the evidence of drift, which is the
    one thing the run history is for."""
    corpus = ROOT / "relive"
    corpus.mkdir(exist_ok=True)
    entry = m.load_registry()["verb-first"]
    case = {"id": "a-case", "reading": "verb-first",
            "state": {"title": "Cache the feed", "body": "- a body"},
            "truth": "yes", "label": {"from": "owner"},
            "source": {"kind": "fixture"}, "role": "case",
            "seen": [{"model": MODEL, "wording": "old", "at": "2026-01-01",
                      "word": "no", "raw": {"type": "noul", "noul": 0.1}}]}
    serving(noul=0.95)
    NEXT["body"] = {"model": MODEL,
                    "answers": {"verb-first": {"type": "noul", "noul": 0.95}}}
    out = m.relive("verb-first", entry, [case], env=env(), root=corpus)
    seen = out[0]["seen"]
    return (len(seen) == 2 and seen[0]["wording"] == "old"
            and seen[1]["wording"] == m.wording(entry)
            and seen[1]["word"] == "yes"), seen


CASES["report --live appends a run and replaces none"] = relive_appends_and_never_replaces


def every_case_fits_its_entry(m):
    """A case of a REGISTERED reading is re-askable: its state carries exactly
    the fields the entry names, and its truth is a word the reading answers.

    THE UNREGISTERED CASES ARE NOT JUDGED HERE and are not thereby unchecked:
    rule-check#460's step 2 corpus lands before its readings do, one state per
    pull request, so `report` counts them by reading until each entry
    arrives."""
    reg = entries(m)
    bad = []
    for name, entry in reg.items():
        want = set(entry["state"]["fields"])
        # WHICH WORDS A READING ANSWERS IS THE CUT'S, NOT THE TYPE'S. A
        # `choice` cut on ONE option answers yes, no or unknown about that
        # option, exactly as a `noul` does -- so the option cut is read first,
        # and only a `choice` cut on the winner answers an option word.
        if (entry.get("thresholds") or {}).get("option"):
            words = {"yes", "no", "none"}
        elif entry["question"]["type"] == m.CHOICE:
            words = set(entry["question"]["criteria"]) | {"none"}
        else:
            words = {"yes", "no", "none"}
        for c in m.read_corpus(name):
            if c.get("reading") != name:
                bad.append(f"{c.get('id')}: reading `{c.get('reading')}`")
            got = set(c.get("state") or {})
            if got != want:
                bad.append(f"{c.get('id')}: state {sorted(got)}, entry names "
                           f"{sorted(want)}")
            truth = c.get("truth")
            if isinstance(truth, str) and truth not in words:
                bad.append(f"{c.get('id')}: truth `{truth}` is no word of "
                           f"{sorted(words)}")
    return not bad, bad


def every_case_is_well_formed(m):
    """Every case of every corpus file, registered or not: a case with no id,
    no reading or no label source is one no reader can count."""
    bad = []
    for path in sorted((HERE / "jev" / "corpus").glob("*.jsonl")):
        if path.stem.endswith(".changes"):
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            c = json.loads(line)
            for field in ("id", "reading", "state", "truth", "label", "source",
                          "role"):
                if field not in c:
                    bad.append(f"{path.name}:{i + 1} no `{field}`")
            if (c.get("label") or {}).get("from") is None:
                bad.append(f"{path.name}:{i + 1} no label source")
            if c.get("role") not in ("case", "flip", "no-match"):
                bad.append(f"{path.name}:{i + 1} role `{c.get('role')}`")
            # A NUMBER WITHOUT ITS REPOSITORY NAMES NOTHING, in a case as in a
            # log row: a member repository's numbers collide with this
            # tracker's.
            src = c.get("source") or {}
            if any(k in src and src[k] is not None
                   for k in ("issue", "pull_request", "comment_id")) \
                    and not src.get("repo"):
                bad.append(f"{path.name}:{i + 1} a number with no `repo`")
    return not bad, bad[:20]


def a_tier_above_shadow_holds_its_evidence_row(m):
    """DECISION 5713111488's bar, enforced rather than remembered: a reading
    that PRINTS or ACTS has at least 8 real cases with a known truth, a flip, a
    no-match, two wordings, three runs, and beats a token-overlap baseline. At
    `shadow` it costs a reader nothing, so it is collecting cases and the row
    does not apply yet."""
    short = {name: m.evidence_row(e, m.read_corpus(name))
             for name, e in entries(m).items() if e["tier"] != m.SHADOW}
    return not any(short.values()), {k: v for k, v in short.items() if v}


def the_evidence_row_names_what_is_short(m):
    """The bar counted against a corpus that meets none of it: each part is
    named on its own, because "short of the evidence row" with no reason sends
    whoever reads it looking at all six."""
    entry = entries(m)["verb-first"]
    thin = [{"id": "one", "reading": "verb-first", "role": "case",
             "truth": "yes", "state": {}, "label": {"from": "owner"},
             "source": {"kind": "fixture"}, "seen": []}]
    short = " | ".join(m.evidence_row(entry, thin))
    for want in ("under 8", "no flip case", "no no-match case",
                 "wording(s) seen, under 2", "run(s) recorded, under 3"):
        if want not in short:
            return False, (want, short)
    return True, short


CASES["the evidence row names each part that is short"] = the_evidence_row_names_what_is_short
CASES["a reading above shadow holds its evidence row"] = a_tier_above_shadow_holds_its_evidence_row
CASES["every case of a registered reading fits its entry"] = every_case_fits_its_entry
CASES["every case of every corpus file is well formed"] = every_case_is_well_formed


def a_bad_entry_never_loads(m):
    """The bounds are read AT LOAD, so a registry file carrying a bad entry
    refuses on the way in rather than on the one call that would have acted."""
    path = ROOT / "bad-readings.json"
    entry = acting(verb="label", label="standing", what="", undo="",
                   act_over=0.9, ask_over=0.7)
    path.write_text(json.dumps({"bad": entry}))
    try:
        m.load_registry(path)
    except ValueError as e:
        return "bound a" in str(e), str(e)
    return False, "loaded a registry whose act moves `standing`"


# ------------------------------------------------------- the store of answers
# RAW PROBABILITIES REPLAYED, so a moved cut asks nothing. Every case here
# counts the requests the stub SAW: a store that is read is a call not sent.


def a_second_identical_ask_sends_nothing(m):
    """The whole point. Same state, same wording, same pinned model: the second
    ask replays and the endpoint sees one request, not two."""
    first = read(m)                      # clears the store, then calls
    serving()                            # resets SEEN["count"] to 0
    second = m.ask("a suite", "a label", STATE, BOTH, env=env(), timeout=5)
    return (SEEN["count"] == 0 and second.cached is True
            and not first.cached
            and second.answers["verb_first"].raw
            == first.answers["verb_first"].raw), (SEEN["count"], second.cached)


def a_hit_is_logged_as_a_hit(m):
    """It is visible, and it is not a call: `report`'s ratio is over what was
    sent, so a hit that logged as an ordinary row would flatter the ratio."""
    read(m)
    LOG.write_text("")
    m.ask("a suite", "a label", STATE, BOTH, env=env(), timeout=5)
    row = json.loads(LOG.read_text().splitlines()[-1])
    return row.get("cached") is True and row.get("state_hash"), row


def moved(m, **kw):
    """(requests the stub saw on the second ask) after one warm ask, with `kw`
    changing one of the three things the key is made of."""
    read(m)
    serving()
    state = kw.get("state", STATE)
    questions = kw.get("questions", BOTH)
    if kw.get("model"):
        m.MODEL = kw["model"]
    try:
        r = m.ask("a suite", "a label", state, questions, env=env(), timeout=5)
    finally:
        m.MODEL = MODEL
    return SEEN["count"], r


def a_changed_state_misses(m):
    count, _r = moved(m, state={"title": "Retire the queue", "body": "- b"})
    return count == 1, count


def a_changed_wording_misses(m):
    reworded = {"verb_first": dict(NOUL_Q, instructions="Is it an order?"),
                "work_kind": CHOICE_Q}
    count, _r = moved(m, questions=reworded)
    return count == 1, count


def a_changed_model_misses(m):
    """The pinned model is in the key, so a version bump replays nothing: a
    band measured under one version says nothing about the next."""
    count, _r = moved(m, model="jev-1.14.0")
    return count == 1, count


def a_moved_cut_replays(m):
    """THE REASON THE RAW PROBABILITIES ARE WHAT IS STORED. The cuts never
    reach the model, so moving one must not move the key: the stored answer is
    replayed and `branch` runs over it again, here into the other word."""
    read(m, noul=0.94)
    serving()
    moved_cut = {"verb_first": dict(NOUL_Q, yes_over=0.99, no_under=0.96),
                 "work_kind": CHOICE_Q}
    r = m.ask("a suite", "a label", STATE, moved_cut, env=env(), timeout=5)
    return (SEEN["count"] == 0 and r.answers["verb_first"].word == "no"),\
        (SEEN["count"], r.answers["verb_first"].word)


def the_noise_switch_sends_every_time(m):
    """`cache=False` is what a run measuring noise sets, and it is explicit:
    a band is what the same state answers ACROSS runs, so a replayed answer
    would report a drift of zero."""
    read(m)
    serving()
    m.ask("a suite", "a label", STATE, BOTH, env=env(), timeout=5, cache=False)
    m.ask("a suite", "a label", STATE, BOTH, env=env(), timeout=5, cache=False)
    # AND THROUGH `judge`, which is what a reader calls: a switch the group
    # caller swallowed would leave every repeat run replaying.
    for _ in range(2):
        m.judge("issue-shape", STATE, read="a label", env=env(), timeout=5,
                log=False, cache=False)
    return SEEN["count"] == 4, SEEN["count"]


def an_answer_from_another_model_is_never_stored(m):
    """It is `unknown` here and would be `unknown` on every replay, so storing
    it would cache a failure."""
    read(m, model="jev-latest")
    serving()
    r = m.ask("a suite", "a label", STATE, BOTH, env=env(), timeout=5)
    return SEEN["count"] == 1 and not r.cached, (SEEN["count"], r.cached)


def a_store_that_will_not_read_costs_a_call(m):
    """NEVER RAISES: a store that is gone, unreadable or corrupt is a call to
    make, not a reading to lose."""
    read(m)
    path = m.cache_path(m.cache_key(STATE, BOTH), env=env())
    path.write_text("{not json")
    serving()
    r = m.ask("a suite", "a label", STATE, BOTH, env=env(), timeout=5)
    return (SEEN["count"] == 1
            and r.answers["verb_first"].word == "yes"), (SEEN["count"], r)


def the_ratio_counts_sent_calls_over_distinct_states(m):
    """`report`'s calls-a-state, over a made log: three calls on two states,
    one of them replayed, reads 2 sent over 2 states with 1 replayed."""
    LOG.write_text("".join(json.dumps(r) + "\n" for r in [
        {"reading": "verb-first", "state_hash": "aaa", "cached": False},
        {"reading": "verb-first", "state_hash": "bbb", "cached": False},
        {"reading": "verb-first", "state_hash": "aaa", "cached": True},
        {"reading": "verb-first", "state_hash": "ccc", "settled": "no"},
        {"reading": "verb-first", "skipped": "the kind read failed"},
        {"reader": "check-finding-sort.py", "state_hash": "ddd"},
        {"reader": "an old row", "read": "before the hash was logged"},
    ]))
    lines = m.spend_lines(env=env())
    head, verb = lines[0], [ln for ln in lines if "verb-first" in ln]
    return (len(verb) == 1 and "2 sent over 2 state(s)" in verb[0]
            and "1.0 a state" in verb[0] and "1 replayed" in verb[0]
            and "1 with no state to group by" in head
            and any("(reader) check-finding-sort.py" in ln for ln in lines)),\
        lines


CASES["a second identical ask replays and sends nothing"] = a_second_identical_ask_sends_nothing
CASES["a replayed answer is logged as a hit, not as a call"] = a_hit_is_logged_as_a_hit
CASES["a changed state misses the store"] = a_changed_state_misses
CASES["a changed wording misses the store"] = a_changed_wording_misses
CASES["a changed model misses the store"] = a_changed_model_misses
CASES["a moved cut replays the stored answer and asks nothing"] = a_moved_cut_replays
CASES["the noise switch sends every time"] = the_noise_switch_sends_every_time
CASES["an answer from another model is never stored"] = an_answer_from_another_model_is_never_stored
CASES["a store that will not read costs a call, not an answer"] = a_store_that_will_not_read_costs_a_call
CASES["report counts calls sent over distinct states"] = the_ratio_counts_sent_calls_over_distinct_states

# ------------------------------------------- the shared log, and what may join
# A STUB'S ANSWER IS NOT EVIDENCE. `<base>/runtime/jev.log` is where the corpus
# grows from, so a run that named its own endpoint never writes there, and the
# join refuses any row that does not say the REAL endpoint answered it.


def a_base(name):
    """A made base checkout: `base_root` is the parent of the git COMMON dir,
    so a directory with a `.git` in it is one. The shared log's own rule is
    then exercised at `<this>/runtime/jev.log` -- the same code path, the same
    `log_path` branch -- without this machine's own log being touched."""
    root = ROOT / name
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "runtime").mkdir(exist_ok=True)
    log = root / "runtime" / "jev.log"
    log.write_text('{"a": 1}\n{"a": 2}\n')
    return root, log


def lines(path):
    return len(path.read_text().splitlines())


def a_stub_never_writes_the_shared_log(m):
    """COUNTED BEFORE AND AFTER, never read by presence: the file is there
    either way, so only the count can say whether a line was added.

    The control is the same call with no `CAMPAIGN_JEV_URL`, which takes the
    shared branch and DOES write -- so what the case measures is the endpoint's
    rule and not a log that was unwritable all along."""
    root, log = a_base("shared-log")
    before = lines(log)
    stub = {"HOME": str(HOME), "CAMPAIGN_JEV_URL": URL,
            "TYPESAFE_API_KEY": "stub-key"}
    serving()
    r = m.ask("a suite", "a label", STATE, BOTH, env=stub, cwd=root, timeout=5)
    stubbed = lines(log)
    # THE CONTROL. No URL named, no key and an empty HOME: `ask` answers
    # `unknown` before it opens a socket, and the row still lands in the shared
    # log, which is the branch the case above must not have taken.
    m.ask("a suite", "a label", STATE, BOTH,
          env={"HOME": str(HOME)}, cwd=root, timeout=5)
    return (stubbed == before and lines(log) == before + 1
            and "CAMPAIGN_JEV_URL" in r.logged),\
        (before, stubbed, lines(log), r.logged)


def a_row_of_no_real_endpoint_is_refused_by_the_join(m):
    """NAMED, not dropped: the output says which row and why. Nothing can ever
    label it, so it is not waiting either."""
    real = log_row("rrrr", "verb-first", "Cache the weather feed", 900)
    stubbed = log_row("ssss", "verb-first", "Cache the weather feed", 900,
                      endpoint="stub")
    legacy = log_row("llll", "verb-first", "Cache the weather feed", 900)
    legacy.pop("endpoint")
    cases, _lines = joined(m, [real, stubbed, legacy])
    ids = sorted(c["id"] for c in cases["verb-first"])
    kept, stray, unreal = m.joinable([real, stubbed, legacy],
                                     m.load_registry())
    return (ids == ["verb-first-rrrr"] and not stray
            and sorted(r["call"] for r in unreal) == ["llll", "ssss"]
            and [r["call"] for r in kept] == ["rrrr"]), (ids, unreal)


def a_row_says_which_endpoint_answered_it(m):
    """One plain word, on every row this module writes: `real` or `stub`. It is
    what the join reads, so a row that did not carry it could be a suite's
    answer imported as the tracker's own history."""
    read(m)
    stubbed = json.loads(LOG.read_text().splitlines()[-1])
    root, log = a_base("endpoint-word")
    m.ask("a suite", "a label", STATE, BOTH, env={"HOME": str(HOME)}, cwd=root,
          timeout=5)
    real = json.loads(log.read_text().splitlines()[-1])
    return (stubbed.get("endpoint") == "stub"
            and real.get("endpoint") == "real"), (stubbed.get("endpoint"),
                                                  real.get("endpoint"))


CASES["a row says which endpoint answered it"] = a_row_says_which_endpoint_answered_it
CASES["a stubbed call never writes the shared log"] = a_stub_never_writes_the_shared_log
CASES["a row no real endpoint answered is refused by the join, and named"] = a_row_of_no_real_endpoint_is_refused_by_the_join

CASES["a registry file carrying a bad act never loads"] = a_bad_entry_never_loads
CASES["an act never moves a label a person alone moves"] = act_never_moves_a_person_label
CASES["an act is never a claim, release, merge, close, launch or retire"] = act_is_never_an_event_with_an_actor
CASES["an entry hands this module no command to run"] = act_carries_no_command_for_this_module
CASES["this module carries out no act of its own"] = this_module_carries_out_no_act
CASES["no reading's act opens a DECISION, at any tier"] = act_never_opens_a_decision
CASES["a BLOCKED reading at act may only route"] = a_blocked_reading_may_only_route
CASES["every registry entry carries what a reader branches on"] = registry_shape
CASES["a reading with no thresholds is at shadow"] = thresholds_or_shadow
CASES["a reading at act declares what it does and how it is undone"] = act_declares_its_undo
CASES["a declared wording is the hash of its question"] = wording_is_computed
CASES["no Jev question is written outside the registry"] = no_question_outside_the_registry

MUTATIONS = [
    # --- the shared log, and what may join ---
    ("a stub allowed to write the shared log",
     "    if URL_ENV in env:", "    if False:",
     "a stubbed call never writes the shared log"),
    ("the endpoint never written on a row",
     "    return STUB if URL_ENV in (os.environ if env is None else env) else REAL",
     "    return REAL", "a row says which endpoint answered it"),
    ("the join taking a row of any endpoint",
     '        if row.get("endpoint") != REAL:', "        if False:",
     "a row no real endpoint answered is refused by the join, and named"),
    # --- one thread, one call, per finding ---
    ("the per-item reading asked once for the whole state",
     '        if not per:\n            if name not in settled:',
     '        if True:\n            if name not in settled:',
     "every question over one thread goes in one call, one per finding"),
    ("the item's name never written into the question",
     '        spec["instructions"] = spec["instructions"].replace(ITEM_MARK, str(item))',
     "        pass",
     "every question over one thread goes in one call, one per finding"),
    ("the marker never required",
     '        if ITEM_MARK not in entry["question"]["instructions"]:',
     "        if False:", "a per-item question must name its item"),
    ("a cleared finding sent all the same",
     "            if item not in cleared:", "            if True:",
     "a finding the prefilter cleared is never sent"),
    ("a computed flag handed the wrong answers",
     '"flag": flag(name, raw) if callable(flag) else flag}',
     '"flag": flag(name, {}) if callable(flag) else flag}',
     "a flag the reader computes from the answers reaches the log row"),
    # --- the thread join ---
    ("the later REVIEW never read",
     '    body = "\\n".join(later)',
     '    body = ""',
     "the thread join reads a later REVIEW that raised the finding again"),
    ("an open thread read as agreement",
     '        if str(thread.get("state", "")).upper() != "MERGED":',
     "        if False:",
     "the thread join waits for the merge where nothing was re-raised"),
    # --- the store of answers ---
    ("the store never read",
     "    stored = cache_read(cache_key(state, questions), env, cwd) if cache else None",
     "    stored = None",
     "a second identical ask replays and sends nothing"),
    ("the store never written",
     "        cache_write(cache_key(state, questions), out, env, cwd)",
     "        pass", "a second identical ask replays and sends nothing"),
    ("the state left out of the key",
     '    return f"{digest(state)}-{digest(sent)}-{MODEL}"',
     '    return f"-{digest(sent)}-{MODEL}"',
     "a changed state misses the store"),
    ("the wording left out of the key",
     '    sent = request_body(state, questions)["questions"]',
     '    sent = "one wording for all"',
     "a changed wording misses the store"),
    ("the pinned model left out of the key",
     '    return f"{digest(state)}-{digest(sent)}-{MODEL}"',
     '    return f"{digest(state)}-{digest(sent)}"',
     "a changed model misses the store"),
    ("the noise switch ignored in `ask`",
     "if cache else None", "if True else None",
     "the noise switch sends every time"),
    ("the noise switch swallowed by `judge`",
     "timeout=timeout, log=False, cache=cache)",
     "timeout=timeout, log=False, cache=True)",
     "the noise switch sends every time"),
    ("a hit counted as a call",
     '        if row.get("cached"):\n'
     '            hits[who] = hits.get(who, 0) + 1\n'
     '            continue',
     "        if False:\n            pass",
     "report counts calls sent over distinct states"),
    ("the confidence floor dropped", 'if confidence < spec["floor"]:', "if False:",
     "a choice under the floor is unknown"),
    ("the option's probability unread",
     'value = (probabilities.get(spec["option"])',
     'value = (probabilities.get("supports")',
     "a choice cut on one option reads that option's probability"),
    ("the no-match option ignored", 'if option == spec["no_match"]:', "if False:",
     "the no-match option is unknown"),
    ("the noul band closed", 'if value <= spec["no_under"]:', "if True:",
     "a noul between the two edges is uncertain"),
    # THE BAND'S MIDDLE IS ITS OWN WORD. Answering `unknown` there is what the
    # two edges were added to stop: a reader cannot tell a reading that did not
    # happen from one that happened and reached no word.
    ("the band's middle answered `unknown` again",
     '        return UNCERTAIN, (f"{what} {value:.2f} sits in the band between "',
     '        return UNKNOWN, (f"{what} {value:.2f} sits in the band between "',
     "a noul between the two edges is uncertain"),
    ("a choice's upper edge dropped",
     '    if confidence < spec.get("certain_over", 0.0):', "    if False:",
     "a choice between the two edges is uncertain"),
    ("a reading with no cut judged all the same",
     "    if not any(k in spec for k in VALUE_EDGES + CHOICE_EDGES):",
     "    if False:",
     "a reading with no cut records and judges nothing"),
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
    ("a noul's criteria dropped from the request",
     'if k in ("type", "instructions", "criteria")}',
     'if k in ("type", "instructions")}',
     "a noul's criteria reaches the model whole"),
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
    ("the unusable URL reported as an endpoint that did not answer",
     "    except ValueError as e:\n        return None, (f\"`{URL_ENV}` names no usable endpoint",
     "    except ZeroDivisionError as e:\n        return None, (f\"`{URL_ENV}` names no usable endpoint",
     "a URL with no scheme is unknown and blames the variable"),
    ("the ~/.env decode error let out", "    except (OSError, UnicodeDecodeError) as e:",
     "    except OSError as e:", "a ~/.env that is not text is unknown, not a traceback"),
    ("ask's boundary removed",
     "    except Exception as e:  # noqa: BLE001 -- the boundary; the promise is here",
     "    except ZeroDivisionError as e:", "a call that raises where nothing should is unknown"),
    ("a set-but-empty endpoint read as unset", "    if not url:",
     "    if False:", "an endpoint set to nothing never reaches the network"),
    # THE FOUR BOUNDS ON AN `act`, each dropped in turn (DECISION 5714078253).
    ("the eight cases never counted", "    if len(real) < 8:", "    if False:",
     "the evidence row names each part that is short"),
    ("a flip no longer required",
     '    if not any(c.get("role") == "flip" for c in cases):', "    if False:",
     "the evidence row names each part that is short"),
    ("a no-match no longer required",
     '    if not any(c.get("role") == "no-match" for c in cases):',
     "    if False:", "the evidence row names each part that is short"),
    ("one wording enough", "    if len(wordings) < 2:", "    if False:",
     "the evidence row names each part that is short"),
    ("one run enough", "    if len(runs) < 3:", "    if False:",
     "the evidence row names each part that is short"),
    ("a live run replaces the history", '        c.setdefault("seen", []).append(',
     '        c["seen"] = []\n        c.setdefault("seen", []).append(',
     "report --live appends a run and replaces none"),
    # THE DEFECT THE REVIEW AT a73fc57 FOUND, from both ends.
    ("the join writes no band",
     '        case["band"] = band_of(entry, case)[0]', "        pass",
     "a case the join writes is held to a band, and drift reads it"),
    ("a choice's band never derived",
     '    if truth in options and truth != cuts.get("no_match"):',
     "    if False:",
     "a case the join writes is held to a band, and drift reads it"),
    ("an unplaced case skipped in silence",
     '            unplaced.append(f"{c[\'id\']} ({why})")', "            pass",
     "a case held to no band is listed, never skipped"),
    ("an act's four fields never required", "        for field in ACT_FIELDS:",
     "        for field in ():",
     "a reading at act declares what it does and how it is undone"),
    ("bound a dropped", '        if verb == "label" and (label in PERSON_LABELS',
     "        if False and (label in PERSON_LABELS",
     "an act never moves a label a person alone moves"),
    ("bound b dropped", "        if verb in NEVER_ACTED:", "        if False:",
     "an act is never a claim, release, merge, close, launch or retire"),
    ("bound c dropped", "        for field in NEVER_IN_AN_ENTRY:",
     "        for field in ():",
     "an entry hands this module no command to run"),
    ("bound d dropped",
     '        if act and str(act.get("opens", "")).upper() == DECISION_KIND:',
     "        if act and False:", "no reading's act opens a DECISION, at any tier"),
    ("the BLOCKED ceiling dropped",
     '        if entry.get("subject") == BLOCKED_SUBJECT and verb != "label":',
     "        if False:", "a BLOCKED reading at act may only route"),
    ("the bounds never read at load",
     "    return check_act_bounds(json.loads(path.read_text(encoding=\"utf-8\")))",
     '    return json.loads(path.read_text(encoding="utf-8"))',
     "a registry file carrying a bad act never loads"),
    ("a skip not logged",
     '"endpoint": endpoint_word(env), "skipped": why}\n    return log_call(',
     '"endpoint": endpoint_word(env), "skipped": why}\n    return "logged to" or log_call(',
     "a skipped reading is logged as one JSON line naming why"),
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

    A RUN INSIDE THE BAND CHANGES NOTHING, and only an excursion widens it, to
    where it went plus the pad. Padding the observation and unioning that was
    already better than padding the union -- which grew the band by `pad` on
    every record whether or not anything moved -- but it still crept whenever a
    run came within `pad` of an edge from the INSIDE, which is the band working
    rather than drifting. So the excursion is tested first and the pad applied
    only to it."""
    if seen is None:
        return was
    if not was:
        return [round(max(0.0, seen[0] - pad), 3),
                round(min(1.0, seen[1] + pad), 3)]
    lo, hi = was
    if seen[0] < lo:
        lo = round(max(0.0, seen[0] - pad), 3)
    if seen[1] > hi:
        hi = round(min(1.0, seen[1] + pad), 3)
    return [lo, hi]


def inside(value, declared):
    return declared is not None and declared[0] <= value <= declared[1]


# Which band a case is held to is `campaign-jev.band_of`'s, asked and never
# restated: this suite kept its own reading of it, and the two disagreed exactly
# where the join wrote a case with no `band`.


# The number the band is over is `campaign-jev.band_value`'s, asked and never
# restated: a suite that kept its own copy would measure a band the module does
# not read.


def live(record, wording_hash=None):
    """THE CORPUS AGAINST THE REAL ENDPOINT, asked with the REGISTRY'S OWN
    question -- never a copy built here, which drifted within one round the
    last time this suite kept one.

    THE ENTRY DECLARES THE BANDS AND THIS ASSERTS THEM. Every case must land
    inside its band, and each cut must sit STRICTLY between the two declared
    bands it separates. That is what makes a threshold measured rather than
    chosen. `--record` widens the declared bands to hold this run, writes the
    wording hash and the date into the entry, and appends one `seen` row per
    case -- appends, because a band is read from the run history and a run that
    overwrote the one before it would erase the evidence of drift.

    `--wording <hash>` asks a RETIRED wording from `scripts/jev/wordings.json`
    instead, which is how a criteria change gets its before-and-after numbers
    and how a reading comes to have been seen under two wordings."""
    jev = load(SOURCE)
    reg = jev.load_registry()
    at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    model = ""
    for name, entry in sorted(reg.items()):
        # A READING WHOSE QUESTION IS COMPOSED PER ITEM IS SKIPPED, AND SAYS
        # SO. `question.per` means production builds one question per claim or
        # per condition out of this entry -- `check-cited-claims.py` and
        # `check-research-bar.py` do -- so asking the entry's bare
        # `instructions` here would measure a call nobody makes and declare a
        # band for it. Measuring those is their own reader's, with their own
        # composer (the REVIEW at a73fc57, note 7).
        if (entry.get("question") or {}).get("per"):
            print(f"  {name}: skipped, its question is composed per "
                  f"`{entry['question']['per']}` by its own reader; a band "
                  f"measured on the bare instructions would be a call nobody "
                  f"makes")
            continue
        cases = jev.read_corpus(name)
        # A READING WITH NO CASES YET IS SKIPPED AT `shadow` AND SAYS SO. A
        # reading enters the registry to collect cases until a record labels
        # them (DECISION 5713929966), so it has no cut and no band; anywhere
        # else, or with a band declared, having no cases is the failure it
        # always was.
        if not cases and entry["tier"] == jev.SHADOW \
                and not (entry.get("thresholds") or {}) \
                and not (entry.get("bands") or {}).get("declared"):
            print(f"  {name}: skipped, no cases yet -- it enters at "
                  f"`{jev.SHADOW}` with no cut, to collect them")
            continue
        check(f"live: {name} has cases", bool(cases), len(cases))
        spec = jev.question_of(entry)
        wording = jev.wording(entry)
        if wording_hash:
            retired = json.loads(WORDINGS.read_text())["wordings"]
            if wording_hash not in retired:
                check(f"live: wording {wording_hash} is on file", False,
                      sorted(retired))
                continue
            spec = dict(retired[wording_hash]["question"])
            spec.update(entry.get("thresholds") or {})
            wording = wording_hash
            if retired[wording_hash]["reading"] != name:
                continue
        q = {name: spec}
        declared = (entry.get("bands") or {}).get("declared") or {}
        seen, outside, wrong, nomatch, flips = {}, [], [], [], []
        for c in cases:
            # THE STORE IS OFF HERE, as it is in `relive`: a band is what the
            # same state answers across runs, and a replayed answer would
            # report a drift of zero (DECISION 5716060001).
            r = jev.ask("campaign-jev-test.py --live", c["id"],
                        c.get("state") or {}, q, log=False, cache=False)
            model = r.model or model
            a = r.answers[name]
            value = jev.band_value(entry, a.raw)
            print(f"  {c['id']:<28} {a.word:<12} "
                  f"{'--' if value is None else format(value, '.2f')}  "
                  f"truth {c['truth']}")
            if record:
                c.setdefault("seen", []).append(
                    {"model": r.model, "wording": wording, "at": at,
                     "word": a.word, "raw": a.raw})
            key = jev.band_of(entry, c)[0]
            if c.get("role") == "no-match":
                nomatch.append((c["id"], a.word, value))
                continue
            if c.get("role") == "flip":
                flips.append((c["id"], a.word, c["truth"]))
            if value is None:
                check(f"live {name} {c['id']} answered", False, (a.word, a.why))
                continue
            if key:
                seen.setdefault(key, []).append(value)
                if not record and not inside(value, declared.get(key)):
                    outside.append((c["id"], value, key, declared.get(key)))
            if entry["question"]["type"] == "choice" and key == "confident" \
                    and a.raw.get("choice") != c["truth"]:
                wrong.append((c["id"], a.raw.get("choice"), c["truth"]))
        if record:
            jev.write_corpus(name, cases)
        print(f"  {name} seen: "
              + "  ".join(f"{k} {band(v)}" for k, v in sorted(seen.items()))
              + f"  declared {declared}")
        check(f"live: every {name} case landed in its declared band",
              not outside, outside)
        check(f"live: every confident {name} answer names the truth",
              not wrong, wrong)
        # THE FLIP IS THE CASE THAT SAYS THE READING READS THE STATE, not the
        # shape of the corpus: the judged thing was changed and the answer has
        # to move with it.
        check(f"live: every {name} flip case answers its flipped truth",
              bool(flips) and all(w == t for _i, w, t in flips), flips)
        # THE TWO TYPES HAVE DIFFERENT NO-MATCH MACHINERY, and pretending
        # otherwise would be the assertion that reads like a pass. A `choice`
        # carries a no-match OPTION, so a state fitting none of the words must
        # come back `unknown` BY that option. A `noul` carries no such thing:
        # asked whether a title opens with an imperative verb, a state with no
        # title at all comes back a confident `no`, measured here. So its
        # no-match case is RECORDED with where it landed rather than asserted
        # into a branch the question has no way of taking -- and `report`
        # counts it as a disagreement, which is what it is.
        if entry["question"]["type"] == "choice":
            check(f"live: the {name} case fitting no option is unknown BY the "
                  f"no-match option",
                  bool(nomatch) and all(w == "unknown" for _i, w, _v in nomatch),
                  nomatch)
        else:
            check(f"live: the {name} no-match case is answered and recorded, "
                  f"since a noul has no no-match option",
                  bool(nomatch) and all(v is not None for _i, _w, v in nomatch),
                  nomatch)
        cuts = entry.get("thresholds") or {}
        if not record and cuts and declared:
            if entry["question"]["type"] == "noul":
                check(f"live: {name}'s no cut sits above the whole declared "
                      f"`no` band",
                      bool(declared.get("no"))
                      and declared["no"][1] < cuts["no_under"],
                      (declared.get("no"), cuts.get("no_under")))
                check(f"live: {name}'s yes cut sits below the whole declared "
                      f"`yes` band",
                      bool(declared.get("yes"))
                      and cuts["yes_over"] < declared["yes"][0],
                      (cuts.get("yes_over"), declared.get("yes")))
                check(f"live: {name}'s two cuts do not cross",
                      cuts["no_under"] <= cuts["yes_over"],
                      (cuts.get("no_under"), cuts.get("yes_over")))
            else:
                # THE SAME RULE, WITH THE UPPER EDGE NAMED. A `choice` cut on a
                # lone `floor` had one number doing both jobs, and it sat inside
                # the measured `confident` band; `certain_over` is that band's
                # own lower edge and what falls between the two is `uncertain`.
                top = cuts.get("certain_over", cuts.get("floor"))
                check(f"live: {name}'s lower edge sits above the whole declared "
                      f"`unsure` band",
                      bool(declared.get("unsure"))
                      and declared["unsure"][1] < cuts["floor"],
                      (declared.get("unsure"), cuts.get("floor")))
                check(f"live: {name}'s upper edge sits below the whole declared "
                      f"`confident` band",
                      bool(declared.get("confident"))
                      and top < declared["confident"][0],
                      (top, declared.get("confident")))
                check(f"live: {name}'s two edges do not cross",
                      cuts["floor"] <= top, (cuts.get("floor"), top))
        if record and not wording_hash:
            # THE BAND IS THE WHOLE RECORDED HISTORY UNDER THIS WORDING, not
            # this run alone: three runs are what a band is made of, and a
            # `--record` that read only the run it just made would declare a
            # band narrower than the evidence and then widen it on the next
            # run, which reads exactly like drift. `seen` is appended above, so
            # this run is already in it.
            history = {}
            for c in cases:
                key = jev.band_of(entry, c)[0]
                for s in c.get("seen") or []:
                    value = jev.band_value(entry, s.get("raw"))
                    if (key and value is not None
                            and s.get("wording") == wording
                            and s.get("model") == jev.MODEL):
                        history.setdefault(key, []).append(value)
            reg[name]["bands"]["declared"] = {
                k: widened(declared.get(k), band(v)) for k, v in history.items()}
            reg[name]["bands"]["measured"] = datetime.date.today().isoformat()
            reg[name]["bands"]["wording"] = wording
            reg[name]["bands"]["model"] = model or reg[name]["bands"]["model"]
    check("live: the pinned model is the one that answered",
          model == jev.MODEL, model)
    if record and not wording_hash:
        REGISTRY.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
        print(f"recorded into {REGISTRY} and the corpus")


def main(argv):
    if "--live" in argv:
        at = argv.index("--wording") if "--wording" in argv else None
        live("--record" in argv, argv[at + 1] if at is not None else None)
        return harness.report()
    pure_branches(load(SOURCE))
    harness.mutate(SOURCE, load, CASES, MUTATIONS)
    return harness.report()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
