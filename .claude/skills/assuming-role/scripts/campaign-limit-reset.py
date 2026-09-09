#!/usr/bin/env python3
"""Read a pane's usage-limit banner, say when the window resets, and fire one prompt after it.

    .claude/skills/assuming-role/scripts/campaign-limit-reset.py <pane> [--now <iso>]
    .claude/skills/assuming-role/scripts/campaign-limit-reset.py <pane> --fire <wake-pane> [--text <prompt>] [--log <path>]

WHAT IT ANSWERS. One line on stdout, a word first, and the caller reads the
word and never the status:

    session <iso>   the pane sits at a session-limit banner; the window resets at <iso>
    weekly <iso>    the same for the weekly limit
    passed <iso>    a banner whose reset is already behind now, with no prompt
                    entered since: the wake is due now
    no limit        the pane was read and no banner stands on it -- none at all,
                    or one on a pane herdr lists as working, which a stopped
                    pane is not; the line says which
    could not read: <why>   herdr is not installed, the pane is not one herdr
                    can read, --now is not a clock, or a banner is on screen
                    whose clause this parser does not know

    exit 0   a reading was made -- any of the first four -- and, with --fire,
             the sleeper was spawned
    exit 1   could not read, or could not fire

THE BANNER, as Claude Code paints it on the pane. Captured from #244's stops
on 2026-09-08 (fixtures/limit-banner-*.txt are those screens):

    ⎿  You've hit your session limit · resets 9pm (Asia/Seoul)
       /upgrade to increase your usage limit.

Only a line that OPENS with the `⎿` glyph is a banner: the same words quoted
in prose, in a NOTE, or in a diff a pane is showing are not, and read
`no limit`. That glyph is the tool-result column, and every stop captured so
far was painted in it; a banner painted in some other column has no evidence
behind it and reads `no limit` too, unremarked. A screen displaying a capture
of the banner itself -- a `cat` of a fixture, or of this file -- is
indistinguishable from the banner, and reads as one. The clause is
`resets <time>` for a reset on the day it was painted and
`resets <Mon> <d> at <time>` for a later day, which the weekly limit
paints; the minutes drop on the hour, so `9pm` and `1:30am` are both seen.
The zone is the account's, in parentheses; one stop was recorded without
it, so it is
optional and the local zone stands in. The LAST banner on the screen is the
reading, since a pane that stopped twice shows both.

A BANNER STAYS ON SCREEN AFTER THE PANE IS WOKEN, so the screen alone cannot
say whether it still stands. What can is herdr's liveness, read through
campaign-name-session.py's `pane_status` so this file adds no reader of the
listing: a pane listed `working` is mid-turn, which a pane stopped at the
banner is not (AGENTS.md § Watching and retiring: a limit menu reports
`idle`), so its banner is stale and reads `no limit`, and the line says so.
Any other status, and a listing that cannot be read, leaves the banner
standing and the line says what was read -- the reading errs toward the
wake, since a prompt into a free pane costs one turn and a wake never sent
costs the whole window. Two things the status cannot separate: the seconds
of the aborting turn in which the banner is painted, and THE READER'S OWN
PANE, which is working for as long as the reader runs -- so a pane equal to
`HERDR_PANE_ID` skips the liveness reading and its banner stands. That
variable is the id the pane had at launch; a pane moved to another
workspace gets a new id and keeps the old one in its environment, and such
a pane's own read falls through to the liveness reading. The cheap key is
still the right one here: `campaign-claim.py live`'s join answers whose
claim a session holds, a different question, and this needs only "is this
me". The screen's own `❯` lines say nothing here: a queued command, a paste, and
text typed but not sent all paint one.

RESOLVING A CLOCK TIME, because the banner carries no date and the reader
does not know when it was painted. A session window is five hours
(planner.md § The planner's clock), so a session reset is never more than
five hours after the stop -- `WINDOW`. Of the clock time's three nearest
days, the one within five hours ahead of now is the reset; when none is, the
most recent one behind now is, and the reading is `passed`. So `1:30am` read
at 23:00 is tomorrow's, `9pm` read at 21:30 has passed, and `9pm` read at
03:00 is yesterday's and passed. The rule errs LATE and never early, with
one exception below: a banner painted a day ago whose clock time is ahead of
now reads as today's, which wakes a pane that is already free an hour or so
late, and a `passed` reading always names a reset that has really passed.
An undated WEEKLY clause is today's, ahead or passed by the clock, and a
weekly banner stands for days: painted on an earlier day it reads a reset
later than the real one -- again late, never into a pane still stopped,
since a weekly reset on an
earlier day has passed. A dated clause takes the nearest of three years, so
a December banner read in January has passed rather than being eleven months
ahead. The exception: in the one fall-back hour of a zone that observes it
the earlier of the two wall clocks is taken, up to an hour early.

--fire <wake-pane> SCHEDULES THE ONE-SHOT: a detached
`sleep <seconds>; herdr agent prompt <wake-pane> <text>` under its own
session, so it outlives this process and the session that ran it -- the
session that reads a banner is on the same account and stops on the same
limit a turn later, which is why a cron in that session cannot do this. The
prompt goes in at the reset plus `LEAD`, one minute, since the reset is a
clock the server rounds; for a `passed` reading it goes in now. It prints
`scheduled pid <n> at <iso> into <wake-pane>: <text>` and the log path. The
log takes this run's own marker line first, `== <now> at <iso> into
<wake-pane>: <text>`, written and flushed before the sleeper is spawned so
nothing of the sleeper's can land above it, and herdr's answer follows: a
prompt into a working pane is queued by the harness, one into a pane at a
dialog is refused as agent_blocked, and this process is gone by then, so
the caller reads the log under the marker. It drives a pane, so it is
refused
(`could not fire: ...`, exit 1) unless HERDR_ENV is 1 (AGENTS.md § Delegate
launch); the target is explicit by construction, there is no default. A
`no limit` reading fires nothing: there is no reset to wait for.

--now <iso> is the clock, for the suite and for reading a screen captured
earlier; default is now, in the local zone, and a clock with no offset is
local. The sleeper's delay is measured from that clock too, so `--fire` with
`--now` lands off by however stale the clock is: a planner passes neither.
"""
import argparse
import datetime as dt
import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from importlib.machinery import SourceFileLoader

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover -- python < 3.9 has no zoneinfo
    ZoneInfo = None

# A banner line: the glyph the harness paints a tool-result line with, then the words.
SHAPE = re.compile(r"^[ \t]*⎿[ \t]+You.ve hit your (?P<rest>.*)$", re.MULTILINE)
CLAUSE = re.compile(
    r"^(?P<kind>session|weekly) limit\W+resets\s+"
    r"(?:(?P<mon>[A-Za-z]{3})\s+(?P<day>\d{1,2})\s+at\s+)?"
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)"
    r"(?:\s*\((?P<zone>[^)]+)\))?",
    re.IGNORECASE)
MONTHS = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
# A session window is five hours, so its reset is at most five hours after the stop.
WINDOW = dt.timedelta(hours=5)
# The prompt lands a minute after the reset the banner names.
LEAD = dt.timedelta(minutes=1)
# How far back the screen is read: a stopped pane paints little after the banner.
LINES = "200"


class Unparsed(Exception):
    """A banner is on screen and its clause could not be resolved."""


def read_pane(pane):
    """(text, None) from `herdr pane read`, or (None, why)."""
    argv = ["herdr", "pane", "read", pane, "--source", "recent-unwrapped",
            "--lines", LINES, "--format", "text"]
    try:
        out = subprocess.run(argv, capture_output=True, text=True)
    except FileNotFoundError:
        return None, "herdr is not installed"
    if out.returncode != 0:
        why = (out.stderr.strip() or out.stdout.strip() or "no message").splitlines()[0]
        return None, f"herdr pane read {pane} exited {out.returncode}: {why}"
    return out.stdout, None


def pane_status(pane):
    """(agent_status, None) or (None, why), by campaign-name-session.py's
    reader of `herdr agent list`, loaded by path so this file is not a second
    reader of that listing."""
    sibling = pathlib.Path(__file__).resolve().parent / "campaign-name-session.py"
    try:
        spec = importlib.util.spec_from_loader("cns", SourceFileLoader("cns", str(sibling)))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.pane_status(pane)
    except Exception as e:  # noqa: BLE001 -- a reading not made, said so, with what failed
        return None, f"could not read the listing ({e.__class__.__name__}: {e})"


def resolve(m, now):
    """(kind, when) for one clause match, against `now`. Pure. Raises Unparsed."""
    zone = m.group("zone")
    tz = now.tzinfo
    if zone:
        try:
            tz = ZoneInfo(zone)
        except Exception:
            raise Unparsed(f"zone {zone!r} is not one this machine knows")
    ampm = m.group("ampm").lower()
    hour = int(m.group("hour")) % 12 + (12 if ampm == "pm" else 0)
    minute = int(m.group("minute") or 0)
    local = now.astimezone(tz)
    try:
        at = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if m.group("mon"):
            mon = MONTHS.get(m.group("mon").lower())
            if mon is None:
                raise Unparsed(f"month {m.group('mon')!r} is not one")
            at = at.replace(month=mon, day=int(m.group("day")))
            years = [at.replace(year=at.year + d) for d in (-1, 0, 1)]
            when = min(years, key=lambda w: abs(w - now))
        elif m.group("kind").lower() == "session":
            days = [at + dt.timedelta(days=d) for d in (-1, 0, 1)]
            ahead = [w for w in days if now < w <= now + WINDOW]
            when = ahead[0] if ahead else max(w for w in days if w <= now)
        else:
            when = at
    except ValueError as e:
        raise Unparsed(str(e))
    kind = "passed" if when <= now else m.group("kind").lower()
    return kind, when


def reading(text, now):
    """(kind, when) for the banner standing on the screen, or None for none.
    Pure. Raises Unparsed when a banner is on screen and its clause is not known."""
    banners = list(SHAPE.finditer(text))
    if not banners:
        return None
    last = banners[-1]
    clause = CLAUSE.match(last.group("rest"))
    if not clause:
        raise Unparsed("a banner is on screen and its clause is not one this parser knows")
    return resolve(clause, now)


def iso(when):
    return when.isoformat(timespec="minutes")


def clock(text):
    """(now, None) from --now, or (None, why). Default the local clock."""
    if text is None:
        return dt.datetime.now().astimezone(), None
    try:
        now = dt.datetime.fromisoformat(text)
    except ValueError:
        return None, f"--now {text!r} is not ISO 8601"
    if now.tzinfo is None:
        now = now.astimezone()
    return now, None


def fire(kind, when, wake_pane, text, log, now):
    """Spawn the detached sleeper. (line, None), or (None, why)."""
    if os.environ.get("HERDR_ENV") != "1":
        return None, "HERDR_ENV is not 1, and --fire drives a pane"
    at = now if kind == "passed" else when + LEAD
    delay = int((at - now).total_seconds())
    if text is None:
        text = (f"The usage window reset at {iso(when)}: read every worker's pane "
                "and resume each one stopped at the banner.")
    if log is None:
        fd, log = tempfile.mkstemp(prefix="campaign-limit-reset-", suffix=".log")
        os.close(fd)
    try:
        with open(log, "ab") as fh:
            fh.write(f"== {iso(now)} at {iso(at)} into {wake_pane}: {text}\n".encode())
            fh.flush()
            proc = subprocess.Popen(
                ["sh", "-c", 'sleep "$0" && exec herdr agent prompt "$1" "$2"',
                 str(delay), wake_pane, text],
                stdin=subprocess.DEVNULL, stdout=fh, stderr=fh,
                start_new_session=True)
    except OSError as e:
        return None, f"the sleeper could not be spawned: {e}"
    return (f"scheduled pid {proc.pid} at {iso(at)} into {wake_pane}: {text}\n"
            f"  log {log}"), None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("pane", help="the pane to read the banner from")
    p.add_argument("--now", help="the clock, ISO 8601; default now, no offset means local")
    p.add_argument("--fire", metavar="WAKE_PANE",
                   help="prompt this pane one minute after the reset, detached")
    p.add_argument("--text", help="the prompt --fire sends; default names the reset")
    p.add_argument("--log", help="where the sleeper writes; default a temp file")
    a = p.parse_args(argv)
    now, why = clock(a.now)
    if why:
        print(f"could not read: {why}")
        return 1
    text, why = read_pane(a.pane)
    if why:
        print(f"could not read: {why}")
        return 1
    try:
        got = reading(text, now)
    except Unparsed as e:
        print(f"could not read: {e}")
        return 1
    note = ""
    if got is not None:
        if a.pane == os.environ.get("HERDR_PANE_ID"):
            note = " (own pane: its liveness is unread, this session is working)"
        else:
            status, why = pane_status(a.pane)
            if status == "working":
                got, note = None, f" (a banner stands, and herdr lists {a.pane} working: stale)"
            elif status:
                note = f" (herdr lists {a.pane} {status})"
            else:
                note = f" (liveness unread: {why})"
    if got is None:
        print("no limit" + note)
        if a.fire:
            print(f"could not fire: no banner on {a.pane}")
            return 1
        return 0
    kind, when = got
    print(f"{kind} {iso(when)}{note}")
    if not a.fire:
        return 0
    line, why = fire(kind, when, a.fire, a.text, a.log, now)
    if why:
        print(f"could not fire: {why}")
        return 1
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
