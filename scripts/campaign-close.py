#!/usr/bin/env python3
"""Close one piece of a campaign -- a sub-issue or a worker -- behind the gates every close shares.

    scripts/campaign-close.py sub-issue <N> <issue> --not-planned "<why>"
    scripts/campaign-close.py worker <N> <pane>

Every smaller close used to restate the same gates in prose: drop a sub-issue,
retire a worker, drop a repository, migrate, hand off. This is where they are
defined ONCE, each read off the script that owns it, by the WORD it prints and
never by its exit status -- a reader that crashed exits non-zero too, so a
status reads a bug as a verdict.

THE THREE GATES, and why each exists (printed beside every refusal)

  settlement   `campaign-tracker.py settlement <N>`, the sub-issue's row.
               A drop is a disposition of an OPEN sub-issue of this campaign;
               settlement is the one reader of whether it is one.
  live         `campaign-claim.py live <N>`, which makes three readings --
               the claim refs, where each is checked out, herdr's sessions.
               A claim somebody is standing in, or may be, is asked about and
               never closed out from under them.
  local-work   `campaign-local-work.py <N> [dir]`, its rows and last line.
               A release deletes the claim ref, and work that exists only on
               this machine has no other copy.

The worker scope reads a fourth thing and none of the three:

  retire       `campaign-heartbeat.py <N>` without --apply, this pane's line.
               Only a worker the heartbeat reads as released, compacted and
               idle since holds nothing an `/exit` could lose, and that
               reading is the heartbeat's; nothing here restates it.

SCOPE sub-issue <N> <issue> --not-planned "<why>"

  1. settlement   Holds when: the row for <issue> reads `open` (close, then
                  release) or `dropped` (a run that closed and did not
                  release: skip the close, release). `complete`, `unread`, no
                  row, or a reading that did not finish refuses.
  2. live         Holds when: `live` made all three readings, no claim naming
                  <issue> is checked out on this machine, and either no claim
                  naming <issue> stands or no session of the campaign is
                  listed. A listed session is asked: the STATUS to send is
                  printed, one per session, since which session holds which
                  claim is not derivable. A `landed` claim blocks nothing.
  3. local-work   Holds when: the reading finished, no place went unread, and
                  no counted row names a claim branch of <issue>. A row of
                  another sub-issue is that sub-issue's business.
  4. author       Holds when: the comment's first line can name who wrote it
                  -- this session's herdr name, or `owner` with no session id.
  5. close        `gh issue close --reason "not planned"` with the comment
                  `DECISION <author>: closed not planned -- <why>`.
                  Holds when: gh exited 0 (skipped on a `dropped` row).
  6. release      `campaign-claim.py release <N> <issue>`, only when a claim
                  ref names <issue>. Holds when: it printed `deleted` or `no
                  ref to delete` and no `refusing:`. It compacts the CALLER's
                  own pane, as every release does.

SCOPE worker <N> <pane>

  1. retire       Holds when: the heartbeat's line for <pane> opens `retire`.
                  Its reason is printed either way.
  2. herdr        Holds when: HERDR_ENV is 1, which is the guard on every
                  herdr command that drives a pane.
  3. exit         `herdr agent prompt <pane> /exit`, the heartbeat's own
                  action text. Holds when: herdr exited 0.
  4. gone         `herdr agent list`, through campaign-claim's reader, every
                  WAIT_EVERY seconds for WAIT_POLLS polls. Holds when: no row
                  names <pane>. Still listed at the end is reported, and the
                  session is never killed.

WHAT IT NEVER DOES: kill a session, touch the `standing` label, skip a gate,
or take a --force. A run that stops halfway is re-run: every gate is read
again, and the `dropped` row is what lets a closed sub-issue reach its release.

    exit 0   every step held
    exit 1   a gate refused or a step failed; the lines above say which, why,
             and what was already changed
"""
import argparse
import importlib.util
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SKILL_SCRIPTS = BASE / ".claude" / "skills" / "assuming-role" / "scripts"
TRACKER_SCRIPT = HERE / "campaign-tracker.py"
CLAIM_SCRIPT = HERE / "campaign-claim.py"
LOCAL_WORK_SCRIPT = HERE / "campaign-local-work.py"
DIRECTORY_SCRIPT = HERE / "campaign-directory.py"
HEARTBEAT_SCRIPT = SKILL_SCRIPTS / "campaign-heartbeat.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The owners, imported: the claim-branch shape, the herdr reading and the
# tracker's name are campaign-claim's; which campaign a session name is of is
# campaign-name-session's; the retire verdict and its action are the
# heartbeat's.
CLAIM = load(CLAIM_SCRIPT, "campaign_claim")
NAMES = load(SKILL_SCRIPTS / "campaign-name-session.py", "cns")
HEARTBEAT = load(HEARTBEAT_SCRIPT, "campaign_heartbeat")
RETIRE = "retire"
EXIT_TEXT = HEARTBEAT.ACTIONS[RETIRE]

WAIT_EVERY = 5
WAIT_POLLS = 12

WHY = {
    "slug": "every claim branch and session name of the campaign is read "
            "under its slug, and an unread one is not an empty campaign",
    "settlement": "a drop is a disposition of an OPEN sub-issue of this "
                  "campaign, and settlement is the one reader of whether it is",
    "live": "a claim somebody is standing in, or may be, is asked about and "
            "never closed out from under them",
    "local-work": "the release deletes the claim ref, and work that exists "
                  "only on this machine has no other copy",
    "author": "every comment carries its kind and its writer on its first line",
    "close": "the disposition is a GitHub fact or it is nothing",
    "release": "a dropped sub-issue's ref is residue only once it is deleted",
    "retire": "only a worker the heartbeat reads as released, compacted and "
              "idle since holds nothing an /exit could lose",
    "herdr": "a herdr command that drives a pane runs only inside herdr "
             "(HERDR_ENV=1), so it cannot act on somebody else's session",
    "exit": "a session leaves by fact, and the fact is its pane stopping",
    "gone": "a session still listed is asked, never killed",
}


class Refused(Exception):
    def __init__(self, gate, reason, changed="nothing was changed"):
        super().__init__(reason)
        self.gate, self.reason, self.changed = gate, reason, changed


def run(*args, **kw):
    """A command that is not installed is a failed run, not a traceback."""
    try:
        return subprocess.run(args, capture_output=True, text=True, **kw)
    except (FileNotFoundError, PermissionError) as e:
        return subprocess.CompletedProcess(
            args, 127, "", f"{args[0]}: {e.__class__.__name__}: {e}")


def script(path, *args):
    r = run(sys.executable, str(path), *args)
    return (r.stdout or "") + (r.stderr or "")


def holds(step, evidence):
    print(f"{step:<11} holds -- {evidence}")


# ------------------------------------------------------------- the readings
# Pure: each takes what its owner printed and returns what the gate needs.


SETTLED = re.compile(r"-- \d+/\d+ settled")


def settlement_word(text, issue):
    """(word, line) for <issue>'s row, or (None, why)."""
    ref = f"{CLAIM.TRACKER}#{issue}"
    finished = False
    for line in text.splitlines():
        t = line.split()
        if len(t) >= 2 and t[0] == ref:
            return t[1], line.strip()
        finished |= bool(SETTLED.search(line)) or "the index is empty" in line
    if finished:
        return None, f"{ref} is not in the campaign's sub-issue index"
    last = text.strip().splitlines()[-1:] or ["<no output>"]
    return None, f"settlement did not finish reading: {last[0].strip()[:200]}"


LIVE_GROUPS = (("claims checked out on this machine", "occupied"),
               ("claims checked out nowhere on this machine", "vacant"),
               ("live sessions of ", "sessions"),
               ("sessions named for no campaign", None))


def live_reading(text, n, slug):
    """`campaign-claim live`'s groups: claim rows as (branch, issue, rest),
    session rows as (name, status, pane). A row is a row only if its first
    word is a claim branch or a session name of this campaign, so the notes
    printed under each group are never read as one."""
    out = {"read": False, "occupied": [], "vacant": [], "sessions": []}
    group = None
    for line in text.splitlines():
        if line.startswith("all three readings were made."):
            out["read"] = True
        head = next((k for h, k in LIVE_GROUPS if line.startswith(h)), False)
        if head is not False:
            group = head
            continue
        if not line.startswith("  "):
            group = None
            continue
        t = line.split()
        if not t or group is None:
            continue
        if group == "sessions":
            if len(t) >= 3 and NAMES.campaign_of(t[0]) == slug:
                out["sessions"].append((t[0], t[1], t[2]))
            continue
        issue = CLAIM.issue_of_branch(t[0], n, slug)
        if issue is not None:
            out[group].append((t[0], issue, " ".join(t[1:])))
    return out


def claims_of(reading, issue):
    """(checked out here, standing elsewhere) for <issue>. `landed` is work on
    main whose ref outlived it, and stands in nobody's way."""
    here = [(b, rest) for b, i, rest in reading["occupied"] if i == issue]
    away = [(b, rest) for b, i, rest in reading["vacant"]
            if i == issue and not rest.startswith("landed as")]
    return here, away


COUNTED_ROW = re.compile(r"^ {4}\S")
LOCAL_VERDICT = re.compile(r"-- \d+ item\(s\) exist only on this machine")


def local_rows(text, n, slug, issue):
    """(finished, unread, rows naming <issue>'s claim branches). A counted row
    is four spaces then its repository; an uncounted one carries `~`."""
    lines = text.strip().splitlines()
    last = lines[-1] if lines else ""
    finished = bool(LOCAL_VERDICT.search(last))
    unread = finished and "went unread" in last
    rows = [line.strip() for line in lines if COUNTED_ROW.match(line)
            and any(CLAIM.issue_of_branch(tok.strip("[];,"), n, slug) == issue
                    for tok in line.split())]
    return finished, unread, rows, last.strip()


HEARTBEAT_LINE = r"^(\S+) {pane} (\S+): (.*)$"


def heartbeat_line(text, pane):
    """(word, name, reason) of the heartbeat's verdict line for <pane>."""
    m = re.search(HEARTBEAT_LINE.format(pane=re.escape(pane)), text, re.M)
    return m.groups() if m else None


def status_text(slug, issue, name):
    return (f"STATUS to {name}: {slug}#{issue} is about to be closed not "
            f"planned. Are you working it? Say what you are doing, what exists "
            f"only on this machine, and whether it is safe to stop.")


# ------------------------------------------------------------- the gates


def gate_settlement(n, issue):
    word, line = settlement_word(script(TRACKER_SCRIPT, "settlement", n), issue)
    if word == "open":
        holds("settlement", line)
        return "open"
    if word == "dropped":
        holds("settlement", f"{line} -- already closed, so release only")
        return "dropped"
    if word is None:
        raise Refused("settlement", line)
    raise Refused("settlement", f"the row reads `{word}`, not `open`: {line}")


def gate_live(n, slug, issue):
    reading = live_reading(script(CLAIM_SCRIPT, "live", n), n, slug)
    if not reading["read"]:
        raise Refused("live", "`campaign-claim live` did not make all three "
                              "readings, so no count from it is safe")
    here, away = claims_of(reading, issue)
    who = reading["sessions"]
    if here or (away and who):
        for name, status, pane in who:
            print(f"  ask {name} ({status}, {pane}): "
                  f"{status_text(slug, issue, name)}")
        what = ([f"{b} is checked out at {p}" for b, p in here]
                + [f"{b} ({m}) stands and {len(who)} session(s) of {slug} "
                   f"are listed" for b, m in away])
        raise Refused("live", "; ".join(what))
    holds("live", f"{len(here) + len(away)} open claim(s) of #{issue}, "
                  f"{len(who)} session(s) of {slug} listed")
    return [b for b, i, _ in reading["occupied"] + reading["vacant"]
            if i == issue]


def gate_local_work(n, slug, issue):
    d = run(sys.executable, str(DIRECTORY_SCRIPT), n)
    word = (d.stdout or "").strip()
    if word == "none":
        args = [n]
    elif word.startswith("/"):
        args = [n, word]
    else:
        raise Refused("local-work", f"campaign-directory {n} answered "
                                    f"{word or '<nothing>'!r}: "
                                    f"{(d.stderr or '').strip()[:160]}")
    finished, unread, rows, last = local_rows(
        script(LOCAL_WORK_SCRIPT, *args), n, slug, issue)
    if not finished:
        raise Refused("local-work", f"the reading did not finish: {last[:200]}")
    if unread:
        raise Refused("local-work", f"places went unread, and one may hold "
                                    f"#{issue}'s branch: {last}")
    if rows:
        raise Refused("local-work", "work on #%s's branch exists only on this "
                                    "machine: %s" % (issue, " | ".join(rows)))
    holds("local-work", f"no counted row names #{issue}'s branch ({last})")


def gate_author(slug):
    sid = os.environ.get(CLAIM.SESSION_ID_VAR)
    if not sid:
        holds("author", "no session id, so a person: owner")
        return "owner"
    sessions, why = CLAIM.herdr_sessions()
    name = ((sessions or {}).get(sid) or {}).get("name")
    if not name or NAMES.campaign_of(name) is None:
        raise Refused("author", f"session {sid} has no campaign name in herdr "
                                f"({why or name or 'no row'})")
    holds("author", name)
    return name


def step_close(issue, author, why):
    body = f"DECISION {author}: closed not planned -- {why}"
    r = run("gh", "issue", "close", issue, "-R", CLAIM.TRACKER,
            "--reason", "not planned", "--comment", body)
    if r.returncode != 0:
        raise Refused("close", f"gh exited {r.returncode}: "
                               f"{(r.stderr or '').strip()[:200]}")
    holds("close", f"{CLAIM.TRACKER}#{issue} closed not planned")


def step_release(n, issue):
    text = script(CLAIM_SCRIPT, "release", n, issue)
    print("\n".join(f"  | {line}" for line in text.rstrip().splitlines()))
    lines = text.splitlines()
    refusal = next((ln for ln in lines if ln.startswith("refusing:")), None)
    done = any(ln.startswith("deleted ") or "no ref to delete" in ln
               for ln in lines)
    if refusal or not done:
        raise Refused("release", refusal or "release printed neither `deleted` "
                                            "nor `no ref to delete`",
                      changed=f"#{issue} is closed not planned; its claim "
                              f"still stands -- re-run once the cause is fixed")
    holds("release", "the claim ref is gone")


def wait_gone(pane, read=None, sleep=None, polls=WAIT_POLLS,
              every=WAIT_EVERY):
    """(gone, what the last poll read). A listing that did not read is not an
    absence, so it is one more poll and never the answer."""
    read, sleep = read or CLAIM.herdr_sessions, sleep or time.sleep
    note = "no poll ran"
    for k in range(polls):
        sessions, why = read()
        if sessions is None:
            note = f"poll {k + 1}: {why}"
        elif not any(row["pane"] == pane for row in sessions.values()):
            return True, f"poll {k + 1}: {pane} is not listed"
        else:
            note = f"poll {k + 1}: {pane} is still listed"
        if k + 1 < polls:
            sleep(every)
    return False, note


# ------------------------------------------------------------- the scopes


def slug_of(n):
    slug, note = CLAIM.campaign_slug(n)
    if slug is None:
        raise Refused("slug", f"the campaign's slug did not read: {note}")
    return slug


def sub_issue(args):
    n, issue = args.campaign_issue, args.issue
    slug = slug_of(n)
    word = gate_settlement(n, issue)
    branches = gate_live(n, slug, issue)
    gate_local_work(n, slug, issue)
    author = gate_author(slug)
    if word == "open":
        step_close(issue, author, args.not_planned)
    if branches:
        step_release(n, issue)
    else:
        holds("release", f"no claim ref names #{issue}; nothing to release")


def worker(args):
    n, pane = args.campaign_issue, args.pane
    text = script(HEARTBEAT_SCRIPT, n)
    line = heartbeat_line(text, pane)
    if line is None:
        first = (text.strip().splitlines() or ["<no output>"])[0]
        raise Refused("retire", f"the heartbeat gave {pane} no verdict -- not "
                                f"a session of #{n}, or it could not read: "
                                f"{first[:200]}")
    word, name, reason = line
    if word != RETIRE:
        raise Refused("retire", f"the heartbeat reads {name} as `{word}`: "
                                f"{reason}")
    holds("retire", f"{name}: {reason}")
    if os.environ.get("HERDR_ENV") != "1":
        raise Refused("herdr", "HERDR_ENV is not 1")
    holds("herdr", "HERDR_ENV=1")
    r = run("herdr", "agent", "prompt", pane, EXIT_TEXT)
    if r.returncode != 0:
        raise Refused("exit", f"herdr exited {r.returncode}: "
                              f"{(r.stderr or '').strip()[:200]}")
    holds("exit", f"sent {EXIT_TEXT} to {pane}")
    gone, note = wait_gone(pane)
    if not gone:
        raise Refused("gone", f"{note} after {WAIT_POLLS * WAIT_EVERY}s: say "
                              f"so on the sub-issue it worked, and ask",
                      changed=f"{EXIT_TEXT} was sent to {pane}")
    holds("gone", note)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="scope", required=True)

    def number(s):
        return s.lstrip("#")

    s = sub.add_parser("sub-issue", help="close one sub-issue not planned, "
                                         "then release its claim")
    s.add_argument("campaign_issue", type=number)
    s.add_argument("issue", type=number)
    s.add_argument("--not-planned", required=True, metavar="WHY",
                   help="the person's reason, written into the closing comment")
    s.set_defaults(fn=sub_issue)
    w = sub.add_parser("worker", help="send /exit to a worker the heartbeat "
                                      "reads as retirable, and wait for it")
    w.add_argument("campaign_issue", type=number)
    w.add_argument("pane")
    w.set_defaults(fn=worker)
    args = ap.parse_args(argv)
    try:
        args.fn(args)
    except Refused as r:
        print(f"REFUSE {r.gate}: {r.reason}")
        print(f"  why: {WHY[r.gate]}")
        print(f"  {r.changed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
