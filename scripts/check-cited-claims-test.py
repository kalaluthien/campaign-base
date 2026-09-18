#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-cited-claims.py asks what a commit touched, from either source, cuts the state each entry names, and never refuses.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers every
question it is sent with one P(contradicts), and the reader runs in a fixture
repository holding its own copies of the scripts it loads and of
scripts/jev/readings.json. Each case is then broken by a mutation of the
reader's text and must go red by its own assertion.

`--live` asks every line of scripts/jev/corpus/<reading>.jsonl, for each reading
the reader owns, against the real endpoint, reads each case's highest
P(contradicts) against its entry's thresholds, counts the cases off their `truth`, and fails a case whose
word differs from the last one `seen` under the same question wording, so a
known miss stays counted and a change is red; `--record` appends the reading
to each line's `seen`.

Usage: scripts/check-cited-claims-test.py [--live [--record]]
"""
import datetime
import hashlib
import http.server
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import types
from pathlib import Path

harness = importlib.import_module("suite-harness-test")
check = harness.check

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-cited-claims.py"
SOURCE = SCRIPT.read_text()
REGISTRY = HERE / "jev" / "readings.json"
CORPUS = HERE / "jev" / "corpus"
ENTRIES = json.loads(REGISTRY.read_text())
ENTRY = ENTRIES["docstring-claims"]
MODEL = "jev-1.13.0"
ROOT = Path(tempfile.mkdtemp(prefix="cited-claims-"))

NEXT = {"p": 0.9}
SEEN = []
# The log rows the last run wrote, so a case can read what the row carried.
LAST = {"rows": []}


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        p = NEXT["p"]
        answers = {q: {"type": "choice", "choice": "supports", "confidence": 0.5,
                       "probabilities": {"contradicts": p, "supports": 1 - p,
                                         "says_nothing": 0.0}}
                   for q in body["questions"]}
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

SPEC = """module fixture
sig Agent {
  /* Set when the agent IS a session working its own claim. */
  peer: lone Agent
}
/* Every claim is held by its own agent. */
pred holds[a: Agent] { some a.peer and helper[a] }
pred helper[a: Agent] { a in Agent }
pred twice { no Agent }
pred other { some Agent }
"""
SPEC_TWICE = "module more\npred twice { some Agent }\n"
CITING = '''#!/usr/bin/env python3
"""A fixture script.

The model is `holds`: an agent holds its own claim; nothing else holds it.

An unrelated paragraph about `other`.
"""
'''
UNRELATED = "#!/usr/bin/env python3\n\"\"\"Cites `holds` too.\"\"\"\n"
REFERENCE = """# A reference

The model is `holds`: an agent holds its own claim.

- A list item naming `other` with nothing to anchor it.

| stage | in `spec/fixture` |
| --- | --- |
| one | `holds` |

| other table | x |
| --- | --- |
| two | y |
- first item
- second item

```sh
`holds` in a fence
```
"""


def module(source):
    m = types.ModuleType("docstringclaims")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return m


def load(source):
    return types.SimpleNamespace(source=source, m=module(source))


def repo(t, edits, p=0.9, url=None, registry=True, tier="advise", drop=()):
    """The reader, as `t.source`, run in a fresh repository whose first commit
    holds the fixture tree and whose index holds `edits` on top of it."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    files = {"spec/fixture/system.als": SPEC, "spec/more/system.als": SPEC_TWICE,
             "scripts/cites.py": CITING, "scripts/also.py": UNRELATED,
             "README.md": "fixture\n",
             ".claude/skills/x/references/ref.md": REFERENCE,
             ".claude/skills/x/SKILL.md": REFERENCE,
             "scripts/check-cited-claims.py": t.source,
             "scripts/campaign-jev.py": (HERE / "campaign-jev.py").read_text(),
             "scripts/check-tree-shape.py": (HERE / "check-tree-shape.py").read_text()}
    if registry:
        entries = json.loads(REGISTRY.read_text())
        for name in entries:
            entries[name]["tier"] = tier
        for name in drop:
            del entries[name]
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
    NEXT["p"] = p
    SEEN.clear()
    env = dict(os.environ, CAMPAIGN_JEV_URL=url or URL, TYPESAFE_API_KEY="stub",
               CAMPAIGN_JEV_LOG=str(d / "jev.log"))
    r = subprocess.run([sys.executable, "scripts/check-cited-claims.py",
                        "--staged"], cwd=d, capture_output=True, text=True, env=env)
    LAST["rows"] = [json.loads(line)
                    for line in (d / "jev.log").read_text().splitlines()
                    if line] if (d / "jev.log").exists() else []
    return r, r.stdout + r.stderr


def asked_names(source=".py"):
    """The names asked of paragraphs from docstrings (`.py`) or references
    (`.md`), told apart by the fixture text the paragraph came from."""
    return sorted(b["state"]["pred"]["name"] for b in SEEN
                  if (b["state"]["paragraph"].split("\n")[0] in REFERENCE)
                  == (source == ".md"))


def cut_claims(t):
    got = t.m.claims("The model is `holds`: an agent holds its own claim; "
                     "nothing else holds it. `other` is\nelsewhere.",
                     "holds", ENTRY["state"]["claims"])
    return got == ["The model is `holds`",
                   "`holds`: an agent holds its own claim"], got


def state_fields(t):
    decls, fields = t.m.declarations({"spec/fixture/system.als": SPEC})
    text = t.m.pred_text("holds", ENTRY["state"]["pred"]["text"], decls, fields,
                         {"spec/fixture/system.als": SPEC})
    return ("Every claim is held" in text and "pred helper" in text
            and "Set when the agent IS" in text and "peer: lone Agent" in text), text


def pred_touched(t):
    r, out = repo(t, {"spec/fixture/system.als":
                      SPEC.replace("some a.peer and", "some a.peer or")})
    return (r.returncode == 0 and asked_names() == ["holds", "holds"]
            and asked_names(".md") == ["holds", "holds"] and len(SEEN) == 4), (
        [b["state"]["paragraph"] for b in SEEN], out)


def paragraph_touched(t):
    r, out = repo(t, {"scripts/cites.py": CITING.replace("nothing else", "no other")})
    return (r.returncode == 0 and asked_names() == ["holds"] and len(SEEN) == 1
            and "pred holds" in SEEN[0]["state"]["pred"]["text"]), (asked_names(), out)


def nothing_touched(t):
    r, out = repo(t, {"README.md": "changed\n"})
    return r.returncode == 0 and not SEEN and "nothing asked" in out, out


def contradicted_printed(t):
    r, out = repo(t, {"scripts/cites.py": CITING.replace("nothing else", "no other")},
                  p=0.83)
    return r.returncode == 0 and "contradicts 0.83" in out, out


def clear_not_printed(t):
    r, out = repo(t, {"scripts/cites.py": CITING.replace("nothing else", "no other")},
                  p=0.05)
    return (r.returncode == 0 and "contradicts 0" not in out
            and "2 clear" in out), out


def gap_counted(t):
    r, out = repo(t, {"scripts/cites.py": CITING.replace("nothing else", "no other")},
                  p=0.35)
    return (r.returncode == 0 and "2 in the gap" in out
            and "0 claim(s) read as contradicted, 0 clear" in out), out


def row_carries_its_join_key(t):
    """WHAT THE MOVE FROM `ask` TO `judge` BOUGHT. The row names the reading
    and its wording, and carries the key as FIELDS -- the repository, the sha
    this commit sits on, the file and the pred -- so a later commit that
    rewrote that docstring can be joined to the answer. Under `ask` the row
    carried none of them and every one of them parked in the log for good."""
    repo(t, {"scripts/cites.py": CITING.replace("nothing else", "no other")})
    judged = [row for row in LAST["rows"] if row.get("reading")]
    one = judged[0] if judged else {}
    return (bool(judged) and one.get("repo") == "o/r"
            and one.get("path") == "scripts/cites.py"
            and one.get("name")
            and len(one.get("commit") or "") == 40
            and len(one.get("wording") or "") == 12), (len(judged), one)


def entry_reaches_model(t):
    repo(t, {"scripts/cites.py": CITING.replace("nothing else", "no other")})
    q = (SEEN[0]["questions"] if SEEN else {}).get("docstring-claims#c0", {})
    return (q.get("criteria") == ENTRY["question"]["criteria"]
            and q.get("instructions", {}).get("question")
            == ENTRY["question"]["instructions"]
            and "yes_over" not in q), q


def unknown_on_failure(t):
    r, out = repo(t, {"scripts/cites.py": CITING.replace("nothing else", "no other")},
                  url="http://127.0.0.1:9/v1/systemone")
    return r.returncode == 0 and "unknown" in out and "did not answer" in out, out


def declared_twice_skipped(t):
    r, out = repo(t, {"scripts/cites.py": CITING.replace("`other`", "`twice`")
                      .replace("nothing else", "no other")})
    return (r.returncode == 0 and "skipped as declared twice: twice" in out
            and "twice" not in asked_names()), (asked_names(), out)


def shadow_prints_counts(t):
    r, out = repo(t, {"scripts/cites.py": CITING.replace("nothing else", "no other")},
                  p=0.83, tier="shadow")
    return (r.returncode == 0 and len(SEEN) == 1 and "contradicts 0.83" not in out
            and "2 claim(s) read as contradicted" in out), out


def glob_in_comment(t):
    text = "module g\n/* First line.\n   covers scripts/*-test.* too. */\npred g { no none }\n"
    decls, _ = t.m.declarations({"g.als": text})
    first = decls["g"][0][1]
    return first == 1, first


def deletion_hunk(t):
    got = t.m.staged_hunks("+++ spec/a.als\n@@ -4 +3,0 @@\n")
    return got == {"spec/a.als": [(3, 4)]}, got


def reference_units(t):
    got = [u for _, _, u in t.m.units(REFERENCE)]
    return got == ["The model is `holds`: an agent holds its own claim.",
                   "- A list item naming `other` with nothing to anchor it.",
                   "| stage | in `spec/fixture` |\n| one | `holds` |",
                   "| other table | x |\n| two | y |",
                   "- first item", "- second item"], got


def plain_name_anchored(t):
    decls = {"holds": [1], "other": [1], "someRule": [1]}
    pre = ENTRIES["reference-claims"]["prefilter"]
    got = [t.m.cited("The model is `holds`. `other` is elsewhere.", decls, pre),
           t.m.cited("`other` sits beside `someRule`.", decls, pre),
           t.m.cited("Run `/model`, then `holds`.", decls, pre),
           t.m.cited("`other` is elsewhere.", decls, {})]
    return got == [["holds"], ["other", "someRule"], [], ["other"]], got


def reference_touched(t):
    r, out = repo(t, {".claude/skills/x/references/ref.md":
                      REFERENCE.replace("its own claim", "its claim")})
    asked = [b["state"]["paragraph"] for b in SEEN]
    return (r.returncode == 0
            and asked == ["The model is `holds`: an agent holds its claim."]
            and "reference-claims`: 1 staged" in out), (asked, out)


def reference_without_entry_not_read(t):
    r, out = repo(t, {".claude/skills/x/references/ref.md":
                      REFERENCE.replace("its own claim", "its claim")},
                  drop=("reference-claims",))
    return (r.returncode == 0 and not SEEN
            and "none a spec/ module or a source; nothing asked" in out), out


def skill_body_not_a_source(t):
    r, out = repo(t, {".claude/skills/x/SKILL.md": REFERENCE.replace("its own", "its")})
    return r.returncode == 0 and not SEEN and "nothing asked" in out, out


def entry_missing_other_asked(t):
    r, out = repo(t, {"spec/fixture/system.als":
                      SPEC.replace("some a.peer and", "some a.peer or")},
                  drop=("reference-claims",))
    return (r.returncode == 0 and "no entry `reference-claims`" in out
            and asked_names() == ["holds", "holds"] and not asked_names(".md")), out


def failure_exits_zero(t):
    r, out = repo(t, {"spec/fixture/system.als": SPEC + "\n"}, registry=False)
    return r.returncode == 0 and "could not read the commit" in out, (r.returncode, out)


CASES = {
    "claims: a sentence's clauses holding the name, a definition keeping it": cut_claims,
    "pred.text: the pred, its comment, its callee and the field's comment": state_fields,
    "a staged pred edit asks every paragraph citing it": pred_touched,
    "a staged paragraph edit asks that paragraph": paragraph_touched,
    "a commit touching neither asks nothing and says so": nothing_touched,
    "a contradicted claim is printed with its value, exit 0": contradicted_printed,
    "a clear claim is counted, not printed": clear_not_printed,
    "a claim between the two edges is counted in the gap": gap_counted,
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "the row carries the reading, the wording and the join key": row_carries_its_join_key,
    "a failed call prints unknown and exits 0": unknown_on_failure,
    "a name declared twice is skipped and named": declared_twice_skipped,
    "a reader that could not read exits 0 and says so": failure_exits_zero,
    "at tier shadow the counts are printed and no claim": shadow_prints_counts,
    "a comment holding a glob keeps its first line": glob_in_comment,
    "a deletion-only hunk touches the lines on both sides": deletion_hunk,
    "reference units: a paragraph, an item, a row under its header, no fence": reference_units,
    "a plain name counts only where the entry's prefilter anchors it": plain_name_anchored,
    "a staged reference paragraph edit asks that paragraph alone": reference_touched,
    "a skill body outside references/ is no source": skill_body_not_a_source,
    "a reference edit with no reference entry reads nothing": reference_without_entry_not_read,
    "a reading missing from the registry is named, the other still asked": entry_missing_other_asked,
}

MUTATIONS = [
    ("a definition split loses the name", 'out.append(f"{tick}: {piece}")', "pass",
     "claims: a sentence's clauses holding the name, a definition keeping it"),
    ("the fields left out of pred.text", 'if "fields" in parts and read:', "if False:",
     "pred.text: the pred, its comment, its callee and the field's comment"),
    ("a touched pred's citations not asked",
     "if not (mine or name in touched):",
     "if not mine:",
     "a staged pred edit asks every paragraph citing it"),
    ('the claims never handed to the call',
     '"claim": {f"c{i}": c for i, c in enumerate(got)}},',
     '"claim": {}},',
     'a contradicted claim is printed with its value, exit 0'),
    ("the failure boundary removed",
     "except Exception as e:  # noqa: BLE001 -- a reading never refuses a commit",
     "except ZeroDivisionError as e:", "a reader that could not read exits 0 and says so"),
    ("a touched paragraph not read as touched",
     "mine = overlaps(hunks.get(path, []), first, last)", "mine = False",
     "a staged paragraph edit asks that paragraph"),
    ("a commit touching neither read in full", "if not relevant:", "if False:",
     "a commit touching neither asks nothing and says so"),
    ("a clear claim printed", 'if a.word == "yes":', 'if a.word != "unknown":',
     "a clear claim is counted, not printed"),
    ("the gap left out of the counts",
     """{counts['uncertain']} in the gap, {counts['unknown']} """, '{counts["unknown"]} ',
     "a claim between the two edges is counted in the gap"),
    ('the row keyed by the file alone',
     '"read": label, "key": dict(key, path=path, name=name)}',
     '"read": label, "key": {"path": path}}',
     'the row carries the reading, the wording and the join key'),
    ('the pred never named on the row',
     '"read": label, "key": dict(key, path=path, name=name)}',
     '"read": label, "key": dict(key, path=path)}',
     'the row carries the reading, the wording and the join key'),
    ("an unknown claim not printed", 'elif a.word == "unknown":', "elif False:",
     "a failed call prints unknown and exits 0"),
    ("the tier not read", 'shown = entry["tier"] != "shadow"', "shown = True",
     "at tier shadow the counts are printed and no claim"),
    ("a comment's opener found mid-line",
     'while j > 0 and not lines[j - 1].lstrip().startswith("/*"):',
     'while j > 0 and "/*" not in lines[j - 1]:',
     "a comment holding a glob keeps its first line"),
    ("a deletion touching one side", "last = first + count - 1 if count else first + 1",
     "last = first + max(count, 1) - 1", "a deletion-only hunk touches the lines on both sides"),
    ("a name declared twice asked anyway", "if len(decls[name]) > 1:", "if False:",
     "a name declared twice is skipped and named"),
    ("a table row without its header", 'body = f"{header}\\n{body}"', "pass",
     "reference units: a paragraph, an item, a row under its header, no fence"),
    ("a list item run into the one above", 'elif re.match(r"([-*]|\\d+\\.)\\s", s):',
     "elif False:",
     "reference units: a paragraph, an item, a row under its header, no fence"),
    ("a header kept past its table", "            header = None\n", "            pass\n",
     "reference units: a paragraph, an item, a row under its header, no fence"),
    ("a source read for a reading the registry lacks",
     "sources[r](p) for r in READINGS if r in registry)",
     "sources[r](p) for r in READINGS)",
     "a reference edit with no reference entry reads nothing"),
    ("a fence read as prose", "fence = not fence", "fence = False",
     "reference units: a paragraph, an item, a row under its header, no fence"),
    ("the prefilter's anchor ignored",
     "return [n for n in names if not re.fullmatch(plain, n) or anchored(n)]",
     "return names",
     "a plain name counts only where the entry's prefilter anchors it"),
    ("a reference paragraph's citations not read",
     "units if REFERENCE.fullmatch(p) else None", "None",
     "a staged reference paragraph edit asks that paragraph alone"),
    ("any markdown under a skill read as a reference",
     "units if REFERENCE.fullmatch(p) else None",
     "units if p.endswith('.md') else None",
     "a skill body outside references/ is no source"),
    ("a missing entry fails the whole run", "if reading not in registry:", "if False:",
     "a reading missing from the registry is named, the other still asked"),
]


def live(record):
    """Every corpus case against the real endpoint, once. A case is red when
    its word differs from the last one recorded under the same wording: a
    known miss stays a counted line, and a change is what fails."""
    m = module(SOURCE)
    jev = m.jev_module()
    for reading in m.READINGS:
        live_one(m, jev, reading, ENTRIES[reading], CORPUS / f"{reading}.jsonl",
                 record)


def live_one(m, jev, name, entry, corpus, record):
    rows = [json.loads(line) for line in corpus.read_text().splitlines() if line]
    t = entry["thresholds"]
    targets = [(r["id"], r["state"]["paragraph"], r["state"]["pred"]["name"],
                r["state"]["pred"]["text"]) for r in rows]
    results = m.ask_all(entry, targets, jev)
    today = datetime.date.today().isoformat()
    wording = hashlib.sha256(json.dumps(entry["question"], sort_keys=True)
                             .encode()).hexdigest()[:12]
    misses = 0
    for row, (label, found, reading) in zip(rows, results):
        ps = [((a.raw or {}).get("probabilities") or {}).get(t["option"])
              for a in reading.answers.values()]
        raw = max(ps) if ps and None not in ps else None
        word = ("unknown" if raw is None else "yes" if raw >= t["yes_over"]
                else "no" if raw <= t["no_under"] else "unknown")
        print(f"{row['id']}  {row['role']:<8} truth {row['truth']:<3} "
              f"{'-' if raw is None else f'{raw:.2f}'} {word}  {row['source']['ref']}")
        misses += word != row["truth"]
        before = [x for x in row["seen"] if x.get("wording") == wording]
        if before:
            check(f"live {row['id']} reads {before[-1]['word']} as last recorded",
                  word == before[-1]["word"], f"{word} at {raw}, {row['source']['ref']}")
        row["seen"].append({"model": reading.model, "wording": wording,
                            "raw": raw if raw is None else round(raw, 2), "word": word, "at": today})
    print(f"{name}: {misses} of {len(rows)} case(s) off their truth")
    check(f"live {name}: every case asked", len(results) == len(rows), len(results))
    if record:
        corpus.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                  for r in rows))
        print(f"recorded into {corpus}")


def main(argv):
    try:
        if "--live" in argv:
            live("--record" in argv)
            return harness.report()
        harness.mutate(SOURCE, load, CASES, MUTATIONS)
        return harness.report()
    finally:
        shutil.rmtree(ROOT, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
