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
before-and-after numbers.

Usage: scripts/campaign-jev-test.py [--live [--record] [--wording <hash>]]
"""
import contextlib
import datetime
import http.server
import importlib
import json
import os
import re
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
    probs = lambda c: {"type": "choice", "choice": "supports", "confidence": 0.9,  # noqa: E731
                       "probabilities": {"supports": 1 - c, "contradicts": c}}
    check("branch: one option's probability over the cut is yes, whoever won",
          m.branch(OPTION_Q, probs(0.55))[0] == "yes")
    check("branch: one option's probability under the cut is no",
          m.branch(OPTION_Q, probs(0.10))[0] == "no")
    check("branch: one option's probability in the gap is unknown",
          m.branch(OPTION_Q, probs(0.35))[0] == "unknown")
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
    "a noul in the gap is unknown": unknown_because(
        "verb_first", "in the gap", noul=0.78),
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
    """A reading at `act` says what it does and how it is undone, or it is not
    at `act`: an irreversible thing on a typed guess is the one answer this
    module never gives."""
    bad = []
    for name, e in entries(m).items():
        if e.get("tier") != m.ACTS:
            continue
        act = e.get("act") or {}
        for k in ("what", "undo", "act_over", "ask_over"):
            if k not in act:
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


def log_row(call, reading, title, number, **kw):
    row = {"at": "2026-09-17T00:00:00+00:00", "call": call, "reading": reading,
           "subject": f"kalaluthien/campaign-base#{number}",
           "read": f"kalaluthien/campaign-base#{number}",
           "repo": "kalaluthien/campaign-base", "issue": number,
           "state": {"title": title, "body": "- a body"},
           "wording": "0" * 12, "settled": None, "tier": "advise",
           "does": "show", "asked": MODEL, "answered": MODEL, "latency": 0.5,
           "branch": "yes", "raw": {"type": "noul", "noul": 0.9}, "why": "",
           "flag": None}
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
            fetch=lambda repo, number: ISSUES.get((repo, number)))
        m.cmd_corpus_join(args)
        out = {n: m.read_corpus(n) for n in ("verb-first", "work-kind")}
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
            fetch=lambda repo, number: ISSUES.get((repo, number))))
        out = m.read_corpus("verb-first")
    finally:
        m.CORPUS = was
        if old is None:
            os.environ.pop("CAMPAIGN_JEV_LOG", None)
        else:
            os.environ["CAMPAIGN_JEV_LOG"] = old
    return len(first["verb-first"]) == 1 and len(out) == 1, \
        (len(first["verb-first"]), len(out or []))


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
    ("the confidence floor dropped", 'if confidence < spec["floor"]:', "if False:",
     "a choice under the floor is unknown"),
    ("the option's probability unread",
     'value = (probabilities.get(spec["option"])',
     'value = (probabilities.get("supports")',
     "a choice cut on one option reads that option's probability"),
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


def band_key(entry, case):
    """Which band a case belongs to: a `noul`'s is its truth, a `choice`'s is
    how decided the answer should be. A case that fits no option belongs to
    neither -- it is the no-match evidence and is reported on its own."""
    if case.get("role") == "no-match" or case.get("truth") == "none":
        return None
    return case["truth"] if entry["question"]["type"] == "noul" else case.get("band")


def measured(entry, raw):
    """The number the band is over: a `noul`'s own value, a `choice`'s
    confidence. NOT `campaign-jev.confidence`, which folds a `noul` to its
    distance from the coin toss -- a band is over the value the model
    returned."""
    if raw is None:
        return None
    return raw.get("noul") if entry["question"]["type"] == "noul" else raw.get("confidence")


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
        cases = jev.read_corpus(name)
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
            r = jev.ask("campaign-jev-test.py --live", c["id"],
                        c.get("state") or {}, q, log=False)
            model = r.model or model
            a = r.answers[name]
            value = measured(entry, a.raw)
            print(f"  {c['id']:<28} {a.word:<12} "
                  f"{'--' if value is None else format(value, '.2f')}  "
                  f"truth {c['truth']}")
            if record:
                c.setdefault("seen", []).append(
                    {"model": r.model, "wording": wording, "at": at,
                     "word": a.word, "raw": a.raw})
            key = band_key(entry, c)
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
                check(f"live: {name}'s floor sits above the whole declared "
                      f"`unsure` band",
                      bool(declared.get("unsure"))
                      and declared["unsure"][1] < cuts["floor"],
                      (declared.get("unsure"), cuts.get("floor")))
                check(f"live: {name}'s floor sits below the whole declared "
                      f"`confident` band",
                      bool(declared.get("confident"))
                      and cuts["floor"] < declared["confident"][0],
                      (cuts.get("floor"), declared.get("confident")))
        if record and not wording_hash:
            # THE BAND IS THE WHOLE RECORDED HISTORY UNDER THIS WORDING, not
            # this run alone: three runs are what a band is made of, and a
            # `--record` that read only the run it just made would declare a
            # band narrower than the evidence and then widen it on the next
            # run, which reads exactly like drift. `seen` is appended above, so
            # this run is already in it.
            history = {}
            for c in cases:
                key = band_key(entry, c)
                for s in c.get("seen") or []:
                    value = measured(entry, s.get("raw"))
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
