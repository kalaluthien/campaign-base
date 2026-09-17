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
  skipped     a section-header comment (`/* ---- name ---- */`), and a sentence
              naming no identifier of the body; each is written as a skip row
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
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
READING = "model-comment"
REGISTRY = HERE / "jev" / "readings.json"
READER = "check-model-comment.py --staged"
S1 = "check-cited-claims.py"
# A `fact` beside S1's three: see the docstring. S1's own `DECL` stays what it
# is, because widening it would widen what prose may cite.
DECL = re.compile(r"^\s*(?:private\s+)?(pred|fun|assert|fact)\s+(\w+)")
SPEC = re.compile(r"spec/.+\.als")
# The comment's own delimiters, off the text before it is cut into sentences: a
# sentence that opens `/* Q13.` is the marker and the claim run together, and
# `*/` at the end is a claim's last word to nobody.
MARKER = re.compile(r"^[ \t]*(?:/\*+|--+|//+)[ \t]?|\*/[ \t]*$", re.M)


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
    """(the sentences to ask, [(sentence, why it was skipped)]).

    THE TWO CODE RULES OF THE ENTRY, in the order they are cheapest: a
    section-header comment is not a claim about anything, and a sentence naming
    no identifier of the body has nothing here to be true or false of.

    AN ALLOY KEYWORD IS NOT AN IDENTIFIER OF THE BODY, and dropping the entry's
    `keywords` from both sides is what makes the second rule mean its own name:
    `all`, `no`, `one`, `in` and `set` are ordinary English too, so a sentence
    sharing only those with the body names nothing in it."""
    header = re.compile(prefilter["section_header"])
    word = re.compile(prefilter["identifiers"])
    keywords = set(prefilter["keywords"])
    names = set(word.findall(body)) - keywords
    asked, skipped = [], []
    for sentence in s1.SENTENCE.split(" ".join(comment.split())):
        sentence = sentence.strip()
        if not sentence:
            continue
        if header.search(sentence):
            skipped.append((sentence, "a section-header comment"))
        elif not names & (set(word.findall(sentence)) - keywords):
            skipped.append((sentence, "names no identifier of the body"))
        else:
            asked.append(sentence)
    return list(dict.fromkeys(asked)), skipped


def ask_all(entry, states, jev, s1, env=None):
    """[(label, claims, Reading)] for every definition, asked six at a time.

    ONE CALL A DEFINITION: `s1.questions` turns the claims into one question
    each, carrying the same instructions and thresholds S1 sends, so the two
    readings cannot drift in the shape of what they ask."""
    def one(state):
        label, found, body = state
        return label, found, jev.ask(READER, label, {"body": body},
                                     s1.questions(entry, found), env=env)
    with ThreadPoolExecutor(6) as pool:
        return list(pool.map(one, states))


def main(argv, out=sys.stdout, env=None):
    if argv != ["--staged"]:
        print("Usage: scripts/check-model-comment.py --staged", file=sys.stderr)
        return 2
    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        if READING not in registry:
            print(f"check-model-comment: no entry `{READING}` in the "
                  f"registry; nothing asked", file=out)
            return 0
        entry = registry[READING]
        s1 = load_sibling(S1)
        # `--no-prefix` PINNED, as S1 pins it: a user's `diff.noprefix` changes
        # what `+++` carries, and a parser reading `b/` found no file at all.
        hunks = s1.staged_hunks(s1.git("diff", "--cached", "-U0", "-M",
                                       "--no-color", "--no-ext-diff",
                                       "--no-prefix"))
        staged = [p for p in hunks if SPEC.fullmatch(p)]
        if not staged:
            print(f"check-model-comment: {len(hunks)} staged file(s), none a "
                  f"spec/ module; nothing asked", file=out)
            return 0
        texts = s1.index_texts([p for p in s1.git("ls-files", "-z").split("\0")
                                if SPEC.fullmatch(p)])
        jev = load_sibling("campaign-jev.py")
        states, skipped = [], 0
        for path, name, comment, body, first, last in definitions(texts, s1):
            if not s1.overlaps(hunks.get(path, []), first, last):
                continue
            found, dropped = claims(comment, body, entry["prefilter"], s1)
            for sentence, why in dropped:
                skipped += 1
                jev.skip(READER, f"{path} `{name}`: {sentence}", why, env=env)
            if found:
                states.append((f"{path} `{name}`", found, body))
        print(f"check-model-comment `{READING}`: {len(staged)} staged spec "
              f"file(s) read; {len(states)} definition(s) asked, "
              f"{sum(len(s[1]) for s in states)} claim(s); {skipped} "
              f"sentence(s) settled by code", file=out)
        if states:
            s1.report(ask_all(entry, states, jev, s1, env), entry, out)
    except Exception as e:  # noqa: BLE001 -- a reading never refuses a commit
        print(f"check-model-comment: could not read the commit "
              f"({e.__class__.__name__}: {e}); nothing asked, exit status "
              f"unmoved", file=out)
    return 0


def load_sibling(name):
    """check-cited-claims.py's own loader, by path, so there is one of it."""
    import importlib.machinery
    import importlib.util
    src = HERE / name
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(src)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
