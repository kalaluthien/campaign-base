#!/usr/bin/env python3
"""Set a session's two names, both paths, from one call.

    scripts/campaign-name-session.py <pane> <name> [<pane> <name> ...]

A session has two names and neither propagates to the other: the herdr pane
name that `herdr agent list` shows, and the harness name that `ListAgents`
resolves and a peer addresses. Renaming one leaves the session answering to two
different names depending on who is asking, so this sets both and reports each.

It is also the naming rule's owner. `AGENTS.md` § The session name states
`campaign-<campaign issue>-<role>-<n>`; a name that does not match is refused here
rather than half-applied, because a rule nothing must consume is a rule that
drifts. `NAME` below is the one pattern: scripts/campaign-claim.py loads this
file by path and reads it there, so `take` can refuse a name from another
campaign without a second spelling of the shape.

scripts/check-rule-readers.py is the second reader that keeps this claim true: it
refuses a commit that stages either of the two herdr rename calls as code in
any tracked markdown outside scripts/ -- inside a fence or a four-space indent,
reading the index rather than the working tree. It catches a pasted copy, not a
re-implementation that names nothing; see its header. Removing the guard
returns this line to being a hope.

    exit 0   every pair applied, both paths
    exit 1   nothing applied -- a name failed the rule, a pane is named twice,
             or the arguments are odd
    exit 2   a herdr call failed partway, or a pane was blocked and got no
             prompt; what was applied is printed

The harness half is `herdr agent prompt <pane> "/rename <name>"`, which is
another session driving that pane -- the same act as a person typing it, and it
works on the caller's own pane too. Whether a given call is PERMITTED is a
per-session permission decision rather than a property of the tool, and it is
not stable: the same call can be refused and then accepted minutes apart. So
this reports what was applied and what was not rather than assuming either,
and the caller's own rename is the one most likely to need a person.

A prompt sent to a WORKING pane is QUEUED, and the harness merges every prompt
queued before the turn ends into one input line: three `/rename` prompts sent
to one working pane landed as the single name
`campaign-1-worker-3/rename campaign-1-planner-1/rename campaign-1-worker-3`
(2026-09-04, #169). A session naming itself is always mid-turn, so refusing a
working pane would refuse the ordinary case. Instead this sends at most one
prompt per pane per call -- a pane named twice is refused before anything is
applied -- and reads the pane's `agent_status` from `herdr agent list` before
sending. `idle` and `done` (herdr's own help calls `done` the same underlying
idle state) are reported as `sent`; `working` and any other status as `queued`,
so the caller knows not to send that pane anything else until `ListAgents`
shows the name; a status this could not read is said as such, and the prompt
is still sent. A BLOCKED pane -- one sitting at a dialog -- gets no prompt at
all: herdr would reject it with `agent_blocked` before any input is sent, and
the dialog is a person's to clear, so this reports the herdr name as applied
and the harness half as not sent, exit 2.
"""
import json
import re
import subprocess
import sys

# One shape, no branches. The sub-issue is deliberately absent: a session works
# several sub-issues, in parallel or one after another, and a name that tracked
# the work in hand would go false at every handover. <n> distinguishes sessions
# sharing a campaign.
# Two roles: a planner files the sub-issues and distributes them, a worker
# works one. A review has no session to name -- it runs as a subagent of the
# session that wants the merge. How <n> is counted across the two roles is
# AGENTS.md § The session name's rule, stated there and nowhere else.
NAME = re.compile(r"^campaign-([0-9]+)-(?:planner|worker)-[0-9]+$")   # group 1: the campaign issue


def refuse(why):
    print(f"campaign-name-session: {why}", file=sys.stderr)
    raise SystemExit(1)


def herdr(*args):
    """One herdr call. Returns the parsed result, or None with the error printed."""
    out = subprocess.run(["herdr", *args], capture_output=True, text=True)
    if out.returncode != 0:
        return None, (out.stderr.strip() or out.stdout.strip() or "no message")
    try:
        return json.loads(out.stdout), None
    except json.JSONDecodeError:
        # prompt returns json too, but do not fail the rename over a shape change
        return {}, None


def pane_status(pane):
    """(agent_status, None) from `herdr agent list`, or (None, why) when the
    list could not be read or does not hold the pane."""
    res, err = herdr("agent", "list")
    if err:
        return None, f"herdr agent list failed: {err}"
    agents = ((res or {}).get("result") or {}).get("agents") or []
    for agent in agents:
        if agent.get("pane_id") == pane:
            return agent.get("agent_status") or "unknown", None
    return None, f"{pane} is not in herdr agent list"


def main():
    args = sys.argv[1:]
    if not args or len(args) % 2:
        refuse("usage: campaign-name-session.py <pane> <name> [<pane> <name> ...]")

    pairs = list(zip(args[::2], args[1::2]))

    # Validate every name before applying any, so a typo in the last pair does
    # not leave the first session renamed on one path and not the other.
    for pane, name in pairs:
        if not NAME.match(name):
            refuse(f"{name!r} is not campaign-<campaign issue>-<role>-<n> "
                   "(role: planner or worker); nothing was applied")
    # One prompt per pane per call: two queued at a working pane merge into
    # one name, and only the last name asked for could have been meant.
    panes = [pane for pane, _ in pairs]
    for pane in panes:
        if panes.count(pane) > 1:
            refuse(f"{pane} is named more than once; two /rename prompts "
                   "queued at one pane merge into a single name. Name it "
                   "once; nothing was applied")

    failed = False
    for pane, name in pairs:
        res, err = herdr("agent", "rename", pane, name)
        if err:
            print(f"  {pane}  herdr name  FAILED: {err}")
            failed = True
            continue
        got = (res.get("result", {}).get("agent", {}) or {}).get("name")
        print(f"  {pane}  herdr name  {got or name}")

        # Read the status before sending, so the report describes the pane the
        # prompt met. A working pane is prompted all the same, because a
        # session naming itself is always working; a blocked one is not.
        status, why = pane_status(pane)
        if status == "blocked":
            print(f"  {pane}  harness     /rename NOT sent: the pane is blocked "
                  f"at a dialog, which herdr would refuse with agent_blocked. "
                  f"Clear the dialog and re-run for this pane")
            failed = True
            continue
        res, err = herdr("agent", "prompt", pane, f"/rename {name}")
        if err:
            print(f"  {pane}  harness     FAILED: {err}")
            failed = True
            continue
        # The prompt is never applied here: the session runs /rename on its
        # next turn. Report it as sent or queued rather than as done, because
        # the only honest confirmation is ListAgents afterwards.
        if status in ("idle", "done"):
            print(f"  {pane}  harness     /rename sent (confirm with ListAgents)")
        elif status is None:
            print(f"  {pane}  harness     /rename sent; the pane's status could "
                  f"not be read ({why}), so whether it queued is unknown "
                  f"(confirm with ListAgents)")
        else:
            print(f"  {pane}  harness     /rename queued: the pane is {status}, "
                  f"so it applies when this turn ends, and any other prompt "
                  f"queued before then merges into the name (confirm with "
                  f"ListAgents)")

    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
