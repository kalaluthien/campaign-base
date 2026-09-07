#!/usr/bin/env python3
"""Refuse a changing call from a session holding no claim on the campaign it is in.

    check-campaign-claim.py    PreToolUse, reading the hook payload on stdin

The pre-tool-use half of the claim gate; scripts/check-commit-claim.py is the
commit half (spec/campaign/orchestration/scenarios.als, `claimBeforeWork` and
`claimBeforeCommit`). A claim is a `<slug>/<issue>-<topic>` branch whose
ref exists on the remote, and nothing on disk (#176).

WHAT IS READ. Two bounded languages. A FILE TOOL names its target. A `gh`
call is one program with a stable grammar: each segment (shlex; ``;|&(){}` ``
split it, and so do the strings another command runs -- the `-c` of a shell
NAMED IN `SHELLS`, alone or last in a cluster like `-lc`, and `eval`'s
operands; the set is the rule and the comment beside it says why, so a shell
absent from it is unread like any other interpreter, as is a string a shell is
merely handed) whose command word is
`gh` -- after `env`, `VAR=x`, `time`, a path -- is looked up in WRITES, and a
segment that will not split refuses. A `gh` TOKEN this cannot read as the call
(`xargs`, or an assignment whose value is `gh`) is read as a write
of unknown kind, since nothing downstream reads a `gh` write.

A HEREDOC BODY IS DATA. It is removed before the command is split, so a commit
message carrying an apostrophe no longer makes the whole call unsplittable
(#193), and it is put back only for a SHELL reading it -- `bash <<EOF` is a
script, `git commit -F - <<MSG` is prose. Which segment a body belongs to is
counted from the `<<` tokens shlex leaves behind, not guessed from the line, so
`bash x.sh && git commit -F - <<M` reads the script and not the message.

NOT a loop body: `do` and `then` are prefixes, so
`for i in 1 2; do gh issue close 9; done` is read as the call it is and
narrowed to #9. Every other Bash command is ALLOWED UNREAD, printing so: a
shell string is an unbounded language, and a shell write on campaign work
lands at the commit, where the other half reads it.

EVERY VERDICT IS LOGGED, one JSON line to `<campaign>/runtime/guard.log` for
the campaign the call was classified into, or `<base>/runtime/guard.log`
outside one; a call under no base is not campaign work and is not logged.
`scripts/guard-precision.py` reads it, and the model rule is
`verdictIsDurable`. The log is written after the verdict is decided, so it can
change nothing, and whether it was written is PRINTED beside the verdict --
a log that quietly stopped being written reads exactly like a log with nothing
to say. Both directories are git-ignored: this is machine-local scratch. A
guard that CRASHED logs too, as verdict `GUARD FAILED`, for that same reason:
`guard-precision.py` reads every non-`REFUSED` row as an allow, so a guard
failing on every call would otherwise be a quiet one.

WHERE A FILE TARGET IS. A base tree -- main checkout, linked worktree anywhere,
delegate clone, all by `git rev-parse --git-common-dir` from the TARGET, never
from cwd -- or a campaign directory at a base root. Anything else is outside.

WHO MAY WRITE WHAT. A session's ROLE decides, read from its name through
`herdr agent list` and the pattern `campaign-name-session.py` owns. What each
role may write is `campaign-roles.py`'s table, imported below and restated
nowhere, here included; a name that pattern does not admit is refused on both
planes. A campaign directory is campaign-plane
scratch, but a CHECKOUT under one -- a member clone, a linked worktree -- is
code like any other. The role being unreadable is not the same as a name that
is not a campaign name: the first falls back to the claim reading below and
says so, because this guard runs for every session on this machine and a
failed read must not wall them all.

THE ROLE IS NOT A SECURITY BOUNDARY, and is not meant to be: `AGENTS.md`
§ The session name says why, and #194 is the sub-issue for tying the name to
something the named session did not choose. What this guard buys is that the
role is EXPLICIT and the mistake is LOUD.

WHO HOLDS A CLAIM. Derived, never stored. Clause 1: the target's own checkout
is on a claimed branch. Clause 2: the session's repository root (the payload
cwd's common dir, or the base above a cwd inside a campaign directory) has a
worktree on one. Clause 2 is the WEAKER gate -- every session at one root
reads as holding every claim under it, design B's named cost -- and for a
FILE write the commit gate is what holds. A `gh` write has no landing, so
clause 2 is its only gate, narrowed by the issue number: `gh issue <verb> <n>`
needs a claim on `<n>`. `gh issue create` is exempt, the number being minted
there. Every exit prints what it read and which branch it took, and for a claim that means which clause held, or that neither did, and what was
read: path, branch, and whether the ref came from `origin/` or the remote.

WHAT A COMMENT MUST LOOK LIKE (kalaluthien/campaign-base#217). A comment is the
one campaign write whose CONTENT this can read, so it is read: the first line
must be `KIND <session name|owner>: <one line>`, KIND one of REPORT, REVIEW,
BLOCKED, DECISION, NOTE, and the whole body at most 2,000 characters. Read from
all four spellings -- `-b`, `--body`, `--comment`, `--body-file` (a path
resolved against the PAYLOAD's cwd, or `-` for the heredoc) -- because a check
covering three of them refuses the careful and passes the careless. Asked
BEFORE the role and the claim, since it is a different question and its
diagnosis names one edit where the claim's names a claim. `gh api ... -f body=`
posts a comment and is NOT read; that ceiling is stated in the refusal itself.

EXIT. 0 allows; 2 refuses with the reading on stderr, where the model reads
it. A `gh` write from a cwd under no base is allowed as not in a campaign.
"""
import datetime
import importlib.machinery
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

# What makes a directory this repository's root: the script that cuts a claim.
HERE = Path(__file__).resolve().parent
# The `assuming-role` skill owns the role machinery (#227), so the two modules
# this guard imports live under it rather than beside this file. Derived from
# HERE and not searched for: a search finds whichever root happens to hold a
# copy, and two copies drifting is the failure this import exists to prevent.
SKILL_SCRIPTS = (HERE.parent / ".claude" / "skills" / "assuming-role"
                 / "scripts")
BASE_MARKER = Path("scripts") / "campaign-claim.py"
# THE MARKER THAT MAKES A DIRECTORY A CAMPAIGN'S, relative to the directory.
# Until #181 it was a `-YYMMDD` suffix on the name; the slug dropped the date,
# and no name shape can tell an arbitrary slug from `scripts/`. So the directory
# says so itself, in a file `opening-campaign` writes at scaffold: one line,
# `<N> <slug>`, derived from the campaign issue and re-derivable at any time,
# which is what lets it live in the git-ignored directory at all.
#
# AT THE DIRECTORY ROOT AND NOT UNDER `runtime/`, although both are ignored.
# `runtime/` is scratch that sessions rewrite and sweep -- the first cut of this
# put the marker there and a concurrent session's clean took it out within the
# hour, which reads to every reader here as "no campaign directory on this
# machine". What identifies the directory has to outlive its scratch.
#
# THIS FILE OWNS THE READING, as it owns `classify` and `claim_on`:
# check-commit-claim.py already imports all three from here, and
# campaign-claim.py's `is_campaign_dir` imports this one rather than restating
# it. It sits here and not there because this is the PreToolUse hook, which
# reads it on every tool call and cannot afford to exec that file's `gh`
# plumbing to ask.
CAMPAIGN_MARKER = Path(".campaign")
# The claim's shape. Only the campaign TOKEN is read from it, and it is compared
# against a session name's token by string equality -- so `<slug>/` and the
# retired `campaign-<N>/` are two tokens and not two spellings of one, exactly
# as `campaign-name-session.py`'s `campaign_of` keeps them.
CLAIM_BRANCH = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)/(\d+)-")

# A name that resolved to no role, as distinct from a role that could not be
# read at all. The table's last row refuses this one; the other falls back to
# the claim reading. The VALUE lives in campaign-roles.py with the roles it is
# the absence of; this diagnosis is the guard's, since only the guard refuses.
NAMELESS = ("A session with no campaign name has no role, and a session with "
            "no role is refused on both planes. Name it: "
            ".claude/skills/assuming-role/scripts/campaign-name-session.py "
            "<pane> <slug>-<role>-<n>")
FILE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
PATH_KEYS = ("file_path", "notebook_path", "path")

WRITES = {("issue", v) for v in "close edit comment reopen develop transfer "
          "delete pin unpin lock unlock".split()} \
    | {("pr", v) for v in "create merge comment review edit close reopen ready "
       "lock unlock".split()} \
    | {("label", v) for v in "create edit delete".split()}
# Flags whose value is a separate word, skipped when the subcommand is sought.
#
# `-l` IS NOT HERE, and the long spelling is (kalaluthien/campaign-base#192
# item 3). `-l` is `--label` for `gh issue create` and `gh issue edit` and
# `--list` for `gh issue develop`, so one table cannot be right for both, and
# the two mistakes are not symmetric. Treating a boolean as valued SWALLOWS
# the word after it: `gh issue develop -l 9` lost the 9 and fell to the
# unnarrowed gate, where any claim at all carries the write -- a weakening.
# Treating a valued flag as boolean reads its value as one more word, so
# `gh issue edit 9 -l 123` still narrows to 9, the first number, and only a
# label typed BEFORE the issue number narrows to the wrong one -- an
# over-refusal, which is the direction to fail in. The remedy is the table and
# not the parser: a subcommand-keyed table would be a second grammar for `gh`
# inside a guard whose whole design is to read one bounded slice of it.
VALUED = {"-R", "--repo", "-X", "--method", "-H", "--header", "-F", "--field",
          "-f", "--raw-field", "-b", "--body", "-t", "--title", "-m",
          "--body-file", "--label", "-a", "--assignee", "--milestone"}
# The three write-licence sets moved to campaign-roles.py with #227, whose
# header carries the rationale each was written with. They are read through
# `roles()` at the point of decision rather than bound to names here: a name
# bound at import is a copy, and the whole point of the table is that this
# guard has none. What stays here is the CLAIM, which is not a property of a
# role -- it is read per call from the target's checkout and this session's
# worktrees.
API_WRITE_FLAGS = {"-F", "--field", "-f", "--raw-field", "--input"}
SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")", "{", "}", "`"}
# Words before a command that are not it, and shells that run a string.
PREFIXES = {"env", "command", "time", "nohup", "sudo", "exec", "do", "then",
            "else", "builtin", "nice"}
# A NAMED LIST, not the category: there is no test for "is a shell", so a shell
# absent from this set has its `-c` string unread like any other interpreter's.
# Adding a name reads one more form and promises nothing about the next.
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
# Words whose OPERAND is itself a command string, re-read as one.
EVALS = {"eval"}
# A heredoc opener and its delimiter: `<<EOF`, `<<'MSG'`, `<<-"X"`. The body
# that follows is data (#193) and is removed before the command is split.
HEREDOC_OPEN = re.compile(
    r"<<-?\s*(?:(['\"])([^'\"]+)\1|([A-Za-z_][A-Za-z0-9_]*))")


def skill_module(stem, alias):
    """One module out of the `assuming-role` skill's scripts, by path.

    Both of this guard's role facts are imported rather than restated: the
    NAME regex, which campaign-name-session.py owns, and the role table, which
    campaign-roles.py owns. A second copy of either here would admit what its
    owner refuses, and the two would drift apart on the first change to
    either. Failure is the CALLER's to report -- `role_of` turns it into
    could-not-look -- so nothing is swallowed here."""
    src = SKILL_SCRIPTS / f"{stem}.py"
    spec = importlib.util.spec_from_loader(
        alias, importlib.machinery.SourceFileLoader(alias, str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_roles = None


def roles():
    """The role table, loaded once. Memoised because `role_of` runs on every
    call this guard sees and the table never changes within one run."""
    global _roles
    if _roles is None:
        _roles = skill_module("campaign-roles", "croles")
    return _roles


_NAME_RULE = None
# Set by `claim_match` when the name rule would not load, and printed beside
# every "not a campaign branch" reading so the two are never confused.
RULE_UNREADABLE = None


def name_rule():
    """`campaign-name-session.py`, imported rather than restated. That script
    owns the session name's shape AND the slug's; a second copy here would admit
    names it refuses, and the two would drift apart on the first change to
    either. It moved under the `assuming-role` skill with #227, so the load
    goes through `skill_module` beside the role table's.

    Cached, and loaded on first use rather than at import: this guard runs on
    every tool call of every session, and the file is read once per process."""
    global _NAME_RULE
    if _NAME_RULE is None:
        _NAME_RULE = skill_module("campaign-name-session", "cns")
    return _NAME_RULE


def name_pattern():
    """The NAME regex alone, for the one reader that embeds its source."""
    return name_rule().NAME


def claim_match(branch, base=None):
    """(campaign token, sub-issue number) for a claim-shaped branch, else None.

    THE TOKEN IS VALIDATED, not merely captured. `CLAIM_BRANCH` admits any first
    segment, because with slugs no regex here can tell a campaign's name from
    `feature` or `release`; what separates them is the slug rule, asked of the
    captured word. Without that, `feature/12-x` read as a claim of a campaign
    called `feature`, and every comparison downstream is against a session name
    that can never carry it.

    Both forms pass: the slug, and the retired `campaign-<N>` a branch cut
    before #181 carries. They stay two tokens and not two spellings of one --
    string equality against the session's own name is the whole comparison, and
    a session renamed to its slug is refused its old claims rather than
    half-admitted."""
    m = CLAIM_BRANCH.match(branch or "")
    if not m:
        return None
    token = m.group(1)
    try:
        rule = name_rule()
    except Exception as e:                  # noqa: BLE001 -- recorded, not raised
        # FAIL CLOSED AND SAY SO. The rule is the only reader of the token, so a
        # file that will not load makes every branch not-a-claim, which refuses.
        # Raising here would be worse than wrong: a PreToolUse hook that
        # tracebacks exits 1, which the harness reads as the hook's OWN error
        # and lets the tool call proceed -- the one outcome a guard may never
        # produce. `RULE_UNREADABLE` carries the cause into the refusal, so the
        # reader is not sent to look for a branch name that was never the
        # problem.
        global RULE_UNREADABLE
        RULE_UNREADABLE = (f"campaign-name-session.py, which owns the slug "
                           f"rule, would not load ({e.__class__.__name__}), so "
                           f"no branch can be read as a claim")
        return None
    if rule.OLD_CAMPAIGN.match(token):
        return token, m.group(2)
    if not rule.slug_ok(token):
        return None
    # A SLUG IS A WORD, so the rule alone cannot tell `demo/12-x` from
    # `feature/12-x` -- and the shape it replaced could, which is a narrowing
    # this must not quietly give up. Where a base root is known, the token has
    # to be one THIS MACHINE holds a campaign directory for. Where none is
    # (a repository outside every base, which #192 item 1 admits on purpose),
    # the rule is all there is and the reading is wider, as it was then.
    # NO BASE ROOT IS `base is None`, NOT AN EMPTY SLUG SET. Outside every base
    # `base_roots_for` returns nothing, and reading that as "this machine holds
    # no campaign of that slug" narrowed `own_claim` for slug branches alone --
    # re-imposing, for one name form, the narrowing #192 item 1 rejected on
    # purpose, while `campaign-<N>/` went on being admitted there. The three
    # callers were promised the wide reading two paragraphs up; this is that
    # promise kept.
    known = known_slugs(base) if base is not None else None
    if known is None:
        return token, m.group(2)
    return (token, m.group(2)) if token in known else None


def claim_token(branch):
    """The campaign token of a branch a caller has ALREADY read as a claim, or
    `""`.

    THE EMPTY STRING IS FAIL-CLOSED IN BOTH DIRECTIONS, which is why it is a
    sentinel and not a `None` the caller must remember to test. Every reader
    below compares it against a session's own campaign token: an `!=` refuses,
    and an `==` drops the holder and then refuses. No real token is empty.

    It exists because `claim_match` may answer None -- for a branch whose token
    the rule will not admit, and for a name rule that would not load -- while
    these sites index its result. They were safe only by an argument about call
    order, and an argument is not a check."""
    m = claim_match(branch)
    return m[0] if m else ""


def claim_issue(branch):
    """The sub-issue number of a branch already read as a claim, or `""`. The
    sentinel is `claim_token`'s, for the same reason."""
    m = claim_match(branch)
    return m[1] if m else ""


def role_of(session_id):
    """(campaign issue, role, how). THREE OUTCOMES, KEPT APART, because they
    license different things:

      * a name of the shape the pattern admits -- the role decides, per #185's
        table, and the campaign number bounds a worker;
      * a row found whose name is absent or of another shape -- LOOKED AND
        FOUND NOTHING, which the table's last row refuses;
      * herdr or the pattern unreadable -- COULD NOT LOOK, which falls back to
        the claim reading alone and prints that it did. This guard runs for
        every session on this machine, so a failed read must not wall them
        all; the floor is the pre-#185 behaviour, which is a gate and not a
        bypass.

    The second is returned as `NO_ROLE`; the third as `None`."""
    if not session_id:
        return None, None, "the payload carries no session id"
    # Both skill modules are read HERE, before herdr, so an unreadable one is
    # could-not-look rather than a crash mid-decision. Reaching any later
    # `NO_ROLE` comparison therefore means the table loaded and memoised.
    try:
        rule = name_rule()
    except Exception as e:                  # noqa: BLE001 -- reported, not raised
        return None, None, ("could not read the name pattern from "
                            "campaign-name-session.py "
                            f"({e.__class__.__name__})")
    try:
        no_role = roles().NO_ROLE
    except Exception as e:                  # noqa: BLE001 -- reported, not raised
        return None, None, ("could not read the role table from "
                            "campaign-roles.py "
                            f"({e.__class__.__name__})")
    try:
        r = subprocess.run(["herdr", "agent", "list"], capture_output=True,
                           text=True)
    except OSError as e:
        return None, None, f"herdr could not run ({e.__class__.__name__})"
    if r.returncode != 0:
        return None, None, (f"herdr agent list exited {r.returncode}: "
                            f"{r.stderr.strip()[:100]}")
    try:
        rows = json.loads(r.stdout)["result"]["agents"]
    except (ValueError, KeyError, TypeError) as e:
        return None, None, ("could not parse herdr output "
                            f"({e.__class__.__name__})")
    if not isinstance(rows, list):
        return None, None, "herdr agents was not a list"
    for a in rows:
        # EVERY SHAPE HERE IS SOMEBODY ELSE'S OUTPUT. A row that is not an
        # object, an `agent_session` that is not one, a `name` that is not a
        # string: each used to reach an attribute that does not exist, and the
        # traceback exited 1 -- which a PreToolUse hook treats as its own error
        # and the call then PROCEEDS. Unreadable is a reading, and it belongs
        # on the could-not-look path with the rest.
        if not isinstance(a, dict):
            return None, None, "a herdr row was not an object"
        sess = a.get("agent_session")
        if sess is not None and not isinstance(sess, dict):
            return None, None, "a herdr row's agent_session was not an object"
        if (sess or {}).get("value") != session_id:
            continue
        name = a.get("name") or ""
        if not isinstance(name, str):
            return None, None, "a herdr row's name was not a string"
        campaign = rule.campaign_of(name)
        if campaign is None:
            return None, no_role, (f"session {session_id} is named "
                                   f"{name or 'nothing'}, which the campaign "
                                   f"name pattern does not admit")
        role = "planner" if "-planner-" in name else "worker"
        return campaign, role, f"session {session_id} is {name}"
    return None, None, (f"no herdr row names session {session_id}, has no role here")


def git(args, cwd):
    """(stdout, why_failed, exit status) for one git command; stdout is None
    on any non-zero exit."""
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args],
                           capture_output=True, text=True)
    except OSError as e:
        return None, f"git could not run ({e.__class__.__name__})", None
    if r.returncode != 0:
        tail = r.stderr.strip().splitlines()
        return None, (tail[-1] if tail else f"git exited {r.returncode}"), r.returncode
    return r.stdout, None, 0


def checkout_of(path: Path):
    """(main checkout root, this checkout's toplevel, note) for the repository
    holding `path`, read from git and never from a filesystem walk: a linked
    worktree anywhere resolves to its main checkout. (None, None, note) when
    no repository holds it."""
    d = next(d for d in [path, *path.parents] if d.is_dir())
    out, why, _ = git(["rev-parse", "--path-format=absolute", "--git-common-dir",
                       "--show-toplevel"], d)
    if out is None:
        return None, None, f"{d}: {why}"
    common, top = (line.strip() for line in out.splitlines()[:2])
    return Path(common).parent.resolve(), Path(top).resolve(), None


def base_above(path: Path):
    """The NEAREST ancestor holding the marker: a path inside a campaign
    directory rather than a checkout.

    NEAREST, NOT TOPMOST, and the choice is stated because #184 left it an
    accident (kalaluthien/campaign-base#191 item 2). With bases nested -- and
    `<campaign>/repos/campaign-base/` is exactly that -- the topmost reading
    answered the OUTER base for a path owned by the inner one, so
    `campaign_dir_of` then found the outer campaign directory and `session_root`
    swept the outer base's worktrees for the inner base's claims. Nearest
    agrees with the two readers beside it, `campaign_dir_of` here and
    `own_campaign_dir` in campaign-claim.py, both of which already take the
    nearest ancestor; three readers of "which one owns this path" that do not
    agree is worse than any one of the answers.

    It is reached only when git resolves no marker-bearing repository for the
    path -- a target under a base root but in no checkout -- so the two
    readings differ rarely. That is a reason to pin the choice, not to leave it
    to the order of a `reversed`."""
    return next((d for d in [path, *path.parents]
                 if (d / BASE_MARKER).is_file()), None)


def is_campaign_dir(path: Path):
    """Whether `path` is a campaign directory, read as the marker's presence and
    not as the name's shape.

    A directory that cannot be stat'd is not a campaign directory rather than a
    refusal, and that is deliberate: this is asked of every ancestor of a target,
    where an unreadable one is somebody else's problem and refusing would deny
    every write on the machine."""
    try:
        return (path / CAMPAIGN_MARKER).is_file()
    except OSError:
        return False


_KNOWN_SLUGS = {}


def marker_fields(d):
    """The whitespace-separated fields of `d`'s campaign marker, or None.

    EVERY WAY A FILE CAN REFUSE TO BE TEXT, not only `OSError`: a `.campaign`
    that is not UTF-8 raises `UnicodeDecodeError`, which is not an `OSError`,
    and letting it out of here tracebacks the PreToolUse hook into exit 1 --
    which the harness reads as the hook's own error and lets the tool call
    PROCEED. One unreadable marker at the base root would have opened that door
    for every session on the machine."""
    try:
        return (d / CAMPAIGN_MARKER).read_text().split()
    except (OSError, UnicodeDecodeError, ValueError):
        return None


def base_roots_for(path: Path):
    """The base roots that could hold the campaign directory a branch's slug
    names, for a checkout at `path`: the marker-bearing ancestors of its MAIN
    checkout, nearest first. Empty when git cannot name one.

    NOT `base_above`, and the difference is the point. `base_above` answers
    "which base OWNS this path", where nearest is right and #191 item 2 says
    why. This answers a different question, and the nearest reading is wrong for
    it in every shape a claim is actually worked in:

      * a LINKED WORKTREE carries `scripts/` of its own and no campaign
        directory, and git puts it wherever it was asked to -- under the
        campaign directory here, a sibling of the base in the suite's fixture --
        so no walk up from IT reaches the base. Its main checkout does, and that
        is what `--git-common-dir` answers;
      * the base's OWN CLONE at `<base>/<campaign>/repos/campaign-base/` is its
        own main checkout, so the same walk reaches the outer base from there.

    ONE START, NOT A UNION. Walking up from the path as well pinned nothing --
    every start it could use, the main checkout also reaches -- and a branch no
    case reddens for is deleted rather than covered. Nor is there a fallback to
    `path` when git answers nothing: `claim_on` and `own_claim` both read the
    branch through git first, so a checkout git cannot name never arrives here.

    Asking the nearest base alone made every slug claim in a worktree read as no
    claim, while `held` -- given a repository root already resolved through the
    git common dir -- read the same branch as a claim, so one run printed both
    verdicts about one branch (#181 review, finding 1).

    WHICH SUITE READS THIS, named because it is not this file's own: the case is
    `a commit in a worktree on a SLUG claim goes through`, in
    check-commit-claim-test.py, and resolving through the path reddens it. The
    guard's own suite stays green under that mutation and no case here was worth
    manufacturing: inside the guard a worktree's claim is found by `held`, whose
    root already comes through the git common dir, so `claim_on` and `own_claim`
    decide only where `held` finds nothing -- a member clone, and the commit
    gate, which calls `claim_on` directly.

    THE RETIRED FORM NEEDS NONE OF THIS, which is why the gap was invisible: a
    `campaign-<N>/` branch carries its campaign in the name and never reaches
    a marker."""
    main, _top, _note = checkout_of(path)
    if main is None:
        return []
    return [d for d in [main, *main.parents] if (d / BASE_MARKER).is_file()]


def known_slugs(base):
    """The slugs of the campaign directories at the base roots above `base`,
    from their markers -- or None when there is no base root above it at all.

    Cached per starting path, and read at most once per process: this guard runs
    on every tool call, and a campaign directory does not appear mid-call. A
    base that will not enumerate contributes nothing -- so a claim reading there
    falls back to the retired form alone, which refuses rather than admits."""
    key = str(base)
    if key not in _KNOWN_SLUGS:
        roots = base_roots_for(Path(base))
        found = set()
        for root in roots:
            try:
                entries = sorted(root.iterdir())
            except OSError:
                continue
            for d in entries:
                fields = marker_fields(d)
                if fields and len(fields) >= 2:
                    found.add(fields[1])
        # NONE IS NOT THE EMPTY SET. No base root above the checkout at all is
        # "there is nothing here to compare a slug against", and #192 item 1
        # admits that checkout on the branch name and its ref alone. A base root
        # that exists and holds no campaign directory is a different answer --
        # this machine holds no campaign of any slug -- and it narrows.
        _KNOWN_SLUGS[key] = found if roots else None
    return _KNOWN_SLUGS[key]


def campaign_number(token, base):
    """The campaign ISSUE NUMBER a session name's token stands for, or None.

    THE TOKEN IS NOT THE NUMBER since #181, and one caller still needs the
    number: the carve-out that lets a worker comment on its own campaign's
    issue compares against an issue number typed on a `gh` line. Every other
    comparison in this file is token against token and asks nothing of this.

    Two sources, both local, because this runs on every tool call:

      * the retired `campaign-<N>` token carries the number itself;
      * a slug is looked up in the `.campaign` markers of the campaign
        directories at `base` -- the file that says which campaign a directory
        is, written at scaffold and re-derivable from the campaign issue.

    None is "I could not say", and the caller falls back to the claim reading,
    which is the narrower gate. A slug whose campaign has no directory on this
    machine is that case: correct, since a session naming a campaign this
    machine does not hold is not one this carve-out should widen for."""
    rule = name_rule()
    if rule.OLD_CAMPAIGN.match(token or ""):
        return token[len("campaign-"):]
    if not token or base is None:
        return None
    found = set()
    for root in base_roots_for(Path(base)):
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for d in entries:
            fields = marker_fields(d)
            if fields and len(fields) >= 2 and fields[1] == token \
                    and fields[0].isdigit():
                found.add(fields[0])
    # TWO MARKERS NAMING ONE SLUG IS NOT A NUMBER. Sorted order is not a
    # tiebreak, and picking one would widen the carve-out for a campaign issue
    # nobody named. `slugs_in` refuses the same duplication on the GitHub side;
    # this is the machine-local half.
    return found.pop() if len(found) == 1 else None


def campaign_dir_of(path: Path, base: Path):
    return next((d for d in [path, *path.parents]
                 if d.parent == base and is_campaign_dir(d)), None)


def classify(target: Path):
    """(inside?, where, checkout toplevel or None, scratch?).

    Inside means campaign work: a base tree read through git, or a campaign
    directory read by shape. The last two are different questions and #185 needs
    both -- a campaign directory sits AT the base root, so a target under it is
    inside the base checkout too and `top` alone cannot tell the code plane from
    campaign-plane scratch."""
    main, top, note = checkout_of(target)
    by_git = main is not None and (main / BASE_MARKER).is_file()
    base = main if by_git else base_above(target)
    if base is None:
        return (False,
                f"in no base tree and no campaign directory ({note or main})",
                top, False)
    camp = campaign_dir_of(target, base)
    if camp is not None:
        # SCRATCH means in a campaign directory and in NO CHECKOUT NEARER than
        # the one holding that directory. A campaign directory sits at the base
        # root, so a plain note under it reports the base as its checkout -- but
        # a member repository clone at <campaign>/repos/<repo>/ and a linked
        # worktree at <campaign>/worktrees/<n>/ are checkouts of their own,
        # under the same campaign directory, and they are code. Keying on the
        # campaign directory alone let a planner edit both.
        _, camp_top, _ = checkout_of(camp)
        scratch = top is None or top == camp_top
        return (True, f"inside the campaign directory {camp}"
                + ("" if scratch else f", in the checkout {top}"), top, scratch)
    return (True,
            f"inside the base {base}" + (f" (checkout {top})" if by_git else ""),
            top, False)


def ref_exists(branch, repo_root):
    """(True/False/None, source). The local `origin/` copy first, the remote
    only when that is absent: a claim just cut and not yet fetched must not
    read as no claim, and a remote that cannot be asked is not an absence."""
    out, _, _ = git(["show-ref", "--verify", "--quiet",
                     f"refs/remotes/origin/{branch}"], repo_root)
    if out is not None:
        return True, f"refs/remotes/origin/{branch} in {repo_root}"
    out, why, rc = git(["ls-remote", "--exit-code", "--heads", "origin", branch],
                       repo_root)
    if out is not None:
        return True, f"ls-remote origin {branch}"
    if rc == 2:
        return False, f"ls-remote origin {branch}: no such head"
    return None, f"ls-remote origin {branch} could not be read ({why})"


def branch_of(top):
    out, _, _ = git(["branch", "--show-current"], top)
    return out.strip() or None if out is not None else None


def claim_on(top):
    """(branch or None, verdict, source) for one checkout: is its branch a
    claim, read as the ref's existence."""
    branch = branch_of(top)
    if not branch or not claim_match(branch, top):
        return branch, False, (f"{top} is on {branch or 'no branch'}, not a "
                               f"campaign branch"
                               + (f" -- {RULE_UNREADABLE}" if RULE_UNREADABLE
                                  else ""))
    exists, source = ref_exists(branch, top)
    return branch, exists, source


def worktrees(repo_root):
    """[(path, branch)] from `git worktree list`, or None when unreadable."""
    out, _, _ = git(["worktree", "list", "--porcelain"], repo_root)
    if out is None:
        return None
    found, path = [], None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = Path(line[9:])
        elif line.startswith("branch refs/heads/") and path is not None:
            found.append((path, line[18:]))
        elif line.startswith("prunable") and found and found[-1][0] == path:
            found.pop()                 # a directory git itself marks gone
    return found


def own_claim(cwd: Path):
    """(path, branch, source) when the checkout the session is STANDING IN is
    itself on a claim, else None.

    `held` sweeps one repository root's worktrees, and a member repository's
    clone under a campaign directory is not one of them -- it is a different
    repository. A delegate on its own pushed claim branch there
    therefore read as holding no claim at all. This is the same branch reading
    `held` does, asked of the checkout at hand rather than of the base's
    worktree list.

    ITS BOUNDARY, STATED RATHER THAN NARROWED (kalaluthien/campaign-base#192
    item 1). What this asks is exactly #176's property and no more: the branch
    name is claim-shaped and its ref exists on WHATEVER remote this checkout
    has. It does not ask that the checkout sit under a campaign directory, nor
    that its origin be the campaign's remote, nor that it be GitHub. So an
    unrelated `git init` repository parked at `<base>/<campaign>/sandbox`, on a
    branch named `campaign-1/888-x` with a local bare origin, gets
    `gh issue close 888` allowed here where `origin/main` refuses it.

    THE THREE NARROWINGS THAT WERE WEIGHED, and why none was taken:

      * require the checkout under a campaign directory of the base above it --
        the probe's sandbox IS under one, so it excludes nothing it should and
        excludes a delegate whose clone sits elsewhere;
      * require the origin's owner to match the base's -- a member repository
        may belong to an owner this account does not, which AGENTS.md says in
        so many words, so this refuses the ordinary case;
      * require the origin to be a GitHub URL -- this one does separate the
        probe from the delegate, and it makes the guard's verdict turn on the
        SHAPE of a remote URL, which no fixture in this repository can exercise
        honestly (every one of them uses a local bare remote). A rule its own
        suite must lie about is worse than the reach.

    So the reach is kept and named. It is bounded by the two things it does
    ask, and each has a case that fails when it is dropped: the branch is
    claim-SHAPED, and its ref EXISTS."""
    _main, top, _note = checkout_of(cwd)
    if top is None:
        return None
    branch = git(["branch", "--show-current"], top)[0]
    branch = (branch or "").strip()
    if not branch or not claim_match(branch, top):
        return None
    exists, source = ref_exists(branch, top)
    return (top, branch, source) if exists else None


def session_root(cwd: Path):
    """(root, how). The session's repository root, or the base above a cwd
    inside a campaign directory, or None."""
    main, _top, _note = checkout_of(cwd)
    # A REPOSITORY INSIDE A BASE IS STILL THAT BASE'S. Preferring the common dir
    # unconditionally resolved a cwd in `<base>/<campaign>/repos/<member>/` to
    # the member repository, which carries no marker -- so the ordinary delegate
    # shape read as "in no campaign" and every campaign-plane write there was
    # allowed unread, while `file_call` refused the same target. This is
    # `classify`'s fallback, mirrored, which is what makes the two halves ask
    # one question rather than two that agree on the suite's cases.
    if main is not None and (main / BASE_MARKER).is_file():
        return main, f"cwd {cwd} -> git common dir -> {main}"
    base = base_above(cwd)
    if base is not None:
        return base, (f"cwd {cwd} is inside {main}, which is no base; the base "
                      f"above it is {base}" if main is not None
                      else f"cwd {cwd} is under the base {base} outside any checkout")
    if main is not None:
        return main, f"cwd {cwd} -> git common dir -> {main}"
    return None, f"cwd {cwd} is under no repository and no base"


def held(repo_root, issue=None):
    """([(path, branch, source)], detail lines): the claimed branches checked
    out under `repo_root`, narrowed to sub-issue `issue` when given."""
    trees = worktrees(repo_root)
    if trees is None:
        return [], [f"git worktree list could not be read at {repo_root}"]
    out, detail = [], []
    base = Path(repo_root)
    claims = [(p, b, claim_match(b, base)) for p, b in trees
              if claim_match(b, base)]
    for path, branch, m in claims:
        if issue is not None and m[1] != str(issue):
            detail.append(f"{path} is on {branch}, not a claim on #{issue}")
            continue
        exists, source = ref_exists(branch, repo_root)
        (out if exists else detail).append(
            (path, branch, source) if exists else f"{path} is on {branch}, but {source}")
    if not claims:
        detail.append(f"no checkout under {repo_root} is on a campaign branch")
    return out, detail


def openers(line, quote):
    """([(delimiter, is `<<-`)], the quote state at the end of the line).

    A `<<` IS ONLY A HEREDOC WHERE IT IS SYNTAX. Searching the raw line for one
    read `git commit -m 'about the <<EOF form'` as opening a heredoc, deleted
    every following line as its body, and so hid the `gh issue close 9` on the
    next line -- a write `main` refuses and this allowed. The same mistake in
    the other direction ate the closing quote of a multi-line
    `gh issue comment --body "... <<EOF ..."` and refused it as unsplittable.
    Both were found by a review at 1a3138e, in a differential over 6217 real
    transcript commands.

    So the scan tracks quoting, and it tracks it ACROSS LINES, because that is
    what the second shape needs: the quote a `<<` sits inside was opened on an
    earlier line. A heredoc BODY is not scanned -- it is data, and shell quoting
    does not cross it -- which is why the caller passes the state back in rather
    than this reading the whole command.

    A backslash outside single quotes escapes the next character; inside single
    quotes it does not, which is why the single-quote branch is separate.

    A COMMAND SUBSTITUTION RE-OPENS COMMAND CONTEXT INSIDE A QUOTE, and leaving
    that out broke the campaign's most common spelling of a body:
    `gh issue comment --body "$(cat <<'EOF' ... EOF )"` puts the opener inside
    double quotes, where the shell still reads it as a heredoc. Two entries of
    the 611-call corpus are exactly that, and both went from allowed to refused
    the moment quoting was tracked without it -- caught by the corpus, which is
    what the corpus is for. So `$(` pushes the quote aside and `)` restores it.

    `quote` is therefore a stack in flight and one value across lines: a
    substitution does not survive a newline in any spelling this reads, and the
    quote it sits inside does.

    A `#` AT WORD START ENDS THE LINE, and leaving it out was worse than not
    tracking quotes at all, because the cross-line carry above then handed the
    comment's stray quote to the next line. `# it's fine` / `bash <<'M'` /
    `gh issue close 11` / `M` was refused at 1a3138e and ALLOWED without this
    branch -- the apostrophe opened a quote, so the real opener on the next
    line was read as quoted and the body stayed a command nobody split. The
    other direction too: `# don't do this` before a `git commit -F - <<'M'`
    made the whole call unsplittable, which is #193 reopened.

    WORD START IS LOAD-BEARING, and the argument that it is not took a review
    to kill. `shlex` treats a mid-word `#` as a comment too, so
    `echo a#b && gh issue close 11` reads the same either way -- but that is
    true only DOWNSTREAM. This scanner runs first and decides which lines
    `strip_heredocs` removes as data, so breaking at a mid-word `#` makes it
    miss a `<<` LATER ON THE SAME LINE and the body is tokenised as commands.
    `test $# -eq 0 && cat <<EOF` / `gh issue close 11` / `EOF` reads as one
    segment holding a stray `gh` without this condition, and as `cat` with a
    data body with it. `$#` and `${f#./}` are ordinary shell.

    THE CORPUS SAYS NOTHING ABOUT THIS ONE. Over its 547 commands, 137 of them
    holding a `#`, the segments are IDENTICAL with and without the condition --
    0 differ, 0 unsplittable either way. The evidence is the constructed shapes
    above and the cases that pin them, and saying so is the point: an earlier
    draft of this paragraph carried a corpus number that came from a review
    report rather than from a run, and it did not reproduce.

    THE BOUNDARY SET IS ` \t;|&` AND DELIBERATELY NOT `()`. A `)` mostly ends a
    substitution rather than a word -- `echo $(echo x)#c` prints `x#c`, and
    `+(#|x)` is a pattern -- so admitting them turned `echo $(echo x)#c && cat
    <<EOF ...` from allowed into refused. Missing a comment that opens straight
    after `(` costs nothing this reads, since a comment there needs no `<<`
    after it on the same line to be a comment."""
    found, i, n, stack = [], 0, len(line), []
    while i < n:
        c = line[i]
        if quote == "'":
            quote = None if c == "'" else quote
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if line.startswith("$(", i):
            stack.append(quote)
            quote = None
            i += 2
            continue
        if c == ")" and stack:
            quote = stack.pop()
            i += 1
            continue
        if quote == '"':
            quote = None if c == '"' else quote
            i += 1
            continue
        if c == "#" and (i == 0 or line[i - 1] in " \t;|&"):
            break
        if c in "'\"":
            quote = c
            i += 1
            continue
        if line.startswith("<<", i):
            m = HEREDOC_OPEN.match(line, i)
            if m:
                found.append((m.group(2) or m.group(3),
                              m.group(0).startswith("<<-")))
                i = m.end()
                continue
        i += 1
    return found, quote


def strip_heredocs(command):
    """(the command with every heredoc BODY removed, the bodies in the order
    their openers appear).

    A HEREDOC BODY IS DATA, NOT A COMMAND (kalaluthien/campaign-base#193). It
    was part of the string handed to shlex, so an ordinary commit message with
    an apostrophe in it -- `machine's` -- made the whole call unsplittable and
    the guard refused it, machine-wide, naming a `gh` call that was not there.
    The body is removed before anything is split, and put back only where the
    line's own command word says it is a command: `strip_heredocs` collects it,
    `segments` re-reads it for a SHELL and for nothing else.

    The terminator is the delimiter alone on its line, or leading tabs stripped
    for `<<-`. An unterminated body runs to the end, which is what a shell
    would fail on and what this must not traceback on."""
    lines = command.split("\n")
    out, bodies, quote = [], [], None
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        opens, quote = openers(line, quote)
        i += 1
        for delim, dash in opens:
            body = []
            while i < len(lines):
                cur = lines[i]
                i += 1
                if (cur.strip() if dash else cur.rstrip()) == delim:
                    break
                body.append(cur)
            bodies.append("\n".join(body))
    return "\n".join(out), bodies


def segments(command):
    """The command's segments as token lists, or (None, why) when shlex will
    not split it.

    The pairing half is `paired_segments` below; this is the shape every caller
    but the comment check wants, and it is a projection of that one rather than
    a second walk."""
    pairs, why = paired_segments(command)
    return (None if pairs is None else [tokens for tokens, _ in pairs]), why


def paired_segments(command):
    """[(tokens, the heredoc bodies that segment opened)], or (None, why).

    `punctuation_chars` makes `;`, `|`, `&` their own tokens.

    THE BODIES COME BACK OUT (kalaluthien/campaign-base#217). `strip_heredocs`
    has always RETURNED them and this walk has always paired them to the
    segment that opened them, by counting `<<` tokens -- it just handed them on
    to a shell and to nothing else. The comment check needs the same pairing
    for a different reason: `gh issue comment -F- <<EOF` puts the comment's
    text in a heredoc, and a check that could not see it would pass every
    heredoc comment silently while refusing the `-b` spelling of the same
    thing. Pairing on the LINE instead would read the commit message in
    `bash x.sh && git commit -F - <<M` as a comment body."""
    command, heredocs = strip_heredocs(command)
    lex = shlex.shlex(command, posix=True, punctuation_chars="();<>|&{}`")
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError as e:
        return None, f"the command would not split ({e})"
    out, cur = [], []
    for t in tokens + [";"]:
        if t not in SEPARATORS:
            cur.append(t)
        elif cur:
            out.append(cur)
            cur = []
    # A string another command runs is that string's segments too: a shell's
    # -c, spelled alone or last in a cluster (`bash -lc`), eval's operands, and
    # a heredoc a SHELL is reading -- `bash <<EOF`, where the body is the
    # script. The bodies were removed above, so they are paired back to the
    # segment that opened them by counting `<<` tokens, which shlex leaves in
    # place. Pairing on the LINE instead would re-read the commit message in
    # `bash x.sh && git commit -F - <<M`, which is the false positive this
    # whole change is about.
    #
    # `depth` used to be carried through this recursion and nothing varied it
    # (kalaluthien/campaign-base#191 item 3): the handed-string re-read that
    # needed a bound was withdrawn in #184. Every inner string is a proper
    # substring of its container, so the recursion is bounded by the command's
    # own length and the parameter had no reader. Removed rather than given
    # one.
    taken = 0
    paired = []
    for seg in list(out):
        mine = heredocs[taken:taken + seg.count("<<")]
        taken += seg.count("<<")
        paired.append((seg, mine))
        word, rest = head(seg)
        if word is None:
            continue
        inners = []
        if word in SHELLS:
            i = next((j for j, t in enumerate(rest[:-1]) if is_dash_c(t)), None)
            if i is not None:
                inners = [rest[i + 1]]
            inners += mine
        elif word in EVALS:
            inners = [t for t in rest[1:] if not t.startswith("-")]
        for text in inners:
            more, why = paired_segments(text)
            if more is None:
                return None, why
            # `out` is NOT extended here any more. `for seg in list(out)`
            # takes its snapshot before the loop and `paired` is what this
            # returns, so the append had no reader after #217 split the walk.
            paired += more
    # WHAT IS DELIBERATELY NOT READ, and why the line is here. A shell that
    # runs what it is HANDED -- `bash <<< '...'`, `... | bash` -- puts the
    # command in a quoted operand, where the `gh` is one word of one token.
    # Re-reading every multi-word token when such a shell is present closed
    # those two and cost more than they were worth: it refused
    # `gh issue create --body "...gh issue close 9..."` (the create exemption
    # defeated by its own body) and `git commit -m "fix gh issue close parsing"
    # && bash deploy.sh`, machine-wide, on a guard every session runs; and a
    # decoy `-b "gh issue close 7"` re-read into a SECOND issue number let a
    # claim on #7 admit a real write to #9. Both were found by review, and
    # both are the shape this design already declines: one more alternation
    # buys one more form and a new bypass. An operand handed to a shell is a
    # shell string, and a shell string is not read.
    return paired, None


def is_dash_c(token):
    """A shell's -c, alone or last in a short-option cluster: `-c`, `-lc`."""
    return (len(token) > 1 and token[0] == "-" and token[1] != "-"
            and token[1:].isalpha() and token.endswith("c"))


def gh_token(token):
    """Whether this token names `gh` -- as the word, as a path, or as the VALUE
    of an assignment, which is how `G=gh; $G issue close 9` hides one."""
    if token.rsplit("/", 1)[-1] == "gh":
        return True
    if "=" in token and not token.startswith("-"):
        return token.split("=", 1)[1].rsplit("/", 1)[-1] == "gh"
    return False


def head(seg):
    """The segment's command word, prefixes and `VAR=x` assignments stripped,
    a path reduced to its basename; and the tokens from it on."""
    i = 0
    while i < len(seg) and (seg[i] in PREFIXES or ("=" in seg[i]
                            and not seg[i].startswith("-"))):
        i += 1
    if i >= len(seg):
        return None, seg
    return seg[i].rsplit("/", 1)[-1], seg[i:]


def gh_words(tokens):
    """The non-flag words after `gh`, a valued flag's value skipped."""
    words, i = [], 1
    while i < len(tokens):
        t = tokens[i]
        i += 2 if t in VALUED else 1
        if not t.startswith("-"):
            words.append(t)
    return words


def gh_write(tokens):
    """(is a write, what) for one segment whose first word is `gh`."""
    words = gh_words(tokens)
    if not words:
        return False, "gh with no subcommand"
    if words[0] == "api":
        # Over ALL tokens: `--method=X` carries its value and can be last,
        # where `-X X` cannot. Slicing the last token off read the attached
        # spelling as absent, which allowed the write.
        method = None
        for j, t in enumerate(tokens):
            if t.startswith("--method="):
                method = t[9:].upper()
                break
            if t in ("-X", "--method") and j + 1 < len(tokens):
                method = tokens[j + 1].upper()
                break
        if method:
            return method != "GET", f"gh api {method}"
        if any(t in API_WRITE_FLAGS or t.split("=")[0] in API_WRITE_FLAGS
               for t in tokens):
            return True, "gh api with a field, which POSTs"
        return False, "gh api with no method and no field"
    pair = tuple(words[:2])
    if pair == ("issue", "create"):
        return False, "gh issue create, exempt: the number is minted there"
    if pair in WRITES:
        return True, "gh " + " ".join(pair)
    return False, "gh " + " ".join(pair) + ", not a write"


# ---------------------------------------------------------- the comment shape
#
# WHY THE GUARD AND NOT A WRITER SCRIPT (kalaluthien/campaign-base#217). The
# design this implements proposed `campaign-comment.py`, a script every comment
# would be posted through, on the premise that the guard cannot see a heredoc
# body. That premise was false: `strip_heredocs` RETURNS the bodies and
# `paired_segments` already pairs them to their segment -- #193 removed them
# from SPLITTING, not from reading. So the same guarantee is thirty lines in a
# file that already parses these calls, against a new script, a new routing
# rule, a second place to learn, and a refusal that would have broken the
# `gh issue reopen --comment` that AGENTS.md itself prescribes.
#
# WHAT THIS DOES NOT CLOSE, stated rather than left to be discovered:
#
#   `gh api repos/.../issues/N/comments -f body=...` posts a comment and is
#   NOT read here. `gh_write` reads it as "a write requiring a claim" and never
#   pairs it against a subcommand, so no kind and no ceiling is checked on that
#   route. Closing it means a second grammar for `gh api`'s field syntax inside
#   a hook every session runs, which is the cost this declines -- as
#   the table's `gh_except` declines the matching hole on `gh issue develop`.
#
#   `--body-file` naming a file this cannot read comes back as unreadable and
#   is refused, not allowed: a body that could not be read is not a body with a
#   kind on it.
COMMENT_KINDS = ("REPORT", "REVIEW", "BLOCKED", "DECISION", "NOTE")
# The pairs whose whole purpose is to post a comment...
COMMENT_WRITES = {("issue", "comment"), ("pr", "comment"), ("pr", "review")}
# ...and the verbs that post one only when `--comment` is given. `gh issue
# reopen --comment` is the form AGENTS.md prescribes for appending a discovery
# to an existing sub-issue, so it is checked and never refused for existing.
COMMENT_FLAG_WRITES = {("issue", "close"), ("issue", "reopen"),
                       ("pr", "close"), ("pr", "reopen")}
COMMENT_CEILING = 2000
# `KIND <session-name|owner>: <one line>`. The name is the only attribution one
# `gh` account leaves, and `owner` is the person's own word arriving through a
# session. `name_pattern` is the session-name rule's one home, imported by this
# file already, so the two cannot drift.
_FIRST_LINE = None


# Set when the name rule would not load, and carried into the verdict beside
# the comment that could not be judged for it.
FIRST_LINE_UNREADABLE = None


def comment_first_line():
    """The first-line pattern, or None when the name rule will not load.

    Built on first use and cached, not at import: `name_pattern` loads another
    file, and this guard runs on every tool call of every session.

    NONE IS COULD-NOT-LOOK, NOT A BAD SHAPE, and it is why this returns rather
    than raising. This pattern is BUILT from the session-name regex, so an
    unreadable `campaign-name-session.py` used to escape as a traceback here --
    and a PreToolUse hook that raises exits 1, which the harness reads as the
    HOOK's error and lets the call PROCEED. That is a hole, not a refusal, and
    it is the same rule `claim_match` and `role_of` already follow. Refusing
    instead would be the opposite mistake: it would wall every comment on the
    machine for a missing file, which is what the campaign plane's fallback
    exists to prevent. So the comment goes on to the claim reading UNJUDGED,
    exactly as a shell-composed body does, and the verdict says so."""
    global _FIRST_LINE, FIRST_LINE_UNREADABLE
    if _FIRST_LINE is None and FIRST_LINE_UNREADABLE is None:
        try:
            name = name_pattern().pattern.strip("^$")
        except Exception as e:              # noqa: BLE001 -- reported, not raised
            FIRST_LINE_UNREADABLE = (
                f"campaign-name-session.py, which owns the session-name half of "
                f"the first line, would not load ({e.__class__.__name__})")
            return None
        _FIRST_LINE = re.compile(
            r"^(?:" + "|".join(COMMENT_KINDS) + r") (?:owner|"
            + name + r"): *\S")
    return _FIRST_LINE


# THE BODY FLAGS, and `--comment` IS NOT AMONG THEM. `gh`'s own example is
# `gh pr review --comment -b "interesting"`, where `--comment` is the review's
# KIND and takes no value; reading it as valued swallowed the `-b` and judged
# the literal string `--body` as the comment's first line -- so a correctly
# kinded REVIEW, the one comment this vocabulary exists to make machine-
# readable, was refused with a diagnosis sending its author to fix a line that
# was already right. `--comment` is valued only on the `COMMENT_FLAG_WRITES`
# verbs, and `comment_body` reads it only there.
BODY_VALUED = {"-b", "--body"}
# `-c` IS `--comment`'s SHORTHAND on `gh issue close|reopen` and
# `gh pr close|reopen` (`gh help issue close`: `-c, --comment string`), and
# reading only the long spelling was the very hole this pair was narrowed to
# close: the careless spelling passing while the careful one is checked. It is
# read INSIDE the `COMMENT_FLAG_WRITES` branch only, because `-c` on
# `gh pr review` is the boolean kind and carries no text.
COMMENT_FLAG = {"-c", "--comment"}
BODY_FILE_VALUED = {"-F", "--body-file"}
# A GNU-style long option takes `--x=v`; a pflag SHORTHAND also takes `-bv`
# with no separator, and `gh` uses pflag. Named here rather than derived, so
# `--body` is never split as though it were `-b` + `ody`.
SHORT_FLAGS = {"-b", "-F", "-c"}
# Every flag this reader knows, so one is never mistaken for another's value.
KNOWN_FLAGS = BODY_VALUED | COMMENT_FLAG | BODY_FILE_VALUED
# What `flag_value` returns when the only candidate value was itself a flag of
# this reader: distinct from None, which means "no such flag was given at all".
SKIPPED = object()
SKIPPED_NOTE = ("its body, or the path its body-file names, is one of this "
                "reader's own flag words, so the value was skipped rather than "
                "judged; the shape was not read")
# WHAT MAKES A BODY UNJUDGEABLE. shlex expands nothing, so a token holding a
# command substitution reaches this check as its SOURCE, not as its value, and
# `--body "$(cat review.md)"` -- a form this campaign used four times on PR
# kalaluthien/campaign-base#183 -- was refused for a first line reading
# `$(cat review.md)`. This file's own doctrine is that a shell string is not
# read; judging one anyway refuses correct work on text nobody wrote. So it is
# ALLOWED and the allow says which text it could not see.
#
# `$(` AND NOTHING ELSE, and the cut is measured over THE SET THIS CONSTANT CAN
# REACH -- which is the correction that matters, because the first measurement
# of it was taken over a wider set; the numbers below are the cost over the set
# this constant reaches. `_judgeable` is called on a body that arrived as a FLAG
# TOKEN and on nothing else: a `--body-file` body returns before it, and so does
# a heredoc. In the allow corpus, 23 bodies arrive by flag token and 44 by
# `--body-file`; 43 of the 44 carry a backtick and were never affected either
# way, and exactly ONE of the 23 did. So the first cut's backtick cost one
# corpus row, not "most comments" -- and that row is still the reason to make
# the cut, because its backticks are BACKSLASH-ESCAPED and so cannot be
# substitution under any reading: it was judged and refused at e73ec4b and
# allowed unjudged at 7804eaf. This cut leaves 7 corpus rows unjudged, all 7
# holding a real `$(`.
#
# THE COST OF THE CUT, stated: a body holding a real `` `cmd` `` or `${VAR}` is
# now judged on its SOURCE. That direction is a refusal, not a pass, and a
# refusal is the direction to fail in. shlex has already resolved the quoting by
# the time this runs, so a literal backtick and a substituting one are
# indistinguishable here; reading the raw command instead is the fix that would
# tell them apart, and it is not paid for by one hypothetical body.
#
# ...AND WHAT THE CUT DOES NOT CLOSE, in the ALLOW direction, which is the half
# a cost paragraph usually omits: `$((1+2))` in a literal body still reads as a
# substitution and is allowed unjudged, and so is a deliberately escaped `\$(`.
# The escaped-literal class the backtick row demonstrated therefore survives for
# `$(`; closing it needs the raw command, same as above.
SUBSTITUTION = ("$(",)


def flag_value(tokens, names):
    """The value of the first of `names` present, or None.

    Three spellings, and the reason all three are read is that a check covering
    two of them refuses the careful and passes the careless: `--x V`, `--x=V`,
    and for a shorthand in `SHORT_FLAGS` the attached `-xV` that pflag accepts
    and this once let through unread.

    Returns `SKIPPED` -- not None -- when the only candidate value was itself
    one of this reader's flags. The caller must tell "there is no body here"
    from "the body was a word I refused to read"."""
    skipped = []
    for j, t in enumerate(tokens):
        # A FLAG OF THIS READER IS NOT ITS OWN NEIGHBOUR'S VALUE. `--comment` is
        # scanned before `-b` and is valued on the close/reopen verbs, so
        # `--comment -b '<text>'` returned the literal `-b` and refused on
        # shape. Skipped only for the flags NAMED in `KNOWN_FLAGS` -- a body may
        # perfectly well begin with `-`, as every bullet list does, and a
        # blanket "starts with a dash" test would drop those.
        #
        # IT IS THIS READER'S FLAG SET AND NOT `gh`'s, stated because the two
        # differ: `gh issue close 7 -c -R owner/repo` reads `-R` as the body and
        # refuses on shape. `gh` rejects a value-less `-c` itself, so nothing
        # reaches that in practice, and widening the set to `gh`'s whole grammar
        # is the second grammar this file declines to keep.
        #
        # AND A BODY WHOSE TEXT *IS* ONE OF THEM IS NOT SILENTLY DROPPED. The
        # first cut of this skip returned None for `--body '-b'`, which posts a
        # comment nothing checked -- the absence-as-a-pass this file exists to
        # refuse. It comes back as UNJUDGED instead, which is an allow that says
        # so, because the alternative is asserting a shape nobody read.
        if t in names and j + 1 < len(tokens):
            if tokens[j + 1] not in KNOWN_FLAGS:
                return tokens[j + 1]
            skipped.append(tokens[j + 1])
        if "=" in t and t.split("=", 1)[0] in names:
            return t.split("=", 1)[1]
        for short in names & SHORT_FLAGS:
            if len(t) > len(short) and t.startswith(short) and t[len(short)] != "=":
                return t[len(short):]
    return SKIPPED if skipped else None


def comment_body(tokens, heredocs, cwd=None):
    """(text, why_unreadable, why_unjudged) for the comment this segment posts;
    (None, None, None) when it posts none. At most one of the three is set.

    THE THIRD IS AN ALLOW AND THE OTHER TWO ARE REFUSALS, and they are separate
    because they are different readings: `why_unreadable` is "I could not look"
    at a file that should have been there, and `why_unjudged` is "there is
    nothing here to look AT" -- a body the shell will compose and this guard
    never sees. Collapsing them would either refuse the second, which refuses
    correct work, or allow the first, which is the absence-as-a-pass this whole
    check exists to avoid.

    FOUR SPELLINGS OF ONE THING, and the reason they are all read here is that
    a check covering three of them refuses the careful and passes the careless.
    `--body-file -` is stdin, which in every form this guard sees is the
    heredoc; a `--body-file` naming a real path is opened.

    `cwd` IS THE PAYLOAD'S AND NOT THIS PROCESS'S. A hook runs wherever the
    harness starts it, so resolving a relative `--body-file` against
    `os.getcwd()` would read a different file from the one the shell is about
    to, or none -- and an absence indistinguishable from a body with no kind on
    it is the whole failure mode this check exists to avoid. Unreadable is
    therefore a REFUSAL that names the resolved path, never a silent pass."""
    words = gh_words(tokens)
    pair = tuple(words[:2])
    if pair in COMMENT_WRITES:
        pass
    elif pair in COMMENT_FLAG_WRITES:
        # THE GATE ADMITS `-c…` AS THE SHORTHAND, and says so rather than
        # pretending to be narrower. A standalone `-c` is already caught by
        # `t in COMMENT_FLAG`, so this clause exists for the ATTACHED `-cTEXT`
        # alone -- and it therefore also admits any other `-c…` word on these
        # four verbs, `-check` included, which `flag_value` then reads as the
        # body `heck` and refuses on shape. No flag `gh` accepts on
        # `issue close|reopen` or `pr close|reopen` collides today; the
        # alternative is this guard keeping a second copy of `gh`'s grammar,
        # which is the cost it declines everywhere else.
        if not any(t in COMMENT_FLAG or t.startswith("--comment=")
                   or (t.startswith("-c") and not t.startswith("--"))
                   for t in tokens):
            return None, None, None
        # ...AND HERE ONLY IS IT VALUED. On these verbs `--comment` carries the
        # text; on `gh pr review` it is the review's kind and carries nothing.
        text = flag_value(tokens, BODY_VALUED | COMMENT_FLAG)
        if text is SKIPPED:
            return None, None, SKIPPED_NOTE
        if text is not None:
            return _judgeable(text)
    else:
        return None, None, None
    text = flag_value(tokens, BODY_VALUED)
    if text is SKIPPED:
        return None, None, SKIPPED_NOTE
    if text is not None:
        return _judgeable(text)
    path = flag_value(tokens, BODY_FILE_VALUED)
    if path is SKIPPED:
        return None, None, SKIPPED_NOTE
    if path is not None and path != "-":
        here = Path(cwd) if cwd is not None else Path.cwd()
        resolved = Path(path) if Path(path).is_absolute() else here / path
        try:
            return resolved.read_text(encoding="utf-8"), None, None
        except OSError as e:
            return None, (f"`{path}` -> {resolved} could not be read "
                          f"({e.__class__.__name__}), so the comment's shape "
                          f"was not read either"), None
    if heredocs:
        return heredocs[0], None, None
    # A `gh pr review --approve` with no body posts a review and no comment; a
    # `gh issue comment` with neither is interactive. Neither has text to check
    # and neither is a shape this can judge.
    return None, None, None


def _judgeable(text):
    """The three-tuple for a body token: judged, or unjudged with the reason.

    The one unjudged case is a command substitution: shlex expands nothing, so
    what arrives here is the SOURCE and never the value."""
    if any(x in text for x in SUBSTITUTION):
        return None, None, (f"its body is composed by the shell "
                            f"({text[:60]!r}), so this guard never sees the "
                            f"text and did not judge it")
    return text, None, None


def comment_findings(text):
    """(every way this comment's shape is wrong, the reason the first line was
    not judged). The CEILING is still measured when the first line cannot be:
    it needs no pattern, and dropping it too would let an unreadable name rule
    silence a second, unrelated check."""
    out = []
    first = text.strip().splitlines()[0] if text.strip() else ""
    pattern = comment_first_line()
    if pattern is not None and not pattern.match(first):
        out.append(f"its first line is {first[:80]!r}, which is not "
                   f"`KIND <session name|owner>: <one line>`. KIND is one of "
                   f"{', '.join(COMMENT_KINDS)}, one intent per comment")
    if len(text) > COMMENT_CEILING:
        out.append(f"it is {len(text)} characters, over {COMMENT_CEILING}")
    return out, (None if pattern is not None else FIRST_LINE_UNREADABLE)


def issue_target(tokens):
    """The issue number a `gh issue <verb> <n>` names, or None. A write that
    names its sub-issue is narrowed to a claim on it."""
    words = gh_words(tokens)
    if words[:1] != ["issue"]:
        return None
    for t in words[2:]:
        # A PATH IS NOT AN ISSUE NUMBER. Reading the tail of any token with a
        # slash made `--body-file /tmp/123` name issue #123 and refused the
        # write for a claim on a number nobody typed. Only a GitHub issue URL
        # has a tail worth reading; everything else must BE the number.
        bare = t.lstrip("#")
        if bare.isdigit():
            return bare
        if "/issues/" in t:
            tail = t.rstrip("/").rsplit("/", 1)[-1]
            if tail.isdigit():
                return tail
    return None


# WHAT THE EXIT SAID, kept for the log. Every exit goes through `refuse` or
# `allow`, so this is the one place a verdict can be caught without threading a
# return value through thirty call sites -- and `main` writes it after `pre`
# returns, so a log write can never change a verdict.
LAST = {}


def refuse(lines):
    LAST.update(verdict="REFUSED", reason=lines[0] if lines else "")
    print("check-campaign-claim: REFUSED.\n  " + "\n  ".join(lines), file=sys.stderr)
    return 2


def allow(lines):
    LAST.update(verdict="allowed", reason=lines[0] if lines else "")
    print("check-campaign-claim: allowed. " + " ".join(lines))
    return 0


def log_path(target, cwd: Path):
    """(the log file, how it was chosen). A verdict is written under the
    CAMPAIGN it was classified into, so a campaign's precision can be read
    without separating it from every other session on the machine; a call in a
    base but no campaign goes to the base's own log; a call under no base at
    all is not campaign work and is not logged.

    `<campaign>/runtime/` and `<base>/runtime/` are both git-ignored, which is
    the point: the log is machine-local scratch and is never committed."""
    for start in ([target] if target is not None else []) + [cwd]:
        main, _top, _note = checkout_of(start)
        base = main if main is not None and (main / BASE_MARKER).is_file() \
            else base_above(start)
        if base is None:
            continue
        camp = campaign_dir_of(start, base)
        root = camp if camp is not None else base
        return root / "runtime" / "guard.log", f"{root}/runtime/guard.log"
    return None, "under no base, so not campaign work and not logged"


def log_verdict(payload, status, target, cwd: Path):
    """Append one line, and return what to say about having done so.

    THE FAILURE MODE OF A MECHANISED RULE IS SILENCE, so this never raises and
    never swallows: a write that did not happen comes back as a sentence the
    caller prints beside the verdict. A guard that logs nothing and says
    nothing reads exactly like a guard that logged."""
    path, how = log_path(target, cwd)
    if path is None:
        return f"verdict not logged: {how}"
    tool_input = payload.get("tool_input") or {}
    row = {
        "at": datetime.datetime.now(datetime.timezone.utc)
                      .isoformat(timespec="seconds"),
        "session": payload.get("session_id") or "",
        "tool": payload.get("tool_name", ""),
        "status": status,
        "verdict": LAST.get("verdict", "?"),
        # The sentence the branch alone prints. `guard-precision.py` groups on
        # it, which is why it is stored whole rather than as a slug nobody
        # would keep in step with the sentences.
        "reason": LAST.get("reason", ""),
        "target": str(target) if target is not None else "",
        "command": (tool_input.get("command") or "")[:200],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError as e:
        return f"verdict not logged to {how} ({e.__class__.__name__})"
    return f"logged to {how}"


TAKE = ("Take the claim first: scripts/campaign-claim.py take <campaign issue> "
        "<issue> <topic>, then work in a checkout on its branch.")


def file_call(tool, target: Path, cwd: Path, session_id=""):
    inside, where, top, scratch = classify(target)
    if not inside:
        return allow([f"{tool} -> {target} is {where}; not campaign work."])
    read = [f"{tool} -> {target}, {where}."]
    campaign, role, how_role = role_of(session_id)
    read.append(how_role if role else
                f"{how_role}, so the role could not be read; falling back to "
                f"the claim reading alone, which is what this gate was "
                f"before #185.")
    # `role is not None` FIRST, and it is not redundant: `role_of` returns
    # None when it could not read herdr OR the table, and evaluating
    # `roles()` here would re-raise the very failure it just turned into
    # could-not-look -- refusing every session on this machine instead of
    # falling back to the claim reading. Measured: with campaign-roles.py
    # removed, the unguarded form refused a claimed worker's own worktree.
    if role is not None and role == roles().NO_ROLE:
        return refuse(read + [NAMELESS])
    if role == "planner":
        # A PLANNER NEVER TOUCHES CODE, and a checkout is where code lives:
        # a base tree, a linked worktree, a delegate clone, a member
        # repository. A campaign DIRECTORY is campaign-plane scratch, which a
        # planner is precisely for -- refusing it would stop a planner keeping
        # the notes it plans from, and #185 puts the campaign directories on
        # the campaign plane beside the issues.
        #
        # NOT keyed on `top` alone: a campaign directory sits at the base
        # root, so a target under it reports the base as its checkout too.
        # `scratch` is the question actually being asked -- in a campaign
        # directory AND in no checkout of its own.
        if not scratch and top is not None:
            return refuse(read + [
                f"a planner may not change code, and {target} is in the "
                f"checkout {top}.",
                "Hand it to a worker: a session of its own on this "
                "machine, or a herdr delegate in the repository clone.",
            ])
        return allow(read + ["a planner writes the campaign plane, and a "
                             "campaign directory outside every checkout is "
                             "campaign-plane scratch."])
    if top is not None:
        branch, is_claim, source = claim_on(top)
        # ITS OWN CAMPAIGN, HERE TOO. Clause 1 asks only whether the target's
        # checkout is on SOME claim, and #185's bound was added to clause 2 and
        # to the gh loop but not here -- so a worker of another campaign,
        # with its role read correctly, edited this campaign's worktree. The
        # docstring said otherwise, which is what makes it a finding rather
        # than a gap.
        if is_claim and role == "worker" and campaign is not None \
                and claim_token(branch) != campaign:
            return refuse(read + [
                f"Clause 1 would hold -- {top} is on {branch} -- but that is a "
                f"claim of another campaign, and this session is of campaign "
                f"`{campaign}`.", TAKE])
        if is_claim:
            return allow(read + [f"Clause 1: the target's checkout {top} is on "
                                 f"{branch}, a claim ({source})."])
        read.append(f"Clause 1 does not hold: {source}.")
    root, how = session_root(cwd)
    if root is None:
        return refuse(read + [how, "No checkout to read a claim from.", TAKE])
    holders, detail = held(root)
    if role == "worker" and campaign is not None:
        # ITS OWN CAMPAIGN AND NO OTHER. The clauses ask whether SOME claim
        # covers the target; the name says which campaign this session is of,
        # so a claim of another campaign is not this session's to stand on.
        kept = [h for h in holders
                if claim_token(h[1]) == campaign]
        if holders and not kept:
            return refuse(read + [
                f"the claims under {root} are of another campaign, and this "
                f"session is of campaign `{campaign}`.",
                *[f"{h[0]} is on {h[1]}" for h in holders], TAKE])
        holders = kept
    if holders:
        path, branch, source = holders[0]
        return allow(read + [f"Clause 2 (the weaker gate; the commit gate is "
                             f"what holds): {how}; {path} is on {branch}, a "
                             f"claim ({source})."])
    return refuse(read + [f"Clause 2 does not hold: {how}.", *detail, TAKE])


def bash_call(command, cwd: Path, session_id=""):
    pairs, why = paired_segments(command)
    segs = None if pairs is None else [t for t, _ in pairs]
    if segs is None:
        # NAMES ONLY WHAT IT READ (#193 defect 2). This used to print "A gh
        # call this cannot split is not read as harmless" for a command with no
        # `gh` in it at all, sending the next reader to rule out a call nobody
        # made. What was actually observed is that the text could not be split,
        # so that is what it says -- and whether a `gh` was among the words is
        # a separate line, printed only when one was.
        seen = [t for t in command.split() if gh_token(t)]
        return refuse([
            why,
            f"the text it could not split, from the start: {command[:120]!r}",
            (f"a `gh` is among its words ({seen[0]}), and which write it makes "
             f"could not be read"
             if seen else
             "no `gh` was seen in it, and none was ruled out either: this "
             "guard finds a write by reading the command, so one it cannot "
             "read is refused rather than assumed harmless"),
            "A heredoc body is not part of this: it is removed before the "
            "split, so a commit message with an apostrophe in it is data.",
        ])
    gh, stray = [], []
    for seg in segs:
        word, rest = head(seg)
        if word == "gh":
            gh.append((rest, *gh_write(rest)))
        elif any(gh_token(t) for t in seg):
            # A form not listed, a heredoc, xargs: read as a write of unknown
            # kind, because nothing downstream reads a gh write.
            stray.append(" ".join(seg)[:60])
    writes = [rest for rest, is_write, _ in gh if is_write]
    if not writes and not stray:
        return allow([f"{what}." for _, _, what in gh]
                     + ["The command was not read for a target: only a file "
                        "tool's path and a gh write are; its write, if any, is "
                        "gated where it lands, by the pre-commit claim gate."])
    what = ", ".join([w for _, is_write, w in gh if is_write]
                     + [f"a `gh` this cannot read as a call, in `{x}`" for x in stray])
    root, how = session_root(cwd)
    # IS THIS CAMPAIGN WORK AT ALL -- asked before the role, and that order is
    # the whole of it. Asked after, a session whose name is not campaign-shaped
    # was refused every `gh` write anywhere on this machine, including in
    # repositories that have nothing to do with any campaign. This guard is
    # registered for every session here, so that is an outage and not a gate.
    if root is None or not (root / BASE_MARKER).is_file():
        why = how if root is None else f"{how}, which is a repository and not a base"
        return allow([f"{what}: {why}, so this session is in no campaign."])
    # THE COMMENT'S SHAPE, before the claim and before the role (#217). It is a
    # different question from both: a session with every claim in the world may
    # not post a comment with no kind on it, and a comment is the one campaign
    # write whose CONTENT this guard can read. Refused here so the diagnosis is
    # the shape, which names one edit, rather than the claim, which would send
    # the reader to take a claim it may already hold.
    shape, unread, unjudged = [], [], []
    for tokens, heredocs in pairs:
        word, rest = head(tokens)
        if word != "gh":
            continue
        text, why_body, why_unjudged = comment_body(rest, heredocs, cwd)
        if why_body:
            unread.append(why_body)
        elif why_unjudged:
            unjudged.append(why_unjudged)
        elif text is not None:
            found, why_shape = comment_findings(text)
            shape += found
            if why_shape:
                unjudged.append(why_shape)
    if shape or unread:
        return refuse([f"{what}: a comment whose shape does not hold.",
                       *[f"  {f}" for f in shape + unread],
                       f"The five kinds are {', '.join(COMMENT_KINDS)}; "
                       f"AGENTS.md § The four messages says which goes where. "
                       f"A `gh api ... -f body=` posts a comment and is NOT "
                       f"read here, which is this check's stated ceiling and "
                       f"not a route around it."])
    # CARRIED PAST THE CLAIM READING, not returned here: an unjudged comment is
    # still a campaign-plane write and still needs its claim. Folded into
    # `what`, which is the one string EVERY exit below prints -- three of them
    # do not carry `fell_back`, so a second list would go silent on exactly the
    # exits a reader is most likely to meet. An allow must never come back
    # looking like a comment that was read and passed.
    if unjudged:
        what += " [" + "; ".join(
            f"shape NOT checked: {u}" for u in unjudged) + "]"
    campaign, role, how_role = role_of(session_id)
    # Computed before the first exit that can use it: every exit of this
    # half that fell back says so, allows included. The allows used to be
    # silent, so an allow after a failed read looked like an allow after a
    # successful one.
    read_on = []
    fell_back = [] if role else [
        f"{how_role}, so the role could not be read; falling back to the "
        f"claim reading alone, which is what this gate was before #185."]
    # `role is not None` FIRST, and it is not redundant: `role_of` returns
    # None when it could not read herdr OR the table, and evaluating
    # `roles()` here would re-raise the very failure it just turned into
    # could-not-look -- refusing every session on this machine instead of
    # falling back to the claim reading. Measured: with campaign-roles.py
    # removed, the unguarded form refused a claimed worker's own worktree.
    if role is not None and role == roles().NO_ROLE:
        return refuse([f"{what}: a campaign-plane write.", how_role, NAMELESS])
    if role == "planner":
        # THE ROW THAT PROMPTED #185. A planner writes the campaign plane of
        # ANY campaign -- a comment on a campaign issue it does not work, a
        # sub-issue body, a close, a claim cut for a delegate. There is no
        # claim to hold for any of those, which is why the claim reading alone
        # had no passing form for them and the closes were run by hand.
        #
        # THE CAMPAIGN PLANE ONLY. Every write in this command must be one, or
        # the licence does not apply and the claim reading decides as it would
        # for anyone: a `gh pr merge` is not a planner's by role, whatever its
        # name says.
        # READ AS A PAIR, and reduced to the subcommand only where the plane
        # is what is being asked. The table's `gh` is keyed on the subcommand
        # because the plane is a property of it; its `gh_except` is keyed on
        # the pair because the exception is a property of one verb.
        licence = roles().ROLES["planner"]
        pairs = set()
        for rest, is_write, _ in gh:
            if not is_write:
                continue
            w = gh_words(rest)
            pairs.add(((w[0] if w else ""), (w[1] if len(w) > 1 else "")))
        verbs = {sub for sub, _ in pairs}
        excepted = sorted(f"{sub} {verb}"
                          for sub, verb in pairs & licence["gh_except"])
        if verbs and verbs <= licence["gh"] and not excepted and not stray:
            return allow([f"{what}: {how_role}, and a planner writes the "
                          f"campaign plane of any campaign."])
        read_on = [f"{how_role}, but `gh {v}` is not the campaign plane, so "
                   f"the planner licence does not cover it"
                   for v in sorted(verbs - licence["gh"])]
        # A REFUSAL AND NOT A SENTENCE. The first cut of this only appended to
        # `read_on` and fell through to the claim reading, which allowed a
        # planner `gh issue develop 9` outright whenever ANY worktree on this
        # machine sat on a claim for #9 -- and the planner's own
        # `campaign-claim take` before a delegate launch creates exactly that
        # state. A licence removal that leaves the write allowed is not a
        # removal, and the sentence in scenarios.als saying so was false. Found
        # by the review of 48dd5fc.
        #
        # IT CARRIES `how` AND `read_on` OUT WITH IT, which the first cut of
        # the return dropped: a refusal on `gh pr merge 5 && gh issue develop 9`
        # named the develop and went silent about the merge and about how the
        # root was resolved. #191 item 1 is the rule -- every exit says what it
        # read -- and an early return is exactly where it gets broken.
        if excepted:
            # `how_role` IS NOT REPEATED HERE. Every entry of `read_on` already
            # opens with it, and this header printed it a second time on a
            # mixed write -- `gh pr merge 5 && gh issue develop 9` -- where
            # both the header and the licence line fired
            # (kalaluthien/campaign-base#213's review). `read_on or [how_role]`
            # and not `read_on` alone: a bare `gh issue develop 9` leaves
            # `read_on` EMPTY, since `issue` is in the table's `gh` and only the
            # pair is excepted, so dropping the header outright would have lost
            # the role reading on exactly the command this branch is for.
            return refuse([f"{what}.", how, *(read_on or [how_role]), *[
                f"`gh {v}` cuts a branch in the sub-issue's own repository "
                f"without reading the binding, the sub-issue's parent, or the "
                f"campaign issue's `## Repos`, so the planner licence does not "
                f"cover it. This reads no flags, so a `--list` is refused with "
                f"it." for v in excepted], TAKE])
        if not read_on:
            read_on = [f"{how_role}, but a gh call this cannot read is not "
                       f"covered by the planner licence"]
    # EVERY issue named must be covered, not one of them. Collapsing two to
    # `None` and asking for any claim at all is a WIDENING: it let a claim on
    # #7 admit `gh issue close 9; gh issue close 7`, and a decoy naming a
    # claimed issue was the shape a review turned into a bypass. A write whose
    # issue this could not read still falls back to the unnarrowed question,
    # which is the weaker gate and is printed as such.
    # (issue, subcommand, verb) per write, so the carve-out below can ask what
    # is being DONE and not only to which number.
    per_write = []
    for x in writes:
        w = gh_words(x)
        per_write.append((issue_target(x),
                          (w[0] if w else ""), (w[1] if len(w) > 1 else "")))
    issues = sorted({i for i, _, _ in per_write} - {None})
    unreadable = stray or any(issue_target(x) is None for x in writes)
    own = own_claim(cwd)
    # THE NUMBER, not the token. The carve-out below compares against an issue
    # number typed on a `gh` line, and since #181 a session name carries a slug;
    # everything else in this function compares token against token.
    own_number = campaign_number(campaign, root) if campaign is not None else None
    detail, uncovered, covering = [], [], []
    carved = False
    for i in issues:
        holders, d = held(root, i)
        if (not holders and own is not None
                and claim_issue(own[1]) == i
                and (role != "worker" or campaign is None
                     or claim_token(own[1]) == campaign)):
            holders = [own]
        # ITS OWN CAMPAIGN'S ISSUE NEEDS NO CLAIM, because no claim can ever
        # cover it: the campaign issue is nobody's sub-issue, so `held` finds
        # nothing there for anyone and every worker was refused a comment on
        # the campaign it works. What licenses it is the session's NAME, which
        # carries that campaign's number -- the same fact the rest of this
        # branch reads. A planner reaches the same write through its own row,
        # on any campaign; this is the worker's, on one (#207).
        if (role == "worker" and own_number is not None and i == own_number
                and all((sub, verb) in roles().ROLES["worker"]["own_campaign_gh"]
                        for j, sub, verb in per_write if j == i)):
            covering.append((i, [("its own campaign", campaign,
                                  "the session name")]))
            carved = True
            continue
        # A WORKER STANDS ONLY ON ITS OWN CAMPAIGN'S CLAIMS, and the filter
        # belongs HERE, per issue. Applied once to the whole root instead, it
        # refused only when EVERY claim was foreign -- so a worker of #1
        # with any claim of its own under the root was admitted to write
        # another campaign's sub-issue, the foreign claim named as the cover.
        # `file_call` filtered per call from the start; this half did not, and
        # the two disagreed on exactly that shape.
        if role == "worker" and campaign is not None:
            foreign = [h for h in holders
                       if claim_token(h[1]) != campaign]
            holders = [h for h in holders if h not in foreign]
            detail += [f"{h[0]} is on {h[1]}, a claim of another campaign; "
                       f"this session is of campaign `{campaign}`"
                       for h in foreign]
        detail += d
        (covering if holders else uncovered).append((i, holders))
    # THE NARROWEST REFUSAL WINS, and that is a rule now rather than the order
    # these branches happen to be written in (kalaluthien/campaign-base#191
    # item 1). A mixed command -- `gh issue close 9 && gh pr merge 5`, where
    # the first names an issue and the second names a pull request -- reaches
    # both this branch, on #9, and the `unreadable` fallback, on the merge.
    # The one that names a NUMBER is the better diagnosis: it tells the reader
    # which claim to take, where the fallback can only say "some claim". So an
    # uncovered named issue is reported first, and the fallback decides only
    # when every named issue is covered. It changes no verdict -- both branches
    # refuse -- and it fixes which sentence the reader gets.
    if uncovered:
        i = uncovered[0][0]
        return refuse([f"{what}: a campaign-plane write, and this session holds "
                       f"no claim covering a write to #{i}.", how, *read_on,
                       *fell_back, *detail, TAKE])
    if unreadable and carved:
        # THE CARVE-OUT COVERS ITS OWN WRITE AND NOTHING BESIDE IT. Without
        # this, `gh issue comment 1 && gh pr merge 12` was admitted: the
        # comment satisfied the campaign issue, the merge fell to the
        # unnarrowed fallback, and any claim under the root carried it out.
        return refuse([f"{what}: the campaign issue is covered by this "
                       f"session's name, and that covers no other write in "
                       f"the same command.", how, *read_on, *fell_back,
                       *detail, TAKE])
    if unreadable:
        holders, d = held(root)
        if role == "worker" and campaign is not None:
            holders = [h for h in holders
                       if claim_token(h[1]) == campaign]
        if (not holders and own is not None
                and (role != "worker" or campaign is None
                     or claim_token(own[1]) == campaign)):
            holders = [own]
        if not holders:
            return refuse([f"{what}: a campaign-plane write, and this session "
                           f"holds no claim covering it.", how, *read_on,
                           *fell_back, *detail, *d, TAKE])
        path, branch, source = holders[0]
        return allow([f"{what}: {how}; {path} is on {branch}, a claim "
                      f"({source}).", *fell_back])
    # WHAT USED TO BE HERE: a second `own_claim` allow and a second refusal,
    # for the state where `covering` is empty and `unreadable` is false. That
    # state cannot be reached (kalaluthien/campaign-base#192 item 2). `issues`
    # is empty only when no write named a number, which makes `unreadable`
    # true and returns above; a non-empty `issues` puts every entry in
    # `covering` or in `uncovered`, and `uncovered` returns above too. A
    # sentinel-instrumented copy took 0 hits over 16 commands against 5
    # fixtures. Deleted rather than kept as a comfort: a branch nothing reaches
    # is a branch nothing tests, and it read as a second, differently-worded
    # answer to a question already answered.
    path, branch, source = covering[0][1][0]
    named = ", ".join(f"#{i}" for i, _ in covering)
    if path == "its own campaign":
        return allow([f"{what}: {how_role}, and #{covering[0][0]} is the "
                      f"campaign issue of the campaign this session is of.",
                      *read_on, *fell_back])
    return allow([f"{what}: {how}; {path} is on {branch}, a claim "
                  f"({source}). It covers {named}.", *fell_back])


def pre(payload):
    session_id = payload.get("session_id") or ""
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    try:
        cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
        if tool in FILE_TOOLS:
            raw = next((tool_input.get(k) for k in PATH_KEYS if tool_input.get(k)),
                       None)
            if not raw:
                return refuse([f"{tool} names no path this can read."])
            target = (cwd / Path(os.path.expanduser(str(raw)))).resolve()
            LAST["target"] = target
            return file_call(tool, target, cwd, session_id)
    except (OSError, RuntimeError) as e:
        return refuse([f"a path would not resolve ({e.__class__.__name__})."])
    if tool == "Bash":
        return bash_call(tool_input.get("command") or "", cwd, session_id)
    return 0


def main() -> int:
    # THE PAYLOAD THAT WOULD NOT READ IS A VERDICT TOO, and it used to return
    # here -- past the log write below, so the one refusal that means the guard
    # was handed something broken was the one refusal nothing recorded and
    # nothing said was unrecorded. That is the exact silence this file argues
    # against. `payload` is empty, so the row carries no session and no
    # command, which is what there was to read.
    try:
        payload = json.load(sys.stdin)
        # KEPT FOR THE LAST RESORT below, which has no other way to reach it:
        # a row logged without the session id is a row `guard-precision.py`
        # cannot pair with anything, and `os.getcwd()` is the guard's own
        # directory rather than the call's.
        LAST["payload"] = payload
    except (ValueError, OSError) as e:
        payload = {}
        status = refuse([f"the hook payload would not read "
                         f"({e.__class__.__name__})",
                         "A guard that was handed nothing has permitted "
                         "nothing."])
        note = log_verdict(payload, status, None, Path(os.getcwd()))
        print(note, file=sys.stderr)
        return status
    event = payload.get("hook_event_name", "")
    if event and event != "PreToolUse":
        status = refuse([f"registered on {event}, but this is a PreToolUse guard "
                         f"and blocks nothing there. Re-run "
                         f"scripts/install-hooks.sh."])
    else:
        status = pre(payload)
    # THE VERDICT IS DURABLE (kalaluthien/campaign-base#196 step 1, spec rule
    # `verdictIsDurable`). Written AFTER the verdict is decided and printed, so
    # nothing about the log can change what this guard allows -- and its own
    # outcome is printed beside the verdict, because a log that quietly stopped
    # being written reads exactly like a log with nothing to say.
    try:
        cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    except OSError:
        cwd = Path(".")
    # THE VERDICT IS REACHED HERE, and the last resort below reads this to tell
    # its two cases apart: a crash BEFORE this line judged nothing, and a crash
    # after it -- in the log write, or anywhere past it -- must not turn a
    # decided REFUSED into an exit 0 announcing that nothing was judged.
    LAST["status"] = status
    note = log_verdict(payload, status, LAST.get("target"), cwd)
    print(note, file=sys.stderr if status else sys.stdout)
    return status


# THE LAST RESORT, and it is not a refusal. An exception escaping `main` exits
# 1, and the harness reads a non-zero-that-is-not-2 as the HOOK's own error and
# lets the tool call PROCEED -- so an unhandled bug here has always been a
# silent bypass, printed as a traceback nobody reads. This turns it into a loud
# allow: the guard says it failed and did not judge the call, in the wording
# every other could-not-look uses. It is deliberately NOT a refusal, because a
# blanket refusal turns any bug in this file into a wall across every session on
# the machine, which is the failure `role_of`'s fallback exists to prevent.
# Each site that CAN fail is still handled where it is, and named there; this
# only stops the ones nobody predicted from being invisible.
#
# ON STDOUT, like `allow`, and not on stderr like `refuse`: what a PreToolUse
# hook writes on an exit-0 path reaches the session through stdout, and a
# message on the channel the harness reads only for a refusal is a loud allow
# that nothing hears.
#
# AND IT WRITES ITS OWN ROW. `guard-precision.py` counts every non-REFUSED row
# as an allow, so a crash that logs nothing is indistinguishable from a guard
# with nothing to say -- a guard failing on EVERY call would read as a quiet
# one. The row is best effort by construction: whatever raised may be the very
# thing the log write needs, so its own failure is caught and said, never
# raised on top of the first.
if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:                   # noqa: BLE001 -- announced, not raised
        import traceback
        decided = LAST.get("status")
        LAST.update(verdict="GUARD FAILED",
                    reason=f"the guard raised {e.__class__.__name__}: {e}")
        crashed = LAST.get("payload") or {}
        try:
            note = log_verdict(crashed, 0 if decided is None else decided,
                               LAST.get("target"),
                               Path(crashed.get("cwd") or os.getcwd()))
        except Exception as e2:              # noqa: BLE001 -- the log is not the verdict
            note = (f"verdict not logged: the log write itself raised "
                    f"{e2.__class__.__name__}")
        if decided is None:
            print(f"check-campaign-claim: the guard FAILED and did not judge "
                  f"this call ({e.__class__.__name__}: {e}). The call is "
                  f"allowed unjudged; this is a defect in the guard, not a "
                  f"verdict. {note}")
            traceback.print_exc(file=sys.stderr)
            sys.exit(0)
        print(f"check-campaign-claim: the verdict was reached and STANDS "
              f"(exit {decided}); the guard then FAILED after it "
              f"({e.__class__.__name__}: {e}). This is a defect in the guard, "
              f"not a change to the verdict. {note}",
              file=sys.stderr if decided else sys.stdout)
        traceback.print_exc(file=sys.stderr)
        sys.exit(decided)
