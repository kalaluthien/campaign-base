#!/usr/bin/env python3
"""Tell a campaign's planners that a worker stopped at a permission prompt or ended.

A harness hook on `Notification` and `SessionEnd`, registered machine-wide by
`scripts/install-hooks.sh`. It is the push half of rule-check#481: a session
reports its own stop, so no watch has to be running to see it.

TWO HALVES, ONE FILE.

  the hook    runs in the session. It keeps two events and drops the rest:
              `Notification` whose `notification_type` is `permission_prompt`,
              and `SessionEnd` whose `reason` is anything but `clear` --
              `/clear` fires `SessionEnd` and keeps the session (probed,
              rule-check#296 NOTE 5718410982). It reads its own name from
              `herdr agent list` by the payload's session id, and anything
              but a `<slug>-worker-<n>` pushes nothing: a planner's own
              prompt is the person's, and a session of no campaign has nobody
              to tell. Then it starts the sender detached and returns.
              NO STDOUT, NEVER NON-ZERO, no exception escapes (one that would is
              a line in `$TMPDIR/campaign-push-crash.log`): `SessionEnd`
              hooks share one short timeout, so the hook does one listing
              (26 ms here, under `campaign-name-session.py`'s own timeout)
              and nothing else that waits.
  the sender  `--send`, in a session of its own so it outlives the pane that
              started it. Per planner: deliver, read back, log one line.

THE TARGET is every listed `<slug>-planner-<n>` of the sender's slug, read
fresh at each push, so a planner that was compacted or replaced is found by
name (P7). No name tells a helper planner from the campaign's own, so both
get it (DECISION 5718822470, call 3).

DELIVERY, per target:

  1. wait    until herdr reads the target `idle` or `done`, every WAIT_EVERY
             seconds, at most READY_POLLS times. A prompt into a working pane
             was once read as text inside a tool result and dropped
             (rule-check#296 NOTE 5718552609). A send herdr refuses
             (`agent_blocked`) is the same wait.
  2. before  count the user records in the target's transcript carrying this
             push's text as typed text. The text holds the push's own time,
             so the count is of this push alone. A tool result is not typed
             text, which is the drop this reads for.
  3. send    `herdr agent prompt <pane> <text>`.
  4. after   count again every WAIT_EVERY seconds, at most LANDED_POLLS
             times, until it is more than `before`. No gain: back to 1,
             ATTEMPTS times in all. A text that lands later than that window
             is sent again, so a planner may read one push twice; `before`
             is re-counted, and the log then says `delivered`.

THE TEXT lands as a user turn in a planner's pane, so it says it is
machine-made, asks only for a look, and carries no instruction and no fact
the planner cannot re-read from `herdr agent list`. `push_text` is its one
home, and the suite holds it to that.

THE LOG is `<campaign>/runtime/push.log`, one line per push per target, the
undelivered ones included: what was read, from where, and which branch was
taken. With no campaign directory on this machine it is
`$TMPDIR/campaign-push-<slug>.log`, and the line says so.

  outcomes   delivered     the transcript gained the text as a user record
             undelivered   no gain after ATTEMPTS sends, or never ready
             gone          the target left herdr's list while this waited
             unread        the target's transcript could not be read, so the
                           text was sent once and nothing was confirmed (seen
                           live on a planner that had had no turn yet)
             no-planner    herdr lists no planner of the slug

Usage: campaign-push.py                  the hook: one JSON payload on stdin
       campaign-push.py --send <event> <name> <pane> <detail>
"""
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[3]
NAME_SCRIPT = HERE / "campaign-name-session.py"
TRANSCRIPT_SCRIPT = HERE / "campaign-transcript.py"
DIRECTORY_SCRIPT = BASE / "scripts" / "campaign-directory.py"

PERMISSION = "permission_prompt"
KEPT_SESSION = "clear"   # the one SessionEnd reason after which the session lives on
WORKER, PLANNER = "worker", "planner"
READY = ("idle", "done")

WAIT_EVERY = 5
READY_POLLS = 360    # 30 min: a planner's long turn; past it the push is logged undelivered
LANDED_POLLS = 12    # 60 s: P2 measured 2 s from the prompt to the target's answer
ATTEMPTS = 2
DETAIL_CHARS = 120
CRASH_LOG = Path(tempfile.gettempdir()) / "campaign-push-crash.log"
OPENING = "campaign-push (machine-made, no instruction):"


def load(path, name):
    """The script at `path` as a module: these are scripts, not a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------ calculations


def event_of(payload):
    """(event, detail) of a payload this pushes, or (None, why it does not)."""
    name = payload.get("hook_event_name")
    if name == "Notification":
        kind = payload.get("notification_type")
        if kind != PERMISSION:
            return None, f"Notification of type {kind!r}"
        return "blocked", str(payload.get("message") or PERMISSION)
    if name == "SessionEnd":
        reason = payload.get("reason")
        if reason == KEPT_SESSION:
            return None, "SessionEnd by /clear, which keeps the session"
        return "ended", f"reason {reason}"
    return None, f"event {name!r}"


def sender_of(sessions, session_id, names):
    """The `<slug>-worker-<n>` name herdr holds for this session, or None."""
    row = sessions.get(session_id)
    if row is None or names.role_word(row["name"]) != WORKER:
        return None
    return row["name"]


def planners(sessions, slug, names):
    """[(session id, name, pane, status)] of every listed planner of <slug>."""
    return sorted(((sid, r["name"], r["pane"], r["status"])
                   for sid, r in sessions.items()
                   if names.campaign_of(r["name"]) == slug
                   and names.role_word(r["name"]) == PLANNER),
                  key=lambda p: p[1])


def push_text(event, name, pane, detail, stamp):
    """The one line a planner's pane receives. No instruction: it names what
    happened and where the planner reads it for itself."""
    detail = " ".join(str(detail).split())[:DETAIL_CHARS]
    return (f"{OPENING} {name} in {pane} {event} at {stamp} ({detail}). "
            f"`herdr agent list` shows it.")


def landed(lines, text, texts):
    """How many user records carry <text> as typed text. `texts` is
    campaign-transcript's reader of a message's text blocks, which leaves a
    tool result out."""
    n = 0
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if (not isinstance(r, dict) or r.get("type") != "user"
                or r.get("isMeta") or r.get("isSidechain")):
            continue
        if text in "".join(texts((r.get("message") or {}).get("content"))):
            n += 1
    return n


# ----------------------------------------------------------------- actions


def deliver(sid, text, read_sessions, count, prompt, sleep=time.sleep):
    """(outcome, why) of one push to the session <sid>. `count(sid)` is (how
    many user records carry the text, None) or (None, why not read). Every
    reader is handed in, so the suite drives each branch with no pane."""
    why = "never sent"
    polls = 0
    for attempt in range(1, ATTEMPTS + 1):
        while True:
            sessions, err = read_sessions()
            row = None if sessions is None else sessions.get(sid)
            status = None if row is None else row["status"]
            if sessions is not None and row is None:
                return "gone", f"herdr no longer lists {sid}; {why}"
            if status in READY:
                before, err = count(sid)
                if before is None:
                    sent, note = prompt(row["pane"], text)
                    return "unread", (f"transcript not read ({err}); sent once, "
                                      f"herdr said {note}")
                sent, note = prompt(row["pane"], text)
                if sent:
                    break
                why = f"herdr refused the send: {note}"
            else:
                why = (f"herdr agent list not read: {err}" if sessions is None
                       else f"target read {status}")
            polls += 1
            if polls >= READY_POLLS:
                return "undelivered", (f"not ready after {polls} polls of "
                                       f"{WAIT_EVERY}s; last: {why}")
            sleep(WAIT_EVERY)
        for _ in range(LANDED_POLLS):
            sleep(WAIT_EVERY)
            after, err = count(sid)
            if after is not None and after > before:
                return "delivered", (f"user records carrying it {before} -> "
                                     f"{after}, send {attempt}, after {polls} "
                                     f"waiting polls")
        why = (f"send {attempt} to {row['pane']} gained no user record in "
               f"{LANDED_POLLS * WAIT_EVERY}s (still {before})")
    return "undelivered", why


def log_path(slug):
    """(path, where it came from). The campaign's `runtime/`, or $TMPDIR."""
    try:
        r = subprocess.run([sys.executable, str(DIRECTORY_SCRIPT), slug, str(BASE)],
                           capture_output=True, text=True, timeout=30)
        word = r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        word = f"unknown ({e.__class__.__name__})"
    if word.startswith("/") and Path(word, "runtime").is_dir():
        return Path(word, "runtime", "push.log"), "campaign-directory.py"
    return (Path(tempfile.gettempdir()) / f"campaign-push-{slug}.log",
            f"$TMPDIR, campaign-directory.py said {word!r}")


def send(event, name, pane, detail, names, transcript, prompt,
         sleep=time.sleep, now=None, out=None):
    """The sender: one logged line per planner of <name>'s campaign."""
    stamp = (now or dt.datetime.now)().strftime("%Y-%m-%dT%H:%M:%S")
    slug = names.campaign_of(name)
    path, where = out or log_path(slug)
    text = push_text(event, name, pane, detail, stamp)

    def line(target, outcome, why):
        with open(path, "a") as f:
            f.write(f"{stamp} {event} {name} {pane} -> {target}: {outcome}; "
                    f"{why}; log by {where}\n")

    sessions, err = names.herdr_sessions()
    if sessions is None:
        line("?", "undelivered", f"herdr agent list not read: {err}")
        return
    found = planners(sessions, slug, names)
    if not found:
        line("-", "no-planner", f"herdr agent list holds {len(sessions)} "
                                f"session(s), no planner of {slug}")
        return

    def count(sid):
        p, err = transcript.transcript_path(sid)
        if p is None:
            return None, err
        try:
            lines = p.read_text(errors="replace").splitlines()
        except OSError as e:
            return None, f"{p}: {e.__class__.__name__}"
        return landed(lines, text, transcript.texts), None

    for sid, target, target_pane, _ in found:
        outcome, why = deliver(
            sid, text, names.herdr_sessions, count, prompt, sleep)
        line(f"{target} {target_pane}", outcome, why)


def herdr_prompt(pane, text):
    """(sent, what herdr said). The send itself, guarded as every driving
    herdr command here is."""
    if os.environ.get("HERDR_ENV") != "1":
        return False, "HERDR_ENV is not 1"
    try:
        r = subprocess.run(["herdr", "agent", "prompt", pane, text],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, e.__class__.__name__
    if r.returncode == 0:
        return True, "exit 0"
    return False, (r.stderr or r.stdout).strip()[:80] or f"exit {r.returncode}"


def hook(payload, names, spawn):
    """The hook half: (started, why). Spawns the sender for a worker's kept
    event and nothing else."""
    event, detail = event_of(payload)
    if event is None:
        return False, detail
    sid = payload.get("session_id")
    sessions, err = names.herdr_sessions()
    if sessions is None:
        return False, f"herdr agent list not read: {err}"
    name = sender_of(sessions, sid, names)
    if name is None:
        return False, f"session {sid} is no worker of a campaign"
    spawn([sys.executable, str(Path(__file__).resolve()), "--send", event, name,
           sessions[sid]["pane"], detail])
    return True, name


def spawn_detached(argv):
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def main(argv):
    if argv[1:2] != ["--send"]:
        payload = json.load(sys.stdin)
        if event_of(payload)[0] is None:   # most events: no listing, no import
            return
    names = load(NAME_SCRIPT, "campaign_name_session")
    if argv[1:2] == ["--send"]:
        event, name, pane, detail = argv[2:6]
        transcript = load(TRANSCRIPT_SCRIPT, "campaign_transcript")
        send(event, name, pane, detail, names, transcript, herdr_prompt)
        return
    hook(payload, names, spawn_detached)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as e:   # a hook's crash never reaches the session it runs in
        with open(CRASH_LOG, "a") as f:
            f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} "
                    f"{sys.argv[1:3]} {e.__class__.__name__}: {e}\n")
    sys.exit(0)
