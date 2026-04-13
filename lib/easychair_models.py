"""
EasyChair Data Models with Pydantic Validation
===============================================

This module defines validated data models for EasyChair conference data
and ACM proceedings export. Using Pydantic ensures data integrity at
runtime and provides clear error messages for validation failures.

Models:
- Author: Individual author with affiliation
- Paper: Conference paper with authors and metadata
- Track: Collection of papers in a track/section
- ProceedingsExport: Complete export with all tracks

Usage:
    from easychair_models import Author, Paper, Track, validate_easychair_data

    # Validation happens automatically
    author = Author(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        affiliation="University"
    )
"""

from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from datetime import datetime
import re


class Author(BaseModel):
    """
    Author information with validation.

    Validates:
    - Names are not empty or whitespace-only
    - Email format (if provided)
    - Affiliation cleaning
    """
    first_name: str = Field(..., min_length=1, description="Author's first name")
    last_name: str = Field(..., min_length=1, description="Author's last name")
    email: Optional[str] = Field(None, description="Author's email address")
    affiliation: Optional[str] = Field(None, description="Author's affiliation/institution")
    country: Optional[str] = Field(None, description="Author's country")
    web_page: Optional[str] = Field(None, description="Author's web page")
    is_corresponding: bool = Field(default=False, description="Is this the corresponding author?")

    # Internal fields for tracking
    person_id: Optional[int] = Field(None, description="EasyChair person ID")

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Ensure names are not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty or whitespace-only")
        return v.strip()

    @field_validator('email')
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate email format if provided."""
        if v is None or not v or v.strip().lower() == "nan":
            return None
        v = v.strip().lower()
        # Basic email validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError(f"Invalid email format: {v}")
        return v

    @field_validator('affiliation', 'country', 'web_page')
    @classmethod
    def clean_optional_string(cls, v: Optional[str]) -> Optional[str]:
        """Clean optional string fields."""
        if v is None or not v or str(v).strip().lower() == "nan":
            return None
        return str(v).strip()

    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def name_key(self) -> tuple:
        """Get unique key for deduplication."""
        return (
            self.first_name.lower().strip(),
            self.last_name.lower().strip(),
            (self.email or "").lower().strip()
        )

    def __str__(self) -> str:
        return self.full_name

    class Config:
        """Pydantic config."""
        validate_assignment = True  # Validate on assignment too
        str_strip_whitespace = True


class Paper(BaseModel):
    """
    Conference paper with validation.

    Validates:
    - Paper has at least one author
    - Title is not empty
    - Author order is preserved
    - At least one corresponding author exists
    """
    submission_id: int = Field(..., description="EasyChair submission ID")
    title: str = Field(..., min_length=1, description="Paper title")
    authors: List[Author] = Field(..., min_items=1, description="List of authors in order")
    track_name: str = Field(..., description="Original track name from EasyChair")
    section_name: str = Field(..., description="Cleaned section name for ACM")
    paper_type: str = Field(..., description="ACM paper type")

    # Optional fields
    keywords: Optional[str] = Field(None, description="Paper keywords")
    submitted_date: Optional[datetime] = Field(None, description="Submission date")
    approval_date: Optional[datetime] = Field(None, description="Approval date")
    abstract: Optional[str] = Field(None, description="Paper abstract")

    @field_validator('title')
    @classmethod
    def validate_title_not_empty(cls, v: str) -> str:
        """Ensure title is not empty."""
        if not v or not v.strip():
            raise ValueError("Paper title cannot be empty")
        return v.strip()

    @model_validator(mode='after')
    def validate_corresponding_author(self):
        """
        Ensure exactly one contact author per paper.
        Priority: 1) First corresponding (✔) with valid email
                  2) First author with valid email
                  3) First author (regardless of email)

        Note: Warnings/errors for priority 2 and 3 are logged in the loader.
        """
        # Helper to check valid email
        def has_valid_email(author: Author) -> bool:
            return author.email is not None and author.email.strip() != ""

        # Remember which authors were marked as corresponding
        marked_corresponding = [a for a in self.authors if a.is_corresponding]

        # Clear all flags to set exactly one
        for author in self.authors:
            author.is_corresponding = False

        # Priority 1: First corresponding (✔) author with valid email
        for author in marked_corresponding:
            if has_valid_email(author):
                author.is_corresponding = True
                return self

        # Priority 2: First author with valid email
        for author in self.authors:
            if has_valid_email(author):
                author.is_corresponding = True
                return self

        # Priority 3: First author (fallback)
        if self.authors:
            self.authors[0].is_corresponding = True

        return self

    @property
    def author_count(self) -> int:
        """Get number of authors."""
        return len(self.authors)

    @property
    def corresponding_authors(self) -> List[Author]:
        """Get list of corresponding authors."""
        return [a for a in self.authors if a.is_corresponding]

    @property
    def has_missing_affiliations(self) -> bool:
        """Check if any author has missing affiliation."""
        return any(not author.affiliation for author in self.authors)

    @property
    def has_missing_emails(self) -> bool:
        """Check if any author has missing email."""
        return any(not author.email for author in self.authors)

    @property
    def event_tracking_number(self) -> str:
        """Generate event tracking number with prefix."""
        from easychair_to_acm_xml import PAPER_TYPE_PREFIX_MAP
        prefix = PAPER_TYPE_PREFIX_MAP.get(self.paper_type, "paper")
        return f"{prefix}{self.submission_id}"

    def __str__(self) -> str:
        return f"Paper #{self.submission_id}: {self.title}"

    class Config:
        """Pydantic config."""
        validate_assignment = True


class Track(BaseModel):
    """
    Track/section containing papers.

    Validates:
    - Track has valid name
    - Papers list is valid
    """
    original_name: str = Field(..., description="Original track name from EasyChair")
    section_name: str = Field(..., description="Cleaned section name for ACM")
    papers: List[Paper] = Field(default_factory=list, description="Papers in this track")

    @property
    def paper_count(self) -> int:
        """Get number of papers."""
        return len(self.papers)

    @property
    def total_authors(self) -> int:
        """Get total author count across all papers."""
        return sum(p.author_count for p in self.papers)

    @property
    def papers_with_missing_affiliations(self) -> int:
        """Count papers with missing affiliations."""
        return sum(1 for p in self.papers if p.has_missing_affiliations)

    def __str__(self) -> str:
        return f"{self.section_name} ({self.paper_count} papers)"

    class Config:
        """Pydantic config."""
        validate_assignment = True


class ValidationIssue(BaseModel):
    """
    Data quality or validation issue.
    """
    severity: Literal["error", "warning", "info"] = Field(..., description="Issue severity")
    category: str = Field(..., description="Issue category (e.g., 'author_order', 'missing_data')")
    message: str = Field(..., description="Human-readable message")
    paper_id: Optional[int] = Field(None, description="Related paper ID")
    author_name: Optional[str] = Field(None, description="Related author name")
    details: Optional[Dict] = Field(None, description="Additional details")

    def __str__(self) -> str:
        prefix = "⚠" if self.severity == "warning" else "✗" if self.severity == "error" else "ℹ"
        base = f"{prefix} {self.message}"
        if self.paper_id:
            base = f"Paper #{self.paper_id}: {base}"
        return base


class ProceedingsExport(BaseModel):
    """
    Complete proceedings export with validation.

    Tracks:
    - All tracks and papers
    - Statistics
    - Validation issues
    """
    proceeding_id: Optional[str] = Field(None, description="ACM proceeding ID")
    conference_name: Optional[str] = Field(None, description="Conference name (auto-detected)")
    tracks: List[Track] = Field(default_factory=list, description="All tracks")
    validation_issues: List[ValidationIssue] = Field(default_factory=list, description="Validation issues")

    # Statistics
    total_papers: int = Field(default=0, description="Total number of papers")
    total_authors: int = Field(default=0, description="Total author entries")
    unique_authors: int = Field(default=0, description="Unique authors")

    @property
    def papers_by_track(self) -> Dict[str, int]:
        """Get paper count by track."""
        return {track.section_name: track.paper_count for track in self.tracks}

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return any(issue.severity == "error" for issue in self.validation_issues)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(issue.severity == "warning" for issue in self.validation_issues)

    @property
    def error_count(self) -> int:
        """Get error count."""
        return sum(1 for issue in self.validation_issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        """Get warning count."""
        return sum(1 for issue in self.validation_issues if issue.severity == "warning")

    def add_issue(
        self,
        severity: Literal["error", "warning", "info"],
        category: str,
        message: str,
        paper_id: Optional[int] = None,
        author_name: Optional[str] = None,
        **details
    ):
        """Add a validation issue."""
        issue = ValidationIssue(
            severity=severity,
            category=category,
            message=message,
            paper_id=paper_id,
            author_name=author_name,
            details=details if details else None
        )
        self.validation_issues.append(issue)

    def update_statistics(self):
        """Update statistics from tracks and papers."""
        self.total_papers = sum(track.paper_count for track in self.tracks)
        self.total_authors = sum(track.total_authors for track in self.tracks)

        # Calculate unique authors
        seen_authors = set()
        for track in self.tracks:
            for paper in track.papers:
                for author in paper.authors:
                    seen_authors.add(author.name_key)
        self.unique_authors = len(seen_authors)

    class Config:
        """Pydantic config."""
        validate_assignment = True


def validate_author_name_consistency(export: ProceedingsExport) -> List[ValidationIssue]:
    """
    Check for potential typos: same email with different names.

    Note: This validation is smart about legitimate variations:
    - Same email with different names: WARNING (likely typo)
    - Same name with different emails: INFO (often legitimate - multiple email addresses)
    - Same name with different affiliations: NOT FLAGGED (completely legitimate - changed institutions)

    Authors can legitimately have:
    - Different affiliations across papers (changed institutions)
    - Different emails across papers (multiple addresses, moved institutions)
    - Different countries across papers (relocated)

    Args:
        export: ProceedingsExport to validate

    Returns:
        List of validation issues found
    """
    issues = []

    # Collect all authors across all papers
    all_authors = []
    for track in export.tracks:
        for paper in track.papers:
            for author in paper.authors:
                all_authors.append((author, paper.submission_id))

    # Check 1: Same email, different names (LIKELY TYPO - flag as warning)
    email_to_names = {}
    for author, paper_id in all_authors:
        if author.email:
            if author.email not in email_to_names:
                email_to_names[author.email] = []
            email_to_names[author.email].append((author.full_name, paper_id))

    for email, names_and_papers in email_to_names.items():
        unique_names = set(name for name, _ in names_and_papers)
        if len(unique_names) > 1:
            names_str = ", ".join(f"'{name}'" for name in unique_names)
            papers_str = ", ".join(f"#{pid}" for _, pid in names_and_papers)
            issues.append(ValidationIssue(
                severity="warning",
                category="name_consistency",
                message=f"Same email '{email}' used with different names: {names_str} (likely typo)",
                details={"email": email, "names": list(unique_names), "papers": papers_str}
            ))

    # Check 2: Same name, different emails (OFTEN LEGITIMATE - flag as info only)
    name_to_emails = {}
    for author, paper_id in all_authors:
        full_name = author.full_name
        if author.email:
            if full_name not in name_to_emails:
                name_to_emails[full_name] = []
            name_to_emails[full_name].append((author.email, paper_id, author.affiliation))

    for name, emails_and_data in name_to_emails.items():
        unique_emails = set(email for email, _, _ in emails_and_data)
        if len(unique_emails) > 1:
            emails_str = ", ".join(f"'{email}'" for email in unique_emails)
            # Show affiliations to help determine if this is legitimate
            aff_info = {}
            for email, paper_id, affiliation in emails_and_data:
                if email not in aff_info:
                    aff_info[email] = affiliation if affiliation else "(no affiliation)"
            aff_str = ", ".join(f"{email} ({aff})" for email, aff in aff_info.items())

            issues.append(ValidationIssue(
                severity="info",
                category="email_consistency",
                message=f"Same name '{name}' used with different emails: {aff_str} (often legitimate)",
                details={"name": name, "emails": list(unique_emails), "context": "Multiple emails can be legitimate if author changed institutions or uses different addresses"}
            ))

    # Note: We do NOT flag different affiliations - this is completely legitimate!
    # Authors often change institutions between papers or have multiple affiliations.

    return issues


def validate_proceedings_export(export: ProceedingsExport) -> ProceedingsExport:
    """
    Run comprehensive validation on a ProceedingsExport.

    Args:
        export: ProceedingsExport to validate

    Returns:
        Same export with validation issues added
    """
    # Update statistics
    export.update_statistics()

    # Check for author name consistency
    consistency_issues = validate_author_name_consistency(export)
    export.validation_issues.extend(consistency_issues)

    # Check for papers with missing data
    for track in export.tracks:
        for paper in track.papers:
            if paper.has_missing_affiliations:
                export.add_issue(
                    "warning",
                    "missing_affiliation",
                    "Paper has at least one author with missing affiliation",
                    paper_id=paper.submission_id
                )

            if paper.has_missing_emails:
                export.add_issue(
                    "warning",
                    "missing_email",
                    "Paper has at least one author with missing email",
                    paper_id=paper.submission_id
                )

    return export
