#!/usr/bin/env python3
# witnesses: H1_HeartbeatRetiresADoneWorker, H1b_HeartbeatRetiresNoHolder, W1_UnclaimedDriftClearsOnClaim, W1b_SettledDriftClearsOnRelease, L1b_PromptAfterTheResetIsAnswered, SessionCompactsBetweenSubIssues
"""Prove campaign-heartbeat reads each session's transcript and banner and
gives one verdict per session -- and that each branch is pinned by a case.

The transcript cases feed `transcript_reading` records in the shape this
machine's transcripts were measured to have (2026-09-10): a release is a
tool result, a compaction a `compact_boundary` record, a prompt a user
record carrying text. The run cases call `main` in-process over a fake
`herdr`, `gh` and `sleep` on a PATH holding nothing else, and a fake HOME
holding the transcripts, so nothing here reads or drives a real pane; every
action is asserted on what the fake herdr was ASKED. The watch cases drive
`Watch.poll` over readings built here and a clock in minutes, and its reader
once over the same fake.

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


def queued(minute, text="Work sub-issue kalaluthien/campaign-base#9 now",
           mode="prompt", **extra):
    """A prompt typed while the pane was busy, in the measured shape
    (2026-09-11): an attachment record, not a user record."""
    return {"type": "attachment", "timestamp": ts(minute), "attachment": dict(
        {"type": "queued_command", "prompt": text, "commandMode": mode,
         "timestamp": ts(minute)}, **extra)}


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


@case("a prompt typed into a busy pane, between release and compaction, keeps the worker")
def _(m):
    r = reading(m, release(1), queued(2, origin={"kind": "human"}), boundary(3))
    v = m.verdict("worker", False, (True, None), "no limit", r)
    return r["prompted"] == ts(2) and v[0] == "keep", (r, v)


@case("a peer's message queued into the pane is not a prompt")
def _(m):
    r = reading(m, queued(2, "<cross-session-message from=x>", isMeta=True,
                          origin={"kind": "peer"}))
    return r["prompted"] is None, r


@case("a queued command in any mode but prompt is not a prompt")
def _(m):
    r = reading(m, queued(2, "Work sub-issue kalaluthien/campaign-base#9 now",
                          mode="task-notification"))
    return r["prompted"] is None, r


@case("a task notification reaching an idle pane is not a prompt")
def _(m):
    r = reading(m, release(1), boundary(2),
                prompt(3, "<task-notification>\n<task-id>b1</task-id>"))
    return r["prompted"] is None, r


@case("a compaction whose boundary carries no size leaves no context, not the stale one")
def _(m):
    r = reading(m, usage(1, 396_000), boundary(2, post=None))
    return r["context"] is None, r


@case("the release's /compact, queued while busy, is not a prompt")
def _(m):
    r = reading(m, release(1), queued(2, "/compact"), boundary(3))
    return r["prompted"] is None, r


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


@case("a prompt after the release but before the compaction is not retired")
def _(m):
    between = "2026-09-10T10:01:30.000Z"   # after the release, before the compaction
    v = m.verdict("worker", False, IDLE, NONE, dict(DONE, prompted=between))
    return v[0] == "keep", v


@case("keep: a transcript with no context size")
def _(m):
    try:
        v = m.verdict("worker", False, IDLE, NONE, big(None))
    except Exception as e:  # noqa: BLE001 -- raising is not answering keep
        return False, f"raised {e.__class__.__name__}"
    return v[0] == "keep" and "no context size" in v[1], v


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
import json, os, sys
a = sys.argv[1:]
T = "repos/kalaluthien/campaign-base"
with open(os.path.join(%(dir)r, "gh.log"), "a") as fh:
    fh.write(" ".join(a) + "\n")
if a[:2] == ["api", T + "/issues/7"]:
    print('["campaign", "campaign:tk"]'); sys.exit(0)
broken = lambda f: os.path.exists(os.path.join(%(dir)r, f))
if a[:3] == ["issue", "view", "7"] and not broken("repos-broken"):
    print("## Repos\n\n- none\n"); sys.exit(0)
if broken("gh-broken"):
    if a[:2] == ["pr", "list"]:
        print("not json"); sys.exit(0)
    sys.exit(1)
if a[:2] == ["api", T + "/git/matching-refs/heads/tk/"]:
    print(json.dumps(["refs/heads/tk/5-a", "refs/heads/tk/6-b"])); sys.exit(0)
if a[:3] == ["api", "--paginate", T + "/issues/7/sub_issues"]:
    print(json.dumps([
        {"number": 5, "state": "open", "labels": []},
        {"number": 6, "state": "open", "labels": [{"name": "backlog"}]},
        {"number": 8, "state": "closed", "labels": [{"name": "bug"}]}])); sys.exit(0)
if a[:2] == ["pr", "list"]:
    pr = lambda n, head, k: {"number": n, "headRefName": head, "state": "OPEN",
                             "headRefOid": "abc1234def", "comments": [{}] * k,
                             "reviews": [{}]}
    print(json.dumps([pr(11, "tk/5-a", 2), pr(3, "tk/5-a", 0),
                      pr(12, "other/5-a", 9)])); sys.exit(0)
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


# the watch

def sess(status="idle", pane="w1:p2", context=None, banner=None):
    return {"pane": pane, "status": status, "context": context, "banner": banner}


def readings(sessions=None, claims=None, issues=None, prs=None, installs=None,
             fail=()):
    r = {"sessions": (sessions or {}, None), "claims": (claims or {}, None),
         "issues": (issues or {}, None), "prs": (prs or {}, None)}
    r.update({f"install {repo}": (word, None) for repo, word in installs or []})
    for source in fail:
        r[source] = (None, "unreachable")
    return r


def polls(m, *steps, own="w1:p1"):
    """The lines each poll printed, one Watch over (minute, readings)."""
    w = m.Watch("tk", own)
    return [w.poll(r, minute * 60) for minute, r in steps]


def drifts(out, rule):
    return [ln for ln in out if ln.split()[1:2] == ["drift"]
            and ln.split()[2] == rule]


LIMIT = "session limit, resets 4pm (in 2h)"


@case("watch: the first poll names the watch and prints every drift and limit, nothing else")
def _(m):
    [out] = polls(m, (0, readings(
        sessions={"tk-worker-2": sess(banner=LIMIT)},
        claims={"tk/5-a": 5}, issues={5: ("open", False), 6: ("open", False)})))
    return (out[0].startswith("watching tk:")
            and "+ drift unclaimed tk#6" in out
            and f"+ limit w1:p2 {LIMIT}" in out
            and not [ln for ln in out if ln.startswith(("+ session", "+ claim", "+ issue"))]), out


@case("watch: a later poll prints only what changed, as + and -")
def _(m):
    a = readings(claims={"tk/5-a": 5})
    b = readings(claims={"tk/5-a": 5, "tk/6-b": 6})
    c = readings(claims={"tk/6-b": 6})
    _, same, grew, shrank = polls(m, (0, a), (1, a), (2, b), (3, c))
    return (same == [] and "+ claim tk/6-b" in grew and "- claim tk/5-a" in shrank
            and "+ claim tk/5-a" not in grew), (same, grew, shrank)


@case("watch: a pull request is a line only while its branch is claimed")
def _(m):
    w = m.Watch("tk")
    w.poll(readings(claims={"tk/5-a": 5}, prs={
        "tk/5-a": (9, "open", "abc1234", 2), "tk/4-z": (8, "merged", "def5678", 7)}), 0)
    return (sorted(ln for ln in w.shown if ln.startswith("pr "))
            == ["pr 9 tk/5-a open abc1234 comments=2"]), w.shown


@case("watch: unclaimed is an open sub-issue without backlog and no claim")
def _(m):
    [out] = polls(m, (0, readings(
        claims={"tk/5-a": 5},
        issues={5: ("open", False), 6: ("open", False), 7: ("open", True),
                8: ("closed", False)})))
    return drifts(out, "unclaimed") == ["+ drift unclaimed tk#6"], out


@case("watch: unworked is more claims than workers, and a planner is no worker")
def _(m):
    two = {"tk/5-a": 5, "tk/6-b": 6}
    staff = {"tk-planner-1": sess(pane="w1:p9"), "tk-worker-2": sess()}
    [out] = polls(m, (0, readings(sessions=staff, claims=two)))
    [even] = polls(m, (0, readings(sessions=staff, claims={"tk/5-a": 5})))
    return (drifts(out, "unworked") == ["+ drift unworked 2 claim(s), 1 worker(s)"]
            and drifts(even, "unworked") == []), (out, even)


@case("watch: stuck is a claim unchanged for 30m while no worker works")
def _(m):
    idle = {"tk-worker-2": sess()}
    r = readings(sessions=idle, claims={"tk/5-a": 5})
    outs = polls(m, (0, r), (29, r), (30, r))
    return (drifts(outs[1], "stuck") == []
            and drifts(outs[2], "stuck") == ["+ drift stuck tk/5-a"]), outs


@case("watch: a working worker or a moving pull request is not stuck")
def _(m):
    busy = readings(sessions={"tk-worker-2": sess("working")}, claims={"tk/5-a": 5})
    worked = polls(m, (0, busy), (30, busy))
    idle = {"tk-worker-2": sess()}
    pr = lambda k: readings(sessions=idle, claims={"tk/5-a": 5},
                            prs={"tk/5-a": (9, "open", "abc1234", k)})
    moved = polls(m, (0, pr(1)), (20, pr(2)), (30, pr(2)))
    return (not drifts(worked[1], "stuck") and not drifts(moved[2], "stuck")), (worked, moved)


@case("watch: settled is a claim whose sub-issue is closed")
def _(m):
    [out] = polls(m, (0, readings(claims={"tk/5-a": 5, "tk/6-b": 6},
                                  issues={5: ("closed", False), 6: ("open", False)})))
    return drifts(out, "settled") == ["+ drift settled tk/5-a"], out


@case("watch: idle-worker is more workers than claims, and one idle for 10m")
def _(m):
    staff = {"tk-worker-2": sess(), "tk-worker-3": sess("working", pane="w1:p3")}
    r = readings(sessions=staff, claims={"tk/5-a": 5})
    outs = polls(m, (0, r), (9, r), (10, r))
    even = polls(m, (0, readings(sessions=staff, claims={"tk/5-a": 5, "tk/6-b": 6})),
                 (10, readings(sessions=staff, claims={"tk/5-a": 5, "tk/6-b": 6})))
    return (drifts(outs[1], "idle-worker") == []
            and drifts(outs[2], "idle-worker") == ["+ drift idle-worker tk-worker-2"]
            and not drifts(even[1], "idle-worker")), (outs, even)


@case("watch: context is a non-working session at or over the ceiling")
def _(m):
    [out] = polls(m, (0, readings(sessions={
        "tk-worker-2": sess(context=m.COMPACT_AT),
        "tk-worker-3": sess("working", pane="w1:p3", context=900_000),
        "tk-worker-4": sess(pane="w1:p4", context=None),
        "tk-worker-5": sess(pane="w1:p5", context=m.COMPACT_AT - 1)})))
    return drifts(out, "context") == [
        f"+ drift context tk-worker-2 {m.COMPACT_AT // 1000}k"], out


@case("watch: install is an install that is not current")
def _(m):
    [out] = polls(m, (0, readings(installs=[("o/base", "behind 2"),
                                            ("o/member", "current")])))
    return drifts(out, "install") == ["+ drift install o/base behind 2"], out


@case("watch: a session status counts after two equal polls")
def _(m):
    s = lambda st: readings(sessions={"tk-worker-2": sess(st)},
                            claims={"tk/5-a": 5})
    outs = polls(m, (0, s("working")), (1, s("idle")), (2, s("idle")))
    return (outs[1] == []
            and "+ session tk-worker-2 idle" in outs[2]), outs


@case("watch: the own pane has no session line, and its context is still read")
def _(m):
    s = lambda st: readings(sessions={"tk-planner-1": sess(st, pane="w1:p1",
                                                           context=300_000)})
    outs = polls(m, (0, s("idle")), (1, s("working")), (2, s("working")))
    return (not [ln for ln in outs[2] if "session" in ln]
            and drifts(outs[0], "context") == ["+ drift context tk-planner-1 300k"]), outs


@case("watch: no limit on a pane is no line")
def _(m):
    [out] = polls(m, (0, readings(sessions={"tk-worker-2": sess(banner="no limit on w1:p2")})))
    return not [ln for ln in out if "limit" in ln], out


@case("watch: a drift still standing reprints as = every 30m")
def _(m):
    r = readings(issues={6: ("open", False)})
    outs = polls(m, (0, r), (29, r), (30, r), (45, r), (60, r))
    eq = "= drift unclaimed tk#6"
    return ([o.count(eq) for o in outs[1:]] == [0, 1, 0, 1]), outs


@case("watch: a source failing 3 polls running prints error once, and its last reading stands")
def _(m):
    ok = readings(claims={"tk/5-a": 5})
    bad = readings(fail=("claims",))
    outs = polls(m, (0, ok), (1, bad), (2, bad), (3, bad), (4, bad))
    back = polls(m, (0, ok), (1, bad), (2, bad), (3, ok), (4, bad))
    errors = [[ln for ln in o if ln.startswith("error claims")] for o in outs]
    return ([len(e) for e in errors] == [0, 0, 0, 1, 0]
            and not [ln for o in outs for ln in o if ln == "- claim tk/5-a"]
            and not [ln for o in back for ln in o if ln.startswith("error")]), (outs, back)


@case("watch: a poll past the ceiling prints error watchdog and exits 1")
def _(m):
    m.POLL_CEILING = 1
    w = m.Watch("tk")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        hung = m.run_watch(w, lambda: m.read_all(
            {"sessions": lambda: time.sleep(3) or ({}, None)}), 60, polls=1)
        fine = m.run_watch(m.Watch("tk"), readings, 60, polls=2,
                           clock=lambda: 0, sleep=lambda s: None)
    return (hung == 1 and fine == 0
            and "error watchdog" in out.getvalue()), out.getvalue()


STUB_DIRECTORY = """import sys
print(%r)
"""
STUB_INSTALLED = """import importlib.util
_s = importlib.util.spec_from_file_location("ci_real", %r)
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)
readable = _m.readable
def rows(readme):
    return [("o/base", "/x", "sh a"), ("o/m", "/y", None)], None
def read_install(repo, path):
    return {"o/base": ("behind 1", "HEAD a"),
            "o/m": ("absent", "/y is not a directory")}[repo]
"""


def watch_read(m, broken=None, reads=1, log=None):
    """The last of `reads` readings of `watch_reader` over the fake, or the
    exception it raised. `broken` names the marker that makes the fake gh
    fail; `log`, a list, receives the fake gh's calls. The campaign's
    directory and installs are stubs, since the real ones read this disk."""
    with tempfile.TemporaryDirectory() as d:
        d = fleet(d)
        if broken:
            (d / broken).write_text("")
        (d / "dir.py").write_text(STUB_DIRECTORY % str(d))
        (d / "inst.py").write_text(STUB_INSTALLED % str(
            m.BASE / "scripts" / "campaign-installed.py"))
        m.DIRECTORY_SCRIPT, m.INSTALLED_SCRIPT = d / "dir.py", d / "inst.py"
        env = {"PATH": str(d / "bin"), "HOME": str(d / "home"), "TMPDIR": str(d)}
        saved, cwd = dict(os.environ), os.getcwd()
        os.environ.update(env)
        os.chdir(d)
        try:
            claim = m.load(m.RELEASE_SCRIPT, "campaign_claim")
            names = m.load(m.HERE / "campaign-name-session.py", "cns")
            read = m.watch_reader("7", "tk", "w1:p1", claim, names, {})
            for _ in range(reads):
                got = read()
            if log is not None and (d / "gh.log").exists():
                log += (d / "gh.log").read_text().splitlines()
            return got
        except Exception as e:  # noqa: BLE001 -- a reader that raised is the defect
            return e
        finally:
            os.chdir(cwd)
            os.environ.clear()
            os.environ.update(saved)


@case("watch reader: sessions come from herdr with context and banner")
def _(m):
    got = watch_read(m)
    if isinstance(got, Exception):
        return False, f"the reader raised {got!r}"
    ss, why = got["sessions"]
    return (why is None and set(ss) == {
                "tk-planner-1", "tk-worker-2", "tk-worker-3", "tk-worker-4",
                "tk-worker-5", "tk-worker-6", "tk-planner-9", "tk-worker-11",
                "tk-worker-10"}
            and ss["tk-worker-3"]["context"] == 210_000
            and ss["tk-worker-6"]["context"] is None
            and ss["tk-worker-4"]["banner"].startswith("session")
            and ss["tk-planner-1"]["banner"] is None), got


@case("watch reader: claims, sub-issues and pull requests of this slug")
def _(m):
    got = watch_read(m)
    if isinstance(got, Exception):
        return False, f"the reader raised {got!r}"
    return (got["claims"] == ({"tk/5-a": 5, "tk/6-b": 6}, None)
            and got["issues"] == ({5: ("open", False), 6: ("open", True),
                                   8: ("closed", False)}, None)
            and got["prs"] == ({"tk/5-a": (11, "open", "abc1234", 3)}, None)), got


@case("watch reader: an unreadable or garbled source is a why, not a raise")
def _(m):
    got = watch_read(m, broken="gh-broken")
    if isinstance(got, Exception):
        return False, f"the reader raised {got!r}"
    whys = {k: got[k][1] for k in ("claims", "issues", "prs")}
    return (all(isinstance(w, str) and w for w in whys.values())
            and "JSONDecodeError" in whys["prs"]), got


@case("watch reader: an unread ## Repos fails the claims and pull requests")
def _(m):
    got = watch_read(m, broken="repos-broken")
    if isinstance(got, Exception):
        return False, f"the reader raised {got!r}"
    return (got["claims"][0] is None and "campaign #7" in got["claims"][1]
            and got["prs"][0] is None and got["issues"][1] is None), got


@case("watch reader: each install is a source, and one unreadable fails alone")
def _(m):
    got = watch_read(m)
    if isinstance(got, Exception):
        return False, f"the reader raised {got!r}"
    return (got.get("install o/base") == ("behind 1", None)
            and got.get("install o/m", (1, ""))[0] is None
            and "absent" in got["install o/m"][1]
            and "installs" not in got), got


@case("watch reader: ## Repos is read on every poll")
def _(m):
    log = []
    got = watch_read(m, reads=2, log=log)
    views = [ln for ln in log if ln.startswith("issue view 7")]
    return (not isinstance(got, Exception) and len(views) == 2), (views, got)


@case("watch: an unreadable install hides no other install's drift")
def _(m):
    r = dict(readings(installs=[("o/base", "behind 1")]))
    r["install o/m"] = (None, "absent: /y")
    outs = polls(m, (0, r), (1, r), (2, r))
    return ("+ drift install o/base behind 1" in outs[0]
            and [ln for ln in outs[2] if ln.startswith("error install o/m")]), outs


@case("watch: no drift is read from a source never read")
def _(m):
    [out] = polls(m, (0, readings(issues={5: ("open", False)},
                                  sessions={"tk-worker-2": sess()}, fail=("claims",))))
    return not [ln for ln in out if " drift " in ln], out


@case("watch: each rule waits only for its own sources")
def _(m):
    [no_sessions] = polls(m, (0, readings(
        claims={"tk/5-a": 5}, issues={5: ("closed", False), 6: ("open", False)},
        fail=("sessions",))))
    idle = {"tk-worker-2": sess()}
    no_prs = polls(m, (0, readings(sessions=idle, claims={"tk/5-a": 5}, fail=("prs",))),
                   (30, readings(sessions=idle, claims={"tk/5-a": 5}, fail=("prs",))))
    return ("+ drift unclaimed tk#6" in no_sessions
            and "+ drift settled tk/5-a" in no_sessions
            and not drifts(no_sessions, "unworked")
            and not drifts(no_prs[1], "stuck")), (no_sessions, no_prs)


@case("watch: a drift clears when its repair lands: a claim, a release")
def _(m):
    open5 = {5: ("open", False)}
    closed5 = {5: ("closed", False)}
    one = {"tk-worker-2": sess()}
    outs = polls(m, (0, readings(sessions=one, issues=open5)),
                 (1, readings(sessions=one, issues=open5, claims={"tk/5-a": 5})),
                 (2, readings(sessions=one, issues=closed5, claims={"tk/5-a": 5})),
                 (3, readings(sessions=one, issues=closed5)))
    return ("+ drift unclaimed tk#5" in outs[0]
            and "- drift unclaimed tk#5" in outs[1]
            and "+ drift settled tk/5-a" in outs[2]
            and "- drift settled tk/5-a" in outs[3]), outs

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
    ("a prompt is text", 'if is_prompt(content):\n                later("prompted", ts)',
     'if False:\n                later("prompted", ts)',
     "a prompt is a user record carrying text"),
    ("a prompt typed into a busy pane", 'elif kind == "attachment":', "elif False:",
     "a prompt typed into a busy pane, between release and compaction, keeps the worker"),
    ("a queued peer message", 'and not a.get("isMeta") and is_prompt', "and is_prompt",
     "a peer's message queued into the pane is not a prompt"),
    ("only a queued prompt", 'and a.get("commandMode") == "prompt"', "",
     "a queued command in any mode but prompt is not a prompt"),
    ("a queued echo", ' and is_prompt(a.get("prompt"))', "",
     "the release's /compact, queued while busy, is not a prompt"),
    ("a prompt before the compaction blocks", 'reading["prompted"] > rel)',
     'reading["prompted"] > comp)',
     "a prompt after the release but before the compaction is not retired"),
    ("keep with no context size", 'if reading["context"] is None:', "if False:",
     "keep: a transcript with no context size"),
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
    ("the bare /compact is an echo", "bool(said) and said != QUEUED_COMPACT and not",
     "bool(said) and not", "the bare /compact that release queues is not a prompt"),
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
    ("a task notice is no prompt", "COMPACTION_ECHOES + (TASK_NOTICE,))", "COMPACTION_ECHOES)",
     "a task notification reaching an idle pane is not a prompt"),
    ("a sizeless boundary clears the context", 'out["context"], out["context_at"] = tokens, ts',
     'out["context"], out["context_at"] = (out["context"] if tokens is None else tokens), ts',
     "a compaction whose boundary carries no size leaves no context, not the stale one"),
    ("the first poll prints drifts and limits only", 'if ln.startswith(("drift ", "limit ")))',
     "if True)", "watch: the first poll names the watch and prints every drift and limit, nothing else"),
    ("a later poll prints the change", "added, removed = sorted(lines - self.shown), sorted(self.shown - lines)",
     "added, removed = sorted(lines), []", "watch: a later poll prints only what changed, as + and -"),
    ("a pull request of a claim only", "for b, p in prs.items() if b in claims}", "for b, p in prs.items()}",
     "watch: a pull request is a line only while its branch is claimed"),
    ("unclaimed", 'if state == "open" and not backlog and n not in claimed:', "if False:",
     "watch: unclaimed is an open sub-issue without backlog and no claim"),
    ("unclaimed skips backlog", "and not backlog and n not in claimed", "and n not in claimed",
     "watch: unclaimed is an open sub-issue without backlog and no claim"),
    ("unclaimed skips a claimed one", "and not backlog and n not in claimed", "and not backlog",
     "watch: unclaimed is an open sub-issue without backlog and no claim"),
    ("unworked", "if len(claims) > len(workers):", "if False:",
     "watch: unworked is more claims than workers, and a planner is no worker"),
    ("unworked is strictly more", "if len(claims) > len(workers):", "if len(claims) >= len(workers):",
     "watch: unworked is more claims than workers, and a planner is no worker"),
    ("a worker by its role word", 'if name.split("-")[-2] == "worker":', "if True:",
     "watch: unworked is more claims than workers, and a planner is no worker"),
    ("stuck", "if now - self.moved[b][1] >= STUCK_AFTER:", "if False:",
     "watch: stuck is a claim unchanged for 30m while no worker works"),
    ("a working worker resets stuck", "if working or b not in self.moved", "if b not in self.moved",
     "watch: a working worker or a moving pull request is not stuck"),
    ("a moving pull request resets stuck", "or self.moved[b][0] != prs.get(b):", ":",
     "watch: a working worker or a moving pull request is not stuck"),
    ("settled", 'if issues.get(n, ("open",))[0] == "closed":', "if False:",
     "watch: settled is a claim whose sub-issue is closed"),
    ("idle-worker needs more workers", "if len(workers) > len(claims):", "if True:",
     "watch: idle-worker is more workers than claims, and one idle for 10m"),
    ("idle-worker waits 10m", "now - self.idle_since[w] >= IDLE_AFTER", "True",
     "watch: idle-worker is more workers than claims, and one idle for 10m"),
    ("context skips a working session", 'if (st != "working" and s.get("context") is not None',
     'if (s.get("context") is not None', "watch: context is a non-working session at or over the ceiling"),
    ("context is inclusive", 'and s["context"] >= COMPACT_AT):', 'and s["context"] > COMPACT_AT):',
     "watch: context is a non-working session at or over the ceiling"),
    ("install", 'and word != "current"}', "and False}",
     "watch: install is an install that is not current"),
    ("two equal polls", 'if self.raw.get(name, s["status"]) == s["status"]:', "if True:",
     "watch: a session status counts after two equal polls"),
    ("the own pane has no session line", 'if s["pane"] != self.own:', "if True:",
     "watch: the own pane has no session line, and its context is still read"),
    ("no limit is no line", 'banner_word(s["banner"]) != "none"', "True",
     "watch: no limit on a pane is no line"),
    ("reprint after 30m", "and now - self.printed.get(ln, now) >= REPRINT_AFTER)", ")",
     "watch: a drift still standing reprints as = every 30m"),
    ("a reprint restarts the 30m", "self.printed = {ln: (now if ln in added or ln in reprint else t)",
     "self.printed = {ln: t", "watch: a drift still standing reprints as = every 30m"),
    ("error after 3 polls", "if self.fails[source] == UNREAD_POLLS:", "if False:",
     "watch: a source failing 3 polls running prints error once, and its last reading stands"),
    ("a reading resets the count", "            self.fails[source] = 0\n", "",
     "watch: a source failing 3 polls running prints error once, and its last reading stands"),
    ("the last reading stands", "self.fails[source] = self.fails.get(source, 0) + 1",
     "self.fails[source] = self.fails.get(source, 0) + 1; self.last.pop(source, None)",
     "watch: a source failing 3 polls running prints error once, and its last reading stands"),
    ("the watchdog is armed", "signal.alarm(POLL_CEILING)", "signal.alarm(0)",
     "watch: a poll past the ceiling prints error watchdog and exits 1"),
    ("an overrun exits 1", 'exiting",\n              flush=True)\n        return 1', 'exiting",\n              flush=True)\n        return 0',
     "watch: a poll past the ceiling prints error watchdog and exits 1"),
    ("the reader reads this campaign's sessions", 'if names.campaign_of(row["name"]) != slug:\n                continue',
     "if False:\n                continue",
     "watch reader: sessions come from herdr with context and banner"),
    ("the reader reads a working session's size", '            if st != "working":\n                s["context"]',
     '            if True:\n                s["context"]',
     "watch reader: sessions come from herdr with context and banner"),
    ("a reader's crash is a why", 'out[source] = (None, f"{e.__class__.__name__}: {e}")', "raise",
     "watch reader: an unreadable or garbled source is a why, not a raise"),
    ("the overrun is no Exception", "class PollOverrun(BaseException):", "class PollOverrun(Exception):",
     "watch: a poll past the ceiling prints error watchdog and exits 1"),
    ("a pull request of this slug", 'if p["headRefName"].startswith(f"{slug}/"):', "if True:",
     "watch reader: claims, sub-issues and pull requests of this slug"),
    ("the latest pull request of a branch", "key=lambda p: p[\"number\"]):", "key=lambda p: -p[\"number\"]):",
     "watch reader: claims, sub-issues and pull requests of this slug"),
    ("backlog by its label", "lb.get(\"name\") == tracker.BACKLOG_LABEL", "False",
     "watch reader: claims, sub-issues and pull requests of this slug"),
    ("claims from the refs", "            out[b] = int(n) if n else None\n", "",
     "watch reader: claims, sub-issues and pull requests of this slug"),
    ("an unread ## Repos fails claims", "        if listed is None:\n            repos.clear()\n            return None, why\n", "",
     "watch reader: an unread ## Repos fails the claims and pull requests"),
    ("no pull requests without the repositories", "        if not repos:\n            return None,", "        if False:\n            return None,",
     "watch reader: an unread ## Repos fails the claims and pull requests"),
    ("an unread install is no reading", "((word, None) if readable(word)", "((word, None) if True",
     "watch reader: each install is a source, and one unreadable fails alone"),
    ("each install its own source", 'out.update(each if why is None else {"installs": (None, why)})',
     'out["installs"] = (each, why)', "watch reader: each install is a source, and one unreadable fails alone"),
    ("## Repos every poll", "        listed, why = claim.campaign_repos(issue)\n",
     "        listed, why = (repos[1:], None) if repos else claim.campaign_repos(issue)\n",
     "watch reader: ## Repos is read on every poll"),
    ("an install drift per source", 'if source.startswith("install ") and word != "current"}',
     'if False}', "watch: an unreadable install hides no other install's drift"),
    ("unclaimed waits for claims and issues", 'if {"claims", "issues"} <= read:', "if True:",
     "watch: no drift is read from a source never read"),
    ("the counting rules wait for sessions", '        if not {"sessions", "claims"} <= read:\n            return out\n', "",
     "watch: each rule waits only for its own sources"),
    ("stuck waits for the pull requests", 'for b in claims if "prs" in read else ():', "for b in claims:",
     "watch: each rule waits only for its own sources"),
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
