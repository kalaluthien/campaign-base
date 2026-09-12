#!/usr/bin/env python3
"""Read every session of a campaign and say, per session, what the planner's heartbeat does to it.

    .claude/skills/assuming-role/scripts/campaign-heartbeat.py <N> [--apply]
    .claude/skills/assuming-role/scripts/campaign-heartbeat.py <N> --watch [--every S]

The planner runs this on every wake (planner.md § The planner's clock). It
reads every session of campaign N -- a herdr row whose name carries N's slug,
this planner's own pane included -- and prints one line per session, the
verdict first, then what it read and from where:

    fire     a limit banner stands on the pane: `campaign-limit-reset.py
             <pane> --fire <own pane>` schedules the planner's wake, once per
             run, since every session shares one account and one reset
    compact  idle, and its context is at least COMPACT_AT tokens: `/compact`
    retire   a worker, idle, whose last assignment prompt names sub-issue N,
             with no `<slug>/<N>-` ref standing and no prompt and no tool
             call since the last such ref went: done by a GitHub fact, `/exit`
    quiet    the own pane, when the campaign has nothing left to do: `/compact`,
             never `/exit`, since a campaign always has a planner. Quiet is
             three readings, each made this run: no session of the campaign
             listed but the own pane (herdr), no open sub-issue without
             `backlog` (the index, as `drift unclaimed` reads it), no claim
             ref standing (the refs). One not made is not quiet, and the own
             pane is judged as any other.
    keep     anything else -- working, blocked, small, and every reading that
             could not be made. It never acts.

A line after the header says whether the campaign is quiet and what the three
readings were. Then one line per action: `sent`, `would send` (no --apply) or
`could not send`. Without --apply nothing is sent and no wake is scheduled.

    exit 0   the sessions were listed and every action asked for was sent
    exit 1   the slug or the listing could not be read, or an action failed

WHAT IS READ, AND FROM WHERE

  herdr agent list     which sessions exist, their names, panes and status;
                       through `campaign-claim.py`'s reader, not a second one.
  the name             whose campaign, by `campaign-name-session.py`'s
                       `campaign_of`, and the role word beside it.
  the transcript       `~/.claude/projects/*/<session id>.jsonl`, the file
                       herdr's session id names. Context size, the last
                       assignment prompt, the last compaction, prompt and
                       tool call all come from here and never from the
                       screen: `transcript_reading` is the one reader, and
                       `campaign-assign.py` asks it the same question.
  the refs             the campaign's claim refs, as the watch reads them
                       (`claim_reading`): a `<slug>/<N>-` ref standing is
                       sub-issue N still claimed.
  the events feed      `gh api repos/<repo>/events` on every repository the
                       refs were read on: the latest DeleteEvent of a branch
                       under `<slug>/<N>-` is when N's claim went. Asked only
                       for an idle worker's N with no ref standing.
  the banner           `campaign-limit-reset.py <pane>`, its first word. The
                       own pane is not read: it is running this, so it is not
                       stopped.

THE OWN PANE (`HERDR_PANE_ID`) is never idle while this runs, so its idle
reading is skipped: a `/compact` sent into it queues until this turn ends,
which is the moment its context is still cached. It is never retired.

A PASSED BANNER IS NOT A FIRE. `passed` means the reset is behind now; the
planner is awake, so a wake scheduled for now would only prompt it again,
and every later run would read the same banner and prompt again. The line
says the stop has passed, and the pane is judged like any other.

WHAT `retire` CANNOT SEE, both ways. Who released the ref is not read, and
neither is which checkout a session stands in (AGENTS.md § Completion): a
worker that took another claim before its assigned one's ref went, and has
been idle since, reads as done. The rest err the safe way, `keep`: the feed
holds a repository's last 300 events (11.5h of this base's, 2026-09-12) and
may lag the delete, so a deletion out of it or not yet in it reads as none;
a sub-issue given in a prompt of another shape is no assignment, and one
whose prompt sits in an earlier file a resume left behind is none; and a
done worker that answers a peer's message with a tool call after the ref
went is kept for good.

NO READING IS STORED. Every verdict is a function of what the sources say
now, so a run repeated with nothing changed says the same thing.

--watch IS THE PLANNER'S WAKE: it polls every S seconds (60) until killed or
quiet and prints only what changed, so a Monitor over it wakes the planner on
an event, and the planner runs this with --apply. Keyed by N and its slug,
which the planner holds at launch; a pull request that appears later is one
more line. Each poll builds a snapshot and prints `+ line` for a line that
appeared and `- line` for one that went; a drift still standing after 30m
reprints as `= line`. The first poll prints `watching <slug>` and every drift
and limit.

A QUIET CAMPAIGN ENDS THE WATCH: two polls running whose sessions, claims and
sub-issues were each read THAT poll -- a last reading standing is not one --
and read quiet print `quiet <slug>: <the three readings>` and exit 0.

  session <name> <status>   herdr, counted after two equal polls, since herdr
                            calls a mid-turn pause idle; the own pane has none
  limit <pane> <banner>     limit-reset's first line, on a non-working pane
  claim <branch>            campaign-claim's refs, in the tracker and ## Repos
  issue <n> <state> [backlog]   the campaign's sub-issue index
  pr <n> <branch> <state> <sha> comments=<k>   a claim's pull request;
                            k counts comments and reviews, so a REPORT or a
                            REVIEW moves it
  drift <rule> <subject>    a desired state that does not hold:
    unclaimed    an open sub-issue without `backlog` has no claim
    unworked     more claims than workers
    stuck        a claim with no pull request change for 30m while no worker
                 works
    settled      a claim whose sub-issue is closed
    idle-worker  more workers than claims, and a worker idle for 10m
    context      a non-working session at or over COMPACT_AT, read through
                 `transcript_reading`, which stops at a compaction
    install      an install whose HEAD is not its origin's tip, by
                 campaign-installed's reader

The rules count claims and workers and never pair them: which session works
which claim is not derivable (AGENTS.md § Completion). A source that fails
three polls running prints `error <source>` and its last reading stands; a poll
running past 300s prints `error watchdog` and exits 1. A drift rule runs once
every source it reads has been read, since an unread one is not empty; each
install is a source of its own, so one unreadable install hides no other.
"""
import argparse
import datetime
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[3]   # .claude/skills/assuming-role/scripts -> the base

# THE COMPACTION THRESHOLD, in context tokens: the owner's number,
# 2026-09-10. Above it every turn re-reads a context that a compaction would
# cut to a summary, and the heartbeat is the only thing that looks.
COMPACT_AT = 200_000

# The claim refs and herdr's listing, through that script's readers.
RELEASE_SCRIPT = BASE / "scripts" / "campaign-claim.py"
# The assignment sentence's shape: `ASSIGNMENT` there is its one home.
ASSIGN_SCRIPT = BASE / "scripts" / "campaign-assign.py"
# GitHub's events feed: 100 a page, and HTTP 422 past the third page (probed
# 2026-09-12), so a repository's last 300 events.
EVENT_PAGES = 3
# What the watch asks for a campaign's directory and its installs.
DIRECTORY_SCRIPT = BASE / "scripts" / "campaign-directory.py"
INSTALLED_SCRIPT = BASE / "scripts" / "campaign-installed.py"

# What a compaction writes into the transcript around itself, which is not a
# prompt: the `/compact` that `release` queues (a bare user record), the
# command's own record, its caveat and its stdout. Read off this machine's
# transcripts 2026-09-10, where the bare one sat after 19 of 22 releases;
# everything else a user record carries as text counts as a prompt, which errs
# toward `keep`.
COMPACTION_ECHOES = ("<command-name>/compact<", "<local-command-")
QUEUED_COMPACT = "/compact"   # exactly: `/compact <focus>` is a person's prompt
# A background task's notice reaching an IDLE pane: a plain user record, no
# isMeta, its text opening with this tag (820 on this machine, 2026-09-11).
# Busy, the same notice is a queued_command of another mode.
TASK_NOTICE = "<task-notification>"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ASSIGNMENT = load(ASSIGN_SCRIPT, "campaign_assign").ASSIGNMENT


def run(*args, **kw):
    """A command that is not installed is a failed run, not a traceback."""
    try:
        return subprocess.run(args, capture_output=True, text=True, **kw)
    except (FileNotFoundError, PermissionError) as e:
        return subprocess.CompletedProcess(
            args, 127, "", f"{args[0]}: {e.__class__.__name__}: {e}")


# --------------------------------------------------------- the transcript


def transcript_path(session_id):
    """(path, None), or (None, why). The file herdr's session id names."""
    root = Path.home() / ".claude" / "projects"
    hits = sorted(root.glob(f"*/{session_id}.jsonl"))
    if len(hits) != 1:
        return None, (f"{len(hits)} transcript(s) named {session_id}.jsonl "
                      f"under {root}")
    return hits[0], None


def texts(content):
    """The text a message carries, as a list of strings."""
    if isinstance(content, str):
        return [content]
    return [b.get("text", "") for b in content or []
            if isinstance(b, dict) and b.get("type") == "text"]


def is_prompt(content):
    """Does this content carry text a person or a peer typed, rather than the
    compaction's own echo, the bare `/compact` release queues, or a
    background task's notice?"""
    said = "".join(texts(content)).strip()
    return bool(said) and said != QUEUED_COMPACT and not said.startswith(
        COMPACTION_ECHOES + (TASK_NOTICE,))


def assignment(content):
    """The sub-issue number an assignment sentence in this content names, or
    None: `ASSIGNMENT`, as the brief hook reads it."""
    hit = ASSIGNMENT.search("".join(texts(content)))
    return int(hit.group("issue")) if hit else None


def transcript_reading(lines):
    """What one session's transcript says. Pure, over its lines. Returns a
    dict of timestamps and the context size:

      assigned   the sub-issue the last prompt carrying an assignment
                 sentence names, at `assigned_at`: `campaign-assign.py`'s
                 prompt and the launch brief. Only a prompt counts, so a
                 summary or a tool result quoting the sentence does not.
      compacted  the last `compact_boundary` record. A record type, so no
                 text anything prints can forge it.
      prompted   the last user record carrying text that is not the
                 compaction's own echo and not a harness note (`isMeta`),
                 or the last prompt typed while the pane was busy: an
                 `attachment` record of type `queued_command`, mode
                 `prompt`, not `isMeta` -- which a peer's message is, and a
                 task notification is another mode.
      acted      the last assistant record calling a tool: a turn after the
                 claim went is work `retire` must not cut off.
      context    input plus cache tokens of the latest usage record, or the
                 boundary's `postTokens` when a compaction came after it --
                 none when the boundary carries none, since the usage before
                 it describes a context the compaction replaced. A
                 `<synthetic>` record -- a limit banner, an API error -- is
                 the harness's, carries zero usage, and is skipped.

    BY TIMESTAMP, NOT POSITION: a command's record carries the time it was
    queued, which can be earlier than records written before it, so every
    "last" is the latest time. Records of a subagent (`isSidechain`) are its
    own context, not this session's."""
    out = {"assigned": None, "assigned_at": None, "compacted": None,
           "prompted": None, "acted": None, "context": None,
           "context_at": None, "records": 0}

    def later(key, ts):
        if out[key] is None or ts > out[key]:
            out[key] = ts

    def size(ts, tokens):
        if out["context_at"] is None or ts > out["context_at"]:
            out["context"], out["context_at"] = tokens, ts

    def said(ts, content):
        later("prompted", ts)
        n = assignment(content)
        if n is not None and (out["assigned_at"] is None
                              or ts > out["assigned_at"]):
            out["assigned"], out["assigned_at"] = n, ts

    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or r.get("isSidechain"):
            continue
        ts = r.get("timestamp")
        if not isinstance(ts, str):
            continue
        out["records"] += 1
        kind, msg = r.get("type"), r.get("message") or {}
        if kind == "system" and r.get("subtype") == "compact_boundary":
            later("compacted", ts)
            size(ts, (r.get("compactMetadata") or {}).get("postTokens"))
        elif kind == "assistant" and msg.get("model") != "<synthetic>":
            calls = msg.get("content")
            if isinstance(calls, list) and any(
                    isinstance(b, dict) and b.get("type") == "tool_use"
                    for b in calls):
                later("acted", ts)
            u = msg.get("usage")
            if not isinstance(u, dict):
                continue
            size(ts, sum(u.get(k) or 0 for k in (
                "input_tokens", "cache_creation_input_tokens",
                "cache_read_input_tokens")))
        elif kind == "user":
            if r.get("isMeta") or r.get("isCompactSummary"):
                continue
            content = msg.get("content")
            if is_prompt(content):
                said(ts, content)
        elif kind == "attachment":
            a = r.get("attachment") or {}
            if (a.get("type") == "queued_command"
                    and a.get("commandMode") == "prompt"
                    and not a.get("isMeta") and is_prompt(a.get("prompt"))):
                said(ts, a.get("prompt"))
    return out


def read_transcript(session_id):
    """(reading, where, None), or (None, where, why)."""
    path, why = transcript_path(session_id)
    if path is None:
        return None, "no transcript", why
    try:
        with open(path, encoding="utf-8") as fh:
            return transcript_reading(fh), str(path), None
    except OSError as e:
        return None, str(path), f"could not read it: {e}"


def when(ts):
    """A transcript's or GitHub's ISO timestamp, as a time: the two write
    different precisions, so their strings do not sort against each other."""
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def ref_went(reading, refs):
    """(when, why): when the claim of the sub-issue this session was last
    assigned went, or None and why no such time is read. Pure over
    `transcript_reading`'s dict and `refs`, a function from a sub-issue to
    ((refs standing, when the last went or None, what was read), None) or
    (None, why)."""
    n = reading["assigned"]
    if n is None:
        return None, (f"no assignment prompt in {reading['records']} "
                      f"record(s)")
    got, why = refs(n)
    if got is None:
        return None, f"assigned #{n}; {why}"
    standing, went, read = got
    if standing:
        return None, f"assigned #{n}; {', '.join(standing)} standing ({read})"
    if went is None:
        return None, f"assigned #{n}; no ref standing and no deletion read ({read})"
    return went, f"assigned #{n}; no ref standing, the last went {went} ({read})"


def compacted_since_ref(reading, refs):
    """(verdict, why) for `campaign-assign.py`: has this session compacted
    since the claim of its last assigned sub-issue went?

      compacted  a compaction later than that
      stale      the claim went and no compaction after it
      unknown    no time it went: no assignment prompt, a ref still
                 standing, or a deletion not read"""
    went, why = ref_went(reading, refs)
    if went is None:
        return "unknown", why
    comp = reading["compacted"]
    if comp and when(comp) > when(went):
        return "compacted", f"{why}, compacted {comp}"
    return "stale", f"{why}, no compaction after it"


# --------------------------------------------------------- the verdict


def banner_word(line):
    """The first word of `campaign-limit-reset.py <pane>`'s answer."""
    if line.startswith(("session ", "weekly ")):
        return "limit"
    if line.startswith("passed "):
        return "passed"
    if line.startswith("no limit"):
        return "none"
    return "unread"


def verdict(role, own, idle, banner, reading, refs):
    """(verdict, why). Pure. `banner` is limit-reset's first line, or None
    for the own pane; `reading` is `transcript_reading`'s dict, or a string
    saying why there is none; `idle` is campaign-assign's idle reading;
    `refs` is `ref_went`'s, asked only of another pane's idle worker. A
    worker not retired says why beside the verdict it got."""
    if not own:
        word = banner_word(banner)
        if word == "unread":
            return "keep", f"banner not read: {banner}"
        if word == "limit":
            return "fire", f"banner: {banner}"
        if not idle[0]:
            return "keep", idle[1]
    if isinstance(reading, str):
        return "keep", f"transcript not read: {reading}"
    passed = " (the limit it stopped on has passed)" if (
        not own and banner_word(banner) == "passed") else ""
    if role == "worker" and not own:
        went, why = ref_went(reading, refs)
        since = [f"a {what} at {ts}" for what, ts in (
            ("prompt", reading["prompted"]), ("tool call", reading["acted"]))
            if went and ts and when(ts) > when(went)]
        if went and not since:
            return "retire", (f"{why}; no prompt and no tool call since"
                              f"{passed}")
        passed += "; not retired: " + (
            f"{' and '.join(since)} after {went}" if since else why)
    if reading["context"] is None:
        return "keep", f"no context size in the transcript{passed}"
    if reading["context"] >= COMPACT_AT:
        return "compact", (f"context {reading['context']:,} >= "
                           f"{COMPACT_AT:,}{passed}")
    return "keep", f"context {reading['context']:,} < {COMPACT_AT:,}{passed}"


# --------------------------------------------------------- the watch

# THE WATCH'S CLOCKS, the owner's numbers (DECISION on rule-check#296,
# 2026-09-11). A poll a minute, since a claim, a push or a comment is minutes
# of work; a stall or an idle worker is news after the time a turn takes.
WATCH_EVERY = 60
STUCK_AFTER = 30 * 60
IDLE_AFTER = 10 * 60
REPRINT_AFTER = 30 * 60
UNREAD_POLLS = 3       # a source failing this many polls running prints `error`
POLL_CEILING = 300     # one poll past this exits 1, so a hung watch is loud
# Quiet polls running before the watch ends: an index or refs read that
# succeeds empty on a `gh` hiccup is one poll, and the exit is for good.
QUIET_POLLS = 2


def workable(issues):
    """The open sub-issues without `backlog`, over the index as
    {n: (state, backlog)}: what `drift unclaimed` and `quiet` both ask."""
    return sorted(n for n, (state, backlog) in issues.items()
                  if state == "open" and not backlog)


def quiet_reading(own, panes, claims, issues):
    """(quiet, what was read). Pure. Each reading is (value, why) as the
    watch takes it -- the panes of the campaign's listed sessions, its claim
    refs, its sub-issue index -- and one not made is not quiet, and says why.
    Quiet is no pane but `own`, no workable sub-issue, and no claim."""
    unread = [f"{name} not read: {why}" for name, (_, why) in (
        ("herdr", panes), ("the refs", claims), ("the index", issues))
        if why is not None]
    if unread:
        return False, "; ".join(unread)
    panes, claims, issues = panes[0], claims[0], issues[0]
    others = [p for p in panes if p != own]
    todo = workable(issues)
    return not (others or todo or claims), (
        f"herdr {len(panes)} session(s), {len(others)} but the own pane; "
        f"the index {len(issues)} sub-issue(s), {len(todo)} open without "
        f"backlog; the refs {len(claims)} claim(s)")


class Watch:
    """What the watch remembers between polls, and the one step over it.

    `poll` is pure: it takes every source's reading as (value, why) -- `why`
    None for a reading made -- and the time, and returns the lines to print.
    A source that could not be read keeps its last reading."""

    def __init__(self, slug, own=None):
        self.slug, self.own = slug, own
        self.last, self.fails = {}, {}
        self.raw, self.stable, self.idle_since = {}, {}, {}
        self.moved = {}      # claim -> (its pull request as last read, since)
        self.shown = None    # the last snapshot; None before the first poll
        self.printed = {}    # drift line -> when it was last printed
        self.calm_polls = 0  # polls running that read quiet
        self.quiet = None    # the `quiet` line, once QUIET_POLLS read it

    def poll(self, readings, now):
        out = []
        for source, (value, why) in sorted(readings.items()):
            if why is not None:
                self.fails[source] = self.fails.get(source, 0) + 1
                if self.fails[source] == UNREAD_POLLS:
                    out.append(f"error {source}: unread for {UNREAD_POLLS} "
                               f"polls, showing the last reading: {why}")
                continue
            self.fails[source] = 0
            self.last[source] = value
            if source == "installs":
                # The list of installs, read: one that left it is no source.
                for gone in [k for k in set(self.last) | set(self.fails)
                             if k.startswith("install ")
                             and k[len("install "):] not in value]:
                    self.last.pop(gone, None)
                    self.fails.pop(gone, None)
            if source == "sessions":
                self.settle(value)
        # Quiet reads this poll's readings, never a last one standing.
        fresh = {s: readings.get(s, (None, "not read this poll"))
                 for s in ("sessions", "claims", "issues")}
        sessions, why = fresh["sessions"]
        calm, what = quiet_reading(
            self.own, (None, why) if why is not None else
            ([s["pane"] for s in sessions.values()], None),
            fresh["claims"], fresh["issues"])
        lines = self.snapshot(now)
        if self.shown is None:
            out.insert(0, f"watching {self.slug}: {len(lines)} line(s)")
            added = sorted(ln for ln in lines
                           if ln.startswith(("drift ", "limit ")))
            removed = []
        else:
            added, removed = sorted(lines - self.shown), sorted(self.shown - lines)
        reprint = sorted(ln for ln in lines if ln.startswith("drift ")
                         and ln not in added
                         and now - self.printed.get(ln, now) >= REPRINT_AFTER)
        self.printed = {ln: (now if ln in added or ln in reprint else t)
                        for ln, t in self.printed.items() if ln in lines}
        for ln in added:
            if ln.startswith("drift "):
                self.printed[ln] = now
        self.shown = lines
        self.calm_polls = self.calm_polls + 1 if calm else 0
        ends = self.calm_polls >= QUIET_POLLS
        if ends:
            self.quiet = f"quiet {self.slug}: {what}"
        return (out + [f"- {ln}" for ln in removed] + [f"+ {ln}" for ln in added]
                + [f"= {ln}" for ln in reprint] + ([self.quiet] if ends else []))

    def settle(self, sessions):
        """A status counts only after two equal polls: herdr calls a mid-turn
        pause idle. A session seen for the first time counts at once."""
        for name, s in sessions.items():
            if self.raw.get(name, s["status"]) == s["status"]:
                self.stable[name] = s["status"]
            self.raw[name] = s["status"]
        for gone in set(self.raw) - set(sessions):
            for d in (self.raw, self.stable, self.idle_since):
                d.pop(gone, None)

    def snapshot(self, now):
        sessions = self.last.get("sessions", {})
        claims = self.last.get("claims", {})
        issues = self.last.get("issues", {})
        prs = self.last.get("prs", {})
        lines, workers = set(), {}
        for name, s in sessions.items():
            st = self.stable[name]
            if st == "working":
                self.idle_since.pop(name, None)
            else:
                self.idle_since.setdefault(name, now)
            if s["pane"] != self.own:
                lines.add(f"session {name} {st}")
            if name.split("-")[-2] == "worker":
                workers[name] = st
            if s.get("banner") and banner_word(s["banner"]) != "none":
                lines.add(f"limit {s['pane']} {s['banner']}")
            if (st != "working" and s.get("context") is not None
                    and s["context"] >= COMPACT_AT):
                lines.add(f"drift context {name} {s['context'] // 1000}k")
        lines |= {f"claim {b}" for b in claims}
        lines |= {f"issue {n} {st}{' backlog' if bl else ''}"
                  for n, (st, bl) in issues.items()}
        lines |= {f"pr {p[0]} {b} {p[1]} {p[2]} comments={p[3]}"
                  for b, p in prs.items() if b in claims}
        lines |= self.drift(claims, issues, prs, workers, now)
        lines |= {f"drift {source} {word}"
                  for source, word in self.last.items()
                  if source.startswith("install ") and word != "current"}
        return lines

    def drift(self, claims, issues, prs, workers, now):
        """The rules count claims and workers and never pair one with the
        other: which session works which claim is not derivable (AGENTS.md
        § Completion). A rule runs once every source it reads has been read:
        an unread source is not an empty one."""
        out = set()
        read = set(self.last)
        claimed = set(claims.values())
        if {"claims", "issues"} <= read:
            for n in workable(issues):
                if n not in claimed:
                    out.add(f"drift unclaimed {self.slug}#{n}")
            for b, n in claims.items():
                if issues.get(n, ("open",))[0] == "closed":
                    out.add(f"drift settled {b}")
        if not {"sessions", "claims"} <= read:
            return out
        if len(claims) > len(workers):
            out.add(f"drift unworked {len(claims)} claim(s), "
                    f"{len(workers)} worker(s)")
        working = any(st == "working" for st in workers.values())
        for b in claims if "prs" in read else ():
            if working or b not in self.moved or self.moved[b][0] != prs.get(b):
                self.moved[b] = (prs.get(b), now)
            if now - self.moved[b][1] >= STUCK_AFTER:
                out.add(f"drift stuck {b}")
        self.moved = {b: v for b, v in self.moved.items() if b in claims}
        if len(workers) > len(claims):
            for w in workers:
                if w in self.idle_since and now - self.idle_since[w] >= IDLE_AFTER:
                    out.add(f"drift idle-worker {w}")
        return out


class PollOverrun(BaseException):
    """Not an Exception, so a reader's catch-all cannot swallow it."""


def run_watch(watch, read, every, polls=None, clock=None, sleep=None):
    """Poll until killed, quiet, or `polls` times; exit 1 when one poll runs
    past POLL_CEILING. `read` returns the readings `Watch.poll` takes."""
    import signal
    import time
    clock, sleep = clock or time.time, sleep or time.sleep

    def overrun(*_):
        raise PollOverrun()

    signal.signal(signal.SIGALRM, overrun)
    done = 0
    try:
        while polls is None or done < polls:
            signal.alarm(POLL_CEILING)
            try:
                out = watch.poll(read(), clock())
            finally:
                signal.alarm(0)
            if out:
                print("\n".join(out), flush=True)
            if watch.quiet:
                return 0
            done += 1
            if polls is None or done < polls:
                sleep(every)
    except PollOverrun:
        print(f"error watchdog: one poll ran past {POLL_CEILING}s; exiting",
              flush=True)
        return 1
    return 0


# --------------------------------------------------------- the shell


ACTIONS = {"compact": "/compact", "retire": "/exit", "quiet": "/compact"}


def slug_of(issue):
    r = run(sys.executable, str(BASE / "scripts" / "campaign-tracker.py"),
            "slug", issue)
    word = r.stdout.strip()
    if r.returncode != 0 or not word:
        return None, (f"campaign-tracker slug {issue} exited {r.returncode}: "
                      f"{word or r.stderr.strip()[:200]}")
    return word, None


def limit_reset(*args):
    return run(sys.executable, str(HERE / "campaign-limit-reset.py"), *args,
               env=dict(os.environ, HERDR_ENV="1"))


def fire_args(issue, pane, own):
    """limit-reset's --fire argv, logged under the campaign's runtime/ when
    the directory can be read; otherwise limit-reset picks a temp log."""
    argv = [pane, "--fire", own]
    r = run(sys.executable, str(BASE / "scripts" / "campaign-directory.py"),
            issue)
    if r.returncode == 0 and r.stdout.strip():
        argv += ["--log", str(Path(r.stdout.strip()) / "runtime"
                             / "limit-wake.log")]
    return argv


def context_of(session_id, cache):
    """A session's context size through `transcript_reading`, re-read only
    when its transcript changed: an idle session's file does not."""
    path, _ = transcript_path(session_id)
    if path is None:
        return None
    try:
        st = path.stat()
        key = (st.st_mtime_ns, st.st_size)
        if cache.get(path, (None,))[0] != key:
            with open(path, encoding="utf-8") as fh:
                cache[path] = (key, transcript_reading(fh)["context"])
    except OSError:
        return None
    return cache[path][1]


def claim_reading(issue, slug, claim, repos=None):
    """(({claim branch: its sub-issue}, the repositories read), None), or
    (None, why): the campaign's claim refs on the tracker and every
    `## Repos` entry, through campaign-claim's readers. The watch's `claims`
    and the run's `retire` both read this. `repos`, a list, receives the
    repositories once `## Repos` reads, refs or not: the watch's pull
    requests need no refs."""
    listed, why = claim.campaign_repos(issue)
    if listed is None:
        return None, why
    repos = repos if repos is not None else []
    repos[:] = [claim.TRACKER] + [r for r in listed if r != claim.TRACKER]
    found, unread = claim.all_refs(repos, issue, slug)
    if unread:
        return None, "; ".join(unread)
    out = {}
    for b in found:
        n = claim.issue_of_branch(b, issue, slug)
        out[b] = int(n) if n else None
    return (out, repos), None


def deletion_of(repos, prefix):
    """((when or None, what was read), None), or (None, why): the latest
    DeleteEvent of a branch under `prefix` in the events feed of any of
    `repos`. The feed is newest first, so a repository's first hit is its
    latest and its later pages are not asked."""
    latest, read = None, []
    for repo in repos:
        seen = 0
        for page in range(1, EVENT_PAGES + 1):
            path = f"repos/{repo}/events?per_page=100&page={page}"
            r = run("gh", "api", path)
            if r.returncode != 0:
                return None, f"gh api {path}: {r.stderr.strip()[:160]}"
            try:
                events = json.loads(r.stdout or "[]")
            except ValueError as e:
                return None, f"gh api {path}: {e.__class__.__name__}"
            seen += len(events)
            hits = [e["created_at"] for e in events
                    if e.get("type") == "DeleteEvent"
                    and (e.get("payload") or {}).get("ref_type") == "branch"
                    and str(e["payload"].get("ref")).startswith(prefix)]
            if hits:
                top = max(hits, key=when)
                if latest is None or when(top) > when(latest):
                    latest = top
                break
            if len(events) < 100:
                break
        read.append(f"{repo} {seen} event(s)")
    return (latest, "; ".join(read)), None


def refs_reader(claims, slug):
    """A function from a sub-issue n to ((the `<slug>/<n>-` refs standing,
    when the last went or None, what was read), None) or (None, why), over
    `claims`, `claim_reading`'s answer. The feed is asked only when no ref
    stands."""
    def of(n):
        got, why = claims
        if got is None:
            return None, f"the refs not read: {why}"
        branches, repos = got
        prefix = f"{slug}/{n}-"
        read = f"{prefix}* on {', '.join(repos)}"
        standing = sorted(b for b, m in branches.items() if m == n)
        if standing:
            return (standing, None, read), None
        found, why = deletion_of(repos, prefix)
        if found is None:
            return None, f"{read}: no ref standing; the feed not read: {why}"
        return ([], found[0], f"{read}; the feed: {found[1]}"), None
    return of


def install_readings(rows, read_install, readable):
    """{`install <repo>`: (word, why)}, one source per install, so one that
    cannot be read fails alone and the others' drift still shows. Which words
    are a reading is campaign-installed's `readable`."""
    out = {}
    for repo, path, _ in rows:
        word, detail = read_install(repo, path)
        out[f"install {repo}"] = ((word, None) if readable(word)
                                  else (None, f"{word}: {detail}"))
    return out


def read_all(readers):
    """Every source's (value, why). A reader that raises is a why, never a
    crash of the watch -- but the watchdog's PollOverrun is no Exception, so
    it passes through to `run_watch`."""
    out = {}
    for source, fn in readers.items():
        try:
            out[source] = fn()
        except Exception as e:  # noqa: BLE001 -- counted, never raised
            out[source] = (None, f"{e.__class__.__name__}: {e}")
    return out


def watch_readers(issue, slug, own, claim, names, cache):
    """The shell half of the watch: one function per source returning its
    reading as (value, why), through the readers the heartbeat and
    campaign-claim already own. `## Repos` is read each poll with the
    claims, so a failed read is that source's why and a scope change shows."""
    tracker = load(BASE / "scripts" / "campaign-tracker.py", "campaign_tracker")
    installed = load(INSTALLED_SCRIPT, "campaign_installed")
    d = run(sys.executable, str(DIRECTORY_SCRIPT), issue)
    readme = Path(d.stdout.strip()) / "README.md" if d.returncode == 0 else None
    repos = []

    def sessions():
        rows, why = claim.herdr_sessions()
        if rows is None:
            return None, why
        out = {}
        for sid, row in rows.items():
            if names.campaign_of(row["name"]) != slug:
                continue
            st = "idle" if row["status"] in ("idle", "done") else row["status"]
            s = {"pane": row["pane"], "status": st, "context": None,
                 "banner": None}
            if st != "working":
                s["context"] = context_of(sid, cache)
                if row["pane"] != own:
                    b = limit_reset(row["pane"]).stdout.strip().splitlines()
                    s["banner"] = b[0] if b else "(no answer)"
            out[row["name"]] = s
        return out, None

    def claims():
        repos.clear()
        got, why = claim_reading(issue, slug, claim, repos)
        return (got[0] if got else None), why

    def issues():
        items, why = tracker.fetch_index(claim.TRACKER, issue)
        if items is None:
            return None, why
        return {i["number"]: (i["state"], any(
            lb.get("name") == tracker.BACKLOG_LABEL
            for lb in i.get("labels") or [])) for i in items}, None

    def prs():
        if not repos:
            return None, "the repositories were not read this poll (claims)"
        out = {}
        for repo in repos:
            r = run("gh", "pr", "list", "-R", repo, "--state", "all",
                    "--limit", "100", "--json",
                    "number,headRefName,state,headRefOid,comments,reviews")
            if r.returncode != 0:
                return None, f"gh pr list -R {repo}: {r.stderr.strip()[:160]}"
            for p in sorted(json.loads(r.stdout or "[]"),
                            key=lambda p: p["number"]):
                if p["headRefName"].startswith(f"{slug}/"):
                    out[p["headRefName"]] = (
                        p["number"], p["state"].lower(), p["headRefOid"][:7],
                        len(p.get("comments") or []) + len(p.get("reviews") or []))
        return out, None

    def installs():
        if readme is None:
            return None, f"campaign-directory {issue}: {d.stderr.strip()[:160]}"
        rows, why = installed.rows(readme)
        if rows is None:
            return None, why
        return install_readings(rows, installed.read_install,
                                installed.readable), None

    return {"sessions": sessions, "claims": claims, "issues": issues,
            "prs": prs, "installs": installs}


def watch_reader(issue, slug, own, claim, names, cache):
    """A function returning every source's reading as `Watch.poll` takes it,
    each install a source of its own."""
    readers = watch_readers(issue, slug, own, claim, names, cache)

    def read():
        out = read_all(readers)
        each, why = out.pop("installs")
        if why is not None:
            out["installs"] = (None, why)
            return out
        out.update(each)
        out["installs"] = (sorted(k[len("install "):] for k in each), None)
        return out
    return read


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("campaign_issue")
    ap.add_argument("--apply", action="store_true",
                    help="send the actions; without it nothing is sent")
    ap.add_argument("--watch", action="store_true",
                    help="poll until killed, printing what changed")
    ap.add_argument("--every", type=int, default=WATCH_EVERY,
                    help="seconds between the watch's polls")
    args = ap.parse_args(argv)
    issue = args.campaign_issue.lstrip("#")

    slug, why = slug_of(issue)
    if slug is None:
        print(f"could not read the slug: {why}")
        return 1
    claim = load(RELEASE_SCRIPT, "campaign_claim")
    names = load(HERE / "campaign-name-session.py", "cns")
    if args.watch:
        own = os.environ.get("HERDR_PANE_ID")
        return run_watch(Watch(slug, own),
                         watch_reader(issue, slug, own, claim, names, {}),
                         args.every)
    assign = load(ASSIGN_SCRIPT, "campaign_assign")
    sessions, why = claim.herdr_sessions()
    if sessions is None:
        print(f"could not list the sessions: {why}")
        return 1
    own = os.environ.get("HERDR_PANE_ID")
    ours = sorted(((row["pane"], sid, row) for sid, row in sessions.items()
                   if names.campaign_of(row["name"]) == slug))
    print(f"read {len(sessions)} session(s) from herdr agent list; "
          f"{len(ours)} of {slug} (#{issue}); own pane {own or 'unknown'}")
    got = read_all({
        "claims": lambda: claim_reading(issue, slug, claim),
        "issues": watch_readers(issue, slug, own, claim, names, {})["issues"]})
    claims = got["claims"]
    calm, what = quiet_reading(own, ([p for p, _, _ in ours], None),
                               (claims[0][0], None) if claims[0] else claims,
                               got["issues"])
    print(f"{'quiet' if calm else 'not quiet'} {slug}: {what}")
    refs = refs_reader(claims, slug)

    todo = []
    for pane, sid, row in ours:
        role = row["name"].split("-")[-2]
        is_own = pane == own
        banner = None
        if not is_own:
            r = limit_reset(pane)
            banner = (r.stdout.strip().splitlines() or ["(no answer)"])[0]
        reading, where, why = read_transcript(sid)
        word, reason = verdict(role, is_own, assign.idle_verdict(row),
                               banner, reading if reading else why, refs)
        if is_own and calm:
            word, reason = "quiet", f"{slug} has nothing left to do"
        print(f"{word} {pane} {row['name']}: {reason}")
        print(f"  read: herdr {row['status']}; transcript {where}"
              + ("; own pane, banner not read" if is_own
                 else f"; banner {banner}"))
        if word != "keep":
            todo.append((word, pane))

    failed = False
    fired = None
    for word, pane in todo:
        if word == "fire":
            if fired:
                print(f"fired already for {fired}: one wake per run, since "
                      f"every session shares one reset")
                continue
            fired = pane
            argv = fire_args(issue, pane, own or "<own pane>")
            if not args.apply:
                print(f"would run campaign-limit-reset.py {' '.join(argv)}")
                continue
            if not own:
                print(f"could not send the wake for {pane}: HERDR_PANE_ID "
                      f"is unset, so there is no pane to wake")
                failed = True
                continue
            r = limit_reset(*argv)
            print(r.stdout.rstrip())
            failed |= r.returncode != 0
            continue
        text = ACTIONS[word]
        if not args.apply:
            print(f"would send {text} to {pane}")
            continue
        r = run("herdr", "agent", "prompt", pane, text,
                env=dict(os.environ, HERDR_ENV="1"))
        if r.returncode != 0:
            print(f"could not send {text} to {pane}: herdr exited "
                  f"{r.returncode}: {r.stderr.strip()[:200]}")
            failed = True
        else:
            print(f"sent {text} to {pane}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
