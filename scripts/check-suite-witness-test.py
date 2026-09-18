#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-suite-witness.py cuts a scenario's claims and its suite's test functions, asks one select call a scenario and one claim call a function picked, and never refuses.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers every
question it is sent, and the reader runs in a fixture repository holding its
own copies of the scripts it loads and of scripts/jev/readings.json. Each case
is then broken by a mutation of the reader's text and must go red by its own
assertion.

THE FIXTURE CARRIES ONE SUITE OF EVERY SHAPE THE TREE HAS: a `CASES` dict of
name -> function, an `@case("...")` decorator over functions all named `_`, bare
`case_*` / `*_cases` / `test_*` names, a declarative suite with no function at
all, and one naming a scenario that has no declaration.

Usage: scripts/check-suite-witness-test.py
"""
import http.server
import importlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import types
from pathlib import Path

harness = importlib.import_module("suite-harness-test")
check = harness.check

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-suite-witness.py"
SOURCE = SCRIPT.read_text()
REGISTRY = HERE / "jev" / "readings.json"
ENTRIES = json.loads(REGISTRY.read_text())
ENTRY = ENTRIES["suite-witness-select"]
MODEL = "jev-1.13.0"
ROOT = Path(tempfile.mkdtemp(prefix="suite-witness-"))

NEXT = {"choice": "t1", "conf": 0.9}
SEEN = []


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        answers = {}
        for q, spec in body["questions"].items():
            opts = list(spec["criteria"])
            if "supports" in opts:
                answers[q] = {"type": "choice", "choice": "supports",
                              "confidence": 0.9,
                              "probabilities": {"supports": 0.9,
                                                "contradicts": 0.05,
                                                "says_nothing": 0.05}}
            else:
                pick = NEXT["choice"] if NEXT["choice"] in opts else opts[0]
                answers[q] = {"type": "choice", "choice": pick,
                              "confidence": NEXT["conf"],
                              "probabilities": {o: (1.0 if o == pick else 0.0)
                                                for o in opts}}
        data = json.dumps({"model": MODEL, "answers": answers}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


SERVER = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{SERVER.server_address[1]}/v1/systemone"

# THE SNAPSHOT IS WHAT SAYS A NAME IS A SCENARIO. check-sdlc-tie's `Tree` reads
# it, and this reader asks that Tree rather than the tree's `.als` text, so a
# fixture whose snapshot omits a name gets it skipped and never asked.
SNAPSHOT = json.dumps({"generated_by": "fixture", "why": "fixture", "commands": [
    ["fixture/checks.als", "check", "Held"],
    ["fixture/checks.als", "run", "Cov_Held"]]})

SPEC = """module fixture
sig Agent {
  peer: lone Agent
}
/* An agent holds its own claim when it has a peer. */
pred holds[a: Agent] { some a.peer }
"""
# THE CLAIM SITS ABOVE THE DECLARATION AND NOT ABOVE THE COMMAND: the `check`
# line below carries a one-line pred list, which is what the reader must NOT
# read as the scenario's claim.
CHECKS = """module fixture/checks
open fixture
/* A held agent keeps its peer, and `holds` is what says so.
   ---------------- the section ----------------
   Every Agent named here is an Agent.
   Dropping the clause reddens it. */
assert Held { all a: Agent | holds[a] implies some a.peer }
/* The reachability floor for `holds`. */
pred Cov_Held { some a: Agent | holds[a] }
-- names `holds`
check Held for 3
-- names `holds`
run Cov_Held for 3
"""

DICT_SUITE = '''#!/usr/bin/env python3
#@ Held
"""A suite whose cases are a dict of name -> function."""


def helper(t):
    return 1


def peer_kept(t):
    return True, ""


def peer_dropped(t):
    return True, ""


CASES = {
    "a held agent keeps its peer": peer_kept,
    "an agent with no peer is not held": peer_dropped,
}
'''

CASE_SUITE = '''#!/usr/bin/env python3
#@ Held
#@ Cov_Held, Held
"""A suite whose cases are a decorator over functions all named `_`."""
CASES = {}


def case(name):
    def register(fn):
        CASES[name] = fn
        return fn
    return register


@case("the peer is read once")
def _(m):
    return True, ""


@case("the floor fires")
def _(m):
    return True, ""
'''

BARE_SUITE = '''#!/usr/bin/env python3
#@ Held
"""A suite whose cases are named by the convention alone."""


def build(t):
    return 1


def case_one(t):
    return True, ""


def two_cases(t):
    return True, ""


def test_three(t):
    return True, ""
'''

FLAT_SUITE = '''#!/usr/bin/env python3
#@ Held
"""A suite whose cases are declarative tuples and no function at all."""
CASES = [
    ("a held agent keeps its peer", {"peer": 1}, "ok"),
]
'''

GHOST_SUITE = '''#!/usr/bin/env python3
#@ NoSuchScenario
"""A suite naming what spec/ does not declare."""


def case_one(t):
    return True, ""
'''

INLINE_SUITE = '''#!/usr/bin/env python3
#@ Held
"""A suite whose cases are a dict of values that are not bare names."""


def refusal(code):
    def run(t):
        return code == 2, ""
    return run


CASES = {
    "a call value is a case": refusal(2),
    "a lambda value is a case": lambda t: (True, ""),
    "a name the literal only holds a place for": None,
}


def filled_in_below(t):
    return True, ""


CASES["a name the literal only holds a place for"] = filled_in_below
CASES["a case added below the literal"] = refusal(3)
'''


# THE FIXTURE'S WITNESS LINES ARE BUILT AND NOT WRITTEN. check-sdlc-tie reads a
# `# witnesses:` line by the line's first non-blank character, so a literal one
# at column zero inside a fixture string is a declaration BY THIS SUITE, and T6
# refuses the commit over a scenario only the fixture has.
DICT_SUITE, CASE_SUITE, BARE_SUITE, FLAT_SUITE, GHOST_SUITE, INLINE_SUITE = (
    t.replace("#@ ", "# witnesses: ") for t in
    (DICT_SUITE, CASE_SUITE, BARE_SUITE, FLAT_SUITE, GHOST_SUITE, INLINE_SUITE))
SUITES = {"scripts/fixture-dict-test.py": DICT_SUITE,
          "scripts/fixture-case-test.py": CASE_SUITE,
          "scripts/fixture-bare-test.py": BARE_SUITE,
          "scripts/fixture-flat-test.py": FLAT_SUITE,
          "scripts/fixture-ghost-test.py": GHOST_SUITE,
          "scripts/fixture-inline-test.py": INLINE_SUITE}


def module(source):
    m = types.ModuleType("suitewitness")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return m


def load(source):
    return types.SimpleNamespace(source=source, m=module(source))


def repo(t, edits, choice="t1", tier="advise", registry=True, url=None,
         extra=None):
    """The reader, as `t.source`, run in a fresh repository whose first commit
    holds the fixture tree and whose index holds `edits` on top of it."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    files = {"spec/fixture/system.als": SPEC,
             "spec/fixture/checks.als": CHECKS,
             "README.md": "fixture\n",
             "scripts/check-suite-witness.py": t.source,
             "scripts/check-model-comment.py": (HERE / "check-model-comment.py").read_text(),
             "scripts/check-cited-claims.py": (HERE / "check-cited-claims.py").read_text(),
             "scripts/campaign-jev.py": (HERE / "campaign-jev.py").read_text(),
             "scripts/check-sdlc-tie.py": (HERE / "check-sdlc-tie.py").read_text(),
             "scripts/check-tree-shape.py": (HERE / "check-tree-shape.py").read_text(),
             "spec/commands.snapshot.json": SNAPSHOT,
             **SUITES, **(extra or {})}
    if registry:
        entries = json.loads(REGISTRY.read_text())
        for name in entries:
            entries[name]["tier"] = tier
        files["scripts/jev/readings.json"] = json.dumps(entries)
    harness.write_tree(d, files)
    harness.git(d, "init", "-q", check=True)
    # AN ORIGIN, so the row's join key can be read: a commit-time reading is
    # keyed by the repository, the sha it sits on and the file.
    harness.git(d, "remote", "add", "origin", "https://github.com/o/r.git",
                check=True)
    harness.git(d, "add", "-A", check=True)
    harness.git(d, "commit", "-qm", "fixture", "--no-verify", check=True)
    harness.write_tree(d, edits)
    harness.git(d, "add", "-A", check=True)
    NEXT["choice"] = choice
    SEEN.clear()
    env = dict(os.environ, CAMPAIGN_JEV_URL=url or URL, TYPESAFE_API_KEY="stub",
               CAMPAIGN_JEV_LOG=str(d / "jev.log"))
    r = subprocess.run([sys.executable, "scripts/check-suite-witness.py",
                        "--staged"], cwd=d, capture_output=True, text=True,
                       env=env)
    return r, r.stdout + r.stderr, d


def rows(d):
    path = d / "jev.log"
    return [json.loads(line) for line in path.read_text().splitlines()
            if line] if path.exists() else []


def selects():
    """[(the candidates sent, the instructions sent)] of every select call. The
    claim is SPLICED into the instructions here, not sent as a field of them:
    the entry's `compose.as` is a placeholder map."""
    return [(b["state"]["candidates"],
             [q["instructions"] for q in b["questions"].values()])
            for b in SEEN if "candidates" in b["state"]]


def claims_sent():
    """[(the function sent, the instructions sent)] of every claim call."""
    return [(b["state"]["test_fn"],
             [q["instructions"] for q in b["questions"].values()])
            for b in SEEN if "test_fn" in b["state"]]


def skips(d):
    """Why each skip row of the run was written."""
    return [x["skipped"] for x in rows(d) if x.get("skipped")]


def touch(text):
    return text.replace("some a.peer }", "some a.peer or no a }")


# ------------------------------------------------------------------ the cuts

def the_tie_reads_the_witness_line(t):
    """check-sdlc-tie owns the `# witnesses:` form, so this reader must hold no
    copy of it: no `declared`, and no pattern in the entry."""
    import ast as A
    tree = A.parse(t.source)
    docs = {id(n.body[0].value) for n in A.walk(tree)
            if isinstance(n, (A.Module, A.FunctionDef, A.ClassDef)) and n.body
            and isinstance(n.body[0], A.Expr)
            and isinstance(n.body[0].value, A.Constant)}
    held = [n.value for n in A.walk(tree)
            if isinstance(n, A.Constant) and isinstance(n.value, str)
            and id(n) not in docs and "witnesses" in n.value]
    return (not hasattr(t.m, "declared")
            and "witnesses" not in ENTRY["prefilter"]
            and "tree.declared(suite)" in t.source and not held), held


def a_case_that_is_not_a_function_is_a_candidate(t):
    """`campaign-close-test` writes 73 of its 158 cases as `refusal(...)` and
    `check-read-range-test` all 14 that way; read as functions they vanish, and
    a case a reader cannot name can only come back `noMatch`."""
    got = t.m.candidates(INLINE_SUITE, ENTRY["prefilter"])
    return ([(c["fn"], c["name"]) for c in got.values()][:2]
            == [("", "a call value is a case"), ("", "a lambda value is a case")]
            and "refusal(" in list(got.values())[0]["body"]), got


def a_case_named_below_the_literal_is_a_candidate(t):
    """`campaign-jev-test` writes 108 of its 133 as `CASES["..."] = fn` below
    the dict, two of them filling a `None` the literal holds a place for. The
    last write of a name wins, as it does for Python, so the placeholder is
    never a candidate of its own and the real function is not lost."""
    got = t.m.candidates(INLINE_SUITE, ENTRY["prefilter"])
    return ([(c["fn"], c["name"]) for c in got.values()]
            == [("", "a call value is a case"),
                ("", "a lambda value is a case"),
                ("filled_in_below", "a name the literal only holds a place for"),
                ("", "a case added below the literal")]
            and not any(c["body"].strip().endswith("None,")
                        for c in got.values())), got


def dict_names_the_case(t):
    got = t.m.candidates(DICT_SUITE, ENTRY["prefilter"])
    return ([c["name"] for c in got.values()]
            == ["a held agent keeps its peer",
                "an agent with no peer is not held"]
            and list(got) == ["t1", "t2"]), got


def decorator_names_the_case(t):
    """Every function is named `_`, so the decorator's string is the only name,
    and the cut must key by position or the two collapse into one."""
    got = t.m.candidates(CASE_SUITE, ENTRY["prefilter"])
    return ([(c["fn"], c["name"]) for c in got.values()]
            == [("_", "the peer is read once"), ("_", "the floor fires")]), got


def bare_names_are_candidates(t):
    got = t.m.candidates(BARE_SUITE, ENTRY["prefilter"])
    return ([c["name"] for c in got.values()]
            == ["case_one", "two_cases", "test_three"]), got


def a_helper_is_not_a_candidate(t):
    got = t.m.candidates(DICT_SUITE, ENTRY["prefilter"])
    return all(c["fn"] != "helper" for c in got.values()), got


def a_declarative_suite_has_no_candidate(t):
    return t.m.candidates(FLAT_SUITE, ENTRY["prefilter"]) == {}, ""


def the_body_is_head_capped(t):
    entry = dict(ENTRY, prefilter=dict(ENTRY["prefilter"], head_lines=1))
    got = t.m.candidates(DICT_SUITE, entry["prefilter"])
    return all(c["body"].count("\n") == 0 for c in got.values()), got


# --------------------------------------------------------------- the reading

def a_staged_suite_asks_its_scenario(t):
    """THE CLAIM TEXT IS PINNED BYTE FOR BYTE, which is also what says the
    comment read was the one above `assert Held` and not the one above
    `check Held for 3` -- that one is a pred list and would show here."""
    r, out, _ = repo(t, {"scripts/fixture-dict-test.py":
                         DICT_SUITE.replace("return True", "return bool(1)")})
    got = selects()
    return (r.returncode == 0 and len(got) == 1
            and got[0][1] == [ENTRY["question"]["instructions"].replace(
                "{claim}", c) for c in
                ("A held agent keeps its peer, and `holds` is what says so.",
                 "Every Agent named here is an Agent.")]
            and "1 scenario(s) asked, 2 claim(s)" in out), (got, out)


def a_staged_spec_asks_every_suite(t):
    """A spec edit re-asks the suites that witness what it declares, not only
    the module itself."""
    r, out, _ = repo(t, {"spec/fixture/checks.als":
                         CHECKS.replace("for 3\n-- names `holds`\nrun",
                                        "for 4\n-- names `holds`\nrun")})
    return (r.returncode == 0 and len(selects()) == 5), (len(selects()), out)


def one_call_a_scenario(t):
    """The decorator suite names `Held` twice and `Cov_Held` once: three
    declarations, two distinct names, and `Cov_Held`'s comment carries a claim
    too -- so two calls and never one a claim."""
    r, out, _ = repo(t, {"scripts/fixture-case-test.py":
                         CASE_SUITE.replace("return True", "return bool(1)")})
    got = selects()
    return (r.returncode == 0 and len(got) == 2
            and sorted(len(c) for _, c in got) == [1, 2]), (got, out)


def a_ghost_name_is_skipped(t):
    r, _, d = repo(t, {"scripts/fixture-ghost-test.py":
                       GHOST_SUITE.replace("return True", "return bool(1)")})
    why = skips(d)
    return (r.returncode == 0 and not selects()
            and any("no declaration under spec/" in w for w in why)), why


def a_declarative_suite_is_skipped(t):
    r, _, d = repo(t, {"scripts/fixture-flat-test.py":
                       FLAT_SUITE.replace('"ok"', '"okay"')})
    why = skips(d)
    return (r.returncode == 0 and not selects()
            and any("holds no case by AST" in w for w in why)), why


def a_settled_sentence_is_a_skip_row(t):
    r, _, d = repo(t, {"scripts/fixture-dict-test.py":
                       DICT_SUITE.replace("return True", "return bool(1)")})
    why = skips(d)
    return (any("a section-header comment" in w for w in why)
            and any("names no identifier of the body" in w for w in why)), why


def one_claim_call_a_picked_function(t):
    r, _, _ = repo(t, {"scripts/fixture-dict-test.py":
                       DICT_SUITE.replace("return True", "return bool(1)")},
                   choice="t2")
    got = claims_sent()
    return (r.returncode == 0 and len(got) == 1
            and got[0][0].startswith("an agent with no peer is not held")), got


def no_match_asks_no_claim_call(t):
    r, out, _ = repo(t, {"scripts/fixture-dict-test.py":
                         DICT_SUITE.replace("return True", "return bool(1)")},
                     choice="noMatch")
    return (r.returncode == 0 and len(selects()) == 1
            and claims_sent() == []
            and "1 scenario(s) asked" in out), (len(selects()), claims_sent(), out)


def over_budget_skips(t):
    # MANY CANDIDATES AND NOT ONE LONG ONE: a body is head-capped, so only the
    # number of test functions can carry a state over the budget.
    fat = "".join(f'def case_{k}(t):\n    x = "{"y" * 90}"\n    return True, ""\n\n'
                  for k in range(400))
    big = DICT_SUITE + "\n" + fat
    r, _, d = repo(t, {"scripts/fixture-dict-test.py": big})
    why = skips(d)
    return (r.returncode == 0 and not selects()
            and any("over the" in w and "budget even at" in w for w in why)), why


def fit_weighs_the_whole_state(t):
    """`campaign-jev` measures `{claim, candidates}` and posts it; a fit that
    weighed the candidates alone leaves the claims unweighed, and a state over
    the budget comes back `unknown` with no skip row at all."""
    cands, head = t.m.fit(DICT_SUITE, ENTRY["prefilter"], 100_000, {})
    text = {k: c["name"] + "\n" + c["body"] for k, c in cands.items()}
    bare = len(json.dumps({"candidates": text}).encode("utf-8"))
    tight = t.m.fit(DICT_SUITE, ENTRY["prefilter"], bare + 50,
                    {"claim": {"c1": "x" * 400}})
    return (len(cands) == 2 and head == ENTRY["prefilter"]["head_lines"]
            and tight == ({}, -1)), (head, bare, tight[1])


def entry_reaches_model(t):
    r, _, _ = repo(t, {"scripts/fixture-dict-test.py":
                       DICT_SUITE.replace("return True", "return bool(1)")})
    q = next(iter(SEEN[0]["questions"].values()))
    return (q["instructions"].startswith(ENTRY["question"]["instructions"]
                                         .split("{claim}")[0])
            and "noMatch" in q["criteria"] and "t1" in q["criteria"]
            and "floor" not in q and "no_match" not in q), q


def the_row_carries_its_join_key(t):
    r, _, d = repo(t, {"scripts/fixture-dict-test.py":
                       DICT_SUITE.replace("return True", "return bool(1)")},
                   choice="t1")
    sel = [x for x in rows(d) if x.get("reading") == "suite-witness-select"]
    clm = [x for x in rows(d) if x.get("reading") == "suite-witness-claim"]
    return (len(sel) == 1 and len(clm) == 1
            and sel[0].get("repo") == "o/r"
            and len(sel[0].get("commit", "")) == 40
            and sel[0].get("path") == "scripts/fixture-dict-test.py"
            and sel[0].get("scenario") == "Held"
            and clm[0].get("name") == "a held agent keeps its peer"
            and sel[0].get("wording") and clm[0].get("wording")), (sel, clm)


def shadow_prints_nothing(t):
    r, out, _ = repo(t, {"scripts/fixture-dict-test.py":
                         DICT_SUITE.replace("return True", "return bool(1)")},
                     tier="shadow")
    return r.returncode == 0 and out == "" and len(selects()) == 1, (out,)


def a_commit_touching_neither_asks_nothing(t):
    r, out, _ = repo(t, {"README.md": "fixture, edited\n"})
    return r.returncode == 0 and not SEEN, (out, len(SEEN))


def failure_exits_zero(t):
    r, out, _ = repo(t, {"scripts/fixture-dict-test.py":
                         DICT_SUITE.replace("return True", "return bool(1)")},
                     registry=False)
    return r.returncode == 0, out


CASES = {
    "the `# witnesses:` form is check-sdlc-tie's and is not copied here": the_tie_reads_the_witness_line,
    "a dict value that is no bare name is still a case, its own source the body": a_case_that_is_not_a_function_is_a_candidate,
    "a case named below the literal is a candidate, the last write of a name winning": a_case_named_below_the_literal_is_a_candidate,
    "a `*CASES` dict names the case, not the function": dict_names_the_case,
    "an `@case(\"...\")` suite names every function `_`, so the cut keys by position": decorator_names_the_case,
    "a bare case_* / *_cases / test_* name is a candidate": bare_names_are_candidates,
    "a helper is not a candidate": a_helper_is_not_a_candidate,
    "a declarative suite yields no candidate": a_declarative_suite_has_no_candidate,
    "a candidate's body is capped at the entry's head_lines": the_body_is_head_capped,
    "a staged suite asks the scenario it witnesses": a_staged_suite_asks_its_scenario,
    "a staged spec module asks every suite that witnesses what it declares": a_staged_spec_asks_every_suite,
    "one select call a scenario, every claim of it in that call": one_call_a_scenario,
    "a declared name with no declaration under spec/ logs a skip": a_ghost_name_is_skipped,
    "a suite with no test function logs a skip and asks nothing": a_declarative_suite_is_skipped,
    "a sentence code settled is written as a skip row naming the rule": a_settled_sentence_is_a_skip_row,
    "one claim call a function picked, carrying that function's body": one_claim_call_a_picked_function,
    "a claim picking noMatch asks no claim call": no_match_asks_no_claim_call,
    "a select state over the budget is not sent and logs a skip": over_budget_skips,
    "the fit weighs the whole state, the claims included": fit_weighs_the_whole_state,
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "the row carries the reading, the wording and the join key": the_row_carries_its_join_key,
    "at tier shadow nothing is printed and the call is still made": shadow_prints_nothing,
    "a commit touching neither a suite nor a spec module asks nothing": a_commit_touching_neither_asks_nothing,
    "a reader that could not read exits 0": failure_exits_zero,
}

MUTATIONS = [
    ("a dict value that is no bare name dropped",
     "        else:\n            inline.append((v, name))",
     "        else:\n            pass",
     "a dict value that is no bare name is still a case, its own source the body"),
    ("the dict key dropped for the function's own name",
     'label[id(first_of[v.id])] = name', 'pass',
     "a `*CASES` dict names the case, not the function"),
    ("a case named below the literal dropped",
     "                picked[t.slice.value] = n.value",
     "                pass",
     "a case named below the literal is a candidate, the last write of a name winning"),
    ("the literal's placeholder left to win over the line that fills it",
     "                picked[t.slice.value] = n.value",
     "                picked.setdefault(t.slice.value, n.value)",
     "a case named below the literal is a candidate, the last write of a name winning"),
    ("the candidates keyed by name",
     '        out[f"t{len(out) + 1}"] = {\n            "name": name, "fn": n.name,',
     '        out[f"t{n.name}"] = {\n            "name": name, "fn": n.name,',
     "an `@case(\"...\")` suite names every function `_`, so the cut keys by position"),
    ("the decorator's name never read",
     '                name = d.args[0].value', '                pass',
     "an `@case(\"...\")` suite names every function `_`, so the cut keys by position"),
    ("the name rule not read from the entry",
     'name_rule = re.compile(prefilter["names"])', 'name_rule = re.compile(r".*")',
     "a helper is not a candidate"),
    ("every function a candidate",
     "        if name is None:\n            continue", "        name = name or n.name",
     "a helper is not a candidate"),
    ("the body never capped",
     '            "name": name, "fn": n.name, "first": at, "last": n.end_lineno,\n'
     '            "body": "\\n".join(lines[at - 1:min(n.end_lineno, at - 1 + head)])}',
     '            "name": name, "fn": n.name, "first": at, "last": n.end_lineno,\n'
     '            "body": "\\n".join(lines[at - 1:n.end_lineno])}',
     "a candidate's body is capped at the entry's head_lines"),
    ("a spec edit read as touching its own file alone",
     "            if suite not in staged and not (set(names) & moved):",
     "            if suite not in staged:",
     "a staged spec module asks every suite that witnesses what it declares"),
    ("one call a claim rather than a scenario",
     '    claims = {f"c{i}": c for i, c in enumerate(found, 1)}',
     '    claims = {f"c{i}": c for i, c in enumerate(found[:1], 1)}',
     "one select call a scenario, every claim of it in that call"),
    ("a name with no declaration asked anyway",
     "                if name not in tree.scenarios or name not in defs:",
     "                if False:",
     "a declared name with no declaration under spec/ logs a skip"),
    ("a suite with no candidate asked anyway",
     "                if not cands:", "                if False:",
     "a suite with no test function logs a skip and asks nothing"),
    ("a settled sentence left unlogged",
     '                    jev.skip(READER, f"{suite} {name}: {sentence}", why, env,\n'
     '                             cwd=HERE)', "                    pass",
     "a sentence code settled is written as a skip row naming the rule"),
    ("a claim call for noMatch",
     "        if t in cands:", "        if t:",
     "a claim picking noMatch asks no claim call"),
    ("every claim its own claim call",
     "            by_fn.setdefault(t, {})[cid] = claims[cid]",
     "            by_fn[t + cid] = {cid: claims[cid]}; cands[t + cid] = cands[t]",
     "one claim call a function picked, carrying that function's body"),
    ("the budget not read",
     '        if len(json.dumps(dict(rest, candidates=text))\n'
     '               .encode("utf-8")) <= budget:',
     "        if True:",
     "a select state over the budget is not sent and logs a skip"),
    ("the claims left out of what the fit weighs",
     "        if len(json.dumps(dict(rest, candidates=text))",
     '        if len(json.dumps(dict(candidates=text))',
     "the fit weighs the whole state, the claims included"),
    ("the row keyed by the suite alone",
     "                         dict(jev.commit_key(cwd=HERE), path=suite,\n"
     "                              scenario=name), env)",
     '                         {"path": suite}, env)',
     "the row carries the reading, the wording and the join key"),
    ("the picked case never named on the claim row",
     "reader=READER, key=dict(key, name=cands[t][\"name\"]),",
     "reader=READER, key=key,",
     "the row carries the reading, the wording and the join key"),
    ("the tier not read before printing",
     '        if reg[SELECT]["tier"] != "shadow":', "        if True:",
     "at tier shadow nothing is printed and the call is still made"),
    ("every tracked suite read whatever the commit holds",
     "            if suite not in staged and not (set(names) & moved):",
     "            if False:",
     "a commit touching neither a suite nor a spec module asks nothing"),
    ("the failure boundary removed",
     "    except Exception as e:  # noqa: BLE001 -- a reading never refuses a commit",
     "    except ZeroDivisionError as e:",
     "a reader that could not read exits 0"),
]


def main():
    harness.mutate(SOURCE, load, CASES, MUTATIONS)
    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
