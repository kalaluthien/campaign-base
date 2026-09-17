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
of every reading -- the question, its `criteria`, the state slice, the code
prefilter, the cuts and the tier -- and a reader asks by NAME:

    judge("issue-shape", {"title": ..., "body": ...},
          read="kalaluthien/campaign-base#455",
          key={"repo": "kalaluthien/campaign-base", "issue": 455})

One group is one state and ONE call. The caller refuses a missing or an extra
state field, because both are the reader's bug: an extra field is state no band
was measured with, a missing one is a question asked about nothing.

UNKNOWN IS THE ANSWER FOR EVERY FAILURE. A state over `STATE_BUDGET` -- which
is never sent and never cut down -- no key, a `~/.env` that is not text,
`CAMPAIGN_JEV_URL` set to nothing, a URL with no scheme, an endpoint that would
not answer, an HTTP error, a timeout, a body that is not JSON, a response naming
another model, an answer missing for a question, an answer of another type, a
raw value the thresholds leave in the gap -- each comes back `unknown` with a
one-line reason, per question. `ask` is the boundary that holds it: every named
path above returns rather than raises, and `ask` catches whatever is left and
answers `unknown` wearing its exception's class name. The ONE thing that raises
is a question of an unsupported TYPE, which is the caller's bug and not the
model's answer. Nothing else may, because a caller prints a verdict on the next
line -- a traceback out of here turned a `check` whose shape held into a refused
claim.

THE THRESHOLDS ARE THE CALLER'S, and they are two numbers and not one:

  noul    `yes_over` and `no_under`, and the gap between them is `unknown`. A
          `noul` near 0.5 means yes and no are equally likely, not a medium
          degree, so a single cut would turn the model's own indecision into a
          verdict.
  choice  `floor` on `confidence`, and the name of the `no_match` option. Both,
          because a `choice` with no fitting option still picks one: a no-match
          option alone missed a no-match answered at low confidence, and a floor
          alone let a confident wrong option through. `confidence` measures how
          concentrated the distribution is, not whether the option set fits.
  option  a `choice` naming one `option` is instead cut on that option's own
          probability, by `yes_over` and `no_under` as a `noul` is: `yes` the
          option holds, `no` it does not, the gap `unknown`. For a reading that
          flags one option -- a claim `contradicts` its evidence -- where the
          winner and its confidence would hide a strong second.

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

EVERY CALL IS LOGGED, one JSON line to `<base>/runtime/jev.log` -- git-ignored
scratch -- naming the reader, a SHORT label for what it read (never the state,
which carries issue bodies), the model that answered, the latency, and per
question the raw value and the branch taken. `Reading.logged` is the sentence
the caller prints beside the verdict, as `check-campaign-claim.py` prints one
beside its own: a caller that logged nothing and said nothing reads exactly like
one that logged.

Usage: scripts/campaign-jev.py report [<reading>] [--live] [--waiting]
       scripts/campaign-jev.py corpus join
       scripts/campaign-jev.py new <reading>
       scripts/campaign-jev.py probe <request.json>   -- a hand probe; the file
       holds {"reader": ..., "label": ..., "state": ..., "questions": {...}}
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import namedtuple
from pathlib import Path

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
UNKNOWN = "unknown"
NOUL, CHOICE = "noul", "choice"

# One question's answer: the branch, the raw value as the model returned it, and
# why the branch is what it is. `why` is filled for `unknown` and empty
# otherwise, so a caller prints a reason exactly where there is one.
Answer = namedtuple("Answer", "word raw why")
# One call: the answers by question id, the model that answered (empty when
# none did), the latency in seconds, and the sentence about the log line.
Reading = namedtuple("Reading", "answers model latency logged")


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
    wears."""
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
    if kind == NOUL or "option" in spec:
        if not isinstance(value, (int, float)):
            return UNKNOWN, f"the answer carries no {what} value"
        if value >= spec["yes_over"]:
            return "yes", ""
        if value <= spec["no_under"]:
            return "no", ""
        return UNKNOWN, (f"{what} {value:.2f} sits in the gap between "
                         f"{spec['no_under']:.2f} and {spec['yes_over']:.2f}, "
                         f"where yes and no are both live")
    option, confidence = raw.get(CHOICE), raw.get("confidence")
    if not isinstance(confidence, (int, float)) or not isinstance(option, str):
        return UNKNOWN, "the answer carries no option and confidence"
    if confidence < spec["floor"]:
        return UNKNOWN, (f"`{option}` at confidence {confidence:.2f}, under the "
                         f"floor of {spec['floor']:.2f}")
    if option == spec["no_match"]:
        return UNKNOWN, (f"the answer is `{option}`, the no-match option: no "
                         f"option of the set fits")
    return option, ""


def base_root(cwd=None):
    """The base checkout's root, or None. AGENTS.md's one form: the parent of
    the COMMON git dir, which is the main checkout even from a linked worktree,
    where `--show-toplevel` answers the worktree instead."""
    try:
        out = subprocess.run(["git", "rev-parse", "--path-format=absolute",
                              "--git-common-dir"], capture_output=True,
                             text=True, timeout=10,
                             cwd=str(cwd) if cwd else None)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return Path(out.stdout.strip()).parent.resolve()


def log_path(env=None, cwd=None):
    """(the log file, how to name it) or (None, why there is none)."""
    env = os.environ if env is None else env
    named = env.get(LOG_ENV)
    if named:
        return Path(named), named
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
        log=True):
    """One call, one `Reading`: a branch per question, and the log line's fate.

    `reader` names who asked -- a script and its subcommand -- and `label` what
    was read, SHORT and carrying no state: `kalaluthien/campaign-base#455
    title+body`, never the body. Both go in the log, which is why the state does
    not: an issue body in a scratch log is a copy nobody swept.

    `questions` maps an id to a spec: `type`, `instructions`, `criteria`, and
    the thresholds `branch` reads. The id never reaches the model, so the
    instructions carry the whole meaning.

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
    it."""
    env = os.environ if env is None else env
    for qid, spec in questions.items():
        if spec["type"] not in (NOUL, CHOICE):
            raise ValueError(f"campaign-jev: question `{qid}` is a "
                             f"`{spec['type']}`; this module answers "
                             f"{NOUL} and {CHOICE}")
    started = time.time()
    try:
        answers, model, why = _answer(state, questions, env, timeout)
    except Exception as e:  # noqa: BLE001 -- the boundary; the promise is here
        why = (f"the call raised where nothing is meant to "
               f"({e.__class__.__name__}), so nothing was read")
        answers, model = unknown_all(questions, why), ""
    latency = time.time() - started
    row = {"at": datetime.datetime.now(datetime.timezone.utc)
                         .isoformat(timespec="seconds"),
           "reader": reader, "read": label, "asked": MODEL,
           "answered": model, "latency": round(latency, 3),
           "answers": {qid: {"branch": a.word, "raw": a.raw, "why": a.why}
                       for qid, a in answers.items()}}
    if why:
        row["why"] = why
    return Reading(answers, model, latency,
                   log_call(row, env, cwd) if log else "not logged here: the "
                   "row is `judge`'s, one per reading")


def _answer(state, questions, env, timeout):
    """(the answers, the model that answered, why the whole call failed or "").
    Every path here is one `ask` names; `ask` owns the ones it does not."""
    # THE BUDGET IS READ FIRST, before the key and before the endpoint: an
    # oversize state is the caller's own bug and needs neither to be known.
    size = len(json.dumps(state).encode("utf-8"))
    if size > STATE_BUDGET:
        why = (f"the state is {size} bytes, over the {STATE_BUDGET}-byte "
               f"budget, so it was not sent; slicing it is the reader's, and "
               f"this never truncates a state to fit")
        return unknown_all(questions, why), "", why
    key, why = read_key(env)
    if why:
        return unknown_all(questions, why), "", why
    url, why = endpoint(env)
    if why:
        return unknown_all(questions, why), "", why
    out, why = post(request_body(state, questions), key, url, timeout)
    if why:
        return unknown_all(questions, why), "", why
    if not isinstance(out, dict):
        why = "the response is not an object"
        return unknown_all(questions, why), "", why
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
REGISTRY = Path(__file__).resolve().parent / "jev" / "readings.json"
CORPUS = Path(__file__).resolve().parent / "jev" / "corpus"
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
    return check_act_bounds(json.loads(path.read_text(encoding="utf-8")))


def wording(entry):
    """The hash of the question as the model is sent it, 12 hex.

    COMPUTED AND NEVER HAND-KEPT. A band belongs to a wording, so a reworded
    question must not be able to keep the band measured for the old one: the
    log and every `seen` row carry this, and the suite refuses an entry whose
    declared `bands.wording` is not the hash of the question beside it."""
    text = json.dumps(entry["question"], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def question_of(entry):
    """The spec `ask` and `branch` read: the question as sent, plus the cuts,
    which are this tree's reading of the answer and are never sent."""
    spec = dict(entry["question"])
    spec.update(entry.get("thresholds") or {})
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
    if tier == ADVISE:
        return SHOW
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
          reg=None, env=None, cwd=None, timeout=TIMEOUT, log=True):
    """One group, one state, ONE call: a `Verdict` per reading of the group.

    `state` carries exactly the fields the group's entries name, and a MISSING
    or an EXTRA one RAISES rather than answering `unknown`. Both are the
    reader's bug and not the model's answer: an extra field is state the bands
    were never measured with, and a missing one is a question asked about
    nothing. The byte budget is `ask`'s and still holds.

    `settled` is what CODE decided -- the prefilter's word -- as
    {reading: word}. Those readings are never asked, and their rows carry the
    word and the model that never saw them, so the log counts what code saved.

    `key` is the join key AS FIELDS -- `repo`, `issue`, and `comment` or
    `pull_request` where there is one -- because every join is "the later fact
    on that number" and a number inside a label is not a field anything can
    read. `flag` is what the reader computed from the answers,
    {"code": ..., "moved_by": ...}: the flag and which answer moved it.

    ONE LOG ROW PER READING, so a row is a case-to-be on its own: the call id
    ties the rows of one call back together."""
    reg = load_registry() if reg is None else reg
    entries = group_of(reg, group)
    want, given = state_fields(entries), set(state)
    if want != given:
        raise ValueError(
            f"campaign-jev: the state of group `{group}` must carry exactly "
            f"{sorted(want)}; missing {sorted(want - given) or 'none'}, extra "
            f"{sorted(given - want) or 'none'}")
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
    settled = dict(settled or {})
    for name in settled:
        if name not in entries:
            raise ValueError(f"campaign-jev: `{name}` is settled but is no "
                             f"reading of group `{group}`")
    asked = {n: question_of(e) for n, e in entries.items() if n not in settled}
    if asked:
        reading = ask(reader or "campaign-jev.judge", read, state, asked,
                      env=env, cwd=cwd, timeout=timeout, log=False)
    else:
        reading = Reading({}, "", 0.0, "")
    call = uuid.uuid4().hex[:12]
    at = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")
    verdicts, notes = {}, []
    for name, entry in sorted(entries.items()):
        if name in settled:
            word, raw, why = settled[name], None, ""
        else:
            answer = reading.answers[name]
            word, raw, why = answer.word, answer.raw, answer.why
        verdicts[name] = Verdict(word, raw, why, entry["tier"],
                                 does(entry, word, raw) if name not in settled
                                 else NOTHING)
        row = {"at": at, "call": call, "reader": reader or "campaign-jev.judge",
               "read": read, "subject": read, "reading": name,
               "wording": wording(entry), "state": state,
               "settled": settled.get(name), "tier": entry["tier"],
               "does": verdicts[name].does, "asked": MODEL,
               "answered": reading.model, "latency": round(reading.latency, 3),
               "branch": word, "raw": raw, "why": why, "flag": flag}
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
    stubs this alone and every join is exercised against it."""
    try:
        out = subprocess.run(
            ["gh", "issue", "view", str(number), "-R", repo, "--json",
             "title,body,state,labels"], capture_output=True, text=True,
            timeout=timeout)
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


JOINS = {"issue-title-kept": join_issue_title_kept,
         "issue-kind-label": join_issue_kind_label}


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
    """The rows a join could label: one reading's, with the join key as fields
    and an answer the reading actually made. A row whose reading left the
    registry is counted apart -- it is not lost, it is unjoinable."""
    out, stray = [], []
    for row in rows:
        entry = reg.get(row.get("reading"))
        if entry is None or entry.get("join") not in JOINS:
            stray.append(row)
        else:
            out.append(row)
    return out, stray


def cmd_corpus_join(args):
    """Label what the log holds, and count what could not be labelled yet."""
    reg = load_registry()
    rows, how, torn = read_log()
    rows, stray = joinable(rows, reg)
    known = {r: {c.get("source", {}).get("ref") for c in read_corpus(r)}
             for r in reg}
    fetched, added, waiting = {}, 0, []
    for row in rows:
        name = row["reading"]
        ref = f"{row.get('call')}:{name}"
        if ref in known.get(name, set()):
            continue
        entry, repo, number = reg[name], row.get("repo"), row.get("issue")
        if not repo or not number:
            waiting.append((row, "the row carries no repo and issue fields"))
            continue
        if (repo, number) not in fetched:
            fetched[(repo, number)] = args.fetch(repo, number)
        truth, evidence, why = JOINS[entry["join"]](row,
                                                    fetched[(repo, number)])
        if truth is None:
            waiting.append((row, why))
            continue
        cases = read_corpus(name)
        cases.append({
            "id": f"{name}-{row['call']}", "reading": name,
            "state": row.get("state") or {}, "truth": truth,
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
                       "raw": row.get("raw")}] if row.get("raw") else [])})
        write_corpus(name, cases)
        known.setdefault(name, set()).add(ref)
        added += 1
    print(f"read {len(rows) + len(stray)} row(s) from {how}"
          + (f", {torn} unparsed" if torn else ""))
    print(f"  {added} case(s) written")
    print(f"  {len(waiting)} row(s) not labelled yet, kept in the log")
    for row, why in waiting[:10]:
        print(f"    {row.get('call')}:{row.get('reading')}  {why}")
    if stray:
        print(f"  {len(stray)} row(s) of no registered reading with a join")
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
    judged = [c for c in cases if last_seen(c) and c.get("truth") is not None]
    if not judged:
        return None, None
    jev = sum(1 for c in judged if last_seen(c).get("word") == c["truth"])
    base = sum(1 for c in judged
               if baseline_word(entry, c.get("state") or {}) == c["truth"])
    return jev / len(judged), base / len(judged)


def waiting_line(reg=None):
    """THE FIRST LINE, and the one the heartbeat prints: what is waiting.

    The corpus grows only if somebody is told it has stopped growing, so this
    counts the three ways it stalls -- rows nobody joined, cases nobody
    labelled, and a reading above `shadow` whose evidence row is short."""
    reg = load_registry() if reg is None else reg
    rows, _how, _torn = read_log()
    rows, _stray = joinable(rows, reg)
    known = {f"{c.get('source', {}).get('ref')}"
             for r in reg for c in read_corpus(r)}
    unjoined = [r for r in rows
                if f"{r.get('call')}:{r.get('reading')}" not in known]
    oldest = min((r.get("at") or "" for r in unjoined), default="")
    unlabelled = sum(1 for r in reg for c in read_corpus(r)
                     if c.get("truth") is None)
    short = [r for r, e in reg.items()
             if e.get("tier") != SHADOW and evidence_row(e, read_corpus(r))]
    return (f"jev waiting: {len(unjoined)} log row(s) unjoined"
            + (f" (oldest {oldest})" if oldest else "")
            + f", {unlabelled} case(s) unlabelled, "
              f"{len(short)} reading(s) short of the evidence row"
            + (f" ({', '.join(sorted(short))})" if short else ""))


def cmd_report(args):
    reg = load_registry()
    print(waiting_line(reg))
    if args.waiting:
        return 0
    names = [args.reading] if args.reading else sorted(reg)
    for name in names:
        entry = reg.get(name)
        if entry is None:
            print(f"\n{name}: no such reading in {REGISTRY}")
            continue
        cases = read_corpus(name)
        if args.live:
            cases = relive(name, entry, cases)
        print(f"\n{name}  tier {entry['tier']}  group {entry['group']}  "
              f"wording {wording(entry)}  {len(cases)} case(s)")
        roles, froms = {}, {}
        for c in cases:
            roles[c.get("role", "case")] = roles.get(c.get("role", "case"), 0) + 1
            src = (c.get("label") or {}).get("from", "<none>")
            froms[src] = froms.get(src, 0) + 1
        print("  by role: " + ", ".join(f"{k} {v}" for k, v in sorted(roles.items())))
        print("  by label: " + ", ".join(f"{k} {v}" for k, v in sorted(froms.items())))
        bad = [c["id"] for c in cases if last_seen(c)
               and c.get("truth") is not None
               and last_seen(c).get("word") != c["truth"]]
        print(f"  disagreement: {len(bad)}" + (f"  {', '.join(bad)}" if bad else ""))
        print("  drift: " + drift_line(entry, cases))
        settled = sum(1 for c in cases
                      if (c.get("source") or {}).get("settled") is not None)
        escalated = sum(1 for c in cases if last_seen(c)
                        and last_seen(c).get("word") == UNKNOWN)
        n = len(cases) or 1
        print(f"  code settled {settled}/{len(cases)} ({settled / n:.0%}), "
              f"Jev escalated {escalated}/{len(cases)} ({escalated / n:.0%})")
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
    """A `seen` value outside the declared band UNDER THE SAME MODEL AND
    WORDING. A value read under another wording is a different question's
    answer and says nothing about this one's band."""
    declared = (entry.get("bands") or {}).get("declared") or {}
    model = (entry.get("bands") or {}).get("model")
    out = []
    for c in cases:
        for s in c.get("seen") or []:
            if s.get("model") != model or s.get("wording") != wording(entry):
                continue
            band = declared.get(c.get("truth")) or declared.get(c.get("band"))
            value = confidence(entry, s.get("raw"))
            if band and value is not None and not (band[0] <= value <= band[1]):
                out.append(f"{c['id']} {value:.2f} outside {band}")
    return ", ".join(out) if out else "none"


def relive(name, entry, cases):
    """`--live`: re-ask every case and APPEND what came back. Nothing is
    replaced -- a band is read from the run history, so a run that overwrote
    the one before it would erase the evidence of drift."""
    at = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")
    q = {name: question_of(entry)}
    for c in cases:
        r = ask("campaign-jev.py report --live", c["id"], c.get("state") or {},
                q, log=False)
        a = r.answers[name]
        c.setdefault("seen", []).append(
            {"model": r.model, "wording": wording(entry), "at": at,
             "word": a.word, "raw": a.raw})
        print(f"  {c['id']:<28} {a.word:<12} {json.dumps(a.raw)}")
    write_corpus(name, cases)
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
                   help="re-ask every case and append what came back")
    p.add_argument("--waiting", action="store_true",
                   help="the first line alone, for the heartbeat")
    p.set_defaults(run=cmd_report)
    p = sub.add_parser("corpus", help="the corpus and its join")
    p.add_argument("action", choices=["join"])
    p.set_defaults(run=cmd_corpus_join, fetch=fetch_issue)
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
