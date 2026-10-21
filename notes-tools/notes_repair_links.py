#!/usr/bin/env python3
"""Repair relative markdown links in notes/ by content (not by assumptions).

For every relative link target that does NOT resolve against the file's own directory:
  * look the target's basename up anywhere under notes/
  * exactly one candidate        -> rewrite to the correct relative path
  * several candidates           -> accept only if the NEAREST one is strictly closer than
                                    the runner-up; otherwise report it for manual review

Context: notes_relink.py was (mistakenly) run a second time after the 10-research cleanup,
which re-based every already-rewritten link of the earlier-moved files -> 105 links ended up
one `../` too deep. This pass restores them. (relink now guards: a link that already
resolves is left alone, so it is idempotent.)

Usage: notes_repair_links.py [--dry-run]
"""
import collections
import os
import re
import sys

NOTES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # notes/ (this file lives in notes/notes-tools/)
LINK = re.compile(r"\]\(([^)\s]+?)(#[^)\s]*)??\)")


def main():
    dry = "--dry-run" in sys.argv
    byname = collections.defaultdict(list)
    for root, _dirs, files in os.walk(NOTES):
        if "/.git" in root:
            continue
        for fn in files:
            if fn.endswith((".md", ".txt")):
                byname[fn].append(os.path.join(root, fn))

    fixed = 0
    ambiguous = []
    for root, _dirs, files in os.walk(NOTES):
        if "/.git" in root:
            continue
        for fn in files:
            if not fn.endswith((".md", ".txt")):
                continue
            path = os.path.join(root, fn)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()

            def repl(m):
                nonlocal fixed
                tgt, frag = m.group(1), m.group(2) or ""
                if tgt.startswith(("http://", "https://", "mailto:", "#")):
                    return m.group(0)
                if os.path.exists(os.path.normpath(os.path.join(root, tgt))):
                    return m.group(0)                     # already resolves -> leave alone
                cands = byname.get(os.path.basename(tgt.split("#")[0]), [])
                if len(cands) == 1:
                    fixed += 1
                    return "](" + os.path.relpath(cands[0], root) + frag + ")"
                if len(cands) > 1:
                    rels = sorted(((os.path.relpath(c, root).count(os.sep),
                                    os.path.relpath(c, root)) for c in cands))
                    if rels[0][0] < rels[1][0]:           # nearest is strictly closer
                        fixed += 1
                        return "](" + rels[0][1] + frag + ")"
                    ambiguous.append("%s: %s -> %s"
                                     % (os.path.relpath(path, NOTES), tgt,
                                        [os.path.relpath(c, NOTES) for c in cands]))
                return m.group(0)

            new_text = LINK.sub(repl, text)
            if new_text != text and not dry:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new_text)

    print("repaired: %d   ambiguous (left as-is): %d" % (fixed, len(ambiguous)))
    for a in ambiguous[:20]:
        print("  " + a)


if __name__ == "__main__":
    main()
