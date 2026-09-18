#!/usr/bin/env python3
"""Print every candidate for each spec/ failure mode, with the reason it was flagged.

The script half of the dead-elimination rule (sdlc-alloy#421 DECISION,
2026-09-14): a script finds ALL candidates over a tree, an agent judges only
that set, and the owner vetoes the table. What makes an artifact dead is that
judgement; how one leaves is `RemoveArtifact` in spec/sdlc/system.als, and
`S9_DeadElimination` is the removal of one this lists under `unwitnessed`.

  defs         every sig/pred/fun/fact/enum/check/run/assert: mentions across
               .als files and files named outside spec/
  unwitnessed  a snapshot command no suite's `# witnesses:` line and no html
               form's `data-refines` names (orphan scenario)
  unpaired     a `_Bites` run with no check of its stem, and a check with no
               `_Bites` (a control of no rule, a rule with no red-first proof)
  duplicate    two predicates or asserts whose bodies are the same text, and a
               `Cov_` name declared in more than one module
  undefined    a declared witness or refines name the snapshot does not list;
               a path-like token in a code file naming no tracked file
  untied       a code path with no suite, or whose suite declares no listed
               scenario; each compared with the tree's own LEGACY,
               read as check-sdlc-tie.py reads it
  premise      a definition whose name carries a multi-machine or handoff
               premise, one no tree fact can observe
  mismatch     a declared witness name spelled nowhere else in its suite
  ruling       not in `all`: asks Jev, per candidate command, the two rulings
               a survey makes by hand, each over a fact code fetched first --
               `dead-premise` (has the situation it needs ever happened here)
               and `dead-reader` (does a live decision read what it checks)

THE RULING MODE is the agent's half made a reading, at the tier its registry
entries in scripts/jev/readings.json give (`shadow`: it logs to the base's
`runtime/jev.log` and prints nothing). Its candidates are the commands, never
a `Cov_` (alloy-check's gate keeps those whatever they duplicate):

  dead-premise  a command whose text or a predicate it names carries a premise
                `PREMISES` names -- a handoff, a narrowed profile, or another
                machine -- asked over `{row, fact}`, the fact being that
                premise's own record: the `bound:` labels on every campaign
                issue, the tracker's NOTEs whose first line reports a
                hand-off, or the `optional = ...` lines of the kind references
  dead-reader   a command no suite declares, asked over `{row, fact}`, the
                fact being, for it and each predicate it names, the files
                outside spec/ that name it -- the `defs` mentions

Each row's `flag` is P(not_shown) or P(dead), the option each entry's
`bands.how` names; no cut is declared on either.

The duplicate ruling is not asked: sdlc-alloy#343 ruled one pair "not one",
and a `Cov_` names no pair to compare (DECISION 5726744824).

WHAT IT READS: the tracked files of the repository holding ROOT (default: the
working directory), from its top, through `git ls-files`. What a suite, a code path, a
scenario, a declaration and a refinement are is check-sdlc-tie.py's `Tree`,
and what a script's own directory is check-tree-shape.py's `in_scripts_dir`,
both imported from beside this file, so the candidates are counted over the
same sets the guard judges. The .als definitions are read here, with comments
blanked, because the snapshot lists commands and not the predicates beside them.

OUTPUT: each mode prints `MODE\\tcount\\t<set it counted>` first, then one row
per candidate, `MODE\\t<entity>\\t<name>\\t<reason>`. It prints and never
refuses: exit 0 whatever it found.

Usage: scripts/spec-dead-count.py [--mode <mode>|all|ruling] [ROOT]
"""
import argparse
import collections
import datetime
import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MODES = ("defs", "unwitnessed", "unpaired", "duplicate", "undefined", "untied",
         "premise", "mismatch")
D = re.compile(r"\s*(?:abstract\s+|one\s+|lone\s+|some\s+|var\s+)*"
               r"(sig|pred|fact|fun|enum|check|run|assert)\s+(\w+)")
NEG = re.compile(r"Unguarded|StillLoses|Bites|Without|Insufficient|Escapes|"
                 r"RepairExcludes|Control|Blocks|Refused|Closes|Admits", re.I)
MM = re.compile(r"Machine|Elsewhere|Migrat|Bound|Handoff|Heir|Successor|Predecessor", re.I)
WORD = re.compile(r"\w+")
# A PREMISE, BY THE WORD ITS RULE IS WRITTEN IN, first match wins: a handoff
# rule names machines too, and its own record is the hand-off, not the label.
# Another machine is read off the command's scope (`2 Machine`) or a word that
# only a second machine gives meaning, never off `Machine` alone, which every
# orchestration rule names.
PREMISES = (("handoff", re.compile(r"Handoff|Heir|Successor|Predecessor")),
            ("narrowing", re.compile(r"[Nn]arrowing")),
            ("machine", re.compile(r"\b(?:exactly\s+)?[2-9]\s+Machine\b|coLocated|"
                                   r"Elsewhere|two machines", re.I)))
HANDOFF = re.compile(r"^NOTE [^:]+: .*\bhand(?:ing)?[- ]?off\b", re.I)
PROFILE = re.compile(r"^`optional = [^`]*`", re.M)
BASE_REPO = "kalaluthien/campaign-base"
FACT_FILES = 6
FLAG = {"dead-premise": "not_shown", "dead-reader": "dead"}
PATH = re.compile(r"(?<![\w/])((?:spec|scripts|\.claude|\.github)/[\w./-]+"
                  r"\.(?:als|py|sh|md|jsonl|json|yml|html))(?!\w)")


# campaign-jev holds every step around the call and loads the siblings
# (rule-check#506).
jev = importlib.import_module("campaign-jev")
tie = jev.load_sibling("check-sdlc-tie.py")
shape = jev.load_sibling("check-tree-shape.py")


def code_lines(text):
    """The .als text with its comments blanked, line structure kept."""
    text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    return re.sub(r"(--|//)[^\n]*", "", text).split("\n")


def cls(name):
    return "cov" if name.startswith("Cov_") else "control" if NEG.search(name) else "scenario"


def declarations(als, text):
    """name -> [(kind, path, text)] for every definition: the comment block
    directly above it and the declaration to the next blank line -- or, for
    a command, its own line alone, since commands sit in runs of one line
    each. A command and the pred or assert it runs share a name; both are
    kept."""
    out = collections.defaultdict(list)
    for f in als:
        lines = text[f].split("\n")
        for i, line in enumerate(lines):
            m = D.match(line)
            if not m or line[:1].isspace():
                continue
            j = i
            if j > 0 and lines[j - 1].rstrip().endswith("*/"):
                while j > 0 and "/*" not in lines[j - 1]:
                    j -= 1
                j -= 1
            while j > 0 and lines[j - 1].lstrip().startswith("--"):
                j -= 1
            k = i
            if m.group(1) in ("check", "run"):
                while k + 1 < len(lines) and "{" in line and "}" not in "\n".join(lines[i:k + 1]):
                    k += 1
            else:
                while k + 1 < len(lines) and lines[k + 1].strip():
                    k += 1
            out[m.group(2)].append((m.group(1), f, "\n".join(lines[j:k + 1])))
    return out


def callees(name, table):
    """The pred, fun and assert names one definition's code names, one level,
    in its own entity."""
    ent = table[name][0][1].rsplit("/", 1)[0]
    code = "\n".join(code_lines("\n".join(t for _, _, t in table[name])))
    return [w for w in dict.fromkeys(WORD.findall(code)) if w != name and w in table
            and any(k in ("pred", "fun", "assert") and p.rsplit("/", 1)[0] == ent
                    for k, p, _ in table[w])]


def row_of(name, table):
    """What the model reads of one command: its own definitions, the command
    line last, then each definition it names, one level."""
    own = sorted(table[name], key=lambda d: d[0] in ("check", "run"))
    named = callees(name, table)
    return "\n\n".join(t for _, _, t in own) + ("\n\n-- what it names:\n" + "\n\n".join(
        t for w in named for k, _, t in table[w] if k not in ("check", "run"))
        if named else "")


def premise_of(row):
    return next((k for k, rx in PREMISES if rx.search(row)), None)


def utc(stamp):
    return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True,
                          check=True, timeout=300).stdout


def machine_fact(until):
    """Every `bound:` label on a campaign issue filed by `until`."""
    issues = [i for i in json.loads(gh("issue", "list", "-R", BASE_REPO, "-l", "campaign",
                                       "-s", "all", "--limit", "1000", "--json",
                                       "number,createdAt,labels"))
              if until is None or utc(i["createdAt"]) <= until]
    bound = collections.Counter(l["name"].removeprefix("bound:") for i in issues
                                for l in i["labels"] if l["name"].startswith("bound:"))
    held = "; ".join(f"{m} on {n}" for m, n in bound.most_common()) or "none"
    return (f"`bound:` labels on the {len(issues)} campaign issues of {BASE_REPO}, "
            f"open and closed: {held}. {len(bound)} machine(s) in all.")


def handoff_fact(until):
    """The tracker's NOTEs, by `until`, whose first line reports a hand-off."""
    rows = gh("api", "--paginate", f"repos/{BASE_REPO}/issues/comments?per_page=100",
              "--jq", '.[] | [.created_at, (.issue_url | split("/") | last), '
              '(.body | split("\n") | first)] | @tsv').splitlines()
    hits = []
    for r in rows:
        at, number, first = (r.split("\t", 2) + ["", ""])[:3]
        if HANDOFF.match(first) and (until is None or utc(at) <= until):
            hits.append(f"- campaign-base#{number} {at[:10]}: {first[:160]}")
    return (f"NOTEs on {BASE_REPO}'s {len(rows)} issue comments whose first line "
            f"reports a hand-off: {len(hits)}" + ("\n" + "\n".join(hits) if hits
                                                   else ". None found."))


def narrowing_fact(files, text):
    """Each kind reference's `optional = ...` line: the profile a kind declares."""
    refs = sorted(f for f in files if re.search(r"/references/kind-[\w-]+\.md$", f))
    lines = [f"- {f.rsplit('/', 1)[1]}: " + (", ".join(PROFILE.findall(text[f])) or
                                             "no `optional = ...` line") for f in refs]
    return (f"The `optional = ...` line of each of the {len(refs)} kind references, "
            "the stages a change of that kind may skip:\n" + "\n".join(lines))


def reader_fact(names, tokens):
    """For each name, the files outside spec/ that name it."""
    out = []
    for n in names:
        found = sorted(g for g, c in tokens.items()
                       if not g.endswith(".als") and g != tie.SNAPSHOT and c[n])
        out.append(f"- {n}: " + (", ".join(found[:FACT_FILES]) + (
            f" and {len(found) - FACT_FILES} more" if len(found) > FACT_FILES else "")
            if found else "named by no file outside spec/"))
    return "Files outside spec/ naming the command and each definition it names:\n" \
        + "\n".join(out)


def ruling_asks(files, text, tokens, commands, declared, until=None):
    """[(group, name, path, state)]: every question the ruling mode asks, with
    the fact each premise needs fetched once. A calculation over the tree, but
    for the premise records, which are read from the tracker."""
    table = declarations(sorted(f for f in files if f.startswith("spec/")
                                and f.endswith(".als")), text)
    facts = {"handoff": lambda: handoff_fact(until),
             "machine": lambda: machine_fact(until),
             "narrowing": lambda: narrowing_fact(files, text)}
    fetched, asks = {}, []
    for m, k, n in commands:
        if n.startswith("Cov_") or n not in table:
            continue
        # The snapshot names a module relative to spec/; the key is its path
        # from the top, the one `fetch_commits` can read at `origin/main`.
        row, path = row_of(n, table), "spec/" + m
        kind = premise_of(row)
        if kind:
            if kind not in fetched:
                fetched[kind] = facts[kind]()
            asks.append(("dead-premise", n, path, {"row": row, "fact": fetched[kind]}))
        if n not in declared:
            asks.append(("dead-reader", n, path, {"row": row, "fact": reader_fact(
                [n] + callees(n, table), tokens)}))
    return asks


def ruling(files, text, tokens, commands, declared, root):
    """Judge every ask, one call each; at `shadow` the log is the output."""
    key = jev.commit_key(cwd=root)
    # The P of the option each entry's `bands.how` says the flag reads.
    jev.perform([jev.Ask(
        [{"group": group, "state": state, "read": f"{path} {name}",
          "key": dict(key, path=path, name=name) if key.get("repo") else None}
         for group, name, path, state in
         ruling_asks(files, text, tokens, commands, declared)],
        {"flag": jev.option_flag(FLAG)})], "spec-dead-count.py", cwd=root)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all", choices=("all", "ruling") + MODES)
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    # The tree's top, not ROOT itself: `git ls-files` below a subdirectory
    # lists paths relative to it, and nothing would start with `spec/`.
    os.chdir(subprocess.run(["git", "-C", args.root, "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True, check=True).stdout.strip())
    want = lambda m: args.mode in ("all", m)
    head = lambda m, n, what: print(f"{m}\t{n}\t{what}")
    row = lambda m, e, n, why: print(f"{m}\t{e}\t{n}\t{why}")

    files = [f for f in subprocess.run(["git", "ls-files"], capture_output=True,
                                       text=True, check=True).stdout.splitlines()
             if os.path.isfile(f)]
    text = {f: open(f, errors="replace").read() for f in files}
    tokens = {f: collections.Counter(WORD.findall(t)) for f, t in text.items()}
    tree = tie.Tree("the working tree", files, text, shape.in_scripts_dir)
    als = sorted(f for f in files if f.startswith("spec/") and f.endswith(".als"))
    commands = json.loads(text[tie.SNAPSHOT])["commands"] if tie.SNAPSHOT in text else []

    defs = []  # (entity, kind, name, mentions in .als, files outside spec/ naming it)
    for f in als:
        for line in code_lines(text[f]):
            m = D.match(line)
            if m:
                k, n = m.groups()
                inspec = sum(c[n] for g, c in tokens.items() if g.endswith(".als"))
                out = [g for g, c in tokens.items()
                       if not g.endswith(".als") and g != tie.SNAPSHOT and c[n]]
                defs.append((f.split("/")[-2], k, n, inspec, out))
    cmds = [(e, k, n) for e, k, n, _, _ in defs if k in ("check", "run")]
    suites = set(tree.suites)
    witnesses = {s: sorted(tree.declared(s)) for s in tree.suites}
    refines = {h: sorted(tree.refines(h)) for h in tree.htmls}
    declared = tree.declared_by_suites() | {n for v in refines.values() for n in v}
    if args.mode == "ruling":
        ruling(files, text, tokens, commands, declared, Path.cwd())
        return 0

    if want("defs"):
        head("defs", len(defs), "definitions in spec/**/*.als")
        row("defs", "-", "unnamed-outside-spec", str(sum(1 for r in defs if not r[4])))
        row("defs", "-", "facts (unnamed by construction, excluded)",
            str(sum(1 for r in defs if r[1] == "fact")))
        row("defs", "-", "named at most once in .als, not fact",
            str(sum(1 for r in defs if r[3] <= 1 and r[1] != "fact")))
        c = collections.Counter()
        for e, k, n in cmds:
            c[e] += 1
            c[cls(n)] += 1
            if MM.search(n):
                c["multi-machine"] += 1
        row("defs", "-", "commands by class (regex over .als)", json.dumps(dict(c), sort_keys=True))
        row("defs", "-", "snapshot commands", str(len(commands)))

    if want("unwitnessed"):
        dead = [(m, k, n) for m, k, n in commands if n not in declared]
        head("unwitnessed", len(dead), f"of {len(commands)} snapshot commands, against "
             f"{len(tree.suites)} suites and {len(tree.htmls)} html forms")
        named = {n: o for e, k, n, _, o in defs if k in ("check", "run")}
        for m, k, n in dead:
            cited = [g for g in named.get(n, []) if g not in suites]
            row("unwitnessed", m.split("/")[-2], n, f"{k} declared by no suite; class "
                f"{cls(n)}; named outside spec by: {','.join(cited) or 'nothing'}")

    if want("unpaired"):
        names = {(e, n) for e, k, n in cmds}
        bites = [(e, n) for e, k, n in cmds if n.endswith("_Bites")]
        checks = [(e, n) for e, k, n in cmds if k == "check"]
        orphans = [(e, n) for e, n in bites if (e, n.removesuffix("_Bites")) not in names]
        unproved = [(e, n) for e, n in checks if (e, n + "_Bites") not in names]
        head("unpaired", len(orphans) + len(unproved), f"{len(bites)} _Bites runs and {len(checks)} checks")
        for e, n in orphans:
            row("unpaired", e, n, "_Bites with no check of its stem")
        for e, n in unproved:
            row("unpaired", e, n, "check with no _Bites (no red-first proof)")

    if want("duplicate"):
        bodies = collections.defaultdict(list)
        for f in als:
            for m in re.finditer(r"^\s*(pred|assert)\s+(\w+)\s*(\[[^\]]*\])?\s*\{(.*?)^\}",
                                 text[f], re.S | re.M):
                body = re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/|--[^\n]*", "", m.group(4))).strip()
                if body:
                    bodies[body].append((f.split("/")[-2], m.group(2)))
        dups = [v for v in bodies.values() if len(v) > 1]
        covs = collections.defaultdict(set)
        for e, k, n, _, _ in defs:
            if n.startswith("Cov_"):
                covs[n].add(e)
        multi = {n: es for n, es in covs.items() if len(es) > 1}
        head("duplicate", len(dups) + len(multi),
             f"{sum(len(v) for v in bodies.values())} pred/assert bodies and {len(covs)} Cov_ names")
        for v in dups:
            row("duplicate", v[0][0], v[0][1], "same body as " + ", ".join(f"{e}/{n}" for e, n in v[1:]))
        for n, es in sorted(multi.items()):
            row("duplicate", ",".join(sorted(es)), n, "Cov_ declared in more than one module")

    if want("undefined"):
        bad = [(s, n) for s, v in witnesses.items() for n in v if n not in tree.scenarios]
        badh = [(h, n) for h, v in refines.items() for n in v if n not in tree.scenarios]
        tracked = set(files)
        paths = set()
        for f in files:
            if not re.search(r"\.(py|sh|yml|md|als|html)$", f) or "/fixtures/" in f or f in suites:
                continue
            for m in PATH.finditer(text[f]):
                p = m.group(1).rstrip(".")
                if p not in tracked and os.path.normpath(os.path.join(os.path.dirname(f), p)) not in tracked:
                    paths.add((f, p))
        head("undefined", len(bad) + len(badh) + len(paths),
             f"{sum(len(v) for v in witnesses.values())} witness names, "
             f"{sum(len(v) for v in refines.values())} refines names, "
             "path tokens in tracked non-test non-fixture files")
        for s, n in bad:
            row("undefined", s, n, "witness name not in snapshot (T6 reads it only in a touched suite)")
        for h, n in badh:
            row("undefined", h, n, "refines name not in snapshot")
        for f, p in sorted(paths):
            row("undefined", f, p, "path token names no tracked file")

    if want("untied"):
        # The tree's own list, and the running copy's where the tree holds no
        # readable one -- the guard's fallback, said on stderr as it says it.
        held, why = tie.own_list(tree)
        legacy = set(tie.LEGACY) if held is None else held
        if held is None:
            print(f"untied\t-\tLEGACY\tthe running copy's: {why}", file=sys.stderr)
        rows = []
        for k in sorted(tree.code):
            own = tree.suites_of(k)
            if not own:
                rows.append((k, "no suite carries its stem"))
            elif not tree.tied(k):
                rows.append((k, f"suite {','.join(own)} declares no listed scenario"))
        head("untied", len(rows), f"{len(tree.code)} code paths, {len(tree.suites)} suites, LEGACY {len(legacy)}")
        for k, why in rows:
            row("untied", k, "-", why + ("; on LEGACY" if k in legacy else "; NOT on LEGACY"))
        for k in sorted(legacy - {k for k, _ in rows}):
            row("untied", k, "-", "on LEGACY but tied or absent (T5 or a fixture)")

    if want("premise"):
        hits = collections.OrderedDict()
        for e, k, n, _, _ in defs:
            if MM.search(n) and k != "fact":
                hits.setdefault((e, n), []).append(k)
        head("premise", len(hits), f"{len(defs)} definitions, name pattern {MM.pattern}")
        for (e, n), ks in hits.items():
            row("premise", e, n, f"{'+'.join(ks)} named on a multi-machine or handoff "
                f"premise; declared by a suite: {n in declared}")

    if want("mismatch"):
        rows = []
        for s, v in witnesses.items():
            body = "\n".join(l for l in text[s].splitlines() if not tie.WITNESSES.match(l))
            for n in v:
                if n not in tree.scenarios or re.search(r"\b" + re.escape(n) + r"\b", body):
                    continue
                stem = n.removeprefix("Cov_") if n.startswith("Cov_") else n.split("_")[0]
                if re.search(r"(?<![A-Za-z])" + re.escape(stem) + r"(?![a-z])", body):
                    rows.append((s, n, f"name spelled nowhere else in the suite; its stem {stem} is"))
                else:
                    rows.append((s, n, f"neither the name nor its stem {stem} spelled anywhere else in the suite"))
        head("mismatch", len(rows), f"{sum(len(v) for v in witnesses.values())} declared "
             f"witness names across {len(witnesses)} suites")
        for s, n, why in rows:
            row("mismatch", s, n, why)
    return 0


if __name__ == "__main__":
    sys.exit(main())
