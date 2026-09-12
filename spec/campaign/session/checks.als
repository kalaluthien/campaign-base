/*
 * The disciplines a campaign session might follow, the witnesses that measure
 * each, and the reachability floor for session/system: its own events, and
 * every refinement it adds to a lower entity's event. github/system.als is
 * spec/'s entry point.
 */
module session/checks

open session/system

/* ---------------- disciplines: candidate repairs ---------------- */

/* Compare-then-write, THE guard the design adopted. Emptying it -- the
   discipline present but comparing nothing -- brings the loss back, so R1c's
   green is the comparison and not the shape of the scenario. */
pred compareThenWriteBody { always (Now.event = WriteBody implies Who.session.worksOn.reposInBody = Who.session.reposInBodyAsRead) }

/* The rejected candidate, modelled as "sync only when every sub-issue is
   settled". R1e is what it costs. */
pred writeBodyAtCloseOnly {
  always (Now.event = WriteBody implies (all i: Who.session.worksOn.memberIssues | settled[i]))
}

/* A rule about WHEN, where compare-then-write is a rule about HOW, so the two
   are not alternatives: R1j measures that, R1k is what it beats
   `writeBodyAtCloseOnly` by. */
pred writeBodyAtTwoMoments {
  always (Now.event = WriteBody implies
            (some Who.session.reposInReadme - Who.session.worksOn.reposInBody        -- a scope change
             or (all i: Who.session.worksOn.memberIssues | settled[i]))) -- or the close
}

/* R1p is why the membership rule is not enough by itself. */
pred boundOnly {
  always (Now.event = Adopt implies Binding.bound[Who.session.worksOn'] = Who.session.machine)
  always (Now.event in WriteBody + CreateDir + DeleteDir implies
            Binding.bound[Who.session.worksOn] = Who.session.machine)
  always ((Now.event = CloseIssue and Now.issue in Campaign.campaignIssue) implies
            Binding.bound[campaignIssueOf[Now.issue]] = Who.session.machine)
  /* The claim and the launch: `campaign-claim take` reads the binding before
     it cuts a ref, so the claim is mechanically gated; the launch is gated by
     AGENTS.md § The binding as a rule, stated here so the model and the prose
     name the same set. */
  always (Now.event in Claim + Launch implies
            Binding.bound[Who.session.worksOn] = Who.session.machine)
}

/* NARROWS the window rather than closing it: read and create are not atomic,
   and this model has no clock. */
pred surveyAtFile {
  always (Now.event = FileCampaignIssue implies
            (no c: Campaign | c in Filed and c.campaignIssue in Open and c in Request.covers))
}

/* So a repository leaving the list is the write that lost it, and not a
   campaign being torn down. */
pred noCloseNoDelete {
  always (Now.event != DeleteDir
          and (Now.event = CloseIssue implies Now.issue not in Campaign.campaignIssue))
}

/* =================== 1. two sessions sync the body =================== */

/* R1. S1 files and adds R0 to its README; S0 adopts while the body is still
   empty; S1 syncs, so the body reads {R0}; S0 syncs from its own stale README,
   so the body reads empty. R0 never returns, and no event means "remove a
   repository". */
pred R1_LostBodyUpdate {
  some c: Campaign, disj s1, s2: Session, r: Repo {
    eventually (Now.event = FileCampaignIssue and Who.session = s1 and Now.issue = c.campaignIssue)
    eventually (Now.event = Adopt and Who.session = s2)
    eventually (Now.event = WriteBody and Who.session = s1)
    eventually (Now.event = WriteBody and Who.session = s2)
    eventually (r in c.reposInBody and after (always r not in c.reposInBody))
    noCloseNoDelete
  }
}

/* R1b. A body write cannot touch a sub-issue link, so the index goes on
   naming an open sub-issue homed in a repository the list has dropped -- and
   closing the campaign deletes that list's last copy. Ordered on purpose:
   unordered it reads SAT on the ordinary window between filing and syncing. */
pred R1b_IndexOutlivesRepoList {
  some c: Campaign, disj s1, s2: Session, i: Issue, r: Repo {
    r != Base and i.repo = r
    eventually (Now.event = WriteBody and Who.session = s1)
    eventually (Now.event = WriteBody and Who.session = s2)
    eventually (i in indexOf[c] and r in c.reposInBody
                and after (always (i in indexOf[c] and i in Open and r not in c.reposInBody)))
    noCloseNoDelete
  }
}

/* R1c. The recommendation, and the loss is gone. */
pred R1c_CompareThenWriteBlocksLoss { compareThenWriteBody and R1_LostBodyUpdate }

/* R1d. UNSAT here would mean R1c went green by forbidding the scenario. */
pred R1d_CompareThenWriteAdmitsBothWrites {
  compareThenWriteBody
  some c: Campaign, disj s1, s2: Session, disj r1, r2: Repo {
    eventually (Now.event = FileCampaignIssue and Who.session = s1 and Now.issue = c.campaignIssue)
    eventually (Now.event = Adopt and Who.session = s2)
    eventually (Now.event = WriteBody and Who.session = s1)
    eventually (Now.event = WriteBody and Who.session = s2)
    eventually (r1 in c.reposInBody and r2 in c.reposInBody)
    noCloseNoDelete
  }
}

/* R1e. Both syncs happen with a real settled sub-issue in the campaign, so
   `writeBodyAtCloseOnly` is obeyed rather than satisfied vacuously. */
pred R1e_CloseOnlyStillLoses {
  writeBodyAtCloseOnly
  some c: Campaign, disj s1, s2: Session, i: Issue, r: Repo {
    eventually (Now.event = FileCampaignIssue and Who.session = s1 and Now.issue = c.campaignIssue)
    eventually (Now.event = AddMember and Who.session = s1 and Now.issue = i)
    eventually (Now.event = Adopt and Who.session = s2)
    eventually (Now.event = WriteBody and Who.session = s1 and i in c.memberIssues and settled[i])
    eventually (Now.event = WriteBody and Who.session = s2 and i in c.memberIssues and settled[i])
    eventually (r in c.reposInBody and after (always r not in c.reposInBody))
    noCloseNoDelete
  }
}

/* R1h. The binding is a rule sessions follow, not a lock GitHub enforces:
   `gh issue edit` refuses nothing. */
pred R1h_UnboundMachineStillLoses {
  some c: Campaign, disj s1, s2: Session, r: Repo {
    s1.machine != s2.machine
    always Binding.bound[c] = s1.machine
    always Binding.bound[c] != s2.machine
    eventually (Now.event = WriteBody and Who.session = s1)
    eventually (Now.event = WriteBody and Who.session = s2)
    eventually (r in c.reposInBody and after (always r not in c.reposInBody))
    noCloseNoDelete
  }
}

/* R1p. Two sessions on the one bound machine are both members, so `boundOnly`
   alone leaves R1's two syncs legal: the membership rule never serialized the
   body. */
pred R1p_BoundAloneStillLoses { boundOnly and R1_LostBodyUpdate }

/* R1j. A WHEN rule says nothing about comparing before you write. */
pred R1j_TwoMomentStillLoses { writeBodyAtTwoMoments and R1_LostBodyUpdate }

/* R1k. The difference from `writeBodyAtCloseOnly` in one trace: under it, this
   mid-campaign sync cannot happen at all. */
pred R1k_TwoMomentAdmitsScopeSync {
  writeBodyAtTwoMoments
  some c: Campaign, s: Session, i: Issue, r: Repo {
    eventually (Now.event = EditReadme and Who.session = s and r not in c.reposInBody)
    eventually (Now.event = WriteBody and Who.session = s
                and i in c.memberIssues and not settled[i] and r in c.reposInBody')
    noCloseNoDelete
  }
}

/* =================== 2. duplicate campaigns =================== */

/* R2. Two campaign issues, one scope. */
pred R2_DuplicateCampaign {
  some disj s1, s2: Session, disj c1, c2: Campaign {
    c1 in Request.covers and c2 in Request.covers
    eventually (Now.event = FileCampaignIssue and Who.session = s1 and Now.issue = c1.campaignIssue)
    eventually (Now.event = FileCampaignIssue and Who.session = s2 and Now.issue = c2.campaignIssue)
    eventually (c1 + c2 in Filed and c1.campaignIssue in Open and c2.campaignIssue in Open)
  }
}

pred R2b_SurveyAtFileBlocks { surveyAtFile and R2_DuplicateCampaign }

/* Control: with the same discipline one campaign still opens. */
pred R2c_SurveyAtFileAdmitsOne {
  surveyAtFile
  some s: Session, c: Campaign {
    c in Request.covers
    eventually (Now.event = FileCampaignIssue and Who.session = s and Now.issue = c.campaignIssue)
  }
}

/* =================== 3. a close during another session's work =================== */

/* R3. The finding needs no delegate at all, which is why it is stated in the
   entity that has none: every live-role gate the design has passes vacuously
   here and the loss happens anyway, because a live SESSION is invisible to
   that gate. Nothing in this entity repairs it -- whether a peer is working the
   tree is carried by this entity's own `claimedIssues` field and by no path on
   disk, so the repair is orchestration/checks.als's A10-A12. */
pred R3_DeleteUnderWorkingSession {
  some c: Campaign, disj s1, s2: Session {
    s1.machine = s2.machine
    eventually (Now.event = DeleteDir and Who.session = s2
                and s1 in working and s1.worksOn = c
                and some (campaignDirsOf[c]).checkedOut)
  }
}

/* =================== 4. a campaign with no member repository =================== */

/* R4. `- none` is encoded as `always no c.reposInBody`. Note what the predicate does
   NOT say: the sub-issue's `repo` IS the base, since with no member
   repository the only place a claim can cut a ref is the base -- "no
   member repository" is a claim about the list, not about where a ref goes.

   Checked WITH the disciplines rather than instead of them, and the claim is
   required: the branch is the claim before it is a workspace.

   SCOPED TO #187, and this trace is ahead of the code. A repo-less sub-issue
   lands no commit, so its ref stays 0 ahead of the base and is never a merged
   pull request's head -- and `campaign-claim release` refuses exactly that
   shape without `--confirmed-absent WHO`, because it cannot tell finished work
   from a claim cut for a holder that has not checked it out yet. So the close
   this trace reaches needs a person's word today, where the model asks for
   none. #187 decides the repair: whether such a sub-issue cuts a ref at all,
   or whether the closed issue is itself the evidence the holder is done. */
pred R4_RepolessCampaign {
  compareThenWriteBody and surveyAtFile
  some s: Session, c: Campaign, i: Issue {
    closeDiscipline[c]
    always no c.reposInBody
    i.repo = Base            -- the only repository a ref can be cut on
    eventually (Now.event = FileCampaignIssue and Who.session = s and Now.issue = c.campaignIssue)
    eventually (Now.event = AddMember and Who.session = s and Now.issue = i)
    eventually (Now.event = Claim and Who.session = s and Now.issue = i)
    eventually (Now.event = CloseIssue and Now.issue = i and no i.pullRequest)
    eventually (Now.event = CloseIssue and Now.issue = c.campaignIssue)
    eventually (campaignClosed[c] and i in c.memberIssues and dropped[i])
  }
}

/* ---------------- commands ---------------- */

-- the loss
run R1_LostBodyUpdate            for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- and it is worse than it looks
run R1b_IndexOutlivesRepoList    for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 14 steps expect 1
-- compare-then-write works: THE guard
run R1c_CompareThenWriteBlocksLoss            for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
-- control: it is not vacuous
run R1d_CompareThenWriteAdmitsBothWrites       for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 14 steps expect 1
-- the candidate it beats
run R1e_CloseOnlyStillLoses      for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- BOUND is a rule, not a lock
run R1h_UnboundMachineStillLoses for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- the membership rule never serialized the body
run R1p_BoundAloneStillLoses     for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- two moments is a WHEN rule, not a HOW
run R1j_TwoMomentStillLoses      for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- control, and the close-only difference
run R1k_TwoMomentAdmitsScopeSync for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1

-- two campaign issues, one scope
run R2_DuplicateCampaign         for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
-- the same shape repairs it
run R2b_SurveyAtFileBlocks       for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 0
-- control
run R2c_SurveyAtFileAdmitsOne    for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1

-- a live session is invisible to the gate; the repair is orchestration/checks.als's A10-A12
run R3_DeleteUnderWorkingSession for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1

-- `- none` opens, claims and closes
run R4_RepolessCampaign          for 2 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Machine, 1 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1


/* ---------------- reachability floor ----------------
 * The events this entity introduces, and every refinement it adds to a
 * lower entity's event. A refinement that cannot be satisfied would make its
 * event unreachable from here upward while the lower entity's own floor stayed
 * green. `Cov_Bound` pins `FileCampaignIssue` rather than reading `some
 * Binding.bound`, which `githubInit` alone satisfies at step 0.
 */
pred Cov_Survey            { eventually Now.event = Survey }
pred Cov_Adopt             { eventually Now.event = Adopt }
pred Cov_ReadBody          { eventually Now.event = ReadBody }
pred Cov_EditReadme        { eventually Now.event = EditReadme }
pred Cov_Brief             { eventually Now.event = Brief }
pred Cov_ContextReset      { eventually (Now.event = ContextReset and Who.session not in Briefed') }
/* Both pinned on the post-state, so each fails when its update is dropped. */
pred Cov_Stamp             { eventually (Now.event = Stamp and Who.session not in Stamped and Who.session in Stamped') }
pred Cov_Unstamp           { eventually (Now.event = Unstamp and Who.session in Stamped and Who.session not in Stamped') }
pred Cov_WriteBodyBySession              { eventually (Now.event = WriteBody and some Who.session) }
pred Cov_CloseCampaignIssue       { eventually (Now.event = CloseIssue and Now.issue in Campaign.campaignIssue) }
pred Cov_FiledBySession    { eventually (Now.event = FileCampaignIssue and some Who.session) }
pred Cov_MemberBySession   { eventually (Now.event = AddMember and some Who.session) }
pred Cov_DirBySession      { eventually (Now.event = CreateDir and some Who.session) }
pred Cov_DeleteBySession   { eventually (Now.event = DeleteDir and some Who.session) }
pred Cov_AcquireBySession  { eventually (Now.event = Acquire and some Who.session) }
pred Cov_ClaimBySession    { eventually (Now.event = Claim and some Who.session) }
pred Cov_ReleaseBySession  { eventually (Now.event = Release and some Who.session) }
pred Cov_LaunchBySession   { eventually (Now.event = Launch and some Who.session) }
pred Cov_MergeBySession    { eventually (Now.event = MergePullRequest and some Who.session) }
pred Cov_Bound             { eventually (Now.event = FileCampaignIssue and some Binding.bound') }

/* ---------------- commands ---------------- */

-- every own event and every refinement this entity adds fires in some trace
run Cov_Survey            for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Adopt             for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_ReadBody          for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_EditReadme        for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Brief             for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_ContextReset      for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Stamp             for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Unstamp           for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_WriteBodyBySession              for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_CloseCampaignIssue       for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_FiledBySession    for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_MemberBySession   for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_DirBySession      for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_DeleteBySession   for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_AcquireBySession  for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_ClaimBySession    for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_ReleaseBySession  for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_LaunchBySession   for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_MergeBySession    for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Bound             for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
