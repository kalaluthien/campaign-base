#!/usr/bin/env python3
"""Prove the role table has the shape its readers take it in.

The table is values, so a case pinning each value would be a second copy of it.
What is checked instead is what a reader silently loses when the shape drifts:
a key the guard subscripts that a row no longer has, a structural kind word the
guard matches that the tracker no longer spells, an exception for a subcommand
the role never held. Each of those still loads and still lists; only the
verdicts change.

Usage: .claude/skills/assuming-role/scripts/campaign-roles-test.py
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[3]
GUARD = BASE / "scripts" / "check-campaign-claim.py"


def load(path, name):
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, str(path)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    m = load(HERE / "campaign-roles.py", "croles")
    tracker = load(BASE / "scripts" / "campaign-tracker.py", "ctracker")
    ran, fails = [], []

    def check(name, cond, detail=""):
        ran.append(name)
        if not cond:
            fails.append(f"{name}  {detail}".rstrip())

    check("the role words are the table's keys, in its order",
          m.ROLE_WORDS == tuple(m.ROLES), m.ROLE_WORDS)
    check("no-role is not a role word, so a nameless session holds no row",
          m.NO_ROLE not in m.ROLES)

    shapes = {role: set(row) for role, row in m.ROLES.items()}
    check("every row has the same keys",
          len({frozenset(s) for s in shapes.values()}) == 1, shapes)

    # WHAT THE GUARD SUBSCRIPTS, read out of its source: `ROLES["<role>"]`
    # and the key after it. A row renamed here would leave that subscript a
    # KeyError the guard's broad handler turns into a refusal of every call.
    # A row it holds as `licence` is subscripted there, by a word key; the
    # structural kind keys have a space or a hyphen and are checked below.
    guard = GUARD.read_text()
    used = re.findall(r'ROLES\["(\w+)"\](?:\["(\w+)"\])?', guard)
    used += [(r, k) for k in set(re.findall(r'licence\["(\w+)"\]', guard))
             for r in m.ROLES]
    check("the guard subscripts the table at least once", used)
    missing = [(r, k) for r, k in used
               if r not in m.ROLES or (k and k not in m.ROLES[r])]
    check("every role and key the guard subscripts is in the table",
          not missing, missing)

    # THE GUARD MATCHES THESE KEYS against the tracker's `kind_of`, so a
    # spelling the tracker does not return grants nothing and says nothing.
    kinds = {tracker.CAMPAIGN, tracker.SUB_ISSUE}
    bad = {role: set(row.get("own_campaign_gh", {})) - kinds
           for role, row in m.ROLES.items()
           if set(row.get("own_campaign_gh", {})) - kinds}
    check("own_campaign_gh is keyed by the tracker's structural kind words",
          not bad, bad)

    def pairs(v):
        return isinstance(v, frozenset) and all(
            isinstance(p, tuple) and len(p) == 2
            and all(isinstance(w, str) for w in p) for p in v)
    check("gh is a frozenset of subcommand words in every row",
          all(isinstance(r.get("gh"), frozenset)
              and all(isinstance(w, str) for w in r["gh"])
              for r in m.ROLES.values()))
    check("gh_except and every own_campaign_gh value are (subcommand, verb) pairs",
          all(pairs(r.get("gh_except")) and all(
              pairs(v) for v in r.get("own_campaign_gh", {}).values())
              for r in m.ROLES.values()))
    dead = {role: sorted(p for p in r.get("gh_except", ())
                         if p[0] not in r.get("gh", ()))
            for role, r in m.ROLES.items()}
    check("an exception names a subcommand its row holds, or it excepts nothing",
          not any(dead.values()), dead)

    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            code = m.main()
    except Exception as e:                  # a row the listing cannot print
        code = repr(e)
    check("the listing exits 0 and names every role",
          code == 0 and all(f"\n  {r}\n" in out.getvalue() for r in m.ROLES),
          code)

    for f in fails:
        print(f"FAIL  {f}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
