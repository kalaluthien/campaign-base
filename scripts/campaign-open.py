#!/usr/bin/env python3
"""Open a chore in one command: file it, bind it, scaffold it, acquire it, claim it.

    scripts/campaign-open.py --chore <slug> --title <title> --body-file <path>
                             [--topic <topic>] [--issue <N>]

A CHORE IS A CAMPAIGN ISSUE THAT IS ITS OWN ONE UNIT OF WORK -- it carries the
`chore` label beside `campaign`, has no sub-issue, and is claimed and worked as
itself by one session named `<slug>-worker-1` (AGENTS.md § Chores). It keeps
every gate a campaign has, because it IS a campaign; what differs is its shape,
and `campaign-tracker.py`'s `CHORE_SECTIONS` owns that.

WHY ONE COMMAND. Opening a chore by hand is `opening-campaign` steps 2 to 5
read off a page and typed out, and a chore is by definition too small to pay
that: the owner's bar is one command and no needless work per chore. So the
steps below are that skill's, in Python, in its order, with each guard kept for
the reason the skill gives. `--chore` is a FLAG and not the shape of the whole
script, so the skill can call these steps for an ordinary campaign later; today
it serves chores only (rule-check#475, DECISION 5718434752 D3) and refuses
without the flag, because an ordinary campaign is still opened by the skill --
its step 2 proposes a name to a person and its step 6 files the first
sub-issues, and neither is a thing a script decides.

THE STEPS, each a function, each printing what it read, from where, and which
branch it took:

  1  shape     the slug, the title, the body and the `## Repos` list, BEFORE
               anything is written -- every reading here is pure or local, so a
               chore that would be malformed costs no issue and no label.
  2  survey    `campaign-tracker.py campaign-issues`, printed in the same
               breath as the create: the routing gate's survey is minutes old
               and two sessions that each surveyed before either filed both
               file (SKILL.md step 3). This cannot judge Scope; it prints and
               goes on, and the caller reads it.
  3  create    the `campaign:<slug>` label FIRST, because `gh label create`
               failing on an existing name IS the uniqueness gate and a label
               minted after the issue would let a second chore be filed under a
               spent slug. Never `--force`. The `chore` label is the one create
               here that tolerates "already exists": it is shared by every
               chore, so its existence gates nothing.
  4  read back `gh issue view --json labels,parent`: the three labels and a null
               parent. A campaign issue filed without its label is invisible to
               every later survey, and a non-null parent means a sub-issue was
               filed instead.
  5  bind      `campaign-tracker.py bind` then `bound`, read as the WORD `here`.
               Everything after this step is a write or a claim, and both are
               gated on the binding.
  6  scaffold  SKILL.md step 4: the directory is FOUND by its marker and never
               composed from the slug, `mkdir` without `-p` is the atomic gate
               between two sessions arriving on one day, and a `mark` that
               refuses takes this run's own directory with it.
  7  acquire   `acquire-repo.sh` per line of `runtime/repos`, by absolute path.
               `- none` is zero lines and no special case.
  8  name      `<slug>-worker-1`. A chore has no planner, so there is one
               session and one counter value. A FAILED rename is a stop: a
               session carrying another campaign's name is skipped by that
               campaign's close gate wherever it sits.
  9  claim     `campaign-claim take <N> <N> <topic>` -- the issue claimed is the
               campaign issue. It is cut only where WHERE is unambiguous: the
               base when `## Repos` is `- none`, the one entry when there is
               one. Several entries print one `take` line each and cut nothing,
               because which of them this chore changes is the worker's reading
               and a ref cut for a repository it never touches is a claim
               nobody releases.

THE WORD AND NOT THE EXIT STATUS is how `campaign-directory.py`,
`campaign-tracker.py bound` and `campaign-repos.py` are read here: each answers
a word whose status is a second, coarser copy -- `none` exits 1 and is an
answer, not a failure.

WHAT A STOP OWES ITS CALLER. Every step that fails says which step, what is
already done and NOT rolled back, and the exact line to resume with. `--issue
<N>` is that resume: it skips the uniqueness reading, the survey and the create
-- the slug is spent by this very issue by then -- and every step after the
create is written to be safe to re-run.

TWO TREES, NAMED APART. The scripts, the skill's assets and `acquire-repo.sh`
are addressed from THIS file's own directory, so a copy running in a worktree
uses that worktree's; `$BASE` is resolved the one way AGENTS.md states and is
used for where the campaign directory lives, which is the main checkout by
definition.

Exit 0 when the chore is open, 1 when a step stopped, 2 on a usage refusal.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRACKER_PY = HERE / "campaign-tracker.py"
CLAIM_PY = HERE / "campaign-claim.py"
REPOS_PY = HERE / "campaign-repos.py"
DIRECTORY_PY = HERE / "campaign-directory.py"
SKILL = HERE.parent / ".claude" / "skills" / "opening-campaign"
ASSETS = SKILL / "assets"
ACQUIRE = SKILL / "scripts" / "acquire-repo.sh"
NAME_PY = (HERE.parent / ".claude" / "skills" / "assuming-role" / "scripts"
           / "campaign-name-session.py")
# The two assets a scaffolded directory must NOT keep: each is filled once per
# issue from the skill's own copy, so a top-level copy has no reader and a
# stale one could be filled long after (SKILL.md step 4).
TEMPLATES = ("sub-issue.md", "chore.md")
# The slug label's colour and description are the skill's, byte for byte: a
# label minted here and a label minted by hand are one label.
SLUG_COLOUR = "1D76DB"
SLUG_DESCRIPTION = ("the campaign's slug: every name a person reads is built "
                    "from it")
CHORE_COLOUR = "5319E7"
CHORE_DESCRIPTION = ("a campaign issue that is its own one unit of work: no "
                     "sub-issue, claimed and worked as itself")


def load(src, alias):
    """The script at `src` as a module: these are scripts, not a package."""
    spec = importlib.util.spec_from_loader(
        alias, importlib.machinery.SourceFileLoader(alias, str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# campaign-repos.py OWNS THE BASE'S NAME, and campaign-tracker.py the chore's
# shape, its label spellings and the pool of spent slugs. Both are imported for
# what only they should say; the `## Repos` LIST is still read by RUNNING
# campaign-repos.py, whose refusals are exit strings, which is what keeps one
# reader of that list rather than two.
REPOS = load(REPOS_PY, "campaign_repos")
TRACKER = load(TRACKER_PY, "campaign_tracker")
BASE_REPO = REPOS.BASE_REPO


def claim_module():
    """campaign-claim.py, imported for `branch_name`: the one spelling of a
    claim's branch. Loaded at the one step that prints a branch, so a run that
    stops before the claim never pays for it."""
    return load(CLAIM_PY, "campaign_claim")


def run(*args, **kw):
    """The one effectful call. Every `gh`, `git`, script and shell step here
    goes through this name, so what a run of this script did is one list, and a
    suite replaces it and makes no write at all.

    A command that is not installed is a failed run, not a traceback."""
    try:
        return subprocess.run([str(a) for a in args], capture_output=True,
                              text=True, **kw)
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(
            args, 127, "", f"{args[0]}: {e.__class__.__name__}: {e}")


def word(r):
    """The first line of a reader's stdout, which is where every one-word
    answer here sits. The status is the coarser copy and is not read."""
    return r.stdout.splitlines()[0].strip() if r.stdout.strip() else ""


def said(r):
    """What a failed command said, for a refusal to quote."""
    return (r.stderr.strip() or r.stdout.strip() or "no message")[:300]


class Stop(Exception):
    """A step that could not go on: which step, and why. What is already done
    and how to resume are the run's, printed once by `main`."""

    def __init__(self, step, why):
        super().__init__(why)
        self.step, self.why = step, why


class Progress:
    """What this run has already written, in the order it was written, and the
    line that resumes it. A refusal prints both: a step that stopped halfway
    through an open leaves an issue, a label, a directory or a ref behind, and
    a caller told only "it failed" has to find each of them by hand."""

    def __init__(self, args):
        self.args, self.done, self.number = args, [], args.issue

    def did(self, note):
        self.done.append(note)
        print(f"  did: {note}")

    def resume(self):
        line = [str(HERE / "campaign-open.py"), "--chore", self.args.chore,
                "--title", self.args.title, "--body-file", self.args.body_file]
        if self.args.topic:
            line += ["--topic", self.args.topic]
        if self.number:
            line += ["--issue", str(self.number)]
        return " ".join(shlex.quote(a) for a in line)


# ------------------------------------------------------------------ 1. shape


def step_shape(slug, title, body, body_file, resumed):
    """Everything about this chore that can be read before anything is written.

    THE ORDER IS BY COST AND NOT BY IMPORTANCE: the slug rule and the shape are
    pure, the spent-slug pool is one `gh` read, and the `## Repos` list is one
    subprocess over a local file. All of them come before step 3, so a chore
    that would be malformed never reaches a label or an issue.

    The uniqueness reading is the one thing a resume skips: by then the slug is
    spent by this very issue, and reading it again would refuse the resume."""
    rule = TRACKER.name_rule()
    if not rule.slug_ok(slug):
        raise Stop("shape", f"{slug!r} is not a slug: kebab-case starting with "
                            f"a letter, at most {rule.SLUG_CEILING} characters, "
                            f"no segment {' or '.join(rule.RESERVED)}. It lands "
                            f"in a session name, a branch and a directory path, "
                            f"so it is refused before any of them is built.")
    print(f"step 1 shape: {slug!r} is a slug "
          f"({NAME_PY.name} slug_ok, the one rule)")

    if resumed:
        print(f"step 1 shape: the spent-slug pool is not read -- --issue "
              f"{resumed} says `campaign:{slug}` is already this chore's")
    else:
        spent, labels, why = TRACKER.spent_slugs(BASE_REPO, TRACKER.LABEL_LIMIT)
        if why:
            raise Stop("shape", f"{why}")
        print(f"step 1 shape: read {BASE_REPO}: {labels} label(s), "
              f"{len(spent)} spent slug(s)")
        if slug in spent:
            raise Stop("shape", f"`{TRACKER.SLUG_LABEL_PREFIX}{slug}` is spent "
                                f"already. A slug names one campaign for as "
                                f"long as its label exists, a closed one's "
                                f"included; mint another.")

    names = [TRACKER.CAMPAIGN_LABEL, TRACKER.CHORE_LABEL,
             f"{TRACKER.SLUG_LABEL_PREFIX}{slug}"]
    findings = TRACKER.shape_findings(TRACKER.CHORE, title, body, False,
                                      names=names)
    for finding in findings:
        print(f"  finding: {finding}")
    if findings:
        raise Stop("shape", f"{len(findings)} finding(s) on the shape of what "
                            f"would be filed, printed above. `{ASSETS}/chore.md` "
                            f"is the template.")
    print(f"step 1 shape: no finding on the {TRACKER.CHORE}'s title and body "
          f"({TRACKER_PY.name} shape_findings, {len(names)} label(s) offered)")

    r = run(REPOS_PY, body_file)
    if r.returncode != 0:
        raise Stop("shape", f"the `## Repos` list of {body_file} did not read: "
                            f"{said(r)}")
    entries = r.stdout.split()
    print(f"step 1 shape: `## Repos` reads {len(entries)} member "
          f"repositor(y|ies): {', '.join(entries) or '- none'}")


# ----------------------------------------------------------------- 2. survey


def step_survey():
    """The open campaigns, printed beside the create. A script cannot judge
    Scope -- that reading is the caller's and the routing gate's -- so this
    prints what the survey said and goes on either way, a survey that would not
    read included: a chore is one unit of work, and refusing to file one over a
    listing nobody was going to match by machine would stop the cheap path for
    the reading it cannot make."""
    r = run(TRACKER_PY, "campaign-issues")
    print(f"step 2 survey: {TRACKER_PY.name} campaign-issues exited "
          f"{r.returncode}")
    for line in (r.stdout or said(r)).splitlines():
        print(f"  | {line}")


# ----------------------------------------------------------------- 3. create


def unmint(slug, state):
    """Take back the slug label THIS RUN minted, when the create after it
    failed. Left standing, the label reads as a spent slug, so the resume line
    a refusal prints would refuse at step 1 and the caller would have to find
    and delete it by hand (pr#478, REVIEW finding 5). A label no issue ever
    wore is not a spent slug. Returns the sentence for the refusal."""
    label = f"{TRACKER.SLUG_LABEL_PREFIX}{slug}"
    r = run("gh", "label", "delete", label, "-R", BASE_REPO, "--yes")
    if r.returncode == 0:
        state.done.pop()
        return (f"`{label}`, minted by this run, was deleted again, so the "
                f"resume line runs as printed.")
    return (f"`{label}`, minted by this run, could NOT be deleted "
            f"({said(r)}): the resume line refuses at step 1 until "
            f"`gh label delete {label} -R {BASE_REPO} --yes` has run.")


def step_create(slug, title, body_file, state):
    """The labels then the issue, in that order and never the other.

    `gh label create` failing because the name exists IS the uniqueness gate
    (SKILL.md step 3), so the slug's label is minted BEFORE the issue: filed
    first, the issue would already exist when the gate spoke, and nothing here
    deletes an issue. `--force` is never passed, for the same reason.

    The `chore` label is the one create that tolerates "already exists": every
    chore wears it, so its existence gates nothing, and `gh issue create`
    refuses a label the repository does not have."""
    r = run("gh", "label", "create", f"{TRACKER.SLUG_LABEL_PREFIX}{slug}",
            "-R", BASE_REPO, "--color", SLUG_COLOUR,
            "--description", SLUG_DESCRIPTION)
    if r.returncode != 0:
        raise Stop("create", f"`gh label create "
                             f"{TRACKER.SLUG_LABEL_PREFIX}{slug}` exited "
                             f"{r.returncode}: {said(r)}\n  A name that exists "
                             f"is the uniqueness gate and not a hiccup: mint "
                             f"another slug. No issue was filed.")
    print(f"step 3 create: minted `{TRACKER.SLUG_LABEL_PREFIX}{slug}` on "
          f"{BASE_REPO}, which is the uniqueness gate")
    state.did(f"the `{TRACKER.SLUG_LABEL_PREFIX}{slug}` label exists on "
              f"{BASE_REPO}")

    r = run("gh", "label", "create", TRACKER.CHORE_LABEL, "-R", BASE_REPO,
            "--color", CHORE_COLOUR, "--description", CHORE_DESCRIPTION)
    if r.returncode == 0:
        print(f"step 3 create: minted `{TRACKER.CHORE_LABEL}` on {BASE_REPO}")
    elif "already exists" in (r.stderr + r.stdout):
        print(f"step 3 create: `{TRACKER.CHORE_LABEL}` was already on "
              f"{BASE_REPO}, which is the ordinary state and gates nothing")
    else:
        raise Stop("create", f"`gh label create {TRACKER.CHORE_LABEL}` exited "
                             f"{r.returncode}: {said(r)}\n  "
                             f"{unmint(slug, state)}")

    r = run("gh", "issue", "create", "-R", BASE_REPO,
            "--label", TRACKER.CAMPAIGN_LABEL,
            "--label", TRACKER.CHORE_LABEL,
            "--label", f"{TRACKER.SLUG_LABEL_PREFIX}{slug}",
            "--title", title, "--body-file", body_file)
    if r.returncode != 0:
        raise Stop("create", f"`gh issue create` exited {r.returncode}: "
                             f"{said(r)}\n  {unmint(slug, state)}")
    url = next((w for w in r.stdout.split() if "/issues/" in w), "")
    number = url.rsplit("/", 1)[-1]
    if not number.isdigit():
        raise Stop("create", f"gh printed {r.stdout.strip()[:200]!r}, which "
                             f"holds no `/issues/<N>` URL, so the issue may "
                             f"exist under a number nothing here read.")
    state.number = number
    state.did(f"chore#{number} is filed: {url}")
    print(f"step 3 create: filed chore#{number} with 3 labels ({url})")
    return number


# -------------------------------------------------------------- 4. read back


def step_read_back(number, slug):
    """The three labels and a null parent, read off the issue itself.

    A campaign issue filed without the `campaign` label is in nobody's survey
    and the next session opens a second one over the same scope; without
    `chore` it is an ordinary campaign that `take` will not claim as itself;
    without the slug nothing can be named. A non-null parent means a sub-issue
    was filed, which `gh issue edit --remove-parent` repairs."""
    r = run("gh", "issue", "view", str(number), "-R", BASE_REPO,
            "--json", "labels,parent")
    if r.returncode != 0:
        raise Stop("read back", f"`gh issue view {number}` exited "
                                f"{r.returncode}: {said(r)}")
    try:
        got = json.loads(r.stdout)
    except ValueError as e:
        raise Stop("read back", f"could not parse gh's output "
                                f"({e.__class__.__name__})")
    have = sorted(label["name"] for label in got["labels"])
    want = [TRACKER.CAMPAIGN_LABEL, TRACKER.CHORE_LABEL,
            f"{TRACKER.SLUG_LABEL_PREFIX}{slug}"]
    missing = [w for w in want if w not in have]
    if missing:
        raise Stop("read back", f"chore#{number} carries {have} and is missing "
                                f"{missing}. Add it: `gh issue edit {number} "
                                f"-R {BASE_REPO} --add-label "
                                f"{','.join(missing)}`.")
    if got["parent"] is not None:
        raise Stop("read back", f"chore#{number} has a parent "
                                f"(#{got['parent'].get('number')}), so a "
                                f"sub-issue was filed and not a chore. "
                                f"`gh issue edit {number} -R {BASE_REPO} "
                                f"--remove-parent` first.")
    print(f"step 4 read back: chore#{number} carries {have} and has no parent")


# ------------------------------------------------------------------- 5. bind


def step_bind(number, state):
    """Bind, then read it back as the WORD. One of the two occasions a session
    binds: a campaign it has just filed itself. Every step after this is a
    write or a claim, and both refuse on anything but `here`."""
    r = run(TRACKER_PY, "bind", str(number))
    for line in (r.stdout or said(r)).splitlines():
        print(f"  | {line}")
    if r.returncode != 0:
        raise Stop("bind", f"`{TRACKER_PY.name} bind {number}` exited "
                           f"{r.returncode}: {said(r)}")
    state.did(f"chore#{number} is bound to this machine")
    r = run(TRACKER_PY, "bound", str(number))
    said_word = word(r)
    if said_word != "here":
        raise Stop("bind", f"`{TRACKER_PY.name} bound {number}` reads "
                           f"{said_word!r}, not `here`. A label naming somebody "
                           f"else means the campaign was migrated out from "
                           f"under this session; nothing further may be "
                           f"written from here.")
    print(f"step 5 bind: `bound {number}` reads the word `here`")


# --------------------------------------------------------------- 6. scaffold


def base_root():
    """$BASE, resolved the one way AGENTS.md states, from THIS FILE's directory
    rather than the working one -- the form returns the main checkout from a
    linked worktree too, where `--show-toplevel` returns the worktree."""
    r = run("git", "-C", str(HERE), "rev-parse", "--path-format=absolute",
            "--git-common-dir")
    if r.returncode != 0:
        raise Stop("scaffold", f"$BASE did not resolve: `git rev-parse "
                               f"--git-common-dir` in {HERE} exited "
                               f"{r.returncode}: {said(r)}")
    return Path(word(r)).parent.resolve()


def scaffold_dir(number, slug, base, state):
    """The campaign directory, made and marked by this run or found already
    there.

    THE DIRECTORY IS FOUND BY ITS MARKER, never composed from the slug: only
    `campaign-directory.py` answers where one is, and the name is composed here
    alone, for the `mkdir` that makes one. The `mkdir` without `-p` is the
    atomic gate between two sessions arriving on the same day; the marker read
    above it is what covers the second day, when the date would mint a fresh
    name for a campaign that already has a directory."""
    r = run(DIRECTORY_PY, str(number), str(base))
    held = word(r)
    if held == "none":
        target = base / f"campaign-{slug}-{time.strftime('%y%m%d')}"
        print(f"step 6 scaffold: {DIRECTORY_PY.name} reads `none`, so this run "
              f"names {target}")
    elif held.startswith("/"):
        target = Path(held)
        if target.parent != base:
            raise Stop("scaffold", f"{target} is not a direct child of {base}; "
                                   f"nothing was scaffolded.")
        print(f"step 6 scaffold: {DIRECTORY_PY.name} reads {target}, which this "
              f"run uses as it is")
        return target
    else:
        raise Stop("scaffold", f"{DIRECTORY_PY.name} reads {held!r}: "
                               f"{said(r)}. Nothing was scaffolded.")

    try:
        target.mkdir()
    except FileExistsError:
        # A DIRECTORY OF THAT NAME CARRYING NO MARKER is not this campaign's:
        # the marker read above says no campaign directory here names it, so
        # this is somebody else's tree or the residue of a run killed between
        # the mkdir and the mark. SKILL.md step 4 sends a person to read its
        # README.md, and that reading is not one a script makes -- writing this
        # chore's README and `runtime/` into it would overwrite whatever it is.
        raise Stop("scaffold", f"{target} exists and no marker in {base} names "
                               f"chore#{number}, so that directory is not this "
                               f"campaign's. Read its README.md: mark it by "
                               f"hand if it is this one, move it aside if it is "
                               f"not, then resume.")
    shutil.copytree(ASSETS, target, dirs_exist_ok=True)
    r = run(DIRECTORY_PY, "mark", str(number), slug, str(target))
    if r.returncode != 0:
        # THIS RUN'S OWN mkdir MADE IT, so this run takes it away: left behind
        # without a marker, a re-run reads `none`, fails the mkdir and says
        # `exists` over a directory nothing sees. Nothing is recorded as done
        # before the mark, because until it lands the directory is not one.
        shutil.rmtree(target)
        raise Stop("scaffold", f"`{DIRECTORY_PY.name} mark` exited "
                               f"{r.returncode}: {said(r)}. The directory this "
                               f"run made was removed, so a re-run starts "
                               f"clean.")
    state.did(f"{target} was created by this run and marked")
    print(f"step 6 scaffold: marked {target} as chore#{number} ({slug})")
    return target


def step_scaffold(number, slug, state):
    """SKILL.md step 4: the directory, the templates removed, the body written
    as GitHub stored it, and `runtime/repos` derived from it.

    `runtime/` holds what is DERIVED from the issue and re-derivable at any
    time, and these two files are that and nothing else. The `.tmp`-then-rename
    is kept so a refused list cannot look like a deliberate `- none`."""
    base = base_root()
    print(f"step 6 scaffold: $BASE is {base} (git --git-common-dir from {HERE})")
    target = scaffold_dir(number, slug, base, state)

    for name in TEMPLATES:
        template = target / name
        if template.exists():
            template.unlink()
            print(f"step 6 scaffold: removed the copied {name}, which is "
                  f"filled per issue from the skill's own copy")

    r = run("gh", "issue", "view", str(number), "-R", BASE_REPO,
            "--json", "body", "--jq", ".body")
    if r.returncode != 0:
        raise Stop("scaffold", f"`gh issue view {number} --json body` exited "
                               f"{r.returncode}: {said(r)}")
    readme = target / "README.md"
    readme.write_text(r.stdout)
    derived = target / "runtime" / "campaign-issue-body-derived.md"
    shutil.copyfile(readme, derived)
    print(f"step 6 scaffold: wrote {readme} from the body GitHub stored "
          f"({len(r.stdout)} characters), and copied it to {derived.name}")

    r = run(REPOS_PY, str(readme))
    if r.returncode != 0:
        raise Stop("scaffold", f"the `## Repos` list of {readme} did not read: "
                               f"{said(r)}. runtime/repos was not written.")
    tmp = target / "runtime" / "repos.tmp"
    tmp.write_text(r.stdout)
    os.replace(tmp, target / "runtime" / "repos")
    entries = r.stdout.split()
    print(f"step 6 scaffold: wrote runtime/repos with {len(entries)} "
          f"entr(y|ies): {', '.join(entries) or '- none'}")
    return base, target, entries


# ---------------------------------------------------------------- 7. acquire


def step_acquire(target, entries, state):
    """One `acquire-repo.sh` per line, by absolute path -- step 6 has just
    created an empty `scripts/` in the directory, so a relative path resolves
    there and fails. `- none` is zero lines and gets no special case; the count
    is printed either way, because a loop that never ran prints nothing and
    reads exactly like one that worked."""
    for entry in entries:
        dest = target / "repos" / entry.rsplit("/", 1)[-1]
        r = run(ACQUIRE, entry, str(dest))
        for line in said(r).splitlines()[-3:]:
            print(f"  | {line}")
        if r.returncode != 0:
            raise Stop("acquire", f"`{ACQUIRE.name} {entry}` exited "
                                  f"{r.returncode}. It is safe to re-run.")
        state.did(f"{entry} is checked out at {dest}")
    print(f"step 7 acquire: {len(entries)} repositor(y|ies) acquired"
          + ("" if entries else " -- no repository acquired, which is what "
                               "`- none` means"))


# ------------------------------------------------------------------- 8. name


def step_name(slug, state):
    """`<slug>-worker-1`, set on this session.

    A chore has no planner and so has one session and one counter value. A
    FAILED rename is a stop (SKILL.md step 3): a session that arrived from
    another campaign keeps that campaign's name until something sets it, and
    `campaign-claim live` believes the name -- so a chore claimed under a stale
    one is invisible to its own close gate.

    OUTSIDE HERDR THERE IS NO PANE TO NAME, and that is said rather than
    skipped silently: the line to run is printed and the run goes on, because
    the claim below is what the name gates and a person can set it first."""
    name = f"{slug}-worker-1"
    pane = os.environ.get("HERDR_PANE_ID")
    if os.environ.get("HERDR_ENV") != "1" or not pane:
        print(f"step 8 name: HERDR_ENV is "
              f"{os.environ.get('HERDR_ENV', 'unset')!r} and HERDR_PANE_ID is "
              f"{pane!r}, so this session is NOT named. Run it yourself:\n"
              f"  {NAME_PY} \"$HERDR_PANE_ID\" {name}")
        return None
    r = run(NAME_PY, pane, name)
    for line in (r.stdout or said(r)).splitlines():
        print(f"  | {line}")
    if r.returncode != 0:
        raise Stop("name", f"`{NAME_PY.name} {pane} {name}` exited "
                           f"{r.returncode}. Do not go on under the old name: "
                           f"every claim and every sweep reads it.")
    state.did(f"this session is named {name}")
    print(f"step 8 name: this session is {name} (pane {pane})")
    return name


# ------------------------------------------------------------------ 9. claim


# The claim guard reads the tool call's own working directory, never a `cd`
# inside the command (#475's first live chore had `gh pr create` refused so).
CD_NOTE = ("step 9 claim: run a `cd` into the checkout as its OWN call, or "
           "use `git -C` and `gh -R`: the claim guard reads the call's "
           "working directory and not a `cd` written in the same command")


def step_claim(number, slug, topic, base, target, entries, state):
    """The claim, cut only where WHERE is unambiguous.

    A chore is claimed as ITSELF, so the campaign issue and the issue are one
    number. `## Repos` decides where: the base when it is `- none`, the one
    entry when there is one. SEVERAL ENTRIES CUT NOTHING -- which of them this
    chore actually changes is the worker's reading, one ref per repository is
    cut as the work reaches it, and a ref cut for a repository nobody touches
    is a claim nobody releases."""
    branch = claim_module().branch_name(slug, number, topic)
    if len(entries) > 1:
        print(f"step 9 claim: `## Repos` names {len(entries)} repositories, so "
              f"which this chore changes is not a reading a script makes. No "
              f"ref was cut. Take one per repository you change:")
        # A TOPIC OF ITS OWN PER REPOSITORY: `release` and `live` find which
        # repository a ref is on by its name, so `take` refuses a chore a name
        # another of its repositories already holds.
        for entry in entries + [BASE_REPO]:
            print(f"  {CLAIM_PY} take {number} {number} "
                  f"{topic}-{entry.rsplit('/', 1)[-1]} --repo {entry}")
        print(CD_NOTE)
        return branch, []

    where = entries[0] if entries else BASE_REPO
    args = [CLAIM_PY, "take", str(number), str(number), topic]
    if entries:
        args += ["--repo", where]
    r = run(*args)
    for line in (r.stdout or said(r)).splitlines():
        print(f"  | {line}")
    if r.returncode != 0:
        raise Stop("claim", f"`{CLAIM_PY.name} take {number} {number} {topic}` "
                            f"exited {r.returncode}: {said(r)}")
    state.did(f"the claim {branch} is cut on {where}")
    print(f"step 9 claim: cut {branch} on {where}")
    # PRINTED, NEVER RUN: a checkout moves this session's own HEAD or adds a
    # worktree, and which of the two is right depends on where the caller is
    # sitting. `git fetch origin <branch>` updates `refs/remotes/origin/<branch>`
    # as well as FETCH_HEAD (git 1.8.4 and after; measured on git 2.54 against a
    # clone of the shape acquire-repo.sh leaves), so the plain `switch` below
    # finds the remote branch and tracks it.
    print("step 9 claim: check it out with")
    if entries:
        clone = target / "repos" / where.rsplit("/", 1)[-1]
        print(f"  git -C {clone} fetch origin {branch} && "
              f"git -C {clone} switch {branch}")
    else:
        tree = target / "worktrees" / f"{number}-{topic}"
        print(f"  git -C {base} fetch origin {branch} && "
              f"git -C {base} worktree add -b {branch} {tree} FETCH_HEAD")
    print(CD_NOTE)
    return branch, [branch]


# ------------------------------------------------------------------------ run


def open_chore(args, state):
    """The nine steps in their order, each stopping the run by raising."""
    slug, topic = args.chore, args.topic or args.chore
    try:
        body = Path(args.body_file).read_text()
    except OSError as e:
        raise Stop("shape", f"{args.body_file} did not read "
                            f"({e.__class__.__name__}); nothing was written.")
    step_shape(slug, args.title, body, args.body_file, args.issue)
    if args.issue:
        print(f"step 2 survey: skipped -- --issue {args.issue} resumes after "
              f"the create, and the survey is what one is read against")
        number = args.issue
        print(f"step 3 create: skipped -- chore#{number} is already filed")
    else:
        step_survey()
        number = step_create(slug, args.title, args.body_file, state)
    step_read_back(number, slug)
    step_bind(number, state)
    base, target, entries = step_scaffold(number, slug, state)
    step_acquire(target, entries, state)
    name = step_name(slug, state)
    branch, cut = step_claim(number, slug, topic, base, target, entries, state)
    branches = ("branch " + ", ".join(cut)) if cut else \
        f"no branch cut, each would be {branch}"
    print(f"chore#{number} https://github.com/{BASE_REPO}/issues/{number} | "
          f"slug {slug} | {target} | {branches} | "
          f"session {name or slug + '-worker-1 (NOT named)'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chore", metavar="SLUG",
                    help="open a chore under this slug. Required: this script "
                         "serves chores only today.")
    ap.add_argument("--title", help="the issue title, verb-first")
    ap.add_argument("--body-file", help="the filled-in assets/chore.md")
    ap.add_argument("--topic", help="the claim branch's topic word; the slug "
                                    "by default")
    ap.add_argument("--issue", metavar="N",
                    help="resume an open that stopped after the create: skips "
                         "the uniqueness reading, the survey and the create, "
                         "and re-runs every step after them")
    args = ap.parse_args()
    if not args.chore:
        print("refusing: --chore <slug> is what this opens. An ordinary "
              "campaign is still opened by the `opening-campaign` skill, whose "
              "step 2 proposes a name to a person and whose step 6 files the "
              "first sub-issues -- neither is a thing a script decides.",
              file=sys.stderr)
        return 2
    if not (args.title and args.body_file):
        print("refusing: --title and --body-file are both needed; the body is "
              f"{ASSETS}/chore.md filled in.", file=sys.stderr)
        return 2
    state = Progress(args)
    try:
        return open_chore(args, state)
    except Stop as stop:
        print(f"\nrefusing at step {stop.step}: {stop.why}", file=sys.stderr)
        print("already done, and NOT rolled back:" if state.done
              else "nothing was written by this run.", file=sys.stderr)
        for note in state.done:
            print(f"  - {note}", file=sys.stderr)
        print(f"resume with:\n  {state.resume()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
