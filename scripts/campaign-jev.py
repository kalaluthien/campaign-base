#!/usr/bin/env python3
"""Ask Jev for a typed judgment over one state, and answer `unknown` rather than guess.

THE ONE CALLER OF JEV IN THIS REPOSITORY. Every reading that wants a judgment
-- reading comprehension a script cannot do -- asks here, so the key, the pinned
model, the thresholds, the failure paths and the log are decided once. A second
caller would each have to get all five right, and the one that got a failure path
wrong would answer with a guess.

WHAT A JUDGMENT IS WORTH. Typed output guarantees the shape, not the truth, so
an answer here NEVER allows and never refuses: a caller prints it beside its own
reading and moves no exit status on it. `spec/campaign/github/system.als`'s
`advised` is that claim in the model, and `JV1b` is the scenario that says a
failed, unconfident or ill-fitting answer advises nothing.

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
apart. `scripts/campaign-jev-test.py --live` is that run, and
`scripts/fixtures/jev-cases.json` records the bands each threshold was set
between, with the date and the model that answered.

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

Usage: scripts/campaign-jev.py <request.json>   -- a hand probe; the file holds
       {"reader": ..., "label": ..., "state": ..., "questions": {...}}
"""
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
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


def ask(reader, label, state, questions, env=None, cwd=None, timeout=TIMEOUT):
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
    shape held into a claim refused."""
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
    return Reading(answers, model, latency, log_call(row, env, cwd))


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


def main(argv):
    """The hand probe: one request file in, the reading out."""
    if len(argv) != 2:
        print("Usage: scripts/campaign-jev.py <request.json>", file=sys.stderr)
        return 2
    try:
        req = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"campaign-jev: could not read {argv[1]} -- {e}", file=sys.stderr)
        return 2
    reading = ask(req.get("reader", "campaign-jev.py probe"),
                  req.get("label", "a hand probe"), req["state"],
                  req["questions"])
    print(f"answered by {reading.model or '<nothing>'} in "
          f"{reading.latency:.2f}s, {reading.logged}")
    for qid, a in reading.answers.items():
        print(f"  {qid:<24} {a.word}" + (f"  -- {a.why}" if a.why else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
