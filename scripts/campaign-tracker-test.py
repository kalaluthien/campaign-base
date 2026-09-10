#!/usr/bin/env python3
"""Prove campaign-tracker reads the whole thing, and says when it could not.

All four subcommands replace a `gh` line that once lived in prose, and all four
carry the rule that made the prose fragile: a listing that stops early reads
exactly like a complete one, and a reading that did not happen reads exactly
like an empty tracker.

`campaign-issues`, `bound` and `index` are covered as pure readings plus a shimmed `gh`;
no case reaches the network. `settlement` runs the installed script behind a `gh`
on PATH that answers from a fixture, so the request shapes and the exit codes are
the ones a person gets. The case that matters most there is the one with no
verdict at all: an index that did not read must refuse, because printing "the
index is empty" at exit 0 reads exactly like a campaign with no sub-issues and
closes it.

Usage: scripts/campaign-tracker-test.py
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRACKER = HERE / "campaign-tracker.py"


def load():
    spec = importlib.util.spec_from_loader(
        "campaign_tracker",
        importlib.machinery.SourceFileLoader("campaign_tracker", str(TRACKER)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tracker(*args, env=None):
    return subprocess.run([sys.executable, str(TRACKER), *args],
                          capture_output=True, text=True, env=env)


# The `gh` a settlement case answers from. One fixture file, keyed by the shape
# of the call, so a change to how the script asks shows up as a missing fixture
# rather than as a silently different answer.
SHIM = '''#!/usr/bin/env python3
import json, os, sys
data = json.load(open(os.environ["SHIM_DATA"]))
a = sys.argv[1:]
if a[0] == "api":
    key = "index"
elif a[0] == "pr":
    key = f"pr:{a[4]}#{a[2]}"
elif "labels" in a[-1]:
    key = "head"
else:
    key = f"issue:{a[4]}#{a[2]}"
v = data.get(key)
if v is None:
    print(f"no fixture for {key}", file=sys.stderr); sys.exit(3)
if isinstance(v, dict) and "exit" in v:
    print(v.get("stderr", ""), file=sys.stderr); sys.exit(v["exit"])
sys.stdout.write(v if isinstance(v, str) else json.dumps(v))
'''


def head(state="OPEN", labels=("campaign",), parent=None):
    return {"state": state, "title": "a campaign",
            "labels": [{"name": n} for n in labels], "parent": parent}


def sub(n, repo="kalaluthien/campaign-base", nested=0):
    return {"number": n, "sub_issues_summary": {"total": nested},
            "repository_url": f"https://api.github.com/repos/{repo}"}


def issue(state, reason=None, prs=(), title="a sub-issue", homeless=False):
    """`homeless` is the shape GitHub returns for a pull request it will not
    place -- its repository deleted, or moved out of this account's reach."""
    return {"state": state, "stateReason": reason, "title": title,
            "closedByPullRequestsReferences": [
                {"number": n, "url": f"https://x/{n}",
                 "repository": None if homeless else
                 {"owner": {"login": "kalaluthien"},
                  "name": "campaign-base"}} for n in prs]}


def settlement(fixture, tmp):
    bin_dir = Path(tmp) / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(SHIM)
    gh.chmod(0o755)
    data = Path(tmp) / "data.json"
    data.write_text(json.dumps(fixture))
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}",
               SHIM_DATA=str(data))
    r = tracker("settlement", "1", env=env)
    return r.returncode, r.stdout, r.stderr


def main():
    m = load()
    ran, fails = [], []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    # ------------------------------------------------- campaign issues: two readings
    def iss(n, label=False, parent=False):
        return {"number": n, "title": f"t{n}",
                "labels": [{"name": "campaign"}] if label else [],
                "parent": {"number": 1} if parent else None}

    listing = [iss(1, label=True), iss(9, label=True, parent=True),
               iss(7), iss(8, parent=True)]
    campaign_issues, stray, bare = m.classify(listing)
    check("a campaign issue is labelled and parentless",
          [i["number"] for i in campaign_issues] == [1])
    check("a labelled issue with a parent is a sub-issue wearing the label",
          [i["number"] for i in stray] == [9])
    check("an unlabelled issue with no parent is reported, not silently a campaign issue",
          [i["number"] for i in bare] == [7])
    check("an ordinary sub-issue is in no list",
          8 not in [i["number"] for i in campaign_issues + stray + bare])
    check("the three lists partition nothing twice",
          len(campaign_issues) + len(stray) + len(bare) == 3)

    # The blocking defect and its sibling: every row must be decided by what the
    # issue itself carries. Deriving either reading from membership in a second
    # `gh` call made *absence* read as a property, so a truncated listing or an
    # issue created between the calls produced a wrong row rather than none.
    check("the label reading comes from the issue, not from a filtered listing",
          [i["number"] for i in m.classify([iss(1, label=True)])[0]] == [1])
    check("...and an unlabelled issue is not promoted by being alone",
          m.classify([iss(1)])[0] == [])
    check("an empty tracker yields empty lists rather than an error",
          m.classify([]) == ([], [], []))

    # ------------------------------------------------------------ the slug
    # The `campaign:<slug>` label is read by exact prefix off a list of names,
    # so every case here is a calculation with no network in it -- including the
    # two states that are refusals rather than verdicts.
    def islug(n, *labels):
        return {"number": n, "title": f"t{n}",
                "labels": [{"name": x} for x in ("campaign", *labels)],
                "parent": None}

    slug, why = m.slug_of(["campaign", "bound:alpha"])
    check("no campaign: label is no slug, and neither `campaign` nor `bound:` "
          "is one", slug is None and why is None)
    slug, why = m.slug_of(["campaign", "campaign:machinery"])
    check("one campaign: label names its slug",
          slug == "machinery" and why is None)
    slug, why = m.slug_of(["campaign:one", "campaign:two"])
    check("two campaign: labels are a refusal, not a verdict",
          slug is None and why and "campaign:one" in why and "campaign:two" in why)
    # A SLUG THE NAME RULE REFUSES IS NOT A SLUG. Returning it would hand out a
    # session name `campaign-name-session.py` then refuses, which is the drift a
    # second reader of one rule always produces; this one imports the rule.
    slug, why = m.slug_of(["campaign:Machinery"])
    check("a slug the name rule refuses is a refusal, naming the rule",
          slug is None and why and "Machinery" in why)
    slug, why = m.slug_of(["campaign:"])
    check("an empty slug is refused rather than returned as the empty string",
          slug is None and why)
    check("slug_labels ignores the plain `campaign` label, which has no colon",
          m.slug_labels(["campaign", "campaign:x"]) == ["campaign:x"])

    read, bad = m.slugs_in([islug(1, "campaign:machinery"), islug(2)])
    check("a campaign issue with no slug is a finding, and its neighbour reads",
          read == {1: "machinery"} and list(bad) == [2]
          and "no `campaign:` label" in bad[2])
    # THE ONE DUPLICATION GITHUB DOES NOT STOP. Label names are unique per
    # repository, so a slug cannot be minted twice; one label on two issues can.
    read, bad = m.slugs_in([islug(1, "campaign:same"), islug(2, "campaign:same"),
                            islug(3, "campaign:other")])
    check("one slug on two campaign issues is a finding on both, not a slug",
          read == {3: "other"} and sorted(bad) == [1, 2]
          and "#1, #2" in bad[1])

    # ------------------------------------------------------ index: the parse
    one = json.dumps([{"number": 1}, {"number": 2}])
    items, why = m.parse_index(one)
    check("an array of sub-issues reads", why is None and len(items) == 2)
    items, why = m.parse_index("")
    check("an empty response is an empty index, not a failure",
          why is None and items == [])
    items, why = m.parse_index("[{]")
    check("malformed output is a why, not an empty index", items is None and why)
    items, why = m.parse_index(json.dumps({"message": "Not Found"}))
    check("an object where an array was expected is a why, not zero sub-issues",
          items is None and why)
    items, why = m.parse_index(json.dumps([{"number": 1}]) + json.dumps([{"number": 2}]))
    check("concatenated pages are a why rather than a silently short index",
          items is None and why)

    # ------------------------------------------- settlement's claim column
    # It read `runtime/claims/` through campaign-claim's own functions until
    # #176 deleted them, and NOTHING covered it: `settlement` died with an
    # AttributeError while every suite stayed green. These are cases over the
    # column itself, so the import is exercised rather than assumed.
    word, note = m.claim_column("o/r", "9")
    check("the claim column reads the remote's refs, and says which",
          "refs under demo/" in note or "did not read" in note)
    reader, why = m.claim_reader()
    check("campaign-claim still exposes what the column imports",
          why is None and hasattr(reader, "matching_refs")
          and hasattr(reader, "refs_for_issue"))

    # THE COLUMN MUST RESOLVE THE SLUG AND PASS IT ON. Without it `all_refs`
    # falls back to its own `slug=None` default, which reads no prefix at all
    # (`campaign-claim.py`'s `prefixes`) -- a campaign with a real slug then
    # settles with "no slug that could be read" on every row, which is what
    # #237's reopening measured on #245.
    seen = {}
    fake = types.SimpleNamespace(
        base_root=lambda: ("/tmp", None),
        claim_repos=lambda repo, root: ([repo], "1 repositor(y/ies)"),
        campaign_slug=lambda n: ("machinery", f"#{n} is `machinery`"),
        all_refs=lambda repos, n, slug=None: (seen.setdefault("slug", slug), {}, [])[1:],
        refs_for_issue=lambda branches, n, number: [])
    real_reader = m.claim_reader
    m.claim_reader = lambda: (fake, None)
    try:
        m.claim_column("o/r", "245")
    finally:
        m.claim_reader = real_reader
    check("claim_column resolves the campaign's slug and hands it to all_refs",
          seen.get("slug") == "machinery")

    # ------------------------------------------- bound and bind: the binding
    # The binding is a `bound:` LABEL since #176. A label set is read by exact
    # name, so the reading is a calculation over a list of names and every case
    # here runs without a network.
    machine, why = m.binding_of(["campaign", "boundary"])
    check("no bound: label is unbound, and `boundary` is not one",
          machine is None and why is None)
    machine, why = m.binding_of(["campaign", "bound:beta"])
    check("one bound: label names its machine",
          machine == "beta" and why is None)
    # THE STATE A COMMENT THREAD COULD NOT REACH and a label set can: two
    # bindings with no latest between them. Refused, never resolved -- picking
    # one hands the campaign to a machine that is not working it.
    machine, why = m.binding_of(["bound:alpha", "bound:beta"])
    check("two bound: labels are a refusal, not a verdict",
          machine is None and why and "bound:alpha" in why and "bound:beta" in why)
    machine, why = m.binding_of(["bound:"])
    check("an empty machine name is unbound rather than the empty string",
          machine is None and why is None)
    check("bound_labels ignores a label that merely opens with the same letters",
          m.bound_labels(["boundary", "bound:x"]) == ["bound:x"])

    # `bind` plans the edit before it makes one, so the three shapes are cases.
    want, drop, already = m.bind_plan([], "alpha")
    check("binding an unbound campaign adds one label and removes none",
          want == "bound:alpha" and drop == [] and not already)
    want, drop, already = m.bind_plan(["campaign", "bound:alpha"], "alpha")
    check("re-binding to the same machine is already, with nothing to remove",
          want == "bound:alpha" and drop == [] and already)
    want, drop, already = m.bind_plan(["bound:beta"], "alpha")
    check("binding a campaign held elsewhere removes the other label",
          want == "bound:alpha" and drop == ["bound:beta"] and not already)
    # The state `bound` refuses, repaired in ONE edit: the wanted label is
    # already there AND another is too, so `already` alone must not short out.
    want, drop, already = m.bind_plan(["bound:alpha", "bound:beta"], "alpha")
    check("bind repairs a two-label campaign in one edit",
          want == "bound:alpha" and drop == ["bound:beta"] and already)
    # The three printed words are the whole contract; a caller reads the word.
    r = tracker("bound", "not-a-number")
    check("bound refuses a malformed campaign issue with exit 2, never a verdict",
          r.returncode == 2 and "not an issue number" in r.stderr
          and r.stdout.strip() == "")

    # ----------------------------------- the flags, which are why this exists
    # Nothing pinned them: the pure functions above pass whatever `gh` was asked
    # for, so deleting `--paginate` or `--limit` left the suite green while the
    # readings silently went back to a truncated first page.
    with tempfile.TemporaryDirectory() as d:
        shim, log = Path(d) / "bin", Path(d) / "argv"
        shim.mkdir()
        (shim / "gh").write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$@\" >> " + str(log) + "\n"
            "case \"$*\" in *sub_issues*) echo '[]' ;; *) echo '[]' ;; esac\n")
        (shim / "gh").chmod(0o755)
        env = {"PATH": f"{shim}:/usr/bin:/bin", "HOME": str(d)}
        tracker("campaign-issues", env=env)
        argv = log.read_text()
        check("campaign issues passes --limit, since gh's default is thirty",
              "--limit" in argv)
        check("...and reads labels and parent from the one listing",
              "number,title,labels,parent" in argv)
        check("...and does not make a second, label-filtered call",
              argv.count("--state") == 1)
        check("...and raises it well past the default",
              any(x.isdigit() and int(x) >= 100 for x in argv.split()))
        # A listing that came back *at* the limit is a reading not made in
        # full, and the rows it would print are actively wrong rather than
        # merely short. It must refuse, not print a note and exit 0.
        (shim / "gh").write_text(
            "#!/bin/sh\necho '[{\"number\":1,\"title\":\"t\",\"labels\":[],"
            "\"parent\":null}]'\n")
        (shim / "gh").chmod(0o755)
        r = tracker("campaign-issues", "--limit", "1", env=env)
        check("a listing at the limit refuses rather than printing wrong rows",
              r.returncode == 1 and "REFUSING" in r.stdout + r.stderr)
        r = tracker("campaign-issues", "--limit", "9", env=env)
        check("...and a listing under the limit does not", r.returncode == 0)

        # A MISSING SLUG IS AN ANSWER, AND A FAILED LISTING IS NOT. Both used to
        # exit 1, so a caller could not tell "I read the tracker and a campaign
        # cannot be worked" from "I could not read the tracker". Two cases, one
        # per status, because either alone passes with the other's branch gone.
        (shim / "gh").write_text(
            "#!/bin/sh\necho '[{\"number\":1,\"title\":\"t\",\"labels\":"
            "[{\"name\":\"campaign\"}],\"parent\":null}]'\n")
        (shim / "gh").chmod(0o755)
        r = tracker("campaign-issues", env=env)
        check("a campaign issue with no slug is exit 3: read, and unworkable",
              r.returncode == 3 and "no `campaign:` label" in r.stdout + r.stderr)
        (shim / "gh").write_text(
            "#!/bin/sh\necho '[{\"number\":1,\"title\":\"t\",\"labels\":"
            "[{\"name\":\"campaign\"},{\"name\":\"campaign:demo\"}],"
            "\"parent\":null}]'\n")
        (shim / "gh").chmod(0o755)
        r = tracker("campaign-issues", env=env)
        check("...and with one it is exit 0, the slug printed beside its issue",
              r.returncode == 0 and "demo" in r.stdout)

        (shim / "gh").write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$@\" >> " + str(log) + "\necho '[]'\n")
        (shim / "gh").chmod(0o755)
        log.write_text("")
        tracker("index", "1", env=env)
        argv = log.read_text()
        check("index passes --paginate, since the endpoint pages at thirty",
              "--paginate" in argv)
        check("...against the sub_issues endpoint, which is the index",
              "sub_issues" in argv)

        # `bound` reads the issue itself, not its comments: one request, and
        # no page to stop early on. Deleting the `--jq` or asking the wrong
        # endpoint is what this pins.
        log.write_text("")
        (shim / "gh").write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$@\" >> " + str(log) + "\necho '[]'\n")
        (shim / "gh").chmod(0o755)
        r = tracker("bound", "1", env=env)
        argv = log.read_text()
        check("bound asks the issue for its labels, not the comments endpoint",
              "labels" in argv and "issues/1" in argv and "comments" not in argv)
        check("...and no bound: label prints `unbound`",
              r.returncode == 0 and r.stdout.strip() == "unbound")

        # The end-to-end refusal, which the pure case above cannot show: two
        # labels must come out as exit 2 with NO verdict on stdout, because a
        # caller reads the word and `unbound` here would invite a re-bind.
        (shim / "gh").write_text(
            "#!/bin/sh\necho '[\"bound:alpha\",\"bound:beta\"]'\n")
        (shim / "gh").chmod(0o755)
        r = tracker("bound", "1", env=env)
        check("two bound: labels exit 2 and print no verdict",
              r.returncode == 2 and r.stdout.strip() == ""
              and "bound:alpha" in r.stderr)

    # ----------------------------------------------- the end-to-end refusals
    # A tracker that cannot be read must never print "open campaign issues (0)".
    with tempfile.TemporaryDirectory() as d:
        shim = Path(d) / "bin"
        shim.mkdir()
        for body, label in ((
                # A non-zero exit that still prints a valid listing. Without the
                # status check the parse succeeds and the failure is invisible;
                # the earlier failing-gh case printed nothing, so the parse
                # branch did the refusing and the status branch was pinned by
                # nothing.
                "#!/bin/sh\necho '[]'\nexit 1\n", "a gh that fails but prints valid output"),
                ("#!/bin/sh\nexit 1\n", "a failing gh"),
                            ("#!/bin/sh\necho 'not json'\n", "unparseable output"),
                            ("#!/bin/sh\necho '{}'\n", "an object instead of a list")):
            (shim / "gh").write_text(body)
            (shim / "gh").chmod(0o755)
            r = tracker("campaign-issues",
                        env={"PATH": f"{shim}:/usr/bin:/bin", "HOME": str(d)})
            out = r.stdout + r.stderr
            check(f"{label} refuses rather than printing an empty tracker",
                  r.returncode == 1 and "open campaign issues" not in out)

    # The same branch on the index reader.
    with tempfile.TemporaryDirectory() as d:
        shim = Path(d) / "bin"
        shim.mkdir()
        (shim / "gh").write_text("#!/bin/sh\necho '[]'\nexit 1\n")
        (shim / "gh").chmod(0o755)
        r = tracker("index", "1",
                    env={"PATH": f"{shim}:/usr/bin:/bin", "HOME": str(d)})
        check("a gh that fails but prints valid output is not an empty index",
              r.returncode == 1 and "0 sub-issue(s)" not in r.stdout)

    for args in (("campaign-issues",), ("index", "1")):
        r = tracker(*args, env={"PATH": "/nonexistent", "HOME": "/tmp"})
        out = r.stdout + r.stderr
        check(f"`{args[0]}` refuses when gh cannot be run",
              r.returncode == 1 and "not" in out.lower() and "Traceback" not in out)
    # `bound` refuses on exit 2, not 1: its status is about the reading, and a
    # caller that read 1 as "unbound" would bind a campaign another machine has.
    r = tracker("bound", "1", env={"PATH": "/nonexistent", "HOME": "/tmp"})
    out = r.stdout + r.stderr
    check("`bound` refuses on exit 2 when gh cannot be run, printing no verdict",
          r.returncode == 2 and "Traceback" not in out
          and out.strip().splitlines()[-1].strip() not in ("here", "unbound"))

    # ----------------------------------------------------------- settlement
    with tempfile.TemporaryDirectory() as tmp:
        merged = {"state": "MERGED"}
        base = {"head": head(),
                "index": [sub(10), sub(11)],
                "issue:kalaluthien/campaign-base#10":
                    issue("CLOSED", "COMPLETED", prs=[90]),
                "issue:kalaluthien/campaign-base#11":
                    issue("CLOSED", "COMPLETED", prs=[91]),
                "pr:kalaluthien/campaign-base#90": merged,
                "pr:kalaluthien/campaign-base#91": merged}

        # The whole reason this section exists: no verdict is not a clean verdict.
        for what, index in (("gh exits non-zero", {"exit": 1, "stderr": "HTTP 404"}),
                            ("the body is not JSON", "<html>not json</html>"),
                            ("the endpoint returns an object", {"total": 2})):
            code, out, err = settlement(dict(base, index=index), tmp)
            check(f"an index that did not read refuses -- {what}",
                  code != 0 and "the index is empty" not in out
                  and "could not read the sub-issue index" in err
                  and "Traceback" not in err)

        code, out, err = settlement(dict(base, index=[]), tmp)
        check("an index that read empty is a campaign with no sub-issues",
              code == 0 and "the index is empty" in out)

        code, out, err = settlement(base, tmp)
        check("every sub-issue settled reads closable",
              code == 0 and "2/2 settled; closable" in out)

        code, out, err = settlement(dict(base, **{
            "issue:kalaluthien/campaign-base#11": issue("OPEN")}), tmp)
        check("one open sub-issue refuses the close",
              code == 0 and "1/2 settled; NOT closable" in out
              and "#11" in out and " open " in out)

        # A sub-issue closed on purpose is settled; the note says which kind, and
        # AGENTS.md tells a reader to quote the note rather than the word.
        code, out, err = settlement(dict(base, **{
            "issue:kalaluthien/campaign-base#11":
                issue("CLOSED", "NOT_PLANNED")}), tmp)
        check("a sub-issue dropped as not planned still settles",
              code == 0 and "2/2 settled; closable" in out
              and "[not planned]" in out)

        code, out, err = settlement(dict(base, **{
            "issue:kalaluthien/campaign-base#11":
                issue("CLOSED", "COMPLETED")}), tmp)
        check("closed as completed with nothing to merge names its note",
              code == 0 and "[completed, no merged pull request]" in out)

        code, out, err = settlement(dict(base, **{
            "pr:kalaluthien/campaign-base#91": {"state": "CLOSED"}}), tmp)
        check("a closing pull request that never merged is dropped, not complete",
              code == 0 and "dropped" in out and "2/2 settled" in out)

        # A reading that could not be made is its own verdict. Every one of
        # these aborted the table before the fourth column existed: the reader
        # asked for a settlement and got a message about `gh`, or a traceback.
        for what, fixture in (
                ("its closing pull request is in a repository gone private",
                 {"pr:kalaluthien/campaign-base#91": {"exit": 1, "stderr": "HTTP 404"}}),
                ("its own issue cannot be read",
                 {"issue:kalaluthien/campaign-base#11": {"exit": 1, "stderr": "HTTP 404"}}),
                ("the API places its pull request in no repository",
                 {"issue:kalaluthien/campaign-base#11":
                  issue("CLOSED", "COMPLETED", prs=[91], homeless=True)})):
            code, out, err = settlement(dict(base, **fixture), tmp)
            check(f"a sub-issue reads unread when {what}",
                  code == 0 and " unread " in out and "Traceback" not in err)
            check(f"...and the count separates it from settled -- {what}",
                  "1/2 settled, 1 unread; NOT closable" in out)
            check(f"...and the refusal names the reading, not open work -- {what}",
                  "could not be read" in out and "open sub-issues remain" not in out)

        # The other end of the same rule: the campaign issue read is one call too, and
        # its failure must not come back as a table with nothing in it.
        code, out, err = settlement(dict(base, head={"exit": 1, "stderr": "HTTP 404"}), tmp)
        check("a campaign issue that did not read refuses, saying no verdict was reached",
              code != 0 and "could not read the campaign issue" in err
              and "No verdict was reached" in err and "Traceback" not in err)

        code, out, err = settlement(dict(base, head=head(labels=())), tmp)
        check("a number with no campaign label is reported as maybe a sub-issue",
              code == 0 and "may be a sub-issue" in out)

        code, out, err = settlement(dict(base, head=head(parent={"number": 7})), tmp)
        check("a campaign issue that is itself a sub-issue is reported",
              code == 0 and "sub-issue of #7" in out)

        code, out, err = settlement(dict(base, index=[sub(10), sub(11, nested=3)]), tmp)
        check("a sub-issue with members of its own is reported, not counted",
              code == 0 and "3 sub-issue(s) of its own" in out)

        code, out, err = settlement(dict(base, head=head(state="CLOSED"), **{
            "issue:kalaluthien/campaign-base#11": issue("OPEN")}), tmp)
        check("a campaign issue closed over an open sub-issue is reported",
              code == 0 and "the campaign issue is closed with sub-issues still open" in out)

        # A sub-issue filed on another repository is read there, not here.
        code, out, err = settlement(dict(base, index=[sub(10), sub(5, repo="o/other")],
                                         **{"issue:o/other#5": issue("OPEN")}), tmp)
        check("a sub-issue in another repository is read against that repository",
              code == 0 and "o/other#5" in out and "1/2 settled" in out)

        # settlement reads the index through the same function `index` prints
        # from. Moving only the parse behind a script once left `--paginate`
        # hand-written on this path, where deleting it silently dropped fourteen
        # sub-issues and turned "NOT closable" into "closable".
        check("settlement and index share one reader of the sub-issue endpoint",
              m.cmd_settlement.__code__.co_names.count("fetch_index") == 1
              and m.cmd_index.__code__.co_names.count("fetch_index") == 1)

    # ------------------------------------------------------------ check (#217)
    # PURE, so every branch has a case that spends no request. `kind_of` and
    # `shape_findings` are the whole reading; `cmd_check` only prints it and
    # turns it into an exit, and the two shell cases below pin that half.
    check("the `campaign` label with no parent is a campaign issue",
          m.kind_of(True, False) == m.CAMPAIGN)
    check("a parent with no label is a sub-issue",
          m.kind_of(False, True) == m.SUB_ISSUE)
    check("both is a stray, which is a defect and not a kind",
          m.kind_of(True, True) == m.STRAY)
    check("neither is the third kind, which every reader leaves alone",
          m.kind_of(False, False) == m.THIRD_KIND)

    good_sub = ("## Intent\n- x\n\n## Definition of done\n- x\n\n## Plan\n- x\n"
                "\n## Lands in\n- none\n")
    good_campaign = ("## Intent\n- x\n\n## Scope\nIn:\n- x\n\n## Definition of done\n"
                     "- x\n\n## Repos\n- none\n")
    check("a well-shaped sub-issue has no finding, plan required",
          m.shape_findings(m.SUB_ISSUE, "Do the thing", good_sub, True) == [])
    check("a well-shaped campaign issue has no finding",
          m.shape_findings(m.CAMPAIGN, "Do the thing", good_campaign, False) == [])
    # THE THIRD KIND HAS NO SHAPE, so a body that would fail every section test
    # passes here. It is the row a body-text classifier could not express.
    check("the third kind is not judged on sections at all",
          m.shape_findings(m.THIRD_KIND, "anything at all", "prose", False) == [])
    # ...BUT THE CEILINGS ARE NOT A KIND'S. A title is a title.
    check("...and still on the ceilings",
          any("over 80" in f for f in m.shape_findings(
              m.THIRD_KIND, "x" * 81, "prose", False)))

    # ONE MISSING SECTION AT A TIME, named. A case that removed two would pass
    # while either branch was deleted.
    for want, body in (
            ("Intent", good_sub.replace("## Intent\n- x\n\n", "")),
            ("Definition of done", good_sub.replace("## Definition of done\n- x\n\n", "")),
            ("Plan", good_sub.replace("## Plan\n- x\n\n", ""))):
        found = m.shape_findings(m.SUB_ISSUE, "t", body, True)
        check(f"a sub-issue with no `## {want}` is refused by that name",
              any(f"no `## {want}` section" in f for f in found))
    # `## Lands in` IS THE ONE ROW THIS FILE DOES NOT DECIDE. It is delegated to
    # `campaign-repos.py`'s `lands_in`, because a presence test here and a real
    # reader there disagreed on four bodies and `check` printed "the shape
    # holds" on each one the claim path then refused. The case is on the
    # DELEGATE's own words, so a copy re-derived here would fail it.
    missing = good_sub.replace("\n## Lands in\n- none\n", "\n")
    found = m.shape_findings(m.SUB_ISSUE, "t", missing, True)
    check("a missing `## Lands in` is refused in the delegate's own words",
          any("no `## Lands in` heading" in f for f in found))
    # A DELEGATE THAT WILL NOT LOAD IS NOT A SECTION THAT IS RIGHT. The branch
    # fires whenever `campaign-repos.py` is missing or unimportable, and it was
    # declared dead when it is merely unreached: an absence read as a pass is
    # what this whole file exists to refuse.
    was = m.repos_module
    try:
        def boom():
            raise ImportError("no campaign-repos.py")
        m.repos_module = boom
        found = m.shape_findings(m.SUB_ISSUE, "t", good_sub, True)
    finally:
        m.repos_module = was
    check("a `## Lands in` reader that will not load is a finding, not a pass",
          len(found) == 1 and "would not load" in found[0]
          and "not a section that is right" in found[0])
    for label, body in (
            ("inside an HTML comment",
             good_sub.replace("## Lands in\n- none\n",
                              "<!--\n## Lands in\n- none\n-->\n")),
            ("empty", good_sub.replace("## Lands in\n- none\n",
                                       "## Lands in\n\n## Z\n- q\n")),
            ("two entries", good_sub.replace("## Lands in\n- none\n",
                                             "## Lands in\n- a/b\n- c/d\n")),
            ("with two spaces in the heading",
             good_sub.replace("## Lands in\n", "##  Lands in\n"))):
        # THE FOUR BODIES THE TWO READERS DISAGREED ON. Each passed the
        # presence test and was refused at the claim, so each is a case -- but
        # the four exercise THREE refusals, not four: the HTML-commented body
        # and the two-space one share the no-heading refusal with each other and
        # with the separate case above, because `section()`'s pattern pins the
        # single space and strips comments before it walks. Kept apart anyway,
        # because what each documents is a disagreement that was real per body;
        # do not read the count as coverage of four branches.
        found = m.shape_findings(m.SUB_ISSUE, "t", body, True)
        check(f"a `## Lands in` {label} is a finding, as it is at the claim",
              len(found) == 1 and "`## Lands in`:" in found[0])
    for want, body in (
            ("Scope", good_campaign.replace("## Scope\nIn:\n- x\n\n", "")),
            ("Repos", good_campaign.replace("\n## Repos\n- none\n", "\n"))):
        found = m.shape_findings(m.CAMPAIGN, "t", body, False)
        check(f"a campaign issue with no `## {want}` is refused by that name",
              any(f"no `## {want}` section" in f for f in found))
    # A CAMPAIGN ISSUE OMITS A SECTION; IT DOES NOT RENAME ONE. `## Plan` and
    # `## Lands in` are a sub-issue's, and requiring them of a campaign would
    # be the vocabulary drifting back apart.
    check("a campaign issue is not asked for `## Plan` or `## Lands in`",
          m.shape_findings(m.CAMPAIGN, "t", good_campaign, True) == [])
    # THE TWO MOMENTS. `## Plan` is due at the claim and not at the filing, so
    # the same body must pass one and fail the other; a case asserting only one
    # of the two passes with the flag ignored.
    no_plan = good_sub.replace("## Plan\n- x\n\n", "")
    check("a sub-issue with no plan passes at filing",
          m.shape_findings(m.SUB_ISSUE, "t", no_plan, False) == [])
    check("...and fails at the claim, which is the same body read twice",
          m.shape_findings(m.SUB_ISSUE, "t", no_plan, True) != [])

    check("a title one character over the ceiling is refused, with both numbers",
          m.shape_findings(m.SUB_ISSUE, "x" * 81, good_sub, True)
          == ["the title is 81 characters, over 80"])
    check("...and a title at the ceiling exactly is not",
          m.shape_findings(m.SUB_ISSUE, "x" * 80, good_sub, True) == [])
    # PADDED UNDER ITS OWN HEADING, not appended: appended, the padding became a
    # SECOND `## Lands in` entry and the body carried two faults, so the "two
    # findings" case below counted three.
    over = good_sub + "\n## Pad\n- " + "y" * 2000
    check("a body over the ceiling is refused, with both numbers",
          any(f"the body is {len(over)} characters, over 2000" in f
              for f in m.shape_findings(m.SUB_ISSUE, "t", over, True)))
    # EVERY FINDING, NOT THE FIRST. A body both too long and missing a section
    # needs two edits, and a checker naming one sends its reader back.
    both = m.shape_findings(m.SUB_ISSUE, "x" * 90, over, True)
    check("a title and a body both over the ceiling give two findings",
          len(both) == 2 and any("title" in f for f in both)
          and any("body" in f for f in both))
    # A STRAY IS ONE FINDING AND NOT A PILE, because the repair is one edit and
    # the sections it should carry are exactly what nobody can say.
    stray_found = m.shape_findings(m.STRAY, "x" * 90, "", True)
    check("a stray is reported as a stray and not as a heap of missing sections",
          len(stray_found) == 1 and "not a kind" in stray_found[0])

    with tempfile.TemporaryDirectory() as tmp:
        # THE SHELL HALF: what `check` exits with, and what it prints beside the
        # verdict. A bare exit code is satisfied by every other cause that
        # shares it, so both cases assert the reading too.
        def shim(body, title="Do the thing", labels=(), parent=True):
            src = ('#!/usr/bin/env python3\nimport json, sys\n'
                   f'print(json.dumps({{"title": {title!r}, "body": {body!r}, '
                   f'"labels": [{{"name": n}} for n in {list(labels)!r}], '
                   f'"parent": {({"number": 1} if parent else None)!r}}}))\n')
            d = Path(tmp) / f"shim{abs(hash(src))}"
            d.mkdir()
            (d / "gh").write_text(src)
            (d / "gh").chmod(0o755)
            env = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}")
            return env

        r = tracker("check", "5", "--plan", env=shim(good_sub))
        check("check exits 0 on a well-shaped sub-issue",
              r.returncode == 0 and "RESULT   the shape holds" in r.stdout)
        check("...and prints what it read, not only its verdict",
              "title  12 chars" in r.stdout and "body   " in r.stdout
              and "sections found: Intent, Definition of done, Plan, Lands in" in r.stdout)
        check("...and names what it did NOT check",
              "NOT checked:" in r.stdout and "verb-first" in r.stdout)
        r = tracker("check", "5", "--plan", env=shim(no_plan))
        check("check exits 1 and puts the finding on stderr",
              r.returncode == 1 and "REFUSING" in r.stderr
              and "no `## Plan` section" in r.stderr)
        # AN ISSUE THAT DID NOT READ IS NOT AN ISSUE WITH NO SHAPE, and it gets
        # its own exit so a caller cannot read one as the other.
        d = Path(tmp) / "unread"
        d.mkdir()
        (d / "gh").write_text("#!/bin/sh\nexit 1\n")
        (d / "gh").chmod(0o755)
        r = tracker("check", "5", env=dict(os.environ,
                                           PATH=f"{d}:{os.environ['PATH']}"))
        check("an unreadable issue exits 2, not 1",
              r.returncode == 2 and "could not read" in r.stderr
              and "is not an issue with no shape" in r.stderr)
        # THE PARKED ROW IS REPORTED AND NOT REFUSED HERE: `backlog` is a
        # claim's question, and a `check` that failed on it could not be used
        # to read a parked issue's shape at all.
        r = tracker("check", "5", "--plan",
                    env=shim(good_sub, labels=("backlog",)))
        check("`backlog` is reported by check and does not fail it",
              r.returncode == 0 and "carries `backlog`" in r.stdout)

        # `bind` REPORTS THE SHAPE AND NEVER GATES ON IT, which is the whole
        # reason `check` is its own verb: `bind` is the ONLY repair for the
        # two-`bound:`-label state, so a `bind` that refused an oversize body
        # would refuse to run on exactly the campaign that needs repairing.
        # Asserted on the LABEL EDIT having happened, not on the exit status,
        # which a `bind` that quietly skipped the edit would share.
        d = Path(tmp) / "bindbad"
        d.mkdir()
        (d / "calls").write_text("")
        (d / "gh").write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            f"open({str(d / 'calls')!r}, 'a').write(' '.join(sys.argv[1:]) + chr(10))\n"
            "if '--json' in sys.argv:\n"
            "    if 'labels' == sys.argv[sys.argv.index('--json') + 1]:\n"
            "        print(json.dumps([]))\n"
            "    else:\n"
            f"        print(json.dumps({{'title': 'x' * 120, 'body': 'no sections here',\n"
            "                           'labels': [], 'parent': {'number': 1}}))\n"
            "sys.exit(0)\n")
        (d / "gh").chmod(0o755)
        r = tracker("bind", "5", env=dict(os.environ,
                                          PATH=f"{d}:{os.environ['PATH']}"))
        calls = (d / "calls").read_text()
        check("bind sets the label even when the shape does not hold",
              r.returncode == 0 and "--add-label bound:" in calls)
        check("...and says so, naming the findings it did not act on",
              "reported and not enforced here" in r.stdout
              and "over 80" in r.stdout)
        # AN UNREADABLE SHAPE IS A THIRD ANSWER, not a clean bill: `bind` must
        # say it did not look rather than print a shape it never read.
        d2 = Path(tmp) / "bindunread"
        d2.mkdir()
        (d2 / "gh").write_text(
            "#!/bin/sh\ncase \"$*\" in *--json*) exit 1 ;; esac\nexit 0\n")
        (d2 / "gh").chmod(0o755)
        r = tracker("bind", "5", env=dict(os.environ,
                                          PATH=f"{d2}:{os.environ['PATH']}"))
        check("bind reports a shape it could not read as unread, and still binds",
              r.returncode == 0 and "the shape was NOT read" in r.stdout)

    # ------------------------------------------------ standing: the person's hold
    # A LABEL READING, so on and off are both cases with no network in them.
    check("the hold is read off the label list",
          m.is_standing(["campaign", "standing"]) is True)
    check("...and its absence is the other reading, not a failure",
          m.is_standing(["campaign", "backlog"]) is False)
    # The prefix readers must not claim it: `standing` has no colon, and a
    # `startswith` here would make `campaign:standing` a hold.
    check("a slug label is not a hold", m.is_standing(["campaign:standing"]) is False)
    check("label_names drops a label with no name rather than raising",
          m.label_names({"labels": [{"name": "a"}, {}, {"name": 2}]}) == ["a"])

    def printed(fn, *a):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fn(*a)
        return buf.getvalue()

    held = {"number": 272, "title": "keep me", "labels": [{"name": "standing"}]}
    free = {"number": 1, "title": "close me", "labels": [{"name": "campaign"}]}
    out = printed(m.rows, "open campaign issues", [held, free])
    check("the survey prints the hold beside the row that carries it",
          "#272" in out and "[standing]" in out.split("#272")[1].split("\n")[0])
    # THE CONTROL. Printed on every row, the marker says nothing; this is the
    # case that separates "read the label" from "printed the word".
    check("...and not beside the row that does not",
          "[standing]" not in out.split("#1")[1].split("\n")[0])

    # ------------------------------------------------ the `<slug>#N` reference form
    check("a bare number is a reference nothing qualifies",
          m.bare_references("see #185 for the role reading") == ["#185"])
    check("a slug-qualified reference is not bare",
          m.bare_references("machinery#1 and sdlc-alloy#246") == [])
    check("a pull request reference is not bare", m.bare_references("pr#255") == [])
    # THE FORM THE `Closes` KEYWORD NEEDS. A refusal here would refuse the one
    # spelling AGENTS.md prescribes for closing a sub-issue.
    check("the full owner/repo#N name is not bare",
          m.bare_references("Closes kalaluthien/campaign-base#217") == [])
    check("one number twice is one finding, in the order it first appears",
          m.bare_references("#9 then #4 then #9") == ["#9", "#4"])
    check("a markdown heading is not a reference", m.bare_references("## Intent") == [])
    # THE LOOKBEHIND, MEMBER BY MEMBER. What qualifies a reference is the WORD
    # CHARACTER before the `#`, and a wider class was measured to cost real
    # misses across the 162 issues on this tracker while protecting nothing:
    # each of these forms is already saved by its own last letter or digit.
    check("a letter before the hash qualifies it", m.bare_references("pr#255") == [])
    check("a digit before the hash qualifies it", m.bare_references("v2#255") == [])
    check("an underscore before the hash qualifies it",
          m.bare_references("a_b#255") == [])
    # THE THREE THAT WERE IN THE CLASS AND COST MISSES, one case each. Every
    # one of these is a bare reference a reader cannot resolve.
    check("a hyphen does not qualify a reference", m.bare_references("pre-#181") == ["#181"])
    check("a slash does not qualify one either",
          m.bare_references("#116/#160") == ["#116", "#160"])
    check("nor does a sentence's full stop",
          m.bare_references("that is the note.#41 says why") == ["#41"])
    check("a body with nothing bare in it warns about nothing",
          m.bare_reference_warning(m.bare_references("machinery#1")) == "")
    check("the warning names every reference and says it is not a refusal",
          "#185" in m.bare_reference_warning(["#185"])
          and "not a refusal" in m.bare_reference_warning(["#185"]))

    # `tmp` IS REBOUND ON PURPOSE. `shim` above is a closure over `main`'s
    # `tmp`, and the directory it named is gone; binding the fresh one to the
    # same name is what lets the two `check` cases below reuse it rather than
    # carry a second copy of the same three lines.
    with tempfile.TemporaryDirectory() as tmp:
        def labels_shim(name, payload):
            d = Path(tmp) / name
            d.mkdir()
            (d / "gh").write_text("#!/usr/bin/env python3\n"
                                  "import sys\n"
                                  f"sys.stdout.write({payload!r})\n")
            (d / "gh").chmod(0o755)
            return dict(os.environ, PATH=f"{d}:{os.environ['PATH']}")

        r = tracker("standing", "272", env=labels_shim("held", '["campaign", "standing"]'))
        check("the standing verb answers with a word on stdout",
              r.returncode == 0 and r.stdout.strip() == "standing")
        r = tracker("standing", "1", env=labels_shim("free", '["campaign"]'))
        check("...and `not-standing` is the other word, not an empty line",
              r.returncode == 0 and r.stdout.strip() == "not-standing")
        # THE NAMED FAILING CASE FOR THE REFUSAL. Labels that did not read must
        # never come back as `not-standing`: that absence is what a close would
        # take for consent. Asserted on the word being absent, not only on the
        # status, since a crash shares exit 2 with a refusal.
        d = Path(tmp) / "unreadable"
        d.mkdir()
        (d / "gh").write_text("#!/bin/sh\necho 'gh: no' >&2\nexit 1\n")
        (d / "gh").chmod(0o755)
        r = tracker("standing", "1", env=dict(os.environ,
                                              PATH=f"{d}:{os.environ['PATH']}"))
        check("labels that did not read exit 2 and print no verdict",
              r.returncode == 2 and "standing" not in r.stdout)
        # The refusal names the verb a person typed, not the verb this reading
        # path was written for.
        check("...and the refusal names `standing`, not `bound`",
              "campaign-tracker standing:" in r.stderr)

        # THE WARNING RIDES WITH THE READING AND MOVES NO EXIT STATUS.
        good_ref = good_sub.replace("## Intent\n- x\n", "## Intent\n- see #185\n")
        # THE TITLE IS READ BESIDE THE BODY. The rule exempts no field, and a
        # title-only case is the one that separates the two arguments; with the
        # body alone this passes with no warning at all.
        r = tracker("check", "5", "--plan",
                    env=shim(good_sub, title="Fix the thing broken by #185"))
        check("a bare reference in the TITLE is warned about too",
              r.returncode == 0 and "WARNING" in r.stdout and "#185" in r.stdout)
        r = tracker("check", "5", "--plan", env=shim(good_ref))
        check("check warns about a bare reference and still holds",
              r.returncode == 0 and "WARNING" in r.stdout
              and "#185" in r.stdout and "RESULT   the shape holds" in r.stdout)
        # THE CONTROL: printed unconditionally, the warning says nothing.
        r = tracker("check", "5", "--plan", env=shim(good_sub))
        check("...and says nothing about a body with no bare reference",
              r.returncode == 0 and "WARNING" not in r.stdout)

    if not ran:
        print("FAIL  the suite ran no case at all")
        return 1
    for f in fails:
        print(f"FAIL  {f}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
