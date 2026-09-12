/*
 * One campaign's directory on a machine, and the repository checkouts inside
 * it. It opens github/system because a directory holds a campaign's work and a
 * checkout is of a repository, and both of those are the entity below.
 *
 *   Machine       a machine a campaign can run on, and which repositories
 *                 are INSTALLED on it: checked out where they are used, not
 *                 only cloned into a campaign directory.
 *   Branch        a git branch a checkout can be on.
 *   CampaignDir   one campaign's directory on one machine: which campaign,
 *                 which machine, and which branch each repository is on.
 *   OnDisk        the campaign directories that currently exist.
 *   Where         the observer: which machine and which repository the current
 *                 event touched.
 *
 * An installed repository has two checkouts on a machine -- the install, where
 * it is used, and the clone under the campaign directory, where it is worked --
 * and a merge is not finished until the install shows it (#239). Before #239 the
 * base alone had that rule, as prose, and `~/.claude` (dotclaude) had none:
 * carrying a merge into the install was each worker's improvisation. `current`
 * below is the set of installed repositories whose install contains everything
 * merged; a MergePullRequest on a repository empties it for that repository on
 * every machine, and a Reach on one machine refills it. The `## Repos` marker
 * that says WHICH repositories are installed and HOW a merge reaches each is
 * `scripts/campaign-repos.py`'s; `scripts/campaign-installed.py check` reads
 * `current` off this machine's disk and `reach` is the event.
 *
 * A campaign directory holds no fact another machine reads, which is what lets
 * it be optional. Its name is `campaign-<slug>-<date>`, or the bare `<slug>`
 * that form replaced for one window, and what makes a directory one is a
 * `.campaign` marker inside it naming the campaign -- neither name is read,
 * because no shape can tell a slug from the base's own `scripts/`.
 * The marker is derived from the campaign issue and re-derivable, so it is
 * still no fact another machine reads.
 *
 * CampaignDir is keyed by an atom rather than carried as two columns on a
 * holder. Keep it that way: Kodkod cannot represent the five-column varying
 * relation those columns would make once the composed universe passes about
 * seventy atoms.
 */
module directory/system

open github/system

sig Machine {
  /* WHICH REPOSITORIES ARE INSTALLED HERE. Static: a trace runs on machines as
     they are, and installing one is not a campaign event. The Base is installed
     on every machine a campaign runs on -- the base root IS its install -- and
     the fact below says so, which is what makes the base one row of this rule
     rather than a special case beside it. */
  installed: set Repo,
  /* THE INSTALLED REPOSITORIES WHOSE INSTALL CONTAINS EVERYTHING MERGED. Never
     wider than `installed`; emptied for a repository by every MergePullRequest
     on it, refilled by Reach. Read off disk by `campaign-installed.py check`:
     the install's HEAD contains the remote's default branch, or does not. */
  var current: set Repo
}
sig Branch {}

/* One campaign's directory on one machine. Keyed by an atom rather than
   carried as two columns on a holder: Kodkod cannot represent the five-ary var
   relation those columns would make once the composed universe passes about
   seventy atoms. */
sig CampaignDir {
  campaign:         one Campaign,
  machine:         one Machine,
  var checkedOut: Repo -> Branch,
  /* THE CLONES HERE THAT CARRY THE CAMPAIGN'S PRINCIPLES. #176 replaced
     `--append-system-prompt-file` and its canary with a `CLAUDE.local.md` in
     the delegate's own clone -- a file on disk in its cwd, so there is nothing
     to prove arrived. #187 question 5 is that no command anywhere wrote one, so
     the mechanism existed only as prose and a delegate launched by the book got
     nothing. Modelled as a set of repositories rather than a file, because what
     a launch needs is that the clone it launches into carries them; WHICH bytes
     is `acquire-repo.sh`'s. Since rule-check#314 those bytes are the campaign's
     own additions only -- a default SDLC profile line and the three role
     sections -- because a sub-issue's kind is a `kind:<k>` label on the
     sub-issue, whose reference the brief hook emits on the assignment prompt;
     that second channel is per sub-issue and per prompt, so it is not a fact
     about a clone and is not modelled here. */
  var principled:  set Repo,
  /* THE CLONES HERE WHOSE COMMITS SOMETHING REFUSES. `claimBeforeCommit` in
     orchestration/scenarios.als is the rule -- a commit on a sub-issue names a
     claim the committer holds -- and it says nothing about whether the checkout
     making the commit runs anything that reads it. `acquire-repo.sh` ran a
     clone's own `scripts/install-hooks.sh` only when the clone shipped one, and
     a member repository ships none, so every member clone got the machine-wide
     no-main-commits shim and NO CLAIM GATE, while check-campaign-claim.py went
     on calling that clone campaign work. The rule held in the model and
     enforced nothing on the trees delegates commit in (#190).

     Separate from `principled` although one step installs both, because they
     answer different questions: `principled` is what a delegate READS, this is
     what its commit is REFUSED by. Modelled as a set of repositories and not a
     file, for the reason given above it. */
  var gated:       set Repo
}
var sig OnDisk in CampaignDir {}

fun campaignDirsOf[c: Campaign]: set CampaignDir             { campaign.c }
/* THE ONE WAY TO REACH A CAMPAIGN'S DIRECTORY, and every reading about a
   campaign goes through it -- orchestration/system.als's `holder` included.
   Stated because the base is a member of its own campaigns: a campaign
   directory holds a CLONE of the base, so a script run from
   `<campaign>/repos/campaign-base/` sits in a second checkout of the same
   repository, and resolving "which base am I" from that checkout's own git
   answers with the clone -- a base whose set of campaign directories is empty,
   which reads as a clean sweep of nothing rather than as a failure. NOT
   MODELLED, and it cannot be here: no atom carries a path, so this is prose
   with a reader in `scripts/campaign-claim.py`'s `base_root`, which walks its
   own ancestors for a campaign directory before it asks git. */
fun campaignDirAt[c: Campaign, m: Machine]: lone CampaignDir { campaign.c & machine.m }
fun machinesHolding[c: Campaign]: set Machine           { (OnDisk & campaign.c).machine }

one sig Where {
  var machine: lone Machine,
  var repo: lone Repo
}

fact DirectoryWellFormed {
  all disj x, y: CampaignDir | x.campaign != y.campaign or x.machine != y.machine
  always all t: CampaignDir, r: Repo | lone t.checkedOut[r]
  all m: Machine | Base in m.installed
  always all m: Machine | m.current in m.installed
}

/* THE REPOSITORIES A CAMPAIGN'S MERGES LAND IN: where each member issue lands,
   its `## Repos` list, and the base, which is a member of every campaign by its
   own route. The member issues are in the set because github/system.als lets a
   member land in a repository the body never listed, and a merge there leaves
   an install behind exactly the same. */
fun landingRepos[c: Campaign]: set Repo { c.memberIssues.repo + c.reposInBody + Base }

/* WHAT A MACHINE HOLDING THE CAMPAIGN STILL OWES: an installed landing
   repository whose install does not contain what was merged. Empty is the
   only reading a close accepts. */
fun unreached[c: Campaign, m: Machine]: set Repo { (m.installed & landingRepos[c]) - m.current }

/* A CAMPAIGN DOES NOT CLOSE WHILE A MERGE HAS NOT REACHED ITS INSTALL on a
   machine holding it. Assumed by a scenario and never a fact, the shape
   github/system.als's `closeDiscipline` takes: `closing-campaign` step 2 is
   the reader, and a check that assumed it as a fact could not exhibit its
   absence. Scoped to `machinesHolding` because that is where the check runs --
   the bound machine's disk -- and a machine that installed the repository but
   never held the campaign is one no session of it can read. */
pred reachDiscipline[c: Campaign] {
  always ((Now.event = CloseIssue and Now.issue = c.campaignIssue)
          implies all m: machinesHolding[c] | no unreached[c, m])
}

/* ---------------- observable events ---------------- */

one sig CreateDir, DeleteDir, Acquire, Reach extends Event {}

fun directoryEvents: set Event { CreateDir + DeleteDir + Acquire + Reach }

pred directoryFrame { OnDisk' = OnDisk and checkedOut' = checkedOut and principled' = principled and gated' = gated and current' = current }

pred createDir[t: CampaignDir] {
  t not in OnDisk
  OnDisk' = OnDisk + t
  checkedOut' = checkedOut
  principled' = principled     -- a fresh directory has no clone yet to principle
  gated' = gated               -- nor one to gate
  current' = current           -- and the installs are not the directory's
  Now.event = CreateDir and no Now.issue and Where.machine = t.machine and no Where.repo
}

/* Unguarded: this entity has no role, so "no campaign closes while a role is
   live under its tree" cannot be stated here. orchestration/checks.als's
   NoOrphanIfGuarded is that rule assumed and checked. */
pred deleteDir[t: CampaignDir] {
  t in OnDisk
  OnDisk'  = OnDisk - t
  checkedOut' = checkedOut - t->Repo->Branch
  principled' = principled - t->Repo    -- the clones go with the directory
  gated' = gated - t->Repo              -- and the hooks go with the clones
  current' = current                    -- the installs stay: they were never inside it
  Now.event = DeleteDir and no Now.issue and Where.machine = t.machine and no Where.repo
}

/* opening-campaign/scripts/acquire-repo.sh. On a re-run over an existing checkout it switches the
   branch, which is what orchestration/scenarios.als's R4c catches it doing under a live role.
   An acquired checkout carries the repository's own git hooks when the repository ships an
   installer (scripts/install-hooks.sh), and otherwise a shim carrying the machine-wide
   no-main-commits guard AND the claim gate; acquire-repo.sh verifies the guard is chained on
   both paths, and refuses to install a gate it cannot run. That the shim also carries the gate
   is #190, and it is what `gated` below is: until then it was the guard alone, so this sentence
   said "the machine-wide no-main-commits guard alone otherwise" and the two halves of this file
   would now disagree. For a repository shipping this base's installer, one writer owns the slot
   -- the installer, which adopts the shim in either of its shapes and refuses anything else --
   because two writers left every delegate clone with no hook of the repository's own, and a
   commit there was never auto-pushed. */
pred acquire[t: CampaignDir, r: Repo, b: Branch] {
  t in OnDisk
  t.checkedOut[r] != b
  checkedOut' = checkedOut - t->r->Branch + t->r->b
  /* ACQUIRE IS WHAT PRINCIPLES A CLONE, and saying so is the whole of the
     mechanism: `acquire-repo.sh` writes the campaign's `AGENTS.md` into the
     checkout as `CLAUDE.local.md` on every checkout it leaves. Written into
     the event because there is no other moment -- the clone comes into
     existence here -- where `checkedOut` is a fact a later event may change.
     Without this `principled` had no producer at all: every directory event
     left it free, so R12c's witness rested on a set nothing wrote. */
  principled' = principled + t->r
  /* AND ACQUIRE IS ALSO WHAT GATES A CLONE. The same moment for the same
     reason, with one difference worth writing down: `install_commit_guard`
     reaches the gate through the BASE, resolved from `acquire-repo.sh`'s own
     path, because a member clone holds no copy of `check-commit-claim.py` to
     run. No atom here carries a path, so which bytes and by which path is the
     script's; the model says only that a clone leaves an Acquire with something
     that refuses its commits. */
  gated' = gated + t->r
  OnDisk' = OnDisk
  current' = current           -- a clone is not the install
  Now.event = Acquire and no Now.issue and Where.machine = t.machine and Where.repo = r
}

/* scripts/campaign-installed.py reach. The post-merge step for an installed
   repository: fast-forward the install to the merged sha and run the row's
   `apply`. It is what refills `current`, and the only thing that does, so a
   merge on an installed repository is followed by exactly this or the campaign
   holding it does not close (`reachDiscipline`). Not tied to an issue: the
   install is one per repository per machine, and two merges on one repository
   are reached by one fast-forward. */
pred reach[m: Machine, r: Repo] {
  r in m.installed
  r not in m.current
  current' = current + m->r
  OnDisk' = OnDisk and checkedOut' = checkedOut and principled' = principled and gated' = gated
  Now.event = Reach and no Now.issue and Where.machine = m and Where.repo = r
}

/* A MERGE EMPTIES `current` FOR THE REPOSITORY IT LANDED IN, on every machine
   that installed it: the install is now behind what was merged, whether or not
   the machine holds the campaign. The github event itself is above this entity
   and does not know `current` exists, so the reading is made here, where the
   event's issue says which repository it landed in. */
pred mergeLeavesInstallBehind {
  Now.event = MergePullRequest
  current' = current - Machine->(Now.issue.repo)
  OnDisk' = OnDisk and checkedOut' = checkedOut and principled' = principled and gated' = gated
  no Where.machine and no Where.repo
}

pred directoryInit {
  all t: CampaignDir | some t.checkedOut implies t in OnDisk
  current = installed          -- nothing is merged at the start of a trace
}

pred directoryStep {
  (Now.event = Stutter and directoryFrame and no Where.machine and no Where.repo)
  or (some t: CampaignDir | createDir[t] or deleteDir[t])
  or (some t: CampaignDir, r: Repo, b: Branch | acquire[t,r,b])
  or (some m: Machine, r: Repo | reach[m,r])
  or mergeLeavesInstallBehind
  or (Now.event in githubEvents - MergePullRequest and directoryFrame and no Where.machine and no Where.repo)
  /* An event declared in an entity above. `Where` is left to that entity: the
     one directly above sets `Where.machine` on its own events, and constrains it
     to none on everything higher, so the observer is pinned exactly once. */
  or (Now.event not in Stutter + githubEvents + directoryEvents and directoryFrame)
}

fact DirectoryTrace { directoryInit and always directoryStep }
