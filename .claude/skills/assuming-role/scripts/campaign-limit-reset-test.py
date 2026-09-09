#!/usr/bin/env python3
# witnesses: L1_PollIntoTheBannerGetsNoAnswer, L1b_PromptAfterTheResetIsAnswered
"""Prove campaign-limit-reset reads the banner off a pane, resolves its clock,
and fires one detached prompt after the reset -- and that each branch of it is
pinned by a named case.

The banner's SHAPE is read from fixtures captured off real stops (fixtures/):
a made-up screen would prove only that the parser reads what its author
imagined. Where a case needs a clause no screen capture holds, `banner()`
builds one line in the captured shape and its docstring says which real
records the clause was seen in. The pane and the prompt go through a fake
`herdr` on PATH that records what it was asked; nothing here drives a real
pane. The allow side is tested as hard as the refuse side: a `/usage` screen,
prose quoting the banner, an added diff line showing it, an empty pane, and
a banner on a pane herdr lists as working all read `no limit`.

Then EVERY BRANCH IS BROKEN IN TURN, on a copy of the script, and the case
named for it must go red BY ITS OWN ASSERTION -- a parser that returns a
plausible time however wrong it is proves less than a green suite usually
does, and a case that goes red by crashing has asserted nothing. `read`
hands a case the script's own `Unparsed` as a value, since raising it is the
script's designed answer, and lets any other exception through to the
harness, where it fails the mutation by name rather than counting as red.

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
# the weekly capture cut at its second banner: a pane that was woken after its
# first banner and went back to work -- a real screen, not a composed one. Its
# banner still stands on the screen; only herdr's liveness says it is stale.
WOKEN_SCREEN = WEEKLY[:WEEKLY.index("You've hit your weekly")].rsplit("\n", 1)[0] + "\n"
KST = dt.timezone(dt.timedelta(hours=9))

RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{(' -- ' + detail) if detail else ''}")


LOADED = {}


def load(script):
    """The script as a module, from its path, so a mutated copy loads too;
    once per path, so a case's `mod.Unparsed` is the class `read` raised."""
    if script not in LOADED:
        spec = importlib.util.spec_from_file_location(f"clr_{len(LOADED)}", script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        LOADED[script] = mod
    return LOADED[script]


def read(script, text, now):
    """What `reading` returned, or the `Unparsed` it raised -- the script's
    designed answer, handed to the case as a value. Anything else raised is a
    crash and propagates."""
    mod = load(script)
    try:
        return mod.reading(text, now)
    except mod.Unparsed as e:
        return e


def at(y, mo, d, h, mi=0, tz=KST):
    return dt.datetime(y, mo, d, h, mi, tzinfo=tz)


def banner(kind, clause):
    """One banner in the captured shape with a clause no screen capture holds.
    The clauses used below were each seen in a real stop's transcript record
    (the API's own text, `You've hit your … limit · resets …`): `1:30am`
    2026-09-08, `Sep 1 at 10pm (Asia/Seoul)` 2026-08-29, `1:10am` with no
    zone 2026-08-27, `12am`/`12pm` and `Dec 30 at 10pm` not seen -- those two
    are the parser's own edge and year rule, on the shape's grammar."""
    return f"  ⎿  You've hit your {kind} limit · resets {clause}\n     /upgrade to increase your usage limit.\n"


# ---------------- the pure reading ----------------
# Each returns (ok, detail); `script` is the path of the copy under test.

def case_session_on_the_hour(script):
    got = read(script, SESSION, at(2026, 9, 8, 18, 47))
    want = ("session", at(2026, 9, 8, 21, 0))
    return got == want, f"{got} != {want}"


def case_weekly_undated_is_todays(script):
    got = read(script, WEEKLY, at(2026, 9, 8, 13, 0))
    want = ("weekly", at(2026, 9, 8, 22, 0))
    return got == want, f"{got} != {want}"


def case_last_banner_wins(script):
    # the weekly fixture holds a session banner above the weekly one
    got = read(script, WEEKLY, at(2026, 9, 8, 13, 0))
    return isinstance(got, tuple) and got[0] == "weekly", f"{got}"


def case_minutes_kept(script):
    got = read(script, banner("session", "1:30am (Asia/Seoul)"), at(2026, 9, 8, 0, 10))
    want = ("session", at(2026, 9, 8, 1, 30))
    return got == want, f"{got} != {want}"


def case_session_wraps_to_tomorrow(script):
    got = read(script, banner("session", "1:30am (Asia/Seoul)"), at(2026, 9, 8, 23, 0))
    want = ("session", at(2026, 9, 9, 1, 30))
    return got == want, f"{got} != {want}"


def case_session_passed(script):
    got = read(script, SESSION, at(2026, 9, 8, 21, 30))
    want = ("passed", at(2026, 9, 8, 21, 0))
    return got == want, f"{got} != {want}"


def case_session_read_next_morning_is_yesterdays(script):
    got = read(script, SESSION, at(2026, 9, 9, 3, 0))
    want = ("passed", at(2026, 9, 8, 21, 0))
    return got == want, f"{got} != {want}"


def case_weekly_passed(script):
    got = read(script, WEEKLY, at(2026, 9, 8, 23, 0))
    want = ("passed", at(2026, 9, 8, 22, 0))
    return got == want, f"{got} != {want}"


def case_weekly_dated(script):
    got = read(script, banner("weekly", "Sep 1 at 10pm (Asia/Seoul)"), at(2026, 8, 29, 10, 57))
    want = ("weekly", at(2026, 9, 1, 22, 0))
    return got == want, f"{got} != {want}"


def case_dated_december_read_in_january_has_passed(script):
    got = read(script, banner("weekly", "Dec 30 at 10pm (Asia/Seoul)"), at(2027, 1, 2, 9, 0))
    want = ("passed", at(2026, 12, 30, 22, 0))
    return got == want, f"{got} != {want}"


def case_noon_and_midnight(script):
    noon = read(script, banner("session", "12pm (Asia/Seoul)"), at(2026, 9, 8, 9, 0))
    midnight = read(script, banner("session", "12am (Asia/Seoul)"), at(2026, 9, 8, 22, 0))
    ok = noon == ("session", at(2026, 9, 8, 12, 0)) and midnight == ("session", at(2026, 9, 9, 0, 0))
    return ok, f"noon {noon}, midnight {midnight}"


def case_zone_from_banner_not_from_now(script):
    # now in UTC; the banner's zone decides which instant 9pm is
    got = read(script, SESSION, at(2026, 9, 8, 9, 47, tz=dt.timezone.utc))
    want = ("session", at(2026, 9, 8, 21, 0))
    return got == want and got[1].utcoffset() == dt.timedelta(hours=9), f"{got} != {want}"


def case_no_zone_takes_nows(script):
    got = read(script, banner("session", "1:10am"), at(2026, 9, 8, 0, 55))
    want = ("session", at(2026, 9, 8, 1, 10))
    return got == want, f"{got} != {want}"


def case_unknown_zone_is_unparsed(script):
    mod = load(script)
    got = read(script, banner("session", "9pm (Mars/Olympus)"), at(2026, 9, 8, 18, 0))
    return isinstance(got, mod.Unparsed), f"returned {got!r}"


def case_unknown_clause_is_unparsed(script):
    mod = load(script)
    got = read(script, "  ⎿  You've hit your session limit · resets soon\n", at(2026, 9, 8, 18, 0))
    return isinstance(got, mod.Unparsed), f"returned {got!r}"


def case_allow_no_banner(script):
    usage = ("Current session: 92% used · resets Sep 7 at 1:30am (Asia/Seoul)\n"
             "Current week (all models): 72% used · resets Sep 8 at 10pm (Asia/Seoul)\n")
    got = [read(script, t, at(2026, 9, 8, 18, 0)) for t in (NONE, usage, "")]
    return got == [None] * 3, f"{got}"


def case_allow_prose_and_an_added_diff_line(script):
    quoted = ("NOTE planner-1: the banner reads `You've hit your session limit · resets 9pm (Asia/Seoul)`\n"
              "and the limit menu is idle.\n")
    diff = "+  ⎿  You've hit your session limit · resets 9pm (Asia/Seoul)\n+     /upgrade to increase your usage limit.\n"
    got = [read(script, t, at(2026, 9, 8, 18, 0)) for t in (quoted, diff)]
    return got == [None, None], f"{got}"


# ---------------- the command, through a fake herdr ----------------

FAKE = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_LOG"
[ -n "$FAKE_STDERR" ] && echo "$FAKE_STDERR" >&2
case "$1 $2" in
  "pane read") cat "$FAKE_SCREEN" ;;
  "agent list") [ -n "$FAKE_LIST_EXIT" ] && exit "$FAKE_LIST_EXIT"
                printf '{"result":{"agents":[{"pane_id":"w40:p1","agent_status":"%s"}]}}\\n' "${FAKE_STATUS:-idle}" ;;
  "agent prompt") echo '{"ok":true}' ;;
esac
exit ${FAKE_EXIT:-0}
"""


def run(script, args, screen, env=None, herdr=True, until=None):
    """(stdout, exit, asked) -- `asked` is every argv the fake herdr saw.
    `until(asked)` is polled for up to two seconds before the fake is torn
    down, for a sleeper that calls herdr after the script has returned."""
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

        def asked():
            return log.read_text().splitlines() if log.exists() else []
        if until:
            for _ in range(40):
                if until(asked()):
                    break
                time.sleep(0.05)
        return out.stdout + out.stderr, out.returncode, asked()


def case_cli_reads_the_pane(script):
    out, code, asked = run(script, ["w40:p1", "--now", "2026-09-08T18:47+09:00"], SESSION)
    reads = [a for a in asked if a.startswith("pane read w40:p1 ")]
    ok = (out.startswith("session 2026-09-08T21:00+09:00") and code == 0 and len(reads) == 1
          and "--source recent-unwrapped" in reads[0] and "--lines 200" in reads[0]
          and "--format text" in reads[0])
    return ok, f"{out!r} exit {code} asked {asked}"


def case_cli_no_limit(script):
    out, code, _ = run(script, ["w40:p1"], NONE)
    return out.strip() == "no limit" and code == 0, f"{out!r} exit {code}"


def case_cli_working_pane_banner_is_stale(script):
    out, code, asked = run(script, ["w40:p1", "--fire", "w40:p7", "--now", "2026-09-08T19:00+09:00"],
                           WOKEN_SCREEN, env={"HERDR_ENV": "1", "FAKE_STATUS": "working"})
    prompted = [a for a in asked if a.startswith("agent prompt")]
    ok = (out.startswith("no limit\ncould not fire: no banner on w40:p1") and code == 1 and not prompted
          and "agent list" in asked)
    return ok, f"{out!r} exit {code} asked {asked}"


def case_cli_idle_pane_banner_stands(script):
    # the same woken screen: idle, the banner is read and the wake is scheduled
    out, code, _ = run(script, ["w40:p1", "--now", "2026-09-08T19:00+09:00"], WOKEN_SCREEN,
                       env={"FAKE_STATUS": "idle"})
    return out.startswith("session 2026-09-08T21:00+09:00") and code == 0, f"{out!r} exit {code}"


def case_cli_unlisted_pane_banner_stands(script):
    # the listing cannot be read: the banner stands, erring toward the wake
    out, code, _ = run(script, ["w40:p1", "--now", "2026-09-08T19:00+09:00"], SESSION,
                       env={"FAKE_LIST_EXIT": "2"})
    return out.startswith("session 2026-09-08T21:00+09:00") and code == 0, f"{out!r} exit {code}"


def case_cli_no_banner_asks_no_status(script):
    out, code, asked = run(script, ["w40:p1"], NONE)
    return out.strip() == "no limit" and "agent list" not in asked, f"{out!r} asked {asked}"


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


def case_cli_now_without_offset_is_local(script):
    # TZ pins the local zone, so the assertion is the same on every machine
    out, code, _ = run(script, ["w40:p1", "--now", "2026-09-08T18:47"], SESSION, env={"TZ": "Asia/Tokyo"})
    return out.startswith("session 2026-09-08T21:00+09:00") and code == 0, f"{out!r} exit {code}"


def case_cli_now_malformed_is_could_not_read(script):
    out, code, asked = run(script, ["w40:p1", "--now", "tomorrow 9pm"], SESSION)
    ok = out.startswith("could not read: --now 'tomorrow 9pm' is not ISO 8601") and code == 1 and not asked
    return ok, f"{out!r} exit {code} asked {asked}"


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
        out, code, asked = run(script, ["w40:p1", "--fire", "w40:p7", "--text", "wake up",
                                        "--log", str(log), "--now", "2026-09-08T21:30+09:00"],
                               SESSION, env={"HERDR_ENV": "1"},
                               until=lambda a: any(x.startswith("agent prompt") for x in a))
        logged = log.read_text() if log.exists() else ""
    prompted = [a for a in asked if a.startswith("agent prompt")]
    ok = ("passed 2026-09-08T21:00+09:00" in out and "scheduled pid " in out
          and " at 2026-09-08T21:30+09:00 into w40:p7: wake up" in out and code == 0
          and prompted == ["agent prompt w40:p7 wake up"]
          and logged.startswith("== 2026-09-08T21:30+09:00 at 2026-09-08T21:30+09:00 into w40:p7: wake up\n")
          and logged.endswith('{"ok":true}\n'))
    return ok, f"{out!r} exit {code} prompted {prompted} log {logged!r}"


def case_fire_ahead_sleeps_until_lead(script):
    out, code, asked = run(script, ["w40:p1", "--fire", "w40:p7", "--now", "2026-09-08T18:47+09:00"],
                           SESSION, env={"HERDR_ENV": "1"})
    pid, log_line = None, None
    for line in out.splitlines():
        if line.startswith("scheduled pid "):
            pid = int(line.split()[2])
        if line.startswith("  log "):
            log_line = line
    own_session = False
    if pid:
        try:
            own_session = os.getpgid(pid) != os.getpgid(0)
        except OSError:
            pass
        try:
            if own_session:
                os.killpg(os.getpgid(pid), signal.SIGTERM)  # the sh and its sleep, in their own group
            else:
                # a group this runner is in is never signalled: the sh's children by parent, then the sh
                subprocess.run(["pkill", "-TERM", "-P", str(pid)], capture_output=True)
                os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    prompted = [a for a in asked if a.startswith("agent prompt")]
    ok = (" at 2026-09-08T21:01+09:00 into w40:p7: The usage window reset at 2026-09-08T21:00+09:00" in out
          and code == 0 and own_session and not prompted
          and log_line is not None and Path(log_line[len("  log "):]).exists())
    return ok, f"{out!r} exit {code} own_session {own_session} prompted {prompted}"


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]

# ---------------- each branch broken in turn ----------------
# (what is broken, anchor in the script, its replacement, the case that must go red)
MUTATIONS = [
    ("the glyph that makes a line a banner", r'r"^[ \t]*⎿[ \t]+You.ve hit your (?P<rest>.*)$"',
     r'r"You.ve hit your (?P<rest>.*)$"', case_allow_prose_and_an_added_diff_line),
    ("a working pane's banner is stale", 'if status == "working":', "if False:", case_cli_working_pane_banner_is_stale),
    ("the weekly kind", "(?P<kind>session|weekly)", "(?P<kind>session|weekl)", case_weekly_undated_is_todays),
    ("pm adds twelve", '(12 if ampm == "pm" else 0)', "0", case_session_on_the_hour),
    ("twelve o'clock wraps", 'int(m.group("hour")) % 12', 'int(m.group("hour")) % 13', case_noon_and_midnight),
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
    ("the last banner", "last = banners[-1]", "last = banners[0]", case_last_banner_wins),
    ("the unknown clause", 'raise Unparsed("a banner is on screen and its clause is not one this parser knows")', "return None",
     case_unknown_clause_is_unparsed),
    ("herdr missing", 'return None, "herdr is not installed"\n    if out.returncode != 0:\n        why',
     "return '', None\n    if out.returncode != 0:\n        why", case_cli_herdr_missing),
    ("herdr's exit", "if out.returncode != 0:\n        why = (out.stderr", "if False:\n        why = (out.stderr",
     case_cli_herdr_refuses),
    ("how far back the pane is read", 'LINES = "200"', 'LINES = "5"', case_cli_reads_the_pane),
    ("the text format", '"--format", "text"', '"--format", "json"', case_cli_reads_the_pane),
    ("could not read's status", 'print(f"could not read: {e}")\n        return 1', 'print(f"could not read: {e}")\n        return 0',
     case_cli_unparsed_is_could_not_read),
    ("a clock with no offset is local", "now = now.astimezone()", "now = now.replace(tzinfo=dt.timezone.utc)",
     case_cli_now_without_offset_is_local),
    ("a clock that is not one", 'return None, f"--now {text!r} is not ISO 8601"', "return dt.datetime.now().astimezone(), None",
     case_cli_now_malformed_is_could_not_read),
    ("the HERDR_ENV guard", 'os.environ.get("HERDR_ENV") != "1"', 'os.environ.get("HERDR_ENV") == "1"',
     case_fire_refused_without_herdr_env),
    ("no banner fires nothing", "if a.fire:\n            print", "if False:\n            print", case_fire_refused_on_no_banner),
    ("now for a passed reset", 'now if kind == "passed" else when + LEAD', "when + LEAD", case_fire_passed_prompts_now),
    ("the lead minute", 'now if kind == "passed" else when + LEAD', 'now if kind == "passed" else when',
     case_fire_ahead_sleeps_until_lead),
    ("the sleeper's own session", "start_new_session=True", "start_new_session=False", case_fire_ahead_sleeps_until_lead),
    ("the run's marker in the log", 'fh.write(f"== {iso(now)} at', 'fh.write(f"-- {iso(now)} at', case_fire_passed_prompts_now),
    ("the log line", 'f"  log {log}"', 'f"  LOG {log}"', case_fire_ahead_sleeps_until_lead),
]


def mutated(old, new):
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
        try:
            ok, detail = case(SCRIPT)
        except Exception as e:  # noqa: BLE001 -- a crashed case is a failed case, named
            ok, detail = False, f"the case crashed: {e!r}"
        check(case.__name__, ok, detail)
    for what, old, new, case in MUTATIONS:
        copy = mutated(old, new)
        name = f"mutation: {what} broken -> {case.__name__} goes red"
        if copy is None:
            check(name, False, f"anchor not found exactly once: {old!r}")
            continue
        try:
            ok, _ = case(copy)
            check(name, not ok, "the case stayed green")
        except Exception as e:  # noqa: BLE001 -- red by a crash asserted nothing
            check(name, False, f"the case crashed instead of asserting: {e!r}")
        finally:
            shutil.rmtree(copy.parent, ignore_errors=True)
    n_cases, n_mut = len(CASES), len(MUTATIONS)
    print(f"campaign-limit-reset-test: {len(RAN)} ran ({n_cases} cases, {n_mut} mutations), "
          f"{len(FAILED)} failed, script {SCRIPT}")
    for f in FAILED:
        print(f"  FAIL {f}")
    return 1 if FAILED or len(RAN) != n_cases + n_mut else 0


if __name__ == "__main__":
    sys.exit(main())
