"""
Analyzes the hierarchical structure of complete_text_data.txt.

The document uses a decimal-section numbering scheme:
  Preamble / Introduction          → special top-level headings
  1.                               → level 1
  1.1.                             → level 2
  1.1.1.                           → level 3
  1.1.1.1.                         → level 4
  ... and so on

This script prints the document's outline and a summary of
how many nodes exist at each depth.
"""

import re
from collections import Counter

FILE = "complete_text_data.txt"
PREVIEW_LEN = 90        # characters of text shown after the section number
SHOW_TABLE_ROWS = False  # set True to include the UN-Regulation table rows


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Matches a decimal section number at the start of a line, e.g.
#   "1."  "2.3."  "2.2.4.1.1."
# Captured groups: the full number string.
SECTION_RE = re.compile(r'^(\d+(?:\.\d+)*\.)\s*(.*)')

# Special headings that are not numbered
SPECIAL_HEADINGS = re.compile(
    r'^(Preamble|Introduction|Annex\s*\d*[A-Za-z]?.*?)(?:\s|$)', re.IGNORECASE
)

# UN-Regulation table header rows (repeated) — skip unless SHOW_TABLE_ROWS
TABLE_RE = re.compile(r'^UN Regulation Title\s+L1')


def count_depth(number_str: str) -> int:
    """Return the depth of a section number like '2.3.1.' → 3."""
    return len(number_str.rstrip('.').split('.'))


def truncate(text: str, length: int) -> str:
    text = text.strip()
    return text[:length] + '…' if len(text) > length else text


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

nodes = []  # list of (depth, label) tuples

with open(FILE, encoding="utf-8") as fh:
    for raw_line in fh:
        line = raw_line.strip()
        if not line:
            continue

        # Skip repeated table-header rows
        if TABLE_RE.match(line) and not SHOW_TABLE_ROWS:
            continue

        # Check for special top-level headings
        m_special = SPECIAL_HEADINGS.match(line)
        if m_special:
            heading = m_special.group(1).strip()
            nodes.append((0, heading))
            continue

        # Check for decimal section numbers
        m_sec = SECTION_RE.match(line)
        if m_sec:
            number = m_sec.group(1)   # e.g. "2.3.1."
            rest   = m_sec.group(2)   # text after the number
            depth  = count_depth(number)
            label  = f"{number} {truncate(rest, PREVIEW_LEN)}"
            nodes.append((depth, label))


# ---------------------------------------------------------------------------
# Print outline
# ---------------------------------------------------------------------------

INDENT = "    "

print("=" * 100)
print("DOCUMENT OUTLINE")
print("=" * 100)

for depth, label in nodes:
    indent = INDENT * depth
    # Use different bullet styles per depth for readability
    bullets = ["◆", "▸", "–", "·", "○", "•"]
    bullet = bullets[min(depth, len(bullets) - 1)]
    print(f"{indent}{bullet} {label}")

# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

depth_counter: Counter = Counter()
for depth, _ in nodes:
    depth_counter[depth] += 1

print()
print("=" * 100)
print("HIERARCHY SUMMARY")
print("=" * 100)
print(f"{'Depth':<10} {'Label':<30} {'Count':>6}")
print("-" * 50)
depth_labels = {
    0: "Special headings (Preamble/Intro/Annex)",
    1: "Level 1  (e.g. 1.)",
    2: "Level 2  (e.g. 1.1.)",
    3: "Level 3  (e.g. 1.1.1.)",
    4: "Level 4  (e.g. 1.1.1.1.)",
    5: "Level 5  (e.g. 1.1.1.1.1.)",
    6: "Level 6+",
}
for d in sorted(depth_counter):
    label = depth_labels.get(d, f"Level {d}")
    print(f"{d:<10} {label:<40} {depth_counter[d]:>6}")

print("-" * 50)
print(f"{'TOTAL':<50} {sum(depth_counter.values()):>6}")
print()
print(f"Maximum nesting depth : {max(depth_counter)}")
print(f"Total outline nodes   : {len(nodes)}")
