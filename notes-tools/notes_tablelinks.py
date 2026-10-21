#!/usr/bin/env python3
"""Turn bare back-ticked relative paths in the notes' navigation tables into real links.

    | ... | `00-current/现状基线.md` |
 -> | ... | [`00-current/现状基线.md`](00-current/现状基线.md) |

Why: the top-level index lists its targets as plain back-ticked paths, so nothing is
clickable and check_links.py cannot see them (a rename would go unnoticed).

Rules:
  * only convert when the path RESOLVES relative to the file's own directory;
  * never convert paths starting with `../` (references into the sibling app repo stay plain
    text -- the notes repo is meant to be readable on its own);
  * idempotent: a back-ticked path already inside `[...](...)` (i.e. preceded by `[`) is left
    alone.

Usage: notes_tablelinks.py [--dry-run]
"""
import os
import re
import sys

NOTES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # notes/
# a back-ticked *.md/*.txt relative path NOT already inside a link's display text
CELL = re.compile(r"(?<!\[)`([^`\n|]+?\.(?:md|txt))`")


def main():
    dry = "--dry-run" in sys.argv
    total = 0
    touched = []
    for root, _dirs, files in os.walk(NOTES):
        if "/.git" in root:
            continue
        for fn in files:
            if not fn.endswith(".md"):
                continue
            path = os.path.join(root, fn)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            n = [0]

            def repl(m):
                p = m.group(1).strip()
                if p.startswith(("../", "/", "http")):
                    return m.group(0)
                if not os.path.exists(os.path.normpath(os.path.join(root, p))):
                    return m.group(0)
                n[0] += 1
                return "[`" + p + "`](" + p + ")"

            new_text = CELL.sub(repl, text)
            if new_text != text:
                total += n[0]
                touched.append("%s (%d)" % (os.path.relpath(path, NOTES), n[0]))
                if not dry:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(new_text)
    print("paths turned into links: %d, files touched: %d" % (total, len(touched)))
    for t in touched:
        print("  " + t)


if __name__ == "__main__":
    main()
