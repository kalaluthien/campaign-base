#!/usr/bin/env python3
"""Prove campaign-repos refuses each wrong list for its own reason, and reads a
right one.

Its refusals were the only statement of what a `## Repos` list may hold and no
case exercised any of them: `campaign-claim-test.py` reaches this script through
two fixture bodies, which covers the heading and one good list, and nothing
else. That is the shape a contract takes just before it drifts -- so each
refusal here is asserted on the SENTENCE it prints, never on the exit status,
which every other refusal shares.

`slug`, `key` and `WRAPPERS` are the second half. They are what makes two spellings one
repository for `campaign-claim.py` as well as for this file
(kalaluthien/campaign-base#205), so a change to either that leaves them agreeing
by accident is what these pin. `is_base` is this file's own and is exported to
nobody.

Usage: scripts/campaign-repos-test.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOS = HERE / "campaign-repos.py"

RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{(' -- ' + detail) if detail else ''}")


def read(body):
    """(exit status, stdout, stderr) for one body."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(body)
        path = fh.name
    try:
        r = subprocess.run([sys.executable, str(REPOS), path],
                           capture_output=True, text=True)
        return r.returncode, r.stdout, r.stderr
    finally:
        Path(path).unlink()


def section(*lines):
    return "# A campaign\n\n## Repos\n" + "".join(f"- {l}\n" for l in lines) \
           + "\n## Intent\nx\n"


# (name, body, expected exit, a phrase the run must print). One row per
# refusal, so deleting any one of them fails exactly one case.
CASES = [
    ("a list of repositories comes back one per line",
     section("owner/one", "other/two"), 0, "owner/one"),
    ("`- none` alone prints nothing and exits 0",
     section("none"), 0, ""),
    ("no heading is not an empty list",
     "# A campaign\n\n## Intent\nx\n", 1, "no `## Repos` heading"),
    ("a line that is not a list item is malformed",
     "## Repos\n* owner/one\n", 1, "malformed line"),
    ("the template placeholder is malformed, not a repository",
     section("<owner/repo>"), 1, "malformed line"),
    ("an empty list is refused, not read as `- none`",
     "## Repos\n\n## Intent\nx\n", 1, "is empty"),
    ("`- none` mixed with a repository is refused",
     section("none", "owner/one"), 1, "never both"),
    ("two entries sharing a checkout directory are refused",
     section("owner/web", "other/Web"), 1, "share the checkout directory"),
    ("the same entry twice is refused as a duplicate",
     section("owner/one", "owner/one"), 1, "duplicate entry"),
    # #205: the base is a member of its own campaign by another route, so the
    # list never names it. Three spellings, because the reader that admitted
    # the plain one admitted all three.
    ("the base is refused from `## Repos`",
     section("kalaluthien/campaign-base"), 1, "names the base"),
    ("...however it is cased",
     section("Kalaluthien/Campaign-Base"), 1, "names the base"),
    ("...and with a `.git` on it",
     section("kalaluthien/campaign-base.git"), 1, "names the base"),
    # ALLOW beside that refusal: a member repository whose name merely looks
    # like the base's must still be read, or the check is a substring match.
    ("a repository that is not the base is still read",
     section("kalaluthien/campaign-base-tools"), 0,
     "kalaluthien/campaign-base-tools"),
    ("...and so is another owner's repository of the same name",
     section("someone/campaign-base"), 0, "someone/campaign-base"),
]


def main():
    for name, body, want_rc, phrase in CASES:
        rc, out, err = read(body)
        both = out + err
        check(name, rc == want_rc and phrase in both,
              f"exit {rc} (wanted {want_rc}): {both.strip()[:160]}")

    # `- none` prints NOTHING, which is a contract callers loop over. Asserted
    # apart from the case above, whose phrase is the empty string and so
    # matches any output at all.
    rc, out, _err = read(section("none"))
    check("`- none` prints no repository at all", rc == 0 and out.strip() == "",
          f"exit {rc}: {out!r}")

    # ---- slug / key: the one reader of what makes two spellings the
    # same repository. campaign-claim.py's `## Lands in` entry goes through
    # these, so each spelling that reaches it in prose has a row.
    sys.path.insert(0, str(HERE))
    import importlib.machinery
    import importlib.util
    spec = importlib.util.spec_from_loader(
        "campaign_repos", importlib.machinery.SourceFileLoader(
            "campaign_repos", str(REPOS)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    for text, want in [
        ("owner/repo", "owner/repo"),
        ("`owner/repo`", "owner/repo"),
        ('"owner/repo"', "owner/repo"),
        ("  owner/repo  ", "owner/repo"),
        ("owner/repo/", "owner/repo"),
        ("owner/repo.git", "owner/repo"),
        ("Owner/Repo", "Owner/Repo"),          # case is LEFT ALONE by slug
        ("<owner/repo>", None),                # the template placeholder
        ("none", None),
        ("nota repo", None),
        ("", None),
        (None, None),
    ]:
        check(f"slug({text!r}) is {want!r}", m.slug(text) == want,
              f"got {m.slug(text)!r}")

    check("key folds case where slug does not",
          m.key("Owner/Repo") == "owner/repo" and m.slug("Owner/Repo")
          == "Owner/Repo")
    check("key is None for a text that names no repository",
          m.key("<owner/repo>") is None)
    check("is_base sees the base through a wrapper, a case and a .git",
          all(m.is_base(x) for x in ("kalaluthien/campaign-base",
                                     "`kalaluthien/campaign-base`",
                                     "Kalaluthien/Campaign-Base",
                                     "kalaluthien/campaign-base.git")))
    check("is_base does not see a repository whose name merely starts with it",
          not m.is_base("kalaluthien/campaign-base-tools"))
    check("is_base does not see another owner's repository of the same name",
          not m.is_base("someone/campaign-base"))
    check("is_base is False for a text that names no repository",
          not m.is_base("<owner/repo>") and not m.is_base(""))
    # BASE_REPO is what campaign-claim.py imports as DEFAULT_REPO, so a rename
    # that touched one and not the other would be caught here rather than by a
    # claim cut on the wrong remote.
    check("BASE_REPO is a slug this file's own reader admits",
          m.slug(m.BASE_REPO) == m.BASE_REPO)

    # ------ `## Lands in`, the sub-issue's destination (#217) ------
    # ONE REFUSAL PER WAY OF BEING WRONG, asserted on the sentence, because the
    # repairs are different: write the heading, fix the bullet, delete an
    # entry, name a repository. `entry` and `why` are exclusive, and each case
    # asserts BOTH halves -- a reader returning an entry beside a refusal would
    # have the caller cut a ref on the strength of a line it had just rejected.
    lands = m.lands_in

    entry, why = lands("## Intent\n- x\n\n## Lands in\n- other/elsewhere\n")
    check("a `## Lands in` naming one repository reads as that repository",
          entry == "other/elsewhere" and why is None, f"{entry!r} {why!r}")
    entry, why = lands("## Lands in\n- none\n")
    check("...and `- none` reads as the sentinel, not as a refusal",
          entry == "none" and why is None, f"{entry!r} {why!r}")
    entry, why = lands("## Lands in\n- `none`\n")
    check("...and a wrapped sentinel is the same answer, as a slug would be",
          entry == "`none`" and why is None, f"{entry!r} {why!r}")
    entry, why = lands("## Intent\n- x\n")
    check("no `## Lands in` heading is refused by that name",
          entry is None and "no `## Lands in` heading" in (why or ""), repr(why))
    entry, why = lands("## Lands in\n\n## Next\n- x\n")
    check("an empty `## Lands in` is refused as empty and not as missing",
          entry is None and "is empty" in (why or ""), repr(why))
    entry, why = lands("## Lands in\n* other/elsewhere\n")
    check("a line that is not a `- ` bullet is refused as malformed",
          entry is None and "malformed line" in (why or ""), repr(why))
    entry, why = lands("## Lands in\n- a/b\n- c/d\n")
    check("two entries are refused, because a claim is one ref",
          entry is None and "2 entries" in (why or "")
          and "one ref" in (why or ""), repr(why))
    entry, why = lands("## Lands in\n- <owner/repo>\n")
    check("the template's own placeholder is refused as naming no repository",
          entry is None and "is not an owner/repo" in (why or "")
          and "nothing was compared" in (why or ""), repr(why))
    # THE BASE IS THE COMMONEST ANSWER HERE and the one `## Repos` refuses.
    # The two sections asking different questions is the whole reason this is a
    # second heading rather than `## Repos` with a count of one, so the case
    # that pins it is the one where they disagree.
    entry, why = lands(f"## Lands in\n- {m.BASE_REPO}\n")
    check("`## Lands in` admits the base, which `## Repos` refuses",
          entry == m.BASE_REPO and why is None, f"{entry!r} {why!r}")
    status, out, err = read(f"## Repos\n- {m.BASE_REPO}\n")
    check("...and the same slug in `## Repos` is still refused",
          status == 1 and "names the base" in err, f"{status}: {err[:120]}")
    # THE WALK IS ONE WALK, so a comment and the next heading bound both
    # sections alike. A second copy of it is what would stop honouring these.
    entry, why = lands("## Lands in\n<!-- - a/b -->\n- other/elsewhere\n"
                       "\n## Plan\n- z\n")
    check("a comment is not an entry and the next `## ` ends the section",
          entry == "other/elsewhere" and why is None, f"{entry!r} {why!r}")

    if not RAN:
        print("FAIL  the suite ran no case at all")
        return 1
    for f in FAILED:
        print(f"FAIL  {f}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
