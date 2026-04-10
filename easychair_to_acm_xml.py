"""
EasyChair to ACM/Sheridan XML/Text/Markdown Converter
======================================================

This script converts EasyChair conference export data (Excel format) into
ACM/Sheridan XML format for proceedings submission, or into text/markdown
format for human-readable listings.

Features:
- Loads EasyChair Submissions and Authors sheets
- Filters accepted papers only
- Consolidates duplicate author entries and fills missing fields
- Detects potential typos (same email with different names, etc.)
- Cleans text fields (removes line feeds, extra whitespace)
- Maps EasyChair track names to ACM section names
- Auto-detects conference name from track data
- Generates detailed statistics and quality warnings (XML format)
- Exports to XML, plain text, or markdown format

Requirements:
- pandas library for data processing
- EasyChair Excel export with 'Submissions' and 'Authors' sheets

Usage:
    # XML format (for ACM submission)
    python easychair_to_acm_xml.py \
        --input "path/to/easychair_export.xlsx" \
        --proceeding_id "2026-SIGIR" \
        --output "sigir2026.xml"

    # Text format (human-readable)
    python easychair_to_acm_xml.py \
        --input "path/to/easychair_export.xlsx" \
        --format txt \
        --output "papers.txt"

    # Markdown format (human-readable)
    python easychair_to_acm_xml.py \
        --input "path/to/easychair_export.xlsx" \
        --format md \
        --output "papers.md"

Author: Generated for ACM proceedings preparation
"""

import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
import argparse
import logging
from collections import defaultdict


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def indent(elem, level=0):
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
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def format_date(date_str):
    """
    Convert date string to ACM format (DD-MON-YYYY).

    Args:
        date_str: Date string or pandas Timestamp

    Returns:
        Formatted date string (e.g., "09-APR-2026") or empty string if invalid
    """
    if pd.isna(date_str) or not date_str:
        return ""
    try:
        if isinstance(date_str, pd.Timestamp):
            dt = date_str
        else:
            dt = pd.to_datetime(date_str)
        return dt.strftime("%d-%b-%Y").upper()
    except:
        return ""


def setup_logging(log_file):
    """
    Set up logging to both console and file.

    Console: INFO level and above (INFO, WARNING, ERROR, CRITICAL)
    File: All levels including DEBUG

    Log levels used in this script:
    - DEBUG: Detailed field corrections, internal processing
    - INFO: Progress updates, statistics, successful operations
    - WARNING: Data quality issues, typos, missing fields
    - ERROR: Critical errors (papers with no authors)

    Args:
        log_file: Path to log file

    Returns:
        logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("easychair_to_acm")
    logger.setLevel(logging.DEBUG)  # Capture all levels

    # Prevent duplicate handlers if function is called multiple times
    if logger.handlers:
        logger.handlers.clear()

    # Console handler - INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)

    # File handler - DEBUG and above (all levels)
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_format)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ============================================================================
# TRACK NAME MAPPING RULES
# ============================================================================
# EasyChair track names are automatically cleaned to match ACM section names.
#
# Transformation rules (applied in order):
# 1. Auto-detect and remove conference prefix (e.g., "SIGIR 2026 ")
# 2. Remove " Track" suffix
# 3. Apply specific track-to-section mappings from TRACK_TO_SECTION_MAP
# 4. If no mapping found, use cleaned track name as-is
#
# Transformations:
#   "SIGIR 2026 Full Papers Track"               -> "Full Research Paper"
#   "SIGIR 2026 Short Papers Track"              -> "Short Research Paper"
#   "SIGIR 2026 Demo Papers Track"               -> "Demo Short Paper"
#   "SIGIR 2026 Resources Papers Track"          -> "Resource Paper"
#   "SIGIR 2026 Reproducibility Track"           -> "Reproducibility Paper"
#   "SIGIR 2026 Industry Papers Track"           -> "Industry Paper"
#   "SIGIR 2026 Perspectives Paper Track"        -> "Perspective Paper"
#   "SIGIR 2026 Workshop Proposals"              -> "Workshop Summary"
#   "SIGIR 2026 Tutorial Proposals"              -> "Tutorial Paper"
#   "SIGIR 2026 Doctoral Colloquium"             -> "Doctoral Abstract"
#   "SIGIR 2026 Low Resource Environments Track" -> "Low Resource Environment"
# ============================================================================

# Track name to ACM section name mapping
# Key: Track name after removing conference prefix and " Track" suffix
# Value: ACM section/paper type name
TRACK_TO_SECTION_MAP = {
    "Full Papers": "Full Research Paper",
    "Short Papers": "Short Research Paper",
    "Demo Papers": "Demo Short Paper",
    "Resources Papers": "Resource Paper",
    "Reproducibility": "Reproducibility Paper",
    "Industry Papers": "Industry Paper",
    "Perspectives Paper": "Perspective Paper",
    "Workshop Proposals": "Workshop Summary",
    "Tutorial Proposals": "Tutorial Paper",
    "Doctoral Colloquium": "Doctoral Abstract",
    "Low Resource Environments": "Low Resource Environment",
}

# Paper type to event tracking number prefix mapping
# Key: ACM paper type name
# Value: Prefix for event_tracking_number (e.g., "fp78" for Full Research Paper #78)
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


def export_easychair_to_text(
    excel_file_path,
    output_file="acm_output.txt",
    track_filter=None,
    format_type="txt",
):
    """
    Convert EasyChair export to text or markdown format.

    Args:
        excel_file_path: Path to EasyChair Excel export
        output_file: Output file name
        track_filter: Optional track name to filter submissions (default: None, include all)
        format_type: Output format type ("txt" or "md")
    """
    # ========================================================================
    # SETUP LOGGING
    # ========================================================================
    log_file = output_file + ".log"
    logger = setup_logging(log_file)

    logger.info("=" * 80)
    logger.info(f"EASYCHAIR TO {format_type.upper()} CONVERSION")
    logger.info("=" * 80)
    logger.debug(f"Loading Excel file: {excel_file_path}")
    logger.info(f"Output file: {output_file}")
    logger.info(f"Log file: {log_file}")

    # Load the Excel sheets
    excel = pd.ExcelFile(excel_file_path)
    submissions_df = pd.read_excel(excel, "Submissions")
    authors_df = pd.read_excel(excel, "Authors")

    logger.info(
        f"Loaded {len(submissions_df)} submissions and {len(authors_df)} author records"
    )

    # Filter by track if specified
    if track_filter:
        submissions_df = submissions_df[submissions_df["Track name"] == track_filter]
        logger.info(
            f"Filtered to {len(submissions_df)} submissions in track: {track_filter}"
        )

    # Filter for accepted papers only
    submissions_df = submissions_df[
        (submissions_df["Decision"] == "Accept paper/proposal")
        | (submissions_df["Decision"] == "tentatively accepted")
    ]
    logger.info(f"Found {len(submissions_df)} accepted submissions")

    # Clean up text fields
    def clean_text(x):
        if pd.isna(x):
            return ""
        return " ".join(str(x).split())

    submissions_df["Title"] = submissions_df["Title"].map(clean_text)
    submissions_df["Track name"] = submissions_df["Track name"].map(clean_text)
    authors_df["First name"] = authors_df["First name"].map(clean_text)
    authors_df["Last name"] = authors_df["Last name"].map(clean_text)
    authors_df["Affiliation"] = authors_df["Affiliation"].map(clean_text)

    # Identify conference prefix
    conference_prefix = ""
    if len(submissions_df) > 0:
        first_track = submissions_df["Track name"].iloc[0]
        parts = first_track.split()
        if len(parts) >= 2:
            conference_prefix = f"{parts[0]} {parts[1]} "
            logger.info(f"Detected conference: {conference_prefix.strip()}")

    # Initialize statistics
    total_authors = 0
    papers_with_no_authors = 0
    papers_with_missing_affiliations = 0
    author_name_mismatches = 0
    track_mapping = {}
    papers_by_track_count = {}

    # Group papers by track
    papers_by_track = {}
    for _, submission in submissions_df.iterrows():
        track_name = str(submission.get("Track name", ""))

        # Get section name
        section_name = track_name
        if conference_prefix and section_name.startswith(conference_prefix):
            section_name = section_name[len(conference_prefix):]
        section_name = section_name.replace(" Track", "")
        section_name = TRACK_TO_SECTION_MAP.get(section_name, section_name)

        if section_name not in papers_by_track:
            papers_by_track[section_name] = []

        # Track mapping statistics
        if track_name not in track_mapping:
            track_mapping[track_name] = section_name

        # Get authors for this submission in correct order
        submission_id = submission["#"]
        authors_str = str(submission.get("Authors", ""))
        authors_str = " ".join(authors_str.split())
        authors_str = authors_str.replace(" and ", ", ")
        correct_order = [name.strip() for name in authors_str.split(",") if name.strip()]

        # Get all authors for this paper from Authors sheet
        paper_authors_unsorted = authors_df[
            authors_df["Submission #"] == submission_id
        ].copy()

        if len(paper_authors_unsorted) == 0:
            logger.error(
                f"No authors found for submission #{submission_id} - skipping paper"
            )
            papers_with_no_authors += 1
            continue

        # Create a mapping of full names to their position
        name_to_position = {}
        for idx, name in enumerate(correct_order):
            name_to_position[name.lower()] = idx

        # Sort authors by correct order
        def get_author_sequence(row):
            nonlocal author_name_mismatches
            full_name = f"{row['First name']} {row['Last name']}".lower()
            if full_name in name_to_position:
                return name_to_position[full_name]
            for correct_name, pos in name_to_position.items():
                if full_name in correct_name or correct_name in full_name:
                    return pos
            # Name mismatch
            author_name_mismatches += 1
            logger.warning(
                f"⚠ Author name mismatch in Paper #{submission_id}: "
                f"'{row['First name']} {row['Last name']}' from Authors sheet "
                f"not found in Submissions.Authors column."
            )
            return row["Person #"] + 1000

        paper_authors_unsorted["_sequence"] = paper_authors_unsorted.apply(
            get_author_sequence, axis=1
        )
        paper_authors = paper_authors_unsorted.sort_values("_sequence")

        total_authors += len(paper_authors)

        # Build author list and check for missing affiliations
        author_list = []
        paper_has_missing_affiliation = False
        for _, author in paper_authors.iterrows():
            first_name = str(author.get("First name", ""))
            last_name = str(author.get("Last name", ""))
            affiliation = str(author.get("Affiliation", ""))
            if pd.isna(affiliation) or affiliation == "nan" or not affiliation.strip():
                affiliation = ""
                paper_has_missing_affiliation = True
            author_list.append((f"{first_name} {last_name}", affiliation))

        if paper_has_missing_affiliation:
            papers_with_missing_affiliations += 1

        papers_by_track[section_name].append({
            "title": str(submission.get("Title", "")),
            "authors": author_list,
            "submission_id": submission_id
        })

    # Count papers by track
    for section, papers in papers_by_track.items():
        papers_by_track_count[section] = len(papers)

    # ========================================================================
    # WRITE OUTPUT FILE
    # ========================================================================
    logger.info("")
    logger.info(f"Generating {format_type.upper()} output...")

    with open(output_file, "w", encoding="utf-8") as f:
        for track_idx, (track_name, papers) in enumerate(sorted(papers_by_track.items())):
            # Track header
            if format_type == "md":
                f.write(f"# {track_name}\n")
            else:
                f.write(f"{track_name}\n")

            # Papers
            for paper in papers:
                if format_type == "md":
                    f.write(f"## {paper['title']}\n")
                else:
                    f.write(f"{paper['title']}\n")

                for author_name, affiliation in paper["authors"]:
                    if affiliation:
                        f.write(f"{author_name}, {affiliation}\n")
                    else:
                        f.write(f"{author_name}\n")

                f.write("\n")

            # Extra blank line between tracks (but not after the last track)
            if track_idx < len(papers_by_track) - 1:
                f.write("\n")

    # ========================================================================
    # PRINT SUMMARY
    # ========================================================================
    total_papers = sum(len(papers) for papers in papers_by_track.values())

    logger.info("")
    logger.info("=" * 80)
    logger.info("EXPORT SUMMARY")
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"✓ {format_type.upper()} file generated: {output_file}")
    logger.info(f"✓ Total papers exported: {total_papers}")
    logger.info(f"✓ Total author entries: {total_authors}")
    if total_papers > 0:
        logger.info(f"✓ Average authors per paper: {total_authors / total_papers:.1f}")

    logger.info("")
    logger.info("-" * 80)
    logger.info("TRACK NAME MAPPING")
    logger.info("-" * 80)
    for original, cleaned in sorted(track_mapping.items()):
        count = papers_by_track_count[cleaned]
        logger.info(f"  {original}")
        logger.info(f"    → {cleaned} ({count} paper{'s' if count != 1 else ''})")

    logger.info("")
    logger.info("-" * 80)
    logger.info("PAPERS BY SECTION")
    logger.info("-" * 80)
    for section, count in sorted(
        papers_by_track_count.items(), key=lambda x: x[1], reverse=True
    ):
        logger.info(f"  {section}: {count}")

    logger.info("")
    logger.info("-" * 80)
    logger.info("DATA QUALITY WARNINGS")
    logger.info("-" * 80)
    if papers_with_no_authors > 0:
        logger.warning(
            f"  ⚠ {papers_with_no_authors} paper(s) skipped due to missing authors"
        )
    if papers_with_missing_affiliations > 0:
        logger.warning(
            f"  ⚠ {papers_with_missing_affiliations} paper(s) have at least one author with missing affiliation"
        )
    if author_name_mismatches > 0:
        logger.warning(
            f"  ⚠ {author_name_mismatches} author(s) had name mismatches between Submissions and Authors sheets"
        )
        logger.warning(f"     → Check log file for details")

    if (
        papers_with_no_authors == 0
        and papers_with_missing_affiliations == 0
        and author_name_mismatches == 0
    ):
        logger.info("  ✓ No data quality issues detected")

    logger.info("")
    logger.info("=" * 80)
    logger.info(f"Log file saved to: {log_file}")

    # ========================================================================
    # RUN AUTHOR ORDER VALIDATION TEST
    # ========================================================================
    logger.info("")
    logger.info("=" * 80)
    logger.info("RUNNING AUTHOR ORDER VALIDATION TEST")
    logger.info("=" * 80)

    import subprocess

    try:
        # Run the validation test script
        test_script = "tests/test_author_order.py"
        result = subprocess.run(
            ["python", test_script, excel_file_path, output_file],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        # Print test output
        if result.stdout:
            for line in result.stdout.splitlines():
                logger.info(line)

        if result.returncode == 0:
            logger.info("")
            logger.info("✓ Author order validation test PASSED")
        else:
            logger.error("")
            logger.error("✗ Author order validation test FAILED")
            logger.error("Please review the issues above and fix the data if needed")
            if result.stderr:
                logger.error("Test error output:")
                for line in result.stderr.splitlines():
                    logger.error(f"  {line}")

    except FileNotFoundError:
        logger.warning(f"Warning: Test script '{test_script}' not found - skipping validation")
    except subprocess.TimeoutExpired:
        logger.error("Error: Validation test timed out after 5 minutes")
    except Exception as e:
        logger.warning(f"Warning: Could not run validation test: {e}")


def export_easychair_to_acm_xml(
    excel_file_path,
    proceeding_id,
    source="EasyChair",
    paper_type=None,
    output_file="acm_output.xml",
    approval_date=None,
    track_filter=None,
):
    """
    Convert EasyChair export to ACM/Sheridan XML format.

    Args:
        excel_file_path: Path to EasyChair Excel export
        proceeding_id: ACM proceeding ID (e.g., "2018-1234.1234")
        source: Source system name (default: "EasyChair")
        paper_type: Type of paper override. If None (default), automatically derives
                    from track/section name. Only use this when exporting a single
                    track or when all papers should have the same type.
        output_file: Output XML file name
        approval_date: Date when papers were approved (optional, for metadata)
        track_filter: Optional track name to filter submissions (default: None, include all)
    """

    # ========================================================================
    # SETUP LOGGING
    # ========================================================================
    # Create log file name based on output file name
    log_file = output_file + ".log"
    logger = setup_logging(log_file)

    logger.info("=" * 80)
    logger.info("EASYCHAIR TO ACM XML CONVERSION")
    logger.info("=" * 80)
    logger.debug(f"Loading Excel file: {excel_file_path}")
    logger.info(f"Proceeding ID: {proceeding_id}")
    logger.info(f"Output file: {output_file}")
    logger.info(f"Log file: {log_file}")

    # Load the Excel sheets
    excel = pd.ExcelFile(excel_file_path)

    # Load dataframes
    submissions_df = pd.read_excel(excel, "Submissions")
    authors_df = pd.read_excel(excel, "Authors")

    logger.info(
        f"Loaded {len(submissions_df)} submissions and {len(authors_df)} author records"
    )

    # Filter by track if specified
    if track_filter:
        submissions_df = submissions_df[submissions_df["Track name"] == track_filter]
        logger.info(
            f"Filtered to {len(submissions_df)} submissions in track: {track_filter}"
        )

    # Filter for accepted papers only
    submissions_df = submissions_df[
        (submissions_df["Decision"] == "Accept paper/proposal")
        | (submissions_df["Decision"] == "tentatively accepted")
    ]
    logger.info(f"Found {len(submissions_df)} accepted submissions")

    # Clean up text fields - remove line feeds and extra whitespace
    def clean_text(x):
        """Remove line feeds, tabs, and extra whitespace."""
        if pd.isna(x):
            return ""
        return " ".join(str(x).split())

    # Clean submission fields
    submissions_df["Title"] = submissions_df["Title"].map(clean_text)
    submissions_df["Track name"] = submissions_df["Track name"].map(clean_text)
    submissions_df["Keywords"] = submissions_df["Keywords"].map(
        lambda x: "; ".join(str(x).split("\n")) if pd.notna(x) and x else ""
    )

    # Identify conference name from track names
    # Assume format: "Conference Year Track Name"
    conference_prefix = ""
    if len(submissions_df) > 0:
        first_track = submissions_df["Track name"].iloc[0]
        # Extract first two words (e.g., "SIGIR 2026")
        parts = first_track.split()
        if len(parts) >= 2:
            conference_prefix = f"{parts[0]} {parts[1]} "
            logger.info(f"Detected conference: {conference_prefix.strip()}")

    # Clean author fields
    authors_df["First name"] = authors_df["First name"].map(clean_text)
    authors_df["Last name"] = authors_df["Last name"].map(clean_text)
    authors_df["Email"] = authors_df["Email"].map(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    authors_df["Affiliation"] = authors_df["Affiliation"].map(clean_text)
    authors_df["Country"] = authors_df["Country"].map(clean_text)

    # ========================================================================
    # CONSOLIDATE DUPLICATE AUTHOR ENTRIES
    # ========================================================================
    # Authors may appear multiple times if they have multiple papers.
    # For each unique author (identified by name+email), consolidate their
    # information by filling in missing fields from other entries.
    # ========================================================================
    logger.info("")
    logger.info("Consolidating duplicate author entries...")
    author_corrections = 0

    def get_author_key(row):
        """Create a unique key for grouping author entries."""
        email = (
            row["Email"].lower().strip()
            if pd.notna(row["Email"]) and row["Email"] and row["Email"] != "nan"
            else ""
        )
        return (
            row["First name"].lower().strip(),
            row["Last name"].lower().strip(),
            email,
        )

    def is_empty_value(val):
        """Check if a field value is empty/missing."""
        return pd.isna(val) or not str(val).strip() or str(val) == "nan"

    # Build consolidated info for each unique author
    authors_df["_author_key"] = authors_df.apply(get_author_key, axis=1)
    consolidated_info = {}

    for author_key, group in authors_df.groupby("_author_key"):
        if len(group) > 1:
            # Multiple entries - find the best (most complete) value for each field
            info = {}
            for field in ["Email", "Country", "Web page"]:
                best_val = ""
                for _, row in group.iterrows():
                    val = row.get(field, "")
                    if not is_empty_value(val) and not best_val:
                        best_val = val
                        break
                info[field] = best_val
            consolidated_info[author_key] = info

    # Apply consolidated info back to all rows
    for idx, row in authors_df.iterrows():
        key = row["_author_key"]
        if key in consolidated_info:
            for field, value in consolidated_info[key].items():
                old_val = row.get(field, "")
                if is_empty_value(old_val) and value:
                    logger.debug(
                        f"  → Filling {field} for {row['First name']} {row['Last name']} "
                        f"(Paper #{row['Submission #']}): '{old_val}' → '{value}'"
                    )
                    authors_df.at[idx, field] = value
                    author_corrections += 1

    authors_df = authors_df.drop(columns=["_author_key"])

    if author_corrections > 0:
        logger.warning(
            f"✓ Made {author_corrections} field correction(s) across duplicate author entries"
        )
        logger.warning(f"  → Check log file for detailed list of corrections")
    else:
        logger.info("✓ No duplicate author entries requiring consolidation")

    # ========================================================================
    # DETECT POTENTIAL TYPOS AND INCONSISTENCIES
    # ========================================================================
    # Look for data quality issues that might indicate typos:
    # 1. Same email but different names (strong indicator of typo)
    # 2. Same name but different emails (could be typo or different person)
    # ========================================================================
    logger.info("")
    logger.info("Checking for potential typos in author data...")
    typo_warnings = []

    # Check 1: Same email, different names
    # Note: Names are already cleaned (whitespace normalized), so we can compare directly
    valid_emails = authors_df[
        authors_df["Email"].notna()
        & (authors_df["Email"] != "")
        & (authors_df["Email"] != "nan")
    ]
    for email, group in valid_emails.groupby("Email"):
        if len(group) > 1:
            # Get unique name combinations (after cleaning)
            first_names = group["First name"].unique()
            last_names = group["Last name"].unique()

            # Only flag if there are ACTUALLY different names (not just duplicates)
            if len(first_names) > 1 or len(last_names) > 1:
                # Get unique name variants to avoid showing same name multiple times
                unique_names = group[
                    ["First name", "Last name", "Submission #"]
                ].drop_duplicates(subset=["First name", "Last name"])

                # Double-check: if after deduplication we only have 1 unique name, skip
                # This catches cases where slight variations (whitespace, etc.) were already cleaned
                if len(unique_names) > 1:
                    for _, row in unique_names.iterrows():
                        typo_warnings.append(
                            {
                                "type": "email_match_name_mismatch",
                                "email": email,
                                "first_name": row["First name"],
                                "last_name": row["Last name"],
                                "paper": row["Submission #"],
                                "message": f"Same email '{email}' but different name",
                            }
                        )

    # Check 2: Same name, different emails
    for (first, last), group in authors_df.groupby(["First name", "Last name"]):
        if len(group) > 1:
            valid_group_emails = group[
                group["Email"].notna()
                & (group["Email"] != "")
                & (group["Email"] != "nan")
            ]
            emails = valid_group_emails["Email"].unique()

            if len(emails) > 1:
                for _, row in valid_group_emails.iterrows():
                    typo_warnings.append(
                        {
                            "type": "name_match_email_mismatch",
                            "first_name": first,
                            "last_name": last,
                            "email": row["Email"],
                            "paper": row["Submission #"],
                            "affiliation": row.get("Affiliation", ""),
                            "message": f"Same name '{first} {last}' but different emails",
                        }
                    )

    # Print warnings grouped by type
    if typo_warnings:
        # Group by type
        email_mismatches = [
            w for w in typo_warnings if w["type"] == "email_match_name_mismatch"
        ]
        name_mismatches = [
            w for w in typo_warnings if w["type"] == "name_match_email_mismatch"
        ]

        # Summary at WARNING level (shown on console)
        logger.warning("")
        logger.warning(
            f"⚠ Found {len(typo_warnings)} potential typo(s) or data inconsistencies:"
        )

        if email_mismatches:
            unique_emails = len(set(w["email"] for w in email_mismatches))
            logger.warning(
                f"  • Same email, different names: {unique_emails} email(s) affected"
            )

        if name_mismatches:
            unique_names = len(
                set((w["first_name"], w["last_name"]) for w in name_mismatches)
            )
            logger.warning(
                f"  • Same name, different emails: {unique_names} name(s) affected"
            )

        logger.warning(f"  → Check log file for complete details")

        # Details at DEBUG level (only in log file)
        logger.debug("")
        logger.debug("=" * 80)
        logger.debug("DETAILED TYPO/INCONSISTENCY REPORT")
        logger.debug("=" * 80)

        if email_mismatches:
            # Count unique emails (not individual warnings)
            unique_emails = len(set(w["email"] for w in email_mismatches))
            logger.debug("")
            logger.debug(
                f"Same email, different names ({unique_emails} email(s) affected):"
            )
            logger.debug("-" * 80)

            # Group by email
            by_email = defaultdict(list)
            for w in email_mismatches:
                by_email[w["email"]].append(w)

            for email, warnings in by_email.items():
                logger.debug(f"  Email: {email}")
                # Group warnings by unique name to show variants clearly
                name_variants = {}
                for w in warnings:
                    name_key = (w["first_name"], w["last_name"])
                    if name_key not in name_variants:
                        name_variants[name_key] = []
                    name_variants[name_key].append(w["paper"])

                # Show each name variant with first/last split visible for easy comparison
                for (first, last), papers in name_variants.items():
                    paper_list = ", ".join(f"#{p}" for p in papers)
                    logger.debug(
                        f"    → First: '{first}' | Last: '{last}' (Papers: {paper_list})"
                    )

        if name_mismatches:
            logger.debug("")
            logger.debug(
                f"Same name, different emails ({len(name_mismatches)} case(s)):"
            )
            logger.debug("-" * 80)
            # Group by name
            by_name = defaultdict(list)
            for w in name_mismatches:
                by_name[(w["first_name"], w["last_name"])].append(w)

            for (first, last), warnings in by_name.items():
                logger.debug(f"  Name: {first} {last}")
                for w in warnings:
                    aff_str = f" - {w['affiliation']}" if w["affiliation"] else ""
                    logger.debug(f"    → Paper #{w['paper']}: {w['email']}{aff_str}")

        logger.debug("")
        logger.debug("=" * 80)
    else:
        logger.info("✓ No potential typos detected")

    # ========================================================================
    # GENERATE ACM XML
    # ========================================================================
    logger.info("")
    logger.info("Generating ACM XML...")

    # Initialize statistics tracking
    track_mapping = {}  # original track -> cleaned section name
    papers_by_track = {}  # cleaned section name -> count
    total_authors = 0
    papers_with_no_authors = 0
    papers_with_missing_affiliations = 0
    papers_with_no_corresponding = 0
    authors_with_missing_emails = 0
    author_name_mismatches = 0  # Authors that couldn't be matched to Submissions.Authors
    author_paper_count = {}  # (first, last, email) -> list of paper IDs
    author_paper_types = {}  # (first, last, email) -> list of paper types

    # Create XML root and parent metadata
    root = ET.Element("erights_record")
    parent = ET.SubElement(root, "parent_data")
    ET.SubElement(parent, "proceeding").text = proceeding_id
    ET.SubElement(parent, "volume").text = ""
    ET.SubElement(parent, "issue").text = ""
    ET.SubElement(parent, "issue_date").text = ""
    ET.SubElement(parent, "source").text = source

    paper_seq = 1

    # Process each accepted submission
    for _, submission in submissions_df.iterrows():
        submission_id = submission["#"]

        # Get authors for this submission in the correct order
        # Parse the "Authors" column from Submissions to get the correct order
        authors_str = str(submission.get("Authors", ""))

        # Clean the text: remove line breaks and extra whitespace
        authors_str = " ".join(authors_str.split())

        # Split by comma or "and" to get individual author names
        # Replace " and " with ", " to normalize separators
        authors_str = authors_str.replace(" and ", ", ")
        correct_order = [name.strip() for name in authors_str.split(",") if name.strip()]

        # Get all authors for this paper from Authors sheet
        paper_authors_unsorted = authors_df[
            authors_df["Submission #"] == submission_id
        ].copy()

        # Create a mapping of full names to their position in correct_order
        name_to_position = {}
        for idx, name in enumerate(correct_order):
            # Try to match "First Last" format
            name_to_position[name.lower()] = idx

        # Assign sequence numbers based on correct order
        def get_author_sequence(row):
            """Determine the correct sequence for an author."""
            nonlocal author_name_mismatches
            full_name = f"{row['First name']} {row['Last name']}".lower()

            # Try exact match first
            if full_name in name_to_position:
                return name_to_position[full_name]

            # Try partial match (useful for names with middle initials, etc.)
            for correct_name, pos in name_to_position.items():
                if full_name in correct_name or correct_name in full_name:
                    return pos

            # Fallback: use Person # if no match found
            # This indicates a data quality issue - name mismatch between sheets
            author_name_mismatches += 1
            logger.warning(
                f"⚠ Author name mismatch in Paper #{submission_id}: "
                f"'{row['First name']} {row['Last name']}' from Authors sheet "
                f"not found in Submissions.Authors column. Using Person # as fallback."
            )
            logger.warning(
                f"  → Expected authors: {', '.join(correct_order)}"
            )
            return row["Person #"] + 1000  # Large offset to put unmatched at end

        paper_authors_unsorted["_sequence"] = paper_authors_unsorted.apply(
            get_author_sequence, axis=1
        )
        paper_authors = paper_authors_unsorted.sort_values("_sequence")

        if len(paper_authors) == 0:
            logger.error(
                f"No authors found for submission #{submission_id} - skipping paper"
            )
            papers_with_no_authors += 1
            continue

        total_authors += len(paper_authors)

        # Create paper element
        paper = ET.SubElement(root, "paper")

        # Determine section name first (needed for auto paper_type)
        track_name = str(submission.get("Track name", ""))
        section_name = track_name

        # Remove conference name prefix
        if conference_prefix and section_name.startswith(conference_prefix):
            section_name = section_name[len(conference_prefix) :]

        # Remove " Track" suffix
        section_name = section_name.replace(" Track", "")

        # Apply track-to-section mapping (use original name if not in map)
        section_name = TRACK_TO_SECTION_MAP.get(section_name, section_name)

        # Determine paper type: use override if provided, otherwise derive from section
        # This ensures correct paper types when exporting multiple tracks:
        # - Demo Papers Track → "Demo Paper"
        # - Full Papers Track → "Full Paper"
        # - Workshop Proposals → "Workshop Summary" (via section_name mapping)
        if paper_type is not None:
            current_paper_type = paper_type  # Manual override for all papers
        else:
            current_paper_type = section_name  # Auto-derive from track/section

        # Paper metadata
        ET.SubElement(paper, "paper_type").text = current_paper_type
        ET.SubElement(paper, "art_submission_date").text = format_date(
            submission.get("Submitted")
        )
        ET.SubElement(paper, "art_approval_date").text = format_date(
            approval_date or submission.get("Approval date", "")
        )
        ET.SubElement(paper, "paper_title").text = str(submission.get("Title", ""))

        # Generate event tracking number with paper type prefix
        # e.g., "fp78" for Full Research Paper #78, "de42" for Demo Short Paper #42
        prefix = PAPER_TYPE_PREFIX_MAP.get(current_paper_type, "paper")
        ET.SubElement(paper, "event_tracking_number").text = f"{prefix}{submission_id}"
        ET.SubElement(paper, "published_article_number").text = ""
        ET.SubElement(paper, "start_page").text = ""
        ET.SubElement(paper, "end_page").text = ""

        # Check data quality issues for this paper
        has_corresponding = any(
            str(auth.get("Corresponding?", "")) == "✔"
            for _, auth in paper_authors.iterrows()
        )
        if not has_corresponding:
            papers_with_no_corresponding += 1

        paper_has_missing_affiliation = False

        # Build authors section
        authors_xml = ET.SubElement(paper, "authors")

        for author_seq, (_, author) in enumerate(paper_authors.iterrows(), start=1):
            author_xml = ET.SubElement(authors_xml, "author")

            # Track author paper count and types
            first_name = str(author.get("First name", ""))
            last_name = str(author.get("Last name", ""))
            email = str(author.get("Email", "")).lower().strip()
            if email == "nan":
                email = ""
            author_key = (first_name, last_name, email)
            if author_key not in author_paper_count:
                author_paper_count[author_key] = []
                author_paper_types[author_key] = []
            author_paper_count[author_key].append(submission_id)
            author_paper_types[author_key].append(current_paper_type)

            # Author name
            ET.SubElement(author_xml, "prefix").text = ""
            ET.SubElement(author_xml, "first_name").text = first_name
            ET.SubElement(author_xml, "middle_name").text = ""
            ET.SubElement(author_xml, "last_name").text = last_name
            ET.SubElement(author_xml, "suffix").text = ""

            # Affiliations
            affiliations_xml = ET.SubElement(author_xml, "affiliations")
            affiliation_xml = ET.SubElement(affiliations_xml, "affiliation")

            # Map EasyChair fields directly to ACM XML without parsing
            # EasyChair provides: Affiliation (single field), Country
            # ACM XML requires: department, institution, city, state_province, country
            affiliation_str = author.get("Affiliation")
            if pd.isna(affiliation_str) or not str(affiliation_str).strip():
                paper_has_missing_affiliation = True
                affiliation_str = ""

            # No parsing - just map the single Affiliation field to institution
            ET.SubElement(affiliation_xml, "department").text = ""
            ET.SubElement(affiliation_xml, "institution").text = str(affiliation_str).strip()
            ET.SubElement(affiliation_xml, "city").text = ""
            ET.SubElement(affiliation_xml, "state_province").text = ""
            ET.SubElement(affiliation_xml, "country").text = str(
                author.get("Country", "")
            )
            ET.SubElement(affiliation_xml, "sequence_no").text = "1"

            # Author metadata
            email = str(author.get("Email", ""))
            if not email or email == "nan" or not email.strip():
                authors_with_missing_emails += 1
            ET.SubElement(author_xml, "email_address").text = email
            ET.SubElement(author_xml, "sequence_no").text = str(author_seq)

            # Corresponding author - check if marked with ✔, or default to first author
            is_corresponding = str(author.get("Corresponding?", "")) == "✔"
            if not has_corresponding and author_seq == 1:
                is_corresponding = True  # Default first author as corresponding
            ET.SubElement(author_xml, "contact_author").text = (
                "Y" if is_corresponding else "N"
            )

            ET.SubElement(author_xml, "ACM_profile_id").text = ""
            ET.SubElement(author_xml, "ACM_client_no").text = ""
            ET.SubElement(author_xml, "ORCID").text = ""
            ET.SubElement(author_xml, "role").text = "author"

        if paper_has_missing_affiliation:
            papers_with_missing_affiliations += 1

        # Track mapping statistics
        if track_name not in track_mapping:
            track_mapping[track_name] = section_name
        papers_by_track[section_name] = papers_by_track.get(section_name, 0) + 1

        # Paper section and sequence
        ET.SubElement(paper, "section").text = section_name
        ET.SubElement(paper, "sequence_no").text = str(paper_seq)

        paper_seq += 1

    # ========================================================================
    # WRITE XML FILE
    # ========================================================================
    indent(root)  # Add pretty-printing indentation
    tree = ET.ElementTree(root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)

    # ========================================================================
    # PRINT DETAILED SUMMARY
    # ========================================================================
    logger.info("")
    logger.info("=" * 80)
    logger.info("EXPORT SUMMARY")
    logger.info("=" * 80)

    total_papers = paper_seq - 1
    unique_authors = len(author_paper_count)

    logger.info("")
    logger.info(f"✓ XML generated: {output_file}")
    logger.info(f"✓ Total papers exported: {total_papers}")
    logger.info(
        f"✓ Total author entries: {total_authors}"
    )  # Sum of all authors across all papers
    logger.info(f"✓ Unique authors: {unique_authors}")  # Distinct individuals
    logger.info(f"✓ Average authors per paper: {total_authors / total_papers:.1f}")
    # Average papers per author = total author entries / unique authors
    # This tells us how many papers each unique author contributes to on average
    logger.info(
        f"✓ Average papers per author: {total_authors / unique_authors if unique_authors > 0 else 0:.2f}"
    )

    logger.info("")
    logger.info("-" * 80)
    logger.info("TRACK NAME MAPPING")
    logger.info("-" * 80)
    for original, cleaned in sorted(track_mapping.items()):
        count = papers_by_track[cleaned]
        logger.info(f"  {original}")
        logger.info(f"    → {cleaned} ({count} paper{'s' if count != 1 else ''})")

    logger.info("")
    logger.info("-" * 80)
    logger.info("PAPERS BY SECTION")
    logger.info("-" * 80)
    for section, count in sorted(
        papers_by_track.items(), key=lambda x: x[1], reverse=True
    ):
        logger.info(f"  {section}: {count}")

    logger.info("")
    logger.info("-" * 80)
    # ========================================================================
    # Show top authors with their paper type distribution
    # Logic: Show top 5 authors, but if there are ties at the 5th position,
    # include ALL tied authors to be fair.
    #
    # Example: If positions 4, 5, 6, 7 all have 3 papers each, we show all 7.
    # ========================================================================
    sorted_authors = sorted(
        author_paper_count.items(), key=lambda x: len(x[1]), reverse=True
    )

    if sorted_authors:
        # Determine cutoff: include at least top 5, plus all ties at the 5th position
        if len(sorted_authors) <= 5:
            authors_to_show = sorted_authors
        else:
            # Get the paper count of the 5th author (index 4)
            fifth_author_count = len(sorted_authors[4][1])

            # Include all authors with paper count >= 5th author's count
            authors_to_show = []
            for author_info in sorted_authors:
                if len(author_info[1]) >= fifth_author_count:
                    authors_to_show.append(author_info)
                else:
                    break  # Stop once we go below the cutoff

        # Update title based on actual count and whether we included ties
        if len(sorted_authors) <= 5:
            # Fewer than 5 authors total, or exactly 5
            logger.info(f"TOP {len(authors_to_show)} MOST PROLIFIC AUTHORS")
        elif len(authors_to_show) == 5:
            # Exactly 5, no ties
            logger.info("TOP 5 MOST PROLIFIC AUTHORS")
        else:
            # More than 5 due to ties at the 5th position
            logger.info(
                f"TOP {len(authors_to_show)} MOST PROLIFIC AUTHORS (including ties)"
            )
        logger.info("-" * 80)

        for i, ((first, last, email), papers) in enumerate(authors_to_show, 1):
            email_str = f" ({email})" if email else ""
            paper_types = author_paper_types[(first, last, email)]

            # Count paper types
            type_counts = {}
            for ptype in paper_types:
                type_counts[ptype] = type_counts.get(ptype, 0) + 1

            # Format paper type distribution
            type_str = ", ".join(
                f"{count} {ptype}" for ptype, count in sorted(type_counts.items())
            )

            logger.info(f"  {i}. {first} {last}{email_str}: {len(papers)} paper(s)")
            logger.info(f"     Paper types: {type_str}")
            if len(papers) <= 10:  # Only show paper IDs if reasonable number
                logger.info(f"     Papers: {', '.join(f'#{p}' for p in papers)}")

    logger.info("")
    logger.info("-" * 80)
    logger.info("DATA QUALITY WARNINGS")
    logger.info("-" * 80)
    if papers_with_no_authors > 0:
        logger.warning(
            f"  ⚠ {papers_with_no_authors} paper(s) skipped due to missing authors"
        )
    if papers_with_no_corresponding > 0:
        logger.warning(
            f"  ⚠ {papers_with_no_corresponding} paper(s) had no corresponding author marked"
        )
        logger.warning(f"     → First author was automatically set as corresponding")
    if papers_with_missing_affiliations > 0:
        logger.warning(
            f"  ⚠ {papers_with_missing_affiliations} paper(s) have at least one author with missing affiliation"
        )
    if authors_with_missing_emails > 0:
        logger.warning(
            f"  ⚠ {authors_with_missing_emails} author(s) have missing or invalid email addresses"
        )
    if author_name_mismatches > 0:
        logger.warning(
            f"  ⚠ {author_name_mismatches} author(s) had name mismatches between Submissions and Authors sheets"
        )
        logger.warning(f"     → Check log file for details and fix the data if needed")

    if (
        papers_with_no_authors == 0
        and papers_with_no_corresponding == 0
        and papers_with_missing_affiliations == 0
        and authors_with_missing_emails == 0
        and author_name_mismatches == 0
    ):
        logger.info("  ✓ No data quality issues detected")

    logger.info("")
    logger.info("=" * 80)
    logger.info(f"Log file saved to: {log_file}")

    # ========================================================================
    # RUN AUTHOR ORDER VALIDATION TEST
    # ========================================================================
    logger.info("")
    logger.info("=" * 80)
    logger.info("RUNNING AUTHOR ORDER VALIDATION TEST")
    logger.info("=" * 80)

    import subprocess

    try:
        # Run the validation test script
        test_script = "tests/test_author_order.py"
        result = subprocess.run(
            ["python", test_script, excel_file_path, output_file],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        # Print test output
        if result.stdout:
            for line in result.stdout.splitlines():
                logger.info(line)

        if result.returncode == 0:
            logger.info("")
            logger.info("✓ Author order validation test PASSED")
        else:
            logger.error("")
            logger.error("✗ Author order validation test FAILED")
            logger.error("Please review the issues above and fix the data if needed")
            if result.stderr:
                logger.error("Test error output:")
                for line in result.stderr.splitlines():
                    logger.error(f"  {line}")

    except FileNotFoundError:
        logger.warning(f"Warning: Test script '{test_script}' not found - skipping validation")
    except subprocess.TimeoutExpired:
        logger.error("Error: Validation test timed out after 5 minutes")
    except Exception as e:
        logger.warning(f"Warning: Could not run validation test: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert EasyChair export to ACM/Sheridan XML, text, or markdown format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all tracks to XML with auto-detected paper types
  python easychair_to_acm_xml.py --input export.xlsx --proceeding_id "2026-SIGIR" --output all.xml

  # Export to text format
  python easychair_to_acm_xml.py --input export.xlsx --format txt --output papers.txt

  # Export to markdown format
  python easychair_to_acm_xml.py --input export.xlsx --format md --output papers.md

  # Export only demo papers to XML
  python easychair_to_acm_xml.py --input export.xlsx --proceeding_id "2026-SIGIR-Demo" \\
    --track "SIGIR 2026 Demo Papers Track" --output demos.xml

  # Override paper type for all papers (rare)
  python easychair_to_acm_xml.py --input export.xlsx --proceeding_id "2026-SIGIR" \\
    --paper_type "Full Paper" --output all_as_full.xml

Note: Track name must be EXACT match (case-sensitive) from EasyChair's "Track name" column.
        """,
    )

    parser.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Path to EasyChair Excel export file (must contain 'Submissions' and 'Authors' sheets)",
    )

    parser.add_argument(
        "--format",
        choices=["xml", "txt", "md"],
        default="xml",
        help="Output format: xml (ACM/Sheridan XML), txt (plain text), or md (markdown). Default: xml",
    )

    parser.add_argument(
        "--proceeding_id",
        metavar="ID",
        help="ACM proceeding ID (e.g., '2026-SIGIR', '2018-1234.1234'). "
        "Required for XML format. Use different IDs for different tracks if submitting separately.",
    )

    parser.add_argument(
        "--source",
        default="EasyChair",
        help="Source system name for XML metadata (default: 'EasyChair'). Only used for XML format.",
    )

    parser.add_argument(
        "--paper_type",
        default=None,
        metavar="TYPE",
        help="Override paper type for ALL papers. By default (recommended), paper type is "
        "automatically derived from track/section name (e.g., 'Demo Paper', 'Full Paper', "
        "'Workshop Summary'). Only use --paper_type to force all papers to the same type, "
        "typically when exporting a single track with --track. Only used for XML format.",
    )

    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Output file name (default: 'acm_output.xml', 'acm_output.txt', or 'acm_output.md' based on format)",
    )

    parser.add_argument(
        "--approval_date",
        default=None,
        metavar="DATE",
        help="Set the same approval date for all papers (format: YYYY-MM-DD). By default, "
        "leaves approval date empty in XML. Use this if you want to set a uniform approval date for all papers. "
        "Only used for XML format.",
    )

    parser.add_argument(
        "--track",
        default=None,
        metavar="NAME",
        help="Export ONLY papers from this specific track (all other tracks are excluded). "
        "Track name must be EXACT match (case-sensitive) from EasyChair's 'Track name' column. "
        "Examples: 'SIGIR 2026 Demo Papers Track', 'SIGIR 2026 Full Papers Track'. "
        "Use this to: (1) generate separate files per track, (2) test with a small track first, "
        "or (3) use different proceeding IDs for different paper types. "
        "To see available track names, check the 'Track name' column in your Excel export.",
    )

    args = parser.parse_args()

    # Set default output filename based on format if not specified
    if args.output is None:
        if args.format == "xml":
            args.output = "acm_output.xml"
        elif args.format == "txt":
            args.output = "acm_output.txt"
        else:  # md
            args.output = "acm_output.md"

    # Handle different output formats
    if args.format in ["txt", "md"]:
        export_easychair_to_text(
            excel_file_path=args.input,
            output_file=args.output,
            track_filter=args.track,
            format_type=args.format,
        )
    else:  # xml
        # Validate that proceeding_id is provided for XML format
        if args.proceeding_id is None:
            parser.error("--proceeding_id is required when --format is 'xml'")

        export_easychair_to_acm_xml(
            excel_file_path=args.input,
            proceeding_id=args.proceeding_id,
            source=args.source,
            paper_type=args.paper_type,
            output_file=args.output,
            track_filter=args.track,
            approval_date=args.approval_date,
        )
