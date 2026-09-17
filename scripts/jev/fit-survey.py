#!/usr/bin/env python3
"""Fit rule-check#460 step 2's six survey sets into this tree's corpus format.

    scripts/jev/fit-survey.py <step2 dir> [--write]
    scripts/jev/fit-survey.py <step2 dir> --entry <reading>

ONE SCRIPT, BECAUSE THE SIX SETS DIFFER ONLY AT THE EDGES (rule-check#460 NOTE
5713910878). Every line of `<step2>/{A..F}/corpus.jsonl` carries the same
core -- `reading`, `case_id`, `source`, the `state` as sent, `wording`, `truth`
{`label`, `rule`, `joined_from`}, `prefilter`, three runs of `answers`, three
`flag`s, `model` and `made_up`. What differs is which numbers `source` holds
(an issue in A, B and D; a comment beside it in E and F; a pull request and two
comment ids in C), and the extra keys C and D carry. Nothing is dropped: the
extras land under ONE named field, `survey`, so a later reading of that set can
still find them.

WHAT THE FIT DECIDES, and each decision is visible in the output rather than
buried:

  the id        `<reading>-<case_id>`, so two sets cannot collide.
  the truth     `truth.label` as it stands -- a word for a one-condition
                reading, and an object keyed by condition for C's and D's
                multi-condition ones. A case is re-askable either way, and
                flattening an object into a word here would invent an answer.
  label.from    `flip-of:<id>` where the line carries `flip_of`;
                `hand:rule-check-worker-47` where it is `made_up` or carries no
                `joined_from`, which is the weakest label and is counted as
                such; `join:460-step2` where the survey joined it to a later
                GitHub fact. `label.rule` keeps `truth.rule`, so the basis of
                the label survives the import.
  role          `flip` where `flip_of` is set, else `case`. `made_up` STAYS a
                field either way: a made case that lost its mark would be read
                as evidence from the tree's own history.
  settled       the line's `prefilter`, the word CODE reached. E's 28 lines
                with `answers: null` are exactly the cases its prefilter
                cleared, so they import as cases the prefilter settled and the
                model never saw -- dropping them would flatter the reading by
                hiding the share code did.
  seen          one row per raw run: the model, the wording, the run's whole
                `answers` object and the `flag` computed from it. A reading's
                band is read from here and nothing is kept by hand.

THE COUNT IS ASSERTED, per set and in total: lines in must equal cases out, and
any line that does not fit is listed by its id and never silently skipped. The
run prints both numbers whether or not it writes.

ONLY THE CORPUS LANDS. Those readings' registry entries land later, one state
per pull request, so `--entry <reading>` PRINTS a converted entry for the author
of that pull request and writes nothing into `scripts/jev/readings.json`. The
six `registry.json` differ in their top level -- a list in A, C, D, E and F, a
dict with `readings` in B -- which `entries_of` folds into one.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
SETS = ("A", "B", "C", "D", "E", "F")
# The keys the core shape uses; anything else a set carries is an extra and
# lands under `survey` rather than being dropped.
CORE = {"reading", "case_id", "source", "state", "wording", "truth",
        "prefilter", "answers", "flag", "model", "made_up", "flip_of"}
WORKER = "hand:rule-check-worker-47"


def entries_of(data):
    """The registry entries of one set's `registry.json`, by name. A list in
    five of the six and a dict with `readings` in B, folded here so no caller
    has to know which set it is reading."""
    rows = data["readings"] if isinstance(data, dict) else data
    if isinstance(rows, dict):
        rows = list(rows.values())
    return {r["name"]: r for r in rows}


def label_from(row):
    """Where the truth came from, in the four words the corpus format uses."""
    if row.get("flip_of"):
        return f"flip-of:{row['reading']}-{row['flip_of']}"
    if row.get("made_up") or not row["truth"].get("joined_from"):
        return WORKER
    return "join:460-step2"


def fit(row, which, at):
    """One survey line as one case, or a raise naming what would not fit."""
    source = dict(row.get("source") or {})
    case = {
        "id": f"{row['reading']}-{row['case_id']}",
        "reading": row["reading"],
        "state": row["state"],
        "truth": row["truth"]["label"],
        "label": {"from": label_from(row), "at": at,
                  "evidence": row["truth"].get("joined_from"),
                  "rule": row["truth"].get("rule")},
        "source": {"kind": "survey",
                   # THE PROVENANCE NAMES THE SUB-ISSUE, not the git-ignored
                   # directory the lines were read from: the directory dies
                   # with the machine and the issue does not.
                   "ref": f"rule-check#460 step 2, set {which}",
                   "repo": source.pop("repo", None)},
        "role": "flip" if row.get("flip_of") else "case",
        "made_up": bool(row.get("made_up")),
        "settled": row.get("prefilter"),
        "seen": [],
    }
    # THE JOIN KEY AS FIELDS, REPOSITORY INCLUDED. A member repository's pull
    # request closes a sub-issue on this tracker and its number collides with
    # this tracker's own, so a number without its repository names nothing
    # (rule-check#460 NOTE 5713928884). `closed_by_repo` is kept where the
    # source carries it.
    for key in ("issue", "pull_request", "comment_id", "review_comment_id",
                "report_comment_id", "closed_by_repo", "url"):
        if key in source:
            case["source"][key] = source.pop(key)
    runs = row.get("answers")
    flags = row.get("flag") or []
    for i, answers in enumerate(runs or []):
        case["seen"].append({"model": row.get("model"),
                             "wording": row.get("wording"), "at": at,
                             "word": None, "raw": answers,
                             "flag": flags[i] if i < len(flags) else None})
    if runs is None:
        # The prefilter cleared it, so nothing was asked. Still a case.
        case["seen"] = []
    extra = {k: v for k, v in row.items() if k not in CORE}
    extra.update(source)
    if extra:
        case["survey"] = extra
    return case


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step2", help="rule-check#460's step2 directory")
    ap.add_argument("--write", action="store_true",
                    help="write scripts/jev/corpus/<reading>.jsonl")
    ap.add_argument("--entry", help="print one reading's converted entry")
    args = ap.parse_args(argv)
    root = Path(args.step2)
    at = datetime.date.today().isoformat()

    if args.entry:
        for which in SETS:
            path = root / which / "registry.json"
            if not path.exists():
                continue
            found = entries_of(json.loads(path.read_text(encoding="utf-8")))
            if args.entry in found:
                print(json.dumps({args.entry: found[args.entry]}, indent=1,
                                 ensure_ascii=False))
                print(f"\nfrom {path}. It is NOT written into "
                      f"{HERE / 'readings.json'}: a reading enters the registry "
                      f"with its own pull request, at `shadow`.", file=sys.stderr)
                return 0
        print(f"fit-survey: no reading `{args.entry}` in any of "
              f"{', '.join(SETS)}", file=sys.stderr)
        return 1

    cases, bad, total = {}, [], 0
    for which in SETS:
        path = root / which / "corpus.jsonl"
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                 if ln.strip()]
        out = 0
        for ln in lines:
            row = json.loads(ln)
            try:
                case = fit(row, which, at)
            except Exception as e:  # noqa: BLE001 -- a line listed, never dropped
                bad.append(f"{which} {row.get('case_id')}: "
                           f"{e.__class__.__name__}: {e}")
                continue
            cases.setdefault(case["reading"], []).append(case)
            out += 1
        total += len(lines)
        print(f"{which}  {len(lines)} line(s) in  {out} case(s) out"
              + ("  MISMATCH" if out != len(lines) else ""))
    made = sum(len(v) for v in cases.values())
    print(f"total  {total} line(s) in  {made} case(s) out over "
          f"{len(cases)} reading(s)")
    for line in bad:
        print(f"  did not fit: {line}")
    for name, rows in sorted(cases.items()):
        print(f"  {name:<28} {len(rows)}")
    if bad or made != total:
        print("fit-survey: refusing to write while a line does not fit",
              file=sys.stderr)
        return 1
    if args.write:
        CORPUS.mkdir(parents=True, exist_ok=True)
        for name, rows in sorted(cases.items()):
            path = CORPUS / f"{name}.jsonl"
            path.write_text("".join(
                json.dumps(c, sort_keys=True, ensure_ascii=False) + "\n"
                for c in rows), encoding="utf-8")
            print(f"wrote {path}  {len(rows)} case(s)  "
                  f"{path.stat().st_size // 1024} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
