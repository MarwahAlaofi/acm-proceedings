"""Generate a formatted Word document of ICTIR referees from an Excel source.

Reads two sheets from ``ictir_referees.xlsx``:
    - ``ICTIR - SPC``: Senior Program Committee members
    - ``ICTIR - PC``:  Program Committee members

Each sheet has columns: ``first name``, ``middle name``, ``last name``,
``affiliation``. The script writes a ``.docx`` file where:
    - Section headings ("Senior Program Committee:" / "Program Committee:")
      are bold ``Linux Biolinum`` 10pt.
    - Names use ``Linux Libertine`` 11pt (regular).
    - Affiliations use ``Linux Libertine`` 11pt italic, wrapped in parentheses.

After writing, ``verify_against_excel`` re-parses the docx and asserts the
extracted (name, affiliation) tuples match the Excel rows exactly, in order.
"""

import argparse
import re
import sys

import pandas as pd
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn

# Typography settings — must match the publisher's style guide.
HEADING_FONT = "Linux Biolinum"
HEADING_SIZE = Pt(10)
NAME_FONT = "Linux Libertine"
NAME_SIZE = Pt(11)


def style_run(run, font_name, size, *, bold=False, italic=False):
    """Apply font, size, and emphasis to a docx run.

    python-docx's high-level ``run.font.name = ...`` only sets the ASCII font
    slot. Word also consults the ``hAnsi``/``cs``/``eastAsia`` slots when
    rendering, so we set all four explicitly via the underlying ``w:rFonts``
    element. Without this, non-ASCII characters (accented names, CJK) can
    silently fall back to the default theme font.
    """
    run.font.name = font_name
    run.font.size = size
    run.bold = bold
    run.italic = italic

    # Ensure a <w:rFonts> child exists on the run's run-properties element,
    # then write the font name into every script slot Word might use.
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        from docx.oxml import OxmlElement
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), font_name)


def format_name(row: pd.Series) -> str:
    """Join ``first [middle] last`` from an Excel row into a single string.

    Middle name is included only when present and non-empty (NaN-safe).
    """
    parts = [str(row["first name"]).strip()]
    middle = row.get("middle name")
    if pd.notna(middle) and str(middle).strip():
        parts.append(str(middle).strip())
    parts.append(str(row["last name"]).strip())
    return " ".join(parts)


def add_entry_runs(paragraph, row: pd.Series) -> None:
    """Append three styled runs for one referee: ``Name (``, affiliation, ``)``.

    Split into separate runs so the affiliation alone can be italicized while
    the name and parentheses stay upright.
    """
    name_run = paragraph.add_run(format_name(row) + " (")
    style_run(name_run, NAME_FONT, NAME_SIZE)

    affil_run = paragraph.add_run(str(row["affiliation"]).strip())
    style_run(affil_run, NAME_FONT, NAME_SIZE, italic=True)

    close_run = paragraph.add_run(")")
    style_run(close_run, NAME_FONT, NAME_SIZE)


def add_section(doc: Document, heading: str, df: pd.DataFrame) -> None:
    """Append a labelled section of referees to the document.

    The first referee shares a paragraph with the bold heading (separated by
    four spaces, matching the requested layout); subsequent referees each get
    their own paragraph.
    """
    rows = list(df.iterrows())
    if not rows:
        return

    # First paragraph: heading + four spaces + first entry on the same line.
    first_para = doc.add_paragraph()
    heading_run = first_para.add_run(heading + "    ")
    style_run(heading_run, HEADING_FONT, HEADING_SIZE, bold=True)
    add_entry_runs(first_para, rows[0][1])

    # Remaining entries: one per paragraph.
    for _, row in rows[1:]:
        para = doc.add_paragraph()
        add_entry_runs(para, row)


def extract_entries(doc: Document) -> list[tuple[str, str]]:
    """Re-parse the docx into ``(name, affiliation)`` tuples in document order.

    Used by the verification step to round-trip the generated file. Section
    headings are stripped from the start of any paragraph that contains them
    so the leading entry on a heading line is still captured. Empty
    paragraphs (the blank separator between sections) are skipped.
    """
    entries = []
    # Greedy ``.*?`` for the name then a parenthesised affiliation at end-of-line.
    pattern = re.compile(r"^(.*?)\s*\(([^)]*)\)\s*$")

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Strip the heading prefix if present so the inline first entry parses.
        for heading in ("Senior Program Committee:", "Program Committee:"):
            if text.startswith(heading):
                text = text[len(heading):].strip()
                break

        match = pattern.match(text)
        if match:
            entries.append((match.group(1).strip(), match.group(2).strip()))
    return entries


def verify_against_excel(doc_path: str, spc: pd.DataFrame, pc: pd.DataFrame) -> None:
    """Assert the docx contents match the Excel rows exactly and in order.

    Builds the expected list by concatenating SPC then PC (the same order the
    document is written in), parses the docx with ``extract_entries``, and
    compares element-by-element. Raises ``SystemExit`` on any count or
    content mismatch; prints up to 10 offending rows to stderr first.
    """
    expected = [
        (format_name(row), str(row["affiliation"]).strip())
        for _, row in pd.concat([spc, pc], ignore_index=True).iterrows()
    ]
    actual = extract_entries(Document(doc_path))

    if len(expected) != len(actual):
        raise SystemExit(
            f"Verification FAILED: expected {len(expected)} entries, found {len(actual)}"
        )

    mismatches = [
        (i, exp, act) for i, (exp, act) in enumerate(zip(expected, actual)) if exp != act
    ]
    if mismatches:
        for i, exp, act in mismatches[:10]:
            print(f"  row {i}: expected {exp!r}, got {act!r}", file=sys.stderr)
        raise SystemExit(f"Verification FAILED: {len(mismatches)} mismatched entries")

    print(f"Verification OK: {len(actual)} entries match Excel order exactly")


def main() -> None:
    """CLI entry point: load Excel, write docx, verify round-trip."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="ictir_referees.xlsx",
                        help="Source Excel file with 'ICTIR - SPC' and 'ICTIR - PC' sheets.")
    parser.add_argument("--output", default="ictir_referees.docx",
                        help="Destination .docx path.")
    args = parser.parse_args()

    # Load both committee sheets up front; column schema is identical.
    spc = pd.read_excel(args.input, sheet_name="ICTIR - SPC")
    pc = pd.read_excel(args.input, sheet_name="ICTIR - PC")

    doc = Document()
    add_section(doc, "Senior Program Committee:", spc)
    doc.add_paragraph()  # Blank paragraph separating the two sections.
    add_section(doc, "Program Committee:", pc)
    doc.save(args.output)
    print(f"Wrote {args.output} ({len(spc)} SPC + {len(pc)} PC)")

    # Round-trip the file we just wrote and confirm it matches the source.
    verify_against_excel(args.output, spc, pc)


if __name__ == "__main__":
    main()
