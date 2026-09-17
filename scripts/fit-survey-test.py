#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove scripts/jev/fit-survey.py turns every survey line into exactly one case, and keeps its marks.

THE SCRIPT IS A ONE-WAY IMPORT of rule-check#460 step 2's six survey sets into
this tree's corpus format, and the whole of its promise is a COUNT: lines in
equals cases out, per set and in total, and a line that does not fit is listed
by its id and never silently skipped. That is what these cases assert, over a
made step2 directory of four lines -- one joined, one made by hand, one flip,
one the prefilter cleared -- rather than over the git-ignored survey, which
dies with the machine this ran on.

THE MARKS ARE THE OTHER HALF. `made_up` and `flip_of` say a case is not
evidence from this tree's own history, and a case that lost either of them
would be counted as one the tracker really produced. So each is asserted where
it lands: `made_up` as its own field, `flip_of` as the `role` and the
`label.from`, and the survey's extra keys under `survey`, which is how nothing
is dropped.

It lives under scripts/ and not beside the script it drives, because CI finds a
suite by the glob `scripts/*-test.*` and a glob never spans a slash.

Usage: scripts/fit-survey-test.py
"""
import contextlib
import importlib
import io
import json
import sys
import tempfile
import types
from pathlib import Path

harness = importlib.import_module("suite-harness-test")
check = harness.check

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "jev" / "fit-survey.py"
SOURCE = SCRIPT.read_text()
ROOT = Path(tempfile.mkdtemp(prefix="fit-survey-"))

# FOUR LINES, ONE OF EACH KIND THE FIT DECIDES DIFFERENTLY. Every field the
# script's `CORE` names is here, because a line missing one is a line that does
# not fit and would be listed rather than converted -- which is a different
# case, below.
LINES = [
    {"reading": "made-reading", "case_id": "c1",
     "source": {"repo": "kalaluthien/campaign-base", "issue": 455},
     "state": {"title": "Cache the feed"}, "wording": "w1",
     "truth": {"label": "yes", "rule": "the title opens with an order",
               "joined_from": "the issue closed with the title kept"},
     "prefilter": None, "answers": [{"c": {"type": "noul", "noul": 0.9}}],
     "flag": [0.1], "model": "jev-1.13.0", "made_up": False},
    {"reading": "made-reading", "case_id": "c2",
     "source": {"repo": "kalaluthien/campaign-base", "issue": 456},
     "state": {"title": "A title nobody wrote"}, "wording": "w1",
     "truth": {"label": "no", "rule": "made by hand", "joined_from": None},
     "prefilter": None, "answers": [{"c": {"type": "noul", "noul": 0.1}}],
     "flag": [0.9], "model": "jev-1.13.0", "made_up": True},
    {"reading": "made-reading", "case_id": "c1-neg",
     "source": {"repo": "kalaluthien/campaign-base", "issue": 455},
     "state": {"title": "The feed is cold"}, "wording": "w1",
     "truth": {"label": "no", "rule": "the verb was cut", "joined_from": None},
     "prefilter": None, "answers": [{"c": {"type": "noul", "noul": 0.2}}],
     "flag": [0.8], "model": "jev-1.13.0", "made_up": False,
     "flip_of": "c1", "stratum": "A"},
    {"reading": "made-reading", "case_id": "c3",
     "source": {"repo": "kalaluthien/campaign-base", "issue": 457},
     "state": {"title": ""}, "wording": "w1",
     "truth": {"label": "no", "rule": "code settles it", "joined_from": None},
     "prefilter": "cleared", "answers": None, "flag": None,
     "model": "jev-1.13.0", "made_up": False},
]
REGISTRY = [{"name": "made-reading", "moment": "a made moment",
             "questions": {"q": {"type": "noul"}}, "tier": "shadow"}]


def step2(name, lines=None, registry=None):
    """A made step2 directory. `A` carries the lines and the other five are
    empty: the fit walks all six by name and reads each one's `corpus.jsonl`,
    so a directory short of one raises rather than being skipped -- which is
    the right way round for a mistyped path, and is why the fixture writes
    them all."""
    root = ROOT / name
    for which in "ABCDEF":
        (root / which).mkdir(parents=True, exist_ok=True)
        rows = (LINES if lines is None else lines) if which == "A" else []
        (root / which / "corpus.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        (root / which / "registry.json").write_text(
            json.dumps((REGISTRY if registry is None else registry)
                       if which == "A" else []), encoding="utf-8")
    return root


def run(m, name, *args, lines=None, registry=None):
    """(exit status, everything printed, the cases written or None)."""
    root = step2(name, lines, registry)
    corpus = ROOT / f"corpus-{name}"
    corpus.mkdir(exist_ok=True)
    m.CORPUS = corpus
    # STDOUT AND STDERR BOTH, since the script prints its counts to one and
    # its refusals to the other, and a case reading only one would pass over
    # the sentence that says nothing was written.
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = m.main([str(root), *args])
    text = out.getvalue() + err.getvalue()
    cases = None
    path = corpus / "made-reading.jsonl"
    if path.exists():
        cases = [json.loads(ln) for ln in path.read_text().splitlines()
                 if ln.strip()]
    return code, text, cases


def counts_are_asserted(m):
    """The count IS the promise: four lines in, four cases out, both printed
    whether or not the run writes."""
    code, text, cases = run(m, "counts")
    return (code == 0 and "A  4 line(s) in  4 case(s) out" in text
            and "total  4 line(s) in  4 case(s) out" in text
            and "MISMATCH" not in text and cases is None), (code, text)


def a_line_that_does_not_fit_is_listed(m):
    """Never silently skipped, and the run refuses to write while one does not
    fit: a corpus short of the survey it came from is one nobody can count."""
    bad = dict(LINES[0]); bad.pop("truth")
    code, text, _cases = run(m, "bad", "--write", lines=[LINES[0], bad])
    return (code == 1 and "did not fit: A c1: KeyError" in text
            and "2 line(s) in  1 case(s) out  MISMATCH" in text
            and "refusing to write" in text), (code, text)


def write_keeps_every_mark(m):
    """`made_up` and `flip_of` say a case is not evidence from this tree's own
    history. A case that lost either would be counted as one the tracker really
    produced."""
    _code, _text, cases = run(m, "marks", "--write")
    by = {c["id"]: c for c in cases or []}
    made = by.get("made-reading-c2") or {}
    flip = by.get("made-reading-c1-neg") or {}
    joined = by.get("made-reading-c1") or {}
    return (len(cases or []) == 4
            and made.get("made_up") is True
            and made.get("label", {}).get("from") == m.WORKER
            and flip.get("role") == "flip"
            and flip.get("label", {}).get("from") == "flip-of:made-reading-c1"
            and joined.get("role") == "case"
            and joined.get("made_up") is False
            and joined.get("label", {}).get("from") == "join:460-step2"), by


def the_prefilters_word_travels(m):
    """A case the prefilter cleared is still a case, and `settled` says so:
    dropping it would flatter the reading by hiding the share code did."""
    _code, _text, cases = run(m, "settled", "--write")
    by = {c["id"]: c for c in cases or []}
    cleared = by.get("made-reading-c3") or {}
    asked = by.get("made-reading-c1") or {}
    return (cleared.get("settled") == "cleared" and cleared.get("seen") == []
            and asked.get("settled") is None
            and len(asked.get("seen") or []) == 1), (cleared, asked)


def a_run_per_raw_run_is_kept(m):
    """One `seen` row per raw run, carrying the model, the wording, the whole
    answers object and the flag computed from it. A band is read from here."""
    _code, _text, cases = run(m, "seen", "--write")
    by = {c["id"]: c for c in cases or []}
    seen = (by.get("made-reading-c1") or {}).get("seen") or [{}]
    return (seen[0].get("model") == "jev-1.13.0"
            and seen[0].get("wording") == "w1"
            and seen[0].get("raw") == {"c": {"type": "noul", "noul": 0.9}}
            and seen[0].get("flag") == 0.1), seen


def nothing_the_survey_carried_is_dropped(m):
    """The extras land under ONE named field, so a later reading of that set
    can still find them: the flip line's `stratum` is one."""
    _code, _text, cases = run(m, "extras", "--write")
    by = {c["id"]: c for c in cases or []}
    flip = by.get("made-reading-c1-neg") or {}
    return flip.get("survey", {}).get("stratum") == "A", flip.get("survey")


def the_entry_is_printed_and_never_written(m):
    """`--entry` prints one reading's converted entry for the author of the
    pull request that lands it. A reading enters the registry with its own pull
    request, at `shadow`, so this writes nothing into readings.json."""
    was = SCRIPT.parent / "readings.json"
    before = was.read_text() if was.exists() else None
    code, text, _cases = run(m, "entry", "--entry", "made-reading")
    after = was.read_text() if was.exists() else None
    return (code == 0 and '"made-reading"' in text
            and '"a made moment"' in text and after == before), (code, text)


def an_unknown_entry_is_refused(m):
    """A reading no set carries is a name the author got wrong, and saying so
    beats printing nothing."""
    code, text, _cases = run(m, "noentry", "--entry", "no-such-reading")
    return code == 1 and "no reading `no-such-reading`" in text, (code, text)


def b_s_registry_shape_folds_into_the_others(m):
    """Five sets hold a list and B a dict with `readings`. A caller that had to
    know which set it was reading would be the copy that drifts."""
    try:
        as_list = m.entries_of(REGISTRY)
        as_dict = m.entries_of({"readings": REGISTRY})
        as_map = m.entries_of({"readings": {"made-reading": REGISTRY[0]}})
    except Exception as e:  # noqa: BLE001 -- a shape it could not fold, named
        return False, f"{e.__class__.__name__}: {e}"
    return (as_list == as_dict == as_map
            and sorted(as_list) == ["made-reading"]), sorted(as_list)


CASES = {
    "lines in equals cases out, per set and in total": counts_are_asserted,
    "a line that does not fit is listed and nothing is written":
        a_line_that_does_not_fit_is_listed,
    "a made case and a flip keep their marks through the fit":
        write_keeps_every_mark,
    "a case the prefilter cleared is still a case, and says so":
        the_prefilters_word_travels,
    "one seen row per raw run, with its flag": a_run_per_raw_run_is_kept,
    "nothing the survey carried is dropped": nothing_the_survey_carried_is_dropped,
    "--entry prints an entry and writes no registry":
        the_entry_is_printed_and_never_written,
    "--entry on a reading no set carries is refused": an_unknown_entry_is_refused,
    "the six registry shapes fold into one": b_s_registry_shape_folds_into_the_others,
}

MUTATIONS = [
    ("the count never asserted", 'if bad or made != total:', "if False:",
     "a line that does not fit is listed and nothing is written"),
    ("a line that does not fit dropped in silence",
     'bad.append(f"{which} {row.get(\'case_id\')}: "\n'
     '                           f"{e.__class__.__name__}: {e}")\n'
     "                continue",
     "                continue",
     "a line that does not fit is listed and nothing is written"),
    ("the made mark dropped", '"made_up": bool(row.get("made_up")),',
     '"made_up": False,', "a made case and a flip keep their marks through the fit"),
    ("a flip imported as an ordinary case",
     '"role": "flip" if row.get("flip_of") else "case",', '"role": "case",',
     "a made case and a flip keep their marks through the fit"),
    ("the prefilter's word dropped", '"settled": row.get("prefilter"),',
     '"settled": None,',
     "a case the prefilter cleared is still a case, and says so"),
    ("the flag left out of the seen row",
     '"flag": flags[i] if i < len(flags) else None})',
     '"flag": None})', "one seen row per raw run, with its flag"),
    ("the survey's extras dropped",
     '    extra = {k: v for k, v in row.items() if k not in CORE}',
     "    extra = {}", "nothing the survey carried is dropped"),
    ("--entry written into the registry rather than printed",
     '        print(f"fit-survey: no reading `{args.entry}` in any of "',
     '        print(f"fit-survey: found `{args.entry}` in none of "',
     "--entry on a reading no set carries is refused"),
    ("B's registry shape read as a list",
     '    rows = data["readings"] if isinstance(data, dict) else data',
     "    rows = data", "the six registry shapes fold into one"),
]


def load(source):
    m = types.ModuleType("fitsurvey")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return m


def main():
    harness.mutate(SOURCE, load, CASES, MUTATIONS)
    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
