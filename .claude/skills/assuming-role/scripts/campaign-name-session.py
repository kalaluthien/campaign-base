#!/usr/bin/env python3
"""Set a session's two names, both paths, from one call.

    scripts/campaign-name-session.py <pane> <name> [<pane> <name> ...]

A session has two names and neither propagates to the other: the herdr pane
name that `herdr agent list` shows, and the harness name that `ListAgents`
resolves and a peer addresses. Renaming one leaves the session answering to two
different names depending on who is asking, so this sets both and reports each.

It is also the naming rule's owner. `AGENTS.md` § The session name states
`<slug>-<role>-<n>`; a name that does not match is refused here rather than
half-applied, because a rule nothing must consume is a rule that drifts.
`NAME`, `SLUG` and `campaign_of` below are the one spelling: scripts/campaign-claim.py
and scripts/check-campaign-claim.py load this file by path and read them there,
so neither restates the shape.

THE SLUG RULE LIVES IN THIS LEAF and not in campaign-tracker.py, which owns the
`campaign:<slug>` label the slug is stored on. check-campaign-claim.py is a
PreToolUse hook that reads the name on every tool call and reaches the rule by
exec'ing this file; reaching it through the tracker instead would exec forty
kilobytes of `gh` plumbing on that path. The tracker imports the rule from here.

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
`campaign-1-executor-3/rename campaign-1-planner-1/rename campaign-1-executor-3`
(2026-09-04, #169 -- `executor` was the role word that day, and a dated
observation is quoted as it was observed). A session naming itself is always
mid-turn, so refusing a working pane would refuse the ordinary case. Instead
this sends at most one prompt per pane per call -- a pane named twice is
refused before anything is applied -- and reads the pane's `agent_status` from
`herdr agent list` before sending. `idle` and `done` (herdr's own help calls
`done` the same underlying idle state) are waited on and reported as `applied`
once the pane prints the CLI's `Session renamed to: <name>`, and as `sent, not
applied yet` when the budget runs out; `working` and any other status as
`queued`, so the caller knows not to send that pane
anything else until `ListAgents` shows the name; a status this could not read
is said as such, and the prompt is still sent. A BLOCKED pane -- one sitting
at a dialog -- gets no prompt at all: herdr would reject it with
`agent_blocked` before any input is sent, and the dialog is a person's to
clear, so this reports the herdr name as applied and the harness half as not
sent, exit 2.
"""
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path as _Path


def _roles_module():
    """`campaign-roles.py`, this skill's sibling, which owns the role words.

    Read rather than restated (#227): the words appear in NAME's alternation
    here and in the licence table there, and a second tuple would let a role
    exist in one and not the other -- a name the guard admits and has no row
    for, or a row no name can reach. The sibling is a dict literal with no
    imports of its own, so this leaf stays cheap to exec, which is the property
    its header is about."""
    src = _Path(__file__).resolve().parent / "campaign-roles.py"
    spec = importlib.util.spec_from_loader(
        "croles", importlib.machinery.SourceFileLoader("croles", str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ROLES = _roles_module().ROLE_WORDS

# The slug: a campaign's name, carried on GitHub by its `campaign:<slug>` label
# and read by people everywhere else. Three conditions, each with a reason:
#
#   * kebab-case starting with a letter, so it is one path segment, one ref
#     segment and one herdr name without quoting or escaping anywhere;
#   * at most SLUG_CEILING characters, so a person picks one campaign out of
#     `ls` at the base root and out of `herdr agent list` at a glance. The
#     owner set 10 on 2026-09-10, and it is the binding bound: herdr's
#     32-character limit on a session name is the other one, and the longest
#     name this file EXPECTS, `<slug>-worker-99`, is now 20 and clears it by
#     twelve -- expects and not admits, because NAME bounds no digit run. Slugs already spent over 10 belong to closed campaigns and are
#     not re-checked;
#   * no segment in RESERVED, for three reasons in one list. `planner` and
#     `worker` are barred so that `<slug>-<role>-<n>` has exactly one reading:
#     with the role words absent from the slug, a name holds one `-planner-` or
#     `-worker-` and NAME's group 1 cannot be anything but the slug. `campaign`
#     is barred so that the retired `campaign-<N>` form cannot come back as a
#     slug: `campaign-1` satisfies SLUG, and admitting it would re-open the
#     two-form window #237 closed, this time with nothing marking it as old.
#     And the last
#     three are the base's own directories at its root, which is where a
#     campaign's directory is created: a campaign slugged `runtime`
#     would name a directory the base already owns, and `scripts/guard-corpus.py`
#     -- which classifies a RECORDED path it cannot stat -- would read that
#     campaign's whole tree as the base's own.
SLUG_CEILING = 10
# The base's own directories at its root. Named here because a slug becomes a
# directory there, and imported by scripts/guard-corpus.py, which excludes the
# same words when it classifies a recorded path it cannot stat -- one set, one
# owner, rather than two copies pointing at each other in prose.
BASE_DIRS = ("scripts", "spec", "runtime")
# `none` IS EVERY WORD-ANSWERING SCRIPT'S "NOTHING HERE", and a slug is read
# back through several of them -- `campaign-tracker.py slug`, and the skills'
# `case "$SLUG" in ""|none)` arms that read it. A campaign slugged `none` would
# be one no directory could be scaffolded for and no close could resolve, with
# every reader telling it the slug did not read. Barred here, once, rather than
# separated by a character class in each caller.
RESERVED = ("campaign", "planner", "worker", "none") + BASE_DIRS
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

# THE RETIRED `campaign-<N>` TOKEN IS GONE (#237). It named branches and
# sessions before #181; it was read beside the slug for one window, which
# closed when the last such pull request merged and no `campaign-1/` ref was
# left. What keeps it from returning is not a regex but `RESERVED`: `campaign`
# is a barred segment, so `campaign-1` is not a slug and no name or branch can
# be minted or read as one.

# One shape, no branches. The sub-issue is deliberately absent: a session works
# several sub-issues, in parallel or one after another, and a name that tracked
# the work in hand would go false at every handover. <n> distinguishes sessions
# sharing a campaign. How <n> is counted across the two roles is AGENTS.md
# § The session name's rule, stated there and nowhere else.
#
# SHAPE ONLY. Whether group 1 is a campaign token this file admits is
# `campaign_of`'s question, because the slug's three conditions are not all
# regular and a regex spelling them would be the copy that drifts from
# `slug_ok`. Every reader calls `campaign_of`; NAME alone admits more.
NAME = re.compile(r"^(.+)-(?:" + "|".join(ROLES) + r")-[0-9]+$")   # group 1: the campaign token


def slug_ok(text):
    """Whether `text` is a slug. A calculation with no network and no state, so
    every condition above is a case."""
    return (bool(SLUG.match(text))
            and len(text) <= SLUG_CEILING
            and not any(seg in RESERVED for seg in text.split("-")))


def campaign_of(name):
    """The campaign token a session name says it is of, or None.

    None covers all three ways a name says nothing: it is not of the shape at
    all, or its role word is missing, or its leading part is not a slug. A
    reader that wants to know WHICH campaign compares this against another
    name's, and the comparison is string equality."""
    m = NAME.match(name or "")
    if not m:
        return None
    token = m.group(1)
    return token if slug_ok(token) else None


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


# THE ECHO IS THE ONLY CONFIRMATION A SCRIPT CAN GET. The harness name is in no
# file on disk and `ListAgents` is a tool rather than a command, so nothing
# outside a session can read that name back. What IS readable is the CLI's own
# line, `Session renamed to: <name>`, printed when the session runs the
# `/rename` -- the literal is in the shipped binary
# (`grep -ao "Session renamed to" "$(which claude)"`, probed 2026-09-10).
#
# WHY IT IS WORTH WAITING FOR: `herdr agent prompt` returns as soon as the
# prompt is delivered, and the session applies it on its next turn. A caller
# that read "sent" and prompted the pane immediately had both land on one input
# line and the name became the rename plus the brief -- `sdlc-alloy-planner-7`
# carried one on 2026-09-10 (#285). So the caller needs a word that separates
# delivered from applied, and this is the reading that gives it one.
#
# A REFUSED READ IS A NOT-YET, NOT A NO. `herdr agent read` refuses a pane that
# is `working`, which is exactly what a pane is for the moment it spends
# applying the rename, so the loop retries rather than concluding. It returns
# text and not JSON, so it does not go through `herdr()`.
ECHO_TRIES = 8
ECHO_SLEEP = 0.5


def rename_echoed(pane, name):
    """(True, None) once the pane has printed `Session renamed to: <name>`,
    or (False, why) when the budget ran out -- `why` naming the last thing the
    read said, so an unconfirmed rename and an unreadable pane are two
    different reports."""
    want = f"Session renamed to: {name}"
    why = "the pane never printed it"
    for attempt in range(ECHO_TRIES):
        if attempt:
            time.sleep(ECHO_SLEEP)
        out = subprocess.run(["herdr", "agent", "read", pane],
                             capture_output=True, text=True)
        if out.returncode != 0:
            why = (out.stderr.strip() or out.stdout.strip()
                   or "herdr agent read failed with no message")
            continue
        if want in out.stdout:
            return True, None
        why = "the pane never printed it"
    return False, why


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
        if campaign_of(name) is None:
            refuse(f"{name!r} is not <slug>-<role>-<n> (role: "
                   f"{' or '.join(ROLES)}; slug: kebab-case, at most "
                   f"{SLUG_CEILING} characters, no segment "
                   f"{' or '.join(RESERVED)}); nothing was applied")
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
            echoed, why = rename_echoed(pane, name)
            if echoed:
                print(f"  {pane}  harness     /rename applied: the pane printed "
                      f"`Session renamed to: {name}`")
            else:
                print(f"  {pane}  harness     /rename sent, not applied yet "
                      f"after {ECHO_TRIES * ECHO_SLEEP:g}s ({why}); do not "
                      f"prompt this pane until ListAgents shows the name, or "
                      f"the two inputs merge into one")
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
