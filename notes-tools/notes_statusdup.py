#!/usr/bin/env python3
"""Report "live status" claims that live OUTSIDE their single home.

Design rule (2026-09-15, user-approved):
  * Invariant facts (decided once, rarely change: JRE = OpenJDK 26, single-generation
    LWJGL 3.4.3, naming table, backend choice, the 1.6.x-26.3 support window) MAY be
    restated anywhere -- readers benefit and syncing them is rare.
  * LIVE status (what changes: "verified on device / not yet / pending re-verify / not
    implemented / in progress") has EXACTLY ONE home. Everywhere else it must be a
    pointer, e.g. "status: see 现状基线.md §5 item 17".

Homes allowed to carry live status (whitelist):
  00-current/现状基线.md            <- the authority (§5 numbered key conclusions)
  00-current/项目总览与新人上手.md    <- the newcomer projection (§3), status words + pointers only
  00-current/已知限制与待解.md        <- the open-issues registry (pending/blocked)
  README.md                          <- the minimal projection (<= a few lines)
90-archive/** is exempt (history is allowed to be stale).

Two kinds of lines are skipped, because they cannot rot into a contradiction:
  * self-declared history (当时/历史/曾/旧/已归档/archive/此前), and
  * DATED observations (2026-09-10 实测 ...) -- a record of an event, not a claim about today.

Usage: notes_statusdup.py [--all] [notes_root]
  default: report the "hard" phrases below and exit 1 if any are found outside a home.
  --all:   also report the softer planning words (待办/在办/下一步/验证计划/计划...).
"""
import os
import re
import sys

HOMES = (
    "00-current/现状基线.md",
    "00-current/项目总览与新人上手.md",
    "00-current/已知限制与待解.md",
    "README.md",
)

HARD = re.compile(
    r"已实机验证|已实机跑通|已实机|实机验证通过|实机通过|实机可玩|实机正常|"
    r"实机未验证|未实机验证|未实机|未验证|待复验|待实机复验|待实机|待提交|"
    r"尚未实现|未实现|已提交并|已提交（"
)
SOFT = re.compile(r"待办|在办|下一步候选|规划中|尚未|计划中|验证计划")

HISTORICAL = re.compile(r"当时|历史|曾|旧|已归档|archive|此前")
# A DATED observation is a record of an event ("2026-09-10 实测 1.21.10 可玩") and can never
# turn into a contradiction, so it is allowed outside a home. An UNDATED claim ("已实机验证")
# asserts something about the present and must live in a home (or become a pointer).
DATED = re.compile(r"20\d\d-\d\d(-\d\d)?")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    root = args[0] if args else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.abspath(root)

    pat = (HARD, SOFT) if show_all else (HARD,)
    hits = 0
    files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel_dir.startswith("90-archive") or "/90-archive" in rel_dir:
            continue
        for fn in sorted(filenames):
            if not fn.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
            if rel in HOMES:
                continue
            with open(os.path.join(dirpath, fn), encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            found = []
            for i, line in enumerate(lines, 1):
                if HISTORICAL.search(line) or DATED.search(line):
                    continue
                for p in pat:
                    for m in p.finditer(line):
                        found.append((i, m.group(0)))
            if found:
                files += 1
                hits += len(found)
                print("== " + rel)
                for i, tok in found:
                    print("  :%-5d %s" % (i, tok))
    print("\nlive-status claims outside their home: %d (in %d files)" % (hits, files))
    print("homes: " + ", ".join(HOMES))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
