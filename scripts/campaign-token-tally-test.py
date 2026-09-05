#!/usr/bin/env python3
"""Prove the tally counts each API message once and attributes it by place, not by prose.

Every case runs against a synthetic transcript tree written into a temporary
directory: no case reads this machine's real `~/.claude/projects`, and none
reaches the network -- the pull-request map is handed in as a file and `gh` is
never called.

The cases are one per branch of the method, because a tally is the shape of
program that returns a plausible number however wrong it is. Deleting the
folding branch, the off-base filter, the timestamp filter, the worktree rule,
the branch rule, the brief rule or the parent rule each makes exactly one named
case fail.

Usage: scripts/campaign-token-tally-test.py
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "campaign-token-tally.py"
RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{('  -- ' + detail) if detail else ''}")


def usage(out, new=100, read=50, settled=True):
    u = {"input_tokens": new, "cache_creation_input_tokens": 0,
         "cache_read_input_tokens": read, "output_tokens": out}
    if settled:
        u["iterations"] = [{"output_tokens": out}]
    return u


def assistant(mid, ts, cwd, branch="main", session="s1", out=100, blocks=None,
              new=100, read=50, settled=True, model="claude-opus-5", agent=None):
    return {"type": "assistant", "timestamp": ts, "cwd": cwd, "gitBranch": branch,
            "sessionId": session, "uuid": mid + "-" + str(out), "agentId": agent,
            "isSidechain": bool(agent),
            "message": {"id": mid, "role": "assistant", "model": model,
                        "content": blocks or [{"type": "text", "text": "x"}],
                        "usage": usage(out, new, read, settled)}}


def user(ts, cwd, text, session="s1", branch="main", agent=None):
    return {"type": "user", "timestamp": ts, "cwd": cwd, "gitBranch": branch,
            "sessionId": session, "uuid": "u" + ts, "agentId": agent,
            "isSidechain": bool(agent),
            "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def write(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")


def run(root, base, command, pr_map, extra=()):
    out = subprocess.run(
        [sys.executable, str(SCRIPT), command, "--root", str(root),
         "--base", str(base), "--pr-map", str(pr_map),
         "--since", "2026-01-02T00:00:00Z", "--until", "2026-01-03T00:00:00Z",
         *extra],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"{command} failed: {out.stderr}")
    return out.stdout


def row(text, first):
    """The row whose first column is `first`, keyed by the table's own headings.

    By heading and not by index, so adding a column to a table does not fail
    every case that reads one -- the cases here are about what a number says,
    and a column's position is not part of that.
    """
    head = None
    for line in text.splitlines():
        cells = line.split()
        if not cells:
            continue
        if head is None:
            if cells[0] in ("issue", "session", "pr", "script"):
                head = cells
            continue
        if cells[0] == first:
            return dict(zip(head, cells))
    return None


def build(tmp):
    """One synthetic corpus, holding one shape per branch of the method."""
    base = tmp / "campaign-base"
    (base / "camp-260101" / "worktrees" / "300").mkdir(parents=True)
    root = tmp / "projects"
    day = "2026-01-02T"

    # A worktree turn, and the message written as three records: two placeholder
    # records and the settled one, all repeating the same input and cache.
    wt = str(base / "camp-260101" / "worktrees" / "300")
    folded = [
        assistant("m-fold", day + "01:00:00Z", wt, out=2, settled=False,
                  blocks=[{"type": "thinking", "thinking": "t"}]),
        assistant("m-fold", day + "01:00:01Z", wt, out=2, settled=False,
                  blocks=[{"type": "text", "text": "y"}]),
        assistant("m-fold", day + "01:00:02Z", wt, out=500, settled=True,
                  blocks=[{"type": "tool_use", "name": "Bash", "id": "t1",
                           "input": {"command":
                                     "scripts/campaign-tracker.py index 1 && "
                                     "scripts/campaign-repos.py README.md"}}]),
    ]
    # Two commands that name a script without running one: the result they
    # return is the script's own source, and charging it to the script would
    # make reading a file look like an agent being printed at.
    look = str(base / "camp-260101" / "worktrees" / "307")
    # A heredoc whose body opens with a script name, and a `for` loop running a
    # script through an interpreter: the two shapes a line-splitting reader gets
    # backwards in opposite directions -- it counts the heredoc line as a
    # command and misses the loop body, because `do` stands in front of one.
    heredoc = ('python3 - <<"PY"\n'
               'campaign-claim.py is only a string here\n'
               'print(1)\n'
               'PY')
    loop = ("for f in one two; do python3 scripts/check-tree-shape.py $f; done")
    reads = [
        assistant("m-grep", day + "01:10:00Z", look, out=10, settled=True,
                  blocks=[{"type": "tool_use", "name": "Bash", "id": "t2",
                           "input": {"command":
                                     "grep -n live scripts/campaign-claim.py"}}]),
        assistant("m-sed", day + "01:20:00Z", look, out=10, settled=True,
                  blocks=[{"type": "tool_use", "name": "Bash", "id": "t3",
                           "input": {"command":
                                     "sed -n 1,40p scripts/campaign-primitives.py"}}]),
        assistant("m-heredoc", day + "01:30:00Z", look, out=10, settled=True,
                  blocks=[{"type": "tool_use", "name": "Bash", "id": "t4",
                           "input": {"command": heredoc}}]),
        assistant("m-loop", day + "01:40:00Z", look, out=10, settled=True,
                  blocks=[{"type": "tool_use", "name": "Bash", "id": "t5",
                           "input": {"command": loop}}]),
        # The invocation path in quotes, which a reader testing the raw word
        # misses however well it handles paths.
        assistant("m-quoted", day + "01:50:00Z", look, out=10, settled=True,
                  blocks=[{"type": "tool_use", "name": "Bash", "id": "t6",
                           "input": {"command":
                                     'W=/tmp/w; "$W/scripts/campaign-repos.py" '
                                     'README.md'}}]),
        # A shell's -c string with no operands after the script: the guard
        # re-reads that string as segments, so counting bash's file operand too
        # would count the one invocation twice.
        assistant("m-dashc", day + "01:55:00Z", look, out=10, settled=True,
                  blocks=[{"type": "tool_use", "name": "Bash", "id": "t7",
                           "input": {"command":
                                     'bash -c "scripts/campaign-tracker.py"'}}]),
    ]
    # A worktree whose directory was deleted when its sub-issue closed.
    dead = str(base / "camp-260101" / "worktrees" / "302")
    # A turn on a claim branch at the base root, and one that is only prose.
    prose = ("the branch is campaign-1/306-topic and issue 305 and "
             "kalaluthien/campaign-base#305 -- none of this is a place")
    write(root / "proj" / "s1.jsonl", [
        {"type": "agent-name", "sessionId": "s1", "agentName": "campaign-1-worker-9"},
        *folded,
        {"type": "user", "timestamp": day + "01:00:03Z", "cwd": wt,
         "gitBranch": "main", "sessionId": "s1", "uuid": "r1",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "t1",
              "content": [{"type": "text", "text": "R" * 400}]}]}},
        *reads,
        {"type": "user", "timestamp": day + "01:50:03Z", "cwd": look,
         "gitBranch": "main", "sessionId": "s1", "uuid": "r2",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "t2",
              "content": [{"type": "text", "text": "S" * 9000}]},
             {"type": "tool_result", "tool_use_id": "t3",
              "content": [{"type": "text", "text": "S" * 9000}]},
             {"type": "tool_result", "tool_use_id": "t4",
              "content": [{"type": "text", "text": "H" * 5000}]},
             {"type": "tool_result", "tool_use_id": "t5",
              "content": [{"type": "text", "text": "L" * 700}]},
             {"type": "tool_result", "tool_use_id": "t6",
              "content": [{"type": "text", "text": "Q" * 800}]},
             {"type": "tool_result", "tool_use_id": "t7",
              "content": [{"type": "text", "text": "C" * 600}]}]}},
        assistant("m-branch", day + "02:00:00Z", str(base),
                  branch="campaign-1/301-topic", out=70),
        assistant("m-dead", day + "02:10:00Z", dead, out=60),
        assistant("m-prose", day + "02:20:00Z", str(base), out=40,
                  blocks=[{"type": "text", "text": prose}]),
        # Inside the window by a fraction of a second: the harness writes
        # milliseconds, so a bound carrying its Z sorts after this message and
        # would drop a second of turns at each end.
        assistant("m-edge", "2026-01-02T00:00:00.500Z",
                  str(base / "camp-260101" / "worktrees" / "308"), out=7),
        # Outside the window by its own timestamp, in a file written just now.
        assistant("m-old", "2026-01-01T00:00:00Z", wt, out=999),
        # Outside every base root: a workspace this campaign does not own.
        assistant("m-elsewhere", day + "02:30:00Z", str(tmp / "elsewhere"), out=888),
    ])
    # A subagent named by its own brief, and one that has none.
    write(root / "proj" / "s1" / "subagents" / "agent-a1.jsonl", [
        # Launched from the worktree of *another* sub-issue, which is what a
        # review of one pull request started from a session working a second
        # one records on every record it writes.
        user(day + "03:00:00Z", wt, "/code-review high 400\n\nreview it",
             session="s1", agent="a1"),
        assistant("m-review", day + "03:01:00Z", wt, out=30, session="s1",
                  model="claude-fable-5-1", agent="a1"),
    ])
    write(root / "proj" / "s1" / "subagents" / "agent-a2.jsonl", [
        user(day + "02:05:00Z", str(base), "find every reader of the guard",
             session="s1", agent="a2"),
        # Unsettled, as a subagent's turns nearly always are: no record of the
        # message carries usage.iterations, so its output is a floor.
        assistant("m-child", day + "02:06:00Z", str(base), out=20, session="s1",
                  agent="a2", settled=False),
    ])
    # A brief naming the pull request the long way. Issues and pull requests
    # share one number sequence, so #400 here is PR 400 and not issue 400.
    write(root / "proj" / "s1" / "subagents" / "agent-a3.jsonl", [
        user(day + "03:30:00Z", str(base),
             "verify the fix on kalaluthien/campaign-base#400",
             session="s1", agent="a3"),
        assistant("m-verify", day + "03:31:00Z", str(base), out=25, session="s1",
                  agent="a3"),
    ])
    pr_map = tmp / "prs.json"
    pr_map.write_text(json.dumps([{"number": 400, "headRefName": "campaign-1/303-x"}]))
    return root, base, pr_map


def main():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d).resolve()   # the transcript records a real path, so must we
        root, base, pr_map = build(tmp)
        issues = run(root, base, "issues", pr_map)
        sessions = run(root, base, "sessions", pr_map)
        reviews = run(root, base, "reviews", pr_map)
        echo = run(root, base, "tool-echo", pr_map)

        # ONE MESSAGE IS ONE TURN. Three records, one turn, and the settled
        # record's output -- not the placeholder's 2, and not the sum of three
        # input counts.
        r300 = row(issues, "300")
        check("a message written as three records is one turn",
              r300 and r300["turns"] == "1", str(r300))
        check("...its output is the settled record's, not the placeholder's",
              r300 and r300["output"] == "500", str(r300))
        check("...and its input is counted once, not once per record",
              r300 and r300["input_new"] == "100" and r300["cache_read"] == "50",
              str(r300))

        # PLACE, IN ORDER. Worktree, then branch, then the brief of a subagent.
        check("a cwd under worktrees/<issue> names the issue", r300 is not None)
        r301 = row(issues, "301")
        check("a campaign branch names the issue when the cwd does not",
              r301 and r301["output"] == "90", str(r301))
        r303 = row(issues, "303")
        # Two subagents name PR 400 -- one by the review command, one in prose --
        # and both land on the sub-issue that pull request is for.
        check("a review subagent is attributed by the pull request in its brief",
              r303 and r303["attributed_by"] == "brief" and r303["output"] == "55",
              str(r303))
        check("...even though it ran in another sub-issue's worktree",
              r300 and r300["turns"] == "1", str(r300))
        check("a pull request named the long way is not read as an issue",
              row(issues, "400") is None, issues)
        check("...and both count as subagent turns, apart from their parent",
              r303 and r303["sub_turns"] == "2" and r303["turns"] == "2", str(r303))

        # A DELETED WORKTREE IS STILL THIS CAMPAIGN'S WORK. The filter is
        # containment in the base root, never whether the path still resolves.
        r302 = row(issues, "302")
        check("a worktree that no longer exists still attributes its turns",
              r302 and r302["output"] == "60", str(r302))

        # WHAT IS NOT READ. A bare number, an issue reference and a branch name
        # in prose all leave the turn unattributed.
        unattr = row(issues, "unattributed")
        check("prose naming a branch or an issue attributes nothing",
              unattr and unattr["output"] == "40", str(unattr))
        check("...and issue 305 and 306 have no row at all",
              row(issues, "305") is None and row(issues, "306") is None)

        # THE WINDOW IS THE MESSAGE'S OWN TIMESTAMP. The file was written now;
        # the turn inside it is from yesterday.
        check("a turn older than the window is dropped though its file is new",
              "999" not in issues and "1 outside the window" in issues, issues[:400])
        check("a cwd outside every base root is dropped and counted",
              "888" not in issues and "1 with a cwd outside" in issues, issues[:400])
        check("a turn in the boundary second itself is kept",
              row(issues, "308") and row(issues, "308")["output"] == "7",
              str(row(issues, "308")))

        # A FOLD IS NOT A DROP. Two records of m-fold were folded into the turn
        # they belong to, and no message was met twice in two files.
        check("folded records are counted as folded, not as dropped duplicates",
              "records folded into one of them 2" in issues, issues[:400])
        check("...and the message-seen-elsewhere counter is its own, and zero",
              "messages already counted in another file 0" in issues, issues[:400])

        # THE FLOOR IS NAMED, AND PER ROW. One subagent turn never settled, so
        # its row is a floor, and the row says so where the number is read.
        check("a row holding an unsettled turn says so in its own settled column",
              r301 and r301["settled"] == "1/2", str(r301))
        check("sub_output carries its own settled count, not the row's",
              r303 and r301 and r303["sub_settled"] == "2/2"
              and r301["sub_settled"] == "0/1", str(r301) + str(r303))
        check("...while a row of settled turns says that",
              r300 and r303 and r300["settled"] == "1/1"
              and r303["settled"] == "2/2", str(r300) + str(r303))
        check("the floor line splits session turns from subagent turns",
              "session: 0 of" in issues and "subagent: 1 of" in issues,
              issues[:900])

        # A SUBAGENT WITH NO BRIEF FALLS BACK TO ITS PARENT'S ISSUE.
        check("a subagent with no issue in its brief takes its parent's",
              r301 and r301["sub_turns"] == "1", str(r301))

        # SESSIONS NAME THE SUBAGENT BY ITS PARENT, which is the only place the
        # name is written.
        check("a subagent's row names the session that started it",
              "(subagent of campaign-1-worker-9)" in sessions, sessions)

        # REVIEWS READ THE LEVEL AND THE PULL REQUEST FROM THE BRIEF.
        check("a review round is one row, with its pull request and level",
              row(reviews, "400") and row(reviews, "400")["level"] == "high",
              reviews)

        # TOOL-ECHO COUNTS A CALL, NOT A MENTION, AND PARTITIONS THE BYTES.
        # The fixture runs campaign-tracker and campaign-repos in one command,
        # greps campaign-claim in another, and reads campaign-primitives with
        # sed in a third.
        tracker = row(echo, "campaign-tracker")
        check("a script a command runs is charged the result it returned",
              tracker and tracker["result_bytes"] == "1,000", str(tracker))
        repos = row(echo, "campaign-repos")
        check("a second script in the same command is counted, not charged twice",
              repos and repos["also_run"] == "1"
              and repos["result_bytes"] == "800", str(repos))
        check("grepping a script is not calling it",
              row(echo, "campaign-claim") is None, echo)
        check("...and neither is reading it with sed",
              row(echo, "campaign-primitives") is None, echo)
        check("a script name inside a heredoc body is not a call",
              row(echo, "campaign-claim") is None, echo)
        shape = row(echo, "check-tree-shape")
        check("a script run through an interpreter inside a loop is a call",
              shape and shape["charged"] == "1"
              and shape["result_bytes"] == "700", str(shape))
        check("a quoted invocation path is a call",
              repos and repos["charged"] == "1", str(repos))
        # tracker is run twice in the corpus: once by the `&&` command, once
        # inside a shell's -c string. Two charged commands, and no third
        # invocation from reading bash's operand as well as the string.
        check("a shell's -c string is read once, not once per reader",
              tracker and tracker["charged"] == "2" and tracker["also_run"] == "0",
              str(tracker))

        # A WINDOW BOUND THAT CANNOT BE COMPARED IS REFUSED, not quietly used.
        bad = subprocess.run(
            [sys.executable, str(SCRIPT), "issues", "--root", str(root),
             "--base", str(base), "--pr-map", str(pr_map), "--offline",
             "--since", "2026-01-02T00:00:00+09:00"],
            capture_output=True, text=True)
        check("a window bound in another offset is refused",
              bad.returncode == 2 and "not UTC" in bad.stderr, bad.stderr)
        worse = subprocess.run(
            [sys.executable, str(SCRIPT), "issues", "--root", str(root),
             "--base", str(base), "--pr-map", str(pr_map), "--offline",
             "--since", "yesterday"],
            capture_output=True, text=True)
        check("...and one that is not a timestamp at all is refused",
              worse.returncode == 2 and "not an ISO timestamp" in worse.stderr,
              worse.stderr)

    for name in FAILED:
        print(f"FAIL  {name}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
