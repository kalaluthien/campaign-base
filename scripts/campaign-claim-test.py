#!/usr/bin/env python3
"""Prove campaign-claim reads a claim off the remote and a checkout, and refuses
to conclude from a reading that did not happen.

The claim is the branch since #176, so what is covered is the join: which refs
exist, where each is checked out, and which of the three groups a row lands in.
The `take` create-ref and the `release` ref delete reach GitHub, so they are
covered through a shimmed `gh` -- the refusals around them are what decide
whether somebody's branch is deleted, and those are pure.

The worktree half runs REAL git against temporary repositories rather than a
parser fixture: `git worktree list --porcelain` is the thing whose output shape
this depends on, and a recorded copy of it would stop being evidence the day git
changes it. Nothing here reaches the network.

Usage: scripts/campaign-claim-test.py
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CLAIM = Path(__file__).resolve().parent / "campaign-claim.py"

RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{(' -- ' + detail) if detail else ''}")


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True, check=True)


def a_repo(root, *branches):
    """A repository with a commit, plus one linked worktree per named branch.
    Returns (repo_path, {branch: worktree path})."""
    repo = Path(root).resolve() / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    (repo / "f").write_text("x")
    git(repo, "add", "f")
    git(repo, "commit", "-qm", "c")
    trees = {}
    for i, b in enumerate(branches):
        w = Path(root).resolve() / f"w{i}"
        git(repo, "worktree", "add", "-q", "-b", b, str(w))
        trees[b] = str(w)
    return repo, trees


# --------------------------------------------------------------- the fixtures

def agent(sid, name, cwd, pane="w1:p1", status="idle"):
    return {"agent_session": {"value": sid}, "name": name, "cwd": cwd,
            "pane_id": pane, "agent_status": status}


def listing(*agents):
    return json.dumps({"result": {"agents": list(agents)}})


GH = """#!/bin/sh
# Every endpoint this suite needs, and a refusal for anything else, so a call
# that escaped a gate is visible as a different failure rather than as silence.
case "$*" in
  # IS IT SETTLED. Matched before the body arms and on `--json state`, or the
  # body answer would come back as a state word and every sub-issue would read
  # open -- which is how these arms first passed while answering the wrong
  # question.
  *"--json state"*"issue view 2 "*|*"issue view 2 "*"--json state"*) echo 'CLOSED completed'; exit 0 ;;
  *"--json state"*"issue view 600 "*|*"issue view 600 "*"--json state"*) echo 'CLOSED not_planned'; exit 0 ;;
  *"--json state"*"issue view 601 "*|*"issue view 601 "*"--json state"*) exit 1 ;;
  *"--json state"*) echo 'OPEN '; exit 0 ;;
  # WHOSE SUB-ISSUE IT IS (#206). Matched before the body arms for the reason
  # the state arms are: a parent read answered with a body comes back as prose
  # and reads as a parent that disagrees. 700 hangs from another campaign, 701
  # from the campaign these cases name, 702 will not read, 703 hangs from
  # nothing, and every other issue is parented to the campaign these cases
  # name -- the ordinary answer, so the cases written before #206 go on
  # exercising what they were written for rather than this reading. The other
  # shims in this file answer 9999 for the same reason: a fixture that read as
  # unparented made a mutation refusing that branch kill the suite mid-way,
  # where it should fail one named case.
  *"--json parent"*"issue view 700 "*|*"issue view 700 "*"--json parent"*) echo '1234'; exit 0 ;;
  *"--json parent"*"issue view 701 "*|*"issue view 701 "*"--json parent"*) echo '9999'; exit 0 ;;
  *"--json parent"*"issue view 702 "*|*"issue view 702 "*"--json parent"*) exit 1 ;;
  *"--json parent"*"issue view 703 "*|*"issue view 703 "*"--json parent"*) echo ''; exit 0 ;;
  # The two sub-issues of campaign 8888, whose `## Repos` will not read.
  *"--json parent"*"issue view 51"*|*"issue view 51"*"--json parent"*) echo '8888'; exit 0 ;;
  *"--json parent"*) echo '9999'; exit 0 ;;
  # WHERE A CLAIM IS CUT, read from the sub-issue since #187. `none` is the
  # ordinary answer here: these cases claim on the base, which is what a
  # repo-less sub-issue resolves to.
  # The CAMPAIGN issue's body, whose `## Repos` is the campaign's scope. A
  # sub-issue may only name a repository this list holds.
  *"issue view 9999 "*) printf '## Repos\n- other/elsewhere\n'; exit 0 ;;
  *"issue view 8888 "*) printf 'no Repos heading at all\n'; exit 0 ;;
  *"issue view 404 "*) echo 'no Repository line here'; exit 0 ;;
  *"issue view 502 "*) echo 'Repository: outside/scope'; exit 0 ;;
  *"issue view 500 "*) echo 'Repository: other/elsewhere'; exit 0 ;;
  # THE BASE SPELLED OUT, which `none` above cannot stand in for: `## Repos`
  # never holds the base, so this is the one line whose two readings differ.
  *"issue view 503 "*) echo 'Repository: kalaluthien/campaign-base'; exit 0 ;;
  # #205: THE SPELLINGS PROSE ARRIVES IN. Each names a repository the campaign
  # already holds, so anything but a clean claim is the raw comparison talking.
  *"issue view 504 "*) echo 'Repository: `other/elsewhere`'; exit 0 ;;
  *"issue view 505 "*) echo 'Repository: kalaluthien/campaign-base.git'; exit 0 ;;
  *"issue view 506 "*) echo 'Repository: Other/Elsewhere'; exit 0 ;;
  # ...and the one that names no repository: the template's own placeholder.
  *"issue view 507 "*) echo 'Repository: <owner/repo>'; exit 0 ;;
  # 512 and 513 are 502 and 503 again, as sub-issues of campaign 8888: the
  # scope cases take under 8888, and since #206 a sub-issue must hang from the
  # campaign it is claimed under.
  *"issue view 512 "*) echo 'Repository: outside/scope'; exit 0 ;;
  *"issue view 513 "*) echo 'Repository: kalaluthien/campaign-base'; exit 0 ;;
  *"issue view 501 "*) exit 1 ;;
  *"issue view"*) echo 'Repository: none'; exit 0 ;;
  *matching-refs*) echo '["refs/heads/campaign-9999/1-alpha","refs/heads/campaign-9999/2-beta"]'; exit 0 ;;
  *compare/main*) echo 0; exit 0 ;;
  # `2-beta` landed; `1-alpha` never did. The two answers are what `live`'s
  # vacant group and `release`'s fresh-claim gate each turn on.
  *"--head campaign-9999/2-beta"*) echo '[{"number": 162}]'; exit 0 ;;
  *"pr list"*|*--state*merged*) echo '[]'; exit 0 ;;
  *"issues/9999"*|*"issues/8888"*) echo '["campaign","bound:'"$(hostname -s)"'"]'; exit 0 ;;
  *commits/main*) echo 1111111111111111111111111111111111111111; exit 0 ;;
  *git/refs*) echo 'Reference already exists' >&2; exit 1 ;;
esac
echo "gh shim: refusing $*" >&2
exit 1
"""

GH_ELSEWHERE = GH.replace('"$(hostname -s)"', '"not-this-machine"')

# TWO SUBCOMMANDS, because #198 made `release` DRIVE a pane as well as read
# one, and a shim that answers everything with the listing would let a
# `/compact` that never went anywhere pass as sent. `agent prompt` writes one
# line per call to `<shims>/../herdr-calls.log`, so a case can assert the
# count, the pane and that HERDR_ENV was set -- and anything else refuses, so a
# call this suite did not anticipate shows up as its own failure.
HERDR = """#!/bin/sh
# THE LOG PATH IS BAKED IN, not derived from $0: PATH lookup makes $0 the
# bare word `herdr`, so `dirname $0` is `.` and the log lands in whatever
# directory the case happened to run from. The case that asserts one prompt
# was sent is what caught that; a case asserting only the exit status would
# not have.
log="%s"
case "$1 $2" in
  "agent list")
    cat <<'JSON'
%s
JSON
    exit 0 ;;
  "agent prompt")
    printf 'HERDR_ENV=%%s pane=%%s prompt=%%s\n' "${HERDR_ENV:-unset}" "$3" "$4" >> "$log"
    exit %s ;;
esac
echo "herdr shim: refusing $*" >&2
exit 1
"""


def prompts(path_dir):
    """Every `herdr agent prompt` the shim on this PATH was asked to make, in
    order. An absent log is NO calls, which is a different answer from one call
    that went to the wrong pane -- and both are asserted."""
    log = Path(path_dir).parent / "herdr-calls.log"   # <shims dir>/../
    if not log.exists():
        return []
    return [ln for ln in log.read_text().splitlines() if ln.strip()]


def shims(d, gh=GH, herdr=None, prompt_exit=0):
    """A PATH directory holding the shims. `gh` is ALWAYS shimmed: the real one
    reaches the network, and a case that did so has written to production behind
    a green line of output."""
    b = Path(d) / "bin"
    b.mkdir(parents=True, exist_ok=True)
    (b / "gh").write_text(gh)
    (b / "gh").chmod(0o755)
    if herdr is not None:
        (b / "herdr").write_text(
            HERDR % (str(Path(d) / "herdr-calls.log"), herdr, prompt_exit))
        (b / "herdr").chmod(0o755)
    # Everything else a case legitimately runs, linked in, because PATH is this
    # directory ALONE: with the real PATH behind it, "herdr is not installed"
    # would silently run the real herdr and prove nothing.
    for tool in ("git", "hostname", "sh", "cat", "printf", "uname"):
        found = shutil.which(tool)
        if found and not (b / tool).exists():
            (b / tool).symlink_to(found)
    return b


def claim(args, path_dir, extra_env=None):
    # HERDR_ENV IS SCRUBBED unless a case names it. This suite is itself run
    # from inside a herdr pane, where HERDR_ENV=1 is already in the
    # environment -- so a case asserting the script set it passed while the
    # script set nothing, and deleting the guard from `campaign-claim.py` left
    # the suite green. Measured 2026-09-05 by that deletion.
    env = dict(os.environ, PATH=str(path_dir))
    env.pop("HERDR_ENV", None)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(CLAIM), *args],
                          capture_output=True, text=True, env=env)


# ----------------------------------------------------------------- the cases

def pure_cases(m):
    # --- which sub-issue a branch names ---
    check("a claim branch names its sub-issue",
          m.issue_of_branch("campaign-1/176-github-facts", "1") == "176")
    check("...and a branch of another campaign names none here",
          m.issue_of_branch("campaign-2/176-x", "1") is None)
    # The one that would silently mis-attribute: `17` must not answer for `176`.
    check("a shorter number is not a prefix match",
          m.issue_of_branch("campaign-1/176-x", "1") == "176"
          and m.refs_for_issue(["campaign-1/176-x"], "1", "17") == [])
    check("a second segment with no number claims no sub-issue",
          m.issue_of_branch("campaign-1/topic-only", "1") is None)
    check("a branch outside the campaign prefix is not ours",
          m.issue_of_branch("main", "1") is None)

    refs, why = m.parse_refs('["refs/heads/campaign-1/7-a","refs/tags/v1"]')
    check("a tag in the ref listing is not a claim branch",
          refs == ["campaign-1/7-a"] and why is None)
    refs, why = m.parse_refs("not json")
    check("a ref listing that did not parse is a why, not zero claims",
          refs is None and why)

    # --- which ref a release is about ---
    b, refusal = m.which_branch(["campaign-1/7-a"], "1", "7", None)
    check("one matching ref answers the release", b == "campaign-1/7-a" and not refusal)
    b, refusal = m.which_branch([], "1", "7", None)
    check("no matching ref is a refusal naming --branch",
          b is None and refusal and "--branch" in refusal)
    b, refusal = m.which_branch(["campaign-1/7-a", "campaign-1/7-b"], "1", "7", None)
    check("TWO refs on one sub-issue are refused, never picked between",
          b is None and refusal and "7-a" in refusal and "7-b" in refusal)
    b, refusal = m.which_branch(["campaign-1/7-a", "campaign-1/7-b"], "1", "7",
                                "campaign-1/7-b")
    check("...and --branch names one directly, past the refusal",
          b == "campaign-1/7-b" and not refusal)

    # --- the binding gate ---
    check("only `here` admits a ref cut", m.binding_verdict("here") is None)
    for word in ("elsewhere", "unbound", "exit 2: gh: not found", ""):
        check(f"the binding refuses on {word!r}", bool(m.binding_verdict(word)))

    # --- the herdr half ---
    rows, why = m.parse_agents(listing(agent("s1", "campaign-1-worker-1", "/x")))
    check("a herdr row is read by its session id",
          why is None and rows["s1"]["name"] == "campaign-1-worker-1")
    rows, why = m.parse_agents(listing({"name": "n", "cwd": "/x", "pane_id": "p"}))
    check("a row herdr cannot identify is counted, never dropped",
          why is None and len(rows) == 1
          and list(rows)[0].startswith("<unidentified:"))
    rows, why = m.parse_agents("{}")
    check("herdr output of an unknown shape is a why, not zero sessions",
          rows is None and why)

    # --- the worktree half, as a parse ---
    where = m.parse_worktrees(
        "worktree /a\nHEAD aaa\nbranch refs/heads/campaign-1/7-a\n\n"
        "worktree /b\nHEAD bbb\ndetached\n\n"
        "worktree /c\nHEAD ccc\nbranch refs/heads/main\n")
    check("a worktree's branch is read off its own paragraph",
          where.get("campaign-1/7-a") == ["/a"])
    check("a DETACHED worktree holds no branch and is not an unread reading",
          "/b" not in sum(where.values(), []))
    check("...and the paragraph after it is still read",
          where.get("main") == ["/c"])

    # --- the join ---
    stood = {"campaign-1/7-a": ["/w/7"]}
    sessions = {
        "s1": {"name": "campaign-1-worker-1", "cwd": "/x", "pane": "p1",
               "status": "working"},
        "s2": {"name": "campaign-2-worker-1", "cwd": "/y", "pane": "p2",
               "status": "idle"},
    }
    occupied, vacant, ours = m.classify(
        ["campaign-1/7-a", "campaign-1/8-b"], stood, sessions, "1")
    check("a claim with a checkout is occupied",
          occupied == [("campaign-1/7-a", ["/w/7"])])
    check("a claim with no checkout is vacant",
          vacant == [("campaign-1/8-b", [])])
    check("only sessions of THIS campaign are listed",
          [n for _, r in ours for n in [r["name"]]] == ["campaign-1-worker-1"])
    # A campaign whose number is a prefix of another's must not collect it.
    check("campaign 1 does not collect campaign 11's sessions",
          not m.classify([], {}, {"s": {"name": "campaign-11-worker-1"}},
                         "1")[2])

    check("occupants names every workspace holding the branch",
          m.occupants({"b": ["/w1", "/w2"]}, "b") == ["/w1", "/w2"])
    check("...and none for a branch nothing holds",
          m.occupants({"b": ["/w1"]}, "other") == [])

    # --- the comparison, and the 404 that is not an absence ---
    check("a comparison that did not happen is not an empty branch",
          m.ahead_count(1, "") is None
          and not m.ahead_verdict(None, "", "boom", "o/r", "b")[0])
    check("a branch ahead of main is refused with its count",
          not m.ahead_verdict(3, "3", "", "o/r", "b")[0]
          and "3 commit(s)" in m.ahead_verdict(3, "3", "", "o/r", "b")[1])
    check("a branch holding nothing beyond main is admitted",
          m.ahead_verdict(0, "0", "", "o/r", "b")[0])
    check("only a 404 reads as a gone ref", m.ref_gone(1, "HTTP 404")
          and not m.ref_gone(1, "HTTP 500") and not m.ref_gone(0, ""))
    check("the ref's own endpoint separates gone from unanswered",
          m.ref_probe(0, "") == "present" and m.ref_probe(1, "HTTP 404") == "gone"
          and m.ref_probe(1, "HTTP 500") == "unanswered")
    ok, text = m.merged_head_verdict(0, "[]", "o/r", "b")
    check("a vanished branch with no merged pull request is reported",
          not ok and "never released" in text)
    ok, text = m.merged_head_verdict(0, '[{"number": 9}]', "o/r", "b")
    check("...and one with a merged pull request is nothing beyond main",
          ok and "#9" in text)
    ok, text = m.merged_head_verdict(1, "", "o/r", "b")
    check("a pull request question that failed is not an absence", not ok)


def git_cases(m):
    """The half that runs real git, so what is proved is git's own shape."""
    with tempfile.TemporaryDirectory() as d:
        repo, trees = a_repo(d, "campaign-9999/1-alpha")
        where, unread = m.checkouts([str(repo)])
        check("a real linked worktree is found on its branch",
              not unread and where.get("campaign-9999/1-alpha")
              == [trees["campaign-9999/1-alpha"]])
        check("...and the main worktree's own branch is found beside it",
              where.get("main") == [str(repo)])

        # A root that is not a repository is NAMED, never skipped: a repository
        # that could not be swept is not an empty one.
        where, unread = m.checkouts([str(repo), str(Path(d) / "nothing")])
        check("a root git will not answer for is reported as unread",
              len(unread) == 1 and "nothing" in unread[0]
              and where.get("campaign-9999/1-alpha"))

        root, why = m.repo_root(trees["campaign-9999/1-alpha"])
        check("a linked worktree resolves to the repository that owns it",
              why is None and root == str(repo))
        root, why = m.repo_root(str(Path(d) / "nothing"))
        check("a directory in no repository is not a failure, just no root",
              root is None and why is None)


def live_cases(m):
    """`live` end to end: a fixture remote, a fixture herdr listing, real git.

    Campaign 9999 is used so the fixture branches cannot collide with anything
    actually checked out on the machine the suite runs on -- the group each row
    lands in is then a property of the fixture and not of the day."""
    with tempfile.TemporaryDirectory() as d:
        path = shims(d, herdr=listing(
            agent("s1", "campaign-9999-worker-1", d),
            agent("s2", "campaign-1-planner-9", d)))
        r = claim(["live", "9999"], path)
        out = r.stdout + r.stderr
        # A VACANT REF WHOSE WORK LANDED BLOCKS NOTHING, and saying so is what
        # makes the group actionable: this tracker leaves merged branches
        # standing, so a close told to refuse on the whole group can never pass.
        check("a vacant claim whose pull request merged is marked landed",
              "campaign-9999/2-beta" in out and "landed as #162" in out)
        check("...and one that never merged is marked so",
              "campaign-9999/1-alpha" in out and "never merged" in out)
        check("live names all three readings before any count",
              "reading 1" in out and "reading 2" in out and "reading 3" in out)
        check("...and reads the campaign's refs off the remote",
              "2 claim(s)" in out)
        check("a claim nothing has checked out is in the vacant group",
              "campaign-9999/1-alpha" in out
              and "claims checked out nowhere on this machine (2)" in out)
        check("a live session of this campaign is listed",
              "campaign-9999-worker-1" in out)
        check("...and a session of another campaign is not",
              "campaign-1-planner-9" not in out)
        check("live reaches no verdict", "No verdict" in out and r.returncode == 0)

        # A reading that did not happen must deny every count below it.
        broken = shims(Path(d) / "broken", gh="#!/bin/sh\nexit 1\n",
                       herdr=listing(agent("s1", "campaign-9999-worker-1", d)))
        r = claim(["live", "9999"], broken)
        out = r.stdout + r.stderr
        check("a failed ref listing denies the counts and exits 1",
              r.returncode == 1 and "FAILED" in out
              and "did not happen" in out
              and "claims checked out nowhere" not in out)

        # herdr absent is the same shape from the other side.
        no_herdr = shims(Path(d) / "noherdr")
        r = claim(["live", "9999"], no_herdr)
        check("herdr that cannot be run is a failed reading, not zero sessions",
              r.returncode == 1 and "FAILED" in r.stdout + r.stderr)


def take_cases(m):
    with tempfile.TemporaryDirectory() as d:
        path = shims(d)
        r = claim(["take", "9999", "1", "alpha"], path)
        out = r.stdout + r.stderr
        check("take on an existing ref exits 3, which is the claim working",
              r.returncode == 3 and "already claimed" in out)
        check("...and it says to read who is standing in it",
              "live 9999" in out)

        # THE SUB-ISSUE IS WHAT IS CLAIMED, not the topic. create-ref alone
        # admits this, because `1-gamma` is a name no ref has; the sweep before
        # it is what refuses. Asserted on the sentence only this branch prints,
        # since the create-ref refusal exits 3 too and would satisfy a weaker
        # case without the sweep existing at all.
        r = claim(["take", "9999", "1", "gamma"], path)
        out = r.stdout + r.stderr
        check("a second TOPIC on a claimed sub-issue is refused",
              r.returncode == 3
              and "one claim whatever the topic" in out)
        check("...and it names the ref that already holds the sub-issue",
              "campaign-9999/1-alpha" in out)

        # ...and the sweep does not refuse a sub-issue nobody has claimed: it
        # gets as far as the create, which the shim answers "already exists".
        r = claim(["take", "9999", "7", "delta"], path)
        out = r.stdout + r.stderr
        check("an unclaimed sub-issue reaches the create-ref",
              "cut from" in out and "one claim whatever the topic" not in out)

        # ------ #187 Q1: WHERE IS A FACT ABOUT THE SUB-ISSUE ------
        # Three refusals, broken apart, because they share exit 1 and a stream.
        # A case asserting only the status passes while any one is deleted.

        # "I could not look" is not "there is nothing there". These two are the
        # pair the guard rules say must never collapse into one another.
        r = claim(["take", "9999", "501", "x"], path)
        out = r.stdout + r.stderr
        check("a sub-issue body that could not be fetched refuses",
              r.returncode == 1 and "could not read #501" in out,
              f"exit {r.returncode}: {out[:200]}")
        r = claim(["take", "9999", "404", "x"], path)
        out = r.stdout + r.stderr
        check("...and a body with no Repository line refuses differently",
              r.returncode == 1 and "no `Repository:` line" in out,
              f"exit {r.returncode}: {out[:200]}")
        check("...naming the template the line comes from",
              "sub-issue.md" in out, out[:300])
        # THE DEFECT ITSELF. `--repo` deciding is what let two takers each hold
        # #N; it may now only agree. Refused rather than resolved: whichever
        # side won silently, one of the two readers would be wrong for good.
        r = claim(["take", "9999", "500", "x", "--repo", "someone/other"], path)
        out = r.stdout + r.stderr
        check("--repo disagreeing with the sub-issue is refused",
              r.returncode == 1 and "The sub-issue decides" in out,
              f"exit {r.returncode}: {out[:200]}")
        check("...and the refusal names both repositories it read",
              "someone/other" in out and "other/elsewhere" in out, out[:300])
        # A REPOSITORY OUTSIDE THE CAMPAIGN'S SCOPE. `Repository:` is prose on
        # one sub-issue; `## Repos` is what a person signed up for, so a
        # sub-issue naming a repository outside it is a scope change filed as a
        # typo. Cutting the ref would make the campaign wider than its charter.
        r = claim(["take", "9999", "502", "x"], path)
        out = r.stdout + r.stderr
        check("a sub-issue naming a repository outside `## Repos` is refused",
              r.returncode == 1 and "belongs in the campaign issue" in out,
              f"exit {r.returncode}: {out[:200]}")
        check("...and names the repository it read and the list it read",
              "outside/scope" in out and "other/elsewhere" in out, out[:300])
        # ...and a scope that could not be READ is not a scope that admits it.
        # Separate from the case above: both exit 1, and only this sentence
        # tells "I looked and it is not there" from "I could not look".
        r = claim(["take", "8888", "512", "x"], path)
        out = r.stdout + r.stderr
        # ASSERTED ON THE SCOPE SENTENCE, not on "could not be read": the
        # BINDING refusal prints that phrase too, so the first shape of this
        # case passed while the campaign body was never fetched at all.
        check("a `## Repos` list that would not read denies the claim",
              r.returncode == 1 and "did not read" in out
              and "not a scope that admits it" in out,
              f"exit {r.returncode}: {out[:250]}")
        # ...and the scope check ADMITS a sub-issue the list holds, or it is a
        # rule that refuses everything.
        r = claim(["take", "9999", "500", "x"], path)
        out = r.stdout + r.stderr
        check("a sub-issue naming a listed repository passes the scope check",
              "which includes other/elsewhere" in out, out[:300])

        # ...and the rule admits the ordinary claim, or it forbids everything.
        # `none` is the repo-less answer and means the base.
        r = claim(["take", "9999", "7", "delta"], path)
        out = r.stdout + r.stderr
        check("a sub-issue naming no member repository cuts on the base",
              "names no member repository" in out and "cut from" in out,
              out[:300])
        # ------ #203: THE BASE SPELLED OUT IS NOT OUT OF SCOPE ------
        # The case the #187 scope check shipped without, and the one value for
        # which the two readings differ: `Repository: <the base>`. `## Repos`
        # lists the MEMBER repositories a campaign clones, so it never holds
        # the base, and reading only the literal `none` as "the base" refused
        # every sub-issue of every campaign whose work lands here. Campaign
        # 9999's list is `other/elsewhere`, so the base is genuinely absent
        # from it -- a fixture listing the base would answer this in place of
        # the code. `R14d_ScopeAdmitsTheBaseWhateverTheListHolds` is the model.
        r = claim(["take", "9999", "503", "epsilon"], path)
        out = r.stdout + r.stderr
        check("a sub-issue naming the base by name cuts its ref",
              "which every campaign is for" in out and "cut from" in out,
              out[:300])
        # ASSERTED ON THE REFUSAL'S ABSENCE TOO, because that is what the
        # defect emitted: reverting the exemption brings this sentence back
        # while the run still exits non-zero for its own reasons.
        check("...and the scope refusal is not what it printed",
              "belongs in the campaign issue" not in out, out[:300])
        # ...and the exemption is decided BEFORE the list is read, not by the
        # list happening to admit it: campaign 8888's body has no `## Repos`
        # heading at all, which denies a claim naming a member repository.
        r = claim(["take", "8888", "513", "zeta"], path)
        out = r.stdout + r.stderr
        check("a base sub-issue is claimable though the campaign's list will not read",
              "cut from" in out and "not a scope that admits it" not in out,
              out[:300])

        # ------ #205: A SLUG IS NORMALIZED THROUGH ONE READER ------
        # Every one of these named a repository campaign 9999 already holds,
        # and every one of them used to come back as the SCOPE refusal -- which
        # says "this campaign is not for that repository" when the truth is
        # "that line was not read as a slug". Asserted on the absence of that
        # sentence as well as on the claim, because the refusal is the defect.
        for issue, spelling in (("504", "backticked"), ("506", "in another case")):
            r = claim(["take", "9999", issue, "x"], path)
            out = r.stdout + r.stderr
            check(f"a `Repository:` line {spelling} names the same repository",
                  "cut from" in out and "belongs in the campaign issue" not in out,
                  out[:300])
        # ...and when the text was CHANGED to read it, the note says so. Only
        # for a spelling that differs from the slug: a line differing by case
        # alone is left as the person wrote it, since `slug` folds nothing.
        r = claim(["take", "9999", "504", "y"], path)
        check("...and a de-wrapped line says what it was read from",
              "read from" in r.stdout + r.stderr, (r.stdout + r.stderr)[:300])
        # The base with a `.git` on it is still the base, so it never reaches
        # the list at all.
        r = claim(["take", "9999", "505", "x"], path)
        out = r.stdout + r.stderr
        check("the base with a `.git` suffix is still the base",
              "which every campaign is for" in out and "cut from" in out,
              out[:300])
        # ...AND A LINE THAT NAMES NO REPOSITORY IS ITS OWN DIAGNOSIS. The
        # template's `<owner/repo>` placeholder is an absent answer; reading
        # angle brackets as a wrapper would cut a ref for a repository
        # literally named `owner/repo`.
        r = claim(["take", "9999", "507", "x"], path)
        out = r.stdout + r.stderr
        check("an unfilled `Repository:` placeholder is refused by its own name",
              r.returncode == 1 and "is not an owner/repo" in out
              and "nothing was compared" in out, f"exit {r.returncode}: {out[:300]}")
        check("...and it is not the scope refusal",
              "belongs in the campaign issue" not in out, out[:300])

        # ------ #206: WHOSE SUB-ISSUE IT IS, READ AND NOT TYPED ------
        # A mistyped campaign number cut a real ref under a campaign the
        # sub-issue does not belong to, and nobody could see it: `live` and
        # `release` list by the `campaign-<N>/` prefix. Three outcomes, three
        # cases, because a parent that could not be read is not a parent that
        # disagrees.
        r = claim(["take", "9999", "700", "x"], path)
        out = r.stdout + r.stderr
        check("a sub-issue of another campaign is refused",
              r.returncode == 1 and "#700 is a sub-issue of #1234, not #9999"
              in out, f"exit {r.returncode}: {out[:300]}")
        check("...and the refusal says where the ref would have been invisible",
              "invisible to the campaign that owns #700" in out, out[:400])
        # ALLOW beside it: the same reading, agreeing.
        r = claim(["take", "9999", "701", "x"], path)
        out = r.stdout + r.stderr
        check("ALLOW beside it: a sub-issue of the campaign named is claimed",
              "#701 is a sub-issue of #9999, the campaign named" in out
              and "cut from" in out, out[:300])
        # ALLOW, printed apart: could not look.
        r = claim(["take", "9999", "702", "x"], path)
        out = r.stdout + r.stderr
        check("a parent that could not be read does not refuse the claim",
              "cut from" in out and "could not be checked" in out, out[:400])
        check("...and it does not print as a parent that disagrees",
              "not #9999" not in out, out[:400])
        # ALLOW, printed apart again: an issue nobody linked. #213 is one,
        # because #1 sits at GitHub's 100-sub-issue cap -- refusing here would
        # refuse the repair of exactly the situation the cap creates.
        r = claim(["take", "9999", "703", "eta"], path)
        out = r.stdout + r.stderr
        check("an unparented sub-issue is claimed, and the note says so",
              "cut from" in out and "sub-issue of no campaign issue" in out
              and "is admitted" in out, out[:400])

        # ------ #187 Q3: A SETTLED SUB-ISSUE'S REF IS RESIDUE ------
        # `delete_branch_on_merge` is off on this tracker, so a merged branch's
        # ref stands until somebody deletes it. Read as a live claim, it made a
        # sub-issue that had ever been settled un-re-workable for ever.
        # Sub-issue 2 is closed-completed and `2-beta` merged as #162.
        r = claim(["take", "9999", "2", "again"], path)
        out = r.stdout + r.stderr
        # ASSERTED ON THE REASON, not on exit 3: the OLD behaviour also refused
        # this, saying "already claimed", so a case keyed on the status passes
        # against the very defect it is here to pin.
        check("a settled sub-issue is refused for BEING settled",
              "is settled and its work is over" in out
              and "already claimed" not in out,
              f"exit {r.returncode}: {out[:250]}")
        check("...and its merged ref is named residue, not a claim",
              "residue of settled work" in out and "#162" in out, out[:300])
        check("...and it says reopening is a person's call",
              "gh issue reopen 2" in out, out[:300])
        # Closed as NOT PLANNED is settled too, or a dropped sub-issue would
        # stay claimable while a completed one did not.
        r = claim(["take", "9999", "600", "x"], path)
        out = r.stdout + r.stderr
        check("a sub-issue dropped as not planned is settled as well",
              r.returncode == 1 and "is settled" in out and "not_planned" in out,
              f"exit {r.returncode}: {out[:250]}")
        # "I could not look" is not "it is open".
        r = claim(["take", "9999", "601", "x"], path)
        out = r.stdout + r.stderr
        check("a state that could not be read denies the claim",
              r.returncode == 1 and "not a sub-issue known to be open" in out,
              f"exit {r.returncode}: {out[:250]}")

        # ...and a merge question that could not be ANSWERED is neither. Its
        # own shim, because the answer has to fail for one branch while the ref
        # listing still succeeds, and widening the shared shim's ref list would
        # move every count the `live` cases assert.
        unread_gh = shims(Path(d) / "unread", gh="""#!/bin/sh
case "$*" in
  *"--json state"*) echo 'OPEN '; exit 0 ;;
  *"--json parent"*) echo '9999'; exit 0 ;;
  *"issue view"*) echo 'Repository: none'; exit 0 ;;
  *matching-refs*) echo '["refs/heads/campaign-9999/3-gamma"]'; exit 0 ;;
  *"issues/9999"*) echo '["campaign","bound:'"$(hostname -s)"'"]'; exit 0 ;;
  *"pr list"*) echo "the merge question failed" >&2; exit 1 ;;
esac
exit 1
""")
        r = claim(["take", "9999", "3", "delta"], unread_gh)
        out = r.stdout + r.stderr
        check("a merge question that could not be answered denies the claim",
              r.returncode == 1 and "whether it is a live claim or" in out,
              f"exit {r.returncode}: {out[:250]}")
        check("...and names the ref it could not settle",
              "campaign-9999/3-gamma" in out, out[:300])

        # ------ FINDING 1: REOPEN-THEN-TAKE, THE ONLY PATH Q3 DELIVERS ON ---
        # A settled sub-issue is refused while it is closed, so re-working one
        # means reopening it. Then its merged ref is still on the remote, and
        # the survey walks past it correctly -- but the RE-CHECK counted the
        # same residue as a rival, deleted the ref just cut, and reported a race
        # against a branch merged weeks ago. Its own shim: sub-issue 8 is OPEN
        # and `8-old` merged as #162, which no other fixture here has.
        reopened = shims(Path(d) / "reopened", gh="""#!/bin/sh
case "$*" in
  *"--json state"*) echo 'OPEN '; exit 0 ;;
  *"--json parent"*) echo '9999'; exit 0 ;;
  *"issue view"*) echo 'Repository: none'; exit 0 ;;
  # Stateful, or the survey sees the ref this run is about to cut and refuses
  # before the re-check -- the branch under test -- is ever reached.
  *matching-refs*)
      if [ -f REOPENDIR/n ]; then
        echo '["refs/heads/campaign-9999/8-old","refs/heads/campaign-9999/8-new"]'
      else
        : > REOPENDIR/n; echo '["refs/heads/campaign-9999/8-old"]'
      fi
      exit 0 ;;
  *"issues/9999"*) echo '["campaign","bound:'"$(hostname -s)"'"]'; exit 0 ;;
  *commits/main*) echo 1111111111111111111111111111111111111111; exit 0 ;;
  *"--head campaign-9999/8-old"*) echo '[{"number": 162}]'; exit 0 ;;
  *"pr list"*) echo '[]'; exit 0 ;;
  *"-X DELETE"*) echo "$*" >> REOPENDIR/deleted; exit 0 ;;
  *git/refs*) exit 0 ;;
esac
exit 1
""".replace("REOPENDIR", str(Path(d) / "reopened")))
        r = claim(["take", "9999", "8", "new"], reopened)
        out = r.stdout + r.stderr
        # ASSERTED ON THE DELETE, not on the exit status: the defect exited 3
        # and printed "in the same moment", which a status-keyed case accepts.
        deleted = Path(d) / "reopened" / "deleted"
        check("a reopened sub-issue's take does NOT delete the ref it just cut",
              not deleted.exists(),
              deleted.read_text() if deleted.exists() else "")
        check("...and it claims the sub-issue",
              r.returncode == 0 and "claimed campaign-9999/8-new" in out,
              f"exit {r.returncode}: {out[:250]}")
        check("...naming the merged ref as residue rather than as a rival",
              "not a rival" in out and "#162" in out, out[:300])

        # THE RACE THE SURVEY ALONE CANNOT CLOSE. Two takers on two topics both
        # see no sibling and both create; the re-check AFTER the create is what
        # settles it, because by then both refs exist. The shim answers empty
        # first and two-refs after, which is exactly that interleaving.
        raced = shims(Path(d) / "raced", gh="""#!/bin/sh
STATE=RACEDIR/n
case "$*" in
  *"--json parent"*) echo '9999'; exit 0 ;;
  *"issue view"*) echo 'Repository: none'; exit 0 ;;
  *"issues/9999"*) echo '["bound:'"$(hostname -s)"'"]'; exit 0 ;;
  # Neither racing ref ever merged, so both are live claims and the yield is
  # what settles them. Without this arm the merge question comes back unread
  # and the re-check refuses instead, which is a different branch.
  *"pr list"*) echo '[]'; exit 0 ;;
  *matching-refs*)
      if [ -f "$STATE" ]; then
        echo '["refs/heads/campaign-9999/5-aaa","refs/heads/campaign-9999/5-zzz"]'
      else
        : > "$STATE"; echo '[]'
      fi
      exit 0 ;;
  *commits/main*) echo 1111111111111111111111111111111111111111; exit 0 ;;
  *"-X DELETE"*) echo "$*" >> RACEDIR/deleted; exit 0 ;;
  *git/refs*) exit 0 ;;
esac
exit 1
""".replace("RACEDIR", str(Path(d) / "raced")))
        r = claim(["take", "9999", "5", "zzz"], raced)
        out = r.stdout + r.stderr
        check("a taker that sees a rival after its own create yields",
              r.returncode == 3 and "in the same moment" in out
              and "campaign-9999/5-aaa" in out)
        check("...and deletes the ref it just cut", "has been deleted again" in out)
        check("...and says the sub-issue may now be free, since the rival "
              "yields too", "may now be free" in out)
        # EVERYONE YIELDS, so the smaller name gets no special door: a tiebreak
        # both racers cannot compute the same way is not a tiebreak. This is the
        # case that would pass under a `min()` rule and must not.
        (Path(d) / "raced" / "n").unlink()
        deleted = Path(d) / "raced" / "deleted"
        if deleted.exists():
            deleted.unlink()
        r = claim(["take", "9999", "5", "aaa"], raced)
        out = r.stdout + r.stderr
        # ASSERTED ON THE DELETE, not on the exit status: a `min()` tiebreak
        # that lets the smaller name keep its ref also exits 3 and also prints
        # "in the same moment", so an exit-status case is satisfied by the very
        # rule this replaced.
        check("the lexicographically smaller name yields too, and its ref goes",
              r.returncode == 3 and deleted.exists()
              and "campaign-9999/5-aaa" in deleted.read_text())
        # A delete that FAILED must not be reported as done: the orphan then
        # refuses every later take on the sub-issue while the message says it
        # is gone.
        # Stateful like `raced`: the survey must come back EMPTY or `take`
        # exits at it and never reaches the create, the re-check, or the delete.
        nodel = shims(Path(d) / "nodel", gh="""#!/bin/sh
STATE=NODELDIR/n
case "$*" in
  *"--json parent"*) echo '9999'; exit 0 ;;
  *"issue view"*) echo 'Repository: none'; exit 0 ;;
  *"issues/9999"*) echo '["bound:'"$(hostname -s)"'"]'; exit 0 ;;
  *matching-refs*)
      if [ -f "$STATE" ]; then
        echo '["refs/heads/campaign-9999/6-a","refs/heads/campaign-9999/6-b"]'
      else
        : > "$STATE"; echo '[]'
      fi
      exit 0 ;;
  *commits/main*) echo 1111111111111111111111111111111111111111; exit 0 ;;
  *"pr list"*) echo '[]'; exit 0 ;;
  *"-X DELETE"*) echo "boom" >&2; exit 1 ;;
  *git/refs*) exit 0 ;;
esac
exit 1
""".replace("NODELDIR", str(Path(d) / "nodel")))
        r = claim(["take", "9999", "6", "b"], nodel)
        out = r.stdout + r.stderr
        check("a failed delete of the yielded ref is reported, not assumed",
              "was NOT deleted" in out and "by hand" in out)

        # A ref listing that failed is not proof the sub-issue is free.
        blind = shims(Path(d) / "blind", gh="""#!/bin/sh
case "$*" in
  *"--json parent"*) echo '9999'; exit 0 ;;
  *"issue view"*) echo 'Repository: none'; exit 0 ;;
  *"issues/9999"*) echo '["bound:'"$(hostname -s)"'"]'; exit 0 ;;
esac
exit 1
""")
        r = claim(["take", "9999", "1", "alpha"], blind)
        check("take refuses when the ref listing did not happen",
              r.returncode == 1 and "not proof the sub-issue is free"
              in r.stdout + r.stderr)

        # The binding, read BEFORE the ref is cut.
        elsewhere = shims(Path(d) / "elsewhere", gh=GH_ELSEWHERE)
        r = claim(["take", "9999", "1", "alpha"], elsewhere)
        out = r.stdout + r.stderr
        check("take refuses when the campaign is bound elsewhere",
              r.returncode == 1 and "bound elsewhere" in out)
        check("...and cuts no ref, so the refusal is before the write",
              "cut from" not in out and "claimed campaign" not in out)


def release_cases(m):
    with tempfile.TemporaryDirectory() as d:
        repo, trees = a_repo(d, "campaign-9999/1-alpha")
        # The refusal only a derived attribution can make: the branch is
        # somebody's workspace right now. The herdr row's cwd is the worktree's
        # OWNING repository, which is how the sweep reaches a worktree at all.
        path = shims(d, herdr=listing(
            agent("s1", "campaign-9999-worker-1", str(repo))))
        r = claim(["release", "9999", "1"], path)
        out = r.stdout + r.stderr
        check("release refuses a branch a workspace is standing in",
              r.returncode == 1 and "checked out in 1 workspace" in out)
        check("...and names the path, so the reader knows where to look",
              trees["campaign-9999/1-alpha"] in out)

        # herdr unreadable: an unread occupant is not an absent one.
        no_herdr = shims(Path(d) / "noherdr")
        r = claim(["release", "9999", "1"], no_herdr)
        check("release refuses when the occupancy reading did not happen",
              r.returncode == 1 and "herdr" in (r.stdout + r.stderr))

        # A BRANCH WITH COMMITS IS NEVER DELETED -- and used to leave no exit
        # at all, so a sub-issue closed `not planned` after its worker pushed
        # kept a ref that `take`'s sweep then refused forever.
        ahead = shims(Path(d) / "ahead", herdr=listing(), gh=GH.replace(
            "*compare/main*) echo 0; exit 0 ;;",
            "*compare/main*) echo 3; exit 0 ;;"))
        r = claim(["release", "9999", "1"], ahead)
        out = r.stdout + r.stderr
        check("release refuses a branch holding commits",
              r.returncode == 1 and "3 commit(s) ahead" in out)
        check("...and names both ways out, one of them a command",
              "gh api -X DELETE" in out and "pull request" in out)

        # `--branch` NAMING A REF THIS DID NOT FIND: falling back to the base
        # aimed the compare, the merged-pull-request question and the DELETE at
        # a repository that may carry the same branch name.
        r = claim(["release", "9999", "1", "--branch",
                   "campaign-9999/1-somewhere-else"], path)
        out = r.stdout + r.stderr
        check("release refuses a --branch whose repository was never read",
              r.returncode == 1 and "which repository it is on is unknown" in out)
        check("...and says which repositories it did read",
              "kalaluthien/campaign-base" in out)

        # A sub-issue with no ref of its own is a refusal, never a silent pass.
        r = claim(["release", "9999", "7"], path)
        check("release refuses a sub-issue no ref names",
              r.returncode == 1 and "no ref under campaign-9999/" in r.stderr)

        # THE FRESH CLAIM. `2-beta` is 0 ahead of main, was never merged, and no
        # workspace holds it -- which is exactly a claim cut for a delegate that
        # has not checked it out yet, and is byte-for-byte what finished work
        # looks like. Deleting it lets a second `take` succeed.
        empty = shims(Path(d) / "empty", herdr=listing())
        r = claim(["release", "9999", "1"], empty)
        out = r.stdout + r.stderr
        check("release refuses an empty branch that was never merged",
              r.returncode == 1 and "never merged" in out
              and "--confirmed-absent" in out)
        check("...and says what deleting it would cost",
              "second `take` succeed" in out)
        # The shim's DELETE is unhandled and exits 1, so reaching it is visible
        # as the delete's own refusal rather than as this gate passing.
        r = claim(["release", "9999", "1", "--confirmed-absent", "a person"],
                  empty)
        out = r.stdout + r.stderr
        check("...and a confirmed absence gets past it to the delete",
              "absence confirmed by: a person" in out)
        # ------ #187 Q2: THE SUB-ISSUE'S OWN STATE ANSWERS THIS ------
        # A repo-less sub-issue lands no commit, so its ref is 0 ahead FOR EVER
        # and no merged pull request will ever exist to say the work is done.
        # `--confirmed-absent` was the only door, and passing it for a sub-issue
        # that is closed-completed would be a person asserting something GitHub
        # already says. Its own shim: the ref list has to hold a branch whose
        # sub-issue is closed, and widening the shared one moves every count the
        # `live` cases assert.
        def rel_gh(state):
            return """#!/bin/sh
case "$*" in
  *"--json state"*) echo '%s'; exit 0 ;;
  *"issue view"*) echo 'Repository: none'; exit 0 ;;
  *matching-refs*) echo '["refs/heads/campaign-9999/4-done"]'; exit 0 ;;
  *"issues/9999"*) echo '["campaign","bound:'"$(hostname -s)"'"]'; exit 0 ;;
  *compare/main*) echo 0; exit 0 ;;
  *"pr list"*) echo '[]'; exit 0 ;;
esac
exit 1
""" % state
        done = shims(Path(d) / "q2done", gh=rel_gh("CLOSED completed"),
                     herdr=listing())
        r = claim(["release", "9999", "4"], done)
        out = r.stdout + r.stderr
        check("a closed sub-issue's empty ref releases with no person's word",
              "its work is over and the ref is residue" in out
              and "--confirmed-absent" not in out,
              out[:300])
        # Dropped counts as settled too, or a sub-issue closed as not planned
        # would strand its ref while a completed one did not.
        gone = shims(Path(d) / "q2gone", gh=rel_gh("CLOSED not_planned"),
                     herdr=listing())
        r = claim(["release", "9999", "4"], gone)
        out = r.stdout + r.stderr
        check("...and a sub-issue dropped as not planned counts as settled",
              "not_planned" in out and "ref is residue" in out, out[:300])
        # ...and an OPEN one still needs the person, or the gate is gone.
        openish = shims(Path(d) / "q2open", gh=rel_gh("OPEN "),
                        herdr=listing())
        r = claim(["release", "9999", "4"], openish)
        out = r.stdout + r.stderr
        check("an open sub-issue's empty ref still needs --confirmed-absent",
              r.returncode == 1 and "--confirmed-absent" in out,
              f"exit {r.returncode}: {out[:250]}")
        check("...and the refusal offers closing the sub-issue as the other way",
              "Close the sub-issue if its work is done" in out, out[:300])
        # "I could not look" is not "it is closed" and not "it is open".
        unread_state = shims(Path(d) / "q2unread", gh=rel_gh("").replace(
            "echo ''; exit 0", "exit 1"), herdr=listing())
        r = claim(["release", "9999", "4"], unread_state)
        out = r.stdout + r.stderr
        check("a state that would not read denies the release",
              r.returncode == 1 and "an unknown is not a release" in out,
              f"exit {r.returncode}: {out[:250]}")

        # ------ FINDINGS 2 AND 7: release reads the sub-issue too ------
        # The spec says "`take` and `release` read the sub-issue's own
        # `Repository:` line"; only `take` did, and `release` picked a
        # repository out of the clones on disk. A delete aimed by the wrong
        # reader takes a ref that is not this sub-issue's.
        r = claim(["release", "9999", "501"], empty)
        out = r.stdout + r.stderr
        check("release refuses when the sub-issue's repository will not read",
              r.returncode == 1 and "could not read #501" in out
              and "this deletes a ref" in out,
              f"exit {r.returncode}: {out[:250]}")
        r = claim(["release", "9999", "500", "--repo", "someone/other"], empty)
        out = r.stdout + r.stderr
        check("...and refuses a --repo that disagrees with the sub-issue",
              r.returncode == 1 and "The sub-issue decides" in out,
              f"exit {r.returncode}: {out[:250]}")
        # FINDING 7. An explicit `--repo <the base>` used to be indistinguishable
        # from no flag, so this one disagreement passed silently. Sub-issue 500
        # says `other/elsewhere`.
        r = claim(["release", "9999", "500", "--repo",
                   "kalaluthien/campaign-base"], empty)
        out = r.stdout + r.stderr
        check("...including an explicit --repo that happens to be the base",
              r.returncode == 1 and "The sub-issue decides" in out,
              f"exit {r.returncode}: {out[:250]}")
        # ...and the allow beside it: an agreeing --repo gets past the check.
        # Asserted on the refusal being ABSENT and the reading having happened,
        # not on the exit status: this run stops later for want of a ref, which
        # is a different branch and would satisfy a status-keyed case either way.
        r = claim(["release", "9999", "500", "--repo", "other/elsewhere"], empty)
        out = r.stdout + r.stderr
        check("...while a release whose --repo AGREES gets past the check",
              "The sub-issue decides" not in out
              and "says its work lands in other/elsewhere" in out,
              f"exit {r.returncode}: {out[:250]}")
        r = claim(["take", "9999", "500", "x", "--repo",
                   "kalaluthien/campaign-base"], path)
        out = r.stdout + r.stderr
        check("...and take says the same about an explicit base --repo",
              r.returncode == 1 and "The sub-issue decides" in out,
              f"exit {r.returncode}: {out[:250]}")
        # THE ALLOW BESIDE THE REFUSAL. `--repo` may confirm, so a `--repo` that
        # AGREES with the sub-issue must pass -- otherwise "may only confirm"
        # is a flag that can only ever refuse, which is a false positive on the
        # one shape the flag exists for. Every refusal branch this lands ships
        # with the ordinary shape it could wrongly catch named beside it.
        r = claim(["take", "9999", "500", "y", "--repo", "other/elsewhere"],
                  path)
        out = r.stdout + r.stderr
        check("...while a --repo that AGREES with the sub-issue passes",
              "The sub-issue decides" not in out and "cut from" in out,
              f"exit {r.returncode}: {out[:250]}")

        # ...and the OTHER side of the same gate: a branch whose pull request
        # merged is finished work, and needs no person to say so.
        r = claim(["release", "9999", "2"], empty)
        out = r.stdout + r.stderr
        check("a merged branch passes the gate with no --confirmed-absent",
              "finished work and not a fresh claim" in out
              and "--confirmed-absent" not in out)


def scope_cases(m):
    """#187 Q4: which campaign directory a reading is about."""
    # The walk, as a calculation. Driven by a path rather than by where this
    # file sits, which differs in a worktree, in a clone, and on CI.
    root = Path("/b")
    check("the campaign directory is the `<slug>-<YYMMDD>` ancestor",
          m.own_campaign_dir(Path("/b/demo-260905/repos/acme/scripts/x.py"))
          == Path("/b/demo-260905"))
    check("...and a path under no campaign directory has none",
          m.own_campaign_dir(Path("/b/scripts/x.py")) is None)
    # The nearest one wins: a campaign directory inside another is still the
    # one this invocation is about.
    check("...and the nearest ancestor wins",
          m.own_campaign_dir(Path("/b/outer-260901/x/inner-260905/s/x.py"))
          == Path("/b/outer-260901/x/inner-260905"))

    # ------ FINDING 3: THE SCOPE MUST BE THE SUBJECT'S, NOT THE INVOKER'S ---
    # `own_campaign_dir` answers "which directory is this script under", which
    # is the invoker's. Scoping on that alone made `live 5` run from campaign
    # #1's tree sweep #1's clones and report all three readings made -- blind to
    # #5's, which the machine-wide sweep at least reached. Confirmed against the
    # one artifact that names a campaign: the derived body's first line.
    with tempfile.TemporaryDirectory() as d:
        camp = Path(d) / "demo-260905"
        (camp / "runtime").mkdir(parents=True)
        (camp / "runtime" / "campaign-issue-body-derived.md").write_text(
            "Bootstrap the thing.\n\n## Intent\n")
        real_own, real_run = m.own_campaign_dir, m.run
        try:
            m.own_campaign_dir = lambda start=None: camp

            class R:
                returncode, stdout, stderr = 0, "Bootstrap the thing.\n\nx", ""
            m.run = lambda *a, **k: R()
            got, note = m.scope_for("9999")
            check("a directory whose derived body matches the campaign scopes",
                  got == camp and "this campaign's directory" in note, note)

            class R2:
                returncode, stdout, stderr = 0, "Some other campaign.\n", ""
            m.run = lambda *a, **k: R2()
            got, note = m.scope_for("9999")
            check("...and one that does not match falls back to the wide sweep",
                  got is None and "not campaign #9999's directory" in note, note)
            check("...saying the sweep was wide, so the reader is not misled",
                  "every campaign directory here was swept" in note, note)

            # "I could not look" is its own answer and also falls back: a scope
            # that MIGHT be the wrong campaign's is worse than no scope, since
            # the wide sweep is noisy and the wrong scope is silently blind.
            class R3:
                returncode, stdout, stderr = 1, "", "boom"
            m.run = lambda *a, **k: R3()
            got, note = m.scope_for("9999")
            check("...and a campaign body that would not read falls back too",
                  got is None and "could not read campaign #9999" in note, note)

            (camp / "runtime" / "campaign-issue-body-derived.md").unlink()
            m.run = lambda *a, **k: R()
            got, note = m.scope_for("9999")
            check("...as does a directory carrying no derived body at all",
                  got is None and "no readable" in note, note)
        finally:
            m.own_campaign_dir, m.run = real_own, real_run

    # THE WIRING, and not the helper alone. A case that only called
    # `own_campaign_dir` would pass with the command never consulting it --
    # which is exactly what happened: the helper was covered and the call was
    # not, and deleting the walk left every case green.
    real = (m.own_campaign_dir, m.sweep_roots, m.base_root, m.matching_refs,
            m.herdr_sessions, m.checkouts, m.claim_repos, m.scope_for)
    seen = {}
    try:
        m.own_campaign_dir = lambda start=None: Path("/the-scope-260905")
        m.scope_for = lambda ci: (Path("/the-scope-260905"),
                                  "SCOPE-NOTE-FOR-THE-READER")
        m.base_root = lambda: ("/b", None)
        m.matching_refs = lambda repo, ci: ([], None)
        m.herdr_sessions = lambda: ({}, None)
        m.checkouts = lambda roots: ({}, [])
        def claim_repos_spy(r, root, only=None, ci=None):
            seen["claim_repos"] = only
            # THE SECOND ARGUMENT, recorded too. Pinning `only` alone left the
            # `## Repos` reading unwired-testable: dropping `args.campaign_issue`
            # from either caller kept every case green, and `live` would print
            # "0 occupied, 0 vacant" over a held claim on an uncloned member --
            # the exact false-clean this branch exists to prevent.
            seen["claim_repos_ci"] = ci
            return [r], "note"
        m.claim_repos = claim_repos_spy
        def spy(sessions, only=None):
            seen["sweep_roots"] = only
            return ([], [], None)
        m.sweep_roots = spy

        class Args:
            campaign_issue, repo = "9999", "o/r"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m.cmd_live(Args())
        # THE NOTE IS PRINTED, not merely returned. `scope_for` says whether the
        # sweep was scoped or fell back to every campaign directory here, and a
        # wrong-scope reading that says nothing is exactly the silent failure
        # the fallback exists to avoid. Deleting `print(scope_note)` reddened no
        # case before this one.
        check("cmd_live prints which sweep it made",
              "SCOPE-NOTE-FOR-THE-READER" in buf.getvalue(),
              buf.getvalue()[:200])
        check("cmd_live scopes its sweep to this campaign's directory",
              seen.get("sweep_roots") == Path("/the-scope-260905"),
              f"got {seen.get('sweep_roots')!r}")
        check("...and scopes the repository reading the same way",
              seen.get("claim_repos") == Path("/the-scope-260905"),
              f"got {seen.get('claim_repos')!r}")
        check("...and names the campaign, so `## Repos` is read at all",
              seen.get("claim_repos_ci") == "9999",
              f"got {seen.get('claim_repos_ci')!r}")
        # FINDING 4: THE OTHER COMMAND. `cmd_release` has the same two calls
        # and the spy covered only `cmd_live`, so dropping the scope from
        # release changed no case at all -- the helper-covered, caller-
        # uncovered shape for the sixth time in this repository.
        seen.clear()
        real_ir, real_ar = m.issue_repo, m.all_refs
        try:
            m.issue_repo = lambda i, d: (d, None, "note")
            m.all_refs = lambda repos, ci: ({}, [])
            class RArgs:
                campaign_issue, issue, repo = "9999", "7", None
                branch, confirmed_absent = None, None
            rbuf = io.StringIO()
            with contextlib.redirect_stdout(rbuf):
                m.cmd_release(RArgs())
            check("cmd_release prints which sweep it made",
                  "SCOPE-NOTE-FOR-THE-READER" in rbuf.getvalue(),
                  rbuf.getvalue()[:200])
        finally:
            m.issue_repo, m.all_refs = real_ir, real_ar
        check("cmd_release scopes its repository reading the same way",
              seen.get("claim_repos") == Path("/the-scope-260905"),
              f"got {seen.get('claim_repos')!r}")
        check("...and names the campaign there too",
              seen.get("claim_repos_ci") == "9999",
              f"got {seen.get('claim_repos_ci')!r}")
    finally:
        (m.own_campaign_dir, m.sweep_roots, m.base_root, m.matching_refs,
         m.herdr_sessions, m.checkouts, m.claim_repos, m.scope_for) = real


def sweep_scope_cases(m):
    """The hop INSIDE sweep_roots, which the other two cases jump over.

    `sweep_roots({}, None)` covers `campaign_clones(only)` and the wiring spy
    replaces `sweep_roots` wholesale, so both ends were pinned and the wire
    between them was not: passing `None` through to `campaign_clones` left every
    case green while the worktree sweep went machine-wide again. Eighth instance
    of that shape here.
    """
    real = m.campaign_clones
    seen = {}
    try:
        def spy(root, only=None):
            seen["only"] = only
            return [], []
        m.campaign_clones = spy
        m.sweep_roots({}, "THE-SCOPE")
        check("sweep_roots passes its scope through to campaign_clones",
              seen.get("only") == "THE-SCOPE", f"got {seen.get('only')!r}")
    finally:
        m.campaign_clones = real


def listed_repo_cases(m):
    """#187 Q1 third defect: `## Repos` is read, not only the clones on disk."""
    real = m.campaign_repos
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "demo-260904" / "repos").mkdir(parents=True)
            # A member repository the campaign is FOR, whose clone was never
            # made here. Its claim is real, on the remote, and was invisible:
            # `live` printed "0 occupied, 0 vacant" and a close passed over a
            # held claim. The clones answer "where might somebody be standing";
            # `## Repos` answers "where might a claim be", and they differ
            # exactly when a member repository was never cloned or was removed.
            m.campaign_repos = lambda ci: (["owner/member"], "listed")
            repos, note = m.claim_repos("base/base", str(root), None, "1")
            check("a `## Repos` member with no clone here is still read",
                  "owner/member" in repos, str(repos))
            check("...and the note says it had no clone, so the reader knows why",
                  "no clone here" in note, note)
            # ...and a list that would not READ narrows nothing silently.
            m.campaign_repos = lambda ci: (None, "the list did not read")
            repos, note = m.claim_repos("base/base", str(root), None, "1")
            check("a `## Repos` that would not read is named, not skipped",
                  "may be unread" in note, note)
            # ...and with no campaign issue passed, the old behaviour stands,
            # so a caller that names its own repository asks nothing extra.
            m.campaign_repos = lambda ci: (["owner/member"], "listed")
            repos, _ = m.claim_repos("base/base", str(root), None, None)
            check("...and nothing is read from `## Repos` when none is asked for",
                  "owner/member" not in repos, str(repos))
    finally:
        m.campaign_repos = real


def sweep_cases(m):
    """The roots, which used to be derived from who was alive."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d).resolve()
        # A base root shaped like the real one: one campaign directory holding a
        # member clone, and one holding none.
        (root / "demo-260904" / "repos" / "acme").mkdir(parents=True)
        (root / "repoless-260904" / "runtime").mkdir(parents=True)
        (root / "not-a-campaign").mkdir()
        clones, unread = m.campaign_clones(str(root))
        check("a member clone under a campaign directory is a sweep root",
              clones == [str(root / "demo-260904" / "repos" / "acme")]
              and not unread)
        check("...found with no session alive anywhere, which is the point",
              not unread)
        check("a directory that is not <slug>-<YYMMDD> is not a campaign",
              str(root / "not-a-campaign") not in " ".join(clones))
        check("a repo-less campaign is not a failed reading",
              not unread)

        # A `repos/` that will not enumerate is NAMED. It is the case that
        # matters: skipping it silently is how a branch in an unswept clone
        # reads as standing in no workspace.
        bad = root / "locked-260904" / "repos"
        bad.mkdir(parents=True)
        bad.chmod(0o000)
        real = m.base_root
        try:
            clones, unread = m.campaign_clones(str(root))
            check("a repos/ that will not enumerate is reported, not skipped",
                  len(unread) == 1 and "locked-260904" in unread[0])
            m.base_root = lambda: (str(root), None)
            roots, unread, why = m.sweep_roots({}, None)
            check("...and an unreadable repos/ comes back through sweep_roots",
                  len(unread) == 1 and "locked-260904" in unread[0])
            # ------ #187 Q4: A NEIGHBOUR'S DIRECTORY IS NOT THIS ONE'S ------
            # The same locked directory, with the sweep scoped to a DIFFERENT
            # campaign's directory. It used to deny `live` and `release` for
            # every campaign on the machine; scoped, it is not read at all.
            mine = root / "mine-260905" / "repos" / "acme"
            mine.mkdir(parents=True)
            clones, unread = m.campaign_clones(str(root), root / "mine-260905")
            check("a neighbour's unreadable repos/ does not deny this campaign",
                  not unread, str(unread))
            check("...and this campaign's own clone is still swept",
                  any("acme" in c for c in clones), str(clones))
            # ...and the scoping does not become a way to MISS this campaign's
            # own failure: locked, scoped to itself, it is still reported.
            clones, unread = m.campaign_clones(str(root), root / "locked-260904")
            check("...while this campaign's OWN unreadable repos/ still denies",
                  len(unread) == 1 and "locked-260904" in unread[0], str(unread))
        finally:
            bad.chmod(0o755)
            m.base_root = real

        # THE WIRING, not the helper. `campaign_clones` passing on its own
        # proves nothing about `sweep_roots` calling it, and the defect was the
        # call site: roots derived from live herdr rows go blind exactly when a
        # session dies. NO SESSIONS AT ALL here, so a root that appears can only
        # have come from the campaign directories.
        real = m.base_root
        try:
            m.base_root = lambda: (str(root), None)
            roots, unread, why = m.sweep_roots({}, None)
            check("sweep_roots reaches a member clone with nothing alive",
                  why is None
                  and str(root / "demo-260904" / "repos" / "acme") in roots)
            check("...and the base root is always among them",
                  str(root) in roots)
        finally:
            m.base_root = real


def verdict_cases(m, capsys=None):
    """`live`'s two closing lines, which must never both print.

    In-process with the three readings stubbed, because the defect is in what
    `cmd_live` PRINTS and the unread it prints about comes from a repository
    this suite must not have to break on the real machine to produce."""
    import io
    import contextlib

    class Args:
        repo, campaign_issue = "o/r", "9"

    real = (m.matching_refs, m.herdr_sessions, m.sweep_roots, m.checkouts,
            m.base_root)
    try:
        m.matching_refs = lambda r, n: (["campaign-9/1-a"], None)
        m.herdr_sessions = lambda: ({}, None)
        m.base_root = lambda: ("/nowhere", None)
        m.sweep_roots = lambda s, only=None: (["/a"], ["/b: would not enumerate"], None)
        m.checkouts = lambda roots: ({}, [])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = m.cmd_live(Args())
        out = buf.getvalue()
        check("an unread repository denies the completed verdict on STDOUT",
              "NOT all readings were made" in out
              and "all three readings were made" not in out)
        check("...and it exits 1", code == 1)
        check("...and names the repository it could not sweep",
              "would not enumerate" in out)

        m.sweep_roots = lambda s, only=None: (["/a"], [], None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = m.cmd_live(Args())
        out = buf.getvalue()
        check("a complete sweep does print the verdict, and exits 0",
              "all three readings were made" in out and code == 0
              and "NOT all readings" not in out)

        # THE BASE ROOT REACHES `classify`, end to end. The printing loop over
        # the swept roots once rebound the same name, so the cwd rule the peer
        # set turns on was compared against the last repository swept -- and
        # every unit case passed, because they call `classify` with the right
        # root directly. This one runs the command.
        m.base_root = lambda: ("/BASE", None)
        m.sweep_roots = lambda s, only=None: (["/some/other/repo"], [], None)
        m.herdr_sessions = lambda: ({"s1": {"name": "<unnamed>",
                                            "cwd": "/BASE/anywhere",
                                            "pane": "p", "status": "idle"}},
                                    None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m.cmd_live(Args())
        out = buf.getvalue()
        check("an unnamed session under the base root reaches the peer list",
              "live sessions of campaign-9 (1)" in out
              and "/BASE/anywhere" in out)
        # A row silently missing from a count is the shape nobody questions, so
        # `live` says which session it left out -- and says plainly when there
        # is no session id to leave out, because then the closer's own row makes
        # the close unpassable with no cause shown anywhere.
        check("live names the session it excluded from the count",
              "this session is" in out)
        import os as _os
        keep = _os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                m.cmd_live(Args())
            check("...and says so when there is no session id at all",
                  "unset" in buf.getvalue())
        finally:
            if keep is not None:
                _os.environ["CLAUDE_CODE_SESSION_ID"] = keep
    finally:
        (m.matching_refs, m.herdr_sessions, m.sweep_roots, m.checkouts,
         m.base_root) = real


def root_cases(m):
    """`base_root` from a clone, which is the base as a member of itself."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d).resolve()
        here = root / "demo-260904" / "repos" / "campaign-base" / "scripts"
        here.mkdir(parents=True)
        real = m.HERE
        try:
            m.HERE = here
            got, why = m.base_root()
            # THE CLONE IS A DIFFERENT REPOSITORY, script and all, so the git
            # rule answers with the clone -- a base root holding no campaign
            # directory, which sweeps clean and lets `release` delete a ref
            # somebody is standing in. The campaign-directory ancestor is what
            # says otherwise.
            check("base_root run from a clone finds the real base root",
                  why is None and got == str(root))
        finally:
            m.HERE = real
        got, why = m.base_root()
        check("...and from the base's own scripts/ it still answers",
              why is None and got)

    check("an ssh remote parses to owner/repo",
          m.REMOTE.search("git@github.com:o/r.git").group(1) == "o/r")
    check("...and an https one",
          m.REMOTE.search("https://github.com/o/r").group(1) == "o/r")


def repos_cases(m):
    """Which repositories a campaign's claims can be on."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d).resolve()
        clone = root / "demo-260904" / "repos" / "acme"
        clone.mkdir(parents=True)
        subprocess.run(["git", "-C", str(clone), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(clone), "remote", "add", "origin",
                        "git@github.com:o/acme.git"], check=True)
        repos, note = m.claim_repos("o/base", str(root))
        # A MEMBER-REPO CLAIM IS ON THE MEMBER'S REMOTE. Reading only the base
        # returned `0 occupied, 0 vacant` over a delegate standing in one.
        check("a member clone's origin joins the repositories read",
              repos == ["o/base", "o/acme"])
        check("...and the base is always first", repos[0] == "o/base")
        repos, note = m.claim_repos("o/base", None)
        check("with no base root, only the named repository is read, and it says so",
              repos == ["o/base"] and "no base root" in note)

    # THE REPOSITORY TRAVELS WITH THE REF, because a delete aimed at the wrong
    # one takes a different repository's commits. Asserted on the MAPPING, not
    # on the return type: `isinstance(..., tuple)` was true of every shape this
    # function could have had, including the one that dropped the repository.
    real = m.matching_refs
    try:
        answers = {"o/base": (["campaign-1/7-a"], None),
                   "o/acme": (["campaign-1/8-b"], None)}
        m.matching_refs = lambda repo, n: answers[repo]
        found, unread = m.all_refs(["o/base", "o/acme"], "1")
        check("all_refs keys each branch to the repository it was found on",
              found == {"campaign-1/7-a": "o/base",
                        "campaign-1/8-b": "o/acme"} and not unread)
        # A repository whose listing failed is NAMED, because a claim that could
        # not be read is not an absent one.
        answers["o/acme"] = (None, "acme would not answer")
        found, unread = m.all_refs(["o/base", "o/acme"], "1")
        check("...and a repository that would not answer is reported",
              found == {"campaign-1/7-a": "o/base"}
              and unread == ["acme would not answer"])
    finally:
        m.matching_refs = real


def peer_cases(m):
    """Who a close is told to ask -- and who it is not."""
    sessions = {
        "me": {"name": "campaign-9-worker-1", "cwd": "/base/x", "pane": "p",
               "status": "idle"},
        "peer": {"name": "campaign-9-planner-2", "cwd": "/base", "pane": "p",
                 "status": "idle"},
        "unnamed": {"name": "<unnamed>", "cwd": "/base/y", "pane": "p",
                    "status": "idle"},
        "other": {"name": "campaign-3-worker-1", "cwd": "/elsewhere",
                  "pane": "p", "status": "idle"},
    }
    _, _, ours = m.classify([], {}, sessions, "9", root="/base", caller="me")
    names = sorted(sid for sid, _ in ours)
    # THE CLOSER IS NOT ITS OWN BLOCKER: a close runs from a session of the
    # campaign, so a gate refusing on any live session of it can never pass.
    check("the caller is excluded from the peers a close must ask",
          "me" not in names)
    # AND A SESSION THAT NEVER NAMED ITSELF IS STILL A PEER. Nothing enforces
    # the naming rule since the record went, so a prefix-only set misses it.
    check("an unnamed session under the base root is still a peer",
          "unnamed" in names)
    check("a named peer of this campaign is a peer", "peer" in names)
    check("a session of another campaign, elsewhere, is not",
          "other" not in names)

    # THE OVERCORRECTION. Counting every session under the base root made
    # `ours` identical for every campaign number, so closing #116 asked #1's
    # planner to stand down. A name that says whose it is, is believed.
    under_base = {"x": {"name": "campaign-1-planner-3", "cwd": "/base",
                        "pane": "p", "status": "idle"}}
    check("a session named for ANOTHER campaign is not this one's, even here",
          not m.classify([], {}, under_base, "116", root="/base",
                         caller=None)[2])
    check("...and it IS its own campaign's",
          len(m.classify([], {}, under_base, "1", root="/base",
                         caller=None)[2]) == 1)

    # `under` answers about absolute paths only: `Path.resolve()` resolves a
    # relative one against the PROCESS cwd, so herdr's `"?"` placeholder counted
    # three unrelated sessions. THE ROOT HERE IS AN ANCESTOR OF THE PROCESS'S
    # OWN CWD, and it has to be: against a root the process is not inside, the
    # resolved junk path falls outside anyway and the case passes with the guard
    # deleted -- which is a fixture that pins nothing.
    inside = str(Path.cwd().parent)
    for junk in ("?", "", "relative/path"):
        check(f"under({junk!r}) is False even from inside the root",
              not m.under(junk, inside))
    check("under() still answers True for a real path inside the root",
          m.under(str(Path.cwd()), inside))
    check("...and False for a sibling that shares a prefix",
          not m.under("/base-other/x", "/base"))


def robustness_cases(m):
    rows, why = m.parse_agents('{"result": {"agents": null}}')
    check("herdr `agents: null` is a why, not a traceback",
          rows is None and why)
    rows, why = m.parse_agents('{"result": {"agents": ["a string"]}}')
    check("a herdr row that is not an object is a why, not a traceback",
          rows is None and why)


def looked(fn, *args):
    """`fn(*args)`, with an exception turned into a (None, text) answer. A case
    that crashes stops every case after it, so a branch whose removal raises
    would be pinned by nothing at all."""
    try:
        return fn(*args)
    except Exception as e:                                    # noqa: BLE001
        return None, f"raised {e.__class__.__name__}: {e}"


def compact_cases(m):
    """#198: the release enqueues `/compact` into its OWN pane, and every way
    that can fail is said out loud rather than skipped.

    The pure half first, then five end-to-end cases over a stubbed `herdr` that
    records what it was asked to send. An allow case sits beside every refusal,
    because a compaction the code declined to make and one it made to the wrong
    pane are the two failures, and only one of them is visible in the exit
    status -- neither, in fact, which is why release's exit is asserted to be
    0 in all five."""
    rows = {"S1": {"name": "campaign-9999-worker-1", "status": "idle",
                   "cwd": "/tmp", "pane": "w1:p1"},
            "S2": {"name": "campaign-9999-worker-2", "status": "idle",
                   "cwd": "/tmp", "pane": "w1:p2"}}
    pane, note = m.own_pane(rows, "S2")
    check("own_pane joins the session id to its own row, not the first row",
          pane == "w1:p2" and "w1:p2" in note and "worker-2" in note,
          f"{pane!r} {note!r}")
    pane, note = m.own_pane(rows, None)
    check("no session id in the environment is a could-not-look, not a pane",
          pane is None and "CLAUDE_CODE_SESSION_ID" in note
          and "cannot name its own session" in note, note)
    # CALLED THROUGH `looked`, because deleting the branch this pins makes
    # `own_pane` raise KeyError, and an exception out of a case kills the suite
    # before any later case runs -- which reads as "no failing case" to a
    # mutation harness and pins the branch with nothing. Measured 2026-09-05.
    pane, note = looked(m.own_pane, rows, "S9")
    check("a session id no row names is said, with how many rows were read",
          pane is None and "no herdr row names it" in note
          and "2 row(s)" in note, note)

    # --- end to end: a release that actually deletes a ref ---
    # The DELETE has to succeed, or the run stops before the compaction and
    # every case below would pass by never reaching the code under test.
    rel_gh = """#!/bin/sh
case "$*" in
  *"--json state"*) echo 'CLOSED completed'; exit 0 ;;
  *"issue view"*) echo 'Repository: none'; exit 0 ;;
  *matching-refs*) echo '["refs/heads/campaign-9999/4-done"]'; exit 0 ;;
  *"issues/9999"*) echo '["campaign","bound:'"$(hostname -s)"'"]'; exit 0 ;;
  *compare/main*) echo 0; exit 0 ;;
  *"pr list"*) echo '[]'; exit 0 ;;
  *"-X DELETE"*) exit 0 ;;
esac
exit 1
"""
    with tempfile.TemporaryDirectory() as d:
        # TWO ROWS, and the releasing session is the SECOND. A shim that
        # prompted the first pane would pass a one-row fixture, which is the
        # bug "never prompts a pane that is not its own" names.
        two = listing(agent("S1", "campaign-9999-worker-1", d, pane="w1:p1"),
                      agent("S2", "campaign-9999-worker-2", d, pane="w1:p2"))

        ok = shims(Path(d) / "ok", gh=rel_gh, herdr=two)
        r = claim(["release", "9999", "4"], ok,
                  {"CLAUDE_CODE_SESSION_ID": "S2"})
        out = r.stdout + r.stderr
        sent = prompts(ok)
        check("release deletes the ref and then compacts its own pane",
              r.returncode == 0 and "deleted campaign-9999/4-done" in out
              and "sent /compact to w1:p2" in out,
              f"exit {r.returncode}: {out[:300]}")
        # THE ANCHOR A LATER READER KEYS ON, printed BEFORE the compaction is
        # attempted so that it is there whether or not the compaction happened.
        # `campaign-assign.py` reads exactly this; keyed on the compaction's own
        # success line instead, a release that could not compact read as a pane
        # that never released and was assigned.
        check("...and prints the release anchor, naming branch AND pane",
              f"{m.RELEASED} campaign-9999/4-done in w1:p2" in out, out[:300])
        check("...sending exactly one /compact, to its own pane, guarded",
              len(sent) == 1 and "pane=w1:p2" in sent[0]
              and "prompt=/compact" in sent[0] and "HERDR_ENV=1" in sent[0],
              repr(sent))
        check("...and never to the other session's pane",
              not any("pane=w1:p1" in ln for ln in sent), repr(sent))

        # NO ROW NAMES THIS SESSION. Released all the same -- compaction is a
        # cost rule, not a gate -- and the miss is printed, because a silent
        # skip is a rule everyone believes is held while nothing is sent.
        miss = shims(Path(d) / "miss", gh=rel_gh, herdr=two)
        r = claim(["release", "9999", "4"], miss,
                  {"CLAUDE_CODE_SESSION_ID": "S404"})
        out = r.stdout + r.stderr
        check("a session no row names still releases, and says it did not compact",
              r.returncode == 0 and "deleted campaign-9999/4-done" in out
              and "not compacting" in out and "no herdr row names it" in out,
              f"exit {r.returncode}: {out[:300]}")
        # THE CASE THE ANCHOR EXISTS FOR. A release that could not compact must
        # still leave the release line, or the next `campaign-assign` reads the
        # pane as one that never released and assigns it -- which is the single
        # case its guard is for.
        # A PANE THIS COULD NOT NAME IS SAID SO, and reads as no anchor at all
        # to `campaign-assign.py`, which refuses -- the right direction, since
        # the compaction was not sent either.
        check("...and the anchor is there, saying the pane is unknown",
              f"{m.RELEASED} campaign-9999/4-done in <pane unknown>" in out,
              out[:400])
        check("...and sends nothing at all",
              prompts(miss) == [], repr(prompts(miss)))

        # NO SESSION ID. The other could-not-look, and a different sentence:
        # a reader who cannot tell the two apart cannot fix either.
        blind = shims(Path(d) / "blind", gh=rel_gh, herdr=two)
        r = claim(["release", "9999", "4"], blind,
                  {"CLAUDE_CODE_SESSION_ID": ""})
        out = r.stdout + r.stderr
        check("no session id releases too, naming the variable it looked for",
              r.returncode == 0 and "deleted campaign-9999/4-done" in out
              and "no CLAUDE_CODE_SESSION_ID in the environment" in out,
              f"exit {r.returncode}: {out[:300]}")
        check("...and sends nothing",
              prompts(blind) == [], repr(prompts(blind)))

        # THE PROMPT ITSELF FAILING is a third could-not-look, and the one a
        # reader is most likely to hit -- a pane that went away between the
        # listing and the send.
        broke = shims(Path(d) / "broke", gh=rel_gh, herdr=two, prompt_exit=3)
        r = claim(["release", "9999", "4"], broke,
                  {"CLAUDE_CODE_SESSION_ID": "S2"})
        out = r.stdout + r.stderr
        check("a prompt that exited non-zero is reported, and still releases",
              r.returncode == 0 and "deleted campaign-9999/4-done" in out
              and "exited 3" in out and "only the compaction did not happen" in out,
              f"exit {r.returncode}: {out[:300]}")

        # THE OTHER SUCCESS EXIT, pinned by nothing until now: the ref is
        # already gone and a merged pull request had it as its head, so there
        # is nothing to delete. It is the ordinary shape for a re-run release,
        # and deleting its `compact_own_pane` call left the whole suite green.
        # Found by review at 114e71a; the mutation string had been indented for
        # the other exit and could never match this one.
        gone_gh = """#!/bin/sh
case "$*" in
  *"--json state"*) echo 'CLOSED completed'; exit 0 ;;
  *"issue view"*) echo 'Repository: none'; exit 0 ;;
  *matching-refs*) echo '["refs/heads/campaign-9999/4-done"]'; exit 0 ;;
  *"issues/9999"*) echo '["campaign","bound:'"$(hostname -s)"'"]'; exit 0 ;;
  *compare/main*) echo 'HTTP 404: Not Found' >&2; exit 1 ;;
  *"git/ref/heads"*) echo 'HTTP 404: Not Found' >&2; exit 1 ;;
  *"pr list"*) echo '[{"number": 208}]'; exit 0 ;;
esac
exit 1
"""
        noref = shims(Path(d) / "noref", gh=gone_gh, herdr=two)
        r = claim(["release", "9999", "4"], noref,
                  {"CLAUDE_CODE_SESSION_ID": "S2"})
        out = r.stdout + r.stderr
        check("the no-ref-and-merged exit releases and compacts too",
              r.returncode == 0 and "no ref to delete" in out
              and "sent /compact to w1:p2" in out,
              f"exit {r.returncode}: {out[:400]}")
        check("...sending exactly one /compact from that exit as well",
              len(prompts(noref)) == 1 and "pane=w1:p2" in prompts(noref)[0],
              repr(prompts(noref)))
        check("...and printing the release anchor, with the pane, there too",
              f"{m.RELEASED} campaign-9999/4-done in w1:p2" in out, out[:400])

        # HERDR ABSENT: `release` refuses long before this on the occupancy
        # sweep, so the compaction is not what is being read here -- and that
        # ordering is itself the assertion, since a compaction attempted on an
        # unreadable listing would be a prompt aimed at a pane nobody read.
        none_at_all = shims(Path(d) / "noherdr", gh=rel_gh)
        r = claim(["release", "9999", "4"], none_at_all,
                  {"CLAUDE_CODE_SESSION_ID": "S2"})
        check("herdr absent refuses the release before any compaction",
              r.returncode == 1 and prompts(none_at_all) == [],
              f"exit {r.returncode}")

def main():
    import importlib.machinery
    import importlib.util
    spec = importlib.util.spec_from_loader(
        "campaign_claim",
        importlib.machinery.SourceFileLoader("campaign_claim", str(CLAIM)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    for fn in (pure_cases, git_cases, live_cases, take_cases, release_cases,
               compact_cases,
               scope_cases, sweep_scope_cases, listed_repo_cases, sweep_cases, verdict_cases, peer_cases,
               robustness_cases,
               root_cases, repos_cases):
        fn(m)
    for name in FAILED:
        print(f"FAIL  {name}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
