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

UNKNOWN IS THE ANSWER FOR EVERY FAILURE. No key, an endpoint that would not
answer, an HTTP error, a timeout, a body that is not JSON, a response naming
another model, an answer missing for a question, an answer of another type, a
raw value the thresholds leave in the gap -- each comes back `unknown` with a
one-line reason, per question. Nothing here raises at a caller, because a
judgment that crashed its reader would be worse than no judgment; the one
exception is a question of an unsupported TYPE, which is the caller's bug and
not the model's answer.

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
    except OSError as e:
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
    """The URL to POST to: `CAMPAIGN_JEV_URL` when set, else the live one."""
    env = os.environ if env is None else env
    return env.get(URL_ENV) or DEFAULT_URL


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
        value = raw.get(NOUL)
        if not isinstance(value, (int, float)):
            return UNKNOWN, f"the answer carries no `{NOUL}` value"
        if value >= spec["yes_over"]:
            return "yes", ""
        if value <= spec["no_under"]:
            return "no", ""
        return UNKNOWN, (f"noul {value:.2f} sits in the gap between "
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
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            text = fh.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
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
    instructions carry the whole meaning."""
    env = os.environ if env is None else env
    for qid, spec in questions.items():
        if spec["type"] not in (NOUL, CHOICE):
            raise ValueError(f"campaign-jev: question `{qid}` is a "
                             f"`{spec['type']}`; this module answers "
                             f"{NOUL} and {CHOICE}")
    row = {"at": datetime.datetime.now(datetime.timezone.utc)
                         .isoformat(timespec="seconds"),
           "reader": reader, "read": label, "asked": MODEL}
    key, why = read_key(env)
    started = time.time()
    if why:
        answers, model, out = unknown_all(questions, why), "", None
    else:
        out, why = post(request_body(state, questions), key,
                        endpoint(env), timeout)
        if why:
            answers, model = unknown_all(questions, why), ""
        elif not isinstance(out, dict):
            answers, model, why = unknown_all(
                questions, "the response is not an object"), "", "not an object"
        elif out.get("model") != MODEL:
            model = str(out.get("model"))
            why = (f"`{model}` answered where `{MODEL}` is pinned; a band "
                   f"measured under one version says nothing about another")
            answers = unknown_all(questions, why)
        else:
            model = out["model"]
            given = out.get("answers")
            given = given if isinstance(given, dict) else {}
            answers = {}
            for qid, spec in questions.items():
                raw = given.get(qid)
                raw = raw if isinstance(raw, dict) else None
                word, note = branch(spec, raw)
                answers[qid] = Answer(word, raw, note)
    latency = time.time() - started
    row.update({"answered": model, "latency": round(latency, 3),
                "answers": {qid: {"branch": a.word, "raw": a.raw,
                                  "why": a.why}
                            for qid, a in answers.items()}})
    if why:
        row["why"] = why
    return Reading(answers, model, latency, log_call(row, env, cwd))


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
