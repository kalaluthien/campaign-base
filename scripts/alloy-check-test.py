#!/usr/bin/env python3
# witnesses: Cov_Handoff, Cov_DeleteDir, Cov_RemoveMember
"""Prove alloy-check refuses a check over an event nothing can fire.

A `check` over an event no trace reaches holds by vacuity, and Alloy's own
`expect` cannot see it: the check comes out UNSAT exactly as a true one does.
kalaluthien/campaign-base#289 shipped four such checks over `Handoff`, whose
event predicate set `Where.machine` where every step above session pins it
empty.

Every case runs the real script on a two-module fixture under a fresh
directory -- `sys/system.als` declaring the events, `sys/checks.als` opening it
and holding the check -- which is that shape in a dozen lines: `hand` asks for
`some Where.machine`, the trace pins `no Where.machine` on every step, and
`HandNeverOnAMachine` holds over it whatever it says.

THE NAMED FAILING CASES, one per refusal branch:

  the #289 shape with no witness       MISSING: the check is green, nothing
                                        shows Hand can fire
  a witness that comes out UNSAT        DEAD, whether or not its own `expect`
                                        already said so
  a witness that is not one, five ways  MISSING: a trace satisfies it without
                                        Hand firing
  three readings it could not make      `could not look`, exit 2, never a pass

and the allow cases beside them: the repaired model, a witness with extra
conjuncts, an `or` inside a quantifier's body, a witness predicate declared in
the opened module, and a check naming no event over a model whose event is dead.

Usage: scripts/alloy-check-test.py   (needs ~/.local/bin/alloy, as CI installs)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "alloy-check.py"

FAILURES = []

SYSTEM = """module sys/system

sig Machine {{}}
abstract sig Event {{}}
one sig Stutter, Hand extends Event {{}}
/* one sig Ghost extends Event {{}} -- a comment, not a declaration */

one sig Now   {{ var event: one Event }}
one sig Where {{ var machine: lone Machine }}

pred hand {{ Now.event = Hand{condition} }}
fact Trace {{ always (no Where.machine and (Now.event = Stutter or hand)) }}
{extra}
"""

CHECKS = """module sys/checks

open sys/system

assert HandNeverOnAMachine {{ always (Now.event = Hand implies no Where.machine) }}
assert SomeEvent {{ always some Now.event /* not about Hand */ }}
{witness}
check {check} for 2 expect 0
{run}
"""

# THE #289 SHAPE: the event's own predicate asks for what every step forbids.
DEAD = " and some Where.machine"


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        FAILURES.append(name)
        if detail:
            print("      " + detail)


def run(d, condition=DEAD, witness="", expect=1, check_name="HandNeverOnAMachine",
        extra="", run_line=None, alloy_says=None):
    """Write the fixture under <d> and run the script on its checks module.

    `witness` is a predicate body for `Cov_Hand`; empty declares no witness.
    `alloy_says` replaces alloy with a stand-in printing those lines, for the
    two readings real alloy never gives: a verdict line this script cannot
    parse, and a command whose `assert` is not in the text.
    """
    env = None
    if alloy_says is not None:
        home = Path(d) / "home"
        (home / ".local" / "bin").mkdir(parents=True)
        fake = home / ".local" / "bin" / "alloy"
        fake.write_text("#!/bin/sh\ncat >&2 <<'EOF'\n" + "\n".join(alloy_says) + "\nEOF\n")
        fake.chmod(0o755)
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    root = Path(d) / "sys"
    root.mkdir(parents=True, exist_ok=True)
    (root / "system.als").write_text(
        SYSTEM.format(condition=condition, extra=extra))
    pred = f"pred Cov_Hand {{ {witness} }}" if witness else ""
    if run_line is None:
        run_line = f"run Cov_Hand for 2 expect {expect}" if witness or extra else ""
    (root / "checks.als").write_text(
        CHECKS.format(witness=pred, check=check_name, run=run_line))
    r = subprocess.run([sys.executable, str(SCRIPT), str(root / "checks.als"),
                        "-o", str(Path(d) / "out")],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout.splitlines(), str(root / "checks.als")


def line(lines, head):
    return next((l for l in lines if l.startswith(head)), "")


def refused(lines, word, event, path):
    """The refusal line naming the event and the file, or ''."""
    l = line(lines, word)
    return l if event in l.split() and path in l else ""


def main() -> int:
    print(f"reading {SCRIPT}")

    # ------------------------------------------------------------ refusals

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d)
        check("the #289 shape with no witness is refused as MISSING, though alloy is green",
              rc == 1 and refused(out, "MISSING", "Hand", path)
              and "alloy exit 0" in line(out, "RESULT"),
              f"exit {rc}: {out[-6:]}")

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, witness="eventually Now.event = Hand", expect=1)
        check("a witness that comes out UNSAT against its expect is named DEAD",
              rc == 1 and "Cov_Hand" in refused(out, "DEAD", "Hand", path),
              f"exit {rc}: {out[-6:]}")

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, witness="eventually Now.event = Hand", expect=0)
        check("a witness declared UNSAT is DEAD, though alloy is green",
              rc == 1 and "Cov_Hand" in refused(out, "DEAD", "Hand", path)
              and "alloy exit 0" in line(out, "RESULT"),
              f"exit {rc}: {out[-6:]}")

    # Each of these comes out SAT through Stutter, so alloy is green and only the
    # shape can tell that nothing showed Hand firing.
    not_witnesses = {
        "a disjunction of the event and another":
            "eventually (Now.event = Hand or Now.event = Stutter)",
        "an `or` among the conjuncts after the event":
            "eventually (Now.event = Hand and some Machine or Now.event = Stutter)",
        "parentheses closing before the body ends":
            "eventually (Now.event = Hand and some Machine) or (Now.event = Stutter)",
        "the event inside a larger formula":
            "always Now.event = Stutter or eventually Now.event = Hand",
        "the event joined to a relation, which is another event":
            "eventually (Now.event = Hand.(Hand->Stutter))",
    }
    for name, body in not_witnesses.items():
        with tempfile.TemporaryDirectory() as d:
            rc, out, path = run(d, witness=body, expect=1)
            check(f"not a witness, refused as MISSING: {name}",
                  rc == 1 and refused(out, "MISSING", "Hand", path)
                  and "alloy exit 0" in line(out, "RESULT"),
                  f"exit {rc}: {out[-6:]}")

    # ------------------------------------------------------------ allows

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, condition="", witness="eventually Now.event = Hand")
        events = line(out, "events")
        check("the repaired model passes, its witness read as SAT",
              rc == 0 and line(out, "witness").split()[1:4] == ["Hand", "Cov_Hand", "SAT"],
              f"exit {rc}: {out[-6:]}")
        check("the events are read from declarations, not from a comment",
              "Hand" in events and "Stutter" in events and "Ghost" not in events,
              events)

    allowed = {
        "a witness with conjuncts after the event":
            "eventually (Now.event = Hand and no Where.machine)",
        "an `or` inside a quantifier's body":
            "eventually (Now.event = Hand and some m: Machine | m in Machine or no Machine)",
    }
    for name, body in allowed.items():
        with tempfile.TemporaryDirectory() as d:
            rc, out, path = run(d, condition="", witness=body)
            check(f"a witness, allowed: {name}",
                  rc == 0 and line(out, "witness").split()[1:4] == ["Hand", "Cov_Hand", "SAT"],
                  f"exit {rc}: {out[-6:]}")

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, condition="",
                            extra="pred Cov_Hand { eventually Now.event = Hand }")
        check("a witness predicate declared in the opened module, run from the root",
              rc == 0 and line(out, "witness").split()[1:4] == ["Hand", "Cov_Hand", "SAT"],
              f"exit {rc}: {out[-6:]}")

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, check_name="SomeEvent")
        check("a check naming no event needs no witness, the dead event notwithstanding",
              rc == 0 and not line(out, "MISSING") and not line(out, "DEAD"),
              f"exit {rc}: {out[-6:]}")

    # ------------------------------------------------------------ could not look

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, run_line="run Cov_Hand for for")
        check("a model alloy cannot run is `could not look`, never a pass",
              rc == 2 and "could not look" in line(out, "RESULT"),
              f"exit {rc}: {out[-4:]}")

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, witness="eventually Now.event = Hand", alloy_says=[
            "00. check HandNeverOnAMachine      0       UNSAT",
            "01. run   Cov_Hand                 0       UNKNOWN"])
        check("a witness alloy printed no verdict for is `could not look`, never a pass",
              rc == 2 and "Hand" in line(out, "UNREAD").split()
              and "could not look" in line(out, "RESULT"),
              f"exit {rc}: {out[-4:]}")

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, check_name="NoSuchAssert", alloy_says=[
            "00. check NoSuchAssert             0       UNSAT"])
        check("a check whose assert is not in the text is `could not look`, never a pass",
              rc == 2 and "NoSuchAssert" in line(out, "RESULT")
              and "could not look" in line(out, "RESULT"),
              f"exit {rc}: {out[-4:]}")

    print(f"{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
