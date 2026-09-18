#!/usr/bin/env python3
# witnesses: M2_MergeInTheStateAfterAPush, M2b_TheRuleExcludesTheStalePush, M2c_AFreshReviewAfterThePushLands, S5b_WithoutTheLandingCheck, S2a_ProseOnlyChange
"""Prove check-merge-review refuses on every branch it claims to refuse on.

One case per refusal, each named after the branch it exercises, and each one
fails when that branch is deleted -- the sweep is recorded in the sub-issue's
REPORT rather than run from here.

PR kalaluthien/campaign-base#262's shape is among them: a pull request carrying
comments, none of which opens REVIEW, merged with nothing refusing it.

NO CASE REACHES THE NETWORK. `gh` is a script this writes onto PATH which
prints the canned JSON the case is about, so what is measured is this reader
and not GitHub's mood. Every case runs the real script end to end, because the
word and the exit status are the whole interface and a case calling the inner
functions would pass with `main`'s wiring cut.

TWO CASES RUN THE MODEL'S OWN SITUATION rather than a hand-written one
(sdlc-alloy#342): alloy solves each of WITNESSES, `alloy-check.py --digest`
prints its instance, and `instance_fixture` turns that into the canned `gh`
answer and the word the model says the reader owes. M2 merges on a push with
no review, M2c on a review taken after the push, so the REVIEW body and the sha
it names reach the verdict. The revision a `Push` advances reaches no verdict
yet: head and REVIEW shift together until a witness reviews before a push.
They need the solver, as CI installs it, and fail red without one.

Usage: scripts/check-merge-review-test.py   (needs ~/.local/bin/alloy)
"""
import contextlib
import hashlib
import http.server
import importlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-merge-review.py"
HEAD = "8ca2609f3b1d4e7a9c0b25d8e6f41a3b7c9d0e2f"
OTHER = "fb1bd4f2a7c3e59018d4b6f0a2c8e1d7b3f9a0c5e"
harness = importlib.import_module("suite-harness-test")
check = harness.check

# EVERY CASE IS POINTED AWAY FROM THIS MACHINE'S OWN JEV LOG AND STORE, AT THE
# ONE RUNNER, so no case can forget. `gate` runs the pull request thread
# reading on every call, and campaign-jev.py falls back to
# `<base>/runtime/jev.log` when nothing names a log -- so the cases written
# before that reading existed, which name nothing, each appended a row marked
# `endpoint: real` to the shared log and put their fixture states in the shared
# store. Measured: 20 rows a run from here, 10 from
# check-campaign-claim-test.py (pr#474 REVIEW issuecomment-5718228578).
JEV_ROOT = Path(tempfile.mkdtemp(prefix="merge-review-jev-"))
JEV_LOG = JEV_ROOT / "jev.log"
with contextlib.closing(socket.socket()) as _s:
    _s.bind(("127.0.0.1", 0))
    JEV_CLOSED = f"http://127.0.0.1:{_s.getsockname()[1]}/v1/systemone"


# ONE LOG ROW PER READING OF THE GROUP, so a case counting rows reads the
# registry rather than a number that drifts the next time the group grows.
THREAD_READINGS = len(
    [e for e in json.loads((SCRIPT.parent / "jev" / "readings.json")
                           .read_text(encoding="utf-8")).values()
     if e.get("group") == "pull-request-thread"])

# WHAT ONE `gate` RUN COSTS THE ENDPOINT, counted rather than argued. The
# thread readings ride in ONE call however many the group holds, so a reading
# added to `pull-request-thread` must not move this number -- and the only way
# to know is to count the POSTs a whole gate run makes. The stub answers every
# question `unknown` by returning no answer at all: what is measured here is
# the REQUEST, not the reply.
POSTS = {"count": 0, "questions": []}


class _Counting(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        POSTS["count"] += 1
        try:
            POSTS["questions"].append(
                sorted(json.loads(raw.decode()).get("questions") or {}))
        except ValueError:
            POSTS["questions"].append([])
        data = json.dumps({"model": "jev-1.13.0", "answers": {}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


_COUNTER = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Counting)
threading.Thread(target=_COUNTER.serve_forever, daemon=True).start()
JEV_COUNTED = f"http://127.0.0.1:{_COUNTER.server_address[1]}/v1/systemone"


COMMENT_ID = [5700000000]


def comment(body, at=None):
    """The REST shape, `user.login` -- not `gh pr view`'s `author.login`. The
    reader changed channels and a fixture still speaking the old one would test
    a mapping nothing performs. The `id` is the REST field the thread reading's
    join key carries: every join is "the later fact on that number", and
    `created_at` is what `one_round` orders on."""
    COMMENT_ID[0] += 1
    row = {"id": COMMENT_ID[0], "user": {"login": "kalaluthien"}, "body": body}
    if at:
        row["created_at"] = at
    return row


def pr_review(body, at=None):
    """The other channel, which spells its timestamp `submitted_at`. A REVIEW
    posted with `gh pr review --comment -b` arrives here, and AGENTS.md admits
    it, so it must reach `one_round` in its own place in time."""
    COMMENT_ID[0] += 1
    row = {"id": COMMENT_ID[0], "user": {"login": "kalaluthien"}, "body": body}
    if at:
        row["submitted_at"] = at
    return row


def fake_gh(bindir, head=HEAD, comments=(), reviews=(), status=0, stdout=None,
            view_stdout=None, branch="sdlc-alloy/363-x", issue=None):
    """A `gh` on PATH answering the three calls this reader makes.

    THREE, not one, since the reader stopped taking its comments from
    `gh pr view`: the head comes from `pr view --json headRefOid`, and the two
    comment channels from `gh api --paginate` over their REST endpoints. The
    fake dispatches on the argument list exactly as the real one would, so a
    case cannot pass by answering a call the script does not make.

    `status` and `stdout` are the two ways an answer goes wrong -- a call that
    failed, and one that is not JSON -- and they apply to the `gh api` calls;
    `view_stdout` is the same for the head call. `issue` is the sub-issue
    `--merge` reads, as `gh issue view --json title,body,labels,parent`."""
    body = json.dumps({"headRefOid": head, "headRefName": branch} if head else {})
    if view_stdout is not None:
        body = view_stdout
    payloads = {"issues": json.dumps(list(comments)),
                "pulls": json.dumps(list(reviews))}
    if stdout is not None:
        payloads = {"issues": stdout, "pulls": stdout}
    gh = Path(bindir) / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f"  *'issue view'*) cat <<'JSON'\n"
        f"{issue if isinstance(issue, str) else json.dumps(issue or {})}\nJSON\n    exit 0 ;;\n"
        f"  *'pr view'*) cat <<'JSON'\n{body}\nJSON\n    exit 0 ;;\n"
        f"  *issues*) cat <<'JSON'\n{payloads['issues']}\nJSON\n    exit {status} ;;\n"
        f"  *pulls*) cat <<'JSON'\n{payloads['pulls']}\nJSON\n    exit {status} ;;\n"
        "esac\n")
    gh.chmod(0o755)
    return gh


def call(bindir, *args, stdin=None, cwd=None, **extra):
    """(word, returncode, everything printed). The word is the first token of
    the output, wherever it was printed: a refusal goes to stderr.

    THE ONE RUNNER, and it names the log and the endpoint for EVERY case rather
    than leaving each to remember: `gate` runs the pull request thread reading,
    so a case that named neither wrote a row into this machine's shared
    `runtime/jev.log` and its fixture state into the shared store. `extra`
    still lets a case name its own."""
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}",
               CAMPAIGN_JEV_LOG=str(JEV_LOG), CAMPAIGN_JEV_URL=JEV_CLOSED)
    env.update(extra)
    # A CASE UNSETS A VARIABLE BY NAMING IT None, which is how the control
    # below runs without the two this helper sets: a case that could only ADD
    # to the environment could not show that what it sets is what does the
    # work.
    env = {k: v for k, v in env.items() if v is not None}
    p = subprocess.run([str(SCRIPT), *args], capture_output=True, text=True,
                       env=env, input=stdin, cwd=cwd)
    text = (p.stdout or "") + (p.stderr or "")
    return (text.split(" ", 1)[0].strip() if text else ""), p.returncode, text


# THE LANDING'S FIXTURE: a tree on `main` holding one tied code path, a.py, and
# one untied, c.py, and a change committed on top of it. The sub-issue carries
# both sections unless a case takes one away.
TREE = {"spec/commands.snapshot.json": '{"commands": [["spec/x/checks.als", "run", "S1"]]}\n',
        "scripts/a.py": "x = 1\n", "scripts/a-test.py": "# witnesses: S1\n",
        "scripts/c.py": "x = 1\n", "README.md": "hi\n"}
SECTIONS = "## Intent\n- i\n## Plan\n- p\n"


def sub_issue(body=SECTIONS):
    return {"title": "t", "body": body, "labels": [], "parent": {"number": 244}}


def landing(d, name, change):
    """A repository whose `main` is TREE and whose HEAD adds `change` to it."""
    root = Path(d) / name
    git = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    for files, ref in ((TREE, "main"), (change, "work")):
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)
        if ref == "main":
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        else:
            subprocess.run([*git, "checkout", "-q", "-b", ref], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-qm", ref, "--no-verify"], check=True)
    return root


MODEL = SCRIPT.parent.parent / "spec" / "campaign" / "orchestration" / "checks.als"
WITNESSES = ("M2_MergeInTheStateAfterAPush", "M2c_AFreshReviewAfterThePushLands")
ALLOY = Path.home() / ".local" / "bin" / "alloy"
STATE = re.compile(r"\s*S\d+(?: \(loop\))?  (.*)")


def witness_digest(d, witness):
    """(the digest of <witness>'s instance, or None, and what went wrong)."""
    out = Path(d) / witness
    try:
        subprocess.run([str(ALLOY), "exec", "-f", "-t", "text", "-c", witness,
                        "-o", str(out), str(MODEL)], capture_output=True, text=True)
    except OSError as e:
        return None, f"alloy could not run: {e}"
    trace = out / f"{witness}-solution-0.txt"
    if not trace.exists():
        return None, f"alloy wrote no instance of {witness} under {out}"
    r = subprocess.run([sys.executable, str(SCRIPT.parent / "alloy-check.py"),
                        "--digest", str(MODEL), str(trace)], capture_output=True, text=True)
    return (r.stdout, "") if r.returncode == 0 else (None, r.stdout + r.stderr)


def sha(revision):
    """The model has no sha, so each revision of the pull request is given one."""
    return hashlib.sha1(f"revision {revision}".encode()).hexdigest()


def instance_fixture(digest):
    """(head, REVIEW bodies, (word, status) the model owes) for one digest.

    THE SHA RULE, stated here once: the pull request opens at revision 0, each
    `Push` of the merged issue makes the next revision the head, and each
    `Review` of it is a REVIEW naming the head in force in its state, signed by
    a session name the reader admits (`S0` is an atom, not one). The word
    is the model's own: `reviewed` exactly when the merged pull request is in
    `Reviewed` in the state whose event is `MergePullRequest`. The `Push` half
    reaches no verdict until a witness reviews before a push: the suite passes
    with it deleted, since M2 and M2c move head and REVIEW together."""
    lines = digest.splitlines()
    if "Reviewed" not in next((l for l in lines if l.startswith("var (")), ""):
        raise LookupError("the digest read no `Reviewed`, so the model's word is unknown")
    rows = [dict(c.split("=", 1) for c in m.group(1).split("  "))
            for m in map(STATE.fullmatch, lines) if m]
    merge = next((i for i, r in enumerate(rows) if r.get("ev") == "MergePullRequest"), None)
    if merge is None:
        raise LookupError("the instance merges nothing")
    issue = rows[merge]["arg"]
    pr = dict(p.split("->") for p in rows[merge]["pr"].split(", "))[issue]
    revision, bodies = 0, []
    for row in rows[:merge]:
        if row.get("arg") != issue:
            continue
        if row.get("ev") == "Push":
            revision += 1
        if row.get("ev") == "Review":
            bodies.append(f"REVIEW upkeep-worker-{row['by'][1:]}: at {sha(revision)[:7]}")
    reviewed = pr in rows[merge].get("Reviewed", "").split(", ")
    return sha(revision), bodies, ("reviewed", 0) if reviewed else ("unreviewed", 1)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        bindir = Path(d) / "bin"
        bindir.mkdir()

        # ---- the gate ------------------------------------------------------

        # PR #262's shape: comments on the pull request, and not one of them
        # opens REVIEW. This is the branch that had no reader at all.
        fake_gh(bindir, comments=[comment(f"REPORT upkeep-worker-3: at {HEAD[:7]}"),
                                  comment("NOTE upkeep-worker-3: a note")])
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a pull request whose comments hold no REVIEW is unreviewed",
              (word, code) == ("unreviewed", 1), f"{word} {code}")
        check("...and the refusal prints the head it read",
              HEAD in text, text)
        check("...and says how many comments it read",
              "2 comment(s) read" in text, text)

        # A REVIEW that names an older sha is the same refusal from the sha's
        # end: the review it points at is at a revision nobody will merge.
        fake_gh(bindir, comments=[comment(f"REVIEW upkeep-worker-3: full round at "
                                          f"{OTHER[:7]}, no findings")])
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a REVIEW naming a sha that is not the head is unreviewed",
              (word, code) == ("unreviewed", 1), f"{word} {code}")
        check("...and the refusal prints the sha that REVIEW did name",
              OTHER[:7] in text, text)

        # CONTROL: the gate is not one that refuses every pull request.
        fake_gh(bindir, comments=[comment(f"REVIEW upkeep-worker-3: full round at "
                                          f"{HEAD[:7]}, no findings")])
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("a REVIEW naming the head is reviewed", (word, code) == ("reviewed", 0),
              f"{word} {code}")

        # ...and a REVIEW posted as a pull-request review, not as a comment,
        # counts too. `gh pr review --comment -b` is a spelling AGENTS.md
        # admits, and reading only `comments` refused it.
        fake_gh(bindir, reviews=[comment(f"REVIEW upkeep-worker-3: at {HEAD[:7]}")])
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("a REVIEW posted as a pull-request review counts",
              (word, code) == ("reviewed", 0), f"{word} {code}")

        # A sha too short to be one is not one: six hex characters is an issue
        # number or a colour, and matching it would pass a REVIEW that pins
        # nothing.
        fake_gh(bindir, comments=[comment(f"REVIEW upkeep-worker-3: at {HEAD[:6]}")])
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("six hex characters do not name a sha",
              (word, code) == ("unreviewed", 1), f"{word} {code}")

        # ---- could not look, which is never a pass -------------------------

        fake_gh(bindir, status=1)
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("a gh call that failed is unknown, not a pass",
              (word, code) == ("unknown", 2), f"{word} {code}")

        # THE LINE, NOT ONLY THE WORD -- the same lesson as the unreadable
        # body below, and this case did not carry it. A `json` handler replaced
        # by a silent `data = {}` lands on the no-head branch, which answers
        # `unknown` too, so the word alone left that branch deletable.
        fake_gh(bindir, stdout="not json at all")
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("an answer that is not JSON is unknown",
              (word, code) == ("unknown", 2) and "not JSON" in text,
              f"{word} {code} {text}")

        # A well-formed answer of the wrong SHAPE is not an empty list of
        # comments. Reading it as one would report "looked and found nothing"
        # for a channel that was never read.
        fake_gh(bindir, stdout='{"message": "Not Found"}')
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a comment channel that answered an object is unknown",
              (word, code) == ("unknown", 2) and "not a list" in text,
              f"{word} {code} {text}")

        fake_gh(bindir, head=None)
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a pull request with no headRefOid is unknown",
              (word, code) == ("unknown", 2), f"{word} {code}")
        check("...and says there is no sha to read a review against",
              "headRefOid" in text, text)

        # ---- the REPORT's end ----------------------------------------------

        fake_gh(bindir)

        word, code, text = call(bindir, "274", "--repo", "o/r", "--report", "-",
                                stdin=f"REPORT upkeep-worker-3: #274 at {OTHER[:7]}\n")
        check("a REPORT pinning a sha that is not the head is stale",
              (word, code) == ("stale", 1), f"{word} {code}")
        check("...and the refusal names both shas",
              OTHER[:7] in text and HEAD in text, text)

        word, code, _ = call(bindir, "274", "--repo", "o/r", "--report", "-",
                             stdin="REPORT upkeep-worker-3: #274, done\n")
        check("a REPORT pinning no sha at all is stale",
              (word, code) == ("stale", 1), f"{word} {code}")

        word, code, _ = call(bindir, "274", "--repo", "o/r", "--report", "-",
                             stdin=f"REPORT upkeep-worker-3: #274 at {HEAD[:7]}\n")
        check("a REPORT pinning the head is pinned",
              (word, code) == ("pinned", 0), f"{word} {code}")

        # A body that is not a REPORT is not a REPORT this may judge. The shape
        # of a first line is check-campaign-claim.py's; this says so rather
        # than reading the sha out of whatever it was handed.
        word, code, text = call(bindir, "274", "--repo", "o/r", "--report", "-",
                                stdin=f"a plain line about {HEAD[:7]}\n")
        check("a body that opens no kind is unknown, not a verdict",
              (word, code) == ("unknown", 2), f"{word} {code}")

        word, code, _ = call(bindir, "274", "--repo", "o/r", "--report", "-",
                             stdin=f"REVIEW upkeep-worker-3: at {HEAD[:7]}\n")
        check("a REVIEW body handed to --report is unknown",
              (word, code) == ("unknown", 2), f"{word} {code}")

        # THE LINE, NOT ONLY THE WORD. A `read_body` that swallowed the error
        # and returned an empty body would answer `unknown` too -- by way of
        # "opens no kind" -- so a case asserting the word alone passes with
        # this branch deleted. The two refusals are told apart by what they
        # say they could not do.
        word, code, text = call(bindir, "274", "--repo", "o/r", "--report",
                                str(Path(d) / "no-such-file"))
        check("a REPORT body that could not be read is unknown",
              (word, code) == ("unknown", 2)
              and "could not read the REPORT body" in text, f"{word} {code} {text}")

        # A file, not only stdin -- the flag takes both and a caller pointing
        # at a written comment must not be the untested path.
        body = Path(d) / "report.md"
        body.write_text(f"REPORT upkeep-worker-3: #274 at {HEAD[:12]}\n")
        word, code, _ = call(bindir, "274", "--repo", "o/r", "--report", str(body))
        check("--report reads a file as well as stdin",
              (word, code) == ("pinned", 0), f"{word} {code}")

        # ---- the sha the run is recorded against ----------------------------

        # `--head` IS THE SUBJECT, and the live tip is a different question.
        # A REVIEW naming the live tip must not turn a run for an older sha
        # green: that is the whole reason the flag exists.
        fake_gh(bindir, head=HEAD,
                comments=[comment(f"REVIEW upkeep-worker-3: at {HEAD[:7]}")])
        word, code, text = call(bindir, "274", "--repo", "o/r", "--head", OTHER)
        check("a REVIEW at the live tip does not review the sha given",
              (word, code) == ("unreviewed", 1), f"{word} {code}")
        check("...and the trail says the branch has moved off it",
              "has since moved to" in text, text)

        fake_gh(bindir, head=HEAD,
                comments=[comment(f"REVIEW upkeep-worker-3: at {OTHER[:7]}")])
        word, code, text = call(bindir, "274", "--repo", "o/r", "--head", OTHER)
        check("...and a REVIEW at the sha given is a review of it",
              (word, code) == ("reviewed", 0), f"{word} {code}")

        fake_gh(bindir, head=HEAD,
                comments=[comment(f"REVIEW upkeep-worker-3: at {HEAD[:7]}")])
        word, code, text = call(bindir, "274", "--repo", "o/r", "--head", HEAD)
        check("a --head that IS the tip says so rather than warning",
              (word, code) == ("reviewed", 0) and "still the branch tip" in text,
              f"{word} {code}")

        # ---- every exit lands on one of the words ---------------------------

        # argparse prints `usage:` and exits 2 -- `unknown`'s status with a
        # different first word, and the first word is what every caller reads.
        word, code, text = call(bindir, "not-a-number")
        check("a call this reader does not take answers unknown, word first",
              (word, code) == ("unknown", 2), f"{word} {code} {text}")

        # ---- the landing ---------------------------------------------------

        def merge(case, change, issue=None, branch="sdlc-alloy/363-x", before="main"):
            fake_gh(bindir, branch=branch, issue=issue or sub_issue())
            return call(bindir, "366", "--repo", "o/r", "--merge", before,
                        cwd=landing(d, case, change))

        # S5b_WithoutTheLandingCheck: a code path written with a suite that
        # witnesses nothing lands with no Spec, and only this reading refuses.
        word, code, text = merge("s5b", {"scripts/b.py": "x = 1\n",
                                        "scripts/b-test.py": "x = 1\n"})
        check("a code path whose suite witnesses no scenario lands unlicensed",
              (word, code) == ("unlicensed", 1) and "without Spec" in text,
              f"{word} {code} {text}")
        check("...and the reading names the untied path",
              "untied code paths it wrote: scripts/b.py" in text, text)

        word, code, text = merge("tied", {"scripts/a.py": "x = 2\n"})
        check("a tied code path lands licensed, its suite and scenario reused",
              (word, code) == ("licensed", 0)
              and "stages held: Intent, Plan, Spec, Test, Code" in text,
              f"{word} {code} {text}")

        # S2a_ProseOnlyChange: nothing runs, so the three skippable stages go.
        word, code, text = merge("prose", {"README.md": "bye\n"})
        check("a prose-only change lands licensed",
              (word, code) == ("licensed", 0)
              and "criterion (nothing runs): holds" in text, f"{word} {code} {text}")

        word, code, text = merge("snapshot", {"scripts/b.py": "x = 1\n",
                                             "scripts/b-test.py": "x = 1\n",
                                             "spec/commands.snapshot.json": '{"commands": []}\n'})
        check("a rewritten snapshot holds Spec for the change",
              (word, code) == ("licensed", 0) and "the snapshot" in text,
              f"{word} {code} {text}")

        word, code, text = merge("suite", {"scripts/a-test.py": "# witnesses: S1\nx = 2\n"})
        check("a suite the change wrote holds Code through the path it drives",
              (word, code) == ("licensed", 0)
              and "stages held: Intent, Plan, Spec, Test, Code" in text,
              f"{word} {code} {text}")

        word, code, text = merge("noissue", {"README.md": "bye\n"}, issue="not json at all")
        check("--merge answers unknown: could not parse",
              (word, code) == ("unknown", 2) and "could not parse" in text,
              f"{word} {code} {text}")

        word, code, text = merge("noplan", {"README.md": "bye\n"},
                                issue=sub_issue(body="## Intent\n- i\n"))
        check("a sub-issue with no Plan lands unlicensed",
              (word, code) == ("unlicensed", 1) and "without Plan" in text,
              f"{word} {code} {text}")

        word, code, text = merge("mixed", {"scripts/a.py": "x = 2\n",
                                          "scripts/c.py": "x = 2\n"})
        check("an untied path beside a tied one is named and does not decide",
              (word, code) == ("licensed", 0)
              and "untied code paths it wrote: scripts/c.py" in text,
              f"{word} {code} {text}")

        word, code, text = merge("noclaim", {"README.md": "bye\n"}, branch="feature")
        check("a head branch that is no claim is unknown",
              (word, code) == ("unknown", 2) and "no claim" in text, f"{word} {code}")

        word, code, text = merge("nobefore", {"README.md": "bye\n"}, before="gone")
        check("a before-ref that names no commit is unknown",
              (word, code) == ("unknown", 2) and "names no commit" in text,
              f"{word} {code} {text}")

        # ---- the shared log, from the suite's own env -----------------------
        # COUNTED BEFORE AND AFTER, never read by presence, over a MADE base
        # checkout: `base_root` is the parent of the git common dir, so a
        # `git init` directory is one, and the shared branch of `log_path` runs
        # there without this machine's own log being touched.
        shared = Path(d) / "made-base"
        shared.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(shared)],
                       check=True)
        (shared / "runtime").mkdir()
        shared_log = shared / "runtime" / "jev.log"
        shared_log.write_text('{"a": 1}\n{"a": 2}\n')
        nohome = Path(d) / "nohome"
        nohome.mkdir()

        def shared_lines():
            return len(shared_log.read_text().splitlines())

        fake_gh(bindir, comments=[comment(f"REVIEW rule-check-worker-9: at "
                                          f"{HEAD[:7]}, no findings")])
        before = shared_lines()
        word, code, _text = call(bindir, "274", "--repo", "o/r", cwd=shared)
        check("a plain gate run in this suite's env writes no shared log line",
              shared_lines() == before and (word, code) == ("reviewed", 0),
              (before, shared_lines(), word, code))
        # THE CONTROL, and it is what makes the case above evidence: the same
        # run with neither variable named takes the shared branch and DOES add
        # a line. HOME is an empty directory and the key is unset, so `ask`
        # answers `unknown` before it opens a socket.
        call(bindir, "274", "--repo", "o/r", cwd=shared,
             CAMPAIGN_JEV_LOG=None, CAMPAIGN_JEV_URL=None,
             TYPESAFE_API_KEY=None, HOME=str(nohome))
        check("...and the control proves it is those variables doing it",
              shared_lines() == before + THREAD_READINGS,
              (before, shared_lines(), THREAD_READINGS))

        # ---- the pull request thread, at shadow ----------------------------
        # THE READING RIDES ON THE THREAD THE GATE ALREADY FETCHED, and it
        # moves nothing: same word, same status, nothing printed. Every case
        # here points the reader at a log and an endpoint of its own.
        jevlog = Path(d) / "thread" / "jev.log"
        jevlog.parent.mkdir(exist_ok=True)
        emptyhome = Path(d) / "nohome"
        emptyhome.mkdir(exist_ok=True)
        closed = "http://127.0.0.1:1/v1/systemone"

        def thread_run(*args, **kw):
            """One gate run with the reading pointed at its own log, and the
            rows it wrote. HOME is an empty directory, so the `~/.env` fallback
            finds neither this machine's key nor anybody else's."""
            jevlog.write_text("")
            word, code, text = call(bindir, *args,
                                    CAMPAIGN_JEV_LOG=str(jevlog),
                                    CAMPAIGN_JEV_URL=kw.get("url", closed),
                                    HOME=str(emptyhome),
                                    **{k: v for k, v in kw.items()
                                       if k not in ("url",)})
            rows = [json.loads(ln) for ln in jevlog.read_text().splitlines()
                    if ln.strip()]
            return word, code, text, rows

        review = ("REVIEW rule-check-worker-9: 2 findings at " + HEAD[:7] + "\n\n"
                  "| F1 | the ceiling is stated twice and the copy drifts |\n"
                  "| F2 | the usage line still calls the flag --dry, and the "
                  "code names it --check |\n")
        report = ("REPORT rule-check-worker-8: fix round 1 at " + HEAD[:7] + "\n\n"
                  "| finding | disposition |\n| --- | --- |\n"
                  "| F1 | fixed: the ceiling is a constant now |\n"
                  "| F2 | see the review |\n")
        fake_gh(bindir, comments=[comment(review), comment(report)])
        word, code, text, rows = thread_run("274", "--repo", "o/r")
        check("the thread reading moves neither the word nor the status",
              (word, code) == ("reviewed", 0), f"{word} {code}")
        check("...and prints nothing of its own",
              "Jev" not in text and "shadow" not in text
              and "disposes" not in text, text)
        by = {r.get("reading"): r for r in rows if r.get("reading")}
        check("...and logs one row per reading of the group",
              sorted(by) == ["C-report-disposes-finding",
                             "C-review-not-the-author",
                             "report-addresses-judge", "unverified-done"], rows)
        check("...each carrying the join key as fields, repository beside "
              "every number",
              all(r.get("repo") == "o/r" and r.get("pull_request") == 274
                  for r in by.values()), rows)
        check("...and the id of the two comments the round is made of",
              all(r.get("review_comment") and r.get("report_comment")
                  for r in by.values()), rows)
        # THE PREFILTER COMES FIRST: F1's id sits on a disposition row carrying
        # `fixed`, so code settles it and it is never sent; F2's row names no
        # disposition word, so it is asked.
        settled = by.get("C-report-disposes-finding", {}).get("settled") or {}
        check("the prefilter settles the finding its REPORT disposed of, and "
              "only that one", settled == {"F1": "disposed"}, settled)
        check("...and the state sent holds every finding of the round",
              sorted((by.get("C-report-disposes-finding", {}).get("state")
                      or {}).get("findings") or {}) == ["F1", "F2"], rows)
        # A KEYLESS RUN ANSWERS `unknown` BEFORE ANY SOCKET IS OPENED, which is
        # what CI is: the state is built, the rows land, nothing is asked.
        # A FANNED READING'S `why` IS ONE PER ITEM, so the reason is read out
        # of the dict as readily as out of the string a whole-reading row has.
        said = lambda w: (" ".join(w.values()) if isinstance(w, dict)  # noqa: E731
                          else w) or ""
        # A ROW CODE SETTLED IS EXEMPT FROM THE SECOND HALF: it was never asked,
        # so it has no reason to name a key that was never read. This fixture's
        # REPORT quotes no command, so `unverified-done` is one of those.
        asked_rows = [r for r in by.values() if r.get("settled") != "yes"]
        check("a keyless run asks nothing and says so",
              all(r.get("answered") == "" for r in by.values())
              and len(asked_rows) == len(by) - 1
              and all("TYPESAFE_API_KEY" in said(r.get("why"))
                      for r in asked_rows), rows)
        check("...and costs the gate no timeout",
              all((r.get("latency") or 0) < 1.0 for r in by.values()),
              [r.get("latency") for r in by.values()])

        # ---- 0 new calls a state -------------------------------------------
        # THE CLAIM IS A NUMBER, SO IT IS COUNTED. `unverified-done` and
        # `report-addresses-judge` ride in the call the group already makes, so
        # ONE gate run sends ONE request however many readings the group holds.
        # Measured on this fixture at 1 with the group's two readings and at 1
        # with its four (rule-check#455 pr 5).
        #
        # THE STORE IS CLEARED BEFORE EACH RUN, because a second run over the
        # same state would be answered out of `jev-cache` and send nothing --
        # which would make the control below read as the invariant holding.
        def counted_run(*args, **kw):
            POSTS["count"], POSTS["questions"] = 0, []
            shutil.rmtree(jevlog.parent / "jev-cache", ignore_errors=True)
            jevlog.write_text("")
            return call(bindir, *args, CAMPAIGN_JEV_LOG=str(jevlog),
                        CAMPAIGN_JEV_URL=JEV_COUNTED, HOME=str(emptyhome),
                        TYPESAFE_API_KEY="stub-key", **kw)

        # A REPORT THE LINT LEAVES FOR JEV -- it pins a sha AND quotes a
        # command -- so all four readings ride and the count is over the whole
        # group. `report` itself quotes none and is settled by code below.
        checked = report + "\n`scripts/campaign-jev-test.py` 227 pass 0 fail\n"
        fake_gh(bindir, comments=[comment(review), comment(checked)])
        word, code, _text = counted_run("274", "--repo", "o/r")
        sent = POSTS["questions"][0] if POSTS["questions"] else []
        check("one gate run sends one request whatever the group holds",
              POSTS["count"] == 1 and (word, code) == ("reviewed", 0),
              (POSTS["count"], word, code))
        check("...carrying every reading of the group, the new two included",
              [q for q in sent if not q.startswith("C-report-disposes")]
              == ["C-review-not-the-author", "report-addresses-judge",
                  "unverified-done"], sent)
        # THE CONTROL: a run over a DIFFERENT thread, which the store cannot
        # answer, must move the counter -- otherwise the 1 above is a stub
        # nothing reached rather than an invariant.
        other = checked.replace("fix round 1", "fix round 2")
        fake_gh(bindir, comments=[comment(review), comment(other)])
        counted_run("274", "--repo", "o/r")
        first = POSTS["count"]
        fake_gh(bindir, comments=[comment(review), comment(checked)])
        POSTS["questions"] = []
        call(bindir, "274", "--repo", "o/r", CAMPAIGN_JEV_LOG=str(jevlog),
             CAMPAIGN_JEV_URL=JEV_COUNTED, HOME=str(emptyhome),
             TYPESAFE_API_KEY="stub-key")
        check("...and the control proves the counter counts",
              first == 1 and POSTS["count"] == 2, (first, POSTS["count"]))

        # ---- lint first, in code -------------------------------------------
        # WHAT CODE ANSWERS IS NEVER SENT, so each branch is read twice: the
        # word on the log row, and the question ids the endpoint was actually
        # given. The CONTROL for all three is `checked` above, which pins a sha
        # AND quotes a command and is asked.
        FLAGS = {}

        def linted(body):
            """(the settled word per reading, the question ids posted). The
            rows' `flag` field lands in `FLAGS`, which is where the branch a
            settled row was settled by is read."""
            fake_gh(bindir, comments=[comment(review), comment(body)])
            counted_run("274", "--repo", "o/r")
            rows = [json.loads(ln) for ln in jevlog.read_text().splitlines()
                    if ln.strip()]
            got = {r["reading"]: r.get("settled") for r in rows
                   if r.get("reading")}
            FLAGS.clear()
            FLAGS.update({r["reading"]: r.get("flag") for r in rows
                          if r.get("reading")})
            return got, (POSTS["questions"][0] if POSTS["questions"] else [])

        # THE NO-SHA FIXTURE QUOTES A COMMAND, so only the sha branch can
        # settle it: written without one it is settled by the third branch too
        # and the case passes with the sha branch deleted -- which it did.
        no_sha = checked.replace(" at " + HEAD[:7], "")
        words, asked = linted(no_sha)
        check("a REPORT that pins no sha is code's to answer, not Jev's",
              words.get("unverified-done") == "yes"
              and "unverified-done" not in asked, (words, asked))
        # AND THE ROW SAYS WHICH BRANCH SETTLED IT. A settled row carries the
        # word and an empty `why` -- `judge` writes no reason for an answer it
        # never asked -- so nothing on it said which of the three branches it
        # was (pr#490 REVIEW 5721893225, F4). It rides in `flag`, the field the
        # reader already computes and `judge` already carries.
        check("a lint-settled row names the branch that settled it",
              "pins no sha" in ((FLAGS.get("unverified-done") or {})
                                .get("lint") or ""),
              FLAGS.get("unverified-done"))
        words, asked = linted(report)
        check("a REPORT quoting no command and no reach line is code's too",
              words.get("unverified-done") == "yes"
              and "unverified-done" not in asked, (words, asked))
        # THE CONTROL FOR THE FLAG: a different branch names itself, and the
        # reading the lint did not settle keeps the flag it always had.
        check("...and the other branch names itself on the row",
              "quotes no command" in ((FLAGS.get("unverified-done") or {})
                                      .get("lint") or "")
              and "lint" not in (FLAGS.get("C-report-disposes-finding") or {}),
              (FLAGS.get("unverified-done"),
               FLAGS.get("C-report-disposes-finding")))
        # AND THE ADDRESS IS STILL ASKED on both `yes` branches: the prose it
        # reads is there, and only the empty round settles it.
        check("...and its address noul is still asked, since the prose is there",
              words.get("report-addresses-judge") is None
              and "report-addresses-judge" in asked, (words, asked))
        words, asked = linted(
            report + "\n`reached campaign-base at /x: HEAD 8ca2609 contains "
                     "8ca2609; apply ok`\n")
        check("a REPORT quoting only an install's reach line is asked",
              words.get("unverified-done") is None
              and "unverified-done" in asked, (words, asked))
        words, asked = linted(
            report + "\n`the ceiling is a constant now`\n")
        check("...and a backticked span that is prose is not a command",
              words.get("unverified-done") == "yes"
              and "unverified-done" not in asked, (words, asked))
        # AN UNCLOSED FENCE RUNS TO THE END OF THE TEXT. Before this the span
        # pattern needed a closing fence, so a REPORT whose only command sat in
        # a fence nobody closed matched neither branch and code settled it
        # `yes` -- the command it quoted never reached Jev (pr#490 REVIEW
        # 5721893225, F3).
        words, asked = linted(report + "\n```\npython3 scripts/x-test.py\n")
        check("a command in an unclosed fence is a quoted command",
              words.get("unverified-done") is None
              and "unverified-done" in asked, (words, asked))
        # THE CONTROL: the same block CLOSED still ends where it ends, so the
        # fix did not swallow the text after a fence.
        words, asked = linted(
            report + "\n```\npython3 scripts/x-test.py\n```\n")
        check("...and a closed fence still ends at its closing fence",
              words.get("unverified-done") is None
              and "unverified-done" in asked, (words, asked))
        fake_gh(bindir, comments=[comment(review)])
        counted_run("274", "--repo", "o/r")
        rows = [json.loads(ln) for ln in jevlog.read_text().splitlines()
                if ln.strip()]
        words = {r["reading"]: r.get("settled") for r in rows
                 if r.get("reading")}
        asked = POSTS["questions"][0] if POSTS["questions"] else []
        check("a round with no REPORT settles both new readings `no`",
              words.get("unverified-done") == "no"
              and words.get("report-addresses-judge") == "no", words)
        check("...and asks neither of them",
              not [q for q in asked
                   if q in ("unverified-done", "report-addresses-judge")], asked)

        # A THREAD WITH NO REPORT AFTER ITS REVIEW HAS NO ROUND TO JUDGE, and
        # the reading still logs: a call that asked nothing is a fact about the
        # thread, not a call that went missing.
        fake_gh(bindir, comments=[comment(review)])
        word, code, text, rows = thread_run("274", "--repo", "o/r")
        by = {r.get("reading"): r for r in rows if r.get("reading")}
        check("a REVIEW with no REPORT after it sends no finding",
              (word, code) == ("reviewed", 0)
              and (by.get("C-report-disposes-finding", {}).get("state")
                   or {}).get("findings") == {}, rows)

        # AND A READING THAT CANNOT BE MADE COSTS THE GATE NOTHING. The log is
        # a path that cannot be written, which is every failure of the store
        # and the log at once.
        fake_gh(bindir, comments=[comment(review), comment(report)])
        word, code, _text = call(bindir, "274", "--repo", "o/r",
                                 CAMPAIGN_JEV_LOG=str(Path(d) / "a" / "b" / "c"
                                                      / "jev.log"),
                                 CAMPAIGN_JEV_URL=closed, HOME=str(emptyhome))
        check("a reading that could not be made leaves the gate's word alone",
              (word, code) == ("reviewed", 0), f"{word} {code}")

        # ---- the round is in TIME, not in channel order --------------------
        # `bodies_of` returns every issue comment and THEN every pull-request
        # review, so before this a REVIEW on the review channel sorted after
        # every REPORT however old it was, and `one_round` found a REVIEW with
        # no REPORT after it every time -- findings={} on every such thread.
        rev_body = ("REVIEW rule-check-worker-9: 1 finding at " + HEAD[:7]
                    + "\n\n| F1 | the ceiling is stated twice and the copy "
                      "drifts, which is the one that rots |\n")
        rep_body = ("REPORT rule-check-worker-8: fix round 1 at " + HEAD[:7]
                    + "\n\n| finding | disposition |\n| --- | --- |\n"
                      "| F1 | see the review |\n")
        fake_gh(bindir, comments=[comment(rep_body, "2026-09-18T02:00:00Z")],
                reviews=[pr_review(rev_body, "2026-09-18T01:00:00Z")])
        word, code, text, rows = thread_run("274", "--repo", "o/r")
        by = {r.get("reading"): r for r in rows if r.get("reading")}
        state = (by.get("C-report-disposes-finding", {}).get("state") or {})
        check("a REVIEW on the review channel yields its findings",
              sorted(state.get("findings") or {}) == ["F1"]
              and state.get("report", "").startswith("REPORT "), rows)
        check("...and the gate's word and status do not move",
              (word, code) == ("reviewed", 0), f"{word} {code}")

        # AND THE NEWER REVIEW WINS WHATEVER CHANNEL IT CAME ON. The old one is
        # on the review channel, which used to sort last and so always won.
        old_rev = ("REVIEW rule-check-worker-9: 1 finding at " + OTHER[:7]
                   + "\n\n| F9 | an older round's finding, long since "
                     "disposed of and gone |\n")
        fake_gh(bindir,
                comments=[comment(rev_body, "2026-09-18T03:00:00Z"),
                          comment(rep_body, "2026-09-18T04:00:00Z")],
                reviews=[pr_review(old_rev, "2026-09-18T01:00:00Z")])
        _word, _code, _text, rows = thread_run("274", "--repo", "o/r")
        by = {r.get("reading"): r for r in rows if r.get("reading")}
        state = (by.get("C-report-disposes-finding", {}).get("state") or {})
        check("a newer comment-channel REVIEW outranks an older review-channel "
              "one", sorted(state.get("findings") or {}) == ["F1"], rows)

        # ---- the model's own situation --------------------------------------

        for witness in WITNESSES:
            digest, why = witness_digest(d, witness)
            try:
                head, bodies, owed = instance_fixture(digest) if digest else (None, [], None)
            except LookupError as e:
                head, owed, why = None, None, f"{e}\n{digest}"
            if owed:
                fake_gh(bindir, head=head, comments=[comment(b) for b in bodies])
                word, code, text = call(bindir, "1", "--repo", "o/r")
            check(f"{witness}'s instance gets the word the model gives it",
                  owed is not None and (word, code) == owed,
                  why or f"model {owed}, reader {word} {code}; {len(bodies)} REVIEW(s)\n{digest}")

    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
