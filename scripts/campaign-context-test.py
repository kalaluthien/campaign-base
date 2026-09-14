#!/usr/bin/env python3
# witnesses: SessionCompactsBetweenSubIssues
"""Cases for campaign-context.py, over a stubbed `gh` on PATH answering from
fixture JSON.

The stub answers exactly the calls listed in its case's `gh.json`, logs every
call it was asked, and fails any other -- so a reading the script was not
supposed to make shows up as an `unread` section and a non-zero exit, and one it
must not make at all (a bare `#N`) is asserted on the log, never on the output.

Usage: scripts/campaign-context-test.py
"""
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTEXT = HERE / "campaign-context.py"
ASSIGN = HERE / "campaign-assign.py"

harness = importlib.import_module("suite-harness-test")
check = harness.check

GH = r'''#!/usr/bin/env python3
import json, sys
from pathlib import Path
home = Path(sys.argv[0]).parent
key = " ".join(sys.argv[1:])
with open(home / "gh.log", "a") as f:
    f.write(key + "\n")
table = json.loads((home / "gh.json").read_text())
if key not in table:
    sys.stderr.write("no fixture for: " + key + "\n")
    sys.exit(1)
sys.stdout.write(json.dumps(table[key]))
'''

R = "o/base"


def comment(cid, when, body, kind="issuecomment", thread="issues/7"):
    return {"id": cid, "created_at": when, "submitted_at": when, "body": body,
            "user": {"login": "someone"},
            "html_url": f"https://github.com/{R}/{thread}#{kind}-{cid}"}


def view(body, parent=2):
    return {"body": body, "url": f"https://github.com/{R}/issues/7",
            "parent": {"number": parent} if parent else None}


def comments_call(n, repo=R):
    return f"api --paginate repos/{repo}/issues/{n}/comments?per_page=100"


def reviews_call(n, repo=R):
    return f"api --paginate repos/{repo}/pulls/{n}/reviews?per_page=100"


VIEW = "issue view 7 -R o/base --json body,url,parent"
BODY = ("## Intent\n\n- see rc#3 and pr#5; the bare #9 and o/other#6 name "
        "no campaign, and rc#2 and rc#7 are the parent and the issue itself; "
        "other#3 is rc#3 again\n\n"
        "## Lands in\n\n- none\n")
LONG = "x" * 5000


def world():
    """The fixture every case starts from; a case edits its own copy."""
    return {
        VIEW: view(BODY),
        comments_call(7): [
            comment(103, "2026-09-03T00:00:00Z",
                    "NOTE rc-worker-1: see rc#4 as well\n\n" + LONG),
            comment(101, "2026-09-01T00:00:00Z",
                    "DECISION owner: keep the ceiling\n\nbecause it is cheap"),
            comment(102, "2026-09-02T00:00:00Z", "just chatter, no kind"),
        ],
        comments_call(3): [
            comment(301, "2026-08-01T00:00:00Z",
                    "DECISION owner: three is decided", thread="issues/3"),
            comment(302, "2026-08-02T00:00:00Z",
                    "REPORT rc-worker-2: a report, not followed",
                    thread="issues/3"),
        ],
        comments_call(4): [],
        comments_call(5): [
            comment(501, "2026-08-05T00:00:00Z",
                    "REVIEW rc-worker-9: pr#5 at abc, 0 defects",
                    thread="pull/5"),
            comment(502, "2026-08-06T00:00:00Z",
                    "NOTE rc-worker-9: a note on a PR, not followed",
                    thread="pull/5"),
        ],
        # A review body has `submitted_at` and no `created_at`.
        reviews_call(5): [{"id": 551, "submitted_at": "2026-08-07T00:00:00Z",
                           "body": "REVIEW rc-worker-8: from gh pr review",
                           "user": {"login": "someone"},
                           "html_url": f"https://github.com/{R}/pull/5"
                                       "#pullrequestreview-551"}],
        comments_call(2): [
            comment(201, "2026-09-04T00:00:00Z",
                    "NOTE rc-planner-1: one carried item for rc#7",
                    thread="issues/2"),
            comment(202, "2026-09-04T01:00:00Z",
                    "NOTE rc-planner-1: about rc#8 only", thread="issues/2"),
            comment(203, "2026-09-04T02:00:00Z",
                    "DECISION owner: rc#70 is another issue",
                    thread="issues/2"),
        ],
    }


def run(table, *args):
    """(completed process, the gh calls made) for one run over `table`."""
    with tempfile.TemporaryDirectory() as d:
        bin_dir = Path(d) / "bin"
        harness.fake(bin_dir, "gh", GH)
        (bin_dir / "gh.json").write_text(json.dumps(table))
        env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
        r = subprocess.run([sys.executable, str(CONTEXT), *(args or ("7", R))],
                           capture_output=True, text=True, env=env, cwd=d)
        log = bin_dir / "gh.log"
        return r, (log.read_text().splitlines() if log.exists() else [])


def section(out, n):
    """The text of section `n`, from its heading to the next one."""
    start = out.find(f"== {n}.")
    end = out.find(f"== {n + 1}.")
    return out[start:end if end > start else len(out)] if start >= 0 else ""


def cases():
    r, calls = run(world())
    out = r.stdout
    one, two, three = section(out, 1), section(out, 2), section(out, 3)

    check("every reading made: exit 0", r.returncode == 0,
          f"rc {r.returncode}: {r.stderr}{out[-400:]}")
    check("the three sections print in their fixed order",
          0 <= out.find("== 1.") < out.find("== 2.") < out.find("== 3."), out)

    check("an own DECISION is a row: kind, author, date, comment id, first line",
          "DECISION owner 2026-09-01 issuecomment-101: keep the ceiling" in one
          and "because it is cheap" in one, one)
    check("an own comment opening with no kind is not a row",
          "chatter" not in out, one)
    check("own rows are oldest first",
          0 <= one.find("issuecomment-101") < one.find("issuecomment-103"), one)
    check("section 1 says what it read and from where",
          comments_call(7).split(" ", 2)[2] in one and "3 comment(s)" in one, one)

    m = harness.load(CONTEXT, "campaign_context")
    cap = m.COMMENT_CAP
    check("a body over the cap is cut, the cap printed beside its measurement",
          f"{len(LONG)} chars, cut at {cap}" in one
          and "x" * (cap + 1) not in one, one[-400:])

    check("a cited pr#N's REVIEW is a row", "issuecomment-501" in two, two)
    check("a cited pr#N's NOTE is not", "issuecomment-502" not in two, two)
    check("a review body is a row, dated by submitted_at",
          "REVIEW rc-worker-8 2026-08-07 pullrequestreview-551" in two, two)
    check("one number cited under two slugs is read and printed once",
          sum(c == comments_call(3) for c in calls) == 1
          and two.count("issuecomment-301") == 1, calls)
    check("a cited slug#N's DECISION is a row, its REPORT is not",
          "issuecomment-301" in two and "issuecomment-302" not in two, two)
    check("a slug#N cited by an own comment is followed, and empty prints empty",
          "rc#4" in two and "(empty)" in two.split("rc#4", 1)[-1], two)
    check("a bare #N and an owner/repo#N are never read",
          not any("/issues/9/" in c or "/issues/6/" in c for c in calls), calls)
    check("the parent and the issue itself are not followed as citations",
          sum(c == comments_call(2) for c in calls) == 1
          and sum(c == comments_call(7) for c in calls) == 1, calls)

    check("the campaign issue's NOTE naming this issue is a row, the heading "
          "naming the issue in full", "issuecomment-201" in three
          and f"citing {R}#7" in three, three)
    check("the campaign issue's comments naming another issue are not",
          "issuecomment-202" not in three and "issuecomment-203" not in three,
          three)

    # A pull request is read on the repository the sub-issue lands in.
    t = world()
    t[VIEW] = view(BODY.replace("- none", "- o/member"))
    t[comments_call(5, "o/member")] = t.pop(comments_call(5))
    t[reviews_call(5, "o/member")] = t.pop(reviews_call(5))
    r, calls = run(t)
    check("pr#N is read on the ## Lands in repository",
          r.returncode == 0 and "issuecomment-501" in section(r.stdout, 2),
          f"rc {r.returncode} {calls}")

    # A reading that failed is `unread` in its own section and exits non-zero.
    t = world()
    del t[reviews_call(5)]
    r, _ = run(t)
    two = section(r.stdout, 2)
    check("a failed gh read prints unread for that section and exits non-zero",
          r.returncode != 0 and "unread" in two.split("pr#5", 1)[-1]
          and "issuecomment-201" in section(r.stdout, 3),
          f"rc {r.returncode}: {r.stdout[-600:]}")

    # No comments, no citations, no parent: three empty sections, exit 0.
    t = {VIEW: view("## Lands in\n\n- none\n", parent=None), comments_call(7): []}
    r, _ = run(t)
    check("an empty section prints as empty",
          r.returncode == 0 and all("(empty" in section(r.stdout, n)
                                    for n in (1, 2, 3)),
          f"rc {r.returncode}: {r.stdout}")

    # A cited thread over the ceiling: the hop yields to own and campaign
    # rows, keeps its newest, and names its thread.
    ceiling = m.ROW_CEILING
    t = world()
    t[comments_call(3)] = [
        comment(900 + i, f"2026-08-01T00:{i:02d}:00Z",
                f"DECISION owner: item {i}", thread="issues/3")
        for i in range(ceiling)]
    r, _ = run(t)
    rows = [ln for ln in r.stdout.splitlines() if ln.startswith("- ")]
    two = section(r.stdout, 2)
    check("rows past the ceiling are cut from the hop, newest kept, thread named",
          len(rows) == ceiling and "cut by the ceiling of" in two
          and f"https://github.com/{R}/issues/3" in two
          and f"issuecomment-{900 + ceiling - 1}" in two
          and "issuecomment-900:" not in two, f"{len(rows)} rows: {two[-500:]}")
    check("own and campaign rows survive a hop over the ceiling",
          "issuecomment-101" in section(r.stdout, 1)
          and "issuecomment-201" in section(r.stdout, 3), r.stdout[-500:])

    # The assignment sentence tells the session to run this first.
    a = harness.load(ASSIGN, "campaign_assign")
    sentence = a.prompt_for(R, "42")
    check("campaign-assign's prompt runs campaign-context.py by its absolute "
          "path first, in one sentence",
          f"{CONTEXT} 42" in sentence
          and sentence.count(". ") == 0, sentence)


def main():
    cases()
    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
