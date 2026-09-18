#!/usr/bin/env python3
"""Print where a spec comment reads contradicted by the definition under it, and refuse nothing.

THE READING `model-comment` in scripts/jev/readings.json, asked through
scripts/campaign-jev.py at `pre-commit` beside check-cited-claims.py. The
entry holds its question, criteria, state fields, prefilter, thresholds and
tier; this reads them and writes none of them. How to ask Jev well in general
is the `asking-jev` skill's `references/`, not this file's.

S1 TURNED INWARD, so the cutter, the question builder and the report are
IMPORTED from check-cited-claims.py rather than written again. S1 reads prose
OUTSIDE spec/ against a definition it cites by name; this reads the comment
sitting directly ABOVE a definition against that definition's own body. Four
things differ, and only these:

  paired      by POSITION and not by a backtick. The comment above a definition
              is about that definition, so there is no `cited`, no `plain_name`
              anchoring and no declared-twice skip: the pairing cannot be
              ambiguous, and a name declared twice still has two comments
  a `fact`    counts. S1's `DECL` reads what prose may CITE, which is only ever
              a pred, fun or assert; a named fact carries a comment like any
              other definition and is read against it here
  the body    is the definition's own code with ITS OWN COMMENTS BLANKED, so a
              claim is never inside its own evidence. S1 puts the comment INTO
              `pred.text` on purpose -- there the claim came from somewhere
              else, and the comment is context; here it is the question
  the state   is `{claim, body}` and not `{paragraph, pred}`. One call carries
              every claim of one definition and each question carries its own
              sentence, so a case is one claim against one body

WHAT IT READS, from the INDEX (`git diff --cached` and `git cat-file`), so what
is judged is what the commit holds:

  definitions every pred, fun, assert and fact under spec/, with the comment
              block directly above it and the block it opens
  claims      one sentence of that comment block, split by S1's `SENTENCE`
  asked       every definition a staged hunk overlaps, its comment included:
              one call a definition, one question a claim, all in one call
  skipped     what the entry's `prefilter` settles, each written as a skip row
              naming which rule removed it, so a count of what this reading
              covered can see what code settled

THE BRANCH is the caller's, on the entry's two edges over P(contradicts): `yes`
contradicted, `no` clear, `uncertain` between the edges and `unknown` where the
reading failed. The tier decides what is printed: at `advise` each contradicted
or unknown claim with its value or reason; at `shadow` the counts alone. Every
call is logged by the caller, and the log line's fate is printed. THE EXIT
STATUS IS 0 on every path, a failure of this script included: a judgment here
never refuses a commit.

THE CASES are scripts/jev/corpus/model-comment.jsonl, each with the values it
was seen at.

Usage: scripts/check-model-comment.py --staged
"""
import importlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
READING = "model-comment"
# THE ROWS' READER KEEPS ITS FLAG, as every row this reader ever wrote carries
# it; which is why the raise line is `raised`'s and not the shell's stock one.
READER = "check-model-comment.py --staged"
INPUT = "staged"
USAGE = "scripts/check-model-comment.py --staged"
S1 = "check-cited-claims.py"
# A `fact` beside S1's three: see the docstring. S1's own `DECL` stays what it
# is, because widening it would widen what prose may cite.
DECL = re.compile(r"^\s*(?:private\s+)?(pred|fun|assert|fact)\s+(\w+)")
SPEC = re.compile(r"spec/.+\.als")
# The comment's own delimiters, off the text before it is cut into sentences: a
# sentence that opens `/* Q13.` is the marker and the claim run together, `*/`
# at the end is a claim's last word to nobody, and a block comment's `*` down
# the left margin is a delimiter that SENTENCE will not split after, so two
# sentences left carrying it become one claim.
MARKER = re.compile(r"^[ \t]*(?:/\*+|--+|//+|\*(?!/))[ \t]?|\*/[ \t]*$", re.M)


def definitions(texts, s1):
    """[(path, name, comment, body, first line, last line)] over the .als
    texts, the comment blanked out of the body and the body out of the
    comment."""
    out = []
    for path in sorted(texts):
        lines = texts[path].split("\n")
        code = s1.code_lines(lines)
        for i, line in enumerate(code):
            m = DECL.match(line)
            if not m:
                continue
            first, last = s1.comment_above(lines, i), s1.block_end(code, i)
            out.append((path, m.group(2),
                        MARKER.sub("", "\n".join(lines[first:i])).strip(),
                        "\n".join(code[i:last + 1]).strip(),
                        first + 1, last + 1))
    return out


def claims(comment, body, prefilter, s1):
    """(the sentences to ask, [(line or sentence, why it was skipped)]).

    THE TWO CODE RULES OF THE ENTRY, in the order they are cheapest: a
    section-header comment is not a claim about anything, and a sentence naming
    no identifier of the body has nothing here to be true or false of.

    A HEADER IS A LINE AND NOT A SENTENCE, and taking it off the comment before
    the sentences are cut is what keeps the rule to its own name: a header ends
    with no `.`, so `SENTENCE` never splits it from the claim written under it,
    and read over the sentences it settled that claim too.

    AN ALLOY KEYWORD IS NOT AN IDENTIFIER OF THE BODY, nor is a one- or
    two-letter word, and dropping both from either side is what makes the
    second rule mean its own name: `all`, `no` and `set` are ordinary English,
    and the article `a` matches a bound `a` in every body that has one."""
    header = re.compile(prefilter["section_header"])
    word = re.compile(prefilter["identifiers"])
    keywords = set(prefilter["keywords"])
    names = set(word.findall(body)) - keywords
    asked, skipped, kept = [], [], []
    for line in comment.split("\n"):
        if header.search(line):
            skipped.append((line.strip(), "a section-header comment"))
        else:
            kept.append(line)
    for sentence in s1.SENTENCE.split(" ".join(" ".join(kept).split())):
        sentence = sentence.strip()
        if not sentence:
            continue
        if not names & (set(word.findall(sentence)) - keywords):
            skipped.append((sentence, "names no identifier of the body"))
        else:
            asked.append(sentence)
    return list(dict.fromkeys(asked)), skipped


def ask_all(entry, states, jev, key, s1):
    """The `Ask` of every definition, six at a time; what it prints is S1's
    `report`, over [(label, claims, {claim id: Answer}, the log line's fate)].

    ONE `judge` CALL A DEFINITION, where it used to be one `ask`. The entry's
    `compose` puts each claim's text in its own question -- the shape
    `s1.questions` built by hand, asserted byte for byte by campaign-jev-test's
    "a question composed into the instructions is what the reader sent" -- so
    what is sent did not move. What the ROW gained is the reading's name, the
    wording, and the KEY: the repository, the sha this commit sits on, the file
    and the definition. Without those a row could never be joined to what
    happened to that comment afterwards, which is why every one of them parked
    in the log for good (sdlc-alloy#458 DECISION 5722176509)."""
    asks = [{"state": {"claim": {f"c{i}": c for i, c in enumerate(found)},
                       "body": body},
             "read": label, "key": dict(key, path=path, name=name)}
            for label, path, name, found, body in states]
    return jev.Ask(asks, {"workers": 6, "group": entry["group"]},
                   lambda judged: s1.report(
                       [(label, found, jev.words_of(entry, j.verdicts[READING]),
                         j.logged)
                        for (label, _path, _name, found, _body), j
                        in zip(states, judged)],
                       entry))


def steps(_inp, registry, jev):
    if READING not in registry:
        yield jev.Say(f"check-model-comment: no entry `{READING}` in the "
                      f"registry; nothing asked")
        return
    entry = registry[READING]
    s1 = jev.load_sibling(S1)
    # `--no-prefix` PINNED, as S1 pins it: a user's `diff.noprefix` changes
    # what `+++` carries, and a parser reading `b/` found no file at all.
    hunks = s1.staged_hunks(s1.git("diff", "--cached", "-U0", "-M",
                                   "--no-color", "--no-ext-diff",
                                   "--no-prefix"))
    staged = [p for p in hunks if SPEC.fullmatch(p)]
    if not staged:
        yield jev.Say(f"check-model-comment: {len(hunks)} staged file(s), none "
                      f"a spec/ module; nothing asked")
        return
    texts = s1.index_texts([p for p in s1.git("ls-files", "-z").split("\0")
                            if SPEC.fullmatch(p)])
    states, skipped = [], 0
    for path, name, comment, body, first, last in definitions(texts, s1):
        if not s1.overlaps(hunks.get(path, []), first, last):
            continue
        found, dropped = claims(comment, body, entry["prefilter"], s1)
        for sentence, why in dropped:
            skipped += 1
            yield jev.Skip(f"{path} `{name}`: {sentence}", why)
        if found:
            states.append((f"{path} `{name}`", path, name, found, body))
    yield jev.Say(f"check-model-comment `{READING}`: {len(staged)} staged spec "
                  f"file(s) read; {len(states)} definition(s) asked, "
                  f"{sum(len(s[3]) for s in states)} claim(s); {skipped} "
                  f"sentence(s) settled by code")
    if states:
        yield ask_all(entry, states, jev, jev.commit_key(), s1)


def raised(e):
    return [f"check-model-comment: could not read the commit "
            f"({e.__class__.__name__}: {e}); nothing asked, exit status "
            f"unmoved"]


def main(argv, out=None, env=None):
    # THE IMPORT INSIDE A BOUNDARY: a campaign-jev that will not load is a
    # reading lost and never a commit refused.
    try:
        jev = importlib.import_module("campaign-jev")
    except Exception as e:  # noqa: BLE001
        for line in raised(e):
            print(line, file=out)
        return 0
    return jev.run_reader(globals(), argv, out=out, env=env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
