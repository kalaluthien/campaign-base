#!/usr/bin/env python3
# witnesses: S23_ChoreLands
"""Cases for campaign-open.py, over a fake `run` that makes no write at all.

THE SUBJECT IS THE ORDER OF THE STEPS AND WHAT STOPS BETWEEN THEM, so the one
effectful name in that script -- `run` -- is replaced by a recorder, and every
case reads what was ASKED rather than an exit status. A `gh` write this script
never makes is the property most of these cases are about: a malformed chore
must cost no label and no issue, and the slug's label must be minted before the
issue so that `gh label create` failing on an existing name still gates.

WHAT IS FAKED AND WHY

  `run`             every gh, git and script call. Nothing here files an issue,
                    mints a label, binds, clones or cuts a ref. The `mark`
                    answer writes the marker its real counterpart writes, so
                    the directory a case reads is the one the script asked for.
  the tracker       campaign-tracker.py's chore kind, its label spellings and
                    its slug pool. Faked rather than imported so these cases
                    hold whatever that file's own suite is doing to it, and so
                    a shape finding, a spent slug and an unreadable pool are
                    each one line to arrange instead of a `gh` fixture.
  `claim_module`    campaign-claim.py, for `branch_name` alone.

WHAT IS REAL: the assets the scaffold copies, the files it writes, the
directory it removes when `mark` refuses, and the argument parsing.

THE NAMED FAILING CASES, both re-run by hand at the sha this suite landed on:
`a spent slug stops before any write`, which goes red when the pool reading is
dropped from step 1, and `the slug's label is minted before the issue`, which
goes red when the two creates swap.

Usage: scripts/campaign-open-test.py
"""
import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPEN_PY = HERE / "campaign-open.py"

harness = importlib.import_module("suite-harness-test")
check = harness.check

SLUG = "demo"
NUMBER = "500"
URL = f"https://github.com/kalaluthien/campaign-base/issues/{NUMBER}"
BODY = ("## Intent\n\n- x\n\n## Definition of done\n\n- y\n\n## Repos\n\n"
        "- none\n")


class FakeTracker:
    """campaign-tracker.py's surface as campaign-open.py uses it, and no more.

    It is the name rule as well, which the real one also is by returning the
    leaf that owns `slug_ok`."""

    CAMPAIGN_LABEL = "campaign"
    CHORE_LABEL = CHORE = "chore"
    SLUG_LABEL_PREFIX = "campaign:"
    LABEL_LIMIT = 200
    SLUG_CEILING = 24
    RESERVED = ("campaign",)

    def __init__(self, spent=(), findings=(), pool_why=None, slug_ok=True):
        self.spent, self.findings = list(spent), list(findings)
        self.pool_why, self._slug_ok = pool_why, slug_ok
        self.asked = []

    def name_rule(self):
        return self

    def slug_ok(self, slug):
        return self._slug_ok

    def spent_slugs(self, repo, limit):
        self.asked.append(("spent_slugs", repo, limit))
        if self.pool_why:
            return None, 0, self.pool_why
        return self.spent, len(self.spent), None

    def shape_findings(self, kind, title, body, want_plan, names=()):
        self.asked.append(("shape_findings", kind, title, body, want_plan,
                           tuple(names)))
        return self.findings


class FakeClaim:
    """campaign-claim.py's one pure function this script asks for."""

    @staticmethod
    def branch_name(slug, issue, topic):
        return f"{slug}/{issue}-{topic}"


class Ran:
    """The recorder that stands in for `run`: every call's argv as one line,
    answered by the first key that is a substring of it.

    An answer is `(rc, stdout, stderr)` or a callable over the argv, for the
    one answer that has to write what its real counterpart writes. An
    unanswered call comes back empty and successful, which makes every reader
    of a WORD stop rather than pass -- an unarranged call cannot look like a
    reading that went well."""

    def __init__(self, answers):
        self.answers, self.seen = list(answers), []

    def __call__(self, *args, **kw):
        line = " ".join(str(a) for a in args)
        self.seen.append(line)
        for key, answer in self.answers:
            if key in line:
                rc, out, err = answer(args) if callable(answer) else answer
                return subprocess.CompletedProcess(args, rc, out, err)
        return subprocess.CompletedProcess(args, 0, "", "")

    def writes(self):
        """Every `gh` call that WRITES, in the order it was made. What most of
        these cases assert is that this list is empty, or that it is these
        three in this order."""
        return [line for line in self.seen
                if line.startswith("gh ")
                and (" label create " in line or " issue create " in line)]

    def count(self, key):
        return len([line for line in self.seen if key in line])


def answers(base, repos="", label_create=(0, "", ""), chore_create=(0, "", ""),
            bound=(0, "here\n", ""), mark=None, directory=(1, "none\n", "")):
    """The happy path's answers, each overridable by one keyword.

    `base` is the temporary directory git is made to name, so the campaign
    directory this script composes lands there and nowhere near a real base."""
    def marked(args):
        target = Path(args[-1])
        (target / ".campaign").write_text(f"{args[2]} {args[3]}\n")
        return 0, f"{target}\n", ""

    return [
        ("campaign-directory.py mark", mark or marked),
        ("campaign-directory.py", directory),
        ("campaign-repos.py", (0, repos, "")),
        ("campaign-issues", (0, "read 0 open campaign issue(s)\n", "")),
        ("gh label create campaign:", label_create),
        ("gh label create chore", chore_create),
        ("gh issue create", (0, f"{URL}\n", "")),
        ("--json labels,parent", (0, json.dumps(
            {"labels": [{"name": n} for n in
                        ("campaign", "chore", f"campaign:{SLUG}")],
             "parent": None}), "")),
        ("--json body", (0, BODY, "")),
        ("campaign-tracker.py bind", (0, "read #500: chore\n", "")),
        ("campaign-tracker.py bound", bound),
        ("rev-parse --path-format", (0, f"{base}/.git\n", "")),
        ("campaign-claim.py take", (0, f"cut {SLUG}/{NUMBER}-{SLUG}\n", "")),
        ("acquire-repo.sh", (0, "", "acquire-repo: ready\n")),
    ]


def open_chore(m, ran, tracker, argv, env=()):
    """(exit status, stdout, stderr) from one run of the script's own `main`,
    with the module's three seams replaced for the duration."""
    m.run, m.TRACKER, m.claim_module = ran, tracker, lambda: FakeClaim
    saved_argv, saved_env = sys.argv, dict(os.environ)
    sys.argv = ["campaign-open.py", *argv]
    os.environ.update(env)
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = m.main()
    finally:
        sys.argv = saved_argv
        os.environ.clear()
        os.environ.update(saved_env)
    return rc, out.getvalue(), err.getvalue()


def a_chore(d, body=BODY):
    """A body file in `d`, and the argv that opens a chore from it."""
    path = Path(d) / "chore.md"
    path.write_text(body)
    return ["--chore", SLUG, "--title", "Do the thing", "--body-file", str(path)]


def main() -> int:
    print(f"reading {OPEN_PY}")
    # A SUITE RUN INSIDE HERDR MUST NOT INHERIT ITS PANE: the naming step reads
    # these two, and a case that expected no rename would silently run one.
    for name in ("HERDR_ENV", "HERDR_PANE_ID"):
        os.environ.pop(name, None)
    m = harness.load(OPEN_PY, "campaign_open")

    # ---------------------------------------------------- the flag is the gate
    with tempfile.TemporaryDirectory() as d:
        ran = Ran([])
        rc, out, err = open_chore(m, ran, FakeTracker(),
                                  a_chore(d)[2:])          # no --chore
        check("without --chore it refuses and runs nothing at all",
              rc == 2 and "opening-campaign" in err and ran.seen == [],
              f"exit {rc}: {err[:200]} {ran.seen}")

    # ------------------------------ step 1 stops BEFORE anything is written --
    # Four readings, four ways for the same property to fail: a chore that
    # would be malformed costs no label, no issue and no directory.
    stops = {
        "a slug the name rule refuses":
            (FakeTracker(slug_ok=False), {}, "is not a slug"),
        "a slug that is already spent":
            (FakeTracker(spent=[SLUG]), {}, "is spent already"),
        "a pool that would not read":
            (FakeTracker(pool_why="gh did not answer"), {}, "did not answer"),
        "a finding on the title or the body":
            (FakeTracker(findings=["no `## Repos` section"]), {},
             "1 finding(s)"),
        "a `## Repos` list the reader refuses":
            (FakeTracker(), {"campaign-repos.py": (1, "", "REFUSE: `* a/b`")},
             "did not read"),
    }
    for why, (tracker, override, says) in stops.items():
        with tempfile.TemporaryDirectory() as d:
            table = answers(d)
            for key, answer in override.items():
                table = [(k, answer if k == key else a) for k, a in table]
            ran = Ran(table)
            rc, out, err = open_chore(m, ran, tracker, a_chore(d))
            check(f"{why} stops step 1, with no gh write and no directory",
                  rc == 1 and says in (out + err) and ran.writes() == []
                  and not list(Path(d).glob("campaign-*")),
                  f"exit {rc}: {err[:200]} | writes {ran.writes()}")

    # THE SHAPE IS ASKED FOR THE CHORE KIND, with the three labels the create
    # is about to file: `shape_findings` reads the `chore` beside `standing`
    # case off that list, so a caller passing no labels asks a narrower
    # question than the one this script needs answered.
    with tempfile.TemporaryDirectory() as d:
        tracker = FakeTracker()
        ran = Ran(answers(d))
        rc, out, err = open_chore(m, ran, tracker, a_chore(d))
        asked = [a for a in tracker.asked if a[0] == "shape_findings"]
        check("the shape is asked once, for the chore kind and the three labels",
              len(asked) == 1 and asked[0][1] == FakeTracker.CHORE
              and asked[0][2] == "Do the thing" and asked[0][4] is False
              and asked[0][5] == ("campaign", "chore", f"campaign:{SLUG}"),
              f"{asked}")

    # ------------------------------------------------- step 3, the two creates
    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        wrote = ran.writes()
        check("the slug's label is minted before the issue", len(wrote) == 3
              and wrote[0].startswith(f"gh label create campaign:{SLUG}")
              and wrote[1].startswith("gh label create chore")
              and wrote[2].startswith("gh issue create")
              and "--force" not in " ".join(wrote), f"{wrote}")

    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d, label_create=(
            1, "", "failed to create label: already exists")))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        check("a slug label that already exists stops, and files no issue",
              rc == 1 and ran.count("gh issue create") == 0
              and "uniqueness gate" in err,
              f"exit {rc}: {err[:200]} | {ran.writes()}")

    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d, chore_create=(
            1, "", "failed to create label: already exists")))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        check("the `chore` label already existing is not a stop",
              rc == 0 and "gates nothing" in out and ran.count("gh issue create") == 1,
              f"exit {rc}: {err[:200]}")

    # A CREATE THAT FAILS AFTER THE SLUG LABEL WAS MINTED takes the label back,
    # or the resume line it prints refuses at step 1 as a spent slug (pr#478).
    with tempfile.TemporaryDirectory() as d:
        ran = Ran([("gh issue create", (1, "", "boom"))] + answers(d))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        check("a failed issue create deletes the slug label this run minted",
              rc == 1 and ran.count(f"gh label delete campaign:{SLUG}") == 1
              and "runs as printed" in err and "--issue" not in err,
              f"exit {rc}: {err[:300]} | {ran.seen}")
        check("...and no longer lists the label as done",
              f"`campaign:{SLUG}` label exists" not in err, err[:300])
    with tempfile.TemporaryDirectory() as d:
        ran = Ran([("gh issue create", (1, "", "boom")),
                   ("gh label delete", (1, "", "nope"))] + answers(d))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        check("...and a delete that fails says the resume line will refuse, "
              "with the command", rc == 1 and "could NOT be deleted" in err
              and f"gh label delete campaign:{SLUG}" in err, err[:400])

    # ------------------------------------------------------- the happy path --
    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        made = sorted(Path(d).glob("campaign-demo-*"))
        target = made[0] if made else Path(d)
        check("a repo-less chore opens: one directory, marked, named for the slug",
              rc == 0 and len(made) == 1
              and (target / ".campaign").read_text() == f"{NUMBER} {SLUG}\n",
              f"exit {rc}: {err[:300]} | {made}")
        check("...with the body GitHub stored as README.md and as the derived copy",
              (target / "README.md").read_text() == BODY
              and (target / "runtime/campaign-issue-body-derived.md"
                   ).read_text() == BODY,
              f"{sorted(p.name for p in target.iterdir())}")
        check("...with runtime/repos written and no repos.tmp left behind",
              (target / "runtime/repos").read_text() == ""
              and not (target / "runtime/repos.tmp").exists(),
              f"{sorted(p.name for p in (target / 'runtime').iterdir())}")
        check("...with both per-issue templates removed from the copy",
              not (target / "sub-issue.md").exists()
              and not (target / "chore.md").exists()
              and (target / "scripts").is_dir(),
              f"{sorted(p.name for p in target.iterdir())}")
        check("...and the claim taken on the campaign issue as its own issue",
              ran.count("campaign-claim.py take") == 1
              and f"take {NUMBER} {NUMBER} {SLUG}" in " ".join(ran.seen)
              and "--repo" not in
              [line for line in ran.seen if "take" in line][0],
              f"{[line for line in ran.seen if 'take' in line]}")
        check("...acquiring nothing, and saying so, because `## Repos` is none",
              ran.count("acquire-repo.sh") == 0
              and "no repository acquired" in out, out[-400:])
        check("...and the summary line names the issue, the directory and the branch",
              f"chore#{NUMBER} {URL}" in out and str(target) in out
              and f"branch {SLUG}/{NUMBER}-{SLUG}" in out, out[-400:])

    # ------------------------------------------------------ the two rollbacks
    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d, mark=(2, "unknown\n", "two directories name that "
                                                   "campaign")))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        check("a mark that refuses takes this run's own directory with it",
              rc == 1 and not list(Path(d).glob("campaign-*"))
              and "was removed" in err and "chore#500 is filed" in err,
              f"exit {rc}: {err[:300]} | {list(Path(d).glob('campaign-*'))}")

    with tempfile.TemporaryDirectory() as d:
        argv = a_chore(d)
        ran = Ran(answers(d))
        # The name this run would compose, already taken by something the
        # marker read says is no campaign's.
        squatter = Path(d) / f"campaign-{SLUG}-{time.strftime('%y%m%d')}"
        squatter.mkdir()
        (squatter / "README.md").write_text("somebody else's\n")
        rc, out, err = open_chore(m, ran, FakeTracker(), argv)
        check("a directory of that name carrying no marker is not written into",
              rc == 1 and "not this campaign's" in err
              and (squatter / "README.md").read_text() == "somebody else's\n"
              and not (squatter / "runtime").exists(),
              f"exit {rc}: {err[:300]}")

    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d, bound=(0, "elsewhere otherbox\n", "")))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        check("`bound` reading `elsewhere` stops before the scaffold",
              rc == 1 and "elsewhere otherbox" in err
              and ran.count("campaign-directory.py") == 0
              and not list(Path(d).glob("campaign-*")),
              f"exit {rc}: {err[:300]}")

    # --------------------------------------------------------- --issue resumes
    with tempfile.TemporaryDirectory() as d:
        tracker = FakeTracker(spent=[SLUG])
        ran = Ran(answers(d))
        rc, out, err = open_chore(m, ran, tracker, a_chore(d) +
                                  ["--issue", NUMBER])
        check("--issue skips the pool, the survey and both creates, and goes on",
              rc == 0 and ran.writes() == [] and ran.count("campaign-issues") == 0
              and [a for a in tracker.asked if a[0] == "spent_slugs"] == []
              and ran.count("campaign-claim.py take") == 1,
              f"exit {rc}: {err[:300]} | {ran.writes()}")

    # ------------------------------------------- several repositories cut none
    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d, repos="one/a\ntwo/b\n"))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        takes = [line for line in out.splitlines() if " take " in line]
        check("several `## Repos` entries cut no ref and print one take line each",
              rc == 0 and ran.count("campaign-claim.py take") == 0
              and len(takes) == 3
              and [line.rsplit(" ", 1)[-1] for line in takes]
              == ["one/a", "two/b", "kalaluthien/campaign-base"],
              f"exit {rc}: {takes}")
        topics = [line.split()[-3] for line in takes]
        check("...each under a topic of its own, since a ref's name is how "
              "release finds its repository",
              len(set(topics)) == 3 and all(t.endswith(n) for t, n in
                                            zip(topics, ("-a", "-b", "-campaign-base"))),
              f"{topics}")
        check("...and each entry is acquired, once, under repos/<name>",
              ran.count("acquire-repo.sh") == 2
              and str(Path(d)) in " ".join(ran.seen)
              and ran.count("repos/a") == 1 and ran.count("repos/b") == 1,
              f"{[line for line in ran.seen if 'acquire' in line]}")

    # one entry is unambiguous, so it IS cut, and `--repo` names where
    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d, repos="one/a\n"))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        taken = [line for line in ran.seen if "campaign-claim.py take" in line]
        check("one `## Repos` entry is unambiguous, so the claim is cut there",
              rc == 0 and len(taken) == 1 and taken[0].endswith("--repo one/a")
              and ran.count("acquire-repo.sh") == 1, f"{taken}")

    # ------------------------------------------------------- step 8, the name
    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d))
        check("outside herdr the rename is printed, not run, and said to be unrun",
              rc == 0 and ran.count("campaign-name-session.py") == 0
              and "NOT named" in out and f"{SLUG}-worker-1" in out,
              f"exit {rc}: {out[-400:]}")

    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d))
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d),
                                  env={"HERDR_ENV": "1",
                                       "HERDR_PANE_ID": "%9"})
        named = [line for line in ran.seen if "campaign-name-session.py" in line]
        check("inside herdr the session is named <slug>-worker-1 for its pane",
              rc == 0 and len(named) == 1
              and named[0].endswith(f"%9 {SLUG}-worker-1"), f"{named}")

    with tempfile.TemporaryDirectory() as d:
        ran = Ran(answers(d) + [("campaign-name-session.py",
                                 (1, "", "FAILED: herdr refused"))])
        rc, out, err = open_chore(m, ran, FakeTracker(), a_chore(d),
                                  env={"HERDR_ENV": "1",
                                       "HERDR_PANE_ID": "%9"})
        check("a rename that FAILED stops the run before the claim",
              rc == 1 and ran.count("campaign-claim.py take") == 0
              and "old name" in err and "resume with" in err,
              f"exit {rc}: {err[:300]}")

    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
