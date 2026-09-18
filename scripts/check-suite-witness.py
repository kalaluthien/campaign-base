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
not a second reader of T6/T7/T8; the witness regex it needs is the entry's
`prefilter.witnesses` and not a copy of that guard's.

THE CLAIM IS THE SCENARIO'S COMMENT, cut exactly as `model-comment` cuts one --
its `definitions`, its `MARKER`, its `claims` and so S1's `SENTENCE`, header
skip and identifier skip, all IMPORTED. What differs is which definitions are
read: not every pred, fun, assert and fact a staged hunk overlaps, but the one
whose NAME a suite declares, wherever in spec/ it sits.

WHAT IT READS, from the INDEX, so what is judged is what the commit holds:

  suites     every tracked `.py` carrying a `# witnesses:` line, which is the
             entry's `prefilter.witnesses`; a staged one is read, and so is
             every suite naming a scenario a staged spec module declares
  claims     one sentence of the comment block above that scenario's own
             declaration -- NOT above its `run`/`check` line, which carries a
             one-line pred list and no claim
  candidates the suite's test functions by AST, name plus body capped at
             `prefilter.head_lines`, keyed t1..tN in file order. A function is
             one when a `*CASES` dict names it, when `@case("...")` decorates
             it, or when its own name matches `prefilter.names`; the name is
             the dict key or the decorator's string where there is one. KEYED
             BY POSITION, because a decorated suite calls every function `_`
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
over 72 states, three runs, P(noMatch) separated the 6 claims a mutant proves a
case carries from the 66 none does at AUC 0.96 against 0.91 for a token-overlap
baseline, while `supports` read 0.74-0.82 and `says_nothing` 0.79-0.85 over the
13-14 states that reached a claim call at all. The floor is 0.0 because a floor
costs positives faster than it buys negatives. The band and the counts are the
select entry's `bands`; the cases are scripts/jev/corpus/suite-witness-select.jsonl.

THE EXIT STATUS IS 0 on every path, a failure of this script included: a
judgment here never refuses a commit. At `shadow` nothing is printed at all;
the log rows are the record.

Usage: scripts/check-suite-witness.py --staged
"""
import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELECT, CLAIM = "suite-witness-select", "suite-witness-claim"
REGISTRY = HERE / "jev" / "readings.json"
READER = "check-suite-witness.py --staged"
S1, S3 = "check-cited-claims.py", "check-model-comment.py"
SPEC = re.compile(r"spec/.+\.als")
SUITE = re.compile(r".+\.py")


def declared(text, witnesses):
    """The scenario names one suite's `# witnesses:` lines carry, in order."""
    out = []
    for m in re.finditer(witnesses, text, re.M):
        out += [n.strip() for n in m.group(1).split(",") if n.strip()]
    return list(dict.fromkeys(out))


def candidates(source, prefilter):
    """{t1..tN: {name, fn, body, first, last}} for one suite's text, or {}.

    THE NAME IS WHAT THE SUITE CALLS THE CASE and not what Python calls the
    function: a `@case("...")` suite names all 125 of them `_`, so the
    decorator's string is the only name a reader could act on. The dict key
    wins over a bare `case_*` match for the same reason, and the whole cut is
    keyed by POSITION, because a name is not unique here."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    lines = source.split("\n")
    fns = [n for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    first_of = {}
    for n in fns:
        first_of.setdefault(n.name, n)
    label = {}
    for n in tree.body:
        if not (isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)):
            continue
        if not any(isinstance(t, ast.Name) and t.id.endswith("CASES")
                   for t in n.targets):
            continue
        for k, v in zip(n.value.keys, n.value.values):
            if (isinstance(v, ast.Name) and v.id in first_of
                    and isinstance(k, ast.Constant) and isinstance(k.value, str)):
                label[id(first_of[v.id])] = k.value
    name_rule = re.compile(prefilter["names"])
    head = prefilter["head_lines"]
    out = {}
    for n in fns:
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


def ask_pair(reg, suite, scenario, found, cands, jev, key, env=None):
    """The two calls for one (suite, scenario); {claim id: the key picked}."""
    text = {t: c["name"] + "\n" + c["body"] for t, c in cands.items()}
    subject = f"{suite} {scenario}"
    if len(json.dumps({"candidates": text}).encode("utf-8")) > jev.STATE_BUDGET:
        jev.skip(READER, f"{subject} select", f"the {len(cands)} test "
                 f"function(s) are over the {jev.STATE_BUDGET}-byte budget",
                 env, cwd=HERE)
        return {}
    claims = {f"c{i}": c for i, c in enumerate(found, 1)}
    got = jev.judge(reg[SELECT]["group"],
                    {"candidates": text, "claim": claims},
                    read=f"{subject} select", reader=READER, key=key,
                    env=env, cwd=HERE)
    picked = {cid: (a.raw or {}).get("choice") for cid, a in
              jev.words_of(reg[SELECT], got.verdicts[SELECT]).items()}
    by_fn = {}
    for cid, t in picked.items():
        if t in cands:
            by_fn.setdefault(t, {})[cid] = claims[cid]
    for t, asked in sorted(by_fn.items()):
        jev.judge(reg[CLAIM]["group"],
                  {"test_fn": text[t], "claim": asked},
                  read=f"{subject} claim {t} {cands[t]['name']}",
                  reader=READER, key=dict(key, name=cands[t]["name"]),
                  env=env, cwd=HERE)
    return picked


def main(argv, out=sys.stdout, env=None):
    if argv != ["--staged"]:
        print("Usage: scripts/check-suite-witness.py --staged", file=sys.stderr)
        return 2
    asked = calls = skipped = 0
    try:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        if SELECT not in reg or CLAIM not in reg:
            return 0
        prefilter = reg[SELECT]["prefilter"]
        s1 = load_sibling(S1)
        s3 = load_sibling(S3)
        jev = load_sibling("campaign-jev.py")
        staged = [p for p in s1.git("diff", "--cached", "--name-only", "-z",
                                    "--diff-filter=d").split("\0") if p]
        tracked = [p for p in s1.git("ls-files", "-z").split("\0") if p]
        texts = s1.index_texts([p for p in tracked if SPEC.fullmatch(p)])
        defs = {}
        for path, name, comment, body, _, _ in s3.definitions(texts, s1):
            defs.setdefault(name, (path, comment, body))
        suites = s1.index_texts([p for p in tracked if SUITE.fullmatch(p)])
        # WHICH SCENARIOS A STAGED SPEC MODULE DECLARES, so a spec edit re-asks
        # the suites that witness it and not only its own file.
        moved = {n for n, (p, _, _) in defs.items() if p in staged}
        for suite in sorted(suites):
            names = declared(suites[suite], prefilter["witnesses"])
            if not names:
                continue
            if suite not in staged and not (set(names) & moved):
                continue
            cands = candidates(suites[suite], prefilter)
            for name in names:
                if name not in defs:
                    skipped += 1
                    jev.skip(READER, f"{suite} {name}", "the name has no "
                             "declaration under spec/, so it has no comment to "
                             "read", env, cwd=HERE)
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
                if not cands:
                    skipped += 1
                    jev.skip(READER, f"{suite} {name}", "the suite holds no "
                             "test function by AST: its cases are declarative "
                             "and no candidate could be named", env, cwd=HERE)
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
        return json.loads(REGISTRY.read_text(encoding="utf-8"))[reading]["tier"]
    except Exception:  # noqa: BLE001
        return "shadow"


def load_sibling(name):
    """check-cited-claims.py's own loader, by path, so there is one of it."""
    import importlib.machinery
    import importlib.util
    src = HERE / name
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(src)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
