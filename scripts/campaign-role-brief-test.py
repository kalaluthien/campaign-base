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
        camp = d / "campaign-260101"
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
        recs = sorted((camp / "runtime" / "briefed").glob("*")) \
            if (camp / "runtime" / "briefed").is_dir() else []
        return r, (recs[0].read_text() if recs else None), camp


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

    # THE RETIRED TOKEN still names a campaign, because `campaign_of` admits
    # it: a session named before #181 must not read as no-role and lose its
    # brief on the strength of a rename it has not been asked to make.
    r, _, _ = run({"session_id": SID}, argv=["--role"],
                  agents=row(SID, "campaign-1-worker-10"))
    check("a name in the retired `campaign-<N>` form still reads as a role",
          r.stdout.strip() == "worker campaign-1", f"out {r.stdout!r}")

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
          r.returncode == 0 and "no role read" not in r.stdout
          and ("could not" in r.stdout.lower() or "exited" in r.stdout),
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

    r, _, _ = run({"hook_event_name": "SessionStart", "source": "startup",
                   "session_id": SID}, agents=NAMED, campaign_agents=None)
    check("a campaign with no AGENTS.md of its own still gets the skill's "
          "brief",
          r.returncode == 0 and "The worker's lifecycle" in r.stdout
          and "WORKER-MARK" not in r.stdout, f"out {r.stdout[:120]!r}")

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
          and "no session id" in r.stderr, f"err {r.stderr!r}")

    for f in fails:
        print(f"FAIL  {f}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
