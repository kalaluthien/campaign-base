#!/usr/bin/env python3
"""Read a pane's usage-limit banner, say when the window resets, and fire one prompt after it.

    scripts/campaign-limit-reset.py <pane> [--now <iso>]
    scripts/campaign-limit-reset.py <pane> --fire <wake-pane> [--text <prompt>] [--log <path>]

WHAT IT ANSWERS. One line on stdout, a word first, and the caller reads the
word and never the status:

    session <iso>   the pane sits at a session-limit banner; the window resets at <iso>
    weekly <iso>    the same for the weekly limit
    passed <iso>    a banner whose reset is already behind now -- the pane stopped
                    and nothing has prompted it since, so the wake is due now
    no limit        the pane was read and its recent screen holds no banner
    could not read: <why>   herdr is not installed, the pane is not one herdr
                    can read, or a banner is on screen whose clause this
                    parser does not know

    exit 0   a reading was made -- any of the first four -- and, with --fire,
             the sleeper was spawned
    exit 1   could not read, or could not fire

THE BANNER, as Claude Code paints it on the pane. Captured from #244's stops
on 2026-09-08 (fixtures/limit-banner-*.txt are those screens):

    ⎿  You've hit your session limit · resets 9pm (Asia/Seoul)
       /upgrade to increase your usage limit.

The clause is `resets <time>` for a reset on the day it was painted and
`resets <Mon> <d> at <time>` for a later day, which is the weekly limit's
shape; the minutes drop on the hour, so `9pm` and `1:30am` are both seen. The
zone is the account's, in parentheses; one capture carried none, so it is
optional and the local zone stands in. The LAST banner on the screen is the
reading, since a pane that stopped twice shows both.

RESOLVING A CLOCK TIME, because the banner carries no date and the reader
does not know when it was painted. A session window is five hours
(planner.md § The planner's clock), so a session reset is never more than
five hours after the stop -- `WINDOW`. Of the clock time's three nearest
days, the one within five hours ahead of now is the reset; when none is, the
most recent one behind now is, and the reading is `passed`. So `1:30am` read
at 23:00 is tomorrow's, `9pm` read at 21:30 has passed, and `9pm` read at
03:00 is yesterday's and passed. An undated WEEKLY clause is today's, ahead or
passed by the clock; painted before midnight and read after it, it reads a
day ahead, which the screen does not carry enough to tell. A dated clause
takes the nearest of three years, so a December banner read in January has
passed rather than being eleven months ahead.

--fire <wake-pane> SCHEDULES THE ONE-SHOT: a detached
`sleep <seconds>; herdr agent prompt <wake-pane> <text>` under its own
session, so it outlives this process and the session that ran it -- the
session that reads a banner is on the same account and stops on the same
limit a turn later, which is why a cron in that session cannot do this. The
prompt goes in at the reset plus `LEAD`, one minute, since the reset is a
clock the server rounds; for a `passed` reading it goes in now. It prints
`scheduled pid <n> at <iso> into <wake-pane>: <text>` and the log path, and
the log is where herdr's own answer lands: a prompt into a working pane is
queued by the harness, one into a pane at a dialog is refused as
agent_blocked, and this process is gone by then, so the caller reads the log.
It drives a pane, so it is refused (`could not fire: ...`, exit 1) unless
HERDR_ENV is 1 (AGENTS.md § Delegate launch) -- the target is explicit by
construction, there is no default. A `no limit` reading fires nothing:
there is no reset to wait for.

--now <iso> is the clock, for the suite and for a screen captured earlier;
default is now, in the local zone.
"""
import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover -- python < 3.9 has no zoneinfo
    ZoneInfo = None

BANNER = re.compile(
    r"hit your (?P<kind>session|weekly) limit\W+resets\s+"
    r"(?:(?P<mon>[A-Za-z]{3})\s+(?P<day>\d{1,2})\s+at\s+)?"
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)"
    r"(?:\s*\((?P<zone>[^)]+)\))?",
    re.IGNORECASE)
# The words every banner carries, whatever its clause: a screen holding them
# and matching nothing above holds a shape this parser does not know.
BANNER_WORDS = "hit your"
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


def resolve(m, now):
    """(kind, when) for one banner match, against `now`. Pure. Raises Unparsed."""
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
    """(kind, when) for the last banner on the screen, or None for none. Pure.
    Raises Unparsed when a banner is on screen and its clause is not known."""
    matches = list(BANNER.finditer(text))
    if not matches:
        if BANNER_WORDS in text:
            raise Unparsed("a banner is on screen and its clause is not one this parser knows")
        return None
    return resolve(matches[-1], now)


def iso(when):
    return when.isoformat(timespec="minutes")


def fire(kind, when, wake_pane, text, log, now):
    """Spawn the detached sleeper. (line, None), or (None, why)."""
    if os.environ.get("HERDR_ENV") != "1":
        return None, "HERDR_ENV is not 1, and --fire drives a pane"
    at = now if kind == "passed" else when + LEAD
    delay = max(0, int((at - now).total_seconds()))
    if text is None:
        text = (f"The usage window reset at {iso(when)}: read every worker's pane "
                "and resume each one stopped at the banner.")
    if log is None:
        fd, log = tempfile.mkstemp(prefix="campaign-limit-reset-", suffix=".log")
        os.close(fd)
    try:
        with open(log, "ab") as fh:
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
    p.add_argument("--now", help="the clock, ISO 8601 with offset; default now")
    p.add_argument("--fire", metavar="WAKE_PANE",
                   help="prompt this pane one minute after the reset, detached")
    p.add_argument("--text", help="the prompt --fire sends; default names the reset")
    p.add_argument("--log", help="where the sleeper writes; default a temp file")
    a = p.parse_args(argv)
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now().astimezone()
    if now.tzinfo is None:
        now = now.astimezone()

    text, why = read_pane(a.pane)
    if why:
        print(f"could not read: {why}")
        return 1
    try:
        got = reading(text, now)
    except Unparsed as e:
        print(f"could not read: {e}")
        return 1
    if got is None:
        print("no limit")
        if a.fire:
            print(f"could not fire: no banner on {a.pane}")
            return 1
        return 0
    kind, when = got
    print(f"{kind} {iso(when)}")
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
