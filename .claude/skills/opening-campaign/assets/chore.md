<!-- The chore. Work too small for a campaign, stated as ONE issue: a campaign
     issue that also carries the `chore` label, has no sub-issue, and is
     claimed and worked as itself. `scripts/campaign-open.py --chore <slug>
     --title <title> --body-file <this, filled>` files it, binds it, scaffolds
     its directory and cuts its claim; nothing here is done by hand.

     Title: one plain sentence, verb first, carrying the words a search would
     use, as a sub-issue's is. Body: bullets or tables, no prose paragraphs.
     Both ceilings are numbers in `scripts/campaign-tracker.py`;
     `campaign-tracker.py check <N>` prints each beside what it measured.

     THREE SECTIONS AND NO OTHERS. A chore OMITS `## Scope`, because nothing is
     ever filed under it and routing must never match it; `## Plan`, because
     work that needs one planned for it is a campaign; and `## Lands in`,
     because `## Repos` already says where and `campaign-claim take --repo`
     picks among its entries and the base.

     NO `kind:` LABEL, NEVER `standing`: `campaign-tracker.py check` refuses
     `chore` beside `standing`, since the label pre-authorises the clean-up
     once the last pull request's `Closes` has closed the issue (AGENTS.md
     § Routing an arriving request).

     REFERENCES CARRY THEIR SLUG: an issue is `<slug>#N`, a pull request
     `pr#N`. -->

## Intent

- <what is wrong or missing now, and what says so>

## Definition of done

- <the condition that settles it, readable off the CLOSED issue: the merged
  pull request, one per repository changed, the last one carrying `Closes`>

## Repos

<!-- As a campaign's: `- none`, alone, when only the base changes; otherwise
     the MEMBER repositories, never the base. An installed one carries
       - owner/repo (installed: <path>, apply: <command>)
     so `campaign-installed.py reach` finds the install after the merge. -->

- <owner/repo, or none>
