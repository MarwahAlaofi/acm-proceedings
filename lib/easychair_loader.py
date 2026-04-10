"""
EasyChair Data Loader with Validation
=====================================

This module loads EasyChair Excel export data into validated Pydantic models,
providing runtime validation and error detection during the loading process.

Usage:
    from easychair_loader import load_easychair_data

    export = load_easychair_data(
        excel_file_path="export.xlsx",
        track_filter=None
    )
"""

import pandas as pd
from typing import Optional, Dict, List
import logging
from collections import defaultdict
from datetime import datetime

from .easychair_models import (
    Author, Paper, Track, ProceedingsExport, ValidationIssue,
    validate_proceedings_export
)

# Track name mapping (same as in main script)
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


def clean_text(x) -> str:
    """Remove line feeds, tabs, and extra whitespace."""
    if pd.isna(x):
        return ""
    return " ".join(str(x).split())


def parse_authors_from_string(authors_str: str) -> List[str]:
    """
    Parse author names from the Submissions.Authors column.

    Args:
        authors_str: Raw author string (e.g., "John Doe, Jane Smith and Bob Lee")

    Returns:
        List of author names in order
    """
    authors_str = clean_text(authors_str)
    authors_str = authors_str.replace(" and ", ", ")
    return [name.strip() for name in authors_str.split(",") if name.strip()]


def load_easychair_data(
    excel_file_path: str,
    track_filter: Optional[str] = None,
    proceeding_id: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> ProceedingsExport:
    """
    Load and validate EasyChair export data.

    Args:
        excel_file_path: Path to EasyChair Excel export
        track_filter: Optional track name to filter
        proceeding_id: Optional ACM proceeding ID
        logger: Optional logger instance

    Returns:
        Validated ProceedingsExport object

    Raises:
        ValueError: If required data is invalid
        FileNotFoundError: If Excel file not found
        KeyError: If required columns are missing
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    # Initialize export object
    export = ProceedingsExport(proceeding_id=proceeding_id)

    logger.info(f"Loading Excel file: {excel_file_path}")

    # Load Excel sheets
    try:
        excel = pd.ExcelFile(excel_file_path)
        submissions_df = pd.read_excel(excel, "Submissions")
        authors_df = pd.read_excel(excel, "Authors")
    except FileNotFoundError:
        raise FileNotFoundError(f"Excel file not found: {excel_file_path}")
    except ValueError as e:
        raise ValueError(f"Error reading Excel sheets: {e}")

    logger.info(
        f"Loaded {len(submissions_df)} submissions and {len(authors_df)} author records"
    )

    # Filter by track if specified
    if track_filter:
        submissions_df = submissions_df[submissions_df["Track name"] == track_filter]
        logger.info(f"Filtered to {len(submissions_df)} submissions in track: {track_filter}")

    # Filter for accepted papers only
    submissions_df = submissions_df[
        (submissions_df["Decision"] == "Accept paper/proposal")
        | (submissions_df["Decision"] == "tentatively accepted")
    ]
    logger.info(f"Found {len(submissions_df)} accepted submissions")

    if len(submissions_df) == 0:
        logger.warning("No accepted submissions found!")
        return export

    # Clean text fields
    submissions_df["Title"] = submissions_df["Title"].map(clean_text)
    submissions_df["Track name"] = submissions_df["Track name"].map(clean_text)
    submissions_df["Keywords"] = submissions_df["Keywords"].map(
        lambda x: "; ".join(str(x).split("\n")) if pd.notna(x) and x else ""
    )

    authors_df["First name"] = authors_df["First name"].map(clean_text)
    authors_df["Last name"] = authors_df["Last name"].map(clean_text)
    authors_df["Email"] = authors_df["Email"].map(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    authors_df["Affiliation"] = authors_df["Affiliation"].map(clean_text)
    authors_df["Country"] = authors_df["Country"].map(clean_text)

    # Detect conference name
    conference_prefix = ""
    if len(submissions_df) > 0:
        first_track = submissions_df["Track name"].iloc[0]
        parts = first_track.split()
        if len(parts) >= 2:
            conference_prefix = f"{parts[0]} {parts[1]} "
            export.conference_name = conference_prefix.strip()
            logger.info(f"Detected conference: {conference_prefix.strip()}")

    # Consolidate duplicate author entries
    logger.info("Consolidating duplicate author entries...")
    authors_df = consolidate_duplicate_authors(authors_df, logger)

    # Group papers by track
    papers_by_track: Dict[str, List[Paper]] = defaultdict(list)
    track_original_names: Dict[str, str] = {}

    # Process each submission
    for _, submission in submissions_df.iterrows():
        try:
            paper = load_paper_from_submission(
                submission,
                authors_df,
                conference_prefix,
                export,
                logger
            )
            if paper:
                # Track mapping
                if paper.section_name not in track_original_names:
                    track_original_names[paper.section_name] = paper.track_name

                papers_by_track[paper.section_name].append(paper)
        except Exception as e:
            logger.error(f"Error loading paper #{submission['#']}: {e}")
            export.add_issue(
                "error",
                "loading_error",
                f"Failed to load paper: {str(e)}",
                paper_id=submission['#']
            )

    # Create Track objects
    for section_name, papers in papers_by_track.items():
        track = Track(
            original_name=track_original_names[section_name],
            section_name=section_name,
            papers=papers
        )
        export.tracks.append(track)

    # Run validation
    logger.info("Running validation...")
    export = validate_proceedings_export(export)

    logger.info(f"Loaded {export.total_papers} papers across {len(export.tracks)} tracks")
    logger.info(f"Total authors: {export.total_authors}, Unique: {export.unique_authors}")

    if export.has_errors:
        logger.error(f"Found {export.error_count} error(s)")
    if export.has_warnings:
        logger.warning(f"Found {export.warning_count} warning(s)")

    return export


def consolidate_duplicate_authors(
    authors_df: pd.DataFrame,
    logger: logging.Logger
) -> pd.DataFrame:
    """
    Fill missing fields for the same author across different papers.

    This function identifies the same person across multiple papers (by name + email)
    and fills ONLY EMPTY fields. It NEVER overwrites existing values, allowing authors
    to legitimately have different affiliations/emails/countries for different papers.

    Example:
    - Paper 1: John Doe (john@mit.edu), affiliation="MIT", country="USA"
    - Paper 2: John Doe (john@mit.edu), affiliation="", country=""
    → Paper 2 gets filled: affiliation="MIT", country="USA"

    - Paper 3: John Doe (john@mit.edu), affiliation="Stanford", country="USA"
    → Paper 3 is NOT changed (existing affiliation is kept)

    Args:
        authors_df: DataFrame with author data
        logger: Logger instance

    Returns:
        Cleaned DataFrame with missing fields filled
    """
    author_corrections = 0

    def get_author_key(row):
        """
        Create a unique key for identifying the same person across papers.
        Uses name + email to identify individuals.
        """
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

    # Group by author identity (across all papers)
    authors_df["_author_key"] = authors_df.apply(get_author_key, axis=1)

    # For each unique author, collect all non-empty values for each field
    # We'll use the first non-empty value found
    consolidated_info = {}

    for author_key, group in authors_df.groupby("_author_key"):
        if len(group) > 1:
            # Author appears in multiple papers
            info = {}
            for field in ["Email", "Country", "Web page", "Affiliation"]:
                # Find first non-empty value for this field
                best_val = ""
                for _, row in group.iterrows():
                    val = row.get(field, "")
                    if not is_empty_value(val):
                        best_val = val
                        break  # Use first non-empty value found
                info[field] = best_val
            consolidated_info[author_key] = info

    # Apply consolidated info ONLY to empty fields (never overwrite)
    for idx, row in authors_df.iterrows():
        key = row["_author_key"]
        if key in consolidated_info:
            for field, value in consolidated_info[key].items():
                old_val = row.get(field, "")
                # Only fill if current value is empty AND we have a value to fill
                if is_empty_value(old_val) and value:
                    logger.debug(
                        f"Filling {field} for {row['First name']} {row['Last name']} "
                        f"(Paper #{row['Submission #']}): '{old_val}' → '{value}'"
                    )
                    authors_df.at[idx, field] = value
                    author_corrections += 1

    authors_df = authors_df.drop(columns=["_author_key"])

    if author_corrections > 0:
        logger.info(f"Made {author_corrections} field correction(s) by filling empty fields across papers")
        logger.info("Note: Existing values were never overwritten (authors can have different affiliations per paper)")
    else:
        logger.info("No empty author fields to fill from other papers")

    return authors_df


def load_paper_from_submission(
    submission: pd.Series,
    authors_df: pd.DataFrame,
    conference_prefix: str,
    export: ProceedingsExport,
    logger: logging.Logger
) -> Optional[Paper]:
    """
    Load a single paper from submission data.

    Args:
        submission: Submission row from DataFrame
        authors_df: Authors DataFrame
        conference_prefix: Conference name prefix
        export: Export object to add issues to
        logger: Logger instance

    Returns:
        Paper object or None if loading fails
    """
    submission_id = int(submission["#"])

    # Get track and section names
    track_name = str(submission.get("Track name", ""))
    section_name = track_name

    if conference_prefix and section_name.startswith(conference_prefix):
        section_name = section_name[len(conference_prefix):]
    section_name = section_name.replace(" Track", "")
    section_name = TRACK_TO_SECTION_MAP.get(section_name, section_name)

    # Paper type is same as section name
    paper_type = section_name

    # Get expected author order from Submissions.Authors column
    authors_str = str(submission.get("Authors", ""))
    expected_order = parse_authors_from_string(authors_str)

    # Get all authors for this paper from Authors sheet
    paper_authors_df = authors_df[authors_df["Submission #"] == submission_id].copy()

    if len(paper_authors_df) == 0:
        logger.error(f"No authors found for submission #{submission_id}")
        export.add_issue(
            "error",
            "no_authors",
            "Paper has no authors",
            paper_id=submission_id
        )
        return None

    # Create name-to-position mapping
    name_to_position = {}
    for idx, name in enumerate(expected_order):
        name_to_position[name.lower()] = idx

    # Build Author objects in correct order
    authors_with_sequence = []
    for _, author_row in paper_authors_df.iterrows():
        try:
            # Create Author object (will validate)
            author = Author(
                first_name=str(author_row.get("First name", "")),
                last_name=str(author_row.get("Last name", "")),
                email=str(author_row.get("Email", "")) if pd.notna(author_row.get("Email")) else None,
                affiliation=str(author_row.get("Affiliation", "")) if pd.notna(author_row.get("Affiliation")) else None,
                country=str(author_row.get("Country", "")) if pd.notna(author_row.get("Country")) else None,
                web_page=str(author_row.get("Web page", "")) if pd.notna(author_row.get("Web page")) else None,
                is_corresponding=str(author_row.get("Corresponding?", "")) == "✔",
                person_id=int(author_row.get("Person #", 0))
            )

            # Determine sequence
            full_name = author.full_name.lower()
            if full_name in name_to_position:
                sequence = name_to_position[full_name]
            else:
                # Try partial match
                sequence = None
                for correct_name, pos in name_to_position.items():
                    if full_name in correct_name or correct_name in full_name:
                        sequence = pos
                        break

                if sequence is None:
                    # Name mismatch
                    logger.warning(
                        f"Author name mismatch in Paper #{submission_id}: "
                        f"'{author.full_name}' from Authors sheet not found in Submissions.Authors"
                    )
                    export.add_issue(
                        "warning",
                        "author_order_mismatch",
                        f"Author '{author.full_name}' not found in expected order",
                        paper_id=submission_id,
                        author_name=author.full_name
                    )
                    sequence = author.person_id + 1000  # Put at end

            authors_with_sequence.append((sequence, author))

        except Exception as e:
            logger.error(f"Error creating author for paper #{submission_id}: {e}")
            export.add_issue(
                "error",
                "author_validation_error",
                f"Failed to validate author: {str(e)}",
                paper_id=submission_id
            )
            continue

    # Sort by sequence
    authors_with_sequence.sort(key=lambda x: x[0])
    authors = [author for _, author in authors_with_sequence]

    if not authors:
        logger.error(f"No valid authors for submission #{submission_id}")
        return None

    # Parse dates
    submitted_date = None
    if pd.notna(submission.get("Submitted")):
        try:
            submitted_date = pd.to_datetime(submission.get("Submitted"))
        except:
            pass

    approval_date = None
    if pd.notna(submission.get("Approval date")):
        try:
            approval_date = pd.to_datetime(submission.get("Approval date"))
        except:
            pass

    # Create Paper object (will validate)
    try:
        paper = Paper(
            submission_id=submission_id,
            title=str(submission.get("Title", "")),
            authors=authors,
            track_name=track_name,
            section_name=section_name,
            paper_type=paper_type,
            keywords=str(submission.get("Keywords", "")) if pd.notna(submission.get("Keywords")) else None,
            submitted_date=submitted_date,
            approval_date=approval_date,
        )
        return paper
    except Exception as e:
        logger.error(f"Error creating paper #{submission_id}: {e}")
        export.add_issue(
            "error",
            "paper_validation_error",
            f"Failed to validate paper: {str(e)}",
            paper_id=submission_id
        )
        return None
