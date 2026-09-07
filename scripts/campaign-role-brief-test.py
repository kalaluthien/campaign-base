#!/usr/bin/env python3
"""Cases for campaign-role-brief.py, run against a fake `herdr` on PATH.

The subject lives under the skill it briefs (#227); this suite stays here,
where CI's `scripts/*-test.*` loop finds it, and resolves its subject by path
as campaign-name-session-test.py does. Every case runs the REAL SKILL.md and
the REAL references -- the brief's content is the artifact, and a fixture
standing in for it would leave the shipped text covered by nothing.

Each case pins ONE branch. The three the suite exists for, because each is an
absence that reads like the others: a session herdr does not name (looked and
found nothing), a herdr that would not answer (could not look), and a record
that matched (looked, found, and deliberately said nothing).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SCRIPT = (BASE / ".claude" / "skills" / "assuming-role" / "scripts"
          / "campaign-role-brief.py")

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["agent", "list"]:
    if os.environ.get("FAKE_LIST_FAILS"):
        print("list broke", file=sys.stderr); sys.exit(1)
    print(json.dumps({"result": {"agents":
          json.loads(os.environ.get("FAKE_AGENTS", "[]"))}}))
else:
    sys.exit(1)
'''

# The campaign AGENTS.md a scaffolded campaign holds: the three sections #227
# put in `opening-campaign/assets/agents/*`, each with a marker no other
# briefed file contains, so a case can say WHICH section was emitted.
CAMPAIGN_AGENTS = """# Campaign principles: test

## Every session

EVERY-MARK

## Planner

PLANNER-MARK

## Worker

WORKER-MARK
"""

def row(session_id, name="demo-worker-10"):
    return [{"pane_id": "w1:p1", "name": name,
             "agent_session": {"value": session_id}}]


def run(payload=None, argv=(), agents=None, list_fails=False, no_herdr=False,
        campaign_agents=CAMPAIGN_AGENTS, record=None, lock_runtime=False,
        raw=None, record_swallows=False):
    """(completed process, the record's text or None, the campaign dir)."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        bin_dir = d / "bin"
        bin_dir.mkdir()
        if not no_herdr:
            fake = bin_dir / "herdr"
            fake.write_text(FAKE)
            fake.chmod(0o755)
        # THE TEMPDIR IS ITSELF A BASE, so `record_path`'s walk stops here
        # rather than in the repository under test. Without it the
        # no-campaign-AGENTS.md case wrote a record into this checkout's own
        # `runtime/briefed/`, which is a suite editing its subject's tree.
        (d / "AGENTS.md").write_text("# outer\n")
        (d / "runtime").mkdir()
        camp = d / "dated"
        (camp / "runtime").mkdir(parents=True)
        if campaign_agents is not None:
            (camp / "AGENTS.md").write_text(campaign_agents)
        if record is not None:
            rec = camp / "runtime" / "briefed"
            rec.mkdir(parents=True)
            (rec / record[0]).write_text(record[1])
        if record_swallows:
            # A record that accepts every write and reads back empty. It is the
            # only shape that separates `written` from `written and read back`:
            # an OSError gives `not written`, and nothing else can make a
            # successful write come back wrong.
            rec = camp / "runtime" / "briefed"
            rec.mkdir(parents=True, exist_ok=True)
            (rec / "1111-2222").symlink_to("/dev/null")
        if lock_runtime:
            (camp / "runtime").chmod(0o500)
        env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                   FAKE_AGENTS=json.dumps(agents or []),
                   CLAUDE_PROJECT_DIR=str(camp))
        if list_fails:
            env["FAKE_LIST_FAILS"] = "1"
        if payload is not None and payload.get("session_id"):
            env["CLAUDE_CODE_SESSION_ID"] = payload["session_id"]
        r = subprocess.run(
            [sys.executable, str(SCRIPT), *argv], env=env, cwd=str(camp),
            input=(raw if raw is not None
                   else ("" if payload is None else json.dumps(payload))),
            capture_output=True, text=True)
        if lock_runtime:
            (camp / "runtime").chmod(0o700)
        recs = [q for root in (camp, d)
                for q in sorted((root / "runtime" / "briefed").glob("*"))]
        where = recs[0].parent.parent.parent if recs else None
        return r, (recs[0].read_text() if recs else None), where


SID = "1111-2222"
NAMED = row(SID)


def main():
    ran, fails = [], []

    def check(name, cond, detail=""):
        ran.append(name)
        if not cond:
            fails.append(f"{name}  {detail}".rstrip())

    # ---- the three readings, through --role ----

    r, _, _ = run({"session_id": SID}, argv=["--role"], agents=NAMED)
    check("--role prints the role and the campaign bounding it",
          r.returncode == 0 and r.stdout.strip() == "worker demo",
          f"exit {r.returncode} out {r.stdout!r}")

    # THE RETIRED TOKEN NAMES NO CAMPAIGN SINCE #237, because `campaign_of`
    # no longer admits it -- and this reader asks that function rather than
    # reading the name itself, so the narrowing reached here with no edit. A
    # session still wearing the old name reads as NO ROLE, which is the
    # repair the brief names: rename it.
    r, _, _ = run({"session_id": SID}, argv=["--role"],
                  agents=row(SID, "campaign-1-worker-10"))
    check("a name in the retired `campaign-<N>` form reads as no role",
          r.stdout.startswith("no role read for"), f"out {r.stdout!r}")

    r, _, _ = run({"session_id": SID}, argv=["--role"], agents=[])
    check("a session herdr holds no row for reads as NO ROLE, naming the id",
          r.returncode == 0 and r.stdout.startswith("no role read for")
          and SID in r.stdout, f"out {r.stdout!r}")

    r, _, _ = run({"session_id": SID}, argv=["--role"],
                  agents=row(SID, name="some-other-session"))
    check("...and so does a row whose name is of no campaign shape, which "
          "names the name it read",
          r.returncode == 0 and r.stdout.startswith("no role read for")
          and "some-other-session" in r.stdout, f"out {r.stdout!r}")

    r, _, _ = run({"session_id": SID}, argv=["--role"], agents=NAMED,
                  list_fails=True)
    check("a herdr that will not answer is COULD NOT LOOK, not no-role",
          r.returncode == 0 and r.stdout.startswith("could not"),
          f"out {r.stdout!r}")

    # ---- what fires, and what does not ----

    r, rec, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                     "session_id": SID, "agent_id": "sub-1"}, agents=NAMED)
    check("a subagent is briefed by its parent and gets nothing, recorded "
          "nothing",
          r.returncode == 0 and r.stdout == "" and rec is None
          and "subagent" in r.stderr, f"out {r.stdout!r} err {r.stderr!r}")

    r, stamp, _ = run({"hook_event_name": "UserPromptSubmit",
                       "session_id": SID}, agents=NAMED)
    check("UserPromptSubmit with no record emits, and writes one",
          r.returncode == 0 and "WORKER-MARK" in r.stdout
          and stamp is not None and stamp.startswith("worker demo "),
          f"out {r.stdout[:80]!r} rec {stamp!r}")

    # THE RECORD THE SESSION ALREADY HAS. Recording the CURRENT stamp is the
    # whole case: a stale one would short-circuit nothing, so a SessionStart
    # that consulted the record would pass against it and this loop would
    # measure the four `source` words and not the rule they are about.
    for source in ("startup", "resume", "clear", "compact"):
        r, rec, _ = run({"hook_event_name": "SessionStart", "source": source,
                         "session_id": SID}, agents=NAMED, record=(SID, stamp))
        check(f"SessionStart source={source} emits with the CURRENT stamp "
              f"already recorded",
              r.returncode == 0 and "WORKER-MARK" in r.stdout,
              f"out {r.stdout[:80]!r} rec {rec!r}")

    r, rec, _ = run({"hook_event_name": "SessionStart", "source": "compact",
                     "session_id": SID}, agents=NAMED,
                    record=(SID, "worker demo deadbeefdead"))
    check("...and rewrites a stale record to what it just briefed",
          rec == stamp, f"rec {rec!r} want {stamp!r}")
    r2, _, _ = run({"hook_event_name": "UserPromptSubmit", "session_id": SID},
                   agents=NAMED, record=(SID, stamp))
    check("...and emits NOTHING on the next turn, the record matching",
          r2.returncode == 0 and r2.stdout == ""
          and "already briefed" in r2.stderr,
          f"out {r2.stdout[:80]!r} err {r2.stderr!r}")

    # A RENAME IS ONE OF THE FOUR TRIGGERS #227 names, and it fires through
    # the stamp rather than through an event: herdr answers with the new name,
    # the role and campaign in the stamp move, and the next prompt re-briefs.
    r, rec, _ = run({"hook_event_name": "UserPromptSubmit", "session_id": SID},
                    agents=row(SID, "other-planner-3"), record=(SID, stamp))
    check("a session renamed into the other role re-briefs on its next prompt",
          "The planner's lifecycle" in r.stdout and "PLANNER-MARK" in r.stdout
          and rec.startswith("planner other "), f"out {r.stdout[:80]!r} rec {rec!r}")

    # THE STAMP IS A SHA AND NOT A LENGTH. This campaign AGENTS.md differs from
    # the one that produced `stamp` by exactly one character, in place -- so a
    # stamp carrying `len(text)` matches and this case is the only thing that
    # fails when the sha is put back to a length.
    edited = CAMPAIGN_AGENTS.replace("WORKER-MARK", "WORKER-MARX")
    r, _, _ = run({"hook_event_name": "UserPromptSubmit", "session_id": SID},
                  agents=NAMED, record=(SID, stamp), campaign_agents=edited)
    check("a same-length edit to a briefed file re-briefs, so the stamp is a "
          "sha and not a length",
          r.returncode == 0 and "WORKER-MARX" in r.stdout,
          f"out {r.stdout[:120]!r}")

    # ---- what the brief carries ----

    r, _, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                   "session_id": SID}, agents=NAMED)
    check("the brief carries the campaign's `## Every session` and the role's "
          "own section, and not the other role's",
          "EVERY-MARK" in r.stdout and "WORKER-MARK" in r.stdout
          and "PLANNER-MARK" not in r.stdout, f"out {r.stdout[-400:]!r}")
    check("...and the skill and the role's reference, without frontmatter",
          "Assuming a role" in r.stdout
          and "The worker's lifecycle" in r.stdout
          and "name: assuming-role" not in r.stdout,
          f"out {r.stdout[:200]!r}")

    r, _, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                   "session_id": SID}, agents=row(SID, "other-planner-3"))
    check("a planner gets the planner reference and the planner section",
          "The planner's lifecycle" in r.stdout and "PLANNER-MARK" in r.stdout
          and "WORKER-MARK" not in r.stdout
          and "planner of campaign `other`" in r.stdout,
          f"out {r.stdout[:200]!r}")

    # A HEADING INSIDE A FENCE IS TEXT. A campaign document quoting `## Worker`
    # in an example used to open the section there and emit the rest of the
    # file, this marker included.
    fenced = CAMPAIGN_AGENTS.replace("PLANNER-MARK", """```
## Worker
FENCE-MARK
```""")
    r, _, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                   "session_id": SID}, agents=NAMED, campaign_agents=fenced)
    check("a `## Worker` inside a fenced block opens nothing",
          "FENCE-MARK" not in r.stdout and "WORKER-MARK" in r.stdout,
          f"out {r.stdout[-300:]!r}")

    # AN OPENER WITH NO CLOSER IS NOT A FENCE. Both directions are silent
    # failures: one before the role heading drops the campaign's section
    # entirely, one inside it emits to end of file.
    stray_before = CAMPAIGN_AGENTS.replace("PLANNER-MARK", "```\nPLANNER-MARK")
    r, _, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                   "session_id": SID}, agents=NAMED,
                  campaign_agents=stray_before)
    check("an unclosed fence before the role's heading does not hide it",
          "WORKER-MARK" in r.stdout, f"out {r.stdout[-200:]!r}")

    stray_inside = (CAMPAIGN_AGENTS.replace("WORKER-MARK", "```\nWORKER-MARK")
                    + "\n# Later\n\nTAIL-MARK\n")
    r, _, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                   "session_id": SID}, agents=NAMED,
                  campaign_agents=stray_inside)
    check("...and one inside it does not run the section to end of file",
          "WORKER-MARK" in r.stdout and "TAIL-MARK" not in r.stdout,
          f"out {r.stdout[-200:]!r}")

    # UP TO THREE SPACES IS STILL A HEADING (CommonMark), and a campaign
    # document is somebody's prose.
    indented = CAMPAIGN_AGENTS + "\n   # Later\n\nTAIL-MARK\n"
    r, _, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                   "session_id": SID}, agents=NAMED, campaign_agents=indented)
    check("a heading indented three spaces still closes the section",
          "WORKER-MARK" in r.stdout and "TAIL-MARK" not in r.stdout,
          f"out {r.stdout[-200:]!r}")

    # A LEVEL-1 HEADING ENDS THE SECTION. `## Worker` is the template's last
    # section, so whatever a campaign appends after it is what this protects.
    tail = CAMPAIGN_AGENTS + "\n# Notes of our own\n\nTAIL-MARK\n"
    r, _, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                   "session_id": SID}, agents=NAMED, campaign_agents=tail)
    check("a `# ` heading after the role's section closes it",
          "WORKER-MARK" in r.stdout and "TAIL-MARK" not in r.stdout,
          f"out {r.stdout[-300:]!r}")

    # ...AND A `###` DOES NOT: a subheading belongs to its section.
    sub = CAMPAIGN_AGENTS.replace("WORKER-MARK",
                                  "WORKER-MARK\n\n### Detail\n\nSUB-MARK")
    r, _, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                   "session_id": SID}, agents=NAMED, campaign_agents=sub)
    check("a `###` subheading stays inside the role's section",
          "SUB-MARK" in r.stdout, f"out {r.stdout[-300:]!r}")

    r, rec, where = run({"hook_event_name": "SessionStart", "source": "startup",
                         "session_id": SID}, agents=NAMED, campaign_agents=None)
    check("a campaign with no AGENTS.md of its own still gets the skill's "
          "brief",
          r.returncode == 0 and "The worker's lifecycle" in r.stdout
          and "WORKER-MARK" not in r.stdout, f"out {r.stdout[:120]!r}")
    # THE RECORD'S FALLBACK, which nothing asserted: the walk takes the NEAREST
    # ancestor holding both `AGENTS.md` and `runtime/`, so a directory that is
    # not a campaign does not capture the record and the last resort is not the
    # repository the script happens to live in.
    check("...and its record lands at the nearest ancestor that has both, not "
          "in the campaign directory that has only one",
          rec is not None and where is not None
          and where.name != "dated"
          and str(where).startswith("/") and "campaign-base" not in str(where),
          f"rec {rec!r} at {where}")

    # ---- an ack is not a write, and no path walls the session ----

    r, rec, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                     "session_id": SID}, agents=NAMED, lock_runtime=True)
    check("a record that could not be written is EMITTED anyway and the "
          "verdict line says it was not written",
          r.returncode == 0 and "WORKER-MARK" in r.stdout
          and "not written" in r.stderr, f"err {r.stderr!r}")

    r, rec, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                     "session_id": SID}, agents=NAMED)
    check("...and one that was written says it was READ BACK, not merely sent",
          "written and read back" in r.stderr, f"err {r.stderr!r}")

    r, rec, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                     "session_id": SID}, agents=NAMED, record_swallows=True)
    check("a record that ACKS the write and holds nothing is reported as read "
          "back different, not as written",
          r.returncode == 0 and "read back different" in r.stderr,
          f"err {r.stderr!r}")

    r, rec, _ = run({"hook_event_name": "UserPromptSubmit", "session_id": SID},
                    agents=NAMED, no_herdr=True)
    check("no herdr on PATH at all: exit 0, no brief, no traceback",
          r.returncode == 0 and r.stdout == "" and "Traceback" not in r.stderr
          and rec is None, f"exit {r.returncode} err {r.stderr[:200]!r}")

    r, rec, _ = run(agents=NAMED, raw="{not json at all")
    check("a payload that will not READ is its own branch, distinct from one "
          "that read and carried nothing",
          r.returncode == 0 and r.stdout == ""
          and "would not read" in r.stderr, f"err {r.stderr!r}")

    r, rec, _ = run({"hook_event_name": "UserPromptSubmit"}, agents=NAMED)
    check("a payload carrying no session id briefs nothing and names why",
          r.returncode == 0 and r.stdout == ""
          and "could not read a session id" in r.stderr, f"err {r.stderr!r}")

    # THE LAST-RESORT RECORD PATH, which no case above can reach: every one of
    # them runs under a directory that HAS a base, which is what the walk finds
    # first. Run a COPY of the skill so `BASE` is a temporary tree, from a cwd
    # with no `AGENTS.md` above it at all, and the fallback is the only branch
    # left. Reported in the REPORT for fix round 1 as covered when it was not.
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        base = d / "base"
        skill = base / ".claude" / "skills" / "assuming-role"
        shutil.copytree(SCRIPT.parent.parent, skill)
        bin_dir = d / "bin"
        bin_dir.mkdir()
        (bin_dir / "herdr").write_text(FAKE)
        (bin_dir / "herdr").chmod(0o755)
        plain = d / "plain"
        plain.mkdir()
        env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                   FAKE_AGENTS=json.dumps(NAMED), CLAUDE_PROJECT_DIR=str(plain))
        r = subprocess.run(
            [sys.executable, str(skill / "scripts" / SCRIPT.name)], env=env,
            cwd=str(plain), capture_output=True, text=True,
            input=json.dumps({"hook_event_name": "SessionStart",
                              "source": "startup", "session_id": SID}))
        landed = sorted((base / "runtime" / "briefed").glob("*")) \
            if (base / "runtime" / "briefed").is_dir() else []
        check("with no base above the cwd the record falls back to the "
              "SCRIPT's own base, and the line says where",
              r.returncode == 0 and len(landed) == 1
              and landed[0].name == SID and str(base) in r.stderr,
              f"landed {landed} err {r.stderr!r}")

    for f in fails:
        print(f"FAIL  {f}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
