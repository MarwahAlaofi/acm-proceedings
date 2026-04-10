"""
Pydantic Model Validation Tests
================================

This script demonstrates and tests the runtime validation capabilities
of the Pydantic models used in the EasyChair converter.

Usage:
    python test_pydantic_validation.py
"""

from easychair_models import Author, Paper, Track, ProceedingsExport, ValidationIssue
from pydantic import ValidationError
import sys


def test_author_validation():
    """Test Author model validation."""
    print("=" * 80)
    print("Testing Author Validation")
    print("=" * 80)

    # Valid author
    print("\n✓ Creating valid author...")
    try:
        author = Author(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            affiliation="University of Example",
            country="USA"
        )
        print(f"  Success: {author.full_name} ({author.email})")
    except ValidationError as e:
        print(f"  ✗ Failed: {e}")
        return False

    # Empty name (should fail)
    print("\n✗ Testing empty first name (should fail)...")
    try:
        author = Author(
            first_name="",
            last_name="Doe",
            email="john.doe@example.com"
        )
        print("  ✗ Should have failed but didn't!")
        return False
    except ValidationError as e:
        print(f"  ✓ Correctly rejected: {e.errors()[0]['msg']}")

    # Invalid email (should fail)
    print("\n✗ Testing invalid email format (should fail)...")
    try:
        author = Author(
            first_name="John",
            last_name="Doe",
            email="not-an-email"
        )
        print("  ✗ Should have failed but didn't!")
        return False
    except ValidationError as e:
        print(f"  ✓ Correctly rejected: {e.errors()[0]['msg']}")

    # Optional fields can be None
    print("\n✓ Testing author with minimal fields...")
    try:
        author = Author(
            first_name="Jane",
            last_name="Smith"
        )
        print(f"  Success: {author.full_name} (no email/affiliation)")
    except ValidationError as e:
        print(f"  ✗ Failed: {e}")
        return False

    print("\n" + "=" * 80)
    print("✓ All Author validation tests passed!")
    print("=" * 80)
    return True


def test_paper_validation():
    """Test Paper model validation."""
    print("\n" + "=" * 80)
    print("Testing Paper Validation")
    print("=" * 80)

    # Create valid authors
    author1 = Author(first_name="John", last_name="Doe", email="john@example.com")
    author2 = Author(first_name="Jane", last_name="Smith", email="jane@example.com")

    # Valid paper
    print("\n✓ Creating valid paper...")
    try:
        paper = Paper(
            submission_id=123,
            title="A Great Paper",
            authors=[author1, author2],
            track_name="Full Papers Track",
            section_name="Full Research Paper",
            paper_type="Full Research Paper"
        )
        print(f"  Success: Paper #{paper.submission_id} with {paper.author_count} authors")
        print(f"  Title: {paper.title}")
        print(f"  Corresponding: {paper.corresponding_authors[0].full_name}")
    except ValidationError as e:
        print(f"  ✗ Failed: {e}")
        return False

    # Paper with no authors (should fail)
    print("\n✗ Testing paper with no authors (should fail)...")
    try:
        paper = Paper(
            submission_id=124,
            title="Bad Paper",
            authors=[],
            track_name="Track",
            section_name="Section",
            paper_type="Type"
        )
        print("  ✗ Should have failed but didn't!")
        return False
    except ValidationError as e:
        print(f"  ✓ Correctly rejected: {e.errors()[0]['msg']}")

    # Empty title (should fail)
    print("\n✗ Testing paper with empty title (should fail)...")
    try:
        paper = Paper(
            submission_id=125,
            title="",
            authors=[author1],
            track_name="Track",
            section_name="Section",
            paper_type="Type"
        )
        print("  ✗ Should have failed but didn't!")
        return False
    except ValidationError as e:
        print(f"  ✓ Correctly rejected: {e.errors()[0]['msg']}")

    # Auto-set corresponding author
    print("\n✓ Testing auto-corresponding author (first author)...")
    try:
        paper = Paper(
            submission_id=126,
            title="Test Paper",
            authors=[
                Author(first_name="A", last_name="Author", is_corresponding=False),
                Author(first_name="B", last_name="Author", is_corresponding=False)
            ],
            track_name="Track",
            section_name="Section",
            paper_type="Type"
        )
        if paper.corresponding_authors[0].last_name == "Author":
            print(f"  Success: First author automatically set as corresponding")
        else:
            print(f"  ✗ Failed: Corresponding not set correctly")
            return False
    except ValidationError as e:
        print(f"  ✗ Failed: {e}")
        return False

    print("\n" + "=" * 80)
    print("✓ All Paper validation tests passed!")
    print("=" * 80)
    return True


def test_proceedings_validation():
    """Test ProceedingsExport validation."""
    print("\n" + "=" * 80)
    print("Testing ProceedingsExport Validation")
    print("=" * 80)

    # Create valid export
    print("\n✓ Creating proceedings export...")
    export = ProceedingsExport(
        proceeding_id="2026-TEST",
        conference_name="TEST 2026"
    )

    # Add validation issues
    print("\n✓ Adding validation issues...")
    export.add_issue(
        "warning",
        "test_category",
        "This is a test warning",
        paper_id=123
    )

    export.add_issue(
        "error",
        "test_category",
        "This is a test error",
        paper_id=124,
        author_name="Test Author"
    )

    print(f"  Total issues: {len(export.validation_issues)}")
    print(f"  Errors: {export.error_count}")
    print(f"  Warnings: {export.warning_count}")
    print(f"  Has errors: {export.has_errors}")
    print(f"  Has warnings: {export.has_warnings}")

    if export.error_count == 1 and export.warning_count == 1:
        print(f"  ✓ Issue tracking works correctly")
    else:
        print(f"  ✗ Issue tracking failed")
        return False

    # Test statistics
    print("\n✓ Testing statistics...")
    author1 = Author(first_name="John", last_name="Doe", email="john@example.com")
    author2 = Author(first_name="Jane", last_name="Smith", email="jane@example.com")
    author3 = Author(first_name="John", last_name="Doe", email="john@example.com")  # Duplicate

    paper1 = Paper(
        submission_id=1,
        title="Paper 1",
        authors=[author1, author2],
        track_name="Track A",
        section_name="Section A",
        paper_type="Type A"
    )

    paper2 = Paper(
        submission_id=2,
        title="Paper 2",
        authors=[author3],  # Same person as author1
        track_name="Track A",
        section_name="Section A",
        paper_type="Type A"
    )

    track = Track(
        original_name="Track A Original",
        section_name="Section A",
        papers=[paper1, paper2]
    )

    export.tracks.append(track)
    export.update_statistics()

    print(f"  Total papers: {export.total_papers}")
    print(f"  Total author entries: {export.total_authors}")
    print(f"  Unique authors: {export.unique_authors}")

    if export.total_papers == 2 and export.total_authors == 3 and export.unique_authors == 2:
        print(f"  ✓ Statistics calculated correctly")
    else:
        print(f"  ✗ Statistics incorrect")
        return False

    print("\n" + "=" * 80)
    print("✓ All ProceedingsExport validation tests passed!")
    print("=" * 80)
    return True


def main():
    """Run all validation tests."""
    print("\n" + "=" * 80)
    print("PYDANTIC MODEL VALIDATION TEST SUITE")
    print("=" * 80)
    print()

    results = []
    results.append(("Author Validation", test_author_validation()))
    results.append(("Paper Validation", test_paper_validation()))
    results.append(("ProceedingsExport Validation", test_proceedings_validation()))

    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)

    all_passed = True
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 80)

    if all_passed:
        print("\n🎉 All validation tests passed!")
        return 0
    else:
        print("\n❌ Some validation tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
