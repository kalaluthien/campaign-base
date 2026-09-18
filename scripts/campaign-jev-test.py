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
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tokenize
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
    # TWO PARENTS FOR THE FILING JOIN: one whose slug the call offered as an
    # option, and one whose slug it did not.
    ("kalaluthien/campaign-base", 903): {
        "title": "Mechanize the written rules", "state": "OPEN",
        "labels": [{"name": "campaign"}, {"name": "campaign:rule-check"}]},
    ("kalaluthien/campaign-base", 904): {
        "title": "Define an SDLC on Alloy specs", "state": "OPEN",
        "labels": [{"name": "campaign"}, {"name": "campaign:sdlc-alloy"}]},
}


# ONE PULL REQUEST THREAD PER SUBJECT, as `ISSUES` is one issue per subject:
# the thread's join asks what came AFTER the REPORT it judged.
THREADS = {
    ("kalaluthien/campaign-base", 700): {
        "state": "OPEN", "comments": [
            {"where": "comment", "at": "2026-09-17T01:00:00Z",
             "body": "REVIEW r-1: F1 the ceiling is stated twice, and the "
                     "second copy is the one that drifts"},
            {"where": "comment", "at": "2026-09-17T02:00:00Z",
             "body": "NOTE w-1: pushed"}]},
    ("kalaluthien/campaign-base", 701): {
        "state": "MERGED", "comments": [
            {"where": "comment", "at": "2026-09-17T02:00:00Z",
             "body": "NOTE w-1: merged"}]},
    # THE LATER REVIEW ON THE REVIEW CHANNEL, which `fetch_thread` used to miss
    # entirely: it read `issues/<n>/comments` alone, so this thread labelled
    # every finding `disposed` at the merge.
    ("kalaluthien/campaign-base", 702): {
        "state": "MERGED", "comments": [
            {"where": "review", "at": "2026-09-17T01:00:00Z",
             "body": "REVIEW r-1: F1 the ceiling is stated twice, and the "
                     "second copy is the one that drifts"}]},
    # THE FIX ROUND `report-next-round` READS: a later REVIEW and a REPORT
    # answering it, both after the row's own `at`.
    ("kalaluthien/campaign-base", 703): {
        "state": "MERGED", "comments": [
            {"where": "review", "at": "2026-09-17T03:00:00Z",
             "body": "REVIEW r-2: one more finding"},
            {"where": "comment", "at": "2026-09-17T04:00:00Z",
             "body": "REPORT w-1: fix round 2 at abc1234"}]},
    # AND THE ROUND STILL OPEN: a later REVIEW nobody has answered.
    ("kalaluthien/campaign-base", 704): {
        "state": "OPEN", "comments": [
            {"where": "comment", "at": "2026-09-17T03:00:00Z",
             "body": "REVIEW r-2: one more finding"}]},
}
# MERGED, AND NOTHING LATER ON THE THREAD, so only the reopen half can speak.
# Four of them, one per way a reopen is or is not named.
for _n in (705, 706, 707, 708):
    THREADS[("kalaluthien/campaign-base", _n)] = {
        "state": "MERGED", "comments": [
            {"where": "comment", "at": "2026-09-17T02:00:00Z",
             "body": "NOTE w-1: merged"}]}

# WHAT THE LAZY SECOND FETCH ANSWERS, keyed as `fetch_reopen` is called. A
# REOPEN IS AN EVENT AND NOT A STATE: 701's sub-issue was reopened after the
# merge and CLOSED AGAIN, which is the ordinary shape here, and a reader of the
# issue's present state called that "never reopened" (pr#490 REVIEW F1).
REOPENS = {
    ("kalaluthien/campaign-base", 701): {
        "merged_at": "2026-09-17T05:00:00Z",
        "issues": [{"number": 910, "repo": "kalaluthien/campaign-base",
                    "state": "CLOSED",
                    "reopened": ["2026-09-17T05:30:00Z"], "comments": [
                        {"at": "2026-09-17T06:00:00Z",
                         "body": "NOTE w-2: the guard pr#701 said was refusing "
                                 "lets the third spelling through"}]}]},
    ("kalaluthien/campaign-base", 702): {"merged_at": "2026-09-17T05:00:00Z",
                                         "issues": []},
    ("kalaluthien/campaign-base", 703): {
        "merged_at": "2026-09-17T05:00:00Z",
        "issues": [{"number": 911, "repo": "kalaluthien/campaign-base",
                    "state": "CLOSED", "reopened": [], "comments": []}]},
    # THE PULL REQUEST NAMED BY ITS URL and by nothing else.
    ("kalaluthien/campaign-base", 705): {
        "merged_at": "2026-09-17T05:00:00Z",
        "issues": [{"number": 912, "repo": "kalaluthien/campaign-base",
                    "state": "OPEN",
                    "reopened": ["2026-09-17T05:30:00Z"], "comments": [
                        {"at": "2026-09-17T06:00:00Z",
                         "body": "NOTE w-2: reopening, the change in https://"
                                 "github.com/kalaluthien/campaign-base/pull/705"
                                 " did not hold"}]}]},
    # THE REPORT NAMED BY ITS COMMENT URL, which carries the id.
    ("kalaluthien/campaign-base", 706): {
        "merged_at": "2026-09-17T05:00:00Z",
        "issues": [{"number": 913, "repo": "kalaluthien/campaign-base",
                    "state": "OPEN",
                    "reopened": ["2026-09-17T05:30:00Z"], "comments": [
                        {"at": "2026-09-17T06:00:00Z",
                         "body": "NOTE w-2: reopening, the REPORT at https://"
                                 "github.com/kalaluthien/campaign-base/pull/999"
                                 "#issuecomment-5700000012 claimed this done"}]}]},
    # THE NEVER-REOPENED CONTROL: a sub-issue that exists, was never reopened,
    # and whose comment names the pull request all the same.
    ("kalaluthien/campaign-base", 707): {
        "merged_at": "2026-09-17T05:00:00Z",
        "issues": [{"number": 914, "repo": "kalaluthien/campaign-base",
                    "state": "CLOSED", "reopened": [], "comments": [
                        {"at": "2026-09-17T06:00:00Z",
                         "body": "NOTE w-2: pr#707 landed it"}]}]},
    # THE NEAR MISS: reopened after the merge, but what it names is a LONGER
    # number that starts with this one, and a bare `#708`, which names no
    # repository.
    ("kalaluthien/campaign-base", 708): {
        "merged_at": "2026-09-17T05:00:00Z",
        "issues": [{"number": 915, "repo": "kalaluthien/campaign-base",
                    "state": "OPEN",
                    "reopened": ["2026-09-17T05:30:00Z"], "comments": [
                        {"at": "2026-09-17T06:00:00Z",
                         "body": "NOTE w-2: reopening over pr#7080, see "
                                 "https://github.com/kalaluthien/campaign-base"
                                 "/pull/7080 and #708, beside the longer id "
                                 "issuecomment-95700000012"}]}]},
}


REOPENED = []


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
    # THE LAZY SECOND FETCH IS A MODULE NAME, not one of `args`'s two subject
    # fetches, so it is replaced here and its calls are counted: a branch that
    # must not take it is asserted on this list being empty.
    was_reopen, REOPENED[:] = m.fetch_reopen, []

    def reopen(repo, number):
        REOPENED.append((repo, number))
        return REOPENS.get((repo, number))
    m.fetch_reopen = reopen
    try:
        args = types.SimpleNamespace(
            fetch=lambda repo, number: ISSUES.get((repo, number)),
            fetch_thread=lambda repo, number: THREADS.get((repo, number)))
        m.cmd_corpus_join(args)
        out = {n: m.read_corpus(n) for n in
               ("verb-first", "work-kind", "C-report-disposes-finding",
                "unverified-done", "filing-scope-covers")}
    finally:
        m.CORPUS = was
        m.fetch_reopen = was_reopen
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


# ------------------------------------------- the filing reading's own three
# A `choice` WHOSE OPTIONS ARE NOT IN THE ENTRY, an address `noul` read by code
# before the option it guards, and a join that labels by the parent the create
# named. Each is asserted on its own, and each has a mutation below.
SCOPES = {"rule-check": "In: mechanise the written rules",
          "homeops": "In: this machine's ops"}
FILING_STATE = {"request": {"title": "Script the upkeep", "body": "- a body"},
                "campaigns": SCOPES}


def filing_entry(m, name="filing-scope-covers"):
    return m.load_registry()[name]


def the_options_are_built_from_the_state(m):
    """A reading whose options are not knowable until the call names the state
    field they come from, and `options_of` builds one option per key of it with
    that key's value as its description."""
    built = m.options_of(filing_entry(m), FILING_STATE)
    return (set(built) == {"rule-check", "homeops", "none"}
            and built["homeops"] == SCOPES["homeops"]), built


def the_entry_s_own_option_wins_a_collision(m):
    """A campaign that ever took the slug `none` must not overwrite the
    no-match option's description, which is what the whole set is read
    against."""
    entry = filing_entry(m)
    built = m.options_of(entry, {"request": {}, "campaigns": {"none": "a slug"}})
    return built["none"] == entry["question"]["criteria"]["none"], built


def the_built_options_are_what_is_sent(m):
    """`question_of` is what `ask` and `branch` read, so the built options must
    reach it -- and `options_from` must not, since it is this tree's own field
    and no part of the question."""
    spec = m.question_of(filing_entry(m), state=FILING_STATE)
    return (set(spec["criteria"]) == {"rule-check", "homeops", "none"}
            and m.OPTIONS_FROM not in spec), sorted(spec)


def verdicts(choice="rule-check", noul=0.04):
    """One `judge`'s verdicts for the filing group, without a call."""
    return {"filing-scope-covers": m_Verdict(choice, {"type": "choice",
                                                      "choice": choice,
                                                      "confidence": 0.9}),
            "filing-addresses-judge": m_Verdict(
                "uncertain", None if noul is None
                else {"type": "noul", "noul": noul})}


class m_Verdict:
    """The two fields `address_word` reads off a verdict."""
    def __init__(self, word, raw):
        self.word, self.raw = word, raw


def the_address_routes_an_addressed_state_to_uncertain(m):
    """rule-check#471 DECISION 5717901390: code reads the address first, and at
    ADDRESS_OVER or over the guarded reading answers `uncertain`, whatever the
    `choice` said. The CONTROL is the same option under the same cut with a
    clean state, which must come back as the option."""
    reg = m.load_registry()
    hostile, why = m.address_word(reg, "filing-scope-covers",
                                  verdicts(noul=m.ADDRESS_OVER))
    clean, _why = m.address_word(reg, "filing-scope-covers",
                                 verdicts(noul=m.ADDRESS_OVER - 0.01))
    return (hostile == m.UNCERTAIN and "at or over" in why
            and clean == "rule-check"), (hostile, clean, why)


def an_address_that_gave_no_value_is_uncertain_too(m):
    """A guard that did not answer did not rule the text out, and reading its
    silence as clean is the direction this rule exists to refuse."""
    word, why = m.address_word(m.load_registry(), "filing-scope-covers",
                               verdicts(noul=None))
    return word == m.UNCERTAIN and "gave no value" in why, (word, why)


def a_reading_with_no_address_keeps_its_own_word(m):
    """Every other reading may be asked this and comes back unchanged, which is
    what lets one reader serve them all. Its own word is a DISTINCT one here,
    so a reader that fell through to the address branch would be read as
    changing it rather than as agreeing."""
    held = verdicts(noul=0.99)
    held["filing-addresses-judge"] = m_Verdict("yes", {"type": "noul",
                                                       "noul": 0.99})
    word, why = m.address_word(m.load_registry(), "filing-addresses-judge",
                               held)
    return word == "yes" and why == "", (word, why)


def filing_row(call, parent, **kw):
    row = {"at": "2026-09-17T00:00:00+00:00", "call": call,
           "reading": "filing-scope-covers",
           "subject": f"kalaluthien/campaign-base#{parent} <- gh issue create",
           "read": f"kalaluthien/campaign-base#{parent} <- gh issue create",
           "repo": "kalaluthien/campaign-base", "issue": parent,
           "state": dict(FILING_STATE), "wording": "0" * 12, "settled": None,
           "tier": "shadow", "does": "nothing", "asked": MODEL,
           "answered": MODEL, "latency": 0.5, "branch": "rule-check",
           "raw": {"type": "choice", "choice": "rule-check", "confidence": 0.9},
           "why": "", "endpoint": "real", "flag": None}
    row.update(kw)
    return row


def the_filing_join_labels_by_the_parent_s_slug(m):
    """The row's own `--parent`, resolved to a slug: the reading runs before
    the filed issue has a number, so the row's `issue` is the parent and the
    label is its `campaign:` label."""
    cases, _lines = joined(m, [filing_row("dddd", 903)])
    got = (cases["filing-scope-covers"] or [{}])[0]
    # AND IT IS HELD TO A BAND. The entry carries the no-match option alone,
    # so a `band_of` reading the entry's own criteria would hold every case of
    # this reading to no band and call none of them drift, for good.
    return (got.get("truth") == "rule-check"
            and got.get("label", {}).get("from") == "join:filing-parent-slug"
            and got.get("band") == "confident"
            and set(got.get("state") or {}) == {"request", "campaigns"}), got


def a_parent_that_was_never_an_option_is_not_labelled(m):
    """The options are the campaigns with a directory on the machine that made
    the call. A parent outside that set is a case no answer could have got
    right, so it waits rather than being written with a truth the reading
    cannot answer."""
    cases, _lines = joined(m, [filing_row("eeee", 904)])
    return not cases["filing-scope-covers"], cases["filing-scope-covers"]


def join_skips_a_subject_that_will_not_read(m):
    """A ROW WHOSE SUBJECT WILL NOT READ IS SKIPPED, COUNTED AND NAMED, and the
    run carries on: the shared log holds 410 rows naming `o/r#274`, a suite's
    fixture repository, and calling those "not labelled yet" asks a reader to
    fix a number that cannot move.

    THE CONTROL IS A ROW OF THE SAME SHAPE WHOSE SUBJECT DOES READ, so what is
    measured is the fetch and not the row. The fetch is counted too: one call
    per subject however many rows name it."""
    asked = []
    def fetch(repo, number):
        asked.append((repo, number))
        return ISSUES.get((repo, number))
    corpus = ROOT / "corpus-unfetchable"
    if corpus.exists():
        for f in corpus.glob("*"):
            f.unlink()
    log = ROOT / "unfetchable.log"
    log.write_text("".join(json.dumps(r) + "\n" for r in [
        log_row("uuu1", "verb-first", "Cache the weather feed", 8001),
        log_row("uuu2", "verb-first", "Cache the weather feed", 8001),
        log_row("uuu3", "verb-first", "Cache the weather feed", 900)]))
    was, old = m.CORPUS, os.environ.get("CAMPAIGN_JEV_LOG")
    m.CORPUS = corpus
    os.environ["CAMPAIGN_JEV_LOG"] = str(log)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            code = m.cmd_corpus_join(types.SimpleNamespace(
                fetch=fetch, fetch_thread=lambda repo, number: None))
        ids = sorted(c["id"] for c in m.read_corpus("verb-first"))
    finally:
        m.CORPUS = was
        if old is None:
            os.environ.pop("CAMPAIGN_JEV_LOG", None)
        else:
            os.environ["CAMPAIGN_JEV_LOG"] = old
    said = out.getvalue()
    return (code == 0 and ids == ["verb-first-uuu3"]
            and "2 row(s) SKIPPED" in said
            and "kalaluthien/campaign-base#8001  2 row(s)" in said
            and "0 row(s) not labelled yet" in said
            and asked.count(("kalaluthien/campaign-base", 8001)) == 1
            and len(log.read_text().splitlines()) == 3),\
        (code, ids, asked, said)


def join_writes_the_reading_s_own_state_slice(m):
    """ONE `judge` CALL CARRIES THE UNION of every reading's fields, so a group
    whose readings name DIFFERENT fields wrote a case carrying every one of
    them -- `judge` RAISES on such a state as an extra field, and `--live`
    would ask a question about state the band was never measured with.

    The control is the other reading of the same group over the SAME row: each
    must get its own half and neither the union."""
    rows = [thread_row("tttt", 702, {"F1": "the ceiling is stated twice"})]
    cases, _lines = joined(m, rows)
    got = (cases["C-report-disposes-finding"] or [{}])[0]
    reg = m.load_registry()
    whole = set(rows[0]["state"])
    return (sorted(got.get("state") or {})
            == sorted(reg["C-report-disposes-finding"]["state"]["fields"])
            and set(got.get("state") or {}) != whole), (got.get("state"), whole)


CASES["a choice's options are built from the state field it names"] = \
    the_options_are_built_from_the_state
CASES["the entry's own option wins a name collision"] = \
    the_entry_s_own_option_wins_a_collision
CASES["the built options are what the question carries"] = \
    the_built_options_are_what_is_sent
CASES["an addressed state routes the reading it guards to uncertain"] = \
    the_address_routes_an_addressed_state_to_uncertain
CASES["an address that gave no value is uncertain too"] = \
    an_address_that_gave_no_value_is_uncertain_too
CASES["a reading that declares no address keeps its own word"] = \
    a_reading_with_no_address_keeps_its_own_word
CASES["the filing join labels by the parent the create named"] = \
    the_filing_join_labels_by_the_parent_s_slug
CASES["a parent that was never an option is not labelled"] = \
    a_parent_that_was_never_an_option_is_not_labelled
CASES["the join writes the reading's own slice of the state"] = join_writes_the_reading_s_own_state_slice
CASES["a row whose subject will not read is skipped, counted and named"] = join_skips_a_subject_that_will_not_read


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


def join_reads_a_later_review_on_the_review_channel(m):
    """A REVIEW posted with `gh pr review --comment -b` is a REVIEW: AGENTS.md
    admits both spellings. Reading one channel labelled the finding `disposed`
    at the merge -- a wrong label, into the corpus, for good."""
    cases, _lines = joined(m, [thread_row("wwww", 702, {
        "F1": "the ceiling is stated twice and the second copy drifts"})])
    got = (cases["C-report-disposes-finding"] or [{}])[0]
    return (got.get("truth") == {"F1": "undisposed"}
            and "raised again: F1" in got.get("label", {}).get("evidence", "")),\
        got


def fetch_thread_asks_the_thread_s_owner(m):
    """`check-merge-review.py` owns the thread read -- both channels, each
    paginated in full -- and this asks it rather than restating which endpoints
    a thread lives on. A second reader of that rule had already drifted: it
    read `issues/<n>/comments` alone.

    Both siblings are stubbed, so the case spends no `gh` call and proves the
    wiring: the rows come back oldest first, whatever channel they arrived on,
    each with its `at` and its `where`."""
    rows = [("comment", "a", "NOTE w-1: pushed", 2, "2026-09-18T02:00:00Z"),
            ("review", "b", "REVIEW r-1: a finding", 1, "2026-09-18T01:00:00Z")]
    reader = types.SimpleNamespace(
        bodies_of=lambda repo, number: (rows, None),
        in_time_order=lambda found: sorted(found, key=lambda r: r[4]))
    was_load, was_run = m.load_sibling, m.subprocess.run
    m.load_sibling = lambda name: reader
    m.subprocess = types.SimpleNamespace(
        run=lambda *a, **k: types.SimpleNamespace(
            returncode=0, stdout='{"state": "MERGED"}'),
        SubprocessError=Exception)
    try:
        got = m.fetch_thread("o/r", 274)
    finally:
        m.load_sibling = was_load
        m.subprocess = subprocess
        m.subprocess.run = was_run
    return (got is not None and got.get("state") == "MERGED"
            and [c["where"] for c in got["comments"]] == ["review", "comment"]
            and [c["at"] for c in got["comments"]]
            == ["2026-09-18T01:00:00Z", "2026-09-18T02:00:00Z"]), got


CASES["the thread join reads a later REVIEW on the review channel"] = join_reads_a_later_review_on_the_review_channel
CASES["fetch_thread asks the script that owns the thread read"] = fetch_thread_asks_the_thread_s_owner


# ------------------------------------ what happened after the REPORT
# `report-next-round`, the join `unverified-done` enters `unmeasurable`
# waiting for. Every branch offline, against the stubbed thread fetch and the
# stubbed LAZY second fetch, whose calls are counted.


def done_row(call, number, report="REPORT w-1: fixed at abc1234", **kw):
    row = thread_row(call, number, {"F1": "a finding"},
                     reading="unverified-done", report_comment=5700000012,
                     branch="yes", raw={"type": "noul", "noul": 0.8},
                     wording="0" * 12)
    row["state"] = dict(row["state"], report=report)
    row.update(kw)
    return row


def join_labels_a_fix_round(m):
    """THE STRONG HALF: a later REVIEW and a REPORT answering it is work that
    came back, so the claim was not verified. The LAZY SECOND FETCH must not be
    taken here -- the thread already settled it -- and that is asserted on the
    call list, not argued."""
    cases, _lines = joined(m, [done_row("dn01", 703)])
    got = (cases["unverified-done"] or [{}])[0]
    return (got.get("truth") == "yes" and got.get("band") == "yes"
            and got.get("label", {}).get("from") == "join:report-next-round"
            and "a fix round" in got.get("label", {}).get("evidence", "")
            and REOPENED == [] and set(got.get("state") or {}) == {"report"}),\
        (got, REOPENED)


def join_waits_on_a_round_nobody_answered(m):
    """A later REVIEW with NO REPORT after it is not yet a fix round: the round
    is open and labelling it either way reads a thread still moving. With the
    pull request open it waits, and the second fetch is not taken."""
    cases, _lines = joined(m, [done_row("dn02", 704)])
    return not cases["unverified-done"] and REOPENED == [], \
        (cases["unverified-done"], REOPENED)


def join_takes_the_second_fetch_only_on_a_merge(m):
    """THE WEAK HALF WAITS FOR THE MERGE, and only then is the reopen asked.
    702 merged with a later REVIEW nobody answered and closes nothing, so the
    fetch IS taken and the row labels `no`."""
    cases, _lines = joined(m, [done_row("dn03", 702)])
    got = (cases["unverified-done"] or [{}])[0]
    return (got.get("truth") == "no" and got.get("band") == "no"
            and "merged with no fix round" in got.get("label", {}).get(
                "evidence", "")
            and REOPENED == [("kalaluthien/campaign-base", 702)]), \
        (got, REOPENED)


def join_reads_a_reopened_sub_issue(m):
    """THE OTHER STRONG HALF: the sub-issue the pull request closes, reopened
    after the merge with a comment naming that pull request. 701 merged with
    nothing later on the thread at all, so only the second fetch can say.

    AND ITS SUB-ISSUE IS CLOSED AGAIN, which is the ordinary shape: the work
    that came back got done and the issue closed once more. Reading the issue's
    present state called that "never reopened" and wrote `no` with an evidence
    sentence saying so (pr#490 REVIEW 5721893225, F1). THE CONTROL is 707,
    whose sub-issue was never reopened and whose comment names the pull request
    all the same: naming without a reopen is not a reopen."""
    cases, _lines = joined(m, [done_row("dn04", 701)])
    got = (cases["unverified-done"] or [{}])[0]
    control, _l = joined(m, [done_row("dn04b", 707)])
    never = (control["unverified-done"] or [{}])[0]
    return (got.get("truth") == "yes"
            and "910 was reopened" in got.get("label", {}).get("evidence", "")
            and REOPENED == [("kalaluthien/campaign-base", 707)]
            and never.get("truth") == "no"), (got, never)


def join_reads_a_reopen_naming_a_url(m):
    """A reopen that names the pull request by ITS URL, and one that names the
    REPORT by its comment url -- the id is in the url, so the id's own pattern
    reads both. Matching a literal `pr#<n>` alone made 0-in-217 unable to tell
    never-happened from never-matched (pr#490 REVIEW 5721893225, F2).

    THE CONTROL IS THE NEAR MISS, 708: reopened after the merge, naming
    `pr#7080`, `/pull/7080`, a bare `#708`, and a comment id that ENDS with the
    REPORT's. A longer number starting or ending with this one is not this one
    (pr#490 REVIEW 5722167494, N1), and a bare `#<n>` names no repository."""
    by_url, _l = joined(m, [done_row("dn06", 705)])
    by_id, _l2 = joined(m, [done_row("dn07", 706)])
    near, _l3 = joined(m, [done_row("dn08", 708)])
    url = (by_url["unverified-done"] or [{}])[0]
    ident = (by_id["unverified-done"] or [{}])[0]
    miss = (near["unverified-done"] or [{}])[0]
    return (url.get("truth") == "yes" and ident.get("truth") == "yes"
            and miss.get("truth") == "no"), (url.get("truth"),
                                             ident.get("truth"),
                                             miss.get("truth"))


def join_asks_one_reopen_per_pull_request(m):
    """ONE REOPEN FETCH PER PULL REQUEST A JOIN RUN. `cmd_corpus_join` dedups
    its two SUBJECT fetches in a map `reopen_of` sat outside, so two rows on
    one pull request paid two `gh pr view`s (pr#490 REVIEW 5721893225, F5).

    Two rows of the SAME pull request, two cases written, ONE fetch."""
    cases, _lines = joined(m, [done_row("dn09", 701), done_row("dn10", 701)])
    return (len(cases["unverified-done"]) == 2
            and REOPENED == [("kalaluthien/campaign-base", 701)]), \
        (len(cases["unverified-done"]), REOPENED)


def join_keeps_a_row_with_no_report(m):
    """A round with no REPORT is a row code settled and the join cannot label:
    there is nothing that claimed anything. It STAYS in the log, and the second
    fetch is not spent on it."""
    cases, lines = joined(m, [done_row("dn05", 701, report="")])
    return (not cases["unverified-done"] and lines == 1 and REOPENED == []), \
        (cases["unverified-done"], lines, REOPENED)


def every_declared_join_is_a_join(m):
    """A `join` naming no function in `JOINS` is a reading whose rows
    `joinable` files as "of no registered reading with a join" -- counted apart
    and never labelled, for good, with nothing saying why."""
    bad = [f"{n}: join `{e['join']}`" for n, e in m.load_registry().items()
           if e.get("join") and e["join"] not in m.JOINS]
    return not bad, bad


CASES["the REPORT join labels a fix round, and spends no second fetch"] = \
    join_labels_a_fix_round
CASES["the REPORT join waits on a round nobody has answered"] = \
    join_waits_on_a_round_nobody_answered
CASES["the REPORT join asks the reopen only once the pull request merged"] = \
    join_takes_the_second_fetch_only_on_a_merge
CASES["the REPORT join reads a sub-issue reopened after the merge"] = \
    join_reads_a_reopened_sub_issue
CASES["the REPORT join reads a reopen naming the pull request by url"] = \
    join_reads_a_reopen_naming_a_url
CASES["two rows of one pull request ask the reopen once"] = \
    join_asks_one_reopen_per_pull_request
CASES["a row with no REPORT is kept and costs no fetch"] = \
    join_keeps_a_row_with_no_report
CASES["every join an entry declares names a function in JOINS"] = \
    every_declared_join_is_a_join


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


def a_case_code_settled_is_never_drift(m):
    """THE DEFECT `report` PRINTED ON EVERY RUN: `work-kind-0873f14b0769`, an
    issue whose `kind:` label settles the reading, came back at 0.40 against a
    `confident` band of [0.53, 1.0] and was named as drift -- a value from a
    state the prefilter means production never to send.

    THE CONTROL IS THE SAME CASE WITH THE PREFILTER'S WORD REMOVED, so what is
    measured is `settled` doing it and not the band, the wording or the model.
    Both spellings are exercised, because `settled_of` reads two."""
    entry = m.load_registry()["work-kind"]
    def case(**kw):
        out = {"id": "work-kind-settled", "reading": "work-kind", "role": "case",
               "truth": "research", "band": "confident", "state": {},
               "label": {"from": "join:issue-kind-label"},
               "seen": [{"model": MODEL, "wording": m.wording(entry),
                         "raw": {"type": "choice", "choice": "development",
                                 "confidence": 0.40}}]}
        out.update(kw)
        return out
    loose = case(settled="research")
    nested = case(source={"kind": "log", "settled": "research"})
    control = case(source={"kind": "log", "settled": None})
    drifted, unplaced = m.drift_line(entry, [loose])
    nested_drift, nested_unplaced = m.drift_line(entry, [nested])
    control_drift, control_unplaced = m.drift_line(entry, [control])
    return (drifted == "none" and len(unplaced) == 1
            and "code settled it" in unplaced[0]
            and nested_drift == "none" and len(nested_unplaced) == 1
            and "work-kind-settled 0.40 outside confident" in control_drift
            and not control_unplaced), (drifted, unplaced, nested_drift,
                                        control_drift)


CASES["a case code settled is never named as drift"] = a_case_code_settled_is_never_drift
CASES["the thread join reads a later REVIEW that raised the finding again"] = join_reads_a_later_review_on_the_thread
CASES["the thread join waits for the merge where nothing was re-raised"] = join_waits_for_the_merge_on_an_open_thread
CASES["a case the join writes is held to a band, and drift reads it"] = a_joined_case_is_held_to_a_band
CASES["a case held to no band is listed, never skipped"] = a_case_held_to_no_band_is_listed


# ------------------------------------------- one thread, one call, per finding
# A READING WHOSE `question.per` NAMES A STATE FIELD is asked once per key of
# that field, IN THE SAME CALL: every question over one pull request thread goes
# in the one call (DECISION 5716060001), and the answers come back as one
# `Verdict` carrying {key: raw} and no word.
THREAD_STATE = {"report": "REPORT w-1: F1 fixed", "own": "REPORT w-1: F1 fixed",
                "findings": {"F1": "a", "F2": "b"},
                "review": "REVIEW r-1: two findings", "thread": "comment w-1: ..."}


def thread_answers(**kw):
    """The stub's reply, keyed the way `judge` fans a per-item reading out."""
    def picked(p):
        return {"type": "choice", "choice": "supports", "confidence": 0.9,
                "probabilities": {"supports": p, "contradicts": 1 - p,
                                  "says_nothing": 0.0}}
    answers = {"C-report-disposes-finding#F1": picked(kw.get("f1", 0.95)),
               "C-report-disposes-finding#F2": picked(kw.get("f2", 0.10)),
               "C-review-not-the-author": picked(0.9),
               "unverified-done": {"type": "noul", "noul": kw.get("done", 0.7)},
               "report-addresses-judge": {"type": "noul",
                                          "noul": kw.get("address", 0.02)}}
    NEXT["status"], NEXT["body"] = 200, {"model": MODEL, "answers": answers}
    SEEN["count"] = 0


def a_per_item_reading_is_one_call(m):
    """Two findings and the other THREE readings of the group: five questions,
    ONE request, and each per-item question's instructions name its own item,
    since the id never reaches the model.

    THE COUNT OF QUESTIONS IS THE GROUP'S AND MOVES WITH IT; the count of
    REQUESTS is the invariant, and it is 1."""
    LOG.write_text("")
    clear_store()
    thread_answers()
    judged = m.judge("pull-request-thread", THREAD_STATE, read="a thread",
                     env=env(), timeout=5, log=False)
    sent = json.loads(SEEN["body"])["questions"]
    v = judged.verdicts["C-report-disposes-finding"]
    named = {qid: "findings.F1" in q["instructions"]
             for qid, q in sent.items() if qid.endswith("#F1")}
    return (SEEN["count"] == 1 and len(sent) == 5 and v.word is None
            and sorted(v.raw) == ["F1", "F2"] and all(named.values())
            and judged.verdicts["C-review-not-the-author"].word == "supports"),\
        (SEEN["count"], sorted(sent), v.word, sorted(v.raw or {}), named)


def the_done_readings_add_one_state_field(m):
    """rule-check#455 pr 5, item 1: `unverified-done` rides in the call the
    group already makes and names no field the group did not already carry.
    pr 6, item 1: its address `report-addresses-judge` names exactly ONE new
    field, `own` -- the REPORT with what it quotes cut out (DECISION
    5723273420) -- and nothing else.

    A NEW FIELD IS A NEW COST AND A SILENT ONE: `judge` builds the union of
    every entry's fields and RAISES on a state missing one, so the reader must
    build it, and every band measured on the old state belongs to a narrower
    one. The CONTROL is the group's field set, which must be exactly what
    `C-report-disposes-finding` and `C-review-not-the-author` already named,
    plus `own`."""
    reg = m.load_registry()
    group = m.group_of(reg, "pull-request-thread")
    old = set(reg["C-report-disposes-finding"]["state"]["fields"]) \
        | set(reg["C-review-not-the-author"]["state"]["fields"])
    done = reg["unverified-done"]["state"]["fields"]
    address = reg["report-addresses-judge"]["state"]["fields"]
    return (sorted(group) == ["C-report-disposes-finding",
                              "C-review-not-the-author",
                              "report-addresses-judge", "unverified-done"]
            and m.state_fields(group) == old | {"own"}
            and done == ["report"] and address == ["own"]), \
        (sorted(group), sorted(m.state_fields(group)), sorted(old), done,
         address)


def the_report_address_guards_the_done_reading(m):
    """rule-check#455 pr 5, item 2: `unverified-done` declares
    `report-addresses-judge` as its `guarded_by`, so `address_word` -- still
    the ONE reader of `ADDRESS_OVER` -- answers `uncertain` at 0.5 or over
    whatever the reading said.

    THE CONTROL is the same held word one hundredth UNDER the cut, which must
    come back as that word: a reader that always returned `uncertain` would
    pass the first half alone."""
    reg = m.load_registry()

    def held(noul):
        return {"unverified-done": m_Verdict("yes", {"type": "noul",
                                                     "noul": 0.90}),
                "report-addresses-judge": m_Verdict(
                    "yes", {"type": "noul", "noul": noul})}
    hostile, why = m.address_word(reg, "unverified-done",
                                  held(m.ADDRESS_OVER))
    clean, _why = m.address_word(reg, "unverified-done",
                                 held(m.ADDRESS_OVER - 0.01))
    silent, silent_why = m.address_word(
        reg, "unverified-done",
        {"unverified-done": m_Verdict("yes", {"type": "noul", "noul": 0.90}),
         "report-addresses-judge": m_Verdict("uncertain", None)})
    return (hostile == m.UNCERTAIN and "at or over" in why and clean == "yes"
            and silent == m.UNCERTAIN and "gave no value" in silent_why), \
        (hostile, clean, silent, why)




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
    return (sent == ["C-report-disposes-finding#F2", "C-review-not-the-author",
                     "report-addresses-judge", "unverified-done"]
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
CASES["the done reading adds no state field and its address adds only `own`"] = \
    the_done_readings_add_one_state_field
CASES["an addressed REPORT routes unverified-done to uncertain"] = \
    the_report_address_guards_the_done_reading
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


def waiting(m, rows, now=None, reg=None):
    """The two forms of the waiting line over one temp log and an empty
    corpus, so the log's rows are the only thing that moves between calls."""
    corpus = ROOT / "corpus-waiting"
    corpus.mkdir(exist_ok=True)
    for f in corpus.glob("*"):
        f.unlink()
    log = ROOT / "waiting.log"
    log.write_text("".join(json.dumps(r) + "\n" for r in rows))
    reg = reg or {"verb-first": {"tier": "shadow", "join": "issue-title-kept"}}
    was = m.CORPUS
    m.CORPUS = corpus
    old = os.environ.get("CAMPAIGN_JEV_LOG")
    os.environ["CAMPAIGN_JEV_LOG"] = str(log)
    try:
        return m.steady_waiting_line(reg, now=now), m.waiting_line(reg)
    finally:
        m.CORPUS = was
        if old is None:
            os.environ.pop("CAMPAIGN_JEV_LOG", None)
        else:
            os.environ["CAMPAIGN_JEV_LOG"] = old


# 2026-09-17T00:00:00+00:00 is `log_row`'s own `at`, so a `now` built off it
# says exactly how old every row in a case is.
LOGGED_AT = datetime.datetime.fromisoformat("2026-09-17T00:00:00+00:00")


def the_watch_line_holds_no_count_that_moves(m):
    """THE NAMED FAILING CASE (DECISION 5718621461). Two snapshots differing
    only by two more unjoined rows must read the SAME to the watch: a changed
    line is an event in every campaign's watch, and two more rows are nothing
    any planner can act on. The exact line must move, or the probe never varied
    what it claims to have varied."""
    now = LOGGED_AT + datetime.timedelta(hours=1)
    rows = [log_row(f"a{i:03d}", "verb-first", "A title", 900) for i in range(4)]
    before, before_exact = waiting(m, rows, now=now)
    more = rows + [log_row("b001", "verb-first", "A title", 900),
                   log_row("b002", "verb-first", "A title", 900)]
    after, after_exact = waiting(m, more, now=now)
    return (before == after and before_exact != after_exact), \
        (before, after, before_exact, after_exact)


def the_watch_line_says_when_waiting_starts_and_ends(m):
    """It carries no count, so it has to still carry the two transitions that
    are worth a planner's attention: nothing waiting, and something."""
    quiet, _exact = waiting(m, [], now=LOGGED_AT)
    busy, _exact = waiting(m, [log_row("c001", "verb-first", "A title", 900)],
                           now=LOGGED_AT + datetime.timedelta(hours=1))
    return (quiet == "jev waiting: nothing" and busy != quiet), (quiet, busy)


def the_watch_line_ages_the_oldest_unjoined_row(m):
    """The third transition: the same rows, read either side of STALE_AFTER.
    An unjoined row is worth saying twice -- when it appears, and when it has
    sat long enough that whoever made it will not be joining it."""
    rows = [log_row("d001", "verb-first", "A title", 900)]
    young, _exact = waiting(
        m, rows, now=LOGGED_AT + m.STALE_AFTER - datetime.timedelta(minutes=1))
    aged, _exact = waiting(m, rows, now=LOGGED_AT + m.STALE_AFTER)
    return ("oldest over" not in young and "oldest over" in aged), (young, aged)


def the_watch_line_names_rows_the_join_refuses(m):
    """A row the join refuses is not waiting -- nothing can ever label it --
    and it is still said, because the exact line has named it since DECISION
    5716626608 and a watch that went quiet would miss a log filling with rows
    no join will ever take. One more refused row is still the same line."""
    now = LOGGED_AT + datetime.timedelta(hours=1)
    one = [log_row("e001", "verb-first", "A title", 900, endpoint="stub")]
    two = one + [log_row("e002", "verb-first", "A title", 900, endpoint="stub")]
    said, exact = waiting(m, one, now=now)
    again, more = waiting(m, two, now=now)
    quiet, _exact = waiting(m, [], now=now)
    return (said == again and "never joinable" in said and exact != more
            and "never joinable" not in quiet), (said, again, quiet, exact, more)


def a_row_with_no_at_is_not_the_oldest(m):
    """An empty string wins a `min`, so a row carrying no `at` read as the
    oldest hid how old the real oldest row was, and the age clause never
    fired while one sat in the log."""
    rows = [log_row("f001", "verb-first", "A title", 900),
            log_row("f002", "verb-first", "A title", 900, at=None)]
    aged, exact = waiting(m, rows, now=LOGGED_AT + m.STALE_AFTER)
    return ("oldest over" in aged
            and "(oldest 2026-09-17T00:00:00+00:00)" in exact), (aged, exact)


def the_age_word_is_written_from_the_constant(m):
    """The word follows STALE_AFTER rather than assuming whole hours, so
    moving the constant to 90 minutes cannot print `over 1h`."""
    got = [m.span_text(datetime.timedelta(hours=6)),
           m.span_text(datetime.timedelta(minutes=90)),
           m.span_text(datetime.timedelta(minutes=30))]
    return got == ["6h", "90m", "30m"], got


CASES["the watch's line names the rows the join refuses, and counts none"] = \
    the_watch_line_names_rows_the_join_refuses
CASES["a row carrying no `at` is not read as the oldest unjoined row"] = \
    a_row_with_no_at_is_not_the_oldest
CASES["the age word is written from the constant, not from whole hours"] = \
    the_age_word_is_written_from_the_constant


CASES["the watch's line holds no count that moves on each call"] = \
    the_watch_line_holds_no_count_that_moves
CASES["the watch's line says when waiting starts and when it ends"] = \
    the_watch_line_says_when_waiting_starts_and_ends
CASES["the watch's line says when the oldest unjoined row has aged"] = \
    the_watch_line_ages_the_oldest_unjoined_row


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
        # BOTH CHECKS, IN THE ORDER `load_registry` RUNS THEM, so this helper
        # answers what the registry refuses rather than what one of its two
        # readers does; a case written against half of it passed over the other.
        m.check_edges(m.check_act_bounds({name: entry}))
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
    # THE CODE, NOT THE PROSE. A docstring naming the spelling a REVIEW may
    # arrive on -- `gh pr review --comment -b` -- is not a write this module
    # makes, and reading it as one is a case that fails on an explanation.
    code = "".join(
        tok.string for tok in tokenize.generate_tokens(
            io.StringIO(SOURCE).readline)
        if tok.type not in (tokenize.STRING, tokenize.COMMENT))
    found = [w for w in writes if w in code]
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
        option_cut = (entry.get("thresholds") or {}).get("option")
        for c in m.read_corpus(name):
            if c.get("reading") != name:
                bad.append(f"{c.get('id')}: reading `{c.get('reading')}`")
            got = set(c.get("state") or {})
            if got != want:
                bad.append(f"{c.get('id')}: state {sorted(got)}, entry names "
                           f"{sorted(want)}")
            # A READING WHOSE OPTIONS ARE BUILT IS JUDGED AGAINST THE CASE'S
            # OWN OPTION SET, not the entry's: the entry holds the no-match
            # option alone and the rest come from the state the case carries,
            # so `options_of` -- the one reader of that rule -- is asked with
            # this case's state. Read per case and not per entry, because two
            # cases of one reading may have been asked different option sets:
            # a leave-one-out no-match case is a positive with its own
            # campaign's option taken away.
            # AND `none` IS NOT ADMITTED FOR FREE. A `choice` answers its own
            # options and nothing else, so the set is exactly them: unioning
            # `none` in admitted a truth of `none` for a reading whose
            # no-match option is spelled `noMatch`, which is the one word this
            # case exists to catch (pr#484 REVIEW 5720443119).
            if option_cut or entry["question"]["type"] != m.CHOICE:
                words = {"yes", "no", "none"}
            else:
                words = set(m.options_of(entry, c.get("state") or {}))
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


def a_row_says_which_kind_of_run_spent_it(m):
    """PRODUCTION AND MEASURING, on the row and apart in the ratio. A measuring
    run asks the same states ON PURPOSE -- the store off, so the noise is
    measured and not the store -- so counting its calls with production's makes
    "calls a state" a number about nothing.

    Both writers are exercised: `ask`'s row and `judge`'s, since `judge` writes
    its own row per reading and a `run` it swallowed would mark every reader's
    call as production."""
    read(m)
    m.ask("a suite", "a label", STATE, BOTH, env=env(), timeout=5,
          cache=False, run=m.MEASURING)
    measuring = json.loads(LOG.read_text().splitlines()[-1])
    serving()
    m.judge("issue-shape", STATE, read="a label", env=env(), timeout=5,
            cache=False, run=m.MEASURING)
    judged = json.loads(LOG.read_text().splitlines()[-1])
    serving()
    m.ask("a suite", "a label", STATE, BOTH, env=env(), timeout=5, cache=False)
    production = json.loads(LOG.read_text().splitlines()[-1])
    return (measuring.get("run") == "measuring"
            and judged.get("run") == "measuring"
            and production.get("run") == "production"),\
        (measuring.get("run"), judged.get("run"), production.get("run"))


def the_ratio_shows_the_two_runs_apart(m):
    """OLD ROWS STAY AND CANNOT BE RE-MARKED, so the all-time ratio they
    dominate is printed as it is and the marked window beside it -- production
    by itself, measuring by itself. A reader that averaged the two would report
    a production ratio nobody measured."""
    LOG.write_text("".join(json.dumps(r) + "\n" for r in [
        # four calls on one state, from before the field existed
        {"reading": "verb-first", "state_hash": "aaa", "cached": False},
        {"reading": "verb-first", "state_hash": "aaa", "cached": False},
        {"reading": "verb-first", "state_hash": "aaa", "cached": False},
        {"reading": "verb-first", "state_hash": "aaa", "cached": False},
        # one production call, one state
        {"reading": "verb-first", "state_hash": "bbb", "cached": False,
         "run": "production"},
        # two measuring calls on one state: the noise run, asking twice
        {"reading": "verb-first", "state_hash": "ccc", "cached": False,
         "run": "measuring"},
        {"reading": "verb-first", "state_hash": "ccc", "cached": False,
         "run": "measuring"},
    ]))
    lines = m.spend_lines(env=env())
    where = {}
    head = ""
    for line in lines:
        if line.startswith(("  all time", "    production", "    measuring",
                            "  since the")):
            head = line.strip().split(" ")[0]
        elif "verb-first" in line:
            where.setdefault(head, []).append(line)
    return (len(where.get("all", [])) == 1
            and "7 sent over 3 state(s), 2.3 a state" in where["all"][0]
            and len(where.get("production", [])) == 1
            and "1 sent over 1 state(s), 1.0 a state" in where["production"][0]
            and len(where.get("measuring", [])) == 1
            and "2 sent over 1 state(s), 2.0 a state" in where["measuring"][0]
            and any("3 row(s) carry it, of 7" in ln for ln in lines)), lines


def a_repeat_run_asks_a_sample_and_the_edges(m):
    """THE RULE, AND WHAT IT KEEPS. A case whose value sits near an edge or a
    band's end is asked EVERY run, because that is the case a run can move a
    threshold with; a flip and a no-match are asked every run, because the live
    half asserts on each by name; a case not yet seen under this wording is
    asked, because nothing is known about it; and a seeded share of the rest.

    THE SEED IS WHAT MAKES A BAND COMPARABLE between runs, so the same draw is
    asserted twice rather than only its size."""
    entry = {"tier": "advise", "group": "g",
             "question": {"type": "choice", "instructions": "i",
                          "criteria": {"a": "x", "b": "y", "none": "z"}},
             "thresholds": {"floor": 0.50, "certain_over": 0.52,
                            "no_match": "none"},
             "bands": {"model": MODEL, "wording": "", "measured": "",
                       "declared": {"confident": [0.53, 1.0],
                                    "unsure": [0.11, 0.43]}}}
    def seen(value):
        return [{"model": MODEL, "wording": m.wording(entry),
                 "raw": {"type": "choice", "choice": "a", "confidence": value}}]
    cases = ([{"id": "near-edge", "role": "case", "seen": seen(0.47)},
              {"id": "near-band-end", "role": "case", "seen": seen(0.55)},
              # 0.75 sits near no mark, so what pins these two is the ROLE
              {"id": "a-flip", "role": "flip", "seen": seen(0.75)},
              {"id": "a-no-match", "role": "no-match", "seen": seen(0.75)},
              {"id": "unseen", "role": "case", "seen": []},
              # 0.99 sits against the `confident` band's 1.0, which is the
              # scale's own end and no mark, so it is NOT pinned
              {"id": "at-the-ceiling", "role": "case", "seen": seen(0.99)}]
             + [{"id": f"settled-{i:02d}", "role": "case", "seen": seen(0.90)}
                for i in range(20)])
    asked, pinned = m.sample_of(entry, cases)
    ids = [c["id"] for c in asked]
    again = [c["id"] for c in m.sample_of(entry, cases)[0]]
    return (set(pinned) == {"near-edge", "near-band-end", "a-flip",
                            "a-no-match", "unseen"}
            and all(i in ids for i in pinned)
            and pinned["a-flip"] == "role flip"
            and pinned["a-no-match"] == "role no-match"
            and pinned["near-edge"].startswith("within")
            and "at-the-ceiling" not in pinned
            and len([i for i in ids if i not in pinned]) == 5 and ids == again
            and ids == [c["id"] for c in cases if c["id"] in set(ids)]),\
        (ids, pinned)


CASES["a row says which kind of run spent the call"] = a_row_says_which_kind_of_run_spent_it
CASES["report shows a measuring run and production apart"] = the_ratio_shows_the_two_runs_apart
CASES["a repeat run asks a seeded sample and every case near an edge"] = a_repeat_run_asks_a_sample_and_the_edges
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
    """One plain word, on every row this module writes, and it is a fact about
    the RESPONSE: `stub` where one came back from a named endpoint, `none`
    where nothing answered at all, and `real` only for the live one.

    THE DEFECT, AND WHY IT IS NOT A DETAIL: the word was read off the
    ENVIRONMENT -- `stub` when `CAMPAIGN_JEV_URL` is set, else `real` -- so
    every run that merely forgot the variable wrote `real`. A fixture's `gh`
    shim, a control call with no key, a reader whose endpoint timed out: each
    put a row the join takes into the shared log, on the strength of a call
    nobody made. The two calls below send nothing at all, and the stub is the
    control that says the word still moves."""
    read(m)
    stubbed = json.loads(LOG.read_text().splitlines()[-1])
    # NO URL AND NO KEY: `ask` reaches nothing, and the old rule read the
    # absent variable as the live endpoint.
    root, log = a_base("endpoint-word")
    m.ask("a suite", "a label", STATE, BOTH, env={"HOME": str(HOME)}, cwd=root,
          timeout=5)
    keyless = json.loads(log.read_text().splitlines()[-1])
    # A CLOSED PORT WITH A KEY: the request is built and nothing answers it.
    LOG.write_text("")
    clear_store()
    m.ask("a suite", "a label", STATE, BOTH, env=env(url=CLOSED), timeout=5)
    closed = json.loads(LOG.read_text().splitlines()[-1])
    return (stubbed.get("endpoint") == "stub"
            and keyless.get("endpoint") == "none"
            and closed.get("endpoint") == "none"
            and m.endpoint_word(m.DEFAULT_URL) == "real"
            and m.endpoint_word(URL) == "stub"),\
        (stubbed.get("endpoint"), keyless.get("endpoint"),
         closed.get("endpoint"))


def a_replay_says_where_the_answer_came_from(m):
    """A REPLAY IS NOT A CALL, and the row must still say where the answer came
    from, so the endpoint travels with the response in the store.

    An entry written before it did -- a bare response, which is what the store
    held until now -- replays and says `none`. Never `real`: the join takes a
    `real` row, and nothing on disk can say which endpoint filled a file that
    did not record one."""
    read(m)
    first = m.ask("a suite", "a label", STATE, BOTH, env=env(), timeout=5)
    hit = json.loads(LOG.read_text().splitlines()[-1])
    held = sorted((LOG.parent / "jev-cache").glob("*.json"))
    for path in held:
        path.write_text(json.dumps(json.loads(path.read_text())["response"]))
    second = m.ask("a suite", "a label", STATE, BOTH, env=env(), timeout=5)
    legacy = json.loads(LOG.read_text().splitlines()[-1])
    return (len(held) == 1 and first.cached and hit.get("endpoint") == "stub"
            and second.cached and legacy.get("endpoint") == "none"
            and second.answers["verb_first"].word == "yes"),\
        (len(held), first.cached, hit.get("endpoint"), second.cached,
         legacy.get("endpoint"))


CASES["a replayed answer says which endpoint answered it"] = a_replay_says_where_the_answer_came_from


def a_skip_row_claims_no_endpoint(m):
    """A `skip` row says the reading asked NOTHING, so no endpoint answered it.
    `real` there would be a row the join could take on the strength of a call
    nobody made -- and the reading that skipped had no key of its own to fail
    on, so the word would have been `real` on every machine."""
    LOG.write_text("")
    # `env()` AND NOT A DICT OF ITS OWN: with no `CAMPAIGN_JEV_LOG` named, the
    # skip falls back to `<base>/runtime/jev.log` -- this machine's own.
    m.skip("a suite", "a label", "the kind read failed", env=env())
    row = json.loads(LOG.read_text().splitlines()[-1])
    kept, stray, unreal = m.joinable([row], m.load_registry())
    return (row.get("endpoint") == "none" and not kept and not stray
            and len(unreal) == 1), (row.get("endpoint"), kept, stray, unreal)


CASES["a skip row says no endpoint answered it, and the join refuses it"] = a_skip_row_claims_no_endpoint
CASES["a row says which endpoint answered it"] = a_row_says_which_endpoint_answered_it
# ------------------------------------- the five that survived every mutation
# Named in pr#474's REVIEW (issuecomment-5718228578) note 4: each was landed
# with a case for what it DOES and none for what it must not do, so the whole
# behaviour could be deleted and the suite stayed green.


def settled_of_reads_both_spellings(m):
    """THE TWO SPELLINGS THE CORPUS CARRIES: `settled` at the top level, which
    the survey fit writes, and `source.settled`, which `corpus join` writes off
    the log row. `report` read only the join's, so every case the survey's
    prefilter had cleared was counted as one Jev answered."""
    top = {"settled": "cleared", "source": {}}
    joined_ = {"source": {"settled": "research"}}
    both = {"settled": "cleared", "source": {"settled": "research"}}
    neither = {"source": {}}
    return (m.settled_of(top) == "cleared"
            and m.settled_of(joined_) == "research"
            and m.settled_of(both) == "cleared"
            and m.settled_of(neither) is None),\
        [m.settled_of(c) for c in (top, joined_, both, neither)]


def scored_skips_a_case_code_settled(m):
    """A case CODE settled is not one Jev got wrong: the model never saw it. It
    is also not scorable when nothing has been seen, or when the run recorded
    no WORD, which is every case of a reading asked per item."""
    seen = [{"word": "no", "raw": {"type": "noul", "noul": 0.04}}]
    asked = {"truth": "yes", "seen": seen, "source": {}}
    settled = {"truth": "yes", "seen": seen, "settled": "no", "source": {}}
    per_item = {"truth": {"F1": "disposed"}, "source": {},
                "seen": [{"word": None, "raw": {"F1": {}}}]}
    nothing = {"truth": "yes", "seen": [], "source": {}}
    no_truth = {"seen": seen, "source": {}}
    return (m.scored(asked) and not m.scored(settled)
            and not m.scored(per_item) and not m.scored(nothing)
            and not m.scored(no_truth)),\
        [m.scored(c) for c in (asked, settled, per_item, nothing, no_truth)]


def an_uncertain_never_acts(m):
    """DECISION 5715993782: `uncertain` is an answer that landed BETWEEN the two
    edges, so the word it would act on is the one the band says is not earned.
    At `advise` it is shown; above that it does nothing, at any confidence."""
    entry = acting(verb="label", label="kind:development", what="x", undo="y",
                   act_over=0.6, ask_over=0.3)
    high = {"type": "noul", "noul": 0.99}
    got = [m.does(entry, "uncertain", high), m.does(entry, "yes", high),
           m.does(entry, "unknown", high)]
    entry["tier"] = "advise"
    shown = m.does(entry, "uncertain", high)
    return (got == ["nothing", "act", "nothing"] and shown == "show"),\
        (got, shown)


def spend_lines_leaves_a_stub_out_of_the_ratio(m):
    """A stub's call cost nobody anything, so it is not in calls-a-state. It is
    counted and named apart, since a row that vanished from both would read as
    a log nobody wrote to."""
    LOG.write_text("".join(json.dumps(r) + "\n" for r in [
        {"reading": "verb-first", "state_hash": "aaa", "endpoint": "real"},
        {"reading": "verb-first", "state_hash": "bbb", "endpoint": "stub"},
        {"reading": "verb-first", "state_hash": "ccc", "endpoint": "stub"},
    ]))
    lines = m.spend_lines(env=env())
    verb = [ln for ln in lines if "verb-first" in ln]
    return (len(verb) == 1 and "1 sent over 1 state(s)" in verb[0]
            and "2 from a stubbed endpoint" in lines[0]), lines


def waiting_line_counts_the_never_joinable_apart(m):
    """A row the join refuses is NOT waiting: nothing can ever label it, so
    counting it as waiting asks a reader to fix a number that cannot move."""
    LOG.write_text("".join(json.dumps(r) + "\n" for r in [
        log_row("aaaa", "verb-first", "Cache the weather feed", 900),
        log_row("bbbb", "verb-first", "Cache the weather feed", 900,
                endpoint="stub"),
        log_row("cccc", "verb-first", "Cache the weather feed", 900,
                endpoint="none"),
    ]))
    old = os.environ.get("CAMPAIGN_JEV_LOG")
    os.environ["CAMPAIGN_JEV_LOG"] = str(LOG)
    try:
        line = m.waiting_line()
    finally:
        if old is None:
            os.environ.pop("CAMPAIGN_JEV_LOG", None)
        else:
            os.environ["CAMPAIGN_JEV_LOG"] = old
    return ("1 log row(s) unjoined" in line
            and "2 row(s) never joinable, no `real` endpoint" in line), line


CASES["settled_of reads both spellings the corpus carries"] = settled_of_reads_both_spellings
CASES["scored skips a case code settled, unseen or asked per item"] = scored_skips_a_case_code_settled
CASES["an `uncertain` never acts, at any confidence"] = an_uncertain_never_acts
CASES["spend_lines leaves a stubbed call out of the ratio"] = spend_lines_leaves_a_stub_out_of_the_ratio
CASES["waiting_line counts the never-joinable apart"] = waiting_line_counts_the_never_joinable_apart

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
def edges_do_not_cross(m):
    """The two edges of a band are in ORDER, or the registry does not load. A
    pair that crossed has no middle, so `uncertain` could never be answered --
    and nothing refused it while the suite only asserted both were present."""
    bad = []
    for cuts, why in (({"yes_over": 0.2, "no_under": 0.5}, "yes_over"),
                      ({"yes_over": 0.5, "no_under": 0.5}, "yes_over"),
                      ({"floor": 0.6, "certain_over": 0.5, "no_match": "none"},
                       "certain_over"),
                      ({"floor": 0.5, "certain_over": 0.5, "no_match": "none"},
                       "certain_over")):
        entry = acting(verb="label", label="kind:development", what="x",
                       undo="y", act_over=0.9, ask_over=0.7)
        entry["thresholds"] = cuts
        if "floor" in cuts:
            entry["question"]["type"] = "choice"
            entry["question"]["criteria"] = {"none": "", "development": ""}
        ok, said = refused(m, entry, why)
        if not ok:
            bad.append((cuts, said))
    # AND IT IS READ AT LOAD, through the file, not only by whoever calls the
    # check: a registry the tree committed with a crossed pair must refuse on
    # the way in.
    path = ROOT / "crossed-readings.json"
    crossed = acting(verb="label", label="kind:development", what="x",
                     undo="y", act_over=0.9, ask_over=0.7)
    crossed["thresholds"] = {"yes_over": 0.2, "no_under": 0.5}
    path.write_text(json.dumps({"crossed": crossed}))
    try:
        m.load_registry(path)
        bad.append(("through load_registry", "a crossed pair loaded"))
    except ValueError as e:
        if "yes_over" not in str(e):
            bad.append(("through load_registry", str(e)))
    # AND THE COMMITTED REGISTRY LOADS, which is the half a made entry cannot
    # show: every edge pair this tree ships is in order.
    try:
        m.load_registry()
    except ValueError as e:
        bad.append(("the committed registry", str(e)))
    return not bad, bad


CASES["the two edges of a band do not cross"] = edges_do_not_cross
CASES["a reading with no thresholds is at shadow"] = thresholds_or_shadow
CASES["a reading at act declares what it does and how it is undone"] = act_declares_its_undo
CASES["a declared wording is the hash of its question"] = wording_is_computed
CASES["no Jev question is written outside the registry"] = no_question_outside_the_registry

MUTATIONS = [
    ("the two edges allowed to cross", "            if hi <= lo:",
     "            if False:", "the two edges of a band do not cross"),
    ("the edge check never run at load",
     "    return check_edges(\n        check_act_bounds(",
     "    return (\n        check_act_bounds(",
     "the two edges of a band do not cross"),
    # --- the five that survived every mutation (pr#474 REVIEW note 4) ---
    ("settled_of reading only the join's spelling",
     '    if case.get("settled") is not None:\n        return case["settled"]',
     "    if False:\n        return None",
     "settled_of reads both spellings the corpus carries"),
    ("scored counting a case code settled",
     '    return (not isinstance(settled_of(case), str) and seen is not None',
     "    return (True and seen is not None",
     "scored skips a case code settled, unseen or asked per item"),
    ("scored counting a per-item case with no word",
     '            and seen.get("word") is not None and case.get("truth") is not None)',
     '            and case.get("truth") is not None)',
     "scored skips a case code settled, unseen or asked per item"),
    ("an uncertain allowed to act",
     '    if word == UNCERTAIN:\n        return NOTHING',
     "    if False:\n        return NOTHING",
     "an `uncertain` never acts, at any confidence"),
    ("a stubbed call counted in the ratio",
     '        if row.get("endpoint") == STUB:\n            stubbed += 1\n            continue',
     "        if False:\n            pass",
     "spend_lines leaves a stubbed call out of the ratio"),
    ("the never-joinable counted as waiting",
     '            + (f"; {len(unreal)} row(s) never joinable, no `{REAL}` endpoint"\n               if unreal else ""))',
     "            + \"\")",
     "waiting_line counts the never-joinable apart"),
    # --- the shared log, and what may join ---
    ("a stub allowed to write the shared log",
     "    if URL_ENV in env:", "    if False:",
     "a stubbed call never writes the shared log"),
    ("the endpoint read off the environment instead of the response",
     "    return REAL if url == DEFAULT_URL else STUB",
     "    return REAL", "a row says which endpoint answered it"),
    ("a call that sent nothing claiming the real endpoint answered it",
     "    key, why = read_key(env)\n    if why:\n"
     '        return unknown_all(questions, why), "", why, False, NONE_SENT',
     "    key, why = read_key(env)\n    if why:\n"
     '        return unknown_all(questions, why), "", why, False, REAL',
     "a row says which endpoint answered it"),
    ("the endpoint never stored beside the answer",
     "        path.write_text(json.dumps({STORED_ENDPOINT: word,",
     "        path.write_text(json.dumps({STORED_ENDPOINT: REAL,",
     "a replayed answer says which endpoint answered it"),
    ("a store entry that names no endpoint replayed as the real one",
     "        word = out.get(STORED_ENDPOINT)\n"
     "        return held, word if word in (REAL, STUB) else NONE_SENT",
     "        return held, REAL",
     "a replayed answer says which endpoint answered it"),
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
    # --- the built options, the address, and the filing join ---
    ("the built options never built",
     "    built = ({str(k): str(v) for k, v in given.items()}\n"
     "             if isinstance(given, dict) else {})",
     "    built = {}",
     "a choice's options are built from the state field it names"),
    ("the entry's own options overwritten by the built ones",
     "    built.update(criteria)\n    return built",
     "    criteria.update(built)\n    return criteria",
     "the entry's own option wins a name collision"),
    ("the built options never reaching the question",
     '    if spec.pop(OPTIONS_FROM, None):\n'
     '        spec["criteria"] = options_of(entry, state)',
     "    spec.pop(OPTIONS_FROM, None)",
     "the built options are what the question carries"),
    ("the address read as an upper edge it never reaches",
     "    if value >= ADDRESS_OVER:", "    if False:",
     "an addressed state routes the reading it guards to uncertain"),
    ("an address that gave no value read as clean",
     "    if value is None:\n        return UNCERTAIN, (f\"the address "
     "`{guard}` gave no value, so the state \"",
     "    if value is None:\n        return word, (f\"the address "
     "`{guard}` gave no value, so the state \"",
     "an address that gave no value is uncertain too"),
    ("every reading read as though it declared an address",
     "    if not guard:\n        return word, \"\"",
     "    if False:\n        return word, \"\"",
     "a reading that declares no address keeps its own word"),
    ("the filing join reading a label that is not the campaign's",
     '    slugs = [n[len("campaign:"):] for n in names if n.startswith("campaign:")]',
     "    slugs = list(names)",
     "the filing join labels by the parent the create named"),
    ("a parent outside the option set labelled all the same",
     "    if slugs[0] not in offered:", "    if False:",
     "a parent that was never an option is not labelled"),
    ("a built-option case held against the entry's own options",
     "    options = options_of(entry, case.get(\"state\"))",
     '    options = entry["question"].get("criteria") or {}',
     "the filing join labels by the parent the create named"),
    # --- the thread join ---
    ("the thread read restated here instead of asked for",
     "        found, why = reader.bodies_of(repo, number)",
     '        found, why = [], "read it here instead"',
     "fetch_thread asks the script that owns the thread read"),
    ("the thread handed back in the order it arrived",
     "                         in reader.in_time_order(found)],",
     "                         in found],",
     "fetch_thread asks the script that owns the thread read"),
    ("a later REVIEW read from one channel only",
     '''    later = [c.get("body") or "" for c in thread.get("comments") or []
             if (c.get("at") or "") > at''',
     '''    later = [c.get("body") or "" for c in thread.get("comments") or []
             if (c.get("where") == "comment") and (c.get("at") or "") > at''',
     "the thread join reads a later REVIEW on the review channel"),
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
     "    stored, word = (cache_read(cache_key(state, questions), env, cwd) if cache\n"
     "                    else (None, NONE_SENT))",
     "    stored, word = None, NONE_SENT",
     "a second identical ask replays and sends nothing"),
    ("the store never written",
     "        cache_write(cache_key(state, questions), out, word, env, cwd)",
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
     "                    else (None, NONE_SENT))",
     "                    else cache_read(cache_key(state, questions), env, cwd))",
     "the noise switch sends every time"),
    ("the noise switch swallowed by `judge`",
     "timeout=timeout, log=False, cache=cache,\n                      run=run)",
     "timeout=timeout, log=False, cache=True,\n                      run=run)",
     "the noise switch sends every time"),
    ("the marked window folded into the all-time one",
     '    marked = [r for r in rows if r.get(RUN_FIELD) in RUNS]',
     "    marked = rows",
     "report shows a measuring run and production apart"),
    ("the run word never written on a row",
     '           "endpoint": answered_by, RUN_FIELD: run,',
     '           "endpoint": answered_by, RUN_FIELD: PRODUCTION,',
     "a row says which kind of run spent the call"),
    ("judge swallowing the run word",
     '               "endpoint": reading.endpoint, RUN_FIELD: run,',
     '               "endpoint": reading.endpoint, RUN_FIELD: PRODUCTION,',
     "a row says which kind of run spent the call"),
    ("the repeat sample drawn afresh every run",
     '    drawn = set(random.Random(SAMPLE_SEED).sample(sorted(rest), take)) if rest \\',
     "    drawn = set(random.Random().sample(sorted(rest), take)) if rest \\",
     "a repeat run asks a seeded sample and every case near an edge"),
    ("the scale's own ends counted as a band's edge",
     "                  if isinstance(v, (int, float)) and 0.0 < v < 1.0]",
     "                  if isinstance(v, (int, float))]",
     "a repeat run asks a seeded sample and every case near an edge"),
    ("a case near an edge left to the sample",
     "        if close:", "        if False:",
     "a repeat run asks a seeded sample and every case near an edge"),
    ("a flip or a no-match left to the sample",
     '        if c.get("role", "case") != "case":',
     "        if False:",
     "a repeat run asks a seeded sample and every case near an edge"),
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
    ("the refused rows dropped from the watch's line",
     '    if unreal:\n        body += ', '    if False:\n        body += ',
     "the watch's line names the rows the join refuses, and counts none"),
    ("the refused rows counted on the watch's line",
     '+ f"rows never joinable, no `{REAL}` endpoint"',
     '+ f"{len(unreal)} rows never joinable, no `{REAL}` endpoint"',
     "the watch's line names the rows the join refuses, and counts none"),
    ("a row with no `at` read as the oldest again",
     'oldest = min((r["at"] for r in unjoined if r.get("at")), default="")',
     'oldest = min((r.get("at") or "" for r in unjoined), default="")',
     "a row carrying no `at` is not read as the oldest unjoined row"),
    ("the age word assuming whole hours",
     'return f"{minutes // 60}h" if minutes and not minutes % 60 else f"{minutes}m"',
     'return f"{minutes // 60}h"',
     "the age word is written from the constant, not from whole hours"),
    # THE WATCH'S LINE, each of its three transitions broken in turn.
    ("the watch's line carrying the count again",
     '        parts.append("log rows unjoined" + aged)',
     '        parts.append(f"{len(unjoined)} log rows unjoined" + aged)',
     "the watch's line holds no count that moves on each call"),
    ("unjoined rows never reaching the watch's line",
     "    if unjoined:\n        aged = ", "    if False:\n        aged = ",
     "the watch's line says when waiting starts and when it ends"),
    ("an unjoined row never going stale",
     "    return now - when >= span", "    return False",
     "the watch's line says when the oldest unjoined row has aged"),
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
    ("the drift line testing a case code settled against a band",
     "        if not held_to_a_band(c):", "        if False:",
     "a case code settled is never named as drift"),
    ("held_to_a_band letting a settled case through",
     '    return settled_of(case) is None or case.get("role") == "no-match"',
     "    return True",
     "a case code settled is never named as drift"),
    ("the join writing the whole group's state into one reading's case",
     '            "state": {k: v for k, v in (row.get("state") or {}).items()\n'
     '                      if k in fields}, "truth": truth,',
     '            "state": row.get("state") or {}, "truth": truth,',
     "the join writes the reading's own slice of the state"),
    ("a subject that will not read counted as waiting",
     "        if fetched[(subject, repo, number)] is None:",
     "        if False:",
     "a row whose subject will not read is skipped, counted and named"),
    ("the subject fetched once per row instead of once per subject",
     "        if (subject, repo, number) not in fetched:",
     "        if True:",
     "a row whose subject will not read is skipped, counted and named"),
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
     "        check_act_bounds(json.loads(path.read_text(encoding=\"utf-8\"))))",
     '        json.loads(path.read_text(encoding="utf-8")))',
     "a registry file carrying a bad act never loads"),
    ("a skip not logged",
     '"skipped": why}\n    return log_call(',
     '"skipped": why}\n    return "logged to" or log_call(',
     "a skipped reading is logged as one JSON line naming why"),
    ("a skip row claiming the real endpoint answered it",
     '           "endpoint": NONE_SENT, RUN_FIELD: PRODUCTION, "skipped": why}',
     '           "endpoint": REAL, RUN_FIELD: PRODUCTION, "skipped": why}',
     "a skip row says no endpoint answered it, and the join refuses it"),
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


# Whether a case's runs may set or test a band is `campaign-jev.held_to_a_band`'s,
# asked and never restated: this suite kept its own reading of it, and the drift
# line kept a third, which called a case code settles drifted for good.


# Which band a case is held to is `campaign-jev.band_of`'s, asked and never
# restated: this suite kept its own reading of it, and the two disagreed exactly
# where the join wrote a case with no `band`.


# The number the band is over is `campaign-jev.band_value`'s, asked and never
# restated: a suite that kept its own copy would measure a band the module does
# not read.


def live(record, wording_hash=None, whole=False):
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
        settled_here = []
        # WHICH CASES A REPEAT RUN ASKS IS `sample_of`'s, and the reason is its
        # own: this run is the noise measurement, and asking every case every
        # time is what put `work-kind` at 24 calls a state. `--all` is the way
        # past it, for a wording change that has to be measured from scratch.
        asked, _pinned = (list(cases) if whole else jev.sample_of(entry, cases)[0],
                          None)
        print(jev.sample_line(entry, cases, asked) if not whole
              else f"  asked all {len(cases)} case(s)")
        for c in asked:
            # THE STORE IS OFF HERE, as it is in `relive`: a band is what the
            # same state answers across runs, and a replayed answer would
            # report a drift of zero (DECISION 5716060001).
            r = jev.ask("campaign-jev-test.py --live", c["id"],
                        c.get("state") or {}, q, cache=False,
                        run=jev.MEASURING)
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
            # WHICH CASES A BAND IS OVER IS `held_to_a_band`'s, and why is its
            # docstring's. What is this loop's own: such a case is still ASKED
            # and still PRINTED, because what the model would have said about a
            # state code settles is the evidence that the prefilter is worth
            # having.
            if not jev.held_to_a_band(c):
                settled_here.append((c["id"], a.word, value))
                continue
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
        if settled_here:
            print(f"  {name}: {len(settled_here)} case(s) code settles, asked "
                  f"and recorded, held to no band -- "
                  + ", ".join(f"{i} {w} {v}" for i, w, v in settled_here[:6]))
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
                if not jev.held_to_a_band(c):
                    continue
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
        live("--record" in argv, argv[at + 1] if at is not None else None,
             "--all" in argv)
        return harness.report()
    pure_branches(load(SOURCE))
    harness.mutate(SOURCE, load, CASES, MUTATIONS)
    return harness.report()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
