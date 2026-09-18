#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-form-behaviour.py asks one call a hunk of a maintenance claim, settles by code what its prefilter names, skips what it cannot send, asks nothing on any other claim, and never refuses; and that the push hook starts it after pushing to GitHub.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers every
question with one `choice`, a fake `gh` on PATH answers the sub-issue, and the
reader runs in a fixture git repository from a `scripts/` directory holding the
real siblings it loads and this reading's registry entry. Each case is then
broken by a mutation of the reader's text and must go red by its own assertion.

`--live` asks every line of scripts/jev/corpus/form-behaviour.jsonl against
the real endpoint and fails a case whose word differs from the last one `seen`
under the same question wording; `--record` appends the reading to `seen`.

Usage: scripts/check-form-behaviour-test.py [--live [--record]]
"""
import datetime
import http.server
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
harness = importlib.import_module("suite-harness-test")
check = harness.check

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-form-behaviour.py"
SOURCE = SCRIPT.read_text()
ENTRY = json.loads((HERE / "jev" / "readings.json").read_text())["form-behaviour"]
CORPUS = HERE / "jev" / "corpus" / "form-behaviour.jsonl"
ROOT = Path(tempfile.mkdtemp(prefix="form-behaviour-"))
SIBLINGS = ("campaign-jev.py", "check-campaign-claim.py", "check-diff-screen.py",
            "campaign-claim.py", "campaign-tracker.py", "campaign-repos.py")
SKILL = HERE.parent / ".claude" / "skills" / "assuming-role" / "scripts"
FILLER = "".join(f"x{i} = {i}\n" for i in range(12))


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                           "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


# THE REPOSITORY. `origin/main` holds `a.py`, `doc.md`, `s.sh` and `old.bin`.
# The branch's first commit changes `a.py`'s docstring; HEAD changes what
# `g` returns, rewords the rule in `doc.md` and its heading, rewords the
# comment in `s.sh`, adds `t-test.py` and rewrites the binary. So HEAD touched
# five files and their branch patches hold six hunks: `g` and `doc.md` are
# asked, the docstring, the comment and the test are settled, the binary is
# skipped. Three more are asked though a marker opens every changed line: a
# shell option line opening `--`, an Alloy comment, which is the spec, and a
# module docstring a script prints as its usage.
REPO = ROOT / "repo"
REPO.mkdir()
git(REPO, "init", "-q", "-b", "main")
A_MAIN = f'def f():\n    """Say one."""\n    return 1\n\n\n{FILLER}\ndef g():\n    return 2\n'
(REPO / "a.py").write_text(A_MAIN)
(REPO / "doc.md").write_text("# Rule\n\nA hook is never bypassed.\n")
(REPO / "s.sh").write_text("# say hi\necho hi\n")
(REPO / "old.bin").write_bytes(b"\x00\x01\x02")
(REPO / "m.sh").write_text("gh pr merge \\\n  --squash \\\n  1\n")
(REPO / "x.als").write_text("-- a hook is never bypassed\nsig A {}\n")
(REPO / "u.py").write_text('"""Usage: u.py <n>"""\nprint(__doc__)\n')
git(REPO, "add", "-A")
git(REPO, "commit", "-q", "-m", "main")
git(REPO, "update-ref", "refs/remotes/origin/main", "HEAD")
git(REPO, "remote", "add", "origin", "git@github.com:o/r.git")
git(REPO, "checkout", "-q", "-b", "demo/9-topic")
(REPO / "a.py").write_text(A_MAIN.replace("Say one.", "Return one."))
git(REPO, "commit", "-qam", "first")
(REPO / "a.py").write_text(A_MAIN.replace("Say one.", "Return one.").replace("return 2", "return 3"))
(REPO / "doc.md").write_text("# Rules\n\nA hook is not bypassed without a reason.\n")
(REPO / "s.sh").write_text("# say hello\necho hi\n")
(REPO / "t-test.py").write_text("assert True\n")
(REPO / "old.bin").write_bytes(b"\x00\x09\x02")
(REPO / "m.sh").write_text("gh pr merge \\\n  --merge --admin \\\n  1\n")
(REPO / "x.als").write_text("-- a hook is not bypassed without a reason\nsig A {}\n")
(REPO / "u.py").write_text('"""Usage: u.py <n> [<m>]"""\nprint(__doc__)\n')
git(REPO, "add", "-A")
git(REPO, "commit", "-q", "-m", "head")
HEAD = git(REPO, "rev-parse", "HEAD")

# A MERGE COMMIT: main moved, and the branch took it in.
MERGED = ROOT / "merged"
shutil.copytree(REPO, MERGED)
git(MERGED, "checkout", "-q", "main")
(MERGED / "m.py").write_text("main moved\n")
git(MERGED, "add", "-A")
git(MERGED, "commit", "-q", "-m", "main moves")
git(MERGED, "update-ref", "refs/remotes/origin/main", "HEAD")
git(MERGED, "checkout", "-q", "demo/9-topic")
git(MERGED, "merge", "-q", "--no-edit", "main")

# NO origin/main at all.
LONE = ROOT / "lone"
shutil.copytree(REPO, LONE)
git(LONE, "update-ref", "-d", "refs/remotes/origin/main")

INTENT = "- give each script reading one home"
MAINTENANCE = {"labels": ["kind:maintenance"], "body": f"## Intent\n\n{INTENT}\n\n## Scope\n- x\n"}

FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_GH_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
issue = os.environ.get("FAKE_ISSUE")
if not issue:
    print("gh: could not connect", file=sys.stderr)
    sys.exit(1)
print(issue)
'''

SEEN = []
LOGGED = []
GH_CALLS = []


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        answers = {q: {"type": "choice", "choice": "asked_behaviour", "confidence": 0.7,
                       "probabilities": {"form_only": 0.1, "asked_behaviour": 0.7,
                                         "unasked_behaviour": 0.15, "unclear": 0.05}}
                   for q in body["questions"]}
        data = json.dumps({"model": "jev-1.13.0", "answers": answers}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


SERVER = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{SERVER.server_address[1]}/v1/systemone"


def load(source):
    m = types.ModuleType("formbehaviour")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return types.SimpleNamespace(source=source, m=m)


def run(t, argv=(), issue=MAINTENANCE, registry=True, cwd=REPO):
    """The finished process; `SEEN` holds the calls, `LOGGED` the log rows,
    `GH_CALLS` what the fake gh was asked."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    scripts = d / "scripts"
    (scripts / "jev").mkdir(parents=True)
    shutil.copytree(SKILL, d / ".claude" / "skills" / "assuming-role" / "scripts",
                    ignore=shutil.ignore_patterns("*-test.py", "fixtures"))
    (scripts / SCRIPT.name).write_text(t.source)
    for name in SIBLINGS:
        shutil.copy(HERE / name, scripts / name)
    if registry:
        (scripts / "jev" / "readings.json").write_text(json.dumps({"form-behaviour": ENTRY}))
    harness.fake(d / "bin", "gh", FAKE_GH)
    SEEN.clear()
    env = dict(os.environ, CAMPAIGN_JEV_URL=URL, TYPESAFE_API_KEY="stub",
               CAMPAIGN_JEV_LOG=str(d / "jev.log"), HOME=str(d),
               GIT_CONFIG_GLOBAL=os.devnull, FAKE_GH_LOG=str(d / "gh.log"),
               FAKE_ISSUE=json.dumps(issue) if issue else "",
               PATH=f"{d / 'bin'}{os.pathsep}{os.environ['PATH']}")
    r = subprocess.run([sys.executable, str(scripts / SCRIPT.name), *argv],
                       capture_output=True, text=True, env=env, cwd=cwd)
    log = d / "jev.log"
    LOGGED[:] = ([json.loads(x) for x in log.read_text().splitlines() if x]
                 if log.exists() else [])
    gh = d / "gh.log"
    GH_CALLS[:] = ([json.loads(x) for x in gh.read_text().splitlines() if x]
                   if gh.exists() else [])
    return r


def asked():
    return sorted((b["state"]["hunk"]["path"], b["state"]["hunk"]["text"].split("\n", 1)[0])
                  for b in SEEN)


def settled():
    return {row["path"]: (row["settled"], (row.get("flag") or {}).get("moved_by"))
            for row in LOGGED if row.get("settled")}


ASKED = ["a.py", "doc.md", "m.sh", "u.py", "x.als"]


def asks_each_unsettled_hunk(t):
    r = run(t)
    paths = [p for p, _ in asked()]
    return (r.returncode == 0 and r.stdout == "" and r.stderr == ""
            and paths == ASKED and len(SEEN) == len(ASKED)), (asked(), r.stderr[-300:])


def state_is_intent_and_hunk(t):
    run(t)
    doc = next((b["state"] for b in SEEN if b["state"]["hunk"]["path"] == "doc.md"), {})
    text = doc.get("hunk", {}).get("text", "")
    return (doc.get("intent") == INTENT and text.startswith("@@ -1,3 +1,3 @@")
            and "-A hook is never bypassed." in text
            and "+A hook is not bypassed without a reason." in text), doc


def settles_by_code(t):
    run(t)
    return settled() == {
        "a.py": ("form_only", "the same AST, docstrings blanked"),
        "s.sh": ("form_only", "comment lines only"),
        "t-test.py": ("form_only", "a test suite")}, settled()


def reads_the_branch_patch(t):
    """The docstring was changed by the FIRST commit, which HEAD did not touch
    again in that hunk: only the merge-base diff shows it."""
    run(t)
    a = sorted(row["hunk"] for row in LOGGED if row.get("path") == "a.py")
    return len(a) == 2, a


def row_carries_its_join_key(t):
    run(t)
    one = next((row for row in LOGGED if row.get("reading") and row.get("path") == "doc.md"), {})
    return (one.get("reading") == "form-behaviour"
            and one.get("repo") == "o/r" and one.get("commit") == HEAD
            and one.get("hunk") == "@@ -1,3 +1,3 @@"
            and one.get("read") == f"demo/9-topic {HEAD[:12]} doc.md @@ -1,3 +1,3 @@"), one


def flag_is_the_unasked_probability(t):
    run(t)
    flags = sorted(json.dumps(row.get("flag")) for row in LOGGED
                   if row.get("reading") and not row.get("settled"))
    return flags == [json.dumps({"code": 0.15, "moved_by": "unasked_behaviour"})] * len(ASKED), flags


def asks_what_only_looks_like_a_comment(t):
    run(t)
    got = {p for p, _ in asked()}
    return {"m.sh", "x.als", "u.py"} <= got and not {"m.sh", "x.als", "u.py"} & set(settled()), \
        (sorted(got), settled())


def an_insertion_hunk_lines_up(t):
    """A `-N,0` hunk inserts AFTER line N: a docstring-only function added
    after line 1 leaves no AST unchanged, and a comment line inserted there
    does. Read at the unit, since git's three lines of context make such a
    hunk only for an empty file."""
    before = "x = 1\ny = 2\n"
    comment = t.m.same_ast(before, "@@ -1,0 +2 @@\n+# note", 1, 0)
    code = t.m.same_ast(before, "@@ -1,0 +2 @@\n+z = 3", 1, 0)
    # one line early would land inside the string and change its value
    string = t.m.same_ast('y = """a\nb"""\nx = 1\n', "@@ -2,0 +3 @@\n+# c", 2, 0)
    return comment and not code and string, (comment, code, string)


def skips_the_binary(t):
    run(t)
    return [(r["read"].rsplit(" ", 1)[-1], r["skipped"]) for r in LOGGED if "skipped" in r] == \
        [("old.bin", "a binary file")], LOGGED


def other_kind_asks_nothing(t):
    r = run(t, issue={"labels": ["kind:development"], "body": MAINTENANCE["body"]})
    return (r.returncode == 0 and not SEEN and not LOGGED
            and GH_CALLS and GH_CALLS[0][:2] == ["api", "repos/kalaluthien/campaign-base/issues/9"]), \
        (len(SEEN), LOGGED, GH_CALLS)


def no_claim_asks_nothing(t):
    r = run(t, argv=(HEAD, "main"))
    return r.returncode == 0 and not SEEN and not LOGGED and not GH_CALLS, (LOGGED, GH_CALLS)


def unread_issue_skips(t):
    r = run(t, issue=None)
    return (r.returncode == 0 and not SEEN
            and [x.get("skipped") for x in LOGGED] == ["sub-issue 9 did not read (LookupError)"]), LOGGED


def no_intent_skips(t):
    r = run(t, issue={"labels": ["kind:maintenance"], "body": "## Intent\n\n## Scope\n- x\n"})
    return (r.returncode == 0 and not SEEN
            and [x.get("skipped") for x in LOGGED] == ["sub-issue 9 has no ## Intent"]), LOGGED


def merge_asks_nothing(t):
    r = run(t, cwd=MERGED)
    return r.returncode == 0 and not SEEN and not LOGGED, (len(SEEN), LOGGED)


def no_merge_base_skips_once(t):
    r = run(t, cwd=LONE)
    return (r.returncode == 0 and not SEEN
            and [x.get("skipped") for x in LOGGED] == ["no merge-base with origin/HEAD or origin/main"]), LOGGED


def failure_logs_skip(t):
    r = run(t, registry=False)
    return (r.returncode == 0 and not SEEN and r.stdout == "" and r.stderr == ""
            and [x.get("skipped") for x in LOGGED] == ["the reading raised FileNotFoundError"]
            ), (r.stderr[-300:], LOGGED)


CASES = {
    "each hunk code did not settle is asked in a call of its own, printing nothing": asks_each_unsettled_hunk,
    "the state is the Intent and the hunk from its @@ line": state_is_intent_and_hunk,
    "a docstring, a comment and a test suite are settled form_only, the rule named": settles_by_code,
    "the hunks are the branch patch's, not HEAD's alone": reads_the_branch_patch,
    "the row carries the reading and the repository, sha, path and hunk": row_carries_its_join_key,
    "an asked row's flag is P(unasked_behaviour)": flag_is_the_unasked_probability,
    "a shell option, an Alloy comment and a module docstring are asked, not settled": asks_what_only_looks_like_a_comment,
    "a -N,0 insertion hunk is applied after line N": an_insertion_hunk_lines_up,
    "a binary logs a skip": skips_the_binary,
    "a claim of another kind asks and logs nothing": other_kind_asks_nothing,
    "a branch that is no claim asks, reads and logs nothing": no_claim_asks_nothing,
    "a sub-issue that did not read logs one skip": unread_issue_skips,
    "a sub-issue with an empty Intent logs one skip": no_intent_skips,
    "a merge commit asks and logs nothing": merge_asks_nothing,
    "a commit with no merge-base logs one skip": no_merge_base_skips_once,
    "a reading that raised exits 0, says nothing and logs a skip": failure_logs_skip,
}

MUTATIONS = [
    ("every hunk asked as one", "for header, text, start, count in hunks(patch):",
     "for header, text, start, count in hunks(patch)[:1]:",
     "each hunk code did not settle is asked in a call of its own, printing nothing"),
    ("the Intent not sent", '{"intent": intent, "hunk"', '{"intent": "", "hunk"',
     "the state is the Intent and the hunk from its @@ line"),
    ("the AST rule dropped", 'if path.endswith(".py") and before is not None and same_ast(',
     'if False and same_ast(',
     "a docstring, a comment and a test suite are settled form_only, the rule named"),
    ("docstrings not blanked", "            body[0] = ast.Pass()\n", "            pass\n",
     "a docstring, a comment and a test suite are settled form_only, the rule named"),
    ("the comment rule dropped", "all(comment.match(line) for line in changed)",
     "all(False for line in changed)",
     "a docstring, a comment and a test suite are settled form_only, the rule named"),
    ("the test rule dropped", "if test.search(path):", "if False:",
     "a docstring, a comment and a test suite are settled form_only, the rule named"),
    ("the hunk left out of the key", '"key": dict(key, path=path, hunk=header) if key',
     '"key": dict(key, path=path) if key',
     "the row carries the reading and the repository, sha, path and hunk"),
    ("the flag read off another option", 'FLAG = "unasked_behaviour"', 'FLAG = "asked_behaviour"',
     "an asked row's flag is P(unasked_behaviour)"),
    ("every marker read in every file", "comment = COMMENT.get(Path(path).suffix)",
     'comment = re.compile(r"^\\s*(#|//|--|/\\*|\\*|\\*/)")',
     "a shell option, an Alloy comment and a module docstring are asked, not settled"),
    ("the module docstring blanked", "        if isinstance(node, ast.Module):\n            continue\n", "",
     "a shell option, an Alloy comment and a module docstring are asked, not settled"),
    ("an insertion applied before line N", "at = start - 1 if count else start", "at = start - 1",
     "a -N,0 insertion hunk is applied after line N"),
    ("the kind not read", "if kind != KIND:", "if False:",
     "a claim of another kind asks and logs nothing"),
    ("no claim still read", "if number is None:\n        return\n", "pass\n",
     "a branch that is no claim asks, reads and logs nothing"),
    ("an unread issue passes silently",
     '        jev.skip(READER, label, f"sub-issue {number} did not read "\n'
     '                 f"({e.__class__.__name__})", env, cwd=HERE)\n', "",
     "a sub-issue that did not read logs one skip"),
    ("no Intent asked anyway", "if not intent:", "if intent is None:",
     "a sub-issue with an empty Intent logs one skip"),
    ("no merge-base passes silently",
     '        jev.skip(READER, label, "no merge-base with origin/HEAD or "\n'
     '                 "origin/main", env, cwd=HERE)\n', "",
     "a commit with no merge-base logs one skip"),
    ("the failure boundary removed",
     "    jev.shielded(READER, subject, lambda: read(argv, subject, jev, env), env,\n"
     "                 cwd=HERE)",
     "    read(argv, subject, jev, env)",
     "a reading that raised exits 0, says nothing and logs a skip"),
]


def hook(origin, pushable=True):
    """(the hook's output, the reader's argv or None). The real push script
    runs beside stub siblings; the stub reader writes its argv to a marker."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    scripts, bare, clone = d / "scripts", d / "bare.git", d / "clone"
    scripts.mkdir()
    shutil.copy(HERE / "push-campaign-branch.sh", scripts / "push-campaign-branch.sh")
    marker = d / "read"
    (scripts / "check-commit-claim.py").write_text(
        "#!/usr/bin/env python3\nimport sys\nprint('claim demo/9-topic')\nsys.exit(0)\n")
    (scripts / "check-diff-screen.py").write_text("#!/bin/sh\nexit 0\n")
    # THE REGISTRY STAND-IN: both readers a push starts.
    (scripts / "campaign-jev.py").write_text(
        "#!/bin/sh\n[ \"$1 $2\" = \"readers-on push\" ] && "
        "printf '%s\\n' \"$(dirname \"$0\")/check-diff-screen.py\" "
        "\"$(dirname \"$0\")/check-form-behaviour.py\"\n")
    (scripts / "check-form-behaviour.py").write_text(
        f"#!/usr/bin/env python3\nimport sys\nopen({str(marker)!r}, 'w').write(' '.join(sys.argv[1:]))\n")
    for s in scripts.iterdir():
        s.chmod(0o755)
    git(d, "init", "-q", "--bare", str(bare))
    shutil.copytree(REPO, clone)
    git(clone, "remote", "set-url", "origin", origin)
    git(clone, "config", "remote.origin.pushurl", str(bare if pushable else d / "nowhere.git"))
    r = subprocess.run([str(scripts / "push-campaign-branch.sh")], cwd=clone,
                       capture_output=True, text=True)
    for _ in range(50):
        if marker.exists():
            break
        time.sleep(0.1)
    return r.stdout + r.stderr, marker.read_text() if marker.exists() else None


def hook_cases():
    out, arg = hook("git@github.com:o/r.git")
    check("the push hook starts the reading on the pushed sha and its branch after pushing a claim to GitHub",
          "pushed demo/9-topic" in out and arg == f"{HEAD} demo/9-topic", (out, arg))
    out, arg = hook(str(ROOT / "elsewhere.git"))
    check("...and not for a remote that is not GitHub",
          "pushed demo/9-topic" in out and arg is None, (out, arg))
    out, arg = hook("https://github.com/o/r", pushable=False)
    check("...nor after a push that failed",
          "could NOT push" in out and arg is None, (out, arg))


def live(record):
    """Every corpus case against the real endpoint, once. Red when its word
    differs from the last one recorded under the same wording."""
    jev = load(SOURCE).m.jev_module()
    rows = [json.loads(line) for line in CORPUS.read_text().splitlines() if line]
    wording = jev.wording(ENTRY)
    today = datetime.date.today().isoformat()
    for row in rows:
        judged = jev.judge(ENTRY["group"], row["state"], read=row["id"],
                           reader="check-form-behaviour-test.py", log=False,
                           reg={"form-behaviour": ENTRY})
        verdict = judged.verdicts["form-behaviour"]
        raw = round(((verdict.raw or {}).get("probabilities") or {})
                    .get("unasked_behaviour", -1), 2)
        before = [x for x in row["seen"] if x.get("wording") == wording]
        if before:
            check(f"live {row['id']} reads {before[-1]['word']} as last recorded",
                  verdict.word == before[-1]["word"], f"{verdict.word} at {raw}")
        row["seen"].append({"model": judged.model, "wording": wording, "raw": raw,
                            "word": verdict.word, "at": today})
    if record:
        CORPUS.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                                  for r in rows))
        print(f"recorded into {CORPUS}")


def main(argv):
    try:
        if "--live" in argv:
            live("--record" in argv)
            return harness.report()
        harness.mutate(SOURCE, load, CASES, MUTATIONS)
        hook_cases()
        return harness.report()
    finally:
        shutil.rmtree(ROOT, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
