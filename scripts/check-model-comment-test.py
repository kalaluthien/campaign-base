#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-model-comment.py asks a touched definition's own comment against its own body, settles by code what the entry says it settles, and never refuses.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers every
question it is sent with one P(contradicts), and the reader runs in a fixture
repository holding its own copies of the scripts it loads and of
scripts/jev/readings.json. Each case is then broken by a mutation of the
reader's text and must go red by its own assertion.

`--live` asks every line of scripts/jev/corpus/model-comment.jsonl against the
real endpoint, reads each case's highest P(contradicts) against the entry's
thresholds, counts the cases off their `truth`, and fails a case whose word
differs from the last one `seen` under the same question wording, so a known
miss stays counted and a change is red; `--record` appends the reading to each
line's `seen`.

Usage: scripts/check-model-comment-test.py [--live [--record]]
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
SCRIPT = HERE / "check-model-comment.py"
SOURCE = SCRIPT.read_text()
REGISTRY = HERE / "jev" / "readings.json"
CORPUS = HERE / "jev" / "corpus" / "model-comment.jsonl"
ENTRIES = json.loads(REGISTRY.read_text())
ENTRY = ENTRIES["model-comment"]
MODEL = "jev-1.13.0"
ROOT = Path(tempfile.mkdtemp(prefix="model-comment-"))

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

# THE FIXTURE CARRIES ONE OF EVERY SHAPE THE READER DECIDES BY, and the words
# are chosen so the two code rules bite: `holds`'s second sentence shares only
# the keyword `some` with its body, `guard`'s comment is a section header,
# `steered`'s is a section header WITH A CLAIM UNDER IT, and `noted`'s shares
# only the one-letter bound variable `a`.
SPEC = """module fixture
sig Agent {
  peer: lone Agent
}
/* An agent holds its own claim when it has a peer.
   The owner decides, and some person alone. */
pred holds[a: Agent] { some a.peer }
/* ---------------- the guard ---------------- */
pred guard[a: Agent] { no a.peer }
/* ---------------- the section ----------------
   A steered agent keeps its peer. */
pred steered[a: Agent] { a.peer in Agent }
-- The owner keeps a copy, and nobody else reads it.
pred noted[a: Agent] { a in Agent }
pred quiet[a: Agent] { a in Agent }
-- Every Agent is an Agent, said twice over.
fact everyAgent { all a: Agent | a in Agent }
"""
CHECKS = """module fixture/checks
open fixture
/* The assert names `holds`. */
assert Held { all a: Agent | holds[a] implies some a.peer }
"""


def module(source):
    m = types.ModuleType("modelcomment")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return m


def load(source):
    return types.SimpleNamespace(source=source, m=module(source))


def repo(t, edits, p=0.9, url=None, registry=True, tier="advise", drop=False):
    """The reader, as `t.source`, run in a fresh repository whose first commit
    holds the fixture tree and whose index holds `edits` on top of it."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    files = {"spec/fixture/system.als": SPEC,
             "spec/fixture/checks.als": CHECKS,
             "README.md": "fixture\n",
             "scripts/check-model-comment.py": t.source,
             "scripts/check-cited-claims.py": (HERE / "check-cited-claims.py").read_text(),
             "scripts/check-tree-shape.py": (HERE / "check-tree-shape.py").read_text(),
             "scripts/campaign-jev.py": (HERE / "campaign-jev.py").read_text()}
    if registry:
        entries = json.loads(REGISTRY.read_text())
        for name in entries:
            entries[name]["tier"] = tier
        if drop:
            del entries["model-comment"]
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
    r = subprocess.run([sys.executable, "scripts/check-model-comment.py",
                        "--staged"], cwd=d, capture_output=True, text=True, env=env)
    return r, r.stdout + r.stderr, d


def rows(d):
    """Every log row the run wrote."""
    path = d / "jev.log"
    return [json.loads(line) for line in path.read_text().splitlines()
            if line] if path.exists() else []


def asked():
    """[(the body sent, the claims sent)] of every call, in call order."""
    return [(b["state"]["body"],
             [q["instructions"]["claim"] for q in b["questions"].values()])
            for b in SEEN]


def cut_definitions(t):
    got = {name: (comment, body) for _, name, comment, body, _, _
           in t.m.definitions({"spec/fixture/system.als": SPEC}, s1(t))}
    return (sorted(got) == ["everyAgent", "guard", "holds", "noted", "quiet",
                            "steered"]
            and got["holds"][0].startswith("An agent holds")
            and got["holds"][0].endswith("some person alone.")
            and got["everyAgent"][0] == "Every Agent is an Agent, said twice over."
            and got["quiet"][0] == ""), got


def s1(t):
    return t.m.load_sibling("check-cited-claims.py")


def body_has_no_comment(t):
    got = {name: body for _, name, _, body, _, _
           in t.m.definitions({"spec/fixture/system.als": SPEC}, s1(t))}
    return ("An agent holds" not in got["holds"]
            and "pred holds[a: Agent] { some a.peer }" in got["holds"]), got["holds"]


def claims_cut_and_settled(t):
    comment, body = next((c, b) for _, n, c, b, _, _
                         in t.m.definitions({"spec/fixture/system.als": SPEC},
                                            s1(t)) if n == "holds")
    found, dropped = t.m.claims(comment, body, ENTRY["prefilter"], s1(t))
    return (found == ["An agent holds its own claim when it has a peer."]
            and [w for _, w in dropped] == ["names no identifier of the body"]), (
        found, dropped)


def section_header_settled(t):
    comment, body = next((c, b) for _, n, c, b, _, _
                         in t.m.definitions({"spec/fixture/system.als": SPEC},
                                            s1(t)) if n == "guard")
    found, dropped = t.m.claims(comment, body, ENTRY["prefilter"], s1(t))
    return found == [] and [w for _, w in dropped] == ["a section-header comment"], (
        found, dropped)


def header_keeps_the_claim_under_it(t):
    """A header carries no terminal stop, so it is never a sentence of its own:
    read over the sentences it takes the claim below it with it."""
    comment, body = next((c, b) for _, n, c, b, _, _
                         in t.m.definitions({"spec/fixture/system.als": SPEC},
                                            s1(t)) if n == "steered")
    found, dropped = t.m.claims(comment, body, ENTRY["prefilter"], s1(t))
    return (found == ["A steered agent keeps its peer."]
            and [w for _, w in dropped] == ["a section-header comment"]), (
        found, dropped)


def one_letter_name_is_not_an_identifier(t):
    """The article `a` against a bound `a` is not a sentence naming something
    in the body, and the entry's pattern is what settles it."""
    comment, body = next((c, b) for _, n, c, b, _, _
                         in t.m.definitions({"spec/fixture/system.als": SPEC},
                                            s1(t)) if n == "noted")
    found, dropped = t.m.claims(comment, body, ENTRY["prefilter"], s1(t))
    return (found == []
            and [w for _, w in dropped] == ["names no identifier of the body"]), (
        found, dropped)


def definition_touched(t):
    r, out, _ = repo(t, {"spec/fixture/system.als":
                         SPEC.replace("{ some a.peer }", "{ some a.peer or no a }")})
    return (r.returncode == 0 and len(asked()) == 1
            and asked()[0][1] == ["An agent holds its own claim when it has a peer."]
            and "1 definition(s) asked, 1 claim(s)" in out), (asked(), out)


def comment_touched(t):
    r, out, _ = repo(t, {"spec/fixture/system.als":
                         SPEC.replace("its own claim", "its claim")})
    return (r.returncode == 0 and len(asked()) == 1
            and asked()[0][1] == ["An agent holds its claim when it has a peer."]), (
        asked(), out)


def a_fact_is_a_definition(t):
    r, out, _ = repo(t, {"spec/fixture/system.als":
                         SPEC.replace("| a in Agent }", "| a in Agent or no a }")})
    return (r.returncode == 0
            and asked() == [("fact everyAgent { all a: Agent | a in Agent or no a }",
                             ["Every Agent is an Agent, said twice over."])]), (
        asked(), out)


def one_call_a_definition(t):
    spec = SPEC.replace("The owner decides, and some person alone.",
                        "A peer of an agent is an agent.")
    r, out, _ = repo(t, {"spec/fixture/system.als": spec})
    return (r.returncode == 0 and len(SEEN) == 1 and len(asked()[0][1]) == 2
            and "1 definition(s) asked, 2 claim(s)" in out), (asked(), out)


def uncommented_not_asked(t):
    r, out, _ = repo(t, {"spec/fixture/system.als":
                         SPEC.replace("pred quiet[a: Agent] { a in Agent }",
                                      "pred quiet[a: Agent] { some a }")})
    return r.returncode == 0 and not SEEN and "0 definition(s) asked" in out, (
        asked(), out)


def no_spec_change_asks_nothing(t):
    r, out, _ = repo(t, {"README.md": "changed\n"})
    return (r.returncode == 0 and not SEEN
            and "none a spec/ module; nothing asked" in out), out


def skip_rows_written(t):
    r, out, d = repo(t, {"spec/fixture/system.als":
                         SPEC.replace("{ some a.peer }", "{ some a.peer or no a }")})
    skipped = [row["skipped"] for row in rows(d) if "skipped" in row]
    return (r.returncode == 0 and skipped == ["names no identifier of the body"]
            and "1 sentence(s) settled by code" in out), (skipped, out)


def contradicted_printed(t):
    r, out, _ = repo(t, {"spec/fixture/system.als":
                         SPEC.replace("{ some a.peer }", "{ some a.peer or no a }")},
                     p=0.83)
    return r.returncode == 0 and "contradicts 0.83" in out, out


def clear_not_printed(t):
    r, out, _ = repo(t, {"spec/fixture/system.als":
                         SPEC.replace("{ some a.peer }", "{ some a.peer or no a }")},
                     p=0.05)
    return (r.returncode == 0 and "contradicts 0" not in out
            and "1 clear" in out), out


def shadow_prints_counts(t):
    r, out, _ = repo(t, {"spec/fixture/system.als":
                         SPEC.replace("{ some a.peer }", "{ some a.peer or no a }")},
                     p=0.83, tier="shadow")
    return (r.returncode == 0 and len(SEEN) == 1 and "contradicts 0.83" not in out
            and "1 claim(s) read as contradicted" in out), out


def row_carries_its_join_key(t):
    """WHAT THE MOVE FROM `ask` TO `judge` BOUGHT. The row names the reading
    and its wording, and carries the key as FIELDS -- the repository, the sha
    this commit sits on, the file and the definition -- so a later commit that
    rewrote that comment can be joined to the answer. Under `ask` the row
    carried none of them and every one of them parked in the log for good."""
    _r, _out, d = repo(t, {"spec/fixture/system.als":
                           SPEC.replace("{ some a.peer }",
                                        "{ some a.peer or no a }")})
    judged = [row for row in rows(d) if row.get("reading") == "model-comment"]
    one = judged[0] if judged else {}
    return (len(judged) == 1 and one.get("repo") == "o/r"
            and one.get("path") == "spec/fixture/system.als"
            and one.get("name") == "holds"
            and len(one.get("commit") or "") == 40
            and len(one.get("wording") or "") == 12), (len(judged), one)


def entry_reaches_model(t):
    repo(t, {"spec/fixture/system.als":
             SPEC.replace("{ some a.peer }", "{ some a.peer or no a }")})
    q = SEEN[0]["questions"]["model-comment#c0"] if SEEN else {}
    return (q.get("criteria") == ENTRY["question"]["criteria"]
            and q.get("instructions", {}).get("question")
            == ENTRY["question"]["instructions"]
            and set(SEEN[0]["state"]) == {"body"} and "yes_over" not in q), (
        q, SEEN[0]["state"] if SEEN else {})


def unknown_on_failure(t):
    r, out, _ = repo(t, {"spec/fixture/system.als":
                         SPEC.replace("{ some a.peer }", "{ some a.peer or no a }")},
                     url="http://127.0.0.1:9/v1/systemone")
    return r.returncode == 0 and "unknown" in out and "did not answer" in out, out


def entry_missing_named(t):
    r, out, _ = repo(t, {"spec/fixture/system.als":
                         SPEC.replace("{ some a.peer }", "{ some a.peer or no a }")},
                     drop=True)
    return (r.returncode == 0 and not SEEN
            and "no entry `model-comment`" in out), out


def failure_exits_zero(t):
    r, out, _ = repo(t, {"spec/fixture/system.als": SPEC + "\n"}, registry=False)
    return r.returncode == 0 and "could not read the commit" in out, (r.returncode, out)


CASES = {
    "definitions: a pred, a fact and an assert, each with the comment above it": cut_definitions,
    "the body carries none of its own comment": body_has_no_comment,
    "claims: a sentence kept, one naming only a keyword settled": claims_cut_and_settled,
    "a section-header comment is settled and nothing is asked of it": section_header_settled,
    "a header over a claim settles the header alone": header_keeps_the_claim_under_it,
    "a sentence sharing only a one-letter bound name is settled": one_letter_name_is_not_an_identifier,
    "a staged body edit asks that definition alone": definition_touched,
    "a staged comment edit asks the definition under it": comment_touched,
    "a named fact is a definition here": a_fact_is_a_definition,
    "one call a definition, every claim of it in that call": one_call_a_definition,
    "a definition with no comment is not asked": uncommented_not_asked,
    "a commit touching no spec module asks nothing and says so": no_spec_change_asks_nothing,
    "a sentence code settled is written as a skip row naming the rule": skip_rows_written,
    "a contradicted claim is printed with its value, exit 0": contradicted_printed,
    "a clear claim is counted, not printed": clear_not_printed,
    "at tier shadow the counts are printed and no claim": shadow_prints_counts,
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "the row carries the reading, the wording and the join key": row_carries_its_join_key,
    "a failed call prints unknown and exits 0": unknown_on_failure,
    "a missing entry is named and nothing is asked": entry_missing_named,
    "a reader that could not read exits 0 and says so": failure_exits_zero,
}

MUTATIONS = [
    ("a fact left out of the definitions",
     '(pred|fun|assert|fact)', '(pred|fun|assert)',
     "a named fact is a definition here"),
    ("the comment's delimiters kept in the claim",
     'MARKER.sub("", "\\n".join(lines[first:i])).strip(),',
     '"\\n".join(lines[first:i]).strip(),',
     "definitions: a pred, a fact and an assert, each with the comment above it"),
    ("the body read with its comment in it",
     '"\\n".join(code[i:last + 1]).strip(),',
     '"\\n".join(lines[first:last + 1]).strip(),',
     "the body carries none of its own comment"),
    ("a keyword counted as an identifier of the body",
     'keywords = set(prefilter["keywords"])', "keywords = set()",
     "claims: a sentence kept, one naming only a keyword settled"),
    ("the identifier rule not read",
     "if not names & (set(word.findall(sentence)) - keywords):", "if False:",
     "claims: a sentence kept, one naming only a keyword settled"),
    ("a section header read as a claim",
     "if header.search(line):", "if False:",
     "a section-header comment is settled and nothing is asked of it"),
    ("the header read over the sentences rather than off the lines",
     'for line in comment.split("\\n"):', "for line in [comment]:",
     "a header over a claim settles the header alone"),
    ("the identifier pattern not read from the entry",
     'word = re.compile(prefilter["identifiers"])',
     'word = re.compile(r"\\b[A-Za-z_]\\w*\\b")',
     "a sentence sharing only a one-letter bound name is settled"),
    ("an untouched definition asked",
     "if not s1.overlaps(hunks.get(path, []), first, last):",
     "if True:",
     "a staged body edit asks that definition alone"),
    ("a comment edit not read as touching its definition",
     "first, last = s1.comment_above(lines, i), s1.block_end(code, i)",
     "first, last = i, s1.block_end(code, i)",
     "a staged comment edit asks the definition under it"),
    ("a definition with no claim of its own asked anyway",
     "if found:", "if True:",
     "a definition with no comment is not asked"),
    ("one call a claim rather than a definition",
     '{"claim": {f"c{i}": c for i, c in enumerate(found)},',
     '{"claim": {f"c{i}": c for i, c in enumerate(found[:1])},',
     "one call a definition, every claim of it in that call"),
    ("the answers never reported",
     "            s1.report(ask_all(entry, states, jev, jev.commit_key(), env),\n"
     "                      entry, out)", "            pass",
     "a contradicted claim is printed with its value, exit 0"),
    ("the tier read as advise whatever the entry says",
     "                      entry, out)",
     '                      dict(entry, tier="advise"), out)',
     "at tier shadow the counts are printed and no claim"),
    ("a settled sentence left unlogged",
     "jev.skip(READER, f\"{path} `{name}`: {sentence}\", why, env=env)", "pass",
     "a sentence code settled is written as a skip row naming the rule"),
    ("the row keyed by the file alone",
     "key=dict(key, path=path, name=name), env=env)",
     "key={\"path\": path}, env=env)",
     "the row carries the reading, the wording and the join key"),
    ("the definition never named on the row",
     "key=dict(key, path=path, name=name), env=env)",
     "key=dict(key, path=path), env=env)",
     "the row carries the reading, the wording and the join key"),
    ("a commit touching no spec module read in full",
     "if not staged:", "if False:",
     "a commit touching no spec module asks nothing and says so"),
    ("a missing entry read as an empty one",
     "if READING not in registry:", "if False:",
     "a missing entry is named and nothing is asked"),
    ("the failure boundary removed",
     "except Exception as e:  # noqa: BLE001 -- a reading never refuses a commit",
     "except ZeroDivisionError as e:",
     "a reader that could not read exits 0 and says so"),
]


def live(record):
    """Every corpus case against the real endpoint, once. A case is red when
    its word differs from the last one recorded under the same wording: a
    known miss stays a counted line, and a change is what fails."""
    m = module(SOURCE)
    jev = m.load_sibling("campaign-jev.py")
    s1_mod = m.load_sibling("check-cited-claims.py")
    rows_ = [json.loads(line) for line in CORPUS.read_text().splitlines() if line]
    t = ENTRY["thresholds"]
    states = [(r["id"], [r["state"]["claim"]], r["state"]["body"]) for r in rows_]
    results = m.ask_all(ENTRY, states, jev, s1_mod)
    today = datetime.date.today().isoformat()
    wording = hashlib.sha256(json.dumps(ENTRY["question"], sort_keys=True)
                             .encode()).hexdigest()[:12]
    misses = 0
    for row, (label, found, reading) in zip(rows_, results):
        ps = [((a.raw or {}).get("probabilities") or {}).get(t["option"])
              for a in reading.answers.values()]
        raw = max(ps) if ps and None not in ps else None
        word = ("unknown" if raw is None else "yes" if raw >= t["yes_over"]
                else "no" if raw <= t["no_under"] else "unknown")
        print(f"{row['id']}  {row['role']:<8} truth {row['truth']:<3} "
              f"{'-' if raw is None else f'{raw:.2f}'} {word}  "
              f"{row['source'].get('ref', '')}")
        misses += word != row["truth"]
        before = [x for x in row["seen"] if x.get("wording") == wording]
        if before:
            check(f"live {row['id']} reads {before[-1]['word']} as last recorded",
                  word == before[-1]["word"], f"{word} at {raw}")
        row["seen"].append({"model": reading.model, "wording": wording,
                            "raw": raw if raw is None else round(raw, 2),
                            "word": word, "at": today})
    print(f"model-comment: {misses} of {len(rows_)} case(s) off their truth")
    check("live model-comment: every case asked", len(results) == len(rows_),
          len(results))
    if record:
        CORPUS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                  for r in rows_))
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
