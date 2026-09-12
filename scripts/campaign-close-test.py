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
import shutil
import subprocess
import sys
import tempfile
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
    for counted, ident, *repo in rows:
        out += [f"  {' ' if counted else '~'} {(repo or [TRACKER])[0]}  "
                f"unpushed commit  {ident}  [2 commit(s)]",
                "      found by  git log", "      clears by push"]
    n = sum(1 for c, *_ in rows if c)
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


INSTALLED_CLEAR = ("kalaluthien/campaign-base  /base  HEAD a1  origin/main a1  -- "
                   "current\n1 row(s) read, 0 behind, 0 apply failed, 0 unread "
                   "-- clear\n")
INSTALLED_BEHIND = ("kalaluthien/campaign-base  /base  HEAD a1  origin/main b2  -- "
                    "behind 2\n1 row(s) read, 1 behind, 0 apply failed, 0 "
                    "unread -- NOT clear\n")
MEMBER = "acme/member"
README_OLD = f"## Intent\n\n- old\n\n## Repos\n\n- {MEMBER}\n"
README_NEW = f"## Intent\n\n- new\n\n## Repos\n\n- {MEMBER}\n"
README_DROPPED = "## Intent\n\n- new\n\n## Repos\n\n- none\n"
TMP = []


def check_line(kind, parent="no", n=ISSUE):
    """`campaign-tracker.py check`'s first line, as it prints it."""
    label = "yes" if kind == "campaign issue" else "no"
    return (f"read {TRACKER}#{n}: {kind} (label `campaign`: {label}, parent: "
            f"{parent})\n  title  9 chars (ceiling 40)\n")


def settlement_all(rows=((f"{TRACKER}#{ISSUE}", "complete"),), state="OPEN"):
    out = [f"campaign issue {TRACKER}#{N}  [{state}]  Title",
           f"  -- claims: #{N} is `{SLUG}`"]
    out += [f"  {ref}  {word:<9} Title of it" for ref, word in rows]
    words = [w for _, w in rows]
    settled = sum(w in ("complete", "dropped") for w in words)
    blockers = (["open sub-issues remain"] if "open" in words else []) + (
        [f"{words.count('unread')} sub-issue(s) could not be read, which "
         f"settles nothing either way"] if "unread" in words else [])
    out += [f"  -- {settled}/{len(rows)} settled; "
            + ("closable" if not blockers else "NOT closable: " + "; ".join(blockers))]
    return "\n".join(out) + "\n"


def whole(readme=README_NEW, body=README_OLD, derived=None, marker=True,
          **over):
    """A world with a real campaign directory under a temporary base root:
    the delete removes it for real, and the sync reads and writes its files."""
    root = Path(tempfile.mkdtemp())
    TMP.append(root)
    d = root / f"campaign-{SLUG}-260912"
    (d / "runtime").mkdir(parents=True)
    (d / "scripts").mkdir()
    (d / "scripts" / ".gitkeep").write_text("")
    (d / "AGENTS.md").write_text("# principles\n")
    (d / "repos" / "member").mkdir(parents=True)
    if marker:
        (d / ".campaign").write_text(f"{N} {SLUG}\n")
    (d / "README.md").write_text(readme)
    if derived is not False:
        (d / "runtime" / "campaign-issue-body-derived.md").write_text(
            body if derived is None else derived)
    w = world(directory=str(d), root=str(root), body=body,
              settlement=settlement_all(),
              live=live(vacant=[(f"rc/{ISSUE}-drop", "landed as #99")]))
    w.update(over)
    w["dir"] = d
    return w


def world(**over):
    w = {"slug": SLUG, "settlement": settlement(),
         "live": live(vacant=[(f"rc/{ISSUE}-drop", "never merged")]),
         "directory": f"/c/campaign-{SLUG}", "local": local(),
         "release": RELEASE_OK, "gh": 0, "herdr": 0,
         "sessions": {SID: ROW}, "heartbeat": heartbeat(RETIRE_LINE),
         "env": {"CLAUDE_CODE_SESSION_ID": SID, "HERDR_ENV": "1"},
         "bound": "here\n", "standing": "not-standing\n",
         "installed": INSTALLED_CLEAR, "body": "", "gh_edit": 0, "gh_view": 0,
         "origin": MEMBER, "lands": {},
         "root": "/c", "released": {}, "issue": "none\n",
         "check": ""}
    w.update(over)
    return w


def answer(w, a):
    ok = lambda out, rc=0: subprocess.CompletedProcess(a, rc, out, "")
    if a[0] == sys.executable:
        name, sub = Path(a[1]).name, a[2:]
        if name == "campaign-tracker.py":
            return ok(w[sub[0]])
        if "--branch" in sub and name == "campaign-claim.py":
            return ok(w["released"].get(sub[sub.index("--branch") + 1],
                                        RELEASE_OK))
        if name == "campaign-claim.py" and sub[0] == "live" and "live_seq" in w:
            seq = w["live_seq"]
            return ok(seq.pop(0) if len(seq) > 1 else seq[0])
        if name == "campaign-claim.py":
            return ok(w[sub[0]])
        if name == "campaign-installed.py":
            w["installed_read"] = Path(sub[1]).read_text()
            return ok(w["installed"])
        if name == "campaign-directory.py":
            w["directory_args"] = sub
            return ok(w["directory"] + "\n", 0 if w["directory"].startswith("/")
                      else 2)
        if name == "campaign-local-work.py":
            return ok(w["local"])
        if name == "campaign-heartbeat.py":
            return ok(w["heartbeat"])
    if a[:3] == ["gh", "issue", "view"]:
        return ok(w["body"], w["gh_view"])
    if a[:3] == ["gh", "issue", "edit"]:
        # What GitHub keeps: the file with a newline more, as measured, or
        # whatever the case says it stored instead.
        w["body"] = w.get("store") or Path(a[a.index("--body-file") + 1]).read_text() + "\n"
        return subprocess.CompletedProcess(a, w["gh_edit"], "", "gh failed")
    if a[:3] == ["gh", "issue", "comment"]:
        w["comment"] = Path(a[a.index("--body-file") + 1]).read_text()
    if a[:3] == ["gh", "issue", "close"]:
        return subprocess.CompletedProcess(a, w.get("gh_close", w["gh"]), "",
                                           "gh failed")
    if a[0] in ("gh", "herdr"):
        return subprocess.CompletedProcess(a, w[a[0]], "", f"{a[0]} failed")
    if a[0] == "lsof":
        return subprocess.CompletedProcess(a, w.get("lsof_rc", 1),
                                           w.get("lsof", ""), "")
    if a[:2] == ["git", "-C"] and a[3:] == ["worktree", "prune"]:
        return ok("")
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
    m.CLAIM.base_root = lambda: (w["root"], None)
    m.CLAIM.remote_of = lambda clone: w["origin"]
    m.CLAIM.issue_repo = lambda issue, default: w["lands"].get(
        issue, (TRACKER, None, "lands in the base"))
    clock = [0.0]

    def sleep(s):
        sleeps.append(s)
        clock[0] += s
    m.time = types.SimpleNamespace(sleep=sleep, monotonic=lambda: clock[0])
    saved = {k: os.environ.pop(k, None) for k in ("CLAUDE_CODE_SESSION_ID",
                                                  "HERDR_ENV")}
    os.environ.update(w["env"])
    buf = io.StringIO()
    was = os.getcwd()
    os.chdir(w.get("cwd") or tempfile.gettempdir())
    try:
        # argparse exits on an argv it refuses; its status is the reading,
        # so a case asserts on it rather than the run ending.
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                code = m.main(argv)
            except SystemExit as e:
                code = e.code
    finally:
        os.chdir(was)
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



# ------------------------------------------------------------- the whole


CLOSE = ["campaign", N]
CLOSE_YES = CLOSE + ["--close"]
CLOSE_ALL = CLOSE + ["--close", "--delete"]
HERE_SCOPE = ["here", N]
DROP_REPO = ["repo", N, MEMBER]


def writes(asked):
    return [a for a in asked if a[:2] == ["gh", "issue"]
            and a[2] in ("edit", "comment", "close")]


def halted(m, argv, w, flag, *says):
    code, out, asked, _ = drive(m, argv, w)
    head = next((ln for ln in out.splitlines() if ln.startswith("HALT: ")), "")
    return (code == 3 and (flag is None or head.endswith(
        f"re-run with {flag} once they say so")) and all(x in out for x in says)
            ), asked, out


def case_campaign_halts(m):
    ok, asked, out = halted(m, CLOSE, whole(), "--close", "every gate held")
    return ok and not writes(asked) and not releases(asked), out


def case_campaign_closes(m):
    w = whole(live=live(vacant=[(f"rc/{ISSUE}-drop", "landed as #99"),
                                ("rc/33-other", "landed as #98")]))
    ok, asked, out = halted(m, CLOSE_YES, w, "--delete", "is closed")
    d = w["dir"]
    edits = [a for a in asked if a[:3] == ["gh", "issue", "edit"]]
    rel = [a[a.index("--branch") + 1] for a in releases(asked)]
    c = closes(asked)
    return (ok and len(edits) == 1 and rel == [f"rc/{ISSUE}-drop", "rc/33-other"]
            and c and c[0][c[0].index("--comment") + 1]
            == "NOTE rc-planner-1: campaign closed."
            and w["comment"].startswith(f"NOTE rc-planner-1: closing campaign #{N} from ")
            and "AGENTS.md" in w["comment"] and "scripts/.gitkeep" in w["comment"]
            and "runtime" not in w["comment"].split("```")[1]
            and (d / "README.md").read_text() == README_NEW + "\n"
            and (d / "runtime" / "campaign-issue-body-derived.md").read_text()
            == README_NEW + "\n" and d.is_dir()), out


def case_leftovers(m):
    w = whole()
    wt = w["dir"] / "worktrees" / "40-x"
    (wt / "scripts").mkdir(parents=True)
    (wt / ".git").write_text("gitdir: /base/.git/worktrees/40-x\n")
    (wt / "scripts" / "a.py").write_text("")
    (w["dir"] / "repos" / "member" / "x").write_text("")
    got = m.leftovers(w["dir"])
    return got == [".campaign", "AGENTS.md", "README.md", "scripts",
                   "scripts/.gitkeep", "worktrees",
                   "worktrees/40-x/ (a git checkout)"], got


def case_campaign_deletes(m):
    w = whole()
    code, out, asked, _ = drive(m, CLOSE_ALL, w)
    return (code == 0 and not w["dir"].exists() and (Path(w["root"])).is_dir()
            and any(a[0] == "lsof" for a in asked)
            and any(a[3:] == ["worktree", "prune"] for a in asked
                    if a[:2] == ["git", "-C"])), out


def case_campaign_closed_already(m):
    w = whole(settlement=settlement_all(state="CLOSED"))
    code, out, asked, _ = drive(m, CLOSE + ["--delete"], w)
    return (code == 0 and not writes(asked) and len(releases(asked)) == 1
            and not w["dir"].exists()), out


def case_campaign_no_directory(m):
    w = whole(directory="none", body=README_OLD)
    code, out, asked, _ = drive(m, CLOSE_YES, w)
    return (code == 0 and w["installed_read"] == README_OLD
            and not [a for a in asked if a[:3] == ["gh", "issue", "edit"]]
            and "No directory of it on this machine" in w["comment"]
            and w["dir"].exists()), out


def case_campaign_synced_already(m):
    w = whole(readme=README_OLD)
    ok, asked, out = halted(m, CLOSE_YES, w, "--delete")
    return ok and not [a for a in asked if a[:3] == ["gh", "issue", "edit"]], out


def case_open_rows_halt(m):
    w = whole(settlement=settlement_all([(f"{TRACKER}#{ISSUE}", "open"),
                                         (f"{TRACKER}#33", "complete")]))
    ok, asked, out = halted(m, CLOSE_ALL, w, None, "1 open sub-issue(s) need a "
                            f"disposition", f"  open  {TRACKER}#{ISSUE}")
    return ok and not writes(asked) and w["dir"].exists(), out


def case_release_refused(m):
    w = whole(released={f"rc/{ISSUE}-drop": RELEASE_REFUSED})
    ok, asked, out = refused(m, CLOSE_YES, w, "release", "ahead of main",
                             "#10 is still open")
    return ok and not closes(asked), out


def case_lsof_open(m):
    w = whole(lsof="COMMAND PID\nzsh 12 me cwd DIR /x\n", lsof_rc=0)
    ok, asked, out = refused(m, CLOSE_ALL, w, "delete", "1 file(s) open under")
    return ok and w["dir"].exists(), out


def case_lsof_missing(m):
    w = whole(lsof_rc=127)
    ok, asked, out = refused(m, CLOSE_ALL, w, "delete", "lsof did not run")
    return ok and w["dir"].exists(), out


def case_not_a_campaign_dir(m):
    w = whole(marker=False)
    ok, asked, out = refused(m, CLOSE_ALL, w, "delete",
                             "is not a campaign directory")
    return ok and w["dir"].exists(), out


def whole_written(gate, *says, **over):
    """A refusal after the first write: the case names what was changed."""
    def case(m):
        w = whole(**over)
        ok, asked, out = refused(m, CLOSE_YES, w, gate, *says)
        return ok and w["dir"].exists(), out
    return case


def whole_refusal(gate, *says, argv=CLOSE_YES, **over):
    def case(m):
        w = whole(**over)
        ok, asked, out = refused(m, argv, w, gate, *says)
        return ok and not writes(asked) and not releases(asked) \
            and w["dir"].exists(), out
    return case


def case_here_lets_go(m):
    w = whole(bound="elsewhere other-mac\n",
              live=live(vacant=[(f"rc/{ISSUE}-drop", "never merged")]))
    code, out, asked, _ = drive(m, HERE_SCOPE + ["--delete"], w)
    return (code == 0 and not writes(asked) and not releases(asked)
            and not w["dir"].exists()), out


def case_here_halts(m):
    w = whole(bound="unbound\n")
    ok, asked, out = halted(m, HERE_SCOPE, w, "--delete")
    return ok and w["dir"].exists(), out


def case_here_nothing(m):
    code, out, asked, _ = drive(m, HERE_SCOPE, whole(
        bound="unbound\n", directory="none"))
    return code == 0 and "nothing on this machine to let go" in out, out


def dropped(readme=README_DROPPED, **over):
    return whole(readme=readme, body=README_OLD, **over)


def case_repo_drops(m):
    w = dropped(
        settlement=settlement_all([(f"{TRACKER}#{ISSUE}", "open")]),
        lands={ISSUE: (TRACKER, None, "lands in the base")},
        local=local(rows=[(True, "rc/40-x", "acme/other")], verdict="counted"),
        live=live(sessions=[("rc-worker-2", "working", OTHER)]))
    ok, asked, out = halted(m, DROP_REPO, w, "--delete")
    edits = [a for a in asked if a[:3] == ["gh", "issue", "edit"]]
    return ok and len(edits) == 1 and w["body"] == README_DROPPED + "\n", out


def case_repo_deletes_clone(m):
    w = dropped()
    code, out, asked, _ = drive(m, DROP_REPO + ["--delete"], w)
    return (code == 0 and not (w["dir"] / "repos" / "member").exists()
            and w["dir"].is_dir()), out


def case_repo_session_in_clone(m):
    w = dropped()
    clone = str(w["dir"] / "repos" / "member")
    w["live"] = live(sessions=[("rc-worker-2", "idle", OTHER)]).replace(
        "/base", clone)
    ok, asked, out = refused(m, DROP_REPO, w, "live", "1 session(s) of rc",
                             "ask rc-worker-2 (idle, w1:p3): which claim do you hold?")
    return ok and not writes(asked), out


def case_repo_claim_in_clone(m):
    w = dropped()
    w["live"] = live(occupied=[("rc/40-x", str(w["dir"] / "repos" / "member"))])
    ok, asked, out = refused(m, DROP_REPO, w, "live", "rc/40-x is checked out")
    return ok and not writes(asked), out


def repo_refusal(gate, *says, argv=DROP_REPO, **over):
    def case(m):
        w = dropped(**over)
        ok, asked, out = refused(m, argv, w, gate, *says)
        return ok and not writes(asked) and (w["dir"] / "repos" / "member").exists(), out
    return case


def case_prune_before_live(m):
    code, out, asked, _ = drive(m, DROP, world())
    prune = [i for i, a in enumerate(asked) if a[:2] == ["git", "-C"]
             and a[2] == "/c" and a[3:] == ["worktree", "prune"]]
    live_at = [i for i, a in enumerate(asked) if a[0] == sys.executable
               and a[2:3] == ["live"]]
    return (code == 0 and prune and live_at and prune[0] < live_at[0]
            and "pruned stale worktree entries under /c" in out), out


def case_directory_gets_the_base(m):
    w = world()
    code, out, asked, _ = drive(m, DROP, w)
    return code == 0 and w["directory_args"] == [N, "/c"], out


def case_compact_said_once(m):
    code, out, asked, _ = drive(m, DROP, world())
    w = whole(live=live(vacant=[(f"rc/{ISSUE}-drop", "landed as #99"),
                                ("rc/33-other", "landed as #98")]))
    code2, out2, _, _ = drive(m, CLOSE_YES, w)
    note = "enqueues /compact on the pane that runs this"
    return code == 0 and out.count(note) == 1 and out2.count(note) == 1, out + out2


def case_release_rereads_live(m):
    first = live(vacant=[(f"rc/{ISSUE}-drop", "landed as #99")])
    second = live(vacant=[(f"rc/{ISSUE}-drop", "landed as #99"),
                          ("rc/34-late", "landed as #97")])
    w = whole(live_seq=[first, second])
    ok, asked, out = halted(m, CLOSE_YES, w, "--delete")
    rel = [a[a.index("--branch") + 1] for a in releases(asked)]
    return ok and rel == [f"rc/{ISSUE}-drop", "rc/34-late"], out


def case_nested_campaign_dir(m):
    w = whole()
    nested = Path(w["root"]) / "deeper"
    nested.mkdir()
    w["dir"] = Path(shutil.move(str(w["dir"]), str(nested)))
    w["directory"] = str(w["dir"])
    ok, asked, out = refused(m, CLOSE_ALL, w, "delete",
                             "is not a campaign directory directly under")
    return ok and w["dir"].exists(), out


# ------------------------------------------------------------- the front door


def whole_padded(m):
    w = whole(check=check_line("campaign issue", n=N))
    code, out, asked, _ = drive(m, [f" {N} "], w)
    return code == 3 and "read as scope campaign -- #10 is a campaign issue" in out, out


def case_front_campaign(m):
    w = whole(check=check_line("campaign issue", n=N))
    code, out, asked, _ = drive(m, [N], w)
    return (code == 3 and "read as scope campaign -- #10 is a campaign issue, "
            "by campaign-tracker check" in out and "re-run with --close" in out), out


def case_front_sub_issue(m):
    w = world(check=check_line("sub-issue", parent=f"#{N}"))
    code, out, asked, _ = drive(m, [ISSUE, "--not-planned", "superseded"], w)
    rel = releases(asked)
    return (code == 0 and f"read as scope sub-issue -- #{ISSUE} is a sub-issue "
            f"of #{N}" in out and len(closes(asked)) == 1
            and rel and rel[0][3:5] == [N, ISSUE]), out


def case_front_sub_issue_halts(m):
    w = world(check=check_line("sub-issue", parent=f"#{N}"))
    code, out, asked, _ = drive(m, [ISSUE], w)
    return (code == 3 and 're-run with --not-planned "<why>"' in out
            and not closes(asked)), out


def case_front_repo(m):
    w = dropped()
    w["cwd"] = str(w["dir"] / "scripts")
    code, out, asked, _ = drive(m, [MEMBER], w)
    return (code == 3 and f"read as scope repo -- {MEMBER} is an owner/repo name; "
            f"#{N} from the marker" in out and "re-run with --delete" in out), out


def case_front_worker(m):
    # The first herdr reading is the front door's lookup, the second the
    # wait after the /exit.
    listed = {"S9": dict(ROW, name="rc-worker-2", pane=PANE)}
    w = world(issue=f"{N}\n", polls=[(listed, None), ({}, None)])
    code, out, asked, _ = drive(m, ["rc-worker-2"], w)
    hb = [a for a in asked if a[0] == sys.executable
          and Path(a[1]).name == "campaign-heartbeat.py"]
    return (code == 0 and f"read as scope worker -- rc-worker-2 is a session "
            f"herdr lists, pane {PANE}, of #{N}" in out and hb and hb[0][2:] == [N]
            and prompts(asked) == [["herdr", "agent", "prompt", PANE, "/exit"]]), out


def case_front_here_marker(m):
    w = whole(bound="unbound\n")
    w["cwd"] = str(w["dir"] / "scripts")
    code, out, asked, _ = drive(m, [], w)
    return (code == 3 and "read as scope here -- no target; #10 from the marker"
            in out and "re-run with --delete" in out), out


def case_front_here_session(m):
    w = whole(bound="unbound\n", issue=f"{N}\n")
    code, out, asked, _ = drive(m, [], w)
    return (code == 3 and "no target; #10 from this session's name rc-planner-1"
            in out), out


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
        "directory", "answered 'unknown'", directory="unknown"),
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
    # the whole: campaign
    "campaign: every gate held and no --close halts before any write":
        case_campaign_halts,
    "campaign: --close syncs, announces, releases every ref, closes, and "
    "halts for --delete": case_campaign_closes,
    "campaign: the delete's list names a checkout once and skips runtime and "
    "repos": case_leftovers,
    "campaign: --close --delete removes the directory and prunes":
        case_campaign_deletes,
    "campaign: a CLOSED issue skips the writes, releases, and deletes":
        case_campaign_closed_already,
    "campaign: no directory here reads the body for installs and deletes "
    "nothing": case_campaign_no_directory,
    "campaign: a body that already is the README is not written":
        case_campaign_synced_already,
    "campaign: open rows halt, listed, for the person's disposition":
        case_open_rows_halt,
    "refuse campaign: bound elsewhere": whole_refusal(
        "bound", "reads `elsewhere other-mac`", bound="elsewhere other-mac\n"),
    "refuse campaign: the binding did not read": whole_refusal(
        "bound", "answered 'error'", bound="error\n"),
    "refuse campaign: standing": whole_refusal(
        "standing", "carries the `standing` label", standing="standing\n"),
    "refuse campaign: a claim is checked out here": whole_refusal(
        "live", "rc/33-x is checked out at /c/wt/33",
        live=live(occupied=[("rc/33-x", "/c/wt/33")])),
    "refuse campaign: a claim checked out nowhere never merged": whole_refusal(
        "live", "rc/33-x is checked out nowhere here and reads `never merged`",
        live=live(vacant=[("rc/33-x", "never merged")])),
    "refuse campaign: a session is listed, and asked": whole_refusal(
        "live", "1 session(s) of rc are listed",
        "ask rc-worker-2 (idle, w1:p3): which claim do you hold?",
        live=live(sessions=[("rc-worker-2", "idle", OTHER)])),
    "refuse campaign: a counted local row": whole_refusal(
        "local-work", "1 item(s) exist only", local=local(
            rows=[(True, "rc/40-x")], verdict="counted")),
    "refuse campaign: local-work left places unread": whole_refusal(
        "local-work", "places went unread", local=local(verdict="unread")),
    "refuse campaign: local-work did not finish": whole_refusal(
        "local-work", "the whole reading did not finish",
        local=local(verdict="refuse")),
    "refuse campaign: an install is behind": whole_refusal(
        "installed", "behind 2", installed=INSTALLED_BEHIND),
    "refuse campaign: a row that did not read": whole_refusal(
        "settlement", "rows that did not read", settlement=settlement_all(
            [(f"{TRACKER}#{ISSUE}", "unread")])),
    "refuse campaign: settlement did not finish": whole_refusal(
        "settlement", "the reading did not finish", settlement=SETTLEMENT_CUT),
    "refuse campaign: no derived copy to compare the body against": whole_refusal(
        "sync", "campaign-issue-body-derived.md to compare", derived=False),
    "refuse campaign: the body moved since the README was derived": whole_refusal(
        "sync", "the body moved", derived="## Intent\n\n- older\n"),
    "refuse campaign: the body GitHub stored is not the README": whole_written(
        "sync", "is not the README", "the body was written",
        store="## Intent\n\n- mangled\n"),
    "refuse campaign: the close did not happen": whole_written(
        "close", "gh exited 1", "announced, and its claim refs released",
        gh_close=1),
    "refuse campaign: the announcement did not post": whole_written(
        "announce", "gh exited 1", "the body was written", gh=1),
    "refuse campaign: a ref that would not release keeps the issue open":
        case_release_refused,
    "refuse campaign: an open file under the directory": case_lsof_open,
    "refuse campaign: lsof that did not run": case_lsof_missing,
    "refuse campaign: a directory with no marker is not deleted":
        case_not_a_campaign_dir,
    "refuse campaign: a marked directory not directly under the base is not "
    "deleted": case_nested_campaign_dir,
    "refuse campaign: the number has a parent of its own": whole_refusal(
        "settlement", "#10 is not a campaign issue", "is itself a sub-issue of #9",
        settlement=settlement_all().replace(
            "  -- claims:", "  -- REPORT: this campaign issue is itself a "
            "sub-issue of #9 -- closing that campaign will not settle this one"
            "\n  -- claims:")),
    "refuse campaign: the number carries no campaign label": whole_refusal(
        "settlement", "#10 is not a campaign issue", "may be a sub-issue read",
        settlement=settlement_all().replace(
            "  -- claims:", "  -- REPORT: no `campaign` label, so this may be a "
            "sub-issue read as a campaign issue\n  -- claims:")),
    "campaign: the release reads live again after the writes":
        case_release_rereads_live,
    "live: stale worktree entries are pruned under the base before live reads":
        case_prune_before_live,
    "directory: campaign-directory is handed the base, not the cwd":
        case_directory_gets_the_base,
    "release: the compaction is said once, beside the first release":
        case_compact_said_once,
    "front: a campaign issue number reads as scope campaign": case_front_campaign,
    "front: a sub-issue number reads as scope sub-issue of its parent":
        case_front_sub_issue,
    "front: a sub-issue without --not-planned halts for the disposition":
        case_front_sub_issue_halts,
    "front: owner/repo reads as scope repo of the directory's campaign":
        case_front_repo,
    "front: a session herdr lists reads as scope worker on its pane":
        case_front_worker,
    "front: no target in a campaign directory reads as scope here by its marker":
        case_front_here_marker,
    "front: no target elsewhere reads as scope here by the session's name":
        case_front_here_session,
    "refuse front: a scope's name alone is not a target": refusal(
        "target", "'here' is the name of a scope, not a target", argv=["here"]),
    "refuse front: digits with more after them are not a number": refusal(
        "target", "'32x' is not a number", argv=["32x"]),
    "refuse front: check answering for another number": refusal(
        "target", "campaign-tracker check 7 answered for #8", argv=["7"],
        check=check_line("campaign issue", n="8")),
    "front: a padded number is read as the number": whole_padded,
    "refuse front: a number of the third kind": refusal(
        "target", "reads as a third kind", argv=["7"],
        check=check_line("third kind", n="7")),
    "refuse front: a number check could not read": refusal(
        "target", "printed no kind line", argv=["7"],
        check="campaign-tracker check: could not read kalaluthien/campaign-base#7\n"),
    "refuse front: a slash that names no repository": refusal(
        "target", "names no owner/repo", argv=["a/b/c"]),
    "refuse front: a word no session carries": refusal(
        "target", "0 of the 1 sessions herdr lists carry that name",
        argv=["rc-worker-9"]),
    "refuse front: a name two sessions carry": refusal(
        "target", "2 of the 2 sessions herdr lists carry that name",
        argv=["rc-worker-2"], sessions={
            "S8": dict(ROW, name="rc-worker-2", pane="w1:p8"),
            "S9": dict(ROW, name="rc-worker-2", pane="w1:p9")}),
    "refuse front: a session whose name carries no campaign": refusal(
        "target", "session plain carries no campaign name", argv=["plain"],
        sessions={"S9": dict(ROW, name="plain", pane=PANE)}),
    "refuse front: herdr did not answer the lookup": refusal(
        "target", "herdr agent list did not read: herdr is down", argv=["plain"],
        polls=[(None, "herdr is down")]),
    "refuse front: a session whose slug names no campaign": refusal(
        "target", "campaign-tracker issue rc answered 'none'", argv=["rc-worker-2"],
        sessions={"S9": dict(ROW, name="rc-worker-2", pane=PANE)}, issue="none\n"),
    "refuse front: no target, no campaign directory, no campaign name": refusal(
        "target", "no campaign directory holds", argv=[], env={}),
    "refuse front: a flag the scope does not take": whole_refusal(
        "target", "which does not take --not-planned",
        argv=[N, "--not-planned", "x"], check=check_line("campaign issue", n=N)),
    "refuse: a release that printed neither word did not release": refusal(
        "release", "printed neither", release=f"releasing rc/{ISSUE}-drop\n",
        acted=True),
    # the whole: here
    "here: bound elsewhere, a vacant claim does not block, and --delete lets "
    "it go": case_here_lets_go,
    "here: without --delete it halts": case_here_halts,
    "here: no directory here is nothing to let go": case_here_nothing,
    "refuse here: bound here": whole_refusal(
        "bound", "bind the machine taking it first", argv=HERE_SCOPE + ["--delete"]),
    "refuse here: a session is listed": whole_refusal(
        "live", "1 session(s) of rc are listed", argv=HERE_SCOPE + ["--delete"],
        bound="unbound\n", live=live(sessions=[("rc-worker-2", "idle", OTHER)])),
    # the whole: repo
    "repo: unlisted, landing elsewhere, another repo's row and a session "
    "elsewhere let it sync and halt": case_repo_drops,
    "repo: --delete removes its clone and leaves the directory":
        case_repo_deletes_clone,
    "refuse repo: the README still lists it": repo_refusal(
        "repos", "still lists acme/member", readme=README_NEW),
    "refuse repo: the base is not a member repository": repo_refusal(
        "repos", "is not a member repository",
        argv=["repo", N, "kalaluthien/campaign-base"]),
    "refuse repo: bound elsewhere": repo_refusal(
        "bound", "reads `elsewhere", bound="elsewhere other-mac\n"),
    "refuse repo: an open sub-issue lands in it": repo_refusal(
        "settlement", "land in acme/member", settlement=settlement_all(
            [(f"{TRACKER}#{ISSUE}", "open")]),
        lands={ISSUE: (MEMBER, MEMBER, "lands in acme/member")}),
    "refuse repo: where an open sub-issue lands did not read": repo_refusal(
        "settlement", "did not read: no ## Lands in", settlement=settlement_all(
            [(f"{TRACKER}#{ISSUE}", "open")]),
        lands={ISSUE: (None, None, "no ## Lands in")}),
    "refuse repo: a claim is checked out in its clone": case_repo_claim_in_clone,
    "refuse repo: a session was started in its clone": case_repo_session_in_clone,
    "refuse repo: a counted local row is its": repo_refusal(
        "local-work", "1 item(s) exist only", local=local(
            rows=[(True, "rc/40-x", MEMBER)], verdict="counted")),
    "refuse repo: the folder is not a clone of it": repo_refusal(
        "delete", "is not a clone of acme/member",
        origin="acme/else"),
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
    ("each is asked", "for name, status, pane, _ in who:",
     "for name, status, pane, _ in []:",
     "refuse: a claim stands and sessions are listed, and each is asked"),
    ("landed blocks nothing", 'if i == issue and not rest.startswith("landed as")]',
     "if i == issue]", "drop: a landed claim of this sub-issue stands in nobody's way"),
    ("the issue matches exactly",
     'here = [(b, rest) for b, i, rest in reading["occupied"] if i == issue]',
     'here = [(b, rest) for b, i, rest in reading["occupied"] if issue in i]',
     "drop: another sub-issue's claim checked out here is its own business"),
    ("directory word", 'if not said.startswith("/"):', "if False:",
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
    ("bound word", 'if (word == "here") != want_here:', "if False:",
     "refuse campaign: bound elsewhere"),
    ("bound here refuses here", 'if (word == "here") != want_here:',
     'if word == "elsewhere":', "refuse here: bound here"),
    ("bound unread", 'if word not in ("here", "elsewhere", "unbound"):',
     "if False:", "refuse campaign: the binding did not read"),
    ("standing", 'if said == "not-standing":', "if True:",
     "refuse campaign: standing"),
    ("whole occupied", 'here = [(b, p) for b, _, p in reading["occupied"] if inside(p)]',
     'here = [(b, p) for b, _, p in reading["occupied"] if False]',
     "refuse campaign: a claim is checked out here"),
    ("whole vacant", 'if vacant_blocks and not m.startswith("landed as")]',
     "if False]", "refuse campaign: a claim checked out nowhere never merged"),
    ("whole landed", 'if vacant_blocks and not m.startswith("landed as")]',
     "if vacant_blocks]",
     "campaign: --close syncs, announces, releases every ref, closes, and "
     "halts for --delete"),
    ("here lets vacant pass", "gate_live_whole(n, slug, vacant_blocks=False)\n"
     "    gate_local_whole(n, directory)\n",
     "gate_live_whole(n, slug, vacant_blocks=True)\n"
     "    gate_local_whole(n, directory)\n",
     "here: bound elsewhere, a vacant claim does not block, and --delete lets "
     "it go"),
    ("whole sessions", '[f"{len(who)} session(s) of {slug} are listed"] * bool(who)',
     "[]", "refuse campaign: a session is listed, and asked"),
    ("repo narrows to its clone",
     "return under is None or Path(path).is_relative_to(under)", "return True",
     "repo: unlisted, landing elsewhere, another repo's row and a session "
     "elsewhere let it sync and halt"),
    ("repo clone sessions", "who = [s for s in reading[\"sessions\"] if inside(s[3])]",
     "who = [s for s in reading[\"sessions\"] if False]",
     "refuse repo: a session was started in its clone"),
    ("whole local rows", "if kept:", "if False:",
     "refuse campaign: a counted local row"),
    ("whole local gaps", "if gaps:", "if False:",
     "refuse campaign: local-work left places unread"),
    ("whole local done", "if not done:", "if False:",
     "refuse campaign: local-work did not finish"),
    ("repo local rows are its",
     "if not repo or REPOS.key(r) == REPOS.key(repo)]", "if True]",
     "repo: unlisted, landing elsewhere, another repo's row and a session "
     "elsewhere let it sync and halt"),
    ("installed", 'if not last.endswith("-- clear"):', "if False:",
     "refuse campaign: an install is behind"),
    ("closable", 'if not s["closable"]:', "if False:",
     "campaign: open rows halt, listed, for the person's disposition"),
    ("settlement finished", 'if not s["finished"]:', "if False:",
     "refuse campaign: settlement did not finish"),
    ("settlement unread rows", "if unread_rows:", "if False:",
     "refuse campaign: a row that did not read"),
    ("landing", "if REPOS.key(subject) == REPOS.key(repo):", "if False:",
     "refuse repo: an open sub-issue lands in it"),
    ("landing unread", 'if subject is None:\n            raise Refused("settlement"',
     'if False:\n            raise Refused("settlement"',
     "refuse repo: where an open sub-issue lands did not read"),
    ("unlisted", "if any(REPOS.key(r) == REPOS.key(repo) for r, _, _ in rows):",
     "if False:", "refuse repo: the README still lists it"),
    ("the base", "if repo is None or REPOS.is_base(repo):", "if repo is None:",
     "refuse repo: the base is not a member repository"),
    ("body moved", 'if now.rstrip("\\n") != derived.read_text().rstrip("\\n"):',
     "if False:", "refuse campaign: the body moved since the README was derived"),
    ("already synced", 'if now.rstrip("\\n") == text.rstrip("\\n"):',
     "if False:", "campaign: a body that already is the README is not written"),
    ("stored body", 'if after is None or rows != before or after.rstrip("\\n") != text.rstrip("\\n"):',
     "if False:", "refuse campaign: the body GitHub stored is not the README"),
    ("announce status", 'if r.returncode != 0:\n        raise Refused("announce"',
     'if False:\n        raise Refused("announce"',
     "refuse campaign: the announcement did not post"),
    ("release all", "if failed:", "if False:",
     "refuse campaign: a ref that would not release keeps the issue open"),
    ("campaign close status", "if r.returncode:", "if False:",
     "refuse campaign: the close did not happen"),
    ("lsof rows", "if open_rows:", "if False:",
     "refuse campaign: an open file under the directory"),
    ("lsof missing", "if r.returncode == 127:", "if False:",
     "refuse campaign: lsof that did not run"),
    ("campaign dir shape", '(path / ".campaign").is_file() and (path / "runtime").is_dir()):',
     "True):", "refuse campaign: a directory with no marker is not deleted"),
    ("clone origin", "if where is None or REPOS.key(where) != REPOS.key(repo):",
     "if False:", "refuse repo: the folder is not a clone of it"),
    ("close is asked", "if not args.close:", "if False:",
     "campaign: every gate held and no --close halts before any write"),
    ("delete is asked", 'if not args.delete:\n        raise Halt(f"#{n} is closed',
     'if False:\n        raise Halt(f"#{n} is closed',
     "campaign: --close syncs, announces, releases every ref, closes, and "
     "halts for --delete"),
    ("here delete is asked", 'if not args.delete:\n        raise Halt(f"deleting {directory}',
     'if False:\n        raise Halt(f"deleting {directory}', "here: without --delete it halts"),
    ("repo delete is asked", 'if not args.delete:\n        raise Halt(f"deleting {clone}',
     'if False:\n        raise Halt(f"deleting {clone}',
     "repo: unlisted, landing elsewhere, another repo's row and a session "
     "elsewhere let it sync and halt"),
    ("a checkout is one line", 'checkouts = [x for x in dirnames if (d / x / ".git").exists()]',
     "checkouts = []", "campaign: the delete's list names a checkout once and "
     "skips runtime and repos"),
    ("runtime and repos are skipped",
     "dirnames[:] = [x for x in dirnames if d / x not in skip]",
     "dirnames[:] = [x for x in dirnames]", "campaign: the delete's list names "
     "a checkout once and skips runtime and repos"),
    ("shape: directly under the base", "if path.parent != root or not (",
     "if not (", "refuse campaign: a marked directory not directly under the "
     "base is not deleted"),
    ("release printed neither", "if refusal or not done:", "if refusal:",
     "refuse: a release that printed neither word did not release"),
    ("not a campaign refuses", 'if s["not_campaign"]:', "if False:",
     "refuse campaign: the number has a parent of its own"),
    ("both reports are read", '"may be a sub-issue read as a campaign issue",',
     '"<never printed>",', "refuse campaign: the number carries no campaign label"),
    ("prune before live", 'r = run("git", "-C", str(root), "worktree", "prune")',
     'r = run("true")',
     "live: stale worktree entries are pruned under the base before live reads"),
    ("the base is passed", 'word_of(DIRECTORY_SCRIPT, n, str(base_root("directory")))',
     "word_of(DIRECTORY_SCRIPT, n)",
     "directory: campaign-directory is handed the base, not the cwd"),
    ("compact said by one release", "    print(COMPACT_NOTE)\n    why = release_refusal",
     "    why = release_refusal",
     "release: the compaction is said once, beside the first release"),
    ("compact said by the loop", "    print(COMPACT_NOTE)\n    failed = []",
     "    failed = []",
     "release: the compaction is said once, beside the first release"),
    ("release reads live again", "step_release_all(n, read_live(n, slug),",
     "step_release_all(n, reading,",
     "campaign: the release reads live again after the writes"),
    ("front: campaign kind", 'if kind == "campaign issue":', "if False:",
     "front: a campaign issue number reads as scope campaign"),
    ("front: sub-issue kind", 'elif kind == "sub-issue":', "elif False:",
     "front: a sub-issue number reads as scope sub-issue of its parent"),
    ("front: of its parent", '["sub-issue", parent.lstrip("#"), n]',
     '["sub-issue", n, n]',
     "front: a sub-issue number reads as scope sub-issue of its parent"),
    ("front: a slash is a repository", 'elif "/" in t:', "elif False:",
     "front: owner/repo reads as scope repo of the directory's campaign"),
    ("front: one session by that name", "if len(panes) != 1:", "if not panes:",
     "refuse front: a name two sessions carry"),
    ("front: the slug names a campaign", "if not n.isdigit():", "if False:",
     "refuse front: a session whose slug names no campaign"),
    ("front: the marker first", "if fields:\n        return fields[0]",
     "if False:\n        return fields[0]",
     "front: no target in a campaign directory reads as scope here by its marker"),
    ("front: the session's name second",
     'if slug is None:\n        raise Refused("target", f"no campaign directory',
     'if False:\n        raise Refused("target", f"no campaign directory',
     "refuse front: no target, no campaign directory, no campaign name"),
    ("front: a session of no campaign",
     'if slug is None:\n            raise Refused("target", f"session {t} carries',
     'if False:\n            raise Refused("target", f"session {t} carries',
     "refuse front: a session whose name carries no campaign"),
    ("front: a scope's name alone reaches the front door",
     "or (\n            argv[0] in SCOPES and len(argv) == 1)", "or (False)",
     "refuse front: a scope's name alone is not a target"),
    ("front: a scope's name alone refuses", "    if t in SCOPES:\n", "    if False:\n",
     "refuse front: a scope's name alone is not a target"),
    ("front: the number is the whole target", 'NUMBER = re.compile(r"^#?(\\d+)$")',
     'NUMBER = re.compile(r"^#?(\\d+)")',
     "refuse front: digits with more after them are not a number"),
    ("front: the target is stripped", 't = (args.target or "").strip() or None',
     "t = args.target", "front: a padded number is read as the number"),
    ("front: check answers for that number", "if m.group(1) != n:", "if False:",
     "refuse front: check answering for another number"),
    ("front: an unread flag refuses", "if extra:", "if False:",
     "refuse front: a flag the scope does not take"),
    ("closed skips the writes", 'if state == "CLOSED":', "if False:",
     "campaign: a CLOSED issue skips the writes, releases, and deletes"),
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
    for root in TMP:
        shutil.rmtree(root, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
