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
A switch cannot do what `role-planner.md` § Handing off does for a slug rename or
a context too large to compact; that path stays.

THE ADDRESS is every row `herdr agent list` shows whose name carries the role
word (`campaign-name-session.py`'s `role_word`), of any campaign, narrowed by
`--from` to those whose transcript's latest assistant model contains that
word (`campaign-heartbeat.py`'s `transcript_reading`, the one transcript
reader). It skips, and names why:

  another role     the name carries another role word, or none
  own pane         this session's own pane: a prompt there queues behind the
                   turn running this script; switch it with `/model` yourself
  model            `--from` was given and the model is not it, or no
                   transcript was read, so the model is unknown
  gone             no longer listed when its turn came
  not idle         mid-turn, where two prompts queue and merge into one line
                   (`campaign-assign.py`'s `idle_verdict`, imported)
  input box        text sits in the pane's input box, which a prompt would
                   join (`campaign-assign.py`'s `input_line`, imported)

The last three are read AGAIN just before each pane is prompted, from a
fresh listing, since a pane can start a turn while the ones before it switch.
A target skipped for one of them is left as it was and fails the run; run
this again once it is idle -- a pane already on the model takes `/model`
again as a no-op.

THE SWITCH, per pane, each step read before the next -- probed on
rule-check#431, and `.claude/skills/using-herdr/references/facts.md` holds the facts:

  1. `herdr agent prompt <pane> "/model <to>"`.
  2. A session with history answers with a `Switch model?` dialog, `Yes`
     selected; a pane read showing it is answered with one Enter. A fresh
     session gets no dialog.
  3. Done when the transcript holds one more `/model` run than it did before
     step 1 AND that run printed `Set model to`. A run that printed anything
     else fails with what it printed. The screen is read only for the dialog.
  4. `/effort <level>`, confirmed the same way by `Set effort level to`.
     Sent only after step 3, because a prompt sent while the dialog is up
     answers it and is lost.

A pane not confirmed in time says whether the dialog is still up, and the
run warns that its `/model` may still land after the default is put back.

THE USER'S DEFAULT IS PUT BACK. Each `/model` and `/effort` also rewrites
`model` and `effortLevel` in ~/.claude/settings.json, which every session later
started without `--model` would take -- a bare `claude --resume`. The owner's
DECISION (rule-check#431 issuecomment-5659640299): read both before the first
prompt, write both back after the last pane, print the values before and
after, and report a write-back that fails. A key is put back only when it
still holds exactly what this run sent (`--to`, `--effort`); one holding
anything else was changed by somebody else meanwhile, and is left as it is,
named, and fails the run. A key that was absent is removed again, every other
key is left alone, and the file is read back after the write. A settings file
that cannot be read refuses the run before any prompt, since nothing could be
put back. This script runs no git at all, so it never commits ~/.claude.

Exit 0 when every addressed pane was switched and the default is as it was (or
on --dry-run); 1 when the listing or the settings could not be read, a target
was skipped or not confirmed, or the default was not put back.
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
# What each command prints when it took, as probed on rule-check#431.
CONFIRM = {"model": "Set model to", "effort": "Set effort level to"}
DIALOG = "Switch model?"
POLLS, POLL_SLEEP = 20, 0.5
SETTINGS = Path.home() / ".claude" / "settings.json"
ABSENT = "<absent>"


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


def read_facts(sid):
    """(reading, None) -- `transcript_reading`'s dict -- or (None, why)."""
    reading, _where, why = heartbeat.read_transcript(sid)
    return reading, why


def runs(reading, name):
    """What each run of the slash command `name` printed, None while unprinted."""
    return [said for cmd, said in reading["commands"] if cmd == name]


def address(sessions, role, own_pane, facts, frm):
    """[(sid, row, why)], `why` None for a pane to switch. Pure: `facts` is
    {sid: (reading, why)} as `read_facts` returned them. Idleness and the
    input box are read later, pane by pane, since they move while this runs."""
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


def ready(sid):
    """(row, None) when the pane can take a prompt now, read from a fresh
    listing, else (row or None, why not)."""
    sessions, why = names.herdr_sessions()
    if sessions is None:
        return None, f"listing unread: {why}"
    row = sessions.get(sid)
    if row is None:
        return None, "gone: no longer listed"
    if not assign.idle_verdict(row)[0]:
        return row, f"not idle: status {row['status']}"
    r = run("herdr", "pane", "read", row["pane"], "--source", "detection")
    if r.returncode != 0:
        return row, f"input box unread: herdr pane read exited {r.returncode}"
    text, why = assign.input_line(r.stdout)
    if text is None:
        return row, f"input box: {why}"
    return row, (f"input box holds {text[:60]!r}" if text else None)


def send(pane, sid, name, value, before):
    """Prompt `/<name> <value>`, answer the model dialog if it shows, and wait
    for run number `before` + 1 of it to print. (ok, what happened)."""
    command = f"/{name} {value}"
    r = run("herdr", "agent", "prompt", pane, command)
    if r.returncode != 0:
        return False, (f"`herdr agent prompt` exited {r.returncode}: "
                       f"{(r.stderr or r.stdout).strip()[:160]}")
    answered = False
    for _ in range(POLLS):
        f, _why = read_facts(sid)
        new = runs(f, name)[before:] if f is not None else []
        if new and new[0] is not None:
            if new[0].startswith(CONFIRM[name]):
                return True, f"{command}: {new[0][:60]}" + (" (dialog answered)" if answered else "")
            return False, f"{command} printed {new[0][:120]!r}"
        if not answered:
            screen = run("herdr", "pane", "read", pane, "--source", "visible")
            if DIALOG in screen.stdout:
                run("herdr", "pane", "send-keys", pane, "enter")
                answered = True
        sleep(POLL_SLEEP)
    screen = run("herdr", "pane", "read", pane, "--source", "visible")
    up = "; the dialog is still up" if DIALOG in screen.stdout else ""
    return False, (f"no {CONFIRM[name]!r} for {command} after "
                   f"{POLLS * POLL_SLEEP:g}s{up}; it may still land")


def switch(row, sid, to, effort):
    """(ok, what happened) for one pane: /model, then /effort."""
    f, why = read_facts(sid)
    if f is None:
        return False, f"transcript unread, so nothing could confirm a switch: {why}"
    ok, said = send(row["pane"], sid, "model", to, len(runs(f, "model")))
    if not ok or not effort:
        return ok, said
    ok, said2 = send(row["pane"], sid, "effort", effort, len(runs(f, "effort")))
    return ok, f"{said}; {said2}"


def read_default(path, keys):
    """({key: value, or ABSENT}, None), or (None, why)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"{path}: {e.__class__.__name__}: {e}"
    if not isinstance(data, dict):
        return None, f"{path}: not a JSON object"
    return {k: data.get(k, ABSENT) for k in keys}, None


def shown(default):
    return " ".join(f"{k}={v!r}" for k, v in default.items()) if default else "unread"


def restore_default(path, saved, sent):
    """(ok, what happened). Each key in `sent` -- the value this run wrote
    there -- goes back to `saved` when it holds exactly that value; one holding
    anything else is somebody else's and is left, and fails. Written into the
    file as it stands now, every other key left alone, in the 2-space layout
    the harness writes, replaced whole, then read back."""
    path = Path(path).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        now = {k: data.get(k, ABSENT) for k in sent}
        back = {k: saved[k] for k in sent if now[k] == sent[k]}
        left = {k: now[k] for k in sent if now[k] not in (saved[k], sent[k])}
        for k, v in back.items():
            if v == ABSENT:
                data.pop(k, None)
            else:
                data[k] = v
        if back:
            tmp = path.with_name(path.name + ".campaign-model.tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            os.replace(tmp, path)
    except (OSError, ValueError, AttributeError) as e:
        return False, f"{path}: {e.__class__.__name__}: {e}"
    reread, why = read_default(path, list(sent))
    want = {k: (saved[k] if k in back else now[k]) for k in sent}
    if reread != want:
        return False, f"read back {shown(reread)}, not {shown(want)}" + (f" ({why})" if why else "")
    said = f"{shown(now)} -> {shown(reread)}"
    if left:
        return False, (f"{said}; left {shown(left)}, which this run did not "
                       f"write -- changed by somebody else meanwhile?")
    return True, said


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--role", required=True, choices=names.ROLES)
    ap.add_argument("--to", required=True, help="the model word /model takes")
    ap.add_argument("--effort", help="the level /effort takes, sent after /model")
    ap.add_argument("--from", dest="frm",
                    help="only sessions whose latest assistant model contains this")
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

    sent = {"model": args.to, **({"effortLevel": args.effort} if args.effort else {})}
    saved, why = read_default(SETTINGS, list(sent))
    if saved is None:
        print(f"refusing: the default could not be read, so it could not be put "
              f"back: {why}", file=sys.stderr)
        return 1
    print(f"{'would send' if args.dry_run else 'sending'} /model {args.to}"
          + (f" and /effort {args.effort}" if args.effort else "")
          + f"; default before: {shown(saved)}, put back after the last pane")

    switched, failed, skipped, unsettled = 0, 0, 0, []
    try:
        for sid, row in todo:
            f = facts[sid][0]
            tag = f"{row['pane']:9} {row['name']} ({f['model'] if f else 'model unknown'})"
            fresh, not_ready = ready(sid)
            if not_ready:
                skipped += 1
                print(f"  skip     {tag}: {not_ready}")
                continue
            if args.dry_run:
                print(f"  address  {tag}")
                continue
            ok, said = switch(fresh, sid, args.to, args.effort)
            switched, failed = switched + ok, failed + (not ok)
            if not ok and "may still land" in said:
                unsettled.append(row["pane"])
            print(f"  {'switched' if ok else 'FAILED  '} {tag}: {said}")
    finally:
        restored = True
        if not args.dry_run:
            restored, said = restore_default(SETTINGS, saved, sent)
            print(f"{'default' if restored else 'FAILED to put back the default'}: {said}")
            if unsettled:
                print(f"warning: a switch not confirmed in {', '.join(unsettled)} may "
                      f"still land and rewrite the default after this; read "
                      f"{SETTINGS} once those panes settle")
    done = ("dry run: nothing sent" if args.dry_run
            else f"{switched} switched, {failed} failed, {skipped} skipped")
    print(f"{done}; {len(todo)} of {len(rows)} listed matched the address")
    if args.dry_run:
        return 0
    return 1 if failed or skipped or not restored else 0


if __name__ == "__main__":
    sys.exit(main())
