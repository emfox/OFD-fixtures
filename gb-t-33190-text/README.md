# GB/T 33190-2016 — the standard and its text

The standard's own text: the issued PDF, a Markdown transcription of it, and
the script that makes one from the other.

```
GBT33190-2016.pdf          the standard, as issued
GBT33190-2016.zh_CN.md     a transcription of its text
scripts/pdf_to_markdown.py the transcription, written down
```

## Why here

A Chinese national standard is not open-licensed. The implementation
repository ([SteleOFD](https://github.com/emfox/SteleOFD)) therefore does not
carry the standard's text, nor the script whose only output is that text. Both
live here, where the material that must be pinned but cannot be licensed
already lives.

What does belong in SteleOFD is the part that turns this text into something
the implementation checks itself against: `scripts/gbt33190.py` reads the
clause numbers and the annex A schemas out of this transcription, and
`scripts/check_compliance.py` holds the register it writes to the test suite.
Those read the standard as an input, never redistributing it.

## The PDF

`GBT33190-2016.pdf` — 132 pages, PDF 1.5, 5,068,468 bytes, sha256
`3c6da794cd5d2c33d968668583e5c0c909d1c0c554a2de37fb02788b72471051`.
Unmodified, so its hash is the hash of what was issued.

## The transcription

`GBT33190-2016.zh_CN.md` — UTF-8, 143,765 bytes, sha256
`74bd389082f7c9da2c41a835e0877e9c005d72dddab90d31f662368641f62cca`.
The text in Chinese, as the standard prints it.

What it is held to:

| | |
| --- | --- |
| Numbered headings | 108 of 108, at the numbers the standard prints |
| Tables | 73, each under its caption, each one table even where a page broke it |
| Schema listings | 13, one per schema of annex A, each complete |
| Contents | every entry, with its page |
| Empty blocks | none |

It is not the standard. Paragraphs are joined and the layout is gone; a cell
that holds a list is one cell with the list's lines in it; the schemas' Latin
is set in a face whose space has no width, so their attributes are re-spaced by
rule rather than by measurement. Where the two differ, the PDF governs.

Read the Markdown to find a clause; quote the PDF to say what it says.

## Rebuilding

```bash
pip install pymupdf
python3 scripts/pdf_to_markdown.py GBT33190-2016.pdf \
    --out GBT33190-2016.zh_CN.md
```

The run prints the block count to stderr and writes nothing else. Rebuilding
from the PDF above must reproduce the committed Markdown byte for byte; if it
does not, either the PDF was replaced or the script changed, and the manifest
entry needs to change with it.

## What the script is doing

The PDF is readable only if its layout is read. Three things break a naive
extraction, and the script's own docstring explains each against the PDF:

1. **Heading numbers are overlapping runs.** `8.3.4.3` is four runs whose boxes
   overlap by half a glyph, so sorting by left edge gives `8 3 . . 4 3`. Lines
   are built by baseline instead. `pdftotext -layout` gets this wrong.
2. **Justified lines are stretched by coordinates, not characters.** A line is
   closed up only between two CJK glyphs, where the gap is the producer's; a
   gap between Latin words is a real space and stays.
3. **A table row is set on three baselines.** Any reading that goes by baseline
   loses the row, so tables are rebuilt from the rules the producer draws and
   the text is assigned to the box it falls into.

Two follow from the way the annexes are printed. A schema's annotation that
runs past the margin is broken there and its second line starts back at the
left of the text block, where it reads as prose and would close the listing
(`Res.xsd` and `CustomTags.xsd` both open with one); it is joined back to the
comment it belongs to. And `OFD.xsd` is interrupted by an example of the schema
in use, so its listing is one fence from the declaration to the closing tag
rather than one fence per page of the annex.

Three smaller ones follow from the same cause — a font whose space has no
width. The schemas' attributes come out run together (`elementname="OFD"`) and
are re-spaced by rule; the cover's English title is set as a single run and is
restored from the title itself; abbreviations are one entry to a line and are
recognised by their shape rather than by being short.
