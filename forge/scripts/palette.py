# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Compile legacy base palette literals to live AMOLED/Glass design tokens."""
import re

PALETTE = {
    "canvas": "#10191a #101718 #141b1d #172021 #17251f #17261f",
    "surface": "#192624 #18231e #14211e #18231e #1b3026 #1a2621 #192b24 #14211c #16221d #15211c #1c2627 #15221c #17251f #1c2d25",
    "raised": "#21332d #202d2b #263230 #20332e #1b2a22 #24332a #293d32 #20362a #263e30 #263b30 #1d3026 #263b30 #1a2621 #293630",
    "hover": "#35523f #42664e #2b4936 #365f43 #213027 #294536 #294235 #2b4c39",
    "selected": "#294d3c #294d3c #263f30 #2b4c39 #294d3c #294d3c",
    "line": "#3b5146 #304139 #2c3c34 #2b3b33 #34473b #374a3e #293d30 #3a3a49 #272731 #293630 #344b3b #2c4035 #3b4a41 #45564c #435248",
    "strong": "#4a6755 #4b6654 #52725d #526d5b #6a8c77 #3b5046 #4b7059 #3e5849 #405247 #486851 #4d6d58 #668b72 #486f56 #658571",
    "ink": "#e6f2e9 #e8f2eb #e3eee6 #dce9df #eeeef5 #dce7df #ecf2ed #dbece0 #dff8e9 #f0faf3 #f1faf4",
    "muted": "#a7bcae #b4cbbd #b5c6b8 #bccdc0 #acc0b1 #a4b6a8 #a6cbb5 #b4b4c8 #a0afa8 #b2c9b9 #b4c7b8 #b2d9bf #9cb7a4",
    "dim": "#82988a #8b9f92 #96ab9b #98b2a0 #8fa197 #889991 #95a49d #94a29b #91aa9b",
}
LOOKUP = {value: f"var(--forge-{token})" for token, values in PALETTE.items() for value in values.split()}
COLOR = re.compile(r"#[\da-fA-F]{3,8}\b")


def compile_palette(text):
    lines = []
    for line in text.splitlines(keepends=True):
        # Root fallbacks must remain concrete, not self-referencing variables.
        if re.match(r"\s*--forge-(?:canvas|surface|raised|line|ink|muted)\s*:", line):
            lines.append(line)
        else:
            lines.append(COLOR.sub(lambda match: LOOKUP.get(match.group().lower(), match.group()), line))
    return "".join(lines)
