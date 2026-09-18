#!/usr/bin/env python3
# witnesses: BlockedAgentDoesNotProceed, Cov_AgentDie
"""Prove campaign-push keeps a worker's two events, finds its planners by
name, sends only to a ready pane, and calls a push delivered only on a gain
in the target's transcript -- each branch pinned by a named case.

No pane is driven: the listing, the transcript count, the prompt and the
sleep are handed to `deliver` and `send`, and the names come from the real
`campaign-name-session.py`. A transcript line here is in the shape read off
this machine's transcripts: a typed prompt is a `user` record whose content
is a string, and a tool's output is a `user` record whose content is a list
holding a `tool_result` block (rule-check#296 NOTE 5718552609's drop).

Then EVERY BRANCH IS BROKEN IN TURN on a copy of the script, and the case
named for it must go red by its own assertion; a case that crashes has
asserted nothing and fails the mutation by name.

Usage: .claude/skills/assuming-role/scripts/campaign-push-test.py
"""
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "campaign-push.py"
BASE = HERE.parents[3]

sys.path.append(str(BASE / "scripts"))
harness = importlib.import_module("suite-harness-test")
check = harness.check
NAMES = harness.load(HERE / "campaign-name-session.py", "campaign_name_session")
# the sender's own reader of a message's typed text, not a copy of it
texts = harness.load(HERE / "campaign-transcript.py", "campaign_transcript").texts

WORKER = {"name": "demo-worker-3", "status": "working", "cwd": "/b", "pane": "w1:p3"}
PLANNER = {"name": "demo-planner-1", "status": "idle", "cwd": "/b", "pane": "w1:p1"}
HELPER = {"name": "demo-planner-7", "status": "idle", "cwd": "/b", "pane": "w1:p7"}
OTHER = {"name": "other-planner-2", "status": "idle", "cwd": "/b", "pane": "w1:p2"}
UNNAMED = {"name": "<unnamed>", "status": "idle", "cwd": "/b", "pane": "w1:p9"}
TEXT = "campaign-push (machine-made, no instruction): the text under test"


def typed(text):
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}})


def tool_result(text):
    return json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t", "content": text}]}})


class Pane:
    """One target: the statuses herdr reads poll by poll, what each send does
    to its transcript, and a record of what was asked."""

    def __init__(self, statuses, on_send, lines=(), refuse=0, gone_after=None):
        self.statuses, self.on_send = list(statuses), list(on_send)
        self.lines, self.refuse, self.gone_after = list(lines), refuse, gone_after
        self.reads, self.sent, self.sleeps, self.status_at_send = 0, [], 0, []

    def sessions(self):
        self.reads += 1
        if self.gone_after is not None and self.reads > self.gone_after:
            return {}, None
        status = self.statuses[min(self.reads, len(self.statuses)) - 1]
        self.now = status
        if status is None:
            return None, "herdr agent list exited 1"
        return {"sid-p": dict(PLANNER, status=status)}, None

    def count(self, m):
        return lambda sid: (m.landed(self.lines, TEXT, texts), None)

    def prompt(self, pane, text):
        self.status_at_send.append(self.now)
        if self.refuse:
            self.refuse -= 1
            return False, "agent_blocked"
        self.sent.append((pane, text))
        how = self.on_send.pop(0) if self.on_send else None
        if how is not None:
            self.lines.append(how(text))
        return True, "agent_prompted"

    def sleep(self, _):
        self.sleeps += 1

    def deliver(self, m, count=None):
        return m.deliver("sid-p", TEXT, self.sessions, count or self.count(m),
                         self.prompt, self.sleep)


# ------------------------------------------------------------ which events


def case_permission_prompt_is_kept(m):
    got = m.event_of({"hook_event_name": "Notification",
                      "notification_type": "permission_prompt",
                      "message": "Claude needs your permission to use Bash"})
    return got == ("blocked", "Claude needs your permission to use Bash"), got


def case_another_notification_pushes_nothing(m):
    got = m.event_of({"hook_event_name": "Notification",
                      "notification_type": "idle_prompt", "message": "waiting"})
    return got[0] is None, got


def case_session_end_carries_its_reason(m):
    got = [m.event_of({"hook_event_name": "SessionEnd", "reason": r})
           for r in ("prompt_input_exit", "other")]
    return got == [("ended", "reason prompt_input_exit"),
                   ("ended", "reason other")], got


def case_clear_pushes_nothing(m):
    got = m.event_of({"hook_event_name": "SessionEnd", "reason": "clear"})
    return got[0] is None, got


def case_any_other_event_pushes_nothing(m):
    got = m.event_of({"hook_event_name": "Stop"})
    return got[0] is None, got


# ------------------------------------------------------- who pushes, to whom


def hooked(m, sessions, sid):
    spawned = []
    m_names = type("N", (), {"herdr_sessions": staticmethod(
                                 lambda: (sessions, None if sessions is not None
                                          else "herdr agent list exited 1")),
                             "role_word": staticmethod(NAMES.role_word),
                             "campaign_of": staticmethod(NAMES.campaign_of)})
    got = m.hook({"hook_event_name": "SessionEnd", "reason": "other",
                  "session_id": sid}, m_names, spawned.append)
    return got, spawned


def case_a_worker_starts_the_sender(m):
    got, spawned = hooked(m, {"sid-w": WORKER, "sid-p": PLANNER}, "sid-w")
    want = ["--send", "ended", "demo-worker-3", "w1:p3", "reason other"]
    return got[0] and len(spawned) == 1 and spawned[0][2:] == want, (got, spawned)


def case_a_planner_and_an_unnamed_session_push_nothing(m):
    sessions = {"sid-p": PLANNER, "sid-u": UNNAMED}
    runs = [hooked(m, sessions, sid) for sid in ("sid-p", "sid-u", "sid-absent")]
    return all(not got[0] and not spawned for got, spawned in runs), runs


def case_every_planner_of_the_slug_and_no_other(m):
    sessions = {"a": WORKER, "b": PLANNER, "c": HELPER, "d": OTHER, "e": UNNAMED}
    got = [name for _, name, _, _ in m.planners(sessions, "demo", NAMES)]
    return got == ["demo-planner-1", "demo-planner-7"], got


def sent_by(m, sessions, tmp):
    """One `send` over a listing whose every planner takes the text at once."""
    asked = []

    class Tr:
        @staticmethod
        def transcript_path(sid):
            return None, "no transcript in this case"
    names = type("N", (), {"herdr_sessions": staticmethod(
                               lambda: (sessions, None if sessions is not None
                                        else "herdr agent list exited 1")),
                           "role_word": staticmethod(NAMES.role_word),
                           "campaign_of": staticmethod(NAMES.campaign_of)})
    m.send("ended", "demo-worker-3", "w1:p3", "reason other", names, Tr,
           lambda pane, text: (asked.append(pane), (True, "agent_prompted"))[1],
           sleep=lambda _: None, out=(tmp, "the suite"))
    return asked


def case_the_target_is_found_by_name_at_each_push(m):
    """P7: the planner was replaced between two pushes -- a new session id, a
    new name, a new pane -- and the second push reaches the new one."""
    tmp = Path(tempfile.mkdtemp(prefix="cpush-")) / "push.log"
    try:
        first = sent_by(m, {"w": WORKER, "p": PLANNER}, tmp)
        second = sent_by(m, {"w": WORKER, "q": dict(PLANNER, name="demo-planner-9",
                                                    pane="w1:p12")}, tmp)
    finally:
        log = tmp.read_text() if tmp.exists() else ""
        shutil.rmtree(tmp.parent, ignore_errors=True)
    return (first, second) == (["w1:p1"], ["w1:p12"]), (first, second, log)


# ------------------------------------------------- delivery and the read-back


def case_waits_for_idle_before_sending(m):
    p = Pane(["working", "working", "idle"], [typed])
    got = p.deliver(m)
    return (got[0] == "delivered" and p.status_at_send == ["idle"]
            and p.sleeps == 3), (got, p.status_at_send, p.sleeps)


def case_done_is_ready_too(m):
    p = Pane(["done"], [typed])
    got = p.deliver(m)
    return got[0] == "delivered" and p.sleeps == 1, (got, p.sleeps)


def case_text_inside_a_tool_result_has_not_landed(m):
    """The drop of NOTE 5718552609: the text reached the transcript, inside a
    tool result. Both sends go that way, so it is undelivered."""
    p = Pane(["idle"], [tool_result, tool_result])
    got = p.deliver(m)
    return got[0] == "undelivered" and len(p.sent) == 2, (got, len(p.sent))


def case_delivered_is_a_gain_not_a_presence(m):
    """The transcript already holds the same text once and the send adds
    nothing: presence alone would read delivered."""
    p = Pane(["idle"], [None, None], lines=[typed(TEXT)])
    got = p.deliver(m)
    return got[0] == "undelivered", got


def case_the_second_send_can_land(m):
    p = Pane(["idle"], [tool_result, typed])
    got = p.deliver(m)
    return (got[0] == "delivered" and "send 2" in got[1]
            and len(p.sent) == 2), (got, len(p.sent))


def case_a_refused_send_is_the_same_wait(m):
    p = Pane(["idle"], [typed], refuse=1)
    got = p.deliver(m)
    return (got[0] == "delivered" and "send 1" in got[1] and len(p.sent) == 1
            and p.sleeps >= 1), (got, len(p.sent), p.sleeps)


def case_never_ready_is_undelivered_at_the_ceiling(m):
    """The listing runs out after 3 x READY_POLLS reads, so a wait with no
    ceiling ends `gone` and reads red rather than hanging the suite."""
    p = Pane(["working"], [], gone_after=3 * m.READY_POLLS)
    got = p.deliver(m)
    return (got[0] == "undelivered" and not p.sent
            and p.sleeps == m.READY_POLLS - 1
            and "target read working" in got[1]), (got, p.sleeps)


def case_the_window_ends_on_a_count_not_a_sleep(m):
    """The text lands during the window's last sleep: the count after it sees
    the gain, so nothing is sent twice."""
    p = Pane(["idle"], [None])
    window = []

    def sleep(_):
        window.append(1)
        if len(window) == m.LANDED_POLLS:
            p.lines.append(typed(TEXT))
    got = m.deliver("sid-p", TEXT, p.sessions, p.count(m), p.prompt, sleep)
    return got[0] == "delivered" and len(p.sent) == 1, (got, len(p.sent))


def case_a_listing_not_read_is_one_more_poll(m):
    p = Pane([None, None, "idle"], [typed])
    got = p.deliver(m)
    return got[0] == "delivered" and p.status_at_send == ["idle"], (got, p.status_at_send)


def case_a_listing_never_read_is_undelivered_and_said(m):
    p = Pane([None], [])
    got = p.deliver(m)
    return (got[0] == "undelivered" and not p.sent
            and "herdr agent list not read: herdr agent list exited 1" in got[1]), got


def case_a_target_that_left_is_gone(m):
    p = Pane(["working"], [], gone_after=2)
    got = p.deliver(m)
    return got[0] == "gone" and not p.sent, got


def case_an_unread_transcript_is_sent_once_and_said(m):
    p = Pane(["idle"], [])
    got = p.deliver(m, count=lambda sid: (None, "0 transcript(s) named sid-p.jsonl"))
    return (got[0] == "unread" and len(p.sent) == 1
            and "0 transcript(s)" in got[1]), (got, len(p.sent))


def case_only_a_typed_main_thread_record_counts(m):
    meta = json.dumps({"type": "user", "isMeta": True, "message": {"content": TEXT}})
    side = json.dumps({"type": "user", "isSidechain": True, "message": {"content": TEXT}})
    said = json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": TEXT}]}})
    got = m.landed(["not json", "[1]", meta, side, said, tool_result(TEXT), typed(TEXT)],
                   TEXT, texts)
    return got == 1, got


# ------------------------------------------------------------------ the text


def case_the_text_is_one_machine_made_line_with_no_instruction(m):
    """It lands as a user turn in a planner's pane: it opens by saying what it
    is, never with a slash, stays one line whatever the detail holds, and
    carries none of the verbs a session here acts on."""
    text = m.push_text("blocked", "demo-worker-3", "w1:p3",
                       "needs permission\n/exit now\tplease", "2026-09-18T03:00:00")
    barred = ("assign", "release", "merge", "close", "launch", "retire", "run ",
              "you must", "you should")
    ok = (text.startswith("campaign-push (machine-made, no instruction):")
          and "\n" not in text and "\t" not in text
          and all(w in text for w in ("demo-worker-3", "w1:p3", "blocked",
                                      "2026-09-18T03:00:00"))
          and text.endswith("`herdr agent list` shows it.")
          and not [w for w in barred
                   if w in text.replace("needs permission /exit now please", "").lower()])
    return ok, text


def case_a_long_detail_is_cut(m):
    text = m.push_text("ended", "demo-worker-3", "w1:p3", "x" * 5000, "t")
    return len(text) < 300, len(text)


# ------------------------------------------------------------------- the log


def case_the_log_holds_one_line_per_target_with_what_was_read(m):
    tmp = Path(tempfile.mkdtemp(prefix="cpush-")) / "push.log"
    try:
        sent_by(m, {"w": WORKER, "p": PLANNER, "h": HELPER}, tmp)
        lines = tmp.read_text().splitlines()
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    ok = (len(lines) == 2
          and all("ended demo-worker-3 w1:p3 -> " in l and ": unread; " in l
                  and "no transcript in this case" in l
                  and "log by the suite" in l for l in lines)
          and "demo-planner-1 w1:p1" in lines[0] and "demo-planner-7 w1:p7" in lines[1])
    return ok, lines


def case_no_planner_is_a_logged_line_and_no_send(m):
    tmp = Path(tempfile.mkdtemp(prefix="cpush-")) / "push.log"
    try:
        asked = sent_by(m, {"w": WORKER, "d": OTHER}, tmp)
        lines = tmp.read_text().splitlines() if tmp.exists() else []
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    return (not asked and len(lines) == 1 and ": no-planner; " in lines[0]
            and "2 session(s)" in lines[0]), (asked, lines)


def case_the_log_is_the_campaigns_runtime(m):
    tmp = Path(tempfile.mkdtemp(prefix="cpush-"))
    try:
        (tmp / "camp" / "runtime").mkdir(parents=True)
        fake = tmp / "campaign-directory.py"
        fake.write_text(f"print({str(tmp / 'camp')!r})\n")
        real, m.DIRECTORY_SCRIPT = m.DIRECTORY_SCRIPT, fake
        try:
            got = m.log_path("demo")
        finally:
            m.DIRECTORY_SCRIPT = real
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return got == (tmp / "camp" / "runtime" / "push.log", "campaign-directory.py"), got


def case_no_campaign_directory_logs_under_tmpdir_and_says_so(m):
    tmp = Path(tempfile.mkdtemp(prefix="cpush-"))
    try:
        fake = tmp / "campaign-directory.py"
        fake.write_text("import sys\nprint('none')\nsys.exit(1)\n")
        real, m.DIRECTORY_SCRIPT = m.DIRECTORY_SCRIPT, fake
        try:
            path, where = m.log_path("demo")
        finally:
            m.DIRECTORY_SCRIPT = real
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return (path.name == "campaign-push-demo.log" and "$TMPDIR" in where
            and "'none'" in where), (path, where)


def case_a_listing_not_read_is_a_logged_line_and_no_send(m):
    tmp = Path(tempfile.mkdtemp(prefix="cpush-")) / "push.log"
    try:
        asked = sent_by(m, None, tmp)
        lines = tmp.read_text().splitlines() if tmp.exists() else []
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    return (not asked and len(lines) == 1 and ": undelivered; herdr agent list "
            "not read" in lines[0]), (asked, lines)


# ------------------------------------------------------- the hook's own shape


def case_a_listing_not_read_starts_no_sender(m):
    got, spawned = hooked(m, None, "sid-w")
    return not got[0] and not spawned and "not read" in got[1], (got, spawned)


def case_no_herdr_env_sends_nothing(m):
    """The guard every driving herdr command here carries. `herdr` is never
    reached: PATH is empty for the call, so a send that went past the guard
    reads `FileNotFoundError` and not the guard's sentence."""
    keep = dict(os.environ)
    try:
        os.environ.pop("HERDR_ENV", None)
        os.environ["PATH"] = ""
        got = m.herdr_prompt("w1:p1", TEXT)
    finally:
        os.environ.clear()
        os.environ.update(keep)
    return got == (False, "HERDR_ENV is not 1"), got


def case_cli_a_dropped_event_imports_and_lists_nothing(m):
    """Most events are dropped: the copy has no sibling to import, so an early
    return that went missing would leave a crash line."""
    tmp = tempfile.mkdtemp(prefix="cpush-")
    try:
        r = subprocess.run([sys.executable, m.__file__], capture_output=True,
                           input=json.dumps({"hook_event_name": "Notification",
                                             "notification_type": "idle_prompt"}),
                           text=True, timeout=60, env=dict(os.environ, TMPDIR=tmp))
        crashed = Path(tmp, "campaign-push-crash.log").exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return (r.returncode == 0 and r.stdout == "" and r.stderr == ""
            and not crashed), (r.returncode, r.stdout, r.stderr, crashed)



def case_cli_a_crash_is_silent_exit_zero_and_a_logged_line(m):
    tmp = tempfile.mkdtemp(prefix="cpush-")
    try:
        r = subprocess.run([sys.executable, m.__file__], input="not json",
                           capture_output=True, text=True, timeout=60,
                           env=dict(os.environ, TMPDIR=tmp))
        crash = Path(tmp, "campaign-push-crash.log")
        logged = crash.read_text() if crash.exists() else ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return (r.returncode == 0 and r.stdout == "" and r.stderr == ""
            and "JSONDecodeError" in logged), (r.returncode, r.stdout, r.stderr, logged)


def case_the_sender_runs_in_a_session_of_its_own(m):
    tmp = Path(tempfile.mkdtemp(prefix="cpush-"))
    out = tmp / "sid"
    try:
        m.spawn_detached([sys.executable, "-c",
                          "import os,sys,time; open(sys.argv[1]+'.tmp','w').write("
                          "str(os.getsid(0))); os.rename(sys.argv[1]+'.tmp', sys.argv[1])",
                          str(out)])
        for _ in range(100):
            if out.exists():
                break
            import time
            time.sleep(0.05)
        got = out.read_text() if out.exists() else "never written"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return got.isdigit() and int(got) != os.getsid(0), (got, os.getsid(0))


def case_the_base_settings_hold_the_window(m):
    """rule-check#481: every session started at the base root compacts by the
    harness's own window, so no watch has to send `/compact`."""
    got = json.loads((BASE / ".claude" / "settings.json").read_text()).get(
        "autoCompactWindow")
    return got == 250000, got


def case_nothing_in_the_tree_starts_a_watch(m):
    """rule-check#481 step 3: the push replaced the planner's watch, so no
    file in the tree names the deleted heartbeat script, and nothing can
    start one. Read off git's index, not the disk, so an untracked scratch
    file is not a hit; the Jev corpus is data that quotes old prompts, and is
    left out. The name is spelled in two halves so this file is not a hit."""
    r = subprocess.run(["git", "-C", str(BASE), "grep", "-l", "campaign-" + "heartbeat",
                        "--", ".", ":!scripts/jev/corpus"],
                       capture_output=True, text=True)
    hits = r.stdout.split()
    return r.returncode == 1 and not hits, hits or r.stderr


CASES = {k: v for k, v in sorted(globals().items()) if k.startswith("case_")}

MUTATIONS = [
    ("the permission prompt's type", 'PERMISSION = "permission_prompt"', 'PERMISSION = "permission"',
     "case_permission_prompt_is_kept"),
    ("only that type", "if kind != PERMISSION:", "if False:", "case_another_notification_pushes_nothing"),
    ("the reason in the text", 'return "ended", f"reason {reason}"', 'return "ended", "ended"',
     "case_session_end_carries_its_reason"),
    ("/clear keeps the session", "if reason == KEPT_SESSION:", "if False:", "case_clear_pushes_nothing"),
    ("no third event", 'return None, f"event {name!r}"', 'return "ended", f"event {name!r}"',
     "case_any_other_event_pushes_nothing"),
    ("only a worker pushes", 'names.role_word(row["name"]) != WORKER', "False",
     "case_a_planner_and_an_unnamed_session_push_nothing"),
    ("the sender's argv", '"--send", event, name,', '"--send", name, event,', "case_a_worker_starts_the_sender"),
    ("the planner's slug", 'if names.campaign_of(r["name"]) == slug', "if True",
     "case_every_planner_of_the_slug_and_no_other"),
    ("the planner role", 'and names.role_word(r["name"]) == PLANNER)', "and True)",
     "case_every_planner_of_the_slug_and_no_other"),
    ("the listing read at each push", "sessions, err = names.herdr_sessions()\n    if sessions is None:\n        line(",
     "sessions, err = CACHE.setdefault('s', names.herdr_sessions())\n    if sessions is None:\n        line(",
     "case_the_target_is_found_by_name_at_each_push"),
    ("ready before the send", "if status in READY:", "if True:", "case_waits_for_idle_before_sending"),
    ("done is ready", 'READY = ("idle", "done")', 'READY = ("idle",)', "case_done_is_ready_too"),
    ("typed text only", '"".join(texts((r.get("message") or {}).get("content")))', 'json.dumps(r.get("message"))',
     "case_text_inside_a_tool_result_has_not_landed"),
    ("a gain, not a presence", "if after is not None and after > before:", "if after:",
     "case_delivered_is_a_gain_not_a_presence"),
    ("the second send", "ATTEMPTS = 2", "ATTEMPTS = 1", "case_the_second_send_can_land"),
    ("a refused send is not a send", "if sent:\n                    break", "if True:\n                    break",
     "case_a_refused_send_is_the_same_wait"),
    ("the window's last count", "            sleep(WAIT_EVERY)\n            after, err = count(sid)",
     "            after, err = count(sid)\n            sleep(WAIT_EVERY)",
     "case_the_window_ends_on_a_count_not_a_sleep"),
    ("why the wait ran out", 'why = (f"herdr agent list not read: {err}" if sessions is None',
     'why = (f"target read {status}" if sessions is None', "case_a_listing_never_read_is_undelivered_and_said"),
    ("a harness note is not a prompt", 'or r.get("isMeta") or r.get("isSidechain")):', "):",
     "case_only_a_typed_main_thread_record_counts"),
    ("a user record only", 'or r.get("type") != "user"', "", "case_only_a_typed_main_thread_record_counts"),
    ("the campaign's own log", 'if word.startswith("/") and', "if False and", "case_the_log_is_the_campaigns_runtime"),
    ("where the fallback came from", 'f"$TMPDIR, campaign-directory.py said {word!r}")', 'f"$TMPDIR")',
     "case_no_campaign_directory_logs_under_tmpdir_and_says_so"),
    ("the HERDR_ENV guard", 'if os.environ.get("HERDR_ENV") != "1":', "if False:", "case_no_herdr_env_sends_nothing"),
    ("a dropped event returns early", "if event_of(payload)[0] is None:   #", "if False:   #",
     "case_cli_a_dropped_event_imports_and_lists_nothing"),
    ("the wait's ceiling", "if polls >= READY_POLLS:", "if False:", "case_never_ready_is_undelivered_at_the_ceiling"),
    ("a target that left", "if sessions is not None and row is None:", "if False:", "case_a_target_that_left_is_gone"),
    ("an unread transcript", "if before is None:", "if False:", "case_an_unread_transcript_is_sent_once_and_said"),
    ("what it says it is", 'OPENING = "campaign-push (machine-made, no instruction):"', 'OPENING = "campaign-push:"',
     "case_the_text_is_one_machine_made_line_with_no_instruction"),
    ("one line whatever the detail", 'detail = " ".join(str(detail).split())[:DETAIL_CHARS]',
     "detail = str(detail)[:DETAIL_CHARS]", "case_the_text_is_one_machine_made_line_with_no_instruction"),
    ("the detail's ceiling", 'detail = " ".join(str(detail).split())[:DETAIL_CHARS]',
     'detail = " ".join(str(detail).split())', "case_a_long_detail_is_cut"),
    ("why, in the log", 'f"{why}; log by {where}\\n")', 'f"log by {where}\\n")',
     "case_the_log_holds_one_line_per_target_with_what_was_read"),
    ("no planner is logged", 'line("-", "no-planner",', '(lambda *a: None)("-", "no-planner",',
     "case_no_planner_is_a_logged_line_and_no_send"),
    ("no exception escapes", "except Exception as e:   #", "except KeyError as e:   #",
     "case_cli_a_crash_is_silent_exit_zero_and_a_logged_line"),
    ("the crash is logged", "with open(CRASH_LOG, \"a\") as f:", "with open(os.devnull, \"a\") as f:",
     "case_cli_a_crash_is_silent_exit_zero_and_a_logged_line"),
    ("the sender's own session", "start_new_session=True", "start_new_session=False",
     "case_the_sender_runs_in_a_session_of_its_own"),
]

COPIES = []


def load(source):
    """The source as a module from a file of its own, so a case that runs it
    as a command runs the mutant and not the script."""
    d = Path(tempfile.mkdtemp(prefix="cpush-mut-"))
    COPIES.append(d)
    # as deep as the script sits, since it resolves the base from its own path:
    # flat under /tmp it has too few parents and the import itself crashes
    # (pr#482's first CI run), which no case would have caught on macOS.
    (d / ".claude" / "skills" / "assuming-role" / "scripts").mkdir(parents=True)
    copy = d / ".claude" / "skills" / "assuming-role" / "scripts" / SCRIPT.name
    copy.write_text("CACHE = {}\n" + source if "CACHE" in source else source)
    copy.chmod(0o755)
    return harness.load(copy, "campaign_push")


def main():
    # a fast clock for the suite alone: the ceilings are read, not waited
    source = SCRIPT.read_text().replace("READY_POLLS = 360 ", "READY_POLLS = 4 ", 1)
    try:
        harness.mutate(source, load, CASES, MUTATIONS)
    finally:
        for d in COPIES:
            shutil.rmtree(d, ignore_errors=True)
    print(f"campaign-push-test: {len(CASES)} cases, {len(MUTATIONS)} mutations, script {SCRIPT}")
    status, want = harness.report(), len(CASES) + len(MUTATIONS)
    if len(harness.RAN) != want:
        print(f"FAIL  the suite ran {len(harness.RAN)} cases, not {want}")
        return 1
    return status


if __name__ == "__main__":
    sys.exit(main())
