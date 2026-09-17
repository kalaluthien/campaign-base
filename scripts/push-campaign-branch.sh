#!/usr/bin/env sh
# Push a campaign branch the moment it has a commit, and say what happened.
#
# Moved out of the post-commit hook's heredoc so it can be linted, tested, and
# listed in the scripts inventory a session is shown at start-up.
set -u

branch=$(git symbolic-ref --quiet --short HEAD) || exit 0

# WHAT A CLAIM LOOKS LIKE IS NOT DECIDED HERE. It was, as `campaign-*/*`, and
# that glob was a second reader of `claim_match` -- so when #181 moved claims
# to `<slug>/<issue>-<topic>` the glob went on matching the retired form alone
# and every claim cut since committed without ever being pushed, silently,
# because the branch simply fell through to `exit 0`. Ask the owning script.
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 0
verdict=$("$HERE/check-commit-claim.py" --is-claim 2>&1)
status=$?

# THE WORD, NOT THE STATUS. Python exits 1 on an uncaught exception, so a bare
# status of 1 read as `answered no` would silently skip the push of a real
# claim on any bug in the reader. The word and the status must agree; when they
# do not, that is itself the unread question.
case "${verdict%% *}" in
claim) [ "$status" -eq 0 ] || status=9 ;;
no-claim) [ "$status" -eq 1 ] && exit 0; status=9 ;;
unknown) status=2 ;;
*) status=9 ;;
esac

case $status in
0) ;;                           # a claim: push it
*)
	# COULD NOT LOOK, so push anyway and say so. The cost of pushing a
	# branch that turns out not to be a claim is a branch on the remote;
	# the cost of not pushing one that is, is work that reads as landed to
	# nobody and dies with the machine.
	echo "push-campaign-branch: could not tell whether $branch is a claim." >&2
	echo "$verdict" | sed 's/^/  /' >&2
	echo "  Pushing anyway -- an unread question is not a no." >&2
	;;
esac

# mktemp, not /tmp/$$: /tmp is world-writable and a pid is guessable, so a
# pre-planted symlink there is truncated and overwritten by the redirect.
if ! err=$(mktemp); then
	echo "push-campaign-branch: mktemp failed; NOT pushing $branch." >&2
	echo "  The commit is local only. Push it yourself." >&2
	exit 0
fi
trap 'rm -f "$err"' EXIT INT TERM

# No force flag and no --no-verify: a rejected push is news, not something to
# overrule. An amend or a rebase lands here too, and the right answer for those
# is to be told, not to have the remote rewritten.
if git push --quiet origin "$branch" 2>"$err"; then
	echo "push-campaign-branch: pushed $branch"
	# THE DIFF SCREEN reads the pushed commit's files, in the background and
	# unwaited, since it asks a model once a file; why here is its docstring's.
	# A GitHub remote only: its later fact is a REVIEW on a pull request there,
	# and a fixture's local remote is not one.
	case $(git remote get-url origin 2>/dev/null) in
	*github.com[:/]*)
		# ONE COMMAND IN THE BACKGROUND, not an `a && b &` list: a list is
		# a subshell holding this hook's stdout open, so a caller capturing
		# `git commit`'s output waited for every Jev call.
		sha=$(git rev-parse HEAD) || exit 0
		nohup "$HERE/check-diff-screen.py" "$sha" "$branch" </dev/null >/dev/null 2>&1 &

		# THE PULL REQUEST GOES UP AT THE FIRST COMMIT, not when the
		# work is ready (AGENTS.md § Execution mode): the branch is
		# already pushed by the line above, so a late pull request only
		# keeps published work out of sight, and an open one is where a
		# review writes its findings. Nothing here opens one -- the
		# title and the body are the session's to write -- so this
		# ANNOUNCES the line and refuses nothing.
		#
		# ONLY AT THE FIRST COMMIT, or a branch whose session chose not
		# to open one yet would be told again at every commit and the
		# line would stop being read. `origin/main` is what the count
		# is against; with no such ref there is no count and nothing is
		# said, rather than a guess.
		ahead=$(git rev-list --count origin/main..HEAD 2>/dev/null) || ahead=
		[ "${ahead:-0}" = 1 ] || exit 0
		# A `gh` THAT WILL NOT RUN IS SAID, NOT ASSUMED. An unread
		# question is not "a pull request already names this branch":
		# announcing a second time costs a session one glance, and
		# staying silent costs the work its visibility.
		if open=$(gh pr list --head "$branch" --state open --json number \
				--jq '.[].number' 2>&1); then
			[ -z "$open" ] || exit 0
			echo "push-campaign-branch: this is $branch's first commit and no open pull request names it."
			echo "  AGENTS.md § Execution mode: open it now, not when the work is ready."
			echo "  gh pr create --base main --head $branch --title <verb-first> --body <Closes ...>"
		else
			echo "push-campaign-branch: could not tell whether a pull request names $branch." >&2
			echo "$open" | sed 's/^/  /' >&2
			echo "  Open one at this first commit if none does." >&2
		fi
		;;
	esac
else
	echo "push-campaign-branch: could NOT push $branch -- the commit is local only." >&2
	sed 's/^/  /' "$err" >&2
	echo "  Push it yourself before anything reads this branch as landed." >&2
fi
exit 0
