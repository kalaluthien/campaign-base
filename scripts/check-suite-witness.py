#!/usr/bin/env python3
"""Log which test function of a suite exercises each claim of the scenario it witnesses, and refuse nothing.

THE READINGS `suite-witness-select` and `suite-witness-claim` in
scripts/jev/readings.json, asked through scripts/campaign-jev.py at
`pre-commit` beside check-sdlc-tie.py. The entries hold the questions, their
criteria, the state's fields, the prefilter's patterns, the thresholds and the
tier; this reads them and writes none of them. How to ask Jev well in general
is the `asking-jev` skill's `references/`, not this file's.

CHECK-SDLC-TIE TIES A SUITE TO A SCENARIO BY NAME AND STOPS THERE: `Tree.declared`
answers which names a suite's `# witnesses:` lines carry, never which of its
test functions carries one. This is the first reader at that grain, so it is
not a second reader of T6/T7/T8 -- and to keep it one, WHICH PATHS ARE SUITES,
WHICH NAMES EACH DECLARES AND WHICH ARE REAL SCENARIOS ARE ALL `Tree`'s, built
here and asked. The regex and the comma split are not copied.

THE CLAIM IS THE SCENARIO'S COMMENT, cut exactly as `model-comment` cuts one --
its `definitions`, its `MARKER`, its `claims` and so S1's `SENTENCE`, header
skip and identifier skip, all IMPORTED. What differs is which definitions are
read: not every pred, fun, assert and fact a staged hunk overlaps, but the one
whose NAME a suite declares, wherever in spec/ it sits.

WHAT IT READS, from the INDEX, so what is judged is what the commit holds:

  suites     `Tree.suites`, each one's names `Tree.declared` and the real ones
             `Tree.scenarios`; a staged suite is read, and so is every suite
             naming a scenario a staged spec module declares
  claims     one sentence of the comment block above that scenario's own
             declaration -- NOT above its `run`/`check` line, which carries a
             one-line pred list and no claim
  candidates the suite's cases by AST, name plus body capped at
             `prefilter.head_lines` -- halved toward `head_floor` where the
             state would not fit the budget -- keyed t1..tN in file order. A case is a
             `*CASES` dict entry, a function `@case("...")` decorates, or one
             whose own name matches `prefilter.names`; the name is the dict key
             or the decorator's string where there is one. A DICT VALUE THAT IS
             NOT A BARE NAME IS STILL A CASE -- a `lambda`, or a call like
             `refusal(...)` that returns one -- and its body is the value's own
             source, since there is no `def` to point at. KEYED BY POSITION,
             because a decorated suite calls every function `_`
  select     ONE call a scenario, state `{candidates}`, one `choice` a claim
             over the functions and `noMatch`, the claim in the instructions
  claim      ONE call a function some claim picked, state `{test_fn}`, one
             `choice` supports / contradicts / says_nothing a claim that picked
             it; nothing is asked for a claim that picked none
  logged     `<suite> <scenario> select` and `<suite> <scenario> claim <t> <name>`
  skipped    one row for a declared name with no declaration under spec/, for a
             scenario whose comment yields no claim, for a suite yielding no
             candidate, and for a select state over the budget

THE KEY is the repository, the sha this commit sits on, the suite path, the
scenario, and -- on a claim call -- the picked case's name, which is what
`witness-case-kept` joins on.

WHAT THE FLAG READS is the SELECT call's `noMatch`, and neither claim option:
over 78 states, three runs, P(noMatch) separated the 6 claims a mutant proves a
case carries from the 72 none does at AUC 0.97 against 0.92 for a token-overlap
baseline, while `supports` read 0.73-0.77 and `says_nothing` 0.80-0.88 over the
15-16 states that reached a claim call at all. The floor is 0.0 because a floor
costs positives faster than it buys negatives. The band, the counts and the two
cautions it does not carry -- 6 positives, and no held-out slice -- are the
select entry's `bands`; the cases are scripts/jev/corpus/suite-witness-select.jsonl.

THE EXIT STATUS IS 0 on every path, a failure of this script included: a
judgment here never refuses a commit. At `shadow` nothing is printed at all;
the log rows are the record.

Usage: scripts/check-suite-witness.py --staged
"""
import ast
import importlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELECT, CLAIM = "suite-witness-select", "suite-witness-claim"
READER = "check-suite-witness.py --staged"
S1, S3 = "check-cited-claims.py", "check-model-comment.py"
TIE = "check-sdlc-tie.py"
SPEC = re.compile(r"spec/.+\.als")


def candidates(source, prefilter):
    """{t1..tN: {name, fn, body, first, last}} for one suite's cases, or {}.

    THE NAME IS WHAT THE SUITE CALLS THE CASE and not what Python calls the
    function: a `@case("...")` suite names all 125 of them `_`, so the
    decorator's string is the only name a reader could act on. The dict key
    wins over a bare `case_*` match for the same reason, and the whole cut is
    keyed by POSITION, because a name is not unique here.

    A DICT VALUE THAT IS NOT A BARE NAME IS STILL A CASE. `campaign-close-test`
    writes 73 of its 158 as `refusal(...)`, `check-read-range-test` all 14 that
    way and `campaign-jev-test` 11 as lambdas: read as functions they vanish,
    and a case a reader cannot name can only come back `noMatch` -- the very
    option the band is declared on. So a value with no `def` behind it carries
    the VALUE's own source as its body.

    A CASE IS ALSO NAMED AFTER THE LITERAL CLOSES. `campaign-jev-test` writes
    108 of its 133 as `CASES["..."] = fn` below the dict, and two of those
    names are in the literal as a `None` placeholder the later line fills --
    so the literal alone reads 26 cases, one of them a candidate whose body is
    the placeholder line. Both forms are collected by name and THE LAST WRITE
    OF A NAME WINS, which is what Python itself does to that dict."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    lines = source.split("\n")
    fns = [n for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    inline = []
    first_of = {}
    for n in fns:
        first_of.setdefault(n.name, n)
    label = {}
    picked = {}
    for n in tree.body:
        if not isinstance(n, ast.Assign):
            continue
        if isinstance(n.value, ast.Dict) and any(
                isinstance(t, ast.Name) and t.id.endswith("CASES")
                for t in n.targets):
            for k, v in zip(n.value.keys, n.value.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    picked[k.value] = v
        for t in n.targets:
            if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                    and t.value.id.endswith("CASES")
                    and isinstance(t.slice, ast.Constant)
                    and isinstance(t.slice.value, str)):
                picked[t.slice.value] = n.value
    for name, v in picked.items():
        if isinstance(v, ast.Name) and v.id in first_of:
            label[id(first_of[v.id])] = name
        else:
            inline.append((v, name))
    name_rule = re.compile(prefilter["names"])
    head = prefilter["head_lines"]
    out = {}
    for n in sorted(fns + [v for v, _ in inline],
                    key=lambda x: min([d.lineno for d in
                                       getattr(x, "decorator_list", [])] + [x.lineno])):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            at = n.lineno
            out[f"t{len(out) + 1}"] = {
                "name": next(t for v, t in inline if v is n), "fn": "",
                "first": at, "last": n.end_lineno,
                "body": "\n".join(lines[at - 1:min(n.end_lineno, at - 1 + head)])}
            continue
        name = label.get(id(n))
        for d in n.decorator_list:
            if (isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                    and d.func.id == "case" and d.args
                    and isinstance(d.args[0], ast.Constant)
                    and isinstance(d.args[0].value, str)):
                name = d.args[0].value
        if name is None and name_rule.match(n.name):
            name = n.name
        if name is None:
            continue
        at = min([d.lineno for d in n.decorator_list] + [n.lineno])
        out[f"t{len(out) + 1}"] = {
            "name": name, "fn": n.name, "first": at, "last": n.end_lineno,
            "body": "\n".join(lines[at - 1:min(n.end_lineno, at - 1 + head)])}
    return out


def fit(source, prefilter, budget, rest):
    """(the candidates, the head the state fits at), ({}, 0) where the suite
    holds no case, or ({}, -1) where its cases do not fit at `head_floor` --
    two different facts, so the skip row says which.

    `rest` IS THE REST OF THE STATE and not a courtesy: `campaign-jev` measures
    what it is about to post, which is `{claim, candidates}`, so a fit that
    weighed the candidates alone left the claims unweighed -- and a state over
    the budget comes back `unknown` with no skip row, the one thing this
    function exists to write.

    A HEAD SHORT ENOUGH FOR THE WORST SUITE IS TOO SHORT FOR THE REST, so the
    cap is squeezed only where it has to be: the entry's `head_lines` first,
    then halved to `head_floor`. `campaign-close-test.py` is why -- its 158
    cases carry 8.6 KB of NAMES before a line of body, and at the declared 40 a
    reading of it is 62 KB against a 60 KB budget. Dropping every suite to what
    that one needs would cost the other eighteen most of their evidence."""
    head = prefilter["head_lines"]
    while head >= prefilter["head_floor"]:
        cands = candidates(source, dict(prefilter, head_lines=head))
        if not cands:
            return {}, 0
        text = {t: c["name"] + "\n" + c["body"] for t, c in cands.items()}
        if not jev_module().over_budget(dict(rest, candidates=text), budget):
            return cands, head
        head //= 2
    return {}, -1


def ask_pair(reg, suite, scenario, found, cands, jev, key, env=None):
    """The two calls for one (suite, scenario); {claim id: the key picked}."""
    text = {t: c["name"] + "\n" + c["body"] for t, c in cands.items()}
    subject = f"{suite} {scenario}"
    claims = {f"c{i}": c for i, c in enumerate(found, 1)}
    return jev.judge_chain(
        SELECT, {"candidates": text, "claim": claims},
        lambda t, asked: {
            "group": reg[CLAIM]["group"],
            "state": {"test_fn": text[t], "claim": asked},
            "read": f"{subject} claim {t} {cands[t]['name']}",
            "key": dict(key, name=cands[t]["name"])}
        if t in cands else None,
        read=f"{subject} select", reg=reg, reader=READER, key=key, env=env,
        cwd=HERE)


def main(argv, out=sys.stdout, env=None):
    if argv != ["--staged"]:
        print("Usage: scripts/check-suite-witness.py --staged", file=sys.stderr)
        return 2
    asked = calls = skipped = 0
    try:
        jev = jev_module()
        reg = jev.load_registry()
        if SELECT not in reg or CLAIM not in reg:
            return 0
        prefilter = reg[SELECT]["prefilter"]
        s1 = jev.load_sibling(S1)
        s3 = jev.load_sibling(S3)
        tie = jev.load_sibling(TIE)
        staged = [p for p in s1.git("diff", "--cached", "--name-only", "-z",
                                    "--diff-filter=d").split("\0") if p]
        tracked = [p for p in s1.git("ls-files", "-z").split("\0") if p]
        # ONE TREE, ASKED. Which paths are suites, which names each declares and
        # which of those are real scenarios are all check-sdlc-tie's readings;
        # a copy of its `WITNESSES` here would be the second reader AGENTS.md
        # refuses, and would drift the first time that line moved.
        in_scripts = jev.load_sibling("check-tree-shape.py").in_scripts_dir
        # `wanted` covers the snapshot and the suites and NOT spec/: the tie
        # never reads a module's text, so the spec texts are fetched beside it.
        want = tie.wanted(tracked, in_scripts)
        spec = [p for p in tracked if SPEC.fullmatch(p)]
        got = s1.index_texts(sorted(set(want) | set(spec)))
        tree = tie.Tree("index", tracked, got, in_scripts)
        texts = {p: t for p, t in got.items() if SPEC.fullmatch(p)}
        defs = {}
        for path, name, comment, body, _, _ in s3.definitions(texts, s1):
            defs.setdefault(name, (path, comment, body))
        # WHICH SCENARIOS A STAGED SPEC MODULE DECLARES, so a spec edit re-asks
        # the suites that witness it and not only its own file.
        moved = {n for n, (p, _, _) in defs.items() if p in staged}
        for suite in sorted(tree.suites):
            names = sorted(tree.declared(suite))
            if not names:
                continue
            if suite not in staged and not (set(names) & moved):
                continue
            for name in names:
                if name not in tree.scenarios or name not in defs:
                    skipped += 1
                    jev.skip(READER, f"{suite} {name}", "the name is no "
                             "scenario of the tree, or has no declaration under "
                             "spec/, so it has no comment to read", env,
                             cwd=HERE)
                    continue
                _, comment, body = defs[name]
                found, dropped = s3.claims(comment, body,
                                           reg["model-comment"]["prefilter"], s1)
                for sentence, why in dropped:
                    skipped += 1
                    jev.skip(READER, f"{suite} {name}: {sentence}", why, env,
                             cwd=HERE)
                if not found:
                    continue
                # the fit is per SCENARIO and not per suite: the claims are
                # half the state, and they are only known here.
                cands, head = fit(tree.texts.get(suite, ""), prefilter,
                                  jev.STATE_BUDGET,
                                  {"claim": {f"c{i}": c for i, c
                                             in enumerate(found, 1)}})
                if not cands:
                    skipped += 1
                    jev.skip(READER, f"{suite} {name}",
                             (f"its cases are over the {jev.STATE_BUDGET}-byte "
                              f"budget even at {prefilter['head_floor']} head "
                              f"line(s)") if head < 0 else
                             ("the suite holds no case by AST: no `*CASES` "
                              "dict, no `@case(...)` decorator and no name the "
                              "entry's `names` matches"), env, cwd=HERE)
                    continue
                asked += len(found)
                calls += 1
                # `path` IS THE SUITE and not the spec module: the join reads
                # what happened to the case, and a sha alone names no file.
                ask_pair(reg, suite, name, found, cands, jev,
                         dict(jev.commit_key(cwd=HERE), path=suite,
                              scenario=name), env)
        if reg[SELECT]["tier"] != "shadow":
            print(f"check-suite-witness `{SELECT}`: {calls} scenario(s) asked, "
                  f"{asked} claim(s); {skipped} settled by code", file=out)
    except Exception as e:  # noqa: BLE001 -- a reading never refuses a commit
        if reg_tier(SELECT) != "shadow":
            print(f"check-suite-witness: could not read the commit "
                  f"({e.__class__.__name__}: {e}); nothing asked, exit status "
                  f"unmoved", file=out)
    return 0


def reg_tier(reading):
    """The reading's tier, or `shadow` when the registry itself did not read --
    silence being the safer half when nothing is known."""
    try:
        return jev_module().load_registry()[reading]["tier"]
    except Exception:  # noqa: BLE001
        return "shadow"


def jev_module():
    """campaign-jev, which holds every step around the call (rule-check#506).
    Called inside `main`'s boundary, so a campaign-jev that will not load is a
    reading lost and never a commit refused."""
    return importlib.import_module("campaign-jev")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
