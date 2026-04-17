"""
EasyChair Data Loader with Validation
=====================================

This module loads EasyChair Excel export data into validated Pydantic models,
providing runtime validation and error detection during the loading process.

Usage:
    from easychair_loader import load_easychair_data

    export = load_easychair_data(
        excel_file_path="export.xlsx",
        track_filter=None,
        submission_date_override="22-JAN-2026",  # Optional
        approval_date_override="02-APR-2026",    # Optional
        section_column="Paper type"              # Optional: column for ACM section tag
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


def parse_acm_date(date_str: str) -> datetime:
    """
    Parse ACM date format (DD-MON-YYYY) to datetime object.

    Args:
        date_str: Date string in ACM format (e.g., "22-JAN-2026")

    Returns:
        datetime object

    Raises:
        ValueError: If date string format is invalid
    """
    try:
        return datetime.strptime(date_str, "%d-%b-%Y")
    except ValueError:
        raise ValueError(
            f"Invalid date format: '{date_str}'. "
            "Expected format: DD-MON-YYYY (e.g., '22-JAN-2026')"
        )


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
    paper_id_filter: Optional[int] = None,
    proceeding_id: Optional[str] = None,
    submission_date_override: Optional[str] = None,
    approval_date_override: Optional[str] = None,
    section_column: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> ProceedingsExport:
    """
    Load and validate EasyChair export data.

    Args:
        excel_file_path: Path to EasyChair Excel export
        track_filter: Optional track name to filter
        paper_id_filter: Optional paper ID to filter (submission number)
        proceeding_id: Optional ACM proceeding ID
        submission_date_override: Optional submission date to use for all papers (e.g., '22-JAN-2026')
        approval_date_override: Optional approval date to use for all papers (e.g., '02-APR-2026')
        section_column: Optional Excel column name to use for ACM section tag (e.g., 'Paper type')
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

    # Parse date overrides if provided
    submission_date_dt = None
    approval_date_dt = None

    if submission_date_override:
        try:
            submission_date_dt = parse_acm_date(submission_date_override)
            logger.info(f"Using submission date override: {submission_date_override}")
        except ValueError as e:
            raise ValueError(f"Invalid submission date: {e}")

    if approval_date_override:
        try:
            approval_date_dt = parse_acm_date(approval_date_override)
            logger.info(f"Using approval date override: {approval_date_override}")
        except ValueError as e:
            raise ValueError(f"Invalid approval date: {e}")

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

    # Validate section_column if provided
    if section_column:
        if section_column not in submissions_df.columns:
            available_cols = ", ".join(submissions_df.columns[:10])
            raise ValueError(
                f"Section column '{section_column}' not found in Submissions sheet. "
                f"Available columns: {available_cols}..."
            )
        logger.info(f"Using column '{section_column}' for ACM section tag")
    else:
        logger.info("No section column specified - section tags will be empty")

    # Filter by track if specified
    if track_filter:
        submissions_df = submissions_df[submissions_df["Track name"] == track_filter]
        logger.info(f"Filtered to {len(submissions_df)} submissions in track: {track_filter}")

    # Filter by paper ID if specified
    if paper_id_filter is not None:
        submissions_df = submissions_df[submissions_df["#"] == paper_id_filter]
        if len(submissions_df) == 0:
            raise ValueError(f"Paper ID {paper_id_filter} not found in Excel file")
        logger.info(f"Filtered to paper ID: {paper_id_filter}")

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
                logger,
                submission_date_override=submission_date_dt,
                approval_date_override=approval_date_dt,
                section_column=section_column
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
    logger: logging.Logger,
    submission_date_override: Optional[datetime] = None,
    approval_date_override: Optional[datetime] = None,
    section_column: Optional[str] = None
) -> Optional[Paper]:
    """
    Load a single paper from submission data.

    Args:
        submission: Submission row from DataFrame
        authors_df: Authors DataFrame
        conference_prefix: Conference name prefix
        export: Export object to add issues to
        logger: Logger instance
        submission_date_override: Optional override for submission date (all papers)
        approval_date_override: Optional override for approval date (all papers)
        section_column: Optional Excel column name to use for ACM section tag

    Returns:
        Paper object or None if loading fails
    """
    submission_id = int(submission["#"])

    # Get track name
    track_name = str(submission.get("Track name", ""))

    # Derive paper type from track name (for automatic mapping)
    derived_type = track_name
    if conference_prefix and derived_type.startswith(conference_prefix):
        derived_type = derived_type[len(conference_prefix):]
    derived_type = derived_type.replace(" Track", "")
    derived_type = TRACK_TO_SECTION_MAP.get(derived_type, derived_type)
    paper_type = derived_type

    # Section name: use specified column if provided, otherwise empty
    if section_column:
        section_name = str(submission.get(section_column, ""))
    else:
        section_name = ""

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

    # Helper to check valid email
    def has_valid_email(author):
        return author.email is not None and author.email.strip() != ""

    # Determine contact author priority BEFORE Paper validation modifies flags
    marked_corresponding_with_email = [a for a in authors if a.is_corresponding and has_valid_email(a)]
    has_priority_1 = len(marked_corresponding_with_email) > 0

    # Parse dates - use overrides if provided, otherwise read from Excel
    if submission_date_override is not None:
        submitted_date = submission_date_override
    else:
        submitted_date = None
        if pd.notna(submission.get("Submitted")):
            try:
                submitted_date = pd.to_datetime(submission.get("Submitted"))
            except:
                pass

    if approval_date_override is not None:
        approval_date = approval_date_override
    else:
        approval_date = None
        if pd.notna(submission.get("Approval date")):
            try:
                approval_date = pd.to_datetime(submission.get("Approval date"))
            except:
                pass

    # Create Paper object (will validate and set contact author)
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

        # Log contact author selection priority if not priority 1
        if not has_priority_1:
            contact_author = paper.corresponding_authors[0] if paper.corresponding_authors else None
            if contact_author:
                # Contact author is first author (either priority 2 or 3)
                if has_valid_email(contact_author):
                    # Priority 2: First author with valid email
                    logger.warning(
                        f"⚠ Paper #{submission_id} ('{paper.title[:60]}...'): "
                        f"No corresponding author marked or no valid email. Using first author with valid email as contact author."
                    )
                    export.add_issue(
                        "warning",
                        "contact_author_priority_2",
                        "Using first author with valid email as contact author (no corresponding author marked with valid email)",
                        paper_id=submission_id
                    )
                else:
                    # Priority 3: First author without valid email
                    logger.error(
                        f"✗ Paper #{submission_id} ('{paper.title[:60]}...'): "
                        f"No valid emails found. Using first author '{contact_author.full_name}' "
                        f"as contact author despite invalid/missing email."
                    )
                    export.add_issue(
                        "error",
                        "contact_author_priority_3",
                        f"Using first author '{contact_author.full_name}' as contact author despite invalid/missing email",
                        paper_id=submission_id
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
