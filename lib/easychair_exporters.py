"""
EasyChair Export Formatters
===========================

This module provides exporters for different output formats (XML, TXT, MD)
that work with validated Pydantic models.

Usage:
    from easychair_exporters import export_to_xml, export_to_text

    export_to_xml(proceedings_export, "output.xml")
    export_to_text(proceedings_export, "output.txt", format_type="txt")
"""

import xml.etree.ElementTree as ET
from typing import Optional, Literal
import logging
from datetime import datetime

from .easychair_models import ProceedingsExport, Track, Paper, Author

# Paper type to event tracking number prefix mapping
PAPER_TYPE_PREFIX_MAP = {
    "Full Research Paper": "fp",
    "Short Research Paper": "sp",
    "Resource Paper": "rr",
    "Reproducibility Paper": "rp",
    "Demo Short Paper": "de",
    "Perspective Paper": "per",
    "Industry Paper": "ip",
    "Tutorial Paper": "tut",
    "Low Resource Environment": "lre",
    "Doctoral Abstract": "dc",
    "Workshop Summary": "wk",
}


def indent_xml(elem, level=0):
    """
    Add pretty-printing indentation to XML elements.

    Args:
        elem: XML Element to indent
        level: Current indentation level (default: 0)
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def format_date(dt: Optional[datetime]) -> str:
    """
    Convert datetime to ACM format (DD-MON-YYYY).

    Args:
        dt: datetime object

    Returns:
        Formatted date string (e.g., "09-APR-2026") or empty string if None
    """
    if dt is None:
        return ""
    return dt.strftime("%d-%b-%Y").upper()


def clean_affiliation_string(affiliation_str: Optional[str]) -> str:
    """
    Clean affiliation string by stripping whitespace and leading/trailing punctuation.

    Handles common data quality issues like:
    - ", Tsinghua University" → "Tsinghua University"
    - "MIT, " → "MIT"
    - " , Stanford University" → "Stanford University"

    Args:
        affiliation_str: Raw affiliation string

    Returns:
        str: Cleaned affiliation string
    """
    if not affiliation_str:
        return ""

    # Strip whitespace
    cleaned = affiliation_str.strip()

    # Strip leading/trailing punctuation (commas, semicolons, periods, etc.)
    # Keep stripping until no more leading/trailing punctuation+whitespace
    while cleaned and cleaned[0] in '.,;:-_':
        cleaned = cleaned[1:].strip()
    while cleaned and cleaned[-1] in '.,;:-_':
        cleaned = cleaned[:-1].strip()

    return cleaned


def export_to_xml(
    export: ProceedingsExport,
    output_file: str,
    source: str = "EasyChair",
    logger: Optional[logging.Logger] = None
) -> None:
    """
    Export proceedings to ACM/Sheridan XML format.

    Args:
        export: Validated ProceedingsExport object
        output_file: Output XML file path
        source: Source system name
        logger: Optional logger instance
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    logger.info("Generating ACM XML...")

    # Create XML root
    root = ET.Element("erights_record")
    parent = ET.SubElement(root, "parent_data")
    ET.SubElement(parent, "proceeding").text = export.proceeding_id or ""
    ET.SubElement(parent, "volume").text = ""
    ET.SubElement(parent, "issue").text = ""
    ET.SubElement(parent, "issue_date").text = ""
    ET.SubElement(parent, "source").text = source

    paper_seq = 1

    # Process each track and paper
    for track in export.tracks:
        for paper in track.papers:
            paper_xml = ET.SubElement(root, "paper")

            # Paper metadata
            ET.SubElement(paper_xml, "paper_type").text = paper.paper_type
            ET.SubElement(paper_xml, "art_submission_date").text = format_date(paper.submitted_date)
            ET.SubElement(paper_xml, "art_approval_date").text = format_date(paper.approval_date)
            ET.SubElement(paper_xml, "paper_title").text = paper.title

            # Event tracking number
            prefix = PAPER_TYPE_PREFIX_MAP.get(paper.paper_type, "paper")
            ET.SubElement(paper_xml, "event_tracking_number").text = f"{prefix}{paper.submission_id}"
            ET.SubElement(paper_xml, "published_article_number").text = ""
            ET.SubElement(paper_xml, "start_page").text = ""
            ET.SubElement(paper_xml, "end_page").text = ""

            # Authors
            authors_xml = ET.SubElement(paper_xml, "authors")

            for author_seq, author in enumerate(paper.authors, start=1):
                author_xml = ET.SubElement(authors_xml, "author")

                # Author name
                ET.SubElement(author_xml, "prefix").text = ""
                ET.SubElement(author_xml, "first_name").text = author.first_name
                ET.SubElement(author_xml, "middle_name").text = ""
                ET.SubElement(author_xml, "last_name").text = author.last_name
                ET.SubElement(author_xml, "suffix").text = ""

                # Affiliations
                affiliations_xml = ET.SubElement(author_xml, "affiliations")
                affiliation_xml = ET.SubElement(affiliations_xml, "affiliation")

                # No parsing - just map Affiliation to institution
                ET.SubElement(affiliation_xml, "department").text = ""
                ET.SubElement(affiliation_xml, "institution").text = clean_affiliation_string(author.affiliation)
                ET.SubElement(affiliation_xml, "city").text = ""
                ET.SubElement(affiliation_xml, "state_province").text = ""
                ET.SubElement(affiliation_xml, "country").text = author.country or ""
                ET.SubElement(affiliation_xml, "sequence_no").text = "1"

                # Author metadata
                ET.SubElement(author_xml, "email_address").text = author.email or ""
                ET.SubElement(author_xml, "sequence_no").text = str(author_seq)
                ET.SubElement(author_xml, "contact_author").text = "Y" if author.is_corresponding else "N"
                ET.SubElement(author_xml, "ACM_profile_id").text = ""
                ET.SubElement(author_xml, "ACM_client_no").text = ""
                ET.SubElement(author_xml, "ORCID").text = ""
                ET.SubElement(author_xml, "role").text = "author"

            # Paper section and sequence
            ET.SubElement(paper_xml, "section").text = paper.section_name
            ET.SubElement(paper_xml, "sequence_no").text = str(paper_seq)

            paper_seq += 1

    # Write XML
    indent_xml(root)
    tree = ET.ElementTree(root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)

    logger.info(f"✓ XML generated: {output_file}")


def export_to_text(
    export: ProceedingsExport,
    output_file: str,
    format_type: Literal["txt", "md"] = "txt",
    logger: Optional[logging.Logger] = None
) -> None:
    """
    Export proceedings to text or markdown format.

    Args:
        export: Validated ProceedingsExport object
        output_file: Output file path
        format_type: Output format ("txt" or "md")
        logger: Optional logger instance
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    logger.info(f"Generating {format_type.upper()} output...")

    with open(output_file, "w", encoding="utf-8") as f:
        for track_idx, track in enumerate(sorted(export.tracks, key=lambda t: t.section_name)):
            # Track header
            if format_type == "md":
                f.write(f"# {track.section_name}\n")
            else:
                f.write(f"{track.section_name}\n")

            # Papers
            for paper in track.papers:
                if format_type == "md":
                    f.write(f"## {paper.title}\n")
                else:
                    f.write(f"{paper.title}\n")

                for author in paper.authors:
                    if author.affiliation:
                        f.write(f"{author.full_name}, {author.affiliation}\n")
                    else:
                        f.write(f"{author.full_name}\n")

                f.write("\n")

            # Extra blank line between tracks (but not after the last track)
            if track_idx < len(export.tracks) - 1:
                f.write("\n")

    logger.info(f"✓ {format_type.upper()} file generated: {output_file}")


def print_summary(
    export: ProceedingsExport,
    logger: logging.Logger
) -> None:
    """
    Print a summary of the export.

    Args:
        export: ProceedingsExport to summarize
        logger: Logger instance
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("EXPORT SUMMARY")
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"✓ Total papers exported: {export.total_papers}")
    logger.info(f"✓ Total author entries: {export.total_authors}")
    logger.info(f"✓ Unique authors: {export.unique_authors}")
    if export.total_papers > 0:
        logger.info(f"✓ Average authors per paper: {export.total_authors / export.total_papers:.1f}")
    if export.unique_authors > 0:
        logger.info(f"✓ Average papers per author: {export.total_authors / export.unique_authors:.2f}")

    logger.info("")
    logger.info("-" * 80)
    logger.info("TRACK NAME MAPPING")
    logger.info("-" * 80)
    for track in sorted(export.tracks, key=lambda t: t.section_name):
        logger.info(f"  {track.original_name}")
        logger.info(f"    → {track.section_name} ({track.paper_count} paper{'s' if track.paper_count != 1 else ''})")

    logger.info("")
    logger.info("-" * 80)
    logger.info("PAPERS BY SECTION")
    logger.info("-" * 80)
    for section, count in sorted(
        export.papers_by_track.items(), key=lambda x: x[1], reverse=True
    ):
        logger.info(f"  {section}: {count}")

    # Print validation issues
    logger.info("")
    logger.info("-" * 80)
    logger.info("DATA QUALITY")
    logger.info("-" * 80)

    # Count issues by severity
    info_count = sum(1 for i in export.validation_issues if i.severity == "info")

    if export.has_errors:
        logger.error(f"  ✗ {export.error_count} error(s) found")
    if export.has_warnings:
        logger.warning(f"  ⚠ {export.warning_count} warning(s) found")
    if info_count > 0:
        logger.info(f"  ℹ {info_count} informational notice(s)")

    if not export.has_errors and not export.has_warnings:
        logger.info("  ✓ No critical data quality issues detected")
        if info_count > 0:
            logger.info("  → Some informational notices present (see log for details)")
    else:
        # Group issues by category
        issues_by_category = {}
        for issue in export.validation_issues:
            if issue.category not in issues_by_category:
                issues_by_category[issue.category] = []
            issues_by_category[issue.category].append(issue)

        for category, issues in sorted(issues_by_category.items()):
            severity_counts = {}
            for issue in issues:
                severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

            severity_str = ", ".join(f"{count} {sev}" for sev, count in severity_counts.items())
            logger.info(f"  • {category}: {len(issues)} ({severity_str})")

        logger.info(f"  → Check log file for complete details")

        # Print first few issues at DEBUG level
        logger.debug("")
        logger.debug("=" * 80)
        logger.debug("VALIDATION ISSUES DETAILS")
        logger.debug("=" * 80)
        logger.debug("")
        logger.debug("Note: 'info' level issues are informational and often legitimate")
        logger.debug("      'warning' level issues may need review")
        logger.debug("      'error' level issues must be fixed")
        logger.debug("")
        for issue in export.validation_issues[:20]:
            logger.debug(str(issue))
            if issue.details:
                for key, value in issue.details.items():
                    logger.debug(f"  {key}: {value}")
            logger.debug("")
        if len(export.validation_issues) > 20:
            logger.debug(f"... and {len(export.validation_issues) - 20} more issues")

    logger.info("")
    logger.info("=" * 80)
