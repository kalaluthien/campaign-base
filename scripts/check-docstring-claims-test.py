#!/usr/bin/env python3
# witnesses: JV1_ARepliedConfidentFittingJudgmentAdvises, JV1b_AFailedLowOrNoMatchAnswerNeverAdvises
"""Prove check-docstring-claims.py asks what a commit touched, cuts the state the entry names, and never refuses.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers every
question it is sent with one P(contradicts), and the reader runs in a fixture
repository holding its own copies of the scripts it loads and of
scripts/jev/readings.json. Each case is then broken by a mutation of the
reader's text and must go red by its own assertion.

`--live` asks every line of scripts/jev/corpus/docstring-claims.jsonl against
the real endpoint, reads each case's highest P(contradicts) against the
entry's thresholds, counts the cases off their `truth`, and fails a case whose
word differs from the last one `seen` under the same question wording, so a
known miss stays counted and a change is red; `--record` appends the reading
to each line's `seen`.

Usage: scripts/check-docstring-claims-test.py [--live [--record]]
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
SCRIPT = HERE / "check-docstring-claims.py"
SOURCE = SCRIPT.read_text()
REGISTRY = HERE / "jev" / "readings.json"
CORPUS = HERE / "jev" / "corpus" / "docstring-claims.jsonl"
ENTRY = json.loads(REGISTRY.read_text())["docstring-claims"]
MODEL = "jev-1.13.0"
ROOT = Path(tempfile.mkdtemp(prefix="docstring-claims-"))

NEXT = {"p": 0.9}
SEEN = []


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


def module(source):
    m = types.ModuleType("docstringclaims")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return m


def load(source):
    return types.SimpleNamespace(source=source, m=module(source))


def repo(t, edits, p=0.9, url=None, registry=True, tier="advise"):
    """The reader, as `t.source`, run in a fresh repository whose first commit
    holds the fixture tree and whose index holds `edits` on top of it."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    files = {"spec/fixture/system.als": SPEC, "spec/more/system.als": SPEC_TWICE,
             "scripts/cites.py": CITING, "scripts/also.py": UNRELATED,
             "README.md": "fixture\n",
             "scripts/check-docstring-claims.py": t.source,
             "scripts/campaign-jev.py": (HERE / "campaign-jev.py").read_text(),
             "scripts/check-tree-shape.py": (HERE / "check-tree-shape.py").read_text()}
    if registry:
        entries = json.loads(REGISTRY.read_text())
        entries["docstring-claims"]["tier"] = tier
        files["scripts/jev/readings.json"] = json.dumps(entries)
    harness.write_tree(d, files)
    harness.git(d, "init", "-q", check=True)
    harness.git(d, "add", "-A", check=True)
    harness.git(d, "commit", "-qm", "fixture", "--no-verify", check=True)
    harness.write_tree(d, edits)
    harness.git(d, "add", "-A", check=True)
    NEXT["p"] = p
    SEEN.clear()
    env = dict(os.environ, CAMPAIGN_JEV_URL=url or URL, TYPESAFE_API_KEY="stub",
               CAMPAIGN_JEV_LOG=str(d / "jev.log"))
    r = subprocess.run([sys.executable, "scripts/check-docstring-claims.py",
                        "--staged"], cwd=d, capture_output=True, text=True, env=env)
    return r, r.stdout + r.stderr


def asked_names():
    return sorted(b["state"]["pred"]["name"] for b in SEEN)


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
            and len(SEEN) == 2), (asked_names(), out)


def paragraph_touched(t):
    r, out = repo(t, {"scripts/cites.py": CITING.replace("nothing else", "no other")})
    return (r.returncode == 0 and asked_names() == ["holds"]
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


def entry_reaches_model(t):
    repo(t, {"scripts/cites.py": CITING.replace("nothing else", "no other")})
    q = SEEN[0]["questions"]["c0"] if SEEN else {}
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
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "a failed call prints unknown and exits 0": unknown_on_failure,
    "a name declared twice is skipped and named": declared_twice_skipped,
    "a reader that could not read exits 0 and says so": failure_exits_zero,
    "at tier shadow the counts are printed and no claim": shadow_prints_counts,
    "a comment holding a glob keeps its first line": glob_in_comment,
    "a deletion-only hunk touches the lines on both sides": deletion_hunk,
}

MUTATIONS = [
    ("a definition split loses the name", 'out.append(f"{tick}: {piece}")', "pass",
     "claims: a sentence's clauses holding the name, a definition keeping it"),
    ("the fields left out of pred.text", 'if "fields" in parts and read:', "if False:",
     "pred.text: the pred, its comment, its callee and the field's comment"),
    ("a touched pred's citations not asked",
     "if name not in decls or not (mine or name in touched):",
     "if name not in decls or not mine:",
     "a staged pred edit asks every paragraph citing it"),
    ("the thresholds not read from the entry", 'spec.update(entry["thresholds"])',
     "pass", "a contradicted claim is printed with its value, exit 0"),
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
    ("the criteria not sent", 'if k in ("type", "criteria")}', 'if k in ("type",)}',
     "the entry's instructions and criteria reach the model, thresholds do not"),
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
]


def live(record):
    """Every corpus case against the real endpoint, once. A case is red when
    its word differs from the last one recorded under the same wording: a
    known miss stays a counted line, and a change is what fails."""
    m = module(SOURCE)
    jev = m.load_sibling("campaign-jev.py")
    rows = [json.loads(line) for line in CORPUS.read_text().splitlines() if line]
    t = ENTRY["thresholds"]
    targets = [(r["id"], r["state"]["paragraph"], r["state"]["pred"]["name"],
                r["state"]["pred"]["text"]) for r in rows]
    results = m.ask_all(ENTRY, targets, jev)
    today = datetime.date.today().isoformat()
    wording = hashlib.sha256(json.dumps(ENTRY["question"], sort_keys=True)
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
                            "raw": raw, "word": word, "at": today})
    print(f"{misses} of {len(rows)} case(s) off their truth")
    check("live: every case asked", len(results) == len(rows), len(results))
    if record:
        CORPUS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                  for r in rows))
        print(f"recorded into {CORPUS}")


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
