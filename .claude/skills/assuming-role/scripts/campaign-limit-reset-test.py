#!/usr/bin/env python3
# witnesses: L1_PollIntoTheBannerGetsNoAnswer, L1b_PromptAfterTheResetIsAnswered
"""Prove campaign-limit-reset reads the banner off a pane, resolves its clock,
and fires one detached prompt after the reset -- and that each branch of it is
pinned by a named case.

The banner is read from FIXTURES captured off real stops (fixtures/), never
from a string this suite made up, because the shape being parsed is Claude
Code's and a fixture is the only evidence of it. The pane and the prompt go
through a fake `herdr` on PATH that records what it was asked; nothing here
drives a real pane. The allow side is tested as hard as the refuse side: a
`/usage` screen, prose about the limit, and an empty pane all read `no limit`.

Then EVERY BRANCH IS BROKEN IN TURN, on a copy of the script, and the case
named for it must go red -- a parser that returns a plausible time however
wrong it is proves less than a green suite usually does. A mutation that
survives, or whose anchor no longer matches, fails the suite by name.

Usage: .claude/skills/assuming-role/scripts/campaign-limit-reset-test.py
"""
import datetime as dt
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "campaign-limit-reset.py"
FIX = HERE / "fixtures"
SESSION = (FIX / "limit-banner-session.txt").read_text()
WEEKLY = (FIX / "limit-banner-weekly.txt").read_text()
NONE = (FIX / "no-banner.txt").read_text()
KST = dt.timezone(dt.timedelta(hours=9))

RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{(' -- ' + detail) if detail else ''}")


def load(script):
    """The script as a module, from its path, so a mutated copy loads too."""
    spec = importlib.util.spec_from_file_location(f"clr_{abs(hash(str(script)))}", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def at(y, mo, d, h, mi=0, tz=KST):
    return dt.datetime(y, mo, d, h, mi, tzinfo=tz)


def banner(kind, clause):
    """One banner line in the captured shape, with a made-up clause -- used only
    where no capture holds the shape, and said so in the case name."""
    return f"  ⎿  You've hit your {kind} limit · resets {clause}\n     /upgrade to increase your usage limit.\n"


# ---------------- the pure reading ----------------
# Each returns (ok, detail); `script` is the path of the copy under test.

def case_session_on_the_hour(script):
    got = load(script).reading(SESSION, at(2026, 9, 8, 18, 47))
    want = ("session", at(2026, 9, 8, 21, 0))
    return got == want, f"{got} != {want}"


def case_weekly_undated_is_todays(script):
    got = load(script).reading(WEEKLY, at(2026, 9, 8, 13, 0))
    want = ("weekly", at(2026, 9, 8, 22, 0))
    return got == want, f"{got} != {want}"


def case_last_banner_wins(script):
    # the weekly fixture holds a session banner above the weekly one
    got = load(script).reading(WEEKLY, at(2026, 9, 8, 13, 0))
    return got is not None and got[0] == "weekly", f"{got}"


def case_minutes_kept(script):
    got = load(script).reading(banner("session", "1:30am (Asia/Seoul)"), at(2026, 9, 8, 0, 10))
    want = ("session", at(2026, 9, 8, 1, 30))
    return got == want, f"{got} != {want}"


def case_session_wraps_to_tomorrow(script):
    got = load(script).reading(banner("session", "1:30am (Asia/Seoul)"), at(2026, 9, 8, 23, 0))
    want = ("session", at(2026, 9, 9, 1, 30))
    return got == want, f"{got} != {want}"


def case_session_passed(script):
    got = load(script).reading(SESSION, at(2026, 9, 8, 21, 30))
    want = ("passed", at(2026, 9, 8, 21, 0))
    return got == want, f"{got} != {want}"


def case_session_read_next_morning_is_yesterdays(script):
    got = load(script).reading(SESSION, at(2026, 9, 9, 3, 0))
    want = ("passed", at(2026, 9, 8, 21, 0))
    return got == want, f"{got} != {want}"


def case_weekly_passed(script):
    got = load(script).reading(WEEKLY, at(2026, 9, 8, 23, 0))
    want = ("passed", at(2026, 9, 8, 22, 0))
    return got == want, f"{got} != {want}"


def case_weekly_dated(script):
    got = load(script).reading(banner("weekly", "Sep 1 at 10pm (Asia/Seoul)"), at(2026, 8, 29, 10, 57))
    want = ("weekly", at(2026, 9, 1, 22, 0))
    return got == want, f"{got} != {want}"


def case_dated_december_read_in_january_has_passed(script):
    got = load(script).reading(banner("weekly", "Dec 30 at 10pm (Asia/Seoul)"), at(2027, 1, 2, 9, 0))
    want = ("passed", at(2026, 12, 30, 22, 0))
    return got == want, f"{got} != {want}"


def case_noon_and_midnight(script):
    mod = load(script)
    noon = mod.reading(banner("session", "12pm (Asia/Seoul)"), at(2026, 9, 8, 9, 0))
    midnight = mod.reading(banner("session", "12am (Asia/Seoul)"), at(2026, 9, 8, 22, 0))
    ok = noon == ("session", at(2026, 9, 8, 12, 0)) and midnight == ("session", at(2026, 9, 9, 0, 0))
    return ok, f"noon {noon}, midnight {midnight}"


def case_zone_from_banner_not_from_now(script):
    # now in UTC; the banner's zone decides which instant 9pm is
    got = load(script).reading(SESSION, at(2026, 9, 8, 9, 47, tz=dt.timezone.utc))
    want = ("session", at(2026, 9, 8, 21, 0))
    return got == want and got[1].utcoffset() == dt.timedelta(hours=9), f"{got} != {want}"


def case_no_zone_takes_nows(script):
    # one real capture read `resets 1:10am` with no parenthesis
    got = load(script).reading(banner("session", "1:10am"), at(2026, 9, 8, 0, 55))
    want = ("session", at(2026, 9, 8, 1, 10))
    return got == want, f"{got} != {want}"


def case_unknown_zone_is_unparsed(script):
    mod = load(script)
    try:
        got = mod.reading(banner("session", "9pm (Mars/Olympus)"), at(2026, 9, 8, 18, 0))
    except mod.Unparsed:
        return True, ""
    return False, f"returned {got}"


def case_unknown_clause_is_unparsed(script):
    mod = load(script)
    try:
        got = mod.reading("  ⎿  You've hit your session limit · resets soon\n", at(2026, 9, 8, 18, 0))
    except mod.Unparsed:
        return True, ""
    return False, f"returned {got}"


def case_allow_no_banner(script):
    mod = load(script)
    usage = ("Current session: 92% used · resets Sep 7 at 1:30am (Asia/Seoul)\n"
             "Current week (all models): 72% used · resets Sep 8 at 10pm (Asia/Seoul)\n")
    prose = "the limit banner names the reset; a session at its usage limit is idle\n"
    got = [mod.reading(t, at(2026, 9, 8, 18, 0)) for t in (NONE, usage, prose, "")]
    return got == [None] * 4, f"{got}"


# ---------------- the command, through a fake herdr ----------------

FAKE = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_LOG"
[ -n "$FAKE_STDERR" ] && echo "$FAKE_STDERR" >&2
case "$1 $2" in
  "pane read") cat "$FAKE_SCREEN" ;;
  "agent prompt") echo '{"ok":true}' ;;
esac
exit ${FAKE_EXIT:-0}
"""


def run(script, args, screen, env=None, herdr=True):
    """(stdout, exit, asked) -- `asked` is every argv the fake herdr saw."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "bin").mkdir()
        if herdr:
            (d / "bin" / "herdr").write_text(FAKE)
            (d / "bin" / "herdr").chmod(0o755)
        (d / "screen.txt").write_text(screen)
        log = d / "asked.txt"
        e = {"PATH": f"{d / 'bin'}:/usr/bin:/bin", "FAKE_LOG": str(log),
             "FAKE_SCREEN": str(d / "screen.txt"), "HOME": os.environ.get("HOME", "/")}
        e.update(env or {})
        out = subprocess.run([sys.executable, str(script), *args],
                             capture_output=True, text=True, env=e)
        asked = log.read_text().splitlines() if log.exists() else []
        return out.stdout + out.stderr, out.returncode, asked


def case_cli_reads_the_pane(script):
    out, code, asked = run(script, ["w40:p1", "--now", "2026-09-08T18:47+09:00"], SESSION)
    ok = (out.startswith("session 2026-09-08T21:00+09:00") and code == 0
          and any(a.startswith("pane read w40:p1 ") and "--source recent-unwrapped" in a for a in asked))
    return ok, f"{out!r} exit {code} asked {asked}"


def case_cli_no_limit(script):
    out, code, _ = run(script, ["w40:p1"], NONE)
    return out.strip() == "no limit" and code == 0, f"{out!r} exit {code}"


def case_cli_herdr_missing(script):
    out, code, _ = run(script, ["w40:p1"], SESSION, herdr=False)
    return out.startswith("could not read: herdr is not installed") and code == 1, f"{out!r} exit {code}"


def case_cli_herdr_refuses(script):
    out, code, _ = run(script, ["w40:p9"], SESSION, env={"FAKE_EXIT": "2", "FAKE_STDERR": "no such pane"})
    want = "could not read: herdr pane read w40:p9 exited 2: no such pane"
    return out.strip() == want and code == 1, f"{out!r} exit {code}"


def case_cli_unparsed_is_could_not_read(script):
    out, code, _ = run(script, ["w40:p1"], "  ⎿  You've hit your session limit · resets soon\n")
    return out.startswith("could not read: a banner is on screen") and code == 1, f"{out!r} exit {code}"


def case_fire_refused_without_herdr_env(script):
    out, code, asked = run(script, ["w40:p1", "--fire", "w40:p7", "--now", "2026-09-08T21:30+09:00"], SESSION)
    prompted = [a for a in asked if a.startswith("agent prompt")]
    ok = "could not fire: HERDR_ENV is not 1" in out and code == 1 and not prompted
    return ok, f"{out!r} exit {code} prompted {prompted}"


def case_fire_refused_on_no_banner(script):
    out, code, asked = run(script, ["w40:p1", "--fire", "w40:p7"], NONE, env={"HERDR_ENV": "1"})
    prompted = [a for a in asked if a.startswith("agent prompt")]
    ok = "could not fire: no banner on w40:p1" in out and code == 1 and not prompted
    return ok, f"{out!r} exit {code} prompted {prompted}"


def case_fire_passed_prompts_now(script):
    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "sleeper.log"
        out, code, _ = run(script, ["w40:p1", "--fire", "w40:p7", "--text", "wake up",
                                    "--log", str(log), "--now", "2026-09-08T21:30+09:00"],
                           SESSION, env={"HERDR_ENV": "1"})
        # the fake herdr on PATH is gone with run()'s temp dir; the sleeper
        # with delay 0 has already called it by the time run() returns, or
        # within a moment -- give it one
        for _ in range(40):
            if log.exists() and "agent prompt" in log.read_text():
                break
            time.sleep(0.05)
        text = log.read_text() if log.exists() else ""
    ok = ("passed 2026-09-08T21:00+09:00" in out and "scheduled pid " in out
          and " at 2026-09-08T21:30+09:00 into w40:p7: wake up" in out and code == 0)
    return ok, f"{out!r} exit {code} log {text!r}"


def case_fire_ahead_sleeps_until_lead(script):
    out, code, asked = run(script, ["w40:p1", "--fire", "w40:p7", "--now", "2026-09-08T18:47+09:00"],
                           SESSION, env={"HERDR_ENV": "1"})
    pid = None
    for line in out.splitlines():
        if line.startswith("scheduled pid "):
            pid = int(line.split()[2])
    alive = False
    if pid:
        try:
            os.kill(pid, 0)
            alive = True
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            pass
    prompted = [a for a in asked if a.startswith("agent prompt")]
    ok = (" at 2026-09-08T21:01+09:00 into w40:p7: The usage window reset at 2026-09-08T21:00+09:00" in out
          and code == 0 and alive and not prompted)
    return ok, f"{out!r} exit {code} alive {alive} prompted {prompted}"


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]

# ---------------- each branch broken in turn ----------------
# (what is broken, anchor in the script, its replacement, the case that must go red)
MUTATIONS = [
    ("the weekly kind", "(?P<kind>session|weekly)", "(?P<kind>session|weekl)", case_weekly_undated_is_todays),
    ("pm adds twelve", '(12 if ampm == "pm" else 0)', "0", case_session_on_the_hour),
    ("twelve o'clock wraps", 'int(m.group("hour")) % 12', 'int(m.group("hour"))', case_noon_and_midnight),
    ("the minutes", 'int(m.group("minute") or 0)', "0", case_minutes_kept),
    ("the banner's zone", "tz = ZoneInfo(zone)", "tz = now.tzinfo", case_zone_from_banner_not_from_now),
    ("the unknown zone", 'raise Unparsed(f"zone {zone!r} is not one this machine knows")', "pass",
     case_unknown_zone_is_unparsed),
    ("the nearest year", "when = min(years, key=lambda w: abs(w - now))", "when = at",
     case_dated_december_read_in_january_has_passed),
    ("the day within the window", "for d in (-1, 0, 1)]\n            ahead", "for d in (0,)]\n            ahead",
     case_session_wraps_to_tomorrow),
    ("yesterday's reset", "max(w for w in days if w <= now)", "at", case_session_read_next_morning_is_yesterdays),
    ("passed", '"passed" if when <= now else', '"passed" if False else', case_session_passed),
    ("the last banner", "resolve(matches[-1], now)", "resolve(matches[0], now)", case_last_banner_wins),
    ("the unknown clause", "if BANNER_WORDS in text:", "if False:", case_unknown_clause_is_unparsed),
    ("herdr missing", 'return None, "herdr is not installed"', "return '', None", case_cli_herdr_missing),
    ("herdr's exit", "if out.returncode != 0:", "if False:", case_cli_herdr_refuses),
    ("could not read's status", 'print(f"could not read: {e}")\n        return 1', 'print(f"could not read: {e}")\n        return 0',
     case_cli_unparsed_is_could_not_read),
    ("the HERDR_ENV guard", 'os.environ.get("HERDR_ENV") != "1"', 'os.environ.get("HERDR_ENV") == "1"',
     case_fire_refused_without_herdr_env),
    ("no banner fires nothing", "if a.fire:\n            print", "if False:\n            print", case_fire_refused_on_no_banner),
    ("now for a passed reset", 'now if kind == "passed" else when + LEAD', "when + LEAD", case_fire_passed_prompts_now),
    ("the lead minute", 'now if kind == "passed" else when + LEAD', 'now if kind == "passed" else when',
     case_fire_ahead_sleeps_until_lead),
]


def mutated(name, old, new):
    """A copy of the script with one anchor replaced; None when the anchor is
    not exactly once in it."""
    src = SCRIPT.read_text()
    if src.count(old) != 1:
        return None
    d = Path(tempfile.mkdtemp(prefix="clr-mut-"))
    copy = d / SCRIPT.name
    copy.write_text(src.replace(old, new))
    copy.chmod(0o755)
    return copy


def main():
    for case in CASES:
        ok, detail = case(SCRIPT)
        check(case.__name__, ok, detail)
    for what, old, new, case in MUTATIONS:
        copy = mutated(what, old, new)
        name = f"mutation: {what} broken -> {case.__name__} goes red"
        if copy is None:
            check(name, False, f"anchor not found exactly once: {old!r}")
            continue
        try:
            ok, _ = case(copy)
        except Exception as e:  # a crash is a failure of the case, which is what is wanted
            ok = False
            _ = repr(e)
        finally:
            shutil.rmtree(copy.parent, ignore_errors=True)
        check(name, not ok, "the case stayed green")
    n_cases, n_mut = len(CASES), len(MUTATIONS)
    print(f"campaign-limit-reset-test: {len(RAN)} ran ({n_cases} cases, {n_mut} mutations), "
          f"{len(FAILED)} failed, script {SCRIPT}")
    for f in FAILED:
        print(f"  FAIL {f}")
    return 1 if FAILED or len(RAN) != n_cases + n_mut else 0


if __name__ == "__main__":
    sys.exit(main())
