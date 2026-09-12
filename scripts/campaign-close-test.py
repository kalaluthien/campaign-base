#!/usr/bin/env python3
# witnesses: S2_SubIssueDropped, R7e_WorkerRuleAdmitsTheDroppedSubIssue, H1_HeartbeatRetiresADoneWorker
"""Prove campaign-close refuses on every gate, with its reason beside it, and
lets the ordinary close through.

Every case calls `main` in-process over a fake `run`: the readers it asks --
campaign-tracker, campaign-claim, campaign-directory, campaign-local-work,
the heartbeat -- answer with text in the shape each prints, and `gh` and
`herdr` answer with a status. Nothing reads GitHub or drives a pane; every
action is asserted on what was ASKED. campaign-claim's slug and herdr
readers are replaced on the module the script imported.

AN ALLOW CASE BESIDE EVERY REFUSAL: another sub-issue's claim, a `landed`
claim, a counted row of another branch, a later poll that finds the pane gone.

Then EVERY REFUSAL IS BROKEN IN TURN: the source is mutated in memory, loaded
as the same file, and the case named for that branch must go red by its own
assertion. A crash fails the mutation. The unmutated run goes first.

Usage: scripts/campaign-close-test.py
"""
import contextlib
import io
import os
import subprocess
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "campaign-close.py"
N, ISSUE, SLUG, SID = "10", "32", "rc", "S1"
TRACKER = "kalaluthien/campaign-base"
PANE, OTHER = "w1:p2", "w1:p3"


def load(source):
    m = types.ModuleType("campaign_close")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return m


# ------------------------------------------------------------- the readers' text


def settlement(word="open", issue=ISSUE):
    return (f"campaign issue {TRACKER}#{N}  [OPEN]  Title\n"
            f"  -- claims: #{N} is `{SLUG}`\n"
            f"  {TRACKER}#{issue}  {word:<9} Drop me\n"
            f"  -- 0/1 settled; NOT closable: open sub-issues remain\n")


SETTLEMENT_CUT = f"campaign issue {TRACKER}#{N}  [OPEN]  Title\n"


UNSWEPT = "!! /c/repos/x: git worktree list failed"


def live(occupied=(), vacant=(), sessions=(), read=True):
    out = [f"scoped to campaign-{SLUG}", "reading 1  refs -- 1 claim(s)"]
    out += [] if read else [f"           {UNSWEPT}"]
    out += ["",
           f"claims checked out on this machine ({len(occupied)}) -- joined"]
    out += [f"  {b:<34} {p}" for b, p in occupied]
    out += ["", f"claims checked out nowhere on this machine ({len(vacant)})"]
    out += [f"  {b:<40} {m}" for b, m in vacant]
    if vacant:
        out += ["  `landed` is finished work whose ref outlived it, and blocks "
                "nothing. The rest are",
                "  one of: a delegate that exited, or a checkout on another "
                "machine. Ask before", "  treating either as free."]
    out += ["", f"live sessions of {SLUG} ({len(sessions)})"]
    out += [f"  {n:<24} {s:<8} {p:<10} /base" for n, s, p in sessions]
    if sessions:
        out += ["  WHICH of these holds which claim above is not derivable."]
    out += ["", "sessions named for no campaign under the base root (0)", ""]
    out += (["all three readings were made. 0 occupied."] if read
            else ["NOT all readings were made: 1 repository could not be swept",
                  f"  {UNSWEPT}"])
    return "\n".join(out) + "\n"


def local(rows=(), verdict="clear"):
    out = [f"campaign #{N}  base /base  directory /c/campaign-{SLUG}"]
    for counted, ident in rows:
        out += [f"  {' ' if counted else '~'} {TRACKER}  unpushed commit  "
                f"{ident}  [2 commit(s)]", "      found by  git log",
                "      clears by push"]
    n = sum(1 for c, _ in rows if c)
    out += [{"clear": f"  -- 0 item(s) exist only on this machine; clear",
             "counted": f"  -- {n} item(s) exist only on this machine; NOT "
                        f"clear: clear every counted row, then re-run",
             "unread": f"  -- {n} item(s) exist only on this machine, and 1 "
                       f"place(s) went unread; NOT clear: read every REPORT "
                       f"place by hand, then re-run",
             "refuse": "  -- REFUSE: `git worktree list` failed"}[verdict]]
    return "\n".join(out) + "\n"


def heartbeat(*lines):
    out = [f"read 3 session(s) from herdr agent list; 2 of {SLUG} (#{N})"]
    for word, pane, name, reason in lines:
        out += [f"{word} {pane} {name}: {reason}",
                f"  read: herdr idle; transcript /t.jsonl; banner no limit"]
    out += [f"would send /exit to {p}" for w, p, _, _ in lines if w == "retire"]
    return "\n".join(out) + "\n"


RETIRE_LINE = ("retire", PANE, "rc-worker-2", "released 1, compacted 2, no "
               "claim held, no prompt since the release, no tool call since "
               "the compaction")
RELEASE_OK = f"releasing rc/{ISSUE}-drop\ndeleted rc/{ISSUE}-drop\n"
RELEASE_REFUSED = ("refusing: kalaluthien/campaign-base says rc/32-drop is 2 "
                   "commit(s) ahead of main.\n")
ROW = {"name": "rc-planner-1", "status": "working", "cwd": "/base",
       "pane": "w1:p1"}


def world(**over):
    w = {"slug": SLUG, "settlement": settlement(),
         "live": live(vacant=[(f"rc/{ISSUE}-drop", "never merged")]),
         "directory": f"/c/campaign-{SLUG}", "local": local(),
         "release": RELEASE_OK, "gh": 0, "herdr": 0,
         "sessions": {SID: ROW}, "heartbeat": heartbeat(RETIRE_LINE),
         "env": {"CLAUDE_CODE_SESSION_ID": SID, "HERDR_ENV": "1"}}
    w.update(over)
    return w


def answer(w, a):
    ok = lambda out, rc=0: subprocess.CompletedProcess(a, rc, out, "")
    if a[0] == sys.executable:
        name, sub = Path(a[1]).name, a[2:]
        if name == "campaign-tracker.py" and sub[0] == "settlement":
            return ok(w["settlement"])
        if name == "campaign-claim.py":
            return ok(w[sub[0]])
        if name == "campaign-directory.py":
            return ok(w["directory"] + "\n", 0 if w["directory"].startswith("/")
                      else 2)
        if name == "campaign-local-work.py":
            return ok(w["local"])
        if name == "campaign-heartbeat.py":
            return ok(w["heartbeat"])
    if a[0] in ("gh", "herdr"):
        return subprocess.CompletedProcess(a, w[a[0]], "", f"{a[0]} failed")
    return subprocess.CompletedProcess(a, 127, "", "not faked")


def drive(m, argv, w):
    """(exit, printed, [argv asked], [sleeps])."""
    asked, sleeps = [], []

    def fake_run(*a, **kw):
        asked.append(list(a))
        return answer(w, list(a))
    m.run = fake_run
    m.CLAIM.campaign_slug = lambda n: ((w["slug"], "ok") if w["slug"]
                                       else (None, "no campaign: label"))
    polls = iter(w.get("polls", []))
    m.CLAIM.herdr_sessions = ((lambda: next(polls, (None, "no more polls")))
                              if "polls" in w else (lambda: (w["sessions"], None)))
    clock = [0.0]

    def sleep(s):
        sleeps.append(s)
        clock[0] += s
    m.time = types.SimpleNamespace(sleep=sleep, monotonic=lambda: clock[0])
    saved = {k: os.environ.pop(k, None) for k in ("CLAUDE_CODE_SESSION_ID",
                                                  "HERDR_ENV")}
    os.environ.update(w["env"])
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = m.main(argv)
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    return code, buf.getvalue(), asked, sleeps


DROP = ["sub-issue", N, ISSUE, "--not-planned", "superseded by rc#33"]
RETIRE = ["worker", N, PANE]


def closes(asked):
    return [a for a in asked if a[:3] == ["gh", "issue", "close"]]


def releases(asked):
    return [a for a in asked if a[0] == sys.executable and a[2:3] == ["release"]]


def prompts(asked):
    return [a for a in asked if a[:3] == ["herdr", "agent", "prompt"]]


def refused(m, argv, w, gate, *says):
    """A refusal: exit 1, the gate named, its why printed, each of `says` in
    the output, and nothing closed, released or prompted unless the case
    allows it."""
    code, out, asked, _ = drive(m, argv, w)
    lines = out.splitlines()
    head = next((ln for ln in lines if ln.startswith("REFUSE ")), "")
    ok = (code == 1 and head.startswith(f"REFUSE {gate}:")
          and f"  why: {m.WHY[gate]}" in lines and all(s in out for s in says))
    return ok, asked, out


def refusal(gate, *says, argv=DROP, acted=False, **over):
    def case(m):
        ok, asked, out = refused(m, argv, world(**over), gate, *says)
        if not acted:
            ok = ok and not (closes(asked) or releases(asked) or prompts(asked))
        return ok, out
    return case


# ------------------------------------------------------------- the allows


def case_drop(m):
    code, out, asked, _ = drive(m, DROP, world())
    c = closes(asked)
    return (code == 0 and len(c) == 1 and c[0][3] == ISSUE
            and c[0][c[0].index("--reason") + 1] == "not planned"
            and c[0][c[0].index("--comment") + 1] == (
                "DECISION rc-planner-1: closed not planned -- superseded by rc#33")
            and len(releases(asked)) == 1), out


def case_no_claim(m):
    code, out, asked, _ = drive(m, DROP, world(live=live(
        sessions=[("rc-worker-2", "working", OTHER)])))
    return code == 0 and len(closes(asked)) == 1 and not releases(asked), out


def case_dropped_resumes(m):
    code, out, asked, _ = drive(m, DROP, world(settlement=settlement("dropped")))
    return code == 0 and not closes(asked) and len(releases(asked)) == 1, out


def case_other_claim_here(m):
    code, out, asked, _ = drive(m, DROP, world(live=live(
        occupied=[(f"rc/{ISSUE}0-other", "/c/wt/320")],
        sessions=[("rc-worker-2", "working", OTHER)])))
    return code == 0 and len(closes(asked)) == 1 and not releases(asked), out


def case_landed_claim(m):
    code, out, asked, _ = drive(m, DROP, world(live=live(
        vacant=[(f"rc/{ISSUE}-drop", "landed as #99")],
        sessions=[("rc-worker-2", "working", OTHER)])))
    return code == 0 and len(closes(asked)) == 1, out


def case_other_local_row(m):
    code, out, asked, _ = drive(m, DROP, world(local=local(
        rows=[(True, f"rc/{ISSUE}0-other"), (False, f"rc/{ISSUE}-drop")],
        verdict="counted")))
    return code == 0 and len(closes(asked)) == 1, out


def case_owner(m):
    code, out, asked, _ = drive(m, DROP, world(env={}))
    c = closes(asked)
    return (code == 0 and c and c[0][c[0].index("--comment") + 1].startswith(
        "DECISION owner: ")), out


def case_no_directory(m):
    code, out, asked, _ = drive(m, DROP, world(directory="none"))
    lw = [a for a in asked if a[0] == sys.executable
          and Path(a[1]).name == "campaign-local-work.py"]
    return code == 0 and lw and lw[0][2:] == [N], out


def case_retire(m):
    code, out, asked, sleeps = drive(m, RETIRE, world(polls=[
        ({SID: dict(ROW, pane=PANE)}, None), ({SID: ROW}, None)]))
    return (code == 0 and prompts(asked) == [["herdr", "agent", "prompt", PANE,
                                              "/exit"]]
            and sleeps == [m.WAIT_EVERY]), out


def case_unread_poll_retries(m):
    code, out, asked, _ = drive(m, RETIRE, world(polls=[
        (None, "herdr exited 1"), ({SID: ROW}, None)]))
    return (code == 0 and len(prompts(asked)) == 1
            and f"poll 2: {PANE} is not listed" in out), out


def case_wait_counts(m):
    reads, sleeps = [], []

    def read():
        reads.append(1)
        return {SID: dict(ROW, pane=PANE)}, None
    gone, note = m.wait_gone(PANE, read=read, sleep=sleeps.append, polls=4,
                             every=7)
    return (not gone and len(reads) == 4 and sleeps == [7, 7, 7]
            and "poll 4" in note), note


# ------------------------------------------------------------- the refusals


def case_status_asked(m):
    two = [("rc-worker-2", "idle", OTHER), ("rc-worker-3", "working", "w1:p4")]
    ok, asked, out = refused(m, DROP, world(live=live(
        vacant=[(f"rc/{ISSUE}-drop", "never merged")], sessions=two)), "live",
        "2 session(s) of rc are listed")
    asks = [ln for ln in out.splitlines() if ln.startswith("  ask ")]
    return (ok and not closes(asked) and len(asks) == 2
            and all(f"STATUS to {n}: {SLUG}#{ISSUE}" in a
                    for (n, _, _), a in zip(two, asks))), out


def case_no_kill(m):
    # THE CEILING IS A LITERAL: 12 polls 5s apart is 11 sleeps, 55s measured.
    # Built from the script's own constants, the case moved with them.
    ok, asked, out = refused(m, RETIRE, world(polls=[
        ({SID: dict(ROW, pane=PANE)}, None)] * 12), "gone",
        f"poll 12: {PANE} is still listed after 55s",
        "/exit was sent to w1:p2")
    return (ok and len(prompts(asked)) == 1
            and not any(a[0] in ("kill", "pkill", "killall")
                        or a[:3] == ["herdr", "agent", "kill"] for a in asked)), out


CASES = {
    # allows
    "drop: an open sub-issue with a vacant claim and nobody listed is closed "
    "and released": case_drop,
    "drop: no claim names it, so listed sessions do not refuse and nothing is "
    "released": case_no_claim,
    "drop: a dropped row resumes at the release without closing again":
        case_dropped_resumes,
    "drop: another sub-issue's claim checked out here is its own business":
        case_other_claim_here,
    "drop: a landed claim of this sub-issue stands in nobody's way":
        case_landed_claim,
    "drop: a counted local row of another branch does not refuse":
        case_other_local_row,
    "drop: no session id writes the comment as owner": case_owner,
    "drop: no campaign directory here reads the base alone": case_no_directory,
    "retire: a worker read as retire gets /exit and is gone on a later poll":
        case_retire,
    "retire: a listing that did not read is one more poll": case_unread_poll_retries,
    "wait: it polls exactly its count and sleeps between polls only":
        case_wait_counts,
    # refusals
    "refuse: the slug did not read": refusal("slug", "did not read", slug=None),
    "refuse: settlement did not finish": refusal(
        "settlement", "did not finish", settlement=SETTLEMENT_CUT),
    "refuse: the sub-issue is not in the index": refusal(
        "settlement", "is not in the campaign's sub-issue index",
        settlement=settlement(issue="33")),
    "refuse: a #320 row is not #32's": refusal(
        "settlement", "is not in the campaign's sub-issue index",
        settlement=settlement(issue=ISSUE + "0")),
    "refuse: a complete row is not open": refusal(
        "settlement", "reads `complete`", settlement=settlement("complete")),
    "refuse: live did not make every reading, and names what it could not": refusal(
        "live", f"no count from it is safe: {UNSWEPT}\n", live=live(read=False)),
    "refuse: this sub-issue's claim is checked out here": refusal(
        "live", f"rc/{ISSUE}-drop is checked out at /c/wt/32",
        live=live(occupied=[(f"rc/{ISSUE}-drop", "/c/wt/32")])),
    "refuse: a claim stands and sessions are listed, and each is asked":
        case_status_asked,
    "refuse: the campaign directory reads unknown": refusal(
        "local-work", "answered 'unknown'", directory="unknown"),
    "refuse: local-work did not finish": refusal(
        "local-work", "did not finish", local=local(verdict="refuse")),
    "refuse: local-work left places unread": refusal(
        "local-work", "went unread", local=local(verdict="unread")),
    "refuse: a counted local row names this sub-issue's branch": refusal(
        "local-work", f"rc/{ISSUE}-drop", local=local(
            rows=[(True, f"rc/{ISSUE}-drop")], verdict="counted")),
    "refuse: the comment's author cannot be named": refusal(
        "author", "has no name of rc in herdr (no row)", sessions={}),
    "refuse: a session of another campaign is not this campaign's author": refusal(
        "author", "has no name of rc", sessions={SID: dict(ROW, name="zz-planner-1")}),
    "refuse: gh could not close the sub-issue": refusal(
        "close", "gh exited 1", gh=1, acted=True),
    "refuse: release refused, and the closed issue is said": refusal(
        "release", "ahead of main", "is closed not planned; its claim still "
        "stands", release=RELEASE_REFUSED, acted=True),
    "refuse: the heartbeat gives the pane no verdict": refusal(
        "retire", "no verdict", argv=RETIRE, heartbeat=heartbeat()),
    "refuse: the heartbeat reads keep, whatever another pane reads": refusal(
        "retire", "as `keep`: context 9 < 200", argv=RETIRE, heartbeat=heartbeat(
            ("retire", OTHER, "rc-worker-3", "done"),
            ("keep", PANE, "rc-worker-2", "context 9 < 200"))),
    "refuse: HERDR_ENV is not 1": refusal(
        "herdr", "not 1", argv=RETIRE, env={}),
    "refuse: herdr could not send /exit": refusal(
        "exit", "herdr exited 1", argv=RETIRE, herdr=1, acted=True),
    "refuse: still listed after the wait, and never killed": case_no_kill,
}

MUTATIONS = [
    ("slug", 'raise Refused("slug",', 'return "rc"\n        raise Refused("slug",',
     "refuse: the slug did not read"),
    ("settlement unfinished", 'return None, f"settlement did not finish',
     'return "open", f"settlement did not finish',
     "refuse: settlement did not finish"),
    ("settlement not indexed", 'return None, f"{ref} is not in the',
     'return "open", f"{ref} is not in the',
     "refuse: the sub-issue is not in the index"),
    ("settlement word", 'raise Refused("settlement", f"the row reads',
     'return "open"\n    raise Refused("settlement", f"the row reads',
     "refuse: a complete row is not open"),
    ("dropped skips the close", 'if word == "open":\n        step_close',
     'if True:\n        step_close',
     "drop: a dropped row resumes at the release without closing again"),
    ("live unread", 'if not reading["read"]:', 'if False:',
     "refuse: live did not make every reading, and names what it could not"),
    ("live names the unswept", 'out["unread"].append(said)', "pass",
     "refuse: live did not make every reading, and names what it could not"),
    ("the row is this issue's exactly", "if len(t) >= 2 and t[0] == ref:",
     "if len(t) >= 2 and ref in t[0]:", "refuse: a #320 row is not #32's"),
    ("checked out here", "if here or (away and who):", "if (away and who):",
     "refuse: this sub-issue's claim is checked out here"),
    ("listed sessions", "if here or (away and who):", "if here:",
     "refuse: a claim stands and sessions are listed, and each is asked"),
    ("each is asked", "for name, status, pane in who:",
     "for name, status, pane in []:",
     "refuse: a claim stands and sessions are listed, and each is asked"),
    ("landed blocks nothing", 'if i == issue and not rest.startswith("landed as")]',
     "if i == issue]", "drop: a landed claim of this sub-issue stands in nobody's way"),
    ("the issue matches exactly",
     'here = [(b, rest) for b, i, rest in reading["occupied"] if i == issue]',
     'here = [(b, rest) for b, i, rest in reading["occupied"] if issue in i]',
     "drop: another sub-issue's claim checked out here is its own business"),
    ("directory word", 'elif word.startswith("/"):', "elif True:",
     "refuse: the campaign directory reads unknown"),
    ("local unfinished", "if not finished:", "if False:",
     "refuse: local-work did not finish"),
    ("local unread", "if unread:", "if False:",
     "refuse: local-work left places unread"),
    ("local row", "if rows:", "if False:",
     "refuse: a counted local row names this sub-issue's branch"),
    ("local row is this issue's",
     "for tok in line.split())]", "for tok in line.split()) or True]",
     "drop: a counted local row of another branch does not refuse"),
    ("author", "if not name or NAMES.campaign_of(name) != slug:", "if False:",
     "refuse: the comment's author cannot be named"),
    ("the author is of this campaign", "NAMES.campaign_of(name) != slug:",
     "NAMES.campaign_of(name) is None:",
     "refuse: a session of another campaign is not this campaign's author"),
    ("close status", 'if r.returncode != 0:\n        raise Refused("close"',
     'if False:\n        raise Refused("close"',
     "refuse: gh could not close the sub-issue"),
    ("release words", "if refusal or not done:", "if False:",
     "refuse: release refused, and the closed issue is said"),
    ("release only a claim", "if branches:", "if True:",
     "drop: no claim names it, so listed sessions do not refuse and nothing is "
     "released"),
    ("retire word", "if word != RETIRE:", "if False:",
     "refuse: the heartbeat reads keep, whatever another pane reads"),
    ("this pane's line", "format(pane=re.escape(pane))", r'format(pane=r"\S+")',
     "refuse: the heartbeat reads keep, whatever another pane reads"),
    ("herdr guard", 'if os.environ.get("HERDR_ENV") != "1":', "if False:",
     "refuse: HERDR_ENV is not 1"),
    ("exit status", 'if r.returncode != 0:\n        raise Refused("exit"',
     'if False:\n        raise Refused("exit"', "refuse: herdr could not send /exit"),
    ("gone", "if not gone:", "if False:",
     "refuse: still listed after the wait, and never killed"),
    ("the poll ceiling", "WAIT_POLLS = 12", "WAIT_POLLS = 36",
     "refuse: still listed after the wait, and never killed"),
    ("the poll spacing", "WAIT_EVERY = 5", "WAIT_EVERY = 6",
     "refuse: still listed after the wait, and never killed"),
    ("the wait is measured", 'after {time.monotonic() - began:.0f}s',
     'after {WAIT_POLLS * WAIT_EVERY}s',
     "refuse: still listed after the wait, and never killed"),
    ("unread is not gone", 'note = f"poll {k + 1}: {why}"',
     'return True, f"poll {k + 1}: {why}"',
     "retire: a listing that did not read is one more poll"),
    ("sleep between polls", "if k + 1 < polls:", "if True:",
     "wait: it polls exactly its count and sleeps between polls only"),
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
            failed.append(f"FAIL  {name} -- {str(detail)[-600:]}")
    help_out = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                              capture_output=True, text=True).stdout
    if "Holds when:" not in help_out:
        failed.append("FAIL  --help from the shipped script carries no "
                      "`Holds when:`")
    print(f"{len(CASES) + 1 - len(failed)}/{len(CASES) + 1} cases pass")
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
