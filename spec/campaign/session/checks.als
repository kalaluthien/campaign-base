/*
 * The disciplines a campaign session might follow, the witnesses that measure
 * each, the property the adopted one holds, and the reachability floor for
 * session/system: its own events, and every refinement it adds to a lower
 * entity's event. github/system.als is spec/'s entry point.
 */
module session/checks

open session/system

/* ---------------- disciplines: candidate repairs ---------------- */

/* Compare-then-write, THE guard the design adopted. Emptying it -- the
   discipline present but comparing nothing -- brings the loss back, so
   CompareThenWriteKeepsEveryRepo's green is the comparison and not the shape
   of a scenario. */
pred compareThenWriteBody { always (Now.event = WriteBody implies Who.session.worksOn.reposInBody = Who.session.reposInBodyAsRead) }

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

/* The recommendation, and the loss is gone: under it no body write drops a
   repository, in R1's shape or any other. */
assert CompareThenWriteKeepsEveryRepo {
  compareThenWriteBody implies always (Now.event = WriteBody implies reposInBody in reposInBody')
}

/* R1d. UNSAT here would mean CompareThenWriteKeepsEveryRepo went green by
   forbidding the writes. */
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
   required: the branch is the claim before it is a workspace. */
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

/* R5. A MODEL SWITCH IS NO HANDOFF (system.als's `modelSwitch`): nobody is
   taken over, nobody exits, every claim, campaign and name stays where it
   was, and the address is one role. Dropping `sessionFrame` from the event,
   or only its `claimedIssues` clause, reddens this. A predecessor on the
   event does not: `PredecessorOnlyOnHandoff` already forbids one, so that
   mutation leaves `Cov_ModelSwitch`, its witness fired while a claim is
   held, with no instance instead. */
assert ModelSwitchKeepsEverySession {
  always (Now.event = ModelSwitch implies
    (no Who.predecessor and Exited' = Exited and claimedIssues' = claimedIssues
     and worksOn' = worksOn and campaignNamed' = campaignNamed
     and lone Who.addressed.role))
}

/* ---------------- commands ---------------- */

-- the loss
run R1_LostBodyUpdate            for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- compare-then-write works: THE guard
check CompareThenWriteKeepsEveryRepo         for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
-- control: it is not vacuous
run R1d_CompareThenWriteAdmitsBothWrites       for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 14 steps expect 1

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

-- a model switch moves nothing a handoff moves
check ModelSwitchKeepsEverySession for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 0

pred Cov_WriteBodyBySession              { eventually (Now.event = WriteBody and some Who.session) }
pred Cov_ReadBody          { eventually Now.event = ReadBody }
pred Cov_EditReadme        { eventually Now.event = EditReadme }
/* Both pinned on the post-state, so each fails when its update is dropped. */
pred Cov_Stamp             { eventually (Now.event = Stamp and Who.session not in Stamped and Who.session in Stamped') }
pred Cov_ModelSwitch       { eventually (Now.event = ModelSwitch and some Who.addressed and some Session.claimedIssues) }

/* ---------------- commands ---------------- */

run Cov_WriteBodyBySession              for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_ReadBody          for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_EditReadme        for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Stamp             for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_ModelSwitch       for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
