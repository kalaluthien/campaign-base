---
name: driving-herdr
description: Use when a session must act on a terminal pane other than its own - start or prompt an agent in one, run a command there, read its screen, wait on its state, list who is live - or when the owner names Herdr; not for work this session can do in its own shell or hand to an in-process subagent.
---

# Driving herdr

This page holds the words and the map. What a command does and where it breaks
are the two references, so a herdr upgrade or a new finding changes a
reference and never this page.

## The terms

| the word | what it names |
| --- | --- |
| herdr | the terminal multiplexer these sessions run in, and the CLI that speaks for the session the caller sits in |
| workspace, tab, pane | herdr's three containers, outermost first; a pane is one terminal, whether or not anything runs in it |
| agent | the coding agent herdr recognises in a pane; it has a status, and a plain shell has none |
| session | one run of a coding agent, with its own id and transcript; a pane outlives it and may host the next |
| delegate | a session another session launched into a pane and answers for |
| agent name | the name herdr holds for a pane's agent; what `herdr` commands and the claim guard read |
| harness name | the name the agent's own harness holds; what a message between sessions is addressed to. Neither name sets the other |
| target | the pane or agent a command acts on; one not named falls to whichever pane the person has focused |
| status | herdr's reading of an agent's screen, a word from a fixed set; the guide defines the set and facts says where a word misleads |

## The references

| the need | read |
| --- | --- |
| what a command does, its ids and statuses, the safe order of a launch, a prompt, a read | [guide](references/guide.md) |
| where that path breaks on this machine | [facts](references/facts.md), by its contents list |
| one command's flags today | the binary's own help, as the guide says to ask for it |
| launching a campaign delegate | `.claude/skills/assuming-role/references/launching.md`, which owns that procedure and cites facts |

Read the guide section for the act, then the facts section of the same act,
before the first command. Where they disagree, the later one wins: facts when
its entry is dated after the guide's last commit, and otherwise the guide,
with the entry re-probed before it is trusted again.

## Changing a reference

| the file | whose it is | when it changes | how |
| --- | --- | --- | --- |
| `references/guide.md` | herdr's, `herdr --skill` byte for byte | the installed herdr was upgraded, or `scripts/check-herdr-guide.py` answers `differs` | `check-herdr-guide.py write`, never by hand: a wrong sentence is fixed upstream and recorded in facts until then |
| `references/facts.md` | ours | a command behaved other than the guide says, or a `write` changed a sentence an entry leans on | one dated entry under the act it belongs to, stating the probe and the herdr version; an entry the new guide now states is removed, one it contradicts is re-probed, in the pull request that carries the `write` |
| this page | ours | a term is added or a reference is added, moved or retired | nothing else lands here: a command, a flag, a version or a probed value belongs to a reference |
