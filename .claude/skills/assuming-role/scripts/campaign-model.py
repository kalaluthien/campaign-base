#!/usr/bin/env python3
"""Move every session of one role on this machine onto another model, in place.

    campaign-model.py --role planner --to opus [--effort high] [--from fable]
                      [--dry-run]

ONE OWNER WORD, EVERY PANE. The owner's order of 2026-09-14 (rule-check#245
comment 5659188284) was carried by hand, one peer reading every transcript and
messaging every planner. The owner then switched a planner's model in its own
session and called that the hand-off (rule-check#431), so this does exactly
that to every session the address names: `/model <to>` into its pane, and
`/effort <level>` after it when asked. No successor, no NOTE, no leave -- the
model is `modelSwitch` in spec/campaign/session/system.als, whose
`ModelSwitchKeepsEverySession` says nothing a hand-off moves is moved here.
A switch cannot do what `planner.md` § Handing off does for a slug rename or
a context too large to compact; that path stays.

THE ADDRESS is every row `herdr agent list` shows whose name carries the role
word (`campaign-name-session.py`'s `role_word`), of any campaign, narrowed by
`--from` to those whose transcript's last assistant `model` contains that
word. It skips, and names why:

  another role     the name carries another role word, or none
  own pane         this session's own pane: a prompt there queues behind the
                   turn running this script; switch it with `/model` yourself
  model            `--from` was given and the model is not it, or no
                   transcript was read, so the model is unknown
  not idle         mid-turn, where two prompts queue and merge into one line
                   (`campaign-assign.py`'s `idle_verdict`, imported)
  input box        text sits in the pane's input box, which a prompt would
                   join (`campaign-assign.py`'s `input_line`, imported)

A skipped pane is left as it was; run this again once it is idle, and a pane
already on the model takes `/model` again as a no-op.

THE SWITCH, per pane, each step read before the next -- probed on
rule-check#431, and `.claude/skills/herdr/references/facts.md` holds the facts:

  1. `herdr agent prompt <pane> "/model <to>"`.
  2. A session with history answers with a `Switch model?` dialog, `Yes`
     selected; a pane read showing it is answered with one Enter. A fresh
     session gets no dialog.
  3. Done when the transcript holds one more `/model` command record than it
     did before step 1 -- counted against that reading, since the transcript
     keeps every earlier switch. The screen is read only for the dialog.
  4. `/effort <level>`, confirmed the same way. Sent only after step 3,
     because a prompt sent while the dialog is up answers it and is lost.

Each `/model` and `/effort` ALSO REWRITES THE USER'S DEFAULT (`model`,
`effortLevel` in ~/.claude/settings.json), which reaches every session later
started without `--model`, such as a bare `claude --resume`. Printed before any
prompt is sent; `--dry-run` prints it too and sends nothing.

Exit 0 when every addressed pane was switched (or on --dry-run), 1 when the
listing could not be read or any addressed pane was not confirmed.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[3]

# A model or effort word goes into a pane as one prompt, so a space would make
# it two words of one command, and a newline two prompts.
TOKEN = re.compile(r"^[\w.\[\]-]+$")
MODEL_CMD = "<command-name>/model</command-name>"
EFFORT_CMD = "<command-name>/effort</command-name>"
DIALOG = "Switch model?"
POLLS, POLL_SLEEP = 20, 0.5


def load(path, alias):
    """A sibling script as a module: these are scripts, not a package."""
    spec = importlib.util.spec_from_loader(
        alias, importlib.machinery.SourceFileLoader(alias, str(path)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


names = load(HERE / "campaign-name-session.py", "cname")
heartbeat = load(HERE / "campaign-heartbeat.py", "cheartbeat")
assign = load(BASE / "scripts" / "campaign-assign.py", "cassign")


def run(*args):
    """A command that is not installed is a failed run, not a traceback."""
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              env=dict(os.environ, HERDR_ENV="1"))
    except OSError as e:
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]}: {e}")


sleep = time.sleep


def transcript_facts(lines):
    """What one transcript says about the model. Pure, over its lines:
    `model`, the last assistant record's (by timestamp; a `<synthetic>` one is
    the harness's and a sidechain is a subagent's), and how many `/model` and
    `/effort` command records it holds."""
    out = {"model": None, "at": None, "model_cmds": 0, "effort_cmds": 0}
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or r.get("isSidechain"):
            continue
        msg = r.get("message") or {}
        if r.get("type") == "assistant":
            model, ts = msg.get("model"), r.get("timestamp")
            if model and model != "<synthetic>" and isinstance(ts, str) \
                    and (out["at"] is None or ts > out["at"]):
                out["model"], out["at"] = model, ts
        elif r.get("type") == "user" and isinstance(msg.get("content"), str):
            out["model_cmds"] += MODEL_CMD in msg["content"]
            out["effort_cmds"] += EFFORT_CMD in msg["content"]
    return out


def read_facts(sid):
    """(facts, None), or (None, why) when no transcript was read."""
    path, why = heartbeat.transcript_path(sid)
    if path is None:
        return None, why
    try:
        with open(path, encoding="utf-8") as fh:
            return transcript_facts(fh), None
    except OSError as e:
        return None, f"{path}: {e}"


def address(sessions, role, own_pane, facts, frm):
    """[(sid, row, why)], `why` None for a pane to switch. Pure: `facts` is
    {sid: (facts, why)} as `read_facts` returned them. Idleness and the input
    box are read later, pane by pane, since they move while this runs."""
    out = []
    for sid, row in sorted(sessions.items(), key=lambda kv: kv[1]["pane"]):
        word = names.role_word(row["name"])
        f, unread = facts.get(sid, (None, "not read"))
        if word != role:
            why = f"another role ({word or 'no role word'})"
        elif row["pane"] == own_pane:
            why = "own pane: switch this session with /model yourself"
        elif frm and f is None:
            why = f"model unknown: {unread}"
        elif frm and frm.lower() not in (f["model"] or "").lower():
            why = f"model is {f['model'] or 'unknown (no assistant turn yet)'}, not {frm}"
        else:
            why = None
        out.append((sid, row, why))
    return out


def ready(row):
    """None when the pane can take a prompt now, else why not."""
    if not assign.idle_verdict(row)[0]:
        return f"not idle: status {row['status']}"
    r = run("herdr", "pane", "read", row["pane"], "--source", "detection")
    if r.returncode != 0:
        return f"input box unread: herdr pane read exited {r.returncode}"
    text, why = assign.input_line(r.stdout)
    if text is None:
        return f"input box: {why}"
    return f"input box holds {text[:60]!r}" if text else None


def send(pane, sid, command, counter, before):
    """Prompt `command`, answer the model dialog if it shows, and wait for the
    transcript's `counter` to pass `before`. (ok, what happened)."""
    r = run("herdr", "agent", "prompt", pane, command)
    if r.returncode != 0:
        return False, (f"`herdr agent prompt` exited {r.returncode}: "
                       f"{(r.stderr or r.stdout).strip()[:160]}")
    answered = False
    for _ in range(POLLS):
        f, _why = read_facts(sid)
        if f is not None and f[counter] > before:
            return True, f"{command} recorded" + (", dialog answered" if answered else "")
        if not answered:
            screen = run("herdr", "pane", "read", pane, "--source", "visible")
            if DIALOG in screen.stdout:
                run("herdr", "pane", "send-keys", pane, "enter")
                answered = True
        sleep(POLL_SLEEP)
    return False, (f"no {command.split()[0]} record in the transcript after "
                   f"{POLLS * POLL_SLEEP:g}s" + (" (dialog answered)" if answered else ""))


def switch(row, sid, to, effort):
    """(ok, what happened) for one pane: /model, then /effort."""
    f, why = read_facts(sid)
    if f is None:
        return False, f"transcript unread, so nothing could confirm a switch: {why}"
    ok, said = send(row["pane"], sid, f"/model {to}", "model_cmds", f["model_cmds"])
    if not ok or not effort:
        return ok, said
    ok, said2 = send(row["pane"], sid, f"/effort {effort}", "effort_cmds", f["effort_cmds"])
    return ok, f"{said}; {said2}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--role", required=True, choices=names.ROLES)
    ap.add_argument("--to", required=True, help="the model word /model takes")
    ap.add_argument("--effort", help="the level /effort takes, sent after /model")
    ap.add_argument("--from", dest="frm",
                    help="only sessions whose last assistant model contains this")
    ap.add_argument("--dry-run", action="store_true",
                    help="list whom it would address, and prompt nothing")
    args = ap.parse_args(argv)
    for flag, value in (("--to", args.to), ("--effort", args.effort), ("--from", args.frm)):
        if value is not None and not TOKEN.match(value):
            print(f"refusing: {flag} {value!r} is not one word", file=sys.stderr)
            return 1
    if not args.dry_run and os.environ.get("HERDR_ENV") != "1":
        print("refusing: HERDR_ENV is not 1, so this is not a herdr pane and "
              "no pane here is its to drive", file=sys.stderr)
        return 1

    sessions, why = names.herdr_sessions()
    if sessions is None:
        print(f"refusing: {why}", file=sys.stderr)
        return 1
    own = os.environ.get("HERDR_PANE_ID")
    facts = {sid: read_facts(sid) for sid in sessions}
    print(f"read {len(sessions)} session(s) from herdr agent list; own pane "
          f"{own or 'unknown (HERDR_PANE_ID unset)'}")
    rows = address(sessions, args.role, own, facts, args.frm)
    todo = [(sid, row) for sid, row, why in rows if why is None]
    for sid, row, why in rows:
        if why is not None:
            print(f"  skip     {row['pane']:9} {row['name']}: {why}")
    print(f"{'would send' if args.dry_run else 'sending'} /model {args.to}"
          + (f" and /effort {args.effort}" if args.effort else "")
          + " -- each also rewrites the default in ~/.claude/settings.json")

    switched = failed = 0
    for sid, row in todo:
        f = facts[sid][0]
        tag = f"{row['pane']:9} {row['name']} ({f['model'] if f else 'model unknown'})"
        not_ready = ready(row)
        if not_ready:
            print(f"  skip     {tag}: {not_ready}")
            continue
        if args.dry_run:
            print(f"  address  {tag}")
            continue
        ok, said = switch(row, sid, args.to, args.effort)
        switched, failed = switched + ok, failed + (not ok)
        print(f"  {'switched' if ok else 'FAILED  '} {tag}: {said}")
    done = "dry run: nothing sent" if args.dry_run else f"{switched} switched, {failed} failed"
    print(f"{done}; {len(todo)} of {len(rows)} listed matched the address")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
