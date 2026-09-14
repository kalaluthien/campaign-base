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

Usage: scripts/spec-dead-count.py [--mode <mode>|all] [ROOT]
"""
import argparse
import collections
import importlib.machinery
import importlib.util
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
PATH = re.compile(r"(?<![\w/])((?:spec|scripts|\.claude|\.github)/[\w./-]+"
                  r"\.(?:als|py|sh|md|jsonl|json|yml|html))(?!\w)")


def sibling(name):
    """A script beside this one as a module, by path: these are scripts and
    not a package."""
    src = Path(__file__).resolve().parent / name
    key = name.replace("-", "_").removesuffix(".py")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(src)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tie = sibling("check-sdlc-tie.py")
shape = sibling("check-tree-shape.py")


def code_lines(text):
    """The .als text with its comments blanked, line structure kept."""
    text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    return re.sub(r"(--|//)[^\n]*", "", text).split("\n")


def cls(name):
    return "cov" if name.startswith("Cov_") else "control" if NEG.search(name) else "scenario"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all", choices=("all",) + MODES)
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
        held, why = tie.own_list(tree)   # the tree's own list, as the guard reads it
        legacy = held or set()
        if held is None:
            print(f"untied\t-\tLEGACY\tnot read: {why}", file=sys.stderr)
        rows = []
        for k in sorted(tree.code):
            suites = tree.suites_of(k)
            if not suites:
                rows.append((k, "no suite carries its stem"))
            elif not tree.tied(k):
                rows.append((k, f"suite {','.join(suites)} declares no listed scenario"))
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
