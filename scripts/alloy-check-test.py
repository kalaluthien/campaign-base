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
  a witness that is not one, 16 ways    MISSING: a trace satisfies it without
                                        Hand firing
  a check naming Hand through a helper  MISSING, as if it named Hand itself,
                                        for a pred, a fun, and helpers whose
                                        parameter or return type is a set
                                        comprehension
  three readings it could not make      `could not look`, exit 2, never a pass
  --closure short of what a verdict     a file reached only transitively, an
  reads                                 `open` inside a block comment, an
                                        alloy `util/` module; an `open` that
                                        is not there is `could not look`

and the allow cases beside them: the repaired model, a witness with extra
conjuncts, an `or` inside a quantifier's body, a witness predicate declared in
the opened module or with parameters or a receiver, a model whose observer
is sdlc's `Step`, a model opening `util/ordering`, a run of a fun, and a check
naming no event over a model whose event is dead.

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
{opens}
pred handFires {{ Now.event = Hand }}
fun handEvent: Event {{ Hand }}

assert ViaHelper {{ always (handFires implies no Where.machine) }}
assert ViaFun {{ always (Now.event = handEvent implies no Where.machine) }}
assert HandNeverOnAMachine {{ always (Now.event = Hand implies no Where.machine) }}
assert SomeEvent {{ always some Now.event /* not about Hand */ }}
{more}
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
        extra="", run_line=None, alloy_says=None, opens="", pred=None, more="",
        observer="Now"):
    """Write the fixture under <d> and run the script on its checks module.

    `witness` is a predicate body for `Cov_Hand`; empty declares no witness.
    `pred` replaces the whole witness declaration, for its other head forms,
    and `more` adds declarations to the checks module.
    `observer` renames the `Now` sig throughout, as sdlc names its `Step`.
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
        SYSTEM.format(condition=condition, extra=extra).replace("Now", observer))
    if pred is None:
        pred = f"pred Cov_Hand {{ {witness} }}" if witness else ""
    if run_line is None:
        run_line = f"run Cov_Hand for 2 expect {expect}" if witness or extra else ""
    (root / "checks.als").write_text(
        CHECKS.format(witness=pred, check=check_name, run=run_line, opens=opens,
                      more=more).replace("Now", observer))
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
        "`||` among the conjuncts":
            "eventually (Now.event = Hand and some Machine || Now.event = Stutter)",
        "`implies` among the conjuncts":
            "eventually (Now.event = Hand and some Machine implies no Machine)",
        "`=>` among the conjuncts":
            "eventually (Now.event = Hand and some Machine => no Machine)",
        "`iff` among the conjuncts":
            "eventually (Now.event = Hand and some Machine iff some none)",
        "parentheses closing after a quantifier's bar":
            "eventually (Now.event = Hand and some m: Machine | m in Machine) or (Now.event = Stutter)",
    }
    for name, body in not_witnesses.items():
        with tempfile.TemporaryDirectory() as d:
            rc, out, path = run(d, witness=body, expect=1)
            check(f"not a witness, refused as MISSING: {name}",
                  rc == 1 and refused(out, "MISSING", "Hand", path)
                  and "alloy exit 0" in line(out, "RESULT"),
                  f"exit {rc}: {out[-6:]}")

    for helper in ("ViaHelper", "ViaFun"):
        with tempfile.TemporaryDirectory() as d:
            rc, out, path = run(d, check_name=helper)
            check(f"an event a check names only through a helper is refused as MISSING: {helper}",
                  rc == 1 and refused(out, "MISSING", "Hand", path)
                  and helper in line(out, "MISSING"),
                  f"exit {rc}: {out[-6:]}")

    # Witnesses about another event than their text says, and helpers whose
    # head hides where their body starts.
    shadows = {
        "the event": ("pred Cov_Hand(Hand: Event) { eventually Now.event = Hand }", ""),
        "`event`": ("pred Cov_Hand[event: univ -> Event] { eventually Now.event = Hand }", ""),
        "`Now`": ("pred Cov_Hand[Now: Fake] { eventually Now.event = Hand }",
                  "sig Fake { event: one Event }"),
        "`Step`": ("pred Cov_Hand[Step: Fake] { eventually Step.event = Hand }",
                   "sig Fake { event: one Event }"),
    }
    for name, (decl, extra) in shadows.items():
        with tempfile.TemporaryDirectory() as d:
            rc, out, path = run(d, pred=decl, extra=extra,
                                run_line="run Cov_Hand for 2 expect 1")
            check(f"not a witness, refused as MISSING: a parameter named like {name}",
                  rc == 1 and refused(out, "MISSING", "Hand", path)
                  and "alloy exit 0" in line(out, "RESULT"),
                  f"exit {rc}: {out[-6:]}")
    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, pred="fun Cov_Hand: set Event { Stutter }",
                            extra="pred Cov_Hand { eventually Now.event = Hand }",
                            run_line="run Cov_Hand for 2 expect 1")
        check("not a witness, refused as MISSING: the root's fun is run, not a pred it opens",
              rc == 1 and refused(out, "MISSING", "Hand", path)
              and "alloy exit 0" in line(out, "RESULT"),
              f"exit {rc}: {out[-6:]}")
    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, check_name="ViaSetParam", more=(
            "pred hf[m: {x: Machine | some x}] { Now.event = Hand }\n"
            "assert ViaSetParam { always (hf[Machine] implies no Where.machine) }"))
        check("a helper whose parameter is a set comprehension is read to its body",
              rc == 1 and refused(out, "MISSING", "Hand", path)
              and "ViaSetParam" in line(out, "MISSING"),
              f"exit {rc}: {out[-6:]}")
    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, pred=("pred Cov_Hand { machine :> Machine = machine }\n"
                                     "pred decoy { eventually Now.event = Hand }"),
                            run_line="run Cov_Hand for 2 expect 1")
        check("not a witness, refused as MISSING: a body opening with `:>` is not a comprehension",
              rc == 1 and refused(out, "MISSING", "Hand", path)
              and "alloy exit 0" in line(out, "RESULT"),
              f"exit {rc}: {out[-6:]}")
    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, check_name="ViaSetType", more=(
            "fun hg: {m: Machine | some m} { Now.event = Hand implies Machine else none }\n"
            "assert ViaSetType { always (some hg implies no Where.machine) }"))
        check("a helper fun whose return type is a set comprehension is read to its body",
              rc == 1 and refused(out, "MISSING", "Hand", path)
              and "ViaSetType" in line(out, "MISSING"),
              f"exit {rc}: {out[-6:]}")
    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(
            d, pred="pred Cov_Hand(m: set (Machine)) { eventually Now.event = Stutter }",
            extra="pred Cov_Hand { eventually Now.event = Hand }",
            run_line="run Cov_Hand for 2 expect 1")
        check("not a witness, refused as MISSING: the root's pred is read, not a namesake it opens",
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

    for form in ("eventually Now.event = Hand",
                 "eventually (Now.event = Hand and some Machine)"):
        with tempfile.TemporaryDirectory() as d:
            rc, out, path = run(d, condition="", witness=form, observer="Step")
            check(f"a model whose observer is sdlc's `Step` passes: {form.replace('Now', 'Step')}",
                  rc == 0 and line(out, "witness").split()[1:4] == ["Hand", "Cov_Hand", "SAT"],
                  f"exit {rc}: {out[-6:]}")

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

    heads = {
        "parameters in parentheses":
            "pred Cov_Hand(m: Machine) { eventually (Now.event = Hand and m = m) }",
        "a receiver":
            "pred Machine.Cov_Hand { eventually (Now.event = Hand and this = this) }",
    }
    for name, decl in heads.items():
        with tempfile.TemporaryDirectory() as d:
            rc, out, path = run(d, condition="", pred=decl,
                                run_line="run Cov_Hand for 2 expect 1")
            check(f"a witness, allowed: its predicate declared with {name}",
                  rc == 0 and line(out, "witness").split()[1:4] == ["Hand", "Cov_Hand", "SAT"],
                  f"exit {rc}: {out[-6:]}")

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, condition="", witness="eventually Now.event = Hand",
                            opens="open util/ordering[Machine]")
        check("a model opening alloy's own util library is read, not `could not look`",
              rc == 0 and line(out, "witness").split()[1:4] == ["Hand", "Cov_Hand", "SAT"],
              f"exit {rc}: {out[-6:]}")

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, condition="", witness="eventually Now.event = Hand",
                            run_line="run Cov_Hand for 2 expect 1\nrun handEvent for 2 expect 1")
        check("a run of a fun is no witness and no error",
              rc == 0 and line(out, "witness").split()[1:4] == ["Hand", "Cov_Hand", "SAT"],
              f"exit {rc}: {out[-6:]}")

    with tempfile.TemporaryDirectory() as d:
        rc, out, path = run(d, check_name="SomeEvent")
        check("a check naming no event needs no witness, the dead event notwithstanding",
              rc == 0 and not line(out, "MISSING") and not line(out, "DEAD"),
              f"exit {rc}: {out[-6:]}")

    # ------------------------------------------------------------ the digest

    # An sdlc trace as alloy writes it: every name qualified by its module path.
    q = "scenarios/system/"
    trace = "\n".join([
        "------State 0-------",
        f"{q}Change<:optional={{{q}Change$0->{q}Test$0}}",
        f"{q}Artifact<:witnesses={{{q}Artifact$1->{q}Artifact$0}}",
        f"{q}Artifact<:drives={{{q}Artifact$1->{q}Artifact$2}}",
        f"{q}Step<:event={{{q}Step$0->{q}Write$0}}",
        f"{q}Step<:artifact={{{q}Step$0->{q}Artifact$0}}",
        f"{q}Step<:subject={{}}",
        f"{q}Written={{}}",
        "------State 1 (loop)-------",
        f"{q}Step<:event={{{q}Step$0->{q}Land$0}}",
        f"{q}Step<:subject={{{q}Step$0->{q}Change$0}}",
        f"{q}Written={{{q}Artifact$0}}",
        f"{q}Licensed={{{q}Artifact$0}}", ""])
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "S_solution-0.txt"
        path.write_text(trace)
        r = subprocess.run([sys.executable, str(SCRIPT), "--digest", str(path)],
                           capture_output=True, text=True)
        out = r.stdout.splitlines()
        static, s0, s1 = line(out, "static:"), line(out, "        S0"), line(out, " S1 (loop)")
        # A cell is `label=value`; the first case asks for the column whatever
        # its value, so the observer strip is the second case's alone.
        for name, head, tail, where in [
                ("sdlc's `Step.event` is the event column", "ev=", "Write", s0),
                ("sdlc's observer atom is stripped from a cell", "ev=Land", "", s1),
                ("sdlc's `Step.artifact` is shown", "artifact=Ar0", "", s0),
                ("sdlc's `Step.subject` is shown", "change=Ch0", "", s1),
                ("sdlc's `Change.optional` is static", "Change<:optional=Ch0->Test", "", static),
                ("sdlc's `witnesses` is static", "Artifact<:witnesses=Ar1->Ar0", "", static),
                ("sdlc's `drives` is static", "Artifact<:drives=Ar1->Ar2", "", static),
                ("sdlc's `Licensed` is a column that varies", "licensed=Ar0", "", s1)]:
            cells = where.replace(";", " ").split()
            check(f"--digest: {name}", r.returncode == 0 and any(
                      c.startswith(head) and c.endswith(tail) and (tail or c == head) for c in cells),
                  f"exit {r.returncode}: {out}")

    # ------------------------------------------------------------ --closure

    # What a module's verdict reads: itself and every file its `open`s reach.
    # CI keys a cached verdict on these files' hash, so a file missing from the
    # list is a change that reuses a stale verdict.
    def closure(d, files, module):
        for name, text in files.items():
            (Path(d) / name).parent.mkdir(parents=True, exist_ok=True)
            (Path(d) / name).write_text(text)
        r = subprocess.run([sys.executable, str(SCRIPT), "--closure", module],
                           capture_output=True, text=True, cwd=d)
        return r.returncode, r.stdout.splitlines()

    chain = {"sys/system.als": "module sys/system\nsig A {}\n",
             "sys/scenarios.als": "module sys/scenarios\nopen sys/system\n",
             "sys/checks.als": "module sys/checks\nopen sys/scenarios\n"
                               "/*\nopen sys/ghost\n*/\nopen util/ordering[A]\n"}

    with tempfile.TemporaryDirectory() as d:
        rc, out = closure(d, chain, "sys/checks.als")
        check("--closure lists the module, then every file its opens reach, transitively",
              rc == 0 and out == ["sys/checks.als", "sys/scenarios.als", "sys/system.als"],
              f"exit {rc}: {out}")

    with tempfile.TemporaryDirectory() as d:
        rc, out = closure(d, chain, "sys/system.als")
        check("--closure of a module that opens nothing lists that module alone",
              rc == 0 and out == ["sys/system.als"], f"exit {rc}: {out}")

    with tempfile.TemporaryDirectory() as d:
        rc, out = closure(d, dict(chain, **{"sys/system.als": "module sys/system\nopen sys/gone\n"}),
                          "sys/checks.als")
        check("--closure over an open that is not there is `could not look` and lists no file",
              rc == 2 and len(out) == 1 and "could not look" in out[0] and "gone" in out[0],
              f"exit {rc}: {out}")

    with tempfile.TemporaryDirectory() as d:
        rc, out = closure(d, {}, "sys/nothing.als")
        check("--closure of a module that is not there is `could not look`",
              rc == 2 and len(out) == 1 and "could not look" in out[0], f"exit {rc}: {out}")

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
