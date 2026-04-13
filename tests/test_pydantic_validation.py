"""
Pydantic Model Validation Tests
================================

This script demonstrates and tests the runtime validation capabilities
of the Pydantic models used in the EasyChair converter.

Usage:
    python tests/test_pydantic_validation.py
    (Run from project root directory)
"""

import sys
import os

# Add parent directory to path so we can import from lib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.easychair_models import Author, Paper, Track, ProceedingsExport, ValidationIssue
from pydantic import ValidationError


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

    # Test contact author priority 1: First corresponding with valid email
    print("\n✓ Testing contact author priority 1 (first corresponding with valid email)...")
    try:
        paper = Paper(
            submission_id=127,
            title="Priority 1 Test",
            authors=[
                Author(first_name="A", last_name="First", email="a@example.com", is_corresponding=False),
                Author(first_name="B", last_name="Second", email="b@example.com", is_corresponding=True),
                Author(first_name="C", last_name="Third", email="c@example.com", is_corresponding=True)
            ],
            track_name="Track",
            section_name="Section",
            paper_type="Type"
        )
        # Should select first corresponding with email (B)
        if len(paper.corresponding_authors) == 1 and paper.corresponding_authors[0].last_name == "Second":
            print(f"  Success: First corresponding author with email selected as contact")
        else:
            print(f"  ✗ Failed: Wrong author selected or multiple contact authors")
            return False
    except ValidationError as e:
        print(f"  ✗ Failed: {e}")
        return False

    # Test contact author priority 2: First author with valid email (no corresponding marked)
    print("\n✓ Testing contact author priority 2 (first author with valid email)...")
    try:
        paper = Paper(
            submission_id=128,
            title="Priority 2 Test",
            authors=[
                Author(first_name="A", last_name="First", is_corresponding=False),  # No email
                Author(first_name="B", last_name="Second", email="b@example.com", is_corresponding=False),
                Author(first_name="C", last_name="Third", email="c@example.com", is_corresponding=False)
            ],
            track_name="Track",
            section_name="Section",
            paper_type="Type"
        )
        # Should select first author with valid email (B)
        if len(paper.corresponding_authors) == 1 and paper.corresponding_authors[0].last_name == "Second":
            print(f"  Success: First author with valid email selected as contact")
        else:
            print(f"  ✗ Failed: Wrong author selected or multiple contact authors")
            return False
    except ValidationError as e:
        print(f"  ✗ Failed: {e}")
        return False

    # Test contact author priority 3: First author (no valid emails)
    print("\n✓ Testing contact author priority 3 (first author fallback)...")
    try:
        paper = Paper(
            submission_id=129,
            title="Priority 3 Test",
            authors=[
                Author(first_name="A", last_name="First", is_corresponding=False),  # No email
                Author(first_name="B", last_name="Second", is_corresponding=False)   # No email
            ],
            track_name="Track",
            section_name="Section",
            paper_type="Type"
        )
        # Should select first author even without email (A)
        if len(paper.corresponding_authors) == 1 and paper.corresponding_authors[0].last_name == "First":
            print(f"  Success: First author selected as contact (fallback)")
        else:
            print(f"  ✗ Failed: Wrong author selected or multiple contact authors")
            return False
    except ValidationError as e:
        print(f"  ✗ Failed: {e}")
        return False

    # Test exactly one contact author (corresponding marked but no valid email)
    print("\n✓ Testing exactly one contact author (corresponding without email uses priority 2)...")
    try:
        paper = Paper(
            submission_id=130,
            title="One Contact Test",
            authors=[
                Author(first_name="A", last_name="First", email="a@example.com", is_corresponding=False),
                Author(first_name="B", last_name="Second", is_corresponding=True)  # Marked but no email
            ],
            track_name="Track",
            section_name="Section",
            paper_type="Type"
        )
        # Should select first author with valid email (A), not the marked corresponding without email
        if len(paper.corresponding_authors) == 1 and paper.corresponding_authors[0].last_name == "First":
            print(f"  Success: Only one contact author (first with valid email)")
        else:
            print(f"  ✗ Failed: Wrong number of contact authors or wrong author selected")
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


def test_different_affiliations_across_papers():
    """Test that authors can have different affiliations for different papers."""
    print("\n" + "=" * 80)
    print("Testing Different Affiliations Across Papers")
    print("=" * 80)

    # Same author with different affiliations in different papers
    print("\n✓ Testing author with different affiliations across papers...")
    author1_paper1 = Author(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        affiliation="MIT",
        country="USA"
    )

    author1_paper2 = Author(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        affiliation="Stanford",
        country="USA"
    )

    paper1 = Paper(
        submission_id=1,
        title="Paper at MIT",
        authors=[author1_paper1],
        track_name="Track",
        section_name="Section",
        paper_type="Type"
    )

    paper2 = Paper(
        submission_id=2,
        title="Paper at Stanford",
        authors=[author1_paper2],
        track_name="Track",
        section_name="Section",
        paper_type="Type"
    )

    print(f"  Paper 1: {author1_paper1.full_name} - {author1_paper1.affiliation}")
    print(f"  Paper 2: {author1_paper2.full_name} - {author1_paper2.affiliation}")
    print(f"  ✓ Both affiliations preserved (legitimate institution change)")

    # Test that validation doesn't flag this as an error
    export = ProceedingsExport()
    track = Track(
        original_name="Track",
        section_name="Section",
        papers=[paper1, paper2]
    )
    export.tracks.append(track)

    from lib.easychair_models import validate_author_name_consistency
    issues = validate_author_name_consistency(export)

    # Should have at most an INFO level notice, not a WARNING or ERROR
    errors_warnings = [i for i in issues if i.severity in ["error", "warning"]]
    if errors_warnings:
        print(f"  ✗ Incorrectly flagged different affiliations as error/warning:")
        for issue in errors_warnings:
            print(f"    {issue}")
        return False

    print(f"  ✓ Validation correctly allows different affiliations per paper")

    # Test different emails too
    print("\n✓ Testing author with different emails across papers...")
    author2_paper1 = Author(
        first_name="Jane",
        last_name="Smith",
        email="jane@mit.edu",
        affiliation="MIT"
    )

    author2_paper2 = Author(
        first_name="Jane",
        last_name="Smith",
        email="jane@stanford.edu",
        affiliation="Stanford"
    )

    paper3 = Paper(
        submission_id=3,
        title="Paper A",
        authors=[author2_paper1],
        track_name="Track",
        section_name="Section",
        paper_type="Type"
    )

    paper4 = Paper(
        submission_id=4,
        title="Paper B",
        authors=[author2_paper2],
        track_name="Track",
        section_name="Section",
        paper_type="Type"
    )

    export2 = ProceedingsExport()
    track2 = Track(
        original_name="Track",
        section_name="Section",
        papers=[paper3, paper4]
    )
    export2.tracks.append(track2)

    issues2 = validate_author_name_consistency(export2)

    # Should have at most INFO level, not ERROR
    errors = [i for i in issues2 if i.severity == "error"]
    if errors:
        print(f"  ✗ Incorrectly flagged different emails as error")
        return False

    # Info notices are OK
    info_notices = [i for i in issues2 if i.severity == "info"]
    print(f"  ✓ Validation allows different emails ({len(info_notices)} info notice)")

    print("\n" + "=" * 80)
    print("✓ All different affiliations/emails tests passed!")
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
    results.append(("Different Affiliations Across Papers", test_different_affiliations_across_papers()))

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
