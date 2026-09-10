#!/usr/bin/env python3
# witnesses: H1_HeartbeatRetiresADoneWorker, H1b_HeartbeatRetiresNoHolder, L1b_PromptAfterTheResetIsAnswered, SessionCompactsBetweenSubIssues
"""Prove campaign-heartbeat reads each session's transcript and banner and
gives one verdict per session -- and that each branch is pinned by a case.

The transcript cases feed `transcript_reading` records in the shape this
machine's transcripts were measured to have (2026-09-10): a release is a
tool result, a compaction a `compact_boundary` record, a prompt a user
record carrying text. The run cases call `main` in-process over a fake
`herdr`, `gh` and `sleep` on a PATH holding nothing else, and a fake HOME
holding the transcripts, so nothing here reads or drives a real pane; every
action is asserted on what the fake herdr was ASKED.

Then EVERY BRANCH IS BROKEN IN TURN: the source is mutated in memory, loaded
as the same file, and the case named for that branch must go red by its own
assertion. A case that crashes has asserted nothing, so a crash fails the
mutation. A control run of every case on the unmutated source goes first.

Usage: .claude/skills/assuming-role/scripts/campaign-heartbeat-test.py
"""
import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "campaign-heartbeat.py"
ANCHOR = "campaign-claim: released"
PANE = "w1:p2"


def load(source):
    """The script from `source`, loaded AS its own file, so the siblings it
    loads by path are the real ones."""
    m = types.ModuleType("campaign_heartbeat")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return m


# ------------------------------------------------------------- records


def ts(minute):
    return f"2026-09-10T10:{minute:02d}:00.000Z"


def release(minute, pane=PANE, branch="rc/1-x"):
    return result(minute, f"sent /compact\n{ANCHOR} {branch} in {pane}")


def boundary(minute, post=9000):
    return {"type": "system", "subtype": "compact_boundary",
            "timestamp": ts(minute), "compactMetadata": {"postTokens": post}}


def usage(minute, tokens, **extra):
    return dict({"type": "assistant", "timestamp": ts(minute), "message": {
        "usage": {"input_tokens": 2, "cache_creation_input_tokens": 998,
                  "cache_read_input_tokens": tokens - 1000}}}, **extra)


def prompt(minute, text="Work sub-issue kalaluthien/campaign-base#9 now", **extra):
    return dict({"type": "user", "timestamp": ts(minute),
                 "message": {"content": text}}, **extra)


def call(minute, tool="Bash"):
    """An assistant turn calling a tool, as the release turn does after the
    release: a REPORT, a memory filed."""
    return {"type": "assistant", "timestamp": ts(minute), "message": {
        "content": [{"type": "tool_use", "name": tool, "input": {}}],
        "usage": {"input_tokens": 1, "cache_creation_input_tokens": 0,
                  "cache_read_input_tokens": 5000}}}


def lines(*records):
    return [json.dumps(r) for r in records]


TOOK = "claimed tk/"


def result(minute, text):
    return {"type": "user", "timestamp": ts(minute), "message": {"content": [
        {"type": "tool_result", "content": text}]}}


def claimed(minute, branch="tk/9-next"):
    """The tool result `campaign-claim.py take` prints when it cuts a claim."""
    return result(minute, f"...\nclaimed {branch}\n  The ref IS the claim")


def reading(m, *records, pane=PANE):
    return m.transcript_reading(lines(*records), ANCHOR, pane, TOOK)


# ------------------------------------------------------------- cases

CASES = {}


def case(name):
    def register(fn):
        CASES[name] = fn
        return fn
    return register


# transcript_reading

@case("a release is a tool result naming this pane")
def _(m):
    r = reading(m, release(1))
    return r["released"] == ts(1), r


@case("another pane's release, read into this transcript, is not this one's")
def _(m):
    r = reading(m, release(1, pane="w1:p9"))
    return r["released"] is None, r


@case("a release quoted in a prompt or a summary is not a release")
def _(m):
    line = f"{ANCHOR} rc/1-x in {PANE}"
    r = reading(m, prompt(1, line), prompt(2, line, isCompactSummary=True))
    return r["released"] is None, r


@case("a release line quoted mid-line in a tool result is not a release")
def _(m):
    r = reading(m, {"type": "user", "timestamp": ts(1), "message": {
        "content": [{"type": "tool_result", "content":
                     f"the run printed {ANCHOR} rc/1-x in {PANE}"}]}})
    return r["released"] is None, r


@case("the compaction marker printed as text is not a compaction")
def _(m):
    r = reading(m, release(1), {"type": "user", "timestamp": ts(2), "message": {
        "content": [{"type": "tool_result", "content":
                     "Compacted (ctrl+o to see full summary)"}]}})
    return r["compacted"] is None, r


@case("every last is by time, not by position in the file")
def _(m):
    r = reading(m, release(5), release(1), boundary(3))
    return r["released"] == ts(5) and m.compacted_since_release(r)[0] == "stale", r


@case("the LAST release decides: release, compact, release is stale")
def _(m):
    r = reading(m, release(1), boundary(2), release(3))
    return m.compacted_since_release(r)[0] == "stale", r


@case("release then compaction is compacted, and no release is unknown")
def _(m):
    a = m.compacted_since_release(reading(m, release(1), boundary(2)))[0]
    b = m.compacted_since_release(reading(m, boundary(2)))[0]
    return (a, b) == ("compacted", "unknown"), (a, b)


@case("context is the latest usage record's input plus cache tokens")
def _(m):
    r = reading(m, usage(1, 300_000), usage(2, 120_000))
    return r["context"] == 120_000, r


@case("context after a compaction is the boundary's postTokens")
def _(m):
    r = reading(m, usage(1, 300_000), boundary(2, post=8_000))
    return r["context"] == 8_000, r


@case("a subagent's records are not this session's context")
def _(m):
    r = reading(m, usage(1, 50_000), usage(2, 400_000, isSidechain=True))
    return r["context"] == 50_000, r


@case("a prompt is a user record carrying text")
def _(m):
    r = reading(m, prompt(4))
    return r["prompted"] == ts(4), r


@case("the compaction's own echoes are not a prompt")
def _(m):
    r = reading(m, prompt(1, "<command-name>/compact</command-name>\n"),
                prompt(2, "<local-command-stdout>Compacted</local-command-stdout>"))
    return r["prompted"] is None, r


@case("the bare /compact that release queues is not a prompt")
def _(m):
    r = reading(m, release(1), prompt(2, "/compact"), boundary(3))
    return r["prompted"] is None, r


@case("a synthetic record, a limit banner, does not zero the context")
def _(m):
    r = reading(m, usage(1, 351_805), {"type": "assistant", "timestamp": ts(2),
        "message": {"model": "<synthetic>", "content": [{"type": "text",
        "text": "You've hit your session limit"}], "usage": {
        "input_tokens": 0, "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0}}})
    return r["context"] == 351_805, r


@case("a person's `/compact <focus>` is a prompt")
def _(m):
    r = reading(m, prompt(4, "/compact keep the review findings"))
    return r["prompted"] == ts(4), r


@case("a claim cut in a tool result is held")
def _(m):
    r = reading(m, release(1), claimed(2))
    return r["held"] == ["tk/9-next"], r


@case("a claim cut BEFORE an unrelated release is still held")
def _(m):
    r = reading(m, claimed(1), release(2), boundary(3))
    return r["held"] == ["tk/9-next"], r


@case("a claim released later in this pane is not held")
def _(m):
    r = reading(m, claimed(1), release(2, branch="tk/9-next"), boundary(3))
    return r["held"] == [], r


@case("prose opening with 'claimed' is not a claim")
def _(m):
    r = reading(m, release(1), result(2, "claimed the same way."))
    return r["held"] == [], r


@case("an assistant turn with text and no tool call is not acting")
def _(m):
    r = reading(m, release(1), {"type": "assistant", "timestamp": ts(2),
        "message": {"content": [{"type": "text", "text": "done"}]}})
    return r["acted"] is None, r


@case("an assistant record without usage leaves the context as it was")
def _(m):
    try:
        r = reading(m, usage(1, 70_000), {"type": "assistant",
                    "timestamp": ts(2), "message": {"content": []}})
    except Exception as e:  # noqa: BLE001 -- raising is not reading
        return False, f"raised {e.__class__.__name__}"
    return r["context"] == 70_000, r


@case("a tool call is read as the session acting")
def _(m):
    r = reading(m, release(1), call(2))
    return r["acted"] == ts(2), r


@case("a harness note and a summary are not a prompt")
def _(m):
    r = reading(m, prompt(1, "Stop hook feedback: x", isMeta=True),
                prompt(2, "This session is being continued", isCompactSummary=True))
    return r["prompted"] is None, r


# verdict

IDLE = (True, None)
BUSY = (False, "status is working, not idle")
NONE = "no limit (herdr lists w1:p2 idle)"
DONE = {"released": ts(1), "compacted": ts(2), "prompted": None,
        "acted": None, "held": [], "context": 9000, "context_at": ts(2),
        "records": 2}


def big(tokens):
    return dict(DONE, released=None, compacted=None, context=tokens)


@case("fire: a banner on another pane")
def _(m):
    v = m.verdict("worker", False, IDLE, "session 2026-09-10T21:00+09:00", big(10))
    return v[0] == "fire", v


@case("a passed banner is not a fire")
def _(m):
    v = m.verdict("worker", False, IDLE, "passed 2026-09-10T09:00+09:00", big(10))
    return v[0] == "keep" and "has passed" in v[1], v


@case("compact: idle at the threshold")
def _(m):
    v = m.verdict("worker", False, IDLE, NONE, big(m.COMPACT_AT))
    return v[0] == "compact", v


@case("one token under the threshold is keep")
def _(m):
    v = m.verdict("worker", False, IDLE, NONE, big(m.COMPACT_AT - 1))
    return v[0] == "keep", v


@case("the own pane is compacted while it works, its banner unread")
def _(m):
    v = m.verdict("planner", True, BUSY, None, big(250_000))
    return v[0] == "compact", v


@case("retire: a worker, idle, released then compacted, no prompt since")
def _(m):
    v = m.verdict("worker", False, IDLE, NONE, DONE)
    return v[0] == "retire", v


@case("tool calls in the release turn, before the compaction, still retire")
def _(m):
    between = "2026-09-10T10:01:30.000Z"   # after the release, before the compaction
    v = m.verdict("worker", False, IDLE, NONE, dict(DONE, acted=between))
    return v[0] == "retire", v


@case("a tool call after the compaction is not retired")
def _(m):
    v = m.verdict("worker", False, IDLE, NONE, dict(DONE, acted=ts(3)))
    return v[0] == "keep", v


@case("a worker holding a claim is not retired")
def _(m):
    v = m.verdict("worker", False, IDLE, NONE, dict(DONE, held=["tk/9-next"]))
    return v[0] == "keep", v


@case("a worker prompted since its release is not retired")
def _(m):
    v = m.verdict("worker", False, IDLE, NONE, dict(DONE, prompted=ts(3)))
    return v[0] == "keep", v


@case("a planner is never retired")
def _(m):
    v = m.verdict("planner", False, IDLE, NONE, DONE)
    return v[0] == "keep", v


@case("the own pane is never retired")
def _(m):
    v = m.verdict("worker", True, BUSY, None, DONE)
    return v[0] == "keep", v


@case("keep: a working pane, whatever its context")
def _(m):
    v = m.verdict("worker", False, BUSY, NONE, big(900_000))
    return v[0] == "keep", v


@case("keep: an unread banner, whatever its context")
def _(m):
    v = m.verdict("worker", False, IDLE, "could not read: herdr exited 1",
                  big(900_000))
    return v[0] == "keep" and "banner not read" in v[1], v


@case("keep: an unread transcript")
def _(m):
    try:
        v = m.verdict("worker", False, IDLE, NONE, "0 transcript(s) named x.jsonl")
    except Exception as e:  # noqa: BLE001 -- raising is not answering keep
        return False, f"raised {e.__class__.__name__}"
    return v[0] == "keep" and "transcript not read" in v[1], v


# the run, end to end

HERDR = r'''#!%(py)s
import json, os, sys
a = sys.argv[1:]
d = %(dir)r
if a[:2] == ["agent", "list"]:
    print(open(os.path.join(d, "listing.json")).read()); sys.exit(0)
if a[:2] == ["pane", "read"]:
    p = os.path.join(d, "screen-" + a[2].replace(":", "_"))
    print(open(p).read() if os.path.exists(p) else ""); sys.exit(0)
if a[:2] == ["agent", "prompt"]:
    with open(os.path.join(d, "prompts.log"), "a") as fh:
        fh.write("HERDR_ENV=%%s pane=%%s prompt=%%s\n"
                 %% (os.environ.get("HERDR_ENV", "unset"), a[2], a[3]))
    sys.exit(int(open(os.path.join(d, "prompt-exit")).read()))
sys.exit(1)
'''
GH = r'''#!%(py)s
import sys
if sys.argv[1:3] == ["api", "repos/kalaluthien/campaign-base/issues/7"]:
    print('["campaign", "campaign:tk"]'); sys.exit(0)
sys.exit(1)
'''


def banner(delta_hours):
    """A banner in the captured shape whose reset is `delta_hours` from now,
    in local time with no zone, so the reading does not depend on the clock."""
    at = dt.datetime.now().astimezone() + dt.timedelta(hours=delta_hours)
    clock = at.strftime("%I:%M%p").lstrip("0").lower()
    return f"  ⎿  You've hit your session limit · resets {clock}\n"


def row(sid, name, pane, status="idle"):
    r = {"agent_session": {"value": sid}, "pane_id": pane,
         "agent_status": status, "cwd": "/tmp"}
    if name:
        r["name"] = name
    return r


FLEET = [  # (sid, name, pane, status, records, screen)
    ("S1", "tk-planner-1", "w1:p1", "working", [usage(1, 250_000)], None),
    ("S2", "tk-worker-2", "w1:p2", "idle",
     [release(1, "w1:p2"), call(2), result(2, "claimed the same way."),
      prompt(3, "/compact"), boundary(4)], ""),
    ("S3", "tk-worker-3", "w1:p3", "idle", [usage(1, 210_000)], ""),
    ("S4", "tk-worker-4", "w1:p4", "idle", [usage(1, 10)], banner(2)),
    ("S5", "tk-worker-5", "w1:p5", "idle", [usage(1, 10)], banner(2)),
    ("S6", "tk-worker-6", "w1:p6", "working", [usage(1, 900_000)], ""),
    ("S7", "other-worker-7", "w1:p7", "idle", [usage(1, 900_000)], ""),
    ("S8", None, "w1:p8", "idle", [usage(1, 900_000)], ""),
    # A planner that is not this one also releases and compacts: never retired.
    ("S9", "tk-planner-9", "w1:p9", "idle", [release(1, "w1:p9"), boundary(2)], ""),
    # Cut a claim in its release turn, before the compaction: holds work.
    ("SB", "tk-worker-11", "w1:pB", "idle",
     [release(1, "w1:pB"), claimed(2), boundary(3)], ""),
    # Two transcripts carry this id: unread, so keep, never compact.
    ("SA", "tk-worker-10", "w1:pA", "idle", [usage(1, 900_000)], ""),
]


def fleet(d, prompt_exit=0, sh=True):
    d = Path(d)
    b = d / "bin"
    b.mkdir(parents=True)
    for name, body in (("herdr", HERDR), ("gh", GH)):
        (b / name).write_text(body % {"py": sys.executable, "dir": str(d)})
        (b / name).chmod(0o755)
    (b / "sleep").write_text("#!/bin/sh\nexit 0\n")
    (b / "sleep").chmod(0o755)
    if sh:
        (b / "sh").symlink_to("/bin/sh")
    (d / "prompt-exit").write_text(str(prompt_exit))
    (d / "listing.json").write_text(json.dumps({"result": {"agents": [
        row(sid, name, pane, status) for sid, name, pane, status, _, _ in FLEET]}}))
    proj = d / "home" / ".claude" / "projects" / "-tmp"
    proj.mkdir(parents=True)
    for sid, _, pane, _, records, screen in FLEET:
        (proj / f"{sid}.jsonl").write_text("\n".join(lines(*records)) + "\n")
        if screen is not None:
            (d / ("screen-" + pane.replace(":", "_"))).write_text(screen)
    other = d / "home" / ".claude" / "projects" / "-other"
    other.mkdir()
    (other / "SA.jsonl").write_text(lines(usage(1, 900_000))[0] + "\n")
    return d


def heartbeat(m, d, *args, own="w1:p1"):
    """(exit, stdout, prompts) of `main` run in-process inside the fake."""
    env = {"PATH": str(d / "bin"), "HOME": str(d / "home"), "TMPDIR": str(d)}
    if own:
        env["HERDR_PANE_ID"] = own
    saved, cwd = dict(os.environ), os.getcwd()
    os.environ.pop("HERDR_ENV", None)
    os.environ.pop("HERDR_PANE_ID", None)
    os.environ.update(env)
    os.chdir(d)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            code = m.main(list(args))
    finally:
        os.chdir(cwd)
        os.environ.clear()
        os.environ.update(saved)
    log = d / "prompts.log"
    return code, out.getvalue(), (log.read_text().splitlines()
                                  if log.exists() else [])


def wait_for(d, pane, text, before):
    """The detached sleeper writes after `main` returns: poll, bounded."""
    for _ in range(50):
        log = d / "prompts.log"
        got = [ln for ln in (log.read_text().splitlines() if log.exists() else [])
               if f"pane={pane} " in ln and text in ln]
        if len(got) > before:
            return got
        time.sleep(0.1)
    return got


def verdicts(out):
    return {ln.split()[1]: ln.split()[0] for ln in out.splitlines()
            if ln.split() and ln.split()[0] in ("fire", "compact", "retire", "keep")}


@case("the run gives one verdict per session of the campaign, and no other")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        code, out, _ = heartbeat(m, fleet(d), "7")
    want = {"w1:p1": "compact", "w1:p2": "retire", "w1:p3": "compact",
            "w1:p4": "fire", "w1:p5": "fire", "w1:p6": "keep",
            "w1:p9": "keep", "w1:pA": "keep", "w1:pB": "keep"}
    return code == 0 and verdicts(out) == want, out


@case("the run says what it read and from where")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        code, out, _ = heartbeat(m, fleet(d), "7")
    return ("9 of tk (#7)" in out and "2 transcript(s) named SA.jsonl" in out and "S3.jsonl" in out
            and "own pane, banner not read" in out and "herdr idle" in out), out


@case("without --apply nothing is sent and each action says what it would do")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        code, out, sent = heartbeat(m, fleet(d), "7")
    return (code == 0 and sent == []
            and "would send /compact to w1:p1" in out
            and "would send /exit to w1:p2" in out
            and "would run campaign-limit-reset.py w1:p4 --fire w1:p1" in out), (sent, out)


@case("--apply sends each action, guarded, to the pane it names")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        d = fleet(d)
        code, out, sent = heartbeat(m, d, "7", "--apply")
    want = {"HERDR_ENV=1 pane=w1:p1 prompt=/compact",
            "HERDR_ENV=1 pane=w1:p2 prompt=/exit",
            "HERDR_ENV=1 pane=w1:p3 prompt=/compact"}
    return code == 0 and want <= set(sent) and "sent /exit to w1:p2" in out, (sent, out)


@case("two banners schedule one wake, into the own pane")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        d = fleet(d)
        code, out, _ = heartbeat(m, d, "7", "--apply")
        woke = wait_for(d, "w1:p1", "usage window reset", 0)
        time.sleep(0.3)
        woke = wait_for(d, "w1:p1", "usage window reset", len(woke) - 1)
    return (code == 0 and len(woke) == 1 and "HERDR_ENV=1" in woke[0]
            and "fired already for w1:p4" in out
            and out.count("scheduled pid") == 1), (woke, out)


@case("an action that could not be sent says so and exits 1")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        code, out, _ = heartbeat(m, fleet(d, prompt_exit=3), "7", "--apply")
    return code == 1 and "could not send /exit to w1:p2" in out, out


@case("with no own pane, --apply cannot wake anyone and exits 1")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        code, out, _ = heartbeat(m, fleet(d), "7", "--apply", own=None)
    return code == 1 and "could not send the wake for w1:p4" in out, out


@case("...while without --apply the same run exits 0")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        code, out, _ = heartbeat(m, fleet(d), "7", own=None)
    return code == 0 and "would run campaign-limit-reset.py w1:p4" in out, out


@case("a wake that could not be scheduled exits 1")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        code, out, _ = heartbeat(m, fleet(d, sh=False), "7", "--apply")
    return code == 1 and "could not fire" in out, out


@case("an unreadable slug is exit 1 and no verdict")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        code, out, sent = heartbeat(m, fleet(d), "8", "--apply")
    return (code == 1 and "could not read the slug" in out
            and not verdicts(out) and sent == []), out


# ------------------------------------------------------------- mutations

# (the branch broken, old text, new text, the case that must go red)
MUTATIONS = [
    ("fire on a banner", 'if word == "limit":', 'if False:',
     "fire: a banner on another pane"),
    ("passed is not a fire", 'if line.startswith("passed "):\n        return "passed"',
     'if line.startswith("passed "):\n        return "limit"',
     "a passed banner is not a fire"),
    ("compact at the threshold", 'if reading["context"] >= COMPACT_AT:',
     'if False:', "compact: idle at the threshold"),
    ("the threshold is inclusive", 'if reading["context"] >= COMPACT_AT:',
     'if reading["context"] > COMPACT_AT:', "compact: idle at the threshold"),
    ("the own pane skips the idle reading", "is_own = pane == own",
     "is_own = False", "the run gives one verdict per session of the campaign, and no other"),
    ("retire", 'if (role == "worker" and not own and since == "compacted"',
     'if False and (role == "worker"', "retire: a worker, idle, released then compacted, no prompt since"),
    ("retire needs no prompt since", 'and not (reading["prompted"]', 'and not (False',
     "a worker prompted since its release is not retired"),
    ("retire only a worker", 'if (role == "worker" and not own', 'if (True and not own',
     "a planner is never retired"),
    ("never retire the own pane", 'if (role == "worker" and not own and',
     'if (role == "worker" and', "the own pane is never retired"),
    ("keep a working pane", "if not idle[0]:", "if False:",
     "keep: a working pane, whatever its context"),
    ("keep an unread banner", 'if word == "unread":', "if False:",
     "keep: an unread banner, whatever its context"),
    ("keep an unread transcript", "if isinstance(reading, str):", "if False:",
     "keep: an unread transcript"),
    ("the release names this pane", "ln.startswith(anchor) and ln.endswith(tail)",
     "ln.startswith(anchor)", "another pane's release, read into this transcript, is not this one's"),
    ("the release is a tool result", "for ln in result_lines(content):",
     "for ln in texts(content) + list(result_lines(content)):",
     "a release quoted in a prompt or a summary is not a release"),
    ("the release opens its line", "ln.startswith(anchor) and ln.endswith(tail)",
     "anchor in ln and ln.endswith(tail)", "a release line quoted mid-line in a tool result is not a release"),
    ("the compaction is a record type", 'r.get("subtype") == "compact_boundary"',
     'r.get("subtype") == "compact_boundary" or "Compacted" in line',
     "the compaction marker printed as text is not a compaction"),
    ("last by time", "if out[key] is None or ts > out[key]:",
     "if True:", "every last is by time, not by position in the file"),
    ("the LAST release", 'later("released", ts)',
     'out["released"] = out["released"] or ts', "the LAST release decides: release, compact, release is stale"),
    ("compacted means after the release", "if comp and comp > rel:", "if comp:",
     "the LAST release decides: release, compact, release is stale"),
    ("context from usage", '"cache_read_input_tokens")))', '"input_tokens",)))',
     "context is the latest usage record's input plus cache tokens"),
    ("context from the boundary",
     'size(ts, (r.get("compactMetadata") or {}).get("postTokens"))', "pass",
     "context after a compaction is the boundary's postTokens"),
    ("skip a subagent", 'if not isinstance(r, dict) or r.get("isSidechain"):',
     "if not isinstance(r, dict):", "a subagent's records are not this session's context"),
    ("a prompt is text", 'later("prompted", ts)', "pass",
     "a prompt is a user record carrying text"),
    ("the compaction's echo", 'COMPACTION_ECHOES = ("<command-name>/compact<", "<local-command-")',
     'COMPACTION_ECHOES = ("\\x00",)', "the compaction's own echoes are not a prompt"),
    ("a harness note", 'if r.get("isMeta") or r.get("isCompactSummary"):',
     'if r.get("isCompactSummary"):', "a harness note and a summary are not a prompt"),
    ("only this campaign's sessions", 'if names.campaign_of(row["name"]) == slug',
     'if names.campaign_of(row["name"]) is not None', "the run gives one verdict per session of the campaign, and no other"),
    ("nothing without --apply", "        if not args.apply:\n            print(f\"would send",
     "        if False:\n            print(f\"would send",
     "without --apply nothing is sent and each action says what it would do"),
    ("the prompt is guarded", 'r = run("herdr", "agent", "prompt", pane, text,\n                env=dict(os.environ, HERDR_ENV="1"))',
     'r = run("herdr", "agent", "prompt", pane, text)',
     "--apply sends each action, guarded, to the pane it names"),
    ("one wake per run", "if fired:", "if False:",
     "two banners schedule one wake, into the own pane"),
    ("the bare /compact is an echo", "if said and said != QUEUED_COMPACT and not",
     "if said and not", "the bare /compact that release queues is not a prompt"),
    ("only the bare /compact", "said != QUEUED_COMPACT and not",
     "not said.startswith(QUEUED_COMPACT) and not",
     "a person's `/compact <focus>` is a prompt"),
    ("read a claim cut", "if took and ln.startswith(took):", "if False:",
     "a claim cut in a tool result is held"),
    ("a release frees its claim", "if b not in freed or freed[b] < t)", "if True)",
     "a claim released later in this pane is not held"),
    ("a claim before the release counts", "if b not in freed or freed[b] < t)",
     'if (b not in freed or freed[b] < t) and t > (out["released"] or ""))',
     "a claim cut BEFORE an unrelated release is still held"),
    ("no claim held", 'and not reading["held"]', "and True",
     "a worker holding a claim is not retired"),
    ("the run reads this campaign's claims", 'f"{claim.CLAIMED} {slug}/")', "None)",
     "the run gives one verdict per session of the campaign, and no other"),
    ("the claim prefix names the slug", 'f"{claim.CLAIMED} {slug}/")', 'f"{claim.CLAIMED} ")',
     "the run gives one verdict per session of the campaign, and no other"),
    ("only a tool call is acting", 'b.get("type") == "tool_use"',
     'b.get("type") in ("tool_use", "text")',
     "an assistant turn with text and no tool call is not acting"),
    ("a record without usage", "            if not isinstance(u, dict):\n                continue\n", "",
     "an assistant record without usage leaves the context as it was"),
    ("skip a synthetic record", 'elif kind == "assistant" and msg.get("model") != "<synthetic>":',
     'elif kind == "assistant":', "a synthetic record, a limit banner, does not zero the context"),
    ("read a tool call", 'later("acted", ts)', "pass",
     "a tool call is read as the session acting"),
    ("no tool call after the compaction", 'and not (reading["acted"] and reading["acted"] > comp)',
     "and True", "a tool call after the compaction is not retired"),
    ("the release turn's calls do not block", 'reading["acted"] > comp)',
     'reading["acted"] > rel)', "tool calls in the release turn, before the compaction, still retire"),
    ("the role off the name", 'role = row["name"].split("-")[-2]', 'role = "worker"',
     "the run gives one verdict per session of the campaign, and no other"),
    ("one transcript per id", "if len(hits) != 1:", "if not hits:",
     "the run gives one verdict per session of the campaign, and no other"),
    ("no own pane, no wake", "            if not own:\n                print(f\"could not send the wake",
     "            if False:\n                print(f\"could not send the wake",
     "with no own pane, --apply cannot wake anyone and exits 1"),
    ("a failed wake is exit 1", "            failed |= r.returncode != 0\n",
     "            pass\n", "a wake that could not be scheduled exits 1"),
    ("a failed send is exit 1", "            failed = True\n        else:",
     "            pass\n        else:", "an action that could not be sent says so and exits 1"),
]


def run_case(m, name):
    try:
        ok, detail = CASES[name](m)
        return bool(ok), detail
    except Exception as e:  # noqa: BLE001 -- a crash is reported, not red
        return None, f"{e.__class__.__name__}: {e}"


def main():
    source = SCRIPT.read_text()
    real = load(source)
    failed = []
    for name in CASES:
        ok, detail = run_case(real, name)
        if not ok:
            failed.append(f"FAIL  {name} -- {str(detail)[:300]}")
    print(f"{len(CASES) - len(failed)}/{len(CASES)} cases pass")
    for label, old, new, name in MUTATIONS:
        count = source.count(old)
        if count != 1:
            failed.append(f"MUTATION {label}: the text to break occurs {count} times")
            continue
        ok, detail = run_case(load(source.replace(old, new)), name)
        if ok is None:
            failed.append(f"MUTATION {label}: {name!r} crashed -- {detail}")
        elif ok:
            failed.append(f"MUTATION {label}: {name!r} stayed green")
    print(f"{len(MUTATIONS)} mutations, "
          f"{sum(1 for f in failed if f.startswith('MUTATION'))} survived or crashed")
    for f in failed:
        print(f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
