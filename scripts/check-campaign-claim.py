#!/usr/bin/env python3
"""Refuse a changing call from a session holding no claim on the campaign it is in.

    check-campaign-claim.py    PreToolUse, reading the hook payload on stdin

The pre-tool-use half of the claim gate; scripts/check-commit-claim.py is the
commit half (spec/campaign/orchestration/scenarios.als, `claimBeforeWork` and
`claimBeforeCommit`). A claim is a `campaign-<N>/<issue>-<topic>` branch whose
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
to say. Both directories are git-ignored: this is machine-local scratch.

WHERE A FILE TARGET IS. A base tree -- main checkout, linked worktree anywhere,
delegate clone, all by `git rev-parse --git-common-dir` from the TARGET, never
from cwd -- or a campaign directory at a base root. Anything else is outside.

WHO MAY WRITE WHAT. A session's ROLE decides, read from its name through
`herdr agent list` and the pattern `campaign-name-session.py` owns: a PLANNER
writes the campaign plane of any campaign and changes no code, a WORKER
writes its own campaign and the sub-issue it claimed, and a name that pattern
does not admit is refused on both. A campaign directory is campaign-plane
scratch, but a CHECKOUT under one -- a member clone, a linked worktree -- is
code like any other. The role being unreadable is not the same as a name that
is not a campaign name: the first falls back to the claim reading below and
says so, because this guard runs for every session on this machine and a
failed read must not wall them all.

THE ROLE IS NOT A SECURITY BOUNDARY. A session can rename itself, so it can
name itself a planner; every session here also shares one `gh` account, so one
that renames itself already holds the power the name would grant. What this
buys is that the role is EXPLICIT and the mistake is LOUD, which is what the
guard is for. #194 is the sub-issue for tying the name to something the named
session did not choose.

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
BASE_MARKER = Path("scripts") / "campaign-claim.py"
# `<slug>-<YYMMDD>`: AGENTS.md's shape for a campaign directory at the root.
CAMPAIGN_DIR = re.compile(r"-\d{6}$")
# The claim's shape. Only `<N>` is read from it.
CLAIM_BRANCH = re.compile(r"^campaign-(\d+)/(\d+)-")

# A name that resolved to no role, as distinct from a role that could not
# be read at all. The table's last row refuses this one; the other falls
# back to the claim reading.
NO_ROLE = "no-role"
NAMELESS = ("A session with no campaign name has no role, and a session with "
            "no role is refused on both planes. Name it: "
            "scripts/campaign-name-session.py <pane> campaign-<N>-<role>-<n>")
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
# WHICH gh WRITES ARE THE CAMPAIGN PLANE. The planner licence is bounded by
# this and not by WRITES, which holds both planes: `gh pr create` is
# OpenPullRequest and `gh pr merge` is MergePullRequest, and
# `codePlaneEvents` in spec/campaign/orchestration/system.als puts the first on
# the code plane while the three merge conditions -- not a role -- hold the
# second. A planner allowed every WRITES row could open and merge pull
# requests and delete another worker's claim ref through `gh api`, which is
# the opposite of "a planner changes no code".
#
# Read as the SUBCOMMAND alone, because that is what the plane is a property
# of. Anything not here is not a planner's by this rule and falls through to
# the claim reading, which refuses it without a claim exactly as before.
PLANNER_GH = {"issue", "label"}

# THE ONE `gh issue` VERB THE LICENCE DOES NOT COVER
# (kalaluthien/campaign-base#213). `gh issue develop` cuts a branch in the
# sub-issue's own repository, and with `--name campaign-<N>/<issue>-<topic>`
# that
# branch IS a claim -- the same object `campaign-claim take` cuts. Bare, it
# names the branch `<issue>-<slug>`, which no reader here treats as a claim;
# the flag is one word away and this guard reads no flags, so the verb is
# judged by what it can cut and not by what a given spelling does cut.
# So the tempting argument, that `develop` belongs beside `gh pr create`
# on the code plane, is WRONG and was checked rather than assumed: `Claim` sits
# in `campaignPlaneEvents` and not in `codePlaneEvents`
# (spec/campaign/orchestration/system.als), and a planner cutting a claim for a
# delegate it is about to launch is precisely what the licence exists to buy.
#
# WHAT IS WRONG IS THE ROUTE, NOT THE PLANE. `campaign-claim take` reads the
# binding, reads the sub-issue's real parent, and refuses a sub-issue whose
# repository the campaign issue's `## Repos` list does not hold --
# `claimWithinScope` in spec/campaign/orchestration/scenarios.als, given a
# reader by #203. `gh issue develop` reads none of the three and cuts the ref
# anyway. Refusing it here leaves ONE route to a claim, which is the only
# condition under which that model rule has a reader at all.
#
# WHAT THIS DOES NOT CLOSE, stated rather than left to be discovered. This is
# the PLANNER branch, so it refuses a planner and nobody else. A session that
# is not a planner still reaches `gh issue develop 9` through the claim reading
# below, so one already holding a claim on #9 can cut a second, unscoped branch
# for it. That hole is strictly narrower -- it needs a claim on the very issue
# named -- and closing it means the guard reading the campaign issue's
# `## Repos` on a `gh` call, a `gh` call inside a `PreToolUse` hook, which is
# the cost #213 weighed and did not pay.
PLANNER_GH_EXCEPT = {("issue", "develop")}

# WHAT A WORKER MAY DO TO ITS OWN CAMPAIGN'S ISSUE WITHOUT A CLAIM. No claim
# can ever cover the campaign issue -- it is nobody's sub-issue -- so #207
# carved it out. Keyed on the VERB and not on the issue number, which is the
# conjunct the first cut was missing: `edit` is the charter body, which only
# `closing-campaign` step 4 writes; `close` closes the CAMPAIGN, a person's
# decision; `delete` and `transfer` are irreversible. A claim on some other
# sub-issue makes none of them safer, so the claim was never the missing test.
OWN_CAMPAIGN_GH = {("issue", "comment")}
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


def name_pattern():
    """`campaign-name-session.py`'s NAME regex, imported rather than restated.
    That script owns the shape; a second copy here would admit names it
    refuses, and the two would drift apart on the first change to either."""
    src = HERE / "campaign-name-session.py"
    spec = importlib.util.spec_from_loader(
        "cns", importlib.machinery.SourceFileLoader("cns", str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.NAME


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
    try:
        pattern = name_pattern()
    except Exception as e:                  # noqa: BLE001 -- reported, not raised
        return None, None, ("could not read the name pattern from "
                            "campaign-name-session.py "
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
        m = pattern.match(name)
        if not m:
            return None, NO_ROLE, (f"session {session_id} is named "
                                   f"{name or 'nothing'}, which the campaign "
                                   f"name pattern does not admit")
        role = "planner" if "-planner-" in name else "worker"
        return m.group(1), role, f"session {session_id} is {name}"
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


def campaign_dir_of(path: Path, base: Path):
    return next((d for d in [path, *path.parents]
                 if d.parent == base and CAMPAIGN_DIR.search(d.name)), None)


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
    if not branch or not CLAIM_BRANCH.match(branch):
        return branch, False, f"{top} is on {branch or 'no branch'}, not a campaign branch"
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
    repository. A delegate on its own pushed `campaign-<N>/...` branch there
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
    if not branch or not CLAIM_BRANCH.match(branch):
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
    claims = [(p, b, CLAIM_BRANCH.match(b)) for p, b in trees if CLAIM_BRANCH.match(b)]
    for path, branch, m in claims:
        if issue is not None and m.group(2) != str(issue):
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
    not split it. `punctuation_chars` makes `;`, `|`, `&` their own tokens."""
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
    for seg in list(out):
        mine = heredocs[taken:taken + seg.count("<<")]
        taken += seg.count("<<")
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
            more, why = segments(text)
            if more is None:
                return None, why
            out += more
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
    return out, None


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
    if role == NO_ROLE:
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
                and CLAIM_BRANCH.match(branch).group(1) != campaign:
            return refuse(read + [
                f"Clause 1 would hold -- {top} is on {branch} -- but that is a "
                f"claim of another campaign, and this session is of campaign "
                f"#{campaign}.", TAKE])
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
                if CLAIM_BRANCH.match(h[1]).group(1) == campaign]
        if holders and not kept:
            return refuse(read + [
                f"the claims under {root} are of another campaign, and this "
                f"session is of campaign #{campaign}.",
                *[f"{h[0]} is on {h[1]}" for h in holders], TAKE])
        holders = kept
    if holders:
        path, branch, source = holders[0]
        return allow(read + [f"Clause 2 (the weaker gate; the commit gate is "
                             f"what holds): {how}; {path} is on {branch}, a "
                             f"claim ({source})."])
    return refuse(read + [f"Clause 2 does not hold: {how}.", *detail, TAKE])


def bash_call(command, cwd: Path, session_id=""):
    segs, why = segments(command)
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
    campaign, role, how_role = role_of(session_id)
    # Computed before the first exit that can use it: every exit of this
    # half that fell back says so, allows included. The allows used to be
    # silent, so an allow after a failed read looked like an allow after a
    # successful one.
    read_on = []
    fell_back = [] if role else [
        f"{how_role}, so the role could not be read; falling back to the "
        f"claim reading alone, which is what this gate was before #185."]
    if role == NO_ROLE:
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
        # is what is being asked. `PLANNER_GH` is keyed on the subcommand
        # because the plane is a property of it; `PLANNER_GH_EXCEPT` is keyed
        # on the pair because the exception is a property of one verb.
        pairs = set()
        for rest, is_write, _ in gh:
            if not is_write:
                continue
            w = gh_words(rest)
            pairs.add(((w[0] if w else ""), (w[1] if len(w) > 1 else "")))
        verbs = {sub for sub, _ in pairs}
        excepted = sorted(f"{sub} {verb}" for sub, verb in pairs & PLANNER_GH_EXCEPT)
        if verbs and verbs <= PLANNER_GH and not excepted and not stray:
            return allow([f"{what}: {how_role}, and a planner writes the "
                          f"campaign plane of any campaign."])
        read_on = [f"{how_role}, but `gh {v}` is not the campaign plane, so "
                   f"the planner licence does not cover it"
                   for v in sorted(verbs - PLANNER_GH)]
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
            return refuse([f"{what}: {how_role}.", how, *read_on, *[
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
    detail, uncovered, covering = [], [], []
    carved = False
    for i in issues:
        holders, d = held(root, i)
        if (not holders and own is not None
                and CLAIM_BRANCH.match(own[1]).group(2) == i
                and (role != "worker" or campaign is None
                     or CLAIM_BRANCH.match(own[1]).group(1) == campaign)):
            holders = [own]
        # ITS OWN CAMPAIGN'S ISSUE NEEDS NO CLAIM, because no claim can ever
        # cover it: the campaign issue is nobody's sub-issue, so `held` finds
        # nothing there for anyone and every worker was refused a comment on
        # the campaign it works. What licenses it is the session's NAME, which
        # carries that campaign's number -- the same fact the rest of this
        # branch reads. A planner reaches the same write through its own row,
        # on any campaign; this is the worker's, on one (#207).
        if (role == "worker" and campaign is not None and i == campaign
                and all((sub, verb) in OWN_CAMPAIGN_GH
                        for j, sub, verb in per_write if j == i)):
            covering.append((i, [("its own campaign", f"campaign-{campaign}",
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
                       if CLAIM_BRANCH.match(h[1]).group(1) != campaign]
            holders = [h for h in holders if h not in foreign]
            detail += [f"{h[0]} is on {h[1]}, a claim of another campaign; "
                       f"this session is of campaign #{campaign}"
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
                       if CLAIM_BRANCH.match(h[1]).group(1) == campaign]
        if (not holders and own is not None
                and (role != "worker" or campaign is None
                     or CLAIM_BRANCH.match(own[1]).group(1) == campaign)):
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
    note = log_verdict(payload, status, LAST.get("target"), cwd)
    print(note, file=sys.stderr if status else sys.stdout)
    return status


if __name__ == "__main__":
    sys.exit(main())
