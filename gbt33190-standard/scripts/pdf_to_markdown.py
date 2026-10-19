#!/usr/bin/env python3
"""Transcribe GB/T 33190-2016 into Markdown, from the text the PDF carries.

It lives beside the PDF and the Markdown it makes, in `emfox/OFD-fixtures`:
a Chinese national standard is not open-licensed, so neither the standard nor
anything derived from it belongs in the implementation repository. This script
is kept here so the transcription can be rebuilt and reviewed from the PDF
next to it, and so that what was done to the text can be read.

Reading order is the problem, and it is not the order the PDF stores.

**A number is one row.** `8.3.4.3` is printed as four runs whose boxes overlap
by about half a glyph, so sorting runs by left edge yields `8 3 . . 4 3`. They
share a baseline with everything else on the visible line, so a line is built
by baseline and its runs joined in that order, overlap and all. `pdftotext
-layout` cannot do this: it reads the overlapping runs as separate columns and
sets them on separate lines, which is why the heading numbers come out as
`8.`, `3.`, `8.4.` stacked.

**A justified line is shorter than it looks.** The producer stretches the
last line of a paragraph to the full measure by widening the gaps between
glyphs rather than between words. The extra distance lives in the coordinates,
not in the characters, so it is removed by looking at the layout: a line is
closed up when the next one sits closer than the leading, and only between two
CJK glyphs, since a gap between Latin words is a real space.

Tables are not read from the text either. The cells of one table row are
typeset on three different baselines, so any reading that goes by baseline
loses the row; but the rules the producer draws are exact to a tenth of a
point, so a table is rebuilt from its rules and the text is assigned to the
box it falls in.

Usage:
    python3 scripts/pdf_to_markdown.py GBT33190-2016.pdf \
        --out GBT33190-2016.zh_CN.md [--pages 6:132]

Written against PyMuPDF: `pip install pymupdf`.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import fitz

# The running head, and the folio in either numbering.
HEADER = re.compile(r"^GB/T\s*33190\s*[—–-]\s*2016$")
# A line that opens in Chinese: the tail of a comment the margin broke, or a
# heading, which is told apart by whether a listing is open.
CJK_LEAD = re.compile(r"^[\u4e00-\u9fff]")
ROMAN = re.compile(r"^[IVXLC\u2160-\u217f]+$")
# Where the text column starts and ends.
COLUMN_LEFT, COLUMN_RIGHT = 60.0, 536.0
# The bands the running head and the folio sit in; nothing else is set there.
HEAD_BAND, FOOT_BAND = 78.0, 752.0
# Runs whose baselines are closer than this are one visible line.
BASELINE = 8.0
# Runs that start closer than this to where the last one ended overlap it.
PART = 1.0
# Body leading is 15.7pt; a paragraph's last line is set at 14.2 to 14.3, and
# the next paragraph's first line follows at 17 or 18. A line closer to the
# next one than LEADING was stretched to justify and carries gaps that are not
# in its text.
LEADING = 15.0
# A gap this much larger than the leading is the space between paragraphs.
PARAGRAPH = 17.0
# Body text is set at the second edge; an entry of the contents, of the
# bibliography or of a schema listing starts at the first and wraps back to it.
MARGIN = 75.0
# A wrapped line that hangs back further left than the body's own edge.
HANGING = 78.0
# Text that ends in one of these has finished what it was saying.
ENDINGS = ("\u3002", "\uff1a", ":", "\uff1b", ";", "\uff1f", "?", "\uff01", "!", ".", ")", "]", ">")
# Two rules closer than this are the two strokes of one thicker rule.
RULE = 0.6
# The heading face. Body text is set in FZSSK, table cells in E-BZ and E-BKB.
HEADING_FACE = "FZHTK--GBK1-0"
# A grid needs this many of each before it is table rather than a box.
MIN_ROWS, MIN_COLUMNS = 2, 2
# Two bars belong to one table when at least three posts run between them:
# the two sides of the box and one column divider. Where there are none the
# bars close one table and open the next.
DIVIDER = 3
# Where a schema listing wraps: the listing is indented to 67.5 and a full
# line reaches 65, so a line that starts left of 66 is a continuation.
COLUMN_INDENT = 66.0

CJK = "\u3000-\u303f\u4e00-\u9fff\uff00-\uffef\u2014\u2018\u2019\u201c\u201d\u2026"
CLAUSE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\s+(\S.*)$")
# `\u9644 \u5f55 A`, `\u9644\u5f55 A` or `\u9644\u5f55A`: the heading spaces
# the glyphs unevenly.
ANNEX = re.compile(r"^\u9644\s*\u5f55\s*([A-Z])$")
# `(\u89c4\u8303\u6027\u9644\u5f55)` under the letter, the annes title under that.
QUALIFIER = re.compile(
    r"^[(\uff08](?:\u89c4\u8303\u6027|\u8d44\u6599\u6027|\u53c2\u8003)"
    r"\u9644\u5f55[)\uff09]$"
)
ANNEX_CLAUSE = re.compile(r"^([A-Z])\.(\d{1,2})\s+(\S.*)$")
# The annexes list their schemas, and each list opens with the name of the
# file it contains, set in the body face rather than the heading one.
SCHEMA = re.compile(r"^([A-Z])\.(\d{1,2})\s+(\S+\.xsd)$")
# An entry of the contents: a clause title, a leader of dots, and a page.
# One dot character is a leader too: the front matter's page is a single
# roman numeral, and the contents set the leaders short for it.
# The front matter is paginated in the roman numerals of the fonts that set
# them, U+2160 to U+217F, rather than in the letters I, V, X, L and C.
CONTENTS = re.compile(r"^(.*?)\s*(?:…+|\.{3,})\s*(\d{1,3}|[IVXLC\u2160-\u217f]{1,4})$")
# The line that closes a schema listing, which is what comes before its name.
SCHEMA_END = re.compile(r"^</xs:schema>$")
# A figure or table number, set apart from its title: `\u8868 30 \u5f84\u5411\u6e10\u53d8\u5c5e\u6027`.
# The standard also writes `\u56fe 34 \u6240\u793a\u662f...` in running text, which is a
# sentence about the figure, not its caption, so the number must be spaced.
# The one caption with no title is the continuation of a table overleaf:
# `\u88681(\u7eed)`.
CAPTION = re.compile(
    r"^(?:\u8868|\u56fe) ?\d+ (?:[^\d\s]|[(\uff08]\u7eed[)\uff09])"
    r"|^\u8868 ?\d+ ?[(\uff08]\u7eed[)\uff09]$"
)
# `\u76ee \u6b21` and `\u524d \u8a00`, titled with their glyphs spaced out.
FRONT = re.compile(r"^([\u4e00-\u9fff]) ?([\u4e00-\u9fff])(?: ?([\u4e00-\u9fff]))?(?: ?([\u4e00-\u9fff]))?$")
FRONT_TITLES = ("\u76ee\u6b21", "\u524d\u8a00", "\u53c2\u8003\u6587\u732e")
# A term's number is set on a line of its own above the term, at the left
# edge: `3.1` then `\u7248\u5f0f fixed layout`. A heading in all but name.
TERM = re.compile(r"^\d{1,2}\.\d{1,2}$")


@dataclass
class Row:
    """One visible line of text."""

    y: float
    x: float
    text: str
    heading: bool
    runs: list[tuple[float, float, str]] = field(default_factory=list)


@dataclass
class Rule:
    """One rule of a table."""

    y: float
    x: float
    x1: float
    down: float
    horizontal: bool


def page_rows(page: fitz.Page) -> list[Row]:
    """The page as visible lines, top to bottom.

    Runs are grouped by baseline, not by the producer's idea of a line: it
    starts a new block whenever the face changes, and a heading number
    changes face up to seven times.
    """
    runs: list[tuple[float, float, float, str, bool]] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"])
            if not text.strip():
                continue
            x0, y0, x1, _y1 = line["bbox"]
            face = any(span["font"] == HEADING_FACE for span in line["spans"])
            runs.append((y0, x0, x1, text, face))
    runs.sort(key=lambda run: (run[0], run[1]))

    rows: list[Row] = []
    for y0, x0, x1, text, face in runs:
        if rows and abs(rows[-1].y - y0) < BASELINE:
            rows[-1].runs.append((x0, x1, text))
            rows[-1].heading = rows[-1].heading or face
            rows[-1].x = min(rows[-1].x, x0)
            continue
        rows.append(Row(y0, x0, "", face, [(x0, x1, text)]))

    for row in rows:
        row.runs.sort()
        row.text = spread(row.runs)
    return [row for row in rows if row.text]


def spread(runs: list[tuple[float, float, str]]) -> str:
    """One line's text, from its `(x0, x1, text)` runs.

    A run that begins before the last one ended is the overlap of a number's
    components and is joined without a gap; a real gap becomes a space.
    """
    text, right = "", None
    for x0, x1, run in runs:
        if right is not None and x0 - right > PART:
            text += " "
        text += run
        right = x1 if right is None else max(right, x1)
    return re.sub(r"[ \t]+", " ", text).strip()


def strokes_of(page: fitz.Page) -> list[Rule]:
    """The rules the producer draws, each as its own stroke."""
    drawn: list[Rule] = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.height < RULE and rect.width > 2 * RULE:
            drawn.append(Rule(rect.y0, rect.x0, rect.x1, 0.0, True))
        elif rect.width < RULE and rect.height > 2 * RULE:
            drawn.append(Rule(rect.y0, rect.x0, rect.x0, rect.y1, False))
    return drawn


def rules_of(page: fitz.Page) -> list[Rule]:
    """The rules the producer draws, as whole table edges.

    A rule of more than hairline weight is drawn as two or three coincident
    ones, and the posts of a table are drawn cell by cell: the post between
    two columns of a row is one stroke per row, not one per table. Both are
    folded here, which is right for reading the grid and wrong for telling
    where one table ends -- see `frames_of`.
    """
    kept: list[Rule] = []
    for rule in strokes_of(page):
        twin = next(
            (
                other
                for other in kept
                if other.horizontal == rule.horizontal
                and (
                    abs(other.y - rule.y) < RULE
                    if rule.horizontal
                    else abs(other.x - rule.x) < RULE
                    and other.down + RULE > rule.y
                    and rule.down + RULE > other.y
                )
            ),
            None,
        )
        if twin is None:
            kept.append(rule)
            continue
        twin.x1 = max(twin.x1, rule.x1)
        twin.down = max(twin.down, rule.down)
    return kept


def frames_of(page: fitz.Page) -> list[tuple[list[float], list[float]]]:
    """The `(rule tops, rule lefts)` of every table on the page, top first.

    A page carries two tables as often as one -- one continuing from the page
    before, a new one below it -- and nothing about the rules says which is
    which: the posts of a continuing table are drawn down the whole page, and
    the posts of the next table start below the prose that separates them.

    What separates them is that the prose has no post running through it, and
    for that the strokes are used as drawn rather than folded: a post is one
    stroke per row, so a folded post would reach down the page and through
    the prose as well. A cell holding a list is 117pt tall, so height alone
    says nothing; a band with no post through it holds the prose between two
    tables. A grid with too few columns is a frame around a figure.
    """
    rules = rules_of(page)
    bars = sorted((rule for rule in rules if rule.horizontal), key=lambda rule: rule.y)
    posts = [rule for rule in rules if not rule.horizontal]
    strokes = [rule for rule in strokes_of(page) if not rule.horizontal]
    if len(bars) < MIN_ROWS + 1:
        return []

    runs: list[list[Rule]] = [[bars[0]]]
    for above, below in zip(bars, bars[1:]):
        if not any(crosses_band(stroke, above, below) for stroke in strokes):
            runs.append([])
        runs[-1].append(below)

    out: list[tuple[list[float], list[float]]] = []
    for run in runs:
        tops = sorted({round(bar.y, 1) for bar in run})
        if len(tops) < MIN_ROWS + 1:
            continue
        # A post runs from the first bar of the table to the last. The two
        # tables on a page share their box posts, so the test is coverage and
        # not exact height.
        lefts = sorted({
            round(post.x, 1)
            for post in posts
            if post.y - RULE <= tops[0] + 1.0 and post.down + RULE >= tops[-1] - 1.0
        })
        if len(lefts) < MIN_COLUMNS + 1:
            continue
        out.append((tops, lefts))
    return out


def crosses_band(stroke: Rule, above: Rule, below: Rule) -> bool:
    """Whether a post, as drawn, runs through the band between two bars."""
    return (
        above.x - RULE <= stroke.x <= above.x1 + RULE
        and stroke.y - RULE <= above.y + RULE
        and stroke.down + RULE >= below.y - RULE
    )


def is_inside(row: Row, frames: list[tuple[list[float], list[float]]]) -> bool:
    """Whether a line falls inside one of the page's tables."""
    return any(tops[0] - 12.0 <= row.y <= tops[-1] + 4.0 for tops, _lefts in frames)


def caption_index(rows: list[Row], top: float) -> int | None:
    """The row that captions the table whose first rule is `top`.

    The caption is the last line above the table and close to it -- above,
    because the caption of a table always comes first, and close, because a
    page can carry a figure's caption higher up that belongs to the figure.
    """
    best = None
    for index, row in enumerate(rows):
        if top - 60 < row.y < top and CAPTION.match(row.text):
            best = index
    return best


def cells_of(page: fitz.Page, tops: list[float], lefts: list[float]) -> list[list[str]]:
    """The table's cells, row by row, from the text that falls inside them.

    A cell holds several lines as often as one -- a list of allowed values, a
    sentence that wraps -- so the lines are gathered in the order the page
    sets them and joined into the cell's text.
    """
    grid: list[list[list[tuple[float, float, str]]]] = [
        [[] for _ in range(len(lefts) - 1)] for _ in range(len(tops) - 1)
    ]
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text:
                continue
            x0, y0, x1, y1 = line["bbox"]
            column = gap_index((x0 + x1) / 2, lefts)
            row = gap_index((y0 + y1) / 2, tops)
            if column is None or row is None:
                continue
            grid[row][column].append((y0, x0, text))

    out: list[list[str]] = []
    for cell_row in grid:
        cells = [
            tidy(" ".join(text for _y, _x, text in sorted(cell, key=lambda line: (line[0], line[1]))))
            for cell in cell_row
        ]
        if any(cells):
            out.append(cells)
    return out


def gap_index(value: float, edges: list[float]) -> int | None:
    """Which gap of `edges` the value falls in.

    The edges are the rules as drawn, and a line of a cell can overlap the
    rule above it by a fraction of a point -- a cell set tight against its
    border -- so the gap is taken to be closed at both ends rather than half
    open, and a value within a point of an edge is taken to be inside the
    gap it is nearest to.
    """
    best, distance = None, float("inf")
    for index in range(len(edges) - 1):
        low, high = edges[index], edges[index + 1]
        if low - 1.0 <= value <= high + 1.0:
            middle = (low + high) / 2
            if abs(value - middle) < distance:
                best, distance = index, abs(value - middle)
    return best


def append_rows(blocks: list[str], index: int, rows: list[list[str]]) -> None:
    """Add the rows of a continuation to the table at `index`.

    The continuation repeats the header of its table, so the header is
    dropped from the rows being added and the table's own header is kept. A
    row repeated verbatim is dropped too: no table in the standard repeats a
    row, and the two pages of a table share a line now and then.
    """
    lines = blocks[index].splitlines()
    present = set(lines[2:])
    blocks[index] = "\n".join(
        lines + [line for line in markdown_table(rows)[2:] if line not in present]
    )


def append_to_table(blocks: list[str], number: str, rows: list[list[str]]) -> bool:
    """Fold a continuation into the table it continues.

    The table being continued is the last one above whose caption carries
    this number. Its caption is the title of the table, the continuation's
    is the number and the marker, so the number is matched with whatever
    space the caption put after it.
    """
    for index in range(len(blocks) - 1, 0, -1):
        if not blocks[index].startswith("| "):
            continue
        if re.match(rf"^\*\*\u8868 ?{number[1:]} ", blocks[index - 1]):
            append_rows(blocks, index, rows)
            return True
    return False


def continued(caption: str) -> str:
    """The number of the table a continuation caption continues.

    A table that runs past the foot of a page is printed again at the top of
    the next with its number and the marker; the rows belong to the table, not to
    a second table of the same number, so the continuation is folded back
    into it.
    """
    match = re.match(r"^(\u8868 ?\d+) ?[(\uff08]\u7eed[)\uff09]$", caption)
    return match.group(1).replace(" ", "") if match else ""


def markdown_table(rows: list[list[str]]) -> list[str]:
    """A GFM table, its first row taken as the header."""
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    out = ["| " + " | ".join(cell.replace("|", "\\|") or " " for cell in padded[0]) + " |"]
    out.append("|" + "|".join(["---"] * width) + "|")
    for row in padded[1:]:
        out.append("| " + " | ".join(cell.replace("|", "\\|") or " " for cell in row) + " |")
    return out


def close_up(text: str) -> str:
    """Squeeze out the gaps a justified line was stretched with.

    Only the gaps between two CJK glyphs are stretched: `GB 13000` and
    a CJK word and a Latin one are spaced because a Latin word follows it,
    and closing those would run the words together. The same holds between a
    CJK glyph and the punctuation that follows it, which the standard sets
    with no gap at all.
    """
    text = re.sub(f"(?<=[{CJK}]) +(?=[{CJK}])", "", text)
    text = re.sub(f"(?<=[{CJK}]) +(?=[\uff0c\u3002\u3001\uff1b\uff1a\uff1f\uff01\uff09\u3011\u300b])", "", text)
    return text.strip()


def tidy(text: str) -> str:
    """One line of the standard, as it reads."""
    return set_off(close_up(text))


def set_off(text: str) -> str:
    """Space a Latin word away from the CJK glyph it was run into.

    The producer omits the gap between a CJK glyph and a Latin word wherever
    the face changes, so `graphicunit` and `OpenFixedlayoutDocument` come out
    of the PDF with no word break at all. The gap is restored here, because
    it is the only place it can be: the characters carry no trace of it.
    Latin text that does have its gaps is left exactly as it is.
    """
    text = re.sub(f"(?<=[a-z0-9])(?=[{CJK}])", " ", text)
    # A gap after a full stop is not restored: `PageRes.xml` and `7.3` are
    # one token each, and the full stop there is part of it.
    return re.sub(f"(?<=[{CJK}])(?=[A-Za-z])", " ", text)


# The attributes of the schemas, and the words that precede them. The listing
# sets its Latin in E-BKB, whose space has no width: `element name="OFD"`
# comes out of the PDF as `elementname="OFD"`. The gap is restored here,
# where the word before the attribute is known.
SCHEMA_ATTRIBUTES = (
    "schemaLocation", "targetNamespace", "elementFormDefault",
    "attributeFormDefault", "minOccurs", "maxOccurs", "use", "default",
    "xmlns",
    "base", "name", "type", "value", "version", "encoding", "ref", "fixed",
)
SCHEMA_OWNERS = (
    "element", "attribute", "complexType", "simpleType", "restriction",
    "extension", "enumeration", "include", "xml", "xs", "schema",
    "choice", "sequence", "all", "group", "any", "annotation",
)


def unmangle(text: str) -> str:
    """Put back the spaces the schema listing did not set.

    Only the gaps before an attribute are restored, and only where the word
    that precedes it is one the schemas use: an attribute value sits inside
    quotes and is left alone, and so is every other token of the listing.
    """
    owners = "|".join(SCHEMA_OWNERS)
    attributes = "|".join(SCHEMA_ATTRIBUTES)
    text = re.sub(rf"(\b(?:{owners}))({attributes})=", r"\1 \2=", text)
    # An attribute that follows a quoted value begins a new one: nothing in
    # a listing puts a letter directly after a closing quote.
    text = re.sub(r'"(?=(?:[a-zA-Z]+:)?[a-zA-Z]+=)', '" ', text)
    # A comment is set with its marks apart from the text inside it.
    text = re.sub(r"<! ?--(?=\S)", "<! --", text)
    # The declaration that opens a schema names two attributes of `xml`.
    text = re.sub(r"^<(\?) ?xml ?(version|encoding)=", r"<?xml \2=", text)
    return text


def is_schema_line(text: str) -> bool:
    """Whether a line can be part of a schema listing.

    The annexes print their schemas as listings, one element or attribute to
    a line, and wrap a long one at the margin. The spacing between words is
    missing throughout -- `attribute` and `name` run together -- so the line
    is kept exactly as the standard sets it rather than repaired into
    something it says nowhere.

    An annotation that runs past the margin is broken there, and the rest of
    it starts at the left of the text block as prose, not as a tag: of the
    schemas in annex A, `Res.xsd` and `CustomTags.xsd` both open with one.
    Such a line continues the comment, and the caller joins it while a listing
    is open rather than letting it close the listing, which would leave the
    rest of the schema outside a fence. A Chinese line is not a listing line
    on its own, so a heading of the standard is still read as a heading.
    """
    return bool(re.match(r"^[\w:./!?<-]", text)) and "<" in text or text.startswith(("xmlns", "target"))


def continues_comment(line: str) -> bool:
    """Whether a line of Chinese continues the annotation the line above opened.

    The annotation is broken at the margin, so its second line carries no
    mark of its own: what tells it apart from a heading that follows the
    schema is the first line, which ends inside the comment rather than
    after it.
    """
    return bool(re.search(r"<! ?--", line)) and "-->" not in line


def is_cover(page: fitz.Page) -> bool:
    """Whether the page is the title page.

    The title page is the one that carries no running head: every other page
    of the standard has `GB/T 33190-2016` set across its top.
    """
    return not any(
        HEADER.match(row.text) for row in page_rows(page) if row.y < HEAD_BAND
    )


# The English title of the cover. The cover sets its Latin in one run with
# the word spaces left out of the characters -- the gaps between the words
# were drawn, not typed -- so the words are restored from the title itself,
# which is printed on the cover of the standard and cited by it.
ENGLISH_TITLE = (
    "Electronic files storage and exchange formats"
    "—Fixed layout documents"
)


def cover(page: fitz.Page) -> str:
    """The title page read as its lines, hardest first."""
    lines = []
    for row in page_rows(page):
        if abs(row.y - 61.0) <= 1.0:
            continue
        text = row.text
        if text.replace(" ", "") == ENGLISH_TITLE.replace(" ", ""):
            text = ENGLISH_TITLE
        lines.append(text)
    return "\n\n".join(lines)


def is_text(row: Row) -> bool:
    """Whether a line is text of the document rather than furniture."""
    if row.y < HEAD_BAND or row.y > FOOT_BAND:
        return False
    if HEADER.match(row.text):
        return False
    if TERM.match(row.text):
        return True
    return not (re.fullmatch(r"\d{1,3}", row.text) or ROMAN.match(row.text))


def level_of(number: str) -> int:
    """The heading level a clause number is written at."""
    return min(6, number.count(".") + 2)


def transcribe(pdf: Path, first: int, last: int) -> list[str]:
    """The document as a list of Markdown blocks."""
    doc = fitz.open(pdf)
    blocks: list[str] = []
    emit = Emitter(blocks)
    for number in range(first, last + 1):
        page = doc[number - 1]
        if is_cover(page):
            emit.block(cover(page))
            continue
        rows = [row for row in page_rows(page) if is_text(row)]
        place(page, rows, frames_of(page), emit)
    emit.done()
    return blocks


def place(page: fitz.Page, rows: list[Row], frames: list[tuple[list[float], list[float]]],
          emit: Emitter) -> None:
    """Read one page in the order it is printed, tables and all.

    A table sits between two lines of prose, and both its caption and the
    text under it decide where its block goes, so the page is not read as
    "prose first, then the tables": the lines and the tables are merged on
    the vertical axis and read top to bottom. A table takes the place of its
    caption, which has already been read as the line that introduces it.
    """
    inside = {id(row) for row in rows if is_inside(row, frames)}
    marks: list[tuple[float, str, object]] = [
        (row.y, "row", row) for row in rows if id(row) not in inside
    ]
    for tops, lefts in frames:
        marks.append((caption_top(rows, tops[0]), "table", (tops, lefts)))
    marks.sort(key=lambda mark: mark[0])
    for _y, kind, item in marks:
        if kind == "row":
            emit.row(item)  # type: ignore[arg-type]
            continue
        tops, lefts = item  # type: ignore[misc]
        table = cells_of(page, tops, lefts)
        caption = caption_index(rows, tops[0])
        if caption is not None and continued(rows[caption].text):
            # A continuation repeats the header of the table above it; its
            # rows are added to that table instead, and the caption of the
            # continuation is dropped with the page break it describes.
            emit.drop()
            if append_to_table(emit.blocks, continued(rows[caption].text), table):
                continue
        emit.block("\n".join(markdown_table(table)))


def caption_top(rows: list[Row], top: float) -> float:
    """Where the block of the table whose first rule is `top` is read in.

    A table is printed under its caption, so the caption comes first and the
    table's rows after it: the mark sits a hair below the caption's baseline
    so that the two sort in the order they are printed. A table with no
    caption on the page is the tail of the one overleaf and goes where the
    page opens.
    """
    index = caption_index(rows, top)
    return (rows[index].y + 0.5) if index is not None else (top - 1000.0)


class Emitter:
    """Turns rows into blocks, tracking the paragraph being built.

    A paragraph is a run of wrapped lines: it ends where the line above was
    stretched to the measure, where that line ended in a full stop or a
    colon, and where a heading, a caption or a table interrupts.

    Two things are folded into the block they belong to rather than emitted
    on their own. A term's number (`3.1`) is set on the line above the term
    it numbers, so it is joined to the term. A line that is set in the
    heading face but opens no clause is a line of schema or a stretch of
    Latin, and is prose like any other.
    """

    def __init__(self, blocks: list[str]) -> None:
        self.blocks = blocks
        self.prose: list[str] = []
        # The last line added to the paragraph, and whether it was a line the
        # producer had stretched to the measure.
        self.last: Row | None = None
        self.stretched = False
        # The term number waiting for its term.
        self.term = ""
        # Whether the last line closed a schema listing, and whether the
        # annex holding the schemas has just been announced.
        self.closed_schema = False
        self.in_annex = False
        # The letter of the annex being read, and whether its qualifier line
        # has been taken into the heading.
        self.annex = ""
        self.qualifier = False
        # The lines of the schema listing being read.
        self.schema_lines: list[str] = []

    def row(self, row: Row) -> None:
        """Add one line of the document."""
        text = row.text
        # A listing wraps a long element at the margin, and the wrapped part
        # starts back at the left of the text block. It is the rest of the
        # line above it -- `minOccurs="0"/>` and `fixed="1.0"/>` close the
        # element the line before opened -- so it is joined on.
        if self.schema_lines and row.x < COLUMN_INDENT:
            self.schema_lines[-1] = unmangle(self.schema_lines[-1] + text)
            self.closed_schema = bool(SCHEMA_END.match(text))
            return
        if is_schema_line(text):
            self.schema_lines.append(unmangle(text))
            self.closed_schema = bool(SCHEMA_END.match(text))
            return
        # An annotation that runs past the margin is broken there, and the
        # rest of it starts at the left of the text block as prose. It is
        # still the comment -- `Res.xsd` and `CustomTags.xsd` each open with
        # one -- so it goes back inside the listing rather than closing it.
        # A heading the standard prints after a schema opens in Chinese too,
        # and is told apart by the comment above it: a heading never follows
        # a line that is still inside one.
        if self.schema_lines and CJK_LEAD.match(text) and continues_comment(self.schema_lines[-1]):
            self.schema_lines[-1] = unmangle(self.schema_lines[-1] + text)
            self.closed_schema = bool(SCHEMA_END.match(text))
            return
        # Anything that is not a line of a listing closes the listing.
        self.close_listing()
        if TERM.match(text):
            # The number arrives on a line of its own, and the definition
            # before it has finished by then even when the line above it was
            # cut off mid-clause -- which is what a hanging indent means.
            self.flush()
            self.term = text
            return
        # The letter of an annex is followed by how it is to be read and by
        # the annex's own title, one under the other; they are one heading.
        if self.annex and (
            QUALIFIER.match(text) or (self.qualifier and not row.heading)
        ):
            if QUALIFIER.match(text):
                self.qualifier = True
                self.blocks[-1] += "\uff08" + text.strip("()\uff08\uff09") + "\uff09"
            else:
                self.blocks[-1] += f" {tidy(text)}"
                self.annex = ""
                self.qualifier = False
            return
        # A heading, a caption and a schema's name open a block of their own,
        # whatever came before them: they follow a table as often as they
        # follow prose, and the short line a table ends with would otherwise
        # take the heading in as the rest of its sentence.
        opened = self.heading(row) or self.schema(row) or self.contents(row)
        if opened is not None:
            self.block(opened)
            return
        if CAPTION.match(text):
            self.block(f"**{tidy(text)}**")
            return
        if self.prose and not self.carries_on(row):
            self.flush()
        text = f"{self.term} {text}" if self.term else text
        self.term = ""
        self.stretched = self.last is not None and row.y - self.last.y < LEADING
        self.prose.append(text)
        self.last = row

    def carries_on(self, row: Row) -> bool:
        """Whether the row continues the paragraph the last line belongs to.

        A stretched line is by definition followed by more of its paragraph,
        and a line whose last word is cut in two by the margin is too. What
        is neither is an entry that ended by itself: the abbreviations are a
        list of them, one to a line, each closing on its own bracket, and a
        short line there is a finished line and not a stretched one.
        """
        if self.last is None:
            return False
        if re.match(r"^[A-Z]{2,8}:", row.text):
            return False
        if self.stretched or re.match(r"^[a-z]{1,12}$", self.last.text.split()[-1]):
            return True
        return not self.last.text.endswith(ENDINGS)

    def heading(self, row: Row) -> str | None:
        """The block a row opens, or `None` when it opens nothing."""
        text = row.text
        if FRONT.match(text) and text.replace(" ", "") in FRONT_TITLES:
            # The spacing is the heading's own: the standard titles these two
            # with their glyphs set apart, and closing them up loses that.
            return f"## {text}"
        annex = ANNEX.match(text)
        if annex:
            self.in_annex = True
            self.annex = annex.group(1)
            return f"# \u9644\u5f55{annex.group(1)}"
        if not row.heading:
            return None
        match = CLAUSE.match(text)
        if match:
            number, title = match.group(1), tidy(match.group(2))
            return f"{'#' * level_of(number)} {number} {title}"
        match = ANNEX_CLAUSE.match(text)
        if match:
            number = f"{match.group(1)}.{match.group(2)}"
            return f"{'#' * level_of(number)} {number} {tidy(match.group(3))}"
        return None

    def contents(self, row: Row) -> str | None:
        """A list entry of the contents, printed as a line of its own.

        The contents set each entry as a title, a leader of dots and a page
        number. The dots are the layout's, not the text's, so they are
        dropped and the page number is kept with the title.
        """
        match = CONTENTS.match(row.text)
        # The pages of the contents are set at the margin; prose that runs to
        # the margin is prose, and a leader of dots is what tells them apart.
        if match is None or not match.group(1).strip():
            return None
        title = tidy(match.group(1))
        page = match.group(2)
        # The front matter is numbered in roman, and has no clause number.
        number = re.match(r"^(\d+(?:\.\d+)*)\s+(.*)$", title)
        if number:
            return f"- {number.group(1)} {number.group(2)} {page}"
        return f"- {title} {page}"

    def schema(self, row: Row) -> str | None:
        """The block a schema name opens, when it follows its listing.

        The name of a schema is set like a line of the listing, so it is
        recognised by where it sits rather than by its face: directly under
        the line that closed the schema before it, or at the top of the annex
        that holds the first one. A line inside a listing that happens to
        name a file has `xs:element` before it, not a closing tag.
        """
        match = SCHEMA.match(row.text)
        if match is None:
            return None
        number = f"{match.group(1)}.{match.group(2)}"
        return f"{'#' * level_of(number)} {number} {match.group(3)}"

    def block(self, text: str) -> None:
        """Close the open paragraph and append a block of its own."""
        self.flush()
        # A listing interrupted before its closing tag -- the annex prints an
        # example between the two halves of `OFD.xsd` -- carries on in the
        # block that follows rather than opening a second fence with no
        # declaration of its own. Closing the fence there would split one
        # schema into two listings, the second of which looks like an example.
        if text.startswith("```xml") and self.blocks and self.blocks[-1].startswith("```xml"):
            if not SCHEMA_END.match(self.blocks[-1].rsplit("\n", 1)[-1].strip()):
                self.blocks[-1] = self.blocks[-1] + "\n" + text.removeprefix("```xml\n").rstrip("`\n")
                return
        self.blocks.append(text)

    def drop(self) -> None:
        """Take back the block just added, if it is a continuation's caption."""
        if self.blocks and re.fullmatch(
            r"\*\*\u8868 ?\d+\(\u7eed\)\*\*", self.blocks[-1]
        ):
            self.blocks.pop()

    def close_listing(self) -> None:
        """Close the schema listing being read, if one is open."""
        if self.schema_lines:
            self.blocks.append("```xml\n" + "\n".join(self.schema_lines) + "\n```")
            self.schema_lines.clear()

    def flush(self) -> None:
        """Close the open paragraph, if one is open.

        The schema listing is not closed here: a paragraph is opened and
        closed around nothing inside a listing, and closing the listing with
        it would cut the schema into blocks of a line or two.
        """
        if self.prose:
            self.blocks.append(tidy("".join(self.prose)))
            self.prose.clear()
        self.last = None
        self.stretched = False
        self.term = ""

    def done(self) -> None:
        self.flush()


def gather(blocks: list[str]) -> list[str]:
    """Join the entries of a list into one block.

    Each entry of the contents is a block of its own -- it is set as a line of
    its own and read as one -- but Markdown starts a new list after a blank
    line, so a run of entries is joined into a single list.
    """
    out: list[str] = []
    for block in blocks:
        if out and block.startswith("- ") and out[-1].splitlines()[-1].startswith("- "):
            out[-1] += "\n" + block
            continue
        out.append(block)
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pages", default="1:132", help="1-based, inclusive")
    options = parser.parse_args(argv)
    first, _, last = options.pages.partition(":")
    blocks = transcribe(options.pdf, int(first), int(last or first))
    options.out.write_text("\n\n".join(gather(blocks)) + "\n", encoding="utf-8")
    print(f"{options.out}: {len(blocks)} blocks", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
