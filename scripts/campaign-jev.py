#!/usr/bin/env python3
"""Ask Jev for a typed judgment over one state, and answer `unknown` rather than guess.

THE ONE CALLER OF JEV IN THIS REPOSITORY. Every reading that wants a judgment
-- reading comprehension a script cannot do -- asks here, so the key, the pinned
model, the thresholds, the failure paths and the log are decided once. A second
caller would each have to get all five right, and the one that got a failure path
wrong would answer with a guess.

WHAT A JUDGMENT IS WORTH, AND ITS TIER. Typed output guarantees the shape, not
the truth, so what an answer may do is declared per reading and not assumed:
`shadow` logs and prints nothing, `advise` prints, and `act` does the
reversible thing its entry names at high confidence, asks at medium and does
nothing at low. A Jev answer never refuses, merges or deletes, and moves no
caller's exit status at any tier. `spec/campaign/github/system.als` is that
claim in the model: a judgment stands in for an agent's read of an issue only
at `act` and only when the call replied, cleared its threshold and fits;
otherwise the issue is escalated to an agent.

THE QUESTION IS NEVER WRITTEN HERE. `scripts/jev/readings.json` is the one home
of every reading -- the question, its `criteria`, how a reading asked per item
puts that item into it (`compose`), the state slice, the code prefilter, the
cuts and the tier -- and a reader asks by NAME:

    judge("issue-shape", {"title": ..., "body": ...},
          read="kalaluthien/campaign-base#455",
          key={"repo": "kalaluthien/campaign-base", "issue": 455})

One group is one state and ONE call. The caller refuses a missing or an extra
state field, because both are the reader's bug: an extra field is state no band
was measured with, a missing one is a question asked about nothing.

TWO THINGS A COMMITTED FILE CANNOT HOLD, and both are declared there all the
same. A `choice` whose options are not knowable until the call -- the open
campaigns, say -- names the state field they are BUILT from with
`options_from`, and `options_of` is the one reader of that rule. A reading
whose state holds somebody else's prose names the group-mate that guards it
with `guarded_by`, and `address_word` is the one reader of THAT rule: at
`ADDRESS_OVER` or over the guarded reading answers `uncertain`, whatever it
said (rule-check#471 DECISION 5717901390).

UNKNOWN IS THE ANSWER FOR EVERY FAILURE. A state over `STATE_BUDGET`, or a
`choice` over `OPTION_BUDGET` options -- neither ever sent, neither ever cut
down -- no key, a `~/.env` that is not text,
`CAMPAIGN_JEV_URL` set to nothing, a URL with no scheme, an endpoint that would
not answer, an HTTP error, a timeout, a body that is not JSON, a response naming
another model, an answer missing for a question, an answer of another type --
each comes back `unknown` with a one-line reason, per question. A raw value the
two edges leave BETWEEN them is not one of those: it is `uncertain`, an answer
that happened and reached no word. `ask` is the boundary that holds it: every
named path above returns rather than raises, and `ask` catches what is left and
answers `unknown` wearing its exception's class name. The ONE thing that raises
is a question of an unsupported TYPE, which is the caller's bug and not the
model's answer. Nothing else may, because a caller prints a verdict on the next
line -- a traceback out of here turned a `check` whose shape held into a refused
claim.

THE THRESHOLDS ARE THE CALLER'S, and they are two numbers and not one:

  noul    `yes_over` and `no_under`, and what falls between them is
          `uncertain`. A `noul` near 0.5 means yes and no are equally likely,
          not a medium degree, so a single cut would turn the model's own
          indecision into a verdict.
  choice  `floor` on `confidence`, the name of the `no_match` option, and where
          the reading has bands, `certain_over` as the floor's upper edge. The
          first two both, because a `choice` with no fitting option still picks
          one: a no-match option alone missed a no-match answered at low
          confidence, and a floor alone let a confident wrong option through.
          `confidence` measures how concentrated the distribution is, not
          whether the option set fits.
  option  a `choice` naming one `option` is instead cut on that option's own
          probability, by `yes_over` and `no_under` as a `noul` is: `yes` the
          option holds, `no` it does not, between them `uncertain`. For a
          reading that flags one option -- a claim `contradicts` its evidence
          -- where the winner and its confidence would hide a strong second.

Every threshold is set from cases of the tree's own history, one of which fits
no option, and asserted as a BAND: the same request comes back a few hundredths
apart. `scripts/campaign-jev-test.py --live` is that run, and the cases live in
`scripts/jev/corpus/<reading>.jsonl` -- one line per case, with every run that
has been made against it -- while each reading's band and the changes that
moved it sit in its entry and in `scripts/jev/corpus/<reading>.changes.jsonl`.

THE CORPUS GROWS BY ITSELF, or it does not grow. Every call writes one log row
PER READING, holding the state, the wording hash, the prefilter's word, the
flag the reader computed and the join key as FIELDS -- repo, issue, and comment
or pull request where there is one, because every join is "the later fact on
that number". `corpus join` asks the per-reading function the entry names what
then happened and writes the labelled case; a row it cannot label yet stays and
is counted, and `report`'s first line is what is waiting.

ONE CALL PER STATE. Every independent question over the same state goes in one
`ask`: forty cost the latency of one and cannot see each other's answers. A
second call is for an answer that must fetch evidence or build the next options.

AND THE SAME STATE IS ASKED ONCE. The raw probabilities of every answer are
stored beside the log, keyed by a hash of the STATE, a hash of the QUESTIONS AS
SENT and the pinned MODEL, so a moved cut, band or combiner replays and asks
nothing; a hit makes no request and needs no key. `cache=False` is the noise
switch, set by `relive` and by the suite's `--live` half and by nothing else,
because a band is what the same state answers ACROSS runs. `report` prints calls
a state per reading, over the calls SENT -- a hit is logged as a hit and is not
one. The store is scratch: gone, unreadable or corrupt, it costs a call and
never an answer (DECISION 5716060001).

EVERY CALL IS LOGGED, one JSON line to `<base>/runtime/jev.log` -- git-ignored
scratch, the base being the campaign directory's parent when the call runs
inside a clone (`base_root`) -- naming the reader, a SHORT label for what it read (never the state,
which carries issue bodies), the model that answered, the latency, the
`endpoint` word, and per question the raw value and the branch taken.

EXCEPT A STUBBED ONE. A run that named `CAMPAIGN_JEV_URL` logs only where
`CAMPAIGN_JEV_LOG` names a file and NEVER to the shared log, and stores nothing
there either, because the shared log is what the corpus grows from and a
suite's answers are not the tracker's history. Every row says which endpoint
answered it, `real` or `stub`, and `corpus join` takes only a `real` one --
refusing the rest by name, including rows written before the field existed,
which cannot say (DECISION 5716626608). A refused row is not waiting: nothing
can label it, so it is counted apart. `Reading.logged` is the sentence
the caller prints beside the verdict, as `check-campaign-claim.py` prints one
beside its own: a caller that logged nothing and said nothing reads exactly like
one that logged.

Usage: scripts/campaign-jev.py report [<reading>] [--live] [--waiting [--steady]]
       scripts/campaign-jev.py corpus join
       scripts/campaign-jev.py new <reading>
       scripts/campaign-jev.py probe <request.json>   -- a hand probe; the file
       holds {"reader": ..., "label": ..., "state": ..., "questions": {...}}
"""
import argparse
import datetime
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import namedtuple
from pathlib import Path

# This script's own directory, which is where its siblings and its registry sit.
HERE = Path(__file__).resolve().parent
# THE MODEL THAT ANSWERED WHEN THE THRESHOLDS WERE SET, pinned. `jev-latest`
# moves on release, and a band measured under one version says nothing about
# the next. A response naming any other model is `unknown`, not a downgrade.
MODEL = "jev-1.13.0"
DEFAULT_URL = "https://api.typesafe.ai/v1/systemone"
# THE TEST SEAM, and the one knob a suite needs: a stub server on 127.0.0.1, or
# a closed port, is how every offline suite that runs a caller of this forces
# `unknown` without a network and without a key.
URL_ENV = "CAMPAIGN_JEV_URL"
LOG_ENV = "CAMPAIGN_JEV_LOG"
KEY_ENV = "TYPESAFE_API_KEY"
# Seconds. A judgment is an aside to a reading that has already been made, so a
# slow endpoint costs the reader `unknown` and not a wait: measured calls run
# 0.6-1.1s, and ten seconds is late rather than slow.
TIMEOUT = 10.0
# HOW MUCH STATE MAY BE SENT, in UTF-8 bytes of the serialized `state`. Bytes
# and not tokens, because counting tokens needs a tokenizer this tree does not
# carry and will not add for a guard.
#
# Measured in sdlc-alloy#458: a state of about 30k tokens answered, while a
# 127 KB and a 235 KB file each came back HTTP 400 `max_tokens_exceeded`. The
# state this tree sends is English prose carrying code, paths and punctuation,
# which tokenizes nearer three bytes per token than the four of plain prose --
# so the 30k tokens that answered is about 90 KB, which sits just under the
# 127 KB that did not, and the two readings agree. 60 KB is two thirds of the
# smallest size known to answer and under half the smallest known to fail; an
# issue body's own ceiling is 2000 characters, so nothing this tree sends comes
# near it and the budget is a guard rather than a limit anyone meets.
#
# A STATE OVER IT IS NOT SENT AND IS NOT CUT DOWN. Truncating here would answer
# a question about a state nobody asked about, and the caller is the only one
# that knows which part of its state carries the answer -- so slicing stays the
# reader's and this returns `unknown` naming both numbers.
STATE_BUDGET = 60_000
# HOW MANY `choice` OPTIONS THE ENDPOINT TAKES, measured and not read off
# a document: 254 scenarios plus the entry's own `noMatch` answer, 255
# refuse with an HTTP 400 that reads exactly like an outage (binary
# search, sdlc-alloy#458 S7, 2026-09-18). It bites a reading whose
# options are BUILT FROM THE STATE and so grow with the tree: `spec/`
# declares 244 commands today, eleven under the ceiling.
OPTION_BUDGET = 255
UNKNOWN = "unknown"
# THE ANSWER THAT LANDED BETWEEN THE EDGES, and it is NOT `unknown`. A lone cut
# inside a measured band flips on noise, so a reading that has bands takes two
# edges and says `uncertain` for what falls between them (DECISION 5715993782).
# The two words are kept apart because they mean different things to a reader:
# `unknown` is a reading that did not happen -- no key, no answer, a model that
# is not the pinned one, a confidence under the floor -- and `uncertain` is one
# that did happen and does not reach a word. `uncertain` warns nothing.
UNCERTAIN = "uncertain"
NOUL, CHOICE = "noul", "choice"
# THE EDGES, by question type. A `noul`, and a `choice` cut on ONE option's own
# probability, take `yes_over` and `no_under`; an ordinary `choice` takes
# `floor` -- below it the answer is `unknown` -- and, where it declares one,
# `certain_over`, the upper edge of the same band. A reading may declare NO
# edge at all, which `campaign-jev-test.py`'s "a reading with no thresholds is
# at shadow" case admits at `shadow` alone -- a suite case, not a function
# here -- and there the model's own word is recorded and nothing is judged.
VALUE_EDGES = ("yes_over", "no_under")
CHOICE_EDGES = ("floor", "certain_over")

# One question's answer: the branch, the raw value as the model returned it, and
# why the branch is what it is. `why` is filled for `unknown` and empty
# otherwise, so a caller prints a reason exactly where there is one.
Answer = namedtuple("Answer", "word raw why")
# One call: the answers by question id, the model that answered (empty when
# none did), the latency in seconds, the sentence about the log line, whether a
# stored answer was replayed, and which endpoint answered it.
Reading = namedtuple("Reading", "answers model latency logged cached endpoint",
                     defaults=(False, "none"))


def read_key(env=None):
    """(the key, "") from the environment or `~/.env`, or ("", why).

    NO SHELL EXPORTS IT. The key lives in `~/.env`, which `uv run --env-file`
    reads and an ordinary session does not, so a reader that only looked at the
    environment would answer `unknown` in every pane on this machine. The
    environment still wins, so a suite and a probe can name their own.

    The key is never returned to a log, a message or a traceback -- only this
    function and the request header ever hold it."""
    env = os.environ if env is None else env
    if env.get(KEY_ENV):
        return env[KEY_ENV], ""
    path = Path(env.get("HOME", "~")).expanduser() / ".env"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        # NOT `OSError` ALONE: a `~/.env` that is not UTF-8 raises
        # UnicodeDecodeError, which walked past this and out through `ask` into
        # the caller's traceback -- a file nobody here wrote, turning a reading
        # that should answer `unknown` into a crash.
        return "", (f"no `{KEY_ENV}` in the environment and {path} did not read "
                    f"({e.__class__.__name__})")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].strip()
        name, sep, value = line.partition("=")
        if sep and name.strip() == KEY_ENV:
            value = value.strip().strip("'\"")
            if value:
                return value, ""
    return "", f"no `{KEY_ENV}` in the environment or in {path}"


def endpoint(env=None):
    """(the URL to POST to, "") -- `CAMPAIGN_JEV_URL` when set, else the live
    one -- or ("", why) when it is set to nothing.

    A SET-BUT-EMPTY VALUE IS NOT AN UNSET ONE. `CAMPAIGN_JEV_URL=` is how a
    caller says "do not call out", and falling through to `DEFAULT_URL` on it
    sent the live endpoint a request the environment had just forbidden. Unset
    still means the live one, because that is the ordinary case."""
    env = os.environ if env is None else env
    if URL_ENV not in env:
        return DEFAULT_URL, ""
    url = env[URL_ENV].strip()
    if not url:
        return "", (f"`{URL_ENV}` is set to nothing, which names no endpoint; "
                    f"unset it to reach {DEFAULT_URL}")
    return url, ""


def branch(spec, raw):
    """(the word, why) for one raw answer against one question's thresholds.

    A CALCULATION, so every branch has a case that spends no request: the
    thresholds are the whole of the decision and nothing here reads a clock, a
    file or the network.

    `spec` is the question as its caller wrote it; `raw` is the answer object
    the response carried, or None when it carried none. An unsupported `type`
    RAISES: a question nobody wrote a branch for is the caller's bug, and
    answering `unknown` would hide it behind the word every failure already
    wears.

    THE EDGES ARE TWO AND THE MIDDLE IS `uncertain`, never `unknown`. A lone cut
    inside a measured band flips on noise, so a reading declares the band it was
    measured over and this answers `uncertain` between the edges -- an answer
    that happened and reached no word, which a reader prints and warns nothing
    about. `unknown` stays what it always was: a reading that did not happen."""
    kind = spec["type"]
    if kind not in (NOUL, CHOICE):
        raise ValueError(f"campaign-jev: no branch for a `{kind}` question; "
                         f"this module answers {NOUL} and {CHOICE}")
    if raw is None:
        return UNKNOWN, "the response carried no answer for this question"
    if raw.get("type") != kind:
        return UNKNOWN, (f"the response answered a `{raw.get('type')}` where a "
                         f"`{kind}` was asked")
    if kind == NOUL:
        value, what = raw.get(NOUL), "noul"
    elif "option" in spec:
        probabilities = raw.get("probabilities")
        value = (probabilities.get(spec["option"])
                 if isinstance(probabilities, dict) else None)
        what = f"P({spec['option']})"
    # A READING THAT DECLARES NO EDGE records the model's own answer and judges
    # nothing. Legal at `shadow` alone -- campaign-jev-test.py's "a reading
    # with no thresholds is at shadow" case, which reads the committed
    # registry -- where a reading enters to collect cases until a record labels
    # them: a cut invented before the first case is the number every later band
    # gets fitted to. A `choice`
    # has a word of its own to record; a `noul` has only a number, so there is
    # no word to earn and it comes back `uncertain`.
    if not any(k in spec for k in VALUE_EDGES + CHOICE_EDGES):
        option = raw.get(CHOICE)
        if kind == CHOICE and isinstance(option, str):
            return option, "no cut is declared, so the option is recorded and "\
                           "not judged"
        return UNCERTAIN, (f"no cut is declared, so this answer is recorded "
                           f"and not judged")
    if kind == NOUL or "option" in spec:
        if not isinstance(value, (int, float)):
            return UNKNOWN, f"the answer carries no {what} value"
        if value >= spec["yes_over"]:
            return "yes", ""
        if value <= spec["no_under"]:
            return "no", ""
        return UNCERTAIN, (f"{what} {value:.2f} sits in the band between "
                          f"{spec['no_under']:.2f} and {spec['yes_over']:.2f}, "
                          f"where neither word is earned")
    option, confidence = raw.get(CHOICE), raw.get("confidence")
    if not isinstance(confidence, (int, float)) or not isinstance(option, str):
        return UNKNOWN, "the answer carries no option and confidence"
    if confidence < spec["floor"]:
        return UNKNOWN, (f"`{option}` at confidence {confidence:.2f}, under the "
                         f"floor of {spec['floor']:.2f}")
    if option == spec["no_match"]:
        return UNKNOWN, (f"the answer is `{option}`, the no-match option: no "
                         f"option of the set fits")
    if confidence < spec.get("certain_over", 0.0):
        return UNCERTAIN, (f"`{option}` at confidence {confidence:.2f} sits in "
                           f"the band between {spec['floor']:.2f} and "
                           f"{spec['certain_over']:.2f}, where the option is "
                           f"not yet earned")
    return option, ""


def base_root(cwd=None):
    """The base checkout's root, or None: the claim guard's `base_root`, the
    one home of that reading (rule-check#370 row 2). A campaign directory among
    the working directory's ancestors decides first and the base root is its
    parent; only with none does git answer, AGENTS.md's one form.

    THE GIT FORM ALONE WROTE INSIDE A CLONE (rule-check#475, DECISION
    5723273621). `campaign-tracker check` run with `<campaign>/repos/<repo>/`
    as its working directory got THAT repository's common dir, so `jev.log`
    and `jev-cache/` landed under the clone: rows `report` never read, and an
    ignored file `local-work` counted against the chore's own unattended close.
    """
    start = Path(cwd) if cwd else Path(os.getcwd())
    try:
        root, _note = load_sibling("check-campaign-claim.py").base_root(
            start.resolve())
    except Exception:                          # noqa: BLE001 -- no base, then
        return None
    return root


# WHICH ENDPOINT ANSWERED, in one plain word on every row. `real` is the live
# one; `stub` is any run that named `CAMPAIGN_JEV_URL`, which is a suite's
# 127.0.0.1 server or a closed port. The join reads it: a stub's answer replayed
# as a real one would be a case the tracker never produced (DECISION
# 5716626608).
# A THIRD WORD, `none`, FOR A ROW NO CALL WAS ANSWERED FOR: a `skip`, a state
# over the budget, no key, an endpoint that did not answer.
#
# THE WORD IS A FACT ABOUT THE CALL AND NOT ABOUT THE ENVIRONMENT. It was
# `stub if CAMPAIGN_JEV_URL is set else real`, which says `real` for every run
# that merely FORGOT the variable -- a fixture's `gh` shim, a suite's control
# call with no key, a reader whose endpoint timed out. Each of those wrote
# `real` on a row no real endpoint had answered, and the join takes such a row
# on the strength of a call nobody made. So the word is decided where the
# response comes back, and nothing but a response can earn `real`.
REAL, STUB, NONE_SENT = "real", "stub", "none"

# WHICH KIND OF RUN SPENT THE CALL, in one plain word on every row this module
# writes. A PRODUCTION call is a reader answering a question it was asked; a
# MEASURING run -- `report --live`, the suite's `--live` and its `--record` --
# asks states it has already asked, with the store off, because that is the only
# way to see how far the same state moves between runs (DECISION 5716060001).
#
# THE TWO ARE NEVER AVERAGED. A measuring run asks the same states ON PURPOSE,
# so counting its calls with production's made "calls a state" a number about
# nothing. They used not to be logged at all, which is worse: the calls were
# spent and invisible. Now they are logged, marked, and counted apart.
PRODUCTION, MEASURING = "production", "measuring"
RUN_FIELD = "run"
RUNS = (PRODUCTION, MEASURING)


def endpoint_word(url):
    """Which endpoint answered, given the URL the response CAME BACK FROM --
    never a plan to reach one: every caller here holds a decoded response by the
    time it asks. A suite that points `CAMPAIGN_JEV_URL` at the live endpoint
    itself is reaching the live endpoint, so the URL and not the variable is
    what is read."""
    return REAL if url == DEFAULT_URL else STUB


def log_path(env=None, cwd=None):
    """(the log file, how to name it) or (None, why there is none).

    A STUBBED CALL NEVER REACHES THE SHARED LOG. `CAMPAIGN_JEV_LOG` names where
    a run logs and always wins; with no name and a stubbed endpoint there is
    nowhere to log, because the shared `<base>/runtime/jev.log` is where the
    corpus grows from and a suite's answers are not evidence. A suite that
    forgets to name a log therefore writes nothing, which it can see."""
    env = os.environ if env is None else env
    named = env.get(LOG_ENV)
    if named:
        return Path(named), named
    if URL_ENV in env:
        return None, (f"`{URL_ENV}` names a stubbed endpoint and no `{LOG_ENV}` "
                      f"names a log, so nothing is written to the shared one")
    root = base_root(cwd)
    if root is None:
        return None, "under no base checkout, so there is no runtime/ to log to"
    return root / "runtime" / "jev.log", f"{root}/runtime/jev.log"


def log_call(row, env=None, cwd=None):
    """Append one line, and return what to say about having done so.

    THE FAILURE MODE OF A MECHANISED RULE IS SILENCE, so this never raises and
    never swallows: a write that did not happen comes back as a sentence the
    caller prints beside the verdict."""
    path, how = log_path(env, cwd)
    if path is None:
        return f"answer not logged: {how}"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError as e:
        return f"answer not logged to {how} ({e.__class__.__name__})"
    return f"logged to {how}"


def skip(reader, label, why, env=None, cwd=None):
    """Log a reading that asked nothing because it could not read its input --
    a kind read that failed, a registry that would not load -- so a count of
    what a shadow reading covered can see the calls it missed. Same line shape
    as `ask`'s, `skipped` in place of `answers`; returns what `log_call` says."""
    row = {"at": datetime.datetime.now(datetime.timezone.utc)
                         .isoformat(timespec="seconds"),
           "reader": reader, "read": label, "asked": MODEL,
           "endpoint": NONE_SENT, RUN_FIELD: PRODUCTION, "skipped": why}
    return log_call(row, os.environ if env is None else env, cwd)


# ------------------------------------------------------------------ the store
# RAW PROBABILITIES ARE KEPT AND REPLAYED, so a moved cut, band or combiner asks
# nothing (DECISION 5716060001). The key is three things and all three matter: a
# hash of the STATE, a hash of the QUESTIONS AS SENT -- the wording, which is
# what `wording()` hashes for a registry entry -- and the pinned MODEL, because
# a band measured under one version says nothing about the next.
#
# IT LIVES BESIDE THE LOG, in git-ignored runtime scratch, and holds the decoded
# response whole. Nothing durable lives there: a store that is gone costs a
# call and never an answer, so every path here returns rather than raises.
CACHE_DIR = "jev-cache"
# THE TWO KEYS OF A STORE FILE. A file that carries neither is an entry written
# before the endpoint travelled with the answer: it still replays, and its
# endpoint is `none`.
STORED_ENDPOINT, STORED_RESPONSE = "endpoint", "response"


def digest(obj):
    """12 hex of one object's canonical JSON. The one hasher, so a key computed
    on the way in and one computed on the way out cannot disagree."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()[:12]


def cache_key(state, questions):
    """`<state>-<wording>-<model>`. The questions are hashed AS SENT, so the
    thresholds -- which never reach the model -- never split the key either."""
    sent = request_body(state, questions)["questions"]
    return f"{digest(state)}-{digest(sent)}-{MODEL}"


def cache_path(key, env=None, cwd=None):
    """The file one key is stored in, or None when there is nowhere to store.

    IT RIDES ON `log_path`, so a stubbed call that named no log has nowhere to
    store and nothing to read: a stub's answer must never be replayed as a real
    one, and a suite that names `CAMPAIGN_JEV_LOG` gets a store of its own
    beside that log. One rule, read in one place."""
    log, _how = log_path(env, cwd)
    return None if log is None else log.parent / CACHE_DIR / f"{key}.json"


def cache_read(key, env=None, cwd=None):
    """(the stored response, which endpoint answered it), or (None, `none`).

    NEVER RAISES: a store that will not read is a call to make, not a reading to
    lose. THE ENDPOINT TRAVELS WITH THE ANSWER, because a replay is not a call
    and the row must still say where the answer came from; an entry written
    before the word was stored answers `none`, which the join refuses, rather
    than being read as the live endpoint's."""
    path = cache_path(key, env, cwd)
    if path is None:
        return None, NONE_SENT
    try:
        out = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, NONE_SENT
    if not isinstance(out, dict):
        return None, NONE_SENT
    held = out.get(STORED_RESPONSE)
    if isinstance(held, dict):
        word = out.get(STORED_ENDPOINT)
        return held, word if word in (REAL, STUB) else NONE_SENT
    return out, NONE_SENT


def cache_write(key, out, word, env=None, cwd=None):
    """Store one decoded response and the endpoint that answered it. NEVER
    RAISES, and says nothing: a store that could not be written costs the next
    reader a call it would have made."""
    path = cache_path(key, env, cwd)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({STORED_ENDPOINT: word,
                                    STORED_RESPONSE: out},
                                   sort_keys=True, ensure_ascii=False),
                        encoding="utf-8")
    except (OSError, TypeError, ValueError):
        return


def request_body(state, questions):
    """The POST body: the pinned model, the state, and every question in ONE
    call. The thresholds stay here -- they are this tree's reading of the
    answer, and the model is never told what cut its caller will apply."""
    return {"model": MODEL, "state": state,
            "questions": {qid: {k: v for k, v in spec.items()
                                if k in ("type", "instructions", "criteria")}
                          for qid, spec in questions.items()}}


def post(body, key, url, timeout):
    """(the decoded response, "") or (None, why). Every network and decode
    failure is a sentence, never an exception: the caller's next line is a
    verdict it must still be able to print."""
    # BUILDING THE REQUEST IS GUARDED, AND SEPARATELY. `Request(...)` parses
    # the URL and raises ValueError on one with no scheme -- a misconfiguration
    # that escaped entirely while this sat above the `try`. It gets its own
    # sentence rather than the one below, because nothing was asked of any
    # endpoint: "the endpoint did not answer" sends a reader looking at a
    # service that was never reached, where the fault is the variable.
    try:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": "Bearer " + key,
                     "Content-Type": "application/json"})
    except ValueError as e:
        return None, (f"`{URL_ENV}` names no usable endpoint ({e}), so nothing "
                      f"was asked")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            text = fh.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # THE BUDGET MAY BE WRONG, so the endpoint's own word for "too large"
        # is read rather than reported as a bare 400: a reader that saw only
        # the number would go looking at its questions.
        try:
            detail = e.read().decode("utf-8", "replace")[:400]
        except Exception:  # noqa: BLE001 -- a body that would not read says nothing
            detail = ""
        if e.code == 400 and "max_tokens_exceeded" in detail:
            return None, (f"the endpoint answered HTTP 400 "
                          f"max_tokens_exceeded: the state was too large for "
                          f"the model, so the {STATE_BUDGET}-byte budget here "
                          f"is set too high")
        return None, f"the endpoint answered HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 -- a timeout, a DNS failure, a closed port
        return None, f"the endpoint did not answer ({e.__class__.__name__})"
    try:
        return json.loads(text), ""
    except ValueError as e:
        return None, f"the response is not JSON ({e.__class__.__name__})"


def unknown_all(questions, why):
    """Every question `unknown` for one reason: the shape every whole-call
    failure answers in, so a caller has one answer per question either way."""
    return {qid: Answer(UNKNOWN, None, why) for qid in questions}


def ask(reader, label, state, questions, env=None, cwd=None, timeout=TIMEOUT,
        log=True, cache=True, run=PRODUCTION):
    """One call, one `Reading`: a branch per question, and the log line's fate.

    `reader` names who asked -- a script and its subcommand -- and `label` what
    was read, SHORT and carrying no state: `kalaluthien/campaign-base#455
    title+body`, never the body. Both go in the log, which is why the state does
    not: an issue body in a scratch log is a copy nobody swept.

    `questions` maps an id to a spec: `type`, `instructions`, `criteria`, and
    the thresholds `branch` reads. The id is a KEY of the body and no part of
    the question, so the instructions carry the whole meaning.

    THIS IS THE BOUNDARY THE MODULE'S PROMISE RESTS ON. An unsupported question
    TYPE raises, and it is the only thing that does: every named failure below
    answers `unknown`, and anything unnamed is caught at the bottom and answers
    `unknown` too, wearing its exception's class name. A caller of this prints a
    verdict on the next line, and a traceback out of here turned a `check` whose
    shape held into a claim refused.

    `log=False` is `judge`'s, and only `judge`'s: it writes one row PER READING
    rather than one per call, so that a join can read a row on its own. Two
    writers of the same line would drift, so there is still exactly one
    function that writes one -- `log_call` -- and this only declines to call
    it.

    `cache=False` IS THE NOISE SWITCH, and it is explicit rather than guessed
    at: a run that measures how far the same state moves between runs must send
    every one of them, so `relive` and the suite's `--live` half set it and
    nothing else does. A hit is logged as a hit and is NOT a call: `report`'s
    calls-a-state ratio is over the calls that were actually sent.

    `run` SAYS WHICH KIND OF RUN SPENT THE CALL, and it goes on the row so that
    `report` can count a measuring run apart from production rather than
    averaging the two."""
    env = os.environ if env is None else env
    for qid, spec in questions.items():
        if spec["type"] not in (NOUL, CHOICE):
            raise ValueError(f"campaign-jev: question `{qid}` is a "
                             f"`{spec['type']}`; this module answers "
                             f"{NOUL} and {CHOICE}")
    started = time.time()
    hit, answered_by = False, NONE_SENT
    try:
        answers, model, why, hit, answered_by = _answer(
            state, questions, env, timeout, cache, cwd)
    except Exception as e:  # noqa: BLE001 -- the boundary; the promise is here
        why = (f"the call raised where nothing is meant to "
               f"({e.__class__.__name__}), so nothing was read")
        answers, model = unknown_all(questions, why), ""
    latency = time.time() - started
    row = {"at": datetime.datetime.now(datetime.timezone.utc)
                         .isoformat(timespec="seconds"),
           "reader": reader, "read": label, "asked": MODEL,
           "endpoint": answered_by, RUN_FIELD: run,
           "answered": model, "latency": round(latency, 3),
           # THE STATE'S HASH AND NOT THE STATE. The label carries no state on
           # purpose -- an issue body in a scratch log is a copy nobody swept --
           # and `report` needs only to tell one state from another to count
           # calls a state.
           "state_hash": digest(state), "cached": hit,
           "answers": {qid: {"branch": a.word, "raw": a.raw, "why": a.why}
                       for qid, a in answers.items()}}
    if why:
        row["why"] = why
    return Reading(answers, model, latency,
                   log_call(row, env, cwd) if log else "not logged here: the "
                   "row is `judge`'s, one per reading", hit, answered_by)


def _answer(state, questions, env, timeout, cache=True, cwd=None):
    """(the answers, the model that answered, why the whole call failed or "",
    whether a stored answer was replayed, which endpoint answered).

    EVERY PATH THAT SENDS NOTHING ANSWERS `none`, and that is the whole of the
    endpoint rule: the word is earned by a response and by nothing else.
    Every path here is one `ask` names; `ask` owns the ones it does not."""
    # THE BUDGET IS READ FIRST, before the key and before the endpoint: an
    # oversize state is the caller's own bug and needs neither to be known.
    size = len(json.dumps(state).encode("utf-8"))
    if size > STATE_BUDGET:
        why = (f"the state is {size} bytes, over the {STATE_BUDGET}-byte "
               f"budget, so it was not sent; slicing it is the reader's, and "
               f"this never truncates a state to fit")
        return unknown_all(questions, why), "", why, False, NONE_SENT
    # THE OPTION CEILING IS THE SECOND BUDGET, and it is read here for the same
    # reason: it is the caller's own bug and the endpoint answers it with an
    # HTTP 400, which reads exactly like an outage. A reading whose options are
    # built from the state grows with the tree, so a cut that fits today sends
    # 256 one command later and comes back `unknown` with nothing naming why.
    over = sorted(qid for qid, q in questions.items()
                  if len((q or {}).get("criteria") or {}) > OPTION_BUDGET)
    if over:
        why = (f"{', '.join(over)} offers more than the {OPTION_BUDGET} "
               f"options the endpoint takes, so it was not sent; narrowing the "
               f"option set is the reader's, and this never drops one to fit")
        return unknown_all(questions, why), "", why, False, NONE_SENT
    # THE STORE IS READ BEFORE THE KEY AND BEFORE THE ENDPOINT. A hit is an
    # answer this state, this wording and this model already gave, so a reader
    # with no key at all still gets it -- and a cut moved since costs nothing,
    # because the raw probabilities are what was stored and `branch` runs here.
    stored, word = (cache_read(cache_key(state, questions), env, cwd) if cache
                    else (None, NONE_SENT))
    if stored is not None:
        return read_answers(stored, questions) + (True, word)
    key, why = read_key(env)
    if why:
        return unknown_all(questions, why), "", why, False, NONE_SENT
    url, why = endpoint(env)
    if why:
        return unknown_all(questions, why), "", why, False, NONE_SENT
    out, why = post(request_body(state, questions), key, url, timeout)
    if why:
        return unknown_all(questions, why), "", why, False, NONE_SENT
    if not isinstance(out, dict):
        why = "the response is not an object"
        return unknown_all(questions, why), "", why, False, NONE_SENT
    word = endpoint_word(url)
    answers, model, why = read_answers(out, questions)
    # ONLY AN ANSWER FROM THE PINNED MODEL IS STORED. One from another version
    # is `unknown` here and would be `unknown` on every replay, so storing it
    # would cache a failure.
    if cache and not why:
        cache_write(cache_key(state, questions), out, word, env, cwd)
    return answers, model, why, False, word


def read_answers(out, questions):
    """(the answers, the model that answered, why) for one decoded response,
    from the endpoint or from the store. ONE READER, so a replayed answer takes
    exactly the branches a fresh one takes."""
    if out.get("model") != MODEL:
        model = str(out.get("model"))
        why = (f"`{model}` answered where `{MODEL}` is pinned; a band "
               f"measured under one version says nothing about another")
        return unknown_all(questions, why), model, why
    given = out.get("answers")
    given = given if isinstance(given, dict) else {}
    answers = {}
    for qid, spec in questions.items():
        raw = given.get(qid)
        raw = raw if isinstance(raw, dict) else None
        word, note = branch(spec, raw)
        answers[qid] = Answer(word, raw, note)
    return answers, out["model"], ""


# ----------------------------------------------------------------- the registry
# THE ONE HOME OF A QUESTION, as data. A reader names a GROUP and hands its
# state; every question of that group goes in one call, and each answer comes
# back with the tier its entry declares and what that tier does with it. No
# script writes a question inline, and `campaign-jev-test.py` refuses one that
# does.
REGISTRY = HERE / "jev" / "readings.json"
CORPUS = HERE / "jev" / "corpus"
# THE THREE TIERS, in the order they are earned. A reading enters at `shadow`,
# where it costs the reader nothing and only the log grows; it moves up by a
# DECISION its entry cites, never by a script.
SHADOW, ADVISE, ACTS = "shadow", "advise", "act"
TIERS = (SHADOW, ADVISE, ACTS)
# WHAT A VERDICT ASKS OF ITS READER. `nothing` at `shadow` and for every
# `unknown`; `show` at `advise`; at `act`, the reversible thing at high
# confidence, the question to a person at medium, and nothing below that.
SHOW, ASK, NOTHING = "show", "ask", "nothing"

# One reading's answer: the branch, the raw value, why, the entry's tier, and
# what the tier asks of the reader.
Verdict = namedtuple("Verdict", "word raw why tier does")
# One `judge` call: a verdict per reading, the model, the latency, the call id
# every log row of the call carries, and the sentence about those rows.
Judged = namedtuple("Judged", "verdicts model latency call logged")


# ------------------------------------------------------ THE BOUNDS ON AN `act`
# FOUR, AND THEY ARE READ WHERE THE REGISTRY IS LOADED, so an entry that breaks
# one never reaches a reader (DECISION 5714078253). A tier is a promise about
# what a typed guess may do, and a promise nothing reads is prose.
#
#   a  an act never moves a label a person alone moves: `standing` and
#      `backlog` are the owner's hold, and `bound:` and `campaign:` are the
#      campaign's own identity. Nothing here can observe that a person changed
#      their mind, which is why those labels are theirs.
#   b  an act is never a claim, a release, a merge, a close, a launch or a
#      retire. Each has an ACTOR in the model -- a session, a planner, a
#      person -- and a judgment is not one of them.
#   c  a write a judgment causes is made by the CALLING READER'S OWN SESSION,
#      through `gh` as that session, so `check-campaign-claim.py` judges it by
#      that session's role and claim. This module therefore carries out no act
#      and runs no command an entry names: an entry that hands one over would
#      be a path around the guard, and is refused.
#   d  on a `BLOCKED`, the ceiling is `advise` plus a route label. The owner's
#      answer to a `BLOCKED` is the planner's `DECISION`
#      (`EscalationGoesThroughAPlanner`), so no reading at any tier may post a
#      comment opening `DECISION`.
ACT_VERBS = ("label", "comment", "rank", "route")
# What an act declares, all four: what it does, how it is undone, and the cuts
# `does` reads. A missing cut is a KeyError there, so it is refused at load.
ACT_FIELDS = ("what", "undo", "act_over", "ask_over")
# The labels only a person moves, by exact name and by prefix.
PERSON_LABELS = ("standing", "backlog")
PERSON_LABEL_PREFIXES = ("bound:", "campaign:")
# The events that have an actor. Named here so the refusal can name the bound;
# none of them is an `ACT_VERBS` either, which is the same rule stated once as
# an allow-list and once as the refusal a reader reads.
NEVER_ACTED = ("claim", "release", "merge", "close", "launch", "retire")
# What an entry may not hand this module: a command line to run would be a
# write by THIS process rather than by the reader's session.
NEVER_IN_AN_ENTRY = ("command", "run", "gh", "shell")
DECISION_KIND = "DECISION"
BLOCKED_SUBJECT = "blocked"


def check_edges(reg):
    """Raise on the first entry whose two edges cross, naming which.

    READ AT LOAD, beside the bounds on an act, because a crossed pair is not a
    cut anybody measured: with `yes_over` at or under `no_under` the band has
    no middle and `uncertain` can never be answered, and with `certain_over` at
    or under `floor` the same. Nothing refused it before -- the suite asserted
    that both edges are PRESENT and never that they are in order -- and every
    edge here has now been moved twice by a measurement (pr#474 REVIEW note 5).

    A reading declaring NEITHER edge is untouched: that is the `shadow` shape,
    and the suite's "a reading with no thresholds is at shadow" case owns it."""
    for name, entry in sorted(reg.items()):
        cuts = entry.get("thresholds") or {}
        for lower, upper in (("no_under", "yes_over"), ("floor", "certain_over")):
            lo, hi = cuts.get(lower), cuts.get(upper)
            if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
                continue
            if hi <= lo:
                raise ValueError(
                    f"campaign-jev: `{name}`'s `{upper}` is {hi} and its "
                    f"`{lower}` is {lo}; the upper edge of a band sits ABOVE "
                    f"the lower one, or the band has no middle and "
                    f"`{UNCERTAIN}` can never be answered")
        # AND THE PER-ITEM SHAPE, read at the same moment and for the same
        # reason: a reading asked per item whose `compose` says nothing is one
        # whose questions nobody can build, and finding that out at the call
        # would cost a reader its judgment in the middle of a commit.
        compose_of(entry)
    return reg


def check_act_bounds(reg):
    """Raise on the first entry that breaks a bound, naming which.

    READ AT LOAD, not at the act: a registry the tree committed with a bad
    entry must fail the suite and the first reader, not the one call that
    happens to clear its threshold."""
    for name, entry in sorted(reg.items()):
        act = entry.get("act")
        # BOUND d FIRST AND FOR EVERY TIER: a `DECISION` Jev wrote is one
        # nobody made, whatever confidence it carried.
        if act and str(act.get("opens", "")).upper() == DECISION_KIND:
            raise ValueError(
                f"campaign-jev: `{name}`'s act opens a `{DECISION_KIND}` "
                f"comment; bound d -- the answer to a BLOCKED is a planner's "
                f"DECISION and never a judgment's, at any tier")
        if entry.get("tier") != ACTS:
            continue
        if not act:
            raise ValueError(f"campaign-jev: `{name}` is at tier `{ACTS}` with "
                             f"no `act`")
        # THE FOUR AN ACT IS MADE OF, refused here rather than by `does`, which
        # would meet a missing cut as a KeyError on the one call that cleared
        # its threshold -- the failure furthest from the entry that caused it.
        for field in ACT_FIELDS:
            if field not in act:
                raise ValueError(
                    f"campaign-jev: `{name}` is at tier `{ACTS}` with no "
                    f"`{field}`; an act says what it does, how it is undone, "
                    f"and the two cuts it acts and asks over")
        for field in NEVER_IN_AN_ENTRY:
            if field in act:
                raise ValueError(
                    f"campaign-jev: `{name}`'s act carries `{field}`; bound c "
                    f"-- a write a judgment causes is made by the calling "
                    f"reader's own session through the ordinary guarded path, "
                    f"so no entry hands this module a command to run")
        verb = act.get("verb")
        if verb in NEVER_ACTED:
            raise ValueError(
                f"campaign-jev: `{name}`'s act is a `{verb}`; bound b -- a "
                f"claim, a release, a merge, a close, a launch and a retire "
                f"each have an actor, and a judgment is not one")
        if verb not in ACT_VERBS:
            raise ValueError(f"campaign-jev: `{name}`'s act verb `{verb}` is "
                             f"not one of {', '.join(ACT_VERBS)}")
        label = act.get("label", "")
        if verb == "label" and (label in PERSON_LABELS
                                or label.startswith(PERSON_LABEL_PREFIXES)):
            raise ValueError(
                f"campaign-jev: `{name}`'s act moves `{label}`; bound a -- "
                f"{', '.join(PERSON_LABELS)} and the `bound:`/`campaign:` "
                f"labels are a person's alone")
        if entry.get("subject") == BLOCKED_SUBJECT and verb != "label":
            raise ValueError(
                f"campaign-jev: `{name}` reads a `{BLOCKED_SUBJECT}` at tier "
                f"`{ACTS}` with a `{verb}`; bound d -- there the ceiling is "
                f"`{ADVISE}` plus a route label")
    return reg


def load_registry(path=None):
    """The readings by name, with the bounds on an act read before any of them
    is handed out. A registry that will not read RAISES: it is this tree's own
    committed file, so an unreadable one is a broken checkout and not a model
    that failed to answer."""
    path = Path(path) if path else REGISTRY
    return check_edges(
        check_act_bounds(json.loads(path.read_text(encoding="utf-8"))))


def wording(entry):
    """The hash of the question as the model is sent it, 12 hex.

    COMPUTED AND NEVER HAND-KEPT. A band belongs to a wording, so a reworded
    question must not be able to keep the band measured for the old one: the
    log and every `seen` row carry this, and the suite refuses an entry whose
    declared `bands.wording` is not the hash of the question beside it."""
    text = json.dumps(entry["question"], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# WHERE THE ITEM'S NAME GOES in a question asked per item. The id is a KEY of
# the request body and no part of the question, so a fan-out whose instructions
# did not name the item would ask one question n times and get one answer n
# times.
ITEM_MARK = "{item}"
# WHERE A `choice`'s OPTIONS COME FROM WHEN THE ENTRY CANNOT HOLD THEM. An
# entry names a state field here, and one option is built per key of that
# field, the key's value being that option's description. The reading that
# needs it asks which OPEN CAMPAIGN's Scope covers a filing: the option set is
# the campaigns open on the day of the call and their Scopes are their own
# prose, neither of which a committed file can state.
#
# WHAT THE WORDING THEN PINS is the instructions and the entry's OWN options --
# the no-match one -- and not the built ones, because `wording()` hashes the
# entry's question as declared. That is the honest hash for this shape: a band
# measured under one campaign set is a band over those Scopes, which is said in
# the entry's `bands` rather than hidden. The built options travel with the
# case all the same, in the state field they were built from, so a case is
# re-askable with the option set it was asked under.
OPTIONS_FROM = "options_from"


def options_of(entry, state=None):
    """The `choice` options as the model is sent them: one per key of the state
    field `options_from` names, plus the entry's own.

    THE ONE READER of that rule, because two ask it -- `question_of`, which
    sends them, and the suite's "every case fits its entry", which checks a
    case's truth against the words the reading could have answered. A second
    copy would let a case be admitted for an option the call never offered.

    THE ENTRY'S OWN WIN A NAME COLLISION, so a campaign that ever took the slug
    `none` could not overwrite the no-match option's description."""
    question = entry.get("question") or {}
    criteria = dict(question.get("criteria") or {})
    field = question.get(OPTIONS_FROM)
    if not field:
        return criteria
    given = (state or {}).get(field)
    built = ({str(k): str(v) for k, v in given.items()}
             if isinstance(given, dict) else {})
    built.update(criteria)
    return built


# HOW A READING ASKED PER ITEM PUTS THE ITEM INTO ITS QUESTION, declared
# BESIDE `question` and never inside it: `wording()` hashes the question block,
# so a shape written in there would move every band's hash without changing one
# word the model reads.
#
# `where` is where the item's TEXT travels, and it decides the state as well,
# because an item the question carries is not sent twice:
#
#   state     the state carries the items, and the instructions name the one
#             being asked by its KEY, at `{item}`; the model reads the text out
#             of the state itself
#   question  the instructions carry the item's TEXT, and every field it came
#             from is withheld from the state the call sends
#   table     the items are the entry's OWN table, named by `table`, and each
#             one's words fill placeholders across the whole question
#   call      the reader makes one CALL an item and the item is that call's
#             state, so this asks one question and fans out nothing
#
# `as` says how, and only `question` has one. A MAP of `{placeholder}` to a
# state field splices each one's item into the instructions -- a reading may
# take more than one, as `done-report-claim` takes the condition and the REPORT
# line that answers it -- and a plain word instead puts the item's text under
# that key of an instructions OBJECT.
#
# THE ITEM SOURCE NEED NOT BE A STATE FIELD. `state.fields` is the slice ONE
# CASE carries, and a case of a per-item reading is one item -- so
# `docstring-claims` names `paragraph` and `pred` and cuts its claims out of
# the paragraph, while `model-comment` names the claim it was asked about. Both
# withhold the source from the call, so both send what they sent before.
COMPOSE = "compose"
IN_STATE, IN_QUESTION, FROM_TABLE, ONE_CALL = "state", "question", "table", "call"
WHERE = (IN_STATE, IN_QUESTION, FROM_TABLE, ONE_CALL)


def compose_of(entry):
    """How a per-item reading composes its question, or None where it is asked
    once. THE ONE READER of that rule: `question_of` sends by it and `judge`
    decides by it which fields the call carries and whether it fans out at all,
    and a second copy would let the question and the state disagree about where
    the item went."""
    if not (entry.get("question") or {}).get("per"):
        return None
    shape = entry.get(COMPOSE)
    if not isinstance(shape, dict) or shape.get("where") not in WHERE:
        raise ValueError(
            f"campaign-jev: a reading asked per "
            f"`{entry['question']['per']}` declares `{COMPOSE}` beside its "
            f"question, with `where` one of {', '.join(WHERE)}; it holds "
            f"{shape!r}")
    for where, field in ((IN_QUESTION, "as"), (FROM_TABLE, "table")):
        if shape["where"] == where and not shape.get(field):
            raise ValueError(
                f"campaign-jev: `{COMPOSE}.where` is `{where}`, so `{field}` "
                f"must say where the item comes from or goes; it holds "
                f"{shape.get(field)!r}")
    if shape["where"] == IN_QUESTION and isinstance(shape["as"], dict):
        loose = sorted(m for m in shape["as"] if not m.startswith("{"))
        if loose:
            raise ValueError(
                f"campaign-jev: `{COMPOSE}.as` maps a PLACEHOLDER to the state "
                f"field its item comes from; {', '.join(loose)} is no "
                f"placeholder")
    if shape["where"] == FROM_TABLE and not isinstance(
            entry.get(shape["table"]), dict):
        raise ValueError(
            f"campaign-jev: `{COMPOSE}.table` names `{shape['table']}`, which "
            f"is no table of this entry")
    built = shape.get("criteria")
    if built is not None:
        if built.get("template") not in (entry["question"].get("criteria") or {}):
            raise ValueError(
                f"campaign-jev: `{COMPOSE}.criteria.template` names "
                f"`{built.get('template')}`, which is no option of this "
                f"entry's question")
        bad = sorted(set((built.get("put") or {}).values()) - set(PUTS))
        if bad or not built.get("put"):
            raise ValueError(
                f"campaign-jev: `{COMPOSE}.criteria.put` fills each "
                f"placeholder from {' or '.join(PUTS)}; it names "
                f"{', '.join(bad) or 'nothing'}")
    return shape


# WHERE A BUILT OPTION'S WORDS COME FROM, for a `choice` whose options are one
# per item of a state field and whose descriptions are a TEMPLATE the entry
# holds under a braced key. `key` is the item's own name and `first line` the
# first line of its value -- which is what the model reads at the top of that
# item in the state, so the description names the file the hunk opens with and
# nothing the call did not send.
PUT_KEY, PUT_FIRST_LINE = "key", "first line"
PUTS = (PUT_KEY, PUT_FIRST_LINE)


def criteria_of(entry, state=None):
    """The `choice` criteria as the model is sent them: the entry's own, or one
    per item of the field `compose.criteria` names, each from the template.

    THE ONE READER of that rule, as `options_of` is of `options_from`. The two
    are different shapes on purpose: `options_from` takes each option's
    DESCRIPTION straight out of the state, and this fills a template the entry
    wrote, so the wording of an option stays in the registry where every other
    wording is."""
    shape = (compose_of(entry) or {}).get("criteria")
    written = entry["question"]["criteria"]
    if not shape:
        return written
    template = written[shape["template"]]
    built = {}
    for key, value in ((state or {}).get(shape["from"]) or {}).items():
        text = template
        for mark, source in shape["put"].items():
            text = text.replace(mark, key if source == PUT_KEY
                                else str(value).split("\n", 1)[0])
        built[key] = text
    for name, text in written.items():
        if name != shape["template"]:
            built[name] = text
    return built


def instructions_of(entry, item, state=None):
    """The instructions ONE ITEM of a per-item reading is asked with, for the
    two shapes that change nothing else about the question."""
    text = entry["question"]["instructions"]
    shape = compose_of(entry)
    if shape["where"] == IN_STATE:
        return text.replace(ITEM_MARK, str(item))
    how = shape["as"]
    if isinstance(how, dict):
        for mark, field in how.items():
            text = text.replace(
                mark, str(((state or {}).get(field) or {}).get(item)))
        return text
    return {"question": text,
            how: ((state or {}).get(entry["question"]["per"]) or {}).get(item)}


def filled_from_table(entry, spec, item):
    """The whole question with one row of the entry's table put into its
    placeholders. The substitution is over the question as JSON TEXT, because a
    row's words reach the criteria and their examples as well as the
    instructions, and each is escaped as JSON on the way in."""
    words = (entry[compose_of(entry)["table"]] or {}).get(item) or {}
    text = json.dumps({k: spec[k] for k in ("type", "instructions", "criteria")})
    for key, value in words.items():
        text = text.replace("{" + key + "}", json.dumps(value)[1:-1])
    return dict(spec, **json.loads(text))


def words_of(entry, verdict):
    """{item: Answer} for a per-item verdict, each raw answer branched.

    `judge` hands a fanned reading its raws and NO word, because what they add
    up to is the entry's `combine` and that is the reader's. The branch of ONE
    item is not: a reader that cut its own would be a second reader of the
    entry's edges, and the two would drift the first time a cut moved."""
    spec, whys = question_of(entry), verdict.why or {}
    out = {}
    for item, raw in (verdict.raw or {}).items():
        word, why = branch(spec, raw)
        # THE CALL'S OWN REASON WINS. `branch` can only say the response
        # carried no answer; the call knows WHY it carried none -- a closed
        # port, a timeout, a body that was not JSON -- and that sentence is
        # what a reader prints and a person acts on.
        out[item] = Answer(word, raw, whys.get(item) or why)
    return out


def item_fields(entry):
    """The state fields a per-item reading takes its items from: the ones the
    caller is asked for and the call does NOT send, because the question
    carries their text. THE ONE READER of that half of `compose.as`."""
    shape = compose_of(entry)
    if shape is None or shape["where"] != IN_QUESTION:
        return set()
    how = shape["as"]
    return set(how.values()) if isinstance(how, dict) \
        else {entry["question"]["per"]}


def items_of(entry, state=None):
    """The items one per-item reading is asked over, by key, or None where it
    is asked once. THE ONE READER of where they come from: the state's own
    field, or the entry's table."""
    shape = compose_of(entry)
    if shape is None or shape["where"] == ONE_CALL:
        return None
    if shape["where"] == FROM_TABLE:
        return entry[shape["table"]]
    return (state or {}).get(entry["question"]["per"])


def question_of(entry, item=None, state=None):
    """The spec `ask` and `branch` read: the question as sent, plus the cuts,
    which are this tree's reading of the answer and are never sent.

    `item` is the key of a reading asked per item, put into the instructions
    the way the entry's `compose` declares -- by replacement and not by
    `format`, so a question holding a brace of its own is not a formatting
    error.

    `state` is what a reading whose options are BUILT is built from, and where
    an item composed into the QUESTION reads its text; it is ignored by every
    other reading, so a caller that does not pass it changes nothing for the
    entries that declare no `options_from` and no per-item shape."""
    spec = dict(entry["question"])
    spec.update(entry.get("thresholds") or {})
    if spec.pop(OPTIONS_FROM, None):
        spec["criteria"] = options_of(entry, state)
    elif "criteria" in spec:
        spec["criteria"] = criteria_of(entry, state)
    if item is None:
        return spec
    if compose_of(entry)["where"] == FROM_TABLE:
        return filled_from_table(entry, spec, item)
    spec["instructions"] = instructions_of(entry, item, state)
    return spec


def group_of(reg, group):
    """The entries of one group, by name, or a raise. A group with no entry is
    a reader asking for a reading nobody declared -- the caller's bug."""
    found = {n: e for n, e in reg.items() if e.get("group") == group}
    if not found:
        raise ValueError(f"campaign-jev: no reading of group `{group}` in "
                         f"{REGISTRY}; the groups are "
                         f"{sorted({e.get('group') for e in reg.values()})}")
    return found


def state_fields(entries):
    fields = set()
    for e in entries.values():
        fields |= set(e["state"]["fields"])
    return fields


def confidence(entry, raw):
    """How concentrated the answer is, on the one scale the tiers read: the
    `choice`'s own `confidence`, and for a `noul` the distance from the coin
    toss, since 0.05 is as decided an answer as 0.95."""
    if not isinstance(raw, dict):
        return None
    if entry["question"]["type"] == NOUL:
        value = raw.get(NOUL)
        return None if not isinstance(value, (int, float)) else max(value,
                                                                   1 - value)
    value = raw.get("confidence")
    return None if not isinstance(value, (int, float)) else value


def band_of(entry, case):
    """(the band key a case is held to, why there is none). THE ONE READER, for
    the join, the drift reader and `--live` alike.

    IT WAS THREE, AND THEY DISAGREED. `corpus join` wrote a case with no `band`,
    the drift reader fell back to the TRUTH word, and for a `choice` the truth
    is an option name and never a band name -- so every case the join added was
    drift-blind for good, at any confidence, while the evidence row and the
    agreement share went on counting it.

    An explicit `band` WINS, because it was measured: `k442`'s truth is a real
    option and its band is `unsure`, which no rule over the truth word could
    derive. Where there is none the band is derived -- a two-word reading's is
    its truth, and a `choice`'s is `confident` for a real option -- and where it
    cannot be derived the case is held to NO band and the reason is returned,
    so a reader lists it rather than silently skipping it. A no-match case is
    one of those: its confidence is the no-match option's and says nothing
    about how decided a real option was."""
    if case.get("band"):
        return case["band"], ""
    if case.get("role") == "no-match":
        return None, ("a no-match case: its confidence is the no-match "
                      "option's and no real option's")
    truth = case.get("truth")
    if not isinstance(truth, str):
        return None, "its truth is not one word"
    cuts = entry.get("thresholds") or {}
    if entry["question"]["type"] == NOUL or cuts.get("option"):
        if truth in ("yes", "no"):
            return truth, ""
        return None, f"`{truth}` is neither yes nor no"
    # THE CASE'S OWN OPTION SET, not the entry's: a reading whose options are
    # built holds the no-match option alone in its entry, so reading that
    # would hold every one of its cases to no band and call none of them
    # drift. `options_of` is the one reader of that rule.
    options = options_of(entry, case.get("state"))
    if truth in options and truth != cuts.get("no_match"):
        return "confident", ""
    return None, f"`{truth}` names no option of the set"


def held_to_a_band(case):
    """May this case's runs set or test the reading's band? THE ONE READER of
    that rule, because the drift line, the live run's loop and its `--record`
    history all ask it -- and the three disagreed.

    A CASE CODE SETTLED IS HELD TO NO BAND. A band is what the states production
    SENDS come back at, and the prefilter's whole job is that this one is never
    sent, so a value from it can neither widen an edge nor be called drift.
    `report` already counts such a case as code's rather than as one Jev got
    wrong (DECISION 5715993782). The live loop knew this and the drift line did
    not: `work-kind-0873f14b0769`, an issue whose `kind:` label settles it, came
    back at 0.40 against a `confident` band of [0.53, 1.0] and was printed as
    this reading's drift on every `report`.

    A NO-MATCH CASE IS EXCEPTED -- `verb-first`'s is settled too, and where it
    lands is the whole point of keeping it -- and `band_of` holds it to no band
    anyway, with its own reason."""
    return settled_of(case) is None or case.get("role") == "no-match"


def band_value(entry, raw):
    """The number a BAND is over, which is not `confidence`'s: a `noul`'s own
    value, and a `choice`'s confidence. The two differ for a `noul` -- 0.04 is
    a decided `no`, so `confidence` folds it to 0.96 -- and a drift reader that
    used the folded number compared every `no` against the `yes` band and
    called the whole corpus drifted."""
    if not isinstance(raw, dict):
        return None
    key = NOUL if entry["question"]["type"] == NOUL else "confidence"
    value = raw.get(key)
    return value if isinstance(value, (int, float)) else None


# ----------------------------------------------------------- THE ADDRESS NOUL
# A READING WHOSE STATE HOLDS SOMEBODY ELSE'S PROSE CARRIES A SECOND QUESTION IN
# THE SAME CALL: does that prose speak to whoever is judging it? rule-check#471
# step 4 measured it -- all ten hostile states went `uncertain` and no clean
# twin did -- and DECISION 5717901390 set the rule: code reads the address
# first, and at 0.5 or over the guarded reading answers `uncertain`, whatever
# it said. A `criteria` sentence telling the model to ignore such text is NOT a
# defence and was measured not to be one.
#
# THE NUMBER LIVES HERE AND NOWHERE ELSE, and it is not a threshold of the
# address entry: an entry declaring `yes_over` 0.5 and `no_under` 0.5 is a band
# with no middle, which `check_edges` refuses. So the address entry declares no
# cut -- it is at `shadow` and has no word to earn -- and this reads its raw
# value.
ADDRESS_OVER = 0.5
# The entry field naming the group-mate that guards a reading. The next state
# that carries the address declares it and reuses this reader.
ADDRESS_FIELD = "guarded_by"


def address_word(reg, name, verdicts):
    """(the word reading `name` reaches once its address has been read, why).

    THE ONE READER of `ADDRESS_OVER`, for every reading that declares a
    `guarded_by`. A reading that declares none comes back with its own word and
    an empty reason, so a caller may ask this of any reading.

    AN ADDRESS THAT COULD NOT BE READ IS `uncertain` TOO. The guard is what
    stands between the answer and text written to move it; a guard that did not
    answer did not rule that text out, and reading its silence as clean is the
    direction this rule exists to refuse."""
    entry = reg.get(name) or {}
    held = verdicts.get(name)
    word = held.word if held is not None else UNKNOWN
    guard = entry.get(ADDRESS_FIELD)
    if not guard:
        return word, ""
    answer = verdicts.get(guard)
    value = band_value(reg.get(guard) or {},
                       answer.raw if answer is not None else None)
    if value is None:
        return UNCERTAIN, (f"the address `{guard}` gave no value, so the state "
                           f"was not read for text addressed to whoever judges "
                           f"it and no word of `{name}` is earned")
    if value >= ADDRESS_OVER:
        return UNCERTAIN, (f"the address `{guard}` is {value:.2f}, at or over "
                           f"{ADDRESS_OVER:.2f}: the state speaks to whoever "
                           f"judges it, so no word of `{name}` is earned")
    return word, (f"the address `{guard}` is {value:.2f}, under "
                  f"{ADDRESS_OVER:.2f}")


def does(entry, word, raw):
    """What the tier asks of the reader for this answer. A CALCULATION: no
    request, no clock, no file, so every branch has a case that spends
    nothing.

    A JEV ANSWER NEVER REFUSES, MERGES OR DELETES, whatever it returns here:
    `act` is a reversible thing the entry names and says how to undo, and the
    caller moves no exit status on any of the four words."""
    tier = entry.get("tier")
    if tier not in TIERS:
        raise ValueError(f"campaign-jev: tier `{tier}` is not one of "
                         f"{', '.join(TIERS)}")
    if word == UNKNOWN or tier == SHADOW:
        return NOTHING
    # A READING ASKED PER ITEM HAS NO WORD HERE, and what its answers add up to
    # is its entry's `combine`, which is the reader's code. So this asks nothing
    # of it beyond `show`: there is no single value to hold against an act cut.
    if word is None:
        return SHOW if tier == ADVISE else NOTHING
    if tier == ADVISE:
        return SHOW
    # AN `uncertain` NEVER ACTS. It is an answer that landed between the two
    # edges, so the word it would act on is the one the band says is not
    # earned; at `advise` it is shown, and above that it does nothing.
    if word == UNCERTAIN:
        return NOTHING
    act = entry.get("act") or {}
    value = confidence(entry, raw)
    if value is None:
        return NOTHING
    if value >= act["act_over"]:
        return ACTS
    if value >= act["ask_over"]:
        return ASK
    return NOTHING


def judge(group, state, read="", reader="", settled=None, key=None, flag=None,
          reg=None, env=None, cwd=None, timeout=TIMEOUT, log=True, cache=True,
          run=PRODUCTION):
    """One group, one state, ONE call: a `Verdict` per reading of the group.

    `state` carries exactly the fields the group's entries name, and a MISSING
    or an EXTRA one RAISES rather than answering `unknown`. Both are the
    reader's bug and not the model's answer: an extra field is state the bands
    were never measured with, and a missing one is a question asked about
    nothing. The byte budget is `ask`'s and still holds.

    `settled` is what CODE decided -- the prefilter's word -- as
    {reading: word}. Those readings are never asked, and their rows carry the
    word and the model that never saw them, so the log counts what code saved.
    For a reading asked PER ITEM the word may instead be a {item: word} dict,
    and only the items it names are settled: a prefilter that clears six of a
    review's eight findings leaves two to ask, in the same one call.

    A READING WHOSE `question.per` NAMES A STATE FIELD IS ASKED ONCE PER KEY OF
    THAT FIELD, all in this same call, under the question ids `<reading>#<key>`.
    Its `Verdict` carries {key: raw} and NO word: what those answers add up to
    is the entry's `combine`, which is code's and the reader's, never this
    module's -- so `does` asks nothing of the reader for it either.

    `key` is the join key AS FIELDS -- `repo`, `issue`, and `comment` or
    `pull_request` where there is one -- because every join is "the later fact
    on that number" and a number inside a label is not a field anything can
    read. A COMMIT-TIME READER'S KEY IS `repo`, `commit` AND `path`: it judges
    one file's text at `pre-commit`, before its own commit exists, so the sha
    it can name is the one it is committing onto and the later fact is what
    happened to that file after it.

    `flag` is what the reader computed from the answers,
    {"code": ..., "moved_by": ...}: the flag and which answer moved it. It may
    be a CALLABLE `(reading, raw) -> flag`, because a reader cannot compute a
    flag from answers it has not got back yet.

    ONE LOG ROW PER READING, so a row is a case-to-be on its own: the call id
    ties the rows of one call back together."""
    reg = load_registry() if reg is None else reg
    entries = group_of(reg, group)
    # THE ITEMS ARE ASKED FOR AND NOT ALWAYS SENT. A reading whose `compose`
    # puts the item's text in the QUESTION is handed its items here all the
    # same -- there is nowhere else they could come from -- and the field they
    # came from is then WITHHELD from the call, because an item carried by the
    # question is not sent twice. So the caller owes the group's fields plus
    # every item source, and the endpoint is sent the fields less those.
    sources = set().union(*(item_fields(e) for e in entries.values())) \
        if entries else set()
    fields = state_fields(entries)
    want, given = fields | sources, set(state)
    if want != given:
        raise ValueError(
            f"campaign-jev: the state of group `{group}` must carry exactly "
            f"{sorted(want)}; missing {sorted(want - given) or 'none'}, extra "
            f"{sorted(given - want) or 'none'}")
    carried = fields - sources
    # A NUMBER WITHOUT ITS REPOSITORY IS NOT A JOIN KEY. A member repository's
    # pull request closes a sub-issue on this tracker, and its number collides
    # with this tracker's own -- 33 of 199 closing links are a member's
    # (rule-check#460 NOTE 5713928884). A join that asked "what happened to
    # #28" would read whichever #28 it happened to find.
    key = dict(key or {})
    numbered = [k for k in ("issue", "pull_request", "comment") if k in key]
    if numbered and not key.get("repo"):
        raise ValueError(
            f"campaign-jev: the join key names {', '.join(numbered)} with no "
            f"`repo`; a number alone names no issue when a member "
            f"repository's numbers collide with this tracker's")
    # A COMMIT-TIME READING IS KEYED BY THE SHA AND THE PATH, and by both. The
    # reader runs at `pre-commit` over the index, so the sha it can name is the
    # one it is committing ONTO and the path is the file it judged; the later
    # fact is what happened to THAT FILE after THAT COMMIT. A sha with no
    # repository names no checkout to read it in, and a sha with no path leaves
    # the join guessing its way around a whole commit's diff.
    if "commit" in key:
        for field in ("repo", "path"):
            if not key.get(field):
                raise ValueError(
                    f"campaign-jev: the join key names `commit` with no "
                    f"`{field}`; a commit-time reading judges one file's text "
                    f"at the sha it is committing onto, so its key is the "
                    f"repository, the sha and the path, and all three")
    settled = dict(settled or {})
    for name in settled:
        if name not in entries:
            raise ValueError(f"campaign-jev: `{name}` is settled but is no "
                             f"reading of group `{group}`")
    asked, fanned = {}, {}
    for name, entry in entries.items():
        per = (entry.get("question") or {}).get("per")
        given = settled.get(name)
        items = items_of(entry, state)
        if items is None:                # asked once: no `per`, or one a call
            if name not in settled:
                asked[name] = question_of(entry, state=state)
            continue
        if not isinstance(items, dict):
            raise ValueError(
                f"campaign-jev: `{name}` is asked per `{per}`, so the items "
                f"`{compose_of(entry)['where']}` holds must be an object of "
                f"one item per question; they are a "
                f"{type(items).__name__}")
        if given is not None and not isinstance(given, dict):
            continue                     # one word settles the whole reading
        # THE ITEM MUST BE IN THE QUESTION, and the entry's `compose` says
        # how. The id is a key of the body and no part of the question, so a
        # shape that named the item nowhere would ask the same question once
        # per item and get one answer n times.
        shape = compose_of(entry)
        marks = ([ITEM_MARK] if shape["where"] == IN_STATE
                 else list(shape["as"]) if shape["where"] == IN_QUESTION
                 and isinstance(shape["as"], dict) else [])
        missing = [m for m in marks
                   if m not in entry["question"]["instructions"]]
        if missing:
            raise ValueError(
                f"campaign-jev: `{name}` is asked per `{per}` and composes its "
                f"item at {', '.join(missing)}, which its instructions do not "
                f"name; the question id is a KEY of the request body and no "
                f"part of the question, so without it the same question would "
                f"be asked once per item")
        fanned[name] = items
        cleared = given or {}
        for item in items:
            if item not in cleared:
                asked[f"{name}#{item}"] = question_of(entry, item, state)
    if asked:
        reading = ask(reader or "campaign-jev.judge", read,
                      {k: v for k, v in state.items() if k in carried}, asked,
                      env=env, cwd=cwd, timeout=timeout, log=False, cache=cache,
                      run=run)
    else:
        reading = Reading({}, "", 0.0, "", False, NONE_SENT)
    call = uuid.uuid4().hex[:12]
    at = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")
    verdicts, notes = {}, []
    for name, entry in sorted(entries.items()):
        if name in fanned:
            # ONE VERDICT PER READING STILL, carrying the per-item answers and
            # no word: combining them is the entry's `combine`, which code does.
            # THE RAWS AND THE WHYS ARE BOTH PER ITEM. A joined string read
            # back to one item was a parse nobody could do safely, and the
            # reason a question went `unknown` -- which is the whole of what
            # a failed call leaves behind -- belongs to that item alone.
            raw, whys = {}, {}
            for item in fanned[name]:
                answer = reading.answers.get(f"{name}#{item}")
                if answer is None:
                    continue
                raw[item] = answer.raw
                if answer.why:
                    whys[item] = answer.why
            word, why = None, whys
            verdicts[name] = Verdict(word, raw, why, entry["tier"],
                                     does(entry, word, raw))
        elif name in settled:
            word, raw, why = settled[name], None, ""
            verdicts[name] = Verdict(word, raw, why, entry["tier"], NOTHING)
        else:
            answer = reading.answers[name]
            word, raw, why = answer.word, answer.raw, answer.why
            verdicts[name] = Verdict(word, raw, why, entry["tier"],
                                     does(entry, word, raw))
        row = {"at": at, "call": call, "reader": reader or "campaign-jev.judge",
               "read": read, "subject": read, "reading": name,
               "wording": wording(entry), "state": state,
               "settled": settled.get(name), "tier": entry["tier"],
               "does": verdicts[name].does, "asked": MODEL,
               "answered": reading.model, "latency": round(reading.latency, 3),
               "state_hash": digest(state), "cached": reading.cached,
               "endpoint": reading.endpoint, RUN_FIELD: run,
               "branch": word, "raw": raw, "why": why,
               "flag": flag(name, raw) if callable(flag) else flag}
        row.update({k: v for k, v in (key or {}).items() if v is not None})
        notes.append(log_call(row, env, cwd) if log else "not logged")
    logged = (notes[0] if len(set(notes)) == 1 and notes
              else "; ".join(notes) or "nothing to log")
    return Judged(verdicts, reading.model, reading.latency, call,
                  f"{len(notes)} row(s) {logged}")


# ------------------------------------------------------------------ the joins
# WHAT HAPPENED AFTER THE ANSWER, read from GitHub, one function per reading
# and named by the entry's `join`. Each answers (truth, evidence, why it could
# not say yet): a row it cannot label STAYS in the log and is counted, because
# a row dropped before it is joined is a case nobody will ever have.


def fetch_issue(repo, number, timeout=30):
    """One issue as `gh` gives it, or None. THE ONE FETCH, so an offline suite
    stubs this alone and every join is exercised against it.

    ITS COMMENTS COME WITH IT, in the same call, because two of the joins read
    what was said on the sub-issue AFTER the reading -- the next DECISION, the
    next REVIEW -- and a second call for them would double every fetch this
    command makes."""
    try:
        out = subprocess.run(
            ["gh", "issue", "view", str(number), "-R", repo, "--json",
             "title,body,state,stateReason,labels,comments"], capture_output=True,
            text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except ValueError:
        return None


def join_issue_title_kept(row, issue):
    """verb-first: is the issue's title still the one judged, after it closed?

    THE TWO HALVES ARE NOT EQUALLY STRONG, and the docstring is where that is
    said. A title REWRITTEN between the judgment and the close is the owner
    correcting the shape, so the state as judged is labelled `no`. A title
    kept through the close is the weaker half -- nobody was asked -- and is
    labelled `yes`, which is why `label.from` records the join by name and the
    reader counts labels by where they came from."""
    if issue is None:
        return None, "", "the issue did not read"
    if str(issue.get("state", "")).upper() == "OPEN":
        return None, "", "still open: the title may change yet"
    judged = (row.get("state") or {}).get("title")
    if not judged:
        return None, "", "the row carries no title to compare"
    kept = issue.get("title") == judged
    return ("yes" if kept else "no",
            f"{row.get('repo')}#{row.get('issue')} closed with the title "
            f"{'kept' if kept else 'rewritten'}", "")


def join_issue_kind_label(row, issue):
    """work-kind: which `kind:` label the issue carries now. The owner's word,
    which is the strongest label this tree has for this reading."""
    if issue is None:
        return None, "", "the issue did not read"
    names = [(l or {}).get("name", "") for l in issue.get("labels") or []]
    kinds = [n[len("kind:"):] for n in names if n.startswith("kind:")]
    if len(kinds) != 1:
        return None, "", (f"{len(kinds)} `kind:` label(s), so the owner's word "
                          f"is not one word")
    return kinds[0], f"label `kind:{kinds[0]}` on {row.get('repo')}#" \
                     f"{row.get('issue')}", ""


def join_filing_parent_slug(row, issue):
    """filing-scope-covers: which campaign the filing was actually filed under.

    THE LABEL IS THE ROW'S OWN `--parent`, resolved to a slug. The reading runs
    at `gh issue create`, before the new issue has a number, so the row's
    `issue` field is the PARENT the create named and not the filing -- which is
    why this reads the `campaign:` label of what it fetched rather than
    anything about a later state. A filer picks the parent by the same reading
    the model is asked to make, so the parent is the strongest label this tree
    has for it and it is available at once.

    A PARENT WHOSE SLUG WAS NOT AMONG THE OPTIONS IS NOT LABELLED. The options
    are the campaigns with a directory on the machine that made the call, and
    no answer of that call could have named a campaign it was never offered;
    labelling it anyway would write a case whose truth is a word the reading
    could not answer, which the suite refuses and a band would be fitted to."""
    if issue is None:
        return None, "", "the parent issue did not read"
    names = [(l or {}).get("name", "") for l in issue.get("labels") or []]
    slugs = [n[len("campaign:"):] for n in names if n.startswith("campaign:")]
    if len(slugs) != 1:
        return None, "", (f"{len(slugs)} `campaign:` label(s) on the parent, so "
                          f"which campaign it is is not one word")
    offered = (row.get("state") or {}).get("campaigns") or {}
    if slugs[0] not in offered:
        return None, "", (f"the parent is `{slugs[0]}`, which was not among the "
                          f"{len(offered)} option(s) this call offered "
                          f"({', '.join(sorted(offered)) or 'none'}): no answer "
                          f"could have named it")
    return slugs[0], (f"label `campaign:{slugs[0]}` on {row.get('repo')}#"
                      f"{row.get('issue')}, the parent the create named"), ""


def load_sibling(name):
    """A sibling script as a module, by path: these are scripts, not a package.
    Loaded WHERE IT IS USED and never at import, because the sibling loads this
    module the same way -- at the point of use -- and two module-level imports
    of each other would not resolve."""
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(HERE / name)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch_thread(repo, number, timeout=30):
    """One pull request's whole thread, oldest first, and its state -- or None.

    IT ASKS `check-merge-review.py`, which owns the thread read: both channels,
    each paginated in full, the id and the timestamp per row. Reading
    `issues/<n>/comments` here instead was a SECOND reader of that rule and it
    had already drifted -- it missed every REVIEW posted with
    `gh pr review --comment -b`, so a finding that a later review-channel
    REVIEW raised again was labelled `disposed` into the corpus at the merge
    (pr#474 REVIEW issuecomment-5718228578).

    THE ONE FETCH for a pull request, as `fetch_issue` is for an issue, so an
    offline suite stubs one function per subject."""
    try:
        reader = load_sibling("check-merge-review.py")
        found, why = reader.bodies_of(repo, number)
        if why or found is None:
            return None
        head = subprocess.run(
            ["gh", "pr", "view", str(number), "-R", repo, "--json", "state"],
            capture_output=True, text=True, timeout=timeout)
    except Exception:  # noqa: BLE001 -- a thread that would not read is None
        return None
    if head.returncode != 0:
        return None
    try:
        state = (json.loads(head.stdout) or {}).get("state") or ""
    except ValueError:
        return None
    return {"comments": [{"where": where, "author": author, "body": body,
                          "id": cid, "at": at}
                         for where, author, body, cid, at
                         in reader.in_time_order(found)],
            "state": state}


def re_raised(finding, body):
    """Is this finding raised again in that later REVIEW? Its id named as an
    item, or half its words carried -- rule-check#460 set C's own rule, so the
    label a case gets here is the label the survey's numbers were measured
    against."""
    return overlap(body, finding) >= 0.5


def join_thread_refinding(row, thread):
    """C-report-disposes-finding: did a LATER REVIEW raise the finding again?

    THE TWO HALVES ARE NOT EQUALLY STRONG, as `join_issue_title_kept`'s are not.
    A finding raised again after this REPORT is a finding the REPORT did not
    dispose, and that half is strong. A pull request that MERGED with no later
    REVIEW is the weak half -- nobody looked again -- and it is what labels the
    disposed class, which is why it waits for the merge rather than reading an
    open thread as agreement."""
    if thread is None:
        return None, "", "the thread did not read"
    findings = (row.get("state") or {}).get("findings") or {}
    if not findings:
        return None, "", "the row carries no finding to label"
    at = row.get("at") or ""
    later = [c.get("body") or "" for c in thread.get("comments") or []
             if (c.get("at") or "") > at
             and (c.get("body") or "").lstrip().startswith("REVIEW ")]
    if not later:
        if str(thread.get("state", "")).upper() != "MERGED":
            return None, "", ("no REVIEW after this REPORT yet, and the pull "
                              "request has not merged")
        return ({k: "disposed" for k in findings},
                f"{row.get('repo')} pr#{row.get('pull_request')} merged with no "
                f"REVIEW after this REPORT", "")
    body = "\n".join(later)
    truth = {k: ("undisposed" if re_raised(text, body) else "disposed")
             for k, text in findings.items()}
    again = sorted(k for k, v in truth.items() if v == "undisposed")
    return (truth,
            f"{len(later)} REVIEW(s) after this REPORT on "
            f"{row.get('repo')} pr#{row.get('pull_request')}; "
            + (f"raised again: {', '.join(again)}" if again
               else "none of these findings raised again"), "")


def fetch_reopen(repo, number, timeout=30):
    """(when the pull request merged, the sub-issues it closes with their state
    and comments) -- or None.

    THE LAZY SECOND FETCH, and the only call either thread join makes beyond
    `fetch_thread`. It is taken for ONE BRANCH ONLY -- a pull request that
    merged with no later round -- because that is the one branch the thread
    itself cannot decide: whether the work came back is a fact of the sub-issue,
    not of the pull request. WHAT IT COSTS: one `gh pr view` plus one timeline
    call per closing reference, which on this tracker is one, ONCE PER PULL
    REQUEST a join run (`reopen_of`), and NOTHING for every other row -- a row
    with a fix round, a row on an open pull request, and a row with no REPORT
    never reach it.

    IT IS A MODULE-LEVEL NAME so an offline suite replaces it as it replaces
    `fetch_thread`; `cmd_corpus_join` routes the two SUBJECT fetches through
    its `args` and this one is not a subject, it is a second question about one.

    The closing reference's OWN repository is read off its url, never assumed to
    be the pull request's: a member repository's pull request closes a sub-issue
    on this base's tracker.

    A REOPEN IS AN EVENT AND NOT A STATE, so the timeline is what is read.
    Reading `gh issue view --json state` instead missed every sub-issue
    reopened and then CLOSED AGAIN -- which is the ordinary shape here, since
    work that came back gets done and the issue closes once more -- and the
    join then labelled the row `no` with an evidence sentence saying no
    sub-issue was reopened (pr#490 REVIEW 5721893225, F1). `kalaluthien/campaign-base#429`
    is that shape: reopened twice on 2026-09-14 and CLOSED now.

    IT COSTS WHAT THE STATE READ COST: one `gh pr view` plus ONE call per
    closing reference, because the timeline carries the comments beside the
    events and `--paginate` returns them as one array."""
    try:
        head = subprocess.run(
            ["gh", "pr", "view", str(number), "-R", repo, "--json",
             "mergedAt,closingIssuesReferences"],
            capture_output=True, text=True, timeout=timeout)
        if head.returncode != 0:
            return None
        found = json.loads(head.stdout) or {}
        issues = []
        for ref in found.get("closingIssuesReferences") or []:
            parts = str(ref.get("url") or "").split("/")
            where = ("/".join(parts[3:5]) if len(parts) > 5 else repo) or repo
            one = subprocess.run(
                ["gh", "api", "--paginate",
                 f"repos/{where}/issues/{ref.get('number')}/timeline"],
                capture_output=True, text=True, timeout=timeout)
            if one.returncode != 0:
                return None
            rows = json.loads(one.stdout) or []
            issues.append({
                "number": ref.get("number"), "repo": where,
                "reopened": [r.get("created_at") or "" for r in rows
                             if r.get("event") == "reopened"],
                "comments": [{"at": r.get("created_at") or "",
                              "body": r.get("body") or ""}
                             for r in rows if r.get("event") == "commented"]})
    except Exception:  # noqa: BLE001 -- a reopen that would not read is None
        return None
    return {"merged_at": found.get("mergedAt") or "", "issues": issues}


# ONE REOPEN FETCH PER PULL REQUEST A JOIN RUN. `cmd_corpus_join` dedups the
# SUBJECT fetches in its own `fetched` map, and this one is not a subject, so
# two rows on one pull request paid two `gh pr view`s (pr#490 REVIEW
# 5721893225, F5). The run clears this, so it is a run's memo and never a cache
# across runs -- a reopen that happened between two runs must still be seen.
REOPEN_SEEN = {}


def reopen_of(repo, number):
    """`fetch_reopen`, memoised for this join run. A `None` is memoised too:
    a subject that would not read this run will not read on the next row
    either, and asking again is the cost this exists to stop."""
    key = (repo, number)
    if key not in REOPEN_SEEN:
        REOPEN_SEEN[key] = fetch_reopen(repo, number)
    return REOPEN_SEEN[key]


def names_of(repo, pull_request, report_comment):
    """The patterns that NAME this pull request or its REPORT in a reopen's
    own words: `pr#<n>`, the pull request's url on that repository, and the
    REPORT comment's id -- which is also every form of that comment's url,
    since the url carries the id.

    NOT A BARE `#<n>`, which names no repository: five campaigns file onto one
    tracker and a member repository's numbers collide with this one's, which is
    the same reason AGENTS.md refuses a bare `#N` in prose.

    EACH ENDS ON A NON-DIGIT, so `pr#49` does not match `pr#490` and the id of
    one comment does not match a longer id starting with it. THE ID ALSO STARTS
    ON ONE, being the only pattern with no prefix of its own to anchor its left
    edge, so it does not match a longer id ending with it either."""
    out = [re.compile(rf"pr#{pull_request}(?!\d)"),
           re.compile(re.escape(f"{repo}/pull/{pull_request}") + r"(?!\d)")]
    if report_comment:
        out.append(re.compile(
            rf"(?<!\d){re.escape(str(report_comment))}(?!\d)"))
    return out


def join_report_next_round(row, thread):
    """unverified-done: what happened AFTER this REPORT?

    THE TWO HALVES ARE NOT EQUALLY STRONG, as `join_thread_refinding`'s are
    not. A FIX ROUND after this REPORT -- a later REVIEW on either channel and
    a REPORT answering it -- is work that came back, and so is the SUB-ISSUE
    the pull request closes REOPENED after the merge naming that pull request
    or that REPORT. Both are the strong half: something the REPORT said was
    done was not.

    A pull request that MERGED with neither is the WEAK half -- nobody looked
    again -- and it is what labels the verified class, which is why it waits
    for the merge rather than reading an open thread as agreement.

    A LATER REVIEW WITH NO REPORT AFTER IT IS NOT YET A FIX ROUND: the round is
    open, nobody has answered it, and reading it either way would label the
    case on a thread still moving."""
    if thread is None:
        return None, "", "the thread did not read"
    if not ((row.get("state") or {}).get("report") or "").strip():
        return None, "", "the row carries no REPORT to label"
    at = row.get("at") or ""
    later = [c for c in thread.get("comments") or [] if (c.get("at") or "") > at]
    where = f"{row.get('repo')} pr#{row.get('pull_request')}"
    for n, one in enumerate(later):
        if not (one.get("body") or "").lstrip().startswith("REVIEW "):
            continue
        if any((d.get("body") or "").lstrip().startswith("REPORT ")
               for d in later[n + 1:]):
            return "yes", (f"a fix round after this REPORT on {where}: a later "
                           f"REVIEW and a REPORT answering it"), ""
    if str(thread.get("state", "")).upper() != "MERGED":
        return None, "", ("no fix round after this REPORT yet, and the pull "
                          "request has not merged")
    reopen = reopen_of(row.get("repo"), row.get("pull_request"))
    if reopen is None:
        return None, "", "the pull request's closing references did not read"
    merged_at = reopen.get("merged_at") or ""
    names = names_of(row.get("repo"), row.get("pull_request"),
                     row.get("report_comment"))
    for issue in reopen.get("issues") or []:
        # THE REOPEN IS AN EVENT AFTER THE MERGE, whatever the issue's state is
        # now: work that came back gets done and the issue closes again.
        after = [at for at in issue.get("reopened") or [] if at > merged_at]
        if not after:
            continue
        for said in issue.get("comments") or []:
            if (said.get("at") or "") <= merged_at:
                continue
            if any(n.search(said.get("body") or "") for n in names):
                return "yes", (f"{issue.get('repo')}#{issue.get('number')} was "
                               f"reopened at {after[0]}, after {where} merged, "
                               f"and named it"), ""
    return "no", (f"{where} merged with no fix round after this REPORT and no "
                  f"sub-issue of it reopened naming it"), ""


def fetch_guard_log(_repo, path):
    """Every row of one guard.log, in the order written, or None. LOCAL: the
    record a shell reading joins to is this machine's, and never on GitHub."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, TypeError):
        return None
    rows = []
    for line in text.splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def join_guard_tree_delta(row, rows):
    """shell-write-unread: did the call change its tree, where a claim gates?

    THE AFTER IS THE SAME SESSION'S NEXT ROW IN THE SAME TREE, whatever tool
    made it, since every guard row carries the tree's state taken before its
    own call. The same state is `no`. A CHANGED tree that another session
    also called into between the two is not labelled: checkouts are shared,
    and nothing says whose call changed it.

    A CHANGED TREE IS LABELLED ONLY BY THE COMMIT GATE'S LATER VERDICT ON IT
    (rule-check#455 DECISION 5723273420): `yes` once the gate has judged a
    commit there as campaign work, whatever it decided; not labelled while no
    commit has been judged, nor where the gate read no campaign work, which
    is outside what the reading asks."""
    if rows is None:
        return None, "", "the guard log did not read"
    tree, before = row.get("tree"), row.get("porcelain")
    mine = [n for n, g in enumerate(rows)
            if g.get("session") == row.get("session")
            and g.get("command_sha") == row.get("command_sha")
            and g.get("tree") == tree and g.get("porcelain") == before
            and (g.get("at") or "") <= (row.get("at") or "")]
    if not mine:
        return None, "", "the guard row this reading was asked on is not in the log"
    at = mine[-1]
    end = next((n for n in range(at + 1, len(rows))
                if rows[n].get("session") == row.get("session")
                and rows[n].get("tree") == tree and rows[n].get("porcelain")),
               None)
    if end is None:
        return None, "", "no later call of this session in this tree yet"
    after = rows[end]
    if after["porcelain"] == before:
        return "no", (f"{tree} read the same before this call and before the "
                      f"session's next ({after.get('tool')}, {after.get('at')})"
                      ), ""
    if any(g.get("tree") == tree and g.get("session") != row.get("session")
           for g in rows[at + 1:end]):
        return None, "", "another session called into this tree before it changed"
    gate = next((g for g in rows[at + 1:] if g.get("tool") == "pre-commit"
                 and g.get("tree") == tree
                 and g.get("session") == row.get("session")), None)
    if gate is None:
        return None, "", ("the tree changed and this session has had no "
                          "commit judged on it yet")
    if gate.get("verdict") == "not campaign work":
        return None, "", "the commit gate reads this tree as no campaign work"
    return "yes", (f"{tree} changed by the session's next call "
                   f"({after.get('at')}), and the commit gate judged it "
                   f"`{gate.get('verdict')}` at {gate.get('at')}"), ""


def repo_of(url):
    """`owner/name` out of a git remote URL, or "". Both spellings git writes:
    `https://github.com/owner/name.git` and `git@github.com:owner/name.git`."""
    found = re.search(r"[:/]([^/:]+/[^/:]+?)(?:\.git)?/*$", (url or "").strip())
    return found.group(1) if found else ""


def clone_of(repo, cwd=None):
    """This machine's checkout of `repo`, or None.

    THE BASE IS THE ONE CHECKOUT A JOIN CAN COUNT ON. A member repository's
    clone lives under a campaign directory -- git-ignored scratch a close
    sweeps -- so a join that read one would answer differently depending on
    which campaigns happen to be open on the day it ran. A sha in any other
    repository reads as None and the join COUNTS it as a subject that would not
    read, which is the same treatment a deleted issue gets and never a guess."""
    root = base_root(cwd)
    if root is None:
        return None
    try:
        out = subprocess.run(["git", "-C", str(root), "remote", "get-url",
                              "origin"], capture_output=True, text=True,
                             timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return root if repo_of(out.stdout) == repo else None


def commit_key(cwd=None):
    """{repo, commit} for a reading made at `pre-commit`, or {} -- the
    repository this tree pushes to and the sha it is committing ONTO.

    THE COMMIT BEING MADE HAS NO SHA YET, which is why the key is its parent:
    the reader runs over the index, and `HEAD` is the newest thing it can name.
    `fetch_commits` reads the window from there, and the join drops the first
    later commit that touched the file -- the one this reading was made for.

    A KEY IT COULD NOT READ IS EMPTY, never half: a row carrying a path and no
    repository is a row the join cannot reach anyway, and it says so."""
    out = {}
    for field, args in (("repo", ("remote", "get-url", "origin")),
                        ("commit", ("rev-parse", "HEAD"))):
        try:
            got = subprocess.run(["git", *args], capture_output=True, text=True,
                                 timeout=10, cwd=str(cwd) if cwd else None)
        except (OSError, subprocess.SubprocessError):
            return {}
        if got.returncode != 0 or not got.stdout.strip():
            return {}
        out[field] = got.stdout.strip()
    out["repo"] = repo_of(out["repo"])
    return out if out["repo"] else {}


def fetch_commits(repo, sha, path, timeout=60, cwd=None):
    """What happened to one file after one commit, or None.

    {commits: [{sha, paths}] touching `path` after `sha`, oldest first;
     own: the commit of those whose parent IS `sha`, or None;
     now: the file as `origin/main` holds it, or None where it is gone;
     window: how many commits `sha..origin/main` holds at all;
     unmerged: set where the sha has not reached `origin/main`}

    `own` IS THE READING'S OWN COMMIT. A commit-time reader runs at
    `pre-commit`, so the sha it names is the PARENT and the change it judged is
    the child -- which touches `path` by construction, since `path` was staged.
    Counting that as somebody coming back to the file let a claim be called
    "read and left" by the very commit that wrote it (pr#492 REVIEW
    5723079103, F1), so it is named here and the join drops it.

    THE ONE FETCH for a commit-time reading, as `fetch_issue` is for an issue
    and `fetch_thread` for a pull request, so an offline suite stubs one
    function per subject. It asks GITHUB NOTHING: the later fact here is the
    history, and git holds that whole and for free.

    IT IS READ AT A SHA AND A PATH, never a sha alone, because the later fact
    is what happened to ONE FILE and the file as `origin/main` holds it now is
    half of it. `window` is the other clock: how much history has passed at
    all, so a join can tell "nobody has touched it yet" from "nobody touched it
    in the twenty commits since".

    A SHA THIS CHECKOUT DOES NOT HOLD IS None, and it is read APART from the
    ancestry: `git merge-base --is-ancestor` exits 128 for a sha that is not a
    commit here and 1 for one that is merely unmerged, and reading both as
    `unmerged` left a row keyed to a squashed or force-pushed sha waiting for
    ever instead of counted among the subjects that will never read
    (pr#492 REVIEW 5723079103, F3).

    A SHA THAT HAS NOT REACHED `origin/main` IS `unmerged` AND NOT None.
    `<sha>..origin/main` over an unmerged claim is every commit main took since
    the fork, not one of which is a later fact about this reading's own change,
    so nothing is read there -- but such a sha is WAITING and not unreadable,
    and None is the word for a subject nothing on this tracker can ever label.
    A reading made on the claim it is about is the ordinary case, so reporting
    those as dead would bury every row this machinery was built for.

    IT READS THE LOCAL `origin/main` AND FETCHES NOTHING. A clone behind the
    remote sees fewer later commits and a shorter window, which costs a label
    and can never write a wrong one: every missing later fact leaves the row
    waiting in the log, where the next run picks it up."""
    root = clone_of(repo, cwd)
    if root is None:
        return None

    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True, timeout=timeout)

    try:
        if git("cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
            return None
        # AND THE REF THE WINDOW IS MEASURED AGAINST. `--is-ancestor` exits 128
        # for a missing `origin/main` exactly as it does for a missing sha, so
        # a checkout without it read every sha `unmerged` for ever instead of
        # saying nothing here can label them (pr#492 REVIEW 5723212225, F3).
        if git("rev-parse", "--verify", "-q",
               "origin/main^{commit}").returncode != 0:
            return None
        if git("merge-base", "--is-ancestor", sha,
               "origin/main").returncode != 0:
            return {"commits": [], "window": 0, "now": None, "unmerged": True}
        window = git("rev-list", "--count", f"{sha}..origin/main")
        log = git("log", "--reverse", "--format=%H %P", "--name-only",
                  f"{sha}..origin/main", "--", path)
        now = git("show", f"origin/main:{path}")
    except (OSError, subprocess.SubprocessError):
        return None
    if window.returncode != 0 or log.returncode != 0:
        return None
    commits, at, own = [], None, None
    for line in log.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        found = re.fullmatch(r"([0-9a-f]{40})((?: [0-9a-f]{40})*)", line)
        if found:
            at = {"sha": found.group(1), "paths": []}
            commits.append(at)
            # BY PREFIX, because `%P` is always 40 hex and the sha a row
            # carries need not be: `cat-file -e` and `merge-base` both take an
            # abbreviation or a tag, and an equality test there found no child
            # and quietly undid the drop above (pr#492 REVIEW 5723212225, F2).
            if own is None and any(p.startswith(sha)
                                   for p in found.group(2).split()):
                own = at["sha"]
        elif at is not None:
            at["paths"].append(line)
    return {"commits": commits, "own": own,
            "window": int(window.stdout.strip() or 0),
            "now": now.stdout if now.returncode == 0 else None}


# HOW MUCH HISTORY MAKES "NOBODY CHANGED IT" A FACT. A comment nobody has gone
# back to says nothing yet; a comment still standing after twenty commits, one
# of them on its own file, was read and left. The number is here and not in an
# entry because it is the same question for every commit-time reading.
COMMIT_WINDOW = 20


def later_comments(issue, at, kind):
    """The bodies of one issue's comments after `at` whose first word is
    `kind`. THE ONE READER of "what was said next on that sub-issue", because
    two joins ask it and a second copy would read a different channel."""
    return [c.get("body") or "" for c in (issue or {}).get("comments") or []
            if (c.get("createdAt") or "") > at
            and (c.get("body") or "").lstrip().startswith(kind + " ")]


def join_decision_gap(row, issue):
    """research-bar: did the next DECISION on that sub-issue name this
    condition as a gap?

    THE OWNER'S OR PLANNER'S NEXT WORD IS THE LABEL, which is the strongest
    this tree has for this reading: the reading says whether a NOTE meets a
    condition of the research bar, and the DECISION answering that NOTE either
    names what is missing or moves the work on. A DECISION carrying half a
    condition's words is that condition named -- rule-check#460 set C's own
    rule, reused here through `re_raised`, so both joins measure "named again"
    the same way.

    THE TWO HALVES ARE NOT EQUALLY STRONG, as `join_issue_title_kept`'s are
    not. A condition NAMED is strong: somebody read the note and said that bar
    was not met. A condition not named is the weak half -- the DECISION may
    simply not have gone through them -- and it is what labels the `no` class,
    which is why `label.from` records the join by name."""
    if issue is None:
        return None, "", "the issue did not read"
    conditions = (row.get("state") or {}).get("condition") or {}
    if not conditions:
        return None, "", "the row carries no condition to label"
    later = later_comments(issue, row.get("at") or "", "DECISION")
    if not later:
        return None, "", "no DECISION on this sub-issue after the NOTE yet"
    body = "\n".join(later)
    truth = {k: ("yes" if re_raised(text, body) else "no")
             for k, text in conditions.items()}
    named = sorted(k for k, v in truth.items() if v == "yes")
    return (truth,
            f"{len(later)} DECISION(s) after this NOTE on {row.get('repo')}#"
            f"{row.get('issue')}; " + (f"named as a gap: {', '.join(named)}"
                                       if named else "none of these named"),
            "")


def join_done_line_reraised(row, issue):
    """done-test-claim, done-report-claim: did a later REVIEW on that sub-issue
    name that Definition-of-done line again?

    THE READING SAYS THE EVIDENCE SHOWS THE LINE HOLDS. A later REVIEW naming
    that line is somebody saying it did not, which is the strong half. The
    weak half is the sub-issue CLOSED with no REVIEW naming it -- nobody looked
    again -- and it is what labels the `yes` class, which is why it waits for
    the close rather than reading an open issue as agreement.

    THE WAIT IS PER CONDITION AND NOT PER ROW. One REVIEW naming ONE of the
    round's lines used to carry every other line of the same row past the
    close, handing the weak half a label nothing had earned; a condition no
    later REVIEW names is simply left out of the truth until the sub-issue
    closes (pr#492 REVIEW 5723079103, F2)."""
    if issue is None:
        return None, "", "the issue did not read"
    conditions = (row.get("state") or {}).get("condition") or {}
    if not conditions:
        return None, "", "the row carries no condition to label"
    later = later_comments(issue, row.get("at") or "", "REVIEW")
    body = "\n".join(later)
    closed = str(issue.get("state", "")).upper() == "CLOSED"
    truth = {}
    for k, text in conditions.items():
        if later and re_raised(text, body):
            truth[k] = "no"
        elif closed:
            truth[k] = "yes"
    again = sorted(k for k, v in truth.items() if v == "no")
    if not truth:
        return None, "", ("no REVIEW naming these lines yet, and the sub-issue "
                          "is still open")
    return (truth,
            f"{len(later)} REVIEW(s) after this reading on {row.get('repo')}#"
            f"{row.get('issue')}, {len(truth)} of {len(conditions)} line(s) "
            f"labelled; " + (f"named again: {', '.join(again)}" if again
                             else "the sub-issue closed with none of these "
                                  "named again"),
            "")


def join_comment_rewritten(row, seen):
    """docstring-claims, reference-claims, model-comment: did a later commit
    take that claim out of the file?

    THE READING SAYS A CLAIM IS CONTRADICTED BY THE CODE UNDER IT, and the
    later fact is what somebody did to the claim. A claim GONE while the
    definition it is about is still there is the strong half: the comment was
    rewritten and the claim did not survive it. A claim still standing is the
    weak half -- and it is only read as one at all once somebody has come back
    to that file and left it, which is why `no` needs a later commit ON THE
    FILE and a window of `COMMIT_WINDOW` commits behind it.

    TWO STATES ARE NOT LABELLED AT ALL, and both are said rather than guessed:
    the file gone from `origin/main`, where what happened to the claim cannot
    be read from what replaced it; and the DEFINITION gone, where a claim gone
    with it says nothing about the claim. A claim left undecided is simply
    left out of the truth, so the ones that are decided are not held back by
    it."""
    if seen is None:
        return None, "", "the file's history did not read"
    if seen.get("unmerged"):
        return None, "", (f"{row.get('commit', '')[:12]} has not reached "
                          f"`origin/main`, so no commit after it is a later "
                          f"fact about this reading")
    claims = (row.get("state") or {}).get("claim") or {}
    if not claims:
        return None, "", "the row carries no claim to label"
    now = seen.get("now")
    if now is None:
        return None, "", (f"`{row.get('path')}` is gone from `origin/main`, so "
                          f"what happened to the claim cannot be read from "
                          f"what replaced it")
    name = row.get("name") or ""
    if name and name not in now:
        return None, "", (f"`{name}` is gone from `{row.get('path')}`, so a "
                          f"claim gone with it says nothing about the claim")
    own = seen.get("own")
    touched = len([c for c in seen.get("commits") or []
                   if c.get("sha") != own])
    window = seen.get("window") or 0
    flat = " ".join(now.split())
    truth = {}
    for text in claims.values():
        if " ".join(str(text).split()) not in flat:
            truth[str(text)] = "yes"
        elif touched and window >= COMMIT_WINDOW:
            truth[str(text)] = "no"
    if not truth:
        return None, "", (f"{window} commit(s) on `origin/main` since, "
                          f"{touched} of them on this file and not this "
                          f"reading's own; every claim is still there and that "
                          f"is under {COMMIT_WINDOW}")
    gone = sorted(k for k, v in truth.items() if v == "yes")
    return (truth,
            f"{len(truth)} of {len(claims)} claim(s) labelled on "
            f"{row.get('path')} `{name}` after {row.get('commit', '')[:12]}, "
            f"{window} commit(s) and {touched} on the file since; "
            + (f"rewritten away: {', '.join(gone)}" if gone
               else "each still there"), "")


def join_witness_case_kept(row, seen):
    """suite-witness-claim: did the suite keep the case the claim was tied to?

    THE MUTATION RUN IS THE TRUTH AND NOTHING RECORDS IT LATER. A mutant of
    the branch the scenario names either reddens the picked case or does not,
    and that is decided by running it -- `suite-harness-test.py`'s `mutate`,
    which no `pre-commit` guard starts and which leaves nothing on
    `origin/main` to read. So the corpus is labelled by that run, at the case's
    own sha, and what this join reads afterwards is the WEAKER later fact the
    tree does keep: whether the pairing survived somebody coming back to the
    suite.

    THE STRONG HALF IS THE CASE GONE while the suite still names the scenario:
    the claim was tied to a case the suite did not keep, and the reading's
    `supports` did not survive it. The weak half is the case still standing,
    and it is read as one only once somebody has come back to the suite and
    left it -- a later commit ON THE FILE and a window of `COMMIT_WINDOW`
    commits behind it, as `comment-rewritten` requires.

    TWO STATES ARE NOT LABELLED AT ALL: the suite gone from `origin/main`, and
    the SCENARIO no longer named anywhere in it -- a suite that stopped
    witnessing the scenario says nothing about which of its cases the
    scenario's claim belonged to."""
    if not seen:
        return None, "", "the suite's history did not read"
    if seen.get("unmerged"):
        return None, "", (f"{row.get('commit', '')[:12]} has not reached "
                          f"`origin/main`, so no commit after it is a later "
                          f"fact about this reading")
    claims = (row.get("state") or {}).get("claim") or {}
    if not claims:
        return None, "", "the row carries no claim to label"
    text = seen.get("now")
    if text is None:
        return None, "", (f"`{row.get('path')}` is gone from `origin/main`, so "
                          f"what happened to the case cannot be read from what "
                          f"replaced it")
    scenario = row.get("scenario") or ""
    if not scenario or scenario not in text:
        return None, "", (f"`{row.get('path')}` no longer names `{scenario}`, "
                          f"so what happened to its cases says nothing about "
                          f"that scenario's claim")
    name = row.get("name") or ""
    if not name:
        return None, "", "the row names no picked case"
    others = len([c for c in seen.get("commits") or []
                  if c.get("sha") != seen.get("own")])
    window = seen.get("window") or 0
    if name in text and not (others and window >= COMMIT_WINDOW):
        return None, "", (f"{window} commit(s) on `origin/main` since, "
                          f"{others} of them on this suite and not this "
                          f"reading's own; `{name}` is still there and that is "
                          f"under {COMMIT_WINDOW}")
    word = "yes" if name in text else "no"
    return ({str(t): word for t in claims.values()},
            f"{len(claims)} claim(s) labelled `{word}` on {row.get('path')} "
            f"`{scenario}` after {row.get('commit', '')[:12]}, {window} "
            f"commit(s) and {others} on the suite since; "
            + (f"the case `{name}` is gone" if word == "no"
               else f"the case `{name}` is still there"), "")


# WHAT A SUITE'S `# witnesses:` LINE NAMES, read off a diff's ADDED lines: the
# commands a suite says it exercises. A removed line is not read -- what a
# scenario stopped being witnessed by says nothing about which one covered the
# Plan -- so a line REWRITTEN to add a name reads as the added line it is.
WITNESSES_ADDED = re.compile(r"^\+\s*#\s*witnesses:\s*(.+)$", re.M)
# A COMMAND THE SAME DIFF ADDS TO THE SNAPSHOT: a scenario that did not exist
# when the Plan was judged, so no option of that call could have been it.
SNAPSHOT_ADDED = re.compile(
    r'^\+\s*\[\s*"[^"]+"\s*,\s*"(?:run|check)"\s*,\s*"(\w+)"\s*\]', re.M)
PLAN_CLOSING_SEEN = {}


def fetch_plan_closing(repo, number, timeout=30):
    """(the pull request that closed this sub-issue, its diff) -- or None.

    THE LAZY SECOND FETCH of the two plan readings, and the only call either
    makes beyond `fetch_issue`. The subject fetch answers `{repo, issue}` and
    the later fact is a PULL REQUEST's diff, which no issue view carries, so
    the closing reference is asked for here and the diff after it.

    It is taken for one branch only -- a sub-issue CLOSED AS COMPLETED -- and
    memoised per issue by `plan_closing_of`, so an open sub-issue, one dropped
    as not planned, and one whose reading already has a case cost nothing.

    THE CLOSING REFERENCE'S OWN REPOSITORY IS READ OFF ITS URL, as
    `fetch_reopen` reads it: a member repository's pull request closes a
    sub-issue on this base's tracker, and `gh pr diff` must be given the
    repository the pull request is on, not the one the issue is on.

    IT IS A MODULE-LEVEL NAME so an offline suite replaces it as it replaces
    the subject fetches; `cmd_corpus_join` routes those through its `args` and
    this one is not a subject, it is a second question about one."""
    try:
        head = subprocess.run(
            ["gh", "issue", "view", str(number), "-R", repo, "--json",
             "closedByPullRequestsReferences"], capture_output=True,
            text=True, timeout=timeout)
        if head.returncode != 0:
            return None
        refs = json.loads(head.stdout).get(
            "closedByPullRequestsReferences") or []
        if len(refs) != 1:
            return {"pull_request": None, "diff": None, "refs": len(refs)}
        ref = refs[0]
        owner = ((ref.get("repository") or {}).get("owner") or {}).get("login")
        name = (ref.get("repository") or {}).get("name")
        on = f"{owner}/{name}" if owner and name else repo
        out = subprocess.run(
            ["gh", "pr", "diff", str(ref["number"]), "-R", on],
            capture_output=True, text=True, timeout=timeout)
        if out.returncode != 0:
            return None
        return {"pull_request": ref["number"], "diff": out.stdout, "refs": 1}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return None


def plan_closing_of(repo, number):
    """`fetch_plan_closing`, memoised for this join run, `None` included --
    both plan readings of one sub-issue ask it, and a subject that would not
    read this run will not read on the second row either."""
    key = (repo, number)
    if key not in PLAN_CLOSING_SEEN:
        PLAN_CLOSING_SEEN[key] = fetch_plan_closing(repo, number)
    return PLAN_CLOSING_SEEN[key]


def plan_witnessed(row, issue):
    """(the command names the closing diff's `# witnesses:` lines add, the
    names that diff also adds to the snapshot, the pull request) -- or
    (None, why not, None).

    THE ONE READER of the later fact both plan readings are labelled by, so
    the two cannot disagree about what the diff said."""
    if issue is None:
        return None, "the issue did not read", None
    if str(issue.get("state", "")).upper() == "OPEN":
        return None, "still open: what the work landed is not written yet", None
    if str(issue.get("stateReason", "")).upper() != "COMPLETED":
        return None, ("closed as not planned, so no diff says what would have "
                      "covered the Plan"), None
    seen = plan_closing_of(row.get("repo"), row.get("issue"))
    if seen is None:
        return None, "the closing pull request did not read", None
    if seen.get("pull_request") is None:
        return None, (f"{seen.get('refs')} closing pull request(s), so the "
                      f"diff that landed this Plan is not one diff"), None
    diff = seen.get("diff") or ""
    named = [n.strip() for line in WITNESSES_ADDED.findall(diff)
             for n in line.split(",") if n.strip()]
    if not named:
        return None, (f"pr#{seen['pull_request']} adds no `# witnesses:` line, "
                      f"so nothing says which scenario the work was tied to"), \
            None
    return named, set(SNAPSHOT_ADDED.findall(diff)), seen["pull_request"]


def join_plan_closing_diff(row, issue):
    """plan-scenario-select: which scenario did the work actually tie itself to?

    THE LATER FACT IS THE CLOSING PULL REQUEST'S DIFF, and it has two halves of
    unequal strength. A `# witnesses:` line naming a command the SAME DIFF adds
    to `spec/commands.snapshot.json` is a scenario that did not exist when the
    reading was made, so no option of that call could have been it and the
    truth is `noMatch`. A line naming a command already in the snapshot is the
    strong half: the work tied itself to a scenario that was on offer, and the
    truth is that option's key.

    WHAT IT DOES NOT SAY, and the docstring is where that is said: a new
    command proves the author WROTE one, never that no existing scenario would
    have done -- which is the very miss this reading exists to catch. So a
    `noMatch` label here is the author's choice and not a fact about `spec/`,
    and a band fitted on these labels inherits that. A diff naming an existing
    command the reading did not offer -- one the entity cut left out -- is not
    labelled at all: the call could not have picked it."""
    named, new, at = plan_witnessed(row, issue)
    if named is None:
        return None, "", new
    picked = {str(v).split("\n", 1)[0].split(None, 1)[-1]: k
              for k, v in ((row.get("state") or {}).get("scenarios")
                           or {}).items()}
    if not picked:
        return None, "", "the row carries no scenarios to label against"
    old = [n for n in named if n not in new]
    if not old:
        return ("noMatch",
                f"pr#{at} witnesses {', '.join(named)}, which it adds to the "
                f"snapshot in the same diff: no scenario on offer was it", "")
    hit = [picked[n] for n in old if n in picked]
    if not hit:
        return None, "", (f"pr#{at} witnesses {', '.join(old)}, which the call "
                          f"did not offer, so no option of it can be right")
    return (hit[0], f"pr#{at} witnesses `{old[0]}`, which the call offered as "
                    f"`{hit[0]}`", "")


def join_plan_cover_kept(row, issue):
    """plan-scenario-cover: did the work tie itself to the scenario picked?

    THE SAME DIFF, READ FOR THE OTHER QUESTION. The cover `noul` asks whether
    the picked scenario exercises what the Plan changes; the later fact that
    bears on it is whether the work ended up witnessed by THAT command. `yes`
    where the diff's `# witnesses:` names it, `no` where it names another
    existing command or a new one instead.

    THE WEAKNESS IS NAMED: a Plan's work may be witnessed by a scenario the
    select call never picked and the cover call was never asked about, and
    that reads `no` here on a pick the question might still have been right
    about. It is a label on the PAIRING and not on the pick alone, which is
    why the select reading is joined apart."""
    named, new, at = plan_witnessed(row, issue)
    if named is None:
        return None, "", new
    scenario = (row.get("state") or {}).get("scenario") or ""
    name = scenario.split("\n", 1)[0].split(None, 1)[-1].strip()
    if not name:
        return None, "", "the row carries no picked scenario to label"
    word = "yes" if name in named and name not in new else "no"
    return (word, f"pr#{at} witnesses {', '.join(named)}; the picked "
                  f"`{name}` is {'among them' if word == 'yes' else 'not'}", "")


JOINS = {"issue-title-kept": join_issue_title_kept,
         "issue-kind-label": join_issue_kind_label,
         "thread-refinding": join_thread_refinding,
         "filing-parent-slug": join_filing_parent_slug,
         "report-next-round": join_report_next_round,
         "decision-gap": join_decision_gap,
         "done-line-reraised": join_done_line_reraised,
         "comment-rewritten": join_comment_rewritten,
         "guard-tree-delta": join_guard_tree_delta,
         "witness-case-kept": join_witness_case_kept,
         "plan-closing-diff": join_plan_closing_diff,
         "plan-cover-kept": join_plan_cover_kept}
# WHICH FIELDS A ROW'S JOIN READS, and which fetch answers it: (the fetch, the
# fields it is given after the repository). A row carries its join key as
# FIELDS, so the subject is the field it names and never a guess. A commit-time
# row names TWO, because no sha alone names a file.
SUBJECTS = {"issue": ("fetch", ("issue",)),
            "pull_request": ("fetch_thread", ("pull_request",)),
            "commit": ("fetch_commits", ("commit", "path")),
            "guard_log": ("fetch_guard_log", ("guard_log",))}
# `guard_log` is a PATH on this machine and names no repository.
LOCAL_SUBJECTS = {"guard_log"}


def subject_of(row):
    """(the subject field, the fetch's name, what it is given after the repo)
    for one row -- or (None, why not, ()).

    THE SECOND HALF IS WHY A ROW NAMES WHAT IT LACKS. Every shape used to park
    under one sentence about `repo` and a number, which said nothing to a row
    carrying a sha and no path; the reason travels beside the verdict here so
    `corpus join` prints the one that fits."""
    repo = row.get("repo")
    subject = next((s for s in SUBJECTS if row.get(s)), None)
    if subject is None or (subject not in LOCAL_SUBJECTS and not repo):
        return None, (f"the row carries no repo and "
                      f"{' or '.join(SUBJECTS)} field"), ()
    how, fields = SUBJECTS[subject]
    missing = [f for f in fields if not row.get(f)]
    if missing:
        return None, (f"the row's `{subject}` key carries no "
                      f"{', '.join(f'`{f}`' for f in missing)}"), ()
    return subject, how, tuple(row[f] for f in fields)


# ------------------------------------------------------------------ the corpus


def corpus_path(reading, root=None):
    return (Path(root) if root else CORPUS) / f"{reading}.jsonl"


def read_corpus(reading, root=None):
    path = corpus_path(reading, root)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def write_corpus(reading, cases, root=None):
    path = corpus_path(reading, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(c, sort_keys=True, ensure_ascii=False)
                            + "\n" for c in cases), encoding="utf-8")


def read_log(env=None, cwd=None):
    """Every row of the log, and the path it came from. A line that will not
    parse is counted rather than raised on: the log is appended to by every
    call, and a torn last line must not cost a join every row before it."""
    path, how = log_path(env=env, cwd=cwd)
    if path is None or not path.exists():
        return [], how, 0
    rows, torn = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            torn += 1
    return rows, how, torn


def joinable(rows, reg):
    """(the rows a join could label, the rows of no joinable reading, the rows
    the real endpoint did not answer).

    A ROW THE REAL ENDPOINT DID NOT ANSWER IS NEVER JOINED. A suite's stub
    answers whatever its case needs, so a case built from one would be evidence
    the tracker never produced; and a row written before the `endpoint` field
    existed cannot say which it was, so it is refused the same way rather than
    guessed at (DECISION 5716626608). Both are COUNTED and named, never dropped:
    they are not waiting for anything, because nothing can ever label them.

    A row whose reading left the registry is counted apart too -- it is not
    lost, it is unjoinable."""
    out, stray, unreal = [], [], []
    for row in rows:
        if row.get("endpoint") != REAL:
            unreal.append(row)
            continue
        entry = reg.get(row.get("reading"))
        if entry is None or entry.get("join") not in JOINS:
            stray.append(row)
        else:
            out.append(row)
    return out, stray, unreal


def cmd_corpus_join(args):
    """Label what the log holds, and count what could not be labelled yet."""
    reg = load_registry()
    # THE JOIN'S OWN SECOND FETCH IS MEMOISED FOR THIS RUN, beside the
    # per-subject `fetched` map below: `reopen_of` is not a subject fetch and
    # so sat outside it, and two rows on one pull request paid twice.
    REOPEN_SEEN.clear()
    PLAN_CLOSING_SEEN.clear()
    rows, how, torn = read_log()
    rows, stray, unreal = joinable(rows, reg)
    known = {r: {c.get("source", {}).get("ref") for c in read_corpus(r)}
             for r in reg}
    fetched, added, waiting, unfetched = {}, 0, [], {}
    for row in rows:
        name = row["reading"]
        ref = f"{row.get('call')}:{name}"
        if ref in known.get(name, set()):
            continue
        entry, repo = reg[name], row.get("repo")
        subject, how, given = subject_of(row)
        if subject is None:
            waiting.append((row, how))
            continue
        at = (subject, repo) + given
        if at not in fetched:
            fetched[at] = getattr(args, how)(repo, *given)
        # A SUBJECT THAT WILL NOT READ AT ALL IS SKIPPED, COUNTED AND NAMED,
        # and it does not fail the run. It is not "not labelled yet" either:
        # the shared log holds hundreds of rows whose subject is a suite's
        # `o/r#274`, a repository that does not exist, and counting those as
        # waiting asks a reader to go and fix a number that cannot move. Each
        # fetch is made ONCE per subject, so a repository that is gone costs
        # one `gh` call however many rows name it.
        if fetched[at] is None:
            named = f"{repo}#{'/'.join(str(g) for g in given)}"
            unfetched.setdefault(named, 0)
            unfetched[named] += 1
            continue
        truth, evidence, why = JOINS[entry["join"]](row, fetched[at])
        if truth is None:
            waiting.append((row, why))
            continue
        # THE READING'S OWN SLICE OF THE STATE, not the group's. One `judge`
        # call carries the union of every reading's fields and its row records
        # that union, so a group whose readings name DIFFERENT fields --
        # `pull-request-thread`, where one reads the report and its findings,
        # one the review and the thread, and two the report alone -- wrote a
        # case carrying every one of them. `judge` then RAISES on such a state
        # as an extra field, and
        # `--live` would ask a question about state the band was never
        # measured with. Found by the suite's "every case of a registered
        # reading fits its entry" on the first thread row ever joined.
        fields = (entry.get("state") or {}).get("fields") or []
        cases = read_corpus(name)
        case = {
            "id": f"{name}-{row['call']}", "reading": name,
            "state": {k: v for k, v in (row.get("state") or {}).items()
                      if k in fields}, "truth": truth,
            "label": {"from": f"join:{entry['join']}",
                      "at": datetime.date.today().isoformat(),
                      "evidence": evidence},
            # THE PREFILTER'S WORD TRAVELS WITH THE CASE, so `report` can say
            # what share of the work code did: a case Jev never saw is still a
            # case, and counting it as one Jev got right would flatter it.
            "source": {"kind": "log", "ref": ref, "settled": row.get("settled"),
                       "flag": row.get("flag")},
            "role": "case",
            "seen": ([{"model": row.get("answered") or "", "at": row.get("at"),
                       "wording": row.get("wording"), "word": row.get("branch"),
                       "raw": row.get("raw")}] if row.get("raw") else [])}
        # THE BAND THE CASE IS HELD TO, WRITTEN NOW. A case with none is one no
        # declared band can ever call drifted, and for a `choice` the truth
        # word is an option name and never a band name -- so a joined case at
        # 0.01 confidence read `drift: none` for good.
        case["band"] = band_of(entry, case)[0]
        cases.append(case)
        write_corpus(name, cases)
        known.setdefault(name, set()).add(ref)
        added += 1
    print(f"read {len(rows) + len(stray) + len(unreal)} row(s) from {how}"
          + (f", {torn} unparsed" if torn else ""))
    print(f"  {added} case(s) written")
    print(f"  {len(waiting)} row(s) not labelled yet, kept in the log")
    for row, why in waiting[:10]:
        print(f"    {row.get('call')}:{row.get('reading')}  {why}")
    if unfetched:
        print(f"  {sum(unfetched.values())} row(s) SKIPPED by the join over "
              f"{len(unfetched)} subject(s) that would not read; nothing on "
              f"this tracker can ever label them, and the run is unaffected")
        for name, count in sorted(unfetched.items(),
                                  key=lambda kv: (-kv[1], kv[0]))[:10]:
            print(f"    {name}  {count} row(s)")
    if stray:
        print(f"  {len(stray)} row(s) of no registered reading with a join")
    if unreal:
        words = sorted({str(r.get("endpoint")) for r in unreal})
        print(f"  {len(unreal)} row(s) REFUSED by the join: `endpoint` is "
              f"{', '.join(words)} and not `{REAL}`, so no later fact of this "
              f"tracker's can label them")
        for row in unreal[:10]:
            print(f"    {row.get('call') or '-'}:"
                  f"{row.get('reading') or row.get('reader')}  "
                  f"endpoint {row.get('endpoint')!r}")
    return 0


# ------------------------------------------------------------------ the reader


def overlap(text, against):
    """A token-overlap score: the share of `against`'s words the text carries.
    THE BASELINE JEV MUST BEAT, and it is deliberately the dumbest thing that
    could work -- a reading that cannot beat this is not worth a request."""
    words = set(re.findall(r"[a-z]{3,}", (text or "").lower()))
    other = set(re.findall(r"[a-z]{3,}", (against or "").lower()))
    return len(words & other) / len(other) if other else 0.0


def baseline_word(entry, state):
    """The word token overlap alone would answer."""
    text = " ".join(str(v) for v in state.values())
    crit = entry["question"].get("criteria") or {}
    if entry["question"]["type"] == NOUL:
        yes = crit.get("true", {})
        no = crit.get("false", {})
        as_text = lambda c: " ".join([c.get("what", "")] + c.get("examples", []))  # noqa: E731
        return "yes" if overlap(text, as_text(yes)) >= overlap(
            text, as_text(no)) else "no"
    scored = [(overlap(text, str(v)), k) for k, v in crit.items()]
    return max(scored)[1] if scored else UNKNOWN


def settled_of(case):
    """The word CODE reached for this case, or None. THE ONE READER of the two
    spellings the corpus carries: `settled` at the top level, which the survey
    fit writes, and `source.settled`, which `corpus join` writes off the log
    row. Two readers of this drifted once already -- `report` counted only the
    join's, so every case the survey's prefilter had cleared read as one Jev
    answered."""
    if case.get("settled") is not None:
        return case["settled"]
    return (case.get("source") or {}).get("settled")


def scored(case):
    """May the agreement share count this case? THE ONE READER, so the
    disagreement list and the share cannot disagree about which cases they are
    over.

    Three ways a case is not scorable, and each is a real one: CODE settled the
    whole reading, so the model never saw it; nothing has been seen; or the run
    recorded no WORD, which is every case of a reading asked PER ITEM -- what
    its per-item answers add up to is the entry's `combine`, and scoring a
    missing word against a truth that is an object would count every one of
    them wrong."""
    seen = last_seen(case)
    return (not isinstance(settled_of(case), str) and seen is not None
            and seen.get("word") is not None and case.get("truth") is not None)


def last_seen(case):
    seen = case.get("seen") or []
    return seen[-1] if seen else None


def evidence_row(entry, cases):
    """DECISION 5713111488's bar, counted: what a reading must hold before it
    sits above `shadow`. Answers the failures by name, so a reading short of
    it says which part is short."""
    short = []
    real = [c for c in cases if c.get("role", "case") == "case"
            and c.get("truth") not in (None, "none")]
    if len(real) < 8:
        short.append(f"{len(real)} real case(s) with a known truth, under 8")
    if not any(c.get("role") == "flip" for c in cases):
        short.append("no flip case")
    if not any(c.get("role") == "no-match" for c in cases):
        short.append("no no-match case")
    wordings = {s.get("wording") for c in cases for s in c.get("seen") or []}
    wordings.discard(None)
    if len(wordings) < 2:
        short.append(f"{len(wordings)} wording(s) seen, under 2")
    runs = {s.get("at") for c in cases for s in c.get("seen") or []}
    runs.discard(None)
    if len(runs) < 3:
        short.append(f"{len(runs)} run(s) recorded, under 3")
    agree, base = agreement(entry, cases)
    if agree is not None and base is not None and agree <= base:
        short.append(f"Jev agrees on {agree:.2f} against the baseline's "
                     f"{base:.2f}, which it must beat")
    return short


def agreement(entry, cases):
    """(Jev's share of cases whose last `seen` word is the truth, the token
    baseline's share over the same cases), or (None, None) with nothing seen."""
    judged = [c for c in cases if scored(c)]
    if not judged:
        return None, None
    jev = sum(1 for c in judged if last_seen(c).get("word") == c["truth"])
    base = sum(1 for c in judged
               if baseline_word(entry, c.get("state") or {}) == c["truth"])
    return jev / len(judged), base / len(judged)


# A LINE THE WATCH READS MUST NOT MOVE ON EVERY CALL. `campaign-heartbeat.py
# --watch` fires its planner whenever a line it prints CHANGES, and every
# `campaign-tracker check` logs two rows, so the exact count below re-fired
# every planner on this machine every few minutes with nothing for any of them
# to do (DECISION 5718621461). The STEADY form names the classes that are
# waiting and no count at all: it changes when waiting starts, when it ends,
# when a class comes or goes, and when the oldest unjoined row passes
# STALE_AFTER -- and each of those is something its reader can act on. The
# exact counts stay one flag away, on `report --waiting`.
STALE_AFTER = datetime.timedelta(hours=6)


def older_than(at, span, now=None):
    """Whether the ISO timestamp `at` is at least `span` old. One absent or
    unreadable is NOT stale: a torn row must not be what moves the line."""
    try:
        when = datetime.datetime.fromisoformat(at)
    except (TypeError, ValueError):
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return now - when >= span


def waiting_facts(reg=None):
    """The ways the corpus stalls, as facts: the rows nobody joined and the
    oldest one's `at`, the cases nobody labelled, the readings above `shadow`
    whose evidence row is short, and the rows the join refuses outright. Both
    lines below render these.

    The corpus grows only if somebody is told it has stopped growing."""
    reg = load_registry() if reg is None else reg
    rows, _how, _torn = read_log()
    rows, _stray, unreal = joinable(rows, reg)
    known = {f"{c.get('source', {}).get('ref')}"
             for r in reg for c in read_corpus(r)}
    unjoined = [r for r in rows
                if f"{r.get('call')}:{r.get('reading')}" not in known]
    # A ROW WITH NO `at` IS NOT THE OLDEST ROW. Read as one, its empty string
    # wins the `min` and hides however old the real oldest row is, so the age
    # clause below would never fire while such a row sat in the log.
    oldest = min((r["at"] for r in unjoined if r.get("at")), default="")
    unlabelled = sum(1 for r in reg for c in read_corpus(r)
                     if c.get("truth") is None)
    short = [r for r, e in reg.items()
             if e.get("tier") != SHADOW and evidence_row(e, read_corpus(r))]
    return unjoined, oldest, unlabelled, short, unreal


def waiting_line(reg=None):
    """THE FIRST LINE, exact: every count as it stands, for whoever asks."""
    unjoined, oldest, unlabelled, short, unreal = waiting_facts(reg)
    return (f"jev waiting: {len(unjoined)} log row(s) unjoined"
            + (f" (oldest {oldest})" if oldest else "")
            + f", {unlabelled} case(s) unlabelled, "
              f"{len(short)} reading(s) short of the evidence row"
            # A ROW THE JOIN REFUSES IS NOT WAITING. Nothing can ever label
            # it, so counting it as waiting would ask a reader to go and fix a
            # number that cannot move; it is printed apart, with its count.
            + (f" ({', '.join(sorted(short))})" if short else "")
            + (f"; {len(unreal)} row(s) never joinable, no `{REAL}` endpoint"
               if unreal else ""))


def spend_tally(rows):
    """(sent by who, distinct states by who, hits by who, blind, stubbed) for
    one set of rows. THE ONE COUNTER, so the all-time window and the window
    since the run field cannot count differently."""
    spent, hits, states, blind, stubbed = {}, {}, {}, 0, 0
    for row in rows:
        if row.get("skipped") is not None or row.get("settled") is not None:
            continue
        # A STUB'S CALL COST NOTHING, so it is not in the ratio. A row from
        # before the field existed is counted, since the shared log is where
        # the real ones were and a stub could not write there anyway.
        if row.get("endpoint") == STUB:
            stubbed += 1
            continue
        who = row.get("reading") or f"(reader) {row.get('reader') or '?'}"
        key = row.get("state_hash")
        if key is None and isinstance(row.get("state"), dict):
            key = digest(row["state"])
        if key is None:
            blind += 1
            continue
        if row.get("cached"):
            hits[who] = hits.get(who, 0) + 1
            continue
        spent[who] = spent.get(who, 0) + 1
        states.setdefault(who, set()).add(key)
    return spent, states, hits, blind, stubbed


def spend_lines(env=None, cwd=None):
    """CALLS A STATE, per reading: the one number that says whether a reader is
    asking the same state over and over (DECISION 5716060001). It is the ratio
    the owner set at 1/5 to 1/20, so it is PRINTED rather than asked for.

    A CACHE HIT IS NOT A CALL. It is logged so it is visible, and counted apart:
    the ratio is over the calls that were actually sent, since that is what the
    endpoint charges for. A row whose reading asked nothing -- a `skipped` row,
    or one code settled -- is neither.

    A row is grouped by the reading it names, and an `ask` row names none, so
    those are grouped by their READER and said to be. Rows with no state to
    group by at all -- every row written before the hash was logged -- are
    counted and named rather than silently left out of the denominator.

    THREE WINDOWS, AND THE ALL-TIME ONE IS NEVER HIDDEN. A row cannot be
    re-marked once written, so the rows from before the `run` field say nothing
    about which kind of run they came from and the all-time ratio they dominate
    stands as it is. Beside it, the same count over the rows that DO carry the
    field, with a MEASURING run and a PRODUCTION call apart: a `--live`,
    `--record` or `relive` run asks the same states on purpose, so its ratio is
    a different number about a different thing, and averaging the two would
    hide whichever moved."""
    rows, how, torn = read_log(env=env, cwd=cwd)
    spent, states, hits, blind, stubbed = spend_tally(rows)
    out = [f"calls a state, over {len(rows)} row(s) of {how}"
           + (f", {torn} unparsed" if torn else "")
           + (f", {blind} with no state to group by" if blind else "")
           + (f", {stubbed} from a stubbed endpoint" if stubbed else "")]

    def block(head, spent, states, hits):
        lines = []
        for who in sorted(set(spent) | set(hits)):
            sent, distinct = spent.get(who, 0), len(states.get(who, ()))
            lines.append(f"    {who:<28} {sent} sent over {distinct} state(s)"
                         + (f", {sent / distinct:.1f} a state" if distinct
                            else "")
                         + (f"; {hits[who]} replayed from the store"
                            if who in hits else ""))
        return [head] + (lines or ["    nothing"])

    out += block(f"  all time ({len(rows)} row(s))", spent, states, hits)
    marked = [r for r in rows if r.get(RUN_FIELD) in RUNS]
    out.append(f"  since the `{RUN_FIELD}` field ({len(marked)} row(s) carry "
               f"it, of {len(rows)})")
    for kind in RUNS:
        part = [r for r in marked if r.get(RUN_FIELD) == kind]
        sp, st, hi, _b, _s = spend_tally(part)
        out += block(f"    {kind} ({len(part)} row(s))", sp, st, hi)
    return out


def span_text(span):
    """A span as a reader says it: whole hours as hours, anything else in
    minutes. Written from the constant, so moving the constant moves the word
    with it rather than leaving `90m` printed as `1h`."""
    minutes = int(span.total_seconds() // 60)
    return f"{minutes // 60}h" if minutes and not minutes % 60 else f"{minutes}m"


def steady_waiting_line(reg=None, now=None):
    """THE SAME FIRST LINE FOR A WATCH: which classes are waiting, no count."""
    unjoined, oldest, unlabelled, short, unreal = waiting_facts(reg)
    parts = []
    if unjoined:
        aged = (f" (oldest over {span_text(STALE_AFTER)})"
                if older_than(oldest, STALE_AFTER, now) else "")
        parts.append("log rows unjoined" + aged)
    if unlabelled:
        parts.append("cases unlabelled")
    if short:
        parts.append("readings short of the evidence row "
                     f"({', '.join(sorted(short))})")
    body = ", ".join(parts)
    # NOT WAITING, AND STILL SAID. Nothing can ever label these rows, so they
    # are no reader's errand -- but the exact line has named them since
    # DECISION 5716626608, and a watch that stopped naming them would go quiet
    # on a log filling with rows no join will ever take.
    if unreal:
        body += ("; " if body else "") + f"rows never joinable, no `{REAL}` endpoint"
    return "jev waiting: " + (body or "nothing")


def cmd_report(args):
    reg = load_registry()
    print(steady_waiting_line(reg) if args.steady else waiting_line(reg))
    if args.waiting:
        return 0
    for line in spend_lines():
        print(line)
    names = [args.reading] if args.reading else sorted(reg)
    for name in names:
        entry = reg.get(name)
        if entry is None:
            print(f"\n{name}: no such reading in {REGISTRY}")
            continue
        cases = read_corpus(name)
        if args.live:
            cases = relive(name, entry, cases, whole=args.all)
        print(f"\n{name}  tier {entry['tier']}  group {entry['group']}  "
              f"wording {wording(entry)}  {len(cases)} case(s)")
        roles, froms = {}, {}
        for c in cases:
            roles[c.get("role", "case")] = roles.get(c.get("role", "case"), 0) + 1
            src = (c.get("label") or {}).get("from", "<none>")
            froms[src] = froms.get(src, 0) + 1
        print("  by role: " + ", ".join(f"{k} {v}" for k, v in sorted(roles.items())))
        print("  by label: " + ", ".join(f"{k} {v}" for k, v in sorted(froms.items())))
        # A CASE CODE SETTLED IS NEVER A DISAGREEMENT. The model was not asked,
        # so the `seen` rows beside it are a record of what it answered before
        # the prefilter existed, and counting them against the truth would
        # charge Jev for a state that is no longer sent (DECISION 5715993782).
        bad = [c["id"] for c in cases if scored(c)
               and last_seen(c).get("word") != c["truth"]]
        print(f"  disagreement: {len(bad)}" + (f"  {', '.join(bad)}" if bad else ""))
        drifted, unplaced = drift_line(entry, cases)
        print("  drift: " + drifted)
        if unplaced:
            print(f"  held to no band ({len(unplaced)}): "
                  + ", ".join(unplaced[:6])
                  + (" ..." if len(unplaced) > 6 else ""))
        # WHOLLY AND PARTLY SETTLED ARE COUNTED APART. For a reading asked per
        # item the prefilter's word is an OBJECT -- some findings cleared, the
        # rest asked -- and counting one of those as a case code settled read
        # this reading as 100% code's when the model answered most of it.
        settled = sum(1 for c in cases if isinstance(settled_of(c), str))
        part = sum(1 for c in cases if isinstance(settled_of(c), dict))
        escalated = sum(1 for c in cases if last_seen(c)
                        and last_seen(c).get("word") == UNKNOWN)
        n = len(cases) or 1
        print(f"  code settled {settled}/{len(cases)} ({settled / n:.0%}), "
              + (f"{part} settled per item, " if part else "")
              + f"Jev escalated {escalated}/{len(cases)} ({escalated / n:.0%})")
        jev, base = agreement(entry, cases)
        print("  agreement: "
              + ("nothing seen yet" if jev is None
                 else f"Jev {jev:.2f} against the token baseline's {base:.2f}"))
        short = evidence_row(entry, cases)
        print("  evidence row: " + ("met" if not short else "; ".join(short)))
    unregistered = {}
    if CORPUS.exists():
        for path in sorted(CORPUS.glob("*.jsonl")):
            if path.stem.endswith(".changes"):
                continue
            if path.stem not in reg:
                unregistered[path.stem] = sum(
                    1 for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip())
    if unregistered:
        print("\ncases whose reading is not registered yet:")
        for name, count in sorted(unregistered.items()):
            print(f"  {name:<28} {count}")
    print("\ntiers: " + ", ".join(
        f"{t} {sum(1 for e in reg.values() if e['tier'] == t)}" for t in TIERS))
    return 0


def drift_line(entry, cases):
    """(the drift, the cases held to no band). A `seen` value outside the
    declared band UNDER THE SAME MODEL AND WORDING; a value read under another
    wording is a different question's answer and says nothing about this one's
    band.

    A CASE `band_of` CANNOT PLACE IS RETURNED, never skipped: a case counted by
    the evidence row and by the agreement share while no band could ever call it
    drifted is the shape this reader was blind in.

    WHETHER A CASE MAY BE TESTED AGAINST A BAND AT ALL IS `held_to_a_band`'s,
    asked here rather than restated: this reader used to call a case code
    settles drifted, on a value from a state production no longer sends."""
    declared = (entry.get("bands") or {}).get("declared") or {}
    model = (entry.get("bands") or {}).get("model")
    out, unplaced = [], []
    for c in cases:
        if not held_to_a_band(c):
            unplaced.append(f"{c['id']} (code settled it, so the state is no "
                            f"longer sent and no band is over it)")
            continue
        key, why = band_of(entry, c)
        if key is None:
            unplaced.append(f"{c['id']} ({why})")
            continue
        band = declared.get(key)
        for s in c.get("seen") or []:
            if s.get("model") != model or s.get("wording") != wording(entry):
                continue
            value = band_value(entry, s.get("raw"))
            if band and value is not None and not (band[0] <= value <= band[1]):
                out.append(f"{c['id']} {value:.2f} outside {key} {band}")
    return (", ".join(out) if out else "none"), unplaced


# WHAT A REPEAT RUN ASKS, and it is not every case (DECISION 5716060001: "a
# repeat run is asked for a sample and for rows in or near the band, not for
# every case"). Three constants and one seed:
#
# NEAR is how close to an edge or to a band's end a recorded value has to sit
# for its case to be asked EVERY time. Those are the cases a run can actually
# move a threshold with; a case answering 0.99 against a `confident` band of
# [0.53, 1.0] has been saying the same thing for five runs and says it again.
#
# SAMPLE_SHARE and SAMPLE_FLOOR are what is taken from the rest, SEEDED, so the
# same cases come back run after run -- a sample redrawn each time would move
# the band by changing who was asked, which reads exactly like drift.
NEAR = 0.05
SAMPLE_SHARE = 0.25
SAMPLE_FLOOR = 4
SAMPLE_SEED = "campaign-jev repeat sample"


def sample_of(entry, cases):
    """(the cases a repeat run asks, why each pinned one is pinned). THE ONE
    READER, because `relive` and the suite's `--live` both ask it and a second
    copy would sample a different set and then compare the two.

    FOUR KINDS ARE ALWAYS ASKED. A case whose recorded value sits within NEAR
    of an edge or of an INNER band end -- 0 and 1 are the scale's own ends and
    no mark -- because that is the case a run can move a threshold with; a case with no recorded value under this wording and model,
    because nothing is known about it yet; a case whose ROLE is not `case` --
    the flip and the no-match -- because the live half asserts on each by name
    and a run that skipped one would assert nothing; and every case of a
    reading with SAMPLE_FLOOR cases or fewer, since there is nothing to save.

    THE REST IS A SEEDED SAMPLE. It returns the cases in the order given, so a
    caller prints them in corpus order and not in the order they were drawn."""
    # 0 AND 1 ARE NOT MARKS. They are the scale's own ends, not a line a
    # threshold can be moved across, and the `confident` band runs to 1.0 --
    # so counting them pinned every case that answers 0.96 or more, which is
    # most of a working reading's corpus, and the sample saved nothing.
    marks = [v for v in (entry.get("thresholds") or {}).values()
             if isinstance(v, (int, float))]
    for band in ((entry.get("bands") or {}).get("declared") or {}).values():
        marks += [v for v in band
                  if isinstance(v, (int, float)) and 0.0 < v < 1.0]
    want, model = wording(entry), (entry.get("bands") or {}).get("model")
    pinned, rest = {}, []
    for c in cases:
        if c.get("role", "case") != "case":
            pinned[c["id"]] = f"role {c.get('role')}"
            continue
        values = [band_value(entry, s.get("raw")) for s in c.get("seen") or []
                  if s.get("wording") == want and s.get("model") == model]
        values = [v for v in values if v is not None]
        if not values:
            pinned[c["id"]] = "no value recorded under this wording and model"
            continue
        close = [m for m in marks if any(abs(v - m) <= NEAR for v in values)]
        if close:
            pinned[c["id"]] = (f"within {NEAR} of "
                               f"{', '.join(format(m, '.2f') for m in sorted(set(close)))}")
            continue
        rest.append(c["id"])
    if len(cases) <= SAMPLE_FLOOR:
        return list(cases), {c["id"]: "the reading has no more" for c in cases}
    take = min(len(rest), max(SAMPLE_FLOOR, round(SAMPLE_SHARE * len(rest))))
    drawn = set(random.Random(SAMPLE_SEED).sample(sorted(rest), take)) if rest \
        else set()
    return [c for c in cases if c["id"] in pinned or c["id"] in drawn], pinned


def sample_line(entry, cases, asked):
    """The one sentence a measuring run prints about what it asked, so the
    sample is read beside the numbers it produced rather than guessed at."""
    return (f"  asked {len(asked)} of {len(cases)} case(s): every one at or "
            f"within {NEAR} of an edge or a band's end, every flip and "
            f"no-match, every one not yet seen under wording "
            f"{wording(entry)}, and a seeded {SAMPLE_SHARE:.0%} of the rest")


def relive(name, entry, cases, env=None, root=None, whole=False):
    """`--live`: re-ask the repeat sample and APPEND what came back. Nothing is
    replaced -- a band is read from the run history, so a run that overwrote
    the one before it would erase the evidence of drift.

    WHICH CASES ARE ASKED IS `sample_of`'s, and `whole` is the way past it.

    A PER-ITEM READING IS NOT ASKED HERE AND SAYS SO. Its question is composed
    from the item, and `question_of` with no item leaves `{condition}` standing
    or hands back the instructions object unfilled -- a question production
    never sends, so a band measured on it would belong to a call nobody makes.
    The suite's `--live` half already refused these; this refused nothing and
    sent the malformed one (pr#492 REVIEW 5723079103, F4)."""
    if (entry.get("question") or {}).get("per"):
        print(f"  {name}: asked per "
              f"`{entry['question']['per']}`, so its question is composed from "
              f"an item and this has none; not asked")
        return cases
    at = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")
    q = {name: question_of(entry)}
    asked, _pinned = (list(cases), {}) if whole else sample_of(entry, cases)
    print(f"  asked {len(asked)} of {len(cases)}" if whole
          else sample_line(entry, cases, asked))
    for c in asked:
        # THE STORE IS OFF HERE. A band is what the same state answers across
        # runs, so a run that replayed a stored answer would measure the store
        # and report a drift of zero (DECISION 5716060001).
        r = ask("campaign-jev.py report --live", c["id"], c.get("state") or {},
                q, env=env, cache=False, run=MEASURING)
        a = r.answers[name]
        c.setdefault("seen", []).append(
            {"model": r.model, "wording": wording(entry), "at": at,
             "word": a.word, "raw": a.raw})
        print(f"  {c['id']:<28} {a.word:<12} {json.dumps(a.raw)}")
    write_corpus(name, cases, root)
    return cases


def cmd_new(args):
    """An empty entry, and the PATH of the skill's reference -- never its text.

    THE GENERAL LESSONS ARE THE SKILL'S and this base holds no copy: a second
    copy is the one that drifts, and a path a reader opens is cheaper than a
    paragraph every reader pays for."""
    empty = {"owner": "", "tier": SHADOW, "group": "", "act": None,
             "state": {"fields": [], "why": ""},
             "prefilter": {"what": ""},
             "question": {"type": NOUL, "instructions": "",
                          "criteria": {"true": {"what": "", "examples": []},
                                       "false": {"what": "", "examples": []}}},
             "thresholds": {}, "join": "",
             "bands": {"model": MODEL, "measured": "", "wording": "",
                       "declared": {}}}
    print(json.dumps({args.reading: empty}, indent=1, ensure_ascii=False))
    print(f"\nA new reading enters at `{SHADOW}`, where it has no thresholds "
          f"and prints nothing.")
    ref = Path(args.references).expanduser()
    print(f"How to ask well is not here: {ref}")
    if not ref.exists():
        print(f"  -- and there is no reference file there yet, so the general "
              f"lessons are still on the sub-issues that found them.")
    return 0


def cmd_probe(args):
    """The hand probe: one request file in, the reading out."""
    try:
        req = json.loads(Path(args.request).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"campaign-jev: could not read {args.request} -- {e}",
              file=sys.stderr)
        return 2
    reading = ask(req.get("reader", "campaign-jev.py probe"),
                  req.get("label", "a hand probe"), req["state"],
                  req["questions"])
    print(f"answered by {reading.model or '<nothing>'} in "
          f"{reading.latency:.2f}s, {reading.logged}")
    for qid, a in reading.answers.items():
        print(f"  {qid:<24} {a.word}" + (f"  -- {a.why}" if a.why else ""))
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("report", help="what is waiting, then each reading")
    p.add_argument("reading", nargs="?")
    p.add_argument("--live", action="store_true",
                   help="re-ask the repeat sample and append what came back")
    p.add_argument("--all", action="store_true",
                   help="with --live, ask every case rather than the sample")
    p.add_argument("--waiting", action="store_true",
                   help="the first line alone, with every count as it stands")
    p.add_argument("--steady", action="store_true",
                   help="that line in the form a watch reads: which classes "
                        "are waiting, and no count that moves on each call")
    p.set_defaults(run=cmd_report)
    p = sub.add_parser("corpus", help="the corpus and its join")
    p.add_argument("action", choices=["join"])
    p.set_defaults(run=cmd_corpus_join, fetch=fetch_issue,
                   fetch_thread=fetch_thread, fetch_commits=fetch_commits,
                   fetch_guard_log=fetch_guard_log)
    p = sub.add_parser("new", help="an empty entry for a new reading")
    p.add_argument("reading")
    p.add_argument("--references",
                   default="~/.claude/skills/asking-jev/references/")
    p.set_defaults(run=cmd_new)
    p = sub.add_parser("probe", help="one request file, asked as written")
    p.add_argument("request")
    p.set_defaults(run=cmd_probe)
    args = ap.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
